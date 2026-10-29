from django import forms
from django.utils.translation import gettext_lazy as _

from measurements.models import Measurement

from .models import Article, Category, CategoryElement, Element


class BootstrapFormMixin:
    """Adds Bootstrap CSS classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css_class = 'form-select'
            else:
                css_class = 'form-control'
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {css_class}".strip()


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['code', 'name']

    def __init__(self, *args, tenant, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        # Measurements are found by the category code they were taken with: a new code would hide them
        if self.instance.pk and Measurement.objects.filter(tenant=tenant, category_code=self.instance.code).exists():
            self.fields['code'].disabled = True
            self.fields['code'].help_text = _('The code cannot be changed because the category has measurements.')

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        duplicates = Category.objects.filter(tenant=self.tenant, code__iexact=code).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_('A category with this code already exists.'))
        return code


class ElementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Element
        fields = ['code', 'name', 'unit']

    def __init__(self, *args, tenant, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        # Measured values keep their meaning: code and unit are fixed once used, the name can be corrected
        if self.instance.pk and self.instance.values.exists():
            for name in ('code', 'unit'):
                self.fields[name].disabled = True
                self.fields[name].help_text = _('Cannot be changed because the element has measured values.')
            self.fields['name'].help_text = _(
                'The element has measured values: a new name is also shown for earlier measurements '
                'in the measurement list and export.')

    def clean_code(self):
        code = Element.normalize_code(self.cleaned_data['code'])
        duplicates = Element.objects.filter(tenant=self.tenant, code__iexact=code).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_('An element with this code already exists.'))
        return code


class CategoryElementForm(BootstrapFormMixin, forms.ModelForm):
    """Adds an element to a category (element and sort order) or changes its sort order (sort order only)."""

    class Meta:
        model = CategoryElement
        fields = ['element', 'sort_order']

    def __init__(self, *args, category, **kwargs):
        self.category = category
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields['element']
        else:
            # Active elements of the tenant that are not in the category yet
            self.fields['element'].queryset = (
                Element.objects.filter(tenant=category.tenant, is_active=True)
                .exclude(category_elements__category=category)
            )
        self.fields['sort_order'].help_text = _('Unique within the category. Numbering in steps of 10 leaves room to insert elements later.')

    def clean_sort_order(self):
        sort_order = self.cleaned_data['sort_order']
        others = CategoryElement.objects.filter(category=self.category).exclude(pk=self.instance.pk)
        if others.filter(sort_order=sort_order).exists():
            raise forms.ValidationError(_('This category already has an element with this sort order.'))
        return sort_order


class ArticleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Article
        fields = ['code', 'color', 'size', 'category', 'barcode']

    def __init__(self, *args, tenant, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        # Only the tenant's active categories, plus the current category when editing
        categories = Category.objects.filter(tenant=tenant, is_active=True)
        if self.instance.category_id:
            categories = categories | Category.objects.filter(pk=self.instance.category_id)
        self.fields['category'].queryset = categories.order_by('code')
        self.fields['barcode'].widget.attrs['inputmode'] = 'numeric'
        for name in Article.TEXT_FIELDS:
            self.fields[name].widget.attrs['style'] = 'text-transform: uppercase'

    def clean_code(self):
        return Article.normalize(self.cleaned_data['code'])

    def clean_color(self):
        return Article.normalize(self.cleaned_data['color'])

    def clean_size(self):
        return Article.normalize(self.cleaned_data['size'])

    def clean(self):
        cleaned_data = super().clean()
        variant = {name: cleaned_data.get(name) for name in Article.TEXT_FIELDS}
        if all(variant.values()):
            duplicate = (Article.objects.filter(tenant=self.tenant, **variant)
                         .exclude(pk=self.instance.pk).first())
            if duplicate:
                raise forms.ValidationError(
                    _('An article with this code, color and size already exists (barcode %(barcode)s).'),
                    params={'barcode': duplicate.barcode},
                )
        return cleaned_data

    def clean_barcode(self):
        barcode = self.cleaned_data['barcode']
        duplicates = Article.objects.filter(tenant=self.tenant, barcode=barcode).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_('An article with this barcode already exists.'))
        return barcode


class CsvImportForm(forms.Form):
    MAX_SIZE_MB = 5

    file = forms.FileField(
        label=_('CSV file'),
        widget=forms.ClearableFileInput(attrs={'accept': '.csv,text/csv', 'class': 'form-control'}),
    )

    def clean_file(self):
        file = self.cleaned_data['file']
        if file.size > self.MAX_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(_('The file is larger than %(size)d MB.') % {'size': self.MAX_SIZE_MB})
        return file
