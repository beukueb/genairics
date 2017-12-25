#!/usr/bin/env python

import luigi, logging, os, sys, itertools
from luigi.util import inherits
from genairics import setupProject
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
        os.path.expanduser('~/.BASESPACE_API'),
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
