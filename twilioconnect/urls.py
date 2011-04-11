from django.conf.urls.defaults import patterns, include, url
import views

urlpatterns = patterns('twilioconnect.views',
    # main and only page
    url(r'^incoming/?', 'incoming'),
)
