from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    # Placeholder start page; replaced by the real pages in later phases
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]
