from django.urls import path

from . import views

app_name = "schedule"
urlpatterns = [
    path('', views.lich, name='calendar'),                                          # UC 6.2 (menu "Schedule")
    path('buoi/<int:pk>/', views.chi_tiet_buoi, name='session_detail'),             # UC 6.2 bước 5–6, luồng 5.1
    path('ca/<int:pk>/', views.chi_tiet_ca, name='shift_detail'),                   # UC 6.2 bước 5–6, luồng 1.1
    path('lop/moi/', views.tao_lop, name='class_create'),                           # UC 6.1
    path('lop/<int:pk>/', views.chi_tiet_lop, name='class_detail'),                 # UC 6.1 (xem lớp, hủy lớp)
    path('lop/<int:pk>/huy/', views.huy_lop, name='class_cancel'),                  # UC 6.1 luồng 1.1
    path('ca/khung/moi/', views.tao_khung_ca, name='shift_create'),                 # UC 6.3 bước 1–2
    path('ca/dang-ky/', views.dang_ky_ca, name='shift_register'),                   # UC 6.3 bước 3–4
    path('ca/khung/<str:ma>/dang-ky/', views.nhan_ca, name='shift_join'),          # UC 6.3: đăng ký là có ca ngay
    path('ca/khung/<str:ma>/huy-dang-ky/', views.huy_nhan_ca, name='shift_leave'),  # UC 6.3: hủy trước hạn chót
    path('ca/tong-hop/', views.tong_hop_ca, name='shift_review'),                   # UC 6.3 bước 8
    path('ca/khung/<str:ma>/', views.khung_ca, name='shift_group'),                 # UC 6.3 bước 8 (điều chỉnh)
    path('ca/cho/<int:pk>/go/', views.go_nguoi, name='shift_seat_remove'),          # UC 6.3: Quản lý gỡ người
    path('ca/cho/<int:pk>/gan/', views.gan_nguoi, name='shift_seat_assign'),        # UC 6.3 bước 8
    path('day-thay/', views.day_thay_danh_sach, name='substitute_list'),            # UC 6.4 bước 1–2
    path('day-thay/<int:pk>/', views.day_thay_chi_tiet, name='substitute_detail'),  # UC 6.4 bước 3–7, luồng 5.1
]
