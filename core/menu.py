"""Menu trái theo vai trò (§5, §11 P0: "mỗi mục menu trỏ tới một app").

Mỗi mục khai báo tên URL của trang đầu tiên của app. Nếu app chưa làm xong (chưa có URL đó),
mục menu hiện mờ và chưa bấm được; khi app thêm đúng URL thì mục tự bật, không phải sửa menu.
"""
from django.urls import NoReverseMatch, reverse

from accounts.models import UserRole

TAT_CA = tuple(UserRole.values)
QL, KT, NV, GD = UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE, UserRole.DIRECTOR
NGHIEP_VU = (GD, QL, KT, NV)   # Super Admin chỉ làm kỹ thuật nên không thấy các mục nghiệp vụ

# (khóa app, tên tiếng Anh, tên tiếng Hàn, icon Remix Icon, tên URL trang đầu, vai trò được thấy, tiền tố tên URL để sáng mục)
# Tiền tố chỉ cần khi nhiều mục chung một app: app `accounts` còn có trang đăng nhập, đổi mật khẩu, tài khoản cá nhân...
# nên mục "User Management" chỉ sáng ở các trang có tên URL bắt đầu bằng `user_`.
MUC_MENU = [
    ('dashboard', 'Overview', '개요', 'ri-dashboard-horizontal-line', 'dashboard:dashboard', TAT_CA, None),
    ('accounts', 'User Management', '계정 설정', 'ri-file-settings-line', 'accounts:user_list', (UserRole.SUPER_ADMIN,), 'user_'),
    ('recruitment', 'Recruitment', '채용', 'ri-user-search-line', 'recruitment:board', (QL,), None),
    ('employees', 'Employees', '직원', 'ri-user-line', 'employees:employee_list', NGHIEP_VU, None),
    ('contracts', 'Contract', '계약', 'ri-draft-line', 'contracts:contract_list', (GD, QL, KT, NV), None),
    ('schedule', 'Schedule', '일정', 'ri-calendar-view', 'schedule:calendar', NGHIEP_VU, None),
    ('attendance', 'Attendance', '근태', 'ri-verified-badge-line', 'attendance:my_attendance', NGHIEP_VU, None),
    ('leave', 'Leave', '휴가', 'ri-calendar-close-line', 'leave:my_leaves', NGHIEP_VU, None),
    ('payroll', 'Payroll', '급여', 'ri-money-dollar-circle-line', 'payroll:my_payslips', (QL, KT, NV), None),
    # Trang quản trị Django (/admin/): Super Admin xem, sửa trực tiếp mọi bảng dữ liệu (phần kỹ thuật)
    ('admin', 'Admin', '관리자', 'ri-shield-user-line', 'admin:index', (UserRole.SUPER_ADMIN,), None),
]


def menu_chinh(request):
    """Context processor: danh sách mục menu cho người đang đăng nhập (đã lọc theo vai trò)."""
    if not request.user.is_authenticated:
        return {'menu_chinh': []}
    app_hien_tai = request.resolver_match.app_name if request.resolver_match else ''
    ten_url_hien_tai = request.resolver_match.url_name if request.resolver_match else ''
    cac_muc = []
    for khoa, ten_anh, ten_han, icon, ten_url, vai_tro, tien_to in MUC_MENU:
        if request.user.role not in vai_tro:
            continue
        try:
            url = reverse(ten_url)
        except NoReverseMatch:
            url = None                      # app chưa làm xong: hiện mờ
        dang_chon = khoa == app_hien_tai and (tien_to is None or (ten_url_hien_tai or '').startswith(tien_to))
        cac_muc.append({'ten_anh': ten_anh, 'ten_han': ten_han, 'icon': icon, 'url': url, 'dang_chon': dang_chon})
    return {'menu_chinh': cac_muc}
