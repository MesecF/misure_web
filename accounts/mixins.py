from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import timezone


class TenantRequiredMixin:
    """
    View is only for tenant users. Login itself is enforced by LoginRequiredMiddleware;
    a superadmin (no tenant) is sent to Django admin.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.tenant is None:
            return redirect('admin:index')
        return super().dispatch(request, *args, **kwargs)


class TenantAdminRequiredMixin(TenantRequiredMixin):
    """View is only for the tenant's admin user."""

    def dispatch(self, request, *args, **kwargs):
        if request.tenant is not None and not request.user.is_tenant_admin:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class TenantQuerysetMixin(TenantRequiredMixin):
    """Limits the view's queryset to the current tenant's records."""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)


class TenantAuditFormMixin:
    """
    For create/update views of AuditModel records: passes the tenant to the form,
    fills tenant and created_* on create, and updated_* when an existing record changes.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        record = form.instance
        if record.pk is None:
            record.tenant = self.request.tenant
            record.created_by = self.request.user
        elif form.has_changed():
            record.updated_at = timezone.now()
            record.updated_by = self.request.user
        return super().form_valid(form)
