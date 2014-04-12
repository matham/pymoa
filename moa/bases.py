'''
* when dispatching events, returning True stops it.
'''


import os
import kivy
kivy.require('1.8.1')
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.widget import Widget
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty)
import moa.factory_registers


class MoaException(Exception):
    pass


class MoaBase(Widget):

    _widgets = {}
    _name = ''

    @staticmethod
    def get_named_instance(name):
        return MoaBase._widgets[name]

    def __init__(self, **kwargs):
        self.size_hint = None, None
        self.size = 0, 0
        super(MoaBase, self).__init__(**kwargs)

        self.bind(name=self._verfiy_name)

    def _verfiy_name(self, instance, value):
        widgets = MoaBase._widgets
        old_name = self._name
        if value == old_name:
            return

        if value and value in widgets:
            raise ValueError('Name {} already exists'.format(value))
        if old_name:
            del widgets[old_name]
        if value:
            widgets[value] = self
        self._name = value

    name = StringProperty('')
    ''' Unique name across all Moa objects
    '''
    log_level = OptionProperty('debug', options=['debug', 'info', 'critical',
                                                 'quiet'])
    ''' How much to log, in addition to whatever the class saves.
    '''
    source = StringProperty('')
    ''' E.g. a filename to load that interpreted by the subclass.
    '''


class MoaApp(App):

    def __init__(self, **kwargs):
        super(MoaApp, self).__init__(**kwargs)
        Builder.load_file(os.path.join(os.path.dirname(__file__),
                                       'data', 'moa_style.kv'))

    def start_root_stage(self, root):
        '''When called, it dispatches start to the root widget.
        '''
        root.dispatch('on_start')


class MoaSource(MoaBase):

    virtual = BooleanProperty(False)
    '''If true, the inputs are fake.
    '''


class MoaSink(MoaBase):

    virtual = BooleanProperty(False)
    '''If true, the outputs are fake.
    '''
