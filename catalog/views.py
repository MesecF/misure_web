from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from accounts.mixins import TenantAdminRequiredMixin, TenantAuditFormMixin, TenantQuerysetMixin

from .forms import ArticleForm, ArticleImportForm, CategoryForm, ElementForm
from .importers import import_articles
from .models import Article, Category, Element


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
        elements = super().get_queryset().select_related('category')
        self.category_filter = self.request.GET.get('category', '')
        self.status_filter = self.request.GET.get('status', 'active')
        if self.category_filter.isdigit():
            elements = elements.filter(category_id=self.category_filter)
        if self.status_filter == 'active':
            elements = elements.filter(is_active=True)
        elif self.status_filter == 'inactive':
            elements = elements.filter(is_active=False)
        return elements

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(tenant=self.request.tenant)
        context['category_filter'] = self.category_filter
        context['status_filter'] = self.status_filter
        return context


class ElementCreateView(TenantAdminRequiredMixin, TenantAuditFormMixin, SaveMessageMixin, CreateView):
    model = Element
    form_class = ElementForm
    success_url = reverse_lazy('catalog:element_list')

    def get_initial(self):
        # Keep the category selected in the list filter and suggest its next sort order
        category = get_category_from_query(self.request)
        if category is None:
            return {'sort_order': None}
        return {'category': category, 'sort_order': Element.next_sort_order(category)}


def get_category_from_query(request):
    category_id = request.GET.get('category', '')
    if not category_id.isdigit():
        return None
    return Category.objects.filter(tenant=request.tenant, pk=category_id).first()


class ElementNextSortOrderView(TenantAdminRequiredMixin, View):
    """HTMX: returns the sort order input filled with the next free number of the chosen category."""

    def get(self, request):
        category = get_category_from_query(request)
        initial = {'sort_order': Element.next_sort_order(category) if category else None}
        form = ElementForm(tenant=request.tenant, initial=initial)
        return HttpResponse(str(form['sort_order']))


class ElementUpdateView(TenantAdminRequiredMixin, TenantQuerysetMixin, TenantAuditFormMixin, SaveMessageMixin,
                        UpdateView):
    model = Element
    form_class = ElementForm
    success_url = reverse_lazy('catalog:element_list')


class ElementToggleActiveView(ToggleActiveView):
    model = Element
    success_url = reverse_lazy('catalog:element_list')


# Articles

class ArticleListView(TenantAdminRequiredMixin, TenantQuerysetMixin, ListView):
    model = Article
    paginate_by = 50

    def get_queryset(self):
        articles = super().get_queryset().select_related('category')
        self.search = self.request.GET.get('q', '').strip()
        self.category_filter = self.request.GET.get('category', '')
        self.status_filter = self.request.GET.get('status', 'active')
        if self.search:
            articles = articles.filter(Q(code__icontains=self.search) | Q(barcode__icontains=self.search))
        if self.category_filter.isdigit():
            articles = articles.filter(category_id=self.category_filter)
        if self.status_filter == 'active':
            articles = articles.filter(is_active=True)
        elif self.status_filter == 'inactive':
            articles = articles.filter(is_active=False)
        return articles

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
