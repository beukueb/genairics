#!/usr/bin/env python3
"""GAX_PIPEX example hello world script

Modify freely for your own needs.
Only requires genairics package to be installed 
within the environment running the script.

The task needs to inherits/requires from genairics
setupProject task as a bare minimum to setup logging.
"""
import luigi
#from luigi.util import requires
from genairics import setupProject, ProjectTask

#@requires(setupProject)
class HelloWorldTask(ProjectTask):
    name = luigi.Parameter(description="person's name")
    age = luigi.IntParameter(default=0, description="person's age")
    
    def run(self):
        from io import StringIO

        logger = self.getLogger()
        stdout = StringIO()
        print(
            'Hello', self.name,'!',
            *(('Are you really already',self.age,'?') if self.age else ()),
            file = stdout
        )
        logger.info(stdout.getvalue())
        print(stdout.getvalue(),end='')

# Set this to the name of the class that will run as the pipeline
gax_pipex_name = 'HelloWorldTask'

if __name__ == '__main__':
    from plumbum import local
    import os, sys

    moduleName = os.path.basename(__file__)[:-3]
    with local.env(
            GAX_PIPEX = "{}.{}".format(moduleName, gax_pipex_name),
            PYTHONPATH = ".:{}".format(os.getenv('PYTHONPATH'))
    ):
        stdout = local['genairics'](*sys.argv[1:])
        if stdout: print(stdout,end='')

    # Example making genairics task to pipeline
    # with local.env(GAX_PIPEX='genairics.datasources.BaseSpaceSource'):
    #    print(local['genairics']('BaseSpaceSource','-h'))
