from django.urls import path

from . import views

app_name = 'recruitment'
urlpatterns = [
    path('', views.bang, name='board'),                                                   # UC 8.1: bảng ứng viên (+ ngăn hồ sơ ?chon=)
    path('dot/moi/', views.them_dot, name='campaign_add'),                                # UC 8.1
    path('dot/<int:pk>/dong/', views.dong_dot, name='campaign_close'),                    # UC 8.1 luồng 1.1
    path('ung-vien/moi/', views.them_ung_vien, name='candidate_add'),                     # UC 8.1
    path('ung-vien/<int:pk>/so-tuyen/', views.so_tuyen, name='candidate_screen'),         # UC 8.1 bước 5
    path('ung-vien/<int:pk>/khong-dat/', views.khong_dat, name='candidate_reject'),       # UC 8.3 luồng 3.1
    path('ung-vien/<int:pk>/xep-lich-phong-van/', views.xep_lich_phong_van, name='schedule_interview'),   # UC 8.2
    path('ung-vien/<int:pk>/xep-lich-demo/', views.xep_lich_demo, name='schedule_demo'),                  # UC 8.2
    path('vong/can-danh-gia/', views.vong_can_danh_gia, name='rounds_due'),               # UC 8.3 bước 1
    path('vong/<int:pk>/sua/', views.sua_vong, name='round_edit'),                        # UC 8.2 luồng 3.1
    path('vong/<int:pk>/huy/', views.huy_vong, name='round_cancel'),                      # UC 8.2 luồng 3.2
    path('vong/<int:pk>/danh-gia/', views.danh_gia_vong, name='round_evaluate'),          # UC 8.3
    path('vong/<int:pk>/vang-mat/', views.vang_mat, name='round_absent'),                 # UC 8.3 luồng 3.1
]
