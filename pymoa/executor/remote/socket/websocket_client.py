"""Websocket Client
===================

"""
from trio_websocket import connect_websocket_url, WebSocketConnection
from trio import Nursery

from pymoa.executor.remote.socket.client import SocketExecutor

__all__ = ('WebSocketExecutor', )


class WebSocketExecutor(SocketExecutor):
    """Executor that sends all requests to a remote server to be executed
    there, using a websocket.
    """

    socket: WebSocketConnection = None

    nursery: Nursery = None

    def __init__(self, nursery: Nursery, **kwargs):
        super(WebSocketExecutor, self).__init__(**kwargs)
        self.nursery = nursery

    async def open_socket(self, channel) -> WebSocketConnection:
        data = self.encode({'channel': channel})
        url = f'ws://{self.server}:{self.port}/api/v1/ws'
        socket = await connect_websocket_url(self.nursery, url)

        try:
            await self.write_socket(data, socket)
            await self.read_decode_json_buffers(socket)
        except Exception:
            await socket.aclose()
            raise

        return socket

    async def decode(self, data):
        raise NotImplementedError

    async def write_socket(self, data: bytes, stream: WebSocketConnection):
        await stream.send_message(data)

    async def read_decode_json_buffers(self, stream: WebSocketConnection):
        data = await stream.get_message()

        if len(data) < 16:
            raise ValueError('Unable to parse message headers')

        msg_len, json_bytes, num_buffers = \
            self.registry.decode_json_buffers_header(data[:16])

        data = data[16:]
        if len(data) != msg_len:
            raise ValueError('Unable to parse message data')

        return self.registry.decode_json_buffers(data, json_bytes, num_buffers)
