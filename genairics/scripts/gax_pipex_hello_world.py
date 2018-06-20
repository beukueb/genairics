#!/usr/bin/env python3
"""GAX_PIPEX example hello world script

Modify freely for your own needs.
Only requires genairics package to be installed 
within the environment running the script.

The task needs to inherits/requires from genairics
setupProject task as a bare minimum to setup logging.

On the cluster server, your .bashrc should specify
GAX_PIPEX and a PYTHONPATH that includes this scripts location.
"""
import luigi
#from luigi.util import requires
from genairics import setupProject, ProjectTask

#@requires(setupProject)
class HelloWorldTask(ProjectTask):
    name = luigi.Parameter(description="person's name")
    age = luigi.IntParameter(default=0, description="person's age")
    loglevel = luigi.IntParameter(default=20, description="log level. 20 -> info; 30 -> warn (includes stdout)")
    
    def run(self):
        print = self.getPrint()
        print(
            'Hello', self.name,'!',
            *(('Are you really already',self.age,'?') if self.age else ()),
            level = self.loglevel
        )
        #self.touchCheckpoint()

    def output(self):
        return self.CheckpointTarget()

# Set this to the name of the class that will run as the pipeline
gax_pipex_name = 'HelloWorldTask'

if __name__ == '__main__':
    from plumbum import local
    import os, sys

    moduleName = os.path.basename(__file__)[:-3]
    with local.env(
            GAX_PIPEX = "{}.{}".format(moduleName, gax_pipex_name), #when submitting to queue will not yet work
            PYTHONPATH = "{}:{}".format(os.path.dirname(__file__),os.getenv('PYTHONPATH')) #as these 2 vars are not passed
    ):
        rc,stdout,stderr = local['genairics'][sys.argv[1:]].run()
        if stdout: print(stdout,end='')
        if stderr: print(stderr,end='') #logging output to stderr and logfile

    # Example making genairics task to pipeline
    # with local.env(GAX_PIPEX='genairics.datasources.BaseSpaceSource'):
    #    print(local['genairics']('BaseSpaceSource','-h'))
