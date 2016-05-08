'''This module provides an App class used to run a Moa experiment.
'''

import os
from os import path
import tempfile
import json

import kivy
from kivy.properties import StringProperty, ObjectProperty
from kivy.app import App
from kivy.lang import Builder
from kivy import resources

import moa.factory_registers
from moa.compat import decode_dict, PY2
from moa.logger import Logger
from moa.base import MoaBase

__all__ = ('MoaApp', )


class MoaApp(MoaBase, App):
    '''App class to run Moa experiments. See module for details.
    '''

    root = ObjectProperty(None, allownone=True, rebind=True)

    root_stage = ObjectProperty(None, allownone=True, rebind=True)
    ''' The root :class:`~moa.stage.MoaStage`, if provided.
    '''

    data_directory = StringProperty('../data')
    ''' The directory where required application data files are saved. This
    is the input directory for the app.
    '''

    log_directory = StringProperty('~/')
    ''' The directory where logs and such are saved. This is the output
    directory for the app.
    '''

    recovery_directory = StringProperty(None, allownone=True)
    '''The recovery directory to use with :meth:`dump_attributes` if
    not None. This is where recovery files are saved.
    '''

    def __init__(self, **kw):
        super(MoaApp, self).__init__(**kw)
        resources.resource_add_path(path.expanduser(self.data_directory))
        Builder.load_file(path.join(path.dirname(__file__),
                                       'data', 'moa_style.kv'))

    def dump_attributes(self, stage=None, save_unnamed=False, prefix='',
                        dir=None):
        '''
        Dumps the dict returned by :meth:`~moa.stage.MoaStage.dump_attributes`
        for all the stages starting with and descending from `stage` into a
        uniquely named json file. The output file extension is `mrec`.

        :Parameters:

            `stage`: :class:`~moa.stage.MoaStage`
                The root stage from where to start to recursively dump the
                attributes. If None, :attr:`root_stage` is used.
            `save_unnamed`: bool
                Whether to also save unnamed stages.
            `prefix`: str
                The prefix to use for the output filename.
            `dir`: str
                The directory in which to save the output file. If None,
                :attr:`recovery_directory` is used.

        :Returns:
            The filename of created output file.

        .. note::
            Unnamed stages will be included, but given a empty dict.

        For example::

            >>> app = MoaApp()
            >>> stage = MoaStage(name='stage1')
            >>> stage.add_stage(MoaStage(name='child1'))
            >>> app.dump_attributes(stage, prefix='example_', dir='/')
            '/example_0wig2f.mrec'

        Its contents are::

            [
              {
                "count": 0,
                "disabled": false,
                "finished": false,
                "name": "stage1",
                "paused": false
              },
              [
                [
                  {
                    "count": 0,
                    "disabled": false,
                    "finished": false,
                    "name": "child1",
                    "paused": false
                  }
                ]
              ]
            ]
        '''
        if stage is None:
            stage = self.root_stage
        if stage is None:
            raise ValueError('A root stage was not provided')

        if dir is None:
            dir = self.recovery_directory
        if dir is None or not path.isdir(dir):
            raise ValueError(
                'A valid recovery directory path was not provided')

        def walk_stages(stage):
            '''Returns a list, where at each level, starting from the root,
            there's a dict describing the states of the stage followed by a
            list of the states of the children, for each child. E.g::

                [root,
                    [child1,
                        [child1.1,
                            [child1.1.1], [child1.1.2]]],
                    [child2,
                        [child2.1,
                            [child2.1.1]],
                        [child2.2]],
                    ...]
            '''
            state = [stage.dump_attributes()]
            children = []
            for child in stage.stages:
                if child.name or save_unnamed:
                    children.append(walk_stages(child))
                else:
                    children.append([{}])
            if children:
                state.append(children)
            return state

        dir = path.abspath(path.expanduser(dir))
        fh, fn = tempfile.mkstemp(suffix='.mrec', prefix=prefix, dir=dir)
        os.close(fh)
        with open(fn, 'w') as fh:
            json.dump(walk_stages(stage), fh, indent=2, sort_keys=True,
                      encoding='utf-8')
        return fn

    def load_attributes(self, filename, stage=None, recover_unnamed=False,
                           verify_name=True):
        ''' Recovers the attributes from a json file created by
        :meth:`dump_attributes` and restores them to `stage` and it's children
        stages recursively.

        :Parameters:

            `filename`: str
                The full filename of the json file.
            `stage`: :class:`~moa.stage.MoaStage`
                The root stage to which the attributes will be restored.
                If None, :attr:`root_stage` is used.
            `recover_unnamed`: bool
                Whether to recover stages that have no name.
            `verify_name`: bool
                Whether to verify that the names of all the stages starting
                with `stage`, match the names from the recovery file.
                Matching and recovery is performed using position in the file
                and in :attr:`~moa.stage.MoaStage.stages`.

                .. note::
                    When False, the names are simply ignored and not restored.

        .. note::
            The stages are recovered and applied depth first, i.e starting with
            the deepest children stages, and then moving upwards.
        '''
        if stage is None:
            stage = self.root_stage
        if stage is None:
            raise ValueError('Root stage was not provided')

        with open(filename, 'r') as fh:
            decode = decode_dict if PY2 else None
            state = json.load(fh, object_hook=decode)

        def apply_state(stage, state):
            '''Function called recursively to apply the list of dicts to the
            stage and substages.
            '''
            if not recover_unnamed and not stage.name:
                return
            if not len(state):
                Logger.debug(
                    "Cannot find recovery info for stage {}".format(stage))
                return
            root_state = state.pop(0)
            if verify_name and root_state['name'] != stage.name:
                raise Exception("Recovered, {}, and stage name, {}, are not "
                    "the same".format(root_state['name'], stage.name))

            if 'name' in root_state:
                del root_state['name']

            if not len(state) or not len(state[0]):
                if len(stage.stages):
                    Logger.debug(
                        "Cannot find recovery info for children of {}".
                        format(stage))
            elif len(stage.stages) != len(state[0]):
                raise Exception("The number of children stages ({}) for {},  "
                "doesn't match the number of stages recovered ({})"
                .format(len(stage.stages), stage, len(state[0])))
            else:
                for i in range(len(state[0])):
                    apply_state(stage.stages[i], state[0][i])
            stage.load_attributes(root_state)

        apply_state(stage, state)
