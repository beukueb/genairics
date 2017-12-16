#!/usr/bin/env python
"""
Tasks here prepare resources that are required for some
pipeline tasks, and are generally available from the
resources directory as specified by $GENAIRICS_RESOURCES
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.util import inherits
from plumbum import local, colors
import logging

resourcedir = os.environ.get('GENAIRICS_RESOURCES',os.path.expanduser('~/resources'))

def RetrieveGenome(luigi.Task):
    """
    Prepares the genome
    """
    genome = luigi.Parameter(default='homo_sapiens')
    release = luigi.IntParameter(default=91,description="release of genome to install")

    def output(self):
        return luigi.LocalTarget(
            os.path.join(resourcedir,'ensembl',genome,'release-{}'.format(self.release))
        )

    def run(self):
        #Make temp dir for data
        local['mkdir']('-p',self.output().path+'_rsyncing')
        stdout = local['rsync'](
            '-av',
            'rsync://ftp.ensembl.org/ensembl/pub/release-{release}/fasta/{species}/dna/*.dna.chromosome.*.fa.gz'.format(
                species=self.genome, release=self.release),
            self.output().path+'_rsyncing'
        )
        #Rename temp dir to final/expected output dir
        os.rename(self.output().path+'_rsyncing',self.output().path)

@inherits(RetrieveGenome)
def STARandRSEMindex(luigi.Task):
    """
    Index that can be used by both STAR aligner and RSEM counter
    """

    def output(self):
        pass

    def run(self):
        pass
