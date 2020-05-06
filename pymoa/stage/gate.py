"""Device gated stage
=====================

"""
from typing import Tuple
from time import perf_counter
import trio
import math
from kivy.properties import (
    BooleanProperty, StringProperty, BoundedNumericProperty, ObjectProperty,
    NumericProperty, ReferenceListProperty)

from pymoa.stage import MoaStage
from pymoa.kivy import AsyncBindQueue
from pymoa.device import Device

__all__ = ('GateStage', 'DigitalGateStage', 'AnalogGateStage')


class GateStage(MoaStage):

    _logged_trigger_names_ = ('state', )

    async def do_trial(self):
        dev = self.device
        prop = self.state_prop
        check_done = self.check_done
        hold_time = self.hold_time
        state = object()
        ignore = not self.use_initial

        def watch_device(instance, value):
            return perf_counter(), value

        # wait in case hold time was not long enough
        async with trio.move_on_at(math.inf) as cancel_scope:
            async for t, new_state in AsyncBindQueue(
                    dev, prop, convert=watch_device, current=True):
                if new_state == state:
                    # completely ignore if they are the same, shouldn't happen
                    continue

                state = self.state = new_state
                if not check_done(t, state):
                    # reset and start waiting again for the correct done state
                    # we don't ignore the first time after state doesn't match
                    ignore = False
                    cancel_scope.deadline = math.inf
                    continue
                elif ignore:
                    continue

                if not hold_time:
                    return

                # check that we aren't holding already
                if cancel_scope.deadline == math.inf:
                    cancel_scope.deadline = trio.current_time() + max(
                        hold_time - (perf_counter() - t), 0)

    def check_done(self, t, value):
        raise NotImplementedError

    device: Device = ObjectProperty(None, allownone=True)
    '''The input device.
    '''

    state_prop: str = StringProperty('state')
    ''' The name of the attr in device to bind.
    '''

    hold_time: float = BoundedNumericProperty(0, min=0)
    ''' How long the state must be held to finish.
    '''

    use_initial: bool = BooleanProperty(True)
    ''' Whether we can complete the stage if when entering, the channel is
    already at this exit_state.
    '''

    state = ObjectProperty(None, allownone=True)


class DigitalGateStage(GateStage):

    def check_done(self, t: float, value: bool):
        return value == self.exit_state

    exit_state: bool = BooleanProperty(False)
    '''The state the device has to be on in order to exit from this stage.
    '''


class AnalogGateStage(GateStage):

    def check_done(self, t: float, value: float):
        return self.min <= value <= self.max

    max: float = NumericProperty(0)

    min: float = NumericProperty(0)

    range: Tuple[float, float] = ReferenceListProperty(min, max)
