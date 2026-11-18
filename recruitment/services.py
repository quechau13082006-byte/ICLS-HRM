"""Hàm nghiệp vụ của app recruitment (UC 8): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc đổi trạng thái ứng viên (§8): mỗi bước chuyển có đúng một hàm và kiểm tra trạng thái hiện tại trước khi chuyển.
"""
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from accounts.models import User, UserRole
from core import thong_bao
from core.models import NotificationType
from core.services import LoiNghiepVu, ghi_nhat_ky, tao_thong_bao
from employees.models import EmploymentType, Position
from .models import (CampaignStatus, Candidate, CandidateStatus, RecruitmentCampaign, RecruitmentResult, RecruitmentTarget,
                     RecruitmentRound, RecruitmentRoundStatus, RecruitmentRoundType)

TEN_VONG = {RecruitmentRoundType.INTERVIEW: 'phỏng vấn', RecruitmentRoundType.DEMO: 'dạy thử (Demo)'}


# ============================================================ UC 8.1 – Đợt tuyển dụng và ứng viên
def tao_dot_tuyen_dung(nguoi_thuc_hien, ten_dot, ngay_bat_dau, ngay_ket_thuc, chi_tieu):
    """UC 8.1 – bước 2: lưu đợt tuyển dụng (status = OPEN) cùng chỉ tiêu từng vị trí.

    `chi_tieu`: dict {vị trí: số lượng cần tuyển}; vị trí có số lượng 0/trống thì bỏ qua, phải còn ít nhất một vị trí.
    """
    chi_tieu = {vi_tri: int(so) for vi_tri, so in (chi_tieu or {}).items() if so and int(so) > 0}
    if not chi_tieu:
        raise LoiNghiepVu(thong_bao.THIEU_CHI_TIEU_TUYEN)
    with transaction.atomic():
        dot = RecruitmentCampaign.objects.create(
            campaign_name=ten_dot, start_date=ngay_bat_dau, end_date=ngay_ket_thuc, created_by=nguoi_thuc_hien)
        RecruitmentTarget.objects.bulk_create(
            RecruitmentTarget(campaign=dot, position=vi_tri, quantity=so)
            for vi_tri, so in sorted(chi_tieu.items(), key=lambda m: Position.values.index(m[0])))
        tom_tat = ', '.join(f'{Position(vi_tri).label} {so}' for vi_tri, so in chi_tieu.items())
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'RecruitmentCampaign', dot.pk, f'Tạo đợt tuyển dụng "{ten_dot}" ({tom_tat})')
    return dot


def tien_do_tuyen_dung(dot):
    """UC 8.1: so sánh chỉ tiêu với thực tế của một đợt, theo từng vị trí.

    Mỗi dòng: vị trí, cần tuyển, đã tuyển (ứng viên HIRED của đợt, cùng vị trí), đạt yêu cầu chờ tiếp nhận (PASSED),
    còn thiếu và % hoàn thành. Vị trí không đặt chỉ tiêu nhưng có người được tuyển vẫn hiện (cần tuyển = 0).
    Trả về dict {'dong': [...], 'can_tuyen', 'da_tuyen', 'phan_tram'}.
    """
    can = {c.position: c.quantity for c in dot.targets.all()}
    dem = {}
    for vi_tri, trang_thai in Candidate.objects.filter(campaign=dot, status__in=[CandidateStatus.HIRED, CandidateStatus.PASSED]
                                                       ).values_list('position', 'status'):
        dem.setdefault(vi_tri, {CandidateStatus.HIRED: 0, CandidateStatus.PASSED: 0})[trang_thai] += 1
    dong = []
    for vi_tri in Position.values:
        if vi_tri not in can and vi_tri not in dem:
            continue
        can_tuyen = can.get(vi_tri, 0)
        da_tuyen = dem.get(vi_tri, {}).get(CandidateStatus.HIRED, 0)
        dong.append({'vi_tri': Position(vi_tri).label, 'can_tuyen': can_tuyen, 'da_tuyen': da_tuyen,
                     'cho_tiep_nhan': dem.get(vi_tri, {}).get(CandidateStatus.PASSED, 0),
                     'con_thieu': max(can_tuyen - da_tuyen, 0),
                     'phan_tram': min(round(da_tuyen * 100 / can_tuyen), 100) if can_tuyen else (100 if da_tuyen else 0)})
    can_tuyen, da_tuyen = sum(can.values()), sum(min(d['da_tuyen'], d['can_tuyen']) for d in dong)
    return {'dong': dong, 'can_tuyen': can_tuyen, 'da_tuyen': sum(d['da_tuyen'] for d in dong),
            'phan_tram': round(da_tuyen * 100 / can_tuyen) if can_tuyen else 0}


def dong_dot_tuyen_dung(nguoi_thuc_hien, dot):
    """UC 8.1 – luồng 1.1.1: OPEN → CLOSED (§8). Đợt đã đóng không nhận thêm ứng viên."""
    if dot.status != CampaignStatus.OPEN:
        raise LoiNghiepVu(thong_bao.DOT_DA_DONG_TRUOC_DO)
    dot.status = CampaignStatus.CLOSED
    dot.save(update_fields=['status'])
    ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'RecruitmentCampaign', dot.pk, f'Đóng đợt tuyển dụng "{dot.campaign_name}"')


def dot_mac_dinh(hom_nay=None):
    """Đợt hiện sẵn khi mở bảng ứng viên và chọn sẵn khi thêm ứng viên ("đợt đang mở gần nhất"):
    1) đợt OPEN đang diễn ra (bắt đầu ≤ hôm nay và chưa quá ngày kết thúc) – nhiều đợt thì lấy đợt bắt đầu sau cùng;
    2) không có thì đợt OPEN sắp bắt đầu sớm nhất; 3) không còn đợt mở thì đợt bắt đầu gần đây nhất; không có đợt → None."""
    hom_nay = hom_nay or date.today()
    dang_mo = RecruitmentCampaign.objects.filter(status=CampaignStatus.OPEN)
    dot = (dang_mo.filter(start_date__lte=hom_nay).filter(Q(end_date__isnull=True) | Q(end_date__gte=hom_nay))
           .order_by('-start_date', '-pk').first())
    if dot is None:
        dot = dang_mo.filter(start_date__gt=hom_nay).order_by('start_date', 'pk').first()
    if dot is None:
        dot = RecruitmentCampaign.objects.order_by('-start_date', '-pk').first()
    return dot


def them_ung_vien(nguoi_thuc_hien, dot, du_lieu):
    """UC 8.1 – bước 4: kiểm tra đợt còn mở và email chưa có trong đợt, lưu ứng viên với status = NEW."""
    if dot.status != CampaignStatus.OPEN:
        raise LoiNghiepVu(thong_bao.DOT_DA_DONG)                              # luồng 3.1
    if Candidate.objects.filter(campaign=dot, email__iexact=du_lieu['email']).exists():
        raise LoiNghiepVu(thong_bao.UNG_VIEN_TRUNG_EMAIL)                      # luồng 3.3
    with transaction.atomic():
        ung_vien = Candidate.objects.create(campaign=dot, status=CandidateStatus.NEW, **du_lieu)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'Candidate', ung_vien.pk, f'Thêm ứng viên {ung_vien.full_name} vào đợt "{dot.campaign_name}"')
    return ung_vien


def danh_gia_so_tuyen(nguoi_thuc_hien, ung_vien, dat, ghi_chu):
    """UC 8.1 – bước 6 và luồng 5.1: lưu ghi chú sơ tuyển; Đạt → SCREENING, Không đạt → REJECTED.

    Chỉ làm được khi ứng viên CHƯA được xếp lịch phỏng vấn: trạng thái NEW, SCREENING, hoặc REJECTED
    mà chưa có vòng nào (bị loại ở sơ tuyển, cho phép sửa lại).
    """
    con_sua_duoc = ung_vien.status in (CandidateStatus.NEW, CandidateStatus.SCREENING) or (
        ung_vien.status == CandidateStatus.REJECTED and not ung_vien.recruitment_rounds.exists())
    if not con_sua_duoc:
        raise LoiNghiepVu(thong_bao.KHONG_SUA_SO_TUYEN)
    ung_vien.screening_note = ghi_chu
    ung_vien.status = CandidateStatus.SCREENING if dat else CandidateStatus.REJECTED
    ung_vien.save(update_fields=['screening_note', 'status', 'updated_at'])
    ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'Candidate', ung_vien.pk,
                f'Sơ tuyển {ung_vien.full_name}: {"Đạt" if dat else "Không đạt"}')
    return ung_vien


def loai_ung_vien(nguoi_thuc_hien, ung_vien, ly_do=''):
    """UC 8.3 – luồng 3.1.1: sau khi vắng mặt, Quản lý có thể đánh giá Không đạt: TEACHING_TRIAL/SCREENING → REJECTED."""
    if ung_vien.status not in (CandidateStatus.SCREENING, CandidateStatus.TEACHING_TRIAL):
        raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_UNG_VIEN)
    ung_vien.status = CandidateStatus.REJECTED
    if ly_do:
        ung_vien.screening_note = (ung_vien.screening_note + '\n' + ly_do).strip()
    ung_vien.save(update_fields=['screening_note', 'status', 'updated_at'])
    ghi_nhat_ky(nguoi_thuc_hien, 'REJECT', 'Candidate', ung_vien.pk, f'Không đạt: {ung_vien.full_name}')
    return ung_vien


# ============================================================ UC 8.2 – Lịch phỏng vấn / Demo
def _kiem_tra_lich(nguoi_phong_van, thoi_gian, bay_gio):
    """UC 8.2 – bước 4: thời gian phải sau hiện tại; người phỏng vấn là Quản lý và không có vòng khác trong 60 phút.

    Hai vòng trùng nhau khi chênh nhau dưới THOI_LUONG_VONG_TUYEN_DUNG_PHUT (60) phút. (P6 sẽ bổ sung kiểm tra
    trùng với buổi dạy qua `schedule.kiem_tra_trung_lich`.)
    """
    if thoi_gian <= bay_gio:
        raise LoiNghiepVu(thong_bao.THOI_GIAN_QUA_KHU)                       # luồng 3.4
    if nguoi_phong_van.role != UserRole.MANAGER or not nguoi_phong_van.is_active:
        raise LoiNghiepVu(thong_bao.NGUOI_PV_PHAI_LA_QUAN_LY)
    khoang = timedelta(minutes=settings.THOI_LUONG_VONG_TUYEN_DUNG_PHUT)
    trung = RecruitmentRound.objects.filter(
        interviewer=nguoi_phong_van, status=RecruitmentRoundStatus.SCHEDULED,
        scheduled_at__gt=thoi_gian - khoang, scheduled_at__lt=thoi_gian + khoang)
    if trung.exists():
        raise LoiNghiepVu(thong_bao.NGUOI_PV_DA_CO_LICH)                      # luồng 3.3


def _dinh_dang_gio(thoi_gian):
    return thoi_gian.strftime('%d/%m/%Y %H:%M')


def _thong_bao_lich(vong):
    """Gửi thông báo cho người phỏng vấn/giám sát và email cho ứng viên về lịch của một vòng."""
    ten_vong = TEN_VONG[vong.round_type]
    dia_diem = vong.location or 'sẽ thông báo sau'
    tao_thong_bao(vong.interviewer, NotificationType.RECRUITMENT, thong_bao.TB_LICH_VONG_TIEU_DE,
                  thong_bao.TB_LICH_VONG_NOI_DUNG.format(loai=ten_vong.capitalize(), ung_vien=vong.candidate.full_name,
                                                         thoi_gian=_dinh_dang_gio(vong.scheduled_at), dia_diem=dia_diem),
                  reverse('recruitment:board') + f'?chon={vong.candidate_id}')
    send_mail(thong_bao.EMAIL_LICH_TIEU_DE.format(loai=ten_vong),
              thong_bao.EMAIL_LICH_NOI_DUNG.format(ung_vien=vong.candidate.full_name, loai=ten_vong,
                                                   thoi_gian=_dinh_dang_gio(vong.scheduled_at), dia_diem=dia_diem),
              None, [vong.candidate.email])


def xep_lich_vong(nguoi_thuc_hien, ung_vien, loai, thoi_gian, dia_diem, nguoi_phong_van, bay_gio=None):
    """UC 8.2 – xếp lịch MỘT vòng (dùng chung cho Phỏng vấn và Dạy thử), báo người phỏng vấn/giám sát và email ứng viên.

    - Phỏng vấn (INTERVIEW): ứng viên phải đang SCREENING → chuyển sang INTERVIEWING.
    - Dạy thử (DEMO): ứng viên phải đang TEACHING_TRIAL, là giáo viên Full-time và chưa có buổi Dạy thử nào đang chờ.
    Muốn đổi lịch thì Hủy rồi xếp lại (bản đơn giản không có "sửa lịch")."""
    bay_gio = bay_gio or datetime.now()
    la_phong_van = loai == RecruitmentRoundType.INTERVIEW
    if ung_vien.status != (CandidateStatus.SCREENING if la_phong_van else CandidateStatus.TEACHING_TRIAL):
        raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_UNG_VIEN)
    if not la_phong_van:
        if ung_vien.position != Position.TEACHER or ung_vien.employment_type != EmploymentType.FULL_TIME:
            raise LoiNghiepVu(thong_bao.CHI_DEMO_GV_FULL_TIME)
        if ung_vien.recruitment_rounds.filter(round_type=RecruitmentRoundType.DEMO,
                                              status=RecruitmentRoundStatus.SCHEDULED).exists():
            raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_UNG_VIEN)      # đã có một buổi Dạy thử đang chờ: hủy rồi xếp lại
    _kiem_tra_lich(nguoi_phong_van, thoi_gian, bay_gio)
    with transaction.atomic():
        vong = RecruitmentRound.objects.create(candidate=ung_vien, round_type=loai, scheduled_at=thoi_gian,
                                               location=dia_diem, interviewer=nguoi_phong_van)
        if la_phong_van:
            ung_vien.status = CandidateStatus.INTERVIEWING
            ung_vien.save(update_fields=['status', 'updated_at'])
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'RecruitmentRound', vong.pk,
                    f'Xếp lịch {TEN_VONG[loai]} {ung_vien.full_name} lúc {_dinh_dang_gio(thoi_gian)}')
    _thong_bao_lich(vong)
    return vong


def _vong_dang_cho(vong):
    if vong.status != RecruitmentRoundStatus.SCHEDULED:
        raise LoiNghiepVu(thong_bao.VONG_KHONG_CON_DANG_CHO)


def huy_vong(nguoi_thuc_hien, vong, vang_mat=False):
    """UC 8.2 – luồng 3.2.1 (hủy) và UC 8.3 – luồng 3.1.1 (ứng viên vắng mặt): SCHEDULED → CANCELLED (§8).

    Phỏng vấn bị hủy thì ứng viên INTERVIEWING → SCREENING để xếp lại; Demo bị hủy thì ứng viên giữ TEACHING_TRIAL.
    """
    _vong_dang_cho(vong)
    with transaction.atomic():
        vong.status = RecruitmentRoundStatus.CANCELLED
        vong.save(update_fields=['status'])
        ung_vien = vong.candidate
        if vong.round_type == RecruitmentRoundType.INTERVIEW and ung_vien.status == CandidateStatus.INTERVIEWING:
            ung_vien.status = CandidateStatus.SCREENING
            ung_vien.save(update_fields=['status', 'updated_at'])
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'RecruitmentRound', vong.pk,
                    f'{"Ứng viên vắng mặt: " if vang_mat else "Hủy "}{TEN_VONG[vong.round_type]} {ung_vien.full_name}')
    return vong


# ============================================================ UC 8.3 – Đánh giá kết quả
def vong_can_danh_gia(bay_gio=None):
    """UC 8.3 – bước 2: các vòng SCHEDULED đã tới giờ diễn ra."""
    bay_gio = bay_gio or datetime.now()
    return RecruitmentRound.objects.filter(
        status=RecruitmentRoundStatus.SCHEDULED, scheduled_at__lte=bay_gio).select_related('candidate', 'interviewer').order_by('scheduled_at')


def danh_gia_vong(nguoi_thuc_hien, vong, nhan_xet, dat, bay_gio=None):
    """UC 8.3 – bước 4–5: lưu nhận xét và kết quả Đạt / Không đạt (bản đơn giản: không chấm điểm), vòng → COMPLETED, cập nhật trạng thái ứng viên, email kết quả.

    Quy tắc trạng thái ứng viên:
    - Đạt phỏng vấn và là giáo viên Full-time → TEACHING_TRIAL (chờ xếp Demo).
    - Đạt phỏng vấn ở vị trí khác → PASSED.   - Đạt Demo → PASSED.
    - Không đạt ở bất kỳ vòng nào → REJECTED.
    """
    bay_gio = bay_gio or datetime.now()
    _vong_dang_cho(vong)
    if vong.scheduled_at > bay_gio:
        raise LoiNghiepVu(thong_bao.VONG_CHUA_DIEN_RA)                       # luồng 3.3
    ung_vien = vong.candidate
    trang_thai_hop_le = (CandidateStatus.INTERVIEWING if vong.round_type == RecruitmentRoundType.INTERVIEW
                         else CandidateStatus.TEACHING_TRIAL)
    if ung_vien.status != trang_thai_hop_le:
        raise LoiNghiepVu(thong_bao.SAI_TRANG_THAI_UNG_VIEN)
    if dat:
        if vong.round_type == RecruitmentRoundType.INTERVIEW:
            trang_thai_moi = (CandidateStatus.TEACHING_TRIAL
                            if ung_vien.position == Position.TEACHER and ung_vien.employment_type == EmploymentType.FULL_TIME
                            else CandidateStatus.PASSED)
        else:
            trang_thai_moi = CandidateStatus.PASSED
    else:
        trang_thai_moi = CandidateStatus.REJECTED
    with transaction.atomic():
        vong.status = RecruitmentRoundStatus.COMPLETED
        vong.note = nhan_xet
        vong.result = RecruitmentResult.PASSED if dat else RecruitmentResult.FAILED
        vong.save()
        ung_vien.status = trang_thai_moi
        ung_vien.save(update_fields=['status', 'updated_at'])
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'RecruitmentRound', vong.pk,
                    f'Đánh giá {TEN_VONG[vong.round_type]} {ung_vien.full_name}: {"Đạt" if dat else "Không đạt"}')
    ten_vong = TEN_VONG[vong.round_type]
    send_mail(thong_bao.EMAIL_KET_QUA_TIEU_DE.format(loai=ten_vong),
              (thong_bao.EMAIL_KET_QUA_DAT if dat else thong_bao.EMAIL_KET_QUA_KHONG_DAT).format(
                  ung_vien=ung_vien.full_name, loai=ten_vong), None, [ung_vien.email])
    return vong


# ============================================================ Truy vấn cho bảng ứng viên
def bang_ung_vien(dot=None, tu_khoa='', vi_tri=''):
    """UC 8.1 – bước 5: danh sách ứng viên (có thể lọc theo đợt, từ khóa, vị trí) để xếp thành các cột trên bảng."""
    danh_sach = Candidate.objects.select_related('campaign').prefetch_related('recruitment_rounds').order_by('created_at')
    if dot is not None:
        danh_sach = danh_sach.filter(campaign=dot)
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(full_name__icontains=tu_khoa.strip()) | Q(email__icontains=tu_khoa.strip())
                                     | Q(phone__icontains=tu_khoa.strip()))
    if vi_tri:
        danh_sach = danh_sach.filter(position=vi_tri)
    return danh_sach


def danh_sach_nguoi_phong_van():
    """Người phỏng vấn/giám sát: chỉ các tài khoản vai trò MANAGER đang hoạt động (UC 8.2 – bước 2)."""
    return User.objects.filter(role=UserRole.MANAGER, is_active=True).order_by('full_name', 'email')


def danh_dau_da_tuyen(ung_vien, nguoi_thuc_hien=None):
    """UC 2.5 – bước 5: ứng viên PASSED → HIRED khi Quản lý tạo hồ sơ nhân sự (§8).

    Hàm của app `recruitment` (app sở hữu bảng candidates) để `employees` gọi sang.
    """
    if ung_vien.status != CandidateStatus.PASSED:
        raise LoiNghiepVu(thong_bao.CHI_TIEP_NHAN_UNG_VIEN_DAT)
    ung_vien.status = CandidateStatus.HIRED
    ung_vien.save(update_fields=['status', 'updated_at'])
    ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'Candidate', ung_vien.pk, f'Ứng viên {ung_vien.full_name} → HIRED')
    return ung_vien
