"""Digital Port
=================

Instances of :mod:`~pymoa.device.port` that represent Digital devices.
"""

import random
import trio
import time
from typing import Optional, Iterable, Dict

from kivy.properties import ObjectProperty

from pymoa.device.port import Channel, Port
from pymoa.executor import apply_executor

__all__ = (
    'DigitalChannel', 'DigitalPort', 'RandomDigitalChannel',
    'RandomDigitalPort')


class DigitalChannel(Channel):
    """A abstract single channel digital device.
    """

    _logged_names_ = ('state', )

    state: Optional[bool] = ObjectProperty(None, allownone=True)
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

    def executor_callback(self, return_value):
        self.state, self.timestamp = return_value
        self.dispatch('on_data_update', self)

    @apply_executor(callback=executor_callback)
    def get_state_value(self):
        return random.random() >= 0.5, time.perf_counter()

    @apply_executor(callback=executor_callback)
    def set_state_value(self, state):
        return state, time.perf_counter()

    async def read_state(self):
        await self.get_state_value()

    async def write_state(self, state: bool, **kwargs):
        await self.set_state_value(state)

    async def pump_state(self):
        while True:
            await self.get_state_value()
            await trio.sleep(.2)


class RandomDigitalPort(DigitalPort):

    _logged_names_ = ('chan0', 'chan1')

    channel_names = ['chan0', 'chan1']

    chan0: bool = ObjectProperty(None, allownone=True)

    chan1: bool = ObjectProperty(None, allownone=True)

    def executor_callback(self, return_value):
        values, self.timestamp = return_value
        for name, value in zip(self.channel_names, values):
            setattr(self, name, value)
        self.dispatch('on_data_update', self)

    @apply_executor(callback=executor_callback)
    def get_channels_value(self):
        return [random.random() >= 0.5 for _ in self.channel_names], \
               time.perf_counter()

    @apply_executor(callback=executor_callback)
    def set_channels_value(self, values):
        return values, time.perf_counter()

    async def read_state(self):
        await self.get_channels_value()

    async def write_states(self, **kwargs: Dict[str, bool]):
        await self.set_channels_value(kwargs)

    async def pump_state(self):
        while True:
            await self.get_channels_value()
            await trio.sleep(.2)
