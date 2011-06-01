from django.contrib import admin
from models import *

admin.site.register(Patient)
admin.site.register(Clinician)

admin.site.register(Task)
admin.site.register(TaskTemplate)

admin.site.register(Process)
admin.site.register(TaskInstance)
admin.site.register(LogMessage)

admin.site.register(Service)
admin.site.register(AlertType)
admin.site.register(Alert)

# admin visibility for scheduled message reminders
admin.site.register(TaskEventSchedule)

