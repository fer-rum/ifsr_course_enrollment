from django.conf.urls import patterns, include, url
from django.contrib import admin
from course_manager.views import View_Participants

import debug_toolbar

admin.autodiscover()
urlpatterns = patterns('',
                       url(r'^admin/', include(admin.site.urls)),
                       url(r'^kurse/', include('course_manager.urls', namespace="cmanagement")),
                       url(r'^$', View_Participants.index, name='index'),
                       url(r'^index/$', View_Participants.index, name='index'),
                       url(r'^_debug_/', include(debug_toolbar.urls))
                       )
