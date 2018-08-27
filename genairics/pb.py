#-*- coding: utf-8 -*-
"""genairics pb module for plumbing

Classes and functions for organzing the pipelines.
All used luigi functions and classes are imported here,
and thus made available by importing pb from genairics.
"""

# luigi imports
from luigi import Parameter, BoolParameter, IntParameter, FloatParameter
from luigi import Config, Task, LocalTarget, WrapperTask
from luigi.util import inherits, requires

# genairics imports
from genairics.tasks import setupProject, ProjectTask, SampleConfig

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

class PipelineWrapper(WrapperTask):
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
    
    @classmethod
    def inherit_task_parameters(cls):
        pipeline = inherits(setupProject)(cls)
        for t in cls.tasks(None): # passing None as stub for `self`
            if issubclass(t,Task) and t is not setupProject:
                pipeline = inherits(t)(pipeline)
        sample_specific_params = SampleConfig.get_param_names()
        for param in pipeline.get_param_names():
            if param in sample_specific_params:
                continue # sample specific params do not need to be inherited
            setattr(
                cls,param,
                getattr(pipeline,param)
            )
        cls.params_inherited = True

    def requires(self):
        yield self.clone(setupProject)
        for task in self.tasks():
            if issubclass(task,Task) and task is not setupProject:
                yield self.clone(task)

    # Context management
    def sample_context(self):
        self.active_context = True
        return self
    
    def __enter__(self):
        if self.active_context:
            if self.params_inherited:
                return 'Testing context'
            else: # Parameters are not yet inherited,
                # return a stub to expose sample tasks for inheritance
                return [None]

    def __exit__(self, type, value, tb):
        del self.active_context
        if not tb:
            return True
        else: return False
