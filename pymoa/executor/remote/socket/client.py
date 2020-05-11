"""Socket Client
================

"""
from typing import AsyncGenerator, Tuple
import time
from async_generator import aclosing
import contextlib
from trio import socket, SocketStream, TASK_STATUS_IGNORED, open_tcp_stream

from pymoa.executor.remote import RemoteExecutor, RemoteReferenceable
from pymoa.executor import NO_CALLBACK

__all__ = ('SocketExecutor', )


class SocketExecutor(RemoteExecutor):
    """Executor that sends all requests to a remote server to be executed
    there, using a socket.
    """

    server: str = ''

    port: int = None

    socket: SocketStream = None

    _packet: int = 0

    def __init__(self, server: str = '', port: int = 0, **kwargs):
        super(SocketExecutor, self).__init__(**kwargs)
        self.server = server
        self.port = port

    def create_socket_context(self):
        return open_tcp_stream(self.server, self.port)

    async def open_socket(self) -> SocketStream:
        data = self.encode({'channel': None})

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (self.server, self.port)
        await sock.connect(server_address)

        stream = SocketStream(sock)
        try:
            await self.write_socket(data, stream)
            await self.read_decode_json_buffers(stream)
        except Exception:
            await stream.aclose()
            raise

        return stream

    def encode(self, data):
        return self.registry.encode_json_buffers(data)

    async def decode(self, data):
        raise NotImplementedError

    async def write_socket(self, data: bytes, sock: SocketStream):
        await sock.send_all(data)

    async def read_decode_json_buffers(self, stream: SocketStream):
        header = b''
        while len(header) < 4 * 4:
            header += await stream.receive_some(16 - len(header))

        msg_len, json_bytes, num_buffers = \
            self.registry.decode_json_buffers_header(header)

        data = []
        n = 0
        while n < msg_len:
            buff = await stream.receive_some(msg_len - n)
            data.append(buff)
            n += len(buff)

        if len(data) == 1:
            data = data[0]
        else:
            data = b''.join(data)

        return self.registry.decode_json_buffers(data, json_bytes, num_buffers)

    def raise_return_value(self, data: dict, packet: int = None):
        if packet is not None:
            packet_ = data['packet']
            if packet_ != packet:
                raise ValueError(
                    f"Packet mismatch when reading: {packet} is not {packet_}")

    async def ensure_remote_instance(
            self, obj: 'RemoteReferenceable', *args, **kwargs):
        packet = self._packet
        self._packet += 1
        data = {
            'data': self._get_ensure_remote_instance_data(obj, args, kwargs),
            'cmd': 'ensure_remote_instance',
            'packet': packet,
        }
        data = self.encode(data)

        self.registry.add_instance(obj)

        await self.write_socket(data, self.socket)
        res = await self.read_decode_json_buffers(self.socket)
        self.raise_return_value(res, packet)

    async def delete_remote_instance(self, obj: 'RemoteReferenceable'):
        packet = self._packet
        self._packet += 1
        data = {
            'data': self._get_delete_remote_instance_data(obj),
            'cmd': 'delete_remote_instance',
            'packet': packet,
        }
        data = self.encode(data)

        await self.write_socket(data, self.socket)
        res = await self.read_decode_json_buffers(self.socket)
        self.raise_return_value(res, packet)

        self.registry.delete_instance(obj)

    async def start_executor(self):
        self.socket = await self.open_socket()

    async def stop_executor(self, block=True):
        if self.socket is not None:
            await self.socket.aclose()
            self.socket = None

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        packet = self._packet
        self._packet += 1
        data = {
            'data': self._get_execute_data(
                obj, sync_fn, args, kwargs, callback),
            'cmd': 'execute',
            'packet': packet,
        }
        data = self.encode(data)

        await self.write_socket(data, self.socket)
        res = await self.read_decode_json_buffers(self.socket)
        self.raise_return_value(res, packet)

        ret_val = res['data']
        if callback is not NO_CALLBACK:
            self.call_execute_callback(obj, ret_val, callback)
        return ret_val

    async def get_remote_object_info(self, obj, query):
        """

        :param obj:
        :param query: Can be one of config or data.
        :return:
        """
        packet = self._packet
        self._packet += 1
        data = {
            'data': self._get_remote_object_info_data(obj, query),
            'cmd': 'get_remote_object_info',
            'packet': packet,
        }
        data = self.encode(data)

        await self.write_socket(data, self.socket)
        res = await self.read_decode_json_buffers(self.socket)
        self.raise_return_value(res, packet)

        return res['data']

    async def get_remote_objects(self):
        return await self.get_remote_object_info(None, 'config')

    async def apply_config_from_remote(self, obj):
        config = await self.get_remote_object_info(obj, 'config')
        self._apply_config_from_remote(obj, config)

    async def generate_stream_events(self, channel, task_status):
        read = self.read_decode_json_buffers
        data = self.encode({'channel': channel})

        async with self.create_socket_context() as stream:
            await self.write_socket(data, stream)
            await read(stream)
            task_status.started()

            last_packet = None
            while True:
                res = await read(stream)
                data = res['data']

                packet = res['packet']
                if last_packet is not None and last_packet + 1 != packet:
                    raise ValueError(
                        f'Packets were skipped {last_packet} -> {packet}')
                last_packet = packet

                yield data

    async def apply_data_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED):
        await self._apply_data_from_remote(
            obj,
            aclosing(self.generate_stream_events(
                f'{obj.hash_val}.data', task_status)))

    @contextlib.asynccontextmanager
    async def get_data_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED) -> AsyncGenerator:
        async with aclosing(self.generate_stream_events(
                f'{obj.hash_val}.data', task_status)) as aiter:
            yield aiter

    async def apply_execute_from_remote(
            self, obj, exclude_self=True, task_status=TASK_STATUS_IGNORED):
        await self._apply_execute_from_remote(
            obj, aclosing(self.generate_stream_events(
                f'{obj.hash_val}.execute', task_status)),
            exclude_self)

    @contextlib.asynccontextmanager
    async def get_execute_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED) -> AsyncGenerator:
        async with aclosing(self.generate_stream_events(
                f'{obj.hash_val}.execute', task_status)) as aiter:
            yield aiter

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        packet = self._packet
        self._packet += 1
        data = {
            'data': self._get_clock_data(),
            'cmd': 'get_echo_clock',
            'packet': packet,
        }
        data = self.encode(data)

        start_time = time.perf_counter_ns()
        await self.write_socket(data, self.socket)
        res = await self.read_decode_json_buffers(self.socket)
        self.raise_return_value(res, packet)

        return start_time, res['data']['server_time'], time.perf_counter_ns()
