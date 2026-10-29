from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Tenant(models.Model):
    """A company using the application. Every business record belongs to exactly one tenant."""

    code = models.CharField(_('code'), max_length=20, unique=True)
    name = models.CharField(_('name'), max_length=100)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'tenant'
        ordering = ['name']
        verbose_name = _('tenant')
        verbose_name_plural = _('tenants')

    def __str__(self):
        return self.name


class TenantUserManager(UserManager):
    def get_by_natural_key(self, username):
        # Usernames are unique per tenant, so a lookup by username alone
        # (Django admin login, createsuperuser) only targets superadmins.
        return self.get(**{self.model.USERNAME_FIELD: username, 'tenant__isnull': True})


class User(AbstractUser):
    """
    Superadmin: tenant is empty, manages tenants and users through Django admin.
    Tenant users: one 'admin' and one 'user' account per tenant.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', _('Administrator')
        USER = 'user', _('User')

    username = models.CharField(
        _('username'), max_length=150, validators=[UnicodeUsernameValidator()],
        help_text=_('Letters, digits and @ . + - _ only.'),
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('tenant'),
    )
    role = models.CharField(_('role'), max_length=10, choices=Role.choices, blank=True)

    objects = TenantUserManager()

    class Meta:
        db_table = 'app_user'
        ordering = ['tenant__name', 'username']
        verbose_name = _('user')
        verbose_name_plural = _('users')
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'username'],
                name='user_username_unique_per_tenant',
                violation_error_message=_('This tenant already has a user with this username.'),
            ),
            models.UniqueConstraint(
                fields=['username'],
                condition=Q(tenant__isnull=True),
                name='user_username_unique_superadmin',
                violation_error_message=_('A superadmin with this username already exists.'),
            ),
            models.UniqueConstraint(
                fields=['tenant', 'role'],
                name='user_one_role_per_tenant',
                violation_error_message=_('This tenant already has a user with this role.'),
            ),
            # A tenant user always has a role; a superadmin never has one
            models.CheckConstraint(
                condition=(Q(tenant__isnull=True) & Q(role='')) | (Q(tenant__isnull=False) & ~Q(role='')),
                name='user_role_matches_tenant',
                violation_error_message=_('Tenant users must have a role; superadmins must not have a tenant or role.'),
            ),
        ]

    @property
    def is_tenant_admin(self):
        return self.role == self.Role.ADMIN


class AuditModel(models.Model):
    """Who created a record and who last changed it. updated_* stay empty until the first change."""

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('created by'),
    )
    updated_at = models.DateTimeField(_('updated at'), null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('updated by'),
    )

    class Meta:
        abstract = True


class LoginFailure(models.Model):
    """A failed login attempt. Recent failures lock that username for a while (accounts/throttle.py)."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='+', verbose_name=_('tenant')
    )
    username = models.CharField(_('username'), max_length=150)
    failed_at = models.DateTimeField(_('failed at'), default=timezone.now)

    class Meta:
        db_table = 'login_failure'
        verbose_name = _('login failure')
        verbose_name_plural = _('login failures')
        indexes = [models.Index(fields=['username', 'failed_at'], name='login_failure_user_time_idx')]

    def __str__(self):
        return f'{self.username} @ {self.failed_at:%Y-%m-%d %H:%M}'
