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
    """
    def output(self):
        return {
            'fastqs': self.input()['fastqs'], # shuttles through the fastqs
            'qc': pb.LocalTarget(os.path.join(self.outfileDir,'QCresults'))
        }
    
    def run(self):
        from plumbum import local
        tmpdir = self.output()['qc'].path+'_tmp'
        os.mkdir(tmpdir)
        stdout = local['fastqc'](
            '-o', tmpdir,
            '-t', config.threads,
            self.input()['fastqs'][0].path,
            *((self.input()['fastqs'][1].path,) if self.pairedEnd else ())
        )
        os.rename(tmpdir,self.output()['qc'].path)
