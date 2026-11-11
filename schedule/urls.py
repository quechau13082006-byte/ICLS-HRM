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
    path('ca/khung/<str:ma>/giu-cho/', views.giu_cho, name='shift_hold'),           # UC 6.3 bước 5–7
    path('ca/khung/<str:ma>/huy-giu-cho/', views.huy_giu_cho, name='shift_release'),  # UC 6.3 luồng 5.1
    path('ca/tong-hop/', views.tong_hop_ca, name='shift_review'),                   # UC 6.3 bước 8
    path('ca/tong-hop/chot/', views.chot_tuan, name='shift_finalize_week'),         # UC 6.3 bước 8–9
    path('ca/khung/<str:ma>/', views.khung_ca, name='shift_group'),                 # UC 6.3 bước 8 (điều chỉnh)
    path('ca/khung/<str:ma>/chot/', views.chot_khung, name='shift_group_finalize'),  # UC 6.3 bước 9
    path('ca/cho/<int:pk>/bo/', views.bo_nguoi, name='shift_seat_remove'),          # UC 6.3 bước 8
    path('ca/cho/<int:pk>/gan/', views.gan_nguoi, name='shift_seat_assign'),        # UC 6.3 bước 8
    path('ca/cho/<int:pk>/doi/', views.doi_nguoi, name='shift_seat_change'),        # UC 6.3 luồng 8.1
    path('day-thay/', views.day_thay_danh_sach, name='substitute_list'),            # UC 6.4 bước 1–2
    path('day-thay/<int:pk>/', views.day_thay_chi_tiet, name='substitute_detail'),  # UC 6.4 bước 3–7, luồng 5.1
    path('buoi/<int:pk>/hoc-bu/', views.buoi_bu, name='makeup_create'),             # UC 6.4 luồng 5.2
    path('buoi/<int:pk>/doi-tro-giang/', views.doi_tro_giang, name='assistant_change'),  # UC 6.4 luồng 1.1
]
