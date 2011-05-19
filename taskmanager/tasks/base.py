import json

from taskmanager.models import TaskInstance

# signifies that our task is done to the dispatcher
# the dispatch should remove us when it receives this
class TaskCompleteException(Exception):
    pass

class BaseTask(object):
    """
    Provides a set of handlers that tasks should override. All tasks must inherit from this base class.
    """
    
    def __init__(self, dispatch, instance):
        self.dispatch = dispatch
        self.instance = instance
        self._prefix = ""

    @property
    def params(self):
        return json.loads(self.instance.params)

    @params.setter
    def params(self, value):
        self.instance.params = json.dumps(value)

    @property
    def prefix(self):
        """
        Returns a prefix which can be used to activate this task. Necessary
        for demultiplexing different kinds of running tasks from each other.

        Incoming messages will have their first word compared against the prefix
        for each running task; the first matching task will have handle() called on it,
        proceeding through each matching task and ending when one returns True.
        """
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        self._prefix = value

    # ==========================
    # == handlers
    # ==========================

    def start(self):
        """
        Invoked when a task is first begun, sometime soon after it's constructed.
        
        Send any initial messages here using self.app.send()
        """
        pass
    
    def handle(self, message):
        """
        Invoked when the dispatch decides a message belongs to this task.

        Raise a ParseError if you know the message was meant for this task and it's invalid.
        The message in the ParseError will be sent back to the user.
        
        Return True if you've dealt with the message somehow. No further tasks (if any exist)
        will receive this message.
        
        Return False if you're not sure if
        a) the message was actually for this task, or
        b) you can't determine if the message is actually invalid.
        (if you can't tell, returning False should be an unusual occurrence)
        """
        return True

    def timeout(self):
        """
        Invoked when the dispatch receives a timeout for this task from the scheduler.

        Timeouts are generally registered by a task after sending a message, during
        which time the task waits for a reply. When the timeout triggers, the task
        can stop waiting for a reply and perform whatever actions are appropriate.
        """
        pass

    # ==========================
    # == pickler functions
    # ==========================
    
    def __getstate__(self):
        odict = self.__dict__.copy() # copy the dict since we change it
        # replace instance with its id
        odict['instance'] = self.instance.id
        # remove the dispatch reference
        # this will have to be manually reassociated
        del odict['dispatch']
        return odict

    def __setstate__(self, dict):
        # replace instance id with the actual instance
        self.instance = TaskInstance.objects.get(pk=dict['instance'])
        self.__dict__.update(dict)   # update attributes
