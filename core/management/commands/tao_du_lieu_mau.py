"""Lệnh `python manage.py tao_du_lieu_mau` – P1 (§11). Chạy lại không nhân đôi dữ liệu.

Tạo: 1 SA (kỹ thuật), 1 Giám đốc, 2 QL, 1 KT; 40 nhân sự (QL, KT, GV Full-time Ca 1 / Ca 2 (gồm 11 GV người Hàn), trợ giảng PT, Staff PT)
mỗi người có hợp đồng ACTIVE, cấu hình lương, quỹ phép (Full-time); một đợt tuyển dụng với vài ứng viên;
20 lớp kèm buổi dạy; vài khung ca; chấm công cả tháng trước.
Bổ sung cho demo (tao_du_lieu_demo_bo_sung): giấy tờ ở đủ trạng thái và mức cảnh báo, 2 nhân sự đang Onboarding
(1 từ ứng viên đợt tuyển dụng đã đóng, 1 vị trí Kế toán chờ Super Admin cấp quyền), 1 nhân sự đã nghỉ (hợp đồng thanh lý,
tài khoản bị khóa), 1 hợp đồng đã gia hạn, giải trình của Quản lý chờ Giám đốc, 1 đơn nghỉ đã duyệt kèm yêu cầu dạy thay,
lịch sử cấu hình lương, vài lần đăng nhập thất bại.
Mật khẩu demo đặt bằng set_password (chỉ khi tạo mới tài khoản).
"""
import calendar
import shutil
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, UserRole
from attendance.models import Attendance, AttendanceStatus
from contracts.models import Contract
from contracts.services import so_hop_dong_ke_tiep
from employees.models import (Department, Employee, EmployeeStatus, EmploymentType, Gender, Position, WorkShift)
from leave.models import LeaveBalance
from payroll.models import SalaryConfig
from recruitment.models import (Candidate, CandidateStatus, RecruitmentCampaign, RecruitmentRound,
                                RecruitmentRoundType)
from leave.models import LeaveRequest
from schedule.models import (AssignmentRole, ClassAssignment, ClassStatus, ShiftAssignment, ShiftStatus,
                             StudyClass, TeachingSession)

MAT_KHAU_DEMO = 'Icls@2026'
EMAIL_GIAM_DOC = 'chauhuynhceo@icls.vn'   # tài khoản Giám đốc   # mật khẩu demo cho mọi tài khoản mẫu

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô']
TEN_LOT = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Quốc', 'Thu', 'Hải', 'Thanh']
TEN = ['An', 'Bình', 'Chi', 'Dũng', 'Giang', 'Hà', 'Hạnh', 'Hiếu', 'Hoa', 'Khánh', 'Lan', 'Linh', 'Long',
       'Mai', 'Nam', 'Nga', 'Phúc', 'Quân', 'Sơn', 'Thảo', 'Trang', 'Tuấn', 'Vy', 'Yến', 'Đạt', 'Hùng',
       'Lâm', 'Oanh', 'Tâm', 'Việt', 'Hương', 'Kiên', 'Loan', 'Nhi', 'Phương', 'Quỳnh', 'Trung', 'Uyên', 'Xuân', 'Duy']


# 11/16 giáo viên (~70%) là người Hàn (bản ngữ): số thứ tự gv -> tên. gv01–gv08 thuộc Ca 1; gv09–gv16 thuộc Ca 2.
# gv01–gv03 (dùng trong demo đơn nghỉ) và gv09, gv10 (dạy lớp tối Thứ 3-5-7) giữ là giáo viên Việt Nam.
GIAO_VIEN_HAN_QUOC = {4: 'Jung Do-yoon', 5: 'Kang Min-seo', 6: 'Yoon Ji-woo', 7: 'Kim Min-jun', 8: 'Lee Seo-yeon',
                      11: 'Han Soo-ah', 12: 'Shin Ye-jun', 13: 'Oh Da-eun', 14: 'Seo Joon-ho',
                      15: 'Park Ji-ho', 16: 'Choi Ha-eun'}


# 20 lớp rải đều sáng / chiều / tối và hai nhóm thứ (A = Thứ 2-4-6, B = Thứ 3-5-7):
# (số thứ tự gv, thứ học, giờ bắt đầu, giờ kết thúc, phòng). Giờ học nằm trọn trong ca của giáo viên
# (Ca 1: 08–17 cho gv01–gv08; Ca 2: 13–21 cho gv09–gv16). Không trùng phòng, không trùng giờ của cùng giáo viên.
# gv15, gv16 (Ca 2) không có lớp nên luôn rảnh để nhận dạy thay (UC 6.4, kịch bản demo §12.3).
A, B = '0,2,4', '1,3,5'
KE_HOACH_LOP = [
    (1, A, '08:00', '10:00', 'P01'), (2, B, '08:00', '10:00', 'P01'), (3, A, '14:00', '16:00', 'P02'),
    (4, B, '10:00', '12:00', 'P02'), (5, A, '10:00', '12:00', 'P03'), (6, B, '14:00', '16:00', 'P03'),
    (7, A, '08:00', '10:00', 'P04'), (8, B, '15:00', '17:00', 'P04'), (9, A, '13:30', '15:30', 'P05'),
    (10, B, '13:30', '15:30', 'P05'), (11, A, '15:30', '17:30', 'P06'), (12, B, '18:00', '20:00', 'P06'),
    (13, A, '18:00', '20:00', 'P07'), (14, B, '19:00', '21:00', 'P07'), (9, B, '18:00', '20:00', 'P08'),
    (10, B, '19:00', '21:00', 'P01'), (1, B, '10:00', '12:00', 'P06'), (2, A, '14:00', '16:00', 'P07'),
    (3, B, '08:00', '10:00', 'P08'), (4, A, '15:00', '17:00', 'P08'),
]

# Ca Part-time trong ngày: sáng / chiều / tối, rải đều cho nhân viên Part-time
KHUNG_PART_TIME = [('Lễ tân', '08:00', '12:00'), ('Tư vấn', '13:00', '17:00'), ('Lễ tân', '17:00', '21:00')]


def _ten(i):
    """Tên tiếng Việt cố định theo số thứ tự (để chạy lại ra cùng kết quả)."""
    return f'{HO[i % len(HO)]} {TEN_LOT[i % len(TEN_LOT)]} {TEN[i % len(TEN)]}'


def _gio(chuoi):
    gio, phut = chuoi.split(':')
    return time(int(gio), int(phut))


class Command(BaseCommand):
    help = 'Tạo dữ liệu mẫu để demo (chạy lại không nhân đôi).'

    def handle(self, *args, **options):
        hom_nay = date.today()
        with transaction.atomic():
            self.tao_tai_khoan_va_nhan_su(hom_nay)
            self.dat_han_hop_dong_mau(hom_nay)
            self.tao_tuyen_dung(hom_nay)
            self.tao_lop_va_buoi_day(hom_nay)
            self.tao_khung_ca(hom_nay)
            self.tao_ca_part_time_gan_day(hom_nay)
            self.tao_don_nghi(hom_nay)
            self.tao_cham_cong_loi_thang_nay(hom_nay)
            self.tao_cham_cong_thang_truoc(hom_nay)
            self.tao_lich_su_luong(hom_nay)
            self.tao_du_lieu_demo_bo_sung(hom_nay)
            self.gan_anh_dai_dien()
        self.stdout.write(self.style.SUCCESS(
            f'Xong. Tài khoản: sa@icls.vn, {EMAIL_GIAM_DOC} (Giám đốc), ql1@icls.vn, ql2@icls.vn, kt@icls.vn, gv01..gv16@icls.vn, '
            f'tg01..tg12@icls.vn, st01..st10@icls.vn (st10 đã nghỉ, bị khóa), gv17@icls.vn và kt02@icls.vn (đang Onboarding). '
            f'Mật khẩu demo: xem MAT_KHAU_DEMO trong lệnh này.'))
        self.stdout.write(f'Nhân sự: {Employee.objects.count()} · Lớp: {StudyClass.objects.count()} · '
                          f'Buổi dạy: {TeachingSession.objects.count()} · Chấm công: {Attendance.objects.count()}')

    # ------------------------------------------------------------------ ảnh đại diện mẫu
    def gan_anh_dai_dien(self):
        """Gán 1 trong 16 ảnh ếch (static/img/avatar_mau, nền trắng) làm ảnh đại diện, xoay vòng theo thứ tự tài khoản.
        Chỉ gán cho tài khoản chưa có ảnh (không ghi đè ảnh người dùng đã tải)."""
        nguon = sorted((settings.BASE_DIR / 'static' / 'img' / 'avatar_mau').glob('*.jpg'))
        if not nguon:
            return
        dich = settings.MEDIA_ROOT / 'avatars'
        dich.mkdir(parents=True, exist_ok=True)
        for stt, user in enumerate(User.objects.order_by('id')):
            if user.avatar:
                continue
            anh = nguon[stt % len(nguon)]
            shutil.copyfile(anh, dich / f'mau_{anh.name}')
            user.avatar = f'avatars/mau_{anh.name}'
            user.save(update_fields=['avatar'])

    # ------------------------------------------------------------------ tài khoản, nhân sự
    def _tao_user(self, email, vai_tro, ho_ten, sdt):
        user, moi = User.objects.get_or_create(
            email=email, defaults={'role': vai_tro, 'full_name': ho_ten, 'phone': sdt})
        if moi:
            user.set_password(MAT_KHAU_DEMO)
            user.save()
        return user

    def _tao_nhan_su(self, so_tt, email, vai_tro, chuc_danh, phong_ban, loai_hinh, ca, hom_nay,
                     luong_co_ban=0, phu_cap_lop=0, phu_cap_trach_nhiem=0, ho_ten=None, quoc_tich='Việt Nam'):
        """Tạo user + employee + hợp đồng ACTIVE + cấu hình lương + quỹ phép (Full-time)."""
        ho_ten = ho_ten or _ten(so_tt)
        sdt = f'09{so_tt:08d}'
        user = self._tao_user(email, vai_tro, ho_ten, sdt)
        ngay_vao = date(hom_nay.year - 1, 9, 1)
        employee, moi = Employee.objects.get_or_create(user=user, defaults={
            'full_name': ho_ten, 'phone': sdt,
            'gender': Gender.FEMALE if so_tt % 2 else Gender.MALE,
            'id_card_number': f'0790{so_tt:08d}' if quoc_tich == 'Việt Nam' else None,  # người nước ngoài không có CCCD
            'nationality': quoc_tich, 'department': phong_ban, 'position': chuc_danh,
            'employment_type': loai_hinh, 'work_shift': ca, 'status': EmployeeStatus.ACTIVE,
            'join_date': ngay_vao, 'bank_account': f'Vietcombank – 0123{so_tt:06d}'})
        if moi:
            Contract.objects.create(
                employee=employee, contract_number=so_hop_dong_ke_tiep(loai_hinh, ngay_vao.year), employment_type=loai_hinh,
                start_date=ngay_vao, end_date=None if loai_hinh == EmploymentType.FULL_TIME
                else date(hom_nay.year + 1, 8, 31))   # chưa có file scan: Quản lý tải lên sau khi ký
            SalaryConfig.objects.create(
                employee=employee, base_salary=Decimal(luong_co_ban),
                hourly_rate=Decimal(settings.DON_GIA_GIO_PT_MAC_DINH) if loai_hinh == EmploymentType.PART_TIME else 0,
                class_allowance_rate=Decimal(phu_cap_lop),
                responsibility_allowance=Decimal(phu_cap_trach_nhiem), effective_from=ngay_vao)
            if loai_hinh == EmploymentType.FULL_TIME:
                LeaveBalance.objects.create(employee=employee, year=hom_nay.year,
                                            total_days=settings.PHEP_NAM_MAC_DINH)
        elif employee.nationality != quoc_tich or employee.full_name != ho_ten:
            # Chạy lại trên dữ liệu cũ: cập nhật tên, quốc tịch (vd giáo viên Hàn Quốc thêm sau)
            employee.full_name, employee.nationality = ho_ten, quoc_tich
            if quoc_tich != 'Việt Nam':
                employee.id_card_number = None
            employee.save()
            user.full_name = ho_ten
            user.save()
        return employee

    def tao_tai_khoan_va_nhan_su(self, hom_nay):
        self._tao_user('sa@icls.vn', UserRole.SUPER_ADMIN, 'Super Admin', '0900000000')  # SA không có hồ sơ (Q1)
        # Giám đốc (quản lý cấp cao): duyệt yêu cầu của Quản lý; không có hồ sơ nhân sự như SA.
        self._tao_user(EMAIL_GIAM_DOC, UserRole.DIRECTOR, 'Huỳnh Ngọc Quế Châu', '0905123456')
        ft, pt = EmploymentType.FULL_TIME, EmploymentType.PART_TIME
        so_tt = 1
        # 2 Quản lý, 1 Kế toán (Full-time Ca 1)
        for email in ('ql1@icls.vn', 'ql2@icls.vn'):
            self._tao_nhan_su(so_tt, email, UserRole.MANAGER, Position.MANAGER, Department.HR_ADMIN, ft,
                              WorkShift.SHIFT_1, hom_nay, luong_co_ban=15000000, phu_cap_trach_nhiem=2000000)
            so_tt += 1
        self._tao_nhan_su(so_tt, 'kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, Department.ACCOUNTING,
                          ft, WorkShift.SHIFT_1, hom_nay, luong_co_ban=12000000, phu_cap_trach_nhiem=1000000)
        so_tt += 1
        # 16 giáo viên Full-time: 8 Ca 1, 8 Ca 2 (trong đó 11 người Hàn Quốc, ~70%)
        for i in range(1, 17):
            ca = WorkShift.SHIFT_1 if i <= 8 else WorkShift.SHIFT_2
            ten_han = GIAO_VIEN_HAN_QUOC.get(i)
            self._tao_nhan_su(so_tt, f'gv{i:02d}@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, Department.ACADEMIC,
                              ft, ca, hom_nay, luong_co_ban=12000000 if ten_han else 10000000,
                              phu_cap_lop=400000 if ten_han else 300000,
                              ho_ten=ten_han, quoc_tich='Hàn Quốc' if ten_han else 'Việt Nam')
            so_tt += 1
        # 12 trợ giảng Part-time
        for i in range(1, 13):
            self._tao_nhan_su(so_tt, f'tg{i:02d}@icls.vn', UserRole.EMPLOYEE, Position.TEACHING_ASSISTANT,
                              Department.ACADEMIC, pt, '', hom_nay)
            so_tt += 1
        # 9 staff Part-time (lễ tân, tư vấn)
        for i in range(1, 10):
            self._tao_nhan_su(so_tt, f'st{i:02d}@icls.vn', UserRole.EMPLOYEE, Position.STAFF,
                              Department.HR_ADMIN, pt, '', hom_nay)
            so_tt += 1

    # ------------------------------------------------------------------ hợp đồng sắp hết hạn (để demo UC 3.5)
    def dat_han_hop_dong_mau(self, hom_nay):
        """3 hợp đồng Part-time có hạn gần để trang "Hợp đồng sắp hết hạn" có dữ liệu: quá hạn, dưới 7 ngày, 7–30 ngày.

        Chỉ đổi khi hợp đồng còn giữ hạn mặc định ban đầu (31/08 năm sau), nên chạy lại không đổi thêm.
        """
        mac_dinh = date(hom_nay.year + 1, 8, 31)
        for email, so_ngay in (('st01@icls.vn', -3), ('tg01@icls.vn', 5), ('tg02@icls.vn', 20)):
            Contract.objects.filter(employee__user__email=email, status='ACTIVE', end_date=mac_dinh).update(
                end_date=hom_nay + timedelta(days=so_ngay))

    # ------------------------------------------------------------------ tuyển dụng
    def tao_tuyen_dung(self, hom_nay):
        ql1 = User.objects.get(email='ql1@icls.vn')
        dot, _ = RecruitmentCampaign.objects.get_or_create(
            campaign_name='Tuyển dụng Q4-2026',
            defaults={'start_date': date(hom_nay.year, 10, 1), 'end_date': date(hom_nay.year, 12, 31),
                      'created_by': ql1})
        ung_vien = [
            ('ungvien1@example.com', 'Lê Thu Hương', Position.TEACHER, EmploymentType.FULL_TIME, CandidateStatus.NEW),
            ('ungvien2@example.com', 'Phạm Quốc Việt', Position.TEACHER, EmploymentType.FULL_TIME,
             CandidateStatus.SCREENING),
            ('ungvien3@example.com', 'Trần Ngọc Nhi', Position.TEACHING_ASSISTANT, EmploymentType.PART_TIME,
             CandidateStatus.NEW),
            ('ungvien4@example.com', 'Đỗ Minh Khánh', Position.STAFF, EmploymentType.PART_TIME,
             CandidateStatus.PASSED),
            ('ungvien5@example.com', 'Vũ Thanh Tâm', Position.TEACHER, EmploymentType.FULL_TIME,
             CandidateStatus.REJECTED),
            ('ungvien6@example.com', 'Bùi Phương Thảo', Position.TEACHER, EmploymentType.FULL_TIME,
             CandidateStatus.INTERVIEWING),
            ('ungvien7@example.com', 'Hoàng Đức Nam', Position.TEACHER, EmploymentType.FULL_TIME,
             CandidateStatus.INTERVIEWING),
            ('ungvien8@example.com', 'Lê Khánh Chi', Position.TEACHER, EmploymentType.FULL_TIME,
             CandidateStatus.TEACHING_TRIAL),
        ]
        ql2 = User.objects.get(email='ql2@icls.vn')
        bay_gio = datetime.now().replace(minute=0, second=0, microsecond=0)
        for so_dt, (email, ho_ten, chuc_danh, loai_hinh, trang_thai) in enumerate(ung_vien, start=1):
            uv, moi = Candidate.objects.get_or_create(campaign=dot, email=email, defaults={
                'full_name': ho_ten, 'phone': f'098000000{so_dt}', 'position': chuc_danh,
                'employment_type': loai_hinh, 'status': trang_thai,
                'screening_note': 'Hồ sơ phù hợp yêu cầu' if trang_thai != CandidateStatus.NEW else ''})
            # Vòng tuyển dụng mẫu: ứng viên 6 có lịch phỏng vấn ngày mai, ứng viên 7 đã tới giờ cần đánh giá
            if moi and trang_thai == CandidateStatus.INTERVIEWING:
                RecruitmentRound.objects.create(
                    candidate=uv, round_type=RecruitmentRoundType.INTERVIEW, interviewer=ql2, location='Phòng họp 1',
                    scheduled_at=bay_gio + timedelta(days=1) if so_dt == 6 else bay_gio - timedelta(hours=1))

    # ------------------------------------------------------------------ lớp học, buổi dạy
    def tao_lop_va_buoi_day(self, hom_nay):
        giao_vien = list(Employee.objects.filter(position=Position.TEACHER).order_by('id'))
        tro_giang = list(Employee.objects.filter(position=Position.TEACHING_ASSISTANT).order_by('id'))
        bat_dau = hom_nay.replace(day=1)
        ket_thuc = bat_dau + timedelta(days=60)
        so_tg = 0
        for i, (so_gv, thu, gio_bd, gio_kt, phong) in enumerate(KE_HOACH_LOP):
            gv = giao_vien[so_gv - 1]
            lop, moi = StudyClass.objects.get_or_create(
                class_name=f'Tiếng Hàn {"Sơ cấp" if i % 2 == 0 else "Trung cấp"} – Lớp {i + 1:02d}',
                defaults={'subject': 'Tiếng Hàn Sơ cấp 1' if i % 2 == 0 else 'Tiếng Hàn Trung cấp 1',
                          'room_name': phong, 'max_students': 20, 'weekdays': thu,
                          'start_time': _gio(gio_bd), 'end_time': _gio(gio_kt),
                          'start_date': bat_dau, 'end_date': ket_thuc, 'status': ClassStatus.ACTIVE})
            if not moi:
                continue
            # Chỉ lớp có giáo viên người Hàn mới có trợ giảng
            tg = None
            if gv.nationality == 'Hàn Quốc':
                tg = tro_giang[so_tg % len(tro_giang)]
                so_tg += 1
            ClassAssignment.objects.create(study_class=lop, employee=gv, assignment_role=AssignmentRole.MAIN_TEACHER,
                                           start_date=bat_dau)
            if tg:
                ClassAssignment.objects.create(study_class=lop, employee=tg,
                                               assignment_role=AssignmentRole.TEACHING_ASSISTANT, start_date=bat_dau)
            cac_thu = {int(x) for x in thu.split(',')}
            buoi = []
            ngay = bat_dau
            while ngay <= ket_thuc:
                if ngay.weekday() in cac_thu:
                    buoi.append(TeachingSession(
                        study_class=lop, session_date=ngay, planned_start=lop.start_time, planned_end=lop.end_time,
                        room_name=phong, planned_teacher=gv, actual_teacher=gv,
                        planned_assistant=tg, actual_assistant=tg))
                ngay += timedelta(days=1)
            TeachingSession.objects.bulk_create(buoi)

    # ------------------------------------------------------------------ khung ca Part-time
    def tao_khung_ca(self, hom_nay):
        if ShiftAssignment.objects.filter(slot_group__startswith='khung-mau-').exists():
            return
        ngay_mai = hom_nay + timedelta(days=1)
        if ngay_mai.weekday() == 6:      # Chủ nhật nghỉ
            ngay_mai += timedelta(days=1)
        han_dang_ky = datetime.combine(ngay_mai - timedelta(days=1), time(18, 0))
        for ten_khung, vai_tro_ca, so_cho, bd, kt in [
            ('le-tan', 'Lễ tân', 2, '08:00', '12:00'), ('tu-van', 'Tư vấn', 1, '13:00', '17:00')]:
            ma_khung = f'khung-mau-{ten_khung}-{uuid.uuid4().hex[:8]}'
            for _ in range(so_cho):
                ShiftAssignment.objects.create(
                    slot_group=ma_khung, shift_role=vai_tro_ca, work_date=ngay_mai, planned_start=_gio(bd),
                    planned_end=_gio(kt), registration_deadline=han_dang_ky, status=ShiftStatus.OPEN)


    # ------------------------------------------------------------------ đơn nghỉ phép (UC 5, để demo duyệt đơn và dạy thay)
    def tao_don_nghi(self, hom_nay):
        """Vài đơn nghỉ ở đủ trạng thái. Chạy lại không nhân đôi (đã có đơn nào thì bỏ qua)."""
        if LeaveRequest.objects.exists():
            return
        thu_2_toi = hom_nay + timedelta(days=7 - hom_nay.weekday())     # Thứ 2 của tuần sau
        nv = lambda email: Employee.objects.get(user__email=email)

        def don(email, loai, hinh_thuc, tu, den, so_ngay, ly_do, trang_thai='PENDING', ghi_chu=''):
            return LeaveRequest.objects.create(
                employee=nv(email), leave_type=loai, duration_type=hinh_thuc, start_date=tu, end_date=den,
                total_days=so_ngay, reason=ly_do, status=trang_thai, review_note=ghi_chu)

        # Chờ duyệt: gv01 (Ca 1, có lớp 09:00–11:00 Thứ 2-4-6) nghỉ 2 ngày → ảnh hưởng buổi dạy; gv03 (Ca 1) nghỉ buổi chiều
        # (nửa ngày chia theo ca: Ca 1 ở 12:00, Ca 2 ở 17:00 – gv09 Ca 2 nghỉ nửa sau 17:00–21:00)
        don('gv01@icls.vn', 'ANNUAL', 'FULL_DAY', thu_2_toi, thu_2_toi + timedelta(days=1), 2, 'Giải quyết việc gia đình')
        don('gv03@icls.vn', 'SICK', 'HALF_DAY_PM', thu_2_toi + timedelta(days=2), thu_2_toi + timedelta(days=2), 0.5, 'Khám sức khỏe')
        don('gv09@icls.vn', 'ANNUAL', 'HALF_DAY_PM', thu_2_toi + timedelta(days=1), thu_2_toi + timedelta(days=1), 0.5, 'Đi khám răng buổi tối')
        don('ql1@icls.vn', 'ANNUAL', 'FULL_DAY', thu_2_toi + timedelta(days=3), thu_2_toi + timedelta(days=3), 1, 'Việc cá nhân (chờ Giám đốc duyệt)')
        # Đã duyệt (đã trừ quỹ phép) và Từ chối (kèm lý do) trong quá khứ gần
        qua_khu = hom_nay - timedelta(days=14)
        qua_khu -= timedelta(days=qua_khu.weekday())                      # Thứ 2 cách đây ~2 tuần
        da_duyet = don('gv02@icls.vn', 'ANNUAL', 'FULL_DAY', qua_khu, qua_khu + timedelta(days=1), 2, 'Nghỉ phục hồi sức khỏe', 'APPROVED')
        quy = LeaveBalance.objects.filter(employee=da_duyet.employee, year=da_duyet.start_date.year).first()
        if quy:
            quy.used_days += 2
            quy.save(update_fields=['used_days'])
        don('gv03@icls.vn', 'ANNUAL', 'FULL_DAY', qua_khu + timedelta(days=2), qua_khu + timedelta(days=2), 1, 'Việc cá nhân',
            'REJECTED', 'Trùng đợt kiểm tra cuối khóa')


    # ------------------------------------------------------------------ ca Part-time đã chốt quanh hôm nay (để tab Lịch làm việc có dữ liệu)
    def tao_ca_part_time_gan_day(self, hom_nay):
        """Ca SCHEDULED cho tuần này và tuần sau (chạy lại không nhân đôi):
        - Mỗi nhân viên Part-time (staff) 2 ca/tuần, khác ngày và khác buổi (sáng/chiều/tối), xoay vòng theo tuần
          → mỗi ngày đều có người trực ở cả ba buổi, không dồn sáng hết rồi chiều hết.
        - Trợ giảng cũng là Part-time nên được đăng ký thêm ca: vài trợ giảng có 1 ca/tuần, chọn ngày KHÔNG có buổi trợ giảng
          (giống luật đăng ký ca thật: không được trùng giờ buổi dạy)."""
        from schedule.services import tim_nhan_su_trung_lich
        ql1 = User.objects.get(email='ql1@icls.vn')
        thu_hai = hom_nay - timedelta(days=hom_nay.weekday())
        nhan_vien = list(Employee.objects.filter(position=Position.STAFF, status=EmployeeStatus.ACTIVE).order_by('id'))
        tro_giang = list(Employee.objects.filter(position=Position.TEACHING_ASSISTANT, status=EmployeeStatus.ACTIVE).order_by('id'))

        def tao_ca(nv, ngay, khung):
            vai_tro, bd, kt = KHUNG_PART_TIME[khung]
            if nv.pk in tim_nhan_su_trung_lich([ngay], _gio(bd), _gio(kt)):
                return False
            ShiftAssignment.objects.get_or_create(
                slot_group=f'mau-lich-{nv.id}-{ngay:%Y%m%d}', employee=nv,
                defaults={'shift_role': vai_tro, 'work_date': ngay, 'planned_start': _gio(bd), 'planned_end': _gio(kt),
                          'registration_deadline': datetime.combine(ngay - timedelta(days=3), time(18, 0)),
                          'registered_at': datetime.combine(ngay - timedelta(days=4), time(9, 0)),
                          'status': ShiftStatus.SCHEDULED, 'assigned_by': ql1})
            return True

        for tuan in (0, 1):
            dau_tuan = thu_hai + timedelta(days=7 * tuan)
            # 9 người × 2 ca = 18 = 6 ngày × 3 buổi: ô (ngày d, buổi k) giao cho người (2d + 3k + tuần) mod 9
            for d in range(6):
                for k in range(3):
                    nv = nhan_vien[(2 * d + 3 * k + tuan) % len(nhan_vien)]
                    tao_ca(nv, dau_tuan + timedelta(days=d), k)
            # 6 trợ giảng đăng ký thêm 1 ca/tuần (thử lần lượt các ngày, bỏ ngày trùng buổi dạy)
            for j, tg in enumerate(tro_giang[::2]):
                for lech in range(6):
                    if tao_ca(tg, dau_tuan + timedelta(days=(j + tuan + lech) % 6), (j + tuan) % 3):
                        break

    # ------------------------------------------------------------------ chấm công lỗi tháng này (UC 4.2 – 4.5)
    def tao_cham_cong_loi_thang_nay(self, hom_nay):
        """Vài bản ghi lỗi ở các ngày làm việc đã qua của THÁNG NÀY để demo giải trình, duyệt, tổng hợp công.
        Ghi đè bản ghi cùng (nhân sự, ngày) nên chạy lại không nhân đôi; bỏ qua nếu chưa có ngày làm việc nào trong tháng."""
        ngay_lam = [hom_nay.replace(day=d) for d in range(1, hom_nay.day)
                    if hom_nay.replace(day=d).weekday() in settings.NGAY_LAM_VIEC]
        if len(ngay_lam) < 3:
            return
        nv = lambda email: Employee.objects.get(user__email=email)

        def ghi(email, ngay, trang_thai, **truong):
            e = nv(email)
            bd, kt = (_gio(x) for x in settings.CA_FULLTIME[e.work_shift])
            vao = datetime.combine(ngay, bd) + timedelta(minutes=truong.pop('tre', 0))
            ra = None if trang_thai in ('MISSING_CHECKOUT', 'ABSENT') else datetime.combine(ngay, kt) - timedelta(minutes=truong.get('early_leave_minutes', 0))
            Attendance.objects.update_or_create(
                employee=e, work_date=ngay, shift_assignment=None,
                defaults={'planned_start': bd, 'planned_end': kt, 'check_in': None if trang_thai == 'ABSENT' else vao, 'check_out': ra,
                          'attendance_status': trang_thai, 'late_minutes': (vao - datetime.combine(ngay, bd)).seconds // 60 if trang_thai == 'LATE' else 0, **truong})

        # gv01: đi trễ 35 phút, ĐÃ giải trình (chờ Quản lý duyệt) · gv09: về sớm 20 phút, chưa giải trình
        # gv02: quên check-out, chưa giải trình · gv10: đi trễ 12 phút, chưa giải trình
        ghi('gv01@icls.vn', ngay_lam[0], 'LATE', tre=35, explanation_status='PENDING',
            explanation_reason='Xe hỏng giữa đường nên phải dừng sửa chữa, đã báo lễ tân trước giờ học.')
        ghi('gv09@icls.vn', ngay_lam[1], 'EARLY_LEAVE', early_leave_minutes=20)
        ghi('gv02@icls.vn', ngay_lam[1], 'MISSING_CHECKOUT')
        ghi('gv10@icls.vn', ngay_lam[2], 'LATE', tre=12)
        # ql2 (Quản lý): đi trễ, ĐÃ giải trình → chỉ Giám đốc duyệt được (Quản lý không tự duyệt cho nhau)
        ghi('ql2@icls.vn', ngay_lam[2], 'LATE', tre=25, explanation_status='PENDING',
            explanation_reason='Đi gặp đối tác trường Đại học Ngoại ngữ về chương trình liên kết, đã báo Giám đốc từ hôm trước.')

    # ------------------------------------------------------------------ chấm công tháng trước
    def tao_cham_cong_thang_truoc(self, hom_nay):
        cuoi_thang_truoc = hom_nay.replace(day=1) - timedelta(days=1)
        self._cham_cong_ca_thang(cuoi_thang_truoc.month, cuoi_thang_truoc.year)

    # ------------------------------------------------------------------ lịch sử lương (3 tháng đã phát hành)
    def tao_lich_su_luong(self, hom_nay, so_thang=3):
        """Chấm công + bảng lương ĐÃ PHÁT HÀNH cho `so_thang` tháng trước tháng vừa rồi, để có dữ liệu trang Lịch sử lương.
        Tháng vừa rồi vẫn để trống cho Kế toán demo "Khởi tạo bảng lương" (UC 7.2). Chạy lại: tháng nào có rồi thì bỏ qua."""
        from payroll.models import Payroll, PayrollDetailCategory
        from payroll import services as luong
        kt = User.objects.get(email='kt@icls.vn')
        dau = hom_nay.replace(day=1)
        cac_thang = []
        for _ in range(so_thang + 1):
            dau = (dau - timedelta(days=1)).replace(day=1)
            cac_thang.append((dau.month, dau.year))
        for thang, nam in reversed(cac_thang[1:]):                 # bỏ tháng vừa rồi, làm từ tháng cũ nhất
            if Payroll.objects.filter(period_month=thang, period_year=nam).exists():
                continue
            self._cham_cong_ca_thang(thang, nam)
            cac_bang = luong.khoi_tao_bang_luong(kt, thang, nam, hom_nay)
            for bang in cac_bang[::5]:                             # thưởng cho vài người để các tháng chênh nhau
                luong.them_khoan_thu_cong(kt, bang, PayrollDetailCategory.BONUS, '', 'Thưởng hiệu suất',
                                          Decimal(300_000 + 100_000 * (thang % 4)))
            luong.chot_va_phat_hanh(kt, thang, nam, datetime.combine(date(nam, thang, 1) + timedelta(days=35), time(9)))
        # Phiếu lương các tháng cũ coi như đã xem, để chuông thông báo không bị dồn 3 × 40 tin
        from core.models import Notification, NotificationType
        Notification.objects.filter(notification_type=NotificationType.PAYROLL).update(is_read=True)

    def _cham_cong_ca_thang(self, thang, nam):
        cac_ngay = [date(nam, thang, d) for d in range(1, calendar.monthrange(nam, thang)[1] + 1)
                    if date(nam, thang, d).weekday() in settings.NGAY_LAM_VIEC]
        # Full-time: một bản ghi mỗi ngày làm việc, không theo ca
        for nv in Employee.objects.filter(employment_type=EmploymentType.FULL_TIME, status=EmployeeStatus.ACTIVE):
            bd, kt = settings.CA_FULLTIME[nv.work_shift]
            for ngay in cac_ngay:
                self._cham_cong(nv, ngay, _gio(bd), _gio(kt), None)
        # Trợ giảng Part-time: 6 ngày đầu, theo buổi dạy (không theo ca)
        for nv in Employee.objects.filter(position=Position.TEACHING_ASSISTANT, status=EmployeeStatus.ACTIVE):
            for ngay in cac_ngay[:6]:
                self._cham_cong(nv, ngay, _gio('18:00'), _gio('20:00'), None)
        # Staff Part-time: 6 ngày, mỗi ngày một ca có chỗ SCHEDULED (theo ca)
        ql1 = User.objects.get(email='ql1@icls.vn')
        for nv in Employee.objects.filter(position=Position.STAFF, status=EmployeeStatus.ACTIVE):
            for ngay in cac_ngay[:6]:
                ca, _ = ShiftAssignment.objects.get_or_create(
                    slot_group=f'mau-{nv.id}-{ngay:%Y%m%d}', employee=nv,
                    defaults={'shift_role': 'Lễ tân', 'work_date': ngay, 'planned_start': _gio('08:00'),
                              'planned_end': _gio('12:00'),
                              'registration_deadline': datetime.combine(ngay - timedelta(days=2), time(18, 0)),
                              'registered_at': datetime.combine(ngay - timedelta(days=3), time(9, 0)),
                              'status': ShiftStatus.SCHEDULED, 'assigned_by': ql1})
                self._cham_cong(nv, ngay, ca.planned_start, ca.planned_end, ca)

    def _cham_cong(self, nv, ngay, bd, kt, ca):
        """Một bản ghi chấm công; thỉnh thoảng đi trễ 10 phút để có dữ liệu LATE."""
        tre = (nv.id + ngay.day) % 11 == 0
        gio_vao = datetime.combine(ngay, bd) + timedelta(minutes=10 if tre else 0)
        dieu_kien = {'employee': nv, 'shift_assignment': ca}
        if ca is None:
            dieu_kien['work_date'] = ngay
        Attendance.objects.get_or_create(**dieu_kien, defaults={
            'work_date': ngay, 'planned_start': bd, 'planned_end': kt, 'check_in': gio_vao,
            'check_out': datetime.combine(ngay, kt), 'late_minutes': 10 if tre else 0,
            'attendance_status': AttendanceStatus.LATE if tre else AttendanceStatus.ON_TIME})


    # ================================================================== bổ sung dữ liệu cho đủ kịch bản demo
    def tao_du_lieu_demo_bo_sung(self, hom_nay):
        """Mỗi phần tự kiểm tra đã có dữ liệu chưa, nên chạy lại không nhân đôi."""
        self.tao_giay_to(hom_nay)
        self.tao_onboarding(hom_nay)
        self.tao_nhan_su_da_nghi(hom_nay)
        self.tao_gia_han_hop_dong(hom_nay)
        self.tao_yeu_cau_day_thay(hom_nay)
        self.tao_lich_su_cau_hinh_luong(hom_nay)
        self.tao_dang_nhap_that_bai()

    @staticmethod
    def _file_pdf(ten):
        """File PDF một trang trắng làm bản scan giả cho giấy tờ mẫu."""
        from django.core.files.base import ContentFile
        noi_dung = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
                    b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n')
        return ContentFile(noi_dung, name=ten)

    # ------------------------------------------------------------------ giấy tờ, chứng chỉ (UC 2.2, 2.4, 2.6, 9.2)
    def tao_giay_to(self, hom_nay):
        """Đủ trạng thái và mức cảnh báo:
        - APPROVED còn hạn dài (CCCD, TOPIK) · APPROVED sắp hết hạn (còn 10 ngày, 25 ngày) · EXPIRED (quá hạn 5 ngày)
        - PENDING của Nhân viên (Quản lý duyệt) và của Quản lý (Giám đốc duyệt) · REJECTED kèm lý do (nhân viên tải lại)."""
        from employees.models import DocumentType, EmployeeDocument
        from employees.services import duyet_giay_to, het_han_giay_to, luu_ho_so_ca_nhan, tu_choi_giay_to
        if EmployeeDocument.objects.exists():
            return
        ql1 = User.objects.get(email='ql1@icls.vn')
        nv = lambda email: Employee.objects.get(user__email=email)
        nam_truoc = hom_nay - timedelta(days=365)

        def nop(email, loai, ten, ngay_cap, ngay_het_han):
            e = nv(email)
            return luu_ho_so_ca_nhan(e, e.phone, e.address, e.bank_account, giay_to={
                'document_type': loai, 'document_name': ten, 'issue_date': ngay_cap, 'expiry_date': ngay_het_han,
                'file_url': self._file_pdf(f'{email.split("@")[0]}_{loai.lower()}.pdf')})

        for email in ('gv01@icls.vn', 'gv02@icls.vn', 'gv03@icls.vn', 'tg01@icls.vn'):
            duyet_giay_to(ql1, nop(email, DocumentType.PERSONAL_ID, 'Căn cước công dân', date(hom_nay.year - 3, 5, 10),
                                   date(hom_nay.year + 12, 5, 10)))
        duyet_giay_to(ql1, nop('gv07@icls.vn', DocumentType.CERTIFICATION, 'TOPIK cấp 6', nam_truoc, nam_truoc + timedelta(days=730)))
        duyet_giay_to(ql1, nop('gv04@icls.vn', DocumentType.CERTIFICATION, 'Chứng chỉ giảng dạy tiếng Hàn (KLTC)',
                               hom_nay - timedelta(days=720), hom_nay + timedelta(days=10)))          # sắp hết hạn: < 30 ngày
        duyet_giay_to(ql1, nop('gv05@icls.vn', DocumentType.CERTIFICATION, 'TOPIK cấp 5',
                               hom_nay - timedelta(days=705), hom_nay + timedelta(days=25)))          # sắp hết hạn: < 30 ngày
        duyet_giay_to(ql1, nop('gv06@icls.vn', DocumentType.CERTIFICATION, 'Chứng chỉ nghiệp vụ sư phạm',
                               hom_nay - timedelta(days=735), hom_nay - timedelta(days=5)))           # đã quá hạn
        het_han_giay_to(hom_nay)                                                                      # như tác vụ hằng ngày
        # Chờ duyệt: của Nhân viên → Quản lý duyệt; của Quản lý → Giám đốc duyệt
        nop('gv11@icls.vn', DocumentType.CERTIFICATION, 'TOPIK cấp 6', hom_nay - timedelta(days=20), hom_nay + timedelta(days=710))
        nop('tg03@icls.vn', DocumentType.PERSONAL_ID, 'Căn cước công dân', date(hom_nay.year - 2, 8, 1), date(hom_nay.year + 15, 8, 1))
        nop('ql2@icls.vn', DocumentType.OTHER, 'Bằng Thạc sĩ Quản trị nhân lực', date(hom_nay.year - 2, 6, 30), None)
        # Bị từ chối: nhân viên thấy lý do và bấm "Tải bản mới"
        tu_choi_giay_to(ql1, nop('gv12@icls.vn', DocumentType.CERTIFICATION, 'Chứng chỉ nghiệp vụ sư phạm',
                                 hom_nay - timedelta(days=100), None),
                        'Ảnh chụp bị mờ, không đọc được số hiệu chứng chỉ. Vui lòng tải bản scan rõ hơn.')

    # ------------------------------------------------------------------ nhân sự đang Onboarding (UC 2.5, 3.1, 1.5)
    def tao_onboarding(self, hom_nay):
        """gv17: tiếp nhận từ ứng viên PASSED của đợt tuyển dụng ĐÃ ĐÓNG (ứng viên → HIRED), chờ Quản lý tạo hợp đồng.
        kt02: vị trí Kế toán nhưng tài khoản tạo ra là Nhân viên → Super Admin nhận thông báo "Yêu cầu cấp quyền"."""
        from employees.services import tao_ho_so_nhan_su
        from recruitment.models import CampaignStatus
        if User.objects.filter(email__in=['gv17@icls.vn', 'kt02@icls.vn']).exists():
            return
        ql1 = User.objects.get(email='ql1@icls.vn')
        dot_cu, _ = RecruitmentCampaign.objects.get_or_create(
            campaign_name='Tuyển dụng Q3-2026', defaults={
                'start_date': date(hom_nay.year, 7, 1), 'end_date': date(hom_nay.year, 9, 30),
                'status': CampaignStatus.CLOSED, 'created_by': ql1})
        Candidate.objects.get_or_create(campaign=dot_cu, email='ungvien10@example.com', defaults={
            'full_name': 'Phan Gia Bảo', 'phone': '0980000010', 'position': Position.TEACHER,
            'employment_type': EmploymentType.FULL_TIME, 'status': CandidateStatus.REJECTED,
            'screening_note': 'Chưa đạt yêu cầu phát âm ở vòng phỏng vấn'})
        uv, _ = Candidate.objects.get_or_create(campaign=dot_cu, email='gv17@icls.vn', defaults={
            'full_name': 'Nguyễn Hoài An', 'phone': '0980000009', 'position': Position.TEACHER,
            'employment_type': EmploymentType.FULL_TIME, 'status': CandidateStatus.PASSED,
            'screening_note': 'TOPIK cấp 6, 2 năm kinh nghiệm dạy tiếng Hàn'})
        chung = {'mat_khau': MAT_KHAU_DEMO, 'nationality': 'Việt Nam', 'join_date': hom_nay, 'address': 'Đà Nẵng'}
        tao_ho_so_nhan_su(ql1, {**chung, 'email': 'gv17@icls.vn', 'full_name': 'Nguyễn Hoài An', 'phone': '0980000009',
                                'gender': Gender.FEMALE, 'date_of_birth': date(1998, 3, 12), 'id_card_number': '079098001234',
                                'department': Department.ACADEMIC, 'position': Position.TEACHER,
                                'employment_type': EmploymentType.FULL_TIME, 'work_shift': WorkShift.SHIFT_2,
                                'bank_account': 'Vietcombank – 0123000171'}, ung_vien=uv, hom_nay=hom_nay)
        tao_ho_so_nhan_su(ql1, {**chung, 'email': 'kt02@icls.vn', 'full_name': 'Trịnh Thu Trang', 'phone': '0980000011',
                                'gender': Gender.FEMALE, 'date_of_birth': date(1996, 11, 2), 'id_card_number': '079096005678',
                                'department': Department.ACCOUNTING, 'position': Position.ACCOUNTANT,
                                'employment_type': EmploymentType.FULL_TIME, 'work_shift': WorkShift.SHIFT_1,
                                'bank_account': 'Techcombank – 1903000112'}, hom_nay=hom_nay)

    # ------------------------------------------------------------------ nhân sự đã nghỉ (UC 3.4, 1.1, 1.5, 2.1)
    def tao_nhan_su_da_nghi(self, hom_nay):
        """st10: thanh lý hợp đồng 10 ngày trước bằng đúng hàm UC 3.4 → nhân sự RESIGNED, hợp đồng TERMINATED,
        tài khoản bị khóa (đăng nhập sẽ báo "Tài khoản của bạn đã bị khóa…"), cấu hình lương được đóng."""
        from contracts.services import thanh_ly_hop_dong
        if User.objects.filter(email='st10@icls.vn').exists():
            return
        e = self._tao_nhan_su(50, 'st10@icls.vn', UserRole.EMPLOYEE, Position.STAFF, Department.HR_ADMIN,
                              EmploymentType.PART_TIME, '', hom_nay, ho_ten='Lý Minh Thư')
        thanh_ly_hop_dong(User.objects.get(email='ql1@icls.vn'), e.contracts.get(status='ACTIVE'),
                          hom_nay - timedelta(days=10), 'Nhân viên xin nghỉ để đi du học', EmployeeStatus.RESIGNED, hom_nay)

    # ------------------------------------------------------------------ hợp đồng đã gia hạn (UC 3.2, 3.3)
    def tao_gia_han_hop_dong(self, hom_nay):
        """tg03: hợp đồng đầu EXPIRED, hợp đồng gia hạn ACTIVE trỏ previous_contract về hợp đồng cũ (xem lịch sử gia hạn)."""
        e = Employee.objects.get(user__email='tg03@icls.vn')
        if Contract.objects.filter(employee=e).count() > 1:
            return
        cu = Contract.objects.get(employee=e, status='ACTIVE')
        moc = hom_nay - timedelta(days=45)
        cu.end_date, cu.status = moc, 'EXPIRED'
        cu.save(update_fields=['end_date', 'status'])
        Contract.objects.create(
            employee=e, contract_number=so_hop_dong_ke_tiep(EmploymentType.PART_TIME, moc.year),
            employment_type=EmploymentType.PART_TIME, start_date=moc + timedelta(days=1),
            end_date=date(hom_nay.year + 1, 8, 31), previous_contract=cu, status='ACTIVE')

    # ------------------------------------------------------------------ đơn nghỉ đã duyệt có buổi cần dạy thay (UC 5.2, 6.4)
    def tao_yeu_cau_day_thay(self, hom_nay):
        """gv05 (giáo viên Hàn, lớp Thứ 2-4-6 10:00–12:00 có trợ giảng) nghỉ ốm Thứ 2 cách 2 tuần; gửi và duyệt bằng đúng hàm
        UC 5.1 / 5.2 → hệ thống tự tạo yêu cầu dạy thay SEARCHING, bỏ trợ giảng buổi đó, báo Quản lý."""
        from leave.services import duyet_don_nghi, gui_don_nghi
        from schedule.models import SubstituteRequest
        if SubstituteRequest.objects.exists():
            return
        gv = Employee.objects.get(user__email='gv05@icls.vn')
        thu_2 = hom_nay + timedelta(days=14 - hom_nay.weekday())
        don = gui_don_nghi(gv, 'SICK', 'FULL_DAY', thu_2, thu_2, 'Tiểu phẫu, bác sĩ yêu cầu nghỉ một ngày')
        duyet_don_nghi(User.objects.get(email='ql1@icls.vn'), don)

    # ------------------------------------------------------------------ lịch sử cấu hình lương (UC 7.1)
    def tao_lich_su_cau_hinh_luong(self, hom_nay):
        """gv01 được tăng lương từ đầu tháng này: cấu hình cũ tự đóng (effective_to), cấu hình mới đang áp dụng."""
        from payroll.services import luu_cau_hinh_luong
        gv = Employee.objects.get(user__email='gv01@icls.vn')
        if SalaryConfig.objects.filter(employee=gv).count() > 1:
            return
        luu_cau_hinh_luong(User.objects.get(email='kt@icls.vn'), gv, Decimal(10_800_000), Decimal(0),
                           Decimal(350_000), Decimal(0), hom_nay.replace(day=1))

    # ------------------------------------------------------------------ đăng nhập thất bại (Dashboard Super Admin)
    def tao_dang_nhap_that_bai(self):
        from core.models import ActivityLog
        from core.services import ghi_nhat_ky
        if ActivityLog.objects.filter(action='LOGIN_FAILED').exists():
            return
        for email in ('gv02@icls.vn', 'khong-ton-tai@icls.vn', 'st10@icls.vn'):
            ghi_nhat_ky(None, 'LOGIN_FAILED', 'User', None, f'Đăng nhập thất bại: {email}')
