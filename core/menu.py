"""Menu trái theo vai trò (§5, §11 P0: "mỗi mục menu trỏ tới một app").

Mỗi mục khai báo tên URL của trang đầu tiên của app. Nếu app chưa làm xong (chưa có URL đó),
mục menu hiện mờ và chưa bấm được; khi app thêm đúng URL thì mục tự bật, không phải sửa menu.
"""
from django.urls import NoReverseMatch, reverse

from accounts.models import UserRole

TAT_CA = tuple(UserRole.values)
QL, KT, NV = UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE

# (khóa app, tên tiếng Anh, tên tiếng Hàn, icon Remix Icon, tên URL trang đầu, vai trò được thấy)
MUC_MENU = [
    ('dashboard', 'Overview', '개요', 'ri-dashboard-horizontal-line', 'dashboard:dashboard', TAT_CA),
    ('recruitment', 'Recruitment', '채용', 'ri-user-search-line', 'recruitment:board', (QL,)),
    ('employees', 'Employees', '직원', 'ri-user-line', 'employees:employee_list', TAT_CA),
    ('contracts', 'Contract', '계약', 'ri-draft-line', 'contracts:contract_list', (QL, KT, NV)),
    ('schedule', 'Schedule', '일정', 'ri-calendar-view', 'schedule:calendar', TAT_CA),
    ('attendance', 'Attendance', '근태', 'ri-verified-badge-line', 'attendance:my_attendance', TAT_CA),
    ('leave', 'Leave', '휴가', 'ri-calendar-close-line', 'leave:my_leaves', TAT_CA),
    ('payroll', 'Payroll', '급여', 'ri-money-dollar-circle-line', 'payroll:my_payslips', (QL, KT, NV)),
]


def menu_chinh(request):
    """Context processor: danh sách mục menu cho người đang đăng nhập (đã lọc theo vai trò)."""
    if not request.user.is_authenticated:
        return {'menu_chinh': []}
    app_hien_tai = request.resolver_match.app_name if request.resolver_match else ''
    cac_muc = []
    for khoa, ten_anh, ten_han, icon, ten_url, vai_tro in MUC_MENU:
        if request.user.role not in vai_tro:
            continue
        try:
            url = reverse(ten_url)
        except NoReverseMatch:
            url = None                      # app chưa làm xong: hiện mờ
        cac_muc.append({'ten_anh': ten_anh, 'ten_han': ten_han, 'icon': icon, 'url': url,
                        'dang_chon': khoa == app_hien_tai})
    return {'menu_chinh': cac_muc}
