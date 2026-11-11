from django.urls import path

from . import views

app_name = 'core'
urlpatterns = [
    path('thong-bao/', views.notification_list, name='notifications'),
    path('thong-bao/doc-tat-ca/', views.notification_mark_read, name='notifications_read_all'),
    path('thong-bao/<int:pk>/doc/', views.notification_mark_read, name='notification_read'),
    path('tai-file/<path:duong_dan>', views.tai_file, name='tai_file'),
]
