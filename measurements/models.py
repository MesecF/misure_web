from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import AuditModel, Tenant
from catalog.models import Article, Element


class Measurement(AuditModel):
    """
    One measurement of an article: a header with the values of its category's elements.
    Article and category data are copied at measurement time, so later article
    changes (CSV import) do not alter history. Deleting only marks the record.
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, related_name='measurements', verbose_name=_('tenant')
    )
    article = models.ForeignKey(
        Article, on_delete=models.PROTECT, related_name='measurements', verbose_name=_('article')
    )
    employee_number = models.PositiveIntegerField(_('employee number'))
    measured_at = models.DateTimeField(_('measured at'), default=timezone.now)

    article_code = models.CharField(_('article code'), max_length=15)
    article_color = models.CharField(_('color'), max_length=10)
    article_size = models.CharField(_('size'), max_length=10)
    article_barcode = models.CharField(_('barcode'), max_length=13)
    category_code = models.CharField(_('category code'), max_length=20)
    category_name = models.CharField(_('category name'), max_length=100)

    deleted_at = models.DateTimeField(_('deleted at'), null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('deleted by'),
    )

    class Meta:
        db_table = 'measurement'
        ordering = ['-measured_at']
        verbose_name = _('measurement')
        verbose_name_plural = _('measurements')
        indexes = [
            models.Index(fields=['tenant', 'measured_at'], name='measurement_tenant_time_idx'),
            models.Index(fields=['tenant', 'category_code'], name='measurement_tenant_cat_idx'),
        ]

    def __str__(self):
        return f'{self.article_code} {self.article_color} {self.article_size} @ {self.measured_at:%Y-%m-%d %H:%M}'

    def copy_article_data(self):
        """Fill the snapshot fields from the current article and its category."""
        article = self.article
        self.article_code = article.code
        self.article_color = article.color
        self.article_size = article.size
        self.article_barcode = article.barcode
        self.category_code = article.category.code
        self.category_name = article.category.name


class MeasurementValue(models.Model):
    """Value of one element in a measurement. Elements left empty are not stored."""

    measurement = models.ForeignKey(
        Measurement, on_delete=models.CASCADE, related_name='values', verbose_name=_('measurement')
    )
    element = models.ForeignKey(
        Element, on_delete=models.PROTECT, related_name='values', verbose_name=_('element')
    )
    element_code = models.CharField(_('element code'), max_length=20)
    element_name = models.CharField(_('element name'), max_length=100)
    element_unit = models.CharField(_('unit of measure'), max_length=20)
    value = models.DecimalField(_('value'), max_digits=9, decimal_places=1)

    class Meta:
        db_table = 'measurement_value'
        verbose_name = _('measurement value')
        verbose_name_plural = _('measurement values')
        constraints = [
            models.UniqueConstraint(fields=['measurement', 'element'], name='measurement_value_unique_element'),
        ]

    def __str__(self):
        return f'{self.element_code}: {self.value} {self.element_unit}'

    def copy_element_data(self):
        """Fill the snapshot fields from the current element."""
        self.element_code = self.element.code
        self.element_name = self.element.name
        self.element_unit = self.element.unit
