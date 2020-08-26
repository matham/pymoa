"""Delay Stage
===============
"""
import random

from pymoa.stage import MoaStage
import trio

__all__ = ('Delay', 'UniformRandomDelay', 'GaussianRandomDelay')


class Delay(MoaStage):
    """A stage that delays for :attr:`delay` seconds before the stage
    is automatically completed.
    """

    _config_props_ = ('delay', )

    def __init__(self, delay=0.5, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay

    async def do_trial(self):
        await trio.sleep(self.delay)

    delay: float = 0.5
    '''How long the stage should delay for each trial.
    '''


class UniformRandomDelay(Delay):
    """Stage that waits for a uniform random delay.
    """

    _config_props_ = ('min', 'max')

    def __init__(self, min=0., max=1., **kwargs):
        super().__init__(**kwargs)
        self.min = min
        self.max = max

    async def init_trial(self, i: int):
        self.delay = random.uniform(self.min, self.max)
        await super().init_trial(i)

    min: float = 0.

    max: float = 1.


class GaussianRandomDelay(Delay):
    """Stage that waits for a Gaussian random delay.
    """

    _config_props_ = ('mu', 'sigma')

    def __init__(self, mu=1., sigma=1., **kwargs):
        super().__init__(**kwargs)
        self.mu = mu
        self.sigma = sigma

    async def init_trial(self, i: int):
        self.delay = max(0., random.gauss(self.mu, self.sigma))
        await super().init_trial(i)

    mu: float = 1.

    sigma: float = 1.
