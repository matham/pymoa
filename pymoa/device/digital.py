"""Digital Port
=================

Instances of :mod:`~pymoa.device.port` that represent Digital devices.
"""

import random
import trio
import time
from typing import Optional, Iterable, Dict

from pymoa.device.port import Channel, Port

__all__ = (
    'DigitalChannel', 'DigitalPort', 'RandomDigitalChannel',
    'RandomDigitalPort')


class DigitalChannel(Channel):
    """A abstract single channel digital device.
    """

    state: Optional[bool] = None
    '''The state of the channel.

    :attr:`state` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to None.
    '''

    async def write_state(self, state: bool, **kwargs):
        """A stub method defining the prototype for :meth:`write_state` of
        derived classes.

        :Parameters:

            `state`: bool
                The value to set the state to.

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        """
        raise NotImplementedError()


class DigitalPort(Port):
    """A abstract multi-channel digital device.
    """

    async def write_states(
            self, high: Iterable[str] = (), low: Iterable[str] = (), **kwargs):
        """A stub method defining the prototype for :meth:`write_state` of
        derived classes.

        For devices that support it, the properties passed in `high` and `low`
        can be set to the requested state simultaneously.

        :Parameters:

            `high`: list
                A list of the names of the properties to set to high (True)
            `low`: list
                A list of the names of the properties to set to low (False)

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        """
        raise NotImplementedError()

    async def write_state(self, channel: str, state: bool, **kwargs):
        if state:
            await self.write_states(high=[channel])
        else:
            await self.write_states(low=[channel])


class RandomDigitalChannel(DigitalChannel):
    """A channel that generates random digital values. Mainly useful as a
    testing device.
    """

    async def read_state(self):
        self.state = random.random() >= 0.5
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def write_state(self, state: bool, **kwargs):
        self.state = state
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def pump_state(self, num_samples, delay=1.):
        for i in range(num_samples):
            if i:
                await trio.sleep(delay)
            await self.read_state()


class RandomDigitalPort(DigitalPort):
    """A port that generates random digital values. Mainly useful as a
    testing device.
    """

    async def read_state(self):
        for name in self.channel_names:
            setattr(self, name, random.random() >= 0.5)
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def write_states(self, **kwargs: Dict[str, bool]):
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def pump_state(self, num_samples, delay=1.):
        for i in range(num_samples):
            if i:
                await trio.sleep(delay)
            await self.read_state()
