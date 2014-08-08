

__all__ = ('GateStage', 'DigitalGateStage', 'AnalogGateStage')


from kivy.properties import (BooleanProperty, StringProperty,
    BoundedNumericProperty, ObjectProperty, NumericProperty,
    ReferenceListProperty)
from kivy.clock import Clock
from time import clock
from moa.stage import MoaStage


class GateStage(MoaStage):

    last_state = None
    ''' Gets reset to None before starting. Gets assigned the value after a
    check.
    '''
    _start_hold_time = None

    def _hold_timeout(self, *largs):
        t = self.hold_time
        elapsed = clock() - self._start_hold_time
        self.add_log(cause='_hold_timeout', vals=('hold_time', t, 'elapsed',
                                                  elapsed))

        if t <= elapsed:
            device = self.device
            device.deactivate(self)
            device.unbind(**{self.state_attr: self._port_callback})
            self.step_stage()
        else:
            Clock.schedule_once(self._hold_timeout, t - elapsed, priority=True)

    def _port_callback(self, instance, value):
        last_val = self.last_state
        self.last_state = value
        if last_val == value:
            return
        vals = ('last_state', last_val, 'new_state', value)

        if self.check_exit(value, last_val):
            t = self.hold_time
            if t:
                self.add_log(cause='_port_callback', vals=vals,
                             message='exit condition met - scheduling timeout')
                self._start_hold_time = clock()
                Clock.schedule_once(self._hold_timeout, t, priority=True)
            else:
                self.add_log(cause='_port_callback',
                             message='exit condition met', vals=vals)
                device = self.device
                device.deactivate(self)
                device.unbind(**{self.state_attr: self._port_callback})
                self.step_stage()
                return False
        else:
            self.add_log(cause='_port_callback',
                         message='exit state unmet', vals=vals)
            Clock.unschedule(self._hold_timeout)

    def pause(self, *largs, **kwargs):
        if super(GateStage, self).pause(*largs, **kwargs):
            device = self.device
            if device is not None:
                device.deactivate(self)
                device.unbind(**{self.state_attr: self._port_callback})
            Clock.unschedule(self._hold_timeout)
            return True
        return False

    def unpause(self, *largs, **kwargs):
        if super(GateStage, self).unpause(*largs, **kwargs):
            device = self.device
            if device is None:
                raise AttributeError('A device has not been assigned to this '
                                     'stage, {}'.format(self))
            self.last_state = None
            device.activate(self)
            device.bind(**{self.state_attr: self._port_callback})
            self._port_callback(device, getattr(device, self.state_attr))
            return True
        return False

    def stop(self, *largs, **kwargs):
        if super(GateStage, self).stop(*largs, **kwargs):
            device = self.device
            if device is not None:
                device.deactivate(self)
                device.unbind(**{self.state_attr: self._port_callback})
            Clock.unschedule(self._hold_timeout)
            return True
        return False

    def step_stage(self, *largs, **kwargs):
        device = self.device
        if device is None:
            raise AttributeError('A device has not been assigned to this '
                                 'stage, {}'.format(self))

        if not super(GateStage, self).step_stage(*largs, **kwargs):
            return False

        self.last_state = None
        device.activate(self)
        device.bind(**{self.state_attr: self._port_callback})
        return (self._port_callback(device, getattr(device, self.state_attr))
                is not False)

    def check_exit(self, value, last_val):
        pass

    device = ObjectProperty(None, allownone=True)
    '''The input device.
    '''

    state_attr = StringProperty('state')
    ''' The name of the attr in device to bind.
    '''

    hold_time = BoundedNumericProperty(0, min=0)
    ''' How long the state must be held to finish.
    '''


class DigitalGateStage(GateStage):

    def check_exit(self, value, last_val):
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

    def check_exit(self, value, last_val):
        return self.min <= value <= self.max

    max = NumericProperty(0)

    min = NumericProperty(0)

    range = ReferenceListProperty(min, max)
