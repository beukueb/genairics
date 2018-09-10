# -*- coding: utf-8 -*-
"""Tasks here prepare resources that are required for some
pipeline tasks, and are generally available from the
resources directory as specified by $GAX_RESOURCES or
in genairics config file 'resourcedir' option
"""
from datetime import datetime, timedelta
import luigi, os, sys, tempfile, pathlib, glob
from luigi.util import inherits, requires
from plumbum import local, colors, FG
import logging

from genairics import config, gscripts

resourcedir = config.resourcedir
logresources = logging.Logger('genairics.resources')

#Set cksum program according to platform
if sys.platform == 'linux':
    cksum = local['sum']
elif sys.platform == 'darwin':
    cksum = local['cksum']['-o',1]
else: raise Exception('{} not supported. Run from docker container.'.format(sys.platform))

def requestFiles(urlDir,fileregex,outdir):
    """
    Download a set of files that match fileregex from urlDir
    checksums are expected to be generated by the "sum" command,
    as is the case for the ftp.ensembl.org repository
    """
    import requests, re
    link = re.compile(r'href="(.+?)"')
    if fileregex: fileregex = re.compile(fileregex)
    if not urlDir.endswith('/'): urlDir+='/'
    # Download checksums if present
    try:
        checksums = requests.get(urlDir+'CHECKSUMS')
        if checksums:
            from io import StringIO
            import pandas as pd
            checksums = pd.read_table(
                StringIO(checksums.text),sep='\s+',
                names=['checksum', 'octets', 'name'],index_col='name'
            )
        else: checksums = None
    except requests.exceptions.ConnectionError:
        logresources.warning('No checksums for %s', urlDir)
        checksums = None
        
    # Retrieve index
    r = requests.get(urlDir)
    for l in link.finditer(r.text):
        l = l.groups()[0]
        if not fileregex or fileregex.match(l):
            file_request = requests.get(urlDir+l, stream=True)
            with open(os.path.join(outdir,l),'wb') as outfile:
                for chunk in file_request.iter_content(chunk_size=512):
                    outfile.write(chunk)
            if checksums is not None:
                csum = int(cksum(os.path.join(outdir,l)).split()[0])
                if csum != checksums.checksum[l]:
                    logresources.warning('%s checksum did not match url location %s',csum,urlDir)

# Tasks
def InstallDependencies(include_system_packages=False, setup_bashrc=False):
    """Installs the genairics dependency programs

    Args: 
        include_system_packages (bool): If true, might ask for sudo to
          install system packages, depending on the *nix distribution.
        setup_bashrc (bool): If true add default configuration to `.bashrc`.
    """
    from genairics.config import config, dep_config
    from plumbum import FG
    with local.env(
            GAX_PREFIX = dep_config.prefix,
            GAX_REPOS = dep_config.repodir,
            **({'GAX_INSTALL_PLATFORM_PACKAGES':''} if include_system_packages else {})
            ):
        local[gscripts % 'genairics_dependencies.sh'] & FG
    if setup_bashrc: setup_bash_config() 

def setup_bash_config():
    """Add genairics config to .bashrc

    TODO: optionally add to config of virtualenv instead of .bashrc
    """
    # Prepare config
    from genairics.config import config, dep_config
    import re
    preamble = '###GAXCONFIG_BEGIN###'
    epilog = '###GAXCONFIG_END###'
    configstr ='''{}
export GAX_REPOS={}
export GAX_PREFIX={}
export GAX_RESOURCES={}
export PATH=$GAX_PREFIX/bin:$PATH
export R_LIBS=$GAX_PREFIX/Rlibs
{}
'''.format(
    preamble,
    dep_config.repodir, dep_config.prefix, config.resultsdir,
    epilog
    )
    config_section = re.compile(
        r'{}.+{}'.format(preamble,epilog),
        flags=re.DOTALL
    )
    with open(os.path.expanduser('~/.bashrc')) as f:
        bashrc = f.read()
    if config_section.search(bashrc):
        bashrc_new = config_section.sub(configstr, bashrc)
        with open(os.path.expanduser('~/.bashrc'),'wt') as f:
            f.write(bashrc_new)
    else:
        with open(os.path.expanduser('~/.bashrc'),'at') as f:
            f.write('\n')
            f.write(configstr)

def setup_directories():
    """Create genairics directories as specified
    by the configuration
    """
    from genairics.config import config
    os.mkdir(config.resourcedir)
    os.mkdir(config.datadir)
    os.mkdir(config.resultsdir)
    
class RetrieveGenome(luigi.Task):
    """
    Prepares the genome
    """
    species = luigi.Parameter(default='homo_sapiens', description="genome species name")
    release = luigi.IntParameter(default=91,
                                 description=
"""ensembl release number of genome
for homo_sapiens, use the following :
 91 => GRCh38 aka hg38;
 75 => GRCh37 aka hg19
"""
    )
    genomeType = luigi.Parameter(
        default='primary_assembly',
        description='Choose from: toplevel, primary_assembly. Some mappers cannot work with `toplevel`. '+
        'For some genomes only `toplevel` is available'
    )
    
    def output(self):
        return luigi.LocalTarget(
            os.path.join(resourcedir,'ensembl',self.species,'release-{}'.format(self.release))
        )

    def run(self):
        import requests

        # Species settings -> determine to which group the species belongs
        headers = {'content-type':'application/json'}
        r = requests.get(
            'http://rest.ensembl.org/info/assembly/' + self.species,
            headers = headers
        )
        if not 'error' in r.json():
            speciesGroup = 'model_organisms'
            collection = ''
            ensemblBaseURL = 'http://ftp.ensembl.org/pub/'
        else:
            r = requests.get(
                'http://rest.ensemblgenomes.org/info/assembly/' + self.species,
                headers = headers
            )
            if 'error' in r.json(): raise KeyError('Species %s not known in ensembl' % self.species)
            assembly = r.json()
            assembly_accession = r.json()['assembly_accession']
            # For non model organism, more information is needed to find the location where the genome is stored
            r = requests.get(
                'http://rest.ensemblgenomes.org/info/genomes/assembly/' + assembly_accession,
                headers = headers
            )
            speciesGroup = r.json()['division'].lower().replace('ensembl','')
            try:
                collection = r.json()['dbname']
                collection = collection[:collection.index('_core_')]
                if collection == self.species: collection = ''
                else: collection += '/' #as it will be inserted in url path
            except KeyError: collection = ''
            ensemblBaseURL = 'http://ftp.ensemblgemomes.org/pub/{}/'.format(speciesGroup)
            
        #Make temp dir for data
        local['mkdir']['-p',self.output().path+'_retrieving/dna'] &FG
        local['mkdir']['-p',self.output().path+'_retrieving/annotation'] &FG
        requestFiles(
            ensemblBaseURL+'release-{release}/fasta/{collection}{species}/dna/'.format(
                species = self.species, collection = collection, release = self.release),
            r'.+.dna.'+self.genomeType+'.fa.gz', #r'.+.dna.chromosome.+.fa.gz',
            self.output().path+'_retrieving/dna'
        )
        requestFiles(
            ensemblBaseURL+'release-{release}/gtf/{collection}{species}/'.format(
                species = self.species, collection = collection, release = self.release),
            r'.+.{release}.gtf.gz'.format(release=self.release),
            self.output().path+'_retrieving/annotation'
        )
        #Unzip all files
        local['gunzip'](*glob.glob(self.output().path+'_retrieving/*/*.gz'))
        #Rename temp dir to final/expected output dir
        os.rename(self.output().path+'_retrieving',self.output().path)

@requires(RetrieveGenome)
class RetrieveBlacklist(luigi.Task):
    """
    Info on blacklists: https://sites.google.com/site/anshulkundaje/projects/blacklists

    Available release:
    91 => GRCh38
    75 => GRCh37 (latest release of hg19)
    """
    availableBlacklists = {
        ('homo_sapiens', 91): "http://mitra.stanford.edu/kundaje/akundaje/release/blacklists/hg38-human/hg38.blacklist.bed.gz",
        ('homo_sapiens', 75):
        "http://mitra.stanford.edu/kundaje/akundaje/release/blacklists/hg19-human/wgEncodeHg19ConsensusSignalArtifactRegions.bed.gz"
    }
    
    def output(self):
        return luigi.LocalTarget(os.path.join(self.input().path,'blacklist.bed.gz'))

    def run(self):
        if (self.genome, self.release) not in self.availableBlacklists:
            raise NotImplementedError("blacklist for %s release %s is not available yet within genairics" % (self.genome,self.release))
        stdout = local['wget'](self.availableBlacklists[(self.genome, self.release)], '-O', self.output().path)
        logresources.info(stdout)

@requires(RetrieveGenome)
class Bowtie2Index(luigi.Task):
    """
    Index that can be used by bowtie2 aligner for ChIPseq, ATACseq, variant calling
    """
    def output(self):
        return (
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/genome_index'.format(
                    species=self.genome,release=self.release))
            ),
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/genome_index/build_completed'.format(
                    species=self.genome,release=self.release))
            )
        )
    
    def run(self):
        genomeDir = self.input().path
        os.mkdir(self.output()[0].path)
        stdout = local['bowtie2-build'](
            '--threads', config.threads,
            ','.join(glob.glob(os.path.join(genomeDir,'dna')+'/*.fa*')),
            os.path.join(self.output()[0].path, self.genome)
        )
        logresources.info(stdout)
        pathlib.Path(self.output()[1].path).touch()        

@inherits(RetrieveGenome)
class STARandRSEMindex(luigi.Task):
    """
    Index that can be used by both STAR aligner and RSEM counter for transcriptomics
    """
    def requires(self):
        return self.clone_parent()
    
    def output(self):
        return (
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/transcriptome_index'.format(
                    species=self.genome,release=self.release))
            ),
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/transcriptome_index/build_completed'.format(
                    species=self.genome,release=self.release))
            )
        )
    
    def run(self):
        genomeDir = self.input().path
        os.mkdir(self.output()[0].path)
        stdout = local[gscripts % 'buildRSEMindex.sh'](
            *glob.glob(os.path.join(genomeDir,'annotation')+'/*.gtf'),
            config.threads,
            ','.join(glob.glob(os.path.join(genomeDir,'dna')+'/*.fa*')),
            os.path.join(self.output()[0].path, self.genome)
        )
        logresources.info(stdout)
        pathlib.Path(self.output()[1].path).touch()

@inherits(RetrieveGenome)
class STARindex(luigi.Task):
    """
    Index that can be used by STAR aligner for genome mapping 
    (for genomic variant discovery, ChiPseq, ATACseq, )

    NOT YET TESTED, for the moment use STARandRSEMindex
    """
    sjdbOverhang = luigi.IntParameter(default=100, description='library prep read length. default of 100 should generally be ok')
    
    def requires(self):
        return self.clone_parent()
    
    def output(self):
        return (
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/genome_index_overhang{overhang}'.format(
                    species=self.genome,release=self.release,overhang=self.sjdbOverhang))
            ),
            luigi.LocalTarget(
                os.path.join(resourcedir,'ensembl/{species}/release-{release}/genome_index_overhang{overhang}/build_completed'.format(
                    species=self.genome,release=self.release,overhang=self.sjdbOverhang))
            )
        )
    
    def run(self):
        genomeDir = self.input().path
        os.mkdir(self.output()[0].path)
        stdout = local['STAR'](
            '--runThreadN', config.threads,
            '--runMode', 'genomeGenerate',
            '--genomeDir', os.path.join(self.output()[0].path, self.genome),
            '--genomeFastaFiles', ','.join(glob.glob(os.path.join(genomeDir,'dna')+'/*.fa*')),
            '--sjdbOverhang', self.sjdbOverhang
            
        )
        #TODO STAR Log.out will be produced should be moved to genome index dir
        logresources.info(stdout)
        pathlib.Path(self.output()[1].path).touch()
