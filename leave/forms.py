"""Form của app leave (UC 5.1–5.4). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
from django import forms

from core.forms import BootstrapForm
from employees.models import Department, Position
from .models import LeaveStatus, LeaveType

NGAY = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
THANG = forms.TextInput(attrs={'type': 'month'})


class DonNghiForm(BootstrapForm):
    """UC 5.1 – bước 2–3: Loại nghỉ, Từ ngày, Đến ngày, Lý do. Nghỉ luôn theo cả ngày (không có nghỉ nửa ngày).

    Cố ý KHÔNG kiểm tra "ngày bắt đầu ≤ kết thúc" ở đây: luật đó nằm trong `services.gui_don_nghi` theo đúng thứ tự §10."""
    leave_type = forms.ChoiceField(label='Loại nghỉ', choices=LeaveType.choices)
    start_date = forms.DateField(label='Từ ngày', widget=NGAY)
    end_date = forms.DateField(label='Đến ngày', widget=NGAY)
    reason = forms.CharField(label='Lý do', widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Nhập lý do xin nghỉ'}))


class BoLocDuyetForm(BootstrapForm):
    """UC 5.2 – bước 1: bộ lọc danh sách đơn chờ duyệt (như Figma: tìm nhân viên, bộ phận, loại nghỉ, trạng thái, tháng)."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Tìm nhân viên'}))
    phong_ban = forms.ChoiceField(required=False, choices=[('', 'Bộ phận: Tất cả')] + list(Department.choices))
    loai = forms.ChoiceField(required=False, choices=[('', 'Loại nghỉ: Tất cả')] + list(LeaveType.choices))
    trang_thai = forms.ChoiceField(required=False, choices=[('', 'Trạng thái: Tất cả')] + list(LeaveStatus.choices))
    thang = forms.CharField(required=False, widget=THANG)


class BoLocTongHopForm(BootstrapForm):
    """UC 5.4 – bước 2: Tháng/Năm, Phòng ban, Vị trí, Loại nghỉ."""
    thang = forms.CharField(required=False, widget=THANG)
    phong_ban = forms.ChoiceField(required=False, choices=[('', 'Phòng ban: Tất cả')] + list(Department.choices))
    vi_tri = forms.ChoiceField(required=False, choices=[('', 'Vị trí: Tất cả')] + list(Position.choices))
    loai = forms.ChoiceField(required=False, choices=[('', 'Loại nghỉ: Tất cả')] + list(LeaveType.choices))
