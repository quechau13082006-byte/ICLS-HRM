"""View dạng hàm của app schedule (UC 6.1–6.3): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2).

Phân quyền (§5):
- 6.1 tạo/hủy lớp, 6.3 tạo khung ca / gán người / gỡ người: chỉ Quản lý.
- 6.2 xem lịch: mọi vai trò; lịch làm việc cá nhân lọc ngay trong truy vấn (Kế toán, Nhân viên chỉ thấy của mình).
- 6.3 đăng ký ca, hủy đăng ký: nhân viên Part-time đang làm việc (đăng ký là có ca ngay).
"""
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required, tra_403
from core.services import KhongCoQuyen, LoiNghiepVu
from employees.models import Employee, EmployeeStatus, EmploymentType, Position
from . import services
from .forms import (ChonNhanVienForm, ChonPhanCongForm, GhiNoiDungBuoiForm, HuyLopForm, KhungCaForm, LopHocForm,
                    LUA_CHON_THU)
from .models import ClassStatus, ShiftAssignment, ShiftStatus, StudyClass, TeachingSession

QL, GD = UserRole.MANAGER, UserRole.DIRECTOR

# Các ô của form lớp học được "mang theo" từ bước 1 sang bước 2 qua ô ẩn (không cần lưu session)
TRUONG_LOP = ['class_name', 'subject', 'room_name', 'max_students', 'start_date', 'end_date', 'weekdays',
              'start_time', 'end_time']


def _nhan_su(user):
    """Hồ sơ nhân sự của người đang đăng nhập; None với Giám đốc (không có hồ sơ, §5)."""
    return getattr(user, 'employee', None)


def _doc_ngay(chuoi, mac_dinh):
    """'2026-10-05' → date; sai định dạng hoặc trống thì dùng mặc định (tránh sập khi người dùng sửa URL)."""
    try:
        return datetime.strptime(chuoi, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return mac_dinh


def _ten_khoang(tu, den):
    """'05 – 11 tháng 10, 2026' (tuần nằm gọn một tháng) hoặc '28/09 – 04/10/2026'."""
    if tu == den:
        return f'{tu:%d/%m/%Y}'
    if tu.month == den.month:
        return f'{tu:%d} – {den:%d} tháng {den.month}, {den.year}'
    return f'{tu:%d/%m} – {den:%d/%m/%Y}'


def _qs(tham_so):
    """Dựng chuỗi query (?a=1&b=2) bỏ các giá trị trống."""
    return '?' + urlencode({k: v for k, v in tham_so.items() if v not in (None, '')})


# ============================================================ UC 6.2 – Xem lịch
@role_required()
def lich(request):
    """UC 6.2 – bước 1–4: hai tab (Lịch làm việc | Lịch lớp học), xem theo TUẦN (bản đơn giản: bỏ chế độ xem theo ngày)."""
    hom_nay = date.today()
    la_quan_ly = request.user.role in (QL, GD)
    tab = 'lop_hoc' if request.GET.get('tab') == 'lop_hoc' else 'lam_viec'
    ngay = _doc_ngay(request.GET.get('ngay'), hom_nay)
    tu_ngay = services.dau_tuan(ngay)
    den_ngay = tu_ngay + timedelta(days=6)

    loc = {'nv': request.GET.get('nv', ''), 'gv': request.GET.get('gv', ''), 'nhom': request.GET.get('nhom', '')}
    tuy_chon = {}
    if tab == 'lam_viec':
        nhan_su_loc = None
        if loc['nv'].isdigit():
            if not la_quan_ly:
                # Luồng 1.1: nhân viên sửa đường dẫn để xem lịch người khác → từ chối
                if _nhan_su(request.user) is None or _nhan_su(request.user).pk != int(loc['nv']):
                    return tra_403(request, thong_bao.KHONG_XEM_LICH_NGUOI_KHAC)
            else:
                nhan_su_loc = Employee.objects.filter(pk=loc['nv']).first()
        cac_muc = services.lich_lam_viec(request.user, tu_ngay, den_ngay, nhan_su_loc)
        if la_quan_ly:
            tuy_chon['nhan_vien'] = Employee.objects.filter(status=EmployeeStatus.ACTIVE).order_by('full_name')
    else:
        giao_vien = Employee.objects.filter(pk=loc['gv']).first() if la_quan_ly and loc['gv'].isdigit() else None
        cac_muc = services.lich_lop_hoc(tu_ngay, den_ngay, giao_vien)
        if la_quan_ly:
            tuy_chon['giao_vien'] = Employee.objects.filter(position=Position.TEACHER,
                                                            status=EmployeeStatus.ACTIVE).order_by('full_name')

    buoc = timedelta(days=7)
    nen = {'tab': tab, **loc}
    # Hai kiểu bảng tuần: lịch lớp học = bảng theo PHÒNG; lịch làm việc = bảng theo NHÂN SỰ (Quản lý/Giám đốc thấy cả
    # trung tâm; nhân viên chỉ một hàng là chính mình).
    kieu = 'bang_phong' if tab == 'lop_hoc' else 'bang_nhan_su'
    bang, tom_tat, cac_nut_loc = None, None, []
    if kieu == 'bang_phong':
        bang = services.dung_bang_phong(cac_muc, tu_ngay, hom_nay)
    elif not la_quan_ly:
        bang = services.dung_bang_nhan_su(cac_muc, tu_ngay, hom_nay)
    else:
        bang = services.dung_bang_nhan_su(cac_muc, tu_ngay, hom_nay, loc['nhom'])
        if loc['nhom'] in ('', 'part_time'):
            bang['cho_trong'] = services.cho_ca_con_trong(tu_ngay)
        tom_tat = services.tom_tat_tuan(cac_muc, tu_ngay, hom_nay)
        # Nút lọc nhanh theo nhóm (thay cho ô chọn từng nhân sự)
        cac_nut_loc = [{'ten': ten, 'dang_chon': loc['nhom'] == ma, 'url': _qs({'tab': tab, 'ngay': ngay, 'nhom': ma})}
                       for ma, ten in (('', 'Tất cả'), ('part_time', 'Part-time'), ('tro_giang', 'Trợ giảng'),
                                       ('full_time', 'Full-time'), ('nghi', 'Có nghỉ phép'))]
    return render(request, 'schedule/lich.html', {
        'tab': tab, 'kieu': kieu, 'bang': bang, 'tom_tat': tom_tat, 'cac_nut_loc': cac_nut_loc, 'tu_ngay': tu_ngay, 'la_quan_ly': la_quan_ly, 'loc': loc, 'tuy_chon': tuy_chon,
        'ten_khoang': _ten_khoang(tu_ngay, den_ngay), 'co_lich': bool(cac_muc), 'khong_co_lich': thong_bao.KHONG_CO_LICH,
        'url_hom_nay': _qs({**nen, 'ngay': hom_nay}), 'url_truoc': _qs({**nen, 'ngay': ngay - buoc}),
        'url_sau': _qs({**nen, 'ngay': ngay + buoc}),
        'url_tab_lam_viec': _qs({'tab': 'lam_viec', 'ngay': ngay}),
        'url_tab_lop_hoc': _qs({'tab': 'lop_hoc', 'ngay': ngay}),
        'la_part_time': services.la_part_time_hoat_dong(_nhan_su(request.user))})


@role_required()
def chi_tiet_buoi(request, pk):
    """UC 6.2 – bước 5–6 và luồng 5.1: chi tiết buổi dạy; giáo viên thực tế ghi nội dung buổi học."""
    buoi = get_object_or_404(TeachingSession.objects.select_related(
        'study_class', 'actual_teacher', 'planned_teacher', 'actual_assistant'), pk=pk)
    nhan_su = _nhan_su(request.user)
    la_gv_thuc_te = nhan_su is not None and nhan_su.pk == (buoi.actual_teacher_id or buoi.planned_teacher_id)
    form = GhiNoiDungBuoiForm(request.POST or None, initial={'lesson_note': buoi.lesson_note})
    if request.method == 'POST':
        try:
            services.ghi_noi_dung_buoi_hoc(request.user, buoi, request.POST.get('lesson_note', ''))
        except KhongCoQuyen as loi:
            return tra_403(request, str(loi))
        messages.success(request, thong_bao.GHI_NOI_DUNG_THANH_CONG)
        return redirect('schedule:session_detail', pk=pk)
    return render(request, 'schedule/chi_tiet_buoi.html', {
        'buoi': buoi, 'giao_vien': buoi.actual_teacher or buoi.planned_teacher, 'la_gv_thuc_te': la_gv_thuc_te,
        'form': form, 'la_quan_ly': request.user.role == QL})


@role_required()
def chi_tiet_ca(request, pk):
    """UC 6.2 – bước 5–6: bấm một ca trên lịch → trang Khung ca của ca đó, tô sáng chỗ được bấm.
    Quản lý / Giám đốc thấy mọi chỗ của khung (Quản lý gán, gỡ người được); nhân viên chỉ thấy chỗ của chính mình.
    Luồng 1.1: không được xem ca của người khác."""
    cho = get_object_or_404(ShiftAssignment.objects.select_related('employee__user'), pk=pk)
    if not services.co_quyen_xem_ca(request.user, cho):
        return tra_403(request, thong_bao.KHONG_XEM_LICH_NGUOI_KHAC)
    return _trang_khung(request, cho.slot_group, cho_dang_xem=cho)


# ============================================================ UC 6.1 – Tạo và phân công lớp học
@role_required(QL)
def tao_lop(request):
    """UC 6.1 – bước 1–8, hai bước trên màn hình: (1) Thông tin lớp → (2) Phân công giáo viên & phòng.

    Không lưu gì vào CSDL ở bước 1: dữ liệu bước 1 được mang sang bước 2 bằng ô ẩn, đến "Xác nhận phân công"
    mới gọi service tạo lớp (một giao dịch)."""
    if request.method != 'POST':
        return render(request, 'schedule/tao_lop.html', {'buoc': 1, 'form': LopHocForm(), 'thu': LUA_CHON_THU, 'thu_chon': []})

    form = LopHocForm(request.POST)
    nut = request.POST.get('buoc', '1')                 # "1" = Tiếp tục, "2" = Xác nhận, "0" = Quay lại
    if nut != '0' and form.is_valid():
        du_lieu = form.cleaned_data
        try:
            goi_y = services.chuan_bi_phan_cong(du_lieu)                              # bước 4–5
        except services.LoiTruongNhap as loi:
            form.add_error(loi.truong, str(loi))                                      # luồng 3.2, 3.3
        else:
            phan_cong = ChonPhanCongForm(request.POST if nut == '2' else None)
            if nut == '2' and phan_cong.is_valid():
                try:
                    lop, so_buoi = services.tao_lop_va_phan_cong(                      # bước 6–8
                        request.user, du_lieu, phan_cong.cleaned_data['giao_vien'], phan_cong.cleaned_data['tro_giang'])
                except services.LoiTruongNhap as loi:
                    phan_cong.add_error(loi.truong if loi.truong in phan_cong.fields else None, str(loi))  # luồng 6.1
                else:
                    messages.success(request, thong_bao.TAO_LOP_THANH_CONG.format(so_buoi=so_buoi))
                    return redirect('schedule:class_detail', pk=lop.pk)
            an = [(k, v) for k, cac_gia_tri in request.POST.lists() if k in TRUONG_LOP for v in cac_gia_tri]
            return render(request, 'schedule/tao_lop.html', {
                'buoc': 2, 'form': form, 'phan_cong': phan_cong, 'an': an, 'du_lieu': du_lieu,
                'cac_ngay': goi_y['cac_ngay'], 'thu_hoc': services.chuoi_thu_hoc(du_lieu['weekdays']),
                'giao_vien': [{'nv': nv, 'so_lop': services.so_lop_dang_day(nv), 'han': services.la_giao_vien_han_quoc(nv)} for nv in goi_y['giao_vien']],
                'tro_giang': goi_y['tro_giang'], 'giao_vien_chon': request.POST.get('giao_vien', ''),
                'tro_giang_chon': request.POST.get('tro_giang', '')})
    return render(request, 'schedule/tao_lop.html', {
        'buoc': 1, 'form': form, 'thu': LUA_CHON_THU, 'thu_chon': request.POST.getlist('weekdays')})


@role_required()
def chi_tiet_lop(request, pk):
    """Chi tiết lớp: thông tin, phân công, danh sách buổi; Quản lý có nút "Hủy lớp" (UC 6.1 luồng 1.1)."""
    lop = get_object_or_404(StudyClass, pk=pk)
    return render(request, 'schedule/chi_tiet_lop.html', {
        'lop': lop, 'thu_hoc': services.chuoi_thu_hoc(lop.weekdays),
        'phan_cong': lop.assignments.select_related('employee').order_by('assignment_role', 'start_date'),
        'cac_buoi': lop.teaching_sessions.select_related('actual_teacher', 'planned_teacher').order_by('session_date'),
        'la_quan_ly': request.user.role == QL, 'form_huy': HuyLopForm(),
        'huy_duoc': lop.status in (ClassStatus.UPCOMING, ClassStatus.ACTIVE)})


@role_required(QL)
@require_POST
def huy_lop(request, pk):
    """UC 6.1 – luồng thay thế 1.1: hủy lớp kèm lý do."""
    lop = get_object_or_404(StudyClass, pk=pk)
    form = HuyLopForm(request.POST)
    form.is_valid()
    try:
        so_buoi = services.huy_lop(request.user, lop, form.cleaned_data.get('ly_do', ''))
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.HUY_LOP_THANH_CONG.format(so_buoi=so_buoi))
    return redirect('schedule:class_detail', pk=pk)


# ============================================================ UC 6.3 – Khung ca Part-time
@role_required(QL)
def tao_khung_ca(request):
    """UC 6.3 – bước 1–2: Quản lý mở khung ca (tạo N chỗ, mời nhân viên Part-time)."""
    form = KhungCaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            services.tao_khung_ca(request.user, d['vai_tro'], d['ngay'], d['bat_dau'], d['ket_thuc'], d['so_nguoi'],
                                  d['han_chot'])
        except services.LoiTruongNhap as loi:
            form.add_error(loi.truong, str(loi))
        else:
            messages.success(request, thong_bao.TAO_KHUNG_CA_THANH_CONG.format(
                vai_tro=d['vai_tro'], ngay=f"{d['ngay']:%d/%m/%Y}", so_nguoi=d['so_nguoi']))
            return redirect('schedule:shift_review')
    return render(request, 'schedule/tao_khung_ca.html', {'form': form})


def _tuan_hien_thi(request):
    """Tuần đang xem của các trang ca làm việc: (thứ 2, chủ nhật, ngày neo)."""
    ngay = _doc_ngay(request.GET.get('ngay'), date.today())
    tu = services.dau_tuan(ngay)
    return tu, tu + timedelta(days=6), ngay


@role_required()
def dang_ky_ca(request):
    """UC 6.3: nhân viên Part-time xem các khung ca của tuần, bấm "Đăng ký" (có ca ngay) hoặc "Hủy đăng ký"."""
    nhan_su = _nhan_su(request.user)
    if not services.la_part_time_hoat_dong(nhan_su):
        return tra_403(request, thong_bao.CHI_PART_TIME_DANG_KY)
    bay_gio = datetime.now()
    tu, den, ngay = _tuan_hien_thi(request)
    cac_khung = [k for k in services.danh_sach_khung_ca(tu, den, bay_gio) if k['trang_thai'] != 'DA_HUY']
    for khung in cac_khung:
        cho_cua_toi = next((c for c in khung['cac_cho']
                            if c.employee_id == nhan_su.pk and c.status == ShiftStatus.SCHEDULED), None)
        khung['cua_toi'] = cho_cua_toi
        if cho_cua_toi is not None:
            khung['trang_thai_toi'] = 'DA_DANG_KY'
        elif khung['het_han']:
            khung['trang_thai_toi'] = 'DONG'
        elif khung['thieu'] == 0:
            khung['trang_thai_toi'] = 'DA_DU'
        else:
            khung['trang_thai_toi'] = 'DANG_MO'
        khung['buoi_trong_ngay'] = 'Sáng' if khung['bd'].hour < 12 else ('Chiều' if khung['bd'].hour < 17 else 'Tối')
    cot = [{'ngay': tu + timedelta(days=i), 'thu': services.TEN_THU[i],
            'cac_khung': [k for k in cac_khung if k['ngay'] == tu + timedelta(days=i)]} for i in range(7)]
    return render(request, 'schedule/dang_ky_ca.html', {
        'nhan_su': nhan_su, 'cot': cot, 'ten_khoang': _ten_khoang(tu, den), 'hom_nay': date.today(),
        'so_ca': len(cac_khung), 'so_ca_mo': sum(1 for k in cac_khung if k['trang_thai_toi'] == 'DANG_MO'),
        'so_vi_tri': sum(k['so_can'] for k in cac_khung), 'so_da_chon': sum(1 for k in cac_khung if k['cua_toi']),
        'url_truoc': _qs({'ngay': ngay - timedelta(days=7)}), 'url_sau': _qs({'ngay': ngay + timedelta(days=7)}),
        'url_hom_nay': _qs({'ngay': date.today()}), 'ngay_neo': ngay, 'la_quan_ly': False,
        'la_part_time': True})


def _ve_trang_dang_ky(ma):
    """Sau khi đăng ký / hủy: quay về đúng tuần của khung ca vừa thao tác."""
    cho = ShiftAssignment.objects.filter(slot_group=ma).first()
    return redirect(reverse('schedule:shift_register') + (_qs({'ngay': cho.work_date}) if cho else ''))


@role_required()
@require_POST
def nhan_ca(request, ma):
    """UC 6.3: nhấn "Đăng ký" một khung ca."""
    nhan_su = _nhan_su(request.user)
    if not services.la_part_time_hoat_dong(nhan_su):
        return tra_403(request, thong_bao.CHI_PART_TIME_DANG_KY)
    try:
        services.dang_ky_ca(nhan_su, ma)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.DANG_KY_CA_THANH_CONG)
    return _ve_trang_dang_ky(ma)


@role_required()
@require_POST
def huy_nhan_ca(request, ma):
    """UC 6.3: "Hủy đăng ký" trước hạn chót."""
    nhan_su = _nhan_su(request.user)
    if not services.la_part_time_hoat_dong(nhan_su):
        return tra_403(request, thong_bao.CHI_PART_TIME_DANG_KY)
    try:
        services.huy_dang_ky_ca(nhan_su, ma)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.DA_HUY_DANG_KY_CA)
    return _ve_trang_dang_ky(ma)


@role_required(QL)
def tong_hop_ca(request):
    """UC 6.3: Quản lý xem tổng hợp đăng ký ca của một tuần (ca còn thiếu, nhân viên chưa đăng ký)."""
    bay_gio = datetime.now()
    tu, den, ngay = _tuan_hien_thi(request)
    cac_khung = [k for k in services.danh_sach_khung_ca(tu, den, bay_gio) if k['trang_thai'] != 'DA_HUY']
    co_nguoi = {nv.pk for k in cac_khung for nv in k['nhan_vien']}
    chua_dang_ky = Employee.objects.filter(employment_type=EmploymentType.PART_TIME,
                                           status=EmployeeStatus.ACTIVE).exclude(pk__in=co_nguoi).select_related('user').order_by('full_name')
    khung_thieu = [k for k in cac_khung if k['thieu'] > 0]
    return render(request, 'schedule/tong_hop_ca.html', {
        'cac_khung': cac_khung, 'ten_khoang': _ten_khoang(tu, den),
        'so_ca_dang_mo': sum(1 for k in cac_khung if k['trang_thai'] == 'DANG_MO'),
        'so_vi_tri': sum(k['so_can'] for k in cac_khung), 'luot_dang_ky': sum(k['da_dang_ky'] for k in cac_khung),
        'so_ca_thieu': len(khung_thieu), 'khung_thieu': khung_thieu, 'chua_dang_ky': chua_dang_ky,
        'ngay_neo': ngay, 'tu_ngay': tu, 'la_quan_ly': True,
        'url_truoc': _qs({'ngay': ngay - timedelta(days=7)}), 'url_sau': _qs({'ngay': ngay + timedelta(days=7)}),
        'url_hom_nay': _qs({'ngay': date.today()})})


@role_required(QL)
def khung_ca(request, ma):
    """UC 6.3: xem từng chỗ của một khung ca; Quản lý gỡ người hoặc gán người vào chỗ trống."""
    return _trang_khung(request, ma)


def _trang_khung(request, ma, cho_dang_xem=None):
    """Trang Khung ca dùng chung cho Quản lý (từ Tổng hợp ca) và cho mọi người (bấm ca trên lịch)."""
    khung = services.khung_ca_cua(ma)
    if khung is None:
        messages.error(request, thong_bao.KHONG_TIM_THAY_KHUNG_CA)
        return redirect('schedule:shift_review' if request.user.role == QL else 'schedule:calendar')
    la_quan_ly = request.user.role == QL
    xem_tat_ca = request.user.role in (QL, GD)
    cac_cho = khung['cac_cho'] if xem_tat_ca else [cho_dang_xem]          # nhân viên: chỉ chỗ của mình
    ung_vien = services.goi_y_nhan_vien_part_time(khung['cac_cho'][0]) if la_quan_ly else []
    return render(request, 'schedule/khung_ca.html', {
        'khung': khung, 'cac_cho': cac_cho, 'cho_dang_xem': cho_dang_xem, 'ung_vien': ung_vien,
        'la_quan_ly': la_quan_ly, 'xem_tat_ca': xem_tat_ca})


def _ve_khung(ma):
    return redirect('schedule:shift_group', ma=ma)


@role_required(QL)
@require_POST
def go_nguoi(request, pk):
    cho = get_object_or_404(ShiftAssignment.objects.select_related('employee__user'), pk=pk)
    try:
        services.go_nguoi_khoi_cho(request.user, cho)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.DA_BO_NGUOI_KHOI_CA)
    return _ve_khung(cho.slot_group)


@role_required(QL)
@require_POST
def gan_nguoi(request, pk):
    cho = get_object_or_404(ShiftAssignment, pk=pk)
    form = ChonNhanVienForm(request.POST)
    if not form.is_valid():
        messages.error(request, ' '.join(m for ds in form.errors.values() for m in ds))
    else:
        try:
            services.gan_nhan_vien_vao_cho(request.user, cho, form.cleaned_data['nhan_su'])
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        else:
            messages.success(request, thong_bao.DA_GAN_NHAN_VIEN_VAO_CA)
    return _ve_khung(cho.slot_group)


# ============================================================ UC 6.4 – Xử lý dạy thay
@role_required(QL, GD)
def day_thay_danh_sach(request):
    """UC 6.4 – bước 1–2: "Buổi dạy cần người thay" – các yêu cầu SEARCHING (nguồn: đơn nghỉ hoặc thanh lý).
    Quản lý bấm vào để xử lý; Giám đốc chỉ xem danh sách."""
    cac_yeu_cau = list(services.yeu_cau_day_thay_dang_tim())
    for yc in cac_yeu_cau:
        yc.giao_vien_vang = services.giao_vien_vang(yc)
        yc.nguon = services.nguon_yeu_cau(yc)
    return render(request, 'schedule/day_thay_ds.html', {'cac_yeu_cau': cac_yeu_cau,
                                                         'la_quan_ly': request.user.role in (QL, GD),
                                                         'xu_ly_duoc': request.user.role == QL})


@role_required(QL)
def day_thay_chi_tiet(request, pk):
    """UC 6.4 – bước 3–7 và luồng 5.1: gợi ý giáo viên, "Chốt dạy thay" hoặc "Hủy buổi học".

    Chốt bị trùng lịch (luồng 5.3) thì hiện lại danh sách gợi ý (trở lại bước 4) kèm câu lỗi."""
    yc = get_object_or_404(services.SubstituteRequest.objects.select_related(
        'teaching_session__study_class', 'teaching_session__actual_teacher', 'teaching_session__planned_teacher',
        'leave_request__employee'), pk=pk)
    buoi = yc.teaching_session
    loi = None
    if request.method == 'POST':
        hanh_dong = request.POST.get('hanh_dong')
        try:
            if hanh_dong == 'huy_buoi':
                services.huy_buoi_hoc(request.user, yc)
                messages.success(request, thong_bao.DA_HUY_BUOI_HOC)
                return redirect('schedule:substitute_list')
            form = ChonNhanVienForm({'nhan_su': request.POST.get('giao_vien')})
            if not form.is_valid():
                loi = 'Vui lòng chọn giáo viên dạy thay.'
            else:
                services.chot_day_thay(request.user, yc, form.cleaned_data['nhan_su'])
                messages.success(request, thong_bao.DA_CHOT_DAY_THAY)
                return redirect('schedule:substitute_list')
        except LoiNghiepVu as e:
            loi = str(e)
            if str(e) == thong_bao.YEU_CAU_DAY_THAY_DA_XU_LY:
                messages.error(request, loi)
                return redirect('schedule:substitute_list')
    dang_tim = yc.status == services.SubstituteStatus.SEARCHING
    return render(request, 'schedule/day_thay_chi_tiet.html', {
        'yc': yc, 'buoi': buoi, 'giao_vien_vang': services.giao_vien_vang(yc), 'nguon': services.nguon_yeu_cau(yc),
        'goi_y': services.goi_y_giao_vien_day_thay(yc) if dang_tim else [], 'dang_tim': dang_tim, 'loi': loi,
        'giao_vien_chon': request.POST.get('giao_vien', ''), 'la_quan_ly': True})
