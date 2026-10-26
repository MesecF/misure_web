"""
CSV import of articles.

File format: ';' delimiter, first row is a header and is ignored, columns in this order:
code; color; size; category code; barcode (EAN-13). Excel saves CSV either as UTF-8 or
Windows-1250, both are accepted.

Rows with errors are rejected and reported; all valid rows are imported.
An existing barcode updates that article (an inactive article stays inactive).
Code, color and size are converted to upper case. Both the barcode and the
combination of code, color and size must be unique.
"""

import csv
import io
from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Article, Category
from .validators import ean13_is_valid

COLUMNS = ['code', 'color', 'size', 'category', 'barcode']
UPDATABLE_FIELDS = ['code', 'color', 'size', 'category']


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


def decode(data):
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1250')


def import_articles(data, tenant, user):
    """Imports articles from the CSV file content (bytes) into the tenant."""
    result = ImportResult()
    rows = list(csv.reader(io.StringIO(decode(data), newline=''), delimiter=';'))

    # (line number, values) of non-empty data rows; the header is line 1
    data_rows = [(number, row) for number, row in enumerate(rows[1:], start=2) if any(v.strip() for v in row)]

    parsed = [(number, row, *parse_row(row)) for number, row in data_rows]

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

    existing = {a.barcode: a for a in Article.objects.filter(tenant=tenant, barcode__in=[v['barcode'] for v in valid])}
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
    if len(row) < len(COLUMNS):
        return None, [_('Expected %(count)d columns, found %(found)d.') % {'count': len(COLUMNS), 'found': len(row)}]
    if any(value.strip() for value in row[len(COLUMNS):]):
        return None, [_('Too many columns.')]
    values = dict(zip(COLUMNS, (value.strip() for value in row)))
    for name in Article.TEXT_FIELDS:
        values[name] = Article.normalize(values[name])
    return values, []


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
