from django.urls import path

from . import views

app_name = 'dashboard'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tac-vu-hang-ngay/chay/', views.chay_tac_vu, name='run_daily_job'),
]
