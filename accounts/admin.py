from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import Tenant, User


class TenantUserFormMixin:
    def clean_username(self):
        # Uniqueness is per tenant and is checked by the model constraints,
        # not globally as in Django's default form.
        return self.cleaned_data['username']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('tenant') and (cleaned_data.get('is_staff') or cleaned_data.get('is_superuser')):
            raise forms.ValidationError(_('Tenant users cannot have staff or superuser access.'))
        return cleaned_data


class TenantUserCreationForm(TenantUserFormMixin, AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('tenant', 'role', 'username')


class TenantUserChangeForm(TenantUserFormMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = TenantUserChangeForm
    add_form = TenantUserCreationForm
    list_display = ('username', 'tenant', 'role', 'is_active', 'is_superuser', 'last_login')
    list_filter = ('tenant', 'role', 'is_active', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('tenant', 'role', 'username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('tenant', 'role', 'username', 'usable_password', 'password1', 'password2'),
        }),
    )
