"""Filters and element columns shared by the measurement list and its export."""

from datetime import date, datetime, time

from django.utils import timezone

from catalog.models import Category, CategoryElement, Element

from .models import Measurement, MeasurementValue


def parse_date(text, default):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return default


ALL_CATEGORIES = 'all'


class MeasurementFilter:
    """
    Reads the filters from the query string. All categories are shown unless one is chosen
    (category=<pk>); each category has its own elements (the value columns).
    """

    def __init__(self, request):
        self.tenant = request.tenant
        params = request.GET
        today = timezone.localdate()
        self.date_from = parse_date(params.get('date_from'), today)
        self.date_to = parse_date(params.get('date_to'), today)
        # Dates entered the wrong way round: the range between them, shown corrected in the form
        if self.date_from > self.date_to:
            self.date_from, self.date_to = self.date_to, self.date_from
        self.search = params.get('q', '').strip()
        self.color = params.get('color', '').strip()
        self.size = params.get('size', '').strip()
        employee = params.get('employee', '').strip()
        self.employee = int(employee) if employee.isascii() and employee.isdigit() else None
        self.employee_text = employee
        # Deleted measurements are only shown to the admin, on request
        self.include_deleted = request.user.is_tenant_admin and params.get('deleted') == '1'

        self.categories = list(Category.objects.filter(tenant=self.tenant).order_by('-is_active', 'code'))
        category_id = params.get('category', ALL_CATEGORIES)
        self.category = next((c for c in self.categories if str(c.pk) == category_id), None)
        self.all_categories = self.category is None and bool(self.categories)

    @property
    def selected(self):
        """A category or all categories is selected; False when the tenant has no (active) categories."""
        return self.all_categories or self.category is not None

    def queryset(self):
        if not self.selected:
            return Measurement.objects.none()
        start = timezone.make_aware(datetime.combine(self.date_from, time.min))
        end = timezone.make_aware(datetime.combine(self.date_to, time.max))
        measurements = Measurement.objects.filter(tenant=self.tenant, measured_at__range=(start, end))
        if self.category:
            # Article and category data as they were when measured
            # Exact match: the snapshot keeps the code as it was, and a category's code cannot
            # change once it has measurements. Uses the (tenant, category_code) index.
            measurements = measurements.filter(category_code=self.category.code)
        if self.search:
            measurements = measurements.filter(article_code__icontains=self.search) | measurements.filter(
                article_barcode__icontains=self.search)
        if self.color:
            measurements = measurements.filter(article_color__iexact=self.color)
        if self.size:
            measurements = measurements.filter(article_size__iexact=self.size)
        if self.employee_text:
            measurements = measurements.filter(employee_number=self.employee) if self.employee else measurements.none()
        if not self.include_deleted:
            measurements = measurements.filter(deleted_at__isnull=True)
        return measurements.select_related('created_by', 'updated_by', 'deleted_by').order_by('-measured_at')

    def columns(self, measurements):
        """
        Elements shown as value columns: the category's elements in their order, then
        elements removed from the category or deactivated that have values in the result.
        For all categories: only elements with values, ordered by category code and the order in it.
        """
        used = set(MeasurementValue.objects.filter(measurement__in=measurements)
                   .values_list('element_id', flat=True).distinct())
        if self.all_categories:
            links = CategoryElement.objects.filter(tenant=self.tenant, element__in=used)
        else:
            links = CategoryElement.objects.filter(category=self.category)
        links = links.select_related('element').order_by('category__code', 'sort_order')
        columns = []
        for link in links:
            if (link.element.is_active or link.element.pk in used) and link.element not in columns:
                columns.append(link.element)
        shown = {element.pk for element in columns}
        columns += list(Element.objects.filter(pk__in=used - shown).order_by('code'))
        return columns


def attach_values(measurements, columns):
    """Sets element_values on each measurement: its values in the order of the columns."""
    for measurement in measurements:
        value_by_element = {v.element_id: v.value for v in measurement.values.all()}
        measurement.element_values = [value_by_element.get(element.pk) for element in columns]
    return measurements
