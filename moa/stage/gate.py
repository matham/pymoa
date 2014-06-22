

__all__ = ('GateStage', )


from kivy.properties import (BooleanProperty, StringProperty,
    BoundedNumericProperty, ObjectProperty)
from kivy.clock import Clock
from time import clock
from moa.stage import MoaStage


class GateStage(MoaStage):

    _last_state = None
    _start_hold_time = None

    def _hold_timeout(self, *largs):
        t = self.hold_time
        elapsed = clock() - self._start_hold_time

        if t <= elapsed:
            device = self.device
            device.deactivate(self)
            device.unbind(**{self.state_attr: self._port_callback})
            self.step_stage()
        else:
            Clock.schedule_once(self._hold_timeout, t - elapsed)

    def _port_callback(self, instance, value):
        last_val = self._last_state
        self._last_state = value
        exit_state = self.exit_state
        if last_val == value:
            return

        if value == exit_state and (self.use_initial or
                                    last_val is not None):
            t = self.hold_time
            if t:
                self._start_hold_time = clock()
                Clock.schedule_once(self._hold_timeout, t)
            else:
                device = self.device
                device.deactivate(self)
                device.unbind(**{self.state_attr: self._port_callback})
                self.step_stage()
                return False
        else:
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
            self._last_state = None
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

        self._last_state = None
        device.activate(self)
        device.bind(**{self.state_attr: self._port_callback})
        return (self._port_callback(device, getattr(device, self.state_attr))
                is not False)

    device = ObjectProperty(None, allownone=True)
    '''The input device.
    '''

    state_attr = StringProperty('state')
    ''' The name of the attr in device to bind.
    '''

    exit_state = BooleanProperty(False)
    '''The state the device has to be on in order to exit from this stage.
    '''

    hold_time = BoundedNumericProperty(0, min=0)
    ''' How long the state must be held to finish.
    '''

    use_initial = BooleanProperty(True)
    ''' Whether we can complete the stage if when entering, the channel is
    already at this exit_state.
    '''
