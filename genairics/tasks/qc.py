#-*- coding: utf-8 -*-
"""genairics qc module 
for quality control tasks
"""
from genairics import pb
from genairics.tasks import SampleTask
from genairics.config import config
import os

class QualityCheck(SampleTask):
    """Check the quality of a single sample

    Uses fastqc.
    Should inherit (in)directly from setupSequencedSample
    Upstream dependent parameters: sample-related, `pairedEnd`
    """
    def output(self):
        return pb.LocalTarget(os.path.join(self.outfileDir,'QCresults'))

    def run(self):
        from plumbum import local
        tmpdir = self.output().path+'_tmp'
        os.mkdir(tmpdir)
        stdout = local['fastqc'](
            '-o', tmpdir,
            '-t', config.threads,
            self.input()[0].path,
            *((self.input()[1].path,) if self.pairedEnd else ())
        )
        os.rename(tmpdir,self.output().path)
