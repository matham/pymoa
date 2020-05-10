"""Quart App
============

"""
# todo: investigate compression and no-cache for data
from http import HTTPStatus
from quart_trio import QuartTrio
from quart import make_response, request, current_app, jsonify
from collections import defaultdict
from itertools import chain
import json
from queue import Full

from pymoa.utils import MaxSizeSkipDeque
from pymoa.executor.remote.rest.server import RestServer

import pymoa.executor.remote.referable_class_register

__all__ = ('create_app', 'QuartRestServer')


class QuartRestServer(RestServer):
    """Quart server side handler.
    """

    quart_app = None

    def __init__(self, quart_app, **kwargs):
        super(QuartRestServer, self).__init__(**kwargs)
        self.quart_app = quart_app

    def post_sse_channel(self, data, channel, channel_type):
        data = self.encode(data)

        queues = self.quart_app.sse_clients[channel] \
            if channel in self.quart_app.sse_clients else {}
        queues2 = self.quart_app.sse_clients[channel_type] \
            if channel_type in self.quart_app.sse_clients else {}
        queues3 = self.quart_app.sse_clients[''] \
            if '' in self.quart_app.sse_clients else {}

        queue: MaxSizeSkipDeque
        for queue in chain(
                queues.values(), queues2.values(), queues3.values()):
            try:
                queue.add_item((data, channel), len(data) + len(channel))
            except Full:
                pass


async def set_sse_callback():
    await current_app.server_executor.start_executor()

    current_app.sse_clients = defaultdict(dict)
    current_app.max_buffer = 100 * 1024 * 1024


async def ensure_instance():
    data = (await request.get_data()).decode('utf8')
    await current_app.server_executor.ensure_instance(data)
    return '', HTTPStatus.NO_CONTENT


async def delete_instance():
    data = (await request.get_data()).decode('utf8')
    await current_app.server_executor.delete_instance(data)
    return '', HTTPStatus.NO_CONTENT


async def execute():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.server_executor.execute(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def get_object_info():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.server_executor.get_object_info(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def get_echo_clock():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.server_executor.get_echo_clock(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def sse():
    channel = request.args.get('channel', '')
    queue = MaxSizeSkipDeque(max_size=current_app.max_buffer)
    key = object()
    current_app.sse_clients[channel][key] = queue

    # todo: send alive with timeout in case skipped packets

    async def send_events():
        try:
            data = json.dumps('alive')
            message = f"data: {data}\n\n"
            yield message.encode('utf-8')

            async for (data, data_channel), packet in queue:
                id_data = json.dumps((packet, data_channel))
                message = f"data: {data}\nid: {id_data}\n\n"
                yield message.encode('utf-8')
        finally:
            del current_app.sse_clients[channel][key]
            if not current_app.sse_clients[channel]:
                del current_app.sse_clients[channel]

    response = await make_response(
        send_events(),
        {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Transfer-Encoding': 'chunked',
        },
    )
    response.timeout = None
    return response


def handle_unexpected_error(error):
    message = [str(x) for x in error.args]
    status_code = 500
    success = False
    response = {
        'success': success,
        'error': {
            'type': error.__class__.__name__,
            'message': f'An unexpected error has occurred: "{message}".'
        }
    }

    return jsonify(response), status_code


def create_app() -> QuartTrio:
    """Creates the quart app.
    """
    app = QuartTrio(__name__)
    app.server_executor = QuartRestServer(quart_app=app)
    app.before_first_request(set_sse_callback)

    app.add_url_rule(
        '/api/v1/objects/create_open', view_func=ensure_instance,
        methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/delete', view_func=delete_instance, methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/execute', view_func=execute, methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/object', view_func=get_object_info, methods=['GET'])
    app.add_url_rule('/api/v1/stream', view_func=sse, methods=['GET'])
    app.add_url_rule(
        '/api/v1/echo_clock', view_func=get_echo_clock, methods=['GET'])

    # app.register_error_handler(Exception, handle_unexpected_error)

    return app


if __name__ == '__main__':
    create_app().run()
