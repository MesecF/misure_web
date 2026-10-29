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
    """A dimension that can be measured. Which elements a category measures is set in CategoryElement."""

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='elements', verbose_name=_('tenant'))
    code = models.CharField(_('code'), max_length=20)
    name = models.CharField(_('name'), max_length=100)
    unit = models.CharField(_('unit of measure'), max_length=20)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        db_table = 'element'
        ordering = ['code']
        verbose_name = _('element')
        verbose_name_plural = _('elements')
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='element_code_unique_per_tenant'),
        ]

    @staticmethod
    def normalize_code(value):
        """Element codes are always upper case, so B05 and b05 cannot both exist."""
        return value.strip().upper()

    def __str__(self):
        return f'{self.code} - {self.name}'


class CategoryElement(AuditModel):
    """An element measured on articles of a category, in the given order."""

    tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, related_name='category_elements', verbose_name=_('tenant')
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='category_elements', verbose_name=_('category')
    )
    element = models.ForeignKey(
        Element, on_delete=models.PROTECT, related_name='category_elements', verbose_name=_('element')
    )
    sort_order = models.PositiveIntegerField(_('sort order'))

    SORT_ORDER_STEP = 10

    class Meta:
        db_table = 'category_element'
        ordering = ['category__code', 'sort_order']
        verbose_name = _('category element')
        verbose_name_plural = _('category elements')
        constraints = [
            models.UniqueConstraint(fields=['category', 'element'], name='category_element_unique'),
            models.UniqueConstraint(fields=['category', 'sort_order'], name='category_element_sort_order_unique'),
        ]

    def __str__(self):
        return f'{self.category.code}: {self.element.code}'

    def clean(self):
        for name in ['category', 'element']:
            related = getattr(self, name, None)
            if related is not None and self.tenant_id and related.tenant_id != self.tenant_id:
                raise ValidationError({name: _('Belongs to a different tenant.')})

    @classmethod
    def next_sort_order(cls, category):
        """Suggested sort order for an element added to the category: the highest plus a step."""
        highest = cls.objects.filter(category=category).aggregate(highest=models.Max('sort_order'))['highest']
        return cls.SORT_ORDER_STEP if highest is None else highest + cls.SORT_ORDER_STEP

    @staticmethod
    def active_elements(category):
        """Active elements of the category in their sort order (used for measurement entry)."""
        return [
            link.element for link in
            CategoryElement.objects.filter(category=category, element__is_active=True)
            .select_related('element').order_by('sort_order')
        ]
