"""Device gated stage
=====================

"""
from time import perf_counter
import trio
import math

from pymoa.stage import MoaStage
from kivy_trio.to_kivy import AsyncKivyBind
from pymoa.device import Device

__all__ = ('GateStage', 'DigitalGateStage', 'AnalogGateStage')


class GateStage(MoaStage):
    """Stage that waits until a device reaches some state.
    """

    _config_props_ = (
        'state_prop', 'hold_time', 'use_initial')

    def __init__(
            self, device=None, state_prop='state', hold_time=0,
            use_initial=True, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.state_prop = state_prop
        self.hold_time = hold_time
        self.use_initial = use_initial

    async def do_trial(self):
        await trio.lowlevel.checkpoint()
        dev = self.device
        prop = self.state_prop
        check_done = self.check_done
        hold_time = self.hold_time
        ignore = not self.use_initial

        def get_state(*args):
            return perf_counter(), getattr(dev, prop)

        # wait in case hold time was not long enough
        with trio.move_on_at(math.inf) as cancel_scope:
            t, state = get_state()
            if not check_done(t, state):
                # move to waiting for correct state
                # we don't ignore the initial if state already doesn't match
                ignore = False
            elif not ignore:
                # matched exit and we can use initial state
                if not hold_time:
                    return
                cancel_scope.deadline = trio.current_time() + max(
                    hold_time - (perf_counter() - t), 0)

            async with AsyncKivyBind(
                    dev, 'on_data_update', convert=get_state) as queue:
                async for t, new_state in queue:
                    if new_state == state:
                        # completely ignore if they are the same
                        continue

                    state = new_state
                    if not check_done(t, state):
                        # reset and start waiting again for the correct done
                        # state we don't ignore the first time after state
                        # doesn't match
                        ignore = False
                        cancel_scope.deadline = math.inf
                        continue
                    elif ignore:
                        continue

                    if not hold_time:
                        return

                    # check that we aren't holding already, if state changed
                    # but it's still done
                    if cancel_scope.deadline == math.inf:
                        cancel_scope.deadline = trio.current_time() + max(
                            hold_time - (perf_counter() - t), 0)

    def check_done(self, t, value):
        raise NotImplementedError

    # todo: add named devices that can be set from config
    device: Device = None
    '''The input device.
    '''

    state_prop: str = 'state'
    ''' The name of the attr in device to bind.
    '''

    hold_time: float = 0
    ''' How long the state must be held to finish.
    '''

    use_initial: bool = True
    ''' Whether we can complete the stage if when entering, the channel is
    already at this exit_state.
    '''


class DigitalGateStage(GateStage):
    """Stage that waits until a digital device becomes :attr:`exit_state`.
    """

    _config_props_ = ('exit_state', )

    def __init__(self, exit_state=False, **kwargs):
        super().__init__(**kwargs)
        self.exit_state = exit_state

    def check_done(self, t: float, value: bool):
        return value == self.exit_state

    exit_state: bool = False
    '''The state the device has to be on in order to exit from this stage.
    '''


class AnalogGateStage(GateStage):
    """Stage that waits until a analog device enters a range of values.
    """

    _config_props_ = ('min', 'max')

    def __init__(self, min=0., max=0., **kwargs):
        super().__init__(**kwargs)
        self.min = min
        self.max = max

    def check_done(self, t: float, value: float):
        return value is not None and self.min <= value <= self.max

    min: float = 0.

    max: float = 0.
