'''Utilities
===============

Module that provides helpful classes and functions.
'''
from kivy.clock import Clock

__all__ = ('to_bool', 'ObjectStateTracker')


def to_bool(val):
    '''Takes anything and converts it to a bool type. If `val` is the `'False'`
    or `'0'` strings it also evaluates to False.

    :Parameters:

        `val`: object
            A value which represents True/False.

    :Returns:
        bool. `val`, evaluated to a boolean.

    ::

        >>> to_bool(0)
        False
        >>> to_bool(1)
        True
        >>> to_bool('0')
        False
        >>> to_bool('1')
        True
        >>> to_bool('False')
        False
        >>> to_bool('')
        False
        >>> to_bool('other')
        True
        >>> to_bool('[]')
        True
    '''
    if val == 'False' or val == '0':
        return False
    return not not val


class ObjectStateTracker(object):
    '''Class for tracking the state of kivy properties and assigning callbacks
    for when the states reach the specified values.

    Specifically, one adds links to a chain of states. Each link is composed
    of a group of objects, with each object having a list of properties and
    the desired value for each property. When all the properties for all the
    objects match the desired values, the link is considered done and the
    callback is executed and then we move to the next link. This is repeated
    until all the links are done. New links can be dynamically added.

    For example::

        >>> from kivy.event import EventDispatcher
        >>> from kivy.properties import BooleanProperty, StringProperty
        >>> from moa.utils import ObjectStateTracker

        >>> def callback1():
        ...     print('Done1!!!')
        >>> def callback2():
        ...     print('Done2!!!')

        >>> class ExampleA(EventDispatcher):
        ...
        ...     name = StringProperty('hello')
        ...     state = BooleanProperty(False)

        >>> tracker = ObjectStateTracker()
        >>> a = ExampleA()

        >>> # add first link
        >>> tracker.add_link(callback1, (a, {'name': 'cheese', 'state': True}))
        >>> a.state = True
        >>> a.name = 'cheese'  # now the first link is satisfied
        Done1!!!
        >>> # link was already satisfied so it's immediately executed.
        >>> tracker.add_link(callback1, (a, {'name': 'cheese', 'state': True}))
        Done1!!!
        >>> tracker.add_link(callback1, (a, {'name': 'apple'}))
        >>> tracker.add_link(callback2, (a, {'name': 'orange'}))
        >>> a.name = 'orange'  # still waiting for the apple link to complete
        >>> a.name = 'apple'  # apple link is now complete
        Done1!!!
        >>> a.name = 'orange'  # finally orange link is now complete.
        Done2!!!

    :Parameters:

        `start`: bool
            Whether the tracker should start in :attr:`running` mode when
            created. Defaults to True. If False, :meth:`start` must be called
            to start tracking.
    '''

    _states = []

    running = False
    '''Whether the tracker is active. Read only.
    '''

    _callback_uids = []

    _timeout_event = None

    def __init__(self, start=True, **kwargs):
        super(ObjectStateTracker, self).__init__(**kwargs)
        self._states = []
        self.running = True
        self._timeout_event = Clock.create_trigger(self._timeout_callback)

    def add_link(self, link_callback, *largs, **kwargs):
        '''Adds a link to the chain.

        :Parameters:

            `link_callback`: callable
                The function to call when the link is done.
            `*largs`: Caught positional args, each a 2-tuple
                A list of 2-tuples. Each 2-tuple has two elements - a object
                and a dict respectively. The dict's keys are property names and
                its values are the desired values of those properties for that
                object. When they match for all the objects and properties
                at the same time the link is done and ``link_callback`` is
                executed.
            `timeout`: float
                If provided as a kwarg, it's how long to wait for this link
                before continuing on even if the condition is not met.

        .. note::

            If the properties already match the desired values the callback
            may be executed immediately.
        '''
        if not largs:
            return

        d = {}
        for k, v in largs:
            if k in d:
                d[k].update(v)
            else:
                d[k] = v
        self._states.append((d, link_callback, kwargs.get('timeout', None)))
        self._start()

    def add_func_links(self, objects, callbacks, prop, value, **kwargs):
        '''Batch adds links that share the same property name and desired
        value.

        For each ``object`` and corresponding ``link_callback`` in ``objects``
        and ``callbacks`, respectively, it adds a link containing ``prop`` and
        ``value``. Any ``kwargs`` are forwarded to :meth:`add_link`.

        The overall effect is similar to::

            for obj, callback in zip(objects, callbacks):
                self.add_link(callback, (obj, {prop: value}))
        '''
        if not objects or not callbacks:
            return

        for obj, callback in zip(objects, callbacks):
            self.add_link(callback, (obj, {prop: value}), **kwargs)

    def start(self):
        '''Starts the tracker to track if not already :attr:`running`.
        '''
        if self.running:
            return

        self.running = True
        self._start()

    def stop(self):
        '''Stops the tracker from tracking if :attr:`running`. :meth:`start`
        must be called after to start tracking again.
        '''
        if not self.running:
            return

        self._timeout_event.cancel()
        self.running = False
        for obj, prop, uid in self._callback_uids:
            obj.unbind_uid(prop, uid)
        self._callback_uids = []

    def clear(self):
        '''Stops tracking and removes all the links.
        '''
        self.stop()
        self._states = []

    def _start(self):
        states = self._states
        # we're running but we already completed last link
        while self.running and states and not self._callback_uids:
            callbacks = self._callback_uids = []
            for obj, props in states[0][0].items():
                for prop, state in props.items():
                    if state == getattr(obj, prop):
                        continue

                    callbacks.append((
                        obj, prop,
                        obj.fbind(prop, self._prop_callback, obj, prop)))

            if callbacks:
                timeout = states[0][2]
                if timeout is not None:
                    self._timeout_event.timeout = timeout
                    self._timeout_event()
                return
            f = states[0][1]
            del states[0]
            f()

    def _timeout_callback(self, *largs):
        if self._states:
            _, f, _ = self._states.pop(0)
            for obj, prop, uid in self._callback_uids:
                obj.unbind_uid(prop, uid)
            self._callback_uids = []
            f()
            self._start()

    def _prop_callback(self, obj, prop, *largs):
        state0, f, _ = self._states[0]
        if state0[obj][prop] != getattr(obj, prop):
            return

        obj.funbind(prop, self._prop_callback, obj, prop)
        del state0[obj][prop]
        if state0[obj]:
            return

        del state0[obj]
        if state0:
            return

        # done with this link
        self._timeout_event.cancel()
        del self._states[0]
        self._callback_uids = []
        f()
        self._start()
