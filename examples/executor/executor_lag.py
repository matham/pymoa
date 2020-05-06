
import trio
from pymoa.executor.remote.rest.quart_app import create_app
from pymoa.executor.remote.rest.client import RestExecutor
from pymoa.executor.threading import ThreadExecutor, AsyncThreadExecutor
from pymoa.executor.remote.dummy import DummyRemoteExecutor


async def measure_within_process_quart_lag():
    app = create_app()
    executor = RestExecutor(uri='http://127.0.0.1:5001')
    requests = []
    responses = []

    async with trio.open_nursery() as nursery:
        nursery.start_soon(app.run_task, "127.0.0.1", 5001)
        await trio.sleep(1)

        async with app.app_context():
            await executor.start_executor()

            for _ in range(100):
                ts, t, te = await executor.get_echo_clock()
                requests.append((t - ts) / 1e6)
                responses.append((te - t) / 1e6)

            await executor.stop_executor(block=True)

        nursery.cancel_scope.cancel()

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'Quart-internal; Request lag: {request}ms. '
          f'Response lag: {response}ms')


async def measure_outside_process_quart_lag():
    executor = RestExecutor(uri='http://127.0.0.1:5000')
    responses = []

    await executor.start_executor()
    await trio.sleep(1)

    for _ in range(100):
        ts, t, te = await executor.get_echo_clock()
        responses.append((te - ts) / 1e6)

    await executor.stop_executor(block=True)

    response = sum(responses) / len(responses)
    print(f'Quart-external; Round-trip lag: {response}ms')


async def measure_cls_lag(cls):
    executor = cls()
    requests = []
    responses = []

    await executor.start_executor()
    await trio.sleep(1)

    for _ in range(100):
        ts, t, te = await executor.get_echo_clock()
        requests.append((t - ts) / 1e6)
        responses.append((te - t) / 1e6)

    await executor.stop_executor(block=True)

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'{cls.__name__}; Request lag: {request}ms. '
          f'Response lag: {response}ms')


if __name__ == '__main__':
    trio.run(measure_within_process_quart_lag)
    # only run if quart app is serving externally
    trio.run(measure_outside_process_quart_lag)

    for cls in (ThreadExecutor, AsyncThreadExecutor, DummyRemoteExecutor):
        trio.run(measure_cls_lag, cls)
