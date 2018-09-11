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
        return index.output()[0] # return index folder
        
    def run(self):
        from plumbum import local, FG
        # run bowtie2 and store as bam file with mapping quality already filtered to mapQ 4
        stdout = (local['bowtie2'][(
            '-p', config.threads,
            '-x', os.path.join(self.required_resources().path,self.species),)+
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

# Variant calling
@pb.inherits(RetrieveGenome)
class Samtools2variants(SampleTask):
    def required_resources(self):
        """
        Resource dependencies are for now started
        from within this function, but should be 
        automated differently in the future
        """
        import glob, os
        genome = self.clone(RetrieveGenome)
        if not genome.complete(): genome.run()
        return {
            'fasta': glob.glob(
                os.path.join(genome.output().path, 'dna', '*.fa')
            )[0],
            'gtf': glob.glob(
                os.path.join(genome.output().path, 'annotation', '*.gtf')
            )[0]
        }

    def run(self):
        from plumbum import local, FG
        local['samtools']['sort', self.input()['bam'].path, self.output()['bam'].path[:-4]] &FG # output bam remove .bam with -4
        local['samtools']['index', self.output()['bam'].path] &FG
        bcf_filename = os.path.join(os.path.dirname(self.input()['bam'].path), 'variants.raw.bcf')
        (local['samtools']['mpileup', '-uD', '-f', self.required_resources()['fasta'], self.output()['bam'].path] |
             local['bcftools']['view', '-bvcg', '-'] > bcf_filename) &FG
        (local['bcftools']['view', bcf_filename] > self.output()['vcf'].path) &FG
        (local['bedtools']['intersect', '-a', self.required_resources()['gtf'], '-b', self.output()['vcf'].path, '-wa', '-u']
             > self.output()['annotated_vcf'].path) &FG
        
    def output(self):
        return {
            'bam': pb.LocalTarget(os.path.join(self.outfileDir,'alignment.sorted.bam')),
            'vcf': pb.LocalTarget(os.path.join(self.outfileDir,'variants.vcf')),
            'annotated_vcf': pb.LocalTarget(os.path.join(self.outfileDir,'variants_annotated.vcf'))
        }
