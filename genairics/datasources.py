# -*- coding: utf-8 -*-
"""Datasources

Connecting genairics pipelines to different (raw) data sources.

Todo:
    * https://support.illumina.com/sequencing/sequencing_software/bcl2fastq-conversion-software.html
"""

import luigi, logging, os, sys, itertools, glob, pathlib
from luigi.util import inherits, requires
from plumbum import local
from genairics import config, setupProject, setupSequencedSample
from genairics.resources import RetrieveGenome

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

@inherits(setupProject)
class ENAsource(luigi.Task):
    """
    Downloads fastq's from given ENA accession number
    """
    ENAaccession = luigi.Parameter('',description='sequencing run project name')

@inherits(setupProject)
@inherits(RetrieveGenome)
class ENAtestSource(luigi.Task):
    """
    Downloads fastq's from given ENA accession number
    """
    def requires(self):
        return [
            self.clone(setupProject),
            self.clone(RetrieveGenome)
        ]

    def run(self):
        import requests
        r = requests.get('https://www.ebi.ac.uk/ena/data/taxonomy/v1/taxon/scientific-name/{}'.format(
            genome.replace('_','%20'))
        )
        taxID = r.json()[0]['taxId']
        r = requests.get('https://www.ebi.ac.uk/ena/data/view/Taxon:{}&portal=read_experiment;display=xml'.format(taxID))
        #https://www.ebi.ac.uk/ena/data/warehouse/search?query=%22cell_line=%22IMR-32%22%22&domain=sample
        #https://www.ebi.ac.uk/ena/data/warehouse/search?query=%22geo_accession=%22GSE37599%22%22&domain=study
        raise NotImplementedError
    
@inherits(setupProject)
@inherits(RetrieveGenome)
class SimulatedSource(luigi.Task):
    def requires(self):
        return [
            self.clone(setupProject),
            self.clone(RetrieveGenome)
        ]

    def run(self):
        import gffutils
        #transform func needed for ensembl gtf => see gffutils docs examples
        def transform_func(x):
            if 'transcript_id' in x.attributes:
                x.attributes['transcript_id'][0] += '_transcript'
            return x
        db = gffutils.create_db(
            glob.glob(os.path.join(self.input()[1].path,'annotation/*.gtf'))[0],':memory:',
            id_spec={'gene': 'gene_id', 'transcript': "transcript_id"},
            merge_strategy="create_unique",
            transform=transform_func,
            keep_order=True
        )
        transcripts = db.features_of_type('transcript')
        #TODO work in progress
        #get transcripts -> to fasta file -> then R polyester for simulation
        raise NotImplementedError
