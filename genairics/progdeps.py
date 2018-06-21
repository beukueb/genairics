#-*- coding: utf-8 -*-
"""genairics program dependencies

ProgramTasks that can be inherited by pipeline tasks
and will provide access to the program, installing if
needed.
"""
from genairics.tasks import ProgramDependencyPackage

sshfs = ProgramDependencyPackage(
    name = 'sshfs'
)
