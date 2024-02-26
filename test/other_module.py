
import trun


class OtherModuleStep(trun.Step):
    p = trun.Parameter()

    def output(self):
        return trun.LocalTarget(self.p)

    def run(self):
        with self.output().open('w') as f:
            f.write('Done!')
