from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/toggle-active/', views.CategoryToggleActiveView.as_view(), name='category_toggle_active'),
    path('categories/<int:pk>/elements/', views.CategoryElementsView.as_view(), name='category_elements'),
    path('category-elements/<int:pk>/', views.CategoryElementUpdateView.as_view(), name='category_element_update'),
    path('category-elements/<int:pk>/delete/', views.CategoryElementDeleteView.as_view(),
         name='category_element_delete'),
    path('elements/', views.ElementListView.as_view(), name='element_list'),
    path('elements/new/', views.ElementCreateView.as_view(), name='element_create'),
    path('elements/<int:pk>/', views.ElementUpdateView.as_view(), name='element_update'),
    path('elements/<int:pk>/toggle-active/', views.ElementToggleActiveView.as_view(), name='element_toggle_active'),
    path('articles/', views.ArticleListView.as_view(), name='article_list'),
    path('articles/new/', views.ArticleCreateView.as_view(), name='article_create'),
    path('articles/import/', views.ArticleImportView.as_view(), name='article_import'),
    path('articles/export/<str:file_format>/', views.ArticleExportView.as_view(), name='article_export'),
    path('articles/<int:pk>/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('articles/<int:pk>/toggle-active/', views.ArticleToggleActiveView.as_view(), name='article_toggle_active'),
]
