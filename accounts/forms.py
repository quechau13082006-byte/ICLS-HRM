"""Form của app accounts (UC 1.1 – 1.5). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ nằm ở services.py."""
import re

from django import forms
from django.conf import settings

from core import thong_bao
from core.forms import BootstrapForm
from .models import User, UserRole


def mat_khau_du_manh(mat_khau):
    """Đủ mạnh = tối thiểu MAT_KHAU_TOI_THIEU ký tự và không được toàn số (câu thông báo ở §10)."""
    return len(mat_khau) >= settings.MAT_KHAU_TOI_THIEU and not mat_khau.isdigit()


class DangNhapForm(BootstrapForm):
    """UC 1.1 – bước 2: để trống thì Django tự báo lỗi "bắt buộc" ngay tại trường (luồng 3.1)."""
    email = forms.EmailField(label='Email', max_length=255,
                             widget=forms.EmailInput(attrs={'placeholder': 'Email', 'autocomplete': 'username', 'autofocus': True}))
    mat_khau = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput(
        attrs={'placeholder': 'Mật khẩu', 'autocomplete': 'current-password'}))


class QuenMatKhauForm(BootstrapForm):
    """UC 1.2 – bước 2–3."""
    email = forms.EmailField(label='Email', max_length=255)


class MatKhauMoiForm(BootstrapForm):
    """Hai ô Mật khẩu mới + Xác nhận, dùng chung cho UC 1.2 (đặt lại) và UC 1.3 (đổi mật khẩu).

    Thứ tự báo lỗi theo §10: không khớp trước, rồi tới chưa đủ mạnh.
    """
    mat_khau_moi = forms.CharField(label='Mật khẩu mới', widget=forms.PasswordInput)
    xac_nhan = forms.CharField(label='Xác nhận mật khẩu mới', widget=forms.PasswordInput)

    def clean(self):
        du_lieu = super().clean()
        moi, xac_nhan = du_lieu.get('mat_khau_moi'), du_lieu.get('xac_nhan')
        if moi and xac_nhan:
            if moi != xac_nhan:
                self.add_error('xac_nhan', thong_bao.MAT_KHAU_XAC_NHAN_KHONG_KHOP)
            elif not mat_khau_du_manh(moi):
                self.add_error('mat_khau_moi', thong_bao.MAT_KHAU_CHUA_DU_MANH)
        return du_lieu


class DoiMatKhauForm(MatKhauMoiForm):
    """UC 1.3 – bước 2–4: thêm ô Mật khẩu hiện tại, kiểm tra đúng mật khẩu đang dùng."""
    mat_khau_hien_tai = forms.CharField(label='Mật khẩu hiện tại', widget=forms.PasswordInput)
    field_order = ['mat_khau_hien_tai', 'mat_khau_moi', 'xac_nhan']

    def __init__(self, nguoi_dung, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nguoi_dung = nguoi_dung

    def clean_mat_khau_hien_tai(self):
        mat_khau = self.cleaned_data['mat_khau_hien_tai']
        if not self.nguoi_dung.check_password(mat_khau):
            raise forms.ValidationError(thong_bao.MAT_KHAU_HIEN_TAI_SAI)
        return mat_khau


class TaiKhoanCaNhanForm(BootstrapForm):
    """UC 1.4 – bước 4. Form CHỈ có 3 trường được sửa (Họ tên, SĐT, Ảnh).

    Email và Vai trò không có trong form nên nếu ai sửa HTML gửi thêm, Django bỏ qua (luồng 3.2).
    """
    full_name = forms.CharField(label='Họ và tên', max_length=150)
    phone = forms.CharField(label='Số điện thoại', max_length=11)
    avatar = forms.FileField(label='Ảnh đại diện (.jpg/.png, tối đa 2 MB)', required=False)

    def clean_phone(self):
        so_dien_thoai = self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'\d{10,11}', so_dien_thoai):
            raise forms.ValidationError('Số điện thoại gồm 10–11 chữ số.')
        return so_dien_thoai

    def clean_avatar(self):
        anh = self.cleaned_data.get('avatar')
        if anh:
            if not anh.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                raise forms.ValidationError('Ảnh đại diện phải là file .jpg hoặc .png.')
            if anh.size > settings.ANH_TOI_DA_MB * 1024 * 1024:
                raise forms.ValidationError(f'Ảnh đại diện không quá {settings.ANH_TOI_DA_MB} MB.')
        return anh


class ThemTaiKhoanForm(BootstrapForm):
    """UC 1.5 – luồng 3.1: Super Admin nhập Email, Họ tên, Vai trò."""
    email = forms.EmailField(label='Email', max_length=255)
    full_name = forms.CharField(label='Họ và tên', max_length=150)
    role = forms.ChoiceField(label='Vai trò', choices=UserRole.choices)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(thong_bao.EMAIL_DA_DUNG)       # luồng 3.3.1
        return email


class DoiVaiTroForm(BootstrapForm):
    """UC 1.5 – bước 4–5."""
    role = forms.ChoiceField(label='Vai trò mới', choices=UserRole.choices)
