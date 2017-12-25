#!/usr/bin/env python

from unittest.mock import Mock, MagicMock, patch, call
from unittest import TestCase
from genairics import runWorkflow, runTaskAndDependencies
from genairics.RNAseq import RNAseq
import os, shutil, tempfile

class test_RNAseq(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.datadir = os.path.join(self.tempdir,'data')
        os.mkdir(self.datadir)
        os.mkdir(os.path.join(self.tempdir,'results'))
        self.genome = 'saccharomyces_cerevisiae'
        self.basespace_testproject = 'NSQ_Run240'
        self.workflow = RNAseq(datadir=self.datadir,
                               project=self.basespace_testproject,
                               genome=self.genome)

    def tearDown(self):
        shutil.rmtree(self.datadir)
        del self.datadir

    def test_parameterSettings(self):
        workflowstr = str(self.workflow)
        self.assertIn(self.datadir, workflowstr)
        self.assertIn(self.genome, workflowstr)
        self.assertIn(self.basespace_testproject, workflowstr)

    def test_runningWorkflow(self):
        #TODO need small dataset to test
        #best to mock basespace api, and test basespace api in separate test
        runWorkflow(self.workflow)
