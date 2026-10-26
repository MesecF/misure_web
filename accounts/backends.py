from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class TenantModelBackend(ModelBackend):
    """
    Authenticates within a tenant, because usernames are only unique per tenant.
    Without a tenant (Django admin login) only superadmins are considered.
    """

    def authenticate(self, request, username=None, password=None, tenant=None, **kwargs):
        if username is None or password is None:
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
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
