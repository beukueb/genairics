# -*- coding: utf-8 -*-
"""Datasources

Connecting genairics pipelines to different (raw) data sources.

Todo:
    * https://support.illumina.com/sequencing/sequencing_software/bcl2fastq-conversion-software.html
"""

import luigi, logging, os, sys, itertools, glob, pathlib
from luigi.util import inherits, requires
from plumbum import local, FG
from genairics import config, setupProject, setupSequencedSample
from genairics.resources import RetrieveGenome
from genairics.tasks import ProjectTask

# Basic data collecting task
class DataSource(ProjectTask):
    """Data source task

    Defines a parameter that specifies where the original data is located.
    This is a meta task, it will then execute the specific task, for downloading
    the data to the local data directory.

    Datasource providers:
        file:///file/path => simple file path location of a directory containing the raw data.
        basespace://NSQRun => NSQRun identifier.
        ena://projectID => ENA project ID.
        rsync://remote/location => what you would use as source in rsync command
        test://[species/[release/[genometype/]]](DNA|RNA)[?coverage=20&replicates=...]
    """
    source = luigi.Parameter('',
        description = '''Data location. Format should be [provider://]path
If no provider, it is assumed to be a file path location. 
Providers: `file`, `basespace`, `ena`, `rsync`
'''
    )
    
    def output(self):
        return luigi.LocalTarget(self.projectdata)

    def run(self):
        import re
        from plumbum import colors
        source_re = re.compile(r'^(?P<provider>\S+)://(?P<location>\S*)$')
        source_m = source_re.match(self.source)
        if source_m:
            provider, location = source_m.groups()
        else: # considered file location if no provider
            provider, location = 'file', self.source
        # Log choice
        self.print(
            'Retrieving', colors.green | location,
            'through', colors.green | provider
        )
        # Data source cases:
        if provider == 'file':
            # In case the data is a local file path, the directory is linked to the datadir
            location = os.path.realpath(location)
            os.symlink(location,self.output().path)
        elif provider == 'rsync':
            rsyncsrc = RsyncSource(
                remoteSource = location,
                **self.projectSetupParams
            )
            rsyncsrc.run()
        elif provider == 'basespace':
            bssource = BaseSpaceSource(
                NSQrun = location,
                **self.projectSetupParams
            )
            bssource.run()
        elif provider == 'ena':
            enasource = ENAsource(
                ENAaccession = location,
                **self.projectSetupParams
            )
            enasource.run()
        elif provider == 'test':
            genome_re = re.compile(
                r'(?:(?P<species>[a-z,A-Z,_,\-]+)/)?'+
                r'(?:(?P<release>\d+)/)?'+
                r'(?:(?P<genomeType>toplevel)/)?'+
                '(?P<options>(?:DNA|RNA)\S*)',
                re.IGNORECASE
            )
            genome_specs = genome_re.match(location).groupdict()
            genome_specs = {k:genome_specs[k] for k in genome_specs if genome_specs[k]}
            options = genome_specs.pop('options')
            testsource = SimulatedSource(
                testCharacteristics = options,
                **genome_specs,
                **self.projectSetupParams
            )
            testsource.run()
        else:
            raise Exception('Provider "{}" unknown'.format(provider))
    
# Specific data collecting tasks
## rsync
@inherits(setupProject)
class RsyncSource(luigi.Task):
    """rsync a remote source
    that will serve as the data source for the pipeline
    """
    remoteSource = luigi.Parameter('',description='the source in an rsync command')

    def output(self):
        return luigi.LocalTarget('{}/{}'.format(self.datadir,self.project))

    def run(self):
        tmpdir = self.output().path+'_rsyncing'
        if not os.path.exists(tmpdir): os.mkdir(tmpdir)
        local['rsync']['-avz',self.remoteSource,tmpdir] & FG
        os.rename(tmpdir,self.output().path)
    
## Illumina
@inherits(setupProject)
class BaseSpaceSource(luigi.Task):
    """
    Uses the BaseSpace API from Illumina for downloading.
    It takes the project name and downloads the fastq files.

    The task is completed when a datadir folder exists with the project name
    so if you do not need to download it, just manually put the data in the datadir
    with the project name.
    """
    NSQrun = luigi.Parameter('',description='sequencing run project name')
    basespace_API_file = luigi.Parameter(
        config.basespaceAPIfile,
        description = 'file that contains your basespace API token. Should only be readable by your user',
        significant = False
    )

    def requires(self):
        return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/{}'.format(self.datadir,self.project))
    
    def run(self):
        if os.path.exists(self.output().path):
            print('folder already downloaded')
            return
        
        import requests, tempfile
        logger = logging.getLogger(__package__)

        # Check if NSQrun is set, otherwise set to project name
        if not self.NSQrun:
            self.NSQrun = self.project
            logger.warning('NSQrun was not provided, assuming same as project %s' % self.project)

        # Load basespace token
        if os.path.exists(self.basespace_API_file):
            BASESPACE_API_TOKEN = open(self.basespace_API_file).read().strip().replace('BASESPACE_API_TOKEN=','')
        elif 'BASESPACE_API_TOKEN' in os.environ:
            BASESPACE_API_TOKEN = os.environ['BASESPACE_API_TOKEN']
        else:
            logger.error('BASESPACE_API_TOKEN not in file or environment')
            raise Exception()

        # Find the project ID
        request = 'http://api.basespace.illumina.com/v1pre3/users/current/projects?access_token=%s&limit=1000' % (BASESPACE_API_TOKEN,)
        r = requests.get(request)
        projectName = False
        for project in r.json()['Response']['Items']:
            if project['Name'] == self.NSQrun:
                (projectName, projectID) = (project['Name'], project['Id'])
                break
    
        if not projectName:
            logger.error('Project {} not found on BaseSpace'.format(self.NSQrun))
            raise Exception()

        # Prepare temp dir for downloading
        outtempdir = tempfile.mkdtemp(prefix=self.datadir+'/',suffix='/')

        # Find project sample IDs (max 1000)
        request = 'http://api.basespace.illumina.com/v1pre3/projects/%s/samples?access_token=%s&limit=1000' % (projectID, BASESPACE_API_TOKEN)
        r = requests.get(request)
        for sample in r.json()['Response']['Items']:
            (sampleName, sampleID) = (sample['Name'], sample['Id'])
            logger.info('Retrieving '+sampleName)
            sampleDir = os.path.join(outtempdir, sampleName)
            os.mkdir(sampleDir)
            sample_request = 'http://api.basespace.illumina.com/v1pre3/samples/%s/files?access_token=%s' % (sampleID, BASESPACE_API_TOKEN)
            sample_request = requests.get(sample_request)
            for sampleFile in sample_request.json()['Response']['Items']:
                filePath = os.path.join(sampleDir, sampleFile['Path'])
                logger.info('Path: '+filePath)
                if not os.path.isfile(filePath):
                    file_request = 'http://api.basespace.illumina.com/%s/content?access_token=%s' % (sampleFile['Href'], BASESPACE_API_TOKEN)
                    file_request = requests.get(file_request, stream=True)
                    with open(filePath,'wb') as outfile:
                        for chunk in file_request.iter_content(chunk_size=512):
                            outfile.write(chunk)
                #check downloas
                if sampleFile['Size'] != os.path.getsize(filePath):
                    logger.error('size of local file and BaseSpace file do not match')
                    raise Exception()

        # Rename tempdir to final project name dir
        os.rename(outtempdir,self.output().path)

## ENA
@requires(setupProject)
class ENAsource(luigi.Task):
    """
    Downloads fastq's from given ENA accession number
    """
    ENAaccession = luigi.Parameter('',description='sequencing run project name')

    def output(self):
        return luigi.LocalTarget(os.path.join(self.datadir,self.project))

    def run(self):
        import requests, io, pandas as pd, tempfile
        from plumbum import local, FG
        #projecturl = "http://www.ebi.ac.uk/ena/data/view/{}&display=xml" #did not give download location for fastqs
        projecturl = "https://www.ebi.ac.uk/ena/data/warehouse/filereport?accession={}&result=read_run&fields=run_accession,fastq_ftp,fastq_md5,fastq_bytes"
        r = requests.get(projecturl.format(self.ENAaccession))
        samples = pd.read_table(io.StringIO(r.text))

        # Prepare temp dir for downloading
        outtempdir = tempfile.mkdtemp(prefix=self.datadir+'/',suffix='/')
        for index, sample in samples.iterrows():
            try:
                sampledir = os.path.join(outtempdir,sample.run_accession)
                os.mkdir(sampledir)
                with local.cwd(sampledir):
                    for f in sample.fastq_ftp.split(';'):
                        local['wget']['http://'+f] & FG
            except AttributeError:
                import warnings
                warnings.warn('No ftp fastq download location for %s' % sample.run_accession)
                os.rmdir(sampledir)
                    
        # Rename tempdir to final project name dir
        os.rename(outtempdir,self.output().path)

# Simulated test data
@inherits(RetrieveGenome)
class SimulatedSource(ProjectTask):
    """Simulate data for testing pipelines, or comparing parameter settings.
    
    `location` parameter string needs to have the following structure:
      - RNA -> RNA[/?coverage=20&replicates=3&maxtranscripts=100]
      - DNA -> DNA[/?coverage=20&replicates=3]
    """
    testCharacteristics = luigi.Parameter('',description='characteristics of the simulated data')

    def required_resources(self):
        genome = self.clone(RetrieveGenome)
        if not genome.complete(): genome.run()
        return genome.output()
    
    def output(self):
        return luigi.LocalTarget(self.projectdata)

    def run(self):
        import re, gzip
        from urllib.parse import parse_qs
        settingsregex = re.compile(
            r'(?P<simultype>DNA|RNA)(?:/?\?(?P<typesettings>\S*))?',
            re.IGNORECASE
        )
        settings = settingsregex.match(self.testCharacteristics).groupdict()
        if settings['simultype'].upper() == 'RNA':
            # RNA transcript simulation
            import gffutils, pyfaidx
            from plumbum import local
            from genairics import gscripts
            genome = self.required_resources()
            genome_fasta = glob.glob(os.path.join(genome.path,'dna/*.fa'))[0]
            tmpdir = self.output().path+'_creating_test_data'

            # RNA settings
            RNAsettings = parse_qs(settings['typesettings'])
            try:
                coverage = int(RNAsettings['coverage'][0])
            except KeyError: coverage = 20 # default value
            try:
                replicates = int(RNAsettings['replicates'][0])
            except KeyError: replicates = 3 # default value
            try:
                maxtranscripts = int(RNAsettings['maxtranscripts'][0])
            except KeyError: maxtranscripts = False # default value
                
            # transform func needed for ensembl gtf => see gffutils docs examples
            def transform_func(x):
                if 'transcript_id' in x.attributes:
                    x.attributes['transcript_id'][0] += '_transcript'
                return x
            db = gffutils.create_db(
                glob.glob(os.path.join(genome.path,'annotation/*.gtf'))[0],':memory:',
                id_spec={'gene': 'gene_id', 'transcript': "transcript_id"},
                merge_strategy = "create_unique",
                transform = transform_func,
                keep_order = True,
                disable_infer_genes = True, # genes should already be in ensembl gtf
                disable_infer_transcripts = True # transcripts should already be in esembl gtf
            )
            transcripts = db.features_of_type('transcript')
            transcriptfilepath = os.path.join(self.projectresults,'metadata','transcripts.fa')
            fasta = pyfaidx.Fasta(genome_fasta)
            if maxtranscripts:
                from itertools import count
                tcount = count(1)
            with open(transcriptfilepath, 'wt') as fout:
                for transcript in transcripts:
                    fout.write('>{}\n{}\n'.format(
                        transcript.id,
                        transcript.sequence(fasta)
                    ))
                    if maxtranscripts:
                        i = next(tcount)
                        if i >= maxtranscripts: break
            
            # R polyester for simulation
            os.mkdir(tmpdir)
            with local.env(R_MODULE="SET"):
                local['bash'][
                    '-l','-c', ' '.join(
                        ['Rscript', gscripts % 'polyester_wrapper.R',
                        transcriptfilepath, str(coverage), str(replicates), tmpdir]
                )]()

            # Transform polyester fasta to gzipped fastq
            for polfile in glob.glob(os.path.join(tmpdir,'*')):
                polbase = os.path.basename(polfile)
                if polbase.startswith('sim_'):
                    # move sim metadata files to project metadata
                    os.rename(
                        polfile,
                        os.path.join(self.projectresults,'metadata',polbase)
                    )
                else: #create gzip fq files
                    sampledir = os.path.join(
                        os.path.dirname(polfile),
                        '_'.join(polbase.split('_')[:2])
                    )
                    if not os.path.exists(sampledir):
                        os.mkdir(sampledir)
                    polqfile = os.path.join(sampledir,polbase.replace('.fasta','.fastq.gz'))
                    with gzip.open(polqfile,'wt') as fout:
                        with open(polfile) as fin:
                            for line in fin:
                                if line.startswith('>'): fout.write('@'+line[1:])
                                else:
                                    fout.write(line)
                                    fout.write('+\n')
                                    fout.write('~'*(len(line)-1)+'\n')
                    os.unlink(polfile)
                                    
        elif settings['simultype'].upper() == 'DNA':
            raise NotImplementedError
        os.rename(tmpdir,self.output().path)

# Raw data preprocessing
class Sample2Dir(ProjectTask):
    """If the data source has all sample files in one directory,
    this task reorganises them based on a regex, everything that
    does not match the regex is put in a `.nomatch` subfolder.
    """
    reorgregex = luigi.Parameter(
        '',
        description = '''Regex that will be used for reorganizing 
sample files in sample dirs if provided, e.g. '(?P<sample>sample\d+)_not_used_in_dir_samle_name'
Files belonging to the same sample should have the same sample group.'''
    )

    def run(self):
        import os, re, glob
        tmpdir = self.projectdata + '_tmp'
        os.mkdir(tmpdir)
        nomatchdir = os.path.join(tmpdir,'.nomatch')
        if self.reorgregex:
            reorgregex = re.compile(self.reorgregex)
            for f in glob.glob(os.path.join(self.projectdata,'*')):
                filename = os.path.basename(f)
                match = reorgregex.search(filename)
                if match:
                    samplegroup = match.groupdict()['sample']
                    sampledir = os.path.join(tmpdir,samplegroup)
                    if not os.path.exists(sampledir): os.mkdir(sampledir)
                    os.rename(f, os.path.join(sampledir,filename))
                else:
                    if not os.path.exists(nomatchdir): os.mkdir(nomatchdir)
                    os.rename(f, os.path.join(nomatchdir,filename))
            os.rmdir(self.projectdata)
            os.rename(tmpdir,self.projectdata)
        self.touchCheckpoint()

    def output(self):
        return self.CheckpointTarget()

class CompressData(ProjectTask):
    """Compresses all files in the project data folder
    if they are not yet compressed, except for files or
    directories starting with `.`
    """
    def run(self):
        import os, gzip, shutil
        for dirpath, dirnames, filenames in os.walk(self.projectdata):
            if '/.' in dirpath: continue # not processing any directory having upstream dir starting with `.`
            for filename in filenames:
                if not filename.endswith('.gz') and not filename.startswith('.'):
                    #local['gzip']['-vf', os.path.join(dirpath,filename)] # ISSUE -> asks for user input
                    fullfname = os.path.join(dirpath,filename)
                    with open(fullfname,'rb') as f_in:
                        with gzip.open(fullfname+'.gz','wb') as f_out:
                            shutil.copyfileobj(f_in,f_out)
                    os.unlink(fullfname)
                    self.print('Compressed',fullfname)
        self.touchCheckpoint()
    
    def output(self):
        return self.CheckpointTarget()    

@requires(BaseSpaceSource)
class mergeFASTQs(luigi.Task):
    """
    Merge fastqs if one sample contains more than one fastq
    This task merges the fastq's for all samples.
    When running a per sample analysis you can also use the
    mergeSampleFASTQs.
    """
    dirstructure = luigi.Parameter(
        default='multidir',
        description='dirstructure of project datat directory: onedir (one file/sample) or multidir (one dir/sample)'
    )
    pairedEnd = luigi.BoolParameter(
        default=False,
        description='paired end sequencing reads'
    )
    removeOriginalFQs = luigi.BoolParameter(
        default=False,
        description='remove the folder with the original, unmerged FASTQ files'
    )
    
    def output(self):
        return (
            luigi.LocalTarget('{}/{}/.completed_{}'.format(self.datadir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/.{}.log'.format(self.datadir,self.project,self.task_family))
        )

    def run(self):
        if self.dirstructure == 'multidir' and not self.output()[0].exists():
            outdir = '{}/{}'.format(self.datadir,self.project)
            oridir = '{}/{}_original_FASTQs'.format(self.datadir,self.project)
            os.rename(outdir,oridir)
            os.mkdir(outdir)
            dirsFASTQs = local['ls'](oridir).split()
            for d in dirsFASTQs:
                (local['ls'] >> (self.output()[1].path))('-lh',os.path.join(oridir,d))
                if self.pairedEnd:
                    (local['cat'] > os.path.join(outdir,d+'_R1.fastq.gz'))(
                        *glob.glob(os.path.join(oridir,d,'*_R1_*.fastq.gz'))
                    )
                    (local['cat'] > os.path.join(outdir,d+'_R2.fastq.gz'))(
                        *glob.glob(os.path.join(oridir,d,'*_R2_*.fastq.gz'))
                    )
                else:
                    (local['cat'] > os.path.join(outdir,d+'.fastq.gz'))(
                        *glob.glob(os.path.join(oridir,d,'*.fastq.gz'))
                    )
            if self.removeOriginalFQs:
                import shutil
                shutil.rmtree(oridir)
                logger.warning('%s removed',oridir)
        # complete file and log file get touched even if no execution is necessary
        pathlib.Path(self.output()[0].path).touch()
        pathlib.Path(self.output()[1].path).touch()

@requires(setupSequencedSample)
class mergeSampleFASTQs(luigi.Task):
    """
    Merges the fastqs of one sample. Expects the `setupSequencedSample` `infile1` and `infile2`
    to be the directories with the original fastq's. Paired end is assumed if `infile2` is provided.
    """
    def output(self):
        infile1Target = luigi.LocalTarget(
            os.path.join(
                self.outfileDir,
                '{}{}.fastq.gz'.format(
                    os.path.basename(self.sampleDir),
                    '_R1' if self.pairedEnd else ''
                )
            )
        )
        infile2Target = luigi.LocalTarget(
            os.path.join(
                self.outfileDir,
                '{}_R2.fastq.gz'.format(os.path.basename(self.sampleDir))
            )
        ) if self.pairedEnd else None
        return (infile1Target,infile2Target) if self.pairedEnd else (infile1Target,)

    def run(self):
        if self.pairedEnd: #if paired-end
            (local['cat'] > self.output()[0].path+'_tmp')(
                *glob.glob(os.path.join(self.sampleDir,'*_R1_*.fastq.gz'))
            )
            (local['cat'] > self.output()[1].path)(
                *glob.glob(os.path.join(self.sampleDir,'*_R2_*.fastq.gz'))
            )
        else: #if single-end or treated as such
            (local['cat'] > self.output()[0].path+'_tmp')(
                *glob.glob(os.path.join(self.sampleDir,'*.fastq.gz'))
            )
        os.rename(self.output()[0].path+'_tmp', self.output()[0].path)

def groupfilelines(iterable, n=4, fillvalue=None):
    """
    read n files per iteration
    default n = 4 => read 1 fastq entry at a time

    >>> for lines in groupfilelines(f):
    ...     break
    """
    from itertools import zip_longest
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

@requires(mergeFASTQs)
class SubsampleProject(luigi.Task):
    """
    Takes a project datadir and subsamples the FASTQs to either an exact number of
    reads or a percentage of the original files
    """
    amount = luigi.FloatParameter(description='amount of reads to subsample')
    percentage = luigi.BoolParameter(
        False,
        description='amount of reads will be treated as the approximate percentage of reads of the sample'
    )
    seed = luigi.IntParameter(0,'seed to use for random selection')
    subsuffix = luigi.Parameter(
        default = '_subsampled',
        description = 'suffix to use for new subsampled data directory'
    )
    
    def output(self):
        return luigi.LocalTarget('{}/{}_subsampled'.format(self.datadir,self.project))

    def run(self):
        import gzip, random
        random.seed(self.seed)
        oridir = '{}/{}'.format(self.datadir,self.project)
        subdir = '{}/{}{}'.format(self.datadir,self.project,self.subsuffix)
        outdir = '{}_subsampling'.format(subdir)
        os.mkdir(outdir)
        for fqfile in glob.glob(
                os.path.join(
                    oridir,
                    '*._R1.fastq.gz' if self.pairedEnd else '*.fastq.gz'
                )):
            # Determine which reads to subsample
            reads = 0
            with gzip.open(fqfile) as gf1:
                for lines in groupfilelines(gf1): reads += 1
                gf1.seek(0)
                if self.percentage: self.amount = int(reads*self.amount)
                selectedReads = random.sample(range(reads),self.amount)
                with gzip.open(os.path.join(outdir,os.path.basename(fqfile)), 'wb') as gfout:
                    for i,lines in enumerate(groupfilelines(gf1)):
                        if i in selectedReads:
                            gfout.writelines(lines)
            if self.pairedEnd:
                fqfile2 = fqfile.replace('_R1.fastq.gz','_R2.fastq.gz')
                with gzip.open(fqfile2) as gf2, gzip.open(os.path.join(outdir,os.path.basename(fqfile2)), 'wb') as gfout:
                    for i,lines in enumerate(groupfilelines(gf2)):
                        if i in selectedReads:
                            gfout.writelines(lines)
        # renaming temporary outdir to final subdir
        os.rename(outdir,subdir)
                
