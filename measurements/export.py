"""Export of the filtered measurements to Excel (.xlsx) and CSV."""

from django.utils.translation import gettext as _

from config.exports import csv_response, local, xlsx_response


def header(columns, include_deleted, element_names):
    """element_names: element columns titled by name instead of code, as chosen on the list page."""
    names = [_('Measured at'), _('Employee number'), _('Article code'), _('Color'), _('Size'), _('Barcode'),
             _('Category')]
    names += [f'{element.name if element_names else element.code} ({element.unit})' for element in columns]
    names += [_('Entered by'), _('Edited by'), _('Edited at')]
    if include_deleted:
        names += [_('Deleted by'), _('Deleted at')]
    return names


def rows(measurements, include_deleted):
    """Rows with typed values: datetimes, numbers and text."""
    for m in measurements:
        row = [local(m.measured_at), m.employee_number, m.article_code, m.article_color, m.article_size,
               m.article_barcode, m.category_code]
        row += m.element_values
        row += [m.created_by.username, m.updated_by.username if m.updated_by else None, local(m.updated_at)]
        if include_deleted:
            row += [m.deleted_by.username if m.deleted_by else None, local(m.deleted_at)]
        yield row


def to_xlsx(measurements, columns, include_deleted, element_names, filename):
    return xlsx_response(_('Measurements'), header(columns, include_deleted, element_names),
                         rows(measurements, include_deleted), filename)


def to_csv(measurements, columns, include_deleted, element_names, filename):
    return csv_response(header(columns, include_deleted, element_names), rows(measurements, include_deleted),
                        filename)
