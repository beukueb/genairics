#!/usr/bin/env python
"""
Variant sequencing pipeline starting from BaseSpace fastq project

References:
 - https://github.com/ekg/freebayes
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
from genairics.resources import resourcedir, RetrieveGenome, Bowtie2Index, RetrieveBlacklist
from genairics.RNAseq import qualityCheck
from genairics.ChIPseq import processGenomicSamples

@requires(processChIPseqSamples)
class VariantCallingSamples(luigi.Task):
    """
    call the variants with freebayes assuming a diploid sample
    """    
    def run(self):
        for sample in glob.glob(os.path.join(self.input()[0].path,'*')):
            (local['freebayes']['-f', 'ref.fa', 'aln.bam'] > 'var.vcf')()


@inherits(BaseSpaceSource)
@inherits(PeakCallingChIPsamples)
class ChIPseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(processGenomicSamples)
        yield self.clone(VariantCallingSamples)

