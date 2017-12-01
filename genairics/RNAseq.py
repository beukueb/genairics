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
class basespaceData(luigi.Task):
    datadir = luigi.Parameter(description='directory that contains data in project folders')
    NSQrun = luigi.Parameter(description='project name')
    apitoken = (
        luigi.Parameter(os.environ.get('BASESPACE_API_TOKEN'),description='$BASESPACE_API_TOKEN') if os.environ.get('BASESPACE_API_TOKEN')
        else luigi.Parameter(description='$BASESPACE_API_TOKEN')
    )

    # Set up temporary dummy output file
    # for every initiated task a new dummy is set up
    # this ensures that every new workflow run, will exectute all tasks
    def output(self):
        return luigi.LocalTarget('{}/../results/{}/plumbing/1_downloadCompleted'.format(self.datadir,self.NSQrun))

    def run(self):
        local['BaseSpaceRunDownloader.py']('-p', self.NSQrun, '-a', self.apitoken, '-d', self.datadir)
        #Renaming download dir simply to project name
        downloadedName = glob.glob('{}/{}*'.format(self.datadir,self.NSQrun))
        if len(downloadedName) != 1: raise Exception('Something went wrong downloading',self.NSQrun)
        else: os.rename(downloadedName[0],'{}/{}'.format(self.datadir,self.NSQrun))
        os.mkdir('{}/../results/{}'.format(self.datadir,self.NSQrun))
        os.mkdir('{}/../results/{}/plumbing'.format(self.datadir,self.NSQrun))
        os.mkdir('{}/../results/{}/summaries'.format(self.datadir,self.NSQrun))
        pathlib.Path(self.output().path).touch()

@inherits(basespaceData)
class mergeFASTQs(luigi.Task):
    """
    Merge fastqs if one sample contains more than one fastq
    """
    dirstructure = luigi.Parameter(default='multidir',
                                   description='dirstructure of datatdir: onedir or multidir')
    defaultMappings['dirstructure'] = 'multidir'
    
    def requires(self):
        return self.clone_parent() #or self.clone(basespaceData)
        
    def output(self):
        return luigi.LocalTarget('{}/../results/{}/plumbing/2_mergeFASTQs'.format(self.datadir,self.NSQrun))

    def run(self):
        if self.dirstructure == 'multidir':
            outdir = '{}/../results/{}/fastqs/'.format(self.datadir,self.NSQrun)
            os.mkdir(outdir)
            dirsFASTQs = local['ls']('{}/{}'.format(self.datadir,self.NSQrun)).split()
            for d in dirsFASTQs:
                (local['ls'] >> (self.output().path + '_log'))('-lh','{}/{}/{}'.format(self.datadir,self.NSQrun,d))
                (local['cat'] > outdir+d+'.fastq.gz')(
                    *glob.glob('{}/{}/{}/*.fastq.gz'.format(self.datadir,self.NSQrun,d))
                )
            os.rename('{}/{}'.format(self.datadir,self.NSQrun),'{}/{}_original_FASTQs'.format(self.datadir,self.NSQrun))
            os.symlink(outdir,'{}/{}'.format(self.datadir,self.NSQrun), target_is_directory = True)
        pathlib.Path(self.output().path).touch()

@inherits(mergeFASTQs)
class qualityCheck(luigi.Task):

    def requires(self):
        return self.clone_parent()
        
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/3_{}_completed'.format(self.datadir,self.NSQrun,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/QCresults'.format(self.datadir,self.NSQrun)),
            luigi.LocalTarget('{}/../results/{}/summaries/qcsummary.csv'.format(self.datadir,self.NSQrun))
        )

    def run(self):
        import zipfile
        from io import TextIOWrapper
        
        local['qualitycheck.sh'](self.NSQrun, self.datadir)
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
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')
    defaultMappings['suffix'] = ''
    genome = luigi.Parameter(default='RSEMgenomeGRCg38',
                             description='reference genome to use')
    defaultMappings['genome'] = 'RSEMgenomeGRCg38'
    pairedEnd = luigi.BoolParameter(default=False,
                               description='paired end sequencing reads')

    defaultMappings['pairedEnd'] = False
    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/4_{}_completed'.format(self.datadir,self.NSQrun,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/alignmentResults'.format(self.datadir,self.NSQrun)),
            luigi.LocalTarget('{}/../results/{}/summaries/STARcounts.csv'.format(self.datadir,self.NSQrun))
        )

    def run(self):
        local['STARaligning.sh'](self.NSQrun, self.datadir, self.suffix, self.genome, self.pairedEnd)

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
    forwardprob = luigi.FloatParameter(default=0.5,
                                       description='stranded seguencing [0 for illumina stranded], or non stranded [0.5]')
    defaultMappings['forwardprob'] = 0.5
    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/5_{}_completed'.format(self.datadir,self.NSQrun,self.task_family)),
            luigi.LocalTarget('{}/../results/{}/countResults'.format(self.datadir,self.NSQrun)),
            luigi.LocalTarget('{}/../results/{}/summaries/RSEMcounts.csv'.format(self.datadir,self.NSQrun))
        )

    def run(self):
        local['RSEMcounts.sh'](self.NSQrun, self.datadir, self.genome+'/human_ensembl', self.forwardprob, self.pairedEnd)
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
    design = luigi.Parameter(description='model design for differential expression analysis')
    
    def requires(self):
        return self.clone_parent()
    
    def output(self):
        return luigi.LocalTarget('{}/../results/{}/plumbing/6_{}_completed'.format(self.datadir,self.NSQrun,self.task_family))

    def run(self):
        local['simpleDEvoom.R'](self.NSQrun, self.datadir, self.design)
        pathlib.Path(self.output().path).touch()

@inherits(countTask)
class RNAseqWorkflow(luigi.WrapperTask):
    def requires(self):
        yield self.clone(basespaceData)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(alignTask)
        yield self.clone(countTask)
        
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
                args += ['--'+paran, os.environ['paran']]
        args = parser.parse_args(' '.join(args))
        print('Arguments retrieved from environment:',args)
    else:
        #Script started directly
        args = parser.parse_args()

    workflow = RNAseqWorkflow(**vars(args))
    print(workflow)
    for task in workflow.requires():
        print(datetime.now(),task)
        if task.complete(): print('Task finished previously')
        else: task.run()

    #print('[re]move ',luigitempdir)
