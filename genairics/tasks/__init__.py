#-*- coding: utf-8 -*-
"""genairics custom task classes.
The tasks in the sample and project subpackages,
should only inherit and not require other tasks,
as they are intended to be used in genairics.pb.PipelineWrapper
classes, which will coordinate the requirements.

Usually subclasses luigi.Task
"""
import luigi, logging, os, pathlib
from luigi.util import inherits, requires
from genairics.config import config
from genairics.mixins import ProjectMixin
from genairics.targets import ProgramTarget

class setupProject(luigi.Task):
    """setupProject prepares the logistics for running the pipeline and directories for the results
    optionally, the metadata can already be provided here that is necessary for e.g. differential expression analysis
    """
    project = luigi.Parameter(description='name of the project; used as folder name within datadir and resultsdir')
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
            if not 'end' in kwargs:
                kwargs['end'] = ''
            print(*args,file=stdout,**kwargs)
            file.log(level,stdout.getvalue())
        return printfunction

    @property
    def projectSetupParams(self):
        """Returns the setupProject param dict
        for intantiating other datasource tasks
        """
        sp = self.clone_parent()
        return {
            p:sp.__getattribute__(p)
            for p in sp.get_param_names()
        }

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

    def getSampleResultFiles(self,filename):
        """Get all sample files matching `filename`

        Args:
            filename (str): File name, can contain wildcards, 
              and subdirs but should not start with '/'.
        """
        import glob, os
        return glob.glob(
            os.path.join(self.projectresults,'sampleResults','*',filename)
        )

## Individual sample tasks
class SampleConfig(luigi.Config):
    """Generic sample specific parameters for input and output,
    that should not be inherited by tasks that are exposed directly
    to the end-user.
    """
    sampleDir = luigi.Parameter(description = 'dir with sample fastq files')
    outfileDir = luigi.Parameter(description = 'sample output dir')

@inherits(SampleConfig)
class SampleTask(luigi.Task):
    """Task with the minimum set of sample parameters for input/output
    and convenience properties.
    """
    
class setupSequencedSample(SampleTask):
    """Sets up the output directory for a specified sequenced sample
    can be either single-end or paired end

    this is intended as the starting point of pipelines that fully process 1 sample a time
    """
    pairedEnd = luigi.BoolParameter(default = False, description = 'True in case of paired-end sequencing')

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

# Program dependency tasks
from genairics.config import program_dependency_config
ponfig = program_dependency_config()

class ProgramDependencyBase(luigi.Task):
    name = luigi.Parameter(description='Program name.')
    remote = luigi.Parameter('',description='Machine on which depedency should exist. Empty string for local machine.')
    
    def output(self):
        return ProgramTarget(self.name,self.remote)

    @property
    def prog(self):
        if not self.complete():
            self.run()
        return self.output().prog
    
    def run(self):
        """
        Inheriting task classes have to overwrite to implement
        installation instructions for program dependencies.
        """
        pass

class ProgramDependencyPackage(ProgramDependencyBase):
    package = luigi.Parameter('',description='Program package name.')
    
    def install_package(self):
        import platform, plumbum as pl
        system = platform.system()
        machine = pl.SshMachine(self.remote) if self.remote else pl.local
        if system == 'Darwin':
            retcode,stdout,stderr = machine['brew'][
                'install',self.package if self.package else self.name
            ].run()
        elif system == 'Linux':
            retcode,stdout,stderr = machine[ponfig.package_manager][
                ponfig.package_install_cmd_args
            ][
                self.package if self.package else self.name
            ].run()

    def run(self):
        self.install_package()

class ProgramDependencySource(ProgramDependencyBase):
    source = luigi.Parameter('',description='Program source url.')
    buildcmd = luigi.Parameter('make',description='Command for building from within source dir.')
    builddir = luigi.Parameter('bin',description='Directory where software will be build relative to source dir.')
    
    def build_program(self):
        import plumbum as pl, sys, glob
        machine = pl.SshMachine(self.remote) if self.remote else pl.local
        with machine.cwd(ponfig.repodir):
            (machine['wget'][self.source] > sys.stdout)()
            archive = self.source.split('/')[-1] #this is going to break if archive name not in url
            if '.tar.' in archive:
                (machine['tar']['-xvf',archive] > sys.stdout)()
                sourcedir = archive[:archive.index('.tar.')]
                with machine.cwd(sourcedir):
                    (machine[self.buildcmd] > sys.stdout)()
                    for binary in glob.glob(os.path.join(self.builddir,'*')):
                        binary = os.path.join(
                            ponfig.repodir,
                            sourcedir,
                            binary
                        )
                        # Make a symbolic link to each generated binary
                        os.symlink(
                            binary,
                            os.path.join(ponfig.prefix,'bin',os.path.basename(binary))
                        )
        
    def run(self):
        self.build_program()
