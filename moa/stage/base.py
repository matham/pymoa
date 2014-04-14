''' largs is banned.
'''

__all__ = ('MoaStage', 'StageRender')

import time
from kivy.clock import Clock
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty, ListProperty)
from kivy.uix.widget import Widget
from kivy.logger import Logger as logging
from moa.base import MoaBase
from moa.threading import CallbackDeque


class StageRender(object):
    '''The class used to render graphical display of stages.
    '''

    def add_render(self, stage, widget, **kwargs):
        pass

    def remove_render(self, stage, widget, **kwargs):
        pass


class MoaStage(Widget, MoaBase):

    __events__ = ('on_start', 'on_stop', )
    ''' stop is dispatched when the children and itself needs to stop.
    '''

    _pause_list = []
    ''' The list of children we ourselves have paused and we need to unpause
    after we ourself become unpaused. Children that were already paused when
    we paused do not have to be unpaused.
    '''
    _loop_done = False
    ''' If the stage loop itself is done, this is True, need it in case
    children not done, so we know that we are ready to finish.
    '''
    _loop_end = False
    ''' If the stage loop itself is done, this is True, need it in case
    children not done, so we know that we are ready to finish.
    '''
    _schedule_queue = None

    def __init__(self, **kwargs):
        super(MoaStage, self).__init__(**kwargs)
        self._pause_list = []
        self._schedule_queue = CallbackDeque(
                                    Clock.create_trigger(self._service_queue))

    def recover(self, options={}, **kwargs):
        pass

    def add_widget(self, widget, index=None, **kwargs):
        if not isinstance(widget, MoaStage):
            self.add_display(widget, index=index, **kwargs)
        else:
            self.add_stage(widget, index, **kwargs)

    def add_stage(self, stage, index=None, **kwargs):
        stages = self.stages
        if not isinstance(stage, MoaStage):
            raise Exception('{} is not an instance of MoaStage and cannot be '
                            'added to stages'.format(stage))
        stage = stage.__self__
        if stage is self:
            raise Exception('You cannot add yourself in a stage')
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

    def add_display(self, widget, **kwargs):
        obj = self
        while obj.stage_render is None:
            parent = obj.parent
            if parent is not None and hasattr(parent, 'stage_render'):
                obj = parent
            else:
                break

        if obj.stage_render is None:
            raise Exception('Stage does not have renderer, so it cannot '
                            'accept {}'.format(widget))
        obj.stage_render.add_render(self, widget, **kwargs)

    def remove_widget(self, widget, **kwargs):
        if not isinstance(widget, MoaStage):
            self.remove_display(widget, **kwargs)
        else:
            self.remove_stage(widget, **kwargs)

    def remove_stage(self, stage, **kwargs):
        try:
            self.stages.remove(stage)
            stage.parent = None
        except ValueError:
            pass

    def remove_display(self, widget, **kwargs):
        obj = self
        while obj.stage_render is None:
            parent = obj.parent
            if parent is not None and hasattr(parent, 'stage_render'):
                obj = parent
            else:
                break

        if obj.stage_render is None:
            raise Exception('Stage does not have renderer, so it cannot '
                            'remove {}'.format(widget))
        obj.stage_render.remove_render(self, widget, **kwargs)

    def on_start(self, **kwargs):
        '''asynchrony a stop signal might arrive before start. Of course
        don't be an a-hole and randomly start stages when it's supposed to
        finish, just that it's ok
        must return if stage was started, false otherwise. True means it was
        eaten - stage started. So true stops the dispatch (unless parallel).
        this must be called through super.
        '''
        if self.disabled:
            logging.info('Moa: stage {} disabled'.format(self))
            return False
        if self.started and not self.finished:
            logging.info('Moa: Already started {}, cannot start while running'.
                         format(self))

        self.clear()
        # the stage needs to end after max_duration if provided
        if not self.paused and self.max_duration > 0.:
            Clock.schedule_once(self._do_stage_timeout, self.max_duration)

        # start the children and everything going
        self.increment_loop(source=self, start=True)
        return True

    def on_paused(self, instance, value, set_children=True, **kwargs):
        if self.disabled or not self.started or self.finished:
            return

        if value:
            # we paused so we need to pause the clock and save elapsed time
            self.elapsed_time += time.clock() - self.start_time
            Clock.unschedule(self._do_stage_timeout)
            if set_children:
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
            if set_children:
                for child in self._pause_list:
                    child.paused = False

    def on_stop(self, source=None, force=False, **kwargs):
        '''When called, it must stop stage and finished must be True if it
        returns False. Whether started or not.
        If it returns True, dispatching stops. To allow dispatching to reach
        everywhere, return False. It is the reponsobility of the one returning
        True, to dispatch stop with original source  at source when ready to
        stop.
        '''
        for c in self.stages[:]:
            if not c.finished and not c.disabled:
                if c.dispatch('on_stop', source=source, force=force, **kwargs):
                    assert not force
                    return True
        # all children were stopped, so we can stop now
        Clock.unschedule(self._do_stage_timeout)
        self.finished = True
        if source is self:
            parent = self.parent
            if parent is not None:
                self._schedule_queue.append(parent.increment_loop, source=self)
        return False

    def on_disabled(self, instance, value, **kwargs):
        if value and self.started and not self.finished:
            self.dispatch('on_stop', source=self, force=True)
        elif not value:
            self.clear()

    def clear(self, **kwargs):
        '''Clears started etc. stops running if running.
        '''
        if self.started and not self.finished:
            logging.exception('Moa: Cleared {}, but stage was not finished'.
                              format(self))
            self.dispatch('on_stop', force=True)

        self.finished = False
        self.started = False
        self.count = 0
        self.elapsed_time = 0.
        self.start_time = 0.
        self._loop_done = False
        self._loop_end = False
        for child in self.stages[:]:
            child.clear()
        return True

    def increment_loop(self, source=None, **kwargs):
        if self.finished:
            logging.warning('Moa: ignored increment {}, because stage is '
                            'finished'.format(self))
            return False

        start = kwargs.get('start', False)
        children = self.stages
        comp_list = self.completion_list
        comp_type = self.completion_type
        order = self.order

        if start:
            self._loop_end = True
        if source is None:
            source = self
        if source is self:
            self._loop_done = True
        loop_done = self._loop_done
        done = self._loop_end = (self._loop_end or (comp_type == 'any' and
            (not comp_list or (loop_done and self in comp_list) or
             any([c.finished and not c.disabled for c in comp_list]))) or
            (comp_type == 'all' and
            ((comp_list and all([(c.finished or c.disabled) and c is not self
            or c is self and loop_done for c in comp_list]))
            or (not comp_list and loop_done and
            all([c.finished for c in children])))))

        i = None
        if not start:
            for k in range(len(children)):
                child = children[k]
                if child.disabled:
                    continue
                if not child.finished:
                    if done:
                        # TODO: make this a kw param and use dispatch
                        child.dispatch('on_stop', source=child)
                        return False
                    elif child.started:
                        return False
                    elif i is None:
                        i = k

        # if not done, all children are not started otherwise they're finished
        if not done:
            # i == None means all children finished
            if i is None:
                if loop_done:   # if we're finished: no more children = done
                    done = True
                else:           # otherwise, go and wait until we finish
                    return False

        # if done, then all children are finished
        if done:
            # now we need to increment the loop
            if (self.repeat == -1 or
                self.count + (0 if start else 1) < self.repeat):
                for child in children:
                    if not child.disabled:
                        child.clear()

                self._loop_done = self._loop_end = False
                if not start:
                    self.elapsed_time += time.clock() - self.start_time
                    self.start_time = time.clock()
                    self.count += 1
                else:
                    self.start_time = time.clock()
                    self.started = True

                if order == 'serial':
                    for child in children:
                        if child.dispatch('on_start'):
                            break
                else:
                    for child in children:
                        child.dispatch('on_start')
                return True
            self.dispatch('on_stop', source=self)
            return False

        # here, i is the child that is not started yet.
        assert order == 'serial'
        for child in children[i:]:
            if child.dispatch('on_start'):
                break
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
            self.dispatch('on_stop', source=self)

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
