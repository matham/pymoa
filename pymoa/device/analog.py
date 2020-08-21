"""Analog Port
=================

Instances of :mod:`~pymoa.device.port` that represent analog input/output
devices.
"""

import random
import trio
import time
from typing import Dict

from kivy.properties import ObjectProperty

from pymoa.device.port import Channel, Port

__all__ = (
    'AnalogChannel', 'AnalogPort', 'RandomAnalogChannel', 'RandomAnalogPort')


class AnalogChannel(Channel):
    """A abstract single channel analog device.
    """

    _logged_names_hint_ = ('state', )

    state = ObjectProperty(None, allownone=True)
    '''The state of the channel.

    :attr:`state` is a :class:`~kivy.properties.NumericProperty` and
    defaults to None.
    '''

    async def write_state(self, value: float, **kwargs):
        '''A stub method defining the prototype for :meth:`write_state` of
        derived classes.

        :Parameters:

            `state`: float, int
                The value to set the state to.

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()


class AnalogPort(Port):
    """A abstract multi-channel analog device.
    """

    async def write_states(self, **kwargs: Dict[str, float]):
        '''A stub method defining the prototype for :meth:`write_state` of
        derived classes.

        For devices that support it, the properties passed in one call
        can be set to the requested state simultaneously.

        Method accepts property names and their values as keyword arguments,
        where each of the properties will be set to those values.

        E.g.::

            >>> port.write_state(voltage=1.6, amp=3.7)

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()

    async def write_state(self, channel: str, value: float, **kwargs):
        await self.write_states(**{channel: value})


class RandomAnalogChannel(AnalogChannel):
    """A channel that generates random analog values. Mainly useful as a
    testing device.
    """

    async def read_state(self):
        self.state = random.random()
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def write_state(self, state: float, **kwargs):
        self.state = state
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def pump_state(self, num_samples, delay=1.):
        for i in range(num_samples):
            if i:
                await trio.sleep(delay)
            await self.read_state()


class RandomAnalogPort(AnalogPort):
    """A port that generates random analog values. Mainly useful as a
    testing device.
    """

    async def read_state(self):
        for name in self.channel_names:
            setattr(self, name, random.random())
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def write_states(self, **kwargs: Dict[str, float]):
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.timestamp = time.perf_counter()
        self.dispatch('on_data_update', self)

    async def pump_state(self, num_samples, delay=1.):
        for i in range(num_samples):
            if i:
                await trio.sleep(delay)
            await self.read_state()
