"""Form của app payroll (UC 7.1, 7.2). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
from decimal import Decimal

from django import forms
from django.conf import settings

from core.forms import BootstrapForm
from employees.models import Department
from .models import PayrollDetailCategory as Nhom
from .models import PayrollDetailType as Loai
from .services import LOAI_CUA_NHOM_THU_CONG

NGAY = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


def _tien(nhan, **kw):
    return forms.DecimalField(label=nhan, required=False, max_digits=15, decimal_places=2,
                              widget=forms.NumberInput(attrs={'step': '1000'}), **kw)


class CauHinhLuongForm(BootstrapForm):
    """UC 7.1 – bước 4–5: các ô tiền (ô nào hiện tùy loại hình, xem template) + Ngày bắt đầu áp dụng.
    Kiểm tra "số tiền ≥ 0", "lương cơ bản/đơn giá giờ > 0" nằm trong `services.luu_cau_hinh_luong` để đúng thứ tự §10;
    ô bỏ trống được hiểu là 0."""
    base_salary = _tien('Lương cơ bản (đ/tháng)')
    class_allowance_rate = _tien('Phụ cấp mỗi lớp (đ)', help_text='Chỉ giáo viên Full-time')
    responsibility_allowance = _tien('Phụ cấp trách nhiệm (đ/tháng)')
    hourly_rate = _tien('Đơn giá giờ (đ/giờ)', initial=settings.DON_GIA_GIO_PT_MAC_DINH)
    effective_from = forms.DateField(label='Ngày bắt đầu áp dụng', widget=NGAY)

    def tien(self, ten):
        """Giá trị tiền của một ô, ô trống = 0."""
        gia_tri = self.cleaned_data.get(ten)
        return Decimal('0') if gia_tri is None else gia_tri


class KhoanThuCongForm(BootstrapForm):
    """UC 7.2 – bước 8 (theo Figma "Add Adjustment"): nhóm khoản, loại (chỉ dùng khi chọn "Khác"), số tiền, mô tả."""
    category = forms.ChoiceField(label='Nhóm khoản', choices=[(ma, Nhom(ma).label) for ma in LOAI_CUA_NHOM_THU_CONG])
    detail_type = forms.ChoiceField(label='Loại khoản (chỉ dùng cho nhóm "Khác")', required=False,
                                    choices=[('', '—'), (Loai.EARNING, 'Khoản cộng (vào thu nhập)'), (Loai.DEDUCTION, 'Khoản trừ (khấu trừ)')])
    amount = forms.DecimalField(label='Số tiền (đ)', required=False, max_digits=15, decimal_places=2,
                                widget=forms.NumberInput(attrs={'step': '1000', 'placeholder': 'Nhập số tiền'}))
    description = forms.CharField(label='Mô tả (không bắt buộc)', required=False, max_length=255,
                                  widget=forms.TextInput(attrs={'placeholder': 'Lý do của khoản này'}))


class BoLocThangForm(BootstrapForm):
    """Bộ lọc của bảng lương tổng (Figma "Monthly Payroll")."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm nhân viên'}))
    phong_ban = forms.ChoiceField(required=False, choices=[('', 'Tất cả phòng ban')] + list(Department.choices))
