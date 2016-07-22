
from time import clock

from kivy.properties import (
    BooleanProperty, StringProperty, BoundedNumericProperty, ObjectProperty,
    NumericProperty, ReferenceListProperty)

from moa.stage import MoaStage
from kivy.clock import Clock

__all__ = ('GateStage', 'DigitalGateStage', 'AnalogGateStage')


class GateStage(MoaStage):

    last_state = None
    ''' Gets reset to None before starting. Gets assigned the value after a
    check.
    '''

    _start_hold_time = None
    _port_callback_trigger = None
    _hold_timeout_trigger = None

    def __init__(self, **kwargs):
        super(GateStage, self).__init__(**kwargs)
        self._port_callback_trigger = \
            Clock.create_trigger_free(self._port_callback)
        self._hold_timeout_trigger = \
            Clock.create_trigger_free(self._hold_timeout)

    def _hold_timeout(self, *largs):
        t = self.hold_time
        elapsed = clock() - self._start_hold_time
        self.log(
            'debug', 'hold timeout elapsed={}, done={}', elapsed, t <= elapsed)

        if t <= elapsed:
            device = self.device
            device.unbind(on_data_update=self._port_callback)
            device.deactivate(self)
            self._port_callback_trigger.cancel()
            self.step_stage()
        else:
            self._hold_timeout_trigger.timeout = t - elapsed
            self._hold_timeout_trigger()

    def _port_callback(self, *largs):
        device = self.device
        value = getattr(self.device, self.state_prop)
        last_val = self.last_state
        self.last_state = value
        if last_val == value:
            return

        if self.check_done(value, last_val):
            t = self.hold_time
            if t:
                if self._start_hold_time is not None:
                    return  # already waiting
                self.log('debug', 'Exit condition met, oldval={}, newval={}. '
                         'Starting timeout', last_val, value)
                self._start_hold_time = clock()
                self._hold_timeout_trigger.timeout = t
                self._hold_timeout_trigger()
            else:
                self.log('debug', 'Exit condition met, oldval={}, newval={}',
                         last_val, value)
                device.unbind(on_data_update=self._port_callback)
                device.deactivate(self)
                self._port_callback_trigger.cancel()
                self._hold_timeout_trigger.cancel()
                self.step_stage()
        else:
            self.log('debug', 'Exit condition unmet, oldval={}, newval={}',
                     last_val, value)
            self._hold_timeout_trigger.cancel()
            self._start_hold_time = None

    def pause(self, *largs, **kwargs):
        if super(GateStage, self).pause(*largs, **kwargs):
            device = self.device
            if device is not None:
                device.unbind(on_data_update=self._port_callback)
                device.deactivate(self)
            self._port_callback_trigger.cancel()
            self._hold_timeout_trigger.cancel()
            return True
        return False

    def unpause(self, *largs, **kwargs):
        if super(GateStage, self).unpause(*largs, **kwargs):
            device = self.device
            if device is None:
                raise AttributeError(
                    'A device has not been assigned to stage {}'.format(self))
            self.last_state = None
            self._start_hold_time = None
            device.activate(self)
            device.bind(on_data_update=self._port_callback)
            self._port_callback_trigger()  # check the initial state
            return True
        return False

    def stop(self, *largs, **kwargs):
        if super(GateStage, self).stop(*largs, **kwargs):
            device = self.device
            if device is not None:
                device.unbind(on_data_update=self._port_callback)
                device.deactivate(self)
            self._port_callback_trigger.cancel()
            self._hold_timeout_trigger.cancel()
            return True
        return False

    def step_stage(self, *largs, **kwargs):
        device = self.device
        if device is None:
            raise AttributeError(
                'A device has not been assigned to stage {}'.format(self))

        if not super(GateStage, self).step_stage(*largs, **kwargs):
            return False

        self.last_state = None
        self._start_hold_time = None
        device.activate(self)
        device.bind(on_data_update=self._port_callback)
        self._port_callback_trigger()  # check the initial state
        return True

    def check_done(self, value, last_val):
        pass

    device = ObjectProperty(None, allownone=True)
    '''The input device.
    '''

    state_prop = StringProperty('state')
    ''' The name of the attr in device to bind.
    '''

    hold_time = BoundedNumericProperty(0, min=0)
    ''' How long the state must be held to finish.
    '''


class DigitalGateStage(GateStage):

    def check_done(self, value, last_val):
        return value == self.exit_state and (self.use_initial or
                                             last_val is not None)

    exit_state = BooleanProperty(False)
    '''The state the device has to be on in order to exit from this stage.
    '''

    use_initial = BooleanProperty(True)
    ''' Whether we can complete the stage if when entering, the channel is
    already at this exit_state.
    '''


class AnalogGateStage(GateStage):

    def check_done(self, value, last_val):
        return self.min <= value <= self.max

    max = NumericProperty(0)

    min = NumericProperty(0)

    range = ReferenceListProperty(min, max)
