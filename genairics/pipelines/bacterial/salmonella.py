#-*- coding: utf-8 -*-
"""Pipeline for Salmonella enteritidis project

For help on settings run `GAX_PIPEX=genairics.pipelines.bacterial.salmonella.genome genairics RNAseq -h`
"""
from genairics import pb
from genairics.datasources import DataSource

#Pipeline
@pb.inherits(DataSource)
class salmonellaGenomePipeline(pb.Pipeline):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(DataSource)
        
        with self.processSamplesIndividually() as samples:
            for sample in samples:
                yield sample
                yield QualityCheck
                yield AlignSample
        yield PCAplotCounts
        yield mergeAlignResults
