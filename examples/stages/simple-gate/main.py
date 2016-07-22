
from os.path import join, dirname
from os import environ
environ['MOA_CLOCK'] = '1'

from moa.stage import MoaStage
from kivy.lang import Builder
from moa.app import MoaApp
from kivy.clock import Clock
from kivy.app import runTouchApp
from kivy.uix.boxlayout import BoxLayout

Builder.load_file(join(dirname(__file__), 'experiment.kv'))
Builder.load_file(join(dirname(__file__), 'graphics.kv'))


class RootStage(MoaStage):
    pass


class RootWidget(BoxLayout):
    pass


class MyApp(MoaApp):

    def build(self):
        widget = RootWidget()
        return widget

    def start_experiment(self):
        stage = self.root_stage = RootStage()
        stage.step_stage()

MyApp().run()
