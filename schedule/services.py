"""Hàm nghiệp vụ của app schedule (UC 6): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

View chỉ kiểm tra quyền → nhận form → gọi hàm ở đây → hiển thị kết quả.
Quy tắc §3.2: app này chỉ GHI vào 5 bảng của schedule; chỉ ĐỌC employees, leave, recruitment;
muốn gửi thông báo / ghi nhật ký thì gọi service của core.

Các nhóm hàm:
  1. Hàm dùng chung: trùng lịch, gợi ý giáo viên (§9.1) – dùng cho UC 6.1, 6.3 (và 6.4, 8.2 sau này).
  2. UC 6.1 – tạo lớp, phân công, sinh buổi dạy, hủy lớp.
  3. UC 6.2 – dựng dữ liệu lịch tuần/ngày, ghi nội dung buổi học.
  4. UC 6.3 – khung ca Part-time: tạo, đăng ký (có ca ngay), hủy đăng ký, Quản lý gán / gỡ người.
  5. Hàm do P5 viết sẵn cho UC 3.4 / 5.2 gọi sang (tao_yeu_cau_day_thay, giai_phong_lich_tuong_lai).
"""
import uuid
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from accounts.models import UserRole
from core import thong_bao
from core.models import NotificationType
from core.services import KhongCoQuyen, LoiNghiepVu, LoiTruongNhap, ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType, Position
from .models import (AssignmentRole, ClassAssignment, ClassStatus, ShiftAssignment, ShiftStatus, StudyClass,
                     SubstituteRequest, SubstituteStatus, TeachingSession, TeachingSessionStatus)

TEN_THU = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật']


# ============================================================ Tiện ích nhỏ
def _gio(chuoi):
    """'08:00' → time(8, 0) (tham số CA_FULLTIME trong settings ghi dạng chuỗi)."""
    return datetime.strptime(chuoi, '%H:%M').time()


def tach_thu(chuoi_thu):
    """'0,2,4' → [0, 2, 4] (cột classes.weekdays)."""
    return [int(x) for x in chuoi_thu.split(',') if x != '']


def chuoi_thu_hoc(chuoi_thu):
    """'1,3' → 'Thứ 3, Thứ 5' để hiển thị."""
    return ', '.join(TEN_THU[x] for x in tach_thu(chuoi_thu))


def _ten_gio(bat_dau, ket_thuc):
    return f'{bat_dau:%H:%M}–{ket_thuc:%H:%M}'


def dau_tuan(ngay):
    """Thứ 2 của tuần chứa `ngay` (tuần bắt đầu từ Thứ 2)."""
    return ngay - timedelta(days=ngay.weekday())


# ============================================================ 1. HÀM DÙNG CHUNG (§9.1, §9.2)
def tim_nhan_su_trung_lich(cac_ngay, bat_dau, ket_thuc):
    """§9.2 – tập id nhân sự bị TRÙNG giờ [bat_dau, ket_thuc) ở ÍT NHẤT MỘT trong `cac_ngay`.

    Hai khoảng giờ trùng nhau khi `bat_dau < ket_thuc_khac` VÀ `ket_thuc > bat_dau_khac`. Xét 4 loại lịch:
    buổi dạy (giáo viên/trợ giảng thực tế, không CANCELLED), chỗ ca đã có người (SCHEDULED),
    vòng tuyển dụng SCHEDULED mà người đó phỏng vấn (60 phút), đơn nghỉ APPROVED.
    Làm một lượt cho nhiều ngày để gợi ý giáo viên không phải hỏi CSDL từng ngày một.
    """
    from leave.models import LeaveRequest
    from recruitment.models import RecruitmentRound, RecruitmentRoundStatus

    cac_ngay = list(cac_ngay)
    bi_trung = set()
    if not cac_ngay:
        return bi_trung

    # (1) Buổi dạy
    buoi = TeachingSession.objects.filter(
        session_date__in=cac_ngay, planned_start__lt=ket_thuc, planned_end__gt=bat_dau
    ).exclude(status=TeachingSessionStatus.CANCELLED)
    for gv_thuc, gv_du_kien, tro_giang in buoi.values_list('actual_teacher_id', 'planned_teacher_id',
                                                           'actual_assistant_id'):
        bi_trung.add(gv_thuc or gv_du_kien)
        if tro_giang:
            bi_trung.add(tro_giang)

    # (2) Chỗ ca đã có người đăng ký
    bi_trung.update(ShiftAssignment.objects.filter(
        work_date__in=cac_ngay, employee__isnull=False, status=ShiftStatus.SCHEDULED,
        planned_start__lt=ket_thuc, planned_end__gt=bat_dau).values_list('employee_id', flat=True))

    # (3) Vòng tuyển dụng: người phỏng vấn là User, đổi sang id nhân sự
    thoi_luong = timedelta(minutes=settings.THOI_LUONG_VONG_TUYEN_DUNG_PHUT)
    cac_vong = RecruitmentRound.objects.filter(status=RecruitmentRoundStatus.SCHEDULED,
                                               scheduled_at__date__in=cac_ngay)
    user_trung = set()
    for vong in cac_vong:
        ngay = vong.scheduled_at.date()
        if vong.scheduled_at < datetime.combine(ngay, ket_thuc) and vong.scheduled_at + thoi_luong > datetime.combine(ngay, bat_dau):
            user_trung.add(vong.interviewer_id)
    if user_trung:
        bi_trung.update(Employee.objects.filter(user_id__in=user_trung).values_list('id', flat=True))

    # (4) Đơn nghỉ đã duyệt (nghỉ luôn cả ngày nên trùng mọi khung giờ của ngày đó)
    cac_don = LeaveRequest.objects.filter(status='APPROVED', start_date__lte=max(cac_ngay),
                                          end_date__gte=min(cac_ngay)).select_related('employee')
    for don in cac_don:
        if any(don.start_date <= ngay <= don.end_date for ngay in cac_ngay):
            bi_trung.add(don.employee_id)
    return bi_trung


def kiem_tra_trung_lich(nhan_su, ngay, bat_dau, ket_thuc):
    """§9.1 – True nếu `nhan_su` đã có lịch khác trùng giờ vào `ngay` (dùng cho UC 6.1, 6.3, 6.4, 8.2)."""
    return nhan_su.pk in tim_nhan_su_trung_lich([ngay], bat_dau, ket_thuc)


def _ca_bao_tron_gio_hoc(nhan_su, bat_dau, ket_thuc):
    """Q16: giáo viên Full-time chỉ dạy lớp nằm TRỌN trong ca của mình (lớp 18–20h chỉ Ca 2). Part-time: không giới hạn."""
    if nhan_su.employment_type != EmploymentType.FULL_TIME:
        return True
    if nhan_su.work_shift not in settings.CA_FULLTIME:
        return False
    gio_vao, gio_ra = (_gio(x) for x in settings.CA_FULLTIME[nhan_su.work_shift])
    return gio_vao <= bat_dau and ket_thuc <= gio_ra


def giao_vien_du_dieu_kien(nhan_su, bat_dau, ket_thuc, chi_full_time=False):
    """Điều kiện KHÔNG xét trùng lịch của một giáo viên: TEACHER, ACTIVE, (Full-time), ca bao trọn giờ học."""
    return (nhan_su.position == Position.TEACHER and nhan_su.status == EmployeeStatus.ACTIVE
            and (not chi_full_time or nhan_su.employment_type == EmploymentType.FULL_TIME)
            and _ca_bao_tron_gio_hoc(nhan_su, bat_dau, ket_thuc))


def goi_y_giao_vien(cac_ngay, bat_dau, ket_thuc, loai_tru=None, chi_full_time=False):
    """§9.1, §9.2 – danh sách giáo viên có thể dạy mọi ngày trong `cac_ngay` khung giờ [bat_dau, ket_thuc).

    TEACHER, ACTIVE, không trùng lịch ở MỌI ngày, và (Full-time) ca làm việc bao trọn giờ học.
    UC 6.1 truyền chi_full_time=True; UC 6.4 truyền loai_tru = giáo viên vắng.
    """
    ung_vien = Employee.objects.filter(position=Position.TEACHER, status=EmployeeStatus.ACTIVE)
    if chi_full_time:
        ung_vien = ung_vien.filter(employment_type=EmploymentType.FULL_TIME)
    if loai_tru is not None:
        ung_vien = ung_vien.exclude(pk=loai_tru.pk)
    bi_trung = tim_nhan_su_trung_lich(cac_ngay, bat_dau, ket_thuc)
    return [nv for nv in ung_vien.order_by('full_name')
            if nv.pk not in bi_trung and _ca_bao_tron_gio_hoc(nv, bat_dau, ket_thuc)]


def goi_y_tro_giang(cac_ngay, bat_dau, ket_thuc):
    """UC 6.1 – bước 5: trợ giảng phù hợp = TEACHING_ASSISTANT, ACTIVE, không trùng giờ (trợ giảng làm theo buổi, Q9)."""
    ung_vien = Employee.objects.filter(position=Position.TEACHING_ASSISTANT, status=EmployeeStatus.ACTIVE)
    bi_trung = tim_nhan_su_trung_lich(cac_ngay, bat_dau, ket_thuc)
    return [nv for nv in ung_vien.order_by('full_name') if nv.pk not in bi_trung]


def la_giao_vien_han_quoc(nhan_su):
    """Chỉ lớp do giáo viên người Hàn Quốc phụ trách mới có trợ giảng."""
    return (nhan_su.nationality or '').strip().lower() in ('hàn quốc', 'han quoc', 'korea', 'south korea')


def so_lop_dang_day(nhan_su):
    """Số lớp giáo viên đang là giáo viên chính (hiện ở thẻ gợi ý như "Tải lớp" trong Figma)."""
    return ClassAssignment.objects.filter(employee=nhan_su, assignment_role=AssignmentRole.MAIN_TEACHER,
                                          end_date__isnull=True,
                                          study_class__status__in=[ClassStatus.UPCOMING, ClassStatus.ACTIVE]).count()


# ============================================================ 2. UC 6.1 – TẠO VÀ PHÂN CÔNG LỚP HỌC
def tinh_ngay_hoc(bat_dau, ket_thuc, cac_thu):
    """UC 6.1 – bước 4: các ngày từ `bat_dau` đến `ket_thuc` có thứ nằm trong `cac_thu` (0 = Thứ 2)."""
    cac_ngay, ngay = [], bat_dau
    while ngay <= ket_thuc:
        if ngay.weekday() in cac_thu:
            cac_ngay.append(ngay)
        ngay += timedelta(days=1)
    return cac_ngay


def kiem_tra_trung_phong(phong, cac_ngay, bat_dau, ket_thuc):
    """UC 6.1 – bước 5: phòng đã có buổi của lớp khác trùng giờ? Chỉ so tên phòng (không có bảng phòng học, §4.2)."""
    if not phong.strip():
        return False
    return TeachingSession.objects.filter(
        room_name__iexact=phong.strip(), session_date__in=cac_ngay, planned_start__lt=ket_thuc,
        planned_end__gt=bat_dau).exclude(status=TeachingSessionStatus.CANCELLED).exists()


def chuan_bi_phan_cong(du_lieu):
    """UC 6.1 – bước 4–5: kiểm tra thông tin lớp, trả về danh sách ngày học + giáo viên / trợ giảng gợi ý.

    Ném LoiTruongNhap: không có ngày học (3.x), phòng bị trùng (3.2), không có giáo viên (3.3).
    """
    cac_thu = tach_thu(du_lieu['weekdays'])
    cac_ngay = tinh_ngay_hoc(du_lieu['start_date'], du_lieu['end_date'], cac_thu)
    if not cac_ngay:
        raise LoiTruongNhap(thong_bao.KHONG_CO_NGAY_HOC, 'weekdays')
    bat_dau, ket_thuc = du_lieu['start_time'], du_lieu['end_time']
    if kiem_tra_trung_phong(du_lieu['room_name'], cac_ngay, bat_dau, ket_thuc):
        raise LoiTruongNhap(thong_bao.PHONG_BI_TRUNG.format(phong=du_lieu['room_name'].strip()), 'room_name')
    giao_vien = goi_y_giao_vien(cac_ngay, bat_dau, ket_thuc, chi_full_time=True)
    if not giao_vien:
        raise LoiTruongNhap(thong_bao.KHONG_CO_GIAO_VIEN)
    return {'cac_ngay': cac_ngay, 'giao_vien': giao_vien, 'tro_giang': goi_y_tro_giang(cac_ngay, bat_dau, ket_thuc)}


def tao_lop_va_phan_cong(nguoi_thuc_hien, du_lieu, giao_vien, tro_giang=None):
    """UC 6.1 – bước 6–8: kiểm tra lại trùng lịch rồi, trong MỘT giao dịch: lưu lớp (UPCOMING), tạo phân công,
    sinh toàn bộ buổi dạy (SCHEDULED, actual_* = planned_*), gửi thông báo. Trả về (lớp, số buổi).

    Ném LoiTruongNhap('giao_vien'/'tro_giang') khi vừa bị trùng lịch do thao tác khác (luồng 6.1) → view quay lại bước 6.
    """
    bat_dau, ket_thuc = du_lieu['start_time'], du_lieu['end_time']
    cac_thu = tach_thu(du_lieu['weekdays'])
    cac_ngay = tinh_ngay_hoc(du_lieu['start_date'], du_lieu['end_date'], cac_thu)
    if not cac_ngay:
        raise LoiTruongNhap(thong_bao.KHONG_CO_NGAY_HOC, 'weekdays')
    if kiem_tra_trung_phong(du_lieu['room_name'], cac_ngay, bat_dau, ket_thuc):
        raise LoiTruongNhap(thong_bao.PHONG_BI_TRUNG.format(phong=du_lieu['room_name'].strip()), 'room_name')

    # Kiểm tra lại ngay trước khi ghi (§10 UC 6.1 bước 7)
    if not giao_vien_du_dieu_kien(giao_vien, bat_dau, ket_thuc, chi_full_time=True):
        raise LoiTruongNhap(thong_bao.GIAO_VIEN_KHONG_HOP_LE, 'giao_vien')
    if tro_giang is not None and not la_giao_vien_han_quoc(giao_vien):
        raise LoiTruongNhap(thong_bao.TRO_GIANG_CHI_LOP_GV_HAN, 'tro_giang')
    if tro_giang is not None and not (tro_giang.position == Position.TEACHING_ASSISTANT
                                      and tro_giang.status == EmployeeStatus.ACTIVE):
        raise LoiTruongNhap(thong_bao.TRO_GIANG_KHONG_HOP_LE, 'tro_giang')
    bi_trung = tim_nhan_su_trung_lich(cac_ngay, bat_dau, ket_thuc)
    if giao_vien.pk in bi_trung:
        raise LoiTruongNhap(thong_bao.GIAO_VIEN_TRUNG_LICH, 'giao_vien')
    if tro_giang is not None and tro_giang.pk in bi_trung:
        raise LoiTruongNhap(thong_bao.TRO_GIANG_TRUNG_LICH, 'tro_giang')

    with transaction.atomic():
        lop = StudyClass.objects.create(
            class_name=du_lieu['class_name'].strip(), subject=du_lieu['subject'].strip(),
            room_name=du_lieu['room_name'].strip(), max_students=du_lieu['max_students'],
            weekdays=','.join(str(x) for x in sorted(cac_thu)), start_time=bat_dau, end_time=ket_thuc,
            start_date=du_lieu['start_date'], end_date=du_lieu['end_date'], status=ClassStatus.UPCOMING)
        ClassAssignment.objects.create(study_class=lop, employee=giao_vien, assignment_role=AssignmentRole.MAIN_TEACHER,
                                       start_date=lop.start_date)
        if tro_giang is not None:
            ClassAssignment.objects.create(study_class=lop, employee=tro_giang,
                                           assignment_role=AssignmentRole.TEACHING_ASSISTANT, start_date=lop.start_date)
        TeachingSession.objects.bulk_create([
            TeachingSession(study_class=lop, session_date=ngay, planned_start=bat_dau, planned_end=ket_thuc,
                            room_name=lop.room_name, planned_teacher=giao_vien, actual_teacher=giao_vien,
                            planned_assistant=tro_giang, actual_assistant=tro_giang,
                            status=TeachingSessionStatus.SCHEDULED)
            for ngay in cac_ngay])
        so_buoi = len(cac_ngay)
        link = reverse('schedule:class_detail', args=[lop.pk])
        for nguoi, vai_tro in ((giao_vien, AssignmentRole.MAIN_TEACHER), (tro_giang, AssignmentRole.TEACHING_ASSISTANT)):
            if nguoi is not None:
                tao_thong_bao(nguoi.user, NotificationType.SCHEDULE, thong_bao.TB_LOP_MOI_TIEU_DE,
                              thong_bao.TB_LOP_MOI_NOI_DUNG.format(
                                  lop=lop.class_name, thu=chuoi_thu_hoc(lop.weekdays),
                                  gio=_ten_gio(bat_dau, ket_thuc), tu_ngay=f'{lop.start_date:%d/%m/%Y}',
                                  vai_tro=AssignmentRole(vai_tro).label, so_buoi=so_buoi), link)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'classes', lop.pk, f'Tạo lớp {lop.class_name} ({so_buoi} buổi)')
    return lop, so_buoi


def huy_lop(nguoi_thuc_hien, lop, ly_do, hom_nay=None):
    """UC 6.1 – luồng thay thế 1.1: hủy lớp UPCOMING/ACTIVE trong một giao dịch.

    Lớp → CANCELLED; buổi SCHEDULED từ hôm nay trở đi → CANCELLED (kèm yêu cầu dạy thay đang tìm → FAILED);
    phân công còn hiệu lực đặt end_date; thông báo giáo viên, trợ giảng. Trả về số buổi đã hủy.
    """
    hom_nay = hom_nay or date.today()
    if not ly_do.strip():
        raise LoiTruongNhap(thong_bao.NHAP_LY_DO_HUY_LOP, 'ly_do')
    if lop.status not in (ClassStatus.UPCOMING, ClassStatus.ACTIVE):
        raise LoiNghiepVu(thong_bao.LOP_KHONG_HUY_DUOC)
    with transaction.atomic():
        lop.status = ClassStatus.CANCELLED
        lop.save(update_fields=['status', 'updated_at'])
        buoi = TeachingSession.objects.filter(study_class=lop, status=TeachingSessionStatus.SCHEDULED,
                                              session_date__gte=hom_nay)
        ma_buoi = list(buoi.values_list('pk', flat=True))
        SubstituteRequest.objects.filter(teaching_session__in=ma_buoi, status=SubstituteStatus.SEARCHING
                                         ).update(status=SubstituteStatus.FAILED)
        so_buoi = buoi.update(status=TeachingSessionStatus.CANCELLED)
        link = reverse('schedule:class_detail', args=[lop.pk])
        for pc in lop.assignments.filter(end_date__isnull=True).select_related('employee__user'):
            pc.end_date = max(hom_nay, pc.start_date)   # end_date không được trước start_date
            pc.save(update_fields=['end_date'])
            tao_thong_bao(pc.employee.user, NotificationType.SCHEDULE, thong_bao.TB_HUY_LOP_TIEU_DE,
                          thong_bao.TB_HUY_LOP_NOI_DUNG.format(lop=lop.class_name, ly_do=ly_do.strip()), link)
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'classes', lop.pk, f'Hủy lớp {lop.class_name}: {ly_do.strip()}')
    return so_buoi


# ============================================================ 3. UC 6.2 – XEM LỊCH LÀM VIỆC & LỊCH LỚP HỌC
def _muc_buoi_day(buoi):
    """Một buổi dạy → một ô trên lịch."""
    mau = {'UPCOMING': 'vang', 'ACTIVE': 'xanh', 'COMPLETED': 'xam', 'CANCELLED': 'do'}[buoi.study_class.status]
    if buoi.status == TeachingSessionStatus.CANCELLED:
        mau = 'do'
    giao_vien = buoi.actual_teacher or buoi.planned_teacher
    return {'loai': 'buoi', 'id': buoi.pk, 'ngay': buoi.session_date, 'bd': buoi.planned_start, 'kt': buoi.planned_end,
            'tieu_de': buoi.study_class.ma_lop, 'ten_lop': buoi.study_class.class_name, 'dong_2': buoi.room_name or 'Chưa có phòng',
            'dong_3': giao_vien.full_name, 'mau': mau, 'huy': buoi.status == TeachingSessionStatus.CANCELLED,
            'phong': buoi.room_name or 'Chưa có phòng', 'nhan_su_id': giao_vien.pk, 'ten': giao_vien.full_name,
            'nhom': 'Giáo viên', 'url': reverse('schedule:session_detail', args=[buoi.pk])}


def _nhom_cua(nhan_su):
    """Nhóm hiển thị trên bảng Lịch làm việc của Quản lý: Trợ giảng / Part-time / Full-time."""
    if nhan_su.position == Position.TEACHING_ASSISTANT:
        return 'Trợ giảng'
    return 'Full-time' if nhan_su.employment_type == EmploymentType.FULL_TIME else 'Part-time'


def _muc_tro_giang(buoi):
    """Một buổi làm trợ giảng → một ô trên bảng Lịch làm việc (hàng của người trợ giảng)."""
    tg = buoi.actual_assistant
    return {'loai': 'tro_giang', 'id': buoi.pk, 'ngay': buoi.session_date, 'bd': buoi.planned_start, 'kt': buoi.planned_end,
            'tieu_de': buoi.study_class.ma_lop, 'ten_lop': buoi.study_class.class_name, 'dong_2': buoi.room_name or 'Chưa có phòng', 'dong_3': '',
            'mau': 'tg', 'huy': False, 'phong': buoi.room_name or 'Chưa có phòng', 'nhan_su_id': tg.pk,
            'ten': tg.full_name, 'nhom': 'Trợ giảng', 'url': reverse('schedule:session_detail', args=[buoi.pk])}


def _muc_ca(cho):
    """Một chỗ ca làm việc → một ô trên lịch (màu theo vai trò ca)."""
    return {'loai': 'ca', 'id': cho.pk, 'ngay': cho.work_date, 'bd': cho.planned_start, 'kt': cho.planned_end,
            'tieu_de': cho.shift_role, 'dong_2': cho.employee.full_name if cho.employee else '',
            'dong_3': '', 'mau': ('ca0', 'ca1', 'ca2')[sum(map(ord, cho.shift_role)) % 3], 'huy': False,
            'phong': '', 'nhan_su_id': cho.employee_id, 'ten': cho.employee.full_name if cho.employee else '',
            'nhom': _nhom_cua(cho.employee) if cho.employee else 'Part-time',
            'url': reverse('schedule:shift_detail', args=[cho.pk])}


def lich_ca_full_time(tu_ngay, den_ngay, nhan_su=None):
    """UC 6.2: ca làm việc CỐ ĐỊNH của nhân sự Full-time (Ca 1 / Ca 2 ghi trong hồ sơ, Thứ 2 – Thứ 7, §6 và Q16) trong khoảng ngày.

    Mỗi (nhân sự, ngày làm việc) một ô. Ngày có đơn nghỉ đã duyệt (luôn nghỉ cả ngày) thì ô là "Nghỉ phép".
    Nếu truyền `nhan_su` thì chỉ lấy của người đó.
    Chỉ ĐỌC employees và leave (§3.2); làm một lượt cho cả khoảng ngày để khỏi hỏi CSDL từng người từng ngày."""
    from leave.models import LeaveRequest   # chỉ đọc (§3.2)
    ds = Employee.objects.filter(employment_type=EmploymentType.FULL_TIME, status=EmployeeStatus.ACTIVE,
                                 work_shift__in=list(settings.CA_FULLTIME), join_date__lte=den_ngay)
    if nhan_su is not None:
        ds = ds.filter(pk=nhan_su.pk)
    cac_don = {}
    for don in LeaveRequest.objects.filter(status='APPROVED', employee__in=ds, start_date__lte=den_ngay, end_date__gte=tu_ngay):
        cac_don.setdefault(don.employee_id, []).append(don)
    cac_muc = []
    for nv in ds.order_by('full_name'):
        gio_vao, gio_ra = (_gio(x) for x in settings.CA_FULLTIME[nv.work_shift])
        ten_ca = 'Ca 1' if nv.work_shift == 'SHIFT_1' else 'Ca 2'
        ngay = tu_ngay
        while ngay <= den_ngay:
            if ngay.weekday() in settings.NGAY_LAM_VIEC and ngay >= nv.join_date:
                nghi = any(d.start_date <= ngay <= d.end_date for d in cac_don.get(nv.pk, []))
                cac_muc.append({
                    'loai': 'nghi' if nghi else 'ca_ft', 'id': nv.pk, 'ngay': ngay, 'bd': gio_vao, 'kt': gio_ra,
                    'tieu_de': 'Nghỉ phép' if nghi else ten_ca, 'huy': False, 'url': '', 'phong': '',
                    'dong_2': nv.full_name, 'dong_3': '',
                    'mau': 'nghi' if nghi else ('ft1' if nv.work_shift == 'SHIFT_1' else 'ft2'),
                    'nhan_su_id': nv.pk, 'ten': nv.full_name, 'nhom': 'Full-time', 'nen': not nghi})
            ngay += timedelta(days=1)
    return cac_muc


def lich_lam_viec(nguoi_xem, tu_ngay, den_ngay, nhan_su_loc=None, chi_cua_minh=False):
    """UC 6.2 – bước 2, tab Lịch làm việc.

    - `chi_cua_minh=True` (tab Cá nhân của dashboard): ai cũng chỉ lấy lịch của CHÍNH mình, kể cả Quản lý / Giám đốc.
    - Quản lý, Giám đốc: lịch của TOÀN trung tâm, gồm ca Part-time đã có người (SCHEDULED), ca cố định Full-time
      (Ca 1 / Ca 2, kèm ngày nghỉ phép) và các buổi làm trợ giảng; lọc được theo nhân sự (`nhan_su_loc`).
    - Kế toán, Nhân viên: chỉ của chính mình: ca Part-time đã đăng ký, ca cố định Full-time (làm nền) và buổi dạy / trợ giảng
      của mình (lọc ngay trong truy vấn, §5).
    """
    cac_ca = ShiftAssignment.objects.filter(status=ShiftStatus.SCHEDULED, employee__isnull=False,
                                            work_date__range=(tu_ngay, den_ngay)).select_related('employee')
    cac_muc = []
    if nguoi_xem.role in (UserRole.MANAGER, UserRole.DIRECTOR) and not chi_cua_minh:
        if nhan_su_loc is not None:
            cac_ca = cac_ca.filter(employee=nhan_su_loc)
        cac_muc.extend(_muc_ca(c) for c in cac_ca)
        cac_muc.extend(lich_ca_full_time(tu_ngay, den_ngay, nhan_su_loc))
        buoi_tg = TeachingSession.objects.filter(
            actual_assistant__isnull=False, session_date__range=(tu_ngay, den_ngay)
        ).exclude(status=TeachingSessionStatus.CANCELLED).select_related('study_class', 'actual_assistant')
        if nhan_su_loc is not None:
            buoi_tg = buoi_tg.filter(actual_assistant=nhan_su_loc)
        cac_muc.extend(_muc_tro_giang(b) for b in buoi_tg)
    else:
        nhan_su = getattr(nguoi_xem, 'employee', None)
        if nhan_su is None:
            return []
        cac_muc.extend(_muc_ca(c) for c in cac_ca.filter(employee=nhan_su))
        cac_muc.extend(lich_ca_full_time(tu_ngay, den_ngay, nhan_su))
        buoi = TeachingSession.objects.filter(
            Q(actual_teacher=nhan_su) | Q(actual_assistant=nhan_su), session_date__range=(tu_ngay, den_ngay)
        ).exclude(status=TeachingSessionStatus.CANCELLED).select_related('study_class', 'actual_teacher',
                                                                         'planned_teacher')
        cac_muc.extend(_muc_buoi_day(b) for b in buoi)
    return cac_muc


def lich_lop_hoc(tu_ngay, den_ngay, giao_vien=None):
    """UC 6.2 – bước 2, tab Lịch lớp học: buổi dạy của toàn trung tâm; QL/Giám đốc lọc được theo Giáo viên."""
    buoi = TeachingSession.objects.filter(session_date__range=(tu_ngay, den_ngay)).select_related(
        'study_class', 'actual_teacher', 'planned_teacher')
    if giao_vien is not None:
        buoi = buoi.filter(Q(actual_teacher=giao_vien) | Q(actual_assistant=giao_vien))
    return [_muc_buoi_day(b) for b in buoi]


def _cot_ngay(thu_hai, hom_nay):
    return [{'ngay': thu_hai + timedelta(days=i), 'thu': TEN_THU[i], 'la_hom_nay': thu_hai + timedelta(days=i) == hom_nay,
             'cuoi_tuan': i >= 5} for i in range(7)]


NHOM_BANG = ['Part-time', 'Trợ giảng', 'Full-time']     # nhóm hay thay đổi theo tuần đứng trước
LOC_NHOM = {'part_time': 'Part-time', 'tro_giang': 'Trợ giảng', 'full_time': 'Full-time'}


def dung_bang_nhan_su(cac_muc, thu_hai, hom_nay=None, loc_nhom=''):
    """UC 6.2 – tab Lịch làm việc của Quản lý/Giám đốc: bảng "mỗi nhân sự một hàng, mỗi ngày một cột".

    - Nhóm xếp Part-time → Trợ giảng → Full-time (nhóm có lịch thay đổi lên trước), trong nhóm xếp theo tên.
    - Mỗi hàng có `co_nghi` (tuần này có ngày nghỉ phép) để Full-time chỉ hiện người có ngày khác thường khi thu gọn,
      và `ca` (nhãn Ca 1 / Ca 2 của Full-time, ghi một lần cạnh tên).
    - `loc_nhom`: '' (tất cả), 'part_time', 'tro_giang', 'full_time' hoặc 'nghi' (chỉ người có nghỉ phép).
    - `tong_ngay` là số người đang làm việc (không tính nghỉ phép) mỗi ngày, tính trên toàn bộ trước khi lọc."""
    hom_nay = hom_nay or date.today()
    cac_hang = {}
    for m in cac_muc:
        chi_so = (m['ngay'] - thu_hai).days
        if not 0 <= chi_so < 7:
            continue
        hang = cac_hang.setdefault(m['nhan_su_id'], {'ten': m['ten'], 'nhom': m['nhom'], 'ca': '', 'co_nghi': False,
                                                      'cac_o': [[] for _ in range(7)]})
        hang['cac_o'][chi_so].append(m)
        if m['loai'] == 'ca_ft':
            hang['ca'] = m['tieu_de']
        if m['loai'] == 'nghi':
            hang['co_nghi'] = True
    for hang in cac_hang.values():
        for o in hang['cac_o']:
            o.sort(key=lambda m: (m['bd'], m['kt']))
    thu_tu_nhom = {ten: i for i, ten in enumerate(NHOM_BANG)}
    ket_qua = sorted(cac_hang.values(), key=lambda h: (thu_tu_nhom.get(h['nhom'], 9), h['ten']))
    tong_ngay = [sum(1 for h in ket_qua if any(m['loai'] != 'nghi' for m in h['cac_o'][i])) for i in range(7)]
    if loc_nhom == 'nghi':
        ket_qua = [h for h in ket_qua if h['co_nghi']]
    elif loc_nhom in LOC_NHOM:
        ket_qua = [h for h in ket_qua if h['nhom'] == LOC_NHOM[loc_nhom]]
    cot = _cot_ngay(thu_hai, hom_nay)
    for c, so in zip(cot, tong_ngay):
        c['so_nguoi'] = so
    nhom = [{'ten': ten, 'hang': [h for h in ket_qua if h['nhom'] == ten]} for ten in NHOM_BANG]
    for n in nhom:
        n['co_nghi'] = any(h['co_nghi'] for h in n['hang'])
    # Nhóm Part-time vẫn hiện khi trống (để thấy dòng "Chỗ còn trống") nếu đang xem tất cả hoặc lọc Part-time
    giu_part_time = loc_nhom in ('', 'part_time')
    return {'cot': cot, 'hang': ket_qua, 'nhom': [n for n in nhom if n['hang'] or (n['ten'] == 'Part-time' and giu_part_time)],
            'tong_ngay': tong_ngay, 'chi_so_hom_nay': (hom_nay - thu_hai).days}


def cho_ca_con_trong(thu_hai):
    """Các chỗ ca Part-time còn TRỐNG trong tuần (theo từng ngày) – dòng "Chỗ còn trống" trên bảng Lịch làm việc."""
    cac_o = [[] for _ in range(7)]
    for cho in ShiftAssignment.objects.filter(status=ShiftStatus.OPEN, employee__isnull=True,
                                              work_date__range=(thu_hai, thu_hai + timedelta(days=6))
                                              ).order_by('work_date', 'planned_start'):
        cac_o[(cho.work_date - thu_hai).days].append(
            {'tieu_de': cho.shift_role, 'bd': cho.planned_start, 'kt': cho.planned_end,
             'url': reverse('schedule:shift_group', args=[cho.slot_group])})
    return cac_o


def tom_tat_tuan(cac_muc, thu_hai, hom_nay=None):
    """4 con số đầu trang Lịch làm việc của Quản lý: đang làm hôm nay, nghỉ phép trong tuần, chỗ ca còn trống, buổi cần
    người thay. Chỉ ĐỌC (đơn nghỉ đọc từ app leave, §3.2)."""
    from leave.models import LeaveRequest
    hom_nay = hom_nay or date.today()
    cuoi_tuan = thu_hai + timedelta(days=6)
    dang_lam = ({m['nhan_su_id'] for m in cac_muc if m['ngay'] == hom_nay and m['loai'] != 'nghi'}
                if thu_hai <= hom_nay <= cuoi_tuan else None)     # tuần đang xem không chứa hôm nay → không có số
    nghi = LeaveRequest.objects.filter(status='APPROVED', start_date__lte=cuoi_tuan, end_date__gte=thu_hai
                                       ).values('employee').distinct().count()
    return {'dang_lam_hom_nay': None if dang_lam is None else len(dang_lam), 'nghi_tuan': nghi,
            'cho_trong': ShiftAssignment.objects.filter(status=ShiftStatus.OPEN, employee__isnull=True,
                                                        work_date__range=(thu_hai, cuoi_tuan)).count(),
            'can_thay': yeu_cau_day_thay_dang_tim().count()}


def dung_bang_phong(cac_muc, thu_hai, hom_nay=None):
    """UC 6.2 – tab Lịch lớp học: bảng "mỗi phòng học một hàng, mỗi ngày một cột" để thấy phòng nào dùng lúc nào,
    lớp nào, giáo viên nào. Ô xếp theo giờ; buổi chưa có phòng nằm ở hàng "Chưa có phòng"."""
    hom_nay = hom_nay or date.today()
    cac_hang = {}
    for m in cac_muc:
        chi_so = (m['ngay'] - thu_hai).days
        if not 0 <= chi_so < 7:
            continue
        hang = cac_hang.setdefault(m['phong'], {'ten': m['phong'], 'cac_o': [[] for _ in range(7)]})
        hang['cac_o'][chi_so].append(m)
    for hang in cac_hang.values():
        for o in hang['cac_o']:
            o.sort(key=lambda m: (m['bd'], m['kt']))
    ket_qua = sorted(cac_hang.values(), key=lambda h: (h['ten'] == 'Chưa có phòng', h['ten']))
    cot = _cot_ngay(thu_hai, hom_nay)
    for i, c in enumerate(cot):
        c['so_buoi'] = sum(len(h['cac_o'][i]) for h in ket_qua)
    return {'cot': cot, 'hang': ket_qua}


def ghi_noi_dung_buoi_hoc(nguoi_ghi, buoi, noi_dung):
    """UC 6.2 – luồng thay thế 5.1.1: giáo viên THỰC TẾ của buổi dạy lưu lesson_note."""
    nhan_su = getattr(nguoi_ghi, 'employee', None)
    if nhan_su is None or nhan_su.pk != (buoi.actual_teacher_id or buoi.planned_teacher_id):
        raise KhongCoQuyen(thong_bao.CHI_GV_GHI_NOI_DUNG)
    buoi.lesson_note = noi_dung.strip()
    buoi.save(update_fields=['lesson_note'])
    ghi_nhat_ky(nguoi_ghi, 'UPDATE', 'teaching_sessions', buoi.pk, 'Ghi nội dung buổi học')
    return buoi


def co_quyen_xem_ca(nguoi_xem, cho):
    """UC 6.2 – luồng 1.1: Quản lý/Giám đốc xem mọi ca; người khác chỉ xem ca của chính mình."""
    if nguoi_xem.role in (UserRole.MANAGER, UserRole.DIRECTOR):
        return True
    return cho.employee_id is not None and cho.employee.user_id == nguoi_xem.pk


# ============================================================ 4. UC 6.3 – KHUNG CA LÀM VIỆC PART-TIME
def la_part_time_hoat_dong(nhan_su):
    """Tiền điều kiện UC 6.3: nhân viên Part-time đang ACTIVE."""
    return (nhan_su is not None and nhan_su.employment_type == EmploymentType.PART_TIME
            and nhan_su.status == EmployeeStatus.ACTIVE)


def tao_khung_ca(nguoi_thuc_hien, vai_tro, ngay, bat_dau, ket_thuc, so_nguoi, han_chot):
    """UC 6.3 – bước 1–2: kiểm tra hạn chót trước giờ bắt đầu ca; tạo ĐÚNG N dòng shift_assignments
    (employee = NULL, OPEN, chung slot_group) trong một giao dịch; mời mọi nhân viên Part-time ACTIVE đăng ký.
    Trả về mã khung ca (slot_group)."""
    if so_nguoi < 1:
        raise LoiTruongNhap(thong_bao.SO_NGUOI_CA_SAI, 'so_nguoi')
    if ket_thuc <= bat_dau:
        raise LoiTruongNhap(thong_bao.GIO_KET_THUC_LOP_SAI, 'ket_thuc')
    if han_chot >= datetime.combine(ngay, bat_dau):
        raise LoiTruongNhap(thong_bao.HAN_CHOT_CA_SAI, 'han_chot')
    ma_khung = str(uuid.uuid4())
    with transaction.atomic():
        ShiftAssignment.objects.bulk_create([
            ShiftAssignment(slot_group=ma_khung, employee=None, shift_role=vai_tro.strip(), work_date=ngay,
                            planned_start=bat_dau, planned_end=ket_thuc, registration_deadline=han_chot,
                            status=ShiftStatus.OPEN)
            for _ in range(so_nguoi)])
        link = reverse('schedule:shift_register')
        noi_dung = thong_bao.TB_MOI_DANG_KY_CA_NOI_DUNG.format(
            vai_tro=vai_tro.strip(), ngay=f'{ngay:%d/%m/%Y}', gio=_ten_gio(bat_dau, ket_thuc), so_nguoi=so_nguoi,
            han_chot=f'{han_chot:%d/%m/%Y %H:%M}')
        for nv in Employee.objects.filter(employment_type=EmploymentType.PART_TIME,
                                          status=EmployeeStatus.ACTIVE).select_related('user'):
            tao_thong_bao(nv.user, NotificationType.SCHEDULE, thong_bao.TB_MOI_DANG_KY_CA_TIEU_DE, noi_dung, link)
        ghi_nhat_ky(nguoi_thuc_hien, 'CREATE', 'shift_assignments', None,
                    f'Mở khung ca {vai_tro.strip()} {ngay:%d/%m/%Y}, {so_nguoi} chỗ ({ma_khung})')
    return ma_khung


# Bản đơn giản (2 trạng thái cho mỗi chỗ): TRỐNG (OPEN) ↔ ĐÃ CÓ NGƯỜI (SCHEDULED).
# Nhân viên bấm "Đăng ký" là có ca ngay, không còn bước "giữ chỗ" chờ Quản lý "chốt".
# Quản lý chỉ điều chỉnh khi cần: gán người vào chỗ trống, hoặc gỡ người ra khỏi chỗ.
def _trang_thai_khung(cac_cho, bay_gio):
    """Trạng thái hiển thị của cả khung ca: Đã hủy / Đang mở (còn trong hạn đăng ký) / Đã đóng (quá hạn)."""
    if all(c.status == ShiftStatus.CANCELLED for c in cac_cho):
        return 'DA_HUY'
    return 'DANG_MO' if bay_gio <= cac_cho[0].registration_deadline else 'DA_DONG'


def danh_sach_khung_ca(tu_ngay, den_ngay, bay_gio=None):
    """UC 6.3 – gom các chỗ theo khung ca (slot_group) trong khoảng ngày, kèm số người đã đăng ký và trạng thái khung."""
    bay_gio = bay_gio or datetime.now()
    nhom = {}
    for cho in ShiftAssignment.objects.filter(work_date__range=(tu_ngay, den_ngay)).select_related(
            'employee__user').order_by('work_date', 'planned_start', 'slot_group', 'pk'):
        nhom.setdefault(cho.slot_group, []).append(cho)
    ket_qua = []
    for ma, cac_cho in nhom.items():
        mau = cac_cho[0]
        co_nguoi = [c for c in cac_cho if c.employee_id and c.status == ShiftStatus.SCHEDULED]
        ket_qua.append({
            'ma': ma, 'cac_cho': cac_cho, 'vai_tro': mau.shift_role, 'ngay': mau.work_date, 'bd': mau.planned_start,
            'kt': mau.planned_end, 'han_chot': mau.registration_deadline, 'so_can': len(cac_cho),
            'da_dang_ky': len(co_nguoi), 'thieu': len(cac_cho) - len(co_nguoi), 'nhan_vien': [c.employee for c in co_nguoi],
            'het_han': bay_gio > mau.registration_deadline, 'trang_thai': _trang_thai_khung(cac_cho, bay_gio)})
    return ket_qua


def khung_ca_cua(ma_khung, bay_gio=None):
    """Một khung ca (cùng cấu trúc `danh_sach_khung_ca`) hoặc None nếu mã sai."""
    cac_cho = ShiftAssignment.objects.filter(slot_group=ma_khung)
    if not cac_cho.exists():
        return None
    ngay = cac_cho.first().work_date
    return next((k for k in danh_sach_khung_ca(ngay, ngay, bay_gio) if k['ma'] == ma_khung), None)


def _nhan_cho_trong(ma_cho, nhan_su, bay_gio, nguoi_gan=None):
    """Ghi người vào một chỗ CHỈ KHI chỗ đó còn trống. Trả về True nếu nhận được.

    Điều kiện "còn trống" nằm ngay trong câu UPDATE, nên hai người cùng bấm vào chỗ cuối cùng thì chỉ một người
    ghi được (kết quả 1), người kia nhận 0 và được báo "Ca này đã đủ người"."""
    return ShiftAssignment.objects.filter(pk=ma_cho, employee__isnull=True, status=ShiftStatus.OPEN).update(
        employee=nhan_su, status=ShiftStatus.SCHEDULED, registered_at=bay_gio, assigned_by=nguoi_gan) == 1


def dang_ky_ca(nhan_su, ma_khung, bay_gio=None):
    """UC 6.3 – nhân viên Part-time bấm "Đăng ký": kiểm tra (còn hạn, chưa đăng ký khung này, không trùng giờ)
    rồi nhận một chỗ trống. Ai bấm trước được trước; hết chỗ → "Ca này đã đủ người." Trả về chỗ vừa nhận."""
    bay_gio = bay_gio or datetime.now()
    if not la_part_time_hoat_dong(nhan_su):
        raise KhongCoQuyen(thong_bao.CHI_PART_TIME_DANG_KY)
    cac_cho = list(ShiftAssignment.objects.filter(slot_group=ma_khung).order_by('pk'))
    if not cac_cho:
        raise LoiNghiepVu(thong_bao.KHONG_TIM_THAY_KHUNG_CA)
    mau = cac_cho[0]
    if bay_gio > mau.registration_deadline:
        raise LoiNghiepVu(thong_bao.HET_HAN_DANG_KY_CA)
    if any(c.employee_id == nhan_su.pk and c.status == ShiftStatus.SCHEDULED for c in cac_cho):
        raise LoiNghiepVu(thong_bao.DA_DANG_KY_CA_NAY)
    if kiem_tra_trung_lich(nhan_su, mau.work_date, mau.planned_start, mau.planned_end):
        raise LoiNghiepVu(thong_bao.TRUNG_GIO_VOI_CA)
    for cho in cac_cho:
        if cho.status == ShiftStatus.OPEN and cho.employee_id is None and _nhan_cho_trong(cho.pk, nhan_su, bay_gio):
            ghi_nhat_ky(nhan_su.user, 'UPDATE', 'shift_assignments', cho.pk, 'Đăng ký ca làm việc')
            cho.refresh_from_db()
            return cho
    raise LoiNghiepVu(thong_bao.CA_DA_DU_NGUOI)


def huy_dang_ky_ca(nhan_su, ma_khung, bay_gio=None):
    """UC 6.3 – nhân viên hủy đăng ký TRƯỚC hạn chót → chỗ trở về Trống cho người khác nhận."""
    bay_gio = bay_gio or datetime.now()
    cho = ShiftAssignment.objects.filter(slot_group=ma_khung, employee=nhan_su, status=ShiftStatus.SCHEDULED).first()
    if cho is None:
        raise LoiNghiepVu(thong_bao.CHUA_DANG_KY_CA_NAY)
    if bay_gio > cho.registration_deadline:
        raise LoiNghiepVu(thong_bao.HET_HAN_DANG_KY_CA)
    cho.employee, cho.status, cho.registered_at, cho.assigned_by = None, ShiftStatus.OPEN, None, None
    cho.save(update_fields=['employee', 'status', 'registered_at', 'assigned_by'])
    ghi_nhat_ky(nhan_su.user, 'UPDATE', 'shift_assignments', cho.pk, 'Hủy đăng ký ca làm việc')
    return cho


def _noi_dung_ca(mau_tin, cho, **them):
    return mau_tin.format(vai_tro=cho.shift_role, ngay=f'{cho.work_date:%d/%m/%Y}',
                          gio=_ten_gio(cho.planned_start, cho.planned_end), **them)


def go_nguoi_khoi_cho(nguoi_thuc_hien, cho):
    """UC 6.3 – Quản lý "Gỡ người": chỗ đã có người → Trống, báo nhân viên."""
    if cho.status != ShiftStatus.SCHEDULED or cho.employee_id is None:
        raise LoiNghiepVu(thong_bao.CHO_CHUA_CO_NGUOI)
    nhan_vien = cho.employee
    with transaction.atomic():
        cho.employee, cho.status, cho.registered_at, cho.assigned_by = None, ShiftStatus.OPEN, None, None
        cho.save(update_fields=['employee', 'status', 'registered_at', 'assigned_by'])
        tao_thong_bao(nhan_vien.user, NotificationType.SCHEDULE, thong_bao.TB_KET_QUA_CA_TIEU_DE,
                      _noi_dung_ca(thong_bao.TB_BO_KHOI_CA_NOI_DUNG, cho), reverse('schedule:calendar'))
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'shift_assignments', cho.pk, f'Gỡ {nhan_vien.full_name} khỏi ca')
    return cho


def gan_nhan_vien_vao_cho(nguoi_thuc_hien, cho, nhan_su, bay_gio=None):
    """UC 6.3 – Quản lý "Gán": đưa một nhân viên Part-time vào chỗ trống (có ca ngay), báo nhân viên."""
    bay_gio = bay_gio or datetime.now()
    if cho.status != ShiftStatus.OPEN or cho.employee_id is not None:
        raise LoiNghiepVu(thong_bao.CHO_KHONG_CON_TRONG)
    if not la_part_time_hoat_dong(nhan_su):
        raise LoiTruongNhap(thong_bao.NHAN_VIEN_CA_KHONG_HOP_LE, 'nhan_su')
    if ShiftAssignment.objects.filter(slot_group=cho.slot_group, employee=nhan_su).exists():
        raise LoiTruongNhap(thong_bao.DA_DANG_KY_CA_NAY, 'nhan_su')
    if kiem_tra_trung_lich(nhan_su, cho.work_date, cho.planned_start, cho.planned_end):
        raise LoiTruongNhap(thong_bao.NHAN_VIEN_TRUNG_LICH, 'nhan_su')
    with transaction.atomic():
        if not _nhan_cho_trong(cho.pk, nhan_su, bay_gio, nguoi_gan=nguoi_thuc_hien):
            raise LoiNghiepVu(thong_bao.CHO_KHONG_CON_TRONG)
        cho.refresh_from_db()
        tao_thong_bao(nhan_su.user, NotificationType.SCHEDULE, thong_bao.TB_KET_QUA_CA_TIEU_DE,
                      _noi_dung_ca(thong_bao.TB_KET_QUA_CA_NOI_DUNG, cho), reverse('schedule:calendar'))
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'shift_assignments', cho.pk, f'Gán {nhan_su.full_name} vào ca')
    return cho


def goi_y_nhan_vien_part_time(cho):
    """Danh sách Part-time ACTIVE chưa có chỗ trong khung và không trùng lịch – cho ô chọn "Gán"."""
    bi_trung = tim_nhan_su_trung_lich([cho.work_date], cho.planned_start, cho.planned_end)
    # người đã có chỗ trong CHÍNH khung này cũng nằm trong bi_trung nên tự bị loại
    return [nv for nv in Employee.objects.filter(employment_type=EmploymentType.PART_TIME,
                                                 status=EmployeeStatus.ACTIVE).order_by('full_name')
            if nv.pk not in bi_trung]


# ============================================================ 5. Hàm P5 viết sẵn (UC 3.4, 5.2 gọi sang)
def tao_yeu_cau_day_thay(buoi_day, don_nghi=None):
    """UC 5.2, 3.4: tạo yêu cầu dạy thay (SEARCHING) cho một buổi dạy; mỗi buổi tối đa một yêu cầu đang tìm.

    Gọi lại cho cùng một buổi thì trả về yêu cầu đang có, không tạo trùng (ràng buộc CSDL cũng chặn).
    """
    yeu_cau = SubstituteRequest.objects.filter(teaching_session=buoi_day, status=SubstituteStatus.SEARCHING).first()
    if yeu_cau is None:
        yeu_cau = SubstituteRequest.objects.create(teaching_session=buoi_day, leave_request=don_nghi,
                                                   status=SubstituteStatus.SEARCHING)
    return yeu_cau


def giai_phong_lich_tuong_lai(nhan_su, ngay):
    """UC 3.4 – bước 5–6: xử lý lịch SAU ngày thanh lý của một nhân sự, trong một giao dịch.

    - Phân công lớp còn hiệu lực → đặt end_date = ngày thanh lý.
    - Buổi dạy mà nhân sự là giáo viên thực tế → tạo yêu cầu dạy thay (SEARCHING).
    - Buổi dạy mà nhân sự là trợ giảng → để trống trợ giảng.
    - Chỗ ca làm việc đã có người → trả về OPEN (không còn người nhận).
    Trả về số buổi dạy cần người thay.
    """
    with transaction.atomic():
        ClassAssignment.objects.filter(employee=nhan_su).filter(
            Q(end_date__isnull=True) | Q(end_date__gt=ngay)).update(end_date=ngay)

        buoi_chinh = TeachingSession.objects.filter(
            actual_teacher=nhan_su, session_date__gt=ngay, status=TeachingSessionStatus.SCHEDULED)
        so_buoi_can_thay = 0
        for buoi in buoi_chinh:
            tao_yeu_cau_day_thay(buoi)
            so_buoi_can_thay += 1

        buoi_tro_giang = TeachingSession.objects.filter(
            session_date__gt=ngay, status=TeachingSessionStatus.SCHEDULED).filter(
            Q(actual_assistant=nhan_su) | Q(planned_assistant=nhan_su))
        for buoi in buoi_tro_giang:
            if buoi.actual_assistant_id == nhan_su.pk:
                buoi.actual_assistant = None
            if buoi.planned_assistant_id == nhan_su.pk:
                buoi.planned_assistant = None
            buoi.save(update_fields=['actual_assistant', 'planned_assistant'])

        ShiftAssignment.objects.filter(
            employee=nhan_su, work_date__gt=ngay, status=ShiftStatus.SCHEDULED
        ).update(employee=None, status=ShiftStatus.OPEN, registered_at=None, assigned_by=None)
    return so_buoi_can_thay


# ============================================================ 6. UC 5.2 gọi sang: lịch bị ảnh hưởng bởi đơn nghỉ
def lich_bi_anh_huong(nhan_su, tu_ngay, den_ngay):
    """UC 5.2 – bước 4 và 7: lịch của `nhan_su` bị ảnh hưởng khi nghỉ (cả ngày) từ `tu_ngay` đến `den_ngay`.

    Trả về dict: buoi_chinh (là giáo viên thực tế → cần dạy thay), buoi_tro_giang, ca_lam_viec (ca đã đăng ký).
    Hàm chỉ ĐỌC (§3.2), không sửa bảng nào.
    """
    buoi = TeachingSession.objects.filter(
        session_date__range=(tu_ngay, den_ngay), status=TeachingSessionStatus.SCHEDULED
    ).select_related('study_class').order_by('session_date', 'planned_start')
    buoi_chinh = list(buoi.filter(Q(actual_teacher=nhan_su) | Q(actual_teacher__isnull=True, planned_teacher=nhan_su)))
    buoi_tro_giang = list(buoi.filter(actual_assistant=nhan_su))
    ca = list(ShiftAssignment.objects.filter(
        employee=nhan_su, status=ShiftStatus.SCHEDULED, work_date__range=(tu_ngay, den_ngay)
    ).order_by('work_date', 'planned_start'))
    return {'buoi_chinh': buoi_chinh, 'buoi_tro_giang': buoi_tro_giang, 'ca_lam_viec': ca}


def tra_lich_khi_nghi(nhan_su, anh_huong):
    """UC 5.2 gọi sang khi DUYỆT đơn nghỉ (bản đơn giản, thay cho "đổi trợ giảng" / "đổi người ca" bằng tay):
    - Buổi người này làm trợ giảng → để trống trợ giảng.
    - Ca Part-time người này đã đăng ký → trả chỗ về Trống để Quản lý gán người khác (hoặc người khác tự đăng ký).
    `anh_huong` là kết quả của `lich_bi_anh_huong`. Gọi trong giao dịch của việc duyệt đơn."""
    for buoi in anh_huong['buoi_tro_giang']:
        buoi.actual_assistant = None
        buoi.save(update_fields=['actual_assistant'])
    for cho in anh_huong['ca_lam_viec']:
        cho.employee, cho.status, cho.registered_at = None, ShiftStatus.OPEN, None
        cho.save(update_fields=['employee', 'status', 'registered_at'])


# ============================================================ 7. UC 6.4 – XỬ LÝ DẠY THAY
def _gio_buoi(buoi):
    return _ten_gio(buoi.planned_start, buoi.planned_end)


def yeu_cau_day_thay_dang_tim():
    """UC 6.4 – bước 2: các yêu cầu SEARCHING, buổi gần nhất lên đầu."""
    return SubstituteRequest.objects.filter(status=SubstituteStatus.SEARCHING).select_related(
        'teaching_session__study_class', 'teaching_session__actual_teacher', 'teaching_session__planned_teacher',
        'leave_request__employee').order_by('teaching_session__session_date', 'teaching_session__planned_start')


def giao_vien_vang(yeu_cau):
    """Giáo viên đang được xếp dạy buổi đó (chính là người vắng, vì chưa chốt người thay)."""
    buoi = yeu_cau.teaching_session
    return buoi.actual_teacher or buoi.planned_teacher


def nguon_yeu_cau(yeu_cau):
    """Nguồn phát sinh yêu cầu: đơn nghỉ (UC 5.2) hoặc thanh lý hợp đồng (UC 3.4, không có đơn nghỉ)."""
    return 'Đơn nghỉ phép' if yeu_cau.leave_request_id else 'Thanh lý hợp đồng'


def goi_y_giao_vien_day_thay(yeu_cau):
    """UC 6.4 – bước 4: TEACHER, ACTIVE, khác giáo viên vắng, (Full-time) ca bao trọn giờ buổi dạy,
    không có buổi dạy/ca trùng giờ và không có đơn nghỉ đã duyệt vào ngày đó (các điều kiện này nằm trong
    `goi_y_giao_vien` + `kiem_tra_trung_lich`)."""
    buoi = yeu_cau.teaching_session
    return goi_y_giao_vien([buoi.session_date], buoi.planned_start, buoi.planned_end, loai_tru=giao_vien_vang(yeu_cau))


def chot_day_thay(nguoi_thuc_hien, yeu_cau, giao_vien):
    """UC 6.4 – bước 5–7: trong MỘT giao dịch cập nhật actual_teacher của buổi và hoàn tất yêu cầu (COMPLETED).

    Kiểm tra lại trùng lịch ngay trước khi ghi (luồng 5.3: "Giáo viên bị trùng lịch, vui lòng chọn lại.").
    Báo cho giáo viên dạy thay và giáo viên vắng, ghi nhật ký."""
    if yeu_cau.status != SubstituteStatus.SEARCHING:
        raise LoiNghiepVu(thong_bao.YEU_CAU_DAY_THAY_DA_XU_LY)
    buoi = yeu_cau.teaching_session
    vang = giao_vien_vang(yeu_cau)
    if giao_vien.pk == vang.pk or not giao_vien_du_dieu_kien(giao_vien, buoi.planned_start, buoi.planned_end):
        raise LoiTruongNhap(thong_bao.GIAO_VIEN_KHONG_HOP_LE, 'giao_vien')
    if kiem_tra_trung_lich(giao_vien, buoi.session_date, buoi.planned_start, buoi.planned_end):
        raise LoiTruongNhap(thong_bao.GIAO_VIEN_TRUNG_LICH, 'giao_vien')
    with transaction.atomic():
        buoi.actual_teacher = giao_vien
        buoi.save(update_fields=['actual_teacher'])
        yeu_cau.substitute_employee = giao_vien
        yeu_cau.manager_confirmed_by = nguoi_thuc_hien
        yeu_cau.status = SubstituteStatus.COMPLETED
        yeu_cau.save(update_fields=['substitute_employee', 'manager_confirmed_by', 'status'])
        lop, ngay = buoi.study_class.class_name, f'{buoi.session_date:%d/%m/%Y}'
        tao_thong_bao(giao_vien.user, NotificationType.SCHEDULE, thong_bao.TB_DAY_THAY_TIEU_DE,
                      thong_bao.TB_DAY_THAY_NOI_DUNG.format(lop=lop, ngay=ngay, gio=_gio_buoi(buoi),
                                                            phong=buoi.room_name or 'chưa có', vang=vang.full_name),
                      reverse('schedule:session_detail', args=[buoi.pk]))
        tao_thong_bao(vang.user, NotificationType.SCHEDULE, thong_bao.TB_DAY_THAY_TIEU_DE,
                      thong_bao.TB_DAY_THAY_CHO_VANG_NOI_DUNG.format(lop=lop, ngay=ngay, gio=_gio_buoi(buoi),
                                                                     nguoi=giao_vien.full_name),
                      reverse('schedule:session_detail', args=[buoi.pk]))
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'substitute_requests', yeu_cau.pk,
                    f'Chốt {giao_vien.full_name} dạy thay {lop} {ngay}')
    return yeu_cau


def huy_buoi_hoc(nguoi_thuc_hien, yeu_cau):
    """UC 6.4 – luồng thay thế 5.1: không có người thay → yêu cầu FAILED, buổi dạy CANCELLED (một giao dịch);
    báo giáo viên phụ trách và trợ giảng. (Bản đơn giản: không có "thêm buổi học bù", không có "đổi trợ giảng".)"""
    if yeu_cau.status != SubstituteStatus.SEARCHING:
        raise LoiNghiepVu(thong_bao.YEU_CAU_DAY_THAY_DA_XU_LY)
    buoi = yeu_cau.teaching_session
    with transaction.atomic():
        yeu_cau.status = SubstituteStatus.FAILED
        yeu_cau.manager_confirmed_by = nguoi_thuc_hien
        yeu_cau.save(update_fields=['status', 'manager_confirmed_by'])
        buoi.status = TeachingSessionStatus.CANCELLED
        buoi.save(update_fields=['status'])
        noi_dung = thong_bao.TB_HUY_BUOI_NOI_DUNG.format(lop=buoi.study_class.class_name,
                                                         ngay=f'{buoi.session_date:%d/%m/%Y}', gio=_gio_buoi(buoi))
        nguoi_nhan = {giao_vien_vang(yeu_cau), buoi.planned_teacher}
        if buoi.actual_assistant:
            nguoi_nhan.add(buoi.actual_assistant)
        for nv in nguoi_nhan:
            tao_thong_bao(nv.user, NotificationType.SCHEDULE, thong_bao.TB_HUY_BUOI_TIEU_DE, noi_dung,
                          reverse('schedule:session_detail', args=[buoi.pk]))
        ghi_nhat_ky(nguoi_thuc_hien, 'UPDATE', 'teaching_sessions', buoi.pk, 'Hủy buổi học do không có người dạy thay')
    return buoi


# ============================================================ 8. UC 7.2 gọi sang: số lớp tính phụ cấp (§9.2)
def dem_lop_tinh_phu_cap(nhan_su, thang, nam):
    """§9.2 "Số lớp tính phụ cấp" của giáo viên Full-time trong tháng: số lớp mà `nhan_su` có phân công MAIN_TEACHER còn hiệu
    lực trong tháng (start_date ≤ cuối tháng và end_date trống hoặc ≥ đầu tháng) VÀ lớp có ít nhất một buổi dạy
    không CANCELLED trong tháng. Chỉ ĐỌC (§3.2)."""
    import calendar
    dau, cuoi = date(nam, thang, 1), date(nam, thang, calendar.monthrange(nam, thang)[1])
    cac_lop = ClassAssignment.objects.filter(
        employee=nhan_su, assignment_role=AssignmentRole.MAIN_TEACHER, start_date__lte=cuoi
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=dau)).values_list('study_class_id', flat=True)
    return TeachingSession.objects.filter(
        study_class_id__in=list(cac_lop), session_date__range=(dau, cuoi)
    ).exclude(status=TeachingSessionStatus.CANCELLED).values('study_class_id').distinct().count()


# ============================================================ 7. UC 9.2 – bước 5: cập nhật lịch học hằng ngày
def cap_nhat_lich_hang_ngay(hom_nay):
    """UC 9.2 – bước 5, trong một giao dịch. Trả về dict số bản ghi đã xử lý ở từng việc:
    `that_bai`, `buoi_hoan_thanh`, `lop_bat_dau`, `lop_ket_thuc`.

    Thứ tự quan trọng: xử lý yêu cầu dạy thay quá hạn TRƯỚC khi đánh dấu buổi đã dạy, để buổi không có người thay
    thành CANCELLED chứ không bị tính nhầm là COMPLETED.
    1. Buổi đã qua mà yêu cầu dạy thay còn SEARCHING → yêu cầu FAILED, buổi CANCELLED, báo giáo viên (như UC 6.4 – 5.1).
    2. Buổi SCHEDULED có ngày trước hôm nay → COMPLETED.
    3. Lớp UPCOMING đến ngày bắt đầu → ACTIVE; rồi lớp ACTIVE quá ngày kết thúc → COMPLETED.
    Chạy lại không đổi gì thêm vì mọi điều kiện lọc đều dựa trên trạng thái cũ.
    """
    with transaction.atomic():
        that_bai = 0
        qua_han = SubstituteRequest.objects.filter(
            status=SubstituteStatus.SEARCHING, teaching_session__session_date__lt=hom_nay
        ).select_related('teaching_session__study_class', 'teaching_session__planned_teacher__user',
                         'teaching_session__actual_teacher__user')
        for yeu_cau in qua_han:
            buoi = yeu_cau.teaching_session
            yeu_cau.status = SubstituteStatus.FAILED
            yeu_cau.save(update_fields=['status'])
            if buoi.status == TeachingSessionStatus.SCHEDULED:
                buoi.status = TeachingSessionStatus.CANCELLED
                buoi.save(update_fields=['status'])
            noi_dung = thong_bao.TB_HUY_BUOI_NOI_DUNG.format(lop=buoi.study_class.class_name,
                                                             ngay=f'{buoi.session_date:%d/%m/%Y}', gio=_gio_buoi(buoi))
            nguoi_nhan = {giao_vien_vang(yeu_cau), buoi.planned_teacher}
            if buoi.actual_assistant:
                nguoi_nhan.add(buoi.actual_assistant)
            for nv in nguoi_nhan:
                tao_thong_bao(nv.user, NotificationType.SCHEDULE, thong_bao.TB_HUY_BUOI_TIEU_DE, noi_dung,
                              reverse('schedule:session_detail', args=[buoi.pk]))
            that_bai += 1
        buoi_hoan_thanh = TeachingSession.objects.filter(
            status=TeachingSessionStatus.SCHEDULED, session_date__lt=hom_nay).update(status=TeachingSessionStatus.COMPLETED)
        lop_bat_dau = StudyClass.objects.filter(
            status=ClassStatus.UPCOMING, start_date__lte=hom_nay).update(status=ClassStatus.ACTIVE)
        lop_ket_thuc = StudyClass.objects.filter(
            status=ClassStatus.ACTIVE, end_date__lt=hom_nay).update(status=ClassStatus.COMPLETED)
    return {'that_bai': that_bai, 'buoi_hoan_thanh': buoi_hoan_thanh, 'lop_bat_dau': lop_bat_dau,
            'lop_ket_thuc': lop_ket_thuc}
