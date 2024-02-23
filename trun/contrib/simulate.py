# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
A module containing classes used to simulate certain behaviors
"""

from multiprocessing import Value
import tempfile
import hashlib
import logging
import os

import trun

logger = logging.getLogger('trun-interface')


class RunAnywayTarget(trun.Target):
    """
    A target used to make a step run every time it is called.

    Usage:

    Pass `self` as the first argument in your step's `output`:

    .. code-block: python

        def output(self):
            return RunAnywayTarget(self)

    And then mark it as `done` in your step's `run`:

    .. code-block: python

        def run(self):
            # Your step execution
            # ...
            self.output().done() # will then be considered as "existing"
    """

    # Specify the location of the temporary folder storing the state files. Subclass to change this value
    temp_dir = os.path.join(tempfile.gettempdir(), 'trun-simulate')
    temp_time = 24 * 3600  # seconds

    # Unique value (PID of the first encountered target) to separate temporary files between executions and
    # avoid deletion collision
    unique = Value('i', 0)

    def __init__(self, step_obj):
        self.step_id = step_obj.step_id

        if self.unique.value == 0:
            with self.unique.get_lock():
                if self.unique.value == 0:
                    self.unique.value = os.getpid()  # The PID will be unique for every execution of the pipeline

        # Deleting old files > temp_time
        if os.path.isdir(self.temp_dir):
            import shutil
            import time
            limit = time.time() - self.temp_time
            for fn in os.listdir(self.temp_dir):
                path = os.path.join(self.temp_dir, fn)
                if os.path.isdir(path) and os.stat(path).st_mtime < limit:
                    shutil.rmtree(path)
                    logger.debug('Deleted temporary directory %s', path)

    def __str__(self):
        return self.step_id

    def get_path(self):
        """
        Returns a temporary file path based on a MD5 hash generated with the step's name and its arguments
        """
        md5_hash = hashlib.new('md5', self.step_id.encode(), usedforsecurity=False).hexdigest()
        logger.debug('Hash %s corresponds to step %s', md5_hash, self.step_id)

        return os.path.join(self.temp_dir, str(self.unique.value), md5_hash)

    def exists(self):
        """
        Checks if the file exists
        """
        return os.path.isfile(self.get_path())

    def done(self):
        """
        Creates temporary file to mark the step as `done`
        """
        logger.info('Marking %s as done', self)

        fn = self.get_path()
        try:
            os.makedirs(os.path.dirname(fn))
        except OSError:
            pass
        open(fn, 'w').close()
