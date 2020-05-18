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
from pymoa.executor import apply_executor, apply_generator_executor

__all__ = (
    'AnalogChannel', 'AnalogPort', 'RandomAnalogChannel', 'RandomAnalogPort')


class AnalogChannel(Channel):
    """A abstract single channel analog device.
    """

    _logged_names_ = ('state', )

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

    def executor_callback(self, return_value):
        self.state, self.timestamp = return_value
        self.dispatch('on_data_update', self)

    @apply_executor(callback=executor_callback)
    def get_state_value(self):
        return random.random(), time.perf_counter()

    @apply_executor(callback=executor_callback)
    def set_state_value(self, state):
        return state, time.perf_counter()

    async def read_state(self):
        await self.get_state_value()

    async def write_state(self, state: float, **kwargs):
        await self.set_state_value(state)

    @apply_generator_executor(callback=executor_callback)
    def generate_data(self, num_samples):
        for _ in range(num_samples):
            yield random.random(), time.perf_counter()

    async def pump_state(self, num_samples):
        async with self.generate_data(num_samples) as aiter:
            async for item in aiter:
                pass


class RandomAnalogPort(AnalogPort):
    """A port that generates random analog values. Mainly useful as a
    testing device.
    """

    _logged_names_ = ('chan0', 'chan1')

    channel_names = ['chan0', 'chan1']

    chan0: float = ObjectProperty(None, allownone=True)

    chan1: float = ObjectProperty(None, allownone=True)

    def executor_callback(self, return_value):
        values, self.timestamp = return_value
        for name, value in zip(self.channel_names, values):
            setattr(self, name, value)
        self.dispatch('on_data_update', self)

    @apply_executor(callback=executor_callback)
    def get_channels_value(self):
        return [random.random() for _ in self.channel_names], \
               time.perf_counter()

    @apply_executor(callback=executor_callback)
    def set_channels_value(self, values):
        return values, time.perf_counter()

    async def read_state(self):
        await self.get_channels_value()

    async def write_states(self, **kwargs: Dict[str, float]):
        await self.set_channels_value(kwargs)

    @apply_generator_executor(callback=executor_callback)
    def generate_data(self, num_samples):
        for _ in range(num_samples):
            yield [random.random() for _ in self.channel_names], \
                time.perf_counter()

    async def pump_state(self, num_samples):
        async with self.generate_data(num_samples) as aiter:
            async for item in aiter:
                pass
