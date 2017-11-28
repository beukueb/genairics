#!/bin/env python
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
        return luigi.LocalTarget('{}/../results/{}/plumbing/3_{}_completed'.format(self.datadir,self.NSQrun,self.task_family))

    def run(self):
        local['qualitycheck.sh'](self.NSQrun, self.datadir)
#        for fqcfile in $(ls $outdir/*.zip)
#do
#    fqcdir=${fqcfile%.zip}
#    unzip -d . $fqcfile ${fqcdir##*/}/summary.txt
#    python - ${fqcdir##*/}/summary.txt <<EOF
#import sys,os
#import pandas as pd
#summ = pd.read_csv(sys.argv[1],sep='\t',header=None)
#if not os.path.exists('qcsummary.csv'):
#  with open('qcsummary.csv','wt') as f:
#    f.write('\t'+'\t'.join(list(summ[1]))+'\n')
#with open('qcsummary.csv','at') as f:
#  f.write(summ[2].ix[0]+'\t'+'\t'.join(list(summ[0]))+'\n')
#EOF
#    rm -rf ${fqcdir##*/}
#done
#mv qcsummary.csv $outdir/

        pathlib.Path(self.output().path).touch()

@inherits(qualityCheck)
class alignTask(luigi.Task):
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')
    defaultMappings['suffix'] = ''
    genome = luigi.Parameter(default='RSEMgenomeGRCg38/human_ensembl',
                             description='reference genome to use')
    defaultMappings['genome'] = 'RSEMgenomeGRCg38/human_ensembl'
    pairedEnd = luigi.BoolParameter(default=False,
                               description='paired end sequencing reads')

    defaultMappings['pairedEnd'] = False
    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/../results/{}/plumbing/4_{}_completed'.format(self.datadir,self.NSQrun,self.task_family))

    def run(self):
        local['STARaligning.py'](self.NSQrun, self.datadir, self.suffix, self.genome, self.pairedEnd)
# cd $VSC_DATA_VO_USER/results/${NSQ_Run}_results/
# if [ "$VSC_HOME" ]; then module load pandas; fi
# python - <<EOF
# #Process STAR counts
# from glob import glob
# import pandas as pd
# import os

# amb = []
# counts = []
# amb_annot = counts_annot = None
# samples = []
# for dir in glob('{}/results/{}_results/alignmentResults/*'.format(os.environ['VSC_DATA_VO_USER'],
#                                                                   os.environ['NSQ_Run'])):
#     f = open(dir+'/ReadsPerGene.out.tab')
#     f = f.readlines()
#     amb.append([int(l.split()[1]) for l in f[:4]])
#     if not amb_annot: amb_annot = [l.split()[0] for l in f[:4]]
#     f = f[4:]
#     if not counts_annot: counts_annot = [l.split()[0] for l in f]
#     else:
#         assert counts_annot == [l.split()[0] for l in f]
#     counts.append([int(l.split()[1]) for l in f])
#     samples.append(dir[dir.rindex('/')+1:])
# counts_df = pd.DataFrame(counts,columns=counts_annot,index=samples).transpose()
# counts_df.to_csv('STARcounts.csv')
# EOF

        pathlib.Path(self.output().path).touch()
    
@inherits(alignTask)
class countTask(luigi.Task):
    forwardprob = luigi.FloatParameter(default=0.5,
                                       description='stranded seguencing [0 for illumina stranded], or non stranded [0.5]')
    defaultMappings['forwardprob'] = 0.5
    
    def requires(self):
        return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/../results/{}/plumbing/5_{}_completed'.format(self.datadir,self.NSQrun,self.task_family))

    def run(self):
        local['RSEMcounts.sh'](self.NSQrun, self.datadir, self.genome, self.forwardprob, self.pairedEnd)
# module load pandas
# python - <<EOF
# #Process RSEM counts
# from glob import glob
# import pandas as pd
# import os

# counts = {}
# samples = []
# for gfile in glob('{}/results/{}_results/countResults/*.genes.results'.format(os.environ['VOU'],
#                                                                               os.environ['NSQ_Run'])):
#     sdf = pd.read_table(gfile,index_col=0)
#     counts[gfile[gfile.rindex('/')+1:-14]] = sdf.expected_count
 
# counts_df = pd.DataFrame(counts)
# counts_df.to_csv('{}_RSEMcounts.csv'.format(os.environ['NSQ_Run']))
# EOF

        pathlib.Path(self.output().path).touch()

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
    for paran,param in countTask.get_params():
        if paran in defaultMappings:
            parser.add_argument('--'+paran, default=defaultMappings[paran], type=typeMapping[type(param)], help=param.description)
        else: parser.add_argument('--'+paran, type=typeMapping[type(param)], help=param.description)
        
    if os.environ.get('LUIGI_PBS_ENV'):
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

    workflow = RNAseqWorkflow(**vars(args))
    print(workflow)
    for task in workflow.requires():
        print(task)
        if not task.complete(): task.run()

    #print('[re]move ',luigitempdir)
