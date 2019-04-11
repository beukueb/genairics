#-*- coding: utf-8 -*-
"""ATAC sequencing pipeline starting from BaseSpace fastq project

For help on settings run `genairics ATACseq -h`
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits, requires
from plumbum import local, colors
import pandas as pd
import logging

## Tasks
from genairics import config, logger, gscripts, setupProject, setupSequencedSample, processSamplesIndividually
from genairics.datasources import BaseSpaceSource, mergeSampleFASTQs
from genairics.resources import resourcedir, STARandRSEMindex, RetrieveBlacklist

### per sample subtasks
from genairics.RNAseq import sampleQualityCheck, cutadaptConfig, cutadaptSampleTask

@inherits(cutadaptConfig)
class alignSTARconfig(luigi.Config):
    """
    Contains global STAR parameters that should be configurable by the end user.
    STAR parameters that are set automatically reside within the alignATACsampleTask only
    including parameters that are sample specific.
    """
    runThreadN = luigi.IntParameter(config.threads,description="processors that STAR will use")
    runMode = luigi.Parameter("alignReads",description="STAR run mode")
    readFilesCommand = luigi.Parameter("zcat",description="command for decompressing fq file")
    outSAMtype = luigi.Parameter("BAM SortedByCoordinate")
    outFilterMultimapNmax = luigi.IntParameter(
        default=1,
        description="how many mappings/read allowed; 1 to exclude multimapping reads")
    alignIntronMax = luigi.IntParameter(1)
    outWigType = luigi.Parameter("bedGraph")
    outWigNorm = luigi.Parameter("RPM")
    
@inherits(alignSTARconfig)
@inherits(mergeSampleFASTQs)
class alignATACsampleTask(luigi.Task):
    """
    The task to process one sample.
    Intended to be called from a project task that contains all samples needed to be processed.
    """
    genomeDir = luigi.Parameter(description='genome dir')

    def requires(self):
        return self.clone(mergeSampleFASTQs)
    
    def run(self):
        stdout = local['STAR'](
            '--runThreadN', self.runThreadN,
            '--runMode', self.runMode,
            '--genomeDir', self.genomeDir,
            '--readFilesIn', self.input()[0].path,
            *((self.input()[1].path,) if self.pairedEnd else ()),
            *(('--outFilterScoreMinOverLread', 0.3, '--outFilterMatchNminOverLread', 0.3) if self.pairedEnd else ()),
            '--readFilesCommand', self.readFilesCommand,
	    '--outFileNamePrefix', self.output().path,
	    '--outSAMtype', self.outSAMtype.split()[0], self.outSAMtype.split()[1],
	    '--alignIntronMax', self.alignIntronMax,
	    '--outWigType', self.outWigType,
            '--outWigNorm', self.outWigNorm
        )
        logger.info('%s output:\n%s',self.task_family,stdout)

    def output(self):
        return luigi.LocalTarget(os.path.join(self.outfileDir,'./'))

# the sample pipeline can inherit and clone the last independent sample subtask[s] directly
@inherits(alignATACsampleTask)
class processATACsampleTask(luigi.Task):
    """
    This wrappers makes sure all the individuel sample tasks get run.
    Each task should be idempotent to avoid issues.
    """
    def run(self):
        #yield subtasks; if completed will go to next subtask
        self.clone(setupSequencedSample).run()
        self.clone(mergeSampleFASTQs).run()
        self.clone(sampleQualityCheck).run()
        self.clone(cutadaptSampleTask).run()
        self.clone(alignATACsampleTask).run()

        pathlib.Path(self.output().path).touch()

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))
    
@inherits(setupProject)
@inherits(alignSTARconfig)    
@inherits(STARandRSEMindex)
class processATACsamplesTask(luigi.Task):
    """
    Align reads to genome with STAR
    """
    pairedEnd = luigi.BoolParameter(
        default=False,
        description='paired end sequencing reads'
    )
    
    def requires(self):
        return {
            'genome':self.clone(STARandRSEMindex), #OPTIONAL use genome index only instead of the RSEM build transcriptome index
        }

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/sampleResults'.format(self.resultsdir,self.project)),
        )

    def run(self):
        # Make output directory
        if not self.output()[1].exists(): os.mkdir(self.output()[1].path)

        # Run the sample subtasks
        for fastqdir in glob.glob(os.path.join(self.datadir,self.project,'*')):
            sample = os.path.basename(fastqdir)
            pASTask = processATACsampleTask( #OPTIONAL future implement with yield
                sampleDir = fastqdir,
                pairedEnd = self.pairedEnd,
                outfileDir = os.path.join(self.output()[1].path,sample),
                genomeDir=self.input()['genome'][0].path,
                **{k:self.param_kwargs[k] for k in alignSTARconfig.get_param_names()}
            )
            if not pASTask.complete(): pASTask.run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@requires(processATACsamplesTask)
class SamBedFilteringTask(luigi.Task):
    """
    Filtering mapped reads on quality and optionally on blacklisted genomic regions 
    (https://sites.google.com/site/anshulkundaje/projects/blacklists)
    Blacklisting currently only for human data
    """
    filterBlacklist = luigi.BoolParameter(True,description="if human genome, filter blacklisted regions")
    samtoolsViewQ = luigi.IntParameter(4,description="samtools view -q mapping quality parameter for filtering")
    
    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            self.input()[1] # forward inherited alignment dir
        )

    def run(self):
        for sampleFile in glob.glob(os.path.join(self.input()[1].path,'*')):
            sample = os.path.basename(sampleFile)
            
            # Filtering mapped reads
            stdout = local['samtools'](
                'view', '-b', '-q', self.samtoolsViewQ, '-@', 2,
                '-o', os.path.join(sampleFile,"Aligned.sortedByCoord.minMQ4.bam"),
	        os.path.join(sampleFile,"Aligned.sortedByCoord.out.bam")
            )
            logger.info(stdout)

            #Filtering blacklisted genomic regions
            if self.filterBlacklist and self.species in {'homo_sapiens'}:
                blacklist = RetrieveBlacklist(species=self.species,release=self.release)
                if not blacklist.complete(): blacklist.run()
                (local['bedtools'][
                    'intersect', '-v', '-abam',
                    os.path.join(sampleFile,"Aligned.sortedByCoord.minMQ4.bam"),
                    '-b', blacklist.output().path] > os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam"))()
                logger.info("blacklist filtering finished")
            else:
                os.rename(
                    os.path.join(sampleFile,"Aligned.sortedByCoord.minMQ4.bam"),
                    os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam")
                )
                logger.info("without blacklist filtering")

            # Indexing final filtered file
            stdout = local['samtools']('index', os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam"))
            logger.info(stdout)
            
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@requires(SamBedFilteringTask)
class PeakCallingTask(luigi.Task):
    """
    MACS2 peak calling

    Work in progress -> still decide how to normalize for bw file
    --normalizeUsingRPKM
    --normalizeTo1x 2451960000  
    """
    callSummits = luigi.BoolParameter(default=False,description="lets MACS2 also call subpeaks")
    normalizeTo1x = luigi.IntParameter(
        default=0,
        description="""
        MACS2 normalization option. If not provided will default to normalize using RPKM.
        Else int needs to be provided of genome size to pass to --normalizeTo1x,
        e.g. 2451960000 for human genome.
        """
    )
    extsize = luigi.IntParameter(
        default=200,
        description="""
        MACS2 extsize option. If O, --nomodel will not be included.
        """
    )
    peakQ = luigi.FloatParameter(
        default=.05,
        description="""
        MACS2 peak calling q option. Cutoff for peak detection.
        """
    )
    
    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            self.input()[1] # forward inherited alignment dir
        )

    def run(self):
        for sampleFile in glob.glob(os.path.join(self.input()[1].path,'*')):
            sample = os.path.basename(sampleFile)
            with local.env(PYTHONPATH=''):
                stdout = local['macs2'](
                    'callpeak', '-t',
                    os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam"),
                    '-n', os.path.join(sampleFile,sample),
                    *(('--nomodel','--extsize',self.extsize) if self.extsize else ()),
                    '--nolambda', '-q', self.peakQ,
                    '--keep-dup', 'auto',
                    *(('--call-summits',) if self.callSummits else ())
                )
            if stdout: logger.info(stdout)
            with local.env(PYTHONPATH=''):
                stdout = local['bamCoverage'](
                    '-p', str(config.threads),
                    *(
                        ('--normalizeUsing','RPGC','--effectiveGenomeSize',self.normalizeTo1x)
                        if self.normalizeTo1x else ('--normalizeUsing','RPKM',)
                    ),
                    #'--extendReads', #TODO make possible for both single/paired end
		    '-b', os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam"),
		    '-o', os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam")[:-3]+'coverage.bw' 
                )
            if stdout: logger.info(stdout)

        # Check point
        pathlib.Path(self.output()[0].path).touch()

from genairics.RNAseq import mergeQualityChecks

@inherits(BaseSpaceSource)
@inherits(PeakCallingTask)
class ATACseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        sampleTask = self.clone(processATACsamplesTask)
        yield processSamplesIndividually(requiredSampleTask = sampleTask)
        yield self.clone(SamBedFilteringTask)
        yield self.clone(PeakCallingTask)
        yield mergeQualityChecks(requiredSampleTask = sampleTask)
