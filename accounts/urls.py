from django.urls import path

from . import views

app_name = 'accounts'
urlpatterns = [
    path('dang-nhap/', views.dang_nhap, name='login'),
    path('dang-xuat/', views.dang_xuat, name='logout'),
    path('quen-mat-khau/', views.quen_mat_khau, name='password_reset'),
    path('dat-lai-mat-khau/<uidb64>/<token>/', views.dat_lai_mat_khau, name='password_reset_confirm'),
    path('doi-mat-khau/', views.doi_mat_khau, name='change_password'),
    path('cua-toi/', views.tai_khoan_cua_toi, name='my_account'),
    path('quan-ly/', views.ds_tai_khoan, name='user_list'),
    path('quan-ly/them/', views.them_tai_khoan, name='user_add'),
    path('quan-ly/<int:pk>/doi-vai-tro/', views.doi_vai_tro, name='user_change_role'),
    path('quan-ly/<int:pk>/khoa-mo-khoa/', views.khoa_mo_khoa, name='user_toggle_lock'),
]
