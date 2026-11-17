from django.urls import path

from . import views

app_name = 'contracts'
urlpatterns = [
    path('', views.danh_sach, name='contract_list'),                          # UC 3.1 (QL, KT: tất cả; NV: của mình)
    path('moi/', views.them_hop_dong, name='contract_add'),                   # UC 3.1
    path('sap-het-han/', views.sap_het_han, name='contract_expiring'),        # UC 3.5
    path('<int:pk>/', views.chi_tiet, name='contract_detail'),                # UC 3.2
    path('<int:pk>/in/', views.in_hop_dong, name='contract_print'),               # UC 3.2 bổ sung: in mẫu hợp đồng
    path('<int:pk>/gia-han/', views.gia_han, name='contract_renew'),          # UC 3.3
    path('<int:pk>/cap-nhat-file/', views.cap_nhat_file, name='contract_update_file'),   # UC 3.3 luồng 1.1
    path('<int:pk>/thanh-ly/', views.thanh_ly, name='contract_terminate'),    # UC 3.4
]
