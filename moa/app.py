

import os
import kivy
kivy.require('1.8.1')
from kivy.app import App
from kivy.lang import Builder
import moa.factory_registers


class MoaApp(App):

    def __init__(self, **kwargs):
        super(MoaApp, self).__init__(**kwargs)
        Builder.load_file(os.path.join(os.path.dirname(__file__),
                                       'data', 'moa_style.kv'))
