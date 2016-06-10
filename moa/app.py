'''App
========

This module provides an App class used to run a Moa experiment.
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
    '''App class runs Moa experiments as well as the Kivy GUI.
    '''

    root = ObjectProperty(None, allownone=True, rebind=True)
    '''The root GUI widget used by Kivy for the UI. Read only.
    '''

    root_stage = ObjectProperty(None, allownone=True, rebind=True)
    ''' The root :class:`~moa.stage.MoaStage` that contains the experiment.
    Must be manually set.
    '''

    data_directory = StringProperty('')
    ''' The directory where application data files are stored. This path
    is automatically added to the kivy search path.

    It must be set by the application if used.
    '''

    recovery_directory = StringProperty('')
    '''The recovery directory to use with :meth:`dump_recovery` if
    not empty. This is where recovery files are saved by default.
    '''

    recovery_filename = StringProperty('')
    '''The filename of the last recovery file written. It is automatically
    set by :meth:`dump_recovery`.
    '''

    def __init__(self, **kw):
        super(MoaApp, self).__init__(**kw)
        Builder.load_file(path.join(path.dirname(__file__),
                                    'data', 'moa_style.kv'))

        def add_data_directory(*largs):
            if not self.data_directory:
                return
            resources.resource_add_path(path.expanduser(self.data_directory))
        self.fbind('data_directory', add_data_directory)
        add_data_directory()

    def dump_recovery(self, stage=None, save_unnamed_stages=True,
                      include_knsname=True, prefix='', directory=''):
        '''Dumps the name and value for all the properties listed in
        :attr:`~moa.stage.MoaStage.restore_properties` for all the stages
        starting with and descending from ``stage`` into a
        uniquely named json file.

        The output file extension is `mrec`.

        :Parameters:

            `stage`: :class:`~moa.stage.MoaStage`
                The root stage from where to start to recursively dump the
                properties. If None, :attr:`root_stage` is used.
            `save_unnamed_stages`: bool
                Whether to also save stages with no knsname. Defaults to True.
            `include_knsname`: bool
                Whether the knsname should be dumped along with the properties
                even if not provided in the
                :attr:`~moa.stage.MoaStage.restore_properties` list. Defaults
                to True.
            `prefix`: str
                The prefix to use for the output filename.
            `directory`: str
                The directory in which to save the output file. If empty,
                :attr:`recovery_directory` is used.

        :Returns:
            The filename of the created recovery file.

        .. note::
            Unnamed stages (with empty knsname) will be included, but will be
            given a empty dict.

        For example::

            >>> app = MoaApp()
            >>> stage = MoaStage(knsname='stage1',
            ...                  restore_properties=['started', 'finished'])
            >>> stage.add_stage(MoaStage(knsname='child1',
            ...                 restore_properties=['count']))
            >>> print(app.dump_recovery(stage, prefix='example_',
            ...                         directory='/'))
            'E:\\example_sh8aui.mrec'

        Its contents is::

            [
              {
                "finished": false,
                "knsname": "stage1",
                "started": false
              },
              [
                {
                  "count": 0,
                  "knsname": "child1"
                }
              ]
            ]
        '''
        if not stage:
            stage = self.root_stage
        if not stage:
            raise ValueError('A root stage was not provided')

        if not directory:
            directory = self.recovery_directory
        if not directory or not path.isdir(directory):
            raise ValueError(
                'A valid recovery directory path was not provided')

        def walk_stages(stage):
            '''Returns a list, where at each level, starting from the root,
            there's a dict describing the recoverable states of the stage
            followed by a list of the recoverable states of the children, for
            each child. E.g::

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
            d = {}
            if stage.knsname or save_unnamed_stages:
                restored = stage.restored_properties
                d = {k: restored.get(k, getattr(stage, k))
                     for k in stage.restore_properties}
                if include_knsname:
                    d['knsname'] = stage.knsname
            state = [d]

            children = []
            for child in stage.stages:
                if child.knsname or save_unnamed_stages:
                    children.append(walk_stages(child))
                else:
                    children.append([{}])
            if children:
                state.extend(children)
            return state

        directory = path.abspath(path.expanduser(directory))
        fh, fn = tempfile.mkstemp(suffix='.mrec', prefix=prefix,
                                  dir=directory)
        os.close(fh)

        d = {'encoding': 'utf-8'} if PY2 else {}
        with open(fn, 'w') as fh:
            json.dump(walk_stages(stage), fh, indent=2, sort_keys=True,
                      separators=(',', ': '), **d)
        self.recovery_filename = fn
        return fn

    def load_recovery(
            self, filename='', stage=None, recover_unnamed_stages=True,
            verify=True):
        '''Recovers the properties from a json file created by
        :meth:`dump_recovery` and restores them to ``stage`` and it's children
        stages recursively.

        For each stage, the recovered dict is stored to
        :attr:`~moa.stage.MoaStage.restored_properties`. `knsname` if present
        is always removed before recovering.

        :Parameters:

            `filename`: str
                The full filename of the json file. If empty it uses
                :attr:`recovery_filename`. Defaults to empty string.
            `stage`: :class:`~moa.stage.MoaStage`
                The root stage to which the attributes will be restored.
                If None, :attr:`root_stage` is used. Defaults to None.
            `recover_unnamed_stages`: bool
                Whether to recover stages that have no knsname. Defaults to
                True.
            `verify`: bool
                Whether to verify that the recovered stage structure match the
                structure of the ``stage`` passed in. If True, the knsnames of
                all the stages must match and the number of stages must match.
                Matching and recovery is performed using position in the file
                and in :attr:`~moa.stage.MoaStage.stages`.

        For example, recovering using the example file generated in
        :meth:`dump_recovery` ::

            >>> from moa.stage import MoaStage
            >>> from moa.app import MoaApp
            >>> app = MoaApp()
            >>> stage = MoaStage(knsname='stage1')
            >>> child1 = MoaStage(knsname='child1')
            >>> stage.add_stage(child1)
            >>> app.load_recovery('E:\\example_sh8aui.mrec', stage=stage)
            >>> print(stage.restored_properties, child1.restored_properties)
            ({}, {})
            >>> print(stage.restored_properties, child1.restored_properties)
            ({'started': False, 'finished': False}, {'count': 0})
        '''
        if stage is None:
            stage = self.root_stage
        if stage is None:
            raise ValueError('Root stage was not provided')

        if not filename:
            filename = self.recovery_filename
        if not filename or not path.isfile(filename):
            raise ValueError(
                'A valid recovery filename was not provided')

        with open(filename) as fh:
            decode = decode_dict if PY2 else None
            state = json.load(fh, object_hook=decode)

        def apply_state(stage, state):
            '''Function called recursively to apply the recovery properties
            list of dicts to the stage and substages.
            '''
            if not recover_unnamed_stages and not stage.knsname:
                return
            if not len(state):
                Logger.debug(
                    "Cannot find recovery info for stage {}".format(stage))
                return

            root_state = state.pop(0)
            if not isinstance(root_state, dict):
                raise Exception('Cannot recover from "{}"'.format(root_state))
            if (verify and 'knsname' in root_state and
                    root_state['knsname'] != stage.knsname):
                raise Exception(
                    'Recovered knsname "{}" and stage knsname "{}", are not '
                    "the same".format(root_state['knsname'], stage.knsname))

            if 'knsname' in root_state:
                del root_state['knsname']

            if not len(state):
                if len(stage.stages):
                    Logger.debug(
                        "Cannot find recovery info for children of {}".
                        format(stage))
            elif len(stage.stages) != len(state):
                raise Exception(
                    "The number of children stages ({}) for {} "
                    "doesn't match the number of stages recovered ({})"
                    .format(len(stage.stages), stage, len(state)))
            else:
                for child_stage, child_state in zip(stage.stages, state):
                    apply_state(child_stage, child_state)
            stage.restored_properties = root_state

        apply_state(stage, state)
