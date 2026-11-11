"""View dạng hàm của app accounts (UC 1): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core import thong_bao
from core.services import LoiNghiepVu
from core.views import ALL_ROLES
from core.permissions import role_required
from . import services
from .forms import (DangNhapForm, DoiMatKhauForm, DoiVaiTroForm, MatKhauMoiForm, QuenMatKhauForm,
                    TaiKhoanCaNhanForm, ThemTaiKhoanForm)
from .models import User, UserRole


# ============================================================ UC 1.1 – Đăng nhập
def dang_nhap(request):
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    form = DangNhapForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ket_qua = services.dang_nhap(request, form.cleaned_data['email'], form.cleaned_data['mat_khau'])
        if ket_qua == services.DANG_NHAP_THANH_CONG:
            trang_tiep = request.POST.get('next') or request.GET.get('next')
            # Chỉ chuyển tới địa chỉ nội bộ, tránh bị lừa chuyển sang trang lạ (open redirect)
            if trang_tiep and url_has_allowed_host_and_scheme(trang_tiep, allowed_hosts={request.get_host()}):
                return redirect(trang_tiep)
            return redirect('dashboard:dashboard')          # bước 5: Dashboard theo vai trò (UC 9.1)
        form.add_error(None, thong_bao.TAI_KHOAN_BI_KHOA if ket_qua == services.DANG_NHAP_BI_KHOA
                       else thong_bao.DANG_NHAP_SAI_THONG_TIN)
    return render(request, 'accounts/dang_nhap.html', {'form': form, 'next': request.GET.get('next', '')})


# ============================================================ UC 1.6 – Đăng xuất
@require_POST
def dang_xuat(request):
    if request.user.is_authenticated:
        services.dang_xuat(request)
        messages.success(request, thong_bao.DA_DANG_XUAT)
    return redirect('accounts:login')           # luồng 1.1: phiên đã hết hạn thì cũng về trang Đăng nhập


# ============================================================ UC 1.2 – Quên mật khẩu
def quen_mat_khau(request):
    form = QuenMatKhauForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.yeu_cau_dat_lai_mat_khau(form.cleaned_data['email'])
        except LoiNghiepVu as loi:
            form.add_error('email', str(loi))                    # luồng 3.2: lỗi hiện ngay dưới ô Email
        else:
            messages.success(request, thong_bao.DA_GUI_HUONG_DAN_DAT_LAI)
            return redirect('accounts:login')
    return render(request, 'accounts/quen_mat_khau.html', {'form': form})


def dat_mat_khau(request, ma_nguoi_dung, token):
    """Trang mở từ link trong email. Dùng cho cả quên mật khẩu (1.2), tài khoản mới (1.5) và onboarding (2.5)."""
    nguoi_dung = services.tim_nguoi_dung_theo_link(ma_nguoi_dung, token)
    if nguoi_dung is None:                                       # luồng 6.1
        messages.error(request, thong_bao.LINK_HET_HAN)
        return redirect('accounts:forgot_password')
    form = MatKhauMoiForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        services.dat_lai_mat_khau(nguoi_dung, form.cleaned_data['mat_khau_moi'])
        messages.success(request, thong_bao.DAT_LAI_MAT_KHAU_THANH_CONG)
        return redirect('accounts:login')
    return render(request, 'accounts/dat_mat_khau.html', {'form': form})


# ============================================================ UC 1.3 – Đổi mật khẩu
@role_required(*ALL_ROLES)
def doi_mat_khau(request):
    form = DoiMatKhauForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        services.doi_mat_khau(request, request.user, form.cleaned_data['mat_khau_moi'])
        messages.success(request, thong_bao.DOI_MAT_KHAU_THANH_CONG)
        return redirect('accounts:my_account')
    return render(request, 'accounts/doi_mat_khau.html', {'form': form})


# ============================================================ UC 1.4 – Tài khoản của tôi
@role_required(*ALL_ROLES)
def tai_khoan_cua_toi(request):
    nguoi_dung = request.user
    form = TaiKhoanCaNhanForm(request.POST or None, request.FILES or None,
                              initial={'full_name': nguoi_dung.full_name, 'phone': nguoi_dung.phone})
    if request.method == 'POST' and form.is_valid():
        services.cap_nhat_tai_khoan(nguoi_dung, form.cleaned_data['full_name'], form.cleaned_data['phone'],
                                    form.cleaned_data['avatar'])
        messages.success(request, thong_bao.CAP_NHAT_TAI_KHOAN_THANH_CONG)
        return redirect('accounts:my_account')
    # Super Admin không có hồ sơ nhân sự nên không hiện Phòng ban, Vị trí
    nhan_su = nguoi_dung.employee if hasattr(nguoi_dung, 'employee') else None
    return render(request, 'accounts/tai_khoan.html', {'form': form, 'nhan_su': nhan_su})


# ============================================================ UC 1.5 – Quản lý tài khoản (chỉ Super Admin)
@role_required(UserRole.SUPER_ADMIN)
def ds_tai_khoan(request):
    vai_tro = request.GET.get('vai_tro', '')
    trang_thai = request.GET.get('trang_thai', '')
    tu_khoa = request.GET.get('q', '').strip()
    danh_sach = services.danh_sach_tai_khoan(vai_tro, trang_thai, tu_khoa)
    trang = Paginator(danh_sach, settings.SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    return render(request, 'accounts/ds_tai_khoan.html', {
        'trang': trang, 'vai_tro': vai_tro, 'trang_thai': trang_thai, 'q': tu_khoa, 'cac_vai_tro': UserRole.choices})


@role_required(UserRole.SUPER_ADMIN)
def them_tai_khoan(request):
    form = ThemTaiKhoanForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.tao_tai_khoan(request.user, form.cleaned_data['email'], form.cleaned_data['full_name'],
                                   form.cleaned_data['role'])
        except LoiNghiepVu as loi:
            form.add_error('email', str(loi))
        else:
            messages.success(request, thong_bao.DA_THEM_TAI_KHOAN)
            return redirect('accounts:user_list')
    return render(request, 'accounts/them_tai_khoan.html', {'form': form})


@role_required(UserRole.SUPER_ADMIN)
def doi_vai_tro(request, pk):
    """Trang xác nhận đổi vai trò (bước 4): hiện kèm chức danh trong hồ sơ nhân sự để đối chiếu.

    Thông báo "Yêu cầu cấp quyền" của UC 2.5 trỏ thẳng tới trang này (luồng 3.2).
    """
    tai_khoan = get_object_or_404(User, pk=pk)
    nhan_su = tai_khoan.employee if hasattr(tai_khoan, 'employee') else None
    form = DoiVaiTroForm(request.POST or None, initial={'role': tai_khoan.role})
    if request.method == 'POST' and form.is_valid():
        try:
            services.doi_vai_tro(request.user, tai_khoan, form.cleaned_data['role'])
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        else:
            messages.success(request, thong_bao.DA_DOI_VAI_TRO)
            return redirect('accounts:user_list')
    return render(request, 'accounts/doi_vai_tro.html', {'form': form, 'tai_khoan': tai_khoan, 'nhan_su': nhan_su})


@role_required(UserRole.SUPER_ADMIN)
@require_POST
def khoa_mo_khoa(request, pk):
    tai_khoan = get_object_or_404(User, pk=pk)
    try:
        if tai_khoan.is_active:
            services.khoa_tai_khoan(tai_khoan, request.user)
            messages.success(request, thong_bao.DA_KHOA_TAI_KHOAN)
        else:
            services.mo_khoa_tai_khoan(tai_khoan, request.user)
            messages.success(request, thong_bao.DA_MO_KHOA_TAI_KHOAN)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    return redirect('accounts:user_list')
