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
from plumbum import local, colors
import pandas as pd

# matplotlib => setup for exporting svg figures only
import matplotlib
matplotlib.use('SVG')
import matplotlib.pyplot as plt

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
            luigi.LocalTarget('{}/../results/{}/summaries'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/plumbing/pipeline.log'.format(self.datadir,self.project))
        )

    def run(self):
        os.mkdir(self.output()[0].path)
        os.mkdir(self.output()[0].path+'/metadata')
        if self.metafile:
            from shutil import copyfile
            copyfile(self.metafile,self.output()[0].path+'/metadata/')
        os.mkdir(self.output()[1].path)
        os.mkdir(self.output()[2].path)

@inherits(setupProject)
class setupLogging(luigi.Task):
    """
    Registers the logging file
    Always needs to run, to enable logging to the file
    """

    def requires(self):
        return self.clone_parent()

    def run(self):
        import logging
        logger = logging.getLogger(__name__)
        logfile = logging.FileHandler(self.requires().output()[3].path)
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(
            logging.Formatter('{asctime} {name} {levelname:8s} {message}', style='{')
        )
        logger.addHandler(logfile)
    
@inherits(setupProject)
class basespaceData(luigi.Task):
    """
    downloads the data from Illumina Basespace with cmgg provided python downloader
    the task is completed when a datadir folder exists with the project name
    so if you do not need to download it, just manually put the data in the datadir
    with the project name
    """
    defaultMappings['NSQrun'] = ''
    NSQrun = luigi.Parameter(defaultMappings['NSQrun'],description='sequencing run name')
    BASESPACE_API_TOKEN = (
        luigi.Parameter(os.environ.get('BASESPACE_API_TOKEN'),description='$BASESPACE_API_TOKEN',significant=False) if os.environ.get('BASESPACE_API_TOKEN')
        else luigi.Parameter(description='$BASESPACE_API_TOKEN',significant=False)
    )

    def requires(self):
        return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/{}'.format(self.datadir,self.project))

    def run(self):
        if not self.NSQrun:
            print(colors.cyan | 'NSQrun not provided and therefore set to project name ' + self.project)
            self.NSQrun = self.project
        (local['BaseSpaceRunDownloader.py'] > '{}/../results/{}/plumbing/download.log'.format(self.datadir,self.project))(
            '-p', self.NSQrun, '-a', self.BASESPACE_API_TOKEN, '-d', self.datadir
        )
        #Renaming download dir simply to project name
        downloadedName = glob.glob('{}/{}*'.format(self.datadir,self.NSQrun))
        if len(downloadedName) != 1: raise Exception('Something went wrong downloading',self.NSQrun)
        else: os.rename(downloadedName[0],self.output().path)

@inherits(setupProject)
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

@inherits(mergeFASTQs)
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
        if not self.metafile:
            samples = glob.glob('{}/../results/{}/alignmentResults/*'.format(self.datadir,self.project))
            samples = pd.DataFrame(
                {'bam_location':samples,
                 'alignment_dir_size':[local['du']['-sh'](s).split('\t')[0] for s in samples]},
                index = [os.path.basename(s) for s in samples]
            )
            metafile = '{}/../results/{}/metadata/samples.csv'.format(self.datadir,self.project)
            samples.to_csv(metafile)
            raise Exception( colors.red |
                '''
                metafile needs to be provided to run DE analysis
                a template file has been generated for you ({})
                adjust file to match your design, add the above file path
                as input "metafile" for the pipeline and rerun
                '''.format(metafile)
            )
        with local.env(R_MODULE="SET"):
            local['bash'][
                '-i','-c', ' '.join(
                    ['Rscript', local['which']('simpleDEvoom.R').strip(),
                     self.project, self.datadir, self.metafile, self.design]
                )]()
        pathlib.Path(self.output()[0].path).touch()

@inherits(basespaceData)
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
    import argparse, logging

    # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logconsole = logging.StreamHandler()
    logconsole.setLevel(logging.ERROR)
    logger.addHandler(logconsole)
    
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
        logger.info('Arguments were retrieved from environment')
    else:
        #Script started directly
        args = parser.parse_args()


    # Workflow
    workflow = RNAseqWorkflow(**vars(args))
    workflow.clone(setupLogging).run()
    logger.info(workflow)
    for task in workflow.requires():
        logger.info(colors.underline | task.task_family)
        if task.complete(): logger.info(colors.green | 'Task finished previously')
        else: task.run()

    #print('[re]move ',luigitempdir)
