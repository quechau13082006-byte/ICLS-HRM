from django.urls import path

from . import views

app_name = "leave"
urlpatterns = [
    path('', views.cua_toi, name='my_leaves'),                          # UC 5.3 + danh sách đơn (menu "Leave")
    path('don/moi/', views.gui_don, name='leave_create'),               # UC 5.1
    path('don/<int:pk>/', views.chi_tiet, name='detail'),               # chi tiết đơn (chủ đơn / người duyệt)
    path('don/<int:pk>/huy/', views.huy_don, name='cancel'),            # UC 5.1 luồng 1.1
    path('don/<int:pk>/xu-ly/', views.xu_ly_don, name='decide'),        # UC 5.2 duyệt / từ chối
    path('duyet/', views.danh_sach_duyet, name='review'),               # UC 5.2
    path('tong-hop/', views.tong_hop, name='summary'),                  # UC 5.4
]
