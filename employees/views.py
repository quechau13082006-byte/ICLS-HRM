"""View dạng hàm của app employees (UC 2): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2)."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import co_quyen_duyet, role_required, tra_403
from core.services import KhongCoQuyen, LoiNghiepVu
from core.views import ALL_ROLES
from recruitment.models import Candidate, CandidateStatus
from . import services
from .forms import BoLocNhanSuForm, HoSoCaNhanForm, NhanSuForm, TuChoiGiayToForm
from .models import DocumentStatus, Employee, EmployeeDocument, EmployeeStatus

SA, QL = UserRole.SUPER_ADMIN, UserRole.MANAGER


def _nhan_su_cua_toi(request):
    """Hồ sơ nhân sự của chính người đang đăng nhập; Super Admin không có hồ sơ (Q1) nên trả None."""
    return request.user.employee if hasattr(request.user, 'employee') else None


# ============================================================ UC 2.1 – Danh sách nhân sự
@role_required(*ALL_ROLES)
def danh_sach(request):
    bo_loc = BoLocNhanSuForm(request.GET or None)
    tham_so = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    ds = services.danh_sach_nhan_su(request.user, tham_so.get('q', ''), tham_so.get('vi_tri', ''),
                                    tham_so.get('loai_hinh', ''), tham_so.get('trang_thai', ''))
    trang = Paginator(ds, settings.SO_DONG_MOI_TRANG).get_page(request.GET.get('page'))
    xem_day_du = request.user.role in (SA, QL)
    boi_canh = {'trang': trang, 'bo_loc': bo_loc, 'xem_day_du': xem_day_du,
                'tham_so_trang': request.GET.copy(),
                'khong_tim_thay': thong_bao.KHONG_TIM_THAY_NHAN_SU}
    if xem_day_du:
        boi_canh['dem'] = services.dem_nhan_su_theo_trang_thai()
        boi_canh['so_cho_duyet'] = services.giay_to_cho_duyet(request.user).count()
    if request.user.role == QL:
        boi_canh['so_canh_bao'] = len(services.danh_sach_canh_bao())
    boi_canh['tham_so_trang'].pop('page', None)
    return render(request, 'employees/danh_sach.html', boi_canh)


@role_required(SA, QL, thong_diep=thong_bao.KHONG_CO_QUYEN_HANH_DONG)     # UC 2.1 – luồng 5.1.1
def chi_tiet(request, pk):
    """UC 2.1 – bước 6: hồ sơ chi tiết (thông tin, giấy tờ, hợp đồng) cho Quản lý và Super Admin."""
    nhan_su = get_object_or_404(Employee.objects.select_related('user'), pk=pk)
    giay_to = [(g, services.muc_canh_bao(g)) for g in nhan_su.documents.order_by('-created_at')]
    # Nút Duyệt/Từ chối chỉ hiện nếu người xem có quyền duyệt giấy tờ của nhân sự này (Q2)
    duoc_duyet = co_quyen_duyet(request.user, nhan_su.user)
    return render(request, 'employees/chi_tiet.html', {
        'nhan_su': nhan_su, 'giay_to': giay_to, 'hop_dong': nhan_su.contracts.order_by('-start_date'),
        'duoc_duyet': duoc_duyet, 'so_giay_to': len(giay_to), 'quy_phep': nhan_su.leave_balances.order_by('-year').first(),
        'cho_duyet': [g for g, _ in giay_to if g.status == DocumentStatus.PENDING]})


@role_required(*ALL_ROLES)
def lien_he(request, pk):
    """UC 2.1 – bước 6: Kế toán/Nhân viên chỉ xem thông tin liên hệ cơ bản; hồ sơ của chính mình thì sang UC 2.3."""
    nhan_su = get_object_or_404(Employee.objects.select_related('user'), pk=pk)
    if nhan_su.user_id == request.user.pk:
        return redirect('employees:my_profile')
    if request.user.role not in (SA, QL) and nhan_su.status != EmployeeStatus.ACTIVE:
        return tra_403(request, thong_bao.KHONG_CO_QUYEN_HANH_DONG)
    return render(request, 'employees/lien_he.html', {'nhan_su': nhan_su})


# ============================================================ UC 2.3 – Hồ sơ của tôi
@role_required(*ALL_ROLES)
def ho_so_cua_toi(request):
    nhan_su = _nhan_su_cua_toi(request)
    if nhan_su is None:                                                            # luồng 1.1
        return render(request, 'employees/khong_co_ho_so.html', {'thong_diep': thong_bao.KHONG_CO_HO_SO})
    boi_canh = services.du_lieu_ho_so(nhan_su)
    boi_canh.update({'nhan_su': nhan_su, 'chua_cap_nhat': thong_bao.CHUA_CAP_NHAT})
    return render(request, 'employees/ho_so_cua_toi.html', boi_canh)


# ============================================================ UC 2.2 – Cập nhật hồ sơ cá nhân
@role_required(*ALL_ROLES)
def sua_ho_so_cua_toi(request):
    nhan_su = _nhan_su_cua_toi(request)
    if nhan_su is None:
        return render(request, 'employees/khong_co_ho_so.html', {'thong_diep': thong_bao.KHONG_CO_HO_SO})
    giay_to_tai_lai = None
    ma_tai_lai = request.POST.get('giay_to_id') or request.GET.get('tai_lai')
    if ma_tai_lai and str(ma_tai_lai).isdigit():
        # Chỉ được "Tải bản mới" cho giấy tờ của CHÍNH MÌNH và không đang chờ duyệt
        giay_to_tai_lai = nhan_su.documents.exclude(status=DocumentStatus.PENDING).filter(pk=ma_tai_lai).first()
    du_lieu_dau = {'phone': nhan_su.phone, 'address': nhan_su.address, 'bank_account': nhan_su.bank_account}
    if giay_to_tai_lai:
        du_lieu_dau.update({'giay_to_id': giay_to_tai_lai.pk, 'document_type': giay_to_tai_lai.document_type,
                            'document_name': giay_to_tai_lai.document_name})
    form = HoSoCaNhanForm(request.POST or None, request.FILES or None, initial=du_lieu_dau)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        giay_to = services.luu_ho_so_ca_nhan(nhan_su, d['phone'], d['address'], d['bank_account'],
                                             form.lay_giay_to(), giay_to_tai_lai)
        messages.success(request, thong_bao.CAP_NHAT_HO_SO_THANH_CONG if giay_to
                         else thong_bao.CAP_NHAT_HO_SO_KHONG_GIAY_TO)
        return redirect('employees:my_profile')
    return render(request, 'employees/sua_ho_so.html', {
        'form': form, 'nhan_su': nhan_su, 'giay_to_tai_lai': giay_to_tai_lai,
        'giay_to': [(g, services.muc_canh_bao(g)) for g in nhan_su.documents.order_by('-created_at')]})


# ============================================================ UC 2.5 – Onboarding (Quản lý)
@role_required(QL)
def them_nhan_su(request):
    """Thêm nhân sự mới thủ công, hoặc tiếp nhận ứng viên PASSED (?ung_vien=<id>, từ UC 8.3)."""
    ung_vien = None
    ma_ung_vien = request.GET.get('ung_vien') or request.POST.get('ung_vien')
    du_lieu_dau = {}
    if ma_ung_vien:
        ung_vien = get_object_or_404(Candidate, pk=ma_ung_vien)
        da_tiep_nhan = Employee.objects.filter(candidate=ung_vien).first()
        if da_tiep_nhan:                                                           # luồng 1.2: không tạo lần hai
            messages.error(request, thong_bao.UNG_VIEN_DA_TIEP_NHAN)
            return redirect('employees:employee_detail', pk=da_tiep_nhan.pk)       # kèm liên kết tới hồ sơ hiện có
        if ung_vien.status != CandidateStatus.PASSED:
            messages.error(request, thong_bao.CHI_TIEP_NHAN_UNG_VIEN_DAT)
            return redirect('employees:employee_list')
        du_lieu_dau = {'full_name': ung_vien.full_name, 'email': ung_vien.email, 'phone': ung_vien.phone,
                       'position': ung_vien.position, 'employment_type': ung_vien.employment_type}
    form = NhanSuForm(request.POST or None, initial=du_lieu_dau)
    if request.method == 'POST' and form.is_valid():
        try:
            nhan_su = services.tao_ho_so_nhan_su(request.user, form.cleaned_data, ung_vien)
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        else:
            messages.success(request, thong_bao.TAO_HO_SO_THANH_CONG)
            return redirect('employees:employee_detail', pk=nhan_su.pk)
    return render(request, 'employees/form_nhan_su.html', {'form': form, 'ung_vien': ung_vien, 'nhan_su': None})


@role_required(QL)
def sua_nhan_su(request, pk):
    nhan_su = get_object_or_404(Employee.objects.select_related('user'), pk=pk)
    form = NhanSuForm(request.POST or None, nhan_su=nhan_su, initial={
        'full_name': nhan_su.full_name, 'email': nhan_su.user.email, 'phone': nhan_su.phone, 'gender': nhan_su.gender,
        'date_of_birth': nhan_su.date_of_birth, 'id_card_number': nhan_su.id_card_number, 'address': nhan_su.address,
        'nationality': nhan_su.nationality, 'department': nhan_su.department, 'position': nhan_su.position,
        'employment_type': nhan_su.employment_type, 'work_shift': nhan_su.work_shift, 'join_date': nhan_su.join_date,
        'bank_account': nhan_su.bank_account})
    if request.method == 'POST' and form.is_valid():
        services.sua_ho_so_nhan_su(request.user, nhan_su, form.cleaned_data)
        messages.success(request, thong_bao.CAP_NHAT_HO_SO_NHAN_SU_THANH_CONG)
        return redirect('employees:employee_detail', pk=nhan_su.pk)
    return render(request, 'employees/form_nhan_su.html', {'form': form, 'ung_vien': None, 'nhan_su': nhan_su})


# ============================================================ UC 2.6 – Duyệt giấy tờ
@role_required(SA, QL)
def giay_to_cho_duyet(request):
    return render(request, 'employees/giay_to_cho_duyet.html',
                  {'giay_to': services.giay_to_cho_duyet(request.user)})


@role_required(SA, QL)
def duyet_giay_to(request, pk):
    giay_to = get_object_or_404(EmployeeDocument.objects.select_related('employee__user'), pk=pk)
    if not co_quyen_duyet(request.user, giay_to.employee.user):
        return tra_403(request, thong_bao.KHONG_CO_QUYEN_HANH_DONG)               # ngoài phạm vi duyệt (Q2)
    if giay_to.status != DocumentStatus.PENDING:                                   # luồng 3.1
        messages.info(request, thong_bao.YEU_CAU_DA_XU_LY)
        return redirect('employees:pending_documents')
    form = TuChoiGiayToForm(request.POST or None)
    if request.method == 'POST':
        try:
            if request.POST.get('hanh_dong') == 'duyet':
                services.duyet_giay_to(request.user, giay_to)
                messages.success(request, thong_bao.DA_DUYET_GIAY_TO)
            else:
                services.tu_choi_giay_to(request.user, giay_to, request.POST.get('ly_do'))
                messages.success(request, thong_bao.DA_TU_CHOI_GIAY_TO)
            return redirect('employees:pending_documents')
        except KhongCoQuyen as loi:
            return tra_403(request, str(loi))
        except LoiNghiepVu as loi:
            if str(loi) == thong_bao.YEU_CAU_DA_XU_LY:                             # người khác xử lý trước
                messages.info(request, str(loi))
                return redirect('employees:pending_documents')
            form.add_error('ly_do', str(loi))                                      # luồng 5.2: chưa nhập lý do
    return render(request, 'employees/duyet_giay_to.html', {'giay_to': giay_to, 'form': form})


# ============================================================ UC 2.4 – Cảnh báo giấy tờ
@role_required(QL)
def canh_bao_giay_to(request):
    muc = request.GET.get('muc', '')
    tu_khoa = request.GET.get('q', '').strip()
    return render(request, 'employees/canh_bao.html', {
        'canh_bao': services.danh_sach_canh_bao(muc, tu_khoa), 'muc': muc, 'q': tu_khoa,
        'khong_co_canh_bao': thong_bao.HIEN_KHONG_CO_CANH_BAO})


@role_required(QL)
@require_POST
def nhac_nho_giay_to(request, pk):
    giay_to = get_object_or_404(EmployeeDocument.objects.select_related('employee__user'), pk=pk)
    services.nhac_nho_cap_nhat(request.user, giay_to)
    messages.success(request, thong_bao.DA_NHAC_NHO)
    return redirect('employees:document_alerts')
