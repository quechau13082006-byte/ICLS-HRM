"""Hàm nghiệp vụ của app attendance (UC 4): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào bảng attendance; chỉ ĐỌC employees, schedule, leave;
`payroll.thang_da_chot` gọi qua service của payroll (import trong hàm); thông báo, nhật ký gọi core.services.
Các nhóm hàm: 1. lịch dự kiến · 2. UC 4.1 check-in/out · 3. tính ngày công, giờ công (§9.2) · 4. UC 4.3 lịch sử ·
5. UC 4.2 giải trình · 6. UC 4.4 duyệt · 7. UC 4.5 bảng tổng hợp.
"""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from accounts.models import User, UserRole
from core import thong_bao
from core.models import NotificationType
from core.permissions import co_quyen_duyet
from core.services import KhongCoQuyen, LoiNghiepVu, LoiTruongNhap, ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType
from leave.models import DurationType, LeaveRequest, LeaveStatus, LeaveType
from schedule.models import ShiftAssignment, ShiftStatus, TeachingSession, TeachingSessionStatus
from .models import Attendance, AttendanceStatus, ExplanationStatus

# Các trạng thái "lỗi" được phép giải trình (UC 4.2)
TRANG_THAI_LOI = (AttendanceStatus.LATE, AttendanceStatus.EARLY_LEAVE, AttendanceStatus.ABSENT,
                  AttendanceStatus.MISSING_CHECKOUT)
# Các trạng thái được tính là "có đi làm" khi tính ngày công (§9.2)
TRANG_THAI_DI_LAM = (AttendanceStatus.ON_TIME, AttendanceStatus.LATE, AttendanceStatus.EARLY_LEAVE)


def _gio(chuoi):
    """'08:00' → time(8, 0) (tham số CA_FULLTIME trong settings ghi dạng chuỗi)."""
    return datetime.strptime(chuoi, '%H:%M').time()


def _bay_gio():
    return datetime.now()


def _so_phut(tu, den):
    """Số phút nguyên giữa hai thời điểm (làm tròn xuống)."""
    return int((den - tu).total_seconds() // 60)


# ============================================================ 1. LỊCH DỰ KIẾN (§9.2)
def _don_nghi_duyet_trong_ngay(nhan_su, ngay):
    return list(LeaveRequest.objects.filter(employee=nhan_su, status=LeaveStatus.APPROVED,
                                            start_date__lte=ngay, end_date__gte=ngay))


def _moc_giua_ca(nhan_su):
    """Mốc chia nửa ca (§6): Full-time theo ca (Ca 1: 12:00, Ca 2: 17:00); Part-time: 12:00."""
    if nhan_su.employment_type == EmploymentType.FULL_TIME and nhan_su.work_shift in settings.CA_FULLTIME:
        return _gio(settings.CA_FULLTIME[nhan_su.work_shift][2])
    return _gio(settings.MOC_NUA_NGAY_PART_TIME)


def nghi_ca_ngay(nhan_su, ngay):
    """UC 4.1 – luồng 1.1: có đơn nghỉ CẢ NGÀY đã duyệt (hoặc đủ hai đơn nửa đầu + nửa sau) chứa `ngay`."""
    cac_don = _don_nghi_duyet_trong_ngay(nhan_su, ngay)
    kieu = {d.duration_type for d in cac_don}
    return DurationType.FULL_DAY in kieu or {DurationType.HALF_DAY_AM, DurationType.HALF_DAY_PM} <= kieu


def lich_du_kien(nhan_su, ngay):
    """§9.1, §9.2 – danh sách khung giờ làm việc dự kiến của `nhan_su` trong `ngay` (có thể rỗng).

    Mỗi khung là dict: bd, kt (giờ), ca (ShiftAssignment hoặc None), ten (nhãn hiển thị).
    - Ngày không thuộc NGAY_LAM_VIEC, hoặc nghỉ cả ngày đã duyệt → rỗng.
    - Full-time: một khung theo `work_shift`.
    - Part-time: mỗi chỗ ca SCHEDULED của ngày là một khung (gắn ca); nếu là trợ giảng thực tế của các buổi dạy
      không CANCELLED trong ngày → thêm MỘT khung từ đầu buổi sớm nhất đến cuối buổi muộn nhất (không gắn ca).
    - Nghỉ nửa ngày đã duyệt: nửa đầu → bỏ phần trước mốc giữa ca; nửa sau → bỏ phần từ mốc giữa ca.
    """
    if ngay.weekday() not in settings.NGAY_LAM_VIEC or nghi_ca_ngay(nhan_su, ngay):
        return []
    khung = []
    if nhan_su.employment_type == EmploymentType.FULL_TIME:
        if nhan_su.work_shift in settings.CA_FULLTIME:
            bd, kt, _ = (_gio(x) for x in settings.CA_FULLTIME[nhan_su.work_shift])
            khung.append({'bd': bd, 'kt': kt, 'ca': None, 'ten': nhan_su.get_work_shift_display()})
    else:
        for ca in ShiftAssignment.objects.filter(employee=nhan_su, work_date=ngay, status=ShiftStatus.SCHEDULED
                                                 ).order_by('planned_start'):
            khung.append({'bd': ca.planned_start, 'kt': ca.planned_end, 'ca': ca, 'ten': ca.shift_role})
        buoi = TeachingSession.objects.filter(actual_assistant=nhan_su, session_date=ngay
                                              ).exclude(status=TeachingSessionStatus.CANCELLED)
        gio_buoi = list(buoi.values_list('planned_start', 'planned_end'))
        if gio_buoi:
            khung.append({'bd': min(g[0] for g in gio_buoi), 'kt': max(g[1] for g in gio_buoi), 'ca': None,
                          'ten': 'Trợ giảng'})
    moc = _moc_giua_ca(nhan_su)
    ket_qua = []
    don_nua = {d.duration_type for d in _don_nghi_duyet_trong_ngay(nhan_su, ngay)}
    for k in khung:
        if DurationType.HALF_DAY_AM in don_nua:
            if k['kt'] <= moc:
                continue
            k['bd'] = max(k['bd'], moc)
        if DurationType.HALF_DAY_PM in don_nua:
            if k['bd'] >= moc:
                continue
            k['kt'] = min(k['kt'], moc)
        ket_qua.append(k)
    return ket_qua


def _ban_ghi_cua_khung(nhan_su, ngay, khung):
    """Bản ghi chấm công đã có của một khung: theo ca (một bản ghi mỗi ca) hoặc theo ngày (không theo ca)."""
    if khung['ca'] is not None:
        return Attendance.objects.filter(employee=nhan_su, shift_assignment=khung['ca']).first()
    return Attendance.objects.filter(employee=nhan_su, work_date=ngay, shift_assignment__isnull=True).first()


# ============================================================ 2. UC 4.1 – CHECK-IN / CHECK-OUT
def man_hinh_cham_cong(nhan_su, ngay):
    """UC 4.1 – bước 2: lịch dự kiến hôm nay kèm bản ghi đã có và nút nào đang bật.

    Trả về dict: nghi_phep (luồng 1.1), khung (danh sách {khung, ban_ghi, hanh_dong}), khong_co_lich (luồng 1.2).
    hanh_dong của mỗi khung: 'check_in' (chưa vào), 'check_out' (đã vào, chưa ra) hoặc None (xong).
    """
    if nghi_ca_ngay(nhan_su, ngay):
        return {'nghi_phep': True, 'khung': [], 'khong_co_lich': False}
    cac_khung = []
    for k in lich_du_kien(nhan_su, ngay):
        ban_ghi = _ban_ghi_cua_khung(nhan_su, ngay, k)
        if ban_ghi is None:
            hanh_dong = 'check_in'
        elif ban_ghi.check_in and not ban_ghi.check_out:
            hanh_dong = 'check_out'
        else:
            hanh_dong = None
        cac_khung.append({'khung': k, 'ban_ghi': ban_ghi, 'hanh_dong': hanh_dong})
    return {'nghi_phep': False, 'khung': cac_khung, 'khong_co_lich': not cac_khung}


def _chon_khung(nhan_su, ngay, ma_ca, cac_khung):
    """Chọn khung theo ca đã chọn (Part-time nhiều ca) hoặc khung duy nhất."""
    if ma_ca:
        for k in cac_khung:
            if k['ca'] is not None and k['ca'].pk == int(ma_ca):
                return k
        raise LoiNghiepVu(thong_bao.CA_KHONG_HOP_LE)
    if len(cac_khung) > 1:
        raise LoiNghiepVu(thong_bao.CHON_CA_CHAM_CONG)
    return cac_khung[0]


def check_in(nhan_su, bay_gio=None, ma_ca=None):
    """UC 4.1 – bước 3–5: tạo bản ghi attendance với giờ dự kiến và check_in = bây giờ.

    Trễ hơn giờ bắt đầu QUÁ `PHUT_CHO_PHEP_TRE` phút → LATE + late_minutes; ngược lại ON_TIME.
    Lỗi: nghỉ phép cả ngày (1.1), không có lịch (1.2), đã check-in (3.1). Trả về bản ghi vừa tạo.
    """
    bay_gio = bay_gio or _bay_gio()
    ngay = bay_gio.date()
    if nhan_su.status != EmployeeStatus.ACTIVE:
        raise LoiNghiepVu(thong_bao.CHI_NHAN_SU_HOAT_DONG_CHAM_CONG)
    if nghi_ca_ngay(nhan_su, ngay):
        raise LoiNghiepVu(thong_bao.NGHI_PHEP_HOM_NAY)
    cac_khung = lich_du_kien(nhan_su, ngay)
    if not cac_khung:
        raise LoiNghiepVu(thong_bao.KHONG_CO_LICH_HOM_NAY)
    khung = _chon_khung(nhan_su, ngay, ma_ca, cac_khung)
    if _ban_ghi_cua_khung(nhan_su, ngay, khung) is not None:
        raise LoiNghiepVu(thong_bao.DA_CHECK_IN)
    phut_tre = _so_phut(datetime.combine(ngay, khung['bd']), bay_gio)
    tre = phut_tre if phut_tre > settings.PHUT_CHO_PHEP_TRE else 0
    with transaction.atomic():
        ban_ghi = Attendance.objects.create(
            employee=nhan_su, shift_assignment=khung['ca'], work_date=ngay, planned_start=khung['bd'],
            planned_end=khung['kt'], check_in=bay_gio, late_minutes=tre,
            attendance_status=AttendanceStatus.LATE if tre else AttendanceStatus.ON_TIME)
    return ban_ghi


def check_out(nhan_su, bay_gio=None, ma_ca=None):
    """UC 4.1 – bước 6–8: lưu check_out; sớm hơn giờ kết thúc → early_leave_minutes + EARLY_LEAVE
    (late_minutes vẫn giữ). Chưa check-in → "Vui lòng thực hiện Check-in trước." (luồng 6.2)."""
    bay_gio = bay_gio or _bay_gio()
    ngay = bay_gio.date()
    cac_ban_ghi = list(Attendance.objects.filter(employee=nhan_su, work_date=ngay, check_in__isnull=False
                                                 ).select_related('shift_assignment').order_by('planned_start'))
    if ma_ca:
        cac_ban_ghi = [b for b in cac_ban_ghi if b.shift_assignment_id == int(ma_ca)]
    chua_ra = [b for b in cac_ban_ghi if b.check_out is None]
    if not cac_ban_ghi:
        raise LoiNghiepVu(thong_bao.CHUA_CHECK_IN)
    if not chua_ra:
        raise LoiNghiepVu(thong_bao.DA_CHECK_OUT)
    if len(chua_ra) > 1:
        raise LoiNghiepVu(thong_bao.CHON_CA_CHAM_CONG)
    ban_ghi = chua_ra[0]
    phut_som = _so_phut(bay_gio, datetime.combine(ban_ghi.work_date, ban_ghi.planned_end))
    with transaction.atomic():
        ban_ghi.check_out = bay_gio
        if phut_som > 0:
            ban_ghi.early_leave_minutes = phut_som
            ban_ghi.attendance_status = AttendanceStatus.EARLY_LEAVE
        ban_ghi.save(update_fields=['check_out', 'early_leave_minutes', 'attendance_status'])
    return ban_ghi


def tong_thoi_gian_lam(ban_ghi):
    """UC 4.1 – bước 8: tổng thời gian làm việc dạng '3 giờ 25 phút' (từ check-in đến check-out)."""
    if not ban_ghi.check_in or not ban_ghi.check_out:
        return ''
    phut = max(_so_phut(ban_ghi.check_in, ban_ghi.check_out), 0)
    return f'{phut // 60} giờ {phut % 60:02d} phút'


# ============================================================ 3. NGÀY CÔNG, GIỜ CÔNG (§9.2)
def _dau_cuoi_thang(thang, nam):
    return date(nam, thang, 1), date(nam, thang, calendar.monthrange(nam, thang)[1])


def tinh_ngay_cong(nhan_su, thang, nam):
    """§9.1, §9.2 – ngày công trong tháng của nhân sự Full-time (Decimal, tối đa NGAY_CONG_CHUAN).

    - Mỗi bản ghi KHÔNG theo ca có trạng thái ON_TIME / LATE / EARLY_LEAVE → 1 ngày (bản ghi được chấp thuận giải trình
      đã thành ON_TIME nên cũng tính); ngày đó có đơn nghỉ nửa ca đã duyệt → 0,5.
    - Cộng ngày nghỉ ANNUAL đã duyệt rơi vào tháng (mỗi ngày làm việc 1, nửa ngày 0,5; đơn vắt qua hai tháng chỉ đếm
      phần trong tháng).
    - Không tính ABSENT, MISSING_CHECKOUT chưa được chấp thuận, nghỉ SICK / UNPAID / OTHER.
    """
    from leave.services import so_ngay_trong_thang   # import trong hàm (§3.2)
    dau, cuoi = _dau_cuoi_thang(thang, nam)
    tong = Decimal('0')
    cac_don = list(LeaveRequest.objects.filter(employee=nhan_su, status=LeaveStatus.APPROVED,
                                               start_date__lte=cuoi, end_date__gte=dau))
    ngay_nghi_nua = {d.start_date for d in cac_don if d.duration_type != DurationType.FULL_DAY}
    for b in Attendance.objects.filter(employee=nhan_su, work_date__range=(dau, cuoi), shift_assignment__isnull=True,
                                       attendance_status__in=TRANG_THAI_DI_LAM):
        tong += Decimal('0.5') if b.work_date in ngay_nghi_nua else Decimal('1')
    for d in cac_don:
        if d.leave_type == LeaveType.ANNUAL:
            tong += so_ngay_trong_thang(d, thang, nam)
    return min(tong, Decimal(settings.NGAY_CONG_CHUAN))


def tinh_gio_cong(nhan_su, thang, nam):
    """§9.1, §9.2 – giờ công trong tháng của nhân sự Part-time, cộng trên MỌI bản ghi (theo ca và theo buổi trợ giảng).

    - Giải trình APPROVED → tính đủ (giờ kết thúc dự kiến − giờ bắt đầu dự kiến).
    - Có cả check-in và check-out → max(0, min(check_out, kết thúc dự kiến) − max(check_in, bắt đầu dự kiến)).
    - Còn lại → 0. Đổi ra giờ, làm tròn 2 chữ số thập phân.
    """
    dau, cuoi = _dau_cuoi_thang(thang, nam)
    giay = 0
    for b in Attendance.objects.filter(employee=nhan_su, work_date__range=(dau, cuoi)):
        bd, kt = datetime.combine(b.work_date, b.planned_start), datetime.combine(b.work_date, b.planned_end)
        if b.explanation_status == ExplanationStatus.APPROVED:
            giay += (kt - bd).total_seconds()
        elif b.check_in and b.check_out:
            giay += max(0, (min(b.check_out, kt) - max(b.check_in, bd)).total_seconds())
    return (Decimal(giay) / Decimal(3600)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ============================================================ 4. UC 4.3 – LỊCH SỬ CHẤM CÔNG CÁ NHÂN
def lich_su_cham_cong(nhan_su, thang, nam):
    """UC 4.3 – bước 2: bản ghi chấm công của CHÍNH nhân sự trong tháng (lọc ngay trong truy vấn, §5), mới nhất lên đầu."""
    dau, cuoi = _dau_cuoi_thang(thang, nam)
    return Attendance.objects.filter(employee=nhan_su, work_date__range=(dau, cuoi)
                                     ).select_related('shift_assignment').order_by('-work_date', '-planned_start')


def tong_cong_thang(nhan_su, thang, nam):
    """UC 4.3 – bước 3: tổng ngày công (Full-time) hoặc tổng giờ công (Part-time): (giá trị, đơn vị)."""
    if nhan_su.employment_type == EmploymentType.FULL_TIME:
        return tinh_ngay_cong(nhan_su, thang, nam), 'ngày công'
    return tinh_gio_cong(nhan_su, thang, nam), 'giờ công'


def la_loi_co_the_giai_trinh(ban_ghi):
    """Dòng có nút "Gửi giải trình": trạng thái lỗi và chưa giải trình lần nào (Q14)."""
    return ban_ghi.attendance_status in TRANG_THAI_LOI and ban_ghi.explanation_status == ExplanationStatus.NONE


# ============================================================ 5. UC 4.2 – GỬI GIẢI TRÌNH
def _nguoi_duyet_cua(nguoi_gui):
    """Người nhận thông báo (Q2): giải trình của Quản lý → Super Admin; của Kế toán/Nhân viên → Quản lý."""
    vai_tro = UserRole.SUPER_ADMIN if nguoi_gui.role == UserRole.MANAGER else UserRole.MANAGER
    return User.objects.filter(role=vai_tro, is_active=True)


def _kiem_tra_chua_chot_luong(ban_ghi):
    from payroll.services import thang_da_chot   # import trong hàm (§3.2)
    if thang_da_chot(ban_ghi.work_date.month, ban_ghi.work_date.year):
        raise LoiNghiepVu(thong_bao.BANG_LUONG_DA_CHOT)


def kiem_tra_co_the_giai_trinh(nhan_su, ban_ghi):
    """Điều kiện để mở/gửi giải trình (UC 4.2 – tiền điều kiện): dòng của chính mình, đang ở trạng thái lỗi, chưa giải
    trình (luồng 1.1: "Ca làm việc này đã được giải trình."), bảng lương tháng đó chưa chốt (luồng 1.2)."""
    if ban_ghi.employee_id != nhan_su.pk:
        raise KhongCoQuyen(thong_bao.KHONG_XEM_BAN_GHI_CHAM_CONG)
    if ban_ghi.explanation_status != ExplanationStatus.NONE:
        raise LoiNghiepVu(thong_bao.DA_GIAI_TRINH)
    if ban_ghi.attendance_status not in TRANG_THAI_LOI:
        raise LoiNghiepVu(thong_bao.KHONG_CO_LOI_DE_GIAI_TRINH)
    _kiem_tra_chua_chot_luong(ban_ghi)


def gui_giai_trinh(nhan_su, ban_ghi, ly_do, tep=None):
    """UC 4.2 – bước 4–5: lưu lý do + minh chứng, explanation_status = PENDING, báo người duyệt (một giao dịch).

    Kiểm tra điều kiện (`kiem_tra_co_the_giai_trinh`) rồi mới kiểm tra lý do không trống
    (luồng 3.1: "Vui lòng nhập lý do giải trình.")."""
    kiem_tra_co_the_giai_trinh(nhan_su, ban_ghi)
    if not ly_do.strip():
        raise LoiTruongNhap(thong_bao.NHAP_LY_DO_GIAI_TRINH, 'ly_do')
    with transaction.atomic():
        ban_ghi.explanation_reason = ly_do.strip()
        if tep:
            ban_ghi.explanation_evidence = tep
        ban_ghi.explanation_status = ExplanationStatus.PENDING
        ban_ghi.save(update_fields=['explanation_reason', 'explanation_evidence', 'explanation_status'])
        noi_dung = thong_bao.TB_GIAI_TRINH_MOI_NOI_DUNG.format(
            nhan_su=nhan_su.full_name, ngay=f'{ban_ghi.work_date:%d/%m/%Y}',
            loi=ban_ghi.get_attendance_status_display().lower())
        for nguoi in _nguoi_duyet_cua(nhan_su.user):
            tao_thong_bao(nguoi, NotificationType.ATTENDANCE, thong_bao.TB_GIAI_TRINH_MOI_TIEU_DE, noi_dung,
                          reverse('attendance:review_detail', args=[ban_ghi.pk]))
        ghi_nhat_ky(nhan_su.user, 'UPDATE', 'attendance', ban_ghi.pk, 'Gửi giải trình chấm công')
    return ban_ghi


def mo_ta_chenh_lech(ban_ghi):
    """Cột "Chênh lệch" (Figma): 'Trễ 35 phút', 'Về sớm 15 phút' hoặc '0 phút'."""
    phan = []
    if ban_ghi.late_minutes:
        phan.append(f'Trễ {ban_ghi.late_minutes} phút')
    if ban_ghi.early_leave_minutes:
        phan.append(f'Về sớm {ban_ghi.early_leave_minutes} phút')
    return ', '.join(phan) or '0 phút'


# ============================================================ 6. UC 4.4 – DUYỆT GIẢI TRÌNH
def pham_vi_duyet(nguoi_duyet):
    """Giải trình trong phạm vi duyệt (Q2): Quản lý → Kế toán, Nhân viên; Super Admin → Quản lý; không gồm của chính mình."""
    if nguoi_duyet.role == UserRole.MANAGER:
        vai_tro = [UserRole.ACCOUNTANT, UserRole.EMPLOYEE]
    elif nguoi_duyet.role == UserRole.SUPER_ADMIN:
        vai_tro = [UserRole.MANAGER]
    else:
        return Attendance.objects.none()
    return Attendance.objects.filter(employee__user__role__in=vai_tro).exclude(employee__user=nguoi_duyet)


def danh_sach_giai_trinh(nguoi_duyet, trang_thai=ExplanationStatus.PENDING, tu_khoa='', phong_ban='', thang=None, nam=None):
    """UC 4.4 – bước 1–2: giải trình thuộc phạm vi duyệt (mặc định PENDING), lọc tên, phòng ban, tháng."""
    ds = pham_vi_duyet(nguoi_duyet).exclude(explanation_status=ExplanationStatus.NONE).select_related(
        'employee', 'shift_assignment').order_by('work_date', 'planned_start', 'pk')
    if trang_thai:
        ds = ds.filter(explanation_status=trang_thai)
    if tu_khoa:
        ds = ds.filter(employee__full_name__icontains=tu_khoa)
    if phong_ban:
        ds = ds.filter(employee__department=phong_ban)
    if thang and nam:
        dau, cuoi = _dau_cuoi_thang(thang, nam)
        ds = ds.filter(work_date__range=(dau, cuoi))
    return ds


def co_quyen_xem_giai_trinh(nguoi_xem, ban_ghi):
    """Chủ bản ghi, hoặc người duyệt trong phạm vi (cùng quy tắc `co_quyen_duyet`)."""
    if ban_ghi.employee.user_id == nguoi_xem.pk:
        return True
    return co_quyen_duyet(nguoi_xem, ban_ghi.employee.user)


def _kiem_tra_duoc_duyet(nguoi_duyet, ban_ghi):
    """Điều kiện chung của chấp thuận và từ chối: còn PENDING, đúng phạm vi (Q2), bảng lương tháng đó chưa chốt (5.3)."""
    if ban_ghi.explanation_status != ExplanationStatus.PENDING:
        raise LoiNghiepVu(thong_bao.YEU_CAU_DA_XU_LY)
    if not co_quyen_duyet(nguoi_duyet, ban_ghi.employee.user):
        raise KhongCoQuyen(thong_bao.KHONG_CO_QUYEN_DUYET_GIAI_TRINH)
    _kiem_tra_chua_chot_luong(ban_ghi)


def chap_thuan_giai_trinh(nguoi_duyet, ban_ghi, bay_gio=None):
    """UC 4.4 – bước 6: APPROVED, late_minutes = early_leave_minutes = 0, attendance_status = ON_TIME (ngày/ca tính đủ công
    theo giờ dự kiến), lưu người duyệt + thời điểm; báo nhân sự, ghi nhật ký (một giao dịch)."""
    bay_gio = bay_gio or _bay_gio()
    _kiem_tra_duoc_duyet(nguoi_duyet, ban_ghi)
    with transaction.atomic():
        ban_ghi.explanation_status = ExplanationStatus.APPROVED
        ban_ghi.late_minutes = ban_ghi.early_leave_minutes = 0
        ban_ghi.attendance_status = AttendanceStatus.ON_TIME
        ban_ghi.explanation_reviewed_by, ban_ghi.explanation_reviewed_at = nguoi_duyet, bay_gio
        ban_ghi.save(update_fields=['explanation_status', 'late_minutes', 'early_leave_minutes', 'attendance_status',
                                    'explanation_reviewed_by', 'explanation_reviewed_at'])
        tao_thong_bao(ban_ghi.employee.user, NotificationType.ATTENDANCE, thong_bao.TB_KET_QUA_GIAI_TRINH_TIEU_DE,
                      thong_bao.TB_GIAI_TRINH_DUOC_CHAP_THUAN.format(ngay=f'{ban_ghi.work_date:%d/%m/%Y}'),
                      reverse('attendance:my_attendance'))
        ghi_nhat_ky(nguoi_duyet, 'APPROVE', 'attendance', ban_ghi.pk, f'Chấp thuận giải trình của {ban_ghi.employee.full_name}')
    return ban_ghi


def tu_choi_giai_trinh(nguoi_duyet, ban_ghi, ly_do, bay_gio=None):
    """UC 4.4 – luồng thay thế 5.1.1: REJECTED + explanation_review_note, giữ nguyên trạng thái lỗi, báo nhân sự.
    Không nhập lý do → "Vui lòng nhập lý do từ chối." (luồng 5.2)."""
    bay_gio = bay_gio or _bay_gio()
    _kiem_tra_duoc_duyet(nguoi_duyet, ban_ghi)
    if not ly_do.strip():
        raise LoiTruongNhap(thong_bao.VUI_LONG_NHAP_LY_DO_TU_CHOI, 'ly_do')
    with transaction.atomic():
        ban_ghi.explanation_status = ExplanationStatus.REJECTED
        ban_ghi.explanation_review_note = ly_do.strip()
        ban_ghi.explanation_reviewed_by, ban_ghi.explanation_reviewed_at = nguoi_duyet, bay_gio
        ban_ghi.save(update_fields=['explanation_status', 'explanation_review_note', 'explanation_reviewed_by',
                                    'explanation_reviewed_at'])
        tao_thong_bao(ban_ghi.employee.user, NotificationType.ATTENDANCE, thong_bao.TB_KET_QUA_GIAI_TRINH_TIEU_DE,
                      thong_bao.TB_GIAI_TRINH_BI_TU_CHOI.format(ngay=f'{ban_ghi.work_date:%d/%m/%Y}', ly_do=ban_ghi.explanation_review_note),
                      reverse('attendance:my_attendance'))
        ghi_nhat_ky(nguoi_duyet, 'REJECT', 'attendance', ban_ghi.pk, f'Từ chối giải trình của {ban_ghi.employee.full_name}')
    return ban_ghi


# ============================================================ 7. UC 4.5 – BẢNG TỔNG HỢP CÔNG
def tong_hop_cong(thang, nam, phong_ban='', vi_tri=''):
    """UC 4.5 – bước 4–5: mỗi nhân sự một dòng: ngày công (Full-time) / giờ công (Part-time), số lần trễ, về sớm, ngày vắng,
    lần thiếu check-out, giải trình chờ duyệt. `can_chu_y` = còn lỗi CHƯA giải trình hoặc giải trình ĐANG CHỜ duyệt (tô đỏ).

    Gồm nhân sự đang làm việc và nhân sự đã nghỉ nhưng có chấm công trong tháng. Trả về list dòng (rỗng nếu không có
    bản ghi nào trong tháng và không có nhân sự phù hợp)."""
    dau, cuoi = _dau_cuoi_thang(thang, nam)
    cac_ban_ghi = {}
    for b in Attendance.objects.filter(work_date__range=(dau, cuoi)):
        cac_ban_ghi.setdefault(b.employee_id, []).append(b)
    nhan_su = Employee.objects.filter(status=EmployeeStatus.ACTIVE) | Employee.objects.filter(pk__in=list(cac_ban_ghi))
    if phong_ban:
        nhan_su = nhan_su.filter(department=phong_ban)
    if vi_tri:
        nhan_su = nhan_su.filter(position=vi_tri)
    ket_qua = []
    for nv in nhan_su.distinct().order_by('full_name'):
        ban_ghi = cac_ban_ghi.get(nv.pk, [])
        cong, don_vi = tong_cong_thang(nv, thang, nam)
        chua_giai_trinh = sum(1 for b in ban_ghi if b.attendance_status in TRANG_THAI_LOI
                              and b.explanation_status == ExplanationStatus.NONE)
        cho_duyet = sum(1 for b in ban_ghi if b.explanation_status == ExplanationStatus.PENDING)
        ket_qua.append({
            'nhan_su': nv, 'cong': cong, 'don_vi': don_vi,
            'so_tre': sum(1 for b in ban_ghi if b.late_minutes > 0),
            'so_som': sum(1 for b in ban_ghi if b.early_leave_minutes > 0),
            'so_vang': sum(1 for b in ban_ghi if b.attendance_status == AttendanceStatus.ABSENT),
            'so_thieu_checkout': sum(1 for b in ban_ghi if b.attendance_status == AttendanceStatus.MISSING_CHECKOUT),
            'chua_giai_trinh': chua_giai_trinh, 'cho_duyet': cho_duyet,
            'can_chu_y': bool(chua_giai_trinh or cho_duyet), 'co_ban_ghi': bool(ban_ghi)})
    return ket_qua


# ============================================================ 8. UC 9.2 – bước 4: chấm công của ngày hôm qua
def ghi_nhan_cham_cong_ngay(ngay):
    """UC 9.2 – bước 4: rà chấm công của `ngay` (hôm qua). Trả về (số ABSENT mới tạo, số MISSING_CHECKOUT mới đánh dấu).

    - Nhân sự ACTIVE có khung làm việc (`lich_du_kien`, đã loại ngày nghỉ cả ngày được duyệt) mà chưa có bản ghi chấm
      công của khung đó → tạo bản ghi ABSENT.
    - Bản ghi có check_in nhưng không có check_out (đang ON_TIME/LATE) → MISSING_CHECKOUT.
    - Mỗi trường hợp gửi một thông báo để nhân sự giải trình (UC 4.2).
    Chạy lại không trùng: khung đã có bản ghi (kể cả ABSENT vừa tạo) thì bỏ qua; bản ghi đã MISSING_CHECKOUT không còn
    thuộc ON_TIME/LATE nên không bị đánh dấu lần nữa.
    """
    ten_ngay = f'{ngay:%d/%m/%Y}'
    link = reverse('attendance:my_attendance')
    so_vang = so_thieu = 0
    with transaction.atomic():
        for nhan_su in Employee.objects.filter(status=EmployeeStatus.ACTIVE, join_date__lte=ngay).select_related('user'):
            for khung in lich_du_kien(nhan_su, ngay):
                if _ban_ghi_cua_khung(nhan_su, ngay, khung) is not None:
                    continue
                Attendance.objects.create(
                    employee=nhan_su, shift_assignment=khung['ca'], work_date=ngay, planned_start=khung['bd'],
                    planned_end=khung['kt'], attendance_status=AttendanceStatus.ABSENT)
                tao_thong_bao(nhan_su.user, NotificationType.ATTENDANCE, thong_bao.TB_VANG_MAT_TIEU_DE.format(ngay=ten_ngay),
                              thong_bao.TB_VANG_MAT_NOI_DUNG.format(ngay=ten_ngay, gio=f"{khung['bd']:%H:%M}–{khung['kt']:%H:%M}"),
                              link)
                so_vang += 1
        thieu = Attendance.objects.filter(
            work_date=ngay, check_in__isnull=False, check_out__isnull=True,
            attendance_status__in=[AttendanceStatus.ON_TIME, AttendanceStatus.LATE]).select_related('employee__user')
        for ban_ghi in thieu:
            ban_ghi.attendance_status = AttendanceStatus.MISSING_CHECKOUT
            ban_ghi.save(update_fields=['attendance_status'])
            tao_thong_bao(ban_ghi.employee.user, NotificationType.ATTENDANCE,
                          thong_bao.TB_THIEU_CHECKOUT_TIEU_DE.format(ngay=ten_ngay),
                          thong_bao.TB_THIEU_CHECKOUT_NOI_DUNG.format(
                              ngay=ten_ngay, gio=f"{ban_ghi.planned_start:%H:%M}–{ban_ghi.planned_end:%H:%M}"), link)
            so_thieu += 1
    return so_vang, so_thieu
