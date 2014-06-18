

__all__ = ('DigitalPortStage', )


from kivy.properties import (BooleanProperty, StringProperty,
    BoundedNumericProperty, ObjectProperty, OptionProperty)
from kivy.clock import Clock
from moa.stage.base import MoaStage
from moa.device.gate import InputChannel, OutputChannel


class DigitalPortStage(MoaStage):

    __last_device = None
    __last_state = None
    __scheduled = False
    __request_event = None

    def on_stop(self, **kwargs):
        if super(DigitalPortStage, self).on_stop(**kwargs):
            return True

        device = self.__last_device
        if device is not None:
            device.remove_request(name=('set_state' if isinstance(device,
            OutputChannel) else 'get_state'), callback_id=self.__request_event)
            self.__last_device = None
        if self.__scheduled:
            Clock.unschedule(self._hold_timeout)
            self.__scheduled = False
        return False

    def _hold_timeout(self, dt):
        t = self.hold_time
        if t <= dt:
            self.__scheduled = False
            device = self.__last_device
            device.remove_request(name=('set_state' if isinstance(device,
            OutputChannel) else 'get_state'), callback_id=self.__request_event)
            self.__last_device = None
            self.increment_loop()
        else:
            Clock.schedule_once(self._hold_timeout, t - dt)

    def _port_callback(self, value, **kwargs):
        last_val = self.__last_state
        self.__last_state = value
        exit_state = self.exit_state
        done = False
        if last_val == value:
            return

        if self.__scheduled:
            Clock.unschedule(self._hold_timeout)
            self.__scheduled = False

        if value == exit_state and (self.use_initial or last_val is not None):
            t = self.hold_time
            if t:
                Clock.schedule_once(self._hold_timeout, t)
                self.__scheduled = True
            else:
                done = True

        if done:
            self._hold_timeout(0)

    def increment_loop(self, **kwargs):
        if not super(DigitalPortStage, self).increment_loop(**kwargs):
            return False

        self.__last_device = device = self.device
        if device is None:
            raise AttributeError('A device has not been assigned to this '
                                 'stage, {}'.format(self))

        if isinstance(device, InputChannel):
            name = 'get_state'
            trigger = True
        else:
            name = 'set_state'
            trigger = False
        self.__last_state = None

        self.__request_event = device.request_callback(name=name,
            callback=self._port_callback, trigger=trigger, repeat=True)
        return True

    device = ObjectProperty(None, allownone=True,
                            basesbaseclass=(InputChannel, OutputChannel))
    '''The input device.
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
