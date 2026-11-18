"""View dạng hàm của app payroll (UC 7): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2).

Phân quyền (§5): cấu hình lương, lập/chốt/phát hành bảng lương: chỉ Kế toán;
phiếu lương cá nhân: Quản lý, Kế toán, Nhân viên (chỉ của mình và chỉ khi đã phát hành).
"""
from datetime import date, datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required, tra_403
from core.services import LoiNghiepVu, LoiTruongNhap
from employees.models import Employee, EmploymentType, Position
from . import services
from .forms import BoLocThangForm, CauHinhLuongForm, KhoanThuCongForm
from .models import Payroll, PayrollDetail, PayrollStatus

QL, KT, NV = UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE


def _nhan_su(user):
    return getattr(user, 'employee', None)


def _doc_thang(chuoi, mac_dinh):
    """'2026-10' (ô chọn tháng) → (tháng, năm); sai định dạng thì dùng mặc định."""
    try:
        d = datetime.strptime(chuoi, '%Y-%m')
        return d.month, d.year
    except (TypeError, ValueError):
        return mac_dinh


def _thang_truoc(hom_nay):
    return (12, hom_nay.year - 1) if hom_nay.month == 1 else (hom_nay.month - 1, hom_nay.year)


# ============================================================ UC 7.3 – Lương của tôi (lịch sử các tháng + phiếu lương)
def _ve_phieu(request, bang):
    """Dựng trang "Lương của tôi": bảng các tháng đã phát hành (tăng/giảm so với tháng trước) và phiếu của tháng đang
    chọn ngay bên dưới (mặc định tháng mới nhất; None nếu chưa có phiếu nào). Chỉ phiếu của chính mình."""
    nhan_su = _nhan_su(request.user)
    ls = services.lich_su_luong(nhan_su)
    cac_thang = [d['bang'] for d in ls['dong']]
    if bang is None and cac_thang:
        bang = cac_thang[0]
    return render(request, 'payroll/phieu_cua_toi.html', {
        'ls': ls, 'cac_thang': cac_thang, 'bang': bang, 'ct': services.chi_tiet_phieu(bang) if bang else None,
        'tab': 'cua_toi', 'chua_co': thong_bao.CHUA_CO_PHIEU_LUONG, 'nhan_su': nhan_su})


@role_required(QL, KT, NV)
def phieu_luong_cua_toi(request):
    """UC 7.3 – bước 1–2: các tháng có phiếu lương SENT của chính mình, kèm phiếu mới nhất."""
    if _nhan_su(request.user) is None:
        return tra_403(request, thong_bao.KHONG_CO_HO_SO)
    return _ve_phieu(request, None)


@role_required(QL, KT, NV)
def xem_phieu(request, pk):
    """UC 7.3 – bước 3–6: chọn một tháng trong bảng. Phiếu của người khác hoặc chưa phát hành → 403 (luồng 3.1)."""
    bang = get_object_or_404(Payroll.objects.select_related('employee__user'), pk=pk)
    if not services.co_quyen_xem_phieu(request.user, bang):
        return tra_403(request, thong_bao.KHONG_XEM_PHIEU_LUONG)
    return _ve_phieu(request, bang)


# ============================================================ UC 7.1 – Cấu hình lương
@role_required(KT)
def cau_hinh_ds(request):
    """UC 7.1 – bước 1: danh sách nhân sự kèm cấu hình đang áp dụng."""
    q, loai = request.GET.get('q', ''), request.GET.get('loai_hinh', '')
    return render(request, 'payroll/cau_hinh_ds.html', {
        'dong': services.nhan_su_can_cau_hinh(q, loai), 'q': q, 'loai_hinh': loai, 'tab': 'cau_hinh',
        'cac_loai': EmploymentType.choices})


@role_required(KT)
def cau_hinh_chi_tiet(request, nv):
    """UC 7.1 – bước 2–7 và luồng 1.1: thông tin nhân sự, cấu hình hiện tại, lịch sử, form "Thêm cấu hình mới"."""
    nhan_su = get_object_or_404(Employee, pk=nv)
    la_ft = nhan_su.employment_type == EmploymentType.FULL_TIME
    form = CauHinhLuongForm(request.POST or None, initial={'effective_from': date.today()})
    if request.method == 'POST' and form.is_valid():
        try:
            services.luu_cau_hinh_luong(request.user, nhan_su, form.tien('base_salary'), form.tien('hourly_rate'),
                                        form.tien('class_allowance_rate'), form.tien('responsibility_allowance'),
                                        form.cleaned_data['effective_from'])
        except LoiTruongNhap as loi:
            form.add_error(loi.truong if loi.truong in form.fields else None, str(loi))      # luồng 5.1, 5.2, 5.3
        except LoiNghiepVu as loi:
            form.add_error(None, str(loi))
        else:
            messages.success(request, thong_bao.LUU_CAU_HINH_THANH_CONG)
            return redirect('payroll:config_detail', nv=nv)
    cac_cau_hinh = list(services.lich_su_cau_hinh(nhan_su))
    return render(request, 'payroll/cau_hinh_chi_tiet.html', {
        'nhan_su': nhan_su, 'form': form, 'la_full_time': la_ft, 'la_giao_vien': nhan_su.position == Position.TEACHER,
        'dang_ap_dung': next((c for c in cac_cau_hinh if c.effective_to is None), None), 'lich_su': cac_cau_hinh, 'tab': 'cau_hinh'})


# ============================================================ UC 7.2 – Lập, chốt, phát hành bảng lương
@role_required(KT)
def bang_luong_ds(request):
    """UC 7.2 – bước 1–2: form chọn Tháng/Năm (mặc định tháng trước) + các tháng đã lập."""
    hom_nay = date.today()
    thang, nam = _thang_truoc(hom_nay)
    return render(request, 'payroll/bang_luong_ds.html', {
        'thang_nhap': f'{nam}-{thang:02d}', 'cac_thang': services.danh_sach_thang(), 'tab': 'bang_luong'})


@role_required(KT)
@require_POST
def khoi_tao(request):
    """UC 7.2 – bước 3–7: nhấn "Khởi tạo bảng lương"."""
    thang, nam = _doc_thang(request.POST.get('thang'), _thang_truoc(date.today()))
    try:
        cac_bang = services.khoi_tao_bang_luong(request.user, thang, nam)
    except services.BangLuongDaTonTai as loi:
        messages.error(request, str(loi))                                  # luồng 3.1: báo rồi mở bảng lương hiện có
        return redirect('payroll:period', nam=nam, thang=thang)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))                                  # luồng 3.2, 3.3, 3.4
        return redirect('payroll:period_list')
    messages.success(request, thong_bao.KHOI_TAO_THANH_CONG.format(so=len(cac_bang)))
    return redirect('payroll:period', nam=nam, thang=thang)


@role_required(KT)
def bang_luong_thang(request, nam, thang):
    """UC 7.2 – bước 7: bảng lương tổng của tháng (theo Figma "Monthly Payroll")."""
    if not 1 <= thang <= 12:
        return redirect('payroll:period_list')
    bo_loc = BoLocThangForm(request.GET or None)
    loc = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    tong = services.tong_ket_thang(thang, nam, loc.get('phong_ban', ''), loc.get('q', ''))
    return render(request, 'payroll/bang_luong_thang.html', {
        'thang': thang, 'nam': nam, 'tong': tong, 'bo_loc': bo_loc, 'trang_thai': services.trang_thai_thang(thang, nam),
        'tab': 'bang_luong', 'DRAFT': PayrollStatus.DRAFT, 'SENT': PayrollStatus.SENT})


def _hanh_dong_thang(request, nam, thang, ham, thanh_cong):
    """Khung chung cho hai nút của tháng (Tính lại, Chốt & phát hành): gọi service, báo kết quả hoặc lỗi, quay về bảng lương tháng."""
    try:
        so = ham(request.user, thang, nam)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thanh_cong.format(so=so))
    return redirect('payroll:period', nam=nam, thang=thang)


@role_required(KT)
@require_POST
def tinh_lai(request, nam, thang):
    """UC 7.2 – luồng thay thế 8.1: nút "Tính lại"."""
    return _hanh_dong_thang(request, nam, thang, services.tinh_lai_bang_luong, thong_bao.TINH_LAI_THANH_CONG)


@role_required(KT)
@require_POST
def chot(request, nam, thang):
    """UC 7.2 – bước 10–13: nút "Chốt & phát hành" (khóa số liệu và gửi phiếu lương cho nhân sự trong một bước)."""
    return _hanh_dong_thang(request, nam, thang, services.chot_va_phat_hanh, thong_bao.CHOT_BANG_LUONG_THANH_CONG)


@role_required(KT)
def chi_tiet_bang_luong(request, pk):
    """UC 7.2 – bước 8: xem chi tiết (xem trước phiếu lương) của một nhân sự và thêm/xóa khoản thủ công khi còn DRAFT."""
    bang = get_object_or_404(Payroll.objects.select_related('employee'), pk=pk)
    ct = services.chi_tiet_phieu(bang)
    for dong in ct['thu_nhap'] + ct['khau_tru'] + ct['thue']:
        dong.tu_dong = services.la_dong_tu_dong(dong)               # dòng hệ thống tự tính (không có nút Xóa)
    return render(request, 'payroll/chi_tiet_bang_luong.html', {
        'bang': bang, 'ct': ct, 'form': KhoanThuCongForm(), 'sua_duoc': bang.status == PayrollStatus.DRAFT,
        'tab': 'bang_luong'})


@role_required(KT)
@require_POST
def them_khoan(request, pk):
    """UC 7.2 – bước 8–9: lưu khoản thủ công (thưởng, điều chỉnh tăng/giảm, thuế TNCN, khác)."""
    bang = get_object_or_404(Payroll.objects.select_related('employee'), pk=pk)
    form = KhoanThuCongForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.them_khoan_thu_cong(request.user, bang, d['category'], d['detail_type'], d['description'], d['amount'])
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        else:
            messages.success(request, thong_bao.THEM_KHOAN_THANH_CONG)
    else:
        messages.error(request, ' '.join(m for ds in form.errors.values() for m in ds))
    return redirect('payroll:payroll_detail', pk=pk)


@role_required(KT)
@require_POST
def xoa_khoan(request, pk):
    """UC 7.2 – luồng thay thế 8.2: xóa một khoản thủ công."""
    chi_tiet = get_object_or_404(PayrollDetail.objects.select_related('payroll__employee'), pk=pk)
    ma_bang = chi_tiet.payroll_id
    try:
        services.xoa_khoan_thu_cong(request.user, chi_tiet)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    else:
        messages.success(request, thong_bao.XOA_KHOAN_THANH_CONG)
    return redirect('payroll:payroll_detail', pk=ma_bang)
