"""Hàm nghiệp vụ của app accounts (UC 1): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ làm: kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
"""
from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from core import thong_bao
from core.models import NotificationType
from core.services import LoiNghiepVu, ghi_nhat_ky, tao_thong_bao
from .models import User

# Kết quả của dang_nhap (view dựa vào đây để chọn câu thông báo)
DANG_NHAP_THANH_CONG = 'THANH_CONG'
DANG_NHAP_SAI_THONG_TIN = 'SAI_THONG_TIN'
DANG_NHAP_BI_KHOA = 'BI_KHOA'


# ============================================================ UC 1.1 / 1.6 – Đăng nhập, Đăng xuất
def dang_nhap(request, email, mat_khau):
    """UC 1.1 – bước 4–5: tìm tài khoản theo email, kiểm tra mật khẩu và is_active, tạo session, ghi nhật ký.

    Không dùng `authenticate()` có sẵn vì nó trả None cho cả "sai mật khẩu" lẫn "bị khóa",
    trong khi §10 yêu cầu hai câu thông báo khác nhau (luồng 3.2 và 3.3).
    """
    tai_khoan = User.objects.filter(email__iexact=email.strip()).first()
    if tai_khoan is None or not tai_khoan.check_password(mat_khau):
        # Luồng 3.2: email không tồn tại hoặc sai mật khẩu → cùng một thông báo, không tiết lộ email có thật hay không
        ghi_nhat_ky(None, 'LOGIN_FAILED', 'User', tai_khoan.pk if tai_khoan else None,
                    f'Đăng nhập thất bại: {email}')
        return DANG_NHAP_SAI_THONG_TIN
    if not tai_khoan.is_active:
        return DANG_NHAP_BI_KHOA                                    # luồng 3.3
    login(request, tai_khoan, backend='django.contrib.auth.backends.ModelBackend')   # tạo session
    ghi_nhat_ky(tai_khoan, 'LOGIN', 'User', tai_khoan.pk, f'Đăng nhập: {tai_khoan.email}')
    return DANG_NHAP_THANH_CONG


def dang_xuat(request):
    """UC 1.6 – bước 2: ghi nhật ký LOGOUT rồi hủy session (logout() xóa session và cookie phiên)."""
    nguoi_dung = request.user
    ghi_nhat_ky(nguoi_dung, 'LOGOUT', 'User', nguoi_dung.pk, f'Đăng xuất: {nguoi_dung.email}')
    logout(request)


# ============================================================ UC 1.2 – Quên mật khẩu / đặt mật khẩu
def tao_link_dat_mat_khau(nguoi_dung):
    """Dựng đường dẫn đặt mật khẩu: mã người dùng (mã hóa base64) + token chống giả mạo.

    Token do `default_token_generator` sinh ra, phụ thuộc vào mật khẩu hiện tại của người dùng và thời điểm
    sinh, nên: (1) hết hạn sau PASSWORD_RESET_TIMEOUT = 24 giờ, (2) đặt mật khẩu xong thì link cũ vô hiệu.
    """
    ma_nguoi_dung = urlsafe_base64_encode(force_bytes(nguoi_dung.pk))
    token = default_token_generator.make_token(nguoi_dung)
    return settings.DIA_CHI_WEB + reverse('accounts:dat_mat_khau', args=[ma_nguoi_dung, token])


def gui_link_dat_mat_khau(nguoi_dung):
    """Dùng chung cho UC 1.2, 1.5, 2.5: gửi email chứa đường dẫn đặt mật khẩu (demo: in ra terminal)."""
    link = tao_link_dat_mat_khau(nguoi_dung)
    send_mail(thong_bao.EMAIL_DAT_MAT_KHAU_TIEU_DE,
              thong_bao.EMAIL_DAT_MAT_KHAU_NOI_DUNG.format(ho_ten=nguoi_dung.full_name or nguoi_dung.email, link=link),
              None, [nguoi_dung.email])
    return link


def yeu_cau_dat_lai_mat_khau(email):
    """UC 1.2 – bước 4–5: kiểm tra email có trong bảng users rồi gửi link. Không có → LoiNghiepVu (luồng 3.2)."""
    nguoi_dung = User.objects.filter(email__iexact=email.strip()).first()
    if nguoi_dung is None:
        raise LoiNghiepVu(thong_bao.EMAIL_KHONG_TON_TAI)
    gui_link_dat_mat_khau(nguoi_dung)
    ghi_nhat_ky(nguoi_dung, 'REMIND', 'User', nguoi_dung.pk, 'Gửi link đặt lại mật khẩu')
    return nguoi_dung


def tim_nguoi_dung_theo_link(ma_nguoi_dung, token):
    """UC 1.2 – bước 7 (phần kiểm tra link): trả về người dùng nếu link còn hiệu lực, ngược lại trả None."""
    try:
        nguoi_dung = User.objects.get(pk=force_str(urlsafe_base64_decode(ma_nguoi_dung)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if default_token_generator.check_token(nguoi_dung, token):
        return nguoi_dung
    return None


def dat_lai_mat_khau(nguoi_dung, mat_khau_moi):
    """UC 1.2 – bước 7: lưu mật khẩu mới (set_password tự mã hóa), ghi nhật ký. Link cũ tự vô hiệu."""
    nguoi_dung.set_password(mat_khau_moi)
    nguoi_dung.save(update_fields=['password', 'updated_at'])
    ghi_nhat_ky(nguoi_dung, 'UPDATE', 'User', nguoi_dung.pk, 'Đặt lại mật khẩu qua đường dẫn')


# ============================================================ UC 1.3 – Đổi mật khẩu
def doi_mat_khau(request, nguoi_dung, mat_khau_moi):
    """UC 1.3 – bước 5: lưu mật khẩu mới, GIỮ phiên đăng nhập hiện tại, ghi nhật ký.

    Đổi mật khẩu làm session cũ mất hiệu lực; `update_session_auth_hash` cập nhật session để người dùng
    không bị đăng xuất.
    """
    nguoi_dung.set_password(mat_khau_moi)
    nguoi_dung.save(update_fields=['password', 'updated_at'])
    update_session_auth_hash(request, nguoi_dung)
    ghi_nhat_ky(nguoi_dung, 'UPDATE', 'User', nguoi_dung.pk, 'Đổi mật khẩu')


# ============================================================ UC 1.4 – Tài khoản cá nhân
def cap_nhat_tai_khoan(nguoi_dung, ho_ten, so_dien_thoai, anh_dai_dien=None):
    """UC 1.4 – bước 5: lưu users; nếu có hồ sơ nhân sự thì đồng bộ employees, TRONG MỘT GIAO DỊCH.

    `transaction.atomic`: hoặc cả hai bảng cùng được lưu, hoặc không bảng nào (tránh lệch dữ liệu).
    """
    with transaction.atomic():
        nguoi_dung.full_name = ho_ten
        nguoi_dung.phone = so_dien_thoai
        if anh_dai_dien:
            nguoi_dung.avatar = anh_dai_dien
        nguoi_dung.save()
        if hasattr(nguoi_dung, 'employee'):          # Super Admin không có hồ sơ (Q1)
            from employees.services import dong_bo_ho_ten_sdt   # import trong hàm (§3.2 quy tắc 3)
            dong_bo_ho_ten_sdt(nguoi_dung.employee, ho_ten, so_dien_thoai)
        ghi_nhat_ky(nguoi_dung, 'UPDATE', 'User', nguoi_dung.pk, 'Cập nhật tài khoản cá nhân')


# ============================================================ UC 1.5 – Quản lý tài khoản (Super Admin)
def danh_sach_tai_khoan(vai_tro='', trang_thai='', tu_khoa=''):
    """UC 1.5 – bước 2: danh sách tài khoản kèm bộ lọc Vai trò, Trạng thái, ô tìm Email/Họ tên."""
    danh_sach = User.objects.all().order_by('email')
    if vai_tro:
        danh_sach = danh_sach.filter(role=vai_tro)
    if trang_thai == 'ACTIVE':
        danh_sach = danh_sach.filter(is_active=True)
    elif trang_thai == 'LOCKED':
        danh_sach = danh_sach.filter(is_active=False)
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(email__icontains=tu_khoa) | Q(full_name__icontains=tu_khoa))
    return danh_sach


def _chan_tu_tac_dong(nguoi_thuc_hien, tai_khoan):
    """Luồng 5.1: không cho Super Admin tự khóa hoặc tự đổi quyền chính mình."""
    if nguoi_thuc_hien is not None and nguoi_thuc_hien.pk == tai_khoan.pk:
        raise LoiNghiepVu(thong_bao.KHONG_TU_KHOA)


def doi_vai_tro(nguoi_thuc_hien, tai_khoan, vai_tro_moi):
    """UC 1.5 – bước 6: cập nhật users.role, ghi nhật ký UPDATE, báo cho người được đổi."""
    _chan_tu_tac_dong(nguoi_thuc_hien, tai_khoan)
    vai_tro_cu = tai_khoan.get_role_display()
    with transaction.atomic():
        tai_khoan.role = vai_tro_moi
        tai_khoan.save(update_fields=['role', 'updated_at'])
        tai_khoan.refresh_from_db()
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'User', tai_khoan.pk,
                    f'Đổi vai trò {tai_khoan.email}: {vai_tro_cu} → {tai_khoan.get_role_display()}')
        tao_thong_bao(tai_khoan, NotificationType.SYSTEM, thong_bao.TB_DOI_VAI_TRO_TIEU_DE,
                      thong_bao.TB_DOI_VAI_TRO_NOI_DUNG.format(cu=vai_tro_cu, moi=tai_khoan.get_role_display()))


def khoa_tai_khoan(tai_khoan, nguoi_thuc_hien=None):
    """UC 1.5 – bước 6 (khóa). Cũng được UC 3.4 gọi lại khi thanh lý hợp đồng (khi đó nguoi_thuc_hien có thể là QL).

    Chuyển users.is_active True → False; kiểm tra trạng thái hiện tại trước khi chuyển (§8).
    Hiệu lực ngay: lần gửi yêu cầu tiếp theo, Django không còn nhận session của tài khoản bị khóa.
    """
    _chan_tu_tac_dong(nguoi_thuc_hien, tai_khoan)
    if not tai_khoan.is_active:
        raise LoiNghiepVu(thong_bao.TAI_KHOAN_DA_KHOA_TRUOC_DO)
    with transaction.atomic():
        tai_khoan.is_active = False
        tai_khoan.save(update_fields=['is_active', 'updated_at'])
        ghi_nhat_ky(nguoi_thuc_hien, 'LOCK', 'User', tai_khoan.pk, f'Khóa tài khoản {tai_khoan.email}')
        tao_thong_bao(tai_khoan, NotificationType.SYSTEM, thong_bao.TB_KHOA_TIEU_DE, thong_bao.TAI_KHOAN_BI_KHOA)


def mo_khoa_tai_khoan(tai_khoan, nguoi_thuc_hien):
    """UC 1.5 – bước 6 (mở khóa): users.is_active False → True."""
    _chan_tu_tac_dong(nguoi_thuc_hien, tai_khoan)
    if tai_khoan.is_active:
        raise LoiNghiepVu(thong_bao.TAI_KHOAN_DANG_MO)
    with transaction.atomic():
        tai_khoan.is_active = True
        tai_khoan.save(update_fields=['is_active', 'updated_at'])
        ghi_nhat_ky(nguoi_thuc_hien, 'UNLOCK', 'User', tai_khoan.pk, f'Mở khóa tài khoản {tai_khoan.email}')
        tao_thong_bao(tai_khoan, NotificationType.SYSTEM, thong_bao.TB_MO_KHOA_TIEU_DE,
                      thong_bao.TB_MO_KHOA_NOI_DUNG)


def tao_tai_khoan(nguoi_thuc_hien, email, ho_ten, vai_tro, gui_email=True, so_dien_thoai=''):
    """UC 1.5 – luồng 3.1.1 (và UC 2.5 dùng lại): tạo users CHƯA có mật khẩu, gửi link đặt mật khẩu, ghi nhật ký.

    `create_user` không truyền mật khẩu → `set_unusable_password()` (không ai đăng nhập được cho tới khi tự đặt).
    `gui_email=False` để UC 2.5 tự gửi email SAU khi cả giao dịch tạo hồ sơ đã lưu thành công.
    """
    if User.objects.filter(email__iexact=email).exists():
        raise LoiNghiepVu(thong_bao.EMAIL_DA_DUNG)
    with transaction.atomic():
        tai_khoan = User.objects.create_user(email, role=vai_tro, full_name=ho_ten, phone=so_dien_thoai)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'User', tai_khoan.pk, f'Tạo tài khoản {email} ({tai_khoan.get_role_display()})')
    if gui_email:
        gui_link_dat_mat_khau(tai_khoan)
    return tai_khoan


def dong_bo_tu_ho_so(tai_khoan, ho_ten=None, so_dien_thoai=None):
    """UC 2.2, 2.5: khi hồ sơ nhân sự đổi Họ tên/SĐT thì đồng bộ sang bảng users.

    Hàm của app `accounts` (app sở hữu bảng users) để app `employees` gọi sang, đúng §3.2.
    """
    if ho_ten is not None:
        tai_khoan.full_name = ho_ten
    if so_dien_thoai is not None:
        tai_khoan.phone = so_dien_thoai
    tai_khoan.save(update_fields=['full_name', 'phone', 'updated_at'])
