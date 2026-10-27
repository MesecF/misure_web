"""Export of the filtered articles to Excel (.xlsx) and CSV."""

from django.utils.translation import gettext as _

from config.exports import csv_response, local, xlsx_response


def header():
    return [_('Code'), _('Color'), _('Size'), _('Category'), _('Category name'), _('Barcode'), _('Active'),
            _('Created by'), _('Created at'), _('Changed by'), _('Changed at')]


def rows(articles):
    """Barcodes stay text, so Excel does not turn them into numbers."""
    for a in articles:
        yield [a.code, a.color, a.size, a.category.code, a.category.name, a.barcode,
               _('Yes') if a.is_active else _('No'),
               a.created_by.username, local(a.created_at),
               a.updated_by.username if a.updated_by else None, local(a.updated_at)]


def to_xlsx(articles, filename):
    return xlsx_response(_('Articles'), header(), rows(articles), filename)


def to_csv(articles, filename):
    return csv_response(header(), rows(articles), filename)
