#-*- coding: utf-8 -*-
"""genairics sample assembly module 
tasks for read assembly of samples
"""
from genairics import pb
from genairics.tasks import SampleTask
from genairics.config import config
import os

from genairics.resources import RetrieveGenome

class SPAdes(SampleTask):
    def run(self):
        from plumbum import local, FG
        stdout = (local['spades.py'][(
            '-o', self.output['assembly_dir'].path,)+
            (
                ('-s', self.input()['fastqs'][0].path) if not self.pairedEnd else
                ('-1', self.input()['fastqs'][0].path, '-2', self.input()['fastqs'][1].path)
            )
        ] &FG

    def output(self):
        return {
            'assembly': pb.LocalTarget(os.path.join(self.outfileDir,'assembly','contigs.fasta')),
            'assembly_dir': pb.LocalTarget(os.path.join(self.outfileDir,'assembly'))
        }
