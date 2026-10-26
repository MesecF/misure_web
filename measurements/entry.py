"""Measurement entry: looking up the scanned article, validating the entered values and saving."""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from catalog.models import Article, Element

from .models import Measurement, MeasurementValue

MAX_EMPLOYEE_NUMBER = 2147483647

# Up to 8 digits before the decimal point and one after; extra trailing zeros
# (e.g. "12.50" from a measuring device) are accepted
VALUE_PATTERN = re.compile(r'^(\d{1,8})(?:\.(\d)0*)?$')


def parse_employee_number(text):
    """Returns (number, error)."""
    text = (text or '').strip()
    if not text:
        return None, _('Enter the employee number.')
    if not text.isdigit() or not 0 < int(text) <= MAX_EMPLOYEE_NUMBER:
        return None, _('The employee number must be a positive whole number.')
    return int(text), None


def find_article(tenant, barcode):
    """Returns (article, error) for a scanned barcode."""
    barcode = (barcode or '').strip()
    if not barcode:
        return None, _('Scan the article barcode.')
    article = Article.objects.select_related('category').filter(tenant=tenant, barcode=barcode).first()
    if article is None:
        return None, _('No article with barcode %(barcode)s.') % {'barcode': barcode}
    if not article.is_active:
        return None, _('Article %(article)s is inactive.') % {'article': article}
    if not article.category.is_active:
        return None, _('Category %(category)s is inactive.') % {'category': article.category.code}
    return article, None


def elements_for(article):
    return list(Element.objects.filter(category=article.category, is_active=True).order_by('sort_order', 'code'))


def parse_value(text):
    """Returns (value, error); value is None for an empty field."""
    text = (text or '').strip().replace(',', '.')
    if not text:
        return None, None
    match = VALUE_PATTERN.match(text)
    if not match:
        return None, _('Enter a number of 0 or more with at most one decimal place.')
    return Decimal(f'{match.group(1)}.{match.group(2) or 0}'), None


@dataclass
class EntryForm:
    """Values entered for the elements of one article, keyed by element id."""

    elements: list
    raw: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    error: str = ''

    @classmethod
    def from_post(cls, elements, data):
        form = cls(elements, raw={e.pk: data.get(f'element_{e.pk}', '') for e in elements})
        for element in elements:
            value, error = parse_value(form.raw[element.pk])
            if error:
                form.errors[element.pk] = error
            elif value is not None:
                form.values[element.pk] = value
        if not form.errors and not form.values:
            form.error = _('Enter at least one value.')
        return form

    @property
    def is_valid(self):
        return not self.errors and not self.error

    def rows(self):
        """(element, entered text, error) for the template."""
        return [(e, self.raw.get(e.pk, ''), self.errors.get(e.pk)) for e in self.elements]


def save_measurement(article, employee_number, form, user):
    with transaction.atomic():
        measurement = Measurement(
            tenant=article.tenant,
            article=article,
            employee_number=employee_number,
            measured_at=timezone.now(),
            created_by=user,
        )
        measurement.copy_article_data()
        measurement.save()
        values = []
        for element in form.elements:
            if element.pk in form.values:
                value = MeasurementValue(measurement=measurement, element=element, value=form.values[element.pk])
                value.copy_element_data()
                values.append(value)
        MeasurementValue.objects.bulk_create(values)
    return measurement


def todays_measurements(article, elements):
    """
    Today's (local time) measurements of the article, newest first.
    Each gets element_values: its values in the order of elements (None where empty).
    """
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    measurements = list(
        Measurement.objects.filter(article=article, deleted_at__isnull=True, measured_at__gte=start)
        .prefetch_related('values')
        .order_by('-measured_at')
    )
    for measurement in measurements:
        value_by_element = {v.element_id: v.value for v in measurement.values.all()}
        measurement.element_values = [value_by_element.get(element.pk) for element in elements]
    return measurements
