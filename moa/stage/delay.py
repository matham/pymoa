

__all__ = ('Delay', )

import random
import time

from kivy.properties import (OptionProperty, BoundedNumericProperty,
    ReferenceListProperty)

from moa.stage import MoaStage
from moa.clock import Clock


class Delay(MoaStage):

    __recovery_attrs__ = ('delay', )

    _delay_step_trigger = None

    def __init__(self, **kwargs):
        super(Delay, self).__init__(**kwargs)
        self._delay_step_trigger = Clock.create_trigger_priority(
            lambda dt: self.step_stage())

    def pause(self, *largs, **kwargs):
        if super(Delay, self).pause(*largs, **kwargs):
            self._delay_step_trigger.cancel()
            return True
        return False

    def unpause(self, *largs, **kwargs):
        if super(Delay, self).unpause(*largs, **kwargs):
            self._delay_step_trigger.timeout = max(
                0, self.delay - self.elapsed_time)
            self._delay_step_trigger()
            return True
        return False

    def stop(self, *largs, **kwargs):
        if super(Delay, self).stop(*largs, **kwargs):
            self._delay_step_trigger.cancel()
            return True
        return False

    def step_stage(self, *largs, **kwargs):
        if not super(Delay, self).step_stage(*largs, **kwargs):
            return False

        if self.delay_type == 'random':
            self.delay = random.uniform(self.min, self.max)

        self._delay_step_trigger.timeout = self.delay
        self._delay_step_trigger()
        return True

    min = BoundedNumericProperty(0., min=0.)

    max = BoundedNumericProperty(1., min=0.)

    range = ReferenceListProperty(min, max)

    delay = BoundedNumericProperty(0.5, min=0.)

    delay_type = OptionProperty('constant', options=['constant', 'random'])
