import pytest
import trio


@pytest.fixture
async def quart_app(nursery):
    from pymoa.executor.remote.app.quart import create_app
    app = create_app()
    nursery.start_soon(app.run_task)
    await trio.sleep(.01)

    async with app.app_context():
        yield app


@pytest.fixture
async def quart_rest_executor(quart_app):
    from pymoa.executor.remote.rest.client import RestExecutor
    async with RestExecutor(uri='http://127.0.0.1:5000') as executor:

        yield executor


@pytest.fixture
async def quart_socket_executor(quart_app, nursery):
    from pymoa.executor.remote.socket.websocket_client import WebSocketExecutor
    async with WebSocketExecutor(
            nursery=nursery, server='127.0.0.1', port=5000) as executor:
        yield executor


@pytest.fixture
async def quart_rest_device(quart_rest_executor):
    from pymoa.device.digital import RandomDigitalChannel

    class DigitalChannel(RandomDigitalChannel):
        pytest_callback = None

        def _get_state_value(self):
            if self.pytest_callback is not None:
                self.pytest_callback()
            return super(DigitalChannel, self)._get_state_value()

    device = RandomDigitalChannel(
        name='rand_device_rest', executor=quart_rest_executor)
    await quart_rest_executor.ensure_remote_instance(
        device, name='rand_device_rest')

    yield device

    await quart_rest_executor.delete_remote_instance(device)


@pytest.fixture
async def quart_socket_device(quart_socket_executor):
    from pymoa.device.digital import RandomDigitalChannel

    class DigitalChannel(RandomDigitalChannel):
        pytest_callback = None

        def _get_state_value(self):
            if self.pytest_callback is not None:
                self.pytest_callback()
            return super(DigitalChannel, self)._get_state_value()

    device = RandomDigitalChannel(
        name='rand_device_socket', executor=quart_socket_executor)
    await quart_socket_executor.ensure_remote_instance(
        device, name='rand_device_socket')

    yield device

    await quart_socket_executor.delete_remote_instance(device)
