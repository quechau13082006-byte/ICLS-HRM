from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from .permissions import role_required, tra_403

ALL_ROLES = (UserRole.SUPER_ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE)


@role_required(*ALL_ROLES)
def notification_list(request):
    """Danh sách thông báo của chính mình."""
    paginator = Paginator(request.user.notifications.all(), settings.SO_DONG_MOI_TRANG)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/notifications.html', {'page': page})


@role_required(*ALL_ROLES)
@require_POST
def notification_mark_read(request, pk=None):
    """Đánh dấu một thông báo (hoặc tất cả nếu không có pk) là đã đọc."""
    queryset = request.user.notifications.filter(is_read=False)
    if pk is not None:
        queryset = queryset.filter(pk=pk)
    queryset.update(is_read=True)
    return redirect('core:notifications')


def _nguoi_dung_duoc_tai(user, duong_dan):
    """Kiểm tra quyền tải file: SA/QL tải tất cả; người khác chỉ tải file của chính mình."""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.MANAGER):
        return True
    if duong_dan.startswith('avatars/'):
        return True
    if duong_dan.startswith('contracts/') and user.role == UserRole.ACCOUNTANT:
        return True    # Kế toán xem mọi hợp đồng (UC 3.2)    # ảnh đại diện: mọi người đã đăng nhập đều thấy (hiện ở thanh menu)
    employee = getattr(user, 'employee', None)
    if employee is None:
        return False
    from attendance.models import Attendance
    from contracts.models import Contract
    from employees.models import EmployeeDocument
    if duong_dan.startswith('employee_documents/'):
        return EmployeeDocument.objects.filter(file_url=duong_dan, employee=employee).exists()
    if duong_dan.startswith('contracts/'):
        return Contract.objects.filter(file_url=duong_dan, employee=employee).exists()
    if duong_dan.startswith('attendance/explanations/'):
        return Attendance.objects.filter(explanation_evidence=duong_dan, employee=employee).exists()
    return False


@role_required(*ALL_ROLES)
def tai_file(request, duong_dan):
    """Tải file trong MEDIA_ROOT có kiểm tra quyền (không mở đường dẫn media công khai)."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    file_path = (media_root / duong_dan).resolve()
    if media_root not in file_path.parents or not file_path.is_file():
        raise Http404
    if not _nguoi_dung_duoc_tai(request.user, duong_dan):
        return tra_403(request)
    return FileResponse(open(file_path, 'rb'))
