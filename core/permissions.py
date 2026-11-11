"""Phân quyền dùng chung (§5)."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.models import UserRole
from . import thong_bao


def tra_403(request, thong_diep=None):
    """Trang 403 kèm câu thông báo của §10 (mặc định: "Bạn không có quyền truy cập chức năng này.")."""
    return render(request, '403.html', {'khong_co_quyen': thong_diep or thong_bao.KHONG_CO_QUYEN}, status=403)


def role_required(*roles, thong_diep=None):
    """Chặn sai vai trò và trả trang 403. Dùng cho mọi view (đã gồm kiểm tra đăng nhập).

    `thong_diep`: câu hiện trên trang 403 khi §10 quy định câu riêng (mặc định: "…truy cập chức năng này.")."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if roles and request.user.role not in roles:
                return tra_403(request, thong_diep)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def co_quyen_duyet(nguoi_duyet, nguoi_gui):
    """Dùng chung cho UC 2.6, 4.4, 5.2 (Q2).

    - Không ai tự duyệt yêu cầu của mình.
    - Yêu cầu của MANAGER chỉ SUPER_ADMIN duyệt.
    - Yêu cầu của NV hoặc KT do MANAGER duyệt.
    """
    if nguoi_duyet.pk == nguoi_gui.pk:
        return False
    if nguoi_gui.role == UserRole.MANAGER:
        return nguoi_duyet.role == UserRole.SUPER_ADMIN
    if nguoi_gui.role in (UserRole.EMPLOYEE, UserRole.ACCOUNTANT):
        return nguoi_duyet.role == UserRole.MANAGER
    return False
