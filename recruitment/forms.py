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
    """UC 8.1 – bước 1: tên, thời gian và chỉ tiêu (số lượng cần tuyển cho từng vị trí, để trống = không tuyển vị trí đó).

    Mỗi vị trí một ô số `sl_<VỊ TRÍ>`; luật "ít nhất một vị trí" kiểm tra ở services.tao_dot_tuyen_dung."""
    campaign_name = forms.CharField(label='Tên đợt tuyển dụng', max_length=255,
                                    widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: Tuyển dụng Q4-2026'}))
    start_date = forms.DateField(label='Ngày bắt đầu', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='Ngày kết thúc', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for ma, ten in Position.choices:
            self.fields[f'sl_{ma}'] = forms.IntegerField(
                label=ten, required=False, min_value=0, max_value=999,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0'}))

    def o_chi_tieu(self):
        """Các ô số lượng theo thứ tự vị trí (template vẽ thành bảng Vị trí | Số lượng cần tuyển)."""
        return [self[f'sl_{ma}'] for ma in Position.values]

    def chi_tieu(self):
        return {ma: self.cleaned_data.get(f'sl_{ma}') or 0 for ma in Position.values}

    def clean(self):
        du_lieu = super().clean()
        bat_dau, ket_thuc = du_lieu.get('start_date'), du_lieu.get('end_date')
        if bat_dau and ket_thuc and ket_thuc < bat_dau:
            self.add_error('end_date', 'Ngày kết thúc không được trước ngày bắt đầu.')
        return du_lieu


class UngVienForm(BootstrapForm):
    """UC 8.1 – bước 3–4. Chọn đợt tuyển dụng (chỉ đợt đang mở). CV là PDF tối đa 5 MB (không bắt buộc)."""
    dot = forms.ModelChoiceField(label='Đợt tuyển dụng', queryset=RecruitmentCampaign.objects.none(), empty_label='— Chọn đợt —',
                                 error_messages={'invalid_choice': thong_bao.DOT_DA_DONG})
    full_name = forms.CharField(label='Họ và tên', max_length=150)
    email = forms.EmailField(label='Email', max_length=255)
    phone = forms.CharField(label='Số điện thoại', max_length=11)
    position = forms.ChoiceField(label='Vị trí ứng tuyển', choices=[('', '— Chọn —')] + list(Position.choices))
    employment_type = forms.ChoiceField(label='Loại hình', choices=[('', '— Chọn —')] + list(EmploymentType.choices))
    cv_file = forms.FileField(label='CV (PDF, tối đa 5 MB)', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dot'].queryset = RecruitmentCampaign.objects.filter(status='OPEN').order_by('-start_date', '-pk')
        self.fields['dot'].label_from_instance = lambda d: (
            f'{d.campaign_name} ({d.start_date:%d/%m/%Y}{" – " + format(d.end_date, "%d/%m/%Y") if d.end_date else ""})')

    def clean_phone(self):
        so = self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'\d{10,11}', so):
            raise forms.ValidationError(thong_bao.SDT_UNG_VIEN_SAI)
        return so

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean(self):
        du_lieu = super().clean()
        dot, email = du_lieu.get('dot'), du_lieu.get('email')
        if dot is not None and email and Candidate.objects.filter(campaign=dot, email__iexact=email).exists():
            self.add_error('email', thong_bao.UNG_VIEN_TRUNG_EMAIL)            # luồng 3.3: trùng email trong CÙNG đợt
        return du_lieu

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
    """UC 8.3 – bước 3: Nhận xét, Kết quả (Đạt/Không đạt). Bản đơn giản: không chấm điểm."""
    note = forms.CharField(label='Nhận xét của người phỏng vấn', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    ket_qua = forms.ChoiceField(label='Kết quả', widget=forms.RadioSelect,
                                choices=[('dat', 'Đạt'), ('khong_dat', 'Không đạt')], initial='dat')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ket_qua'].widget.attrs['class'] = 'form-check-input'



class BoLocUngVienForm(BootstrapForm):
    """Thanh công cụ của bảng ứng viên: tìm tên/email/SĐT, lọc vị trí, chọn đợt."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm tên, email, sđt...'}))
    vi_tri = forms.ChoiceField(required=False, choices=[('', 'Lọc vị trí')] + list(Position.choices))
    dot = forms.ModelChoiceField(required=False, queryset=RecruitmentCampaign.objects.order_by('-start_date'),
                                 empty_label='Tất cả đợt')
