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
import logging

# matplotlib => setup for exporting svg figures only
import matplotlib
matplotlib.use('SVG')
import matplotlib.pyplot as plt

## Tasks
from genairics import logger, gscripts, setupProject
from genairics.datasources import BaseSpaceSource

@inherits(setupProject)
class mergeFASTQs(luigi.Task):
    """
    Merge fastqs if one sample contains more than one fastq
    """
    dirstructure = luigi.Parameter(default='multidir',
                                   description='dirstructure of project datat directory: onedir (one file/sample) or multidir (one dir/sample)')
    
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
        
        local[gscripts % 'qualitycheck.sh'](self.project, self.datadir)
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
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')
    genome = luigi.Parameter(default='RSEMgenomeGRCg38',
                             description='reference genome to use')
    pairedEnd = luigi.BoolParameter(default=False,
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
        stdout = local[gscripts % 'STARaligning.sh'](self.project, self.datadir, self.suffix, self.genome, self.pairedEnd)
        logger.info('%s output:\n%s',self.task_family,stdout)
        
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
    forwardprob = luigi.FloatParameter(default=0.5,
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
        local[gscripts % 'RSEMcounts.sh'](
            self.project, self.datadir, self.genome+'/human_ensembl', self.forwardprob, self.pairedEnd
        )
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
    design = luigi.Parameter(default='',
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
            msg = colors.red | '''
                metafile needs to be provided to run DE analysis
                a template file has been generated for you ({})
                adjust file to match your design, add the above file path
                as input "metafile" for the pipeline and rerun
                '''.format(metafile)
            logger.error(msg)
            raise Exception()
        with local.env(R_MODULE="SET"):
            local['bash'][
                '-i','-c', ' '.join(
                    ['Rscript', gscripts % 'simpleDEvoom.R',
                     self.project, self.datadir, self.metafile, self.design]
                )]()
        pathlib.Path(self.output()[0].path).touch()

@inherits(BaseSpaceSource)
@inherits(diffexpTask)
class RNAseqWorkflow(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(alignTask)
        yield self.clone(countTask)
        if self.design: yield self.clone(diffexpTask)
        
if __name__ == '__main__':
    import argparse
    from genairics import typeMapping
    
    parser = argparse.ArgumentParser(description='''
    RNAseq processing pipeline.
    Arguments that end with "[value]" or "[]" are optional and do not always need to be provided.
    When the program is finished running, you can check the log file with "less -r plumbing/pipeline.log"
    from your project's result directory. Errors will also be printed to stdout.
    ''')
    for paran,param in RNAseqWorkflow.get_params():
        if type(param._default) in typeMapping.values():
            parser.add_argument('--'+paran, default=param._default, type=typeMapping[type(param)],
                                help=param.description+' [{}]'.format(param._default))
        else: parser.add_argument('--'+paran, type=typeMapping[type(param)], help=param.description)
        
    # if arguments are set in environment, they are used as the argument default values
    # this allows seemless integration with PBS jobs
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
    from genairics import runWorkflow
    workflow = RNAseqWorkflow(**vars(args))
    runWorkflow(workflow)
