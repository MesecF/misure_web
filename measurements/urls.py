from django.urls import path

from . import views

app_name = 'measurements'

urlpatterns = [
    path('', views.MeasurementListView.as_view(), name='list'),
    path('export/<str:file_format>/', views.MeasurementExportView.as_view(), name='export'),
    path('new/', views.MeasurementEntryView.as_view(), name='entry'),
    path('new/article/', views.ArticlePanelView.as_view(), name='article_panel'),
    path('<int:pk>/', views.MeasurementDetailView.as_view(), name='detail'),
    path('<int:pk>/delete/', views.MeasurementDeleteView.as_view(), name='delete'),
    path('<int:pk>/restore/', views.MeasurementRestoreView.as_view(), name='restore'),
]
