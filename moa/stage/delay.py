

__all__ = ('Delay', )

import random
from functools import partial
from kivy.clock import Clock
from kivy.properties import (BooleanProperty, NumericProperty, StringProperty,
    OptionProperty, BoundedNumericProperty, ReferenceListProperty,
    ObjectProperty)
from kivy.logger import Logger as logging
from moa.stage.base import MoaStage


class Delay(MoaStage):

    _increment_trigger = None

    def __init__(self, **kwargs):
        super(Delay, self).__init__(**kwargs)
        self._increment_func = lambda dt: self.increment_loop(source=self)
        self._increment_func.__name__ = '{},{}'.format(
            id(self._increment_func), id(self))

    # TODO: fix kivy dispatch to accept kwargs
    def on_stop(self, source=None, force=False, **kwargs):
        if super(Delay, self).on_stop(source=source, **kwargs):
            return True
        Clock.unschedule(self._increment_func)
        return False

    def increment_loop(self, source, **kwargs):
        if not super(Delay, self).increment_loop(source, **kwargs):
            return False

        if self.delay_type == 'random':
            self.value = random.uniform(self.min, self.max)
        Clock.schedule_once(self._increment_func, self.value)
        return True

    min = BoundedNumericProperty(0., min=0.)

    max = BoundedNumericProperty(1., min=0.)

    range = ReferenceListProperty(min, max)

    value = BoundedNumericProperty(0.5, min=0.)

    delay_type = OptionProperty('constant', options=['constant', 'random'])
