

__all__ = ('Delay', )

import random
import time
from kivy.clock import Clock
from kivy.properties import (OptionProperty, BoundedNumericProperty,
    ReferenceListProperty)
from moa.stage import MoaStage


class Delay(MoaStage):

    def pause(self, *largs, **kwargs):
        if super(Delay, self).pause(*largs, **kwargs):
            self.delay = max(0, self.delay - (time.clock() - self.start_time))
            Clock.unschedule(self.step_stage)
            return True
        return False

    def unpause(self, *largs, **kwargs):
        if super(Delay, self).unpause(*largs, **kwargs):
            Clock.schedule_once(self.step_stage, self.delay)
            return True
        return False

    def stop(self, *largs, **kwargs):
        if super(Delay, self).stop(*largs, **kwargs):
            Clock.unschedule(self.step_stage)
            return True
        return False

    def step_stage(self, *largs, **kwargs):
        if not super(Delay, self).step_stage(*largs, **kwargs):
            return False

        if self.delay_type == 'random':
            self.delay = random.uniform(self.min, self.max)
        Clock.schedule_once(self.step_stage, self.delay)
        return True

    min = BoundedNumericProperty(0., min=0.)

    max = BoundedNumericProperty(1., min=0.)

    range = ReferenceListProperty(min, max)

    delay = BoundedNumericProperty(0.5, min=0.)

    delay_type = OptionProperty('constant', options=['constant', 'random'])
