from django import forms
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

from . import throttle
from .models import Tenant


class TenantLoginForm(forms.Form):
    """Login for tenant users: company, username and password. Works with Django's LoginView."""

    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(is_active=True),
        label=_('Company'),
        empty_label=_('Select company'),
    )
    username = forms.CharField(label=_('Username'), max_length=150)
    password = forms.CharField(label=_('Password'), strip=False, widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
        self.fields['tenant'].widget.attrs.update({'class': 'form-select', 'autofocus': True})
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'username'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'current-password'})

    def clean(self):
        cleaned_data = super().clean()
        tenant = cleaned_data.get('tenant')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        if tenant and username and password:
            if throttle.is_locked(tenant, username):
                raise forms.ValidationError(
                    _('Too many failed login attempts. Try again in %(minutes)d minutes.')
                    % {'minutes': throttle.LOCK_MINUTES})
            self.user_cache = authenticate(self.request, username=username, password=password, tenant=tenant)
            if self.user_cache is None:
                raise forms.ValidationError(_('Invalid company, username or password.'))
        return cleaned_data

    def get_user(self):
        return self.user_cache
