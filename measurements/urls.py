from django.urls import path

from . import views

app_name = 'measurements'

urlpatterns = [
    path('new/', views.MeasurementEntryView.as_view(), name='entry'),
    path('new/article/', views.ArticlePanelView.as_view(), name='article_panel'),
]
