"""Stage
==========

A stage is fundamental to an experiment. A stage typically describes an epoch
during an experiment when something happens or when we wait for something to
happen. An experiment is composed of many stages.

A stage can contain other stages.
"""

from typing import List, Tuple, Dict, Optional
import trio
import math

from kivy.properties import (
    BooleanProperty, NumericProperty, OptionProperty, BoundedNumericProperty,
    ObjectProperty, ListProperty)

from pymoa.data_logger import Loggable

__all__ = ('MoaStage', )


class MoaStage(Loggable):
    """Base stage for structuring an experiment.

    """

    __events__ = (
        'on_stage_start', 'on_trial_start', 'on_trial_end', 'on_stage_end')

    _logged_trigger_names_ = __events__

    _logged_names_ = ('count', )

    __trial_cancel_scope = None

    __stage_cancel_scope = None

    def add_stage(
            self, stage: 'MoaStage', index: Optional[int] = None, **kwargs):
        """ Different than widget because of None.
        """
        stages = self.stages
        if not isinstance(stage, MoaStage):
            raise Exception(
                f'{stage} is not an instance of MoaStage and cannot be '
                f'added to stages')
        parent = stage.parent
        # check if widget is already a child of another widget
        if parent:
            raise Exception(
                f'Cannot add {stage}, it already has a parent {parent}')
        stage.parent = self

        if index is None or index >= len(stages):
            stages.append(stage)
        else:
            stages.insert(stage, index)

    def remove_stage(self, stage: 'MoaStage', **kwargs):
        if stage.parent is not self:
            raise ValueError(f'{stage} is not a child stage of {self}.')

        try:
            self.stages.remove(stage)
            stage.parent = None
        except ValueError:
            pass

    async def _do_stage_trial(
            self, i, stages, complete_on, complete_on_whom, serial):
        complete_on_whom = complete_on_whom.copy()
        max_trial_duration = self.max_trial_duration

        def handle_done(completed_stage):
            # if there are no more stages, no need to cancel
            if completed_stage not in complete_on_whom:
                return

            if complete_on == 'all':
                complete_on_whom.remove(completed_stage)
                if complete_on_whom:
                    return
            trial_scope.cancel_scope.cancel()

        async def start_trial_and_signal(
                trial_num, task_status=trio.TASK_STATUS_IGNORED):
            await self.init_trial(trial_num)
            task_status.started()
            await self.do_trial()
            handle_done(self)

        async def run_children_serially():
            for child_stage in stages:
                if not child_stage.stage_is_skipped:
                    await child_stage.run_stage()
                handle_done(child_stage)

        async def start_child_stage(
                child_stage, task_status=trio.TASK_STATUS_IGNORED):
            await child_stage.run_stage(task_status=task_status)
            handle_done(child_stage)

        try:
            async with trio.open_nursery() as trial_scope:
                self.__trial_cancel_scope = trial_scope
                if max_trial_duration:
                    trial_scope.cancel_scope.deadline = \
                        trio.current_time() + max_trial_duration

                await trial_scope.start(start_trial_and_signal, i)

                if serial:
                    trial_scope.start_soon(run_children_serially)
                else:
                    for stage in stages:
                        if not stage.stage_is_skipped:
                            await trial_scope.start(
                                start_child_stage, stage)
                        else:
                            handle_done(stage)
        finally:
            self.__trial_cancel_scope = None

        return trial_scope.cancel_scope.cancelled_caught

    async def _do_stage_trials(self):
        serial = self.order == 'serial'
        repeat = self.repeat
        stages = self.stages[:]
        complete_on = self.complete_on

        complete_on_whom = set(self.complete_on_whom)
        if not complete_on_whom:
            complete_on_whom.update(stages)
            complete_on_whom.add(self)

        i = 0
        while repeat < 0 or i < repeat:
            try:
                canceled = await self._do_stage_trial(
                    i, stages, complete_on, complete_on_whom, serial)
            except Exception:
                await self.trial_done(interrupted=True)
                raise
            except trio.Cancelled:
                with trio.move_on_at(math.inf) as cleanup_scope:
                    cleanup_scope.shield = True
                    await self.trial_done(interrupted=True)
                raise

            with trio.move_on_at(math.inf) as cleanup_scope:
                cleanup_scope.shield = True
                await self.trial_done(canceled=canceled)

            i += 1

    async def run_stage(self, task_status=trio.TASK_STATUS_IGNORED):
        max_duration = self.max_duration
        normal_exit = True
        self.active = True

        try:
            async with trio.move_on_at(math.inf) as stage_scope:
                # save so we can call stop on the stage
                self.__stage_cancel_scope = stage_scope
                if max_duration:
                    stage_scope.deadline = trio.current_time() + max_duration

                await self.init_stage()
                task_status.started()

                await self._do_stage_trials()
        except Exception:
            normal_exit = False
            await self.stage_done(interrupted=True)
            raise
        except trio.Cancelled:
            normal_exit = False
            with trio.move_on_at(math.inf) as cleanup_scope:
                cleanup_scope.shield = True
                await self.stage_done(interrupted=True)
            raise
        finally:
            self.__stage_cancel_scope = None
            if not normal_exit:
                self.active = False

        try:
            with trio.move_on_at(math.inf) as cleanup_scope:
                cleanup_scope.shield = True
                await self.stage_done(canceled=stage_scope.cancelled_caught)
        finally:
            self.active = False

    async def init_stage(self):
        self.count = 0

    async def init_trial(self, i: int):
        self.count = i

    async def do_trial(self):
        pass

    async def trial_done(self, interrupted=False, canceled=False):
        """Canceled means that cancel was called for the trial, and the
        trial definitely ended early. """
        pass

    async def stage_done(self, interrupted=False, canceled=False):
        """Canceled means that cancel was called for the trial, and the
        trial definitely ended early. """
        pass

    def stop_stage(self):
        if self.__stage_cancel_scope is not None:
            self.__stage_cancel_scope.cancel()

    def stop_trial(self):
        if self.__trial_cancel_scope is not None:
            self.__trial_cancel_scope.cancel_scope.cancel()

    @property
    def stage_is_skipped(self):
        """ If True, when step_stage is called, it must continue the chain,
        even if not actually started. It is important, that this method does
        not modify the state. I.e. calling this method twice in series
        should return the same value.
        """
        return self.disabled

    def __repr__(self):
        active = 'active' if self.active else 'inactive'
        parent_name = ''
        if self.parent:
            parent_name = self.parent.name or 'unnamed'
        cls = self.__class__
        cls_name = cls.__module__ + '.' + cls.__qualname__

        return f'<{cls_name} name="{self.name}": {self.count}/{self.repeat} ' \
               f'parent="{parent_name}" {active}>'

    def on_stage_start(self, *largs):
        pass

    def on_trial_start(self, count, *largs):
        pass

    def on_trial_end(self, count, *largs):
        pass

    def on_stage_end(self, *largs):
        pass

    stages: List['MoaStage'] = ListProperty([])
    '''A list of children :class:`MoaStage` instance. When a stage is started,
    it's children stages are also started with the exact details depending on
    the :attr:`order`.

    Similarly, a stage is considred finished when its children stages
    are done and when its loops are done, depending on

    It is read only. To modify, call :meth:`add_stage` or :meth:`remove_stage`.
    '''

    parent: 'MoaStage' = ObjectProperty(None, allownone=True)
    '''Parent of this widget.

    :attr:`parent` is an :class:`~kivy.properties.ObjectProperty` and
    defaults to None.

    The parent of a widget is set when the widget is added to another widget
    and unset when the widget is removed from its parent.
    '''

    repeat: int = BoundedNumericProperty(1, min=-1)
    ''' 1 is once, -1 is indefinitely.
    '''

    count: int = BoundedNumericProperty(-1, min=-1)
    ''' Zero is the first etc. updated after the loop jumps back. read only
    '''

    max_duration: float = BoundedNumericProperty(0, min=0)
    '''If non zero, the total duration that this stage goes on. Including
    the loops.
    '''

    max_trial_duration: float = BoundedNumericProperty(0, min=0)

    order: str = OptionProperty('serial', options=['serial', 'parallel'])
    '''Whether sub-stages are run at same time or one after the other.
    '''

    complete_on: str = OptionProperty('all', options=['all', 'any'])
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    complete_on_whom: List['MoaStage'] = ListProperty([])
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    active: bool = BooleanProperty(False)

    disabled: bool = BooleanProperty(False)
    ''' If this stage is disabled.
    '''
