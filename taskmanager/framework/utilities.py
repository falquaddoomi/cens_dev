"""
Contains a collection of miscellaneous utility
functions and classes used throughout the framework.
"""

from collections import defaultdict
import weakref

def coroutine(func):
    """
    A decorator function that takes care of starting a coroutine
    automatically on call.

    Will eventually be used to implete the coroutine approach
    to task authoring.
    """
    def start(*args,**kwargs):
        cr = func(*args,**kwargs)
        cr.next()
        return cr
    return start

class KeepRefs(object):
    """
    Holds all instances of a class in a list, accessible via
    get_instances(cls). Use as a mix-in.

    Used in TaskDispatcher to send a "session deleted" message to
    every TaskDispatcher that's been created.
    """
    __refs__ = defaultdict(list)
    def __init__(self):
        self.__refs__[self.__class__].append(weakref.ref(self))

    @classmethod
    def get_instances(cls):
        for inst_ref in cls.__refs__[cls]:
            inst = inst_ref()
            if inst is not None:
                yield inst
