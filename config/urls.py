"""Điều hướng URL của dự án ICLS_HRM."""
from django.contrib import admin
from django.urls import include, path

# Trang quản trị Django (/admin/): chỉ Super Admin vào được (is_staff tự bật theo vai trò, xem accounts.models.User.save)
admin.site.site_header = 'ICLS HRM – Trang quản trị'
admin.site.site_title = 'ICLS HRM Admin'
admin.site.index_title = 'Quản trị dữ liệu hệ thống (chỉ Super Admin)'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tai-khoan/', include('accounts.urls')),
    path('tuyen-dung/', include('recruitment.urls')),
    path('nhan-su/', include('employees.urls')),
    path('hop-dong/', include('contracts.urls')),
    path('lich/', include('schedule.urls')),
    path('nghi-phep/', include('leave.urls')),
    path('cham-cong/', include('attendance.urls')),
    path('luong/', include('payroll.urls')),
    path('', include('core.urls')),
    path('', include('dashboard.urls')),
]
