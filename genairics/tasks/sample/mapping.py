#-*- coding: utf-8 -*-
"""genairics sample mapping module 
tasks for mapping samples
"""
from genairics import pb
from genairics.tasks import SampleTask
from genairics.config import config
import os

from genairics.resources import RetrieveGenome, Bowtie2Index

@pb.inherits(Bowtie2Index)
class Bowtie2align(SampleTask):
    def required_resources(self):
        """
        Resource dependencies are for now started
        from within this function, but should be 
        automated differently in the future
        """
        genome = self.clone(RetrieveGenome)
        index = self.clone(Bowtie2Index)
        if not genome.complete(): genome.run()
        if not index.complete(): index.run()
        return index.output()
        
    def run(self):
        from plumbum import local, FG
        # run bowtie2 and store as bam file with mapping quality already filtered to mapQ 4
        stdout = (local['bowtie2'][(
            '-p', config.threads,
            '-x', os.path.join(self.required_resources().path,self.genome),)+
            (
                ('-U', self.input()['fastqs'][0].path) if not self.pairedEnd else
                ('-1', self.input()['fastqs'][0].path, '-2', self.input()['fastqs'][1].path)
            )
        ] | local['samtools']['view', '-q', 4, '-Sbh', '-'] > self.output()['bam'].path)()
        if stdout: logger.info(stdout)

    def output(self):
        return {
            'bam': pb.LocalTarget(os.path.join(self.outfileDir,'alignment.bam'))
        }
