"""View dạng hàm của app recruitment (UC 8): kiểm tra quyền → nhận form → gọi service → hiển thị (§0 luật 2).

Cả 8.1, 8.2, 8.3 chỉ dành cho Quản lý (§5). Bảng ứng viên có "ngăn hồ sơ" bên phải (theo Figma): mở bằng
`?chon=<id ứng viên>`; mọi thao tác trong ngăn là POST rồi quay lại đúng ứng viên đó.
"""
from datetime import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required
from core.services import LoiNghiepVu
from employees.models import Employee, EmploymentType, Position
from . import services
from .forms import (BoLocUngVienForm, DanhGiaVongForm, DotTuyenDungForm, LichVongForm, SoTuyenForm, UngVienForm)
from .models import (CampaignStatus, Candidate, CandidateStatus, RecruitmentCampaign, RecruitmentRound,
                     RecruitmentRoundStatus, RecruitmentRoundType)

QL = UserRole.MANAGER

# Các cột của bảng (theo Figma): (khóa, tiêu đề, màu thanh bên trái, các trạng thái ứng viên nằm trong cột)
CAC_COT = [
    ('so_tuyen', 'Sơ tuyển', '#004c08', (CandidateStatus.NEW, CandidateStatus.SCREENING)),
    ('phong_van', 'Phỏng vấn', '#004c08', (CandidateStatus.INTERVIEWING,)),
    ('day_thu', 'Dạy thử', '#004c08', (CandidateStatus.TEACHING_TRIAL,)),
    ('cho_tiep_nhan', 'Đạt – chờ tiếp nhận', '#f08812', (CandidateStatus.PASSED,)),
    ('trung_tuyen', 'Đã tiếp nhận', '#004c08', (CandidateStatus.HIRED,)),
    ('khong_dat', 'Không đạt', '#ee8c7f', (CandidateStatus.REJECTED,)),
]


def _the_ung_vien(ung_vien, bay_gio):
    """Dòng chữ nhỏ ở đáy thẻ ứng viên trên bảng (trạng thái việc cần làm tiếp)."""
    vong_cho = next((v for v in ung_vien.recruitment_rounds.all() if v.status == RecruitmentRoundStatus.SCHEDULED), None)
    nhan, loai = '', 'muted'
    if ung_vien.status == CandidateStatus.NEW:
        nhan, loai = 'Hồ sơ mới', 'new'
    elif ung_vien.status == CandidateStatus.SCREENING:
        nhan = 'Chờ xếp lịch phỏng vấn'
    elif ung_vien.status == CandidateStatus.INTERVIEWING and vong_cho:
        hom_nay = vong_cho.scheduled_at.date() == bay_gio.date()
        nhan = ('Hôm nay · ' if hom_nay else vong_cho.scheduled_at.strftime('%d/%m · ')) + vong_cho.scheduled_at.strftime('%H:%M')
        loai = 'new' if hom_nay else 'muted'
        if vong_cho.scheduled_at <= bay_gio:
            nhan, loai = 'Cần đánh giá · ' + vong_cho.scheduled_at.strftime('%H:%M'), 'new'
    elif ung_vien.status == CandidateStatus.TEACHING_TRIAL:
        nhan = (f'Demo {vong_cho.scheduled_at:%d/%m · %H:%M}' if vong_cho else 'Chờ xếp lịch Demo')
        if vong_cho and vong_cho.scheduled_at <= bay_gio:
            nhan, loai = 'Cần đánh giá Demo · ' + vong_cho.scheduled_at.strftime('%H:%M'), 'new'

    elif ung_vien.status == CandidateStatus.PASSED:
        nhan, loai = 'Chờ tiếp nhận (Onboarding)', 'new'
    elif ung_vien.status == CandidateStatus.HIRED:
        nhan = 'Đã tiếp nhận'
    elif ung_vien.status == CandidateStatus.REJECTED:
        nhan = 'Không đạt'
    return {'ung_vien': ung_vien, 'nhan': nhan, 'loai': loai}


def _tham_so_loc(request):
    """Giữ nguyên bộ lọc (tìm kiếm, vị trí, đợt) khi mở/đóng ngăn hồ sơ; bỏ tham số `chon`."""
    tham_so = request.GET.copy()
    tham_so.pop('chon', None)
    return tham_so.urlencode()


def _ve_bang(request, chon=None, bay_gio=None, **form_co_loi):
    """Vẽ bảng ứng viên (và ngăn hồ sơ nếu có `chon`). `form_co_loi`: form vừa nhập sai, để hiện lỗi lại trong ngăn."""
    bay_gio = bay_gio or datetime.now()
    du_lieu_loc = request.GET.copy()
    chi_can_danh_gia = request.GET.get('can_danh_gia') == '1'
    if chi_can_danh_gia:
        du_lieu_loc['dot'] = ''          # vòng cần đánh giá có thể thuộc bất kỳ đợt nào
    elif 'dot' not in du_lieu_loc:
        # Mới bấm vào Recruitment (chưa chọn đợt): hiện đợt đang mở gần nhất. Chọn "Tất cả đợt" thì gửi dot= rỗng.
        mac_dinh = services.dot_mac_dinh()
        if mac_dinh is not None:
            du_lieu_loc['dot'] = str(mac_dinh.pk)
    bo_loc = BoLocUngVienForm(du_lieu_loc)
    tham_so = bo_loc.cleaned_data if bo_loc.is_valid() else {}
    dot = tham_so.get('dot')
    danh_sach = services.bang_ung_vien(dot, tham_so.get('q', ''), tham_so.get('vi_tri', ''))
    if chi_can_danh_gia:
        # UC 8.3 – bước 1–2: chỉ ứng viên có vòng phỏng vấn / demo đã tới giờ mà chưa đánh giá
        danh_sach = danh_sach.filter(pk__in=services.vong_can_danh_gia(bay_gio).values('candidate_id'))
    danh_sach = list(danh_sach)
    cot = []
    for khoa, tieu_de, mau, trang_thai in CAC_COT:
        the = [_the_ung_vien(u, bay_gio) for u in danh_sach if u.status in trang_thai]
        cot.append({'khoa': khoa, 'tieu_de': tieu_de, 'mau': mau, 'the': the})
    boi_canh = {
        'bo_loc': bo_loc, 'dot': dot, 'cot': cot, 'tong': len(danh_sach),
        'so_vi_tri': len({u.position for u in danh_sach}),
        'cac_dot': RecruitmentCampaign.objects.order_by('-start_date'),
        'tham_so_dot': _tham_so_loc(request), 'chi_can_danh_gia': chi_can_danh_gia,
        'so_vong_can_danh_gia': services.vong_can_danh_gia(bay_gio).count()}
    if chon is not None:
        boi_canh.update(_ngan_ho_so(chon, bay_gio, form_co_loi))
    return render(request, 'recruitment/bang.html', boi_canh)


def _ngan_ho_so(ung_vien, bay_gio, form_co_loi):
    """Dữ liệu cho ngăn hồ sơ ứng viên: tiến trình các vòng, các form còn dùng được theo trạng thái."""
    vong = list(ung_vien.recruitment_rounds.select_related('interviewer').order_by('scheduled_at'))
    vong_pv = next((v for v in vong if v.round_type == RecruitmentRoundType.INTERVIEW
                    and v.status == RecruitmentRoundStatus.SCHEDULED), None)
    vong_demo = next((v for v in vong if v.round_type == RecruitmentRoundType.DEMO
                      and v.status == RecruitmentRoundStatus.SCHEDULED), None)
    vong_dang_cho = vong_pv or vong_demo
    sua_duoc_so_tuyen = ung_vien.status in (CandidateStatus.NEW, CandidateStatus.SCREENING) or (
        ung_vien.status == CandidateStatus.REJECTED and not vong)
    ket_qua = {
        'ung_vien': ung_vien, 'cac_vong': vong, 'vong_dang_cho': vong_dang_cho,
        'den_gio': bool(vong_dang_cho and vong_dang_cho.scheduled_at <= bay_gio),
        'sua_duoc_so_tuyen': sua_duoc_so_tuyen,
        'duoc_xep_demo': (ung_vien.status == CandidateStatus.TEACHING_TRIAL and not vong_demo
                          and ung_vien.position == Position.TEACHER and ung_vien.employment_type == EmploymentType.FULL_TIME),
        'nhan_su': Employee.objects.filter(candidate=ung_vien).first(),
        'form_so_tuyen': form_co_loi.get('form_so_tuyen') or SoTuyenForm(
            initial={'ket_qua': 'khong_dat' if ung_vien.status == CandidateStatus.REJECTED else 'dat',
                     'ghi_chu': ung_vien.screening_note}),
        'form_lich': form_co_loi.get('form_lich') or LichVongForm(),
        'form_danh_gia': form_co_loi.get('form_danh_gia') or DanhGiaVongForm(),
        'loi_dang_mo': next(iter(form_co_loi), ''),
        'schedule_interview_url': reverse('recruitment:schedule_interview', args=[ung_vien.pk]),
        'schedule_demo_url': reverse('recruitment:schedule_demo', args=[ung_vien.pk]),
    }
    return ket_qua


def _quay_lai(ung_vien):
    """Về bảng ứng viên, mở đúng đợt của ứng viên và ngăn hồ sơ của họ."""
    return redirect(f"{reverse('recruitment:board')}?dot={ung_vien.campaign_id}&chon={ung_vien.pk}")


# ============================================================ UC 8.1 – Bảng ứng viên, đợt tuyển dụng
@role_required(QL)
def bang(request):
    chon = None
    if request.GET.get('chon', '').isdigit():
        chon = get_object_or_404(Candidate, pk=request.GET['chon'])
    return _ve_bang(request, chon)


@role_required(QL)
def them_dot(request):
    form = DotTuyenDungForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        dot = services.tao_dot_tuyen_dung(request.user, d['campaign_name'], d['start_date'], d['end_date'])
        messages.success(request, thong_bao.TAO_DOT_THANH_CONG)
        return redirect(f"{reverse('recruitment:board')}?dot={dot.pk}")
    return render(request, 'recruitment/form_dot.html', {'form': form})


@role_required(QL)
@require_POST
def dong_dot(request, pk):
    dot = get_object_or_404(RecruitmentCampaign, pk=pk)
    try:
        services.dong_dot_tuyen_dung(request.user, dot)
        messages.success(request, thong_bao.DONG_DOT_THANH_CONG)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    return redirect(f"{reverse('recruitment:board')}?dot={dot.pk}")


@role_required(QL)
def them_ung_vien(request):
    """UC 8.1 – bước 3–4: Quản lý chọn đợt (chỉ đợt đang mở; mặc định đợt đang xem trên bảng hoặc đợt mặc định)."""
    ma_dot = request.POST.get('dot') or request.GET.get('dot') or ''
    dot = get_object_or_404(RecruitmentCampaign, pk=ma_dot) if ma_dot.isdigit() else None
    if dot is not None and dot.status != CampaignStatus.OPEN:
        messages.error(request, thong_bao.DOT_DA_DONG)                            # luồng 3.1
        return redirect(f"{reverse('recruitment:board')}?dot={dot.pk}")
    if dot is None:
        mac_dinh = services.dot_mac_dinh()
        dot = mac_dinh if mac_dinh is not None and mac_dinh.status == CampaignStatus.OPEN else None
    form = UngVienForm(request.POST or None, request.FILES or None, initial={'dot': dot.pk if dot else None})
    if request.method == 'POST' and form.is_valid():
        dot = form.cleaned_data['dot']
        du_lieu = {k: v for k, v in form.cleaned_data.items() if k != 'dot'}
        try:
            ung_vien = services.them_ung_vien(request.user, dot, du_lieu)
        except LoiNghiepVu as loi:
            if dot is not None and dot.status != CampaignStatus.OPEN:
                messages.error(request, str(loi))
                return redirect(f"{reverse('recruitment:board')}?dot={dot.pk}")
            form.add_error('email', str(loi))
        else:
            messages.success(request, thong_bao.THEM_UNG_VIEN_THANH_CONG)
            return _quay_lai(ung_vien)
    return render(request, 'recruitment/form_ung_vien.html', {
        'form': form, 'co_dot_mo': RecruitmentCampaign.objects.filter(status=CampaignStatus.OPEN).exists()})


@role_required(QL)
@require_POST
def so_tuyen(request, pk):
    ung_vien = get_object_or_404(Candidate, pk=pk)
    form = SoTuyenForm(request.POST)
    if form.is_valid():
        try:
            services.danh_gia_so_tuyen(request.user, ung_vien, form.cleaned_data['ket_qua'] == 'dat', form.cleaned_data['ghi_chu'])
            messages.success(request, thong_bao.LUU_SO_TUYEN_THANH_CONG)
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        return _quay_lai(ung_vien)
    return _ve_bang(request, ung_vien, form_so_tuyen=form)


@role_required(QL)
@require_POST
def khong_dat(request, pk):
    ung_vien = get_object_or_404(Candidate, pk=pk)
    try:
        services.loai_ung_vien(request.user, ung_vien, request.POST.get('ly_do', '').strip())
        messages.success(request, thong_bao.DA_DANH_DAU_KHONG_DAT)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    return _quay_lai(ung_vien)


# ============================================================ UC 8.2 – Lịch phỏng vấn / Demo
@role_required(QL)
@require_POST
def xep_lich(request, pk, loai):
    """UC 8.2: một view cho cả hai nút "Xác nhận lịch phỏng vấn" và "Xác nhận lịch Demo" (URL truyền sẵn `loai`)."""
    ung_vien = get_object_or_404(Candidate, pk=pk)
    form = LichVongForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.xep_lich_vong(request.user, ung_vien, loai, d['scheduled_at'], d['location'], d['interviewer'])
            messages.success(request, thong_bao.DA_XEP_LICH_PHONG_VAN if loai == RecruitmentRoundType.INTERVIEW
                             else thong_bao.DA_XEP_LICH_DEMO)
        except LoiNghiepVu as loi:
            form.add_error('scheduled_at' if loi.args[0] in (thong_bao.THOI_GIAN_QUA_KHU, thong_bao.NGUOI_PV_DA_CO_LICH)
                           else None, str(loi))
            return _ve_bang(request, ung_vien, form_lich=form)
        return _quay_lai(ung_vien)
    return _ve_bang(request, ung_vien, form_lich=form)


@role_required(QL)
@require_POST
def huy_vong(request, pk):
    vong = get_object_or_404(RecruitmentRound.objects.select_related('candidate'), pk=pk)
    try:
        services.huy_vong(request.user, vong)
        messages.success(request, thong_bao.DA_HUY_VONG)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    return _quay_lai(vong.candidate)


# ============================================================ UC 8.3 – Đánh giá kết quả
@role_required(QL)
@require_POST
def danh_gia_vong(request, pk):
    vong = get_object_or_404(RecruitmentRound.objects.select_related('candidate'), pk=pk)
    form = DanhGiaVongForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.danh_gia_vong(request.user, vong, d['note'], d['ket_qua'] == 'dat')
            messages.success(request, thong_bao.DA_LUU_KET_QUA_VONG)
        except LoiNghiepVu as loi:
            messages.error(request, str(loi))
        return _quay_lai(vong.candidate)
    return _ve_bang(request, vong.candidate, form_danh_gia=form)


@role_required(QL)
@require_POST
def vang_mat(request, pk):
    vong = get_object_or_404(RecruitmentRound.objects.select_related('candidate'), pk=pk)
    try:
        services.huy_vong(request.user, vong, vang_mat=True)
        messages.success(request, thong_bao.DA_DANH_DAU_VANG_MAT)
    except LoiNghiepVu as loi:
        messages.error(request, str(loi))
    return _quay_lai(vong.candidate)
