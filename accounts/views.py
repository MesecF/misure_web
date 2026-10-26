from django.contrib.auth.views import LoginView

from .forms import TenantLoginForm


class TenantLoginView(LoginView):
    form_class = TenantLoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
