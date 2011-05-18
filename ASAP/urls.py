#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.conf.urls.defaults import *

import ASAP.views

urlpatterns = patterns('',
    # ================================
    # ASAP forms
    # ================================
    (r'^signup/?$', ASAP.views.signupform),
    (r'^thanks/?$', ASAP.views.thanks),
    (r'^checkphone/?$', ASAP.views.checkphone),
    (r'^checkemail/?$', ASAP.views.checkemail)
)
