#!/usr/bin/env python
"""
genairics.jobs contains all the logics for submitting genairics pipelines as jobs
to for example a qsub system
"""
from plumbum import local, SshMachine
from luigi.contrib.ssh import RemoteTarget
from luigi.util import inherits
import luigi

# Tasks
from genairics import setupProject

class QueuJob(luigi.Task):
    """
    Submits a pipeline as a qsub job.
    """
    job = luigi.TaskParameter(description = 'the pipeline that will be submitted as a qsub job')
    resources = luigi.DictParameter(
        default = {'walltime':'20:00:00','nodes':1, 'ppn':4},
        description = 'the resources that will be asked by the qsub job'
    )
    remote = luigi.Parameter('', description='provide ssh config remote name, if job is to be submitted remotely')

    def output(self):
        return (
            luigi.LocalTarget('{}/../results/{}/plumbing/completed_{}'.format(job.datadir,job.project,self.task_family))
            if not self.remote else
            RemoteTarget('{}/../results/{}/plumbing/completed_{}'.format(job.datadir,job.project,self.task_family))
        )

    def run(self):
        machine = SshMachine(self.remote) if self.remote else local
        jobvariables = ['GENAIRICS_ENV_ARGS={}'.format(job.task_family),'LUIGI_SET_FRIENDLY=']
        for n in job.get_param_names():
            job.append('{}="{}"'.format(n,job.__getattribute__(n)))
        qsub = machine['qsub'][
            '-l','walltime={}'.format(self.resources['walltime']),
            '-l','nodes={}:ppn={}'.format(self.resources['nodes'],self.resources['ppn']),
            '-v',','.join(jobvariables)
        ]
        qsubID = qsub('-v','',machine['genairics'])
        machine['touch'](self.output().path)
        if self.remote: machine.close()
