#-*- coding: utf-8 -*-
"""genairics sample preprocessing module 
for generic sample tasks such as merging fastqs
and setting them up for processing
"""
from genairics import pb
from plumbum import local
import os, glob

class PrepareFASTQs(pb.Task):
    """
    Merges the fastqs of one sample if necessary.
    Should inherit (in)directly from setupSequencedSample.

    Upstream dependent parameters: sample-related, `pairedEnd`

    Default pairedEndFileMarkers are based on Illumina sequenced
    library naming conventions. These parameters allow changing
    that if the project FASTQ files have a different convention.
    """
    pairedEndFile1Marker = pb.Parameter(
        '_R1_',
        description = 'Substring that identifies each first file of a paired end seq library'
    )
    pairedEndFile2Marker = pb.Parameter(
        '_R2_',
        description = 'Substring that identifies each second file of a paired end seq library'
    )
    
    def output(self):
        infile1Target = pb.LocalTarget(
            os.path.join(
                self.outfileDir,
                '{}{}.fastq.gz'.format(
                    os.path.basename(self.sampleDir),
                    '_R1' if self.pairedEnd else ''
                )
            )
        )
        infile2Target = pb.LocalTarget(
            os.path.join(
                self.outfileDir,
                '{}_R2.fastq.gz'.format(os.path.basename(self.sampleDir))
            )
        ) if self.pairedEnd else None
        return {
            'fastqs': (infile1Target,infile2Target) if self.pairedEnd else (infile1Target,)
        }
    
    def run(self):
        if self.pairedEnd: #if paired-end
            (local['cat'] > self.output()['fastqs'][0].path+'_tmp')(
                *glob.glob(os.path.join(self.sampleDir,'*{}*.fastq.gz'.format(self.pairedEndFile1Marker)))
            )
            # paired end file written directly to final file path, R1 file only renamed at task end to signal completion
            (local['cat'] > self.output()['fastqs'][1].path)(
                *glob.glob(os.path.join(self.sampleDir,'*{}*.fastq.gz'.format(self.pairedEndFile2Marker)))
            )
        else: #if single-end or treated as such
            (local['cat'] > self.output()['fastqs'][0].path+'_tmp')(
                *glob.glob(os.path.join(self.sampleDir,'*.fastq.gz'))
            )
        os.rename(self.output()['fastqs'][0].path+'_tmp', self.output()['fastqs'][0].path)
