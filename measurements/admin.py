from django.contrib import admin

from catalog.admin import ReadOnlyAdmin

from .models import Measurement, MeasurementValue


class MeasurementValueInline(admin.TabularInline):
    model = MeasurementValue
    fields = ('element_code', 'element_name', 'value', 'element_unit')
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Measurement)
class MeasurementAdmin(ReadOnlyAdmin):
    list_display = ('measured_at', 'article_code', 'article_color', 'article_size', 'category_code',
                    'employee_number', 'tenant', 'deleted_at')
    list_filter = ('tenant', 'category_code')
    search_fields = ('article_code', 'article_barcode', 'employee_number')
    date_hierarchy = 'measured_at'
    inlines = [MeasurementValueInline]
