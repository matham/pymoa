import trio
from pymoa.device.digital import RandomDigitalChannel
from pymoa.executor.remote.rest.client import RestExecutor


async def test_run_in_quart_executor(
        quart_app, quart_executor: RestExecutor,
        quart_device: RandomDigitalChannel):
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    quart_device.fbind('on_data_update', callback)

    assert quart_device.name == 'rand_device'
    assert quart_device.state is None

    data = None
    async with trio.open_nursery() as nursery:
        gen = await quart_executor.get_execute_from_remote(quart_device)
        nursery.start_soon(quart_device.read_state)
        async for data in gen:
            break

    assert quart_device.state is not None
    assert count == 1
    timestamp = quart_device.timestamp

    assert data
    ex_state, ex_timestamp = data['return_value']
    assert quart_device.timestamp == ex_timestamp
    assert quart_device.state == ex_state

    remote_device = quart_app.server_executor.registry.hashed_instances[
        quart_device.hash_val]
    assert remote_device.timestamp == ex_timestamp
    assert remote_device.state == ex_state
    await trio.sleep(.01)

    await quart_device.read_state()
    assert quart_device.timestamp > timestamp
    assert count == 2

