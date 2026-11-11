"""View dạng hàm của app contracts (UC 3): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2).

Phân quyền (§5): thêm, gia hạn, cập nhật file, thanh lý, theo dõi hết hạn chỉ Quản lý; xem danh sách và chi tiết:
Quản lý, Kế toán (xem tất cả), Nhân viên (chỉ của mình). Super Admin không thuộc phân hệ này.
"""
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required, tra_403
from core.services import LoiNghiepVu
from employees.models import EmploymentType
from . import services
from .forms import BoLocHopDongForm, FileScanForm, GiaHanForm, HopDongForm, ThanhLyForm
from .models import Contract, ContractStatus

QL, KT, NV = UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE


def _canh_bao_chon_ca(request, nhan_su):
    """Chuyển sang Full-time thì cần Ca làm việc (hồ sơ không có ca cho Part-time)."""
    if nhan_su.employment_type == EmploymentType.FULL_TIME and not nhan_su.work_shift:
        messages.warning(request, thong_bao.CAN_CHON_CA_SAU_DOI_LOAI_HINH)


# ============================================================ UC 3.1 – Danh sách hợp đồng
@role_required(QL, KT, NV)
def danh_sach(request):
    bo_loc = BoLocHopDongForm(request.GET or None)
    tham_so = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    ds = services.danh_sach_hop_dong(request.user, tham_so.get('q', ''), tham_so.get('loai_hinh', ''), tham_so.get('trang_thai', ''))
    trang = Paginator(ds, settings.SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    tham_so_trang = request.GET.copy()
    tham_so_trang.pop('page', None)
    return render(request, 'contracts/danh_sach.html', {
        'trang': trang, 'bo_loc': bo_loc, 'tham_so_trang': tham_so_trang, 'la_quan_ly': request.user.role == QL,
        'hom_nay': date.today()})


@role_required(QL)
def them_hop_dong(request):
    nhan_su_chon = request.GET.get('nhan_su', '')
    form = HopDongForm(request.POST or None, request.FILES or None,
                       initial={'nhan_su': nhan_su_chon} if nhan_su_chon.isdigit() else None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            hop_dong = services.them_hop_dong(request.user, d['nhan_su'], d['contract_number'], d['employment_type'],
                                              d['start_date'], d['end_date'], d['file_url'])
        except LoiNghiepVu as loi:
            # Lỗi nghiệp vụ gắn vào ô tương ứng (§3.4: dùng form.add_error)
            truong = 'nhan_su' if str(loi) in (thong_bao.HOP_DONG_DANG_HIEU_LUC, thong_bao.NHAN_SU_KHONG_DUOC_KY) else (
                'contract_number' if str(loi) == thong_bao.SO_HOP_DONG_DA_TON_TAI else None)
            form.add_error(truong, str(loi))
        else:
            messages.success(request, thong_bao.THEM_HOP_DONG_THANH_CONG)
            _canh_bao_chon_ca(request, d['nhan_su'])
            return redirect('contracts:contract_detail', pk=hop_dong.pk)
    return render(request, 'contracts/form_hop_dong.html', {'form': form, 'che_do': 'them'})


# ============================================================ UC 3.2 – Chi tiết hợp đồng
@role_required(QL, KT, NV, thong_diep=thong_bao.KHONG_XEM_HOP_DONG)
def chi_tiet(request, pk):
    hop_dong = get_object_or_404(Contract.objects.select_related('employee__user', 'previous_contract'), pk=pk)
    if not services.co_quyen_xem_hop_dong(request.user, hop_dong):
        return tra_403(request, thong_bao.KHONG_XEM_HOP_DONG)                    # luồng 1.1
    truoc, sau = services.lich_su_gia_han(hop_dong)
    con_lai = services.so_ngay_con_lai(hop_dong)
    sap_het_han = (hop_dong.status == ContractStatus.ACTIVE and con_lai is not None and con_lai <= settings.SO_NGAY_CANH_BAO)
    return render(request, 'contracts/chi_tiet.html', {
        'hop_dong': hop_dong, 'truoc': truoc, 'sau': sau, 'con_lai': con_lai, 'sap_het_han': sap_het_han,
        'la_quan_ly': request.user.role == QL, 'dang_hieu_luc': hop_dong.status == ContractStatus.ACTIVE})


@role_required(QL, KT, NV, thong_diep=thong_bao.KHONG_XEM_HOP_DONG)
def in_hop_dong(request, pk):
    """UC 3.2 (bổ sung): mẫu hợp đồng lao động tự điền từ hồ sơ, hợp đồng và cấu hình lương; bấm In / Lưu PDF.
    Cùng quyền với trang chi tiết: Quản lý, Kế toán xem mọi hợp đồng; Nhân viên chỉ hợp đồng của mình."""
    hop_dong = get_object_or_404(Contract.objects.select_related('employee__user', 'previous_contract'), pk=pk)
    if not services.co_quyen_xem_hop_dong(request.user, hop_dong):
        return tra_403(request, thong_bao.KHONG_XEM_HOP_DONG)
    return render(request, 'contracts/in_hop_dong.html', services.du_lieu_in_hop_dong(hop_dong))


# ============================================================ UC 3.3 – Gia hạn, cập nhật file
@role_required(QL)
def gia_han(request, pk):
    hop_dong_cu = get_object_or_404(Contract.objects.select_related('employee'), pk=pk)
    if hop_dong_cu.status != ContractStatus.ACTIVE:
        messages.error(request, thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
        return redirect('contracts:contract_detail', pk=pk)
    form = GiaHanForm(request.POST or None, request.FILES or None, hop_dong_cu=hop_dong_cu,
                      initial={'employment_type': hop_dong_cu.employment_type, 'start_date': hop_dong_cu.end_date})
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            moi = services.gia_han_hop_dong(request.user, hop_dong_cu, d['contract_number'], d['employment_type'],
                                            d['start_date'], d['end_date'], d['file_url'])
        except LoiNghiepVu as loi:
            form.add_error(None, str(loi))
        else:
            messages.success(request, thong_bao.GIA_HAN_THANH_CONG)
            _canh_bao_chon_ca(request, hop_dong_cu.employee)
            return redirect('contracts:contract_detail', pk=moi.pk)
    return render(request, 'contracts/form_gia_han.html', {'form': form, 'hop_dong': hop_dong_cu})


@role_required(QL)
def cap_nhat_file(request, pk):
    hop_dong = get_object_or_404(Contract.objects.select_related('employee'), pk=pk)
    form = FileScanForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.cap_nhat_file_scan(request.user, hop_dong, form.cleaned_data['file_url'])
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        else:
            messages.success(request, thong_bao.CAP_NHAT_FILE_THANH_CONG)
        return redirect('contracts:contract_detail', pk=pk)
    return render(request, 'contracts/form_file.html', {'form': form, 'hop_dong': hop_dong})


# ============================================================ UC 3.4 – Thanh lý
@role_required(QL)
def thanh_ly(request, pk):
    hop_dong = get_object_or_404(Contract.objects.select_related('employee'), pk=pk)
    if hop_dong.status != ContractStatus.ACTIVE:
        messages.error(request, thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
        return redirect('contracts:contract_detail', pk=pk)
    form = ThanhLyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            so_buoi = services.thanh_ly_hop_dong(request.user, hop_dong, d['ngay_thanh_ly'], d['ly_do'], d['hinh_thuc'])
        except LoiNghiepVu as loi:
            truong = {thong_bao.NGAY_THANH_LY_SAI: 'ngay_thanh_ly', thong_bao.NHAP_LY_DO_THANH_LY: 'ly_do'}.get(str(loi))
            form.add_error(truong, str(loi))
        else:
            messages.success(request, thong_bao.THANH_LY_THANH_CONG)
            if so_buoi:
                messages.info(request, f'Có {so_buoi} buổi dạy cần người thay (xử lý ở UC 6.4).')
            return redirect('contracts:contract_detail', pk=pk)
    return render(request, 'contracts/form_thanh_ly.html', {'form': form, 'hop_dong': hop_dong})


# ============================================================ UC 3.5 – Hợp đồng sắp hết hạn
@role_required(QL)
def sap_het_han(request):
    q = request.GET.get('q', '').strip()
    nhom = services.hop_dong_sap_het_han(q)
    return render(request, 'contracts/sap_het_han.html', {
        'qua_han': nhom[services.NHOM_QUA_HAN], 'duoi_7': nhom[services.NHOM_DUOI_7], 'tu_7_den_30': nhom[services.NHOM_7_30],
        'tong': sum(len(v) for v in nhom.values()), 'q': q,
        'khong_co': thong_bao.KHONG_CO_HOP_DONG_SAP_HET_HAN})
