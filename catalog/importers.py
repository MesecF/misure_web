"""
CSV import of articles and elements.

File format: ';' delimiter, first row is a header and is ignored. Excel saves CSV either as
UTF-8 or Windows-1250, both are accepted. Rows with errors are rejected and reported; all
valid rows are imported.

Articles: code; color; size; category code; barcode (EAN-13).
An existing barcode updates that article (an inactive article stays inactive).
Code, color and size are converted to upper case. Both the barcode and the
combination of code, color and size must be unique.

Elements: code; name; unit of measure.
Only new elements are imported: a code that already exists (also inactive) is rejected.
The code is converted to upper case.
"""

import csv
import io
from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Article, Category, Element
from .validators import ean13_is_valid

COLUMNS = ['code', 'color', 'size', 'category', 'barcode']
UPDATABLE_FIELDS = ['code', 'color', 'size', 'category']
ELEMENT_COLUMNS = ['code', 'name', 'unit']


@dataclass
class RejectedRow:
    line: int
    content: str
    reasons: list


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: list = field(default_factory=list)


class InvalidFile(Exception):
    """The upload is not a text CSV file (e.g. an Excel workbook or another encoding)."""


def decode(data):
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text = data.decode('cp1250')
        except UnicodeDecodeError:
            raise InvalidFile from None
    # Binary files (.xlsx) and UTF-16 text contain NUL characters, a CSV file never does
    if '\0' in text:
        raise InvalidFile
    return text


def read_rows(data):
    """
    (line number, values) of the non-empty data rows of the CSV file content; the header is line 1.
    Raises InvalidFile when the content cannot be read as CSV.
    """
    try:
        rows = list(csv.reader(io.StringIO(decode(data), newline=''), delimiter=';'))
    except csv.Error:
        # e.g. an opening quote that is never closed makes the rest of the file one huge field
        raise InvalidFile from None
    return [(number, row) for number, row in enumerate(rows[1:], start=2) if any(v.strip() for v in row)]


def split_columns(row, columns):
    """Returns (values, reasons): stripped values by column name, or None when the column count is wrong."""
    if len(row) < len(columns):
        return None, [_('Expected %(count)d columns, found %(found)d.') % {'count': len(columns), 'found': len(row)}]
    if any(value.strip() for value in row[len(columns):]):
        return None, [_('Too many columns.')]
    return dict(zip(columns, (value.strip() for value in row))), []


def import_articles(data, tenant, user):
    """Imports articles from the CSV file content (bytes) into the tenant."""
    result = ImportResult()
    parsed = [(number, row, *parse_row(row)) for number, row in read_rows(data)]

    # Duplicates are looked for within the file and against the tenant's existing articles
    barcode_counts = Counter(values['barcode'] for *_ignored, values, _reasons in parsed if values)
    variant_counts = Counter(variant_of(values) for *_ignored, values, _reasons in parsed if values)
    categories = {category.code.lower(): category for category in Category.objects.filter(tenant=tenant)}
    barcode_by_variant = {
        variant_of(article): article.barcode
        for article in Article.objects.filter(tenant=tenant).only(*Article.TEXT_FIELDS, 'barcode')
    }

    valid = []
    for number, row, values, reasons in parsed:
        if values:
            reasons = validate_values(values, categories, barcode_counts, variant_counts, barcode_by_variant)
        if reasons:
            result.rejected.append(RejectedRow(number, ';'.join(row), reasons))
        else:
            valid.append(values)

    # With the category, so comparing it below does not run a query per article
    existing = {a.barcode: a for a in Article.objects.filter(tenant=tenant, barcode__in=[v['barcode'] for v in valid])
                .select_related('category')}
    now = timezone.now()
    to_create, to_update = [], []
    for values in valid:
        article = existing.get(values['barcode'])
        if article is None:
            to_create.append(Article(tenant=tenant, created_by=user, **values))
        elif any(getattr(article, name) != values[name] for name in UPDATABLE_FIELDS):
            for name in UPDATABLE_FIELDS:
                setattr(article, name, values[name])
            article.updated_at = now
            article.updated_by = user
            to_update.append(article)
        else:
            result.unchanged += 1

    with transaction.atomic():
        Article.objects.bulk_create(to_create, batch_size=500)
        Article.objects.bulk_update(to_update, UPDATABLE_FIELDS + ['updated_at', 'updated_by'], batch_size=500)
    result.created = len(to_create)
    result.updated = len(to_update)
    return result


def variant_of(record):
    """(code, color, size) of an article or of a row's values."""
    if isinstance(record, dict):
        return tuple(record[name] for name in Article.TEXT_FIELDS)
    return tuple(getattr(record, name) for name in Article.TEXT_FIELDS)


def parse_row(row):
    """Returns (values, reasons): values are None when the column count is wrong."""
    values, reasons = split_columns(row, COLUMNS)
    if values:
        for name in Article.TEXT_FIELDS:
            values[name] = Article.normalize(values[name])
    return values, reasons


def validate_values(values, categories, barcode_counts, variant_counts, barcode_by_variant):
    """Returns the reasons for rejecting the row; empty when it is valid. Replaces the category code with the category."""
    reasons = []
    labels = {'code': _('Code'), 'color': _('Color'), 'size': _('Size'), 'category': _('Category'), 'barcode': _('Barcode')}
    for name in COLUMNS:
        if not values[name]:
            reasons.append(_('%(field)s is empty.') % {'field': labels[name]})
    for name in Article.TEXT_FIELDS:
        max_length = Article._meta.get_field(name).max_length
        if len(values[name]) > max_length:
            reasons.append(_('%(field)s is longer than %(max)d characters.') % {'field': labels[name], 'max': max_length})

    if values['category']:
        category = categories.get(values['category'].lower())
        if category is None:
            reasons.append(_('Category "%(code)s" does not exist.') % {'code': values['category']})
        elif not category.is_active:
            reasons.append(_('Category "%(code)s" is inactive.') % {'code': values['category']})
        values['category'] = category

    if values['barcode']:
        if not ean13_is_valid(values['barcode']):
            reasons.append(_('"%(value)s" is not a valid EAN-13 barcode.') % {'value': values['barcode']})
        elif barcode_counts[values['barcode']] > 1:
            reasons.append(_('Barcode appears more than once in the file.'))

    variant = variant_of(values)
    if all(variant):
        if variant_counts[variant] > 1:
            reasons.append(_('The same code, color and size appear more than once in the file.'))
        existing_barcode = barcode_by_variant.get(variant)
        if existing_barcode and existing_barcode != values['barcode']:
            reasons.append(_('An article with this code, color and size already exists (barcode %(barcode)s).')
                           % {'barcode': existing_barcode})

    return reasons


def import_elements(data, tenant, user):
    """Imports new elements from the CSV file content (bytes) into the tenant."""
    result = ImportResult()
    parsed = []
    for number, row in read_rows(data):
        values, reasons = split_columns(row, ELEMENT_COLUMNS)
        if values:
            values['code'] = Element.normalize_code(values['code'])
        parsed.append((number, row, values, reasons))

    code_counts = Counter(values['code'] for *_ignored, values, _reasons in parsed if values)
    existing = {element.code.upper(): element for element in Element.objects.filter(tenant=tenant)}

    to_create = []
    for number, row, values, reasons in parsed:
        if values:
            reasons = validate_element(values, code_counts, existing)
        if reasons:
            result.rejected.append(RejectedRow(number, ';'.join(row), reasons))
        else:
            to_create.append(Element(tenant=tenant, created_by=user, **values))

    Element.objects.bulk_create(to_create)
    result.created = len(to_create)
    return result


def validate_element(values, code_counts, existing):
    """Returns the reasons for rejecting the element row; empty when it is valid."""
    reasons = []
    labels = {'code': _('Code'), 'name': _('Name'), 'unit': _('Unit')}
    for name in ELEMENT_COLUMNS:
        max_length = Element._meta.get_field(name).max_length
        if not values[name]:
            reasons.append(_('%(field)s is empty.') % {'field': labels[name]})
        elif len(values[name]) > max_length:
            reasons.append(_('%(field)s is longer than %(max)d characters.') % {'field': labels[name], 'max': max_length})
    code = values['code']
    if code:
        if code_counts[code] > 1:
            reasons.append(_('Code appears more than once in the file.'))
        element = existing.get(code)
        if element is not None and element.is_active:
            reasons.append(_('Element "%(code)s" already exists.') % {'code': code})
        elif element is not None:
            reasons.append(_('Element "%(code)s" already exists and is inactive.') % {'code': code})
    return reasons
