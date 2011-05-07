from django.db import models

class ASAPParticipant(models.Model):
    name = models.CharField(max_length=100)
    birth_date = models.DateField(blank=True, null=True)

    def __unicode__(self):
        return self.name
