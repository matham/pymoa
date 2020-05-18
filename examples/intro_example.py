from pymoa.stage import MoaStage
from pymoa.stage.delay import Delay, UniformRandomDelay
from pymoa.stage.gate import DigitalGateStage
from pymoa.device.digital import DigitalChannel
from pymoa.data_logger import SimpleTerminalLogger
from pymoa.executor import apply_executor
from pymoa.executor.threading import ThreadExecutor
import trio
import random
from time import perf_counter


class VirtualDevice(DigitalChannel):

    def executor_callback(self, return_value):
        self.state, self.timestamp = return_value
        self.dispatch('on_data_update', self)

    @apply_executor(callback=executor_callback)
    def write_state(self, state: bool, **kwargs):
        return state, perf_counter()

    async def pump_state(self):
        while True:
            await trio.sleep(random.random() * 10 + 1)
            await self.write_state(random.random() >= 0.5)


class SugarPalletStage(MoaStage):

    motor_device: VirtualDevice = None

    def __init__(self, motor_device, **kwargs):
        super(SugarPalletStage, self).__init__(**kwargs)
        self.motor_device = motor_device

    async def do_trial(self):
        await self.motor_device.write_state(True)
        await trio.sleep(0.2)
        await self.motor_device.write_state(False)


executor = ThreadExecutor()
photo_bream_device = VirtualDevice(name='photobeam_device', executor=executor)
motor_device = VirtualDevice(name='motor_device', executor=executor)

root = MoaStage(name='Root stage')
trial = MoaStage(name='Trial', repeat=2)

root.add_stage(Delay(delay=20, name='Habituation'))
root.add_stage(trial)
root.add_stage(Delay(delay=15, name='post delay'))

trial.add_stage(DigitalGateStage(
    device=photo_bream_device, exit_state=True, name='photobeam_stage'))
trial.add_stage(SugarPalletStage(
    motor_device=motor_device, name='sugar pallet stage'))
trial.add_stage(UniformRandomDelay(min=20, max=40, name='ITI'))


logger = SimpleTerminalLogger(separator=',')
for stage in root.iterate_stages():
    logger.add_logged_instance(stage)


async def run_experiment():
    # start the threading executor
    await executor.start_executor()
    async with trio.open_nursery() as nursery:
        async def run_root_stage():
            # run the experiment stages, but when done also cancel reading the
            # devices
            await root.run_stage()
            nursery.cancel_scope.cancel()

        # reads the photobeam device continuously
        nursery.start_soon(photo_bream_device.pump_state)
        # runs the experiment stages
        nursery.start_soon(run_root_stage)

    # we're done so we can stop the threading executor
    await executor.stop_executor()

trio.run(run_experiment)
