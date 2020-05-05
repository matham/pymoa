import pytest
import trio


@pytest.fixture
async def quart_app(nursery):
    from pymoa.executor.remote.rest.quart_app import create_app
    app = create_app()
    nursery.start_soon(app.run_task)
    await trio.sleep(.01)

    async with app.app_context():
        yield app


@pytest.fixture
async def quart_executor(quart_app):
    from pymoa.executor.remote.rest.client import RestExecutor
    executor = RestExecutor(uri='http://127.0.0.1:5000')
    await executor.start_executor()

    yield executor

    await executor.stop_executor(block=True)


@pytest.fixture
async def quart_device(quart_executor):
    from pymoa.device.digital import RandomDigitalChannel

    class DigitalChannel(RandomDigitalChannel):
        pytest_callback = None

        def _get_state_value(self):
            if self.pytest_callback is not None:
                self.pytest_callback()
            return super(DigitalChannel, self)._get_state_value()

    device = RandomDigitalChannel(name='rand_device', executor=quart_executor)
    await quart_executor.ensure_remote_instance(device, name='rand_device')

    yield device

    await quart_executor.delete_remote_instance(device)
