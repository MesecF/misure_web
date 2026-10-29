from datetime import timedelta

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from catalog.models import Category

from . import throttle
from .mixins import TenantAdminRequiredMixin, TenantQuerysetMixin
from .models import LoginFailure, Tenant, User


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

    def test_username_allows_only_letters_digits_and_some_signs(self):
        user = User(username='pero ivic!', tenant=self.tenant_a, role='user')
        with self.assertRaises(ValidationError) as error:
            user.full_clean()
        self.assertIn('username', error.exception.message_dict)
        User(username='pero.ivic_2@x', tenant=self.tenant_a, role='user', password='x').full_clean()

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


class LoginFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(code='A', name='Company A')
        cls.tenant_b = Tenant.objects.create(code='B', name='Company B')
        cls.admin_a = User.objects.create_user('admin', password='pw-a', tenant=cls.tenant_a, role='admin')
        cls.user_a = User.objects.create_user('operator', password='pw-op', tenant=cls.tenant_a, role='user')
        cls.superadmin = User.objects.create_superuser('root', password='pw-super')

    def login(self, tenant, username, password):
        return self.client.post(reverse('login'), {'tenant': tenant.pk, 'username': username, 'password': password})

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

    def test_login_with_correct_company(self):
        response = self.login(self.tenant_a, 'admin', 'pw-a')
        self.assertRedirects(response, reverse('home'))
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Company A')
        self.assertContains(response, 'Administration')

    def test_login_with_wrong_company_fails(self):
        response = self.login(self.tenant_b, 'admin', 'pw-a')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid company, username or password.')

    def test_too_many_failures_lock_the_username(self):
        for _attempt in range(throttle.MAX_FAILURES):
            self.assertContains(self.login(self.tenant_a, 'admin', 'wrong'), 'Invalid company, username or password.')
        # Locked: also the right password is refused, other users are not affected
        self.assertContains(self.login(self.tenant_a, 'admin', 'pw-a'), 'Too many failed login attempts.')
        self.assertRedirects(self.login(self.tenant_a, 'operator', 'pw-op'), reverse('home'))
        # After the lock time
        LoginFailure.objects.update(failed_at=timezone.now() - timedelta(minutes=throttle.LOCK_MINUTES + 1))
        self.client.logout()
        self.assertRedirects(self.login(self.tenant_a, 'admin', 'pw-a'), reverse('home'))

    def test_successful_login_clears_failures(self):
        self.login(self.tenant_a, 'admin', 'wrong')
        self.assertRedirects(self.login(self.tenant_a, 'admin', 'pw-a'), reverse('home'))
        self.assertFalse(LoginFailure.objects.exists())

    def test_django_admin_login_is_locked_too(self):
        for _attempt in range(throttle.MAX_FAILURES):
            self.assertIsNone(authenticate(username='root', password='wrong'))
        self.assertIsNone(authenticate(username='root', password='pw-super'))
        # The same username in a tenant is counted separately
        self.assertFalse(throttle.is_locked(self.tenant_a, 'root'))

    def test_ended_session_sends_htmx_request_to_login_page(self):
        response = self.client.get(reverse('measurements:article_panel'), {'barcode': '1'},
                                   HTTP_HX_REQUEST='true', HTTP_HX_CURRENT_URL='http://testserver/measurements/new/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], f"{reverse('login')}?next=%2Fmeasurements%2Fnew%2F")
        # Normal requests are redirected as usual
        self.assertEqual(self.client.get(reverse('measurements:article_panel')).status_code, 302)

    def test_inactive_company_is_not_offered(self):
        self.tenant_b.is_active = False
        self.tenant_b.save()
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Company A')
        self.assertNotContains(response, 'Company B')

    def test_regular_user_has_no_administration_menu(self):
        self.login(self.tenant_a, 'operator', 'pw-op')
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Administration')

    def test_logout(self):
        self.login(self.tenant_a, 'admin', 'pw-a')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertRedirects(self.client.get(reverse('home')), f"{reverse('login')}?next=/")

    def test_deactivating_company_logs_out_its_users(self):
        self.login(self.tenant_a, 'admin', 'pw-a')
        self.tenant_a.is_active = False
        self.tenant_a.save()
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

    def test_superadmin_is_sent_to_django_admin(self):
        self.client.force_login(self.superadmin)
        self.assertRedirects(self.client.get(reverse('home')), reverse('admin:index'))

    def test_default_language_is_english_regardless_of_browser(self):
        response = self.client.get(reverse('login'), headers={'accept-language': 'hr'})
        self.assertContains(response, '<html lang="en">')

    def test_language_can_be_changed_before_login(self):
        response = self.client.post(reverse('set_language'), {'language': 'it', 'next': reverse('login')})
        self.assertRedirects(response, reverse('login'))
        self.assertContains(self.client.get(reverse('login')), '<html lang="it">')

    def test_pages_are_translated(self):
        self.login(self.tenant_a, 'admin', 'pw-a')
        expected = {
            'hr': ['Novo mjerenje', 'Administracija', 'Odjava', 'Kategorije'],
            'it': ['Nuova misurazione', 'Amministrazione', 'Esci', 'Categorie'],
            'en': ['New measurement', 'Administration', 'Log out', 'Categories'],
        }
        for language, texts in expected.items():
            self.client.post(reverse('set_language'), {'language': language, 'next': '/'})
            response = self.client.get(reverse('home'))
            for text in texts:
                self.assertContains(response, text, msg_prefix=language)

    def test_login_error_is_translated(self):
        self.client.post(reverse('set_language'), {'language': 'hr', 'next': '/'})
        response = self.login(self.tenant_b, 'admin', 'pw-a')
        self.assertContains(response, 'Neispravna tvrtka, korisničko ime ili lozinka.')


class TenantMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_a = Tenant.objects.create(code='A', name='Company A')
        cls.tenant_b = Tenant.objects.create(code='B', name='Company B')
        cls.admin_a = User.objects.create_user('admin', tenant=cls.tenant_a, role='admin')
        cls.user_a = User.objects.create_user('operator', tenant=cls.tenant_a, role='user')
        admin_b = User.objects.create_user('admin', tenant=cls.tenant_b, role='admin')
        Category.objects.create(tenant=cls.tenant_a, code='BA', name='Category A', created_by=cls.admin_a)
        Category.objects.create(tenant=cls.tenant_b, code='BB', name='Category B', created_by=admin_b)

    def request_for(self, user):
        request = RequestFactory().get('/')
        request.user = user
        request.tenant = user.tenant
        return request

    def test_queryset_contains_only_own_tenant_records(self):
        class CategoryList(TenantQuerysetMixin, ListView):
            model = Category

        view = CategoryList()
        view.setup(self.request_for(self.admin_a))
        self.assertEqual([b.code for b in view.get_queryset()], ['BA'])

    def test_admin_only_view_rejects_regular_user(self):
        class AdminOnly(TenantAdminRequiredMixin, View):
            def get(self, request):
                return HttpResponse('ok')

        self.assertEqual(AdminOnly.as_view()(self.request_for(self.admin_a)).status_code, 200)
        with self.assertRaises(PermissionDenied):
            AdminOnly.as_view()(self.request_for(self.user_a))
