"""Hàm nghiệp vụ của app employees (UC 2): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào employees và employee_documents; muốn đổi bảng của app khác thì gọi
service của app đó (accounts, leave, recruitment, core), và import ngay trong hàm.
"""
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from core import thong_bao
from core.models import NotificationType
from core.permissions import co_quyen_duyet
from core.services import KhongCoQuyen, LoiNghiepVu, ghi_nhat_ky, tao_thong_bao
from .models import (DocumentStatus, Employee, EmployeeDocument, EmployeeStatus, EmploymentType, Position)

# Mức cảnh báo giấy tờ (UC 2.4)
MUC_CON_HAN = 'VALID'
MUC_SAP_HET_HAN = 'EXPIRING'
MUC_DA_HET_HAN = 'EXPIRED'


# ============================================================ UC 1.4 → đồng bộ từ tài khoản
def dong_bo_ho_ten_sdt(nhan_su, ho_ten, so_dien_thoai):
    """UC 1.4 – bước 5: đồng bộ Họ tên, SĐT từ tài khoản sang hồ sơ nhân sự.

    (ROADMAP xếp hàm này ở P4; đã viết từ P2 vì UC 1.4 cần.)
    """
    nhan_su.full_name = ho_ten
    nhan_su.phone = so_dien_thoai
    nhan_su.save(update_fields=['full_name', 'phone', 'updated_at'])
    return nhan_su


# ============================================================ Hàm cho UC 3 (hợp đồng) gọi sang
def kich_hoat_nhan_su(nhan_su):
    """UC 3.1 – bước 7: ONBOARDING → ACTIVE khi có hợp đồng đầu tiên (Q5, §8)."""
    if nhan_su.status != EmployeeStatus.ONBOARDING:
        raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_NHAN_SU)
    nhan_su.status = EmployeeStatus.ACTIVE
    nhan_su.save(update_fields=['status', 'updated_at'])
    return nhan_su


def dong_bo_loai_hinh(nhan_su, loai_hinh):
    """UC 3.1, 3.3: đồng bộ employees.employment_type theo hợp đồng ACTIVE.

    Part-time không có ca cố định nên xóa work_shift; chuyển sang Full-time thì tạo quỹ phép năm nay (Q11).
    """
    from leave.services import tao_quy_phep   # import trong hàm (§3.2)
    nhan_su.employment_type = loai_hinh
    if loai_hinh == EmploymentType.PART_TIME:
        nhan_su.work_shift = ''
    nhan_su.save(update_fields=['employment_type', 'work_shift', 'updated_at'])
    if loai_hinh == EmploymentType.FULL_TIME:
        tao_quy_phep(nhan_su)
    return nhan_su


def chuyen_nghi_viec(nhan_su, hinh_thuc):
    """UC 3.4 – bước 5: ACTIVE → RESIGNED (nhân sự xin nghỉ) hoặc TERMINATED (trung tâm chấm dứt) (§8)."""
    if nhan_su.status != EmployeeStatus.ACTIVE or hinh_thuc not in (EmployeeStatus.RESIGNED, EmployeeStatus.TERMINATED):
        raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_NHAN_SU)
    nhan_su.status = hinh_thuc
    nhan_su.save(update_fields=['status', 'updated_at'])
    return nhan_su


# ============================================================ UC 2.1 – Danh sách nhân sự
def tim_ma_nhan_vien(tu_khoa):
    """Đọc mã NV người dùng gõ: "NV0012", "nv12" hay "12" đều ra id 12; không phải mã thì trả None."""
    chuoi = tu_khoa.strip().upper()
    if chuoi.startswith('NV'):
        chuoi = chuoi[2:]
    return int(chuoi) if chuoi.isdigit() else None


def danh_sach_nhan_su(nguoi_xem, tu_khoa='', vi_tri='', loai_hinh='', trang_thai=''):
    """UC 2.1 – bước 2–4: danh sách nhân sự theo phạm vi quyền.

    - Super Admin, Quản lý: mọi trạng thái, đủ cột.
    - Kế toán, Nhân viên: chỉ nhân sự ACTIVE (và bỏ qua bộ lọc Trạng thái).
    """
    danh_sach = Employee.objects.select_related('user').order_by('id')
    xem_day_du = nguoi_xem.role in (UserRole.SUPER_ADMIN, UserRole.MANAGER)
    if not xem_day_du:
        danh_sach = danh_sach.filter(status=EmployeeStatus.ACTIVE)
    elif trang_thai:
        danh_sach = danh_sach.filter(status=trang_thai)
    if tu_khoa:
        dieu_kien = Q(full_name__icontains=tu_khoa.strip())
        ma = tim_ma_nhan_vien(tu_khoa)
        if ma is not None:
            dieu_kien |= Q(id=ma)
        danh_sach = danh_sach.filter(dieu_kien)
    if vi_tri:
        danh_sach = danh_sach.filter(position=vi_tri)
    if loai_hinh:
        danh_sach = danh_sach.filter(employment_type=loai_hinh)
    return danh_sach


def dem_nhan_su_theo_trang_thai():
    """Số nhân sự theo từng trạng thái (hiện ở đầu danh sách cho Quản lý và Super Admin)."""
    dem = {ma: 0 for ma in EmployeeStatus.values}
    for ma in Employee.objects.values_list('status', flat=True):
        dem[ma] += 1
    return dem


# ============================================================ Giấy tờ: phạm vi duyệt, mức cảnh báo
def giay_to_cho_duyet(nguoi_duyet):
    """UC 2.6 – bước 2: giấy tờ PENDING thuộc phạm vi duyệt của người này (Q2).

    - Quản lý: giấy tờ của Nhân viên và Kế toán.
    - Super Admin: giấy tờ của tài khoản vai trò Quản lý.
    - Không bao giờ gồm giấy tờ của chính người duyệt.
    """
    danh_sach = EmployeeDocument.objects.filter(status=DocumentStatus.PENDING).select_related('employee__user')
    if nguoi_duyet.role == UserRole.MANAGER:
        danh_sach = danh_sach.filter(employee__user__role__in=[UserRole.EMPLOYEE, UserRole.ACCOUNTANT])
    elif nguoi_duyet.role == UserRole.SUPER_ADMIN:
        danh_sach = danh_sach.filter(employee__user__role=UserRole.MANAGER)
    else:
        return danh_sach.none()
    return danh_sach.exclude(employee__user=nguoi_duyet).order_by('created_at')


def muc_canh_bao(giay_to, hom_nay=None):
    """Giấy tờ còn hạn / sắp hết hạn (≤ SO_NGAY_CANH_BAO ngày) / đã hết hạn.

    Giấy tờ APPROVED mà quá ngày hết hạn cũng tính là "đã hết hạn" ngay, không cần chờ tác vụ hằng ngày
    (UC 9.2) đổi trạng thái sang EXPIRED.
    """
    hom_nay = hom_nay or date.today()
    if giay_to.status == DocumentStatus.EXPIRED:
        return MUC_DA_HET_HAN
    if giay_to.expiry_date and giay_to.status == DocumentStatus.APPROVED:
        if giay_to.expiry_date < hom_nay:
            return MUC_DA_HET_HAN
        if giay_to.expiry_date <= hom_nay + timedelta(days=settings.SO_NGAY_CANH_BAO):
            return MUC_SAP_HET_HAN
    return MUC_CON_HAN


def _nguoi_duyet_cua(nhan_su):
    """Người nhận thông báo "giấy tờ chờ duyệt": Quản lý; nếu người gửi là Quản lý thì Super Admin (Q2)."""
    vai_tro = UserRole.SUPER_ADMIN if nhan_su.user.role == UserRole.MANAGER else UserRole.MANAGER
    return User.objects.filter(role=vai_tro, is_active=True).exclude(pk=nhan_su.user_id)


# ============================================================ UC 2.2 – Cập nhật hồ sơ cá nhân
def luu_ho_so_ca_nhan(nhan_su, so_dien_thoai, dia_chi, tai_khoan_ngan_hang, giay_to=None, giay_to_cu=None):
    """UC 2.2 – bước 5–6: lưu thông tin cá nhân ngay; giấy tờ mới (nếu có) vào PENDING và báo người duyệt.

    `giay_to` là dict (document_type, document_name, issue_date, expiry_date, file_url) khi tải giấy tờ MỚI.
    `giay_to_cu` là bản ghi cũ khi bấm "Tải bản mới" (luồng 1.1): cập nhật chính bản ghi đó, không tạo thêm.
    Tất cả trong một transaction. Trả về giấy tờ vừa tạo/cập nhật (hoặc None).
    """
    from accounts.services import dong_bo_tu_ho_so   # import trong hàm (§3.2 quy tắc 3)
    with transaction.atomic():
        nhan_su.phone = so_dien_thoai
        nhan_su.address = dia_chi
        nhan_su.bank_account = tai_khoan_ngan_hang
        nhan_su.save(update_fields=['phone', 'address', 'bank_account', 'updated_at'])
        dong_bo_tu_ho_so(nhan_su.user, so_dien_thoai=so_dien_thoai)           # đồng bộ users.phone

        ket_qua = None
        if giay_to_cu is not None and giay_to:
            ket_qua = tai_ban_moi_giay_to(giay_to_cu, giay_to['issue_date'], giay_to['expiry_date'], giay_to['file_url'])
        elif giay_to:
            ket_qua = EmployeeDocument.objects.create(employee=nhan_su, status=DocumentStatus.PENDING, **giay_to)
        if ket_qua is not None:
            for nguoi_duyet in _nguoi_duyet_cua(nhan_su):
                tao_thong_bao(nguoi_duyet, NotificationType.PROFILE, thong_bao.TB_CHO_DUYET_TIEU_DE,
                              thong_bao.TB_CHO_DUYET_NOI_DUNG.format(nhan_su=nhan_su.full_name, ten=ket_qua.document_name),
                              reverse('employees:document_review', args=[ket_qua.pk]))
        ghi_nhat_ky(nhan_su.user, 'UPDATE', 'Employee', nhan_su.pk,
                    'Cập nhật hồ sơ cá nhân' + (f'; tải giấy tờ "{ket_qua.document_name}"' if ket_qua else ''))
    return ket_qua


def tai_ban_moi_giay_to(giay_to, ngay_cap, ngay_het_han, file):
    """UC 2.2 – luồng 1.1.1 (Q15): "Tải bản mới" cập nhật CHÍNH bản ghi cũ, đưa về PENDING, xóa lý do từ chối cũ."""
    giay_to.issue_date = ngay_cap
    giay_to.expiry_date = ngay_het_han
    giay_to.file_url = file
    giay_to.status = DocumentStatus.PENDING
    giay_to.rejection_reason = ''
    giay_to.reviewed_by = None
    giay_to.reviewed_at = None
    giay_to.save()
    return giay_to


# ============================================================ UC 2.6 – Duyệt giấy tờ
def _kiem_tra_duoc_duyet(nguoi_duyet, giay_to):
    if not co_quyen_duyet(nguoi_duyet, giay_to.employee.user):
        raise KhongCoQuyen(thong_bao.KHONG_CO_QUYEN_HANH_DONG)


def duyet_giay_to(nguoi_duyet, giay_to):
    """UC 2.6 – bước 6: PENDING → APPROVED, lưu người duyệt, báo nhân viên, ghi nhật ký.

    Dùng `update()` có điều kiện `status=PENDING`: nếu hai người cùng bấm, chỉ người đến trước được
    xử lý (kết quả 0 dòng → báo "Yêu cầu đã được xử lý.").
    """
    _kiem_tra_duoc_duyet(nguoi_duyet, giay_to)
    with transaction.atomic():
        so_dong = EmployeeDocument.objects.filter(pk=giay_to.pk, status=DocumentStatus.PENDING).update(
            status=DocumentStatus.APPROVED, reviewed_by=nguoi_duyet, reviewed_at=timezone.now(), rejection_reason='')
        if not so_dong:
            raise LoiNghiepVu(thong_bao.YEU_CAU_DA_XU_LY)
        tao_thong_bao(giay_to.employee.user, NotificationType.PROFILE, thong_bao.TB_DA_DUYET_TIEU_DE,
                      thong_bao.TB_DA_DUYET_NOI_DUNG.format(ten=giay_to.document_name), reverse('employees:my_profile'))
        ghi_nhat_ky(nguoi_duyet, 'APPROVE', 'EmployeeDocument', giay_to.pk, f'Duyệt giấy tờ "{giay_to.document_name}"')


def tu_choi_giay_to(nguoi_duyet, giay_to, ly_do):
    """UC 2.6 – luồng 5.1.1: PENDING → REJECTED kèm lý do (bắt buộc), báo nhân viên tải lại (UC 2.2 luồng 1.1)."""
    ly_do = (ly_do or '').strip()
    if not ly_do:
        raise LoiNghiepVu(thong_bao.VUI_LONG_NHAP_LY_DO_TU_CHOI)          # luồng 5.2
    _kiem_tra_duoc_duyet(nguoi_duyet, giay_to)
    with transaction.atomic():
        so_dong = EmployeeDocument.objects.filter(pk=giay_to.pk, status=DocumentStatus.PENDING).update(
            status=DocumentStatus.REJECTED, rejection_reason=ly_do, reviewed_by=nguoi_duyet, reviewed_at=timezone.now())
        if not so_dong:
            raise LoiNghiepVu(thong_bao.YEU_CAU_DA_XU_LY)
        tao_thong_bao(giay_to.employee.user, NotificationType.PROFILE, thong_bao.TB_TU_CHOI_TIEU_DE,
                      thong_bao.TB_TU_CHOI_NOI_DUNG.format(ten=giay_to.document_name, ly_do=ly_do),
                      reverse('employees:my_profile_edit'))
        ghi_nhat_ky(nguoi_duyet, 'REJECT', 'EmployeeDocument', giay_to.pk,
                    f'Từ chối giấy tờ "{giay_to.document_name}": {ly_do}')


# ============================================================ UC 2.4 – Cảnh báo giấy tờ sắp hết hạn
def danh_sach_canh_bao(muc='', tu_khoa='', hom_nay=None):
    """UC 2.4 – bước 2–3: giấy tờ APPROVED sắp hết hạn (≤ 30 ngày) và giấy tờ đã hết hạn, kèm mức cảnh báo.

    Trả về list (giay_to, muc_canh_bao). `muc` lọc theo EXPIRING hoặc EXPIRED; `tu_khoa` lọc theo tên nhân sự.
    """
    hom_nay = hom_nay or date.today()
    han_cuoi = hom_nay + timedelta(days=settings.SO_NGAY_CANH_BAO)
    danh_sach = EmployeeDocument.objects.filter(
        Q(status=DocumentStatus.EXPIRED) | Q(status=DocumentStatus.APPROVED, expiry_date__isnull=False,
                                              expiry_date__lte=han_cuoi)
    ).select_related('employee').order_by('expiry_date')
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(employee__full_name__icontains=tu_khoa.strip()))
    ket_qua = []
    for giay_to in danh_sach:
        muc_hien_tai = muc_canh_bao(giay_to, hom_nay)
        if muc_hien_tai != MUC_CON_HAN and (not muc or muc == muc_hien_tai):
            ket_qua.append((giay_to, muc_hien_tai))
    return ket_qua


def nhac_nho_cap_nhat(nguoi_thuc_hien, giay_to, hom_nay=None):
    """UC 2.4 – bước 5: thông báo cho nhân viên sở hữu tải bản mới, ghi nhật ký REMIND."""
    tinh_trang = 'đã hết hạn' if muc_canh_bao(giay_to, hom_nay) == MUC_DA_HET_HAN else 'sắp hết hạn'
    with transaction.atomic():
        tao_thong_bao(giay_to.employee.user, NotificationType.PROFILE, thong_bao.TB_NHAC_NHO_TIEU_DE,
                      thong_bao.NHAC_NHO_GIAY_TO.format(ten=giay_to.document_name, tinh_trang=tinh_trang),
                      reverse('employees:my_profile_edit'))
        ghi_nhat_ky(nguoi_thuc_hien, 'REMIND', 'EmployeeDocument', giay_to.pk,
                    f'Nhắc cập nhật giấy tờ "{giay_to.document_name}" ({tinh_trang})')


# ============================================================ UC 2.5 – Onboarding
def tao_ho_so_nhan_su(nguoi_thuc_hien, du_lieu, ung_vien=None, hom_nay=None):
    """UC 2.5 – bước 5–6: tạo users + employees (+ quỹ phép nếu Full-time + ứng viên HIRED) TRONG MỘT GIAO DỊCH,
    rồi gửi email đặt mật khẩu và báo Super Admin nếu vị trí là Quản lý/Kế toán.

    Quản lý chỉ tạo tài khoản role EMPLOYEE (Q3); nâng quyền do Super Admin làm.
    `du_lieu` là dict đã kiểm tra từ form (email, full_name, phone, ... gồm cả employment_type và work_shift).
    """
    from accounts.services import gui_link_dat_mat_khau, tao_tai_khoan   # import trong hàm (§3.2)
    from leave.services import tao_quy_phep
    from recruitment.services import danh_dau_da_tuyen
    hom_nay = hom_nay or date.today()
    if ung_vien is not None and Employee.objects.filter(candidate=ung_vien).exists():
        raise LoiNghiepVu(thong_bao.UNG_VIEN_DA_TIEP_NHAN)               # luồng 1.2
    du_lieu = dict(du_lieu)
    email = du_lieu.pop('email')
    with transaction.atomic():
        tai_khoan = tao_tai_khoan(nguoi_thuc_hien, email, du_lieu['full_name'], UserRole.EMPLOYEE,
                                  gui_email=False, so_dien_thoai=du_lieu['phone'])
        nhan_su = Employee.objects.create(user=tai_khoan, candidate=ung_vien, status=EmployeeStatus.ONBOARDING, **du_lieu)
        if nhan_su.employment_type == EmploymentType.FULL_TIME:
            tao_quy_phep(nhan_su, hom_nay.year)
        if ung_vien is not None:
            danh_dau_da_tuyen(ung_vien, nguoi_thuc_hien)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'Employee', nhan_su.pk, f'Tạo hồ sơ nhân sự {nhan_su.code} – {nhan_su.full_name}')
    # Các việc dưới đây chạy SAU khi giao dịch đã lưu, để lỗi gửi email không làm mất hồ sơ vừa tạo
    gui_link_dat_mat_khau(tai_khoan)
    if nhan_su.position in (Position.MANAGER, Position.ACCOUNTANT):
        for super_admin in User.objects.filter(role=UserRole.SUPER_ADMIN, is_active=True):
            tao_thong_bao(super_admin, NotificationType.SYSTEM, thong_bao.TB_CAP_QUYEN_TIEU_DE,
                          thong_bao.TB_CAP_QUYEN_NOI_DUNG.format(nhan_su=nhan_su.full_name, vi_tri=nhan_su.get_position_display(),
                                                                 email=tai_khoan.email),
                          reverse('accounts:user_change_role', args=[tai_khoan.pk]))
    return nhan_su


def sua_ho_so_nhan_su(nguoi_thuc_hien, nhan_su, du_lieu):
    """UC 2.5 – luồng 1.1.1: Quản lý sửa hồ sơ. Không đổi Email và Loại hình (Loại hình chỉ đổi qua hợp đồng).

    Cập nhật employees, đồng bộ users.full_name/phone, ghi nhật ký. Đổi Ca làm việc có hiệu lực từ ngày hôm sau
    và không ảnh hưởng chấm công cũ vì mỗi bản ghi chấm công đã lưu sẵn giờ dự kiến của chính nó.
    """
    from accounts.services import dong_bo_tu_ho_so
    with transaction.atomic():
        for ten_truong, gia_tri in du_lieu.items():
            if ten_truong not in ('email', 'employment_type'):
                setattr(nhan_su, ten_truong, gia_tri)
        nhan_su.save()
        dong_bo_tu_ho_so(nhan_su.user, nhan_su.full_name, nhan_su.phone)
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'Employee', nhan_su.pk, f'Sửa hồ sơ nhân sự {nhan_su.code}')
    return nhan_su


# ============================================================ UC 2.3 – Xem hồ sơ cá nhân
def du_lieu_ho_so(nhan_su, hom_nay=None):
    """UC 2.3 – bước 2: gom dữ liệu của CHÍNH nhân sự: hợp đồng ACTIVE, giấy tờ (kèm mức cảnh báo), quỹ phép năm nay."""
    hom_nay = hom_nay or date.today()
    giay_to = [(g, muc_canh_bao(g, hom_nay)) for g in nhan_su.documents.order_by('-created_at')]
    quy_phep = nhan_su.leave_balances.filter(year=hom_nay.year).first()
    return {
        'hop_dong': nhan_su.contracts.filter(status='ACTIVE').first(),
        'giay_to': giay_to,
        'quy_phep': quy_phep,
        'giay_to_cho_duyet': [g for g, _ in giay_to if g.status == DocumentStatus.PENDING],
    }


# ============================================================ UC 9.2 – bước 2: giấy tờ (tác vụ hằng ngày)
def _tinh_trang_theo_ngay_con_lai(so_ngay):
    return 'đã hết hạn' if so_ngay < 0 else 'hết hạn hôm nay' if so_ngay == 0 else f'còn {so_ngay} ngày là hết hạn'


def het_han_giay_to(hom_nay):
    """UC 9.2 – bước 2 (phần 1): giấy tờ APPROVED có expiry_date trước hôm nay → EXPIRED. Trả về số giấy tờ đã chuyển.

    Chạy lại lần hai không còn giấy tờ APPROVED quá hạn nên trả về 0 (không xử lý trùng).
    """
    return EmployeeDocument.objects.filter(
        status=DocumentStatus.APPROVED, expiry_date__isnull=False, expiry_date__lt=hom_nay
    ).update(status=DocumentStatus.EXPIRED, updated_at=timezone.now())


def _da_nhac_hom_nay(nguoi_nhan, tieu_de, noi_dung):
    """Đã có đúng thông báo này gửi cho người nhận trong ngày chưa (tránh gửi trùng khi chạy lại, §9.2)."""
    from core.models import Notification
    return Notification.objects.filter(recipient=nguoi_nhan, title=tieu_de, message=noi_dung,
                                       created_at__date=date.today()).exists()


def nhac_han_giay_to(hom_nay):
    """UC 9.2 – bước 2 (phần 2): giấy tờ APPROVED còn đúng 30, 7 ngày hoặc hết hạn hôm nay (CAC_MOC_NHAC) → nhắc
    nhân sự sở hữu và mọi Quản lý đang hoạt động. Không nhắc người đã nghỉ việc. Trả về số thông báo đã gửi."""
    so_thong_bao = 0
    cac_moc = [hom_nay + timedelta(days=n) for n in settings.CAC_MOC_NHAC]
    cac_giay_to = EmployeeDocument.objects.filter(
        status=DocumentStatus.APPROVED, expiry_date__in=cac_moc,
        employee__status__in=[EmployeeStatus.ACTIVE, EmployeeStatus.ONBOARDING]).select_related('employee__user')
    quan_ly = list(User.objects.filter(role=UserRole.MANAGER, is_active=True))
    for giay_to in cac_giay_to:
        tinh_trang = _tinh_trang_theo_ngay_con_lai((giay_to.expiry_date - hom_nay).days)
        noi_dung_nv = thong_bao.NHAC_NHO_GIAY_TO.format(ten=giay_to.document_name, tinh_trang=tinh_trang)
        noi_dung_ql = thong_bao.TB_GIAY_TO_QL_NOI_DUNG.format(ten=giay_to.document_name, nhan_su=giay_to.employee.full_name,
                                                              tinh_trang=tinh_trang)
        gui_cho = [(giay_to.employee.user, thong_bao.TB_NHAC_NHO_TIEU_DE, noi_dung_nv, reverse('employees:my_profile_edit'))]
        gui_cho += [(q, thong_bao.TB_GIAY_TO_QL_TIEU_DE, noi_dung_ql, reverse('employees:document_alerts')) for q in quan_ly]
        for nguoi_nhan, tieu_de, noi_dung, link in gui_cho:
            if not _da_nhac_hom_nay(nguoi_nhan, tieu_de, noi_dung):
                tao_thong_bao(nguoi_nhan, NotificationType.PROFILE, tieu_de, noi_dung, link)
                so_thong_bao += 1
    return so_thong_bao
