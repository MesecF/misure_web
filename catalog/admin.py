from django.contrib import admin

from .models import Article, Category, CategoryElement, Element


class ReadOnlyAdmin(admin.ModelAdmin):
    """Superadmin can inspect tenant data; it is maintained by tenant admins in the application."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Article)
class ArticleAdmin(ReadOnlyAdmin):
    list_display = ('code', 'color', 'size', 'category', 'barcode', 'tenant', 'is_active')
    list_filter = ('tenant', 'category', 'is_active')
    search_fields = ('code', 'barcode')


@admin.register(Element)
class ElementAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'unit', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('code', 'name')


@admin.register(CategoryElement)
class CategoryElementAdmin(ReadOnlyAdmin):
    list_display = ('category', 'sort_order', 'element', 'tenant')
    list_filter = ('tenant', 'category')
