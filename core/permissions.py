"""Phân quyền dùng chung (§5)."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.models import UserRole
from . import thong_bao


def tra_403(request, thong_diep=None):
    """Trang 403 kèm câu thông báo của §10 (mặc định: "Bạn không có quyền truy cập chức năng này.")."""
    return render(request, '403.html', {'khong_co_quyen': thong_diep or thong_bao.KHONG_CO_QUYEN}, status=403)


# Các vai trò của hệ thống (đều là vai trò nghiệp vụ; không còn vai trò Super Admin).
VAI_TRO_NGHIEP_VU = (UserRole.DIRECTOR, UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE)


def role_required(*roles, thong_diep=None):
    """Chặn sai vai trò và trả trang 403. Dùng cho mọi view (đã gồm kiểm tra đăng nhập).

    Không ghi vai trò nào (`@role_required()`) nghĩa là mọi vai trò (VAI_TRO_NGHIEP_VU).
    `thong_diep`: câu hiện trên trang 403 khi §10 quy định câu riêng (mặc định: "…truy cập chức năng này.")."""
    cho_phep = roles or VAI_TRO_NGHIEP_VU

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in cho_phep:
                return tra_403(request, thong_diep)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def co_quyen_duyet(nguoi_duyet, nguoi_gui):
    """Dùng chung cho UC 2.6, 4.4, 5.2 (Q2).

    - Không ai tự duyệt yêu cầu của mình.
    - Yêu cầu của MANAGER chỉ Giám đốc (DIRECTOR) duyệt.
    - Yêu cầu của NV hoặc KT do MANAGER duyệt.
    """
    if nguoi_duyet.pk == nguoi_gui.pk:
        return False
    if nguoi_gui.role == UserRole.MANAGER:
        return nguoi_duyet.role == UserRole.DIRECTOR
    if nguoi_gui.role in (UserRole.EMPLOYEE, UserRole.ACCOUNTANT):
        return nguoi_duyet.role == UserRole.MANAGER
    return False
