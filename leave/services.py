"""Hàm nghiệp vụ của app leave (UC 5): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào leave_requests và leave_balances. Muốn tạo yêu cầu dạy thay thì gọi
schedule.services (import trong hàm), muốn gửi thông báo / ghi nhật ký thì gọi core.services.
Các nhóm hàm: 1. tính toán chung · 2. UC 5.1 gửi/hủy đơn · 3. UC 5.2 duyệt · 4. UC 5.3 quỹ phép · 5. UC 5.4 tổng hợp.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from core import thong_bao
from core.models import NotificationType
from core.permissions import co_quyen_duyet
from core.services import KhongCoQuyen, LoiNghiepVu, LoiTruongNhap, ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType
from .models import DurationType, LeaveBalance, LeaveRequest, LeaveStatus, LeaveType


# ============================================================ 1. Tính toán chung (§9.1, §9.2)
def tinh_so_ngay_nghi(tu_ngay, den_ngay, hinh_thuc=DurationType.FULL_DAY):
    """§9.2 – `total_days`: đếm các ngày thuộc NGAY_LAM_VIEC (Thứ 2 – Thứ 7) từ tu_ngay đến den_ngay.

    Hình thức nửa ngày = 0,5 (bắt buộc tu_ngay = den_ngay và hôm đó phải là ngày làm việc, nếu không trả 0).
    """
    so_ngay, ngay = 0, tu_ngay
    while ngay <= den_ngay:
        if ngay.weekday() in settings.NGAY_LAM_VIEC:
            so_ngay += 1
        ngay += timedelta(days=1)
    if hinh_thuc != DurationType.FULL_DAY:
        return Decimal('0.5') if (so_ngay == 1 and tu_ngay == den_ngay) else Decimal('0')
    return Decimal(so_ngay)


def dinh_dang_so_ngay(so):
    """Decimal('8.5') → '8,5'; Decimal('12.0') → '12' (kiểu viết số của tiếng Việt, như "0,5" trong §9.2)."""
    so = Decimal(so)
    return str(int(so)) if so == so.to_integral() else str(so.normalize()).replace('.', ',')


def lay_quy_phep(nhan_su, nam):
    """Quỹ phép năm `nam` của nhân sự Full-time (tạo nếu chưa có); Part-time trả về None."""
    return tao_quy_phep(nhan_su, nam)


def _nguoi_duyet_cua(nguoi_gui):
    """Người nhận thông báo duyệt (Q2): đơn của Quản lý → Super Admin; đơn của Kế toán/Nhân viên → Quản lý."""
    vai_tro = UserRole.SUPER_ADMIN if nguoi_gui.role == UserRole.MANAGER else UserRole.MANAGER
    return User.objects.filter(role=vai_tro, is_active=True)


def _khoang_ngay(don):
    return {'tu_ngay': f'{don.start_date:%d/%m/%Y}', 'den_ngay': f'{don.end_date:%d/%m/%Y}'}


def _cac_thang_trong(tu_ngay, den_ngay):
    """Các cặp (tháng, năm) mà khoảng ngày đi qua – để kiểm tra "tháng đã chốt lương"."""
    ket_qua, ngay = [], date(tu_ngay.year, tu_ngay.month, 1)
    while ngay <= den_ngay:
        ket_qua.append((ngay.month, ngay.year))
        ngay = date(ngay.year + (ngay.month == 12), ngay.month % 12 + 1, 1)
    return ket_qua


def _trung_don(don_khac, tu_ngay, den_ngay, hinh_thuc):
    """Hai đơn trùng nhau khi khoảng ngày giao nhau, TRỪ trường hợp hai đơn nửa ngày cùng ngày nhưng khác nửa
    (nghỉ sáng + nghỉ chiều là hợp lệ)."""
    if don_khac.start_date > den_ngay or don_khac.end_date < tu_ngay:
        return False
    nua = (DurationType.HALF_DAY_AM, DurationType.HALF_DAY_PM)
    if hinh_thuc in nua and don_khac.duration_type in nua and hinh_thuc != don_khac.duration_type:
        return False
    return True


# ============================================================ 2. UC 5.1 – GỬI / HỦY ĐƠN
def gui_don_nghi(nhan_su, loai_nghi, hinh_thuc, tu_ngay, den_ngay, ly_do):
    """UC 5.1 – bước 4–6: kiểm tra, tính số ngày, lưu đơn PENDING và báo người duyệt. Trả về đơn.

    Thứ tự kiểm tra (đúng §10): ngày bắt đầu ≤ kết thúc (3.2) · nửa ngày cùng ngày · Part-time không phép năm (3.4) ·
    không trùng đơn PENDING/APPROVED (3.3) · tháng chưa chốt lương · có ngày làm việc (3.5) · đủ quỹ phép (3.1).
    """
    if nhan_su.status != EmployeeStatus.ACTIVE:
        raise LoiNghiepVu(thong_bao.CHI_NHAN_SU_HOAT_DONG_NGHI)
    if tu_ngay > den_ngay:
        raise LoiTruongNhap(thong_bao.NGAY_BAT_DAU_SAU_KET_THUC, 'end_date')
    if hinh_thuc != DurationType.FULL_DAY and tu_ngay != den_ngay:
        raise LoiTruongNhap(thong_bao.NUA_NGAY_CUNG_NGAY, 'end_date')
    if loai_nghi == LeaveType.ANNUAL and nhan_su.employment_type != EmploymentType.FULL_TIME:
        raise LoiTruongNhap(thong_bao.PART_TIME_KHONG_PHEP_NAM, 'leave_type')
    for don_khac in LeaveRequest.objects.filter(employee=nhan_su, status__in=[LeaveStatus.PENDING, LeaveStatus.APPROVED]):
        if _trung_don(don_khac, tu_ngay, den_ngay, hinh_thuc):
            raise LoiTruongNhap(thong_bao.TRUNG_DON_NGHI)
    from payroll.services import thang_da_chot   # import trong hàm (§3.2)
    for thang, nam in _cac_thang_trong(tu_ngay, den_ngay):
        if thang_da_chot(thang, nam):
            raise LoiTruongNhap(thong_bao.THANG_DA_CHOT_LUONG.format(thang=thang, nam=nam))

    so_ngay = tinh_so_ngay_nghi(tu_ngay, den_ngay, hinh_thuc)
    if so_ngay == 0:
        raise LoiTruongNhap(thong_bao.KHONG_CO_NGAY_LAM_VIEC)
    if loai_nghi == LeaveType.ANNUAL:
        con_lai = lay_quy_phep(nhan_su, tu_ngay.year).remaining_days
        if so_ngay > con_lai:
            raise LoiTruongNhap(thong_bao.QUY_PHEP_KHONG_DU.format(con_lai=dinh_dang_so_ngay(con_lai)))

    with transaction.atomic():
        don = LeaveRequest.objects.create(
            employee=nhan_su, leave_type=loai_nghi, duration_type=hinh_thuc, start_date=tu_ngay, end_date=den_ngay,
            total_days=so_ngay, reason=ly_do.strip(), status=LeaveStatus.PENDING)
        noi_dung = thong_bao.TB_DON_MOI_NOI_DUNG.format(
            nhan_su=nhan_su.full_name, so_ngay=dinh_dang_so_ngay(so_ngay), loai=LeaveType(loai_nghi).label.lower(),
            ly_do=don.reason, **_khoang_ngay(don))
        for nguoi in _nguoi_duyet_cua(nhan_su.user):
            tao_thong_bao(nguoi, NotificationType.LEAVE, thong_bao.TB_DON_MOI_TIEU_DE, noi_dung,
                          reverse('leave:detail', args=[don.pk]))
        ghi_nhat_ky(nhan_su.user, 'CREATE', 'leave_requests', don.pk, f'Gửi đơn nghỉ {don.start_date:%d/%m/%Y}–{don.end_date:%d/%m/%Y}')
    return don


def huy_don_nghi(nhan_su, don):
    """UC 5.1 – luồng thay thế 1.1.1: nhân sự hủy đơn PENDING của chính mình → CANCELLED, báo người duyệt."""
    if don.employee_id != nhan_su.pk:
        raise KhongCoQuyen(thong_bao.KHONG_XEM_DON_NGHI)
    if don.status != LeaveStatus.PENDING:
        raise LoiNghiepVu(thong_bao.KHONG_HUY_DON_DUOC)
    with transaction.atomic():
        don.status = LeaveStatus.CANCELLED
        don.save(update_fields=['status'])
        noi_dung = thong_bao.TB_HUY_DON_NOI_DUNG.format(nhan_su=nhan_su.full_name, **_khoang_ngay(don))
        for nguoi in _nguoi_duyet_cua(nhan_su.user):
            tao_thong_bao(nguoi, NotificationType.LEAVE, thong_bao.TB_HUY_DON_TIEU_DE, noi_dung,
                          reverse('leave:detail', args=[don.pk]))
        ghi_nhat_ky(nhan_su.user, 'UPDATE', 'leave_requests', don.pk, 'Hủy đơn nghỉ')
    return don


def don_cua_nhan_su(nhan_su, nam, trang_thai=''):
    """UC 5.3 – bước 2: các đơn nghỉ của chính nhân sự có ngày bắt đầu trong năm `nam` (lọc ngay trong truy vấn, §5)."""
    ds = LeaveRequest.objects.filter(employee=nhan_su, start_date__year=nam).order_by('-start_date', '-pk')
    return ds.filter(status=trang_thai) if trang_thai else ds


def tom_tat_anh_huong(don):
    """Số buổi dạy chính / trợ giảng / ca làm việc bị ảnh hưởng của một đơn (hiện ở cột "Ảnh hưởng lịch dạy")."""
    from schedule.services import lich_bi_anh_huong   # import trong hàm (§3.2)
    return lich_bi_anh_huong(don.employee, don.start_date, don.end_date, don.duration_type)


# ============================================================ 3. UC 5.2 – DUYỆT ĐƠN
def pham_vi_duyet(nguoi_duyet):
    """Các đơn nằm trong phạm vi duyệt (Q2): Quản lý → đơn của Kế toán, Nhân viên; Super Admin → đơn của Quản lý.
    Không bao giờ gồm đơn của chính người duyệt."""
    if nguoi_duyet.role == UserRole.MANAGER:
        vai_tro = [UserRole.ACCOUNTANT, UserRole.EMPLOYEE]
    elif nguoi_duyet.role == UserRole.SUPER_ADMIN:
        vai_tro = [UserRole.MANAGER]
    else:
        return LeaveRequest.objects.none()
    return LeaveRequest.objects.filter(employee__user__role__in=vai_tro).exclude(employee__user=nguoi_duyet)


def danh_sach_don_duyet(nguoi_duyet, tu_khoa='', phong_ban='', loai='', trang_thai=LeaveStatus.PENDING, tu_ngay=None, den_ngay=None):
    """UC 5.2 – bước 1–2: danh sách đơn trong phạm vi duyệt (mặc định chỉ PENDING), có lọc như Figma."""
    ds = pham_vi_duyet(nguoi_duyet).select_related('employee__user').order_by('start_date', 'pk')
    if tu_khoa:
        ds = ds.filter(employee__full_name__icontains=tu_khoa)
    if phong_ban:
        ds = ds.filter(employee__department=phong_ban)
    if loai:
        ds = ds.filter(leave_type=loai)
    if trang_thai:
        ds = ds.filter(status=trang_thai)
    if tu_ngay:
        ds = ds.filter(end_date__gte=tu_ngay)
    if den_ngay:
        ds = ds.filter(start_date__lte=den_ngay)
    return ds


def thong_ke_duyet(nguoi_duyet, thang, nam):
    """Bốn ô số đầu trang duyệt (Figma): chờ duyệt, đã duyệt / từ chối trong tháng, yêu cầu dạy thay đang tìm."""
    from schedule.models import SubstituteRequest, SubstituteStatus
    pham_vi = pham_vi_duyet(nguoi_duyet)
    trong_thang = pham_vi.filter(reviewed_at__year=nam, reviewed_at__month=thang)
    return {
        'cho_duyet': pham_vi.filter(status=LeaveStatus.PENDING).count(),
        'da_duyet': trong_thang.filter(status=LeaveStatus.APPROVED).count(),
        'tu_choi': trong_thang.filter(status=LeaveStatus.REJECTED).count(),
        'can_day_thay': SubstituteRequest.objects.filter(status=SubstituteStatus.SEARCHING,
                                                         leave_request__in=pham_vi).count()}


def lich_su_nghi_trong_nam(don):
    """UC 5.2 – bước 4: các đơn đã duyệt của cùng nhân sự trong năm (không gồm đơn đang xem)."""
    return LeaveRequest.objects.filter(employee=don.employee, status=LeaveStatus.APPROVED,
                                       start_date__year=don.start_date.year).exclude(pk=don.pk).order_by('start_date')


def _kiem_tra_duoc_duyet(nguoi_duyet, don):
    """Điều kiện chung của duyệt và từ chối: đơn còn PENDING (luồng 3.1) và đúng phạm vi duyệt (Q2)."""
    if don.status != LeaveStatus.PENDING:
        raise LoiNghiepVu(thong_bao.YEU_CAU_DA_XU_LY)
    if not co_quyen_duyet(nguoi_duyet, don.employee.user):
        raise KhongCoQuyen(thong_bao.KHONG_CO_QUYEN_DUYET_DON)


def duyet_don_nghi(nguoi_duyet, don, bay_gio=None):
    """UC 5.2 – bước 6–8, trong MỘT giao dịch: APPROVED + người duyệt; đơn ANNUAL thì kiểm tra lại quỹ phép rồi cộng
    used_days; tìm lịch bị ảnh hưởng: buổi dạy chính → needs_substitute + yêu cầu dạy thay (SEARCHING), buổi trợ giảng
    và ca đã chốt → báo Quản lý điều chỉnh; báo kết quả cho nhân sự, ghi nhật ký. Trả về dict số buổi bị ảnh hưởng."""
    from schedule.services import lich_bi_anh_huong, tao_yeu_cau_day_thay   # import trong hàm (§3.2)
    bay_gio = bay_gio or timezone.now().replace(tzinfo=None)
    _kiem_tra_duoc_duyet(nguoi_duyet, don)
    nhan_su = don.employee
    with transaction.atomic():
        if don.leave_type == LeaveType.ANNUAL:
            quy = lay_quy_phep(nhan_su, don.start_date.year)
            if quy is None or don.total_days > quy.remaining_days:                    # luồng 5.3
                raise LoiNghiepVu(thong_bao.QUY_PHEP_NHAN_SU_KHONG_DU)
            quy.used_days += don.total_days
            quy.save(update_fields=['used_days'])
        don.status, don.reviewed_by, don.reviewed_at = LeaveStatus.APPROVED, nguoi_duyet, bay_gio
        anh_huong = lich_bi_anh_huong(nhan_su, don.start_date, don.end_date, don.duration_type)
        don.needs_substitute = bool(anh_huong['buoi_chinh'])
        don.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'needs_substitute'])
        for buoi in anh_huong['buoi_chinh']:
            tao_yeu_cau_day_thay(buoi, don)
        tao_thong_bao(nhan_su.user, NotificationType.LEAVE, thong_bao.TB_KET_QUA_DON_TIEU_DE,
                      thong_bao.TB_DON_DUOC_DUYET.format(**_khoang_ngay(don)), reverse('leave:detail', args=[don.pk]))
        quan_ly = User.objects.filter(role=UserRole.MANAGER, is_active=True).exclude(pk=nhan_su.user_id)
        if anh_huong['buoi_chinh']:
            for ql in quan_ly:
                tao_thong_bao(ql, NotificationType.SCHEDULE, thong_bao.TB_CAN_DAY_THAY_TIEU_DE,
                              thong_bao.TB_CAN_DAY_THAY_NOI_DUNG.format(nhan_su=nhan_su.full_name, so_buoi=len(anh_huong['buoi_chinh'])),
                              reverse('schedule:substitute_list'))
        if anh_huong['buoi_tro_giang'] or anh_huong['ca_lam_viec']:
            for ql in quan_ly:
                tao_thong_bao(ql, NotificationType.SCHEDULE, thong_bao.TB_DIEU_CHINH_LICH_TIEU_DE,
                              thong_bao.TB_DIEU_CHINH_LICH_NOI_DUNG.format(
                                  nhan_su=nhan_su.full_name, so_tro_giang=len(anh_huong['buoi_tro_giang']),
                                  so_ca=len(anh_huong['ca_lam_viec']), **_khoang_ngay(don)), reverse('schedule:calendar'))
        ghi_nhat_ky(nguoi_duyet, 'APPROVE', 'leave_requests', don.pk, f'Duyệt đơn nghỉ của {nhan_su.full_name}')
    return {'buoi_chinh': len(anh_huong['buoi_chinh']), 'buoi_tro_giang': len(anh_huong['buoi_tro_giang']),
            'ca_lam_viec': len(anh_huong['ca_lam_viec'])}


def tu_choi_don_nghi(nguoi_duyet, don, ly_do, bay_gio=None):
    """UC 5.2 – luồng thay thế 5.1.1: REJECTED + lưu review_note, giữ nguyên quỹ phép, báo nhân sự kèm lý do.
    Không nhập lý do → "Vui lòng nhập lý do từ chối." (luồng 5.2)."""
    bay_gio = bay_gio or timezone.now().replace(tzinfo=None)
    _kiem_tra_duoc_duyet(nguoi_duyet, don)
    if not ly_do.strip():
        raise LoiTruongNhap(thong_bao.VUI_LONG_NHAP_LY_DO_TU_CHOI, 'ly_do')
    with transaction.atomic():
        don.status, don.reviewed_by, don.reviewed_at, don.review_note = LeaveStatus.REJECTED, nguoi_duyet, bay_gio, ly_do.strip()
        don.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note'])
        tao_thong_bao(don.employee.user, NotificationType.LEAVE, thong_bao.TB_KET_QUA_DON_TIEU_DE,
                      thong_bao.TB_DON_BI_TU_CHOI.format(ly_do=don.review_note, **_khoang_ngay(don)),
                      reverse('leave:detail', args=[don.pk]))
        ghi_nhat_ky(nguoi_duyet, 'REJECT', 'leave_requests', don.pk, f'Từ chối đơn nghỉ của {don.employee.full_name}')
    return don


def co_quyen_xem_don(nguoi_xem, don):
    """Chủ đơn, hoặc người duyệt có phạm vi trùng với chủ đơn (cùng quy tắc `co_quyen_duyet`, không xét đơn của chính mình)."""
    if don.employee.user_id == nguoi_xem.pk:
        return True
    return co_quyen_duyet(nguoi_xem, don.employee.user)


# ============================================================ 4. UC 5.3 – QUỸ PHÉP CÁ NHÂN
def thong_tin_quy_phep(nhan_su, nam):
    """UC 5.3 – bước 2–3: ba thẻ Tổng phép năm / Đã sử dụng / Còn lại (= Tổng − Đã dùng). Part-time → None (luồng 1.1)."""
    if nhan_su.employment_type != EmploymentType.FULL_TIME:
        return None
    return lay_quy_phep(nhan_su, nam)


# ============================================================ 5. UC 5.4 – TỔNG HỢP NGHỈ PHÉP
def so_ngay_trong_thang(don, thang, nam):
    """Phần số ngày của đơn rơi vào tháng đang xem (đơn vắt qua hai tháng chỉ đếm phần trong tháng)."""
    dau, cuoi = date(nam, thang, 1), date(nam + (thang == 12), thang % 12 + 1, 1) - timedelta(days=1)
    return tinh_so_ngay_nghi(max(don.start_date, dau), min(don.end_date, cuoi), don.duration_type)


def tong_hop_nghi_phep(thang, nam, phong_ban='', vi_tri='', loai=''):
    """UC 5.4 – bước 4: đơn ĐÃ DUYỆT giao với tháng/năm, lọc phòng ban, vị trí, loại nghỉ; kèm tổng số ngày theo loại
    và số ngày phép năm còn lại của từng nhân sự Full-time (theo bộ lọc). Trả về dict (rỗng nếu không có đơn nào)."""
    dau, cuoi = date(nam, thang, 1), date(nam + (thang == 12), thang % 12 + 1, 1) - timedelta(days=1)
    don = LeaveRequest.objects.filter(status=LeaveStatus.APPROVED, start_date__lte=cuoi, end_date__gte=dau
                                      ).select_related('employee').order_by('start_date', 'employee__full_name')
    if phong_ban:
        don = don.filter(employee__department=phong_ban)
    if vi_tri:
        don = don.filter(employee__position=vi_tri)
    if loai:
        don = don.filter(leave_type=loai)
    dong = [{'don': d, 'so_ngay': so_ngay_trong_thang(d, thang, nam)} for d in don]
    tong_theo_loai = {ma: Decimal('0') for ma, _ in LeaveType.choices}
    for d in dong:
        tong_theo_loai[d['don'].leave_type] += d['so_ngay']
    nhan_su_ft = Employee.objects.filter(employment_type=EmploymentType.FULL_TIME, status=EmployeeStatus.ACTIVE)
    if phong_ban:
        nhan_su_ft = nhan_su_ft.filter(department=phong_ban)
    if vi_tri:
        nhan_su_ft = nhan_su_ft.filter(position=vi_tri)
    quy = {q.employee_id: q for q in LeaveBalance.objects.filter(year=nam, employee__in=nhan_su_ft)}
    phep_con_lai = [{'nhan_su': nv, 'quy': quy.get(nv.pk)} for nv in nhan_su_ft.order_by('full_name')]
    return {'dong': dong, 'tong_theo_loai': [(LeaveType(ma).label, so) for ma, so in tong_theo_loai.items()],
            'phep_con_lai': phep_con_lai}


def tao_quy_phep(nhan_su, nam=None):
    """UC 2.5 – bước 5: tạo quỹ phép năm (mặc định 12 ngày) cho nhân sự Full-time (Q11: chỉ Full-time có phép năm).

    Hàm của app `leave` (app sở hữu bảng leave_balances) để `employees` gọi sang. Chạy lại không tạo trùng.
    """
    if nhan_su.employment_type != EmploymentType.FULL_TIME:
        return None
    nam = nam or date.today().year
    quy_phep, _ = LeaveBalance.objects.get_or_create(
        employee=nhan_su, year=nam, defaults={'total_days': settings.PHEP_NAM_MAC_DINH})
    return quy_phep


def tao_quy_phep_hang_loat(nam):
    """UC 9.2 – bước 6: tạo quỹ phép (12 ngày) cho mọi nhân sự Full-time ACTIVE chưa có quỹ phép của năm `nam`.

    Dùng lại `tao_quy_phep` nên Part-time bị bỏ qua (Q11). Trả về số quỹ phép MỚI tạo; chạy lại trả về 0."""
    so_moi = 0
    da_co = set(LeaveBalance.objects.filter(year=nam).values_list('employee_id', flat=True))
    for nhan_su in Employee.objects.filter(status=EmployeeStatus.ACTIVE, employment_type=EmploymentType.FULL_TIME):
        if nhan_su.pk not in da_co and tao_quy_phep(nhan_su, nam) is not None:
            so_moi += 1
    return so_moi
