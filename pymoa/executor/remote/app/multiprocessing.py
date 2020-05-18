"""Multiprocessing app
======================

"""

# todo: immediately close connection for sse/stream if full
from collections import defaultdict
from async_generator import aclosing
from itertools import chain
import argparse
import trio
from trio import socket, SocketStream, SocketListener, serve_listeners

from pymoa.utils import MaxSizeSkipDeque
from pymoa.executor.remote.socket.server import SocketServer

import pymoa.executor.remote.referable_class_register

__all__ = ('run_app', 'ProcessSocketServer')

MAX_QUEUE_SIZE = 20


class ProcessSocketServer(SocketServer):
    """Quart server side socket handler.
    """

    max_buffer = MAX_QUEUE_SIZE

    stream_clients = {}

    def __init__(self, **kwargs):
        super(ProcessSocketServer, self).__init__(**kwargs)
        self.stream_clients = defaultdict(dict)

    async def decode(self, data):
        raise NotImplementedError

    def post_stream_channel(self, data, channel_type, hash_val):
        stream_clients = self.stream_clients
        channel = f'{hash_val}.{channel_type}'

        queues = stream_clients[channel] if channel in stream_clients else {}
        queues2 = stream_clients[channel_type] \
            if channel_type in stream_clients else {}
        queues3 = stream_clients[hash_val] \
            if hash_val in stream_clients else {}
        queues4 = stream_clients[''] if '' in stream_clients else {}

        sse_queues = list(chain(
            queues.values(), queues2.values(), queues3.values(),
            queues4.values()))

        if sse_queues:
            queue: MaxSizeSkipDeque
            for queue in sse_queues:
                queue.add_item((data, channel_type, hash_val, channel), 1)

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


async def socket_handler(executor: ProcessSocketServer, stream: SocketStream):
    await executor.write_socket(executor.encode({'data': 'hello'}), stream)

    while True:
        msg = await executor.read_decode_json_buffers(stream)
        cmd = msg['cmd']
        packet = msg['packet']
        data = msg['data']

        ret_data = {
            'cmd': cmd,
            'packet': packet,
        }

        if cmd == 'ensure_remote_instance':
            res = await executor.ensure_instance(data)
        elif cmd == 'delete_remote_instance':
            res = await executor.delete_instance(data)
        elif cmd == 'execute':
            res = await executor.execute(data)
        elif cmd == 'execute_generator':
            ret_data['done_execute'] = False
            async with aclosing(executor.execute_generator(data)) as aiter:
                async for item in aiter:
                    ret_data['data'] = item
                    await executor.write_socket(
                        executor.encode(ret_data), stream)

            res = None
            ret_data['done_execute'] = True
        elif cmd == 'get_remote_object_info':
            res = await executor.get_object_info(data)
        elif cmd == 'get_echo_clock':
            res = await executor.get_echo_clock(data)
        else:
            raise Exception(f'Unknown command "{cmd}"')

        ret_data['data'] = res
        await executor.write_socket(executor.encode(ret_data), stream)


async def socket_stream_handler(
        executor: ProcessSocketServer, stream: SocketStream, channel):
    await executor.write_socket(executor.encode({'data': 'hello'}), stream)

    queue = MaxSizeSkipDeque(max_size=executor.max_buffer)
    key = object()
    executor.stream_clients[channel][key] = queue

    while True:
        try:
            async for (data, channel_type, hash_val, data_channel), \
                    packet in queue:
                msg_data = {
                    'data': data,
                    'packet': packet,
                    'channel_type': channel_type,
                    'hash_val': hash_val,
                    'channel': data_channel,
                }
                await executor.write_socket(executor.encode(msg_data), stream)
        finally:
            del executor.stream_clients[channel][key]
            if not executor.stream_clients[channel]:
                del executor.stream_clients[channel]


async def serve(host, port):
    # todo: catch and send back errors
    executor = ProcessSocketServer()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (host, port)
    await sock.bind(server_address)
    sock.listen()

    async def handler(stream: SocketStream):
        data = await executor.read_decode_json_buffers(stream)
        if data.get('eof', False):
            nursery.cancel_scope.cancel()
            return

        channel = data['channel']

        if channel is None:
            await socket_handler(executor, stream)
        else:
            await socket_stream_handler(executor, stream, channel)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(serve_listeners, handler, [SocketListener(sock)])


def run_app():
    parser = argparse.ArgumentParser(description='PyMoa process server.')
    parser.add_argument(
        '--host', dest='host', action='store', default="127.0.0.1")
    parser.add_argument(
        '--port', dest='port', action='store', default=5000, type=int)
    args = parser.parse_args()

    trio.run(serve, args.host, args.port)


if __name__ == '__main__':
    run_app()
