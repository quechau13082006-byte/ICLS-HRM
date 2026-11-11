"""View dạng hàm của app leave (UC 5): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2).

Phân quyền (§5): gửi đơn, quỹ phép, hủy đơn: mọi vai trò CÓ hồ sơ nhân sự (Super Admin không có hồ sơ);
duyệt đơn: Quản lý (đơn của Kế toán, Nhân viên) và Super Admin (đơn của Quản lý), không tự duyệt;
tổng hợp nghỉ phép: Quản lý, Super Admin (chỉ xem).
"""
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
from employees.models import EmploymentType
from . import services
from .forms import BoLocDuyetForm, BoLocTongHopForm, DonNghiForm
from .models import LeaveRequest, LeaveStatus

QL, SA = UserRole.MANAGER, UserRole.SUPER_ADMIN


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


def _trang(request, danh_sach):
    return Paginator(danh_sach, settings.SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))


def _tham_so_trang(request):
    tham_so = request.GET.copy()
    tham_so.pop('page', None)
    return tham_so


# ============================================================ UC 5.3 – Quỹ phép & đơn nghỉ của tôi
@role_required()
def cua_toi(request):
    """UC 5.3 (và danh sách đơn của UC 5.1): ba thẻ quỹ phép + đơn nghỉ trong năm, lọc theo trạng thái."""
    nhan_su = _nhan_su(request.user)
    if nhan_su is None:
        return redirect('leave:review')       # Super Admin không có đơn nghỉ cá nhân, đưa tới trang duyệt
    hom_nay = date.today()
    try:
        nam = int(request.GET.get('nam', hom_nay.year))
    except ValueError:
        nam = hom_nay.year
    trang_thai = request.GET.get('trang_thai', '')
    if trang_thai not in LeaveStatus.values:
        trang_thai = ''
    tat_ca = services.don_cua_nhan_su(nhan_su, nam)
    trang = _trang(request, services.don_cua_nhan_su(nhan_su, nam, trang_thai))
    for don in trang:                              # cột "Ảnh hưởng lịch dạy" của Figma
        if don.status in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
            ah = services.tom_tat_anh_huong(don)
            don.so_anh_huong = len(ah['buoi_chinh']) + len(ah['buoi_tro_giang']) + len(ah['ca_lam_viec'])
            don.ten_lop_anh_huong = ', '.join(sorted({b.study_class.class_name for b in ah['buoi_chinh']}))
    quy = services.thong_tin_quy_phep(nhan_su, nam)
    dem = {ma: tat_ca.filter(status=ma).count() for ma in LeaveStatus.values}
    return render(request, 'leave/cua_toi.html', {
        'nhan_su': nhan_su, 'nam': nam, 'quy': quy, 'la_full_time': nhan_su.employment_type == EmploymentType.FULL_TIME,
        'khong_co_quy': thong_bao.PART_TIME_KHONG_CO_QUY_PHEP, 'trang': trang, 'trang_thai': trang_thai, 'dem': dem,
        'tong': tat_ca.count(), 'tham_so_trang': _tham_so_trang(request), 'tab': 'cua_toi'})


# ============================================================ UC 5.1 – Gửi và hủy đơn
@role_required()
def gui_don(request):
    """UC 5.1 – bước 1–6: form tạo đơn; Full-time thấy số ngày phép năm còn lại."""
    nhan_su = _nhan_su(request.user)
    if nhan_su is None:
        return tra_403(request, thong_bao.KHONG_CO_HO_SO)
    form = DonNghiForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            services.gui_don_nghi(nhan_su, d['leave_type'], d['duration_type'], d['start_date'], d['end_date'], d['reason'])
        except LoiTruongNhap as loi:
            form.add_error(loi.truong if loi.truong in form.fields else None, str(loi))    # luồng 3.1 – 3.5
        except LoiNghiepVu as loi:
            form.add_error(None, str(loi))
        else:
            messages.success(request, thong_bao.GUI_DON_THANH_CONG)
            return redirect('leave:my_leaves')
    quy = services.thong_tin_quy_phep(nhan_su, date.today().year)
    return render(request, 'leave/form_don.html', {
        'form': form, 'nhan_su': nhan_su, 'quy': quy, 'tab': 'cua_toi',
        'hinh_thuc': form['duration_type'].value() or 'FULL_DAY'})


@role_required()
def chi_tiet(request, pk):
    """Chi tiết đơn nghỉ: chủ đơn hoặc người duyệt trong phạm vi. Hiện lịch bị ảnh hưởng, quỹ phép, lịch sử nghỉ trong năm
    (UC 5.2 – bước 4); chủ đơn PENDING có nút "Hủy đơn", người duyệt có nút "Duyệt đơn" / "Từ chối"."""
    don = get_object_or_404(LeaveRequest.objects.select_related('employee__user', 'reviewed_by'), pk=pk)
    if not services.co_quyen_xem_don(request.user, don):
        return tra_403(request, thong_bao.KHONG_XEM_DON_NGHI)
    la_chu_don = don.employee.user_id == request.user.pk
    dang_cho = don.status == LeaveStatus.PENDING
    anh_huong = services.tom_tat_anh_huong(don) if don.status in (LeaveStatus.PENDING, LeaveStatus.APPROVED) else None
    quy = services.thong_tin_quy_phep(don.employee, don.start_date.year)
    return render(request, 'leave/chi_tiet.html', {
        'don': don, 'la_chu_don': la_chu_don, 'anh_huong': anh_huong, 'quy': quy,
        'lich_su': services.lich_su_nghi_trong_nam(don), 'dang_cho': dang_cho,
        'duoc_duyet': dang_cho and not la_chu_don, 'tab': 'cua_toi' if la_chu_don else 'duyet'})


@role_required()
@require_POST
def huy_don(request, pk):
    """UC 5.1 – luồng thay thế 1.1: hủy đơn PENDING của chính mình."""
    nhan_su = _nhan_su(request.user)
    don = get_object_or_404(LeaveRequest, pk=pk)
    if nhan_su is None or don.employee_id != nhan_su.pk:                 # đơn của người khác: 403, không phải 404
        return tra_403(request, thong_bao.KHONG_XEM_DON_NGHI)
    try:
        services.huy_don_nghi(nhan_su, don)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.DA_HUY_DON)
    return redirect('leave:my_leaves')


# ============================================================ UC 5.2 – Duyệt đơn
@role_required(QL, SA)
def danh_sach_duyet(request):
    """UC 5.2 – bước 1–2: ô số + danh sách đơn thuộc phạm vi duyệt (mặc định lọc "Chờ duyệt")."""
    hom_nay = date.today()
    du_lieu = request.GET if request.GET else {'trang_thai': LeaveStatus.PENDING}
    bo_loc = BoLocDuyetForm(du_lieu)
    loc = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    thang, nam = _doc_thang(loc.get('thang'), (hom_nay.month, hom_nay.year))
    tu_ngay = den_ngay = None
    if loc.get('thang'):
        tu_ngay = date(nam, thang, 1)
        den_ngay = date(nam + (thang == 12), thang % 12 + 1, 1)
        den_ngay = date.fromordinal(den_ngay.toordinal() - 1)
    ds = services.danh_sach_don_duyet(request.user, loc.get('q', ''), loc.get('phong_ban', ''), loc.get('loai', ''),
                                      loc.get('trang_thai', ''), tu_ngay, den_ngay)
    trang = _trang(request, ds)
    for don in trang:
        if don.status == LeaveStatus.PENDING:
            ah = services.tom_tat_anh_huong(don)
            don.so_anh_huong = len(ah['buoi_chinh']) + len(ah['buoi_tro_giang']) + len(ah['ca_lam_viec'])
    return render(request, 'leave/duyet.html', {
        'bo_loc': bo_loc, 'trang': trang, 'tham_so_trang': _tham_so_trang(request), 'tab': 'duyet',
        'so': services.thong_ke_duyet(request.user, hom_nay.month, hom_nay.year), 'thang_hien_tai': hom_nay})


@role_required(QL, SA)
@require_POST
def xu_ly_don(request, pk):
    """UC 5.2 – bước 5 (nút "Duyệt đơn") và luồng 5.1 (nút "Từ chối" kèm lý do)."""
    don = get_object_or_404(LeaveRequest.objects.select_related('employee__user'), pk=pk)
    try:
        if request.POST.get('hanh_dong') == 'tu_choi':
            services.tu_choi_don_nghi(request.user, don, request.POST.get('ly_do', ''))
            messages.success(request, thong_bao.DA_TU_CHOI_DON)
        else:
            ket_qua = services.duyet_don_nghi(request.user, don)
            messages.success(request, thong_bao.DA_DUYET_DON + (
                f" Đã tạo {ket_qua['buoi_chinh']} yêu cầu dạy thay." if ket_qua['buoi_chinh'] else ''))
    except KhongCoQuyen as loi:
        return tra_403(request, str(loi))
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))             # 5.2 (chưa nhập lý do), 5.3 (quỹ phép), 3.1 (đã xử lý)
        if str(loi) == thong_bao.YEU_CAU_DA_XU_LY:
            return redirect('leave:review')           # luồng 3.1: tải lại danh sách
        return redirect('leave:detail', pk=pk)
    return redirect('leave:review')


# ============================================================ UC 5.4 – Tổng hợp nghỉ phép
@role_required(QL, SA)
def tong_hop(request):
    """UC 5.4: đơn đã duyệt theo tháng, tổng ngày nghỉ theo loại, phép năm còn lại của nhân sự Full-time (chỉ xem)."""
    hom_nay = date.today()
    bo_loc = BoLocTongHopForm(request.GET or None)
    loc = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    thang, nam = _doc_thang(loc.get('thang'), (hom_nay.month, hom_nay.year))
    ket_qua = services.tong_hop_nghi_phep(thang, nam, loc.get('phong_ban', ''), loc.get('vi_tri', ''), loc.get('loai', ''))
    return render(request, 'leave/tong_hop.html', {
        'bo_loc': bo_loc, 'thang': thang, 'nam': nam, 'thang_nhap': f'{nam}-{thang:02d}', 'ket_qua': ket_qua,
        'khong_co_du_lieu': thong_bao.KHONG_CO_DU_LIEU_NGHI, 'tab': 'tong_hop'})
