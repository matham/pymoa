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

    data = {}
    exec_data = {}
    exec_gen = await quart_executor.get_execute_from_remote(quart_device)
    data_gen = await quart_executor.get_data_from_remote(quart_device)

    async def read_exec_gen():
        nonlocal exec_data
        async for exec_data in exec_gen:
            break

    async def read_data_gen():
        nonlocal data
        async for data in data_gen:
            break

    async with trio.open_nursery() as nursery:
        nursery.start_soon(quart_device.read_state)
        nursery.start_soon(read_data_gen)
        nursery.start_soon(read_exec_gen)

    assert quart_device.state is not None
    assert count == 1
    timestamp = quart_device.timestamp

    assert exec_data
    ex_state, ex_timestamp = exec_data['return_value']

    assert quart_device.timestamp == ex_timestamp
    assert quart_device.state == ex_state

    assert data
    logged_items = data['logged_items']
    assert logged_items['timestamp'] == ex_timestamp
    assert logged_items['state'] == ex_state

    remote_device = quart_app.server_executor.registry.hashed_instances[
        quart_device.hash_val]
    assert remote_device.timestamp == ex_timestamp
    assert remote_device.state == ex_state
    await trio.sleep(.01)

    await quart_device.read_state()
    assert quart_device.timestamp > timestamp
    assert count == 2


async def test_echo_clock(quart_executor: RestExecutor):
    a, b, c = await quart_executor.get_echo_clock()
    assert b >= a
    assert c >= b
