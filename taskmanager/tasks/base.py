
# signifies that our task is done to the dispatcher
# the dispatch should remove us when it receives this
class TaskCompleteException(Exception):
    pass

class BaseTask(object):
    """
    Provides a set of handlers that tasks should override. All tasks must inherit from this base class.
    """
    
    def __init__(self, app, patient, session, args=None):
        self.app = app
        self.patient = patient
        self.session = session
        self.args = args
        self.prefies = []

    def prefixes(self):
        """
        Returns a prefix (or list of them) which can be used to activate this task. Necessary
        for demultiplexing different kinds of running tasks from each other.

        Incoming messages will have their first word compared against the list of prefixes
        for each running task; the first matching task will have handle() called on it,
        proceeding through each matching task and ending when one returns True.
        """
        return self.prefixes

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
