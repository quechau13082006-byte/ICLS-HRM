from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('email', 'full_name')
    # Mật khẩu chỉ hiện dạng mã hóa, không sửa ở đây (đổi mật khẩu qua trang của hệ thống); quyền admin tự theo vai trò
    readonly_fields = ('password', 'last_login', 'date_joined', 'is_staff', 'is_superuser')
    exclude = ('groups', 'user_permissions')
