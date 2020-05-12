"""Server
=========

"""
from async_generator import aclosing
from pymoa.executor.remote import RemoteExecutorServer, RemoteDataLogger

__all__ = ('RestServer', 'SSELogger')


class RestServer(RemoteExecutorServer):
    """Rest server side class to handle incoming executor requests.
    """

    stream_objects = True

    stream_data_logs = True

    def __init__(self, stream_objects=True, stream_data_logs=True, **kwargs):
        super(RestServer, self).__init__(**kwargs)

        self.stream_objects = stream_objects
        self.stream_data_logs = stream_data_logs

        if self.stream_data_logs:
            self.stream_data_logger = SSELogger(
                sse_post_callback=self.post_sse_channel)

    async def ensure_instance(self, data: str) -> None:
        registry = self.registry
        data = self.decode(data)
        hash_val = data['hash_val']

        if hash_val in registry.hashed_instances:
            return

        obj, data = await self._create_instance(data)

        if self.stream_objects:
            self.post_sse_channel(data, 'ensure', hash_val)

    async def delete_instance(self, data: str) -> None:
        data = self.decode(data)
        hash_val = data['hash_val']

        obj, data = await self._delete_instance(data)

        if self.stream_objects:
            self.post_sse_channel(data, 'delete', hash_val)

    async def execute(self, data: str) -> str:
        data = self.decode(data)
        hash_val = data['hash_val']

        res, data = await self._execute(data)

        if self.stream_objects:
            self.post_sse_channel(data, 'execute', hash_val)

        return self.encode(res)

    async def execute_generator(self, data: str):
        data = self.decode(data)
        hash_val = data['hash_val']
        async with aclosing(self._execute_generator(data)) as aiter:
            async for res, data in aiter:
                yield res

                if self.stream_objects:
                    self.post_sse_channel(data, 'execute', hash_val)

    def post_sse_channel(self, data, channel, hash_val):
        """Needs to be able to handle cross-thread requests.

        :param data:
        :param channel:
        :param hash_val:
        :return:
        """
        raise NotImplementedError

    async def get_object_info(self, data: str) -> str:
        """Can be one of config or data.

        :param data:
        :return:
        """
        data = self.decode(data)
        data = await self._get_object_info_data(data)
        return self.encode(data)

    async def get_echo_clock(self, data: str) -> str:
        data = self.decode(data)
        data = self._get_clock_data(data)
        return self.encode(data)


class SSELogger(RemoteDataLogger):
    """Logs all the properties and events to the server's sse data stream
    channel.
    """

    sse_post_callback = None

    def __init__(self, sse_post_callback, **kwargs):
        super(SSELogger, self).__init__(**kwargs)
        self.sse_post_callback = sse_post_callback

    def log_item(self, obj, props=None, trigger_name=None, trigger_value=None):
        data = self._get_log_item_data(obj, props, trigger_name, trigger_value)
        self.sse_post_callback(data, 'data', obj.hash_val)
