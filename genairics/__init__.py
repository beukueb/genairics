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
from plumbum import local, colors

# matplotlib => setup for exporting svg figures only
# work around for plotting issues with matplotlib
import platform, matplotlib
if platform.system() != 'Darwin': matplotlib.use('SVG')

# Configuration
from genairics.config import config, saveConfig

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

# genairics tasks
from genairics.tasks import setupProject, setupSequencedSample, processSamplesIndividually

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
        
def runWorkflow(pipeline,verbose=True):
    from genairics.tasks import setupProject
    # Log start runWorkflow pipeline
    pipeline.clone(setupProject).logger.info(pipeline)
    # different options to start pipeline, only 1 not commented out
    scheduler = luigi.scheduler.Scheduler()
    worker = luigi.worker.Worker(scheduler = scheduler, worker_processes = 1)
    worker.add(pipeline)
    worker.run() # this could also be started in a thread => thread.start_new_thread(w.run, ())
    #luigi.build([pipeline]) #can start any list of tasks and also starts scheduler, worker
    #runTaskAndDependencies(pipeline) # genairics own dependency checking
