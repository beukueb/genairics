# -*- coding: utf-8 -*-
from unittest.mock import Mock, MagicMock, patch, call
from unittest import TestCase
import os, genairics as gax
from plumbum import local

class test_dependency_script(TestCase):
    def setUp(self):
        self.scriptdir = os.path.join(os.path.dirname(gax.__file__),'scripts')

    def tearDown(self):
        del self.scriptdir

    def test_script_syntax(self):
        script = os.path.join(self.scriptdir,'genairics_dependencies.sh')
        self.assertFalse(local['bash']('-n',script))
