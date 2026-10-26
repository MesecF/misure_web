from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Tenant, User


class TenantUserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(code='A', name='Company A')
        cls.tenant_b = Tenant.objects.create(code='B', name='Company B')
        cls.admin_a = User.objects.create_user('admin', password='pw-a', tenant=cls.tenant_a, role='admin')
        cls.admin_b = User.objects.create_user('admin', password='pw-b', tenant=cls.tenant_b, role='admin')
        cls.superadmin = User.objects.create_superuser('admin', password='pw-super')

    def test_same_username_authenticates_within_its_tenant(self):
        self.assertEqual(authenticate(username='admin', password='pw-a', tenant=self.tenant_a), self.admin_a)
        self.assertEqual(authenticate(username='admin', password='pw-b', tenant=self.tenant_b), self.admin_b)
        self.assertIsNone(authenticate(username='admin', password='pw-a', tenant=self.tenant_b))

    def test_login_without_tenant_only_finds_superadmin(self):
        self.assertEqual(authenticate(username='admin', password='pw-super'), self.superadmin)
        self.assertIsNone(authenticate(username='admin', password='pw-a'))

    def test_inactive_tenant_cannot_log_in(self):
        self.tenant_a.is_active = False
        self.tenant_a.save()
        self.assertIsNone(authenticate(username='admin', password='pw-a', tenant=self.tenant_a))

    def test_username_unique_per_tenant(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('admin', tenant=self.tenant_a, role='user')

    def test_one_user_per_role_per_tenant(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('second-admin', tenant=self.tenant_a, role='admin')

    def test_tenant_user_requires_role(self):
        user = User(username='norole', tenant=self.tenant_a, role='')
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_admin_add_user_allows_same_username_in_other_tenant(self):
        self.client.force_login(self.superadmin)
        data = {
            'tenant': self.tenant_b.pk,
            'role': 'user',
            'username': 'operator',
            'usable_password': 'true',
            'password1': 'Str0ng-pass-123',
            'password2': 'Str0ng-pass-123',
        }
        response = self.client.post('/admin/accounts/user/add/', {**data, 'tenant': self.tenant_a.pk})
        self.assertEqual(response.status_code, 302)
        response = self.client.post('/admin/accounts/user/add/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.filter(username='operator').count(), 2)

    def test_admin_add_user_rejects_second_admin_in_tenant(self):
        self.client.force_login(self.superadmin)
        response = self.client.post('/admin/accounts/user/add/', {
            'tenant': self.tenant_a.pk,
            'role': 'admin',
            'username': 'another',
            'usable_password': 'true',
            'password1': 'Str0ng-pass-123',
            'password2': 'Str0ng-pass-123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This tenant already has a user with this role.')
