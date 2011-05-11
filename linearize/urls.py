from django.conf.urls.defaults import patterns, include, url
import views

urlpatterns = patterns('linearize.views',
    # main and only page
    # url(r'/?', 'index'),
    url(r'formtest/?', 'formtest'),
)
