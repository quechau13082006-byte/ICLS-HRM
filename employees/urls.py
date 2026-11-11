from django.urls import path

from . import views

app_name = 'employees'
urlpatterns = [
    path('', views.danh_sach, name='employee_list'),                                   # UC 2.1
    path('moi/', views.them_nhan_su, name='employee_add'),                             # UC 2.5
    path('ho-so-cua-toi/', views.ho_so_cua_toi, name='my_profile'),                    # UC 2.3
    path('ho-so-cua-toi/sua/', views.sua_ho_so_cua_toi, name='my_profile_edit'),       # UC 2.2
    path('giay-to/cho-duyet/', views.giay_to_cho_duyet, name='pending_documents'),     # UC 2.6
    path('giay-to/canh-bao/', views.canh_bao_giay_to, name='document_alerts'),         # UC 2.4
    path('giay-to/<int:pk>/', views.duyet_giay_to, name='document_review'),            # UC 2.6
    path('giay-to/<int:pk>/nhac-nho/', views.nhac_nho_giay_to, name='document_remind'),  # UC 2.4
    path('<int:pk>/', views.chi_tiet, name='employee_detail'),                         # UC 2.1 (QL, SA)
    path('<int:pk>/lien-he/', views.lien_he, name='employee_contact'),                 # UC 2.1 (KT, NV)
    path('<int:pk>/sua/', views.sua_nhan_su, name='employee_edit'),                    # UC 2.5 luồng 1.1
]
