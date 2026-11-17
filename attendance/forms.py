"""Form của app attendance (UC 4.2, 4.4, 4.5). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
from django import forms
from django.conf import settings

from core import thong_bao
from core.forms import BootstrapForm
from employees.models import Department, Position
from .models import ExplanationStatus


class GiaiTrinhForm(BootstrapForm):
    """UC 4.2 – bước 2–3: Lý do giải trình (bắt buộc, kiểm tra trong service để đúng thứ tự §10) + File minh chứng."""
    ly_do = forms.CharField(label='Lý do', required=False,
                            widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mô tả sự cố đã xảy ra ảnh hưởng đến ca làm'}))
    minh_chung = forms.FileField(label='File minh chứng (ảnh/PDF, không bắt buộc)', required=False)

    def clean_minh_chung(self):
        tep = self.cleaned_data.get('minh_chung')
        if tep and (not tep.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png'))
                    or tep.size > settings.FILE_TOI_DA_MB * 1024 * 1024):
            raise forms.ValidationError(thong_bao.FILE_KHONG_HOP_LE)
        return tep


class BoLocGiaiTrinhForm(BootstrapForm):
    """UC 4.4 – bước 1: bộ lọc danh sách giải trình."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm nhân viên'}))
    phong_ban = forms.ChoiceField(required=False, choices=[('', 'Tất cả phòng ban')] + list(Department.choices))
    trang_thai = forms.ChoiceField(required=False, choices=[('', 'Mọi trạng thái')] + [
        (m, l) for m, l in ExplanationStatus.choices if m != ExplanationStatus.NONE])
    thang = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month'}))


class BoLocTongHopForm(BootstrapForm):
    """UC 4.5 – bước 2: Tháng/Năm, Phòng ban, Vị trí."""
    thang = forms.CharField(required=False, widget=forms.TextInput(attrs={'type': 'month'}))
    phong_ban = forms.ChoiceField(required=False, choices=[('', 'Tất cả phòng ban')] + list(Department.choices))
    vi_tri = forms.ChoiceField(required=False, choices=[('', 'Tất cả vị trí')] + list(Position.choices))
