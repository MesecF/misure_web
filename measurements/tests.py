from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Tenant, User
from catalog.models import Article, Category, Element

from .entry import parse_value
from .models import Measurement


class ParseValueTests(SimpleTestCase):
    def test_accepted_values(self):
        cases = {'12': '12.0', '12.5': '12.5', '12,5': '12.5', ' 0 ': '0.0', '12.50': '12.5', '99999999.9': '99999999.9'}
        for text, expected in cases.items():
            self.assertEqual(parse_value(text), (Decimal(expected), None), text)

    def test_empty_value(self):
        self.assertEqual(parse_value('  '), (None, None))

    def test_rejected_values(self):
        for text in ['-1', '12.55', '1.2.3', 'abc', '123456789', '12.', '.5', '4006381333931']:
            value, error = parse_value(text)
            self.assertIsNone(value, text)
            self.assertIsNotNone(error, text)


class MeasurementEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(code='A', name='Company A')
        cls.other_tenant = Tenant.objects.create(code='B', name='Company B')
        cls.user = User.objects.create_user('operator', tenant=cls.tenant, role='user')
        admin = User.objects.create_user('admin', tenant=cls.tenant, role='admin')
        other_admin = User.objects.create_user('admin', tenant=cls.other_tenant, role='admin')
        cls.category = Category.objects.create(tenant=cls.tenant, code='NIKE', name='Nike', created_by=admin)
        cls.article = Article.objects.create(tenant=cls.tenant, code='A1', color='BLACK', size='M', category=cls.category,
                                             barcode='4006381333931', created_by=admin)
        common = {'tenant': cls.tenant, 'category': cls.category, 'unit': 'cm', 'created_by': admin}
        cls.length = Element.objects.create(code='L', name='Length', sort_order=10, **common)
        cls.width = Element.objects.create(code='W', name='Width', sort_order=20, **common)
        Element.objects.create(code='X', name='Old', sort_order=30, is_active=False, **common)
        other_category = Category.objects.create(tenant=cls.other_tenant, code='NIKE', name='Nike', created_by=other_admin)
        Article.objects.create(tenant=cls.other_tenant, code='B1', color='RED', size='S', category=other_category,
                               barcode='5901234123457', created_by=other_admin)

    def setUp(self):
        self.client.force_login(self.user)

    def panel(self, barcode, employee_number='123'):
        return self.client.get(reverse('measurements:article_panel'),
                               {'employee_number': employee_number, 'barcode': barcode})

    def save(self, values, barcode='4006381333931', employee_number='123'):
        data = {'employee_number': employee_number, 'barcode': barcode}
        data.update({f'element_{element.pk}': value for element, value in values.items()})
        return self.client.post(reverse('measurements:entry'), data)

    def test_entry_page_is_available_to_regular_user(self):
        response = self.client.get(reverse('measurements:entry'))
        self.assertEqual(response.status_code, 200)

    def test_scanned_barcode_shows_active_elements_in_order(self):
        response = self.panel('4006381333931')
        self.assertEqual(response.context['form'].elements, [self.length, self.width])
        self.assertContains(response, 'Length')
        self.assertNotContains(response, 'Old')

    def test_unknown_barcode_and_other_tenants_article(self):
        self.assertContains(self.panel('9780201379624'), 'No article with barcode 9780201379624.')
        self.assertContains(self.panel('5901234123457'), 'No article with barcode 5901234123457.')

    def test_inactive_article_and_category_are_refused(self):
        Article.objects.filter(pk=self.article.pk).update(is_active=False)
        self.assertContains(self.panel('4006381333931'), 'is inactive')
        Article.objects.filter(pk=self.article.pk).update(is_active=True)
        Category.objects.filter(pk=self.category.pk).update(is_active=False)
        self.assertContains(self.panel('4006381333931'), 'Category NIKE is inactive.')

    def test_category_without_elements(self):
        Element.objects.filter(category=self.category).update(is_active=False)
        self.assertContains(self.panel('4006381333931'), 'No elements are defined for category NIKE.')

    def test_employee_number_is_required_and_remembered(self):
        response = self.panel('4006381333931', employee_number='')
        self.assertContains(response, 'Enter the employee number.')
        self.assertContains(response, 'data-focus="employee_number"')
        self.assertContains(self.panel('4006381333931', employee_number='-5'), 'must be a positive whole number')
        self.panel('4006381333931', employee_number='4711')
        self.assertContains(self.client.get(reverse('measurements:entry')), 'value="4711"')

    def test_save_measurement_with_snapshot(self):
        response = self.save({self.length: '12,5', self.width: ''}, employee_number='4711')
        self.assertContains(response, 'Measurement saved at')
        measurement = Measurement.objects.get()
        self.assertEqual((measurement.employee_number, measurement.created_by, measurement.tenant),
                         (4711, self.user, self.tenant))
        self.assertEqual((measurement.article_code, measurement.article_color, measurement.article_size,
                          measurement.article_barcode, measurement.category_code, measurement.category_name),
                         ('A1', 'BLACK', 'M', '4006381333931', 'NIKE', 'Nike'))
        value = measurement.values.get()
        self.assertEqual((value.element, value.value, value.element_name, value.element_unit),
                         (self.length, Decimal('12.5'), 'Length', 'cm'))

    def test_after_saving_a_new_empty_form_for_same_article_is_shown(self):
        response = self.save({self.length: '12.5'})
        self.assertEqual(response.context['article'], self.article)
        self.assertEqual(response.context['form'].raw, {})
        self.assertEqual(len(response.context['todays_measurements']), 1)

    def test_at_least_one_value_is_required(self):
        response = self.save({self.length: '', self.width: ' '})
        self.assertContains(response, 'Enter at least one value.')
        self.assertFalse(Measurement.objects.exists())

    def test_invalid_value_keeps_entered_values(self):
        response = self.save({self.length: '12.5', self.width: '-3'})
        self.assertContains(response, 'at most one decimal place')
        self.assertContains(response, 'value="12.5"')
        self.assertFalse(Measurement.objects.exists())

    def test_several_measurements_of_same_article_today(self):
        self.save({self.length: '12.5'})
        response = self.save({self.width: '7'})
        self.assertEqual(Measurement.objects.count(), 2)
        rows = [m.element_values for m in response.context['todays_measurements']]
        self.assertEqual(rows, [[None, Decimal('7.0')], [Decimal('12.5'), None]])

    def test_deleted_measurements_are_not_listed(self):
        self.save({self.length: '12.5'})
        Measurement.objects.update(deleted_at='2026-01-01T00:00Z')
        self.assertEqual(self.panel('4006381333931').context['todays_measurements'], [])
