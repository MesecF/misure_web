from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Article, Category, Element


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

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        duplicates = Category.objects.filter(tenant=self.tenant, code__iexact=code).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_('A category with this code already exists.'))
        return code


class ElementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Element
        fields = ['category', 'code', 'name', 'unit', 'sort_order']

    def __init__(self, *args, tenant, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
        # Only the tenant's active categories, plus the current category when editing
        categories = Category.objects.filter(tenant=tenant, is_active=True)
        if self.instance.category_id:
            categories = categories | Category.objects.filter(pk=self.instance.category_id)
        self.fields['category'].queryset = categories.order_by('code')
        if self.instance.pk and self.instance.values.exists():
            # Recorded measurements refer to this element under its category
            self.fields['category'].disabled = True
            self.fields['category'].help_text = _('The category cannot be changed because the element is used in measurements.')
        if not self.instance.pk:
            # Choosing a category fills in the next free sort order of that category
            self.fields['category'].widget.attrs.update({
                'hx-get': reverse('catalog:element_next_sort_order'),
                'hx-target': f'#{self["sort_order"].auto_id}',
                'hx-swap': 'outerHTML',
            })
        self.fields['sort_order'].help_text = _('Unique within the category. Numbering in steps of 10 leaves room to insert elements later.')

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        code = cleaned_data.get('code')
        sort_order = cleaned_data.get('sort_order')
        if category:
            others = Element.objects.filter(category=category).exclude(pk=self.instance.pk)
            if code and others.filter(code=code).exists():
                self.add_error('code', _('This category already has an element with this code.'))
            if sort_order is not None and others.filter(sort_order=sort_order).exists():
                self.add_error('sort_order', _('This category already has an element with this sort order.'))
        return cleaned_data

    def clean_code(self):
        return self.cleaned_data['code'].strip()


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


class ArticleImportForm(forms.Form):
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
