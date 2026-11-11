"""Test của app leave – P1: các ràng buộc CSDL (§7.3.13, §7.3.14)."""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.mau_test import tao_nhan_su
from leave.models import LeaveBalance, LeaveRequest


class RangBuocLeaveTest(TestCase):
    def test_don_nghi_ngay_ket_thuc_truoc_ngay_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.create(employee=tao_nhan_su(), leave_type='SICK', start_date=date(2026, 10, 5),
                                        end_date=date(2026, 10, 4), total_days=1, reason='ốm')

    def test_moi_nhan_su_mot_quy_phep_moi_nam(self):
        nv = tao_nhan_su()
        LeaveBalance.objects.create(employee=nv, year=2026)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveBalance.objects.create(employee=nv, year=2026)

    def test_da_dung_vuot_tong_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveBalance.objects.create(employee=tao_nhan_su(), year=2026, total_days=12, used_days=13)

    def test_remaining_days_la_thuoc_tinh_tinh_ra(self):
        qp = LeaveBalance.objects.create(employee=tao_nhan_su(), year=2026, total_days=12, used_days=Decimal('2.5'))
        self.assertEqual(qp.remaining_days, Decimal('9.5'))


# =====================================================================================================
# P7 – UC 5.1, 5.2, 5.3, 5.4 (và liên thông với UC 6.4). Tên test bám mã luồng ở §10 (ROADMAP §12.1).
# =====================================================================================================
from datetime import datetime, time, timedelta

from django.urls import reverse

from accounts.models import User, UserRole
from core import thong_bao
from core.models import ActivityLog, Notification
from core.mau_test import tao_nhan_su_hoat_dong as hoat_dong
from core.services import KhongCoQuyen, LoiNghiepVu
from employees.models import Department, EmploymentType, Position, WorkShift
from leave import services
from leave.models import LeaveStatus
from payroll.models import Payroll
from schedule import services as lich
from schedule.models import ShiftAssignment, SubstituteRequest, TeachingSession

FT, PT = EmploymentType.FULL_TIME, EmploymentType.PART_TIME
T2 = date(2026, 10, 12)       # Thứ 2
T3 = date(2026, 10, 13)       # Thứ 3
BAY_GIO = datetime(2026, 10, 9, 9, 0)


class NenTangNghi(TestCase):
    """Dữ liệu chung: Super Admin (không có hồ sơ), 2 Quản lý, Kế toán, giáo viên Full-time Ca 2, nhân viên Part-time."""

    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN, full_name='SA')
        self.ql = hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER, FT)
        self.ql2 = hoat_dong('ql2@icls.vn', UserRole.MANAGER, Position.MANAGER, FT)
        self.kt = hoat_dong('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, FT)
        self.gv = hoat_dong('gv@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_2)
        self.pt = hoat_dong('pt@icls.vn', UserRole.EMPLOYEE, Position.STAFF, PT)
        for nv in (self.ql, self.ql2, self.kt, self.gv):
            services.tao_quy_phep(nv, 2026)

    def dang_nhap(self, nguoi):
        self.client.force_login(nguoi.user if hasattr(nguoi, 'user') else nguoi)

    def gui(self, nv, loai='ANNUAL', hinh_thuc='FULL_DAY', tu=T2, den=T3, ly_do='Việc gia đình'):
        return services.gui_don_nghi(nv, loai, hinh_thuc, tu, den, ly_do)

    def quy(self, nv):
        return LeaveBalance.objects.get(employee=nv, year=2026)

    def tao_lop_gv(self, tro_giang=None):
        """Lớp Thứ 2-4-6, 18:00–20:00, 5–16/10/2026 do self.gv dạy (6 buổi)."""
        return lich.tao_lop_va_phan_cong(self.ql.user, dict(
            class_name='TOPIK 2', subject='Trung cấp', room_name='P201', max_students=20, start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 16), weekdays='0,2,4', start_time=time(18), end_time=time(20)), self.gv, tro_giang)[0]


class TinhToanNghiTest(NenTangNghi):
    def test_tinh_so_ngay_nghi(self):
        d = Decimal
        self.assertEqual(services.tinh_so_ngay_nghi(date(2026, 10, 5), date(2026, 10, 10)), d(6))     # Thứ 2 – Thứ 7
        self.assertEqual(services.tinh_so_ngay_nghi(date(2026, 10, 5), date(2026, 10, 11)), d(6))     # Chủ nhật không tính
        self.assertEqual(services.tinh_so_ngay_nghi(date(2026, 10, 5), date(2026, 10, 19)), d(13))      # 6 + 6 + Thứ 2 19/10
        self.assertEqual(services.tinh_so_ngay_nghi(date(2026, 10, 11), date(2026, 10, 11)), d(0))    # chỉ Chủ nhật
        self.assertEqual(services.tinh_so_ngay_nghi(T2, T2, 'HALF_DAY_AM'), d('0.5'))
        self.assertEqual(services.tinh_so_ngay_nghi(T2, T2, 'HALF_DAY_PM'), d('0.5'))
        self.assertEqual(services.tinh_so_ngay_nghi(date(2026, 10, 11), date(2026, 10, 11), 'HALF_DAY_AM'), d(0))
        self.assertEqual(services.tinh_so_ngay_nghi(T2, T3, 'HALF_DAY_AM'), d(0))                      # nửa ngày phải cùng ngày

    def test_dinh_dang_so_ngay(self):
        self.assertEqual(services.dinh_dang_so_ngay(Decimal('8.5')), '8,5')
        self.assertEqual(services.dinh_dang_so_ngay(Decimal('12.0')), '12')
        self.assertEqual(services.dinh_dang_so_ngay(Decimal('0.5')), '0,5')


class Uc51Test(NenTangNghi):
    def test_uc5_1_basic_gui_don_phep_nam(self):
        don = self.gui(self.gv)
        self.assertEqual((don.status, don.total_days, don.leave_type, don.duration_type), ('PENDING', Decimal('2'), 'ANNUAL', 'FULL_DAY'))
        self.assertEqual((don.start_date, don.end_date, don.reason), (T2, T3, 'Việc gia đình'))
        self.assertFalse(don.needs_substitute)
        self.assertEqual(self.quy(self.gv).used_days, 0)                    # gửi đơn chưa trừ phép, chỉ trừ khi duyệt
        nguoi_nhan = set(Notification.objects.filter(title=thong_bao.TB_DON_MOI_TIEU_DE).values_list('recipient_id', flat=True))
        self.assertEqual(nguoi_nhan, {self.ql.user_id, self.ql2.user_id})   # mọi Quản lý nhận, Kế toán/SA không nhận
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='leave_requests', object_id=don.pk).exists())

    def test_uc5_1_basic_don_cua_quan_ly_bao_super_admin(self):
        self.gui(self.ql)
        nguoi_nhan = set(Notification.objects.filter(title=thong_bao.TB_DON_MOI_TIEU_DE).values_list('recipient_id', flat=True))
        self.assertEqual(nguoi_nhan, {self.sa.pk})

    def test_uc5_1_basic_nua_ngay_la_0_5(self):
        don = self.gui(self.gv, 'SICK', 'HALF_DAY_AM', T2, T2)
        self.assertEqual(don.total_days, Decimal('0.5'))

    def test_uc5_1_basic_part_time_nghi_om_va_khong_luong(self):
        for loai in ('SICK', 'UNPAID', 'OTHER'):
            self.gui(self.pt, loai, 'FULL_DAY', date(2026, 11, 2) + timedelta(days=['SICK', 'UNPAID', 'OTHER'].index(loai)),
                     date(2026, 11, 2) + timedelta(days=['SICK', 'UNPAID', 'OTHER'].index(loai)))
        self.assertEqual(LeaveRequest.objects.filter(employee=self.pt).count(), 3)

    def test_uc5_1_basic_qua_man_hinh_va_hien_so_phep_con_lai(self):
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('leave:leave_create'))
        self.assertContains(r, 'Bạn còn 12')
        r = self.client.post(reverse('leave:leave_create'), {
            'leave_type': 'ANNUAL', 'duration_type': 'FULL_DAY', 'start_date': '2026-10-12', 'end_date': '2026-10-13',
            'reason': 'Việc gia đình'}, follow=True)
        self.assertContains(r, 'Gửi đơn nghỉ phép thành công.')
        self.assertEqual(LeaveRequest.objects.get().employee, self.gv)

    def test_uc5_1_exc_3_1_quy_phep_khong_du(self):
        quy = self.quy(self.gv)
        quy.used_days = Decimal('11')                                       # còn 1 ngày
        quy.save()
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.gui(self.gv)                                               # xin 2 ngày
        self.assertEqual(str(ctx.exception), 'Quỹ phép năm của bạn không đủ (còn lại: 1 ngày). Vui lòng chọn loại Nghỉ không lương.')
        quy.used_days = Decimal('11.5')
        quy.save()
        with self.assertRaisesMessage(LoiNghiepVu, 'còn lại: 0,5 ngày'):
            self.gui(self.gv)
        self.assertEqual(LeaveRequest.objects.count(), 0)
        self.gui(self.gv, 'ANNUAL', 'HALF_DAY_PM', T2, T2)                  # đúng bằng số còn lại thì được
        self.assertEqual(LeaveRequest.objects.count(), 1)

    def test_uc5_1_exc_3_1_hien_canh_bao_do_tren_man_hinh(self):
        quy = self.quy(self.gv)
        quy.used_days = Decimal('11')
        quy.save()
        self.dang_nhap(self.gv)
        r = self.client.post(reverse('leave:leave_create'), {
            'leave_type': 'ANNUAL', 'duration_type': 'FULL_DAY', 'start_date': '2026-10-12', 'end_date': '2026-10-13', 'reason': 'x'})
        self.assertContains(r, 'Quỹ phép năm của bạn không đủ (còn lại: 1 ngày). Vui lòng chọn loại Nghỉ không lương.')
        self.assertContains(r, 'alert-danger')

    def test_uc5_1_exc_3_2_ngay_bat_dau_sau_ngay_ket_thuc(self):
        with self.assertRaisesMessage(LoiNghiepVu, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'):
            self.gui(self.gv, tu=T3, den=T2)
        self.dang_nhap(self.gv)
        r = self.client.post(reverse('leave:leave_create'), {
            'leave_type': 'SICK', 'duration_type': 'FULL_DAY', 'start_date': '2026-10-13', 'end_date': '2026-10-12', 'reason': 'x'})
        self.assertContains(r, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_uc5_1_exc_3_3_trung_don_dang_cho_hoac_da_duyet(self):
        don = self.gui(self.gv)
        with self.assertRaisesMessage(LoiNghiepVu, 'Bạn đã có đơn nghỉ trong khoảng thời gian này.'):
            self.gui(self.gv, 'SICK', tu=T3, den=T3 + timedelta(days=1))    # chạm ngày 13/10
        don.status = 'APPROVED'
        don.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.TRUNG_DON_NGHI):
            self.gui(self.gv, 'SICK', tu=T2, den=T2)

    def test_don_da_huy_hoac_tu_choi_khong_gay_trung(self):
        for trang_thai in ('CANCELLED', 'REJECTED'):
            don = self.gui(self.gv)
            don.status = trang_thai
            don.save()
        self.gui(self.gv)                                                   # ngày đó giờ trống
        self.assertEqual(LeaveRequest.objects.filter(status='PENDING').count(), 1)

    def test_nghi_sang_va_nghi_chieu_cung_ngay_khong_trung_nhung_nua_ngay_va_ca_ngay_thi_trung(self):
        self.gui(self.gv, 'SICK', 'HALF_DAY_AM', T2, T2)
        self.gui(self.gv, 'SICK', 'HALF_DAY_PM', T2, T2)                    # nửa còn lại: hợp lệ
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.TRUNG_DON_NGHI):
            self.gui(self.gv, 'SICK', 'HALF_DAY_AM', T2, T2)                # cùng nửa: trùng
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.TRUNG_DON_NGHI):
            self.gui(self.gv, 'SICK', 'FULL_DAY', T2, T2)                   # cả ngày chồng lên nửa ngày: trùng

    def test_uc5_1_exc_3_4_part_time_chon_phep_nam(self):
        with self.assertRaisesMessage(LoiNghiepVu, 'Chỉ nhân sự Full-time được sử dụng phép năm.'):
            self.gui(self.pt)
        self.dang_nhap(self.pt)
        r = self.client.post(reverse('leave:leave_create'), {
            'leave_type': 'ANNUAL', 'duration_type': 'FULL_DAY', 'start_date': '2026-10-12', 'end_date': '2026-10-13', 'reason': 'x'})
        self.assertContains(r, 'Chỉ nhân sự Full-time được sử dụng phép năm.')

    def test_uc5_1_exc_3_5_khong_co_ngay_lam_viec(self):
        chu_nhat = date(2026, 10, 11)
        with self.assertRaisesMessage(LoiNghiepVu, 'Khoảng thời gian đã chọn không có ngày làm việc.'):
            self.gui(self.gv, 'SICK', tu=chu_nhat, den=chu_nhat)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.KHONG_CO_NGAY_LAM_VIEC):
            self.gui(self.gv, 'SICK', 'HALF_DAY_AM', chu_nhat, chu_nhat)

    def test_nua_ngay_phai_cung_ngay(self):
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.NUA_NGAY_CUNG_NGAY):
            self.gui(self.gv, 'SICK', 'HALF_DAY_AM', T2, T3)

    def test_uc5_1_thang_da_chot_luong_khong_gui_duoc_don(self):
        Payroll.objects.create(employee=self.gv, period_month=10, period_year=2026, status='LOCKED')
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.gui(self.gv)
        self.assertEqual(str(ctx.exception), 'Tháng 10/2026 đã chốt lương, không thể gửi đơn nghỉ trong tháng này.')
        with self.assertRaisesMessage(LoiNghiepVu, 'Tháng 10/2026 đã chốt'):                 # đơn vắt qua tháng 10 → 11
            self.gui(self.gv, 'SICK', tu=date(2026, 10, 30), den=date(2026, 11, 2))
        self.gui(self.gv, 'SICK', tu=date(2026, 11, 2), den=date(2026, 11, 3))               # tháng 11 chưa chốt: được
        Payroll.objects.filter(employee=self.gv).update(status='DRAFT')                      # bảng lương nháp không khóa
        self.gui(self.gv, 'SICK', tu=T2, den=T2)

    def test_nhan_su_khong_hoat_dong_khong_gui_duoc(self):
        self.gv.status = 'RESIGNED'
        self.gv.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_NHAN_SU_HOAT_DONG_NGHI):
            self.gui(self.gv)

    def test_super_admin_khong_co_ho_so_khong_tao_don(self):
        self.dang_nhap(self.sa)
        self.assertContains(self.client.get(reverse('leave:leave_create')), thong_bao.KHONG_CO_HO_SO, status_code=403)

    def test_uc5_1_alt_1_1_huy_don_dang_cho(self):
        don = self.gui(self.gv)
        Notification.objects.all().delete()
        services.huy_don_nghi(self.gv, don)
        don.refresh_from_db()
        self.assertEqual(don.status, LeaveStatus.CANCELLED)
        nguoi_nhan = set(Notification.objects.filter(title=thong_bao.TB_HUY_DON_TIEU_DE).values_list('recipient_id', flat=True))
        self.assertEqual(nguoi_nhan, {self.ql.user_id, self.ql2.user_id})

    def test_uc5_1_alt_1_1_huy_don_qua_man_hinh(self):
        don = self.gui(self.gv)
        self.dang_nhap(self.gv)
        r = self.client.post(reverse('leave:cancel', args=[don.pk]), follow=True)
        self.assertContains(r, 'Đã hủy đơn nghỉ phép.')
        don.refresh_from_db()
        self.assertEqual(don.status, 'CANCELLED')

    def test_chi_huy_duoc_don_dang_cho_va_cua_chinh_minh(self):
        don = self.gui(self.gv)
        don.status = 'APPROVED'
        don.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.KHONG_HUY_DON_DUOC):
            services.huy_don_nghi(self.gv, don)
        don.status = 'PENDING'
        don.save()
        with self.assertRaises(KhongCoQuyen):
            services.huy_don_nghi(self.kt, don)
        self.dang_nhap(self.kt)                                              # qua URL: người khác bị chặn
        self.assertEqual(self.client.post(reverse('leave:cancel', args=[don.pk])).status_code, 403)
        don.refresh_from_db()
        self.assertEqual(don.status, 'PENDING')


class Uc52Test(NenTangNghi):
    def duyet(self, don, nguoi=None):
        return services.duyet_don_nghi(nguoi or self.ql.user, don, BAY_GIO)

    def test_uc5_2_basic_duyet_don_phep_nam_tru_quy(self):
        don = self.gui(self.gv)
        ket_qua = self.duyet(don)
        don.refresh_from_db()
        self.assertEqual((don.status, don.reviewed_by, don.reviewed_at), ('APPROVED', self.ql.user, BAY_GIO))
        self.assertFalse(don.needs_substitute)
        self.assertEqual(ket_qua, {'buoi_chinh': 0, 'buoi_tro_giang': 0, 'ca_lam_viec': 0})
        quy = self.quy(self.gv)
        self.assertEqual((quy.used_days, quy.remaining_days), (Decimal('2'), Decimal('10')))
        self.assertTrue(Notification.objects.filter(recipient=self.gv.user, title=thong_bao.TB_KET_QUA_DON_TIEU_DE).exists())
        self.assertTrue(ActivityLog.objects.filter(action='APPROVE', model_name='leave_requests', object_id=don.pk).exists())

    def test_duyet_don_khong_phai_phep_nam_khong_tru_quy(self):
        self.duyet(self.gui(self.gv, 'SICK'))
        self.assertEqual(self.quy(self.gv).used_days, 0)

    def test_uc5_2_basic_don_anh_huong_buoi_day_chinh_tao_yeu_cau_day_thay(self):
        lop = self.tao_lop_gv()
        don = self.gui(self.gv, tu=date(2026, 10, 7), den=date(2026, 10, 9))     # Thứ 4 – Thứ 6: buổi 7/10 và 9/10
        Notification.objects.all().delete()
        ket_qua = self.duyet(don)
        self.assertEqual(ket_qua['buoi_chinh'], 2)
        don.refresh_from_db()
        self.assertTrue(don.needs_substitute)
        yeu_cau = SubstituteRequest.objects.filter(leave_request=don)
        self.assertEqual(yeu_cau.count(), 2)
        self.assertEqual({y.status for y in yeu_cau}, {'SEARCHING'})
        self.assertEqual({y.teaching_session.session_date for y in yeu_cau}, {date(2026, 10, 7), date(2026, 10, 9)})
        self.assertEqual({y.teaching_session.study_class for y in yeu_cau}, {lop})
        for ql in (self.ql, self.ql2):                                            # Quản lý nhận thông báo "cần người thay"
            self.assertTrue(Notification.objects.filter(recipient=ql.user, title=thong_bao.TB_CAN_DAY_THAY_TIEU_DE).exists())

    def test_uc5_2_nghi_nua_ca_chi_anh_huong_dung_buoi(self):
        self.tao_lop_gv()                                                         # Ca 2: mốc giữa ca 17:00; buổi 18:00 thuộc NỬA SAU
        sang = self.gui(self.gv, 'SICK', 'HALF_DAY_AM', date(2026, 10, 7), date(2026, 10, 7))
        chieu = self.gui(self.gv, 'SICK', 'HALF_DAY_PM', date(2026, 10, 7), date(2026, 10, 7))
        self.assertEqual(len(lich.lich_bi_anh_huong(self.gv, sang.start_date, sang.end_date, sang.duration_type)['buoi_chinh']), 0)
        self.assertEqual(len(lich.lich_bi_anh_huong(self.gv, chieu.start_date, chieu.end_date, chieu.duration_type)['buoi_chinh']), 1)
        self.assertEqual(self.duyet(sang)['buoi_chinh'], 0)
        self.assertEqual(SubstituteRequest.objects.count(), 0)
        self.assertEqual(self.duyet(chieu)['buoi_chinh'], 1)
        self.assertEqual(SubstituteRequest.objects.count(), 1)

    def test_moc_giua_ca_theo_tung_ca_va_part_time(self):
        gv_ca1 = hoat_dong('gv1@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_1)
        self.assertEqual(lich.moc_giua_ca(gv_ca1), time(12))
        self.assertEqual(lich.moc_giua_ca(self.gv), time(17))
        self.assertEqual(lich.moc_giua_ca(self.pt), time(12))

    def test_uc5_2_buoi_tro_giang_va_ca_lam_viec_chi_bao_quan_ly_khong_tao_yeu_cau(self):
        tg = hoat_dong('tg@icls.vn', UserRole.EMPLOYEE, Position.TEACHING_ASSISTANT, PT)
        self.tao_lop_gv(tro_giang=tg)
        ShiftAssignment.objects.create(
            slot_group='g1', employee=tg, shift_role='Lễ tân', work_date=T2, planned_start=time(9), planned_end=time(12),
            registration_deadline=datetime(2026, 10, 1), status='SCHEDULED')
        don = self.gui(tg, 'SICK', tu=date(2026, 10, 7), den=T2)                  # 7 – 12/10
        Notification.objects.all().delete()
        ket_qua = self.duyet(don)
        self.assertEqual((ket_qua['buoi_chinh'], ket_qua['buoi_tro_giang'], ket_qua['ca_lam_viec']), (0, 3, 1))   # buổi 7, 9, 12/10
        self.assertEqual(SubstituteRequest.objects.count(), 0)
        don.refresh_from_db()
        self.assertFalse(don.needs_substitute)
        thong_bao_ql = Notification.objects.filter(recipient=self.ql.user, title=thong_bao.TB_DIEU_CHINH_LICH_TIEU_DE).get()
        self.assertIn('3 buổi làm trợ giảng và 1 ca làm việc', thong_bao_ql.message)

    def test_uc5_2_alt_5_1_tu_choi_kem_ly_do(self):
        don = self.gui(self.gv)
        services.tu_choi_don_nghi(self.ql.user, don, 'Trùng lịch thi', BAY_GIO)
        don.refresh_from_db()
        self.assertEqual((don.status, don.review_note, don.reviewed_by), ('REJECTED', 'Trùng lịch thi', self.ql.user))
        self.assertEqual(self.quy(self.gv).used_days, 0)                          # giữ nguyên quỹ phép
        tb = Notification.objects.get(recipient=self.gv.user, title=thong_bao.TB_KET_QUA_DON_TIEU_DE)
        self.assertIn('Trùng lịch thi', tb.message)

    def test_uc5_2_exc_5_2_tu_choi_khong_nhap_ly_do(self):
        don = self.gui(self.gv)
        for ly_do in ('', '   '):
            with self.assertRaises(LoiNghiepVu) as ctx:
                services.tu_choi_don_nghi(self.ql.user, don, ly_do)
            self.assertEqual(str(ctx.exception), 'Vui lòng nhập lý do từ chối.')
        don.refresh_from_db()
        self.assertEqual(don.status, 'PENDING')

    def test_uc5_2_exc_5_2_qua_man_hinh(self):
        don = self.gui(self.gv)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('leave:decide', args=[don.pk]), {'hanh_dong': 'tu_choi', 'ly_do': ''}, follow=True)
        self.assertContains(r, 'Vui lòng nhập lý do từ chối.')
        don.refresh_from_db()
        self.assertEqual(don.status, 'PENDING')

    def test_uc5_2_exc_5_3_quy_phep_khong_con_du_luc_duyet(self):
        quy = self.quy(self.gv)
        quy.used_days = Decimal('9')                                              # còn 3 ngày
        quy.save()
        don_a = self.gui(self.gv, tu=T2, den=T3)                                  # 2 ngày
        don_b = self.gui(self.gv, tu=date(2026, 10, 14), den=date(2026, 10, 15))  # 2 ngày: lúc gửi mỗi đơn đều còn đủ
        self.duyet(don_a)                                                         # còn 1
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.duyet(don_b)
        self.assertEqual(str(ctx.exception), 'Quỹ phép của nhân sự không còn đủ. Vui lòng từ chối hoặc đề nghị nhân sự đổi loại nghỉ.')
        don_b.refresh_from_db()
        self.assertEqual(don_b.status, 'PENDING')                                 # giao dịch lùi lại, đơn vẫn chờ
        self.assertEqual(self.quy(self.gv).used_days, Decimal('11'))

    def test_uc5_2_exc_3_1_don_da_xu_ly(self):
        don = self.gui(self.gv)
        self.duyet(don)
        with self.assertRaisesMessage(LoiNghiepVu, 'Yêu cầu đã được xử lý.'):
            self.duyet(don)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.YEU_CAU_DA_XU_LY):
            services.tu_choi_don_nghi(self.ql.user, don, 'x')
        self.assertEqual(self.quy(self.gv).used_days, Decimal('2'))               # không bị trừ hai lần
        don_huy = self.gui(self.gv, 'SICK', tu=date(2026, 10, 20), den=date(2026, 10, 20))
        services.huy_don_nghi(self.gv, don_huy)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.YEU_CAU_DA_XU_LY):
            self.duyet(don_huy)

    def test_uc5_2_exc_3_1_qua_man_hinh_tai_lai_danh_sach(self):
        don = self.gui(self.gv)
        self.duyet(don)
        self.dang_nhap(self.ql)
        r = self.client.post(reverse('leave:decide', args=[don.pk]), {'hanh_dong': 'duyet'}, follow=True)
        self.assertContains(r, 'Yêu cầu đã được xử lý.')
        self.assertRedirects(r, reverse('leave:review'))

    def test_q2_phan_cap_duyet_khong_tu_duyet(self):
        don_nv = self.gui(self.gv)
        don_kt = self.gui(self.kt)
        don_ql = self.gui(self.ql)
        self.duyet(don_nv)                                                        # Quản lý duyệt Nhân viên
        self.duyet(don_kt)                                                        # Quản lý duyệt Kế toán
        with self.assertRaises(KhongCoQuyen):                                     # Quản lý khác không duyệt được đơn Quản lý
            self.duyet(don_ql, self.ql2.user)
        with self.assertRaises(KhongCoQuyen):                                     # Quản lý không tự duyệt
            self.duyet(don_ql, self.ql.user)
        with self.assertRaises(KhongCoQuyen):                                     # Kế toán, Nhân viên không có quyền duyệt
            self.duyet(self.gui(self.pt, 'SICK'), self.kt.user)
        self.duyet(don_ql, self.sa)                                               # Super Admin duyệt đơn Quản lý
        don_ql.refresh_from_db()
        self.assertEqual((don_ql.status, don_ql.reviewed_by), ('APPROVED', self.sa))
        don_moi = self.gui(self.gv, 'SICK', tu=date(2026, 10, 20), den=date(2026, 10, 20))
        with self.assertRaises(KhongCoQuyen):                                     # Super Admin không duyệt đơn Nhân viên
            self.duyet(don_moi, self.sa)

    def test_pham_vi_danh_sach_duyet(self):
        don_nv, don_kt, don_ql = self.gui(self.gv), self.gui(self.kt), self.gui(self.ql)
        self.assertEqual(set(services.danh_sach_don_duyet(self.ql.user)), {don_nv, don_kt})   # không có đơn của chính mình / Quản lý
        self.assertEqual(set(services.danh_sach_don_duyet(self.ql2.user)), {don_nv, don_kt})      # đơn của Quản lý chỉ Super Admin duyệt
        self.assertEqual(set(services.danh_sach_don_duyet(self.sa)), {don_ql})
        self.assertEqual(list(services.danh_sach_don_duyet(self.kt.user)), [])
        self.duyet(don_nv)
        self.assertEqual(set(services.danh_sach_don_duyet(self.ql.user)), {don_kt})           # mặc định chỉ PENDING
        self.assertEqual(set(services.danh_sach_don_duyet(self.ql.user, trang_thai='')), {don_nv, don_kt})
        self.assertEqual(set(services.danh_sach_don_duyet(self.ql.user, tu_khoa='kt')), {don_kt})

    def test_uc5_2_basic_qua_man_hinh_duyet_danh_sach_va_chi_tiet(self):
        don = self.gui(self.gv, tu=T2, den=T3)
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('leave:review'))
        self.assertContains(r, 'Duyệt nghỉ phép')
        self.assertContains(r, 'gv@icls.vn')
        self.assertEqual(r.context['so']['cho_duyet'], 1)
        r = self.client.get(reverse('leave:detail', args=[don.pk]))
        self.assertContains(r, 'Duyệt đơn')
        self.assertContains(r, 'Quỹ phép còn lại')
        r = self.client.post(reverse('leave:decide', args=[don.pk]), {'hanh_dong': 'duyet'}, follow=True)
        self.assertContains(r, 'Đã duyệt đơn nghỉ phép.')
        don.refresh_from_db()
        self.assertEqual(don.status, 'APPROVED')

    def test_phan_quyen_man_hinh_duyet(self):
        don = self.gui(self.gv)
        for nguoi in (self.gv, self.kt, self.pt):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('leave:review')).status_code, 403)
            self.assertEqual(self.client.post(reverse('leave:decide', args=[don.pk]), {'hanh_dong': 'duyet'}).status_code, 403)
        self.dang_nhap(self.ql2)
        self.assertEqual(self.client.get(reverse('leave:review')).status_code, 200)
        self.dang_nhap(self.sa)                                                   # SA vào được trang duyệt nhưng không duyệt đơn Nhân viên
        self.assertEqual(self.client.get(reverse('leave:review')).status_code, 200)
        self.assertEqual(self.client.post(reverse('leave:decide', args=[don.pk]), {'hanh_dong': 'duyet'}).status_code, 403)
        don.refresh_from_db()
        self.assertEqual(don.status, 'PENDING')

    def test_chi_tiet_don_chi_chu_don_va_nguoi_duyet_xem_duoc(self):
        don = self.gui(self.gv)
        for nguoi in (self.gv, self.ql, self.ql2):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('leave:detail', args=[don.pk])).status_code, 200)
        for nguoi in (self.kt, self.pt, self.sa):
            self.dang_nhap(nguoi)
            r = self.client.get(reverse('leave:detail', args=[don.pk]))
            self.assertContains(r, 'Bạn không có quyền xem đơn nghỉ này.', status_code=403)

    def test_uc5_2_lien_thong_uc6_4_duyet_don_roi_chot_nguoi_day_thay(self):
        """Từ đơn nghỉ được duyệt → yêu cầu dạy thay → Quản lý chốt người thay → lịch của người thay có buổi đó."""
        self.tao_lop_gv()
        gv_thay = hoat_dong('gvthay@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_2)
        don = self.gui(self.gv, tu=date(2026, 10, 7), den=date(2026, 10, 7))
        self.duyet(don)
        yc = SubstituteRequest.objects.get(leave_request=don)
        self.assertIn(gv_thay, lich.goi_y_giao_vien_day_thay(yc))
        self.assertNotIn(self.gv, lich.goi_y_giao_vien_day_thay(yc))              # giáo viên vắng không nằm trong gợi ý
        lich.chot_day_thay(self.ql.user, yc, gv_thay)
        buoi = TeachingSession.objects.get(pk=yc.teaching_session_id)
        self.assertEqual((buoi.actual_teacher, buoi.planned_teacher), (gv_thay, self.gv))
        buoi_day = lambda nv: [m['ngay'] for m in lich.lich_lam_viec(nv.user, date(2026, 10, 5), date(2026, 10, 11)) if m['loai'] == 'buoi']
        self.assertEqual(buoi_day(gv_thay), [date(2026, 10, 7)])                                   # người thay có thêm buổi 7/10
        self.assertEqual(buoi_day(self.gv), [date(2026, 10, 5), date(2026, 10, 9)])                # giáo viên vắng mất buổi 7/10


class Uc53Test(NenTangNghi):
    def test_uc5_3_basic_ba_the_quy_phep_va_danh_sach_don(self):
        d1 = self.gui(self.gv, tu=T2, den=T2 + timedelta(days=0), hinh_thuc='HALF_DAY_AM')       # 0,5 ngày
        services.duyet_don_nghi(self.ql.user, d1, BAY_GIO)
        d2 = self.gui(self.gv, tu=date(2026, 10, 14), den=date(2026, 10, 15))                    # 2 ngày, chờ duyệt
        self.gui(self.kt)                                                                         # đơn người khác
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('leave:my_leaves'), {'nam': 2026})
        quy = r.context['quy']
        self.assertEqual((quy.total_days, quy.used_days, quy.remaining_days), (12, Decimal('0.5'), Decimal('11.5')))
        self.assertEqual(set(r.context['trang']), {d1, d2})                                       # chỉ đơn của chính mình
        self.assertEqual((r.context['dem']['PENDING'], r.context['dem']['APPROVED']), (1, 1))
        self.assertContains(r, 'Phép còn lại')
        self.assertContains(r, '11,5')

    def test_uc5_3_loc_theo_trang_thai_va_nam(self):
        d1 = self.gui(self.gv)
        d2 = self.gui(self.gv, 'SICK', tu=date(2026, 10, 20), den=date(2026, 10, 20))
        services.huy_don_nghi(self.gv, d2)
        d_cu = LeaveRequest.objects.create(employee=self.gv, leave_type='SICK', start_date=date(2025, 3, 3), end_date=date(2025, 3, 3),
                                           total_days=1, reason='x', status='APPROVED')
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('leave:my_leaves'), {'nam': 2026, 'trang_thai': 'PENDING'})
        self.assertEqual(set(r.context['trang']), {d1})
        self.assertEqual(set(self.client.get(reverse('leave:my_leaves'), {'nam': 2026}).context['trang']), {d1, d2})
        self.assertEqual(set(self.client.get(reverse('leave:my_leaves'), {'nam': 2025}).context['trang']), {d_cu})
        self.assertEqual(self.client.get(reverse('leave:my_leaves'), {'nam': 'abc', 'trang_thai': 'xyz'}).status_code, 200)

    def test_uc5_3_exc_1_1_part_time_khong_co_quy_phep(self):
        self.gui(self.pt, 'SICK')
        self.dang_nhap(self.pt)
        r = self.client.get(reverse('leave:my_leaves'))
        self.assertIsNone(r.context['quy'])
        self.assertContains(r, 'Nhân sự Part-time không có quỹ phép năm.')
        self.assertNotContains(r, 'Phép còn lại')
        self.assertEqual(len(r.context['trang']), 1)                                              # vẫn có danh sách đơn

    def test_uc5_3_cua_ca_quan_ly_ke_toan_nhan_vien_va_super_admin(self):
        for nguoi in (self.ql, self.kt, self.gv):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('leave:my_leaves')).status_code, 200)
        self.dang_nhap(self.sa)
        self.assertRedirects(self.client.get(reverse('leave:my_leaves')), reverse('leave:review'))

    def test_menu_leave_da_bat(self):
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('leave:my_leaves'))
        self.assertTrue(any(m['url'] == reverse('leave:my_leaves') for m in r.context['menu_chinh']))


class Uc54Test(NenTangNghi):
    def don_da_duyet(self, nv, loai, tu, den, ht='FULL_DAY'):
        don = services.gui_don_nghi(nv, loai, ht, tu, den, 'x')
        services.duyet_don_nghi(self.ql.user if nv.user.role != 'MANAGER' else self.sa, don, BAY_GIO)
        return don

    def test_uc5_4_basic_don_da_duyet_tong_theo_loai_va_phep_con_lai(self):
        self.don_da_duyet(self.gv, 'ANNUAL', T2, T3)                                   # 2 ngày phép năm
        self.don_da_duyet(self.kt, 'SICK', date(2026, 10, 14), date(2026, 10, 14))     # 1 ngày ốm
        self.don_da_duyet(self.pt, 'UNPAID', date(2026, 10, 15), date(2026, 10, 15), 'HALF_DAY_AM')   # 0,5 ngày
        self.gui(self.gv, 'SICK', tu=date(2026, 10, 20), den=date(2026, 10, 20))       # còn chờ duyệt: không tính
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('leave:summary'), {'thang': '2026-10'})
        ket_qua = r.context['ket_qua']
        self.assertEqual(len(ket_qua['dong']), 3)
        tong = dict(ket_qua['tong_theo_loai'])
        self.assertEqual((tong['Phép năm'], tong['Nghỉ ốm'], tong['Không lương'], tong['Khác']),
                         (Decimal('2'), Decimal('1'), Decimal('0.5'), Decimal('0')))
        con_lai = {d['nhan_su'].full_name: d['quy'].remaining_days for d in ket_qua['phep_con_lai']}
        self.assertEqual(con_lai['gv@icls.vn'], Decimal('10'))
        self.assertEqual(con_lai['kt@icls.vn'], Decimal('12'))
        self.assertNotIn('pt@icls.vn', con_lai)                                        # Part-time không có quỹ phép

    def test_uc5_4_don_vat_qua_hai_thang_chi_dem_phan_trong_thang(self):
        don = self.don_da_duyet(self.gv, 'ANNUAL', date(2026, 10, 30), date(2026, 11, 3))   # T6, T7 | CN(1/11), T2, T3
        self.assertEqual(don.total_days, Decimal('4'))
        self.assertEqual(services.so_ngay_trong_thang(don, 10, 2026), Decimal('2'))
        self.assertEqual(services.so_ngay_trong_thang(don, 11, 2026), Decimal('2'))
        thang_10 = services.tong_hop_nghi_phep(10, 2026)
        thang_11 = services.tong_hop_nghi_phep(11, 2026)
        self.assertEqual(dict(thang_10['tong_theo_loai'])['Phép năm'], Decimal('2'))
        self.assertEqual(dict(thang_11['tong_theo_loai'])['Phép năm'], Decimal('2'))
        self.assertEqual(services.tong_hop_nghi_phep(12, 2026)['dong'], [])

    def test_uc5_4_loc_phong_ban_vi_tri_loai_nghi(self):
        self.gv.department = Department.HR_ADMIN
        self.gv.save()
        self.don_da_duyet(self.gv, 'ANNUAL', T2, T2)
        self.don_da_duyet(self.kt, 'SICK', T2, T2)
        ten = lambda kq: sorted(d['don'].employee.full_name for d in kq['dong'])
        self.assertEqual(ten(services.tong_hop_nghi_phep(10, 2026)), ['gv@icls.vn', 'kt@icls.vn'])
        self.assertEqual(ten(services.tong_hop_nghi_phep(10, 2026, phong_ban=Department.HR_ADMIN)), ['gv@icls.vn'])
        self.assertEqual(ten(services.tong_hop_nghi_phep(10, 2026, vi_tri=Position.ACCOUNTANT)), ['kt@icls.vn'])
        self.assertEqual(ten(services.tong_hop_nghi_phep(10, 2026, loai='SICK')), ['kt@icls.vn'])
        ds = services.tong_hop_nghi_phep(10, 2026, phong_ban=Department.HR_ADMIN)['phep_con_lai']
        self.assertEqual([d['nhan_su'].full_name for d in ds], ['gv@icls.vn'])               # bảng phép còn lại cũng lọc

    def test_uc5_4_exc_3_1_khong_co_du_lieu(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('leave:summary'), {'thang': '2026-07'})
        self.assertContains(r, 'Không có dữ liệu nghỉ phép trong khoảng thời gian đã chọn.')
        self.gui(self.gv)                                                                       # đơn chỉ chờ duyệt vẫn là "không có dữ liệu"
        self.assertContains(self.client.get(reverse('leave:summary'), {'thang': '2026-10'}), thong_bao.KHONG_CO_DU_LIEU_NGHI)

    def test_uc5_4_phan_quyen_chi_quan_ly_va_super_admin(self):
        for nguoi in (self.kt, self.gv, self.pt):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('leave:summary')).status_code, 403)
        for nguoi in (self.ql, self.sa):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('leave:summary')).status_code, 200)

    def test_uc5_4_thang_sai_dinh_dang_dung_thang_hien_tai(self):
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('leave:summary'), {'thang': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.context['thang'], r.context['nam']), (date.today().month, date.today().year))


# ============================================================ UC 9.2 – bước 6: quỹ phép hằng năm (P10)
class TaoQuyPhepHangLoatTest(TestCase):
    def test_chi_tao_cho_full_time_active_chua_co_quy_va_chay_lai_khong_trung(self):
        from core.mau_test import tao_nhan_su_hoat_dong as hoat_dong
        from employees.models import EmploymentType as LH
        from leave import services as dv
        from leave.models import LeaveBalance as Quy
        ft1 = hoat_dong('ft1@icls.vn', loai_hinh=LH.FULL_TIME)
        ft2 = hoat_dong('ft2@icls.vn', loai_hinh=LH.FULL_TIME)
        hoat_dong('pt@icls.vn', loai_hinh=LH.PART_TIME)                       # Part-time: không có phép năm (Q11)
        onb = hoat_dong('onb@icls.vn', loai_hinh=LH.FULL_TIME)
        onb.status = 'ONBOARDING'
        onb.save()
        Quy.objects.create(employee=ft2, year=2026, total_days=12, used_days=3)    # đã có quỹ: giữ nguyên
        self.assertEqual(dv.tao_quy_phep_hang_loat(2026), 1)
        self.assertEqual(Quy.objects.get(employee=ft1, year=2026).total_days, 12)
        self.assertEqual(Quy.objects.get(employee=ft2, year=2026).used_days, 3)
        self.assertEqual(Quy.objects.filter(year=2026).count(), 2)
        self.assertEqual(dv.tao_quy_phep_hang_loat(2026), 0)
        self.assertEqual(dv.tao_quy_phep_hang_loat(2027), 2)                  # sang năm mới tạo quỹ mới cho cả hai
