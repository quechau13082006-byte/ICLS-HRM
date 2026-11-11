"""Lệnh `python manage.py tao_du_lieu_mau` – P1 (§11). Chạy lại không nhân đôi dữ liệu.

Tạo: 1 SA, 2 QL, 1 KT; 40 nhân sự (QL, KT, GV Full-time Ca 1 / Ca 2 (gồm 4 GV người Hàn), trợ giảng PT, Staff PT)
mỗi người có hợp đồng ACTIVE, cấu hình lương, quỹ phép (Full-time); một đợt tuyển dụng với vài ứng viên;
20 lớp kèm buổi dạy; vài khung ca; chấm công cả tháng trước.
Mật khẩu demo đặt bằng set_password (chỉ khi tạo mới tài khoản).
"""
import calendar
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, UserRole
from attendance.models import Attendance, AttendanceStatus
from contracts.models import Contract
from employees.models import (Department, Employee, EmployeeStatus, EmploymentType, Gender, Position, WorkShift)
from leave.models import LeaveBalance
from payroll.models import SalaryConfig
from recruitment.models import (Candidate, CandidateStatus, RecruitmentCampaign, RecruitmentRound,
                                RecruitmentRoundType)
from leave.models import LeaveRequest
from schedule.models import (AssignmentRole, ClassAssignment, ClassStatus, ShiftAssignment, ShiftStatus,
                             StudyClass, TeachingSession)

MAT_KHAU_DEMO = 'Icls@2026'   # mật khẩu demo cho mọi tài khoản mẫu

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô']
TEN_LOT = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Quốc', 'Thu', 'Hải', 'Thanh']
TEN = ['An', 'Bình', 'Chi', 'Dũng', 'Giang', 'Hà', 'Hạnh', 'Hiếu', 'Hoa', 'Khánh', 'Lan', 'Linh', 'Long',
       'Mai', 'Nam', 'Nga', 'Phúc', 'Quân', 'Sơn', 'Thảo', 'Trang', 'Tuấn', 'Vy', 'Yến', 'Đạt', 'Hùng',
       'Lâm', 'Oanh', 'Tâm', 'Việt', 'Hương', 'Kiên', 'Loan', 'Nhi', 'Phương', 'Quỳnh', 'Trung', 'Uyên', 'Xuân', 'Duy']


# 4 giáo viên người Hàn (bản ngữ): số thứ tự gv -> tên. gv07, gv08 thuộc Ca 1; gv15, gv16 thuộc Ca 2
GIAO_VIEN_HAN_QUOC = {7: 'Kim Min-jun', 8: 'Lee Seo-yeon', 15: 'Park Ji-ho', 16: 'Choi Ha-eun'}


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
        self.stdout.write(self.style.SUCCESS(
            f'Xong. Tài khoản: sa@icls.vn, ql1@icls.vn, ql2@icls.vn, kt@icls.vn, gv01..gv16@icls.vn, '
            f'tg01..tg12@icls.vn, st01..st09@icls.vn. Mật khẩu demo: xem MAT_KHAU_DEMO trong lệnh này.'))
        self.stdout.write(f'Nhân sự: {Employee.objects.count()} · Lớp: {StudyClass.objects.count()} · '
                          f'Buổi dạy: {TeachingSession.objects.count()} · Chấm công: {Attendance.objects.count()}')

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
                employee=employee, contract_number=f'HD{employee.id:04d}', employment_type=loai_hinh,
                start_date=ngay_vao, end_date=None if loai_hinh == EmploymentType.FULL_TIME
                else date(hom_nay.year + 1, 8, 31), file_url='contracts/mau.pdf')
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
        # 16 giáo viên Full-time: 8 Ca 1, 8 Ca 2 (trong đó 4 người Hàn Quốc)
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
        for i in range(20):
            gv = giao_vien[i % 16]
            # Lớp 15, 16 (buổi tối) giao cho gv09, gv10 và học Thứ 3-5-7 thay vì Thứ 2-4-6: nhờ vậy gv15, gv16 (Ca 2) không
            # có lớp tối Thứ 2-4-6, luôn có người rảnh để nhận dạy thay khi giáo viên nghỉ (UC 6.4, kịch bản demo §12.3).
            toi_thu_ba = i in (14, 15)
            if toi_thu_ba:
                gv = giao_vien[i - 6]
            # Ca 1: 09:00–11:00; Ca 2: 18:00–20:00 (đều nằm trọn trong ca của giáo viên)
            gio_bd, gio_kt = ('09:00', '11:00') if gv.work_shift == WorkShift.SHIFT_1 else ('18:00', '20:00')
            thu = '0,2,4' if i < 16 and not toi_thu_ba else '1,3,5'    # giáo viên có 2 lớp thì học khác thứ nên không trùng giờ
            phong = f'P{(i % 8) + 1:02d}' if i < 16 else f'P{(i - 16) + 1:02d}'
            lop, moi = StudyClass.objects.get_or_create(
                class_name=f'Tiếng Hàn {"Sơ cấp" if i % 2 == 0 else "Trung cấp"} – Lớp {i + 1:02d}',
                defaults={'subject': 'Tiếng Hàn Sơ cấp 1' if i % 2 == 0 else 'Tiếng Hàn Trung cấp 1',
                          'room_name': phong, 'max_students': 20, 'weekdays': thu,
                          'start_time': _gio(gio_bd), 'end_time': _gio(gio_kt),
                          'start_date': bat_dau, 'end_date': ket_thuc, 'status': ClassStatus.ACTIVE})
            if not moi:
                continue
            tg = tro_giang[i % 12] if i < 12 else None
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

        # Chờ duyệt: gv01 (Ca 1, có lớp 09:00–11:00 Thứ 2-4-6) nghỉ 2 ngày → ảnh hưởng buổi dạy; gv09 (Ca 2) nghỉ nửa ngày sau ca
        don('gv01@icls.vn', 'ANNUAL', 'FULL_DAY', thu_2_toi, thu_2_toi + timedelta(days=1), 2, 'Giải quyết việc gia đình')
        don('gv09@icls.vn', 'SICK', 'HALF_DAY_PM', thu_2_toi + timedelta(days=2), thu_2_toi + timedelta(days=2), 0.5, 'Khám sức khỏe')
        don('ql1@icls.vn', 'ANNUAL', 'FULL_DAY', thu_2_toi + timedelta(days=3), thu_2_toi + timedelta(days=3), 1, 'Việc cá nhân (chờ Super Admin duyệt)')
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
        """Mỗi nhân viên Part-time (staff) có 2 ca SCHEDULED mỗi tuần, cho tuần này và tuần sau. Chạy lại không nhân đôi."""
        ql1 = User.objects.get(email='ql1@icls.vn')
        thu_hai = hom_nay - timedelta(days=hom_nay.weekday())
        nhan_vien = list(Employee.objects.filter(position=Position.STAFF).order_by('id'))
        for tuan in (0, 1):
            for i, nv in enumerate(nhan_vien):
                for lan, thu in enumerate((i % 6, (i + 3) % 6)):
                    ngay = thu_hai + timedelta(days=7 * tuan + thu)
                    sang = (i + lan) % 2 == 0
                    bd, kt = ('08:00', '12:00') if sang else ('13:00', '17:00')
                    ShiftAssignment.objects.get_or_create(
                        slot_group=f'mau-lich-{nv.id}-{ngay:%Y%m%d}', employee=nv,
                        defaults={'shift_role': 'Lễ tân' if sang else 'Tư vấn', 'work_date': ngay, 'planned_start': _gio(bd),
                                  'planned_end': _gio(kt), 'registration_deadline': datetime.combine(ngay - timedelta(days=3), time(18, 0)),
                                  'registered_at': datetime.combine(ngay - timedelta(days=4), time(9, 0)),
                                  'status': ShiftStatus.SCHEDULED, 'assigned_by': ql1})

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
            bd, kt = ((_gio(x) for x in settings.CA_FULLTIME[e.work_shift][:2]))
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

    # ------------------------------------------------------------------ chấm công tháng trước
    def tao_cham_cong_thang_truoc(self, hom_nay):
        dau_thang_nay = hom_nay.replace(day=1)
        cuoi_thang_truoc = dau_thang_nay - timedelta(days=1)
        thang, nam = cuoi_thang_truoc.month, cuoi_thang_truoc.year
        cac_ngay = [date(nam, thang, d) for d in range(1, calendar.monthrange(nam, thang)[1] + 1)
                    if date(nam, thang, d).weekday() in settings.NGAY_LAM_VIEC]
        # Full-time: một bản ghi mỗi ngày làm việc, không theo ca
        for nv in Employee.objects.filter(employment_type=EmploymentType.FULL_TIME):
            bd, kt, _ = settings.CA_FULLTIME[nv.work_shift]
            for ngay in cac_ngay:
                self._cham_cong(nv, ngay, _gio(bd), _gio(kt), None)
        # Trợ giảng Part-time: 6 ngày đầu, theo buổi dạy (không theo ca)
        for nv in Employee.objects.filter(position=Position.TEACHING_ASSISTANT):
            for ngay in cac_ngay[:6]:
                self._cham_cong(nv, ngay, _gio('18:00'), _gio('20:00'), None)
        # Staff Part-time: 6 ngày, mỗi ngày một ca có chỗ SCHEDULED (theo ca)
        ql1 = User.objects.get(email='ql1@icls.vn')
        for nv in Employee.objects.filter(position=Position.STAFF):
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
