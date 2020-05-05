import trio
from threading import get_ident


async def test_run_in_dummy_executor():
    from pymoa.device.digital import RandomDigitalChannel
    from pymoa.executor.remote.dummy import DummyRemoteExecutor

    executor = DummyRemoteExecutor()
    device = RandomDigitalChannel(name='rand_device', executor=executor)
    await executor.start_executor()
    await executor.ensure_remote_instance(device)
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    device.fbind('on_data_update', callback)

    assert device.name == 'rand_device'
    assert device.state is None

    await device.read_state()
    assert device.state is not None
    assert count == 1
    timestamp = device.timestamp
    await trio.sleep(.01)

    await device.read_state()
    assert device.timestamp > timestamp
    assert count == 2

    await executor.delete_remote_instance(device)
    await executor.stop_executor(block=True)


async def test_run_in_dummy_executor_thread():
    from pymoa.device.digital import RandomDigitalChannel
    from pymoa.executor.remote.dummy import DummyRemoteExecutor
    ident = [None, None, get_ident()]

    class DigitalChannel(RandomDigitalChannel):
        def _get_state_value(self):
            ident[0] = get_ident()
            return super(DigitalChannel, self)._get_state_value()

    executor = DummyRemoteExecutor(use_thread_executor=True)
    device = DigitalChannel(name='rand_device', executor=executor)
    await executor.start_executor()
    await executor.ensure_remote_instance(device)
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
        ident[1] = get_ident()
    device.fbind('on_data_update', callback)

    assert device.name == 'rand_device'
    assert device.state is None

    await device.read_state()
    assert device.state is not None
    assert count == 1
    assert ident[1] == ident[2]
    assert ident[0] != ident[2]
    timestamp = device.timestamp
    await trio.sleep(.01)

    await device.read_state()
    assert device.timestamp > timestamp
    assert count == 2
    assert ident[1] == ident[2]
    assert ident[0] != ident[2]

    await executor.delete_remote_instance(device)
    await executor.stop_executor(block=True)
