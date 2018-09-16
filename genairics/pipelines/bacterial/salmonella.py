#-*- coding: utf-8 -*-
"""Pipeline for Salmonella enteritidis project

For help on settings run `GAX_PIPEX=genairics.pipelines.bacterial.salmonella.SalmonellaProject genairics SalmonellaProject -h`
"""
from genairics import pb
from genairics.tasks import setupProject, setupSequencedSample
from genairics.datasources import DataSource, Sample2Dir, CompressData
from genairics.tasks.sample.preprocessing import PrepareFASTQs
from genairics.tasks.sample.qc import QualityCheck
from genairics.tasks.sample.mapping import Bowtie2align, Samtools2variants
from genairics.tasks.project.variants import VariantTree

#Pipeline
class SalmonellaProject(pb.PipelineWrapper):
    def tasks(self):
        yield setupProject
        yield DataSource
        yield Sample2Dir
        yield CompressData
        
        with self.sample_context():
            yield setupSequencedSample
            yield PrepareFASTQs
            yield QualityCheck
            yield Bowtie2align
            yield Samtools2variants

        #Merging tasks
        yield VariantTree

SalmonellaProject.inherit_task_parameters()
