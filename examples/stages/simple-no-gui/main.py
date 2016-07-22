
from os.path import join, dirname
from os import environ
environ['MOA_CLOCK'] = '1'

from moa.stage import MoaStage
from kivy.lang import Builder
from moa.app import MoaApp
from kivy.clock import Clock
from kivy.app import runTouchApp

Builder.load_file(join(dirname(__file__), 'experiment.kv'))


class RootStage(MoaStage):
    pass


class MyApp(MoaApp):

    def on_start(self, *largs):
        stage = self.root_stage = RootStage()
        Clock.schedule_once(lambda *largs: stage.step_stage(), 5.)

MyApp().run()
