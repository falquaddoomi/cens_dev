from django.db import models
from django.db.models import Q

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

    def get_diagnoses_names(self):
        return self.diagnoses.values_list("proper_name", flat=True)

    def get_area(self):
        for d in ASAPParticipant.areas:
            if self.zipcode in ASAPParticipant.areas[d]:
                return d
        return None

    def is_adult(self):
        return self.age >= 18

    # resource listings; separate funcs so we can invoke them from the template
    def get_applicable_resources(self,category):
        # initial filter on category and area
        result = Resource.objects.filter(category=category).filter(Q(area=self.get_area)|Q(area=None))
        # exclude age-inappropriate resources
        if self.is_adult:
            result = result.exclude(for_under18=True)
        else:
            result = result.exclude(for_over18=True)
        # match their diagnoses, finally
        result = result.filter(diagnoses__in=Diagnosis.objects.filter(asapparticipant=self))|result.exclude(mmfield__id__isnull=False)
        return result
        
    def get_online_resource(self):
        try:
            return self.get_applicable_resources("online")[0]
        except:
            return None

    def get_peer_resource(self):
        try:
            return self.get_applicable_resources("peer")[0]
        except:
            return None

    def get_1on1_resource(self):
        try:
            return self.get_applicable_resources("1on1")[0]
        except:
            return None

    class Meta:
        verbose_name = "ASAP Participant"
    
    def __unicode__(self):
        return "%s %s (ASAP)" % (self.firstname, self.lastname)

    # ==
    # == list of zipcodes (silly, i know)
    # == who knows, maybe we'll move this to the db someday
    # == from http://zipcodes.addresses.com/zip_codes_by_city/
    # ==

    areas = {
        'Sherman Oaks': [
            "91401", 
            "91403", 
            "91411", 
            "91413", 
            "91423", 
            "91495"
        ],
        'Bakersfield': [
            "93263", 
            "93301", 
            "93302", 
            "93303", 
            "93304", 
            "93305", 
            "93306", 
            "93307", 
            "93308", 
            "93309", 
            "93311", 
            "93312", 
            "93313", 
            "93314", 
            "93380", 
            "93383", 
            "93384", 
            "93385", 
            "93386", 
            "93387", 
            "93388", 
            "93389", 
            "93390"
        ],
        'Santa Barbara': [
            "93101", 
            "93102", 
            "93103", 
            "93105", 
            "93106", 
            "93107", 
            "93108", 
            "93109", 
            "93110", 
            "93111", 
            "93116", 
            "93117", 
            "93118", 
            "93120", 
            "93121", 
            "93130", 
            "93140", 
            "93150", 
            "93160", 
            "93190", 
            "93199"
        ]
    }

class Resource(models.Model):
    CATEGORY_CHOICES = (
        ('online', 'Online'),
        ('peer', 'Peer Group'),
        ('1on1', 'One on One'),
        ('outdoor', 'Outdoor Adventure'),
        ('indoor', 'In-door Activities'),
    )
    AREA_CHOICES = (
        ('Sherman Oaks', 'Sherman Oaks'),
        ('Bakersfield', 'Bakersfield'),
        ('Santa Barbara', 'Santa Barbara'),
    )
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    text = models.TextField()
    area = models.CharField(max_length=100, choices=AREA_CHOICES,null=True,blank=True)
    diagnoses = models.ManyToManyField(Diagnosis, verbose_name="diagnoses",blank=True)
    for_over18 = models.BooleanField()
    for_under18 = models.BooleanField()

    def __unicode__(self):
        return "%s (area: %s): %s" % (self.category, self.area, self.text)
