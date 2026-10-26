from django.contrib import admin

from .models import Article, Brand, Element


class ReadOnlyAdmin(admin.ModelAdmin):
    """Superadmin can inspect tenant data; it is maintained by tenant admins in the application."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Brand)
class BrandAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'tenant', 'is_active')
    list_filter = ('tenant', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Article)
class ArticleAdmin(ReadOnlyAdmin):
    list_display = ('code', 'color', 'size', 'brand', 'barcode', 'tenant', 'is_active')
    list_filter = ('tenant', 'brand', 'is_active')
    search_fields = ('code', 'barcode')


@admin.register(Element)
class ElementAdmin(ReadOnlyAdmin):
    list_display = ('code', 'name', 'unit', 'brand', 'sort_order', 'tenant', 'is_active')
    list_filter = ('tenant', 'brand', 'is_active')
    search_fields = ('code', 'name')
