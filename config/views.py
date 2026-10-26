from django.views.generic import TemplateView

from accounts.mixins import TenantRequiredMixin


class HomeView(TenantRequiredMixin, TemplateView):
    template_name = 'home.html'
