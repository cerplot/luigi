
import os
import tempfile

import trun.server
import server_test

tempdir = tempfile.mkdtemp()


class DummyStep(trun.Step):
    id = trun.IntParameter()

    def run(self):
        f = self.output().open('w')
        f.close()

    def output(self):
        return trun.LocalTarget(os.path.join(tempdir, str(self.id)))


class RemoteSchedulerTest(server_test.ServerTestBase):

    def _test_run(self, workers):
        steps = [DummyStep(id) for id in range(20)]
        trun.build(steps, workers=workers, scheduler_port=self.get_http_port())

        for t in steps:
            self.assertEqual(t.complete(), True)
            self.assertTrue(os.path.exists(t.output().path))

    def test_single_worker(self):
        self._test_run(workers=1)

    def test_multiple_workers(self):
        self._test_run(workers=10)
