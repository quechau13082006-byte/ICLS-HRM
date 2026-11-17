from django.urls import path

from . import views

app_name = "attendance"
urlpatterns = [
    path('', views.cua_toi, name='my_attendance'),                              # UC 4.1 + 4.3 (menu "Attendance")
    path('check-in/', views.nhan_check_in, name='check_in'),                    # UC 4.1 bước 3–5
    path('check-out/', views.nhan_check_out, name='check_out'),                 # UC 4.1 bước 6–8
    path('giai-trinh/<int:pk>/', views.gui_giai_trinh, name='explain'),         # UC 4.2
    path('duyet/', views.danh_sach_giai_trinh, name='review'),                  # UC 4.4 bước 1–2
    path('duyet/<int:pk>/', views.chi_tiet_giai_trinh, name='review_detail'),   # UC 4.4 bước 3–4
    path('duyet/<int:pk>/xu-ly/', views.xu_ly_giai_trinh, name='review_decide'),  # UC 4.4 bước 5
    path('tong-hop/', views.tong_hop, name='summary'),                          # UC 4.5 bước 1–5
    path('tong-hop/<int:nv>/', views.chi_tiet_cong, name='summary_detail'),     # UC 4.5 bước 6–7
]
