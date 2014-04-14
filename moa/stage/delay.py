

__all__ = ('Delay', )

import random
import time
from kivy.clock import Clock
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty)
from moa.stage.base import MoaStage


class Delay(MoaStage):

    def on_paused(self, instance, value, **kwargs):
        super(Delay, self).on_paused(instance, value, **kwargs)

        if self.disabled or not self.started or self.finished:
            return

        if value:
            self.delay = max(0, self.delay - (time.clock() - self.start_time))
            Clock.unschedule(self.increment_loop)
        else:
            Clock.schedule_once(self.increment_loop, self.delay)

    def on_stop(self, **kwargs):
        if super(Delay, self).on_stop(**kwargs):
            return True
        Clock.unschedule(self.increment_loop)
        return False

    def increment_loop(self, *largs, **kwargs):
        if not super(Delay, self).increment_loop(**kwargs):
            return False

        if self.delay_type == 'random':
            self.delay = random.uniform(self.min, self.max)
        Clock.schedule_once(self.increment_loop, self.delay)
        return True

    min = BoundedNumericProperty(0., min=0.)

    max = BoundedNumericProperty(1., min=0.)

    range = ReferenceListProperty(min, max)

    delay = BoundedNumericProperty(0.5, min=0.)

    delay_type = OptionProperty('constant', options=['constant', 'random'])
