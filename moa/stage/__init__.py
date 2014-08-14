''' largs is banned.
TODO: when completion_type is any, save the one that initiated the stop
'''

__all__ = ('MoaStage', )

import time
from kivy.clock import Clock
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty)
from kivy.uix.widget import Widget
from moa.base import MoaBase


class MoaStage(MoaBase, Widget):

    _pause_list = []
    ''' The list of children we ourselves have paused and we need to unpause
    after we ourself become unpaused. Children that were already paused when
    we paused do not have to be unpaused.
    '''
    _loop_finishing = False

    def __init__(self, **kwargs):
        self.size_hint = None, None
        self.size = 0, 0
        super(MoaStage, self).__init__(**kwargs)
        self.canvas = None
        self._pause_list = []

    def on_opacity(self, instance, value):
        # don't allow accessing canvas that was set to none
        pass

    def get_state(self, state=None):
        if state is None:
            state = {}
        for attr in ('name', 'disabled', 'finished', 'paused', 'count'):
            state[attr] = getattr(self, attr)
        return state

    def recover_state(self, state):
        self.clear()
        for k, v in state.iteritems():
            setattr(self, k, v)

    def add_widget(self, widget, index=None, **kwargs):
        if widget is self:
            raise Exception('You cannot add yourself in a MoaStage')

        if isinstance(widget, MoaStage):
            self.add_stage(widget, index, **kwargs)
        elif not isinstance(widget, Widget):
            raise Exception('add_widget() can be used only with Widget '
                            'or MoaStage classes.')
        else:
            children = self.children
            if index is None or index >= len(children):
                children.append(widget)
            else:
                children.insert(widget, index)

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
        stage.parent = parent = self
        # child will be disabled if added to a disabled parent
        if parent.disabled:
            stage.disabled = True

        if index is None or index >= len(stages):
            stages.append(stage)
        else:
            stages.insert(stage, index)

    def remove_widget(self, widget, **kwargs):
        if isinstance(widget, MoaStage):
            self.remove_stage(widget, **kwargs)
        else:
            try:
                self.children.remove(widget)
            except ValueError:
                pass

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
            self.add_log(cause='pause', message='ignored', attrs=('disabled',
                'started', 'finished'))
            return False
        self.add_log(cause='pause', vals=('recurse', recurse))

        # we paused so we need to pause the clock and save elapsed time
        self.elapsed_time += time.clock() - self.start_time
        Clock.unschedule(self._do_stage_timeout)
        if recurse:
            pause_list = self._pause_list
            for child in self.stages:
                # only pause children not yet paused
                if not child.paused:
                    child.pause()
                    pause_list.append(child)
        return True

    def unpause(self, recurse=True):
        paused = self.paused
        self.paused = False

        if self.disabled or not self.started or self.finished or not paused:
            self.add_log(cause='unpause', message='ignored', attrs=('disabled',
                'started', 'finished'), vals=('paused', paused))
            return False
        self.add_log(cause='unpause', vals=('recurse', recurse))

        self.start_time = time.clock()
        if self.max_duration > 0.:
            Clock.schedule_once(self._do_stage_timeout, max(0.,
            self.max_duration - self.elapsed_time), priority=True)
        if recurse:
            for child in self._pause_list:
                if child.paused:
                    child.unpause()
        self._pause_list = []
        return True

    def stop(self, stage=True, **kwargs):
        '''Stops async recursively. Use self.finished to check when really
        stopped.

        When this is called with super, this instance loop_done is set to True.
        '''
        if not self.started or self.finished:
            self.add_log(cause='stop', message='ignored', attrs=('started',
                'finished'), vals=('stage', stage))
            return False
        self.add_log(cause='stop', vals=('stage', stage))

        # all children were stopped, so we can stop now
        Clock.unschedule(self._do_stage_timeout)
        if stage:
            self.finishing = True
        else:
            self._loop_finishing = True
        self.step_stage(source=self)
        return True

    def on_disabled(self, instance, value, **kwargs):
        ''' Dispatch.
        '''
        self.add_log(cause='disabled', vals=('disabled', value))
        if value:
            self.stop()

    def clear(self, recurse=False, loop=False, **kwargs):
        '''Clears started etc. stops running if running.
        '''
        if not loop and self.started and not self.finished:
            self.add_log(level='warning', message='Clearing unfinished stage, '
                'may lead to state corruption', cause='clear',
                vals=('started', self.started, 'finished', self.finished))

        self._loop_finishing = False
        self.loop_done = False
        self.timed_out = False

        if not loop:
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
        even if not actually started.
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
        start = (not self.started or self.finished) and source is self
        add_log = self.add_log

        if start:
            if self.get_skip_stage():
                add_log(cause='step_stage', message='skip starting stage '
                        'because of get_skip_stage')
                return False
            add_log(cause='step_stage', message='starting stage')
            self.clear()
            for child in children:
                child.clear()

            self.start_time = time.clock()
            self.started = True
            max_duration = self.max_duration
            if not self.paused and max_duration > 0.:
                add_log(cause='step_stage',
                        message='scheduling max_duration timeout',
                        vals=('max_duration', max_duration))
                Clock.schedule_once(self._do_stage_timeout, max_duration,
                                    priority=True)
        elif not self.started and source is not self:
            add_log(level='warning',
                    message='ignored because source not started',
                    cause='step_stage', vals=('source', source))
            return False
        elif self.finished:
            add_log(level='error',
                    message='ignored because stage is finished',
                    cause='step_stage', vals=('source', source))
            return False
        elif self.max_duration > 0.:
            Clock.unschedule(self._do_stage_timeout)

        # decide if this loop iteration is done
        if source is self and not start:
            self.loop_done = True
        loop_done = self.loop_done
        done = self._loop_finishing = (self.finishing or self._loop_finishing
            or (comp_type == 'any' and
            (not comp_list or (loop_done and self in comp_list) or
             any([c.finished and not c.get_skip_stage() for c in comp_list])))
            or (comp_type == 'all' and
            ((comp_list and all([(c.finished or c.get_skip_stage()) and
                                 c is not self
            or c is self and loop_done for c in comp_list]))
            or (not comp_list and (not children and loop_done or children and
            all([c.finished or c.get_skip_stage() for c in children]))))))

        add_log(cause='step_stage', vals=('source', source, 'done', done,
                                          'loop_done', loop_done))
        i = None
        # if we need to finish, stop all the children
        if done:
            for child in children:
                if child.stop():
                    return False
            if not loop_done:
                self.stop(stage=False)
                return False
        elif not start:
            # if parallel, all should be started so just wait until we done
            if order == 'parallel':
                return False
            # if serial see if there's a next child to start, otherwise wait to
            # finish
            else:
                # if we don't need to finish, find the first not started child
                for k in range(len(children)):
                    child = children[k]
                    if not child.get_skip_stage() and not child.finished:
                        # if a child is already running we cannot proceed
                        if child.started:
                            return False
                        else:
                            i = k
                            break

                # if we didn't find a child to start, then just wait
                if i is not None:
                    for child in children[i:]:
                        if not child.get_skip_stage():
                            child.step_stage()
                            return False
                        add_log(cause='step_stage', message='skipping starting'
                                ' next serial child: {}'.format(child))

                add_log('warning', message='Could not start a child; this '
                        'code should not have been reached')
                # if no child was started, we may now need to finish
                if not loop_done:
                    return False

        # if we reached here then either start or (loop_done and all children
        # are done)
        if not self.finishing and (start or self.repeat == -1 or
            self.count + (0 if start else 1) < self.repeat):

            if not start:
                add_log(cause='step_stage', message='incrementing count',
                        vals=('count', self.count))
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

        add_log(cause='step_stage', message='finishing stage')
        self.finished = True
        parent = self.parent
        if parent is not None:
            parent.step_stage(source=self)
        return False

    def _do_stage_timeout(self, *l):
        self.add_log(cause='max_duration', message='timed out')
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

    stage_render = ObjectProperty(None, allownone=True)
    ''' The class used to display and control this stage in the stage tree.
    When `None`, we walk the parent tree until we find one which is not `None`,
    or an error is raised.
    This cannot be set from kv, because the children are added before this
    rule is applied. So from .py, either added as constructor argument,  or in
    constructor.
    '''

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
