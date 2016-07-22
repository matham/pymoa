'''Stages
==========

A stage is fundamental to an experiment. A stage typically describes an epoch
during an experiment when something happens or when we wait for something to
happen. An experiment is composed of many stages.

A stage can contain other stages.
'''

import time
from functools import partial

from kivy.properties import (
    BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty, AliasProperty, DictProperty)
from kivy.uix.widget import Widget
from kivy.factory import Factory

from moa.base import MoaBase
from kivy.clock import Clock
import moa.stage

__all__ = ('MoaStage', )


class StageMetaclass(type):
    '''Metaclass to automatically register new stage classes with the
    :class:`~kivy.factory.Factory`.

    .. warning::
        This metaclass is used by MoaStage. Do not use it directly!
    '''
    def __init__(mcs, name, bases, attrs):
        super(StageMetaclass, mcs).__init__(name, bases, attrs)
        Factory.register(name, cls=mcs)

StageBase = StageMetaclass('StageBase', (MoaBase, ), {})


def _ask_step_stage(obj, dt, **kwargs):
    obj.step_stage(**kwargs)


class MoaStage(StageBase):
    '''
    '''

    __events__ = ('on_stage_start', 'on_trial_start', 'on_trial_end',
                  'on_stage_end')

    __metaclass__ = StageMetaclass

    pause_list = ListProperty([])
    ''' The list of children this stage paused and we therefore need to unpause
    them after this stage becomes unpaused. Children stages that were already
    paused when the stage paused do not have to be unpaused.
    '''

    _loop_finishing = BooleanProperty(False)
    '''Whether this loop iteratioon is force stopped. loop_done is true only
    the stage loop itelf completed, but maybe not the substages.
    when this is true, the substages are force stopped.'''

    _within_step_stage = False

    def add_widget(self, widget, index=None, **kwargs):
        if widget is self:
            raise Exception('You cannot add yourself in a MoaStage')

        if isinstance(widget, (MoaStage, _MoaStageAlt, moa.stage.MoaStage)):
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
        if not isinstance(stage, (MoaStage, _MoaStageAlt, moa.stage.MoaStage)):
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
        if isinstance(widget, (MoaStage, _MoaStageAlt, moa.stage.MoaStage)):
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
            pause_list = self.pause_list
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
            Clock.schedule_once_free(self._do_stage_timeout, max(0.,
            self.max_duration - self.elapsed_time))
        if recurse:
            for child in self.pause_list:
                try:
                    if child.paused:
                        child.unpause(True)
                except ReferenceError:
                    pass
        self.pause_list = []
        return True

    def stop(self, stage=True, **kwargs):
        '''Stops async recursively. Use self.finished to check when really
        stopped.

        When this is called with super, this instance loop_done is set to True.
        '''
        if not self.started or self.finished or stage and self.finishing or \
                not stage and self.loop_done:
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

    def clear(self, loop=False, **kwargs):
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
        return True

    def apply_restore_properties(self):
        items = list(self.restored_properties.items())
        self.restored_properties = {}
        for k, v in items:
            setattr(self, k, v)

    def skip_stage(self):
        ''' If True, when step_stage is called, it must continue the chain,
        even if not actually started. It is important, that this method does
        not modify the state. I.e. calling this method twice in series
        should return the same value.
        '''
        return self.disabled

    def start_stage(self):
        self.log('debug', 'Step stage, starting stage')
        self.clear()
        for child in self.stages[:]:
            child.clear()

        self.apply_restore_properties()
        self.start_time = time.clock()
        max_duration = self.max_duration
        if not self.paused and max_duration > 0.:
            Clock.schedule_once_free(
                self._do_stage_timeout, max_duration)
        self.started = True
        self.dispatch('on_stage_start')
        return True

    def start_trial(self, start_stage=False):
        stages = self.stages[:]
        if not start_stage:
            for child in stages:
                child.clear()
            self.clear(loop=True)
            t = time.clock()
            self.elapsed_time += t - self.start_time
            self.start_time = t
            self.count += 1
        self.dispatch('on_trial_start', self.count)

        if self.order == 'serial':
            for child in stages:
                if not child.skip_stage():
                    child.step_stage()
                    break
        else:
            for child in stages:
                child.step_stage()
        return True

    def advance_child_stage(self):
        # loop not done, so decide if need to start next child, or wait
        # for self/substage to complete.

        # if parallel, all children should be started already
        if self.order == 'parallel':
            return False

        i = None
        log = self.log
        stages = self.stages[:]
        # when serial see if there's a next child to start
        for k in range(len(stages)):
            child = stages[k]
            if not child.skip_stage() and not child.finished:
                # if a child is already running we cannot proceed
                if child.started:
                    log('warning', 'Could not start next child ({})'
                        '; this code should not have been reached', child)
                    return False
                else:
                    i = k
                    break

        if i is not None:
            for child in stages[i:]:
                if not child.skip_stage():
                    child.step_stage()
                    return False
                log('debug', 'skipping starting next serial child ({})',
                    child)

        if not self.loop_done:
            return False

        # if child becomes disabled between when we computed done and now
        # then we may end up here and the loop may need to be ended.
        log('warning', 'Could not start a child; this code should not '
            'have been reached')
        # if not loop_done:
        return False

    def check_loop_done(self):
        '''if this loop should be terminated and increment count.
        '''
        loop_done = self.loop_done
        comp_list = self.completion_list or self.stages
        comp_type = self.completion_type
        if self.finishing or self._loop_finishing:
            return True

        if not comp_list:
            return loop_done

        if comp_type == 'any':
            if loop_done and self in comp_list:
                return True
            return any((c.finished and not c.skip_stage() for c in comp_list))

        for c in comp_list:
            if c == self:
                if not loop_done:
                    return False
            else:
                if not c.finished and not c.skip_stage():
                    return False
        return True

    def ask_step_stage(self, source=None, **kwargs):
        return Clock.schedule_once_free(
            partial(_ask_step_stage, self, source=source, **kwargs), -1)

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
        log = self.log
        if self._within_step_stage:
            log('error', 'step_stage for has been called recursively and may '
                'result in incorrect behavior. Please use ask_step_stage '
                'instead', stack_info=True)
        children = self.stages[:]
        if source is None:
            source = self
        # if we should start this stage
        start = (not self.started or self.finished) and source is self

        if start:
            if self.skip_stage():
                log('debug', 'Step stage start skipped with skip_stage()')
                return False
            self._within_step_stage = True
            try:
                if not self.start_stage():
                    return False
            finally:
                self._within_step_stage = False
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
            self._within_step_stage = True
            self.loop_done = True
            self._within_step_stage = False
        # if this loop should be terminated and increment count
        old_done = self._loop_finishing
        done = self._loop_finishing = self.check_loop_done()
        if not old_done and done:
            self._within_step_stage = True
            self.dispatch('on_trial_end', self.count)
            self._within_step_stage = False

        # if we need to finish loop, stop all the children and ourself
        # (just the loop, not stage)
        if done:
            for child in children:
                if child.stop():
                    return False
            # in case child initiated completion, so we did not finish loop
            if not self.loop_done:
                self.stop(stage=False)
                return False
        elif not start:
            # if self is responsible and it's not done there's nothing to do
            if source is self:
                return False
            return self.advance_child_stage()

        # if we reached here then either start or loop and children are done
        if not self.finishing and (start or self.repeat == -1 or
                                   self.count + 1 < self.repeat):
            self._within_step_stage = True
            try:
                return self.start_trial(start_stage=start)
            finally:
                self._within_step_stage = False

        if self.max_duration > 0.:
            Clock.unschedule(self._do_stage_timeout)
        self.elapsed_time += time.clock() - self.start_time
        self._within_step_stage = True
        self.finished = True
        self.dispatch('on_stage_end')
        self._within_step_stage = False
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
        return '<{} knsname="{}": {}/{} parent="{}" {}>'.format(
            self.__class__.__name__, self.knsname, self.count + 1, self.repeat,
            'None' if self.parent is None else self.parent.knsname, text)

    def on_stage_start(self, *largs):
        pass

    def on_trial_start(self, count):
        pass

    def on_trial_end(self, count):
        pass

    def on_stage_end(self):
        pass

    stages = ListProperty([])
    '''A list of children :class:`MoaStage` instance. When a stage is started,
    it's children stages are also started with the exact details depending on
    the :attr:`order`.

    Similarly, a stage is considred finished when its children stages
    are done and when its loops are done, depending on

    It is read only. To modify, call :meth:`add_stage` or :meth:`remove_stage`.
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

    restored_properties = DictProperty({})

    restore_properties = ListProperty([])

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

from moa.stage.__init__ import MoaStage as _MoaStageAlt
