'''
TODO: when completion_type is any, save the one that initiated the stop
'''

__all__ = ('MoaStage', )

import time

from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty)
from kivy.uix.widget import Widget
from kivy.lang import Factory

from moa.base import MoaBase
from moa.clock import Clock


def _get_bases(cls):
    for base in cls.__bases__:
        if base.__name__ == 'object':
            break
        yield base
        for cbase in _get_bases(base):
            yield cbase


class StageMetaclass(type):
    '''Metaclass to automatically register new stage classes with the
    :kivy:class:`~kivy.factory.Factory`.

    .. warning::
        This metaclass is used by MoaStage. Do not use it directly!
    '''
    def __init__(mcs, name, bases, attrs):
        super(StageMetaclass, mcs).__init__(name, bases, attrs)
        Factory.register(name, cls=mcs)

StageBase = StageMetaclass('StageBase', (MoaBase, ), {})


class MoaStage(StageBase):

    __metaclass__ = StageMetaclass

    __dump_attrs__ = ('disabled', 'finished', 'paused', 'count')

    _cls_attrs = None

    _pause_list = []
    ''' The list of children we ourselves have paused and we need to unpause
    after we ourself become unpaused. Children that were already paused when
    we paused do not have to be unpaused.
    '''
    _loop_finishing = BooleanProperty(False)
    # whether this loop iteratioon is force stopped. loop_done is true only
    # the stage loop itelf completed, but maybe not the substages.
    # when this is true, the substages are force stopped.

    def __init__(self, **kwargs):
        super(MoaStage, self).__init__(**kwargs)
        cls_inst = self.__class__
        if cls_inst._cls_attrs is None:
            cls_inst._cls_attrs = attrs = []
            for cls in [cls_inst] + list(_get_bases(cls_inst)):
                if not hasattr(cls, '__dump_attrs__'):
                    continue

                for attr in cls.__dump_attrs__:
                    if attr in attrs:
                        continue
                    if not hasattr(self, attr):
                        raise Exception('Missing attribute <{}> in <{}>'.
                                        format(attr, cls_inst.__name__))
                    attrs.append(attr)
        self._pause_list = []

    def dump_attributes(self, state=None):
        attrs = self.__class__._cls_attrs
        exclude = self.exclude_attrs
        if state is None:
            state = {}
        for attr in attrs:
            if attr not in exclude:
                state[attr] = getattr(self, attr)
        return state

    def load_attributes(self, state):
        exclude = self.exclude_attrs
        self.clear()
        for attr, value in state.items():
            if attr not in exclude:
                setattr(self, attr, value)

    def add_widget(self, widget, index=None, **kwargs):
        if widget is self:
            raise Exception('You cannot add yourself in a MoaStage')

        if isinstance(widget, MoaStage):
            self.add_stage(widget, index, **kwargs)
        elif not isinstance(widget, Widget):
            raise Exception('add_widget() can be used only with Widget '
                            'or MoaStage based classes.')
        else:
            if self.renderer is not None:
                raise ValueError(
                    'Stage already has renderer {}, cannot add {}'.
                    format(self.renderer, widget))
            self.renderer = widget.__self__

    def add_stage(self, stage, index=None, **kwargs):
        ''' Different than widget because of None.
        '''
        stages = self.stages
        if not isinstance(stage, MoaStage):
            raise Exception('{} is not an instance of MoaStage and cannot be '
                            'added to stages'.format(stage))
        stage = stage.__self__
        parent = stage.parent
        # check if widget is already a child of another widget
        if parent:
            raise Exception('Cannot add {}, it already has a parent {}'.format(
                            stage, parent))
        stage.parent = self
        # child will be disabled if added to a disabled parent
        if self.disabled:
            stage.disabled = True

        if index is None or index >= len(stages):
            stages.append(stage)
        else:
            stages.insert(stage, index)

    def remove_widget(self, widget, **kwargs):
        if isinstance(widget, MoaStage):
            self.remove_stage(widget, **kwargs)
        elif widget == self.renderer:
            self.renderer = None

    def remove_stage(self, stage, **kwargs):
        try:
            self.stages.remove(stage)
            stage.parent = None
        except ValueError:
            pass

    def pause(self, recurse=True):
        paused = self.paused
        self.paused = True

        if self.disabled or not self.started or self.finished or paused:
            self.log('debug', 'Pausing ignored')
            return False
        self.log('debug', 'Pausing recurse={}', recurse)

        # we paused so we need to pause the clock and save elapsed time
        self.elapsed_time += time.clock() - self.start_time
        Clock.unschedule(self._do_stage_timeout)
        if recurse:
            pause_list = self._pause_list
            for child in self.stages:
                # only pause children not yet paused
                if not child.paused:
                    child.pause(True)
                    pause_list.append(child.proxy_ref)
        return True

    def unpause(self, recurse=True):
        paused = self.paused
        self.paused = False

        if self.disabled or not self.started or self.finished or not paused:
            self.log('debug', 'Un-pausing ignored')
            return False
        self.log('debug', 'Unpausing recurse={}', recurse)

        self.start_time = time.clock()
        if self.max_duration > 0.:
            Clock.schedule_once_priority(self._do_stage_timeout, max(0.,
            self.max_duration - self.elapsed_time))
        if recurse:
            for child in self._pause_list:
                try:
                    if child.paused:
                        child.unpause(True)
                except ReferenceError:
                    pass
        self._pause_list = []
        return True

    def stop(self, stage=True, **kwargs):
        '''Stops async recursively. Use self.finished to check when really
        stopped.

        When this is called with super, this instance loop_done is set to True.
        '''
        if not self.started or self.finished:
            self.log('debug', 'Stopping ignored. Source stage={}', stage)
            return False
        self.log('debug', 'Stopping. Source stage={}', stage)

        # all children were stopped, so we can stop now
        Clock.unschedule(self._do_stage_timeout)
        self.stopped = True
        if stage:
            self.finishing = True
        else:
            self._loop_finishing = True
        self.step_stage(source=self)
        return True

    def on_disabled(self, instance, value, **kwargs):
        ''' Dispatch.
        '''
        if value:
            self.stop()

    def clear(self, recurse=False, loop=False, **kwargs):
        '''Clears started etc. stops running if running.
        '''
        if not loop and self.started and not self.finished:
            self.log('warning', 'Clearing unfinished stage, may lead to state '
                     'corruption')

        self._loop_finishing = False
        self.loop_done = False
        self.timed_out = False

        if not loop:
            self.stopped = False
            self.finished = False
            self.started = False
            self.count = 0
            self.elapsed_time = 0.
            self.start_time = 0.
            self.finishing = False
        if recurse:
            for child in self.stages[:]:
                child.clear(recurse)
        return True

    def get_skip_stage(self):
        ''' If True, when step_stage is called, it must continue the chain,
        even if not actually started. It is important, that this method does
        not modify the state. I.e. calling this method twice in series
        should return the same value.
        '''
        return self.disabled

    def step_stage(self, source=None, **kwargs):
        ''' Only allowed to be called when after on_stop, or if class finished
        loop on its own in which case finishing is True.

        source None is the same as self.

        When source is self (None) and we need to step the loop, it may only
        return false if didn't start b/c not finished or disabled. To prevent
        from starting set it to disabled, and not by just returning here False.
        Otherwise, we may never proceed to the next stage because the stop
        condition is not met, but start returns False.

        TODO: if the stage itself can complete the stage and no child was
        started because disabled, check after trying to start children if the
        state should be completed.

        This ignores if we're paused.

        there is one entrance (here) and two exists (stop, and here). Exit code
        should be in both exists.
        '''

        children = self.stages[:]
        comp_list = self.completion_list
        comp_type = self.completion_type
        order = self.order
        if source is None:
            source = self
        # if we should start this stage
        start = (not self.started or self.finished) and source is self
        log = self.log

        if start:
            if self.get_skip_stage():
                log('debug', 'Step stage start skipped with get_skip_stage()')
                return False
            log('debug', 'Step stage, starting stage')
            self.clear()
            for child in children:
                child.clear()

            self.start_time = time.clock()
            self.started = True
            max_duration = self.max_duration
            if not self.paused and max_duration > 0.:
                Clock.schedule_once_priority(
                    self._do_stage_timeout, max_duration)
        elif not self.started and source is not self:
            log('warning', 'Step stage ignored because not started and source '
                'is not self. source={}', source)
            return False
        elif self.finished:
            log('error', 'Step stage ignored because already finished. '
                'source={}', source)
            return False
        else:
            log('debug', 'Step stage with source={}', source)

        # decide if this loop iteration is done
        if source is self and not start:
            self.loop_done = True
        loop_done = self.loop_done
        # if this loop should be terminated and increment count
        done = self._loop_finishing = (
            self.finishing or self._loop_finishing or (
            comp_type == 'any' and (not comp_list or (loop_done and self in comp_list) or
            any([c.finished and not c.get_skip_stage() for c in comp_list])))
            or (comp_type == 'all' and
            ((comp_list and all([(c.finished or c.get_skip_stage()) and
                                 c != self
            or c == self and loop_done for c in comp_list]))
            or (not comp_list and (not children and loop_done or children and
            all([c.finished or c.get_skip_stage() for c in children]))))))

        i = None
        # if we need to finish loop, stop all the children and ourself
        # (just the loop, not stage)
        if done:
            for child in children:
                if child.stop():
                    return False
            # in case child initiated completion, so we did not finish loop
            if not loop_done:
                self.stop(stage=False)
                return False
        elif not start:
            # loop not done, so decide if need to start next child, or wait
            # for self/substage to complete.

            # if self is responsible and it's not done there's nothing to do
            # or if parallel, all children should be started already
            if source is self or order == 'parallel':
                return False

            # when serial see if there's a next child to start
            for k in range(len(children)):
                child = children[k]
                if not child.get_skip_stage() and not child.finished:
                    # if a child is already running we cannot proceed
                    if child.started:
                        log('warning', 'Could not start next child ({})'
                            '; this code should not have been reached', child)
                        return False
                    else:
                        i = k
                        break

            if i is not None:
                for child in children[i:]:
                    if not child.get_skip_stage():
                        child.step_stage()
                        return False
                    log('debug', 'skipping starting next serial child ({})',
                        child)

            if not loop_done:
                return False

            # if child becomes disabled between when we computed done and now
            # then we may end up here and the loop may need to be ended.
            log('warning', 'Could not start a child; this code should not '
                'have been reached')
            # if not loop_done:
            return False

        # if we reached here then either start or loop and children are done
        if not self.finishing and (start or self.repeat == -1 or
                                   self.count + 1 < self.repeat):
            if not start:
                for child in children:
                    child.clear()
                self.clear(loop=True)
                t = time.clock()
                self.elapsed_time += t - self.start_time
                self.start_time = t
                self.count += 1

            if order == 'serial':
                for child in children:
                    if not child.get_skip_stage():
                        child.step_stage()
                        break
            else:
                for child in children:
                    child.step_stage()
            return True

        if self.max_duration > 0.:
            Clock.unschedule(self._do_stage_timeout)
        self.finished = True
        parent = self.parent
        if parent is not None:
            parent.step_stage(source=self)
        return False

    def _do_stage_timeout(self, *l):
        self.timed_out = True
        self.stop()

    def __repr__(self):
        if self.finished:
            text = 'finished'
        elif self.started:
            text = 'started'
        else:
            text = 'not started'
        return '<{} name="{}": {}/{} parent="{}" {}>'.format(
            self.__class__.__name__, self.name, self.count + 1, self.repeat,
            'None' if self.parent is None else self.parent.name, text)

    stages = ListProperty([])
    ''' read only
    '''

    parent = ObjectProperty(None, allownone=True)
    '''Parent of this widget.

    :attr:`parent` is an :class:`~kivy.properties.ObjectProperty` and
    defaults to None.

    The parent of a widget is set when the widget is added to another widget
    and unset when the widget is removed from its parent.
    '''

    renderer = ObjectProperty(None, allownone=True)
    ''' The class used to display and control this stage in the stage tree.
    When `None`, we walk the parent tree until we find one which is not `None`,
    or an error is raised.
    This cannot be set from kv, because the children are added before this
    rule is applied. So from .py, either added as constructor argument,  or in
    constructor.
    '''

    render_cls = ObjectProperty(None, allownone=True)
    ''' The class used to display and control this stage in the stage tree.
    When `None`, we walk the parent tree until we find one which is not `None`,
    or an error is raised.
    This cannot be set from kv, because the children are added before this
    rule is applied. So from .py, either added as constructor argument,  or in
    constructor.
    '''

    exclude_attrs = ListProperty([])

    repeat = BoundedNumericProperty(1, min=-1)
    ''' 1 is once, -1 is indefinitely.
    '''

    count = BoundedNumericProperty(0, min=0)
    ''' Zero is the first etc. updated after the loop jumps back. read only
    '''

    max_duration = BoundedNumericProperty(0, min=0)
    '''If non zero, the total duration that this stage goes on. Including
    the loops.
    '''

    timed_out = BooleanProperty(False)
    ''' If max_duration timed out.
    '''

    order = OptionProperty('serial', options=['serial', 'parallel'])
    '''Whether sub-stages are run at same time or one after the other.
    '''

    completion_type = OptionProperty('all', options=['all', 'any'])
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    completion_list = ListProperty([])
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    start_time = NumericProperty(0)
    ''' The time the stage started, or when last loop incremented. If paused,
    it's the time when unpaused. Only valid between started and finished.
    '''

    elapsed_time = NumericProperty(0)
    ''' The time elapsed. time.clock(). Only valid after started.
    time.clock() - start_time + elapsed_time is the total time in stage.
    '''

    disabled = BooleanProperty(False)
    ''' If this stage is disabled.
    '''

    started = BooleanProperty(False)
    '''Set to true whenever the stage is started.
    '''

    finished = BooleanProperty(False)
    ''' Set to True whenever the stage ended (forced or normal).
    don't step stage on finished, because it's already done from step_stage
    that set finished.
    Some finishing code may execute after setting finished.
    '''

    stopped = BooleanProperty(False)
    '''Whether the stage was stopped early, or if it naturally completed.
    '''

    paused = BooleanProperty(False)
    ''' If we are paused.
    '''

    loop_done = BooleanProperty(False)
    ''' If the stage loop itself is done, this is True, need it in case
    children not done, so we know that we are ready to finish.
    '''

    finishing = BooleanProperty(False)
    ''' If the stage is trying to finish.
    '''
