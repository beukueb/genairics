#-*- coding: utf-8 -*-
"""Pipeline for Salmonella enteritidis project

For help on settings run `GAX_PIPEX=genairics.pipelines.bacterial.salmonella.SalmonellaProject genairics SalmonellaProject -h`
"""
from genairics import pb
from genairics.tasks import setupProject, setupSequencedSample
from genairics.datasources import DataSource
from genairics.tasks.sample.preprocessing import PrepareFASTQs
from genairics.tasks.sample.qc import QualityCheck

#Pipeline
# Sample level
# class SalmonellaSample(pb.SamplePipelineWrapper):
#     def tasks(self):
#         yield setupSequencedSample
#         yield mergeSampleFASTQs
#         yield QualityCheck

# SalmonellaSample.inherit_task_parameters()

# Project level
class SalmonellaProject(pb.PipelineWrapper):
    def tasks(self):
        yield setupProject
        yield DataSource
        
        with self.sample_context() as sample_context:
            yield setupSequencedSample
            yield PrepareFASTQs
            yield QualityCheck

SalmonellaProject.inherit_task_parameters()
