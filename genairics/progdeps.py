#-*- coding: utf-8 -*-
"""genairics program dependencies

ProgramTasks that can be inherited by pipeline tasks
and will provide access to the program, installing if
needed.
"""
from genairics.tasks import ProgramDependencyPackage, ProgramDependencySource

sshfs = ProgramDependencyPackage(
    name = 'sshfs'
)

#TODO depends on cmake
spades = ProgramDependencySource(
    source = 'http://cab.spbu.ru/files/release3.12.0/SPAdes-3.12.0.tar.gz',
    buildcmd = './spades_compile.sh'
)
