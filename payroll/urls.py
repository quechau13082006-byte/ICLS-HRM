from django.urls import path

from . import views

app_name = "payroll"
urlpatterns = [
    path('', views.phieu_luong_cua_toi, name='my_payslips'),                                   # UC 7.3 (menu "Payroll")
    path('phieu/<int:pk>/', views.xem_phieu, name='payslip'),                                  # UC 7.3 bước 3–6
    path('cau-hinh/', views.cau_hinh_ds, name='config_list'),                                  # UC 7.1 bước 1
    path('cau-hinh/<int:nv>/', views.cau_hinh_chi_tiet, name='config_detail'),                 # UC 7.1 bước 2–7, luồng 1.1
    path('bang-luong/', views.bang_luong_ds, name='period_list'),                              # UC 7.2 bước 1–3
    path('bang-luong/tao/', views.khoi_tao, name='period_create'),                             # UC 7.2 bước 3–7
    path('bang-luong/<int:nam>/<int:thang>/', views.bang_luong_thang, name='period'),          # UC 7.2 bảng lương tổng
    path('bang-luong/<int:nam>/<int:thang>/tinh-lai/', views.tinh_lai, name='period_recalc'),  # UC 7.2 luồng 8.1
    path('bang-luong/<int:nam>/<int:thang>/chot/', views.chot, name='period_lock'),            # UC 7.2 bước 10–11
    path('bang-luong/<int:nam>/<int:thang>/phat-hanh/', views.phat_hanh, name='period_send'),  # UC 7.2 bước 12–13
    path('bang-luong/chi-tiet/<int:pk>/', views.chi_tiet_bang_luong, name='payroll_detail'),   # UC 7.2 bước 8
    path('bang-luong/chi-tiet/<int:pk>/them/', views.them_khoan, name='detail_add'),           # UC 7.2 bước 8–9
    path('bang-luong/khoan/<int:pk>/xoa/', views.xoa_khoan, name='detail_delete'),             # UC 7.2 luồng 8.2
]
