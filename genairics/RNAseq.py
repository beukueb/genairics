#!/bin/env python
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be
"""
Full pipeline starting from BaseSpace fastq project
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits
from plumbum import local

## Luigi dummy file target dir
ldft = tempfile.mkdtemp(prefix='/tmp/luigi',suffix='/')

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
    def __init__(self,*args,**kwargs):
        self.tmpdir = tempfile.mkdtemp(prefix=ldft)
        super().__init__(*args,**kwargs)

    def output(self):
        return luigi.LocalTarget(self.tmpdir+'/success')

    def run(self):
        local['BaseSpaceRunDownloader.py']('-p',self.NSQrun,'-a', self.apitoken)
        pathlib.Path(self.output().path).touch()
    
@inherits(basespaceData)
class qualityCheck(ExternalProgramTask):
    dirstructure = luigi.Parameter(default='multidir',
                                   description='dirstructure of datatdir: onedir or multidir')

    def requires(self):
        return basespaceData()
        
    def __init__(self,*args,**kwargs):
        self.tmpdir = tempfile.mkdtemp(prefix=ldft)
        super().__init__(*args,**kwargs)

    def output(self):
        return luigi.LocalTarget(self.tmpdir+'/success')

    def run(self):
        local['qualitycheck.sh'](self.NSQrun, self.dirstructure, self.datadir)
        pathlib.Path(self.output().path).touch()

@inherits(qualityCheck)
class alignTask(ExternalProgramTask):
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')
    genome = luigi.Parameter(default='RSEMgenomeGRCg38/human_ensembl',
                             description='reference genome to use')

    def requires(self):
        return qualityCheck()
    
    def __init__(self,*args,**kwargs):
        self.tmpdir = tempfile.mkdtemp(prefix=ldft)
        super().__init__(*args,**kwargs)

    def output(self):
        return luigi.LocalTarget(self.tmpdir+'/success')

    def run(self):
        local['STARaligning.py'](self.NSQrun, self.dirstructure, self.datadir, self.suffix, self.genome)
        pathlib.Path(self.output().path).touch()
    
@inherits(alignTask)
class countTask(ExternalProgramTask):
    forwardprob = luigi.FloatParameter(default=0.5,
                                       description='stranded seguencing [0 for illumina stranded], or non stranded [0.5]')
    PEND = luigi.BoolParameter(default=False,
                               description='paired end sequencing reads')

    def requires(self):
        return qualityCheck()
    
    def __init__(self,*args,**kwargs):
        self.tmpdir = tempfile.mkdtemp(prefix=ldft)
        super().__init__(*args,**kwargs)

    def output(self):
        return luigi.LocalTarget(self.tmpdir+'/success')

    def run(self):
        local['RSEMcounting.sh'](self.NSQrun, self.datadir, self.genome, self.forwardprob, self.PEND)
        pathlib.Path(self.output().path).touch()

@inherits(countTask)
class diffexpTask(ExternalProgramTask):
    design = luigi.Parameter(description='model design for differential expression analysis')
    
    def requires(self):
        return countTask()
    
    def __init__(self,*args,**kwargs):
        self.tmpdir = tempfile.mkdtemp(prefix=ldft)
        super().__init__(*args,**kwargs)

    def output(self):
        return luigi.LocalTarget(self.tmpdir+'/success')

    def run(self):
        local['simpleDEvoom.R'](self.NSQrun, self.datadir, self.design)
        pathlib.Path(self.output().path).touch()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RNAseq processing pipeline.')
    # if arguments are set in environment, they are used as the argument default values
    # this allows seemless integration with PBS jobs

    if os.environ.get('PBS_JOBNAME'):
        #Retrieve arguments from qsub job environment
        #For testing:
        # os.environ.setdefault('datadir','testdir')
        # os.environ.setdefault('NSQrun','testrun')
        args = parser.parse_args('{} {} {}'.format(
            os.environ.get('datadir'),
            os.environ.get('NSQrun'),
            '--PEND ' if os.environ.get('PEND') else '',
        ).split())
    else:
        #Script started directly
        args = parser.parse_args()

    # Set up DAG
    default_args = {
        'owner': os.environ.get('USER','airflow'),
        'depends_on_past': False,
        #'start_date': datetime(2017, 9, 1),
        'email': ['christophe.vanneste@ugent.be'],
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        # 'queue': 'bash_queue',
        # 'pool': 'backfill',
        # 'priority_weight': 10,
        # 'end_date': datetime(2016, 1, 1),
    }

    # CLI options for pipeline are passed through params
    dag = DAG('RNAseq', start_date = datetime(2017, 9, 1), default_args = default_args, schedule_interval=timedelta(1), params = vars(args))

    dag >> qualityCheck >> alignTask >> countTask #>> diffexpTask
    dag.run()

    workflow = alignTask(datadir='/tmp',NSQrun='run1',apitoken='123abc',dirstructure='one')
