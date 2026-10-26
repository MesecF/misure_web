from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import AuditModel, Tenant

from .validators import validate_ean13


class Brand(AuditModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='brands', verbose_name=_('tenant'))
    code = models.CharField(_('code'), max_length=20)
    name = models.CharField(_('name'), max_length=100)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'brand'
        ordering = ['code']
        verbose_name = _('brand')
        verbose_name_plural = _('brands')
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='brand_code_unique_per_tenant'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'


class Article(AuditModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='articles', verbose_name=_('tenant'))
    code = models.CharField(_('code'), max_length=15)
    color = models.CharField(_('color'), max_length=10)
    size = models.CharField(_('size'), max_length=10)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='articles', verbose_name=_('brand'))
    barcode = models.CharField(_('barcode'), max_length=13, validators=[validate_ean13])
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'article'
        ordering = ['code', 'color', 'size']
        verbose_name = _('article')
        verbose_name_plural = _('articles')
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'barcode'], name='article_barcode_unique_per_tenant'),
        ]

    def __str__(self):
        return f'{self.code} {self.color} {self.size}'

    def clean(self):
        if self.brand_id and self.tenant_id and self.brand.tenant_id != self.tenant_id:
            raise ValidationError({'brand': _('Brand belongs to a different tenant.')})


class Element(AuditModel):
    """A dimension that is measured on articles of a brand."""

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='elements', verbose_name=_('tenant'))
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='elements', verbose_name=_('brand'))
    code = models.CharField(_('code'), max_length=20)
    name = models.CharField(_('name'), max_length=100)
    unit = models.CharField(_('unit of measure'), max_length=20)
    sort_order = models.PositiveIntegerField(_('sort order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'element'
        ordering = ['brand__code', 'sort_order', 'code']
        verbose_name = _('element')
        verbose_name_plural = _('elements')
        constraints = [
            models.UniqueConstraint(fields=['brand', 'code'], name='element_code_unique_per_brand'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        if self.brand_id and self.tenant_id and self.brand.tenant_id != self.tenant_id:
            raise ValidationError({'brand': _('Brand belongs to a different tenant.')})
