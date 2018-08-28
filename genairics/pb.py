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
from genairics.tasks import setupSequencedSample as BaseSampleTask


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
    baseTask = setupProject
    
    @classmethod
    def inherit_task_parameters(cls):
        pipeline = inherits(cls.baseTask)(cls)
        from unittest.mock import MagicMock
        for t in cls.tasks(MagicMock()): # passing cls as stub for `self`
            if issubclass(t,Task) and t is not cls.baseTask:
                pipeline = inherits(t)(pipeline)
        sample_specific_params = SampleConfig.get_param_names()
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
            # Sample context specific task
            if hasattr(self,'active_context'):
                # TODO inheritance is not yet dealt with for sample specific task
                # within context. For now make a SamplePipelineWrapper to use in the
                # context as a single task
                task = requires(self.previousTask)(task)
                for sampleDir, outfileDir in self.sample_generator():
                    yield task(
                        sampleDir = sampleDir,
                        outfileDir = outfileDir,
                         **{k:self.param_kwargs[k] for k in task.get_param_names()}
                    )
            # General project tasks    
            elif issubclass(task,Task) and task is not self.baseTask:
                task = requires(self.previousTask)(task)
                yield self.clone(task)
                self.previousTask = task

    # Sample context management
    def sample_context(self):
        self.active_context = True
        return self
    
    def __enter__(self):
        if self.active_context:
            if self.params_inherited:
                # Prepare sample generator
                import glob
                sampleDirs = glob.glob(os.path.join(self.datadir, self.project, '*'))
                if sampleDirs:
                    self.sample_generator = lambda: ( # Creates a function to provide the generator on each call
                        ( # Generates tuples of the sample data and results directory
                            d,
                            os.path.join(self.datadir, self.project, 'sampleResults', os.path.basename(d))
                        )
                        for d in sampleDirs
                    )
                else:
                    raise Exception('Dynamic dependency not yet met, cannot provide sample directories.')
            else: # Parameters are not yet inherited,
                # return a stub to expose sample tasks for inheritance
                return [None]

    def __exit__(self, type, value, tb):
        del self.active_context, self.sample_generator
        if not tb:
            return True
        else: return False

class SamplePipelineWrapper(PipelineWrapper):
    baseTask = BaseSampleTask
