from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from accounts.mixins import TenantAdminRequiredMixin, TenantAuditFormMixin, TenantQuerysetMixin

from .export import to_csv, to_xlsx
from .forms import ArticleForm, ArticleImportForm, CategoryElementForm, CategoryForm, ElementForm
from .importers import import_articles
from .models import Article, Category, CategoryElement, Element


class SaveMessageMixin:
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('"%(record)s" saved.') % {'record': self.object})
        return response


class ToggleActiveView(TenantAdminRequiredMixin, View):
    """Activates or deactivates a record; records are never deleted."""

    model = None
    success_url = None

    def post(self, request, pk):
        record = get_object_or_404(self.model, pk=pk, tenant=request.tenant)
        record.is_active = not record.is_active
        record.updated_at = timezone.now()
        record.updated_by = request.user
        record.save(update_fields=['is_active', 'updated_at', 'updated_by'])
        if record.is_active:
            messages.success(request, _('"%(record)s" activated.') % {'record': record})
        else:
            messages.success(request, _('"%(record)s" deactivated.') % {'record': record})
        # Return to the list with its filters, but only within this site
        next_url = request.POST.get('next', '')
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = self.success_url
        return redirect(next_url)


# Categories

class CategoryListView(TenantAdminRequiredMixin, TenantQuerysetMixin, ListView):
    model = Category


class CategoryCreateView(TenantAdminRequiredMixin, TenantAuditFormMixin, SaveMessageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy('catalog:category_list')


class CategoryUpdateView(TenantAdminRequiredMixin, TenantQuerysetMixin, TenantAuditFormMixin, SaveMessageMixin,
                      UpdateView):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy('catalog:category_list')


class CategoryToggleActiveView(ToggleActiveView):
    model = Category
    success_url = reverse_lazy('catalog:category_list')


# Elements

class ElementListView(TenantAdminRequiredMixin, TenantQuerysetMixin, ListView):
    model = Element

    def get_queryset(self):
        elements = super().get_queryset().prefetch_related('category_elements__category')
        self.status_filter = self.request.GET.get('status', 'active')
        if self.status_filter == 'active':
            elements = elements.filter(is_active=True)
        elif self.status_filter == 'inactive':
            elements = elements.filter(is_active=False)
        return elements

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.status_filter
        return context


class ElementCreateView(TenantAdminRequiredMixin, TenantAuditFormMixin, SaveMessageMixin, CreateView):
    model = Element
    form_class = ElementForm
    success_url = reverse_lazy('catalog:element_list')


class ElementUpdateView(TenantAdminRequiredMixin, TenantQuerysetMixin, TenantAuditFormMixin, SaveMessageMixin,
                        UpdateView):
    model = Element
    form_class = ElementForm
    success_url = reverse_lazy('catalog:element_list')


class ElementToggleActiveView(ToggleActiveView):
    model = Element
    success_url = reverse_lazy('catalog:element_list')


# Elements of a category

class CategoryElementsView(TenantAdminRequiredMixin, View):
    """Elements measured for a category: list, add, change sort order, remove."""

    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk, tenant=request.tenant)
        form = CategoryElementForm(category=category,
                                   initial={'sort_order': CategoryElement.next_sort_order(category)})
        return self.render(request, category, form)

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk, tenant=request.tenant)
        form = CategoryElementForm(request.POST, category=category)
        if not form.is_valid():
            return self.render(request, category, form)
        link = form.save(commit=False)
        link.tenant = request.tenant
        link.category = category
        link.created_by = request.user
        link.save()
        messages.success(request, _('"%(element)s" added.') % {'element': link.element})
        return redirect('catalog:category_elements', pk=category.pk)

    @staticmethod
    def render(request, category, form):
        links = category.category_elements.select_related('element').order_by('sort_order')
        return render(request, 'catalog/category_elements.html', {
            'category': category, 'links': links, 'form': form,
        })


class CategoryElementUpdateView(TenantAdminRequiredMixin, View):
    """Changes the sort order of an element in a category."""

    def post(self, request, pk):
        link = get_object_or_404(CategoryElement, pk=pk, tenant=request.tenant)
        form = CategoryElementForm(request.POST, instance=link, category=link.category)
        if form.is_valid():
            if form.has_changed():
                link.updated_at = timezone.now()
                link.updated_by = request.user
                form.save()
                messages.success(request, _('"%(element)s" saved.') % {'element': link.element})
        else:
            messages.error(request, ' '.join(form.errors['sort_order']))
        return redirect('catalog:category_elements', pk=link.category_id)


class CategoryElementDeleteView(TenantAdminRequiredMixin, View):
    """Removes an element from a category; recorded measurements keep their values."""

    def post(self, request, pk):
        link = get_object_or_404(CategoryElement, pk=pk, tenant=request.tenant)
        link.delete()
        messages.success(request, _('"%(element)s" removed from the category.') % {'element': link.element})
        return redirect('catalog:category_elements', pk=link.category_id)


# Articles

def filter_articles(articles, search, category_filter, status_filter):
    """The article list's filters, also used by its export."""
    if search:
        articles = articles.filter(Q(code__icontains=search) | Q(barcode__icontains=search))
    if category_filter.isdigit():
        articles = articles.filter(category_id=category_filter)
    if status_filter == 'active':
        articles = articles.filter(is_active=True)
    elif status_filter == 'inactive':
        articles = articles.filter(is_active=False)
    return articles


class ArticleListView(TenantAdminRequiredMixin, TenantQuerysetMixin, ListView):
    model = Article
    paginate_by = 50

    def get_queryset(self):
        articles = super().get_queryset().select_related('category')
        self.search = self.request.GET.get('q', '').strip()
        self.category_filter = self.request.GET.get('category', '')
        self.status_filter = self.request.GET.get('status', 'active')
        return filter_articles(articles, self.search, self.category_filter, self.status_filter)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(tenant=self.request.tenant)
        context['search'] = self.search
        context['category_filter'] = self.category_filter
        context['status_filter'] = self.status_filter
        # Filters without the page number, for the pagination links
        query = self.request.GET.copy()
        query.pop('page', None)
        context['filter_query'] = query.urlencode()
        return context


class ArticleExportView(TenantAdminRequiredMixin, View):
    """Exports all articles matching the list's filters (not only the current page)."""

    def get(self, request, file_format):
        if file_format not in ('xlsx', 'csv'):
            raise Http404
        params = request.GET
        articles = Article.objects.filter(tenant=request.tenant).select_related('category', 'created_by', 'updated_by')
        articles = filter_articles(articles, params.get('q', '').strip(), params.get('category', ''),
                                   params.get('status', 'active'))
        filename = f'articles_{timezone.localdate()}'
        export = to_xlsx if file_format == 'xlsx' else to_csv
        return export(articles, filename)


class ArticleCreateView(TenantAdminRequiredMixin, TenantAuditFormMixin, SaveMessageMixin, CreateView):
    model = Article
    form_class = ArticleForm
    success_url = reverse_lazy('catalog:article_list')


class ArticleUpdateView(TenantAdminRequiredMixin, TenantQuerysetMixin, TenantAuditFormMixin, SaveMessageMixin,
                        UpdateView):
    model = Article
    form_class = ArticleForm
    success_url = reverse_lazy('catalog:article_list')


class ArticleToggleActiveView(ToggleActiveView):
    model = Article
    success_url = reverse_lazy('catalog:article_list')


class ArticleImportView(TenantAdminRequiredMixin, FormView):
    form_class = ArticleImportForm
    template_name = 'catalog/article_import.html'

    def form_valid(self, form):
        result = import_articles(form.cleaned_data['file'].read(), self.request.tenant, self.request.user)
        return self.render_to_response(self.get_context_data(form=ArticleImportForm(), result=result))
