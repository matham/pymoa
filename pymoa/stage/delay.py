"""Delay Stage
===============
"""
from typing import Tuple
import random

from kivy.properties import (
    OptionProperty, BoundedNumericProperty, ReferenceListProperty)

from pymoa.stage import MoaStage
import trio

__all__ = ('Delay', 'UniformRandomDelay', 'GaussianRandomDelay')


class Delay(MoaStage):
    """A stage that delays for :attr:`delay` seconds before the stage
    is automatically completed.
    """

    async def do_trial(self):
        await trio.sleep(self.delay)

    delay: float = BoundedNumericProperty(0.5, min=0.)
    '''How long the stage should delay for each trial.
    '''


class UniformRandomDelay(Delay):
    """Stage that waits for a uniform random delay.
    """

    async def do_trial(self):
        self.delay = random.uniform(self.min, self.max)
        await super(UniformRandomDelay, self).do_trial()

    min: float = BoundedNumericProperty(0., min=0.)

    max: float = BoundedNumericProperty(1., min=0.)

    range: Tuple[float, float] = ReferenceListProperty(min, max)
    '''A 2-tuple of the minimum and maximum value used to generate
    :attr:`delay` when :attr:`delay_type` is `random`. The :attr:`delay`
    '''


class GaussianRandomDelay(Delay):
    """Stage that waits for a Gaussian random delay.
    """

    async def do_trial(self):
        self.delay = max(0, random.gauss(self.mu, self.sigma))
        await super(GaussianRandomDelay, self).do_trial()

    mu: float = BoundedNumericProperty(1., min=0.)

    sigma: float = BoundedNumericProperty(1., min=0.)
