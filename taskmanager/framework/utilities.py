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

# random date-parsing routines to make my life easier
from datetime import datetime
from parsedatetime import parsedatetime

def parsedt(datestr, offset=None, verify_complete=False):
    """
    Parses 'datestr' as a date using the parsedatetime library.

    If offset is specified, the date is computed relative to that date (e.g.
    'in 7 days' will be interpreted relative to the offset date). If an offset
    is not specified, it defaults to the current date and time.

    If verify_complete is True, 'instr' must result in a date AND time, otherwise
    a ValueError exception is raised.
    """

    pdt = parsedatetime.Calendar()
    (result, retval) = pdt.parse(datestr, offset)

    if verify_complete and (retval < 2):
        raise ValueError("Could not parse '%s' as both a date and time (result: %d)" % (datestr, retval))
    
    return datetime(*result[0:7])
