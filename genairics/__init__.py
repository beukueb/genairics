#!/usr/bin/env python
"""
GENeric AIRtight omICS package
"""

import luigi, os, logging

## Helper function
class LuigiStringTarget(str):
    """
    Using this class to wrap a string, allows
    passing it between tasks through the output-input route
    """
    def exists(self):
        return bool(self)

# Set up logging
logger = logging.getLogger(os.path.basename(__file__))
logger.setLevel(logging.INFO)
logconsole = logging.StreamHandler()
logconsole.setLevel(logging.ERROR)
logger.addHandler(logconsole)

typeMapping = {
    luigi.parameter.Parameter: str,
    luigi.parameter.BoolParameter: bool,
    luigi.parameter.FloatParameter: float
}
