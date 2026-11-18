"""Hàm nghiệp vụ của app accounts (UC 1): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ làm: kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
"""
from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

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


# ============================================================ UC 1.2 – Quên mật khẩu
def gui_link_dat_lai_mat_khau(request, email):
    """UC 1.2 – bước 4–5: email thuộc tài khoản đang hoạt động thì gửi đường dẫn đặt lại mật khẩu.

    Đường dẫn dùng `default_token_generator` của Django: hiệu lực theo PASSWORD_RESET_TIMEOUT (mặc định 3 ngày) và
    tự mất hiệu lực khi mật khẩu đã đổi (dùng một lần). Email không tồn tại hoặc tài khoản bị khóa thì không gửi gì,
    nhưng view vẫn hiện cùng một câu thông báo để người ngoài không dò được email nào có tài khoản.
    Trả về True nếu đã gửi thư.
    """
    tai_khoan = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if tai_khoan is None:
        return False
    duong_dan = request.build_absolute_uri(reverse('accounts:password_reset_confirm', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(tai_khoan.pk)),
        'token': default_token_generator.make_token(tai_khoan)}))
    send_mail(thong_bao.EMAIL_DAT_LAI_MK_TIEU_DE,
              thong_bao.EMAIL_DAT_LAI_MK_NOI_DUNG.format(ten=tai_khoan.full_name or tai_khoan.email, duong_dan=duong_dan),
              None, [tai_khoan.email])
    ghi_nhat_ky(tai_khoan, 'PASSWORD_RESET_REQUEST', 'User', tai_khoan.pk, f'Yêu cầu đặt lại mật khẩu: {tai_khoan.email}')
    return True


def tai_khoan_tu_duong_dan(uidb64, token):
    """UC 1.2 – bước 7 (luồng 6.1): trả về tài khoản nếu đường dẫn còn hiệu lực, ngược lại None."""
    try:
        tai_khoan = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not tai_khoan.is_active or not default_token_generator.check_token(tai_khoan, token):
        return None
    return tai_khoan


def dat_lai_mat_khau(tai_khoan, mat_khau_moi):
    """UC 1.2 – bước 7: lưu mật khẩu mới (đường dẫn cũ tự hết hiệu lực vì token gắn với mật khẩu), ghi nhật ký."""
    tai_khoan.set_password(mat_khau_moi)
    tai_khoan.save(update_fields=['password', 'updated_at'])
    ghi_nhat_ky(tai_khoan, 'PASSWORD_RESET', 'User', tai_khoan.pk, f'Đặt lại mật khẩu qua email: {tai_khoan.email}')


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
    danh_sach = User.objects.select_related('employee').order_by('email')   # kèm hồ sơ để hiện Chức danh
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


def tao_tai_khoan(nguoi_thuc_hien, email, ho_ten, vai_tro, mat_khau, so_dien_thoai=''):
    """UC 1.5 – luồng 3.1.1 (và UC 2.5 dùng lại): tạo users với mật khẩu ban đầu do người tạo nhập, ghi nhật ký.

    `create_user` tự mã hóa mật khẩu (set_password). Người dùng nhận mật khẩu từ người tạo và tự đổi ở UC 1.3.
    """
    if User.objects.filter(email__iexact=email).exists():
        raise LoiNghiepVu(thong_bao.EMAIL_DA_DUNG)
    with transaction.atomic():
        tai_khoan = User.objects.create_user(email, mat_khau, role=vai_tro, full_name=ho_ten, phone=so_dien_thoai)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'User', tai_khoan.pk, f'Tạo tài khoản {email} ({tai_khoan.get_role_display()})')
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
