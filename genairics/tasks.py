#!/usr/bin/env python
"""genairics custom task classes

Usually subclasses luigi.Task
"""
import luigi, logging, os, pathlib
from luigi.util import inherits, requires
from genairics.config import config
from genairics.mixins import ProjectMixin

class setupProject(luigi.Task):
    """setupProject prepares the logistics for running the pipeline and directories for the results
    optionally, the metadata can already be provided here that is necessary for e.g. differential expression analysis
    """
    project = luigi.Parameter(description='name of the project. if you want the same name as Illumina run name, provide here')
    datadir = luigi.Parameter(config.datadir, description='directory that contains data in project subfolders')
    resultsdir = luigi.Parameter(config.resultsdir, description='directory that contains results in project subfolders')
    metafile = luigi.Parameter('',description='metadata file for interpreting results and running differential expression analysis')
    
    def output(self):
        return (
            luigi.LocalTarget(os.path.join(self.resultsdir,self.project)),
            luigi.LocalTarget(os.path.join(self.resultsdir,self.project,'plumbing')),
            luigi.LocalTarget(os.path.join(self.resultsdir,self.project,'summaries')),
        )

    def run(self):
        if not self.complete():
            os.mkdir(self.output()[0].path)
            os.mkdir(os.path.join(self.output()[0].path,'metadata'))
            if self.metafile:
                from shutil import copyfile
                copyfile(self.metafile,os.path.join(self.output()[0].path,'/metadata/'))
            os.mkdir(self.output()[1].path)
            os.mkdir(self.output()[2].path)

    @property
    def logger(self):
        """Get project logger

        Setups logging for the project and returns the logger.
        """
        # Create project folders if necessary
        if not self.complete(): self.run()

        # Logging setup
        logger = logging.getLogger(__package__)
        # Filehandle
        logfilename = os.path.join(
            self.output()[1].path,
            'pipeline.log'
        )
        if logfilename not in [
                fh.baseFilename for fh in logger.handlers if isinstance(fh,logging.FileHandler)
        ]:
            logfile = logging.FileHandler(logfilename)
            logfile.setLevel(logging.INFO)
            logfile.setFormatter(
                logging.Formatter('{asctime} {name} {levelname:8s} {message}', style='{')
            )
            logger.addHandler(logfile)
        # Stdout
        if not [fh for fh in logger.handlers if isinstance(fh,logging.StreamHandler)]:
            logconsole = logging.StreamHandler()
            logconsole.setLevel(logging.DEBUG)
            logger.addHandler(logconsole)
        return logger

@requires(setupProject)
class ProjectTask(luigi.Task,ProjectMixin):
    """ProjectTask

    Class intended for inheriting instead of luigi.Task for defining
    tasks that have setupProject in their parameter inheritance or
    requirements.

    Defines methods related to the project management, such as
    getting the project logger.
    """
    @property
    def print(self):
        """
        Generates a printfunction that will output to the logger.
        """
        logger = self.logger
        def printfunction(*args,file=logger,level=logging.INFO,**kwargs):
            """
            Args:
                file (logger): print `file` argument redefined to point to logger
                level (int): Logging level, e.g. `logging.INFO` or `20`
            """
            from io import StringIO
            stdout = StringIO()
            print(*args,file=stdout,*kwargs)
            file.log(level,stdout.getvalue())
        return printfunction

    def CheckpointTarget(self):
        return luigi.LocalTarget(
            os.path.join(
                self.resultsdir,
                self.project,
                'plumbing/.completed_{}'.format(self.task_family)
            )
        )

    def touchCheckpoint(self):
        pathlib.Path(self.CheckpointTarget().path).touch()
                
class setupSequencedSample(luigi.Task):
    """Sets up the output directory for a specified sequenced sample
    can be either single-end or paired end

    this is intended as the starting point of pipelines that fully process 1 sample a time
    """
    sampleDir = luigi.Parameter(description = 'dir with sample fastq files')
    pairedEnd = luigi.BoolParameter(default = False, description = 'True in case of paired-end sequencing')
    outfileDir = luigi.Parameter(description = 'sample output dir')

    def output(self):
        return luigi.LocalTarget(self.outfileDir)
        
    def run(self):
        if not self.output().exists(): os.mkdir(self.output().path)

#@inherits(setupProject)
class processSamplesIndividually(luigi.Task):
    """Requires as parameter the wrapper task for the
    specific pipeline that includes all tasks that need
    to be performed for all samples individually.
    Tasks that merge individual sample results need
    to require this task and need to inherit from setupProject
    as setupProject parameters are used in processSamplesIndividually
    through the requiredSampleTask.
    """
    requiredSampleTask = luigi.TaskParameter(
        description = "the wrapper task that will handle execution of processing all samples individually"
    )

    def requires(self):
        return self.requiredSampleTask

    def run(self):
        pathlib.Path(self.output()[0].path).touch()

    def output(self):
        return (
            luigi.LocalTarget( # complete check point file
                os.path.join(
                    self.requiredSampleTask.resultsdir,
                    self.requiredSampleTask.project,
                    'plumbing/completed_{}'.format(self.task_family)
                )
            ),
            luigi.LocalTarget( # sample results location (should be made by required task)
                os.path.join(
                    self.requiredSampleTask.resultsdir,
                    self.requiredSampleTask.project,
                    'sampleResults'
                )
            )
        )

