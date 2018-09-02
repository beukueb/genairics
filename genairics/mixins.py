#-*- coding: utf-8 -*-
"""mixins defines interface classes

interface classes are not intended to be inherited as
primary class, but instead as secondary classes to add
functionality through the methods defined in the mixins

Example:
    >>> class LuigiTaskWithExtraMethod(luigi.Task,InterfaceClass):
    ...     pass
"""

import luigi, logging, os

class ProjectMixin(object):
    """ProjectMixin intended to be used on luigi.Tasks inheriting
    from setupProject

    Offers convenience property methods.
    """
    @property
    def logger(self):
        from genairics import setupProject
        return self.clone(setupProject).logger

    @property
    def projectdata(self):
        return os.path.join(
            self.datadir,
            self.project
        )    

    @property
    def projectresults(self):
        return os.path.join(
            self.resultsdir,
            self.project
        )

    @property
    def plumbdir(self):
        return os.path.join(
            self.resultsdir,
            self.project,
            'plumbing'
        )

class SampleTaskMixin(object):
    """Sample task specific functionality
    For now only redefines the checkpoint file location
    """
    def CheckpointTarget(self):
        return luigi.LocalTarget(
            os.path.join(
                self.resultsdir,
                self.project,
                'sampleResults',
                self.outfileDir,
                '.completed_{}'.format(self.task_family)
            )
        )
    
class PlumbumMixin(object):
    """PlumbumMixin class to offer 
    interface to plumbum local and redirect output to logger
    """
    def execute(self,command,*args,logger=None,retcode=0):
        """execute command and redirect output to logger

        Args:
           command (plumbum.commands.base.BoundCommand): The bound command to 
             run. If `*args` than they are still attached to the command.
           logger (loggin.Logger): If Task does not have logger property,
             needs to be provided here.
        """
        if args:
            command = command[args]
        if hasattr(self,'logger') and not logger:
            logger = self.logger
        elif not logger:
            raise Exception(
                'Provide logger arg, or use mixin class ProjectMixin to provide logger attribute'
            )
        retcode, stdout, stderr = command.run(retcode=retcode)
        if stdout: logger.info(stdout)
        if stderr: logger.warn(stderr)
