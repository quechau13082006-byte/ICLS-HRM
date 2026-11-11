"""Form của app recruitment (UC 8.1 – 8.3). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
import re

from django import forms
from django.conf import settings

from core import thong_bao
from core.forms import BootstrapForm
from employees.models import EmploymentType, Position
from . import services
from .models import Candidate, CandidateStatus, RecruitmentCampaign

DINH_DANG_GIO = '%Y-%m-%dT%H:%M'          # định dạng của ô <input type="datetime-local">


class DotTuyenDungForm(BootstrapForm):
    """UC 8.1 – bước 1."""
    campaign_name = forms.CharField(label='Tên đợt tuyển dụng', max_length=255,
                                    widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: Tuyển dụng Q4-2026'}))
    start_date = forms.DateField(label='Ngày bắt đầu', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='Ngày kết thúc', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        du_lieu = super().clean()
        bat_dau, ket_thuc = du_lieu.get('start_date'), du_lieu.get('end_date')
        if bat_dau and ket_thuc and ket_thuc < bat_dau:
            self.add_error('end_date', 'Ngày kết thúc không được trước ngày bắt đầu.')
        return du_lieu


class UngVienForm(BootstrapForm):
    """UC 8.1 – bước 3–4. CV là PDF tối đa 5 MB (không bắt buộc, vì cột cv_file cho phép trống)."""
    full_name = forms.CharField(label='Họ và tên', max_length=150)
    email = forms.EmailField(label='Email', max_length=255)
    phone = forms.CharField(label='Số điện thoại', max_length=11)
    position = forms.ChoiceField(label='Vị trí ứng tuyển', choices=[('', '— Chọn —')] + list(Position.choices))
    employment_type = forms.ChoiceField(label='Loại hình', choices=[('', '— Chọn —')] + list(EmploymentType.choices))
    cv_file = forms.FileField(label='CV (PDF, tối đa 5 MB)', required=False)

    def __init__(self, *args, dot=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dot = dot

    def clean_phone(self):
        so = self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'\d{10,11}', so):
            raise forms.ValidationError(thong_bao.SDT_UNG_VIEN_SAI)
        return so

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if self.dot is not None and Candidate.objects.filter(campaign=self.dot, email__iexact=email).exists():
            raise forms.ValidationError(thong_bao.UNG_VIEN_TRUNG_EMAIL)       # luồng 3.3
        return email

    def clean_cv_file(self):
        tep = self.cleaned_data.get('cv_file')
        if tep and (not tep.name.lower().endswith('.pdf') or tep.size > settings.FILE_TOI_DA_MB * 1024 * 1024):
            raise forms.ValidationError(thong_bao.CV_KHONG_HOP_LE)            # luồng 3.2
        return tep


class SoTuyenForm(BootstrapForm):
    """UC 8.1 – bước 5: kết quả sơ tuyển (Đạt/Không đạt) và ghi chú."""
    ket_qua = forms.ChoiceField(label='Kết quả sơ tuyển', widget=forms.RadioSelect,
                                choices=[('dat', 'Đạt sơ tuyển'), ('khong_dat', 'Không đạt')], initial='dat')
    ghi_chu = forms.CharField(label='Ghi chú sơ tuyển', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ket_qua'].widget.attrs['class'] = 'form-check-input'


class LichVongForm(BootstrapForm):
    """UC 8.2 – bước 2–3: ngày giờ, địa điểm/link (hoặc lớp/phòng Demo), người phỏng vấn/giám sát (chỉ Quản lý)."""
    scheduled_at = forms.DateTimeField(
        label='Ngày giờ', input_formats=[DINH_DANG_GIO, '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DINH_DANG_GIO))
    location = forms.CharField(label='Địa điểm / link online / lớp - phòng Demo', required=False, max_length=255)
    interviewer = forms.ModelChoiceField(label='Người phỏng vấn / giám sát', queryset=None, empty_label='— Chọn —')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['interviewer'].queryset = services.danh_sach_nguoi_phong_van()
        self.fields['interviewer'].label_from_instance = lambda u: u.full_name or u.email


class DanhGiaVongForm(BootstrapForm):
    """UC 8.3 – bước 3: Điểm (0–10), Nhận xét, Kết quả (Đạt/Không đạt)."""
    score = forms.DecimalField(label='Điểm đánh giá (hệ số 10)', max_digits=4, decimal_places=2, required=False,
                               widget=forms.NumberInput(attrs={'step': '0.1'}))
    note = forms.CharField(label='Nhận xét của người phỏng vấn', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    ket_qua = forms.ChoiceField(label='Kết quả', widget=forms.RadioSelect,
                                choices=[('dat', 'Đạt'), ('khong_dat', 'Không đạt')], initial='dat')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ket_qua'].widget.attrs['class'] = 'form-check-input'

    def clean_score(self):
        diem = self.cleaned_data.get('score')
        if diem is None or not (0 <= diem <= settings.DIEM_TOI_DA):
            raise forms.ValidationError(thong_bao.DIEM_SAI)                   # luồng 3.2
        return diem


class BoLocUngVienForm(BootstrapForm):
    """Thanh công cụ của bảng ứng viên: tìm tên/email/SĐT, lọc vị trí, chọn đợt."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm tên, email, sđt...'}))
    vi_tri = forms.ChoiceField(required=False, choices=[('', 'Lọc vị trí')] + list(Position.choices))
    dot = forms.ModelChoiceField(required=False, queryset=RecruitmentCampaign.objects.order_by('-start_date'),
                                 empty_label='Tất cả đợt')
