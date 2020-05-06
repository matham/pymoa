from typing import AsyncGenerator, Tuple
import uuid
from asks import Session
from asks.errors import BadStatus
import time
import trio

from pymoa.executor.remote.rest import SSEStream
from pymoa.executor.remote import RemoteExecutor, RemoteReferencable
from pymoa.executor import NO_CALLBACK

__all__ = ('RestExecutor', )


def raise_for_status(response):
    """
    Raise BadStatus if one occurred.
    """
    if 400 <= response.status_code < 500:
        raise BadStatus(
            '{} Client Error: {} for url: {}'.format(
                response.status_code, response.reason_phrase, response.url
            ),
            response,
            response.status_code
        )
    elif 500 <= response.status_code < 600:
        raise BadStatus(
            '{} Server Error: {} for url: {}'.format(
                response.status_code, response.reason_phrase, response.url
            ),
            response,
            response.status_code
        )


class RestExecutor(RemoteExecutor):

    session: Session = None

    uri: str = ''

    limiter: trio.CapacityLimiter = None

    def __init__(self, uri: str, connections: int = 1, **kwargs):
        super(RestExecutor, self).__init__(**kwargs)
        if uri.endswith('/'):
            uri = uri[:-1]
        self.uri = uri
        self.session = Session(connections=connections)
        self._uuid = uuid.uuid4().bytes

    async def ensure_remote_instance(
            self, obj: 'RemoteReferencable', *args, **kwargs):
        data = self._get_ensure_remote_instance_data(obj, args, kwargs)
        data = self.encode(data)

        self.registry.add_instance(obj)
        uri = f'{self.uri}/api/v1/objects/create_open'
        response = await self.session.post(
            uri, data=data, headers={'Content-Type': 'application/json'})
        response.raise_for_status()

    async def delete_remote_instance(self, obj: 'RemoteReferencable'):
        data = self._get_delete_remote_instance_data(obj)
        data = self.encode(data)

        uri = f'{self.uri}/api/v1/objects/delete'
        response = await self.session.post(
            uri, data=data, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        self.registry.delete_instance(obj)

    async def start_executor(self):
        self.limiter = trio.CapacityLimiter(1)

    async def stop_executor(self, block=True):
        self.limiter = None

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        data = self._get_execute_data(obj, sync_fn, args, kwargs, callback)
        data = self.encode(data)

        uri = f'{self.uri}/api/v1/objects/execute'
        async with self.limiter:
            response = await self.session.post(
                uri, data=data, headers={'Content-Type': 'application/json'})
            response.raise_for_status()

            res = self.decode(response.text)
            if callback is not NO_CALLBACK:
                self.call_execute_callback(obj, res, callback)
        return res

    async def get_remote_object_info(self, obj, query):
        """

        :param obj:
        :param query: Can be one of config or data.
        :return:
        """
        data = self._get_remote_object_info_data(obj, query)
        data = self.encode(data)

        uri = f'{self.uri}/api/v1/objects/object'
        response = await self.session.get(
            uri, data=data, headers={'Content-Type': 'application/json'})
        response.raise_for_status()

        return self.decode(response.text)

    async def get_remote_objects(self):
        return await self.get_remote_object_info(None, 'config')

    async def apply_config_from_remote(self, obj):
        config = await self.get_remote_object_info(obj, 'config')
        self._apply_config_from_remote(obj, config)

    async def generate_sse_events(self, response):
        last_packet = None
        async for _, data, id_, _ in SSEStream.stream(response):
            data = self.decode(data)
            if data == 'alive':
                continue

            packet, data_channel = self.decode(id_)
            if last_packet is not None and last_packet + 1 != packet:
                raise ValueError(
                    f'Packets were skipped {last_packet} -> {packet}')
            last_packet = packet

            yield data

    async def apply_data_from_remote(self, obj):
        params = {'channel': f'{obj.hash_val}.data'}
        uri = f'{self.uri}/api/v1/stream'
        response = await self.session.get(uri, params=params, stream=True)
        raise_for_status(response)

        await self._apply_data_from_remote(
            obj, self.generate_sse_events(response))

    async def get_data_from_remote(self, obj) -> AsyncGenerator:
        params = {'channel': f'{obj.hash_val}.data'}
        uri = f'{self.uri}/api/v1/stream'
        response = await self.session.get(uri, params=params, stream=True)
        raise_for_status(response)

        return self.generate_sse_events(response)

    async def apply_execute_from_remote(self, obj, exclude_self=True):
        params = {'channel': f'{obj.hash_val}.execute'}
        uri = f'{self.uri}/api/v1/stream'
        response = await self.session.get(uri, params=params, stream=True)
        raise_for_status(response)

        await self._apply_execute_from_remote(
            obj, self.generate_sse_events(response), exclude_self)

    async def get_execute_from_remote(self, obj) -> AsyncGenerator:
        params = {'channel': f'{obj.hash_val}.execute'}
        uri = f'{self.uri}/api/v1/stream'
        response = await self.session.get(uri, params=params, stream=True)
        raise_for_status(response)

        return self.generate_sse_events(response)

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        start_time = time.perf_counter_ns()
        data = await self._get_clock_data()
        data = self.encode(data)

        uri = f'{self.uri}/api/v1/echo_clock'
        response = await self.session.get(
            uri, data=data, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        server_time = self.decode(response.text)['server_time']

        return start_time, server_time, time.perf_counter_ns()
