from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from . import throttle


class TenantModelBackend(ModelBackend):
    """
    Authenticates within a tenant, because usernames are only unique per tenant.
    Without a tenant (Django admin login) only superadmins are considered.
    """

    def authenticate(self, request, username=None, password=None, tenant=None, **kwargs):
        if username is None or password is None:
            return None
        # Too many recent failures: refused even with the right password (accounts/throttle.py)
        if throttle.is_locked(tenant, username):
            return None
        User = get_user_model()
        users = User._default_manager.filter(username=username)
        if tenant is None:
            users = users.filter(tenant__isnull=True)
        else:
            users = users.filter(tenant=tenant, tenant__is_active=True)
        user = users.first()
        if user is None:
            # Run the hasher anyway to keep response time the same as for a wrong password
            User().set_password(password)
        elif user.check_password(password) and self.user_can_authenticate(user):
            throttle.clear_failures(tenant, username)
            return user
        throttle.record_failure(tenant, username)
        return None
