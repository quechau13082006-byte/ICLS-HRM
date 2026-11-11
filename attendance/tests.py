"""Test của app attendance – P1: các ràng buộc CSDL (§7.3.12)."""
from datetime import date, datetime, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from attendance.models import Attendance
from core.mau_test import tao_nhan_su
from schedule.models import ShiftAssignment


class RangBuocAttendanceTest(TestCase):
    def _cc(self, nv, ca=None, ngay=date(2026, 10, 5)):
        return Attendance.objects.create(employee=nv, shift_assignment=ca, work_date=ngay, planned_start=time(8),
                                         planned_end=time(12), attendance_status='ON_TIME')

    def test_mot_ban_ghi_moi_ngay_khi_khong_theo_ca(self):
        nv = tao_nhan_su()
        self._cc(nv)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._cc(nv)

    def test_mot_ban_ghi_moi_ca(self):
        nv = tao_nhan_su(loai_hinh='PART_TIME', ca='')
        ca = ShiftAssignment.objects.create(slot_group='g', employee=nv, shift_role='Lễ tân', work_date=date(2026, 10, 5),
                                            planned_start=time(8), planned_end=time(12),
                                            registration_deadline=datetime(2026, 10, 4, 18))
        self._cc(nv, ca)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._cc(nv, ca)

    def test_part_time_nhieu_ca_trong_mot_ngay_hop_le(self):
        nv = tao_nhan_su(loai_hinh='PART_TIME', ca='')
        for i, (bd, kt) in enumerate([(time(8), time(12)), (time(13), time(17))]):
            ca = ShiftAssignment.objects.create(slot_group=f'g{i}', employee=nv, shift_role='Lễ tân',
                                                work_date=date(2026, 10, 5), planned_start=bd, planned_end=kt,
                                                registration_deadline=datetime(2026, 10, 4, 18))
            self._cc(nv, ca)
        self.assertEqual(nv.attendance_logs.count(), 2)


# =====================================================================================================
# P8 – UC 4.1 – 4.5. Tên test bám mã luồng ở §10 (ROADMAP §12.1). Ngày cố định: 06/10/2026 là Thứ 3.
# =====================================================================================================
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from attendance import services
from attendance.models import AttendanceStatus as TT
from attendance.models import ExplanationStatus as GT
from core import thong_bao
from core.mau_test import tao_nhan_su_hoat_dong as hoat_dong
from core.models import ActivityLog, Notification
from core.services import KhongCoQuyen, LoiNghiepVu
from employees.models import Department, EmploymentType, Position, WorkShift
from leave.models import LeaveRequest
from payroll.models import Payroll
from schedule.models import StudyClass, TeachingSession

FT, PT = EmploymentType.FULL_TIME, EmploymentType.PART_TIME
T3 = date(2026, 10, 6)          # Thứ 3
CN = date(2026, 10, 11)         # Chủ nhật


def luc(gio, phut=0, giay=0, ngay=T3):
    return datetime.combine(ngay, time(gio, phut, giay))


class NenTangCC(TestCase):
    """Super Admin, 2 Quản lý, Kế toán, giáo viên Full-time Ca 1 và Ca 2, nhân viên Part-time, trợ giảng Part-time."""

    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN, full_name='SA')
        self.ql = hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER, FT)
        self.ql2 = hoat_dong('ql2@icls.vn', UserRole.MANAGER, Position.MANAGER, FT)
        self.kt = hoat_dong('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, FT)
        self.gv1 = hoat_dong('gv1@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_1)    # 08:00–17:00
        self.gv2 = hoat_dong('gv2@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_2)    # 13:00–21:00
        self.pt = hoat_dong('pt@icls.vn', UserRole.EMPLOYEE, Position.STAFF, PT)
        self.tg = hoat_dong('tg@icls.vn', UserRole.EMPLOYEE, Position.TEACHING_ASSISTANT, PT)

    def dang_nhap(self, nguoi):
        self.client.force_login(nguoi.user if hasattr(nguoi, 'user') else nguoi)

    def ca(self, nv, ngay=T3, bd=time(8), kt=time(12), vai_tro='Lễ tân', trang_thai='SCHEDULED', ma=None):
        return ShiftAssignment.objects.create(
            slot_group=ma or f'g-{nv.pk}-{ngay}-{bd}', employee=nv, shift_role=vai_tro, work_date=ngay, planned_start=bd,
            planned_end=kt, registration_deadline=datetime(2026, 9, 1), status=trang_thai)

    def nghi(self, nv, hinh_thuc='FULL_DAY', ngay=T3, den=None, loai='SICK', trang_thai='APPROVED', so_ngay=1):
        return LeaveRequest.objects.create(employee=nv, leave_type=loai, duration_type=hinh_thuc, start_date=ngay,
                                           end_date=den or ngay, total_days=so_ngay, reason='x', status=trang_thai)

    def cc(self, nv, ngay=T3, bd=time(8), kt=time(17), trang_thai=TT.ON_TIME, vao=None, ra=None, tre=0, som=0, ca=None,
           giai_trinh=GT.NONE):
        return Attendance.objects.create(
            employee=nv, shift_assignment=ca, work_date=ngay, planned_start=bd, planned_end=kt, check_in=vao, check_out=ra,
            late_minutes=tre, early_leave_minutes=som, attendance_status=trang_thai, explanation_status=giai_trinh,
            explanation_reason='x' if giai_trinh != GT.NONE else '')


# ---------------------------------------------------------------------------------- Lịch dự kiến (§9.2)
class LichDuKienTest(NenTangCC):
    def khung(self, nv, ngay=T3):
        return [(k['bd'], k['kt']) for k in services.lich_du_kien(nv, ngay)]

    def test_full_time_theo_ca_trong_ho_so(self):
        self.assertEqual(self.khung(self.gv1), [(time(8), time(17))])
        self.assertEqual(self.khung(self.gv2), [(time(13), time(21))])

    def test_chu_nhat_khong_co_lich(self):
        self.assertEqual(self.khung(self.gv1, CN), [])

    def test_nghi_ca_ngay_da_duyet_khong_con_lich_nhung_don_chua_duyet_thi_van_co(self):
        don = self.nghi(self.gv1, trang_thai='PENDING')
        self.assertEqual(self.khung(self.gv1), [(time(8), time(17))])
        don.status = 'APPROVED'
        don.save()
        self.assertEqual(self.khung(self.gv1), [])
        self.assertTrue(services.nghi_ca_ngay(self.gv1, T3))

    def test_nghi_nua_ca_chi_con_nua_con_lai_theo_moc_giua_ca(self):
        # Ca 1 mốc 12:00: nghỉ nửa đầu còn 12–17; Ca 2 mốc 17:00: nghỉ nửa sau còn 13–17
        self.nghi(self.gv1, 'HALF_DAY_AM')
        self.nghi(self.gv2, 'HALF_DAY_PM')
        self.assertEqual(self.khung(self.gv1), [(time(12), time(17))])
        self.assertEqual(self.khung(self.gv2), [(time(13), time(17))])

    def test_nghi_ca_hai_nua_thi_khong_con_lich(self):
        self.nghi(self.gv1, 'HALF_DAY_AM')
        self.nghi(self.gv1, 'HALF_DAY_PM')
        self.assertEqual(self.khung(self.gv1), [])
        self.assertTrue(services.nghi_ca_ngay(self.gv1, T3))

    def test_part_time_moi_ca_scheduled_la_mot_khung_gan_ca(self):
        sang = self.ca(self.pt, bd=time(8), kt=time(12))
        chieu = self.ca(self.pt, bd=time(14), kt=time(18), vai_tro='Tư vấn')
        self.ca(self.pt, bd=time(19), kt=time(21), trang_thai='PENDING')              # chưa chốt: không tính
        self.ca(self.pt, ngay=T3 + timedelta(days=1))                                 # ngày khác
        cac_khung = services.lich_du_kien(self.pt, T3)
        self.assertEqual([(k['bd'], k['kt'], k['ca']) for k in cac_khung], [(time(8), time(12), sang), (time(14), time(18), chieu)])

    def test_tro_giang_mot_khung_tu_dau_buoi_dau_den_cuoi_buoi_cuoi_khong_gan_ca(self):
        lop = StudyClass.objects.create(class_name='L', subject='s', weekdays='1', start_time=time(9), end_time=time(11),
                                        start_date=T3, end_date=T3)
        for bd, kt, trang_thai in ((time(9), time(11), 'SCHEDULED'), (time(14), time(16), 'COMPLETED'), (time(17), time(19), 'CANCELLED')):
            TeachingSession.objects.create(study_class=lop, session_date=T3, planned_start=bd, planned_end=kt,
                                           planned_teacher=self.gv1, actual_teacher=self.gv1, actual_assistant=self.tg, status=trang_thai)
        cac_khung = services.lich_du_kien(self.tg, T3)
        self.assertEqual([(k['bd'], k['kt'], k['ca']) for k in cac_khung], [(time(9), time(16), None)])   # buổi hủy không tính

    def test_part_time_nghi_nua_ngay_dung_moc_12h(self):
        self.ca(self.pt, bd=time(8), kt=time(12))
        self.ca(self.pt, bd=time(14), kt=time(18), vai_tro='Tư vấn')
        don = self.nghi(self.pt, 'HALF_DAY_AM')
        self.assertEqual(self.khung(self.pt), [(time(14), time(18))])                  # ca sáng nằm trọn nửa đầu: bỏ
        don.duration_type = 'HALF_DAY_PM'
        don.save()
        self.assertEqual(self.khung(self.pt), [(time(8), time(12))])

    def test_part_time_khong_co_ca_khong_co_lich(self):
        self.assertEqual(self.khung(self.pt), [])


# ---------------------------------------------------------------------------------- UC 4.1
class Uc41Test(NenTangCC):
    def test_uc4_1_basic_check_in_dung_gio(self):
        b = services.check_in(self.gv1, luc(8, 3))
        self.assertEqual((b.work_date, b.planned_start, b.planned_end, b.check_in), (T3, time(8), time(17), luc(8, 3)))
        self.assertEqual((b.attendance_status, b.late_minutes, b.shift_assignment, b.explanation_status), (TT.ON_TIME, 0, None, GT.NONE))

    def test_uc4_1_basic_nguong_tre_5_phut(self):
        self.assertEqual(services.check_in(self.gv1, luc(8, 5, 0)).attendance_status, TT.ON_TIME)       # đúng 5 phút: còn được cho phép
        Attendance.objects.all().delete()
        self.assertEqual(services.check_in(self.gv1, luc(8, 5, 59)).attendance_status, TT.ON_TIME)      # 5 phút 59 giây vẫn là 5 phút
        Attendance.objects.all().delete()
        b = services.check_in(self.gv1, luc(8, 6))                                                       # quá 5 phút
        self.assertEqual((b.attendance_status, b.late_minutes), (TT.LATE, 6))
        Attendance.objects.all().delete()
        b = services.check_in(self.gv1, luc(8, 35))
        self.assertEqual((b.attendance_status, b.late_minutes), (TT.LATE, 35))

    def test_check_in_som_hon_gio_bat_dau_la_dung_gio(self):
        b = services.check_in(self.gv1, luc(7, 40))
        self.assertEqual((b.attendance_status, b.late_minutes), (TT.ON_TIME, 0))

    def test_uc4_1_basic_check_out_dung_gio_va_tong_thoi_gian(self):
        services.check_in(self.gv1, luc(8, 0))
        b = services.check_out(self.gv1, luc(17, 5))
        self.assertEqual((b.check_out, b.attendance_status, b.early_leave_minutes), (luc(17, 5), TT.ON_TIME, 0))
        self.assertEqual(services.tong_thoi_gian_lam(b), '9 giờ 05 phút')

    def test_uc4_1_basic_check_out_som_giu_nguyen_so_phut_tre(self):
        services.check_in(self.gv1, luc(8, 35))                                  # trễ 35 phút
        b = services.check_out(self.gv1, luc(16, 30))                            # sớm 30 phút
        self.assertEqual((b.attendance_status, b.late_minutes, b.early_leave_minutes), (TT.EARLY_LEAVE, 35, 30))

    def test_check_out_tre_van_giu_trang_thai_tre(self):
        services.check_in(self.gv1, luc(8, 20))
        b = services.check_out(self.gv1, luc(17, 30))
        self.assertEqual((b.attendance_status, b.late_minutes, b.early_leave_minutes), (TT.LATE, 20, 0))

    def test_check_in_ca_2_va_nua_ca_sau_nghi_nua_dau(self):
        self.assertEqual(services.check_in(self.gv2, luc(13, 0)).planned_start, time(13))
        self.nghi(self.gv1, 'HALF_DAY_AM')                                       # chỉ còn 12:00–17:00
        b = services.check_in(self.gv1, luc(12, 3))
        self.assertEqual((b.planned_start, b.planned_end, b.attendance_status), (time(12), time(17), TT.ON_TIME))

    def test_part_time_nhieu_ca_phai_chon_ca_va_moi_ca_mot_ban_ghi(self):
        sang = self.ca(self.pt, bd=time(8), kt=time(12))
        chieu = self.ca(self.pt, bd=time(14), kt=time(18), vai_tro='Tư vấn')
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHON_CA_CHAM_CONG):
            services.check_in(self.pt, luc(8, 0))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CA_KHONG_HOP_LE):
            services.check_in(self.pt, luc(8, 0), ma_ca=99999)
        b1 = services.check_in(self.pt, luc(8, 2), ma_ca=sang.pk)
        b2 = services.check_in(self.pt, luc(14, 10), ma_ca=chieu.pk)
        self.assertEqual((b1.shift_assignment, b2.shift_assignment, b2.attendance_status, b2.late_minutes), (sang, chieu, TT.LATE, 10))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_CHECK_IN):
            services.check_in(self.pt, luc(8, 5), ma_ca=sang.pk)
        out = services.check_out(self.pt, luc(11, 40), ma_ca=sang.pk)             # check-out đúng ca đã chọn
        self.assertEqual((out.shift_assignment, out.early_leave_minutes), (sang, 20))
        self.assertEqual(Attendance.objects.filter(employee=self.pt).count(), 2)

    def test_part_time_hai_ca_dang_mo_check_out_khong_chon_ca_bi_chan(self):
        sang = self.ca(self.pt, bd=time(8), kt=time(12))
        chieu = self.ca(self.pt, bd=time(12, 30), kt=time(18), vai_tro='Tư vấn')
        services.check_in(self.pt, luc(8, 0), ma_ca=sang.pk)
        services.check_in(self.pt, luc(12, 30), ma_ca=chieu.pk)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHON_CA_CHAM_CONG):
            services.check_out(self.pt, luc(13, 0))
        services.check_out(self.pt, luc(12, 0), ma_ca=sang.pk)
        b = services.check_out(self.pt, luc(18, 0))                               # chỉ còn một ca chưa ra: tự nhận
        self.assertEqual(b.shift_assignment, chieu)

    def test_tro_giang_cham_cong_theo_ngay_khong_theo_ca(self):
        lop = StudyClass.objects.create(class_name='L', subject='s', weekdays='1', start_time=time(18), end_time=time(20),
                                        start_date=T3, end_date=T3)
        TeachingSession.objects.create(study_class=lop, session_date=T3, planned_start=time(18), planned_end=time(20),
                                       planned_teacher=self.gv2, actual_teacher=self.gv2, actual_assistant=self.tg)
        b = services.check_in(self.tg, luc(18, 2))
        self.assertEqual((b.shift_assignment, b.planned_start, b.planned_end), (None, time(18), time(20)))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_CHECK_IN):
            services.check_in(self.tg, luc(18, 3))

    def test_uc4_1_alt_1_1_nghi_phep_ca_ngay(self):
        self.nghi(self.gv1)
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.check_in(self.gv1, luc(8, 0))
        self.assertEqual(str(ctx.exception), 'Hôm nay bạn nghỉ phép.')
        man_hinh = services.man_hinh_cham_cong(self.gv1, T3)
        self.assertEqual((man_hinh['nghi_phep'], man_hinh['khung']), (True, []))

    def test_uc4_1_exc_1_2_khong_co_lich_hom_nay(self):
        for nv, ngay in ((self.gv1, CN), (self.pt, T3)):                         # Chủ nhật; Part-time chưa có ca
            with self.assertRaises(LoiNghiepVu) as ctx:
                services.check_in(nv, luc(8, 0, ngay=ngay))
            self.assertEqual(str(ctx.exception), 'Hôm nay bạn không có lịch làm việc.')
        self.assertTrue(services.man_hinh_cham_cong(self.pt, T3)['khong_co_lich'])

    def test_uc4_1_exc_3_1_da_check_in(self):
        services.check_in(self.gv1, luc(8, 0))
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.check_in(self.gv1, luc(8, 1))
        self.assertEqual(str(ctx.exception), 'Bạn đã thực hiện Check-in hôm nay.')
        self.assertEqual(Attendance.objects.filter(employee=self.gv1).count(), 1)     # không tạo bản ghi mới

    def test_uc4_1_exc_6_2_chua_check_in(self):
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.check_out(self.gv1, luc(17, 0))
        self.assertEqual(str(ctx.exception), 'Vui lòng thực hiện Check-in trước.')
        self.assertEqual(Attendance.objects.count(), 0)

    def test_check_out_hai_lan_bi_chan(self):
        services.check_in(self.gv1, luc(8, 0))
        services.check_out(self.gv1, luc(17, 0))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_CHECK_OUT):
            services.check_out(self.gv1, luc(17, 1))

    def test_nhan_su_khong_hoat_dong_khong_cham_cong(self):
        self.gv1.status = 'RESIGNED'
        self.gv1.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_NHAN_SU_HOAT_DONG_CHAM_CONG):
            services.check_in(self.gv1, luc(8, 0))

    def test_man_hinh_cham_cong_hanh_dong_theo_trang_thai(self):
        self.assertEqual(services.man_hinh_cham_cong(self.gv1, T3)['khung'][0]['hanh_dong'], 'check_in')
        services.check_in(self.gv1, luc(8, 0))
        self.assertEqual(services.man_hinh_cham_cong(self.gv1, T3)['khung'][0]['hanh_dong'], 'check_out')
        services.check_out(self.gv1, luc(17, 0))
        self.assertIsNone(services.man_hinh_cham_cong(self.gv1, T3)['khung'][0]['hanh_dong'])

    def test_uc4_1_qua_man_hinh(self):
        gia = type('HomNay', (date,), {'today': classmethod(lambda cls: T3)})
        self.dang_nhap(self.gv1)
        with mock.patch('attendance.views.date', gia):
            r = self.client.get(reverse('attendance:my_attendance'))
            self.assertContains(r, 'Check-In')
        with mock.patch('attendance.services._bay_gio', return_value=luc(8, 35)):
            r = self.client.post(reverse('attendance:check_in'), follow=True)
            self.assertContains(r, 'Check-in thành công lúc 08:35.')
            r = self.client.post(reverse('attendance:check_in'), follow=True)
            self.assertContains(r, 'Bạn đã thực hiện Check-in hôm nay.')
        with mock.patch('attendance.services._bay_gio', return_value=luc(17, 2)):
            r = self.client.post(reverse('attendance:check_out'), follow=True)
            self.assertContains(r, 'Check-out thành công lúc 17:02. Tổng thời gian làm việc: 8 giờ 27 phút.')
        b = Attendance.objects.get(employee=self.gv1)
        self.assertEqual((b.attendance_status, b.late_minutes), (TT.LATE, 35))

    def test_uc4_1_exc_6_2_qua_man_hinh(self):
        self.dang_nhap(self.gv1)
        with mock.patch('attendance.services._bay_gio', return_value=luc(17, 0)):
            r = self.client.post(reverse('attendance:check_out'), follow=True)
        self.assertContains(r, 'Vui lòng thực hiện Check-in trước.')

    def test_chi_nhan_post_va_super_admin_khong_cham_cong(self):
        self.dang_nhap(self.gv1)
        self.assertEqual(self.client.get(reverse('attendance:check_in')).status_code, 405)
        self.dang_nhap(self.sa)
        self.assertEqual(self.client.post(reverse('attendance:check_in')).status_code, 403)
        self.assertEqual(self.client.post(reverse('attendance:check_out')).status_code, 403)

    def test_moi_vai_tro_co_ho_so_cham_cong_duoc(self):
        for nv in (self.ql, self.kt, self.gv1, self.pt):
            self.dang_nhap(nv)
            self.assertEqual(self.client.get(reverse('attendance:my_attendance')).status_code, 200)


# ---------------------------------------------------------------------------------- UC 4.3 + ngày công, giờ công
class TinhCongTest(NenTangCC):
    def test_tinh_ngay_cong_full_time(self):
        # 3 ngày đi làm (đúng giờ, trễ, về sớm) = 3; ABSENT và MISSING_CHECKOUT chưa giải trình = 0
        for i, tt in enumerate((TT.ON_TIME, TT.LATE, TT.EARLY_LEAVE, TT.ABSENT, TT.MISSING_CHECKOUT)):
            self.cc(self.gv1, ngay=date(2026, 10, 1) + timedelta(days=i), trang_thai=tt)
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('3'))

    def test_giai_trinh_duoc_chap_thuan_thanh_on_time_nen_duoc_tinh(self):
        b = self.cc(self.gv1, trang_thai=TT.LATE, tre=40, giai_trinh=GT.PENDING)
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('1'))        # trễ vẫn tính 1 ngày
        b.attendance_status, b.explanation_status = TT.ABSENT, GT.REJECTED
        b.save()
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('0'))

    def test_ngay_cong_cong_phep_nam_da_duyet_va_chi_phep_nam(self):
        self.cc(self.gv1, ngay=date(2026, 10, 1))                                              # 1
        self.nghi(self.gv1, ngay=date(2026, 10, 14), den=date(2026, 10, 15), loai='ANNUAL', so_ngay=2)   # +2
        self.nghi(self.gv1, ngay=date(2026, 10, 20), loai='SICK')                              # nghỉ ốm: 0
        self.nghi(self.gv1, ngay=date(2026, 10, 21), loai='UNPAID')                            # không lương: 0
        self.nghi(self.gv1, ngay=date(2026, 10, 22), loai='ANNUAL', trang_thai='PENDING')      # chưa duyệt: 0
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('3'))

    def test_ngay_co_don_nghi_nua_ca_thi_di_lam_chi_tinh_0_5_va_phep_nam_nua_ngay_cong_them_0_5(self):
        ngay = date(2026, 10, 7)
        self.cc(self.gv1, ngay=ngay, bd=time(12), kt=time(17))                                 # chỉ làm nửa sau ca
        self.nghi(self.gv1, 'HALF_DAY_AM', ngay=ngay, loai='ANNUAL', so_ngay=Decimal('0.5'))   # nghỉ phép năm nửa đầu
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('1.0'))          # 0,5 + 0,5
        ngay2 = date(2026, 10, 8)
        self.cc(self.gv1, ngay=ngay2, bd=time(12), kt=time(17))
        self.nghi(self.gv1, 'HALF_DAY_AM', ngay=ngay2, loai='SICK', so_ngay=Decimal('0.5'))    # nghỉ ốm nửa đầu: chỉ 0,5
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('1.5'))

    def test_don_phep_nam_vat_qua_hai_thang_chi_dem_phan_trong_thang(self):
        self.nghi(self.gv1, ngay=date(2026, 10, 30), den=date(2026, 11, 3), loai='ANNUAL', so_ngay=4)    # T6, T7 | CN, T2, T3
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('2'))
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 11, 2026), Decimal('2'))

    def test_ngay_cong_toi_da_26(self):
        ngay = date(2026, 10, 1)
        while ngay.month == 10:
            if ngay.weekday() != 6:
                self.cc(self.gv1, ngay=ngay)
            ngay += timedelta(days=1)
        self.assertEqual(Attendance.objects.filter(employee=self.gv1).count(), 27)             # tháng 10/2026 có 27 ngày Thứ 2–Thứ 7
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('26'))

    def test_tinh_gio_cong_part_time(self):
        d = date(2026, 10, 1)
        # (a) ca 08–12, thực tế 08:30–11:30 = 3,00 giờ
        self.cc(self.pt, ngay=d, bd=time(8), kt=time(12), vao=luc(8, 30, ngay=d), ra=luc(11, 30, ngay=d), ca=self.ca(self.pt, ngay=d, ma='a'))
        # (b) ca 08–12, vào sớm 07:50 ra muộn 12:30 → chỉ tính trong giờ dự kiến = 4,00 giờ
        d2 = date(2026, 10, 2)
        self.cc(self.pt, ngay=d2, bd=time(8), kt=time(12), vao=luc(7, 50, ngay=d2), ra=luc(12, 30, ngay=d2), ca=self.ca(self.pt, ngay=d2, ma='b'))
        # (c) giải trình được chấp thuận, không có check-out → tính đủ 14–18 = 4,00 giờ
        d3 = date(2026, 10, 3)
        self.cc(self.pt, ngay=d3, bd=time(14), kt=time(18), vao=luc(14, 0, ngay=d3), trang_thai=TT.ON_TIME, giai_trinh=GT.APPROVED,
                ca=self.ca(self.pt, ngay=d3, bd=time(14), kt=time(18), ma='c'))
        # (d) chỉ có check-in (quên check-out), chưa giải trình → 0 giờ; (e) giải trình đang chờ duyệt → 0 giờ
        d4, d5 = date(2026, 10, 5), date(2026, 10, 6)
        self.cc(self.pt, ngay=d4, bd=time(8), kt=time(12), vao=luc(8, 0, ngay=d4), trang_thai=TT.MISSING_CHECKOUT, ca=self.ca(self.pt, ngay=d4, ma='d'))
        self.cc(self.pt, ngay=d5, bd=time(8), kt=time(12), vao=luc(8, 0, ngay=d5), trang_thai=TT.MISSING_CHECKOUT, giai_trinh=GT.PENDING,
                ca=self.ca(self.pt, ngay=d5, ma='e'))
        # (f) buổi trợ giảng 18:00–20:00 (không theo ca): 18:10 → 19:55 = 1,75 giờ
        d6 = date(2026, 10, 7)
        self.cc(self.pt, ngay=d6, bd=time(18), kt=time(20), vao=luc(18, 10, ngay=d6), ra=luc(19, 55, ngay=d6))
        self.assertEqual(services.tinh_gio_cong(self.pt, 10, 2026), Decimal('12.75'))          # 3 + 4 + 4 + 0 + 0 + 1,75
        self.assertEqual(services.tinh_gio_cong(self.pt, 9, 2026), Decimal('0.00'))

    def test_gio_cong_lam_tron_2_chu_so(self):
        self.cc(self.pt, bd=time(8), kt=time(9), vao=luc(8, 0), ra=luc(8, 20))
        self.assertEqual(services.tinh_gio_cong(self.pt, 10, 2026), Decimal('0.33'))          # 20 phút = 0,333… giờ

    def test_uc4_3_basic_lich_su_chi_cua_chinh_minh_va_dung_thang(self):
        b1 = self.cc(self.gv1, ngay=date(2026, 10, 5))
        b2 = self.cc(self.gv1, ngay=date(2026, 10, 6))
        self.cc(self.gv1, ngay=date(2026, 9, 30))                       # tháng khác
        self.cc(self.gv2, ngay=date(2026, 10, 6))                       # người khác
        self.assertEqual(list(services.lich_su_cham_cong(self.gv1, 10, 2026)), [b2, b1])      # mới nhất lên đầu
        self.dang_nhap(self.gv1)
        r = self.client.get(reverse('attendance:my_attendance'), {'thang': '2026-10'})
        self.assertEqual(r.context['lich_su'], [b2, b1])
        self.assertEqual((r.context['cong'], r.context['don_vi']), (Decimal('2'), 'ngày công'))
        r = self.client.get(reverse('attendance:my_attendance'), {'thang': '2026-09'})
        self.assertEqual(len(r.context['lich_su']), 1)

    def test_uc4_3_basic_part_time_tong_gio_cong(self):
        self.cc(self.pt, bd=time(8), kt=time(12), vao=luc(8, 0), ra=luc(12, 0))
        self.dang_nhap(self.pt)
        r = self.client.get(reverse('attendance:my_attendance'), {'thang': '2026-10'})
        self.assertEqual((r.context['cong'], r.context['don_vi']), (Decimal('4.00'), 'giờ công'))
        self.assertContains(r, 'Tổng tháng: 4 giờ công')

    def test_uc4_3_nut_gui_giai_trinh_chi_o_dong_loi_chua_giai_trinh(self):
        loi = self.cc(self.gv1, ngay=date(2026, 10, 5), trang_thai=TT.LATE, tre=20)
        tot = self.cc(self.gv1, ngay=date(2026, 10, 6))
        da_gt = self.cc(self.gv1, ngay=date(2026, 10, 7), trang_thai=TT.LATE, tre=20, giai_trinh=GT.PENDING)
        self.assertTrue(services.la_loi_co_the_giai_trinh(loi))
        self.assertFalse(services.la_loi_co_the_giai_trinh(tot))
        self.assertFalse(services.la_loi_co_the_giai_trinh(da_gt))
        self.dang_nhap(self.gv1)
        r = self.client.get(reverse('attendance:my_attendance'), {'thang': '2026-10'})
        self.assertContains(r, reverse('attendance:explain', args=[loi.pk]))
        self.assertNotContains(r, reverse('attendance:explain', args=[tot.pk]))
        self.assertNotContains(r, reverse('attendance:explain', args=[da_gt.pk]))

    def test_uc4_3_exc_4_1_khong_co_du_lieu_trong_thang(self):
        self.dang_nhap(self.gv1)
        r = self.client.get(reverse('attendance:my_attendance'), {'thang': '2026-01'})
        self.assertContains(r, 'Không có dữ liệu chấm công trong khoảng thời gian đã chọn.')

    def test_thang_sai_dinh_dang_khong_sap_va_super_admin_chuyen_sang_bang_tong_hop(self):
        self.dang_nhap(self.gv1)
        self.assertEqual(self.client.get(reverse('attendance:my_attendance'), {'thang': 'abc'}).status_code, 200)
        self.dang_nhap(self.sa)
        self.assertRedirects(self.client.get(reverse('attendance:my_attendance')), reverse('attendance:summary'))

    def test_mo_ta_chenh_lech(self):
        self.assertEqual(services.mo_ta_chenh_lech(self.cc(self.gv1, tre=35)), 'Trễ 35 phút')
        self.assertEqual(services.mo_ta_chenh_lech(self.cc(self.gv1, ngay=date(2026, 10, 7), som=15)), 'Về sớm 15 phút')
        self.assertEqual(services.mo_ta_chenh_lech(self.cc(self.gv1, ngay=date(2026, 10, 8), tre=5, som=10)), 'Trễ 5 phút, Về sớm 10 phút')
        self.assertEqual(services.mo_ta_chenh_lech(self.cc(self.gv1, ngay=date(2026, 10, 9))), '0 phút')


# ---------------------------------------------------------------------------------- UC 4.2
class Uc42Test(NenTangCC):
    def loi(self, nv=None, **kw):
        kw.setdefault('trang_thai', TT.LATE)
        kw.setdefault('tre', 35)
        return self.cc(nv or self.gv1, **kw)

    def test_uc4_2_basic_gui_giai_trinh(self):
        b = self.loi()
        services.gui_giai_trinh(self.gv1, b, '  Bị hư xe, phải dừng sửa chữa  ')
        b.refresh_from_db()
        self.assertEqual((b.explanation_status, b.explanation_reason), (GT.PENDING, 'Bị hư xe, phải dừng sửa chữa'))
        self.assertEqual(b.attendance_status, TT.LATE)                                  # lỗi giữ nguyên cho tới khi được chấp thuận
        self.assertEqual(set(Notification.objects.filter(title=thong_bao.TB_GIAI_TRINH_MOI_TIEU_DE).values_list('recipient_id', flat=True)),
                         {self.ql.user_id, self.ql2.user_id})                           # mọi Quản lý nhận, Kế toán/SA không
        self.assertTrue(ActivityLog.objects.filter(model_name='attendance', object_id=b.pk, action='UPDATE').exists())

    def test_giai_trinh_cua_quan_ly_bao_super_admin(self):
        services.gui_giai_trinh(self.ql, self.loi(self.ql), 'x')
        self.assertEqual(set(Notification.objects.filter(title=thong_bao.TB_GIAI_TRINH_MOI_TIEU_DE).values_list('recipient_id', flat=True)),
                         {self.sa.pk})

    def test_moi_loai_loi_deu_giai_trinh_duoc_va_on_time_thi_khong(self):
        for i, tt in enumerate((TT.LATE, TT.EARLY_LEAVE, TT.ABSENT, TT.MISSING_CHECKOUT)):
            b = self.cc(self.gv1, ngay=date(2026, 10, 1) + timedelta(days=i), trang_thai=tt)
            services.gui_giai_trinh(self.gv1, b, 'lý do')
            b.refresh_from_db()
            self.assertEqual(b.explanation_status, GT.PENDING)
        tot = self.cc(self.gv1, ngay=date(2026, 10, 8))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.KHONG_CO_LOI_DE_GIAI_TRINH):
            services.gui_giai_trinh(self.gv1, tot, 'lý do')

    def test_uc4_2_basic_qua_man_hinh_kem_minh_chung(self):
        thu_muc = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, thu_muc, True)
        b = self.loi()
        self.dang_nhap(self.gv1)
        with override_settings(MEDIA_ROOT=thu_muc):
            r = self.client.get(reverse('attendance:explain', args=[b.pk]))
            self.assertContains(r, 'Giải trình chấm công')
            self.assertContains(r, 'Trễ 35 phút')
            r = self.client.post(reverse('attendance:explain', args=[b.pk]), {
                'ly_do': 'Bị hư xe', 'minh_chung': SimpleUploadedFile('bien-lai.pdf', b'%PDF-1.4 x', content_type='application/pdf')}, follow=True)
        self.assertContains(r, 'Gửi giải trình thành công.')
        b.refresh_from_db()
        self.assertEqual(b.explanation_status, GT.PENDING)
        self.assertTrue(b.explanation_evidence.name.startswith('attendance/explanations/'))

    def test_uc4_2_exc_3_1_bo_trong_ly_do(self):
        b = self.loi()
        for ly_do in ('', '   '):
            with self.assertRaises(LoiNghiepVu) as ctx:
                services.gui_giai_trinh(self.gv1, b, ly_do)
            self.assertEqual(str(ctx.exception), 'Vui lòng nhập lý do giải trình.')
        b.refresh_from_db()
        self.assertEqual(b.explanation_status, GT.NONE)
        self.dang_nhap(self.gv1)
        r = self.client.post(reverse('attendance:explain', args=[b.pk]), {'ly_do': ''})
        self.assertContains(r, 'Vui lòng nhập lý do giải trình.')
        self.assertContains(r, 'invalid-feedback')

    def test_uc4_2_exc_1_1_da_giai_trinh_truoc_do(self):
        for tt in (GT.PENDING, GT.APPROVED, GT.REJECTED):
            b = self.loi(ngay=date(2026, 10, 1) + timedelta(days={'PENDING': 0, 'APPROVED': 1, 'REJECTED': 2}[tt]), giai_trinh=tt)
            with self.assertRaises(LoiNghiepVu) as ctx:
                services.gui_giai_trinh(self.gv1, b, 'lần hai')
            self.assertEqual(str(ctx.exception), 'Ca làm việc này đã được giải trình.')
        self.dang_nhap(self.gv1)                                                       # chặn ngay khi mở form (bước 1)
        r = self.client.get(reverse('attendance:explain', args=[b.pk]), follow=True)
        self.assertContains(r, 'Ca làm việc này đã được giải trình.')
        self.assertRedirects(r, reverse('attendance:my_attendance'))

    def test_uc4_2_exc_1_2_bang_luong_da_chot(self):
        b = self.loi()
        Payroll.objects.create(employee=self.gv1, period_month=10, period_year=2026, status='LOCKED')
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.gui_giai_trinh(self.gv1, b, 'lý do')
        self.assertEqual(str(ctx.exception), 'Bảng lương tháng này đã chốt, không thể thay đổi chấm công.')
        self.dang_nhap(self.gv1)
        self.assertContains(self.client.get(reverse('attendance:explain', args=[b.pk]), follow=True),
                            'Bảng lương tháng này đã chốt, không thể thay đổi chấm công.')
        Payroll.objects.update(status='DRAFT')                                         # bảng lương nháp thì chưa khóa
        services.gui_giai_trinh(self.gv1, b, 'lý do')
        self.assertEqual(Attendance.objects.get(pk=b.pk).explanation_status, GT.PENDING)

    def test_thang_khac_chua_chot_van_giai_trinh_duoc(self):
        Payroll.objects.create(employee=self.gv1, period_month=9, period_year=2026, status='SENT')
        services.gui_giai_trinh(self.gv1, self.loi(), 'lý do')

    def test_khong_giai_trinh_ho_nguoi_khac_va_file_sai_dinh_dang_bi_chan(self):
        b = self.loi(self.gv2)
        with self.assertRaises(KhongCoQuyen):
            services.gui_giai_trinh(self.gv1, b, 'lý do')
        self.dang_nhap(self.gv1)
        self.assertEqual(self.client.get(reverse('attendance:explain', args=[b.pk])).status_code, 403)
        mine = self.loi(self.gv1, ngay=date(2026, 10, 7))
        r = self.client.post(reverse('attendance:explain', args=[mine.pk]), {
            'ly_do': 'x', 'minh_chung': SimpleUploadedFile('virus.exe', b'x')})
        self.assertContains(r, thong_bao.FILE_KHONG_HOP_LE)
        self.assertEqual(Attendance.objects.get(pk=mine.pk).explanation_status, GT.NONE)
        self.dang_nhap(self.sa)
        self.assertEqual(self.client.get(reverse('attendance:explain', args=[mine.pk])).status_code, 403)


# ---------------------------------------------------------------------------------- UC 4.4
class Uc44Test(NenTangCC):
    BAY_GIO = datetime(2026, 10, 7, 9, 0)

    def cho_duyet(self, nv=None, **kw):
        kw.setdefault('trang_thai', TT.LATE)
        kw.setdefault('tre', 35)
        kw.setdefault('giai_trinh', GT.PENDING)
        kw.setdefault('vao', luc(8, 35))
        kw.setdefault('ra', luc(12, 2))
        return self.cc(nv or self.gv1, **kw)

    def test_uc4_4_basic_chap_thuan_xoa_loi_va_tinh_du_cong(self):
        b = self.cho_duyet(tre=35, trang_thai=TT.LATE)
        b.early_leave_minutes = 10
        b.save()
        services.chap_thuan_giai_trinh(self.ql.user, b, self.BAY_GIO)
        b.refresh_from_db()
        self.assertEqual((b.explanation_status, b.late_minutes, b.early_leave_minutes, b.attendance_status),
                         (GT.APPROVED, 0, 0, TT.ON_TIME))
        self.assertEqual((b.explanation_reviewed_by, b.explanation_reviewed_at), (self.ql.user, self.BAY_GIO))
        self.assertTrue(Notification.objects.filter(recipient=self.gv1.user, title=thong_bao.TB_KET_QUA_GIAI_TRINH_TIEU_DE).exists())
        self.assertTrue(ActivityLog.objects.filter(action='APPROVE', model_name='attendance', object_id=b.pk).exists())

    def test_chap_thuan_ngay_vang_thi_duoc_tinh_du_cong(self):
        b = self.cho_duyet(trang_thai=TT.ABSENT, tre=0, vao=None, ra=None)
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('0'))
        services.chap_thuan_giai_trinh(self.ql.user, b, self.BAY_GIO)
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('1'))

    def test_chap_thuan_part_time_tinh_du_gio_du_kien(self):
        b = self.cho_duyet(self.pt, trang_thai=TT.MISSING_CHECKOUT, tre=0, bd=time(8), kt=time(12), ra=None)
        self.assertEqual(services.tinh_gio_cong(self.pt, 10, 2026), Decimal('0.00'))
        services.chap_thuan_giai_trinh(self.ql.user, b, self.BAY_GIO)
        self.assertEqual(services.tinh_gio_cong(self.pt, 10, 2026), Decimal('4.00'))

    def test_uc4_4_alt_5_1_tu_choi_giu_nguyen_loi_kem_ly_do(self):
        b = self.cho_duyet()
        services.tu_choi_giai_trinh(self.ql.user, b, 'Minh chứng không hợp lệ', self.BAY_GIO)
        b.refresh_from_db()
        self.assertEqual((b.explanation_status, b.explanation_review_note, b.attendance_status, b.late_minutes),
                         (GT.REJECTED, 'Minh chứng không hợp lệ', TT.LATE, 35))
        tb = Notification.objects.get(recipient=self.gv1.user, title=thong_bao.TB_KET_QUA_GIAI_TRINH_TIEU_DE)
        self.assertIn('Minh chứng không hợp lệ', tb.message)
        self.assertEqual(services.tinh_ngay_cong(self.gv1, 10, 2026), Decimal('1'))          # LATE vẫn là có đi làm

    def test_uc4_4_exc_5_2_tu_choi_khong_nhap_ly_do(self):
        b = self.cho_duyet()
        for ly_do in ('', '  '):
            with self.assertRaises(LoiNghiepVu) as ctx:
                services.tu_choi_giai_trinh(self.ql.user, b, ly_do)
            self.assertEqual(str(ctx.exception), 'Vui lòng nhập lý do từ chối.')
        self.assertEqual(Attendance.objects.get(pk=b.pk).explanation_status, GT.PENDING)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'tu_choi'}, follow=True)
        self.assertContains(r, 'Vui lòng nhập lý do từ chối.')

    def test_uc4_4_exc_5_3_bang_luong_da_chot_chan_ca_chap_thuan_lan_tu_choi(self):
        b = self.cho_duyet()
        Payroll.objects.create(employee=self.gv1, period_month=10, period_year=2026, status='SENT')
        for ham, doi_so in ((services.chap_thuan_giai_trinh, ()), (services.tu_choi_giai_trinh, ('lý do',))):
            with self.assertRaises(LoiNghiepVu) as ctx:
                ham(self.ql.user, b, *doi_so)
            self.assertEqual(str(ctx.exception), 'Bảng lương tháng này đã chốt, không thể thay đổi chấm công.')
        b.refresh_from_db()
        self.assertEqual((b.explanation_status, b.attendance_status, b.late_minutes), (GT.PENDING, TT.LATE, 35))
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'chap_thuan'}, follow=True)
        self.assertContains(r, 'Bảng lương tháng này đã chốt, không thể thay đổi chấm công.')

    def test_da_xu_ly_roi_khong_xu_ly_lai(self):
        b = self.cho_duyet()
        services.chap_thuan_giai_trinh(self.ql.user, b, self.BAY_GIO)
        with self.assertRaisesMessage(LoiNghiepVu, 'Yêu cầu đã được xử lý.'):
            services.chap_thuan_giai_trinh(self.ql.user, b)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.YEU_CAU_DA_XU_LY):
            services.tu_choi_giai_trinh(self.ql.user, b, 'x')
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'chap_thuan'}, follow=True)
        self.assertContains(r, 'Yêu cầu đã được xử lý.')
        self.assertRedirects(r, reverse('attendance:review'))

    def test_q2_phan_cap_duyet_khong_tu_duyet(self):
        nv, kt, ql = self.cho_duyet(self.gv1), self.cho_duyet(self.kt, ngay=date(2026, 10, 7)), self.cho_duyet(self.ql, ngay=date(2026, 10, 8))
        services.chap_thuan_giai_trinh(self.ql.user, nv, self.BAY_GIO)                  # Quản lý duyệt Nhân viên
        services.chap_thuan_giai_trinh(self.ql.user, kt, self.BAY_GIO)                  # Quản lý duyệt Kế toán
        for nguoi in (self.ql2.user, self.ql.user):                                     # đơn Quản lý: Quản lý khác và chính mình đều không
            with self.assertRaises(KhongCoQuyen):
                services.chap_thuan_giai_trinh(nguoi, ql)
        services.chap_thuan_giai_trinh(self.sa, ql, self.BAY_GIO)                       # Super Admin duyệt giải trình của Quản lý
        self.assertEqual(Attendance.objects.get(pk=ql.pk).explanation_reviewed_by, self.sa)
        khac = self.cho_duyet(self.gv2, ngay=date(2026, 10, 9))
        with self.assertRaises(KhongCoQuyen):                                           # SA không duyệt của Nhân viên; Kế toán không duyệt ai
            services.chap_thuan_giai_trinh(self.sa, khac)
        with self.assertRaises(KhongCoQuyen):
            services.chap_thuan_giai_trinh(self.kt.user, khac)

    def test_pham_vi_danh_sach_duyet(self):
        nv, kt, ql = self.cho_duyet(self.gv1), self.cho_duyet(self.kt, ngay=date(2026, 10, 7)), self.cho_duyet(self.ql, ngay=date(2026, 10, 8))
        da_xu_ly = self.cho_duyet(self.gv2, giai_trinh=GT.APPROVED)
        self.assertEqual(set(services.danh_sach_giai_trinh(self.ql.user)), {nv, kt})              # mặc định PENDING, không có của Quản lý
        self.assertEqual(set(services.danh_sach_giai_trinh(self.ql2.user)), {nv, kt})
        self.assertEqual(set(services.danh_sach_giai_trinh(self.sa)), {ql})
        self.assertEqual(list(services.danh_sach_giai_trinh(self.kt.user)), [])
        self.assertEqual(set(services.danh_sach_giai_trinh(self.ql.user, trang_thai='')), {nv, kt, da_xu_ly})
        self.assertEqual(set(services.danh_sach_giai_trinh(self.ql.user, tu_khoa='kt')), {kt})
        self.assertEqual(set(services.danh_sach_giai_trinh(self.ql.user, thang=10, nam=2026)), {nv, kt})
        self.assertEqual(list(services.danh_sach_giai_trinh(self.ql.user, thang=9, nam=2026)), [])

    def test_uc4_4_basic_qua_man_hinh_danh_sach_chi_tiet_va_chap_thuan(self):
        b = self.cho_duyet()
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('attendance:review'))
        self.assertContains(r, 'Giải trình chờ duyệt')
        self.assertContains(r, 'gv1@icls.vn')
        self.assertEqual(r.context['so_cho_duyet'], 1)
        r = self.client.get(reverse('attendance:review_detail', args=[b.pk]))
        self.assertContains(r, 'Chấp thuận')
        self.assertContains(r, '08:00 – 17:00')
        r = self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'chap_thuan'}, follow=True)
        self.assertContains(r, 'Đã chấp thuận giải trình.')
        self.assertEqual(Attendance.objects.get(pk=b.pk).explanation_status, GT.APPROVED)

    def test_phan_quyen_man_hinh_duyet(self):
        b = self.cho_duyet()
        for nguoi in (self.gv1, self.kt, self.pt):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('attendance:review')).status_code, 403)
            self.assertEqual(self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'chap_thuan'}).status_code, 403)
        self.dang_nhap(self.sa)                                  # SA vào được danh sách nhưng không duyệt giải trình của Nhân viên
        self.assertEqual(self.client.get(reverse('attendance:review')).status_code, 200)
        self.assertEqual(self.client.post(reverse('attendance:review_decide', args=[b.pk]), {'hanh_dong': 'chap_thuan'}).status_code, 403)
        self.assertEqual(Attendance.objects.get(pk=b.pk).explanation_status, GT.PENDING)

    def test_chi_tiet_chi_chu_ban_ghi_va_nguoi_duyet_xem_duoc(self):
        b = self.cho_duyet()
        for nguoi in (self.gv1, self.ql, self.ql2):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('attendance:review_detail', args=[b.pk])).status_code, 200)
        for nguoi in (self.kt, self.pt, self.sa, self.gv2):
            self.dang_nhap(nguoi)
            self.assertContains(self.client.get(reverse('attendance:review_detail', args=[b.pk])),
                                'Bạn không có quyền xem bản ghi chấm công này.', status_code=403)
        self.dang_nhap(self.gv1)                                 # chủ bản ghi thấy chi tiết nhưng không có nút duyệt
        self.assertNotContains(self.client.get(reverse('attendance:review_detail', args=[b.pk])), 'Chấp thuận')

    def test_file_minh_chung_chi_chu_va_nguoi_duyet_tai_duoc(self):
        thu_muc = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, thu_muc, True)
        with override_settings(MEDIA_ROOT=thu_muc):
            b = self.cho_duyet()
            b.explanation_evidence.save('bien-lai.pdf', SimpleUploadedFile('bien-lai.pdf', b'%PDF-1.4 x'))
            url = reverse('core:tai_file', args=[b.explanation_evidence.name])
            for nguoi, ma in ((self.gv1, 200), (self.ql, 200), (self.sa, 200), (self.kt, 403), (self.gv2, 403)):
                self.dang_nhap(nguoi)
                r = self.client.get(url)
                self.assertEqual(r.status_code, ma, nguoi)
                if ma == 200:
                    r.close()
            self.dang_nhap(self.ql)
            self.assertContains(self.client.get(reverse('attendance:review_detail', args=[b.pk])), 'Xem file minh chứng')


# ---------------------------------------------------------------------------------- UC 4.5
class Uc45Test(NenTangCC):
    def test_uc4_5_basic_tong_hop_tung_nhan_su(self):
        # gv1 (Full-time): 2 ngày đúng giờ, 1 trễ chưa giải trình, 1 vắng đã giải trình (chờ duyệt), 1 thiếu check-out đã chấp thuận
        self.cc(self.gv1, ngay=date(2026, 10, 1))
        self.cc(self.gv1, ngay=date(2026, 10, 2))
        self.cc(self.gv1, ngay=date(2026, 10, 3), trang_thai=TT.LATE, tre=20)
        self.cc(self.gv1, ngay=date(2026, 10, 5), trang_thai=TT.ABSENT, giai_trinh=GT.PENDING)
        self.cc(self.gv1, ngay=date(2026, 10, 6), trang_thai=TT.ON_TIME, giai_trinh=GT.APPROVED)
        # pt (Part-time): 1 ca 4 giờ, về sớm 30 phút
        self.cc(self.pt, bd=time(8), kt=time(12), vao=luc(8, 0), ra=luc(11, 30), trang_thai=TT.EARLY_LEAVE, som=30)
        # gv2: không có bản ghi nào; kt: một lần thiếu check-out
        self.cc(self.kt, trang_thai=TT.MISSING_CHECKOUT)
        dong = {d['nhan_su'].full_name: d for d in services.tong_hop_cong(10, 2026)}
        g = dong['gv1@icls.vn']
        self.assertEqual((g['cong'], g['don_vi'], g['so_tre'], g['so_som'], g['so_vang'], g['so_thieu_checkout'], g['chua_giai_trinh'], g['cho_duyet']),
                         (Decimal('4'), 'ngày công', 1, 0, 1, 0, 1, 1))      # 2 đúng giờ + 1 trễ + 1 ON_TIME(được chấp thuận) = 4 công
        self.assertTrue(g['can_chu_y'])
        p = dong['pt@icls.vn']
        self.assertEqual((p['cong'], p['don_vi'], p['so_som'], p['can_chu_y']), (Decimal('3.50'), 'giờ công', 1, True))   # còn lỗi chưa giải trình
        self.assertEqual((dong['kt@icls.vn']['so_thieu_checkout'], dong['kt@icls.vn']['chua_giai_trinh']), (1, 1))
        t = dong['gv2@icls.vn']
        self.assertEqual((t['cong'], t['can_chu_y'], t['co_ban_ghi']), (Decimal('0'), False, False))
        self.assertNotIn('sa@icls.vn', dong)                                # Super Admin không có hồ sơ nhân sự

    def test_giai_trinh_da_xu_ly_khong_con_to_do(self):
        b = self.cc(self.gv1, trang_thai=TT.LATE, tre=20, giai_trinh=GT.PENDING)
        truoc = next(d for d in services.tong_hop_cong(10, 2026) if d['nhan_su'] == self.gv1)
        self.assertEqual((truoc['so_tre'], truoc['cho_duyet'], truoc['can_chu_y']), (1, 1, True))      # đang chờ duyệt: tô đỏ
        services.chap_thuan_giai_trinh(self.ql.user, b)
        d = next(d for d in services.tong_hop_cong(10, 2026) if d['nhan_su'] == self.gv1)
        self.assertEqual((d['so_tre'], d['cho_duyet'], d['chua_giai_trinh'], d['can_chu_y']), (0, 0, 0, False))

    def test_uc4_5_loc_phong_ban_vi_tri_va_chi_dung_thang(self):
        self.gv1.department = Department.HR_ADMIN
        self.gv1.save()
        self.cc(self.gv1, ngay=date(2026, 10, 1))
        self.cc(self.gv1, ngay=date(2026, 9, 1))
        ten = lambda ds: [d['nhan_su'].full_name for d in ds]
        self.assertEqual(ten(services.tong_hop_cong(10, 2026, phong_ban=Department.HR_ADMIN)), ['gv1@icls.vn'])
        self.assertEqual(ten(services.tong_hop_cong(10, 2026, vi_tri=Position.ACCOUNTANT)), ['kt@icls.vn'])
        self.assertEqual(services.tong_hop_cong(10, 2026, vi_tri=Position.ACCOUNTANT)[0]['cong'], Decimal('0'))
        self.assertEqual(next(d for d in services.tong_hop_cong(9, 2026) if d['nhan_su'] == self.gv1)['cong'], Decimal('1'))

    def test_nhan_su_da_nghi_nhung_co_cham_cong_trong_thang_van_hien(self):
        self.cc(self.gv1, ngay=date(2026, 10, 1))
        self.gv1.status = 'RESIGNED'
        self.gv1.save()
        self.assertIn(self.gv1, [d['nhan_su'] for d in services.tong_hop_cong(10, 2026)])
        self.assertNotIn(self.gv1, [d['nhan_su'] for d in services.tong_hop_cong(11, 2026)])

    def test_uc4_5_exc_3_1_thang_chua_co_du_lieu(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('attendance:summary'), {'thang': '2026-07'})
        self.assertContains(r, 'Không có dữ liệu chấm công trong khoảng thời gian đã chọn.')
        self.assertTrue(r.context['trong'])

    def test_uc4_5_basic_qua_man_hinh_va_chi_tiet_nhan_su(self):
        self.cc(self.gv1, ngay=date(2026, 10, 3), trang_thai=TT.LATE, tre=20)
        self.dang_nhap(self.kt)
        r = self.client.get(reverse('attendance:summary'), {'thang': '2026-10'})
        self.assertContains(r, 'Bảng tổng hợp công')
        self.assertContains(r, 'hang-do')                                     # dòng còn lỗi chưa giải trình được tô đỏ
        r = self.client.get(reverse('attendance:summary_detail', args=[self.gv1.pk]), {'thang': '2026-10'})
        self.assertContains(r, 'gv1@icls.vn')
        self.assertContains(r, '03/10/2026')
        self.assertContains(r, 'Trễ 20 phút')
        self.assertEqual(r.context['cong'], Decimal('1'))
        self.assertNotContains(r, 'Gửi giải trình')                          # xem chi tiết chỉ để xem
        self.assertEqual(self.client.get(reverse('attendance:summary_detail', args=[99999])).status_code, 404)

    def test_uc4_5_phan_quyen_chi_ql_kt_sa(self):
        for nguoi in (self.gv1, self.pt, self.tg):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('attendance:summary')).status_code, 403)
            self.assertEqual(self.client.get(reverse('attendance:summary_detail', args=[self.gv1.pk])).status_code, 403)
        for nguoi in (self.ql, self.kt, self.sa):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('attendance:summary')).status_code, 200)

    def test_menu_attendance_da_bat(self):
        self.dang_nhap(self.gv1)
        r = self.client.get(reverse('attendance:my_attendance'))
        self.assertTrue(any(m['url'] == reverse('attendance:my_attendance') for m in r.context['menu_chinh']))


# ============================================================ UC 9.2 – bước 4: chấm công của ngày hôm qua (P10)
class TacVuNgayChamCongTest(TestCase):
    """`ghi_nhan_cham_cong_ngay(ngay)`. Ngày xét: Thứ 2 26/10/2026 (ngày làm việc)."""
    NGAY = date(2026, 10, 26)

    def setUp(self):
        self.ft = hoat_dong('ft@icls.vn', loai_hinh=EmploymentType.FULL_TIME, ca=WorkShift.SHIFT_1)   # 08:00–17:00

    def test_khong_co_ban_ghi_thi_tao_absent_va_bao_nhan_su(self):
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(self.NGAY), (1, 0))
        b = Attendance.objects.get(employee=self.ft, work_date=self.NGAY)
        self.assertEqual((b.attendance_status, b.planned_start, b.planned_end), (TT.ABSENT, time(8), time(17)))
        tb = Notification.objects.get(recipient=self.ft.user)
        self.assertIn('vắng mặt ngày 26/10/2026', tb.message)

    def test_co_check_in_khong_check_out_thanh_missing_checkout(self):
        b = Attendance.objects.create(employee=self.ft, work_date=self.NGAY, planned_start=time(8), planned_end=time(17),
                                      check_in=datetime(2026, 10, 26, 8, 0), attendance_status=TT.ON_TIME)
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(self.NGAY), (0, 1))
        b.refresh_from_db()
        self.assertEqual(b.attendance_status, TT.MISSING_CHECKOUT)
        self.assertIn('check-out', Notification.objects.get(recipient=self.ft.user).message)

    def test_nghi_ca_ngay_da_duyet_va_ngay_khong_lam_viec_khong_bi_vang(self):
        LeaveRequest.objects.create(employee=self.ft, leave_type='ANNUAL', duration_type='FULL_DAY', start_date=self.NGAY,
                                    end_date=self.NGAY, total_days=1, reason='Việc nhà', status='APPROVED')
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(self.NGAY), (0, 0))
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(date(2026, 10, 25)), (0, 0))   # Chủ nhật

    def test_chay_lai_khong_tao_trung(self):
        services.ghi_nhan_cham_cong_ngay(self.NGAY)
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(self.NGAY), (0, 0))
        self.assertEqual(Attendance.objects.filter(employee=self.ft).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.ft.user).count(), 1)

    def test_nhan_su_chua_active_hoac_chua_vao_lam_khong_bi_tinh_vang(self):
        moi = hoat_dong('moi@icls.vn', loai_hinh=EmploymentType.FULL_TIME, ca=WorkShift.SHIFT_1)
        moi.join_date = date(2026, 10, 27)                                     # vào làm SAU ngày xét
        moi.save()
        tao = hoat_dong('onb@icls.vn', loai_hinh=EmploymentType.FULL_TIME, ca=WorkShift.SHIFT_1)
        tao.status = 'ONBOARDING'
        tao.save()
        self.assertEqual(services.ghi_nhan_cham_cong_ngay(self.NGAY), (1, 0))       # chỉ ft@icls.vn

    def test_uc4_1_alt_6_1_quen_check_out_tac_vu_hang_ngay_danh_dau_va_bao_giai_trinh(self):
        """UC 4.1 – luồng 6.1: check-in nhưng quên check-out → UC 9.2 ghi MISSING_CHECKOUT, báo nhân sự, và nhân sự
        giải trình được (UC 4.2)."""
        from dashboard.services import chay_tac_vu_ngay
        b = Attendance.objects.create(employee=self.ft, work_date=self.NGAY, planned_start=time(8), planned_end=time(17),
                                      check_in=datetime(2026, 10, 26, 8, 0), attendance_status=TT.ON_TIME)
        chay_tac_vu_ngay(date(2026, 10, 27))                      # chạy sáng hôm sau, như lịch 06:00
        b.refresh_from_db()
        self.assertEqual(b.attendance_status, TT.MISSING_CHECKOUT)
        self.assertTrue(Notification.objects.filter(recipient=self.ft.user, title__contains='check-out').exists())
        self.assertTrue(services.la_loi_co_the_giai_trinh(b))
