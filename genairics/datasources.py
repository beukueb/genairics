#!/usr/bin/env python

import luigi, logging, os, sys, itertools
from luigi.util import inherits
from genairics import setupProject

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
    BASESPACE_API_TOKEN = (
        luigi.Parameter(os.environ.get('BASESPACE_API_TOKEN'),
                        description='BASESPACE_API_TOKEN already set'
                        ,significant=False) if os.environ.get('BASESPACE_API_TOKEN')
        else luigi.Parameter('NOT_YET_SET',
                             description=
                             'set "$BASESPACE_API_TOKEN" in your bash config files. not necessary or recommended to provide as CLI argument',
                             significant=False)
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
        
        # Find the project ID
        request = 'http://api.basespace.illumina.com/v1pre3/users/current/projects?access_token=%s&limit=1000' % (self.BASESPACE_API_TOKEN,)
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
        request = 'http://api.basespace.illumina.com/v1pre3/projects/%s/samples?access_token=%s&limit=1000' % (projectID, self.BASESPACE_API_TOKEN)
        r = requests.get(request)
        for sample in r.json()['Response']['Items']:
            (sampleName, sampleID) = (sample['Name'], sample['Id'])
            logger.info('Retrieving '+sampleName)
            sampleDir = os.path.join(outtempdir, sampleName)
            os.mkdir(sampleDir)
            sample_request = 'http://api.basespace.illumina.com/v1pre3/samples/%s/files?access_token=%s' % (sampleID, self.BASESPACE_API_TOKEN)
            sample_request = requests.get(sample_request)
            for sampleFile in sample_request.json()['Response']['Items']:
                filePath = os.path.join(sampleDir, sampleFile['Path'])
                logger.info('Path: '+filePath)
                if not os.path.isfile(filePath):
                    file_request = 'http://api.basespace.illumina.com/%s/content?access_token=%s' % (sampleFile['Href'], self.BASESPACE_API_TOKEN)
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
