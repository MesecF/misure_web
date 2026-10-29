from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from django.views.i18n import set_language

from accounts.views import TenantLoginView

from .views import HelpView, HomeView

urlpatterns = [
    path('admin/', admin.site.urls),
    # The language can be changed on the login page too
    path('i18n/setlang/', login_not_required(set_language), name='set_language'),
    path('login/', TenantLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('catalog/', include('catalog.urls')),
    path('measurements/', include('measurements.urls')),
    path('help/', HelpView.as_view(), name='help'),
    path('', HomeView.as_view(), name='home'),
]
