"""Hàm nghiệp vụ của app payroll (UC 7): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào salary_configs, payrolls, payroll_details. Chỉ ĐỌC employees, contracts, schedule,
attendance; muốn lấy ngày công, giờ công, số lớp thì gọi service của app sở hữu dữ liệu (import trong hàm).
Các nhóm hàm: 1. dùng chung (§9.1) · 2. UC 7.1 cấu hình lương · 3. UC 7.2 lập, tính lại, chốt, phát hành bảng lương ·
4. UC 7.3 phiếu lương cá nhân · 5. hàm P5, P7 viết sẵn cho app khác gọi (dong_cau_hinh_luong, thang_da_chot).
"""
import calendar
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from core import thong_bao
from core.models import NotificationType
from core.services import LoiNghiepVu, LoiTruongNhap, ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType, Position
from .models import (Payroll, PayrollDetail, PayrollDetailCategory as Nhom, PayrollDetailType as Loai, PayrollStatus,
                     SalaryConfig)

# 4 nhóm hệ thống tự tính (xóa và tính lại được) và các nhóm do Kế toán nhập (luôn được giữ lại), §7.3.18
NHOM_TU_DONG = (Nhom.WORKDAY_SALARY, Nhom.PART_TIME_HOURLY_PAY, Nhom.CLASS_ALLOWANCE, Nhom.RESPONSIBILITY_ALLOWANCE)
# Nhóm thủ công → loại khoản; OTHER do Kế toán chọn EARNING hoặc DEDUCTION nên để None
LOAI_CUA_NHOM_THU_CONG = {Nhom.BONUS: Loai.EARNING, Nhom.ADJUSTMENT_INCREASE: Loai.EARNING,
                          Nhom.ADJUSTMENT_DECREASE: Loai.DEDUCTION, Nhom.PERSONAL_INCOME_TAX: Loai.TAX, Nhom.OTHER: None}
LOAI_CUA_NHOM_TU_DONG = Loai.EARNING
# Dòng thuế TNCN do hệ thống tự tính nhận dấu hiệu này ở đầu mô tả (bảng payroll_details không có cột riêng để đánh dấu),
# còn dòng thuế Kế toán nhập tay thì không có dấu hiệu này nên được giữ khi tính lại.
MO_TA_THUE_TU_DONG = 'Thuế TNCN (tự tính)'


class BangLuongDaTonTai(LoiNghiepVu):
    """UC 7.2 – luồng 3.1: view bắt lỗi này để mở bảng lương hiện có thay vì chỉ báo lỗi."""


# ============================================================ 1. DÙNG CHUNG (§9.1, §9.2)
def lam_tron_dong(so):
    """Tiền tính bằng Decimal, làm tròn đến đồng (ROUND_HALF_UP) – §3.4."""
    return Decimal(so).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def dau_cuoi_thang(thang, nam):
    return date(nam, thang, 1), date(nam, thang, calendar.monthrange(nam, thang)[1])


def cau_hinh_hieu_luc(nhan_su, ngay):
    """§9.1 – cấu hình lương có hiệu lực vào `ngay`: effective_from ≤ ngay và (effective_to trống hoặc ≥ ngay). None nếu chưa có."""
    return SalaryConfig.objects.filter(employee=nhan_su, effective_from__lte=ngay).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=ngay)).order_by('-effective_from').first()


def tinh_thue_tncn(thu_nhap, la_full_time):
    """Thuế TNCN tạm tính của một tháng (đã làm tròn đồng), theo tham số trong settings.

    - Full-time: thu nhập tính thuế = thu nhập − giảm trừ bản thân (THUE_GIAM_TRU_BAN_THAN, không âm), rồi tính LŨY TIẾN
      theo từng bậc (phần thu nhập rơi vào bậc nào chịu thuế suất của bậc đó).
    - Part-time: thu nhập từ THUE_PART_TIME_NGUONG trở lên bị khấu trừ THUE_PART_TIME_TY_LE trên toàn bộ thu nhập;
      dưới ngưỡng thì không thuế.
    """
    thu_nhap = Decimal(thu_nhap)
    if not la_full_time:
        if thu_nhap >= settings.THUE_PART_TIME_NGUONG:
            return lam_tron_dong(thu_nhap * Decimal(settings.THUE_PART_TIME_TY_LE))
        return Decimal('0')
    con_lai = thu_nhap - Decimal(settings.THUE_GIAM_TRU_BAN_THAN)
    if con_lai <= 0:
        return Decimal('0')
    thue, can_duoi = Decimal('0'), Decimal('0')
    for can_tren, thue_suat in settings.THUE_BAC_LUY_TIEN:
        phan_trong_bac = con_lai - can_duoi if can_tren is None else min(con_lai, Decimal(can_tren)) - can_duoi
        if phan_trong_bac <= 0:
            break
        thue += phan_trong_bac * Decimal(thue_suat)
        if can_tren is None:
            break
        can_duoi = Decimal(can_tren)
    return lam_tron_dong(thue)


def la_dong_tu_dong(chi_tiet):
    """Dòng do hệ thống tự tính (4 nhóm tự động và dòng thuế TNCN tự tính): không xóa tay được, được tính lại."""
    return chi_tiet.category in NHOM_TU_DONG or (
        chi_tiet.category == Nhom.PERSONAL_INCOME_TAX and chi_tiet.description.startswith(MO_TA_THUE_TU_DONG))


# ============================================================ 2. UC 7.1 – CẤU HÌNH LƯƠNG
def nhan_su_can_cau_hinh(tu_khoa='', loai_hinh=''):
    """UC 7.1 – bước 1: nhân sự ONBOARDING hoặc ACTIVE kèm cấu hình đang áp dụng (effective_to trống)."""
    ds = Employee.objects.filter(status__in=[EmployeeStatus.ONBOARDING, EmployeeStatus.ACTIVE]).order_by('full_name')
    if tu_khoa:
        ds = ds.filter(full_name__icontains=tu_khoa)
    if loai_hinh:
        ds = ds.filter(employment_type=loai_hinh)
    dang_ap_dung = {c.employee_id: c for c in SalaryConfig.objects.filter(employee__in=ds, effective_to__isnull=True)}
    return [{'nhan_su': nv, 'cau_hinh': dang_ap_dung.get(nv.pk)} for nv in ds]


def lich_su_cau_hinh(nhan_su):
    """UC 7.1 – bước 2 và luồng 1.1: mọi cấu hình của nhân sự, mới nhất trước."""
    return SalaryConfig.objects.filter(employee=nhan_su).order_by('-effective_from')


def luu_cau_hinh_luong(nguoi_thuc_hien, nhan_su, luong_co_ban, don_gia_gio, phu_cap_lop, phu_cap_trach_nhiem, ngay_ap_dung):
    """UC 7.1 – bước 6–7: kiểm tra rồi, trong MỘT giao dịch, đóng cấu hình cũ (effective_to = ngày áp dụng mới − 1 ngày)
    và tạo cấu hình mới. Trả về cấu hình mới.

    Thứ tự kiểm tra (§10): số tiền ≥ 0 (5.2) · Full-time có lương cơ bản > 0, Part-time có đơn giá giờ > 0 (5.2) ·
    ngày áp dụng sau ngày áp dụng của cấu hình hiện tại (5.1) · ngày áp dụng không thuộc tháng đã chốt lương (5.3).
    Ô không dùng cho loại hình của nhân sự được lưu là 0 (Part-time không có lương cơ bản; chỉ giáo viên Full-time có phụ cấp lớp).
    """
    if nhan_su.status not in (EmployeeStatus.ONBOARDING, EmployeeStatus.ACTIVE):
        raise LoiNghiepVu(thong_bao.NHAN_SU_KHONG_CAU_HINH_LUONG)
    la_full_time = nhan_su.employment_type == EmploymentType.FULL_TIME
    la_giao_vien = nhan_su.position == Position.TEACHER
    for ten_truong, gia_tri in (('base_salary', luong_co_ban), ('hourly_rate', don_gia_gio),
                                ('class_allowance_rate', phu_cap_lop), ('responsibility_allowance', phu_cap_trach_nhiem)):
        if gia_tri < 0:
            raise LoiTruongNhap(thong_bao.SO_TIEN_AM, ten_truong)
    if la_full_time and luong_co_ban <= 0:
        raise LoiTruongNhap(thong_bao.LUONG_CO_BAN_PHAI_DUONG, 'base_salary')
    if not la_full_time and don_gia_gio <= 0:
        raise LoiTruongNhap(thong_bao.DON_GIA_GIO_PHAI_DUONG, 'hourly_rate')
    moi_nhat = SalaryConfig.objects.filter(employee=nhan_su).order_by('-effective_from').first()
    if moi_nhat is not None and ngay_ap_dung <= moi_nhat.effective_from:
        raise LoiTruongNhap(thong_bao.NGAY_AP_DUNG_SAI, 'effective_from')
    if thang_da_chot(ngay_ap_dung.month, ngay_ap_dung.year):
        raise LoiTruongNhap(thong_bao.CAU_HINH_THANG_DA_CHOT, 'effective_from')
    with transaction.atomic():
        if moi_nhat is not None and moi_nhat.effective_to is None:
            moi_nhat.effective_to = ngay_ap_dung - timedelta(days=1)
            moi_nhat.save(update_fields=['effective_to'])
        cau_hinh = SalaryConfig.objects.create(
            employee=nhan_su, base_salary=luong_co_ban if la_full_time else 0,
            hourly_rate=0 if la_full_time else don_gia_gio,
            class_allowance_rate=phu_cap_lop if (la_full_time and la_giao_vien) else 0,
            responsibility_allowance=phu_cap_trach_nhiem if la_full_time else 0, effective_from=ngay_ap_dung)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'salary_configs', cau_hinh.pk,
                    f'Cấu hình lương của {nhan_su.full_name} từ {ngay_ap_dung:%d/%m/%Y}')
    return cau_hinh


# ============================================================ 3. UC 7.2 – LẬP, TÍNH LẠI, CHỐT, PHÁT HÀNH
def pham_vi_tinh_luong(thang, nam):
    """UC 7.2 – bước 5, §9.2: danh sách (nhân sự, ngày dùng để chọn cấu hình lương).

    Nhân sự ACTIVE (đã vào làm trước hoặc trong tháng) → ngày cuối tháng; nhân sự đã nghỉ (RESIGNED/TERMINATED) có ngày
    thanh lý hợp đồng trong tháng → chính ngày thanh lý. Không gồm ONBOARDING."""
    from contracts.models import Contract   # chỉ đọc (§3.2)
    dau, cuoi = dau_cuoi_thang(thang, nam)
    ket_qua = {nv.pk: (nv, cuoi) for nv in Employee.objects.filter(status=EmployeeStatus.ACTIVE, join_date__lte=cuoi)}
    for hd in Contract.objects.filter(termination_date__range=(dau, cuoi), employee__status__in=[
            EmployeeStatus.RESIGNED, EmployeeStatus.TERMINATED]).select_related('employee').order_by('termination_date'):
        ket_qua[hd.employee_id] = (hd.employee, hd.termination_date)
    return sorted(ket_qua.values(), key=lambda x: x[0].full_name)


def tinh_cac_dong_tu_dong(nhan_su, cau_hinh, thang, nam):
    """UC 7.2 – bước 6, §9.2: các dòng EARNING hệ thống tự tính, dạng (nhóm, nội dung, số tiền); dòng 0 đồng bỏ qua.

    - Full-time: WORKDAY_SALARY = lương cơ bản × ngày công / 26 (ngày công đã tối đa 26).
    - Giáo viên Full-time: CLASS_ALLOWANCE = phụ cấp mỗi lớp × số lớp.
    - Có phụ cấp trách nhiệm: RESPONSIBILITY_ALLOWANCE = mức phụ cấp.
    - Part-time: PART_TIME_HOURLY_PAY = đơn giá giờ × tổng giờ công.
    """
    from attendance.services import tinh_gio_cong, tinh_ngay_cong      # import trong hàm (§3.2)
    from schedule.services import dem_lop_tinh_phu_cap
    cac_dong = []
    if nhan_su.employment_type == EmploymentType.FULL_TIME:
        ngay_cong = tinh_ngay_cong(nhan_su, thang, nam)
        cac_dong.append((Nhom.WORKDAY_SALARY, f'Lương ngày công: {ngay_cong.normalize():f}/{settings.NGAY_CONG_CHUAN} ngày',
                         lam_tron_dong(cau_hinh.base_salary * ngay_cong / settings.NGAY_CONG_CHUAN)))
        if nhan_su.position == Position.TEACHER:
            so_lop = dem_lop_tinh_phu_cap(nhan_su, thang, nam)
            cac_dong.append((Nhom.CLASS_ALLOWANCE, f'Phụ cấp lớp: {so_lop} lớp × {cau_hinh.class_allowance_rate:,.0f} đ'.replace(',', '.'),
                             lam_tron_dong(cau_hinh.class_allowance_rate * so_lop)))
        cac_dong.append((Nhom.RESPONSIBILITY_ALLOWANCE, 'Phụ cấp trách nhiệm', lam_tron_dong(cau_hinh.responsibility_allowance)))
    else:
        gio_cong = tinh_gio_cong(nhan_su, thang, nam)
        cac_dong.append((Nhom.PART_TIME_HOURLY_PAY, f'Lương giờ: {gio_cong} giờ × {cau_hinh.hourly_rate:,.0f} đ'.replace(',', '.'),
                         lam_tron_dong(cau_hinh.hourly_rate * gio_cong)))
    return [d for d in cac_dong if d[2] > 0]


def _cap_nhat_thue_tu_dong(bang_luong):
    """Tính lại dòng thuế TNCN TỰ ĐỘNG từ tổng thu nhập (EARNING) hiện có: xóa dòng tự tính cũ rồi tạo dòng mới nếu thuế > 0.
    Dòng thuế Kế toán nhập tay không bị đụng tới (cộng thêm vào total_tax)."""
    bang_luong.details.filter(category=Nhom.PERSONAL_INCOME_TAX, description__startswith=MO_TA_THUE_TU_DONG).delete()
    thu_nhap = sum((d.amount for d in bang_luong.details.filter(detail_type=Loai.EARNING)), Decimal('0'))
    la_full_time = bang_luong.employee.employment_type == EmploymentType.FULL_TIME
    thue = tinh_thue_tncn(thu_nhap, la_full_time)
    if thue > 0:
        mo_ta = (f'{MO_TA_THUE_TU_DONG}: thu nhập {thu_nhap:,.0f} đ, giảm trừ {Decimal(settings.THUE_GIAM_TRU_BAN_THAN):,.0f} đ'
                 if la_full_time else f'{MO_TA_THUE_TU_DONG}: khấu trừ {Decimal(settings.THUE_PART_TIME_TY_LE) * 100:.0f}% thu nhập {thu_nhap:,.0f} đ')
        PayrollDetail.objects.create(payroll=bang_luong, detail_type=Loai.TAX, category=Nhom.PERSONAL_INCOME_TAX,
                                     description=mo_ta.replace(',', '.'), amount=thue)


def tinh_lai_tong(bang_luong):
    """UC 7.2 – bước 7, 9: cập nhật thuế TNCN tự tính rồi tính gross = Σ EARNING; total_deduction = Σ DEDUCTION;
    total_tax = Σ TAX (gồm thuế tự tính và thuế nhập tay); net = gross − deduction − tax."""
    _cap_nhat_thue_tu_dong(bang_luong)
    tong = {Loai.EARNING: Decimal('0'), Loai.DEDUCTION: Decimal('0'), Loai.TAX: Decimal('0')}
    for chi_tiet in bang_luong.details.all():
        tong[chi_tiet.detail_type] += chi_tiet.amount
    bang_luong.gross_pay, bang_luong.total_deduction, bang_luong.total_tax = tong[Loai.EARNING], tong[Loai.DEDUCTION], tong[Loai.TAX]
    bang_luong.net_pay = bang_luong.gross_pay - bang_luong.total_deduction - bang_luong.total_tax
    bang_luong.save(update_fields=['gross_pay', 'total_deduction', 'total_tax', 'net_pay'])
    return bang_luong


def _bang_luong_cua_thang(thang, nam):
    return Payroll.objects.filter(period_month=thang, period_year=nam).select_related('employee')


def trang_thai_thang(thang, nam):
    """Trạng thái của cả bảng lương tháng: None (chưa lập), DRAFT, LOCKED hoặc SENT (suy ra từ các bản ghi, không lưu riêng)."""
    trang_thai = set(_bang_luong_cua_thang(thang, nam).values_list('status', flat=True))
    if not trang_thai:
        return None
    if PayrollStatus.DRAFT in trang_thai:
        return PayrollStatus.DRAFT
    return PayrollStatus.SENT if trang_thai == {PayrollStatus.SENT} else PayrollStatus.LOCKED


def _kiem_tra_du_cau_hinh(phamvi):
    """UC 7.2 – luồng 3.3: mọi nhân sự trong phạm vi phải có cấu hình lương hiệu lực; trả về {id: cấu hình}."""
    cau_hinh, thieu = {}, []
    for nv, ngay in phamvi:
        c = cau_hinh_hieu_luc(nv, ngay)
        if c is None:
            thieu.append(nv.full_name)
        else:
            cau_hinh[nv.pk] = c
    if thieu:
        raise LoiNghiepVu(thong_bao.NHAN_SU_THIEU_CAU_HINH.format(ds=', '.join(thieu)))
    return cau_hinh


def _them_dong_tu_dong(bang_luong, nhan_su, cau_hinh, thang, nam):
    PayrollDetail.objects.bulk_create([
        PayrollDetail(payroll=bang_luong, detail_type=LOAI_CUA_NHOM_TU_DONG, category=nhom, description=mo_ta, amount=so_tien)
        for nhom, mo_ta, so_tien in tinh_cac_dong_tu_dong(nhan_su, cau_hinh, thang, nam)])
    return tinh_lai_tong(bang_luong)


def khoi_tao_bang_luong(nguoi_thuc_hien, thang, nam, hom_nay=None):
    """UC 7.2 – bước 4–7: kiểm tra điều kiện rồi, trong MỘT giao dịch, tạo payrolls (DRAFT) + các dòng tự động cho từng nhân sự.

    Thứ tự kiểm tra (§10): tháng đã kết thúc (3.4) · chưa có bảng lương tháng này (3.1, ném BangLuongDaTonTai) · không còn
    giải trình chấm công PENDING trong tháng (3.2) · mọi nhân sự trong phạm vi có cấu hình lương (3.3). Trả về danh sách bảng lương.
    """
    from attendance.models import Attendance, ExplanationStatus   # chỉ đọc (§3.2)
    hom_nay = hom_nay or date.today()
    dau, cuoi = dau_cuoi_thang(thang, nam)
    if hom_nay <= cuoi:
        raise LoiNghiepVu(thong_bao.THANG_CHUA_KET_THUC)
    if _bang_luong_cua_thang(thang, nam).exists():
        raise BangLuongDaTonTai(thong_bao.BANG_LUONG_DA_TON_TAI)
    cho_duyet = Attendance.objects.filter(work_date__range=(dau, cuoi), explanation_status=ExplanationStatus.PENDING).count()
    if cho_duyet:
        raise LoiNghiepVu(thong_bao.CON_GIAI_TRINH_CHO_DUYET.format(so=cho_duyet))
    phamvi = pham_vi_tinh_luong(thang, nam)
    cau_hinh = _kiem_tra_du_cau_hinh(phamvi)
    with transaction.atomic():
        ket_qua = []
        for nv, _ngay in phamvi:
            bang = Payroll.objects.create(employee=nv, period_month=thang, period_year=nam, status=PayrollStatus.DRAFT,
                                          created_by=nguoi_thuc_hien)
            ket_qua.append(_them_dong_tu_dong(bang, nv, cau_hinh[nv.pk], thang, nam))
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'payrolls', None, f'Khởi tạo bảng lương {thang:02d}/{nam} ({len(ket_qua)} nhân sự)')
    return ket_qua


def tinh_lai_bang_luong(nguoi_thuc_hien, thang, nam):
    """UC 7.2 – luồng thay thế 8.1: khi bảng lương tháng còn DRAFT, xóa 4 nhóm dòng TỰ ĐỘNG rồi tính lại (giữ nguyên dòng
    thủ công) và bổ sung bảng lương cho nhân sự mới thuộc phạm vi. Trả về số bảng lương đã tính lại."""
    hien_co = {b.employee_id: b for b in _bang_luong_cua_thang(thang, nam)}
    if not hien_co:
        raise LoiNghiepVu(thong_bao.CHUA_CO_BANG_LUONG)
    if trang_thai_thang(thang, nam) != PayrollStatus.DRAFT:
        raise LoiNghiepVu(thong_bao.BANG_LUONG_DA_CHOT_KHONG_TINH_LAI)
    phamvi = pham_vi_tinh_luong(thang, nam)
    cau_hinh = _kiem_tra_du_cau_hinh(phamvi)
    _, cuoi = dau_cuoi_thang(thang, nam)
    trong_pham_vi = {nv.pk for nv, _ in phamvi}
    with transaction.atomic():
        for ma_nv, bang in hien_co.items():
            nv = bang.employee
            c = cau_hinh.get(ma_nv) or cau_hinh_hieu_luc(nv, cuoi)       # nhân sự không còn trong phạm vi: giữ cấu hình cuối tháng
            bang.details.filter(category__in=NHOM_TU_DONG).delete()
            if c is not None:
                _them_dong_tu_dong(bang, nv, c, thang, nam)
            else:
                tinh_lai_tong(bang)
        moi = [nv for nv, _ in phamvi if nv.pk not in hien_co]
        for nv in moi:
            bang = Payroll.objects.create(employee=nv, period_month=thang, period_year=nam, status=PayrollStatus.DRAFT,
                                          created_by=nguoi_thuc_hien)
            _them_dong_tu_dong(bang, nv, cau_hinh[nv.pk], thang, nam)
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'payrolls', None,
                    f'Tính lại bảng lương {thang:02d}/{nam} (thêm {len(moi)} nhân sự mới)')
    return len(hien_co) + len(moi)


def them_khoan_thu_cong(nguoi_thuc_hien, bang_luong, nhom, loai_khi_khac, mo_ta, so_tien):
    """UC 7.2 – bước 8–9: Kế toán thêm khoản thủ công (BONUS, ADJUSTMENT_INCREASE/DECREASE, PERSONAL_INCOME_TAX, OTHER);
    lưu dòng chi tiết và tính lại các tổng của nhân sự đó. Số tiền luôn dương; cộng hay trừ do nhóm quyết định
    (OTHER: Kế toán chọn EARNING hoặc DEDUCTION qua `loai_khi_khac`)."""
    if bang_luong.status != PayrollStatus.DRAFT:
        raise LoiNghiepVu(thong_bao.BANG_LUONG_KHONG_SUA_DUOC)
    if nhom not in LOAI_CUA_NHOM_THU_CONG:
        raise LoiTruongNhap(thong_bao.NHOM_KHONG_NHAP_TAY, 'category')
    if so_tien is None or so_tien <= 0:
        raise LoiTruongNhap(thong_bao.SO_TIEN_PHAI_DUONG, 'amount')
    loai = LOAI_CUA_NHOM_THU_CONG[nhom]
    if loai is None:
        if loai_khi_khac not in (Loai.EARNING, Loai.DEDUCTION):
            raise LoiTruongNhap(thong_bao.CHON_KHOAN_CONG_HAY_TRU, 'detail_type')
        loai = loai_khi_khac
    with transaction.atomic():
        chi_tiet = PayrollDetail.objects.create(payroll=bang_luong, detail_type=loai, category=nhom,
                                                description=mo_ta.strip() or Nhom(nhom).label, amount=lam_tron_dong(so_tien))
        tinh_lai_tong(bang_luong)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'payroll_details', chi_tiet.pk,
                    f'{Nhom(nhom).label} {chi_tiet.amount} cho {bang_luong.employee.full_name}')
    return chi_tiet


def xoa_khoan_thu_cong(nguoi_thuc_hien, chi_tiet):
    """UC 7.2 – luồng thay thế 8.2: xóa một khoản thủ công (chỉ khi còn DRAFT) rồi tính lại các tổng."""
    bang_luong = chi_tiet.payroll
    if bang_luong.status != PayrollStatus.DRAFT:
        raise LoiNghiepVu(thong_bao.BANG_LUONG_KHONG_SUA_DUOC)
    if la_dong_tu_dong(chi_tiet):
        raise LoiNghiepVu(thong_bao.CHI_XOA_KHOAN_THU_CONG)
    with transaction.atomic():
        ma = chi_tiet.pk
        chi_tiet.delete()
        tinh_lai_tong(bang_luong)
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'payroll_details', ma, f'Xóa khoản thủ công của {bang_luong.employee.full_name}')
    return bang_luong


def chot_bang_luong(nguoi_thuc_hien, thang, nam, bay_gio=None):
    """UC 7.2 – bước 10–11: không nhân sự nào có net_pay âm ("Thực nhận của [tên] đang âm…" – luồng 10.1), rồi chuyển TOÀN BỘ
    payrolls của tháng DRAFT → LOCKED + locked_at trong một giao dịch. Từ lúc này `thang_da_chot` trả True nên chấm công,
    giải trình, đơn nghỉ, cấu hình lương thuộc tháng đó bị khóa. Trả về số bảng lương đã chốt."""
    bay_gio = bay_gio or datetime.now()
    cac_bang = list(_bang_luong_cua_thang(thang, nam).order_by('employee__full_name'))
    if not cac_bang:
        raise LoiNghiepVu(thong_bao.CHUA_CO_BANG_LUONG)
    if any(b.status != PayrollStatus.DRAFT for b in cac_bang):
        raise LoiNghiepVu(thong_bao.BANG_LUONG_DA_CHOT_ROI)
    for b in cac_bang:
        if b.net_pay < 0:
            raise LoiNghiepVu(thong_bao.THUC_NHAN_AM.format(ten=b.employee.full_name))
    with transaction.atomic():
        Payroll.objects.filter(pk__in=[b.pk for b in cac_bang]).update(status=PayrollStatus.LOCKED, locked_at=bay_gio)
        ghi_nhat_ky(nguoi_thuc_hien, 'LOCK', 'payrolls', None, f'Chốt bảng lương {thang:02d}/{nam}')
    return len(cac_bang)


def phat_hanh_phieu_luong(nguoi_thuc_hien, thang, nam, bay_gio=None):
    """UC 7.2 – bước 12–13: LOCKED → SENT + sent_at, báo từng nhân sự "Phiếu lương tháng X/Y đã được phát hành.",
    ghi nhật ký (một giao dịch). Phải chốt trước khi phát hành. Trả về số phiếu đã phát hành."""
    bay_gio = bay_gio or datetime.now()
    cac_bang = list(_bang_luong_cua_thang(thang, nam).select_related('employee__user'))
    if not cac_bang:
        raise LoiNghiepVu(thong_bao.CHUA_CO_BANG_LUONG)
    if any(b.status == PayrollStatus.DRAFT for b in cac_bang):
        raise LoiNghiepVu(thong_bao.PHAI_CHOT_TRUOC_KHI_PHAT_HANH)
    cho_phat = [b for b in cac_bang if b.status == PayrollStatus.LOCKED]
    if not cho_phat:
        raise LoiNghiepVu(thong_bao.DA_PHAT_HANH_ROI)
    with transaction.atomic():
        for b in cho_phat:
            b.status, b.sent_at = PayrollStatus.SENT, bay_gio
            b.save(update_fields=['status', 'sent_at'])
            tao_thong_bao(b.employee.user, NotificationType.PAYROLL, thong_bao.TB_PHIEU_LUONG_TIEU_DE,
                          thong_bao.PHIEU_LUONG_DA_PHAT_HANH.format(thang=thang, nam=nam), reverse('payroll:payslip', args=[b.pk]))
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'payrolls', None, f'Phát hành phiếu lương {thang:02d}/{nam} ({len(cho_phat)} phiếu)')
    return len(cho_phat)


def danh_sach_thang():
    """Trang "Bảng lương": mỗi tháng đã lập một dòng (số nhân sự, tổng thực nhận, trạng thái), tháng mới nhất trước."""
    thang_nam = Payroll.objects.values_list('period_year', 'period_month').distinct().order_by('-period_year', '-period_month')
    ket_qua = []
    for nam, thang in thang_nam:
        cac_bang = _bang_luong_cua_thang(thang, nam)
        ket_qua.append({'thang': thang, 'nam': nam, 'so_nhan_su': cac_bang.count(),
                        'tong_thuc_nhan': sum((b.net_pay for b in cac_bang), Decimal('0')), 'trang_thai': trang_thai_thang(thang, nam)})
    return ket_qua


def tong_ket_thang(thang, nam, phong_ban='', tu_khoa=''):
    """Bảng lương tổng (Figma "Monthly Payroll"): các dòng + tổng gross/khấu trừ/thuế/thực nhận + đếm theo trạng thái."""
    cac_bang = _bang_luong_cua_thang(thang, nam).order_by('employee__full_name')
    if phong_ban:
        cac_bang = cac_bang.filter(employee__department=phong_ban)
    if tu_khoa:
        cac_bang = cac_bang.filter(employee__full_name__icontains=tu_khoa)
    cac_bang = list(cac_bang)
    tong = lambda truong: sum((getattr(b, truong) for b in cac_bang), Decimal('0'))
    return {'cac_bang': cac_bang, 'gross': tong('gross_pay'), 'khau_tru': tong('total_deduction'), 'thue': tong('total_tax'),
            'thuc_nhan': tong('net_pay'), 'dem': {t: sum(1 for b in cac_bang if b.status == t) for t in PayrollStatus.values}}


# ============================================================ 4. UC 7.3 – PHIẾU LƯƠNG CÁ NHÂN
def phieu_luong_da_phat_hanh(nhan_su):
    """UC 7.3 – bước 2: các tháng có phiếu lương SENT của CHÍNH nhân sự (lọc ngay trong truy vấn, §5). DRAFT, LOCKED không hiện."""
    return Payroll.objects.filter(employee=nhan_su, status=PayrollStatus.SENT).order_by('-period_year', '-period_month')


def co_quyen_xem_phieu(nguoi_xem, bang_luong):
    """UC 7.3 – luồng 3.1: chỉ chủ phiếu và chỉ khi phiếu đã phát hành (SENT)."""
    return bang_luong.employee.user_id == nguoi_xem.pk and bang_luong.status == PayrollStatus.SENT


def chi_tiet_phieu(bang_luong):
    """UC 7.3 – bước 4: chia các dòng thành thu nhập, khấu trừ, thuế (để vẽ phiếu lương)."""
    cac_dong = list(bang_luong.details.order_by('pk'))
    return {'thu_nhap': [d for d in cac_dong if d.detail_type == Loai.EARNING],
            'khau_tru': [d for d in cac_dong if d.detail_type == Loai.DEDUCTION],
            'thue': [d for d in cac_dong if d.detail_type == Loai.TAX]}


# ============================================================ 5. Hàm viết sẵn cho app khác gọi (P5, P7)
def dong_cau_hinh_luong(nhan_su, ngay):
    """UC 3.4 – bước 5: đặt effective_to = ngày thanh lý cho cấu hình lương đang áp dụng (effective_to trống).

    Hàm của app `payroll` (app sở hữu bảng salary_configs) để `contracts` gọi sang. Ràng buộc CSDL yêu cầu
    effective_to ≥ effective_from nên nếu cấu hình bắt đầu sau ngày thanh lý thì đóng đúng ngày bắt đầu của nó.
    Trả về số cấu hình đã đóng.
    """
    so_dong = 0
    for cau_hinh in SalaryConfig.objects.filter(employee=nhan_su, effective_to__isnull=True):
        cau_hinh.effective_to = max(ngay, cau_hinh.effective_from)
        cau_hinh.save(update_fields=['effective_to'])
        so_dong += 1
    return so_dong


def thang_da_chot(thang, nam):
    """§9.2 – tháng đã chốt lương: tồn tại bảng lương của tháng đó có status LOCKED hoặc SENT.

    Viết ở P7 vì UC 5.1 dùng để chặn đơn nghỉ thuộc tháng đã chốt (ROADMAP §11 P7); UC 4.2, 4.4, 7.1 dùng lại sau.
    """
    return Payroll.objects.filter(period_month=thang, period_year=nam,
                                  status__in=[PayrollStatus.LOCKED, PayrollStatus.SENT]).exists()
