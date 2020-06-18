import trio
from queue import Queue, Empty
import time
from threading import Thread
from contextlib import ExitStack

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock

from pymoa.executor.threading import TrioPortal
from pymoa.kivy import kivy_run_in_async, mark, \
    async_run_in_kivy, EventLoopStoppedError, KivyEventCancelled, \
    KivyClockContextManager, trio_thread, kivy_thread, \
    TrioPortalContextManager, ContextVarContextManager

kv = '''
BoxLayout:
    spacing: '5dp'
    orientation: 'vertical'
    BoxLayout:
        spacing: '5dp'
        Button:
            on_release: app.wait_async(float(delay.text or 0))
            text: 'Press to wait'
        TextInput:
            id: delay
            text: '1.5'
            input_filter: 'float'
            hint_text: 'delay'
        Label:
            text: 'measured delay: {}\\n{}'.format(app.delay, app.delay_msg)
    BoxLayout:
        spacing: '5dp'
        Button:
            on_release: app.trigger_async_error()
            text: 'Trigger error:'
        Label:
            text: 'Error message: {}'.format(app.error_msg)
    Label:
        text: 'trio sent: {}'.format(app.trio_msg)
'''


class DemoApp(App):

    delay = NumericProperty(0)

    delay_msg = StringProperty('')

    error_msg = StringProperty('')

    trio_msg = StringProperty('')

    count = 0

    def build(self):
        return Builder.load_string(kv)

    async def sleep_for(self, delay):
        await trio.sleep(delay)
        self.count += 1
        return f'Thanks for nap {self.count}!!'

    @kivy_run_in_async
    def wait_async(self, delay):
        self.delay = 0
        self.delay_msg = ''
        ts = time.perf_counter()
        try:
            self.delay_msg = yield mark(self.sleep_for, delay)
        except KivyEventCancelled:
            print('cancelled wait_async while it was waiting')
            return
        self.delay = time.perf_counter() - ts

    async def raise_error(self):
        await trio.sleep(2)
        raise ValueError('Who has woken me at this hour???')

    @kivy_run_in_async
    def trigger_async_error(self):
        self.error_msg = ''
        try:
            yield mark(self.raise_error)
        except ValueError as e:
            self.error_msg = str(e)
        except KivyEventCancelled:
            print('cancelled trigger_async_error while it was waiting')

    @async_run_in_kivy
    def send_kivy_message(self, packet):
        self.trio_msg = f'beetle juice {packet} times'

    async def send_msg_to_kivy_from_trio(self):
        i = 0
        while True:
            try:
                await self.send_kivy_message(i)
            except EventLoopStoppedError:
                # kivy stopped so nothing more to do
                return
            i += 1
            await trio.sleep(1.3)

    def _trio_thread_target(self, clock, queue: Queue):
        async def runner():
            portal = TrioPortal()
            token = trio_thread.set(portal)
            queue.put(portal)

            try:
                await self.send_msg_to_kivy_from_trio()
            finally:
                if token is not None:
                    trio_thread.reset(token)

        with KivyClockContextManager(clock):
            trio.run(runner)

    def run_threading(self):
        queue = Queue(maxsize=1)
        thread = Thread(target=self._trio_thread_target, args=(Clock, queue))
        thread.start()

        ts = time.perf_counter()
        res = None
        while time.perf_counter() - ts < 1:
            try:
                res = queue.get(block=True, timeout=.1)
            except Empty:
                pass
            else:
                break
        if res is None:
            raise TimeoutError(
                'Timed out waiting for trio thread to initialize')

        with TrioPortalContextManager(res):
            with ContextVarContextManager(kivy_thread, Clock):
                self.run()

        thread.join()

    async def run_app(self):
        with ExitStack() as stack:
            portal = TrioPortal()
            stack.enter_context(TrioPortalContextManager(portal))
            stack.enter_context((KivyClockContextManager(Clock)))
            stack.enter_context((ContextVarContextManager(kivy_thread, Clock)))
            stack.enter_context((ContextVarContextManager(trio_thread, portal)))
            async with trio.open_nursery() as app_nursery:
                app_nursery.start_soon(self.async_run, 'trio')
                app_nursery.start_soon(self.send_msg_to_kivy_from_trio)


if __name__ == '__main__':
    # trio.run(DemoApp().run_app)
    DemoApp().run_threading()
