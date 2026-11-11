"""Form của app contracts (UC 3.1 – 3.5). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
from datetime import date

from django import forms
from django.conf import settings

from core import thong_bao
from core.forms import BootstrapForm
from employees.models import EmploymentType, EmployeeStatus
from . import services
from .models import Contract, ContractStatus

LOAI_HINH = [('', '— Chọn —')] + list(EmploymentType.choices)


def kiem_tra_file_scan(tep):
    """File scan hợp đồng: PDF/JPG/PNG, tối đa FILE_TOI_DA_MB; bắt buộc phải có file (UC 3.1 – luồng 5.3)."""
    if not tep:
        raise forms.ValidationError(thong_bao.THIEU_FILE_SCAN)
    if not tep.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')) or tep.size > settings.FILE_TOI_DA_MB * 1024 * 1024:
        raise forms.ValidationError(thong_bao.FILE_KHONG_HOP_LE)
    return tep


class BoLocHopDongForm(BootstrapForm):
    """UC 3.1 – bước 2: tìm theo tên nhân sự / số hợp đồng, lọc Loại và Trạng thái."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm theo số hợp đồng / nhân sự'}))
    loai_hinh = forms.ChoiceField(required=False, choices=[('', 'Full time / Part time')] + list(EmploymentType.choices))
    trang_thai = forms.ChoiceField(required=False, choices=[('', 'Active / Expired / Terminated')] + list(ContractStatus.choices))


class HopDongForm(BootstrapForm):
    """UC 3.1 – bước 4–5: thêm hợp đồng mới (Số HĐ, Loại, Ngày bắt đầu/kết thúc, File scan)."""
    nhan_su = forms.ModelChoiceField(label='Nhân sự', queryset=None, empty_label='— Chọn —',
                                     help_text='Chỉ nhân sự đang Onboarding hoặc đang làm việc')
    contract_number = forms.CharField(label='Số hợp đồng', max_length=50,
                                      widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: HD-2026-020'}))
    employment_type = forms.ChoiceField(label='Loại hình', choices=LOAI_HINH)
    start_date = forms.DateField(label='Ngày bắt đầu', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='Ngày kết thúc', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                               help_text='Để trống nếu không xác định thời hạn')
    file_url = forms.FileField(label='File scan hợp đồng (PDF, JPG, PNG, tối đa 5 MB)', required=False)

    # Hợp đồng gia hạn dùng lại form này nhưng khóa ô Nhân sự (xem GiaHanForm)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nhan_su'].queryset = services.nhan_su_duoc_ky()
        self.fields['nhan_su'].label_from_instance = lambda nv: f'{nv.code} · {nv.full_name}'

    def clean_contract_number(self):
        so = self.cleaned_data['contract_number'].strip()
        if Contract.objects.filter(contract_number__iexact=so).exists():
            raise forms.ValidationError(thong_bao.SO_HOP_DONG_DA_TON_TAI)           # luồng 5.2
        return so

    def clean_file_url(self):
        return kiem_tra_file_scan(self.cleaned_data.get('file_url'))

    def clean(self):
        du_lieu = super().clean()
        bat_dau, ket_thuc = du_lieu.get('start_date'), du_lieu.get('end_date')
        if bat_dau and ket_thuc and ket_thuc <= bat_dau:
            self.add_error('end_date', thong_bao.NGAY_KET_THUC_HD_SAI)             # luồng 5.3
        return du_lieu


class GiaHanForm(BootstrapForm):
    """UC 3.3 – bước 2–3: hợp đồng mới (nhân sự và hợp đồng cũ đã điền sẵn, không sửa)."""
    contract_number = forms.CharField(label='Số hợp đồng mới', max_length=50)
    employment_type = forms.ChoiceField(label='Loại hình (có thể đổi FT/PT)', choices=LOAI_HINH)
    start_date = forms.DateField(label='Ngày bắt đầu mới', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='Ngày kết thúc mới', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                               help_text='Để trống nếu không xác định thời hạn')
    file_url = forms.FileField(label='File scan hợp đồng / phụ lục (PDF, JPG, PNG, tối đa 5 MB)', required=False)

    def __init__(self, *args, hop_dong_cu=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hop_dong_cu = hop_dong_cu

    def clean_contract_number(self):
        so = self.cleaned_data['contract_number'].strip()
        if Contract.objects.filter(contract_number__iexact=so).exists():
            raise forms.ValidationError(thong_bao.SO_HOP_DONG_DA_TON_TAI)           # luồng 3.2
        return so

    def clean_file_url(self):
        return kiem_tra_file_scan(self.cleaned_data.get('file_url'))

    def clean(self):
        du_lieu = super().clean()
        bat_dau, ket_thuc = du_lieu.get('start_date'), du_lieu.get('end_date')
        if bat_dau and self.hop_dong_cu and bat_dau <= self.hop_dong_cu.start_date:
            self.add_error('start_date', thong_bao.NGAY_HOP_DONG_MOI_SAI)           # luồng 3.1
        if bat_dau and ket_thuc and ket_thuc <= bat_dau:
            self.add_error('end_date', thong_bao.NGAY_HOP_DONG_MOI_SAI)
        return du_lieu


class FileScanForm(BootstrapForm):
    """UC 3.3 – luồng 1.1: chỉ thay file scan."""
    file_url = forms.FileField(label='File scan mới (PDF, JPG, PNG, tối đa 5 MB)', required=False)

    def clean_file_url(self):
        return kiem_tra_file_scan(self.cleaned_data.get('file_url'))


class ThanhLyForm(BootstrapForm):
    """UC 3.4 – bước 2–3: Ngày thanh lý, Lý do, Hình thức nghỉ."""
    ngay_thanh_ly = forms.DateField(label='Ngày thanh lý', widget=forms.DateInput(attrs={'type': 'date'}))
    ly_do = forms.CharField(label='Lý do thanh lý', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    hinh_thuc = forms.ChoiceField(label='Hình thức nghỉ', widget=forms.RadioSelect, initial=EmployeeStatus.RESIGNED,
                                  choices=[(EmployeeStatus.RESIGNED, 'Nhân sự xin nghỉ (RESIGNED)'),
                                           (EmployeeStatus.TERMINATED, 'Trung tâm chấm dứt (TERMINATED)')])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hinh_thuc'].widget.attrs['class'] = 'form-check-input'
        self.fields['ngay_thanh_ly'].initial = date.today()
