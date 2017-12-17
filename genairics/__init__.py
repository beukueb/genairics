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

import luigi, os, logging
from luigi.util import inherits
from plumbum import local, colors

## Helper function
class LuigiStringTarget(str):
    """
    Using this class to wrap a string, allows
    passing it between tasks through the output-input route
    """
    def exists(self):
        return bool(self)

# Set genairics script dir to be used with % formatting
gscripts = '{}/scripts/%s'.format(os.path.dirname(__file__))

# Set up logging
logger = logging.getLogger(__package__)
logger.setLevel(logging.INFO)
logconsole = logging.StreamHandler()
logconsole.setLevel(logging.WARNING)
logger.addHandler(logconsole)

typeMapping = {
    luigi.parameter.Parameter: str,
    luigi.parameter.ChoiceParameter: str,
    luigi.parameter.BoolParameter: bool,
    luigi.parameter.FloatParameter: float,
    luigi.parameter.IntParameter: int
}

# Generic tasks
class setupProject(luigi.Task):
    """
    setupProject prepares the logistics for running the pipeline and directories for the results
    optionally, the metadata can already be provided here that is necessary for e.g. differential expression analysis
    """
    project = luigi.Parameter(description='name of the project. if you want the same name as Illumina run name, provide here')
    datadir = luigi.Parameter(description='directory that contains data in project folders')
    metafile = luigi.Parameter('',description='metadata file for interpreting results and running differential expression analysis')
    
    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/plumbing'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/summaries'.format(self.datadir,self.project)),
            luigi.LocalTarget('{}/../results/{}/plumbing/pipeline.log'.format(self.datadir,self.project))
        )

    def run(self):
        os.mkdir(self.output()[0].path)
        os.mkdir(self.output()[0].path+'/metadata')
        if self.metafile:
            from shutil import copyfile
            copyfile(self.metafile,self.output()[0].path+'/metadata/')
        os.mkdir(self.output()[1].path)
        os.mkdir(self.output()[2].path)

@inherits(setupProject)
class setupLogging(luigi.Task):
    """
    Registers the logging file
    Always needs to run, to enable logging to the file
    """
    def requires(self):
        return self.clone_parent()

    def run(self):
        #TODO put in a decorator for run functions, or rely on true luigi running
        if not self.requires().complete(): self.requires().run()
        
        logger = logging.getLogger(__package__)
        logfile = logging.FileHandler(self.input()[3].path)
        logfile.setLevel(logging.INFO)
        logfile.setFormatter(
            logging.Formatter('{asctime} {name} {levelname:8s} {message}', style='{')
        )
        logger.addHandler(logfile)

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
    runTaskAndDependencies(pipeline)
