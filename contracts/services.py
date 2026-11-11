"""Hàm nghiệp vụ của app contracts (UC 3): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào bảng contracts. Muốn đổi nhân sự, tài khoản, lịch, lương thì gọi service của
app sở hữu bảng đó (employees, accounts, schedule, payroll) và import ngay trong hàm.
"""
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.db.models import Q

from accounts.models import User, UserRole
from core import thong_bao
from core.models import NotificationType
from core.services import LoiNghiepVu, ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType
from .models import Contract, ContractStatus

# Ba nhóm của trang "Hợp đồng sắp hết hạn" (UC 3.5)
NHOM_QUA_HAN = 'QUA_HAN'
NHOM_DUOI_7 = 'DUOI_7'
NHOM_7_30 = '7_30'


# ============================================================ UC 3.1, 3.2 – Danh sách hợp đồng
def danh_sach_hop_dong(nguoi_xem, tu_khoa='', loai_hinh='', trang_thai=''):
    """UC 3.1 – bước 2: danh sách hợp đồng kèm tìm kiếm và bộ lọc Loại, Trạng thái.

    Quản lý, Kế toán xem mọi hợp đồng; Nhân viên chỉ thấy hợp đồng của chính mình (UC 3.2).
    """
    danh_sach = Contract.objects.select_related('employee__user').order_by('-start_date', '-id')
    if nguoi_xem.role not in (UserRole.MANAGER, UserRole.ACCOUNTANT):
        danh_sach = danh_sach.filter(employee__user=nguoi_xem)
    if loai_hinh:
        danh_sach = danh_sach.filter(employment_type=loai_hinh)
    if trang_thai:
        danh_sach = danh_sach.filter(status=trang_thai)
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(contract_number__icontains=tu_khoa.strip())
                                     | Q(employee__full_name__icontains=tu_khoa.strip()))
    return danh_sach


def co_quyen_xem_hop_dong(nguoi_xem, hop_dong):
    """UC 3.2 – bước 2: Quản lý, Kế toán xem mọi hợp đồng; Nhân viên chỉ xem hợp đồng của chính mình."""
    if nguoi_xem.role in (UserRole.MANAGER, UserRole.ACCOUNTANT):
        return True
    return nguoi_xem.role == UserRole.EMPLOYEE and hop_dong.employee.user_id == nguoi_xem.pk


def nhan_su_duoc_ky():
    """UC 3.1 – bước 4: chỉ nhân sự ONBOARDING hoặc ACTIVE được ký hợp đồng."""
    return Employee.objects.filter(status__in=[EmployeeStatus.ONBOARDING, EmployeeStatus.ACTIVE]).order_by('full_name')


def lich_su_gia_han(hop_dong):
    """Chuỗi hợp đồng liên kết qua previous_contract: các hợp đồng trước (cũ → mới) và các hợp đồng gia hạn sau nó."""
    truoc, hien = [], hop_dong.previous_contract
    while hien is not None and hien not in truoc:
        truoc.append(hien)
        hien = hien.previous_contract
    sau, hien = [], hop_dong.renewals.order_by('start_date').first()
    while hien is not None and hien not in sau:
        sau.append(hien)
        hien = hien.renewals.order_by('start_date').first()
    return list(reversed(truoc)), sau


def so_ngay_con_lai(hop_dong, hom_nay=None):
    """Số ngày còn lại tới end_date (âm nếu đã quá hạn); None nếu hợp đồng không xác định thời hạn."""
    hom_nay = hom_nay or date.today()
    return (hop_dong.end_date - hom_nay).days if hop_dong.end_date else None


def so_thang_hop_dong(hop_dong):
    """Số tháng của hợp đồng xác định thời hạn; None nếu không xác định thời hạn.

    Tính cả ngày kết thúc (01/01–31/12 là 12 tháng); phần ngày lẻ từ 15 ngày trở lên làm tròn thành 1 tháng.
    """
    if not hop_dong.end_date:
        return None
    bd, kt = hop_dong.start_date, hop_dong.end_date + timedelta(days=1)
    so_thang = (kt.year - bd.year) * 12 + (kt.month - bd.month)
    if kt.day < bd.day:
        so_thang -= 1
    moc = date(bd.year + (bd.month - 1 + so_thang) // 12, (bd.month - 1 + so_thang) % 12 + 1, 1)
    ngay_le = (kt - moc).days - (min(bd.day, 28) - 1)
    return so_thang + (1 if ngay_le >= 15 else 0)


def du_lieu_in_hop_dong(hop_dong):
    """UC 3.2 (bổ sung) – dữ liệu tự điền vào mẫu hợp đồng lao động để In / Lưu PDF.

    Lương không lưu trong bảng contracts mà ở salary_configs (UC 7.1), nên chỉ ĐỌC cấu hình lương đang hiệu lực
    tại ngày bắt đầu hợp đồng (nếu chưa có thì lấy cấu hình hiện tại). Chưa có cấu hình thì mẫu để dòng chấm.
    """
    from payroll.services import cau_hinh_hieu_luc        # chỉ đọc bảng của app payroll (§3.2)
    nhan_su = hop_dong.employee
    cau_hinh = cau_hinh_hieu_luc(nhan_su, hop_dong.start_date) or cau_hinh_hieu_luc(nhan_su, date.today())
    so_thang = so_thang_hop_dong(hop_dong)
    if so_thang is None:
        bao_truoc = 45                                     # Điều 35, 36 Bộ luật Lao động 2019
    elif so_thang >= 12:
        bao_truoc = 30
    else:
        bao_truoc = 3
    ca = settings.CA_FULLTIME.get(nhan_su.work_shift) if nhan_su.work_shift else None
    return {
        'hop_dong': hop_dong, 'nhan_su': nhan_su, 'trung_tam': settings.TRUNG_TAM, 'cau_hinh': cau_hinh,
        'so_thang': so_thang, 'bao_truoc': bao_truoc, 'bao_truoc_ngay_lam_viec': so_thang is not None and so_thang < 12,
        'la_full_time': hop_dong.employment_type == EmploymentType.FULL_TIME, 'ca': ca,
        'phep_nam': settings.PHEP_NAM_MAC_DINH, 'ngay_tra_luong': settings.NGAY_TRA_LUONG,
        'ngay_cong_chuan': settings.NGAY_CONG_CHUAN,
    }


# ============================================================ kiểm tra dùng chung
def _kiem_tra_so_hop_dong(so_hop_dong):
    if Contract.objects.filter(contract_number__iexact=so_hop_dong).exists():
        raise LoiNghiepVu(thong_bao.SO_HOP_DONG_DA_TON_TAI)


def _kiem_tra_file(tep):
    if not tep:
        raise LoiNghiepVu(thong_bao.THIEU_FILE_SCAN)


# ============================================================ UC 3.1 – Thêm hợp đồng
def them_hop_dong(nguoi_thuc_hien, nhan_su, so_hop_dong, loai_hinh, ngay_bat_dau, ngay_ket_thuc, tep_scan):
    """UC 3.1 – bước 6–7: kiểm tra, rồi trong MỘT giao dịch: tạo hợp đồng ACTIVE, đồng bộ loại hình nhân sự,
    nếu nhân sự đang ONBOARDING thì chuyển ACTIVE và báo cho nhân sự (Q5).
    """
    from employees.services import dong_bo_loai_hinh, kich_hoat_nhan_su   # import trong hàm (§3.2)
    if nhan_su.status not in (EmployeeStatus.ONBOARDING, EmployeeStatus.ACTIVE):
        raise LoiNghiepVu(thong_bao.NHAN_SU_KHONG_DUOC_KY)
    if Contract.objects.filter(employee=nhan_su, status=ContractStatus.ACTIVE).exists():
        raise LoiNghiepVu(thong_bao.HOP_DONG_DANG_HIEU_LUC)                       # luồng 5.1
    _kiem_tra_so_hop_dong(so_hop_dong)                                           # luồng 5.2
    if ngay_ket_thuc and ngay_ket_thuc <= ngay_bat_dau:
        raise LoiNghiepVu(thong_bao.NGAY_KET_THUC_HD_SAI)                         # luồng 5.3
    _kiem_tra_file(tep_scan)
    with transaction.atomic():
        hop_dong = Contract.objects.create(
            employee=nhan_su, contract_number=so_hop_dong, employment_type=loai_hinh, start_date=ngay_bat_dau,
            end_date=ngay_ket_thuc, file_url=tep_scan, status=ContractStatus.ACTIVE)
        dong_bo_loai_hinh(nhan_su, loai_hinh)
        if nhan_su.status == EmployeeStatus.ONBOARDING:
            kich_hoat_nhan_su(nhan_su)
            tao_thong_bao(nhan_su.user, NotificationType.CONTRACT, thong_bao.TB_HD_KICH_HOAT_TIEU_DE,
                          thong_bao.TB_HD_KICH_HOAT_NOI_DUNG.format(so_hd=so_hop_dong))
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'Contract', hop_dong.pk, f'Thêm hợp đồng {so_hop_dong} cho {nhan_su.code}')
    return hop_dong


# ============================================================ UC 3.3 – Gia hạn, cập nhật file
def gia_han_hop_dong(nguoi_thuc_hien, hop_dong_cu, so_hop_dong, loai_hinh, ngay_bat_dau, ngay_ket_thuc, tep_scan):
    """UC 3.3 – bước 4–5: hợp đồng cũ ACTIVE → EXPIRED; tạo hợp đồng mới ACTIVE trỏ previous_contract về hợp đồng cũ;
    đồng bộ loại hình; báo nhân sự. Tất cả trong một giao dịch.

    Thứ tự quan trọng: phải chuyển hợp đồng cũ sang EXPIRED TRƯỚC khi tạo hợp đồng mới, vì CSDL chỉ cho mỗi nhân sự
    một hợp đồng ACTIVE (UniqueConstraint có điều kiện).
    """
    from employees.services import dong_bo_loai_hinh
    if hop_dong_cu.status != ContractStatus.ACTIVE:
        raise LoiNghiepVu(thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
    _kiem_tra_so_hop_dong(so_hop_dong)                                           # luồng 3.2
    if ngay_bat_dau <= hop_dong_cu.start_date or (ngay_ket_thuc and ngay_ket_thuc <= ngay_bat_dau):
        raise LoiNghiepVu(thong_bao.NGAY_HOP_DONG_MOI_SAI)                        # luồng 3.1
    _kiem_tra_file(tep_scan)
    nhan_su = hop_dong_cu.employee
    with transaction.atomic():
        hop_dong_cu.status = ContractStatus.EXPIRED
        hop_dong_cu.save(update_fields=['status'])
        hop_dong_moi = Contract.objects.create(
            employee=nhan_su, contract_number=so_hop_dong, employment_type=loai_hinh, start_date=ngay_bat_dau,
            end_date=ngay_ket_thuc, previous_contract=hop_dong_cu, file_url=tep_scan, status=ContractStatus.ACTIVE)
        dong_bo_loai_hinh(nhan_su, loai_hinh)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'Contract', hop_dong_moi.pk,
                    f'Gia hạn {hop_dong_cu.contract_number} → {so_hop_dong}')
        tao_thong_bao(nhan_su.user, NotificationType.CONTRACT, thong_bao.TB_HD_GIA_HAN_TIEU_DE,
                      thong_bao.TB_HD_GIA_HAN_NOI_DUNG.format(so_hd=so_hop_dong, bat_dau=ngay_bat_dau.strftime('%d/%m/%Y')))
    return hop_dong_moi


def cap_nhat_file_scan(nguoi_thuc_hien, hop_dong, tep_scan):
    """UC 3.3 – luồng 1.1.1: thay file scan của hợp đồng ACTIVE. Không sửa thông tin khác (đổi điều khoản = gia hạn)."""
    if hop_dong.status != ContractStatus.ACTIVE:
        raise LoiNghiepVu(thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
    _kiem_tra_file(tep_scan)
    hop_dong.file_url = tep_scan
    hop_dong.save(update_fields=['file_url'])
    ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'Contract', hop_dong.pk, f'Cập nhật file scan {hop_dong.contract_number}')
    return hop_dong


# ============================================================ UC 3.4 – Thanh lý
def thanh_ly_hop_dong(nguoi_thuc_hien, hop_dong, ngay_thanh_ly, ly_do, hinh_thuc, hom_nay=None):
    """UC 3.4 – bước 4–7: thanh lý hợp đồng và điều phối các app khác, trong MỘT giao dịch.

    1. contracts (app này): ACTIVE → TERMINATED, lưu ngày và lý do.
    2. employees: ACTIVE → RESIGNED (nhân sự xin nghỉ) hoặc TERMINATED (trung tâm chấm dứt).
    3. accounts: khóa tài khoản.
    4. payroll: đóng cấu hình lương đang hiệu lực.
    5. schedule: đóng phân công lớp, giải phóng ca, tạo yêu cầu dạy thay cho buổi dạy sau ngày thanh lý.
    Sau đó báo Quản lý số buổi cần người thay. Ngày thanh lý phải trong [ngày bắt đầu hợp đồng, hôm nay] (Q7).
    """
    from accounts.services import khoa_tai_khoan                     # import trong hàm (§3.2 quy tắc 3)
    from employees.services import chuyen_nghi_viec
    from payroll.services import dong_cau_hinh_luong
    from schedule.services import giai_phong_lich_tuong_lai
    hom_nay = hom_nay or date.today()
    if hop_dong.status != ContractStatus.ACTIVE:
        raise LoiNghiepVu(thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
    ly_do = (ly_do or '').strip()
    if not ly_do:
        raise LoiNghiepVu(thong_bao.NHAP_LY_DO_THANH_LY)                          # luồng 3.2
    if ngay_thanh_ly < hop_dong.start_date or ngay_thanh_ly > hom_nay:
        raise LoiNghiepVu(thong_bao.NGAY_THANH_LY_SAI)                            # luồng 3.1
    nhan_su = hop_dong.employee
    with transaction.atomic():
        hop_dong.status = ContractStatus.TERMINATED
        hop_dong.termination_date = ngay_thanh_ly
        hop_dong.termination_reason = ly_do
        hop_dong.save(update_fields=['status', 'termination_date', 'termination_reason'])
        chuyen_nghi_viec(nhan_su, hinh_thuc)
        if nhan_su.user.is_active:
            khoa_tai_khoan(nhan_su.user, nguoi_thuc_hien=None)                   # tự động nên không có "người tự khóa mình"
        dong_cau_hinh_luong(nhan_su, ngay_thanh_ly)
        so_buoi_can_thay = giai_phong_lich_tuong_lai(nhan_su, ngay_thanh_ly)
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'Contract', hop_dong.pk,
                    f'Thanh lý {hop_dong.contract_number} ({hinh_thuc}) ngày {ngay_thanh_ly:%d/%m/%Y}: {ly_do}')
        if so_buoi_can_thay:
            for quan_ly in User.objects.filter(role=UserRole.MANAGER, is_active=True):
                tao_thong_bao(quan_ly, NotificationType.SCHEDULE, thong_bao.TB_THANH_LY_TIEU_DE,
                              thong_bao.TB_THANH_LY_NOI_DUNG.format(nhan_su=nhan_su.full_name, so_buoi=so_buoi_can_thay),
                              reverse('schedule:substitute_list'))     # UC 6.4: bấm thông báo mở danh sách
    return so_buoi_can_thay


# ============================================================ UC 3.5 – Hợp đồng sắp hết hạn
def hop_dong_sap_het_han(tu_khoa='', hom_nay=None):
    """UC 3.5 – bước 2–3: hợp đồng ACTIVE có end_date ≤ hôm nay + 30 ngày, chia ba nhóm.

    - Đã quá hạn: end_date trước hôm nay.   - Còn dưới 7 ngày: còn 0–6 ngày.   - Còn 7–30 ngày.
    Hệ thống KHÔNG tự kết thúc hợp đồng quá hạn (Q6); chỉ liệt kê để Quản lý quyết định gia hạn hay thanh lý.
    Trả về dict {nhóm: [(hợp đồng, số ngày còn lại)]}.
    """
    hom_nay = hom_nay or date.today()
    danh_sach = Contract.objects.filter(
        status=ContractStatus.ACTIVE, end_date__isnull=False,
        end_date__lte=hom_nay + timedelta(days=settings.SO_NGAY_CANH_BAO)).select_related('employee').order_by('end_date')
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(contract_number__icontains=tu_khoa.strip())
                                     | Q(employee__full_name__icontains=tu_khoa.strip()))
    nhom = {NHOM_QUA_HAN: [], NHOM_DUOI_7: [], NHOM_7_30: []}
    for hop_dong in danh_sach:
        con_lai = (hop_dong.end_date - hom_nay).days
        khoa = NHOM_QUA_HAN if con_lai < 0 else NHOM_DUOI_7 if con_lai < 7 else NHOM_7_30
        nhom[khoa].append((hop_dong, con_lai))
    return nhom


# ============================================================ UC 9.2 – bước 3: nhắc hợp đồng (tác vụ hằng ngày)
def nhac_hop_dong_het_han(hom_nay):
    """UC 9.2 – bước 3: hợp đồng ACTIVE còn đúng 30, 7, 0 ngày (CAC_MOC_NHAC) hoặc VỪA quá ngày kết thúc (hôm qua)
    → thông báo cho mọi Quản lý đang hoạt động. Hệ thống KHÔNG đổi trạng thái hợp đồng (Q6). Trả về số thông báo gửi.

    Gửi trùng được chặn: đã có thông báo cùng người nhận, cùng nội dung trong ngày thì bỏ qua (chạy lại không trùng).
    """
    from core.models import Notification
    cac_moc = [hom_nay + timedelta(days=n) for n in settings.CAC_MOC_NHAC] + [hom_nay - timedelta(days=1)]
    quan_ly = list(User.objects.filter(role=UserRole.MANAGER, is_active=True))
    so_thong_bao = 0
    for hop_dong in Contract.objects.filter(status=ContractStatus.ACTIVE, end_date__in=cac_moc).select_related('employee'):
        con_lai = (hop_dong.end_date - hom_nay).days
        tinh_trang = ('vừa quá ngày kết thúc' if con_lai < 0 else 'hết hạn hôm nay' if con_lai == 0
                      else f'còn {con_lai} ngày là hết hạn')
        noi_dung = thong_bao.TB_HOP_DONG_HAN_NOI_DUNG.format(so_hd=hop_dong.contract_number,
                                                             nhan_su=hop_dong.employee.full_name, tinh_trang=tinh_trang)
        for nguoi_nhan in quan_ly:
            if not Notification.objects.filter(recipient=nguoi_nhan, title=thong_bao.TB_HOP_DONG_HAN_TIEU_DE,
                                               message=noi_dung, created_at__date=date.today()).exists():
                tao_thong_bao(nguoi_nhan, NotificationType.CONTRACT, thong_bao.TB_HOP_DONG_HAN_TIEU_DE, noi_dung,
                              reverse('contracts:contract_expiring'))
                so_thong_bao += 1
    return so_thong_bao
