from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from accounts.models import AuditModel, Tenant

from .validators import validate_ean13


class Category(AuditModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='categories', verbose_name=_('tenant'))
    code = models.CharField(_('code'), max_length=20)
    name = models.CharField(_('name'), max_length=100)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'category'
        ordering = ['code']
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        constraints = [
            # Case-insensitive, because the CSV import matches category codes regardless of case
            models.UniqueConstraint(F('tenant'), Lower('code'), name='category_code_unique_per_tenant'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name}'


class Article(AuditModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='articles', verbose_name=_('tenant'))
    code = models.CharField(_('code'), max_length=15)
    color = models.CharField(_('color'), max_length=10)
    size = models.CharField(_('size'), max_length=10)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='articles', verbose_name=_('category'))
    barcode = models.CharField(_('barcode'), max_length=13, validators=[validate_ean13])
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'article'
        ordering = ['code', 'color', 'size']
        verbose_name = _('article')
        verbose_name_plural = _('articles')
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'barcode'], name='article_barcode_unique_per_tenant'),
            # Code, color and size are stored in upper case, see normalize()
            models.UniqueConstraint(fields=['tenant', 'code', 'color', 'size'], name='article_variant_unique_per_tenant'),
        ]

    TEXT_FIELDS = ['code', 'color', 'size']

    @staticmethod
    def normalize(value):
        """Code, color and size are always upper case."""
        return value.strip().upper()

    def __str__(self):
        return f'{self.code} {self.color} {self.size}'

    def clean(self):
        if self.category_id and self.tenant_id and self.category.tenant_id != self.tenant_id:
            raise ValidationError({'category': _('Category belongs to a different tenant.')})


class Element(AuditModel):
    """A dimension that is measured on articles of a category."""

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='elements', verbose_name=_('tenant'))
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='elements', verbose_name=_('category'))
    code = models.CharField(_('code'), max_length=20)
    name = models.CharField(_('name'), max_length=100)
    unit = models.CharField(_('unit of measure'), max_length=20)
    sort_order = models.PositiveIntegerField(_('sort order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'element'
        ordering = ['category__code', 'sort_order', 'code']
        verbose_name = _('element')
        verbose_name_plural = _('elements')
        constraints = [
            models.UniqueConstraint(fields=['category', 'code'], name='element_code_unique_per_category'),
            # Also applies to inactive elements, so reactivating never causes a clash
            models.UniqueConstraint(fields=['category', 'sort_order'], name='element_sort_order_unique_per_category'),
        ]

    SORT_ORDER_STEP = 10

    @classmethod
    def next_sort_order(cls, category):
        """Suggested sort order for a new element: the category's highest (incl. inactive) plus a step."""
        highest = cls.objects.filter(category=category).aggregate(highest=models.Max('sort_order'))['highest']
        return cls.SORT_ORDER_STEP if highest is None else highest + cls.SORT_ORDER_STEP

    def __str__(self):
        return f'{self.code} - {self.name}'

    def clean(self):
        if self.category_id and self.tenant_id and self.category.tenant_id != self.tenant_id:
            raise ValidationError({'category': _('Category belongs to a different tenant.')})
