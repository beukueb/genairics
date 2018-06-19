#!/usr/bin/env python
"""
genairics: GENeric AIRtight omICS pipelines

Copyright (C) 2017  Christophe Van Neste

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program at the root of the source package.
"""

import luigi, os, pathlib, logging
from luigi.util import inherits, requires
from plumbum import local, colors
from multiprocessing import cpu_count

# matplotlib => setup for exporting svg figures only
# work around for plotting issues with matplotlib
import platform, matplotlib
if platform.system() != 'Darwin': matplotlib.use('SVG')

## genairics configuration (integrated with luigi config)
class genairics(luigi.Config):
    general_log = luigi.Parameter(default=os.path.expanduser('~/.genairics.log'))
    datadir = luigi.Parameter(
        default = os.environ.get('GAX_DATADIR',os.path.expanduser('~/data')),
        description = 'default directory that contains data in project subfolders'
    )
    resultsdir = luigi.Parameter(
        default = os.environ.get('GAX_RESULTSDIR',os.path.expanduser('~/results')),
        description = 'default directory that contains results in project subfolders'
    )
    resourcedir = luigi.Parameter(
        default = os.environ.get('GAX_RESOURCES',os.path.expanduser('~/resources')),
        description = 'default directory where resources such as genomes are stored'
    )
    basespaceAPIfile = luigi.Parameter(
        default = os.path.expanduser('~/.BASESPACE_API'),
        description = 'file containing BaseSpace API token'
    )
    nodes = luigi.IntParameter(
        default = os.environ.get('PBS_NUM_NODES',1),
        description = 'nodes to use to execute pipeline'
    )
    threads = luigi.IntParameter(
        default = cpu_count(),
        description = 'processors per node to request'
    )
    ui = luigi.ChoiceParameter(
        default = 'wui',
        choices = ['wui','gui','cli'],
        description = 'user interface mode'
    )
    browser = luigi.Parameter(
        default = 'firefox',
        description = 'browser to use for wui'
    )

config = genairics()

def saveConfig(configs):
    """
    saves every config in list configs to LUIGI_CONFIG_PATH destination,
    or - if not provided - in 'luigi.cfg' in current working directory
    """
    if type(configs) != list: configs = [configs]
    with open(os.environ.get('LUIGI_CONFIG_PATH','luigi.cfg'),'wt') as outconfig:
        for config in configs:
            outconfig.write('[{}]\n'.format(config.get_task_family()))
            for param in config.get_param_names():
                outconfig.write('{}={}\n'.format(param,config.__getattribute__(param)))

## Helper function
class LuigiStringTarget(str):
    """
    Using this class to wrap a string, allows
    passing it between tasks through the output-input route
    """
    def exists(self):
        return bool(self)

class LuigiLocalTargetAttribute(luigi.LocalTarget):
    """LocalTargetAttribute extends luigi.LocalTarget,
    reguiring the existence of the LocalTarget and a 
    specific attribute set in that target

    Args:
        patch (str): file path passed to LocalTarget.
        attribute (str): Attribute name that needs to exist in LocalTarget file.
        attrvalue (bytes): Attrbute value. Will be encoded to bytes if str.
            Default value is b'set', just indicating that attirbute has been set.
    """
    def __init__(self,path,attribute,attrvalue=b'set',**kwargs):
        if isinstance(attrvalue, str): attrvalue = attrvalue.encode()
        super().__init__(path,**kwargs)
        self.attribute = attribute
        self.attrvalue = attrvalue

    def pathExists(self):
        """Returns the LocalTarget exists result.
        Can be useful to check prior to touching the attribute,
        as this would automatically create the file.
        """
        return super().exists()
        
    def exists(self):
        """Returns True if file path exists and file attribute
        is equal to attrvalue.
        """
        if self.pathExists():
            try:
                import xattr
                x = xattr.xattr(self.path)
                if x.has_key(self.attribute):
                    return x.get(self.attribute) == self.attrvalue
            except OSError:
                with open(self.attrfilename(),'rb') as attrfile:
                    return attrfile.read() == self.attrvalue
        # All other options return False
        return False

    def touch(self):
        """touch LocalTarget file and set extended attribute to attrvalue
        If file does not exist it will be created.
        """
        pathlib.Path(self.path).touch()
        try:
            import xattr
            x = xattr.xattr(self.path)
            x.set(self.attribute,self.attrvalue)
        except OSError:
            with open(self.attrfilename(),'wb') as attrfile:
                attrfile.write(self.attrvalue)

    def attrfilename(self):
        """If xattr is not os/fs supported,
        this function provides a filename 
        where attrvalue can be stored.

        TODO upon removing target this attrfile is not removed
        """
        return os.path.join(
            os.path.dirname(self.path),
            '.{}_{}.attr'.format(
                os.path.basename(self.path),
                self.attribute
            )
        )
        
# Set genairics script dir to be used with % formatting
gscripts = '{}/scripts/%s'.format(os.path.dirname(__file__))

# Set up logging
logger = logging.getLogger(__package__)
logger.setLevel(logging.INFO)
logconsole = logging.StreamHandler()
logconsole.setLevel(logging.DEBUG)
logger.addHandler(logconsole)
if config.general_log:
    logfile = logging.FileHandler(config.general_log)
    logfile.setLevel(logging.WARNING)
    logfile.setFormatter(
        logging.Formatter('{asctime} {name} {levelname:8s} {message}', style='{')
    )
    logger.addHandler(logfile)

typeMapping = {
    luigi.parameter.Parameter: str,
    luigi.parameter.ChoiceParameter: str,
    luigi.parameter.BoolParameter: bool,
    luigi.parameter.FloatParameter: float,
    luigi.parameter.IntParameter: int
}

# Generic tasks
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

    def getLogger(self):
        """Get project logger

        Setups logging for the project and returns the logger.
        """
        logger = logging.getLogger(__package__)
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
        return logger

@requires(setupProject)
class ProjectTask(luigi.Task):
    """ProjectTask

    Class intended for inheriting instead of luigi.Task for defining
    tasks that have setupProject in their parameter inheritance or
    requirements.

    Defines methods related to the project management, such as
    getting the project logger.
    """
    def getLogger(self):
        return self.clone(setupProject).getLogger()
    
#TODO REMOVE setupLogging
@requires(setupProject)
class setupLogging(luigi.Task):
    """Registers the logging file

    Always needs to run, to enable logging to the file

    DEPRACATED you should use the setupProject getLogger function
    """
    def output(self):
        return luigi.LocalTarget(os.path.join(self.input()[1].path,'pipeline.log'))
    
    def run(self):
        if not self.requires().complete(): self.requires().run()
        
        logger = logging.getLogger(__package__)
        logfile = logging.FileHandler(self.output().path)
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(
            logging.Formatter('{asctime} {name} {levelname:8s} {message}', style='{')
        )
        logger.addHandler(logfile)
        if not self.complete(): pathlib.Path(self.output().path).touch()
            
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
    
# genairic (non-luigi) directed workflow runs
def runTaskAndDependencies(task):
    #TODO -> recursive function for running workflow, check luigi alternative first
    if not task.complete():
        dependencies = task.requires()
        try:
            for dependency in dependencies:
                try:
                    if not dependency.complete(): runTaskAndDependencies(dependency)
                except AttributeError:
                    dependency = task.requires()[dependency]
                    if not dependency.complete(): runTaskAndDependencies(dependency)
        except TypeError:
            dependency = task.requires()
            if not dependency.complete(): runTaskAndDependencies(dependency)
        logger.info(colors.underline | task.task_family)
        task.run()
    else:
        logger.info(
                '{}\n{}'.format(colors.underline | task.task_family,colors.green | 'Task finished previously')
        )
        
def runWorkflow(pipeline):
    pipeline.clone(setupLogging).run()
    logger.info(pipeline)
    # different options to start pipeline, only 1 not commented out
    scheduler = luigi.scheduler.Scheduler()
    worker = luigi.worker.Worker(scheduler = scheduler, worker_processes = 1)
    worker.add(pipeline)
    worker.run() # this could also be started in a thread => thread.start_new_thread(w.run, ())
    #luigi.build([pipeline]) #can start any list of tasks and also starts scheduler, worker
    #runTaskAndDependencies(pipeline) # genairics own dependency checking
