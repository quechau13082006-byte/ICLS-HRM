
from datetime import date, datetime

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required, tra_403
from core.services import KhongCoQuyen, LoiNghiepVu, LoiTruongNhap
from employees.models import Employee
from . import services
from .forms import BoLocGiaiTrinhForm, BoLocTongHopForm, GiaiTrinhForm
from .models import Attendance, AttendanceStatus, ExplanationStatus

QL, KT, SA = UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.SUPER_ADMIN


def _nhan_su(user):
    """Hồ sơ nhân sự của người đăng nhập; None với Super Admin (§5)."""
    return getattr(user, 'employee', None)


def _doc_thang(chuoi, mac_dinh):
    """'2026-10' (ô chọn tháng của trình duyệt) → (tháng, năm); sai định dạng thì dùng mặc định."""
    try:
        d = datetime.strptime(chuoi, '%Y-%m')
        return d.month, d.year
    except (TypeError, ValueError):
        return mac_dinh


# ============================================================ UC 4.1 + 4.3 – Chấm công của tôi
@role_required()
def cua_toi(request):
    """UC 4.1 – bước 1–2 (lịch hôm nay + nút Check-in/Check-out) và UC 4.3 (lịch sử theo tháng, tổng công)."""
    nhan_su = _nhan_su(request.user)
    if nhan_su is None:
        return redirect('attendance:summary')            # Super Admin không chấm công, đưa tới bảng tổng hợp
    hom_nay = date.today()
    thang, nam = _doc_thang(request.GET.get('thang'), (hom_nay.month, hom_nay.year))
    lich_su = list(services.lich_su_cham_cong(nhan_su, thang, nam))
    for b in lich_su:
        b.chenh_lech = services.mo_ta_chenh_lech(b)
        b.giai_trinh_duoc = services.la_loi_co_the_giai_trinh(b)
    cong, don_vi = services.tong_cong_thang(nhan_su, thang, nam)
    return render(request, 'attendance/cua_toi.html', {
        'nhan_su': nhan_su, 'hom_nay': hom_nay, 'bay_gio': datetime.now(), 'man_hinh': services.man_hinh_cham_cong(nhan_su, hom_nay),
        'lich_su': lich_su, 'cong': cong, 'don_vi': don_vi, 'thang': thang, 'nam': nam, 'thang_nhap': f'{nam}-{thang:02d}',
        'khong_co_du_lieu': thong_bao.KHONG_CO_DU_LIEU_CHAM_CONG, 'tab': 'cua_toi',
        'dem_dung_gio': sum(1 for b in lich_su if b.attendance_status == AttendanceStatus.ON_TIME),
        'dem_bat_thuong': sum(1 for b in lich_su if b.attendance_status in services.TRANG_THAI_LOI),
        'dem_cho_duyet': sum(1 for b in lich_su if b.explanation_status == ExplanationStatus.PENDING)})


def _can_ho_so(request):
    """Trả về hồ sơ nhân sự, hoặc None khi tài khoản không có hồ sơ (Super Admin)."""
    return _nhan_su(request.user)


@role_required()
@require_POST
def nhan_check_in(request):
    """UC 4.1 – bước 3–5: nút "Check-in" (Part-time nhiều ca thì gửi kèm mã ca)."""
    nhan_su = _can_ho_so(request)
    if nhan_su is None:
        return tra_403(request, thong_bao.KHONG_CO_HO_SO)
    try:
        ban_ghi = services.check_in(nhan_su, ma_ca=request.POST.get('ma_ca') or None)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))               # luồng 1.1, 1.2, 3.1
    else:
        messages.success(request, thong_bao.CHECK_IN_THANH_CONG.format(gio=f'{ban_ghi.check_in:%H:%M}'))
    return redirect('attendance:my_attendance')


@role_required()
@require_POST
def nhan_check_out(request):
    """UC 4.1 – bước 6–8: nút "Check-out"."""
    nhan_su = _can_ho_so(request)
    if nhan_su is None:
        return tra_403(request, thong_bao.KHONG_CO_HO_SO)
    try:
        ban_ghi = services.check_out(nhan_su, ma_ca=request.POST.get('ma_ca') or None)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))               # luồng 6.2: "Vui lòng thực hiện Check-in trước."
    else:
        messages.success(request, thong_bao.CHECK_OUT_THANH_CONG.format(
            gio=f'{ban_ghi.check_out:%H:%M}', tong=services.tong_thoi_gian_lam(ban_ghi)))
    return redirect('attendance:my_attendance')


# ============================================================ UC 4.2 – Gửi giải trình
@role_required()
def gui_giai_trinh(request, pk):
    """UC 4.2 – bước 1–5: form giải trình cho một dòng chấm công lỗi của chính mình."""
    nhan_su = _nhan_su(request.user)
    ban_ghi = get_object_or_404(Attendance.objects.select_related('employee', 'shift_assignment'), pk=pk)
    if nhan_su is None or ban_ghi.employee_id != nhan_su.pk:
        return tra_403(request, thong_bao.KHONG_XEM_BAN_GHI_CHAM_CONG)
    try:
        services.kiem_tra_co_the_giai_trinh(nhan_su, ban_ghi)       # luồng 1.1, 1.2: chặn ngay khi mở form
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
        return redirect('attendance:my_attendance')
    form = GiaiTrinhForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.gui_giai_trinh(nhan_su, ban_ghi, form.cleaned_data['ly_do'], form.cleaned_data['minh_chung'])
        except LoiTruongNhap as loi:
            form.add_error(loi.truong if loi.truong in form.fields else None, str(loi))        # luồng 3.1
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
            return redirect('attendance:my_attendance')
        else:
            messages.success(request, thong_bao.GUI_GIAI_TRINH_THANH_CONG)
            return redirect('attendance:my_attendance')
    ban_ghi.chenh_lech = services.mo_ta_chenh_lech(ban_ghi)
    return render(request, 'attendance/giai_trinh.html', {'form': form, 'ban_ghi': ban_ghi, 'tab': 'cua_toi'})


# ============================================================ UC 4.4 – Duyệt giải trình
@role_required(QL, SA)
def danh_sach_giai_trinh(request):
    """UC 4.4 – bước 1–2: giải trình thuộc phạm vi duyệt (mặc định chỉ "Chờ duyệt")."""
    hom_nay = date.today()
    bo_loc = BoLocGiaiTrinhForm(request.GET if request.GET else {'trang_thai': ExplanationStatus.PENDING})
    loc = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    thang = nam = None
    if loc.get('thang'):
        thang, nam = _doc_thang(loc['thang'], (hom_nay.month, hom_nay.year))
    ds = services.danh_sach_giai_trinh(request.user, loc.get('trang_thai', ''), loc.get('q', ''), loc.get('phong_ban', ''), thang, nam)
    tham_so = request.GET.copy()
    tham_so.pop('page', None)
    trang = Paginator(ds, settings.SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    for b in trang:
        b.chenh_lech = services.mo_ta_chenh_lech(b)
    return render(request, 'attendance/duyet.html', {
        'bo_loc': bo_loc, 'trang': trang, 'tham_so_trang': tham_so, 'tab': 'duyet',
        'so_cho_duyet': services.pham_vi_duyet(request.user).filter(explanation_status=ExplanationStatus.PENDING).count()})


@role_required()
def chi_tiet_giai_trinh(request, pk):
    """UC 4.4 – bước 3–4: giờ dự kiến, giờ thực tế, lý do, minh chứng. Chủ bản ghi và người duyệt trong phạm vi xem được."""
    ban_ghi = get_object_or_404(Attendance.objects.select_related('employee__user', 'shift_assignment', 'explanation_reviewed_by'), pk=pk)
    if not services.co_quyen_xem_giai_trinh(request.user, ban_ghi):
        return tra_403(request, thong_bao.KHONG_XEM_BAN_GHI_CHAM_CONG)
    la_chu = ban_ghi.employee.user_id == request.user.pk
    ban_ghi.chenh_lech = services.mo_ta_chenh_lech(ban_ghi)
    return render(request, 'attendance/chi_tiet_giai_trinh.html', {
        'ban_ghi': ban_ghi, 'la_chu': la_chu, 'tab': 'cua_toi' if la_chu else 'duyet',
        'duoc_duyet': ban_ghi.explanation_status == ExplanationStatus.PENDING and not la_chu})


@role_required(QL, SA)
@require_POST
def xu_ly_giai_trinh(request, pk):
    """UC 4.4 – bước 5 ("Chấp thuận") và luồng 5.1 ("Từ chối" kèm lý do)."""
    ban_ghi = get_object_or_404(Attendance.objects.select_related('employee__user'), pk=pk)
    try:
        if request.POST.get('hanh_dong') == 'tu_choi':
            services.tu_choi_giai_trinh(request.user, ban_ghi, request.POST.get('ly_do', ''))
            messages.success(request, thong_bao.DA_TU_CHOI_GIAI_TRINH)
        else:
            services.chap_thuan_giai_trinh(request.user, ban_ghi)
            messages.success(request, thong_bao.DA_CHAP_THUAN_GIAI_TRINH)
    except KhongCoQuyen as loi:
        return tra_403(request, str(loi))
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))               # 5.2 (thiếu lý do), 5.3 (đã chốt lương), đã xử lý
        if str(loi) == thong_bao.YEU_CAU_DA_XU_LY:
            return redirect('attendance:review')
        return redirect('attendance:review_detail', pk=pk)
    return redirect('attendance:review')


# ============================================================ UC 4.5 – Bảng tổng hợp công
@role_required(QL, KT, SA)
def tong_hop(request):
    """UC 4.5 – bước 1–5: bảng tổng hợp công toàn trung tâm theo tháng (chỉ xem)."""
    hom_nay = date.today()
    bo_loc = BoLocTongHopForm(request.GET or None)
    loc = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    thang, nam = _doc_thang(loc.get('thang'), (hom_nay.month, hom_nay.year))
    dong = services.tong_hop_cong(thang, nam, loc.get('phong_ban', ''), loc.get('vi_tri', ''))
    return render(request, 'attendance/tong_hop.html', {
        'bo_loc': bo_loc, 'dong': dong, 'thang': thang, 'nam': nam, 'thang_nhap': f'{nam}-{thang:02d}', 'tab': 'tong_hop',
        'trong': not any(d['co_ban_ghi'] for d in dong), 'khong_co_du_lieu': thong_bao.KHONG_CO_DU_LIEU_CHAM_CONG,
        'tong_cho_duyet': sum(d['cho_duyet'] for d in dong)})


@role_required(QL, KT, SA)
def chi_tiet_cong(request, nv):
    """UC 4.5 – bước 6–7: chi tiết từng ngày công của một nhân sự trong tháng."""
    nhan_su = get_object_or_404(Employee, pk=nv)
    hom_nay = date.today()
    thang, nam = _doc_thang(request.GET.get('thang'), (hom_nay.month, hom_nay.year))
    lich_su = list(services.lich_su_cham_cong(nhan_su, thang, nam))
    for b in lich_su:
        b.chenh_lech = services.mo_ta_chenh_lech(b)
    cong, don_vi = services.tong_cong_thang(nhan_su, thang, nam)
    return render(request, 'attendance/chi_tiet_cong.html', {
        'nhan_su': nhan_su, 'lich_su': lich_su, 'cong': cong, 'don_vi': don_vi, 'thang': thang, 'nam': nam,
        'thang_nhap': f'{nam}-{thang:02d}', 'khong_co_du_lieu': thong_bao.KHONG_CO_DU_LIEU_CHAM_CONG, 'tab': 'tong_hop'})
