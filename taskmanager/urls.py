#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *
import taskmanager.views as views
import taskmanager.subviews.login as login
import taskmanager.subviews.dashboard as dashboard
import taskmanager.subviews.details as details

import taskmanager.subviews.contexts.patients as contexts_patients
import taskmanager.subviews.contexts.tasks as contexts_tasks
import taskmanager.subviews.contexts.monitor as contexts_monitor

import taskmanager.subviews.ASAP as ASAP

urlpatterns = patterns('',
    (r'^$', dashboard.default), # redirects to their last-viewed context (or 'patients' if none)
    (r'^login$', login.prompt_login),
    (r'^logout$', login.perform_logout),

    # ================================
    # patients context
    # ================================
    (r'^patients/?$', contexts_patients.default),
    (r'^patients/(?P<patientid>\d+)/processes/?$', contexts_patients.processes),
    (r'^patients/(?P<patientid>\d+)/tasks/?$', contexts_patients.tasks),
    (r'^patients/(?P<patientid>\d+)/history/?$', contexts_patients.history),
    (r'^patients/(?P<patientid>\d+)/messagelog/?$', contexts_patients.messagelog),
    (r'^patients/(?P<patientid>\d+)/calendar/?$', contexts_patients.calendar),

    # patients context: POST targets and an AJAX thing
    (r'^patients/add/?$', contexts_patients.add_patient),
    (r'^tasks/add/?$', contexts_patients.add_scheduled_task),
    (r'^processes/add/?$', contexts_patients.add_scheduled_process),
    (r'^tasktemplates/(?P<tasktemplateid>\d+)/fields/?$', contexts_patients.get_tasktemplate_fields),

    # ================================
    # tasks context
    # ================================
    (r'^tasks/?$', contexts_tasks.default),
    (r'^tasks/(?P<taskid>\d+)/templates/?$', contexts_tasks.templates),
    (r'^tasks/(?P<taskid>\d+)/templates/(?P<tasktemplateid>\d+)/?$', contexts_tasks.templates),
    (r'^tasks/(?P<taskid>\d+)/messages/?$', contexts_tasks.messages),
                       
    # tasks context: POST targets
    (r'^tasks/templates/add/?$', contexts_tasks.add_tasktemplate),
    (r'^tasks/templates/update/?$', contexts_tasks.update_template),
    (r'^tasks/messages/update/?$', contexts_tasks.update_messages),

    # ================================
    # monitor context
    # ================================
    (r'^monitor/?$', contexts_monitor.default),
    (r'^services/(?P<serviceid>\d+)/status/?$', contexts_monitor.status),
    (r'^services/(?P<serviceid>\d+)/alerts/?$', contexts_monitor.alerts),

    # monitor context: POST targets
    (r'^monitor/alerts/mark_reviewed', contexts_monitor.mark_alerts_reviewed),
                       
    # ================================
    # details views
    # ================================
    (r'^processes/(?P<processid>\d+)/details/?$', details.process_details),
    (r'^tasks/(?P<taskid>\d+)/details/?$', details.scheduledtask_details),
    (r'^sessions/(?P<sessionid>\d+)/details/?$', details.session_details),
    (r'^patients/(?P<patientid>\d+)/details/?$', details.patient_details),

    # detail view commands
    (r'^patients/(?P<patientid>\d+)/command/?$', details.patient_command),
    (r'^processes/(?P<processid>\d+)/command/?$', details.process_command),
    (r'^tasks/(?P<taskid>\d+)/command/?$', details.scheduledtask_command),
    (r'^sessions/(?P<sessionid>\d+)/command/?$', details.session_command),

    # legacy scheduler views                   
    (r'^scheduler/?$', views.scheduler),
    (r'^scheduler/add/?$', views.add_scheduled_task),
    (r'^scheduler/check_service$', views.check_scheduler),

    # AJAX proxy
    (r'^proxy/(?P<url>.+)$', views.proxy),

    # ================================
    # ASAP forms
    # ================================
    (r'^ASAP/signup/?$', ASAP.signupform),
)
