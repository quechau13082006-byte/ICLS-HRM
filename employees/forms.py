"""Form của app employees (UC 2.1 – 2.6). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
import re

from django import forms
from django.conf import settings

from accounts.models import User
from core import thong_bao
from core.forms import BootstrapForm
from .models import (Department, DocumentType, Employee, EmploymentType, Gender, Position, WorkShift)

NHAN_TRONG = [('', '— Chọn —')]


def kiem_tra_so_dien_thoai(gia_tri):
    gia_tri = gia_tri.strip()
    if not re.fullmatch(r'\d{10,11}', gia_tri):
        raise forms.ValidationError(thong_bao.SDT_SAI_DINH_DANG)
    return gia_tri


def kiem_tra_file(tep):
    """File giấy tờ: PDF/JPG/PNG, tối đa FILE_TOI_DA_MB (UC 2.2 – luồng 3.2)."""
    if tep:
        hop_le = tep.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png'))
        if not hop_le or tep.size > settings.FILE_TOI_DA_MB * 1024 * 1024:
            raise forms.ValidationError(thong_bao.FILE_KHONG_HOP_LE)
    return tep


class BoLocNhanSuForm(BootstrapForm):
    """UC 2.1 – bước 3: từ khóa (Họ tên hoặc Mã NV) và các bộ lọc Vị trí, Loại hình, Trạng thái."""
    q = forms.CharField(required=False, label='Tìm kiếm',
                        widget=forms.TextInput(attrs={'placeholder': 'Tìm theo họ tên hoặc mã NV'}))
    # Ô chưa chọn hiện đúng tên bộ lọc ("Vị trí", "Loại nhân sự", "Trạng thái") như thiết kế Figma
    vi_tri = forms.ChoiceField(required=False, label='Vị trí', choices=[('', 'Vị trí')] + list(Position.choices))
    loai_hinh = forms.ChoiceField(required=False, label='Loại nhân sự', choices=[('', 'Loại nhân sự')] + list(EmploymentType.choices))
    trang_thai = forms.ChoiceField(required=False, label='Trạng thái',
                                   choices=[('', 'Trạng thái')] + list(Employee._meta.get_field('status').choices))


class HoSoCaNhanForm(BootstrapForm):
    """UC 2.2 – bước 2–4: thông tin cá nhân (lưu ngay) + giấy tờ/chứng chỉ (chờ duyệt).

    Phần giấy tờ là TÙY CHỌN: bỏ trống cả phần này thì chỉ lưu thông tin cá nhân. Nếu nhập một phần
    thì phải đủ Loại, Tên, File. Khi "Tải bản mới" (có `giay_to_id`), Loại và Tên giữ nguyên, chỉ nhập lại Ngày và File.
    """
    phone = forms.CharField(label='Số điện thoại', max_length=11)
    address = forms.CharField(label='Địa chỉ', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    bank_account = forms.CharField(label='Tài khoản ngân hàng', required=False, max_length=100,
                                   help_text='Ví dụ: Vietcombank – 0123456789')
    giay_to_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    document_type = forms.ChoiceField(label='Loại giấy tờ', required=False, choices=NHAN_TRONG + list(DocumentType.choices))
    document_name = forms.CharField(label='Tên giấy tờ', required=False, max_length=150,
                                    widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: TOPIK cấp 6'}))
    issue_date = forms.DateField(label='Ngày cấp', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    expiry_date = forms.DateField(label='Ngày hết hạn', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                                  help_text='Để trống nếu giấy tờ không có thời hạn')
    file_url = forms.FileField(label='File đính kèm (PDF, JPG, PNG, tối đa 5 MB)', required=False)

    def clean_phone(self):
        return kiem_tra_so_dien_thoai(self.cleaned_data['phone'])

    def clean_file_url(self):
        return kiem_tra_file(self.cleaned_data.get('file_url'))

    def clean(self):
        du_lieu = super().clean()
        tai_ban_moi = bool(du_lieu.get('giay_to_id'))
        co_giay_to = any(du_lieu.get(t) for t in ('document_type', 'document_name', 'issue_date', 'expiry_date', 'file_url'))
        if tai_ban_moi or co_giay_to:
            if not tai_ban_moi:
                for truong in ('document_type', 'document_name'):
                    if not du_lieu.get(truong):
                        self.add_error(truong, thong_bao.THIEU_TRUONG_GIAY_TO)
            if not du_lieu.get('file_url') and 'file_url' not in self.errors:
                self.add_error('file_url', thong_bao.THIEU_TRUONG_GIAY_TO)
            cap, het_han = du_lieu.get('issue_date'), du_lieu.get('expiry_date')
            if cap and het_han and het_han <= cap:
                self.add_error('expiry_date', thong_bao.NGAY_HET_HAN_SAI)             # luồng 3.3
        du_lieu['co_giay_to'] = tai_ban_moi or co_giay_to
        return du_lieu

    def lay_giay_to(self):
        """Dict dùng cho EmployeeDocument.objects.create(...) (hoặc cập nhật bản ghi cũ); None nếu không tải giấy tờ."""
        d = self.cleaned_data
        if not d.get('co_giay_to'):
            return None
        return {'document_type': d.get('document_type'), 'document_name': d.get('document_name'),
                'issue_date': d.get('issue_date'), 'expiry_date': d.get('expiry_date'), 'file_url': d.get('file_url')}


class NhanSuForm(BootstrapForm):
    """UC 2.5 – bước 3–4: form tạo hồ sơ nhân sự (Onboarding) và sửa hồ sơ (luồng 1.1).

    Khi sửa (`nhan_su` được truyền vào): không cho sửa Email và Loại hình (Loại hình chỉ đổi qua hợp đồng).
    """
    full_name = forms.CharField(label='Họ và tên', max_length=150)
    email = forms.EmailField(label='Email cá nhân', max_length=255)
    phone = forms.CharField(label='Số điện thoại', max_length=11)
    gender = forms.ChoiceField(label='Giới tính', required=False, choices=NHAN_TRONG + list(Gender.choices))
    date_of_birth = forms.DateField(label='Ngày sinh', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    id_card_number = forms.CharField(label='Số CCCD', required=False, max_length=12)
    address = forms.CharField(label='Địa chỉ', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    nationality = forms.CharField(label='Quốc tịch', max_length=30, initial='Việt Nam')
    department = forms.ChoiceField(label='Phòng ban', choices=NHAN_TRONG + list(Department.choices))
    position = forms.ChoiceField(label='Vị trí / Chức danh', choices=NHAN_TRONG + list(Position.choices))
    employment_type = forms.ChoiceField(label='Loại hình', choices=NHAN_TRONG + list(EmploymentType.choices))
    work_shift = forms.ChoiceField(label='Ca làm việc (Full-time)', required=False,
                                   choices=[('', '— Không có (Part-time) —')] + list(WorkShift.choices))
    join_date = forms.DateField(label='Ngày vào làm', widget=forms.DateInput(attrs={'type': 'date'}))
    bank_account = forms.CharField(label='Tài khoản ngân hàng', required=False, max_length=100,
                                   help_text='Ví dụ: Vietcombank – 0123456789')

    def __init__(self, *args, nhan_su=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.nhan_su = nhan_su
        if nhan_su is not None:                        # chế độ sửa: khóa Email và Loại hình
            for ten in ('email', 'employment_type'):
                self.fields[ten].required = False
                self.fields[ten].disabled = True

    def clean_phone(self):
        return kiem_tra_so_dien_thoai(self.cleaned_data['phone'])

    def clean_id_card_number(self):
        so = self.cleaned_data['id_card_number'].strip()
        if not so:
            return None                                # để trống thì lưu NULL (cột UNIQUE cho phép nhiều NULL)
        if not re.fullmatch(r'\d{12}', so):
            raise forms.ValidationError(thong_bao.CCCD_SAI_DINH_DANG)
        trung = Employee.objects.filter(id_card_number=so)
        if self.nhan_su is not None:
            trung = trung.exclude(pk=self.nhan_su.pk)
        if trung.exists():
            raise forms.ValidationError(thong_bao.EMAIL_HOAC_CCCD_TON_TAI)         # luồng 3.2
        return so

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if self.nhan_su is None and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(thong_bao.EMAIL_HOAC_CCCD_TON_TAI)         # luồng 3.2
        return email

    def clean(self):
        du_lieu = super().clean()
        loai_hinh = self.nhan_su.employment_type if self.nhan_su else du_lieu.get('employment_type')
        ca = du_lieu.get('work_shift')
        if loai_hinh == EmploymentType.FULL_TIME and not ca:
            self.add_error('work_shift', thong_bao.CAN_CHON_CA_FULL_TIME)           # bắt buộc với Full-time
        elif loai_hinh == EmploymentType.PART_TIME and ca:
            self.add_error('work_shift', thong_bao.PART_TIME_KHONG_CO_CA)           # để trống với Part-time
        return du_lieu


class TuChoiGiayToForm(BootstrapForm):
    """UC 2.6 – luồng 5.1: lý do từ chối bắt buộc."""
    ly_do = forms.CharField(label='Lý do từ chối', required=False, widget=forms.Textarea(attrs={'rows': 3}))
