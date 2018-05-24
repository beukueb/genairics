#!/usr/bin/env python
"""
ATAC sequencing pipeline starting from BaseSpace fastq project
"""

from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits, requires
from plumbum import local, colors
import pandas as pd
import logging

## Tasks
from genairics import config, logger, gscripts, setupProject
from genairics.datasources import BaseSpaceSource, mergeFASTQs
from genairics.resources import resourcedir, STARandRSEMindex, RetrieveBlacklist
from genairics.RNAseq import qualityCheck

### ATAC specific Tasks
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
class alignATACsampleTask(luigi.Task):
    """
    The task to process one sample.
    Intended to be called from a project task that contains all samples needed to be processed.
    """
    genomeDir = luigi.Parameter(description='genome dir')
    readFilesIn = luigi.Parameter(description='fastqfile(s)')
    outFileNamePrefix = luigi.Parameter(description='result destination')

    def output(self):
        return luigi.LocalTarget(self.outFileNamePrefix)

    def run(self):
        os.mkdir(self.outFileNamePrefix)
        stdout = local['STAR'](
            '--runThreadN', self.runThreadN,
            '--runMode', self.runMode,
            '--genomeDir', self.genomeDir,
            '--readFilesIn', self.readFilesIn,
            '--readFilesCommand', self.readFilesCommand,
	    '--outFileNamePrefix', self.outFileNamePrefix,
	    '--outSAMtype', self.outSAMtype.split()[0], self.outSAMtype.split()[1],
	    '--alignIntronMax', self.alignIntronMax,
	    '--outWigType', self.outWigType,
            '--outWigNorm', self.outWigNorm
        )
        logger.info('%s output:\n%s',self.task_family,stdout)
    
@inherits(mergeFASTQs)
@inherits(alignSTARconfig)    
@inherits(STARandRSEMindex)
class alignATACsamplesTask(luigi.Task):
    """
    Align reads to genome with STAR
    TODO pairedEnd processing not implemented yet
    """
    pairedEnd = luigi.BoolParameter(default=False,
                                    description='paired end sequencing reads')
    
    def requires(self):
        return {
            'genome':self.clone(STARandRSEMindex), #OPTIONAL use genome index only instead of the RSEM build transcriptome index
            'fastqs':self.clone(mergeFASTQs)
        }

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/alignmentResults'.format(self.resultsdir,self.project)),
        )

    def run(self):
        if self.pairedEnd: raise NotImplementedError('paired end not yet implemented')
        
        # Make output directory
        if not self.output()[1].exists(): os.mkdir(self.output()[1].path)

        # Run the sample subtasks
        for fastqfile in glob.glob(os.path.join(self.datadir,self.project,'*.fastq.gz')):
            sample = os.path.basename(fastqfile).replace('.fastq.gz','')
            alignATACsampleTask( #OPTIONAL future implement with yield
                genomeDir=self.input()['genome'][0].path,
                readFilesIn=fastqfile,
                outFileNamePrefix=os.path.join(self.output()[1].path,sample+'/'), #optionally in future first to temp location
                **{k:self.param_kwargs[k] for k in alignSTARconfig.get_param_names()}
            ).run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@requires(alignATACsamplesTask)
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
            if self.filterBlacklist and self.genome in {'homo_sapiens'}:
                blacklist = RetrieveBlacklist(genome=self.genome,release=self.release)
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
        MACS2 normalization option. If not provided will default to --normalizeUsingRPKM.
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
                    *(('--normalizeTo1x',self.normalizeTo1x) if self.normalizeTo1x else ('--normalizeUsingRPKM',)),
                    #'--extendReads', #TODO make possible for both single/paired end
		    '-b', os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam"),
		    '-o', os.path.join(sampleFile,"Filtered.sortedByCoord.minMQ4.bam")[:-3]+'coverage.bw' 
                )
            if stdout: logger.info(stdout)

        # Check point
        pathlib.Path(self.output()[0].path).touch()
    
@inherits(BaseSpaceSource)
@inherits(PeakCallingTask)
class ATACseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(alignATACsamplesTask)
        yield self.clone(SamBedFilteringTask)
        yield self.clone(PeakCallingTask)
