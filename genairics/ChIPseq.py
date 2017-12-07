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

## Helper function
class LuigiStringTarget(str):
    def exists(self):
        return bool(self)

## Tasks
from RNAseq import setupProject, setupLogging, basespaceData, mergeFASTQs

### Single file tasks
class Sample(luigi.Task):
    """
    This class simply describes the parameters needed to work with a sample.
    When inherited tasks can process a sample. It is recommended to always
    produce a subdirectory in the resultdir for a specific task when processing
    more than one sample.
    """
    sample = luigi.Parameter(description="sample filename")
    resultdir = luigi.Parameter(description="general result directory")
    extension = luigi.ChoiceParameter(choices=['fastq','fastq.gz'],default='fastq.gz')

    def output(self):
        return {
            'sample': luigi.LocalTarget(self.sample),
            'name': LuigiStringTarget(
                os.path.basename(self.sample)[:-1-len(self.extension)]
            ),
            'resultdir': luigi.LocalTarget(self.resultdir)
        }

    def run(self):
        logger = logging.getLogger(os.path.basename(__file__))
        if not self.output()['resultdir'].exists():
            os.mkdir(self.output()['resultdir'].path)
            logger.info('created result directory %s',self.output()['resultdir'].path)
        if not self.sample.endswith(self.extension):
            logger.warning('sample does not end with "%s". naming will be wrong',self.extension)

@inherits(Sample)
class countReadsSample(luigi.Task):
    def requires(self): return self.clone_parent()
    
    def run(self):
        (local['cat'][self.sample] | local['grep']['-c','@'])()
