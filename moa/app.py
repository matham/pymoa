
__all__ = ('MoaApp', )

import os
from os import path
import tempfile
import json
import kivy
kivy.require('1.8.1')
from kivy.properties import StringProperty, ObjectProperty
from kivy.app import App
from kivy.lang import Builder

import moa.factory_registers
from moa.compat import decode_dict, PY2


class MoaApp(App):

    root_stage = ObjectProperty(None, allownone=True)
    ''' The root stage.
    '''

    data_directory = StringProperty('~/')
    ''' Where logs and such are saved.
    When crashing, recovery is saved here
    '''

    def save_state(self, stage=None, save_unnamed=False, prefix='',
                   dir=''):
        '''
        Walks the stages starting with stage and dumps the states to a json
        file.
        '''
        if stage is None:
            stage = self.root_stage
        if stage is None:
            raise ValueError('Root stage was not provided')

        def walk_stages(stage):
            state = [stage.get_state()]
            children = []
            for child in stage.stages:
                if child.name or save_unnamed:
                    children.append(walk_stages(child))
                else:
                    children.append([{}])
            if children:
                state.append(children)
            return state

        dir = dir if path.isdir(dir) else \
            path.abspath(path.expanduser(self.data_directory))
        fh, fn = tempfile.mkstemp(suffix='.mrec', prefix=prefix, dir=dir)
        os.close(fh)
        with open(fn, 'w') as fh:
            json.dump(walk_stages(stage), fh, indent=2, sort_keys=True,
                      encoding='utf-8')
        return fn

    def recover_state(self, filename, stage=None, recover_unnamed=False,
                      verify_name=True):
        ''' Recovers the state saved with :meth:`save_state`.

        .. note::
            It does not recover name.
        '''
        if stage is None:
            stage = self.root_stage
        if stage is None:
            raise ValueError('Root stage was not provided')

        with open(filename, 'r') as fh:
            decode = decode_dict if PY2 else None
            state = json.load(fh, object_hook=decode)

        def apply_state(stage, state):
            if not recover_unnamed and not stage.name:
                return
            root_state = state.pop(0)
            if verify_name and root_state['name'] != stage.name:
                raise Exception("Recovered, {}, and stage name, {}, are not "
                    "the same".format(root_state['name'], stage.name))

            if 'name' in root_state:
                del root_state['name']
            stage.recover_state(root_state)

            if not len(state) or not len(state[0]):
                if not len(stage.stages):
                    return
                raise Exception("Cannot find rules in the recovery file to "
                "to apply to the children of {}".format(stage))
            elif len(stage.stages) != len(state[0]):
                raise Exception("The number of children stages for {}, {},  "
                "doesn't match the number of stages read, {}"
                .format(stage, len(stage.stages), len(state[0])))

            for i in range(len(state[0])):
                apply_state(stage.stages[i], state[0][i])

        apply_state(stage, state)

    def run(self):
        Builder.load_file(path.join(path.dirname(__file__),
                                       'data', 'moa_style.kv'))
        return super(MoaApp, self).run()
