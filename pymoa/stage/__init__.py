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

from kivy.properties import BooleanProperty, BoundedNumericProperty
from kivy.event import EventDispatcher

from pymoa.base import MoaBase

__all__ = ('MoaStage', )


class MoaStage(EventDispatcher, MoaBase):
    """Base stage for structuring an experiment.

    """

    __events__ = (
        'on_stage_start', 'on_trial_start', 'on_trial_end', 'on_stage_end')

    _logged_names_hint_ = __events__ + ('count', 'active')

    _config_props_ = (
        'disabled', 'complete_on', 'order', 'max_trial_duration',
        'max_duration', 'repeat')

    __trial_cancel_scope = None

    __stage_cancel_scope = None

    def __init__(
            self, repeat=1, max_duration=0., max_trial_duration=0.,
            order='serial', complete_on='all', complete_on_whom=(),
            disabled=False,
            **kwargs):
        super().__init__(**kwargs)
        self.stages = []
        self.complete_on_whom = list(complete_on_whom)
        self.repeat = repeat
        self.max_duration = max_duration
        self.max_trial_duration = max_trial_duration
        self.order = order
        self.complete_on = complete_on
        self.disabled = disabled

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
        # check if stage is already a child of another stage
        if parent:
            raise Exception(
                f'Cannot add {stage}, it already has a parent {parent}')
        stage.parent = self

        if index is None or index >= len(stages):
            stages.append(stage)
        else:
            stages.insert(index, stage)

    def remove_stage(self, stage: 'MoaStage', **kwargs):
        if stage.parent is not self:
            raise ValueError(f'{stage} is not a child stage of {self}.')

        self.stages.remove(stage)
        stage.parent = None

    async def _do_stage_trial(
            self, i, stages, complete_on, complete_on_whom, serial):
        complete_on_whom = complete_on_whom.copy()
        max_trial_duration = self.max_trial_duration
        currently_running = 0

        def handle_done(completed_stage: MoaStage) -> bool:
            nonlocal currently_running
            currently_running -= 1
            # if this doesn't affect cancellation, no need to cancel
            if completed_stage not in complete_on_whom:
                return False

            if complete_on == 'all':
                complete_on_whom.remove(completed_stage)
                if complete_on_whom:
                    return False

            assert currently_running >= 0
            if currently_running:
                # only manually cancel if there are others running
                trial_scope.cancel_scope.cancel()
            return True

        async def start_trial_and_signal(
                trial_num, task_status=trio.TASK_STATUS_IGNORED):
            await self.init_trial(trial_num)
            task_status.started()

            # todo: document that it is dispatched **after** init
            self.dispatch('on_trial_start', self, trial_num)

            await self.do_trial()
            handle_done(self)

        async def start_child_stage(
                child_stage, task_status=trio.TASK_STATUS_IGNORED):
            # if we're done because a previously started stage finished and the
            # stage is done, check to see if we're canceled before starting
            await trio.lowlevel.checkpoint()

            await child_stage.run_stage(task_status=task_status)
            handle_done(child_stage)

        try:
            async with trio.open_nursery() as trial_scope:
                self.__trial_cancel_scope = trial_scope
                if max_trial_duration:
                    trial_scope.cancel_scope.deadline = \
                        trio.current_time() + max_trial_duration

                currently_running += 1
                await trial_scope.start(start_trial_and_signal, i)

                if serial:
                    # do children sequentially
                    for stage in stages:
                        currently_running += 1
                        if not stage.stage_is_skipped:
                            await stage.run_stage()
                        # don't schedule more stuff if we're done
                        if handle_done(stage):
                            return
                else:
                    # start the children one of the other, but only wait for
                    # the stage to init before starting the next. So all
                    # children will run parallel once init
                    for stage in stages:
                        currently_running += 1
                        if not stage.stage_is_skipped:
                            await trial_scope.start(start_child_stage, stage)
                        else:
                            if handle_done(stage):
                                # don't schedule more stuff if we're done
                                return
        finally:
            self.__trial_cancel_scope = None

        # todo: make sure this value is correct when it timed out
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
                with trio.CancelScope(shield=True):
                    await self.trial_done(exception=True)
                    # todo: document that it is dispatched **after** done
                    self.dispatch('on_trial_end', self, i)
                raise
            except trio.Cancelled:
                # if we get Cancelled, that means this stage wasn't canceled,
                # but rather some stage above us was canceled so we canceled
                with trio.CancelScope(shield=True):
                    await self.trial_done(exception=True)
                    self.dispatch('on_trial_end', self, i)
                raise

            with trio.CancelScope(shield=True):
                await self.trial_done(canceled=canceled)
                self.dispatch('on_trial_end', self, i)

            i += 1

    async def run_stage(self, task_status=trio.TASK_STATUS_IGNORED):
        max_duration = self.max_duration
        normal_exit = True
        self.active = True

        try:
            with trio.move_on_at(math.inf) as stage_scope:
                # save so we can call stop on the stage
                self.__stage_cancel_scope = stage_scope
                if max_duration:
                    stage_scope.deadline = trio.current_time() + max_duration

                await self.init_stage()
                task_status.started()

                # todo: document that it is dispatched **after** init
                self.dispatch('on_stage_start', self)

                await self._do_stage_trials()
        except Exception:
            normal_exit = False
            with trio.CancelScope(shield=True):
                await self.stage_done(exception=True)
                self.dispatch('on_stage_end', self)
            raise
        except trio.Cancelled:
            # if we get Cancelled, that means this stage wasn't canceled, but
            # rather some stage above us was canceled so we also got canceled
            normal_exit = False
            with trio.CancelScope(shield=True):
                await self.stage_done(exception=True)
                # todo: document that it is dispatched **after** done
                self.dispatch('on_stage_end', self)
            raise
        finally:
            self.__stage_cancel_scope = None
            if not normal_exit:
                # won't be able to set it later
                self.active = False

        try:
            with trio.CancelScope(shield=True):
                await self.stage_done(canceled=stage_scope.cancelled_caught)
                self.dispatch('on_stage_end', self)
        finally:
            self.active = False

    async def init_stage(self):
        """Should take minimal time and must be called with ``super``.
        """
        self.count = 0

    async def init_trial(self, i: int):
        """Should take minimal time and must be called with ``super``.
        """
        self.count = i

    async def do_trial(self):
        raise NotImplementedError

    async def trial_done(self, exception=False, canceled=False):
        """Canceled means that cancel was called for this specific stage and
        trial, or it timed out, or the complete_on_whom caused it to exit.

        Called under a shielded cancel scope.
        """
        pass

    async def stage_done(self, exception=False, canceled=False):
        """Canceled means that cancel was called for this specific stage
        and it ended early.

        Called under a shielded cancel scope.
        """
        pass

    def stop_stage(self):
        if self.__stage_cancel_scope is not None:
            self.__stage_cancel_scope.cancel()

    def stop_trial(self):
        """Continues the next trial.
        """
        if self.__trial_cancel_scope is not None:
            self.__trial_cancel_scope.cancel_scope.cancel()

    @property
    def stage_is_skipped(self):
        return self.disabled

    def __repr__(self):
        active = 'active' if self.active else 'inactive'
        name = self.name or 'unnamed'
        parent_name = ''
        if self.parent:
            parent_name = self.parent.name or 'unnamed'
        cls = self.__class__
        cls_name = cls.__module__ + '.' + cls.__qualname__

        return f'<{cls_name} name="{name}": {self.count}/{self.repeat} ' \
               f'parent="{parent_name}" {active} at 0x{id(self):016X}>'

    def on_stage_start(self, *largs):
        pass

    def on_trial_start(self, obj, count, *largs):
        pass

    def on_trial_end(self, obj, count, *largs):
        pass

    def on_stage_end(self, *largs):
        pass

    def iterate_stages(self):
        yield self
        for stage in self.stages:
            for child in stage.iterate_stages():
                yield child

    stages: List['MoaStage'] = []
    '''A list of children :class:`MoaStage` instance. When a stage is started,
    it's children stages are also started with the exact details depending on
    the :attr:`order`.

    Similarly, a stage is considred finished when its children stages
    are done and when its loops are done, depending on

    It is read only. To modify, call :meth:`add_stage` or :meth:`remove_stage`.
    '''

    parent: 'MoaStage' = None
    '''Parent of this widget.

    :attr:`parent` is an :class:`~kivy.properties.ObjectProperty` and
    defaults to None.

    The parent of a widget is set when the widget is added to another widget
    and unset when the widget is removed from its parent.
    '''

    repeat: int = 1
    ''' 1 is once, -1 is indefinitely.
    '''

    count: int = BoundedNumericProperty(-1, min=-1)
    ''' Zero is the first etc. updated after the loop jumps back. read only
    '''

    max_duration: float = 0
    '''If non zero, the total duration that this stage goes on. Including
    the loops and stage initialization, excluding :meth:`stage_done`.
    '''

    max_trial_duration: float = 0
    '''If non zero, the total duration that each trial goes on. Including
    the trial initialization but excluding :meth:`trial_done`.
    '''

    order: str = 'serial'
    '''Whether sub-stages are run at same time or one after the other.
    '''

    complete_on: str = 'all'
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    complete_on_whom: List['MoaStage'] = []
    ''' If parallel, whether it completes when any or all of its sub-stages
    are done. Can be `all`, `any`, or a list-type of child and self.
    '''

    active: bool = BooleanProperty(False)

    disabled: bool = False
    ''' If this stage is disabled.
    '''
