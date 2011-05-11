from django.db import models

from taskmanager.models import *

# =================================================================
# ==== ASAP data, both static and dynamic
# =================================================================

class Diagnosis(models.Model):
    proper_name = models.CharField(max_length=100)
    
    def __unicode__(self):
        return "%s" % (self.proper_name)
    
    class Meta:
        verbose_name_plural = "Diagnoses"

class ASAPGoalCategory(models.Model):
    name = models.CharField(max_length=100)
    html_name = models.CharField(max_length=100)
    col_name = models.CharField(max_length=100)
    order = models.IntegerField(blank=True,null=True)

    class Meta:
        verbose_name = "ASAP Goal Category"
        verbose_name_plural = "ASAP Goal Categories"
        ordering = ["order"]

    def __unicode__(self):
        return "%s" % (self.col_name)

class ASAPGoal(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ASAPGoalCategory)
    order = models.IntegerField(blank=True,null=True)
    tasktemplate = models.ForeignKey(TaskTemplate,blank=True,null=True)

    class Meta:
        verbose_name = "ASAP Goal"
        verbose_name_plural = "ASAP Goals"
        ordering = ["order"]

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.category.col_name)
    
class ASAPParticipant(models.Model):
    patient = models.OneToOneField(Patient)
    
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    cellphone = models.CharField(max_length=100)
    email = models.EmailField()
    age = models.IntegerField(blank=True,null=True)
    zipcode = models.CharField(max_length=30,blank=True,null=True)
    diagnoses = models.ManyToManyField(Diagnosis, verbose_name="diagnoses")
    other_diagnosis = models.CharField(max_length=100,blank=True)
    questionnaire_pref = models.CharField(max_length=100)
    goals = models.ManyToManyField(ASAPGoal, verbose_name="goals")

    class Meta:
        verbose_name = "ASAP Participant"
    
    def __unicode__(self):
        return "%s %s (ASAP)" % (self.firstname, self.lastname)
