from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views import View

from accounts.mixins import TenantAdminRequiredMixin, TenantRequiredMixin
from catalog.models import Category, CategoryElement

from .entry import (EntryForm, elements_for, find_article, parse_employee_number, save_measurement,
                    todays_measurements, update_measurement)
from .export import to_csv, to_xlsx
from .listing import MeasurementFilter, attach_values
from .models import Measurement

SESSION_EMPLOYEE_NUMBER = 'employee_number'


class MeasurementEntryView(TenantRequiredMixin, View):
    """
    Entry page. The article panel (elements and today's measurements) is loaded
    with HTMX when a barcode is scanned and replaced after each save.
    """

    def get(self, request):
        return render(request, 'measurements/entry.html', {
            'employee_number': request.session.get(SESSION_EMPLOYEE_NUMBER, ''),
        })

    def post(self, request):
        employee_number, article, error, error_field = self.check_employee_and_article(request, request.POST)
        if error:
            return self.render_panel(request, error=error, error_field=error_field)
        elements = elements_for(article)
        form = EntryForm.from_post(elements, request.POST)
        if not form.is_valid:
            return self.render_panel(request, article=article, form=form)
        measurement = save_measurement(article, employee_number, form, request.user)
        # A new measurement starts right away for the same article and employee
        return self.render_panel(request, article=article, form=EntryForm(elements), saved=measurement)

    @staticmethod
    def check_employee_and_article(request, data):
        """
        Returns (employee_number, article, error, error_field); error_field is the input
        the cursor goes back to. A valid employee number is remembered for the session.
        """
        employee_number, error = parse_employee_number(data.get('employee_number'))
        if error:
            return None, None, error, 'employee_number'
        request.session[SESSION_EMPLOYEE_NUMBER] = employee_number
        article, error = find_article(request.tenant, data.get('barcode'))
        return employee_number, article, error, 'barcode' if error else ''

    @staticmethod
    def render_panel(request, article=None, form=None, error='', error_field='', saved=None):
        context = {'article': article, 'form': form, 'error': error, 'error_field': error_field, 'saved': saved}
        if article is not None:
            context['todays_measurements'] = todays_measurements(article, form.elements)
        return render(request, 'measurements/partials/article_panel.html', context)


class ArticlePanelView(MeasurementEntryView):
    """HTMX: panel for the scanned barcode."""

    http_method_names = ['get']

    def get(self, request):
        employee_number, article, error, error_field = self.check_employee_and_article(request, request.GET)
        if error:
            return self.render_panel(request, error=error, error_field=error_field)
        return self.render_panel(request, article=article, form=EntryForm(elements_for(article)))


def safe_next(request, default):
    """The list URL with its filters to go back to, if it points to this site."""
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return default


class MeasurementListView(TenantRequiredMixin, View):
    paginate_by = 50

    def get(self, request):
        measurement_filter = MeasurementFilter(request)
        measurements = measurement_filter.queryset()
        columns = measurement_filter.columns(measurements)
        page = Paginator(measurements.prefetch_related('values'), self.paginate_by).get_page(request.GET.get('page'))
        attach_values(page.object_list, columns)
        query = request.GET.copy()
        query.pop('page', None)
        return render(request, 'measurements/measurement_list.html', {
            'filter': measurement_filter,
            'columns': columns,
            'page_obj': page,
            'filter_query': query.urlencode(),
        })


class MeasurementExportView(TenantRequiredMixin, View):
    """Exports all measurements matching the filters (not only the current page)."""

    def get(self, request, file_format):
        if file_format not in ('xlsx', 'csv'):
            raise Http404
        measurement_filter = MeasurementFilter(request)
        measurements = measurement_filter.queryset()
        columns = measurement_filter.columns(measurements)
        measurements = attach_values(list(measurements.prefetch_related('values')), columns)
        category = slugify(measurement_filter.category.code) if measurement_filter.category else 'none'
        filename = f'measurements_{category}_{measurement_filter.date_from}_{measurement_filter.date_to}'
        export = to_xlsx if file_format == 'xlsx' else to_csv
        return export(measurements, columns, measurement_filter.include_deleted, filename)


class MeasurementDetailView(TenantRequiredMixin, View):
    """Details of a measurement; the admin can correct the employee number and values here."""

    def get(self, request, pk):
        measurement = self.get_measurement(request, pk)
        elements = self.elements_for(measurement)
        raw = {value.element_id: str(value.value) for value in measurement.values.all()}
        return self.render(request, measurement, EntryForm(elements, raw=raw), str(measurement.employee_number))

    def post(self, request, pk):
        if not request.user.is_tenant_admin:
            raise PermissionDenied
        measurement = self.get_measurement(request, pk)
        if measurement.deleted_at:
            raise PermissionDenied
        form = EntryForm.from_post(self.elements_for(measurement), request.POST)
        employee_number, employee_error = parse_employee_number(request.POST.get('employee_number'))
        if employee_error or not form.is_valid:
            return self.render(request, measurement, form, request.POST.get('employee_number', ''), employee_error)
        if update_measurement(measurement, employee_number, form, request.user):
            messages.success(request, _('Measurement corrected.'))
        return redirect(safe_next(request, reverse('measurements:list')))

    @staticmethod
    def get_measurement(request, pk):
        return get_object_or_404(
            Measurement.objects.select_related('created_by', 'updated_by', 'deleted_by').prefetch_related('values'),
            pk=pk, tenant=request.tenant,
        )

    @staticmethod
    def elements_for(measurement):
        """The category's active elements in their order, plus elements that have a value in the measurement."""
        category = Category.objects.filter(tenant=measurement.tenant, code__iexact=measurement.category_code).first()
        elements = CategoryElement.active_elements(category) if category else []
        shown = {element.pk for element in elements}
        with_values = [value.element for value in measurement.values.select_related('element')
                       if value.element_id not in shown]
        return elements + sorted(with_values, key=lambda element: element.code)

    @staticmethod
    def render(request, measurement, form, employee_number, employee_error=''):
        return render(request, 'measurements/measurement_detail.html', {
            'measurement': measurement,
            'form': form,
            'employee_number': employee_number,
            'employee_error': employee_error,
            'can_edit': request.user.is_tenant_admin and not measurement.deleted_at,
            'next': safe_next(request, reverse('measurements:list')),
        })


class MeasurementDeleteView(TenantAdminRequiredMixin, View):
    """Marks the measurement as deleted; it can be restored."""

    def post(self, request, pk):
        measurement = get_object_or_404(Measurement, pk=pk, tenant=request.tenant, deleted_at__isnull=True)
        measurement.deleted_at = timezone.now()
        measurement.deleted_by = request.user
        measurement.save(update_fields=['deleted_at', 'deleted_by'])
        messages.success(request, _('Measurement deleted.'))
        return redirect(safe_next(request, reverse('measurements:list')))


class MeasurementRestoreView(TenantAdminRequiredMixin, View):
    def post(self, request, pk):
        measurement = get_object_or_404(Measurement, pk=pk, tenant=request.tenant, deleted_at__isnull=False)
        measurement.deleted_at = None
        measurement.deleted_by = None
        measurement.updated_at = timezone.now()
        measurement.updated_by = request.user
        measurement.save(update_fields=['deleted_at', 'deleted_by', 'updated_at', 'updated_by'])
        messages.success(request, _('Measurement restored.'))
        return redirect(safe_next(request, reverse('measurements:list')))
