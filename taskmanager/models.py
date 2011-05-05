#!/usr/bin/env python

import django
from django.db import models
from django.contrib.auth.models import User
from django.db.models import *

# needed to link Tasks to Templates
import dbtemplates.models

from datetime import datetime
from pytz import timezone
import os, json

# =================================================================
# ==== Users
# =================================================================

class Clinician(models.Model):
    # links the Clinician object to a User object for authentication purposes
    user = models.ForeignKey(User, unique=True)
    
    def __unicode__(self):
        return "%s" % (self.user)
    
# signal handler to associate users with clinician objects
from django.db.models.signals import post_save

def user_save_handler(sender, **kwargs):
    if 'created' in kwargs and kwargs['created']:
        clinician = Clinician(user=kwargs['instance'])
        clinician.save()

post_save.connect(user_save_handler, sender=User)

class Patient(models.Model):
    CONTACT_PREF_CHOICES = (
        ('sms', 'via SMS'),
        ('email', 'via E-mail'),
        ('irc', 'via IRC'),
    )
    address = models.CharField(max_length=200) # phone number, but address for compatibility
    email = models.CharField(max_length=200)
    handle = models.CharField(max_length=100)
    contact_pref = models.CharField(max_length=50, choices=CONTACT_PREF_CHOICES, default='sms')
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    clinicians = models.ManyToManyField(Clinician)
    halted = models.BooleanField(default=False)

    def get_address(self):
        if self.contact_pref == "phone": return self.address
        elif self.contact_pref == "email": return self.email
        elif self.contact_pref == "irc": return self.handle
        else: return self.address

    def get_mode_address(self,mode):
        if mode == "phone": return self.address
        elif mode == "email": return self.email
        elif mode == "irc": return self.handle
        else: return self.address
        
    def __unicode__(self):
        return "%s, %s (%s)" % (self.last_name, self.first_name, self.address)

# =================================================================
# ==== Services and Alerts
# =================================================================

class Service(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    last_status = models.CharField(max_length=100, blank=True, null=True)
    last_status_date = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return self.name

class AlertType(models.Model):
    STATUSES =(
            (u'error', u'error'),
            (u'info', u'info'),
            (u'exception', u'exception'),
            (u'generic', u'generic')
        )
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    service = models.ForeignKey(Service)
    title_template = models.CharField(max_length=500)
    message_template = models.TextField()
    status = models.CharField(max_length=100, choices=STATUSES)
    
    def __unicode__(self):
        return self.name

class AlertManager(models.Manager):
    def add_alert(self, alert_type, title="", message="", arguments={}, patient=None):
        na = Alert(
            alert_type = AlertType.objects.get(name=alert_type),
            title = title,
            message = message,
            arguments = json.dumps(arguments),
            patient = patient
            )
        na.save()
    
class Alert(models.Model):
    alert_type = models.ForeignKey(AlertType)
    patient = models.ForeignKey(Patient, blank=True, null=True)
    title = models.CharField(max_length=100)
    message = models.TextField()
    arguments = models.TextField()
    add_date = models.DateTimeField(auto_now_add=True)

    objects = AlertManager()

    class Meta:
        ordering = ['-add_date']

    def __unicode__(self):
        if self.patient:
            return "%s for %s" % (self.alert_type, self.patient)    
        else:
            return self.alert_type

# =================================================================
# ==== Task Descriptions
# =================================================================

class Task(models.Model):
    name = models.CharField(max_length=100)
    module = models.CharField(max_length=100)
    className = models.CharField(max_length=100)
    schedulable = models.BooleanField(blank=True,default=False)

    # maintains the templates used by this task
    templates = models.ManyToManyField(dbtemplates.models.Template,blank=True)

    def __unicode__(self):
        return "%s (%s.%s)" % (self.name, self.module, self.className)

class TaskTemplate(models.Model):
    name = models.CharField(max_length=100)
    task = models.ForeignKey(Task)
    arguments = models.TextField(blank=True)
    schedulable = models.BooleanField(blank=True,default=True)

    def __unicode__(self):
        return "%s" % (self.name)

# =================================================================
# ==== Processes (Scheduled Task + Session aggregation)
# =================================================================

class ProcessManager(models.Manager):
    def get_pending_processes(self):
        # a pending process has only incomplete scheduled tasks and no completed sessions
        qset = super(ProcessManager, self).get_query_set()
        return qset.filter(taskinstance__state="pending").exclude(taskinstance__state="completed")
    
    def get_current_processes(self):
        # a current process has at least one incomplete session or scheduled task
        qset = super(ProcessManager, self).get_query_set()
        return qset.filter(scheduledtask__state="running")
    
    def get_completed_processes(self):
        # a completed process has only complete scheduled tasks and sessions
        qset = super(ProcessManager, self).get_query_set()
        return qset.exclude(scheduledtask__completed=False).exclude(session__completed=False)

    def reap_empty_processes(self):
        # removes any processes that have no referring instances
        qset = super(ProcessManager, self).get_query_set()
        qset.annotate(num_instances=Count('taskinstance')).filter(num_instances=0).delete()
    
class Process(models.Model):
    name = models.CharField(max_length=100)
    patient = models.ForeignKey(Patient)
    creator = models.ForeignKey(Clinician, blank=True, null=True)
    add_date = models.DateTimeField(auto_now_add=True)

    objects = ProcessManager()

    def get_tasks(self):
        return self.scheduledtask_set.all()

    def get_sessions(self):
        return self.session_set.all()

    def get_pending_tasks(self):
        # a current process has at least one incomplete session
        return self.scheduledtask_set.filter(completed=False)
    
    def get_current_sessions(self):
        # a current process has at least one incomplete session
        return self.session_set.filter(completed=False)

    def get_completed_sessions(self):
        # a current process has at least one incomplete session
        return self.session_set.filter(completed=True)

    def get_status(self):
        pending_cnt = self.get_pending_tasks().count()
        current_cnt = self.get_current_sessions().count()
        completed_cnt = self.get_completed_sessions().count()
        
        if pending_cnt > 0 and current_cnt <= 0 and completed_cnt <= 0: return "pending"
        elif (current_cnt) > 0 or (pending_cnt > 0 and completed_cnt > 0): return "running"
        elif pending_cnt <= 0 and current_cnt <= 0 and completed_cnt > 0: return "past"
        else: return "unknown"

    class Meta:
        verbose_name_plural = "processes"

    def __unicode__(self):
        return "%s (#%d)" % (self.name, self.id)

# =================================================================
# ==== TaskInstance (aggregated by Processes)
# ==== DESCRIPTION:
# ==== a taskinstance is a running instance of a task for a
# ==== particular user, as parameterized by a tasktemplate.
# =================================================================

class TaskInstanceManager(models.Manager):
    def get_pending_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(schedule_date__gt=datetime.now(), status="pending")
    
    def get_due_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(schedule_date__lte=datetime.now(), status="pending")
    
    def get_running_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(status="running")
    
    def get_timedout_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(timeout_date__lte=datetime.now(), status="running")
    
    def get_completed_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(status="completed")

    def get_errored_tasks(self):
        qset = super(TaskInstanceManager, self).get_query_set()
        return qset.filter(status="errored")

    def create_task(self, patient, task, params, schedule_date, creator="n/a", name=None):
        """
        Creates a new task for a given patient, with a dict of params
        (usually specified from filling out a TaskTemplate). The task
        will run on schedule_date, at which point it will be promoted
        from the "pending" status to the "running" status and actually
        begin execution of the machine associated with its Task.

        A new Process will be created to encapsulate this TaskInstance, which
        will bear the name of the chosen Task by default, but can be
        overridden by the name parameter.
        """

        p = Process(
            name=(name if name is not None else task.name),
            creator=creator,
            patient=patient
            )
        p.save()

        t = TaskInstance(
            patient=patient,
            task=task,
            mode=patient.contact_pref,
            process=p,
            params=params,
            schedule_date=schedule_date
            )
        t.save()
    
class TaskInstance(models.Model):
    # core information
    patient = models.ForeignKey(Patient)
    task = models.ForeignKey(Task)
    mode = models.CharField(max_length=50, choices=Patient.CONTACT_PREF_CHOICES) # method of contact (e.g. email, sms)
    process = models.ForeignKey(Process)
    active = models.BooleanField(default=True)

    # possible states
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('errored', 'Errored')
    )

    # current state of the task
    state = models.CharField(max_length=100, default="pending", choices=STATUS_CHOICES)
    details = models.CharField(max_length=800,blank=True,null=True)
    # state information for the task
    params = models.TextField(blank=True) # filled in from TaskTemplate, persistent
    context = models.TextField(blank=True) # managed by task, possibly non-persistent
    
    # state change times
    # past tense dates are dates that are set when they occur
    # whereas future tense are events that are set prior to occurring
    added_date = models.DateTimeField(auto_now_add=True) # pending until schedule_date arrives
    schedule_date = models.DateTimeField(blank=True,null=True) # due until executed
    ran_date = models.DateTimeField(blank=True,null=True) # running until completed
    timeout_date = models.DateTimeField(blank=True,null=True) # no status, waiting to be poked
    completed_date = models.DateTimeField(blank=True,null=True) # completed forever
    errored_date = models.DateTimeField(blank=True,null=True) # errored forever(?)

    objects = TaskInstanceManager()

    def get_messages(self):
        return self.sessionmessage_set.all()

    def mark_running(self):
        self.state = "running"
        self.ran_date = datetime.now()
        self.save()
        
    def mark_errored(self, details):
        self.state = "errored"
        self.details = details
        self.errored_date = datetime.now()
        self.save()
        
    def mark_completed(self):
        if self.state == "completed": return
        self.state = "completed"
        self.completed_date = datetime.now()
        self.save()
        
    def is_pending(self):
        return (self.schedule_date > datetime.now()) and (self.state == "pending")

    def is_due(self):
        return (self.schedule_date <= datetime.now()) and (self.state == "pending")
    
    def is_running(self):
        return (self.state == "running")
    
    def is_past(self):
        return (self.state == "completed")

    def is_errored(self):
        return (self.state == "errored")

    def get_status(self):
        if self.is_pending(): return "pending"
        elif self.is_due(): return "due"
        elif self.is_running(): return "running"
        elif self.is_past(): return "past"
        else: return "unknown"

    def spawn_task(self, task, update_params, schedule_date):
        """
        Spawns a new task for the current patient. The task
        will run on schedule_date, at which point it will be promoted
        from the "pending" status to the "running" status and actually
        begin execution of the machine associated with its Task.

        The new task will have the same process as the existing task,
        and its params will be the existing parameters updated by the
        specified ones.
        """

        # copy existing parameters and update them with the new params
        new_params = dict(self.params)
        new_params.update(update_params)

        t = TaskInstance(
            patient=self.patient,
            task=self.task,
            mode=self.mode,
            process=self.process,
            params=new_params,
            schedule_date=schedule_date
            )
        t.save()

    class Meta:
        verbose_name_plural = "task instances"
        
    def __unicode__(self):
        return "Task Instance for %s on %s" % (self.patient.address, self.task.name)

class SessionMessage(models.Model):
    session = models.ForeignKey(TaskInstance)
    message = models.TextField()
    outgoing = models.BooleanField()
    add_date = models.DateTimeField(auto_now_add=True)
    
    def __unicode__(self):
        if self.outgoing:
            return "Sent to %s: %s" % (self.session.patient.address, self.message)
        else:
            return "Received from %s: %s" % (self.session.patient.address, self.message)
