'''Delay Stage
===============
'''

import random

from kivy.properties import (
    OptionProperty, BoundedNumericProperty, ReferenceListProperty)

from moa.stage import MoaStage
from kivy.clock import Clock

__all__ = ('Delay', )


class Delay(MoaStage):
    '''A stage that delays for :attr:`delay` seconds before the stage
    is automatically completed.
    '''

    _delay_step_trigger = None

    def __init__(self, **kwargs):
        super(Delay, self).__init__(**kwargs)
        self._delay_step_trigger = Clock.create_trigger_free(
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
    '''A 2-tuple of the minimum and maximum value used to generate
    :attr:`delay` when :attr:`delay_type` is `random`. The :attr:`delay`
    '''

    delay = BoundedNumericProperty(0.5, min=0.)
    '''How long the stage should delay for each trial. See :attr:`delay_type`.
    '''

    delay_type = OptionProperty('constant', options=['constant', 'random'])
    '''Whether the :attr:`delay` is a constant value provided by the user or if
    :attr:`delay` should be generated randomly for each trial from a linear
    :attr:`range`.

    If random, :attr:`delay` will automatically be updated with a new value
    before each trial.

    Possible values are ``'constant'`` and ``'random'``. Defaults to
    ``'constant'``.
    '''
