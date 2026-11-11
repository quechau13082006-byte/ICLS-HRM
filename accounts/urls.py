from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('dang-nhap/', views.dang_nhap, name='login'),
    path('dang-xuat/', views.dang_xuat, name='logout'),
    path('quen-mat-khau/', views.quen_mat_khau, name='forgot_password'),
    path('dat-mat-khau/<str:ma_nguoi_dung>/<str:token>/', views.dat_mat_khau, name='dat_mat_khau'),
    path('doi-mat-khau/', views.doi_mat_khau, name='change_password'),
    path('cua-toi/', views.tai_khoan_cua_toi, name='my_account'),
    path('quan-ly/', views.ds_tai_khoan, name='user_list'),
    path('quan-ly/them/', views.them_tai_khoan, name='user_add'),
    path('quan-ly/<int:pk>/doi-vai-tro/', views.doi_vai_tro, name='user_change_role'),
    path('quan-ly/<int:pk>/khoa-mo-khoa/', views.khoa_mo_khoa, name='user_toggle_lock'),
]
