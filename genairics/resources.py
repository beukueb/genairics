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
logresources = logging.Logger('genairics.resources')

class RetrieveGenome(luigi.Task):
    """
    Prepares the genome
    """
    genome = luigi.Parameter(default='homo_sapiens')
    release = luigi.IntParameter(default=91,description="release of genome to install")

    def output(self):
        return luigi.LocalTarget(
            os.path.join(resourcedir,'ensembl',self.genome,'release-{}'.format(self.release))
        )

    def run(self):
        #Make temp dir for data
        local['mkdir']('-p',self.output().path+'_rsyncing/dna')
        local['mkdir']('-p',self.output().path+'_rsyncing/annotation')
        stdout = local['rsync'](
            '-av',
            'rsync://ftp.ensembl.org/ensembl/pub/release-{release}/fasta/{species}/dna/*.dna.chromosome.*.fa.gz'.format(
                species=self.genome, release=self.release),
            self.output().path+'_rsyncing/dna'
        )
        logresources.info(stdout)
        stdout = local['rsync'](
            '-av',
            'rsync://ftp.ensembl.org/ensembl/pub/release-{release}/gff3/{species}/*.{release}.gff3.gz'.format(
                species=self.genome, release=self.release),
            self.output().path+'_rsyncing/annotation'
        )
        logresources.info(stdout)
        #Unzip all files
        local['gunzip'](*glob.glob(self.output().path+'_rsyncing/*/*.gz'))
        #Rename temp dir to final/expected output dir
        os.rename(self.output().path+'_rsyncing',self.output().path)

@inherits(RetrieveGenome)
class STARandRSEMindex(luigi.Task):
    """
    Index that can be used by both STAR aligner and RSEM counter
    """
    threads = luigi.IntParameter(default=1, description='threads to use to build mapping index')

    def requires(self):
        return self.clone_parent()
    
    def output(self):
        return (
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/index'.format(
                    species=self.genome,release=self.release))
            ),
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/index/build_completed'.format(
                    species=self.genome,release=self.release))
            )
        )
    
    def run(self):
        genomeDir = self.input().path
        stdout = local['rsem-prepare-reference'](
            '-gff3', *glob.glob(os.path.join(genomeDir,'annotation')+'/*.gff3'),
            '--star', '--star-sjdboverhang', '100', '-p', self.threads,
            ','.join(glob.glob(os.path.join(genomeDir,'dna')+'/*.fa*')),
            os.path.join(self.output()[0].path, self.genome)
        )
        logresources.info(stdout)
        os.path.touch(self.output()[1].path)
