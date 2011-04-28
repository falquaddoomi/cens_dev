from django.db import models

# Create your models here.
class IncomingSMS(models.Model):
    received_time = models.DateTimeField(auto_now_add=True)
    get_data = models.TextField()
    post_data = models.TextField()
    headers = models.TextField()
    
    def __unicode__(self):
        return "Hit at %s" % (self.received_time.ctime())
