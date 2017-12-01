#!/usr/bin/env python
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be
"""
Full pipeline starting from BaseSpace fastq project
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits
from plumbum import local
import pandas as pd

## Luigi dummy file target dir
#luigitempdir = tempfile.mkdtemp(prefix=os.environ.get('TMPDIR','/tmp/')+'luigi',suffix='/')

## Default settings
defaultMappings = {}

## Tasks
class setupProject(luigi.Task):
    """
    setupProject prepares the logistics for running the pipeline and directories for the results
    optionally, the metadata can already be provided here that is necessary for e.g. differential expression analysis
    """
    project = luigi.Parameter(description='name of the project')
    datadir = luigi.Parameter(description='directory that contains data in project folders')
    defaultMappings['metafile'] = ''
    metafile = luigi.Parameter(defaultMappings['metafile'], description='metadata file for interpreting results')
    
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/plumbing'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/summaries'.format(self.datadir,self.project))
        )

    def run(self):
        os.mkdir(self.output()[0].path)
        if self.metafile:
            from shutil import copyfile
            os.mkdir(self.output()[0].path+'/metadata')
            copyfile(self.metafile,self.output()[0].path+'/metadata/')
        os.mkdir(self.output()[1].path)
        os.mkdir(self.output()[2].path)

@inherits(setupProject)
class basespaceData(luigi.Task):
    """
    downloads the data from Illumina Basespace with cmgg provided python downloader
    the task is completed when a datadir folder exists with the project name
    so if you do not need to download it, just manually put the data in the datadir
    with the project name
    """
    NSQrun = luigi.Parameter(description='sequencing run name')
    BASESPACE_API_TOKEN = (
        luigi.Parameter(os.environ.get('BASESPACE_API_TOKEN'),description='$BASESPACE_API_TOKEN') if os.environ.get('BASESPACE_API_TOKEN')
        else luigi.Parameter(description='$BASESPACE_API_TOKEN')
    )

    def requires(self):
        return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/{}'.format(self.datadir,self.project))

    def run(self):
        (local['BaseSpaceRunDownloader.py'] > '{}/../results/{}/plumbing/download.log'.format(self.datadir,self.project))(
            '-p', self.NSQrun, '-a', self.BASESPACE_API_TOKEN, '-d', self.datadir
        )
        #Renaming download dir simply to project name
        downloadedName = glob.glob('{}/{}*'.format(self.datadir,self.NSQrun))
        if len(downloadedName) != 1: raise Exception('Something went wrong downloading',self.NSQrun)
        else: os.rename(downloadedName[0],'{}/{}'.format(self.datadir,self.project))

@inherits(basespaceData)
class mergeFASTQs(luigi.Task):
    """
    Merge fastqs if one sample contains more than one fastq
    """
    defaultMappings['dirstructure'] = 'multidir'
    dirstructure = luigi.Parameter(default=defaultMappings['dirstructure'],
                                   description='dirstructure of datatdir: onedir or multidir')
    
    def requires(self):
        return self.clone_parent() #or self.clone(basespaceData)
        
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/plumbing/{}.log'.format(self.datadir,self.project,self.task_family))
        )

    def run(self):
        if self.dirstructure == 'multidir':
            outdir = '{}/../results/{}/fastqs/'.format(self.datadir,self.project)
            os.mkdir(outdir)
            dirsFASTQs = local['ls']('{}/{}'.format(self.datadir,self.project)).split()
            for d in dirsFASTQs:
                (local['ls'] >> (self.output()[1].path))('-lh','{}/{}/{}'.format(self.datadir,self.project,d))
                (local['cat'] > outdir+d+'.fastq.gz')(
                    *glob.glob('{}/{}/{}/*.fastq.gz'.format(self.datadir,self.project,d))
                )
            os.rename('{}/{}'.format(self.datadir,self.project),'{}/{}_original_FASTQs'.format(self.datadir,self.project))
            os.symlink(outdir,'{}/{}'.format(self.datadir,self.project), target_is_directory = True)
        pathlib.Path(self.output()[0].path).touch()

@inherits(mergeFASTQs)
class qualityCheck(luigi.Task):
    """
    Runs fastqc on all samples and makes an overall summary
    """
    def requires(self):
        return self.clone_parent()
        
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/QCresults'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/summaries/qcsummary.csv'.format(self.datadir,self.project))
        )

    def run(self):
        import zipfile
        from io import TextIOWrapper
        
        local['qualitycheck.sh'](self.project, self.datadir)
        qclines = []
        for fqcfile in glob.glob(self.output()[1].path+'/*.zip'):
            zf = zipfile.ZipFile(fqcfile)
            with zf.open(fqcfile[fqcfile.rindex('/')+1:-4]+'/summary.txt') as f:
                ft = TextIOWrapper(f)
                summ = pd.read_csv(TextIOWrapper(f),sep='\t',header=None)
                qclines.append(summ[2].ix[0]+'\t'+'\t'.join(list(summ[0]))+'\n')
        with self.output()[2].open('w') as outfile:
            outfile.writelines(['\t'+'\t'.join(list(summ[1]))+'\n']+qclines)
        pathlib.Path(self.output()[0].path).touch()

@inherits(qualityCheck)
class alignTask(luigi.Task):
    """
    Align reads to genome with STAR
    """
    defaultMappings['suffix'] = ''
    suffix = luigi.Parameter(default=defaultMappings['suffix'],description='use when preparing for xenome filtering')
    defaultMappings['genome'] = 'RSEMgenomeGRCg38'
    genome = luigi.Parameter(default=defaultMappings['genome'],
                             description='reference genome to use')
    defaultMappings['pairedEnd'] = False
    pairedEnd = luigi.BoolParameter(default=defaultMappings['pairedEnd'],
                               description='paired end sequencing reads')

    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/alignmentResults'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/summaries/STARcounts.csv'.format(self.datadir,self.project))
        )

    def run(self):
        local['STARaligning.sh'](self.project, self.datadir, self.suffix, self.genome, self.pairedEnd)

        #Process STAR counts
        amb = []
        counts = []
        amb_annot = counts_annot = None
        samples = []
        for dir in glob.glob(self.output()[1].path+'/*'):
            f = open(dir+'/ReadsPerGene.out.tab')
            f = f.readlines()
            amb.append([int(l.split()[1]) for l in f[:4]])
            if not amb_annot: amb_annot = [l.split()[0] for l in f[:4]]
            f = f[4:]
            if not counts_annot: counts_annot = [l.split()[0] for l in f]
            else:
                assert counts_annot == [l.split()[0] for l in f]
            counts.append([int(l.split()[1]) for l in f])
            samples.append(dir[dir.rindex('/')+1:])
        # Alignment summary file
        counts_df = pd.DataFrame(counts,columns=counts_annot,index=samples).transpose()
        counts_df.to_csv(self.output()[2].path)
        # Check point
        pathlib.Path(self.output()[0].path).touch()
    
@inherits(alignTask)
class countTask(luigi.Task):
    """
    Recount reads with RSEM
    """
    defaultMappings['forwardprob'] = 0.5
    forwardprob = luigi.FloatParameter(default=defaultMappings['forwardprob'],
                                       description='stranded seguencing [0 for illumina stranded], or non stranded [0.5]')
    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/countResults'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/summaries/RSEMcounts.csv'.format(self.datadir,self.project))
        )

    def run(self):
        local['RSEMcounts.sh'](self.project, self.datadir, self.genome+'/human_ensembl', self.forwardprob, self.pairedEnd)
        # Process RSEM counts
        counts = {}
        samples = []
        for gfile in glob.glob(self.output()[1].path+'/*.genes.results'):
            sdf = pd.read_table(gfile,index_col=0)
            counts[gfile[gfile.rindex('/')+1:-14]] = sdf.expected_count

        # Counts summary file
        counts_df = pd.DataFrame(counts)
        counts_df.to_csv(self.output()[2].path)
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@inherits(countTask)
class diffexpTask(luigi.Task):
    defaultMappings['design'] = ''
    design = luigi.Parameter(defaultMappings['design'],
                             description='model design for differential expression analysis')
    
    def requires(self):
        return self.clone_parent()
    
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/summaries/DEexpression.csv'.format(self.datadir,self.project))
        )

    def run(self):
        with local.env(R_MODULE="SET"):
            local['simpleDEvoom.R'](self.project, self.datadir, self.metafile, self.design)
        pathlib.Path(self.output()[0].path).touch()

@inherits(diffexpTask)
class RNAseqWorkflow(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(basespaceData)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(alignTask)
        yield self.clone(countTask)
        if self.design: yield self.clone(diffexpTask)
        
if __name__ == '__main__':
    import argparse

    typeMapping = {
        luigi.parameter.Parameter: str,
        luigi.parameter.BoolParameter: bool,
        luigi.parameter.FloatParameter: float
    }
    
    parser = argparse.ArgumentParser(description='RNAseq processing pipeline.')
    # if arguments are set in environment, they are used as the argument default values
    # this allows seemless integration with PBS jobs
    for paran,param in RNAseqWorkflow.get_params():
        if paran in defaultMappings:
            parser.add_argument('--'+paran, default=defaultMappings[paran], type=typeMapping[type(param)], help=param.description)
        else: parser.add_argument('--'+paran, type=typeMapping[type(param)], help=param.description)
        
    if 'GENAIRICS_ENV_ARGS' in os.environ:
        #For testing:
        # os.environ.setdefault('datadir','testdir')
        # os.environ.setdefault('NSQrun','testrun')

        #Retrieve arguments from qsub job environment
        args = []
        for paran,param in RNAseqWorkflow.get_params():
            if paran in os.environ:
                args += ['--'+paran, os.environ[paran]]
        args = parser.parse_args(args)
        print('Arguments retrieved from environment:',args)
    else:
        #Script started directly
        args = parser.parse_args()

    workflow = RNAseqWorkflow(**vars(args))
    print(workflow)
    for task in workflow.requires():
        print(datetime.now(),task.task_family)
        if task.complete(): print('Task finished previously')
        else: task.run()

    #print('[re]move ',luigitempdir)
