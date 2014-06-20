''' largs is banned.
'''

__all__ = ('MoaStage', )

import time
from kivy.clock import Clock
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty)
from kivy.uix.widget import Widget
from moa.base import MoaBase
from moa.threading import CallbackDeque


class MoaStage(MoaBase, Widget):

    _pause_list = []
    ''' The list of children we ourselves have paused and we need to unpause
    after we ourself become unpaused. Children that were already paused when
    we paused do not have to be unpaused.
    '''
    _loop_finishing = False
    _schedule_queue = None
    _schedule_increment = None

    def __init__(self, **kwargs):
        self.size_hint = None, None
        self.size = 0, 0
        super(MoaStage, self).__init__(**kwargs)
        self._pause_list = []
        self._schedule_queue = CallbackDeque(
                                    Clock.create_trigger(self._service_queue))
        self._schedule_increment = \
        lambda dt: self.parent.step_stage(source=self)

    def get_state(self, state=None):
        if state is None:
            state = {}
        for attr in ('name', 'disabled', 'finished', 'paused', 'count'):
            state[attr] = getattr(self, attr)
        return state

    def recover(self, state):
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

    def on_paused(self, instance, value, recurse=True, **kwargs):
        if self.disabled or not self.started or self.finished:
            return

        if value:
            # we paused so we need to pause the clock and save elapsed time
            self.elapsed_time += time.clock() - self.start_time
            Clock.unschedule(self._do_stage_timeout)
            if recurse:
                pause_list = self._pause_list
                for child in self.stages:
                    # only pause children not yet paused
                    if not child.paused:
                        child.paused = True
                        pause_list.append(child)
        else:
            self.start_time = time.clock()
            if self.max_duration > 0.:
                Clock.schedule_once(self._do_stage_timeout, max(0.,
                self.max_duration - self.elapsed_time))
            if recurse:
                for child in self._pause_list:
                    child.paused = False

    def stop(self, stage=True, **kwargs):
        '''Stops async recursively. Use self.finished to check when really
        stopped.

        When this is called with super, this instance loop_done is set to True.
        '''
        if not self.started or self.finished:
            return False

        # all children were stopped, so we can stop now
        Clock.unschedule(self._do_stage_timeout)
        if stage:
            self.finishing = True
        else:
            self._loop_finishing = True
        self.step_stage(source=self)
        return False

    def on_disabled(self, instance, value, **kwargs):
        ''' Dispatch.
        '''
        if value and self.started and not self.finished:
            self.stop()

    def clear(self, recurse=False, **kwargs):
        '''Clears started etc. stops running if running.
        '''
        if self.started and not self.finished:
            self.logger.warning('Clearing unfinished stage, may lead to state '
                                'corruption')

        self.finished = False
        self.started = False
        self.count = 0
        self.elapsed_time = 0.
        self.start_time = 0.
        self.loop_done = False
        self.finishing = False
        self._loop_finishing = False
        if recurse:
            for child in self.stages[:]:
                child.clear(recurse)
        return True

    def step_stage(self, source=None, **kwargs):
        ''' Only allowed to be called when after on_stop, or if class finished
        lopp on its own in which case finishing is True.

        source None is the same as self.

        When source is self (None) and we need to step the loop, it may only
        return false if didn't start b/c not finished or disabled. To prevent
        from starting set it to disabled, and not by just returning here False.
        Otherwise, we may never proceed to the next stage because the stop
        condition is not met, but start returns False.
        '''

        children = self.stages[:]
        comp_list = self.completion_list
        comp_type = self.completion_type
        order = self.order
        logger = self.logger
        if source is None:
            source = self
        start = (not self.started or self.finished) and source is self

        if start:
            if self.disabled:
                logger.debug('Skipped starting disabled stage')
                return False
            logger.trace('Starting stage')
            self.clear()
            for child in children:
                child.clear()

            self.start_time = time.clock()
            self.started = True
            if not self.paused and self.max_duration > 0.:
                Clock.schedule_once(self._do_stage_timeout, self.max_duration)
        elif not self.started and source is not self:
            logger.warning('Ignored step_stage for source {}, because'
                           ' stage is not started'.format(source))
            return False
        elif self.finished:
            logger.error('Ignored step_stage (source={}) on finished '
                         'stage'.format(source))
            return False

        # decide if this loop iteration is done
        if source is self and not start:
            self.loop_done = True
        loop_done = self.loop_done
        done = self._loop_finishing = (self.finishing or self._loop_finishing
            or (comp_type == 'any' and
            (not comp_list or (loop_done and self in comp_list) or
             any([c.finished and not c.disabled for c in comp_list])))
            or (comp_type == 'all' and
            ((comp_list and all([(c.finished or c.disabled) and c is not self
            or c is self and loop_done for c in comp_list]))
            or (not comp_list and loop_done and
            all([c.finished for c in children])))))

        # if we need to finish, stop all the children
        i = None
        if done:
            for child in children:
                if not child.disabled and child.started and not child.finished:
                    child.stop()
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
                    if not child.disabled and not child.finished:
                        # if a child is already running we cannot proceed
                        if child.started:
                            return False
                        elif i is None:
                            i = k
                            break

                # if we didn't find a child to start, then just wait
                if i is not None:
                    for child in children[i:]:
                        if child.step_stage():
                            return False
                logger.warning('Could not start a child; this code should '
                               'not have been reached')
                # if no child was started, we may now need to finish
                if not loop_done:
                    return False

        # if we reached here then either start or (loop_done and all children
        # are done)
        if not self.finishing and (start or self.repeat == -1 or
            self.count + (0 if start else 1) < self.repeat):

            if not start:
                for child in children:
                    if not child.disabled:
                        child.clear()
                self.loop_done = self._loop_finishing = False
                t = time.clock()
                self.elapsed_time += t - self.start_time
                self.start_time = t
                self.count += 1

            if order == 'serial':
                for child in children:
                    if child.step_stage():
                        break
            else:
                for child in children:
                    child.step_stage()
            return True

        self.finished = True
        parent = self.parent
        if parent is not None:
            parent.step_stage(source=self)
        return False

    def _service_queue(self, dt):
        while 1:
            try:
                f, largs, kwargs = self._schedule_queue.popleft()
            except IndexError:
                return

            f(*largs, **kwargs)

    def _do_stage_timeout(self, *l):
        if (self.max_duration > 0. and time.clock() - self.start_time +
            self.elapsed_time >= self.max_duration):
            self.stop()

    def __repr__(self):
        if self.finished:
            text = 'finished'
        elif self.started:
            text = 'started'
        else:
            text = 'not started'
        return '<{} name="{}": {}/{} parent="{}" {}>'.format(
            self.__class__.__name__, self.name, self.count, self.repeat,
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
