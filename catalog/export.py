"""Export of the filtered articles and elements to Excel (.xlsx) and CSV."""

from django.utils.translation import gettext as _

from config.exports import csv_response, local, xlsx_response


def audit(record):
    """Active flag and who created and last changed the record."""
    return [_('Yes') if record.is_active else _('No'),
            record.created_by.username, local(record.created_at),
            record.updated_by.username if record.updated_by else None, local(record.updated_at)]


def audit_header():
    return [_('Active'), _('Created by'), _('Created at'), _('Changed by'), _('Changed at')]


def article_header():
    return [_('Code'), _('Color'), _('Size'), _('Category'), _('Category name'), _('Barcode'), *audit_header()]


def article_rows(articles):
    """Barcodes stay text, so Excel does not turn them into numbers."""
    for a in articles:
        yield [a.code, a.color, a.size, a.category.code, a.category.name, a.barcode, *audit(a)]


def element_header():
    return [_('Code'), _('Name'), _('Unit'), _('Categories'), *audit_header()]


def element_rows(elements):
    """Categories: codes of the categories the element is measured in."""
    for e in elements:
        categories = ', '.join(sorted(link.category.code for link in e.category_elements.all()))
        yield [e.code, e.name, e.unit, categories, *audit(e)]


def export(file_format, title, header, rows, filename):
    if file_format == 'xlsx':
        return xlsx_response(title, header, rows, filename)
    return csv_response(header, rows, filename)
