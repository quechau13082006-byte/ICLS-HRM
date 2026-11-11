"""Form của app schedule (UC 6.1 – 6.3). Form chỉ kiểm tra định dạng nhập liệu; luật nghiệp vụ ở services.py."""
from django import forms

from core import thong_bao
from core.forms import BootstrapForm
from employees.models import Employee
from .services import TEN_THU

LUA_CHON_THU = [(str(i), ten) for i, ten in enumerate(TEN_THU)]
GIO = forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')
NGAY = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


class LopHocForm(BootstrapForm):
    """UC 6.1 – bước 2–3: thông tin lớp. Các thứ học đọc từ nhiều ô tích (name="weekdays") và gộp thành "0,2,4"."""
    class_name = forms.CharField(label='Tên lớp', max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: TOPIK 2'}))
    subject = forms.CharField(label='Môn / Trình độ', max_length=100,
                              widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: Trung cấp · TOPIK'}))
    room_name = forms.CharField(label='Phòng học', max_length=100, required=False,
                                widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: Phòng 201'}),
                                help_text='Dùng để kiểm tra trùng phòng; để trống nếu chưa có phòng')
    max_students = forms.IntegerField(label='Sĩ số tối đa', min_value=0, initial=20)
    start_date = forms.DateField(label='Ngày bắt đầu', widget=NGAY)
    end_date = forms.DateField(label='Ngày kết thúc dự kiến', widget=NGAY)
    weekdays = forms.MultipleChoiceField(label='Các thứ học trong tuần', choices=LUA_CHON_THU,
                                         error_messages={'required': thong_bao.CHON_THU_HOC})
    start_time = forms.TimeField(label='Giờ bắt đầu', widget=GIO)
    end_time = forms.TimeField(label='Giờ kết thúc', widget=GIO)

    def clean_weekdays(self):
        return ','.join(str(x) for x in sorted(int(t) for t in self.cleaned_data['weekdays']))

    def clean(self):
        du_lieu = super().clean()
        gio_bd, gio_kt = du_lieu.get('start_time'), du_lieu.get('end_time')
        if gio_bd and gio_kt and gio_kt <= gio_bd:
            self.add_error('end_time', thong_bao.GIO_KET_THUC_LOP_SAI)          # luồng 3.1
        ngay_bd, ngay_kt = du_lieu.get('start_date'), du_lieu.get('end_date')
        if ngay_bd and ngay_kt and ngay_kt < ngay_bd:
            self.add_error('end_date', thong_bao.NGAY_KET_THUC_LOP_SAI)        # luồng 3.1
        return du_lieu


class ChonPhanCongForm(BootstrapForm):
    """UC 6.1 – bước 6: chọn giáo viên chính (bắt buộc) và trợ giảng (không bắt buộc). Việc "có nằm trong danh
    sách gợi ý không" do service kiểm tra lại (bước 7)."""
    giao_vien = forms.ModelChoiceField(queryset=Employee.objects.all(),
                                       error_messages={'required': 'Vui lòng chọn giáo viên chính.',
                                                       'invalid_choice': 'Giáo viên không hợp lệ.'})
    tro_giang = forms.ModelChoiceField(queryset=Employee.objects.all(), required=False,
                                       error_messages={'invalid_choice': 'Trợ giảng không hợp lệ.'})


class HuyLopForm(BootstrapForm):
    """UC 6.1 – luồng thay thế 1.1: lý do hủy lớp (service kiểm tra bắt buộc)."""
    ly_do = forms.CharField(label='Lý do hủy lớp', required=False, widget=forms.Textarea(attrs={'rows': 3}))


class GhiNoiDungBuoiForm(BootstrapForm):
    """UC 6.2 – luồng thay thế 5.1: nội dung buổi học."""
    lesson_note = forms.CharField(label='Nội dung buổi học', required=False, widget=forms.Textarea(attrs={'rows': 5}))


class KhungCaForm(BootstrapForm):
    """UC 6.3 – bước 1: Quản lý mở khung ca."""
    vai_tro = forms.CharField(label='Vai trò ca', max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Ví dụ: Lễ tân, Tư vấn'}))
    ngay = forms.DateField(label='Ngày', widget=NGAY)
    bat_dau = forms.TimeField(label='Giờ bắt đầu', widget=GIO)
    ket_thuc = forms.TimeField(label='Giờ kết thúc', widget=GIO)
    so_nguoi = forms.IntegerField(label='Số người cần', min_value=1, initial=1,
                                  error_messages={'min_value': thong_bao.SO_NGUOI_CA_SAI})
    han_chot = forms.DateTimeField(label='Hạn chót đăng ký', input_formats=['%Y-%m-%dT%H:%M'],
                                   widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))

    def clean(self):
        du_lieu = super().clean()
        if du_lieu.get('bat_dau') and du_lieu.get('ket_thuc') and du_lieu['ket_thuc'] <= du_lieu['bat_dau']:
            self.add_error('ket_thuc', thong_bao.GIO_KET_THUC_LOP_SAI)
        return du_lieu


class ChonNhanVienForm(BootstrapForm):
    """UC 6.3 – bước 8 và luồng 8.1: chọn nhân viên để gán vào chỗ trống / đổi người."""
    nhan_su = forms.ModelChoiceField(queryset=Employee.objects.all(),
                                     error_messages={'required': 'Vui lòng chọn nhân viên.',
                                                     'invalid_choice': thong_bao.NHAN_VIEN_CA_KHONG_HOP_LE})


class BuoiBuForm(BootstrapForm):
    """UC 6.4 – luồng thay thế 5.2: chọn ngày, giờ (và phòng, giáo viên mặc định lấy từ buổi đã hủy) cho buổi học bù."""
    ngay = forms.DateField(label='Ngày học bù', widget=NGAY)
    bat_dau = forms.TimeField(label='Giờ bắt đầu', widget=GIO)
    ket_thuc = forms.TimeField(label='Giờ kết thúc', widget=GIO)
    room_name = forms.CharField(label='Phòng học', max_length=100, required=False)
    giao_vien = forms.ModelChoiceField(label='Giáo viên', queryset=Employee.objects.none(), empty_label=None,
                                       error_messages={'required': 'Vui lòng chọn giáo viên.',
                                                       'invalid_choice': thong_bao.GIAO_VIEN_KHONG_HOP_LE})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['giao_vien'].queryset = Employee.objects.filter(position='TEACHER', status='ACTIVE').order_by('full_name')
