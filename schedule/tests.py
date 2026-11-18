"""Test của app schedule – P1: các ràng buộc CSDL (§7.3.8–7.3.11, §7.3.15)."""
from datetime import date, datetime, time

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.mau_test import tao_lop, tao_nhan_su
from schedule.models import ShiftAssignment, StudyClass, SubstituteRequest, TeachingSession


class RangBuocScheduleTest(TestCase):
    def test_lop_ngay_ket_thuc_truoc_ngay_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudyClass.objects.create(class_name='X', subject='s', weekdays='0', start_time=time(9),
                                      end_time=time(11), start_date=date(2026, 2, 1), end_date=date(2026, 1, 1))

    def test_lop_gio_ket_thuc_truoc_gio_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudyClass.objects.create(class_name='X', subject='s', weekdays='0', start_time=time(11),
                                      end_time=time(9), start_date=date(2026, 1, 1), end_date=date(2026, 2, 1))

    def _buoi(self, lop, gv, bd=time(9), kt=time(11)):
        return TeachingSession.objects.create(study_class=lop, session_date=date(2026, 10, 5), planned_start=bd,
                                              planned_end=kt, planned_teacher=gv)

    def test_buoi_day_gio_ket_thuc_truoc_gio_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._buoi(tao_lop(), tao_nhan_su(), bd=time(11), kt=time(9))

    def _cho(self, ma, nv=None, bd=time(8), kt=time(12)):
        return ShiftAssignment.objects.create(
            slot_group=ma, employee=nv, shift_role='Lễ tân', work_date=date(2026, 10, 5), planned_start=bd,
            planned_end=kt, registration_deadline=datetime(2026, 10, 4, 18))

    def test_mot_nguoi_khong_giu_hai_cho_trong_cung_khung_ca(self):
        nv = tao_nhan_su(loai_hinh='PART_TIME', ca='')
        self._cho('g1', nv)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._cho('g1', nv)

    def test_nhieu_cho_trong_cung_khung_ca_hop_le(self):
        self._cho('g1')
        self._cho('g1')
        self.assertEqual(ShiftAssignment.objects.filter(slot_group='g1').count(), 2)

    def test_ca_gio_ket_thuc_truoc_gio_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._cho('g2', bd=time(12), kt=time(8))

    def test_mot_buoi_chi_mot_yeu_cau_day_thay_dang_tim(self):
        buoi = self._buoi(tao_lop(), tao_nhan_su())
        SubstituteRequest.objects.create(teaching_session=buoi)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubstituteRequest.objects.create(teaching_session=buoi)


# =====================================================================================================
# P6 – UC 6.1, 6.2, 6.3. Tên test bám mã luồng ở §10 (xem ROADMAP §12.1).
# =====================================================================================================
from datetime import timedelta

from django.urls import reverse

from accounts.models import User, UserRole
from core import thong_bao
from core.models import ActivityLog, Notification
from core.services import LoiNghiepVu
from employees.models import Employee, EmployeeStatus, EmploymentType, Position, WorkShift
from leave.models import LeaveRequest
from recruitment.models import Candidate, RecruitmentCampaign, RecruitmentRound
from schedule import services
from schedule.models import (ClassAssignment, ClassStatus, ShiftStatus, SubstituteRequest, SubstituteStatus,
                             TeachingSessionStatus)


def nv_hoat_dong(email, vai_tro=UserRole.EMPLOYEE, chuc_danh=Position.STAFF, loai_hinh=EmploymentType.PART_TIME, ca=''):
    """Nhân sự đang làm việc (tao_nhan_su mặc định ONBOARDING nên đổi sang ACTIVE)."""
    nv = tao_nhan_su(email, vai_tro, chuc_danh, loai_hinh, ca)
    nv.status = EmployeeStatus.ACTIVE
    nv.save()
    return nv


def gv_ft(email, ca):
    return nv_hoat_dong(email, chuc_danh=Position.TEACHER, loai_hinh=EmploymentType.FULL_TIME, ca=ca)


def du_lieu_lop(**ghi_de):
    # 05/10/2026 là Thứ 2 → Thứ 2, 4, 6 trong 2 tuần: 5, 7, 9, 12, 14, 16/10 = 6 buổi
    du_lieu = dict(class_name='TOPIK 2', subject='Trung cấp', room_name='Phòng 201', max_students=20,
                   start_date=date(2026, 10, 5), end_date=date(2026, 10, 16), weekdays='0,2,4',
                   start_time=time(18), end_time=time(20))
    du_lieu.update(ghi_de)
    return du_lieu


def du_lieu_post(**ghi_de):
    """Dữ liệu form bước 1 dạng chuỗi như trình duyệt gửi lên."""
    d = du_lieu_lop(**ghi_de)
    return {'class_name': d['class_name'], 'subject': d['subject'], 'room_name': d['room_name'],
            'max_students': d['max_students'], 'start_date': f"{d['start_date']:%Y-%m-%d}",
            'end_date': f"{d['end_date']:%Y-%m-%d}", 'weekdays': d['weekdays'].split(','),
            'start_time': f"{d['start_time']:%H:%M}", 'end_time': f"{d['end_time']:%H:%M}"}


class NenTang(TestCase):
    """Dữ liệu chung: 1 quản lý, giáo viên Ca 1 / Ca 2, trợ giảng, nhân viên Part-time."""

    def setUp(self):
        self.ql = nv_hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER, EmploymentType.FULL_TIME)
        self.gv_ca2 = gv_ft('gv2@icls.vn', WorkShift.SHIFT_2)
        self.gv_ca1 = gv_ft('gv1@icls.vn', WorkShift.SHIFT_1)
        # Chỉ lớp có giáo viên người Hàn Quốc mới có trợ giảng
        Employee.objects.filter(pk__in=[self.gv_ca1.pk, self.gv_ca2.pk]).update(nationality='Hàn Quốc')
        self.gv_ca1.refresh_from_db()
        self.gv_ca2.refresh_from_db()
        self.tg = nv_hoat_dong('tg@icls.vn', chuc_danh=Position.TEACHING_ASSISTANT)
        self.pt1 = nv_hoat_dong('pt1@icls.vn')
        self.pt2 = nv_hoat_dong('pt2@icls.vn')
        self.pt3 = nv_hoat_dong('pt3@icls.vn')

    def dang_nhap(self, nhan_su):
        self.client.force_login(nhan_su.user)

    def tao_lop_san(self, gv=None, tro_giang=None, **ghi_de):
        return services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(**ghi_de), gv or self.gv_ca2, tro_giang)


class TroGiangChiLopGiaoVienHanTest(NenTang):
    def test_giao_vien_viet_nam_khong_duoc_co_tro_giang(self):
        Employee.objects.filter(pk=self.gv_ca2.pk).update(nationality='Việt Nam')
        self.gv_ca2.refresh_from_db()
        with self.assertRaises(services.LoiTruongNhap):
            self.tao_lop_san(tro_giang=self.tg)
        lop, _ = self.tao_lop_san()                      # không trợ giảng thì vẫn tạo được
        self.assertFalse(lop.assignments.filter(assignment_role='TEACHING_ASSISTANT').exists())

    def test_giao_vien_han_quoc_co_tro_giang(self):
        lop, _ = self.tao_lop_san(tro_giang=self.tg)
        self.assertTrue(lop.assignments.filter(assignment_role='TEACHING_ASSISTANT').exists())


# ---------------------------------------------------------------------------------- Trùng lịch (§9.2)
class TrungLichTest(NenTang):
    NGAY = date(2026, 10, 5)

    def test_hai_khoang_gio_cham_nhau_khong_tinh_la_trung(self):
        self.tao_lop_san()                                        # gv_ca2 dạy 18:00–20:00 ngày 5/10
        self.assertTrue(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(19), time(21)))
        self.assertTrue(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(17), time(18, 30)))
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(20), time(21)))   # bắt đầu đúng lúc kết thúc
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(16), time(18)))
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, date(2026, 10, 6), time(18), time(20)))  # ngày khác

    def test_buoi_da_huy_khong_tinh_trung(self):
        lop, _ = self.tao_lop_san()
        lop.teaching_sessions.update(status=TeachingSessionStatus.CANCELLED)
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(18), time(20)))

    def test_tro_giang_thuc_te_cung_bi_tinh_trung(self):
        self.tao_lop_san(tro_giang=self.tg)
        self.assertTrue(services.kiem_tra_trung_lich(self.tg, self.NGAY, time(18), time(20)))

    def test_cho_ca_chi_tinh_khi_da_co_nguoi_dang_ky(self):
        ma = services.tao_khung_ca(self.ql.user, 'Lễ tân', self.NGAY, time(9), time(12), 2, datetime(2026, 10, 4, 18))
        self.assertFalse(services.kiem_tra_trung_lich(self.pt1, self.NGAY, time(9), time(12)))   # chỗ OPEN chưa của ai
        services.dang_ky_ca(self.pt1, ma, datetime(2026, 10, 1, 8))
        self.assertTrue(services.kiem_tra_trung_lich(self.pt1, self.NGAY, time(10), time(11)))

    def test_vong_tuyen_dung_60_phut(self):
        chien_dich = RecruitmentCampaign.objects.create(campaign_name='Đợt 1', start_date=date(2026, 10, 1))
        ung_vien = Candidate.objects.create(campaign=chien_dich, full_name='UV', email='uv@x.vn', phone='0900000001',
                                            position=Position.TEACHER, employment_type=EmploymentType.FULL_TIME)
        RecruitmentRound.objects.create(candidate=ung_vien, round_type='INTERVIEW', interviewer=self.ql.user,
                                        scheduled_at=datetime(2026, 10, 5, 9, 0))        # 09:00–10:00
        self.assertTrue(services.kiem_tra_trung_lich(self.ql, self.NGAY, time(9, 30), time(11)))
        self.assertFalse(services.kiem_tra_trung_lich(self.ql, self.NGAY, time(10), time(11)))

    def test_don_nghi_ca_ngay_trung_moi_khung_gio(self):
        LeaveRequest.objects.create(employee=self.gv_ca2, leave_type='SICK',
                                    start_date=self.NGAY, end_date=self.NGAY, total_days=1, reason='x', status='APPROVED')
        self.assertTrue(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(18), time(20)))
        self.assertTrue(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(13), time(14)))

    def test_don_nghi_chua_duyet_khong_tinh(self):
        LeaveRequest.objects.create(employee=self.gv_ca2, leave_type='SICK',
                                    start_date=self.NGAY, end_date=self.NGAY, total_days=1, reason='x', status='PENDING')
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, self.NGAY, time(18), time(20)))


# ---------------------------------------------------------------------------------- UC 6.1
class Uc61Test(NenTang):
    def test_tinh_ngay_hoc(self):
        ngay = services.tinh_ngay_hoc(date(2026, 10, 5), date(2026, 10, 16), [0, 2, 4])
        self.assertEqual(ngay, [date(2026, 10, d) for d in (5, 7, 9, 12, 14, 16)])

    def test_uc6_1_chi_goi_y_giao_vien_co_ca_bao_tron_gio_hoc(self):
        ngay = services.tinh_ngay_hoc(date(2026, 10, 5), date(2026, 10, 16), [0, 2, 4])
        ten = lambda ds: sorted(nv.full_name for nv in ds)
        self.assertEqual(ten(services.goi_y_giao_vien(ngay, time(18), time(20), chi_full_time=True)), ['gv2@icls.vn'])
        self.assertEqual(ten(services.goi_y_giao_vien(ngay, time(9), time(11), chi_full_time=True)), ['gv1@icls.vn'])
        self.assertEqual(ten(services.goi_y_giao_vien(ngay, time(14), time(16), chi_full_time=True)),
                         ['gv1@icls.vn', 'gv2@icls.vn'])
        self.assertEqual(services.goi_y_giao_vien(ngay, time(7), time(9), chi_full_time=True), [])   # trước cả hai ca

    def test_goi_y_loai_giao_vien_nghi_viec_hoac_dang_onboarding(self):
        self.gv_ca2.status = EmployeeStatus.RESIGNED
        self.gv_ca2.save()
        ngay = services.tinh_ngay_hoc(date(2026, 10, 5), date(2026, 10, 16), [0, 2, 4])
        self.assertEqual(services.goi_y_giao_vien(ngay, time(18), time(20), chi_full_time=True), [])

    def test_uc6_1_basic_sinh_dung_so_buoi_va_phan_cong(self):
        lop, so_buoi = self.tao_lop_san(tro_giang=self.tg)
        self.assertEqual(so_buoi, 6)
        self.assertEqual(lop.status, ClassStatus.UPCOMING)
        self.assertEqual(lop.weekdays, '0,2,4')
        self.assertEqual(lop.teaching_sessions.count(), 6)
        self.assertEqual({b.session_date.weekday() for b in lop.teaching_sessions.all()}, {0, 2, 4})
        for b in lop.teaching_sessions.all():
            self.assertEqual((b.status, b.room_name), (TeachingSessionStatus.SCHEDULED, 'Phòng 201'))
            self.assertEqual((b.planned_teacher, b.actual_teacher), (self.gv_ca2, self.gv_ca2))
            self.assertEqual((b.planned_assistant, b.actual_assistant), (self.tg, self.tg))
        vai_tro = {pc.employee_id: pc.assignment_role for pc in lop.assignments.all()}
        self.assertEqual(vai_tro, {self.gv_ca2.pk: 'MAIN_TEACHER', self.tg.pk: 'TEACHING_ASSISTANT'})
        self.assertTrue(all(pc.end_date is None for pc in lop.assignments.all()))
        # Giáo viên và trợ giảng đều nhận thông báo
        self.assertEqual(Notification.objects.filter(recipient=self.gv_ca2.user, title=thong_bao.TB_LOP_MOI_TIEU_DE).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.tg.user, title=thong_bao.TB_LOP_MOI_TIEU_DE).count(), 1)

    def test_uc6_1_basic_khong_co_tro_giang(self):
        lop, _ = self.tao_lop_san()
        self.assertEqual(lop.assignments.count(), 1)
        self.assertIsNone(lop.teaching_sessions.first().actual_assistant)

    def test_uc6_1_basic_qua_man_hinh_hai_buoc(self):
        self.dang_nhap(self.ql)
        buoc1 = self.client.post(reverse('schedule:class_create'), {**du_lieu_post(), 'buoc': '1'})
        self.assertEqual(buoc1.status_code, 200)
        self.assertContains(buoc1, 'Phân công giáo viên')
        self.assertContains(buoc1, 'gv2@icls.vn')
        self.assertNotContains(buoc1, 'gv1@icls.vn')               # Ca 1 không bao trọn 18:00–20:00
        self.assertEqual(StudyClass.objects.count(), 0)            # bước 1 chưa ghi gì vào CSDL
        buoc2 = self.client.post(reverse('schedule:class_create'), {
            **du_lieu_post(), 'buoc': '2', 'giao_vien': self.gv_ca2.pk, 'tro_giang': self.tg.pk}, follow=True)
        self.assertContains(buoc2, 'Tạo lớp và phân công thành công (6 buổi).')
        lop = StudyClass.objects.get()
        self.assertRedirects(buoc2, reverse('schedule:class_detail', args=[lop.pk]))

    def test_uc6_1_alt_quay_lai_buoc_1_giu_nguyen_du_lieu(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_create'), {**du_lieu_post(), 'buoc': '0'})
        self.assertContains(r, 'value="TOPIK 2"')
        self.assertContains(r, 'Thông tin lớp')

    def test_uc6_1_alt_1_1_huy_lop(self):
        lop, _ = self.tao_lop_san(tro_giang=self.tg)
        buoi_se_huy = lop.teaching_sessions.get(session_date=date(2026, 10, 12))
        yeu_cau = SubstituteRequest.objects.create(teaching_session=buoi_se_huy)
        so_buoi = services.huy_lop(self.ql.user, lop, 'Không đủ học viên', hom_nay=date(2026, 10, 9))
        self.assertEqual(so_buoi, 4)                                # 9, 12, 14, 16/10
        lop.refresh_from_db()
        self.assertEqual(lop.status, ClassStatus.CANCELLED)
        da_huy = set(lop.teaching_sessions.filter(status='CANCELLED').values_list('session_date', flat=True))
        self.assertEqual(da_huy, {date(2026, 10, d) for d in (9, 12, 14, 16)})
        self.assertEqual(lop.teaching_sessions.filter(status='SCHEDULED').count(), 2)     # 5, 7/10 đã qua: giữ nguyên
        yeu_cau.refresh_from_db()
        self.assertEqual(yeu_cau.status, SubstituteStatus.FAILED)
        self.assertTrue(all(pc.end_date == date(2026, 10, 9) for pc in lop.assignments.all()))
        for nguoi in (self.gv_ca2, self.tg):
            self.assertTrue(Notification.objects.filter(recipient=nguoi.user, title=thong_bao.TB_HUY_LOP_TIEU_DE).exists())
        # Giáo viên rảnh lại: lớp mới cùng giờ không còn bị trùng
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, date(2026, 10, 12), time(18), time(20)))

    def test_huy_lop_phan_cong_chua_bat_dau_end_date_khong_truoc_start_date(self):
        lop, _ = self.tao_lop_san()
        services.huy_lop(self.ql.user, lop, 'x', hom_nay=date(2026, 9, 1))     # hủy trước ngày khai giảng
        self.assertEqual(ClassAssignment.objects.get(study_class=lop).end_date, date(2026, 10, 5))

    def test_huy_lop_phai_co_ly_do_va_dung_trang_thai(self):
        lop, _ = self.tao_lop_san()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.NHAP_LY_DO_HUY_LOP):
            services.huy_lop(self.ql.user, lop, '  ')
        services.huy_lop(self.ql.user, lop, 'x', hom_nay=date(2026, 10, 1))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.LOP_KHONG_HUY_DUOC):
            services.huy_lop(self.ql.user, lop, 'x')

    def test_uc6_1_alt_1_1_huy_lop_qua_view(self):
        lop, _ = self.tao_lop_san()
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_cancel', args=[lop.pk]), {'ly_do': 'Nghỉ dịch'}, follow=True)
        lop.refresh_from_db()
        self.assertEqual(lop.status, ClassStatus.CANCELLED)
        self.assertContains(r, 'Đã hủy lớp')

    def test_uc6_1_exc_3_1_du_lieu_sai_hien_loi_tai_truong(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_create'), {
            **du_lieu_post(start_time=time(20), end_time=time(18), end_date=date(2026, 10, 1)), 'buoc': '1'})
        self.assertContains(r, thong_bao.GIO_KET_THUC_LOP_SAI)
        self.assertContains(r, thong_bao.NGAY_KET_THUC_LOP_SAI)
        r = self.client.post(reverse('schedule:class_create'), {'buoc': '1'})
        self.assertContains(r, 'Trường này là bắt buộc')
        self.assertContains(r, thong_bao.CHON_THU_HOC)
        self.assertEqual(StudyClass.objects.count(), 0)

    def test_uc6_1_exc_3_1_khoang_ngay_khong_co_ngay_hoc(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_create'), {            # 5/10 (Thứ 2) → 6/10 (Thứ 3), chỉ học Thứ 7
            **du_lieu_post(end_date=date(2026, 10, 6), weekdays='5'), 'buoc': '1'})
        self.assertContains(r, thong_bao.KHONG_CO_NGAY_HOC)

    def test_uc6_1_exc_3_2_phong_bi_trung(self):
        self.tao_lop_san(gv=self.gv_ca2)                                     # Phòng 201, 18:00–20:00
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_create'), {
            **du_lieu_post(class_name='Lớp khác', start_time=time(19), end_time=time(21)), 'buoc': '1'})
        self.assertContains(r, 'Phòng Phòng 201 đã có lớp khác vào khung giờ này.')
        self.assertEqual(StudyClass.objects.count(), 1)

    def test_phong_khac_ten_hoac_khac_gio_khong_bi_trung(self):
        self.tao_lop_san()
        ngay = services.tinh_ngay_hoc(date(2026, 10, 5), date(2026, 10, 16), [0, 2, 4])
        self.assertTrue(services.kiem_tra_trung_phong('phòng 201', ngay, time(19), time(21)))       # không phân biệt hoa thường
        self.assertFalse(services.kiem_tra_trung_phong('Phòng 202', ngay, time(19), time(21)))
        self.assertFalse(services.kiem_tra_trung_phong('Phòng 201', ngay, time(20), time(21)))
        self.assertFalse(services.kiem_tra_trung_phong('', ngay, time(19), time(21)))               # chưa có phòng: bỏ qua

    def test_uc6_1_exc_3_3_khong_co_giao_vien_phu_hop(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:class_create'), {
            **du_lieu_post(start_time=time(6), end_time=time(7)), 'buoc': '1'})     # trước mọi ca làm việc
        self.assertContains(r, thong_bao.KHONG_CO_GIAO_VIEN)
        self.assertEqual(StudyClass.objects.count(), 0)

    def test_uc6_1_exc_3_3_giao_vien_bi_trung_lich_het_nguoi(self):
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng A')
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.KHONG_CO_GIAO_VIEN):
            services.chuan_bi_phan_cong(du_lieu_lop(room_name='Phòng B'))

    def test_uc6_1_exc_6_1_giao_vien_vua_bi_trung_lich(self):
        # Quản lý đang ở bước 6 chọn gv_ca2; trong lúc đó lớp khác chiếm giáo viên này
        du_lieu = du_lieu_lop(room_name='Phòng B')
        self.assertIn(self.gv_ca2, services.chuan_bi_phan_cong(du_lieu)['giao_vien'])
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng A')
        so_lop = StudyClass.objects.count()
        with self.assertRaises(services.LoiTruongNhap) as ctx:
            services.tao_lop_va_phan_cong(self.ql.user, du_lieu, self.gv_ca2)
        self.assertEqual(str(ctx.exception), 'Giáo viên bị trùng lịch, vui lòng chọn lại.')
        self.assertEqual(StudyClass.objects.count(), so_lop)         # không lưu gì
        self.assertEqual(TeachingSession.objects.count(), 6)

    def test_uc6_1_exc_6_1_qua_view_quay_lai_buoc_6(self):
        self.dang_nhap(self.ql)
        du_lieu = du_lieu_post(room_name='Phòng B')
        # giáo viên Ca 2 bị chiếm lịch (lớp khác) rồi quản lý mới bấm xác nhận
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng A')
        r = self.client.post(reverse('schedule:class_create'), {**du_lieu, 'buoc': '2', 'giao_vien': self.gv_ca2.pk})
        self.assertEqual(StudyClass.objects.count(), 1)
        self.assertContains(r, thong_bao.KHONG_CO_GIAO_VIEN)        # hết giáo viên → về lại bước 1 báo lỗi 3.3

    def test_chi_giao_vien_goi_y_moi_duoc_chon(self):
        with self.assertRaises(services.LoiTruongNhap) as ctx:
            services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(), self.gv_ca1)    # Ca 1 không bao trọn 18–20h
        self.assertEqual(str(ctx.exception), thong_bao.GIAO_VIEN_KHONG_HOP_LE)
        with self.assertRaises(services.LoiTruongNhap) as ctx:
            services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(), self.gv_ca2, self.pt1)   # PT staff không phải trợ giảng
        self.assertEqual(str(ctx.exception), thong_bao.TRO_GIANG_KHONG_HOP_LE)

    def test_tro_giang_trung_lich_bi_chan(self):
        self.tao_lop_san(gv=self.gv_ca2, tro_giang=self.tg, room_name='Phòng A')
        gv_khac = gv_ft('gv2b@icls.vn', WorkShift.SHIFT_2)
        Employee.objects.filter(pk=gv_khac.pk).update(nationality='Hàn Quốc')     # chỉ lớp GV người Hàn mới có trợ giảng
        gv_khac.refresh_from_db()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.TRO_GIANG_TRUNG_LICH):
            services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(room_name='Phòng B'), gv_khac, self.tg)

    def test_phan_quyen_tao_lop_chi_quan_ly(self):
        for nv in (self.gv_ca2, self.pt1):
            self.dang_nhap(nv)
            self.assertEqual(self.client.get(reverse('schedule:class_create')).status_code, 403)
            self.assertEqual(self.client.post(reverse('schedule:class_cancel', args=[1])).status_code, 403)
        self.dang_nhap(self.ql)
        self.assertEqual(self.client.get(reverse('schedule:class_create')).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('schedule:class_create')).status_code, 302)   # chưa đăng nhập → trang đăng nhập


# ---------------------------------------------------------------------------------- UC 6.2
class Uc62Test(NenTang):
    TUAN = '2026-10-05'

    def ca_da_chot(self, nhan_vien, vai_tro='Lễ tân', ngay=date(2026, 10, 6)):
        return ShiftAssignment.objects.create(
            slot_group=f'g-{nhan_vien.pk}-{vai_tro}', employee=nhan_vien, shift_role=vai_tro, work_date=ngay,
            planned_start=time(8), planned_end=time(12), registration_deadline=datetime(2026, 10, 1, 18),
            status=ShiftStatus.SCHEDULED, assigned_by=self.ql.user)

    def tieu_de(self, response):
        """Tên các ô trên bảng tuần (bỏ ca cố định Full-time và ô nghỉ phép – chỉ là nền)."""
        bang = response.context['bang']
        if bang is None:
            return []
        return sorted(m.get('ten_lop', m['tieu_de']) for h in bang['hang'] for o in h['cac_o'] for m in o
                      if not m.get('nen') and m['loai'] != 'nghi')

    def test_uc6_2_basic_quan_ly_thay_ca_toan_trung_tam_va_loc_theo_nhan_su(self):
        self.ca_da_chot(self.pt1, 'Lễ tân')
        self.ca_da_chot(self.pt2, 'Tư vấn')
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertEqual(self.tieu_de(r), ['Lễ tân', 'Tư vấn'])
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN, 'nv': self.pt1.pk})
        self.assertEqual(self.tieu_de(r), ['Lễ tân'])

    def test_uc6_2_basic_nhan_vien_chi_thay_lich_cua_minh(self):
        self.ca_da_chot(self.pt1, 'Lễ tân')
        self.ca_da_chot(self.pt2, 'Tư vấn')
        self.tao_lop_san(gv=self.gv_ca2, tro_giang=self.tg)
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertEqual(self.tieu_de(r), ['Lễ tân'])                        # không thấy ca của pt2, không thấy buổi dạy
        self.dang_nhap(self.tg)                                              # trợ giảng thấy buổi dạy mình hỗ trợ
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertEqual(self.tieu_de(r), ['TOPIK 2'] * 3)                   # 5, 7, 9/10
        self.dang_nhap(self.gv_ca2)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertEqual(self.tieu_de(r), ['TOPIK 2'] * 3)

    def test_uc6_2_ke_toan_chi_thay_cua_minh_va_giam_doc_thay_het(self):
        ke_toan = nv_hoat_dong('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, EmploymentType.FULL_TIME)
        self.ca_da_chot(self.pt1)
        self.dang_nhap(ke_toan)
        self.assertEqual(self.tieu_de(self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})), [])
        sa = User.objects.create_user('gd@icls.vn', 'x', role=UserRole.DIRECTOR, full_name='Giám đốc')
        self.client.force_login(sa)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertEqual(self.tieu_de(r), ['Lễ tân'])

    def test_cho_ca_con_trong_khong_hien_tren_lich(self):
        cho = self.ca_da_chot(self.pt1)
        cho.employee, cho.status = None, ShiftStatus.OPEN
        cho.save()
        self.dang_nhap(self.ql)
        self.assertEqual(self.tieu_de(self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})), [])

    def test_uc6_2_basic_tab_lich_lop_hoc_ai_cung_xem_toan_trung_tam(self):
        self.tao_lop_san(gv=self.gv_ca2)
        for nv in (self.pt1, self.gv_ca1, self.ql):
            self.dang_nhap(nv)
            r = self.client.get(reverse('schedule:calendar'), {'tab': 'lop_hoc', 'ngay': self.TUAN})
            self.assertEqual(self.tieu_de(r), ['TOPIK 2'] * 3)
            self.assertContains(r, 'gv2@icls.vn')

    def test_loc_lich_lop_chi_danh_cho_quan_ly(self):
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng A')
        gv_b = gv_ft('gvb@icls.vn', WorkShift.SHIFT_2)
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp B', room_name='Phòng B'), gv_b)  # gv_ca2 bận nên chọn gv_b
        self.dang_nhap(self.ql)
        tham_so = {'tab': 'lop_hoc', 'ngay': self.TUAN}
        self.assertEqual(self.tieu_de(self.client.get(reverse('schedule:calendar'), {**tham_so, 'gv': gv_b.pk})), ['Lớp B'] * 3)
        self.dang_nhap(self.pt1)      # nhân viên truyền bộ lọc thì bị bỏ qua, vẫn thấy cả hai lớp
        self.assertEqual(len(self.tieu_de(self.client.get(reverse('schedule:calendar'), {**tham_so, 'gv': gv_b.pk}))), 6)

    def test_uc6_2_basic_chi_xem_theo_tuan(self):
        self.tao_lop_san()
        self.dang_nhap(self.ql)
        tuan = self.client.get(reverse('schedule:calendar'), {'tab': 'lop_hoc', 'ngay': '2026-10-12', 'che_do': 'ngay'})
        self.assertEqual(tuan.context['url_truoc'], '?tab=lop_hoc&ngay=2026-10-05')     # tham số che_do cũ bị bỏ qua
        self.assertEqual(tuan.context['url_sau'], '?tab=lop_hoc&ngay=2026-10-19')
        self.assertContains(tuan, '12 – 18 tháng 10, 2026')
        self.assertNotContains(tuan, '>Ngày</a>')

    def test_ngay_sai_dinh_dang_dung_hom_nay_khong_sap(self):
        self.dang_nhap(self.ql)
        self.assertEqual(self.client.get(reverse('schedule:calendar'), {'ngay': 'abc', 'nv': 'xyz'}).status_code, 200)

    def test_uc6_2_exc_3_1_khong_co_lich(self):
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': '2026-12-07'})
        self.assertContains(r, 'Không có lịch trình trong thời gian này.')

    def test_uc6_2_exc_1_1_khong_xem_lich_nguoi_khac(self):
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:calendar'), {'nv': self.pt2.pk})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, 'Bạn không có quyền xem lịch cá nhân của người khác.', status_code=403)
        self.assertEqual(self.client.get(reverse('schedule:calendar'), {'nv': self.pt1.pk}).status_code, 200)
        cho_cua_pt2 = self.ca_da_chot(self.pt2)
        r = self.client.get(reverse('schedule:shift_detail', args=[cho_cua_pt2.pk]))
        self.assertContains(r, 'Bạn không có quyền xem lịch cá nhân của người khác.', status_code=403)

    def test_bam_ca_tren_lich_mo_trang_khung_ca(self):
        cho = self.ca_da_chot(self.pt1)
        cho_khac = ShiftAssignment.objects.create(                                 # cùng khung, người khác
            slot_group=cho.slot_group, employee=self.pt2, shift_role='Lễ tân', work_date=cho.work_date,
            planned_start=time(8), planned_end=time(12), registration_deadline=datetime(2026, 10, 1, 18),
            status=ShiftStatus.SCHEDULED, assigned_by=self.ql.user)
        self.dang_nhap(self.pt1)                                                   # nhân viên: chỉ thấy chỗ của mình
        r = self.client.get(reverse('schedule:shift_detail', args=[cho.pk]))
        self.assertTemplateUsed(r, 'schedule/khung_ca.html')
        self.assertEqual(r.context['cac_cho'], [cho])
        self.assertNotContains(r, 'pt2@icls.vn')
        self.assertNotContains(r, 'Gỡ người')
        self.dang_nhap(self.ql)                                                    # Quản lý: thấy cả khung, gỡ / gán được
        r = self.client.get(reverse('schedule:shift_detail', args=[cho.pk]))
        self.assertEqual(list(r.context['cac_cho']), list(ShiftAssignment.objects.filter(slot_group=cho.slot_group)))
        self.assertIn(cho_khac, r.context['cac_cho'])
        self.assertContains(r, 'Gỡ người')

    def test_uc6_2_basic_chi_tiet_buoi_day(self):
        lop, _ = self.tao_lop_san(tro_giang=self.tg)
        buoi = lop.teaching_sessions.first()
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:session_detail', args=[buoi.pk]))
        for chu in ('TOPIK 2', 'Phòng 201', '18:00–20:00', 'gv2@icls.vn', 'tg@icls.vn', 'Đã lên lịch'):
            self.assertContains(r, chu)
        self.assertNotContains(r, 'Ghi nội dung buổi học')          # người xem không phải giáo viên: không có ô ghi

    def test_uc6_2_alt_5_1_giao_vien_thuc_te_ghi_noi_dung_buoi_hoc(self):
        lop, _ = self.tao_lop_san(tro_giang=self.tg)
        buoi = lop.teaching_sessions.first()
        self.dang_nhap(self.gv_ca2)
        r = self.client.post(reverse('schedule:session_detail', args=[buoi.pk]), {'lesson_note': 'Bài 1: Chào hỏi'}, follow=True)
        self.assertContains(r, 'Đã lưu nội dung buổi học.')
        buoi.refresh_from_db()
        self.assertEqual(buoi.lesson_note, 'Bài 1: Chào hỏi')

    def test_ghi_noi_dung_nguoi_khac_bi_chan(self):
        lop, _ = self.tao_lop_san(tro_giang=self.tg)
        buoi = lop.teaching_sessions.first()
        for nv in (self.tg, self.gv_ca1, self.ql):          # trợ giảng, giáo viên khác, kể cả quản lý
            self.dang_nhap(nv)
            r = self.client.post(reverse('schedule:session_detail', args=[buoi.pk]), {'lesson_note': 'hack'})
            self.assertEqual(r.status_code, 403)
        buoi.refresh_from_db()
        self.assertEqual(buoi.lesson_note, '')

    def test_giao_vien_day_thay_moi_la_giao_vien_thuc_te(self):
        lop, _ = self.tao_lop_san()
        buoi = lop.teaching_sessions.first()
        buoi.actual_teacher = self.gv_ca1                   # mô phỏng dạy thay (UC 6.4 làm ở P7)
        buoi.save()
        self.dang_nhap(self.gv_ca1)
        self.client.post(reverse('schedule:session_detail', args=[buoi.pk]), {'lesson_note': 'Dạy thay'})
        buoi.refresh_from_db()
        self.assertEqual(buoi.lesson_note, 'Dạy thay')
        self.dang_nhap(self.gv_ca2)                         # giáo viên dự kiến không còn quyền
        self.assertEqual(self.client.post(reverse('schedule:session_detail', args=[buoi.pk]), {'lesson_note': 'x'}).status_code, 403)

    def test_menu_schedule_da_bat(self):
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:calendar'))
        self.assertTrue(any(m['url'] == reverse('schedule:calendar') for m in r.context['menu_chinh']))


# ---------------------------------------------------------------------------------- UC 6.3
class Uc63Test(NenTang):
    NGAY = date(2026, 10, 12)
    HAN = datetime(2026, 10, 10, 18)
    TRUOC_HAN = datetime(2026, 10, 8, 9)
    SAU_HAN = datetime(2026, 10, 10, 18, 1)

    def mo_khung(self, so_nguoi=2, vai_tro='Lễ tân', bd=time(9), kt=time(12)):
        return services.tao_khung_ca(self.ql.user, vai_tro, self.NGAY, bd, kt, so_nguoi, self.HAN)

    def cac_cho(self, ma):
        return list(ShiftAssignment.objects.filter(slot_group=ma).order_by('pk'))

    # ----- bước 1–2
    def test_uc6_3_basic_tao_dung_n_dong_cung_slot_group_va_moi_part_time(self):
        ma = self.mo_khung(3)
        cho = self.cac_cho(ma)
        self.assertEqual(len(cho), 3)
        self.assertTrue(all(c.employee is None and c.status == ShiftStatus.OPEN and c.slot_group == ma for c in cho))
        self.assertTrue(all(c.registration_deadline == self.HAN for c in cho))
        da_moi = set(Notification.objects.filter(title=thong_bao.TB_MOI_DANG_KY_CA_TIEU_DE).values_list('recipient_id', flat=True))
        self.assertEqual(da_moi, {self.pt1.user_id, self.pt2.user_id, self.pt3.user_id, self.tg.user_id})
        self.assertNotIn(self.gv_ca2.user_id, da_moi)             # Full-time không được mời

    def test_uc6_3_basic_tao_khung_qua_view(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:shift_create'), {
            'vai_tro': 'Tư vấn', 'ngay': '2026-10-12', 'bat_dau': '13:00', 'ket_thuc': '17:00', 'so_nguoi': 2,
            'han_chot': '2026-10-10T18:00'}, follow=True)
        self.assertEqual(ShiftAssignment.objects.filter(shift_role='Tư vấn').count(), 2)
        self.assertContains(r, 'Đã tạo khung ca Tư vấn ngày 12/10/2026 (2 chỗ)')

    def test_tao_khung_han_chot_phai_truoc_gio_bat_dau(self):
        with self.assertRaises(services.LoiTruongNhap) as ctx:
            services.tao_khung_ca(self.ql.user, 'Lễ tân', self.NGAY, time(9), time(12), 1, datetime(2026, 10, 12, 9, 0))
        self.assertEqual(str(ctx.exception), thong_bao.HAN_CHOT_CA_SAI)
        self.assertEqual(ShiftAssignment.objects.count(), 0)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:shift_create'), {
            'vai_tro': 'x', 'ngay': '2026-10-12', 'bat_dau': '09:00', 'ket_thuc': '08:00', 'so_nguoi': 0,
            'han_chot': '2026-10-13T09:00'})
        self.assertContains(r, thong_bao.GIO_KET_THUC_LOP_SAI)
        self.assertContains(r, thong_bao.SO_NGUOI_CA_SAI)

    # ----- Đăng ký là có ca ngay (bản đơn giản: Trống ↔ Đã có người)
    def test_uc6_3_basic_dang_ky_la_co_ca_ngay(self):
        ma = self.mo_khung(2)
        cho = services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        self.assertEqual((cho.employee, cho.status, cho.registered_at), (self.pt1, ShiftStatus.SCHEDULED, self.TRUOC_HAN))
        self.assertEqual(sorted(c.status for c in self.cac_cho(ma)), ['OPEN', 'SCHEDULED'])

    def test_uc6_3_basic_dang_ky_qua_man_hinh_va_hien_tren_lich(self):
        ngay = date.today() + timedelta(days=9)
        ma = services.tao_khung_ca(self.ql.user, 'Lễ tân', ngay, time(9), time(12), 1, datetime.now() + timedelta(days=5))
        self.dang_nhap(self.pt1)
        r = self.client.get(reverse('schedule:shift_register'), {'ngay': ngay})
        self.assertContains(r, 'Đã đăng ký 0/1')
        r = self.client.post(reverse('schedule:shift_join', args=[ma]), follow=True)
        self.assertContains(r, thong_bao.DANG_KY_CA_THANH_CONG)
        self.assertContains(r, 'Hủy đăng ký')
        self.assertContains(r, 'Đã đăng ký 1/1')
        lich = services.lich_lam_viec(self.pt1.user, ngay, ngay)
        self.assertTrue(any(m['loai'] == 'ca' for m in lich))            # có ca ngay trên lịch, không chờ chốt

    def test_uc6_3_ai_dang_ky_truoc_duoc_truoc_va_hai_nguoi_cung_bam_cho_cuoi(self):
        ma = self.mo_khung(1)
        cho = self.cac_cho(ma)[0]
        # Hai người cùng thấy chỗ trống rồi cùng bấm: câu UPDATE có điều kiện chỉ cho MỘT người nhận được
        self.assertTrue(services._nhan_cho_trong(cho.pk, self.pt1, self.TRUOC_HAN))
        self.assertFalse(services._nhan_cho_trong(cho.pk, self.pt2, self.TRUOC_HAN))
        cho.refresh_from_db()
        self.assertEqual(cho.employee, self.pt1)
        with self.assertRaisesMessage(LoiNghiepVu, 'Ca này đã đủ người.'):
            services.dang_ky_ca(self.pt2, ma, self.TRUOC_HAN)

    def test_uc6_3_exc_dang_ky_sau_han_chot(self):
        ma = self.mo_khung(1)
        with self.assertRaisesMessage(LoiNghiepVu, 'Đã hết thời hạn đăng ký ca làm việc này.'):
            services.dang_ky_ca(self.pt1, ma, self.SAU_HAN)
        services.dang_ky_ca(self.pt1, ma, self.HAN)            # đúng hạn chót vẫn được
        self.assertEqual(self.cac_cho(ma)[0].employee, self.pt1)

    def test_uc6_3_exc_da_dang_ky_khung_nay(self):
        ma = self.mo_khung(2)
        services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_DANG_KY_CA_NAY):
            services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        self.assertEqual(ShiftAssignment.objects.filter(employee=self.pt1).count(), 1)

    def test_uc6_3_exc_trung_gio_voi_ca_hoac_buoi_day_khac(self):
        ma1 = self.mo_khung(2, 'Lễ tân', time(9), time(12))
        ma2 = self.mo_khung(2, 'Tư vấn', time(11), time(14))
        services.dang_ky_ca(self.pt1, ma1, self.TRUOC_HAN)
        with self.assertRaisesMessage(LoiNghiepVu, 'Bạn đã có lịch làm việc trùng giờ với ca này.'):
            services.dang_ky_ca(self.pt1, ma2, self.TRUOC_HAN)
        self.tao_lop_san(gv=self.gv_ca1, tro_giang=self.tg, start_time=time(9), end_time=time(11), room_name='P1')
        with self.assertRaisesMessage(LoiNghiepVu, 'Bạn đã có lịch làm việc trùng giờ với ca này.'):
            services.dang_ky_ca(self.tg, ma1, self.TRUOC_HAN)

    def test_chi_part_time_dang_lam_viec_moi_dang_ky(self):
        ma = self.mo_khung(1)
        for nv in (self.gv_ca2, self.ql):
            with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_PART_TIME_DANG_KY):
                services.dang_ky_ca(nv, ma, self.TRUOC_HAN)
        self.pt1.status = EmployeeStatus.RESIGNED
        self.pt1.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_PART_TIME_DANG_KY):
            services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.KHONG_TIM_THAY_KHUNG_CA):
            services.dang_ky_ca(self.pt2, 'khong-co', self.TRUOC_HAN)

    # ----- Hủy đăng ký
    def test_uc6_3_huy_dang_ky_truoc_han_thi_cho_ve_trong(self):
        ma = self.mo_khung(1)
        services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        cho = services.huy_dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        self.assertEqual((cho.employee, cho.status, cho.registered_at), (None, ShiftStatus.OPEN, None))
        services.dang_ky_ca(self.pt2, ma, self.TRUOC_HAN)       # người khác nhận được chỗ vừa trả

    def test_huy_dang_ky_sau_han_hoac_chua_dang_ky_bi_chan(self):
        ma = self.mo_khung(1)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHUA_DANG_KY_CA_NAY):
            services.huy_dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        with self.assertRaisesMessage(LoiNghiepVu, 'Đã hết thời hạn đăng ký ca làm việc này.'):
            services.huy_dang_ky_ca(self.pt1, ma, self.SAU_HAN)

    # ----- Quản lý gán / gỡ người
    def test_uc6_3_quan_ly_go_nguoi_va_gan_nguoi_co_thong_bao(self):
        ma = self.mo_khung(1)
        services.dang_ky_ca(self.pt1, ma, self.TRUOC_HAN)
        cho = self.cac_cho(ma)[0]
        services.go_nguoi_khoi_cho(self.ql.user, cho)
        cho.refresh_from_db()
        self.assertEqual((cho.employee, cho.status), (None, ShiftStatus.OPEN))
        self.assertTrue(Notification.objects.filter(recipient=self.pt1.user, title=thong_bao.TB_KET_QUA_CA_TIEU_DE).exists())
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHO_CHUA_CO_NGUOI):
            services.go_nguoi_khoi_cho(self.ql.user, cho)
        services.gan_nhan_vien_vao_cho(self.ql.user, cho, self.pt2)
        cho.refresh_from_db()
        self.assertEqual((cho.employee, cho.status, cho.assigned_by), (self.pt2, ShiftStatus.SCHEDULED, self.ql.user))
        self.assertTrue(Notification.objects.filter(recipient=self.pt2.user, title=thong_bao.TB_KET_QUA_CA_TIEU_DE).exists())
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHO_KHONG_CON_TRONG):
            services.gan_nhan_vien_vao_cho(self.ql.user, cho, self.pt3)

    def test_gan_nhan_vien_khong_hop_le_bi_chan(self):
        ma = self.mo_khung(2)
        cho1, cho2 = self.cac_cho(ma)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.NHAN_VIEN_CA_KHONG_HOP_LE):
            services.gan_nhan_vien_vao_cho(self.ql.user, cho1, self.gv_ca2)          # Full-time
        services.gan_nhan_vien_vao_cho(self.ql.user, cho1, self.pt1)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_DANG_KY_CA_NAY):
            services.gan_nhan_vien_vao_cho(self.ql.user, cho2, self.pt1)             # đã có chỗ trong khung này
        self.assertNotIn(self.pt1, services.goi_y_nhan_vien_part_time(cho2))

    def test_uc6_3_tong_hop_va_dieu_chinh_qua_view(self):
        ngay = date.today() + timedelta(days=9)
        ma = services.tao_khung_ca(self.ql.user, 'Lễ tân', ngay, time(9), time(12), 2, datetime.now() + timedelta(days=5))
        services.dang_ky_ca(self.pt1, ma)
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:shift_review'), {'ngay': ngay})
        self.assertContains(r, 'Bảng tổng hợp đăng ký ca')
        self.assertNotContains(r, 'Chốt')
        self.assertEqual((r.context['so_vi_tri'], r.context['luot_dang_ky'], r.context['so_ca_thieu']), (2, 1, 1))
        self.assertEqual({nv.pk for nv in r.context['chua_dang_ky']}, {self.pt2.pk, self.pt3.pk, self.tg.pk})
        self.assertContains(self.client.get(reverse('schedule:shift_group', args=[ma])), 'Gỡ người')
        cho_trong = ShiftAssignment.objects.get(slot_group=ma, employee__isnull=True)
        r = self.client.post(reverse('schedule:shift_seat_assign', args=[cho_trong.pk]), {'nhan_su': self.pt2.pk}, follow=True)
        self.assertContains(r, 'Đã gán nhân viên vào chỗ trống.')
        r = self.client.post(reverse('schedule:shift_seat_remove', args=[cho_trong.pk]), follow=True)
        self.assertContains(r, 'Đã gỡ nhân viên khỏi chỗ này.')

    def test_gan_nguoi_qua_view_bao_loi_khi_chon_sai(self):
        ma = self.mo_khung(1)
        cho = self.cac_cho(ma)[0]
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:shift_seat_assign', args=[cho.pk]), {'nhan_su': self.gv_ca2.pk}, follow=True)
        self.assertContains(r, thong_bao.NHAN_VIEN_CA_KHONG_HOP_LE)
        r = self.client.post(reverse('schedule:shift_seat_assign', args=[cho.pk]), {}, follow=True)
        self.assertContains(r, 'Vui lòng chọn nhân viên.')

    def test_phan_quyen_ca_lam_viec(self):
        ma = self.mo_khung(1)
        cho = self.cac_cho(ma)[0]
        quan_ly_only = [('get', reverse('schedule:shift_create')), ('get', reverse('schedule:shift_review')),
                        ('get', reverse('schedule:shift_group', args=[ma])),
                        ('post', reverse('schedule:shift_seat_assign', args=[cho.pk])),
                        ('post', reverse('schedule:shift_seat_remove', args=[cho.pk]))]
        for nv in (self.pt1, self.gv_ca2):
            self.dang_nhap(nv)
            for cach, url in quan_ly_only:
                self.assertEqual(getattr(self.client, cach)(url).status_code, 403, url)
        self.dang_nhap(self.ql)
        for cach, url in quan_ly_only[:3]:
            self.assertEqual(getattr(self.client, cach)(url).status_code, 200, url)
        for nv in (self.ql, self.gv_ca2):
            self.dang_nhap(nv)
            self.assertContains(self.client.get(reverse('schedule:shift_register')), thong_bao.CHI_PART_TIME_DANG_KY, status_code=403)
            self.assertEqual(self.client.post(reverse('schedule:shift_join', args=[ma])).status_code, 403)
        self.dang_nhap(self.pt1)
        self.assertEqual(self.client.get(reverse('schedule:shift_register')).status_code, 200)
        self.assertEqual(self.client.get(reverse('schedule:shift_join', args=[ma])).status_code, 405)   # chỉ nhận POST


# =====================================================================================================
# P7 – UC 6.4 Xử lý dạy thay
# =====================================================================================================
class Uc64Test(NenTang):
    """Lớp Thứ 2-4-6 18:00–20:00 (5–16/10/2026, Phòng 201) do gv_ca2 dạy, tg trợ giảng; gv_ca2 vắng buổi Thứ 4 7/10."""

    def setUp(self):
        super().setUp()
        self.lop, _ = self.tao_lop_san(gv=self.gv_ca2, tro_giang=self.tg)
        self.buoi = self.lop.teaching_sessions.get(session_date=date(2026, 10, 7))
        self.yc = services.tao_yeu_cau_day_thay(self.buoi)
        self.gv_thay = gv_ft('gvthay@icls.vn', WorkShift.SHIFT_2)

    # ----- bước 1–4
    def test_uc6_4_basic_danh_sach_yeu_cau_dang_tim(self):
        yc_thanh_ly = SubstituteRequest.objects.create(
            teaching_session=self.lop.teaching_sessions.get(session_date=date(2026, 10, 9)))
        daxong = SubstituteRequest.objects.create(
            teaching_session=self.lop.teaching_sessions.get(session_date=date(2026, 10, 12)), status='COMPLETED')
        self.assertEqual(list(services.yeu_cau_day_thay_dang_tim()), [self.yc, yc_thanh_ly])    # SEARCHING, theo ngày
        self.assertNotIn(daxong, services.yeu_cau_day_thay_dang_tim())
        self.assertEqual(services.giao_vien_vang(self.yc), self.gv_ca2)
        self.assertEqual(services.nguon_yeu_cau(yc_thanh_ly), 'Thanh lý hợp đồng')
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:substitute_list'))
        self.assertContains(r, 'Buổi dạy cần người thay')
        self.assertContains(r, 'TOPIK 2')
        self.assertContains(r, 'Thanh lý hợp đồng')
        self.assertContains(r, 'gv2@icls.vn')

    def test_uc6_4_goi_y_giao_vien_day_thay(self):
        gv_ca1 = self.gv_ca1                                            # Ca 1 (08–17h) không bao trọn 18–20h
        gv_ban = gv_ft('gvban@icls.vn', WorkShift.SHIFT_2)              # có buổi dạy trùng giờ cùng ngày
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp bận', room_name='P9', start_date=date(2026, 10, 7),
                                                                 end_date=date(2026, 10, 7), weekdays='2'), gv_ban)
        gv_nghi = gv_ft('gvnghi@icls.vn', WorkShift.SHIFT_2)            # nghỉ phép đã duyệt hôm đó
        LeaveRequest.objects.create(employee=gv_nghi, leave_type='SICK', start_date=date(2026, 10, 7),
                                    end_date=date(2026, 10, 7), total_days=1, reason='x', status='APPROVED')
        gv_pt = nv_hoat_dong('gvpt@icls.vn', chuc_danh=Position.TEACHER, loai_hinh=EmploymentType.PART_TIME)   # Part-time: không giới hạn ca
        goi_y = {nv.full_name for nv in services.goi_y_giao_vien_day_thay(self.yc)}
        self.assertEqual(goi_y, {'gvthay@icls.vn', 'gvpt@icls.vn'})
        self.assertNotIn(gv_ca1.full_name, goi_y)
        self.assertNotIn('gv2@icls.vn', goi_y)                          # khác giáo viên vắng

    # ----- bước 5–7
    def test_uc6_4_basic_chot_day_thay(self):
        Notification.objects.all().delete()
        services.chot_day_thay(self.ql.user, self.yc, self.gv_thay)
        self.yc.refresh_from_db()
        self.buoi.refresh_from_db()
        self.assertEqual((self.yc.status, self.yc.substitute_employee, self.yc.manager_confirmed_by),
                         ('COMPLETED', self.gv_thay, self.ql.user))
        self.assertEqual((self.buoi.actual_teacher, self.buoi.planned_teacher), (self.gv_thay, self.gv_ca2))
        self.assertEqual(self.buoi.status, 'SCHEDULED')
        self.assertEqual(set(Notification.objects.filter(title=thong_bao.TB_DAY_THAY_TIEU_DE).values_list('recipient_id', flat=True)),
                         {self.gv_thay.user_id, self.gv_ca2.user_id})        # báo cả người thay và người vắng
        self.assertTrue(ActivityLog.objects.filter(model_name='substitute_requests', object_id=self.yc.pk).exists())
        # chấm công và lịch dùng người thực tế: giáo viên thay bận khung giờ này, giáo viên vắng thì rảnh
        self.assertTrue(services.kiem_tra_trung_lich(self.gv_thay, date(2026, 10, 7), time(18), time(20)))

    def test_uc6_4_basic_chot_qua_man_hinh(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:substitute_detail', args=[self.yc.pk]))
        self.assertContains(r, 'gvthay@icls.vn')
        self.assertContains(r, 'Chốt dạy thay')
        r = self.client.post(reverse('schedule:substitute_detail', args=[self.yc.pk]),
                             {'hanh_dong': 'chot', 'giao_vien': self.gv_thay.pk}, follow=True)
        self.assertContains(r, 'Đã chốt giáo viên dạy thay.')
        self.buoi.refresh_from_db()
        self.assertEqual(self.buoi.actual_teacher, self.gv_thay)

    def test_uc6_4_exc_5_3_giao_vien_vua_bi_trung_lich_tro_lai_buoc_4(self):
        # Giáo viên thay được gợi ý, nhưng trước khi bấm "Chốt" lớp khác đã chiếm lịch của họ
        self.assertIn(self.gv_thay, services.goi_y_giao_vien_day_thay(self.yc))
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp chen ngang', room_name='P9', start_date=date(2026, 10, 7),
                                                                 end_date=date(2026, 10, 7), weekdays='2'), self.gv_thay)
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.chot_day_thay(self.ql.user, self.yc, self.gv_thay)
        self.assertEqual(str(ctx.exception), 'Giáo viên bị trùng lịch, vui lòng chọn lại.')
        self.yc.refresh_from_db()
        self.buoi.refresh_from_db()
        self.assertEqual((self.yc.status, self.buoi.actual_teacher), ('SEARCHING', self.gv_ca2))   # không đổi gì
        self.dang_nhap(self.ql)                                                                        # trên màn hình: hiện lại danh sách kèm lỗi
        r = self.client.post(reverse('schedule:substitute_detail', args=[self.yc.pk]), {'hanh_dong': 'chot', 'giao_vien': self.gv_thay.pk})
        self.assertContains(r, 'Giáo viên bị trùng lịch, vui lòng chọn lại.')
        self.assertContains(r, 'Giáo viên gợi ý')

    def test_chot_giao_vien_khong_hop_le_hoac_chua_chon(self):
        for gv in (self.gv_ca2, self.gv_ca1, self.tg):          # chính giáo viên vắng; Ca 1 không bao trọn giờ; trợ giảng không phải GV
            with self.assertRaises(services.LoiTruongNhap) as ctx:
                services.chot_day_thay(self.ql.user, self.yc, gv)
            self.assertEqual(str(ctx.exception), thong_bao.GIAO_VIEN_KHONG_HOP_LE)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:substitute_detail', args=[self.yc.pk]), {'hanh_dong': 'chot'})
        self.assertContains(r, 'Vui lòng chọn giáo viên dạy thay.')

    def test_yeu_cau_da_xu_ly_khong_chot_lai(self):
        services.chot_day_thay(self.ql.user, self.yc, self.gv_thay)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.YEU_CAU_DAY_THAY_DA_XU_LY):
            services.chot_day_thay(self.ql.user, self.yc, self.gv_thay)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.YEU_CAU_DAY_THAY_DA_XU_LY):
            services.huy_buoi_hoc(self.ql.user, self.yc)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:substitute_detail', args=[self.yc.pk]),
                             {'hanh_dong': 'chot', 'giao_vien': self.gv_thay.pk}, follow=True)
        self.assertContains(r, 'Yêu cầu dạy thay đã được xử lý.')

    # ----- luồng thay thế 5.1, 5.2, 1.1
    def test_uc6_4_alt_5_1_huy_buoi_hoc(self):
        Notification.objects.all().delete()
        services.huy_buoi_hoc(self.ql.user, self.yc)
        self.yc.refresh_from_db()
        self.buoi.refresh_from_db()
        self.assertEqual((self.yc.status, self.buoi.status), ('FAILED', 'CANCELLED'))
        self.assertEqual(set(Notification.objects.filter(title=thong_bao.TB_HUY_BUOI_TIEU_DE).values_list('recipient_id', flat=True)),
                         {self.gv_ca2.user_id, self.tg.user_id})       # giáo viên phụ trách và trợ giảng
        self.assertFalse(services.kiem_tra_trung_lich(self.gv_ca2, date(2026, 10, 7), time(18), time(20)))   # buổi hủy không còn chiếm lịch

    def test_uc6_4_alt_5_1_huy_buoi_qua_man_hinh_ve_danh_sach(self):
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('schedule:substitute_detail', args=[self.yc.pk]), {'hanh_dong': 'huy_buoi'}, follow=True)
        self.assertContains(r, 'Đã hủy buổi học.')
        self.assertRedirects(r, reverse('schedule:substitute_list'))
        r = self.client.get(reverse('schedule:session_detail', args=[self.buoi.pk]))
        self.assertNotContains(r, 'Thêm buổi học bù')       # bản đơn giản: không còn học bù, không còn đổi trợ giảng
        self.assertNotContains(r, 'Đổi trợ giảng')

    def test_phan_quyen_xu_ly_day_thay_chi_quan_ly(self):
        urls = [('get', reverse('schedule:substitute_list')), ('get', reverse('schedule:substitute_detail', args=[self.yc.pk])),
                ('post', reverse('schedule:substitute_detail', args=[self.yc.pk]))]
        for nv in (self.gv_ca2, self.pt1, self.tg):
            self.dang_nhap(nv)
            for cach, url in urls:
                self.assertEqual(getattr(self.client, cach)(url).status_code, 403, url)
        self.dang_nhap(self.ql)
        for cach, url in urls[:2]:
            self.assertEqual(getattr(self.client, cach)(url).status_code, 200, url)

    def test_thanh_ly_hop_dong_thong_bao_dan_den_danh_sach_day_thay(self):
        """UC 3.4 → UC 6.4: yêu cầu phát sinh từ thanh lý hiện trong danh sách, thông báo có đường dẫn."""
        from contracts.services import thanh_ly_hop_dong   # noqa: F401  (chỉ kiểm tra import được, luồng đầy đủ đã test ở contracts)
        yc = SubstituteRequest.objects.create(teaching_session=self.lop.teaching_sessions.get(session_date=date(2026, 10, 9)))
        self.assertIn(yc, services.yeu_cau_day_thay_dang_tim())
        self.assertEqual(services.nguon_yeu_cau(yc), 'Thanh lý hợp đồng')


# =====================================================================================================
# Sắp xếp lại hai tab lịch: ca cố định Full-time, bảng theo nhân sự (lịch làm việc), bảng theo phòng (lịch lớp học)
# =====================================================================================================
class LichBangTest(NenTang):
    """Tuần 05/10 – 11/10/2026. Full-time: ql (không ca), gv_ca1 (Ca 1), gv_ca2 (Ca 2). Part-time: pt1, pt2, pt3, tg."""
    TUAN = date(2026, 10, 5)
    CUOI_TUAN = date(2026, 10, 11)

    def ft(self, nhan_vien=None):
        return [m for m in services.lich_ca_full_time(self.TUAN, self.CUOI_TUAN, nhan_vien)]

    def test_ca_co_dinh_full_time_thu_2_den_thu_7_theo_ca_trong_ho_so(self):
        cac_muc = self.ft(self.gv_ca1)
        self.assertEqual([m['ngay'].weekday() for m in cac_muc], [0, 1, 2, 3, 4, 5])        # không có Chủ nhật
        self.assertEqual({(m['tieu_de'], m['bd'], m['kt'], m['loai']) for m in cac_muc}, {('Ca 1', time(8), time(17), 'ca_ft')})
        self.assertEqual({(m['tieu_de'], m['bd'], m['kt']) for m in self.ft(self.gv_ca2)}, {('Ca 2', time(13), time(21))})
        self.assertEqual({m['nhom'] for m in cac_muc}, {'Full-time'})

    def test_ca_co_dinh_chi_cho_full_time_dang_lam_viec_co_ca(self):
        ten = {m['ten'] for m in self.ft()}
        self.assertEqual(ten, {'gv1@icls.vn', 'gv2@icls.vn'})            # ql không có ca trong hồ sơ; Part-time không có ca cố định
        self.gv_ca1.status = EmployeeStatus.RESIGNED
        self.gv_ca1.save()
        self.assertEqual({m['ten'] for m in self.ft()}, {'gv2@icls.vn'})

    def test_ca_co_dinh_ngay_nghi_phep_hien_la_nghi_phep(self):
        LeaveRequest.objects.create(employee=self.gv_ca1, leave_type='ANNUAL', start_date=date(2026, 10, 6),
                                    end_date=date(2026, 10, 7), total_days=2, reason='x', status='APPROVED')
        LeaveRequest.objects.create(employee=self.gv_ca1, leave_type='SICK', start_date=date(2026, 10, 9),
                                    end_date=date(2026, 10, 9), total_days=1, reason='x', status='PENDING')       # chưa duyệt: vẫn làm
        theo_ngay = {m['ngay'].day: m for m in self.ft(self.gv_ca1)}
        self.assertEqual((theo_ngay[6]['loai'], theo_ngay[7]['loai']), ('nghi', 'nghi'))
        self.assertEqual(theo_ngay[8]['loai'], 'ca_ft')
        self.assertEqual(theo_ngay[9]['loai'], 'ca_ft')

    def test_quan_ly_thay_ca_toan_trung_tam_gom_full_time_va_part_time(self):
        ShiftAssignment.objects.create(slot_group='g', employee=self.pt1, shift_role='Lễ tân', work_date=date(2026, 10, 6), planned_start=time(8),
                                       planned_end=time(12), registration_deadline=datetime(2026, 10, 1), status='SCHEDULED')
        for nguoi in (self.ql, User.objects.create_user('gd@icls.vn', 'x', role=UserRole.DIRECTOR, full_name='Giám đốc')):
            cac_muc = services.lich_lam_viec(getattr(nguoi, 'user', nguoi), self.TUAN, self.CUOI_TUAN)
            self.assertEqual({m['nhom'] for m in cac_muc}, {'Full-time', 'Part-time'})
            self.assertEqual({m['loai'] for m in cac_muc}, {'ca_ft', 'ca'})
        loc = services.lich_lam_viec(self.ql.user, self.TUAN, self.CUOI_TUAN, nhan_su_loc=self.gv_ca1)
        self.assertEqual({m['ten'] for m in loc}, {'gv1@icls.vn'})

    def test_nhan_vien_full_time_thay_ca_co_dinh_cua_minh_lam_nen(self):
        cac_muc = services.lich_lam_viec(self.gv_ca2.user, self.TUAN, self.CUOI_TUAN)
        self.assertEqual({m['ten'] for m in cac_muc}, {'gv2@icls.vn'})
        self.assertTrue(all(m.get('nen') for m in cac_muc))
        bang = services.dung_bang_nhan_su(cac_muc, self.TUAN, self.TUAN)
        self.assertEqual(len(bang['hang']), 1)                                      # lịch cá nhân: một hàng là chính mình
        self.assertEqual([len(o) for o in bang['hang'][0]['cac_o']], [1, 1, 1, 1, 1, 1, 0])   # ca cố định Thứ 2–Thứ 7

    def test_bang_nhan_su_part_time_truoc_full_time_sau_va_dem_so_nguoi_moi_ngay(self):
        ShiftAssignment.objects.create(slot_group='g', employee=self.pt1, shift_role='Lễ tân', work_date=date(2026, 10, 10), planned_start=time(8),
                                       planned_end=time(12), registration_deadline=datetime(2026, 10, 1), status='SCHEDULED')
        LeaveRequest.objects.create(employee=self.gv_ca1, leave_type='ANNUAL', start_date=date(2026, 10, 6),
                                    end_date=date(2026, 10, 6), total_days=1, reason='x', status='APPROVED')
        cac_muc = services.lich_lam_viec(self.ql.user, self.TUAN, self.CUOI_TUAN)
        bang = services.dung_bang_nhan_su(cac_muc, self.TUAN, self.TUAN)
        self.assertEqual([(h['nhom'], h['ten']) for h in bang['hang']],                 # nhóm hay thay đổi lên trước
                         [('Part-time', 'pt1@icls.vn'), ('Full-time', 'gv1@icls.vn'), ('Full-time', 'gv2@icls.vn')])
        gv1 = bang['hang'][1]
        self.assertEqual([len(o) for o in gv1['cac_o']], [1, 1, 1, 1, 1, 1, 0])
        self.assertEqual(gv1['cac_o'][1][0]['loai'], 'nghi')                        # Thứ 3 nghỉ phép
        self.assertEqual((gv1['ca'], gv1['co_nghi'], bang['hang'][2]['co_nghi']), ('Ca 1', True, False))
        self.assertEqual(bang['tong_ngay'], [2, 1, 2, 2, 2, 3, 0])                  # số người làm: Thứ 3 chỉ còn gv2 (gv1 nghỉ); Thứ 7 có thêm pt1
        self.assertEqual([c['so_nguoi'] for c in bang['cot']], bang['tong_ngay'])
        self.assertEqual(bang['chi_so_hom_nay'], 0)
        self.assertTrue(bang['cot'][6]['cuoi_tuan'])
        self.assertEqual([h['ten'] for h in services.dung_bang_nhan_su(cac_muc, self.TUAN, self.TUAN, 'nghi')['hang']], ['gv1@icls.vn'])
        self.assertEqual([h['ten'] for h in services.dung_bang_nhan_su(cac_muc, self.TUAN, self.TUAN, 'part_time')['hang']], ['pt1@icls.vn'])

    def test_quan_ly_thay_buoi_tro_giang_cho_trong_va_so_tom_tat(self):
        self.tao_lop_san(gv=self.gv_ca1, tro_giang=self.tg, start_time=time(9), end_time=time(11), room_name='P1')
        ma = services.tao_khung_ca(self.ql.user, 'Tư vấn', date(2026, 10, 8), time(13), time(17), 2, datetime(2026, 10, 7, 18))
        services.dang_ky_ca(self.pt1, ma, datetime(2026, 10, 1, 8))
        cac_muc = services.lich_lam_viec(self.ql.user, self.TUAN, self.CUOI_TUAN)
        tro_giang = [m for m in cac_muc if m['loai'] == 'tro_giang']
        self.assertTrue(tro_giang)
        self.assertEqual({(m['ten'], m['nhom']) for m in tro_giang}, {('tg@icls.vn', 'Trợ giảng')})
        bang = services.dung_bang_nhan_su(cac_muc, self.TUAN, self.TUAN)
        self.assertEqual([n['ten'] for n in bang['nhom']], ['Part-time', 'Trợ giảng', 'Full-time'])
        cho_trong = services.cho_ca_con_trong(self.TUAN)
        self.assertEqual([len(o) for o in cho_trong], [0, 0, 0, 1, 0, 0, 0])        # Thứ 5: 1 chỗ Tư vấn còn trống
        tom_tat = services.tom_tat_tuan(cac_muc, self.TUAN, self.TUAN)
        self.assertEqual(tom_tat['cho_trong'], 1)
        self.assertIsNone(services.tom_tat_tuan(cac_muc, self.TUAN, date(2026, 11, 1))['dang_lam_hom_nay'])   # tuần khác
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN})
        self.assertContains(r, 'Chỗ ca còn trống')
        self.assertContains(r, 'Có nghỉ phép')
        self.assertContains(r, 'rs-tg')
        r = self.client.get(reverse('schedule:calendar'), {'ngay': self.TUAN, 'nhom': 'tro_giang'})
        self.assertEqual({h['nhom'] for h in r.context['bang']['hang']}, {'Trợ giảng'})

    def test_bang_phong_nhom_theo_phong_va_xep_theo_gio(self):
        gv_khac = gv_ft('gvb@icls.vn', WorkShift.SHIFT_1)
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng B', class_name='Lớp tối')
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp sáng', room_name='Phòng B', start_time=time(9), end_time=time(11)), gv_khac)
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp A', room_name='Phòng A', start_time=time(9), end_time=time(11)), self.gv_ca1)
        services.tao_lop_va_phan_cong(self.ql.user, du_lieu_lop(class_name='Lớp không phòng', room_name='', start_time=time(14), end_time=time(16)), nv_hoat_dong(
            'gvc@icls.vn', chuc_danh=Position.TEACHER, loai_hinh=EmploymentType.FULL_TIME, ca=WorkShift.SHIFT_1))
        cac_muc = services.lich_lop_hoc(self.TUAN, self.CUOI_TUAN)
        bang = services.dung_bang_phong(cac_muc, self.TUAN, self.TUAN)
        self.assertEqual([h['ten'] for h in bang['hang']], ['Phòng A', 'Phòng B', 'Chưa có phòng'])     # phòng chưa rõ nằm cuối
        phong_b = bang['hang'][1]
        self.assertEqual([m['ten_lop'] for m in phong_b['cac_o'][0]], ['Lớp sáng', 'Lớp tối'])           # Thứ 2: 09:00 trước 18:00
        self.assertEqual([len(o) for o in phong_b['cac_o']], [2, 0, 2, 0, 2, 0, 0])                      # Thứ 2-4-6
        self.assertEqual([c['so_buoi'] for c in bang['cot']], [4, 0, 4, 0, 4, 0, 0])

    def test_man_hinh_hai_kieu_bang_theo_tab_va_vai_tro(self):
        self.tao_lop_san(gv=self.gv_ca2, room_name='Phòng 201')
        tham_so = {'ngay': '2026-10-05'}
        self.dang_nhap(self.ql)                                                    # Quản lý: lịch làm việc = bảng theo nhân sự
        r = self.client.get(reverse('schedule:calendar'), tham_so)
        self.assertEqual(r.context['kieu'], 'bang_nhan_su')
        self.assertContains(r, 'rs-table')
        self.assertContains(r, 'gv1@icls.vn')
        self.assertContains(r, 'Ca 1')
        self.assertContains(r, 'Ca 2')
        self.assertContains(r, 'người làm')
        self.assertNotContains(r, 'Không có lịch trình trong thời gian này.')
        r = self.client.get(reverse('schedule:calendar'), {**tham_so, 'tab': 'lop_hoc'})   # lịch lớp học = bảng theo phòng
        self.assertEqual(r.context['kieu'], 'bang_phong')
        self.assertContains(r, 'Phòng 201')
        self.assertContains(r, 'phòng có lịch trong tuần')
        self.dang_nhap(self.gv_ca2)                                                # nhân viên: cũng là bảng tuần, một hàng là chính mình
        r = self.client.get(reverse('schedule:calendar'), tham_so)
        self.assertEqual(r.context['kieu'], 'bang_nhan_su')
        self.assertEqual(len(r.context['bang']['hang']), 1)
        self.assertContains(r, 'rs-ft')                                            # ca cố định ghi rõ "Ca 2 13–21"
        self.assertNotContains(r, 'người làm')                                     # không có số đếm của Quản lý
        self.assertNotContains(r, 'gv1@icls.vn')                                   # không thấy người khác
        self.assertContains(self.client.get(reverse('schedule:calendar'), {**tham_so, 'tab': 'lop_hoc'}), 'rs-table')   # lịch lớp: ai cũng là bảng theo phòng

    def test_tuan_co_ca_co_dinh_thi_khong_bao_trong_lich(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': '2026-10-06'})
        self.assertNotContains(r, 'Không có lịch trình trong thời gian này.')

    def test_loc_theo_nhan_su_chi_con_hang_cua_nguoi_do(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('schedule:calendar'), {'ngay': '2026-10-05', 'nv': self.gv_ca1.pk})
        self.assertEqual([h['ten'] for h in r.context['bang']['hang']], ['gv1@icls.vn'])


# ============================================================ UC 9.2 – bước 5: cập nhật lịch học hằng ngày (P10)
class CapNhatLichHangNgayTest(TestCase):
    """`cap_nhat_lich_hang_ngay(hom_nay)`. Hôm nay giả định 27/10/2026."""
    HOM_NAY = date(2026, 10, 27)

    def setUp(self):
        from core.mau_test import tao_nhan_su_hoat_dong
        self.gv = tao_nhan_su_hoat_dong('gv@icls.vn', chuc_danh='TEACHER', loai_hinh='FULL_TIME', ca='SHIFT_1')

    def lop(self, ten, bat_dau, ket_thuc, trang_thai):
        from core.mau_test import tao_lop
        lop = tao_lop(ten)
        lop.start_date, lop.end_date, lop.status = bat_dau, ket_thuc, trang_thai
        lop.save()
        return lop

    def buoi(self, lop, ngay, trang_thai='SCHEDULED'):
        return TeachingSession.objects.create(study_class=lop, session_date=ngay, planned_start=time(9), planned_end=time(11),
                                              planned_teacher=self.gv, actual_teacher=self.gv, status=trang_thai)

    def test_buoi_da_qua_thanh_completed_buoi_hom_nay_va_tuong_lai_giu_nguyen(self):
        from schedule import services as dv
        lop = self.lop('A', date(2026, 10, 1), date(2026, 12, 31), 'ACTIVE')
        da_qua, hom_nay, tuong_lai = (self.buoi(lop, date(2026, 10, 26)), self.buoi(lop, self.HOM_NAY),
                                      self.buoi(lop, date(2026, 10, 28)))
        da_huy = self.buoi(lop, date(2026, 10, 20), 'CANCELLED')
        kq = dv.cap_nhat_lich_hang_ngay(self.HOM_NAY)
        self.assertEqual(kq['buoi_hoan_thanh'], 1)
        for b in (da_qua, hom_nay, tuong_lai, da_huy):
            b.refresh_from_db()
        self.assertEqual([b.status for b in (da_qua, hom_nay, tuong_lai, da_huy)],
                         ['COMPLETED', 'SCHEDULED', 'SCHEDULED', 'CANCELLED'])

    def test_yeu_cau_day_thay_qua_han_failed_buoi_cancelled_va_bao_giao_vien(self):
        from core.models import Notification
        from schedule import services as dv
        lop = self.lop('A', date(2026, 10, 1), date(2026, 12, 31), 'ACTIVE')
        buoi = self.buoi(lop, date(2026, 10, 26))
        con_han = self.buoi(lop, date(2026, 10, 29))
        yc = SubstituteRequest.objects.create(teaching_session=buoi)
        yc_con_han = SubstituteRequest.objects.create(teaching_session=con_han)
        kq = dv.cap_nhat_lich_hang_ngay(self.HOM_NAY)
        self.assertEqual((kq['that_bai'], kq['buoi_hoan_thanh']), (1, 0))
        for doi_tuong in (yc, buoi, yc_con_han, con_han):
            doi_tuong.refresh_from_db()
        self.assertEqual((yc.status, buoi.status), ('FAILED', 'CANCELLED'))        # không bị tính nhầm là COMPLETED
        self.assertEqual((yc_con_han.status, con_han.status), ('SEARCHING', 'SCHEDULED'))   # buổi tương lai: còn thời gian tìm
        self.assertTrue(Notification.objects.filter(recipient=self.gv.user, title='Buổi dạy bị hủy').exists())

    def test_trang_thai_lop_upcoming_active_completed(self):
        from schedule import services as dv
        sap = self.lop('Sắp', date(2026, 10, 27), date(2026, 12, 31), 'UPCOMING')       # đến ngày bắt đầu
        chua_den = self.lop('Chưa', date(2026, 10, 28), date(2026, 12, 31), 'UPCOMING')
        xong = self.lop('Xong', date(2026, 8, 1), date(2026, 10, 26), 'ACTIVE')          # quá ngày kết thúc
        chua_xong = self.lop('ChuaXong', date(2026, 8, 1), date(2026, 10, 27), 'ACTIVE') # kết thúc đúng hôm nay: còn học
        da_huy = self.lop('Huy', date(2026, 8, 1), date(2026, 9, 1), 'CANCELLED')
        kq = dv.cap_nhat_lich_hang_ngay(self.HOM_NAY)
        self.assertEqual((kq['lop_bat_dau'], kq['lop_ket_thuc']), (1, 1))
        for lop in (sap, chua_den, xong, chua_xong, da_huy):
            lop.refresh_from_db()
        self.assertEqual([x.status for x in (sap, chua_den, xong, chua_xong, da_huy)],
                         ['ACTIVE', 'UPCOMING', 'COMPLETED', 'ACTIVE', 'CANCELLED'])

    def test_chay_lai_khong_xu_ly_them(self):
        from schedule import services as dv
        lop = self.lop('A', date(2026, 10, 1), date(2026, 10, 20), 'UPCOMING')
        self.buoi(lop, date(2026, 10, 10))
        dv.cap_nhat_lich_hang_ngay(self.HOM_NAY)
        self.assertEqual(set(dv.cap_nhat_lich_hang_ngay(self.HOM_NAY).values()), {0})
