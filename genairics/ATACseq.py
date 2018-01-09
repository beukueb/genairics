#!/usr/bin/env python
"""
ATAC sequencing pipeline starting from BaseSpace fastq project
"""

from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits
from plumbum import local, colors
import pandas as pd
import logging

## Tasks
from genairics import config, logger, gscripts, setupProject
from genairics.datasources import BaseSpaceSource, mergeFASTQs
from genairics.resources import resourcedir, STARandRSEMindex

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
        stdout = local['STAR'](
            '--runThreadN', self.runThreadN,
            '--runMode', self.runMode,
            '--genomeDir', resourcedir+'/ensembl/{species}/release-{release}/transcriptome_index'.format(
                species=self.genome,release=self.release
            ),
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
            'genome':self.clone(STARandRSEMindex), #TODO need genome not transcriptome index
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
        os.mkdir(self.output()[1])

        # Run the sample subtasks
        for fastqfile in glob.glob(os.path.join(self.datadir,self.project,'*.fastq.gz')):
            sample = os.path.basename(fastqfile).replace('.fastq.gz','')
            yield alignATACsampleTask(
                genomeDir=self.input()['genome'][1].path,
                readFilesIn=fastqfile,
                outFileNamePrefix=os.path.join(self.output()[1].path,sample+'/'), #optionally in future first to temp location
                **{k:self.param_kwargs[k] for k in alignSTARconfig.get_param_names()}
            ).run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@inherits(BaseSpaceSource)
@inherits(alignATACsamplesTask)
class ATACseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(alignATACsamplesTask)
