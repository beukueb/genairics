#-*- coding: utf-8 -*-
"""genairics pb module for plumbing

Classes and functions for organzing the pipelines.
All used luigi functions and classes are imported here,
and thus made available by importing pb from genairics.
"""

# luigi imports
from luigi import Parameter, BoolParameter, IntParameter, FloatParameter, ListParameter
from luigi import Config, Task, LocalTarget, WrapperTask
from luigi.util import inherits, requires

# genairics imports
from genairics.tasks import setupProject, ProjectTask, SampleConfig
from genairics.tasks import setupSequencedSample as BaseSampleTask
from genairics.mixins import SampleTaskMixin

# general imports
import os

# Pipeline meta tasks
class Pipeline(ProjectTask):
    """Pipeline task

    Use this task class to enumerate and yield the pipeline tasks
    in the requires method, just like luigi.WrapperTask but with
    extra checkpoint for the pipeline and allowing for automated 
    discovery of pipelines within genairics.pipelines subdir (TODO).
    """
    def output(self):
        return self.CheckpointTarget()

    def run(self):
        self.touchCheckpoint()

sample_specific_params = set(SampleConfig.get_param_names())

class PipelineWrapper(Pipeline):
    """
    Produces an executable pipeline that can be defined as follows:

    class salmonellaGenome(pb.PipelineWrapper):
      def tasks(self):
        yield DataSource
        with self.sample_context() as samples:
            for sample in samples:
                yield sample
                yield QualityCheck
                yield AlignSample
        yield PCAplotCounts
        yield mergeAlignResults

    It will then obtain required parameters by:
    >>> salmonellaGenome.inherit_task_parameters()
    """
    params_inherited = False
    baseTask = setupProject
    
    @classmethod
    def inherit_task_parameters(cls):
        pipeline = inherits(cls.baseTask)(cls)
        from unittest.mock import MagicMock
        for t in cls.tasks(MagicMock()): # passing cls as stub for `self`
            if issubclass(t,Task) and t is not cls.baseTask:
                pipeline = inherits(t)(pipeline)
        for param in pipeline.get_param_names():
            if param in sample_specific_params and cls.baseTask is setupProject:
                delattr(cls,param)
                #continue # sample specific params do not need to be inherited
            #setattr( # cls == pipeline, so no need to setattr again
            #    cls,param,
            #    getattr(pipeline,param)
            #)
        cls.params_inherited = True

    def requires(self):
        yield self.clone(self.baseTask)
        self.previousTask = self.baseTask
        for task in self.tasks():
            # Inherit from previousTask and set for next
            task = requires(self.previousTask)(task)
            self.previousTask = task
            
            # Sample context specific task
            if hasattr(self,'active_context'):
                for sampleDir, outfileDir in self.sample_generator():
                    sampleTaskInstance = task(
                        sampleDir = sampleDir,
                        outfileDir = outfileDir,
                         **{
                             k:self.param_kwargs[k]
                             for k in set(task.get_param_names()) - sample_specific_params
                             }
                    )
                    try:
                        self.active_context[task].append(sampleTaskInstance)
                    except KeyError:
                        # This insures that the active_context dictionary
                        # contains the last sample task run with  all its instances
                        self.active_context = {task:[sampleTaskInstance]}
                    yield sampleTaskInstance
            # General project tasks    
            elif issubclass(task,Task) and task is not self.baseTask:
                yield self.clone(task)

    def debug_requirements(self,jumpSameClassTasks=True):
        """yield the first task that needs completion.
        Add the end returns all task classes that had
        uncompleted tasks.
        
        Args:
            jumpSameClassTasks (bool): If true, similar uncompleted tasks,
              are jumped
        """
        uncompletedTaskClasses = set()
        for task in self.requires():
            if not task.complete() and not (jumpSameClassTasks and type(task) in uncompletedTaskClasses):
                uncompletedTaskClasses.add(type(task))
                yield task
        return uncompletedTaskClasses
        
    # Sample context management
    def sample_context(self):
        self.active_context = {'initiated': True}
        return self
    
    def __enter__(self):
        if self.active_context:
            if self.params_inherited:
                # Prepare sample generator
                import glob
                sampleDirs = glob.glob(os.path.join(self.datadir, self.project, '*'))
                sampleResultsDir = os.path.join(self.resultsdir, self.project, 'sampleResults')
                if sampleDirs:
                    if not os.path.exists(sampleResultsDir):
                        # Creating sampleResults dir here, upon entering sample context and when
                        # sample data dirs ready for processing (could also do this in setupProject)
                        os.mkdir(sampleResultsDir)
                    self.sample_generator = lambda: ( # Creates a function to provide the generator on each call
                        ( # Generates tuples of the sample data and results directory
                            d,
                            os.path.join(sampleResultsDir, os.path.basename(d))
                        )
                        for d in sampleDirs
                    )
                    return self.sample_generator
                else:
                    self.sample_generator = lambda: []
                    return [None]
                    #raise Exception('Dynamic dependency not yet met, cannot provide sample directories.')
            else: # Parameters are not yet inherited,
                # return a stub to expose sample tasks for inheritance
                return [None]

    def __exit__(self, type, value, tb):
        # Set up new base task for merging tasks that come after the sample context
        self.previousTask = SampleContextFinished()

        del self.active_context, self.sample_generator
        if not tb:
            return True
        else: return False

class SamplePipelineWrapper(SampleTaskMixin,PipelineWrapper):
    baseTask = BaseSampleTask

class SampleContextFinished(ProjectTask):
    lastSampleTasks = ListParameter([],description='list of last set of sample tasks that should have completed')

    def output(self):
        return self.CheckpointTarget()
        
    def run(self):
        allCompleted = bool(self.lastSampleTasks) # if empty task list will be false
        for task in self.lastSampleTasks:
            if not task.complete():
                allCompleted = False
        if allCompleted:
            self.touchCheckpoint()
        else:
            import warnings
            warnings.warn('No sample tasks have been completed')
        
