"""Multiprocessing Socket Client
=================================

"""
from trio import socket
import sys
import subprocess

from pymoa.executor.remote.socket.client import SocketExecutor

__all__ = ('MultiprocessSocketExecutor', )


class MultiprocessSocketExecutor(SocketExecutor):
    """Executor that sends all requests to a remote server to be executed
    there, using a websocket.
    """

    server: str = ''

    port: int = None

    def __init__(self, server: str = '', port: int = 0, **kwargs):
        super(MultiprocessSocketExecutor, self).__init__(**kwargs)
        self.server = server
        self.port = port

    async def decode(self, data):
        raise NotImplementedError

    async def start_executor(self):
        port = self.port
        if not port:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            await s.bind(("", 0))
            s.listen(1)
            port = self.port = s.getsockname()[1]
            await s.aclose()

        subprocess.Popen(
            [sys.executable, '-m', 'pymoa.executor.remote.app.multiprocessing',
             '--port', str(port)])
        await super(MultiprocessSocketExecutor, self).start_executor()

    async def stop_executor(self, block=True):
        await super(MultiprocessSocketExecutor, self).stop_executor(
            block=block)

        data = self.encode({'channel': None, 'eof': True})
        async with self.create_socket_context() as sock:
            await self.write_socket(data, sock)
