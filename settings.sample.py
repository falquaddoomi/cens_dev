#!/home/faisal/checkouts/dev/dev_virtual/bin/python
# vim: ai ts=4 sts=4 et sw=4
# encoding=utf-8

# -------------------------------------------------------------------- #
#                          MAIN CONFIGURATION                          #
# -------------------------------------------------------------------- #

# django
TIME_ZONE = 'US/Pacific'
DBTEMPLATES_USE_REVERSION = True
AUTH_PROFILE_MODULE = "taskmanager.Clinician"
LOGIN_URL = "/taskmanager/login"

# you should configure your database here before doing any real work.
# see: http://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "rapidsms.sqlite3",
    }
}


# the rapidsms backend configuration is designed to resemble django's
# database configuration, as a nested dict of (name, configuration).
#
# the ENGINE option specifies the module of the backend; the most common
# backend types (for a GSM modem or an SMPP server) are bundled with
# rapidsms, but you may choose to write your own.
#
# all other options are passed to the Backend when it is instantiated,
# to configure it. see the documentation in those modules for a list of
# the valid options for each.
INSTALLED_BACKENDS = {
    #"att": {
    #    "ENGINE": "rapidsms.backends.gsm",
    #    "PORT": "/dev/ttyUSB0"
    #},
    #"verizon": {
    #    "ENGINE": "rapidsms.backends.gsm,
    #    "PORT": "/dev/ttyUSB1"
    #},
    "message_tester": {
        "ENGINE": "rapidsms.backends.bucket",
    },
    "irc": {
        "ENGINE": "rapidsms.backends.irc",
        "host": "irc.freenode.net",
        "channels": ["##cens_testing"],
        "nick": "CENS_Listener"
    },
    "clickatell": {
        "ENGINE":  "rapidsms.backends.clickatell", 
        "port": 8005,
        "gateway_url": "http://api.clickatell.com/http/sendmsg",
        "api_id": "<clickatell api key>",
        "username": "<clickatell username>",
        "password": "<clickatell password>",
        "phone_no": "<clickatell number>"
    }
}


# to help you get started quickly, many django/rapidsms apps are enabled
# by default. you may wish to remove some and/or add your own.
INSTALLED_APPS = [

    # the essentials.
    "django_nose",
    "djtables",
    "rapidsms",

    # common dependencies (which don't clutter up the ui).
    "rapidsms.contrib.handlers",
    "rapidsms.contrib.ajax",

    # enable the django admin using a little shim app (which includes
    # the required urlpatterns), and a bunch of undocumented apps that
    # the AdminSite seems to explode without.
    "django.contrib.sites",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.contenttypes",

    # the rapidsms contrib apps.
    "rapidsms.contrib.default",
    "rapidsms.contrib.export",
    "rapidsms.contrib.httptester",
    # "rapidsms.contrib.locations",
    "rapidsms.contrib.messagelog",
    "rapidsms.contrib.messaging",
    "rapidsms.contrib.registration",
    "rapidsms.contrib.scheduler",
    "rapidsms.contrib.echo",

    # for django-reversion - http://wiki.github.com/etianen/django-reversion/getting-started
    "reversion",
    "dbtemplates",
    # for South - http://south.aeracode.org/docs/index.html
    "south",
    # our apps
    "taskmanager",
    "linearize",
    "twilioconnect"
]


# this rapidsms-specific setting defines which views are linked by the
# tabbed navigation. when adding an app to INSTALLED_APPS, you may wish
# to add it here, also, to expose it in the rapidsms ui.
RAPIDSMS_TABS = [
    ("rapidsms.contrib.messagelog.views.message_log",       "Message Log"),
    ("rapidsms.contrib.registration.views.registration",    "Registration"),
    ("rapidsms.contrib.messaging.views.messaging",          "Messaging"),
    # ("rapidsms.contrib.locations.views.locations",          "Map"),
    ("rapidsms.contrib.scheduler.views.index",              "Event Scheduler"),
    ("rapidsms.contrib.httptester.views.generate_identity", "Message Tester"),
]


# -------------------------------------------------------------------- #
#                         BORING CONFIGURATION                         #
# -------------------------------------------------------------------- #


# debug mode is turned on as default, since rapidsms is under heavy
# development at the moment, and full stack traces are very useful
# when reporting bugs. don't forget to turn this off in production.
DEBUG = TEMPLATE_DEBUG = True


# after login (which is handled by django.contrib.auth), redirect to the
# dashboard rather than 'accounts/profile' (the default).
LOGIN_REDIRECT_URL = "/"


# use django-nose to run tests. rapidsms contains lots of packages and
# modules which django does not find automatically, and importing them
# all manually is tiresome and error-prone.
TEST_RUNNER = "django_nose.NoseTestSuiteRunner"


# for some reason this setting is blank in django's global_settings.py,
# but it is needed for static assets to be linkable.
MEDIA_URL = "/static/"


# ==== BEGIN NORMAL DJANGO STUFF =======================================

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# ==== END NORMAL DJANGO STUFF =========================================

# this is required for the django.contrib.sites tests to run, but also
# not included in global_settings.py, and is almost always ``1``.
# see: http://docs.djangoproject.com/en/dev/ref/contrib/sites/
SITE_ID = 1


# the default log settings are very noisy.
LOG_LEVEL = "INFO"
LOG_FILE = "rapidsms.log"
LOG_FORMAT = "[%(name)s]: %(message)s"
LOG_SIZE = 1024*16  # 16 kb
LOG_BACKUPS = 8  # number of logs to keep


# these weird dependencies should be handled by their respective apps,
# but they're not, so here they are. most of them are for django admin.
TEMPLATE_CONTEXT_PROCESSORS = [
    # "django.core.context_processors.auth", # deprecated!
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
]


# -------------------------------------------------------------------- #
#                           HERE BE DRAGONS!                           #
#        these settings are pure hackery, and will go away soon        #
# -------------------------------------------------------------------- #


# these apps should not be started by rapidsms in your tests, however,
# the models and bootstrap will still be available through django.
TEST_EXCLUDED_APPS = [
    "django.contrib.sessions",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rapidsms",
    "rapidsms.contrib.ajax",
    "rapidsms.contrib.httptester",
]

# the project-level url patterns
ROOT_URLCONF = "urls"


# since we might hit the database from any thread during testing, the
# in-memory sqlite database isn't sufficient. it spawns a separate
# virtual database for each thread, and syncdb is only called for the
# first. this leads to confusing "no such table" errors. We create
# a named temporary instance instead.
import os, tempfile, sys

if 'test' in sys.argv:
    for db_name in DATABASES:
        DATABASES[db_name]['TEST_NAME'] = os.path.join(
            tempfile.gettempdir(),
            "%s.rapidsms.test.sqlite3" % db_name)

# FAISAL: ok, i realize this is bad juju, but it's just for testing purposes
# we're monkeypatching the AJAX proxy port to prevent conflicts with the existing framework instance
import rapidsms.contrib.ajax.settings

rapidsms.contrib.ajax.settings.AJAX_PROXY_PORT = 8012

# scheduler settings, reliant on the port defined above
SCHEDULER_TARGET_URL = 'http://localhost:%d/taskmanager/' % (rapidsms.contrib.ajax.settings.AJAX_PROXY_PORT)
# SCHEDULER_QUIET_HOURS = {'start': 22, 'end': 8}
SCHEDULER_QUIET_HOURS = None # disables quiet hours
SCHEDULER_CHECK_INTERVAL = 15 # time in seconds between polls of the database
