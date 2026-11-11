"""Test của app payroll – P1: các ràng buộc CSDL (§7.3.16–7.3.18)."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.mau_test import tao_nhan_su
from payroll.models import Payroll, PayrollDetail, SalaryConfig


class RangBuocPayrollTest(TestCase):
    def test_cung_ngay_ap_dung_khong_co_hai_cau_hinh(self):
        nv = tao_nhan_su()
        SalaryConfig.objects.create(employee=nv, effective_from=date(2026, 1, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            SalaryConfig.objects.create(employee=nv, effective_from=date(2026, 1, 1))

    def test_so_tien_am_trong_cau_hinh_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SalaryConfig.objects.create(employee=tao_nhan_su(), base_salary=-1, effective_from=date(2026, 1, 1))

    def test_effective_to_truoc_effective_from_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SalaryConfig.objects.create(employee=tao_nhan_su(), effective_from=date(2026, 2, 1),
                                        effective_to=date(2026, 1, 1))

    def test_mot_bang_luong_moi_nhan_su_moi_thang(self):
        nv = tao_nhan_su()
        Payroll.objects.create(employee=nv, period_month=9, period_year=2026)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payroll.objects.create(employee=nv, period_month=9, period_year=2026)

    def test_thang_ngoai_1_12_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payroll.objects.create(employee=tao_nhan_su(), period_month=13, period_year=2026)

    def test_chi_tiet_luong_so_tien_am_bi_chan(self):
        pl = Payroll.objects.create(employee=tao_nhan_su(), period_month=9, period_year=2026)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PayrollDetail.objects.create(payroll=pl, detail_type='EARNING', category='BONUS',
                                         description='Thưởng', amount=-5)


class ThangDaChotTest(TestCase):
    """§9.2 `thang_da_chot` (viết ở P7): chỉ bảng lương LOCKED hoặc SENT mới khóa tháng."""

    def test_thang_da_chot_theo_trang_thai_bang_luong(self):
        from payroll.services import thang_da_chot
        nv = tao_nhan_su()
        self.assertFalse(thang_da_chot(10, 2026))                                  # chưa có bảng lương
        bang = Payroll.objects.create(employee=nv, period_month=10, period_year=2026)   # DRAFT
        self.assertFalse(thang_da_chot(10, 2026))
        bang.status = 'LOCKED'
        bang.save()
        self.assertTrue(thang_da_chot(10, 2026))
        bang.status = 'SENT'
        bang.save()
        self.assertTrue(thang_da_chot(10, 2026))
        self.assertFalse(thang_da_chot(11, 2026))                                  # tháng khác không bị ảnh hưởng
        self.assertFalse(thang_da_chot(10, 2025))


# =====================================================================================================
# P9 – UC 7.1, 7.2, 7.3. Tên test bám mã luồng ở §10 (ROADMAP §12.1). Tháng lương mẫu: 10/2026, lập ngày 02/11/2026.
# =====================================================================================================
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse

from accounts.models import User, UserRole
from attendance.models import Attendance
from attendance.services import gui_giai_trinh
from contracts.models import Contract
from core import thong_bao
from core.mau_test import tao_nhan_su_hoat_dong as hoat_dong
from core.models import ActivityLog, Notification
from core.services import LoiNghiepVu
from employees.models import EmployeeStatus, EmploymentType, Position, WorkShift
from leave.models import LeaveRequest
from leave.services import gui_don_nghi
from payroll import services
from payroll.models import PayrollDetail, PayrollDetailCategory as Nhom, PayrollDetailType as Loai, PayrollStatus
from schedule.models import AssignmentRole, ClassAssignment, StudyClass, TeachingSession

FT, PT = EmploymentType.FULL_TIME, EmploymentType.PART_TIME
D = Decimal
HOM_NAY = date(2026, 11, 2)           # sau khi tháng 10/2026 kết thúc


class NenTangLuong(TestCase):
    """Super Admin, Kế toán, Quản lý, giáo viên Full-time, nhân viên Part-time, trợ giảng Part-time, mỗi người có cấu hình lương."""

    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN, full_name='SA')
        self.kt = hoat_dong('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, FT)
        self.ql = hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER, FT)
        self.gv = hoat_dong('gv@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, FT, WorkShift.SHIFT_2)
        self.pt = hoat_dong('pt@icls.vn', UserRole.EMPLOYEE, Position.STAFF, PT)
        self.tg = hoat_dong('tg@icls.vn', UserRole.EMPLOYEE, Position.TEACHING_ASSISTANT, PT)
        self.cau_hinh(self.kt, base_salary=10_000_000)
        self.cau_hinh(self.ql, base_salary=20_000_000, responsibility_allowance=2_000_000)
        self.cau_hinh(self.gv, base_salary=12_000_000, class_allowance_rate=500_000)
        self.cau_hinh(self.pt, hourly_rate=35_000)
        self.cau_hinh(self.tg, hourly_rate=40_000)

    def dang_nhap(self, nguoi):
        self.client.force_login(nguoi.user if hasattr(nguoi, 'user') else nguoi)

    def cau_hinh(self, nv, tu=date(2026, 1, 1), den=None, **gia_tri):
        return SalaryConfig.objects.create(employee=nv, effective_from=tu, effective_to=den, **gia_tri)

    def ngay_lam(self, so_ngay, thang=10, nam=2026):
        """So_ngay ngày Thứ 2–Thứ 7 đầu tiên của tháng."""
        ngay, ket_qua = date(nam, thang, 1), []
        while len(ket_qua) < so_ngay:
            if ngay.weekday() != 6:
                ket_qua.append(ngay)
            ngay += timedelta(days=1)
        return ket_qua

    def di_lam(self, nv, ngay, bd=time(8), kt=time(17), vao=None, ra=None, trang_thai='ON_TIME', **kw):
        return Attendance.objects.create(employee=nv, work_date=ngay, planned_start=bd, planned_end=kt,
                                         check_in=vao, check_out=ra, attendance_status=trang_thai, **kw)

    def du_lieu_thang_10(self):
        """Dữ liệu chấm công tháng 10/2026 để tính tay (xem số trong các test)."""
        for ngay in self.ngay_lam(20):                                            # gv: 20 ngày đi làm + 2 ngày phép năm = 22 công
            self.di_lam(self.gv, ngay)
        LeaveRequest.objects.create(employee=self.gv, leave_type='ANNUAL', duration_type='FULL_DAY', start_date=date(2026, 10, 28),
                                    end_date=date(2026, 10, 29), total_days=2, reason='x', status='APPROVED')
        for ngay in self.ngay_lam(26):                                            # ql: đủ 26 công
            self.di_lam(self.ql, ngay)
        d1, d2 = date(2026, 10, 1), date(2026, 10, 2)                             # pt: 4 giờ + 4 giờ = 8 giờ
        for d in (d1, d2):
            self.di_lam(self.pt, d, time(8), time(12), datetime.combine(d, time(8)), datetime.combine(d, time(12)))
        d3 = date(2026, 10, 3)                                                    # tg: 18:10 → 20:40 trong khung 18–20 = 1,83 giờ
        self.di_lam(self.tg, d3, time(18), time(20), datetime.combine(d3, time(18, 10)), datetime.combine(d3, time(20, 40)))
        # lớp tính phụ cấp: lớp A (có buổi trong tháng) = 1; lớp B (mọi buổi bị hủy) = 0; lớp C (phân công hết hạn 30/9) = 0
        for ten, hieu_luc_den, trang_thai in (('A', None, 'SCHEDULED'), ('B', None, 'CANCELLED'), ('C', date(2026, 9, 30), 'SCHEDULED')):
            lop = StudyClass.objects.create(class_name=ten, subject='s', weekdays='1', start_time=time(18), end_time=time(20),
                                            start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
            ClassAssignment.objects.create(study_class=lop, employee=self.gv, assignment_role=AssignmentRole.MAIN_TEACHER,
                                           start_date=date(2026, 9, 1), end_date=hieu_luc_den)
            TeachingSession.objects.create(study_class=lop, session_date=date(2026, 10, 6), planned_start=time(18), planned_end=time(20),
                                           planned_teacher=self.gv, actual_teacher=self.gv, status=trang_thai)

    def lap(self, thang=10, nam=2026, hom_nay=HOM_NAY):
        return services.khoi_tao_bang_luong(self.kt.user, thang, nam, hom_nay)

    def bang(self, nv, thang=10, nam=2026):
        return Payroll.objects.get(employee=nv, period_month=thang, period_year=nam)

    def dong(self, bang):
        return {d.category: d for d in bang.details.all()}


# ---------------------------------------------------------------------------------- UC 7.1
class Uc71Test(NenTangLuong):
    def luu(self, nv, lương=0, gio=0, lop=0, tn=0, ngay=date(2026, 12, 1)):
        return services.luu_cau_hinh_luong(self.kt.user, nv, D(lương), D(gio), D(lop), D(tn), ngay)

    def test_cau_hinh_hieu_luc_theo_ngay(self):
        nv = hoat_dong('moi@icls.vn')
        self.assertIsNone(services.cau_hinh_hieu_luc(nv, date(2026, 5, 1)))               # chưa có cấu hình nào
        c1 = self.cau_hinh(nv, date(2026, 1, 1), date(2026, 5, 31), hourly_rate=30_000)
        c2 = self.cau_hinh(nv, date(2026, 6, 1), hourly_rate=35_000)
        self.assertEqual(services.cau_hinh_hieu_luc(nv, date(2026, 5, 31)), c1)            # ngày kết thúc: còn hiệu lực
        self.assertEqual(services.cau_hinh_hieu_luc(nv, date(2026, 6, 1)), c2)
        self.assertEqual(services.cau_hinh_hieu_luc(nv, date(2030, 1, 1)), c2)             # effective_to trống: còn mãi
        self.assertIsNone(services.cau_hinh_hieu_luc(nv, date(2025, 12, 31)))              # trước cấu hình đầu tiên

    def test_uc7_1_basic_them_cau_hinh_moi_dong_cau_hinh_cu(self):
        cu = SalaryConfig.objects.get(employee=self.gv)
        moi = self.luu(self.gv, lương=15_000_000, lop=600_000, tn=1_000_000, ngay=date(2026, 12, 1))
        cu.refresh_from_db()
        self.assertEqual(cu.effective_to, date(2026, 11, 30))                              # ngày áp dụng mới − 1 ngày
        self.assertEqual((moi.base_salary, moi.class_allowance_rate, moi.responsibility_allowance, moi.hourly_rate, moi.effective_to),
                         (D(15_000_000), D(600_000), D(1_000_000), D(0), None))
        self.assertEqual(SalaryConfig.objects.filter(employee=self.gv).count(), 2)         # lịch sử được bảo toàn
        self.assertEqual(services.cau_hinh_hieu_luc(self.gv, date(2026, 11, 30)), cu)
        self.assertEqual(services.cau_hinh_hieu_luc(self.gv, date(2026, 12, 1)), moi)
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='salary_configs', object_id=moi.pk).exists())

    def test_part_time_luu_don_gia_gio_va_khong_luu_luong_co_ban(self):
        moi = self.luu(self.pt, lương=9_999_999, gio=38_000, lop=5, tn=5)             # các ô không dùng cho Part-time bị bỏ
        self.assertEqual((moi.hourly_rate, moi.base_salary, moi.class_allowance_rate, moi.responsibility_allowance),
                         (D(38_000), D(0), D(0), D(0)))

    def test_phu_cap_lop_chi_danh_cho_giao_vien_full_time(self):
        moi = self.luu(self.ql, lương=21_000_000, lop=300_000, tn=2_000_000, gio=50_000)   # Quản lý không phải giáo viên
        self.assertEqual((moi.class_allowance_rate, moi.hourly_rate, moi.responsibility_allowance), (D(0), D(0), D(2_000_000)))

    def test_nhan_su_dang_onboarding_cau_hinh_duoc(self):
        nv = hoat_dong('ob@icls.vn')
        nv.status = EmployeeStatus.ONBOARDING
        nv.save()
        self.assertEqual(self.luu(nv, gio=35_000, ngay=date(2026, 12, 1)).employee, nv)

    def test_nhan_su_da_nghi_khong_cau_hinh_duoc(self):
        self.gv.status = EmployeeStatus.RESIGNED
        self.gv.save()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.NHAN_SU_KHONG_CAU_HINH_LUONG):
            self.luu(self.gv, lương=1_000_000)

    def test_uc7_1_exc_5_1_ngay_ap_dung_khong_sau_cau_hinh_hien_tai(self):
        for ngay in (date(2026, 1, 1), date(2025, 12, 31)):                                 # bằng và trước ngày áp dụng hiện tại
            with self.assertRaises(LoiNghiepVu) as ctx:
                self.luu(self.gv, lương=15_000_000, ngay=ngay)
            self.assertEqual(str(ctx.exception), 'Ngày áp dụng phải sau ngày áp dụng của cấu hình hiện tại.')
        self.assertEqual(SalaryConfig.objects.filter(employee=self.gv).count(), 1)

    def test_uc7_1_exc_5_2_so_tien_khong_hop_le(self):
        for kwargs, truong, cau in (({'lương': -1}, 'base_salary', thong_bao.SO_TIEN_AM), ({'lương': 1, 'tn': -5}, 'responsibility_allowance', thong_bao.SO_TIEN_AM),
                                    ({'lương': 0}, 'base_salary', thong_bao.LUONG_CO_BAN_PHAI_DUONG)):
            with self.assertRaises(services.LoiTruongNhap) as ctx:
                self.luu(self.gv, **kwargs)
            self.assertEqual((str(ctx.exception), ctx.exception.truong), (cau, truong))
        for kwargs, cau in (({'gio': 0}, thong_bao.DON_GIA_GIO_PHAI_DUONG), ({'gio': -1}, thong_bao.SO_TIEN_AM)):
            with self.assertRaises(services.LoiTruongNhap) as ctx:
                self.luu(self.pt, **kwargs)
            self.assertEqual((str(ctx.exception), ctx.exception.truong), (cau, 'hourly_rate'))
        self.assertEqual(SalaryConfig.objects.filter(employee=self.gv).count(), 1)

    def test_uc7_1_exc_5_3_thang_da_chot_luong(self):
        Payroll.objects.create(employee=self.kt, period_month=12, period_year=2026, status='LOCKED')
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.luu(self.gv, lương=15_000_000, ngay=date(2026, 12, 15))
        self.assertEqual(str(ctx.exception), 'Không thể áp dụng cấu hình cho tháng đã chốt lương.')
        self.assertIsNone(SalaryConfig.objects.get(employee=self.gv).effective_to)          # cấu hình cũ không bị đóng
        self.luu(self.gv, lương=15_000_000, ngay=date(2027, 1, 1))                           # tháng khác thì được

    def test_uc7_1_alt_1_1_lich_su_va_qua_man_hinh(self):
        self.dang_nhap(self.kt)
        r = self.client.get(reverse('payroll:config_detail', args=[self.gv.pk]))
        self.assertContains(r, 'Cấu hình đang hiệu lực')
        self.assertContains(r, '12.000.000 đ')
        r = self.client.post(reverse('payroll:config_detail', args=[self.gv.pk]), {
            'base_salary': '15000000', 'class_allowance_rate': '600000', 'responsibility_allowance': '', 'effective_from': '2026-12-01'}, follow=True)
        self.assertContains(r, 'Lưu cấu hình lương thành công.')
        self.assertEqual([c.effective_from for c in services.lich_su_cau_hinh(self.gv)], [date(2026, 12, 1), date(2026, 1, 1)])
        self.assertContains(r, 'Lịch sử cấu hình lương')

    def test_uc7_1_loi_hien_tai_truong_qua_man_hinh(self):
        self.dang_nhap(self.kt)
        r = self.client.post(reverse('payroll:config_detail', args=[self.gv.pk]), {
            'base_salary': '-5', 'effective_from': '2026-12-01'})
        self.assertContains(r, 'Số tiền không được âm.')
        self.assertContains(r, 'invalid-feedback')
        r = self.client.post(reverse('payroll:config_detail', args=[self.gv.pk]), {'base_salary': '1000', 'effective_from': '2026-01-01'})
        self.assertContains(r, 'Ngày áp dụng phải sau ngày áp dụng của cấu hình hiện tại.')

    def test_uc7_1_danh_sach_nhan_su_va_phan_quyen_chi_ke_toan(self):
        moi = hoat_dong('chua@icls.vn')
        self.dang_nhap(self.kt)
        r = self.client.get(reverse('payroll:config_list'))
        self.assertContains(r, 'Chưa có cấu hình lương')
        self.assertEqual({d['nhan_su'].pk for d in r.context['dong'] if d['cau_hinh'] is None}, {moi.pk})
        for nguoi in (self.ql, self.gv, self.pt):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('payroll:config_list')).status_code, 403)
            self.assertEqual(self.client.get(reverse('payroll:config_detail', args=[self.gv.pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse('payroll:config_detail', args=[self.gv.pk]), {'effective_from': '2027-01-01'}).status_code, 403)
        self.dang_nhap(self.sa)
        self.assertEqual(self.client.get(reverse('payroll:config_list')).status_code, 403)


# ---------------------------------------------------------------------------------- UC 7.2
class Uc72Test(NenTangLuong):
    def test_uc7_2_basic_khoi_tao_tinh_dung_tung_nhan_su(self):
        self.du_lieu_thang_10()
        cac_bang = self.lap()
        self.assertEqual(len(cac_bang), 5)
        self.assertEqual({b.status for b in cac_bang}, {'DRAFT'})
        self.assertEqual({b.created_by for b in cac_bang}, {self.kt.user})
        # gv: 22 công → 12.000.000 × 22 / 26 = 10.153.846,15 → 10.153.846 ; 1 lớp × 500.000 ; phụ cấp trách nhiệm 0 nên bỏ qua
        g = self.bang(self.gv)
        dong = self.dong(g)
        self.assertEqual(set(dong), {Nhom.WORKDAY_SALARY, Nhom.CLASS_ALLOWANCE})
        self.assertEqual((dong[Nhom.WORKDAY_SALARY].amount, dong[Nhom.CLASS_ALLOWANCE].amount), (D(10_153_846), D(500_000)))
        self.assertIn('22/26 ngày', dong[Nhom.WORKDAY_SALARY].description)
        self.assertEqual((g.gross_pay, g.total_deduction, g.total_tax, g.net_pay), (D(10_653_846), D(0), D(0), D(10_653_846)))
        # ql: đủ 26 công → 20.000.000 + phụ cấp trách nhiệm 2.000.000 = 22.000.000; thuế TNCN tự tính:
        # (22.000.000 − giảm trừ 15.500.000) = 6.500.000 × 5% = 325.000 → thực nhận 21.675.000
        q = self.bang(self.ql)
        self.assertEqual((q.gross_pay, q.total_tax, q.net_pay), (D(22_000_000), D(325_000), D(21_675_000)))
        self.assertEqual(set(self.dong(q)), {Nhom.WORKDAY_SALARY, Nhom.RESPONSIBILITY_ALLOWANCE, Nhom.PERSONAL_INCOME_TAX})
        # pt: 8 giờ × 35.000 = 280.000 ; tg: 18:10–20:00 = 1h50 = 1,83 giờ × 40.000 = 73.200
        self.assertEqual(self.bang(self.pt).gross_pay, D(280_000))
        self.assertEqual(self.dong(self.bang(self.pt))[Nhom.PART_TIME_HOURLY_PAY].category, Nhom.PART_TIME_HOURLY_PAY)
        self.assertEqual(self.bang(self.tg).gross_pay, D(73_200))
        # kt: không có chấm công → mọi dòng 0 đồng bị bỏ
        k = self.bang(self.kt)
        self.assertEqual((k.details.count(), k.gross_pay, k.net_pay), (0, D(0), D(0)))
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='payrolls').exists())

    def test_so_lop_theo_thang(self):
        from schedule.services import dem_lop_tinh_phu_cap
        self.du_lieu_thang_10()
        self.assertEqual(dem_lop_tinh_phu_cap(self.gv, 10, 2026), 1)       # A có buổi; B hủy hết; C hết hạn phân công 30/9
        self.assertEqual(dem_lop_tinh_phu_cap(self.gv, 9, 2026), 0)        # tháng 9 không có buổi nào (các buổi mẫu nằm ở 10/2026)
        TeachingSession.objects.create(study_class=StudyClass.objects.get(class_name='C'), session_date=date(2026, 9, 15), planned_start=time(18),
                                       planned_end=time(20), planned_teacher=self.gv, actual_teacher=self.gv)
        self.assertEqual(dem_lop_tinh_phu_cap(self.gv, 9, 2026), 1)        # lớp C còn phân công trong tháng 9 và có buổi dạy

    def test_cong_thuc_tinh_don_gian_khong_cham_cong(self):
        self.lap()
        for nv in (self.gv, self.ql, self.pt):
            self.assertEqual(self.bang(nv).gross_pay, self.bang(nv).net_pay)
        self.assertEqual(self.bang(self.ql).gross_pay, D(2_000_000))      # chỉ còn phụ cấp trách nhiệm (0 ngày công), dưới mức giảm trừ nên không thuế

    def test_uc7_2_pham_vi_nhan_su_va_cau_hinh_theo_ngay_thanh_ly(self):
        da_nghi = hoat_dong('nghi@icls.vn', UserRole.EMPLOYEE, Position.STAFF, PT)
        da_nghi.status = EmployeeStatus.RESIGNED
        da_nghi.save()
        Contract.objects.create(employee=da_nghi, contract_number='HD1', employment_type=PT, start_date=date(2026, 1, 1),
                                status='TERMINATED', termination_date=date(2026, 10, 15), file_url='x.pdf')
        # Cấu hình đổi giữa tháng: 30.000 đến 14/10, 33.000 từ 15/10 (đóng đúng ngày thanh lý như dong_cau_hinh_luong)
        self.cau_hinh(da_nghi, date(2026, 1, 1), date(2026, 10, 14), hourly_rate=30_000)
        self.cau_hinh(da_nghi, date(2026, 10, 15), date(2026, 10, 15), hourly_rate=33_000)
        nghi_cu = hoat_dong('nghicu@icls.vn')                                   # thanh lý tháng 9: không thuộc tháng 10
        nghi_cu.status = EmployeeStatus.TERMINATED
        nghi_cu.save()
        Contract.objects.create(employee=nghi_cu, contract_number='HD2', employment_type=PT, start_date=date(2026, 1, 1),
                                status='TERMINATED', termination_date=date(2026, 9, 30), file_url='y.pdf')
        onboarding = hoat_dong('ob@icls.vn')
        onboarding.status = EmployeeStatus.ONBOARDING
        onboarding.save()
        moi_vao = hoat_dong('moi@icls.vn')                                      # vào làm sau tháng 10
        moi_vao.join_date = date(2026, 11, 5)
        moi_vao.save()
        phamvi = {nv.pk: ngay for nv, ngay in services.pham_vi_tinh_luong(10, 2026)}
        self.assertEqual(phamvi[da_nghi.pk], date(2026, 10, 15))                 # cấu hình dùng ngày thanh lý
        self.assertEqual(phamvi[self.gv.pk], date(2026, 10, 31))                 # còn lại dùng ngày cuối tháng
        for nv in (nghi_cu, onboarding, moi_vao):
            self.assertNotIn(nv.pk, phamvi)
        self.lap()
        self.assertEqual(self.dong(self.bang(da_nghi)), {})                       # chưa có giờ công nên không dòng nào
        self.assertFalse(Payroll.objects.filter(employee__in=[nghi_cu, onboarding, moi_vao]).exists())

    def test_cau_hinh_dung_theo_ngay_thanh_ly(self):
        da_nghi = hoat_dong('nghi@icls.vn', UserRole.EMPLOYEE, Position.STAFF, PT)
        da_nghi.status = EmployeeStatus.RESIGNED
        da_nghi.save()
        Contract.objects.create(employee=da_nghi, contract_number='HD1', employment_type=PT, start_date=date(2026, 1, 1),
                                status='TERMINATED', termination_date=date(2026, 10, 15), file_url='x.pdf')
        self.cau_hinh(da_nghi, date(2026, 1, 1), date(2026, 10, 14), hourly_rate=30_000)
        self.cau_hinh(da_nghi, date(2026, 10, 15), date(2026, 10, 15), hourly_rate=33_000)
        d = date(2026, 10, 2)
        self.di_lam(da_nghi, d, time(8), time(12), datetime.combine(d, time(8)), datetime.combine(d, time(12)))
        self.lap()
        self.assertEqual(self.bang(da_nghi).gross_pay, D(132_000))                # 4 giờ × 33.000 (cấu hình hiệu lực ngày thanh lý)

    def test_uc7_2_exc_3_4_thang_chua_ket_thuc(self):
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.lap(hom_nay=date(2026, 10, 31))                                # còn đang trong tháng
        self.assertEqual(str(ctx.exception), 'Chỉ lập bảng lương cho tháng đã kết thúc.')
        with self.assertRaises(LoiNghiepVu):
            self.lap(11, 2026, hom_nay=HOM_NAY)                                 # tháng hiện tại
        self.assertEqual(Payroll.objects.count(), 0)
        self.assertEqual(len(self.lap(hom_nay=date(2026, 11, 1))), 5)           # sang ngày 1/11 là lập được

    def test_uc7_2_exc_3_1_bang_luong_da_ton_tai(self):
        self.lap()
        with self.assertRaises(services.BangLuongDaTonTai) as ctx:
            self.lap()
        self.assertEqual(str(ctx.exception), 'Bảng lương tháng này đã tồn tại.')
        self.assertEqual(Payroll.objects.count(), 5)                           # không tạo thêm

    def test_uc7_2_exc_3_2_con_giai_trinh_cho_duyet(self):
        for i in (1, 2):
            self.di_lam(self.gv, date(2026, 10, i), trang_thai='LATE', explanation_status='PENDING', explanation_reason='x')
        self.di_lam(self.gv, date(2026, 11, 3), trang_thai='LATE', explanation_status='PENDING', explanation_reason='x')   # tháng khác: không tính
        self.di_lam(self.gv, date(2026, 10, 5), trang_thai='LATE', explanation_status='APPROVED', explanation_reason='x')
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.lap()
        self.assertEqual(str(ctx.exception), 'Còn 2 giải trình chấm công chờ duyệt trong tháng. Vui lòng xử lý trước khi lập bảng lương.')
        self.assertEqual(Payroll.objects.count(), 0)

    def test_uc7_2_exc_3_3_nhan_su_chua_co_cau_hinh(self):
        for ten in ('a@icls.vn', 'b@icls.vn'):
            hoat_dong(ten)
        with self.assertRaises(LoiNghiepVu) as ctx:
            self.lap()
        self.assertEqual(str(ctx.exception), 'Các nhân sự sau chưa có cấu hình lương: a@icls.vn, b@icls.vn.')
        self.assertEqual(Payroll.objects.count(), 0)                           # dừng lại, không tạo bảng lương nào

    def test_uc7_2_alt_8_1_tinh_lai_giu_dong_thu_cong_va_them_nhan_su_moi(self):
        self.du_lieu_thang_10()
        self.lap()
        g = self.bang(self.gv)
        thuong = services.them_khoan_thu_cong(self.kt.user, g, Nhom.BONUS, '', 'Thưởng giảng dạy xuất sắc', D(1_000_000))
        # dữ liệu đổi trong lúc bảng lương còn DRAFT: giải trình được chấp thuận thêm 1 ngày công (ngày 30/10) cho gv
        self.di_lam(self.gv, date(2026, 10, 30), trang_thai='ON_TIME')
        moi = hoat_dong('moi@icls.vn')
        self.cau_hinh(moi, hourly_rate=35_000)
        so = services.tinh_lai_bang_luong(self.kt.user, 10, 2026)
        self.assertEqual(so, 6)                                                  # 5 cũ + 1 nhân sự mới
        g.refresh_from_db()
        dong = self.dong(g)
        # 23 công → 12.000.000 × 23 / 26 = 10.615.384,6… → 10.615.385 (làm tròn lên); dòng thưởng thủ công vẫn còn
        self.assertEqual(dong[Nhom.WORKDAY_SALARY].amount, D(10_615_385))
        self.assertTrue(PayrollDetail.objects.filter(pk=thuong.pk).exists())
        self.assertEqual(g.details.filter(category=Nhom.WORKDAY_SALARY).count(), 1)         # không nhân đôi dòng tự động
        self.assertEqual((g.gross_pay, g.net_pay), (D(10_615_385 + 500_000 + 1_000_000), D(10_615_385 + 500_000 + 1_000_000)))
        self.assertTrue(Payroll.objects.filter(employee=moi, period_month=10).exists())
        self.assertEqual(Payroll.objects.filter(period_month=10, period_year=2026).count(), 6)

    def test_tinh_lai_chua_co_bang_luong_hoac_da_chot_bi_chan(self):
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHUA_CO_BANG_LUONG):
            services.tinh_lai_bang_luong(self.kt.user, 10, 2026)
        self.lap()
        services.chot_bang_luong(self.kt.user, 10, 2026)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.BANG_LUONG_DA_CHOT_KHONG_TINH_LAI):
            services.tinh_lai_bang_luong(self.kt.user, 10, 2026)

    def test_uc7_2_basic_them_khoan_thu_cong_tinh_lai_tong(self):
        self.du_lieu_thang_10()
        self.lap()
        g = self.bang(self.gv)                                                   # gross 10.653.846
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.BONUS, '', '', D(1_000_000))                   # EARNING
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.ADJUSTMENT_INCREASE, '', 'Bù lương tháng trước', D(100_000))   # EARNING
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.ADJUSTMENT_DECREASE, '', 'Trừ tạm ứng', D(200_000))           # DEDUCTION
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.PERSONAL_INCOME_TAX, '', '', D(300_000))                      # TAX
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.OTHER, Loai.DEDUCTION, 'Phạt', D(50_000))                      # chọn trừ
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.OTHER, Loai.EARNING, 'Khác', D(25_000))                        # chọn cộng
        g.refresh_from_db()
        self.assertEqual(g.gross_pay, D(10_653_846 + 1_000_000 + 100_000 + 25_000))       # 11.778.846
        self.assertEqual((g.total_deduction, g.total_tax), (D(250_000), D(300_000)))
        self.assertEqual(g.net_pay, D(11_778_846 - 250_000 - 300_000))                    # 11.228.846
        loai = {d.category + d.description: d.detail_type for d in g.details.filter(category__in=[Nhom.OTHER, Nhom.BONUS])}
        self.assertEqual(loai[Nhom.BONUS + 'Thưởng'], Loai.EARNING)                       # mô tả trống lấy tên nhóm
        self.assertEqual(loai[Nhom.OTHER + 'Phạt'], Loai.DEDUCTION)
        self.assertTrue(all(d.amount > 0 for d in g.details.all()))                       # số tiền luôn dương

    def test_them_khoan_thu_cong_khong_hop_le(self):
        self.lap()
        g = self.bang(self.gv)
        for so_tien in (D(0), D(-5), None):
            with self.assertRaises(services.LoiTruongNhap) as ctx:
                services.them_khoan_thu_cong(self.kt.user, g, Nhom.BONUS, '', '', so_tien)
            self.assertEqual((str(ctx.exception), ctx.exception.truong), (thong_bao.SO_TIEN_PHAI_DUONG, 'amount'))
        with self.assertRaises(services.LoiTruongNhap) as ctx:                             # OTHER phải chọn cộng hay trừ
            services.them_khoan_thu_cong(self.kt.user, g, Nhom.OTHER, '', 'x', D(1000))
        self.assertEqual(str(ctx.exception), thong_bao.CHON_KHOAN_CONG_HAY_TRU)
        with self.assertRaises(services.LoiTruongNhap):                                    # nhóm tự động không nhập tay
            services.them_khoan_thu_cong(self.kt.user, g, Nhom.WORKDAY_SALARY, '', 'x', D(1000))
        services.chot_bang_luong(self.kt.user, 10, 2026)
        g.refresh_from_db()
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.BANG_LUONG_KHONG_SUA_DUOC):
            services.them_khoan_thu_cong(self.kt.user, g, Nhom.BONUS, '', '', D(1000))

    def test_uc7_2_alt_8_2_xoa_khoan_thu_cong(self):
        self.du_lieu_thang_10()
        self.lap()
        g = self.bang(self.gv)
        khoan = services.them_khoan_thu_cong(self.kt.user, g, Nhom.ADJUSTMENT_DECREASE, '', 'x', D(200_000))
        g.refresh_from_db()
        self.assertEqual(g.net_pay, D(10_653_846 - 200_000))
        services.xoa_khoan_thu_cong(self.kt.user, khoan)
        g.refresh_from_db()
        self.assertEqual((g.total_deduction, g.net_pay), (D(0), D(10_653_846)))
        tu_dong = g.details.get(category=Nhom.WORKDAY_SALARY)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_XOA_KHOAN_THU_CONG):         # dòng hệ thống tính không xóa tay
            services.xoa_khoan_thu_cong(self.kt.user, tu_dong)
        services.chot_bang_luong(self.kt.user, 10, 2026)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.BANG_LUONG_KHONG_SUA_DUOC):
            services.xoa_khoan_thu_cong(self.kt.user, PayrollDetail.objects.get(pk=tu_dong.pk))

    def test_uc7_2_basic_chot_bang_luong(self):
        self.du_lieu_thang_10()
        self.lap()
        bay_gio = datetime(2026, 11, 3, 9, 0)
        self.assertEqual(services.trang_thai_thang(10, 2026), PayrollStatus.DRAFT)
        self.assertFalse(services.thang_da_chot(10, 2026))
        so = services.chot_bang_luong(self.kt.user, 10, 2026, bay_gio)
        self.assertEqual(so, 5)
        self.assertEqual(set(Payroll.objects.values_list('status', flat=True)), {'LOCKED'})
        self.assertEqual(set(Payroll.objects.values_list('locked_at', flat=True)), {bay_gio})
        self.assertEqual(services.trang_thai_thang(10, 2026), PayrollStatus.LOCKED)
        self.assertTrue(services.thang_da_chot(10, 2026))
        self.assertTrue(ActivityLog.objects.filter(action='LOCK', model_name='payrolls').exists())
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.BANG_LUONG_DA_CHOT_ROI):
            services.chot_bang_luong(self.kt.user, 10, 2026)

    def test_uc7_2_exc_10_1_thuc_nhan_am_khong_chot(self):
        self.lap()
        k = self.bang(self.kt)                                                    # kt: thu nhập 0, nên trừ 100.000 sẽ âm
        services.them_khoan_thu_cong(self.kt.user, k, Nhom.ADJUSTMENT_DECREASE, '', 'x', D(100_000))
        k.refresh_from_db()
        self.assertEqual(k.net_pay, D(-100_000))
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.chot_bang_luong(self.kt.user, 10, 2026)
        self.assertEqual(str(ctx.exception), 'Thực nhận của kt@icls.vn đang âm, vui lòng kiểm tra các khoản khấu trừ.')
        self.assertEqual(set(Payroll.objects.values_list('status', flat=True)), {'DRAFT'})   # không chốt bất kỳ bảng nào
        services.xoa_khoan_thu_cong(self.kt.user, k.details.get())
        self.assertEqual(services.chot_bang_luong(self.kt.user, 10, 2026), 5)

    def test_sau_khi_chot_khoa_cham_cong_giai_trinh_nghi_phep_va_cau_hinh(self):
        """Hậu điều kiện UC 7.2: tháng đã chốt thì giải trình, đơn nghỉ, cấu hình lương thuộc tháng đó không đổi được."""
        loi = self.di_lam(self.gv, date(2026, 10, 3), trang_thai='LATE', late_minutes=30)
        self.lap()
        services.chot_bang_luong(self.kt.user, 10, 2026)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.BANG_LUONG_DA_CHOT):
            gui_giai_trinh(self.gv, loi, 'lý do')
        with self.assertRaisesMessage(LoiNghiepVu, 'đã chốt lương'):
            gui_don_nghi(self.gv, 'SICK', 'FULL_DAY', date(2026, 10, 20), date(2026, 10, 20), 'x')
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CAU_HINH_THANG_DA_CHOT):
            services.luu_cau_hinh_luong(self.kt.user, self.gv, D(15_000_000), D(0), D(0), D(0), date(2026, 10, 20))
        gui_don_nghi(self.gv, 'SICK', 'FULL_DAY', date(2026, 11, 10), date(2026, 11, 10), 'x')   # tháng 11 chưa chốt: bình thường

    def test_uc7_2_basic_phat_hanh_phieu_luong(self):
        self.lap()
        with self.assertRaises(LoiNghiepVu) as ctx:
            services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)                  # chưa chốt thì chưa phát hành
        self.assertEqual(str(ctx.exception), thong_bao.PHAI_CHOT_TRUOC_KHI_PHAT_HANH)
        services.chot_bang_luong(self.kt.user, 10, 2026)
        bay_gio = datetime(2026, 11, 4, 8, 0)
        self.assertEqual(services.phat_hanh_phieu_luong(self.kt.user, 10, 2026, bay_gio), 5)
        self.assertEqual(set(Payroll.objects.values_list('status', flat=True)), {'SENT'})
        self.assertEqual(set(Payroll.objects.values_list('sent_at', flat=True)), {bay_gio})
        self.assertEqual(services.trang_thai_thang(10, 2026), PayrollStatus.SENT)
        nguoi_nhan = set(Notification.objects.filter(title=thong_bao.TB_PHIEU_LUONG_TIEU_DE).values_list('recipient_id', flat=True))
        self.assertEqual(nguoi_nhan, {nv.user_id for nv in (self.kt, self.ql, self.gv, self.pt, self.tg)})
        self.assertEqual(Notification.objects.filter(recipient=self.gv.user).get().message, 'Phiếu lương tháng 10/2026 đã được phát hành.')
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.DA_PHAT_HANH_ROI):
            services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHUA_CO_BANG_LUONG):
            services.phat_hanh_phieu_luong(self.kt.user, 9, 2026)

    def test_danh_sach_thang_va_tong_ket(self):
        self.du_lieu_thang_10()
        self.lap()
        ds = services.danh_sach_thang()
        self.assertEqual((ds[0]['thang'], ds[0]['nam'], ds[0]['so_nhan_su'], ds[0]['trang_thai']), (10, 2026, 5, 'DRAFT'))
        tong = services.tong_ket_thang(10, 2026)
        self.assertEqual(tong['thuc_nhan'], D(10_653_846 + 21_675_000 + 280_000 + 73_200))
        self.assertEqual(tong['thue'], D(325_000))
        self.assertEqual(tong['dem'], {'DRAFT': 5, 'LOCKED': 0, 'SENT': 0})
        self.assertEqual([b.employee for b in services.tong_ket_thang(10, 2026, tu_khoa='pt')['cac_bang']], [self.pt])

    def test_uc7_2_qua_man_hinh_toan_bo_quy_trinh(self):
        self.du_lieu_thang_10()
        self.dang_nhap(self.kt)
        r = self.client.get(reverse('payroll:period_list'))
        self.assertContains(r, 'Khởi tạo bảng lương')
        with mock.patch('payroll.views.date', type('Fake', (date,), {'today': classmethod(lambda cls: HOM_NAY)})):
            with mock.patch('payroll.services.date', type('Fake', (date,), {'today': classmethod(lambda cls: HOM_NAY)})):
                r = self.client.post(reverse('payroll:period_create'), {'thang': '2026-10'}, follow=True)
        self.assertContains(r, 'Đã khởi tạo bảng lương cho 5 nhân sự.')
        self.assertContains(r, 'Bảng lương tháng 10/2026')
        self.assertContains(r, 'Chốt bảng lương')
        g = self.bang(self.gv)
        r = self.client.get(reverse('payroll:payroll_detail', args=[g.pk]))
        self.assertContains(r, 'Thêm khoản thủ công')
        self.assertContains(r, '10.153.846 đ')
        r = self.client.post(reverse('payroll:detail_add', args=[g.pk]), {'category': 'BONUS', 'amount': '1000000', 'description': 'Thưởng'}, follow=True)
        self.assertContains(r, 'Đã thêm khoản vào bảng lương.')
        khoan = g.details.get(category='BONUS')
        r = self.client.post(reverse('payroll:detail_delete', args=[khoan.pk]), follow=True)
        self.assertContains(r, 'Đã xóa khoản khỏi bảng lương.')
        r = self.client.post(reverse('payroll:period_recalc', args=[2026, 10]), follow=True)
        self.assertContains(r, 'Đã tính lại bảng lương (5 nhân sự).')
        r = self.client.post(reverse('payroll:period_send', args=[2026, 10]), follow=True)            # chưa chốt
        self.assertContains(r, 'Vui lòng chốt bảng lương trước khi phát hành phiếu lương.')
        r = self.client.post(reverse('payroll:period_lock', args=[2026, 10]), follow=True)
        self.assertContains(r, 'Đã chốt bảng lương (5 nhân sự).')
        self.assertContains(r, 'Phát hành phiếu lương')
        r = self.client.post(reverse('payroll:period_send', args=[2026, 10]), follow=True)
        self.assertContains(r, 'Đã phát hành 5 phiếu lương.')
        self.assertEqual(services.trang_thai_thang(10, 2026), 'SENT')

    def test_uc7_2_exc_3_1_qua_man_hinh_mo_bang_luong_hien_co(self):
        self.lap()
        self.dang_nhap(self.kt)
        with mock.patch('payroll.services.date', type('Fake', (date,), {'today': classmethod(lambda cls: HOM_NAY)})):
            r = self.client.post(reverse('payroll:period_create'), {'thang': '2026-10'}, follow=True)
        self.assertContains(r, 'Bảng lương tháng này đã tồn tại.')
        self.assertRedirects(r, reverse('payroll:period', args=[2026, 10]))

    def test_uc7_2_exc_3_4_qua_man_hinh(self):
        self.dang_nhap(self.kt)
        homnay = date.today()
        r = self.client.post(reverse('payroll:period_create'), {'thang': f'{homnay.year}-{homnay.month:02d}'}, follow=True)
        self.assertContains(r, 'Chỉ lập bảng lương cho tháng đã kết thúc.')

    def test_uc7_2_phan_quyen_chi_ke_toan(self):
        self.lap()
        g = self.bang(self.gv)
        urls = [('get', reverse('payroll:period_list')), ('get', reverse('payroll:period', args=[2026, 10])),
                ('get', reverse('payroll:payroll_detail', args=[g.pk])), ('post', reverse('payroll:period_create')),
                ('post', reverse('payroll:period_recalc', args=[2026, 10])), ('post', reverse('payroll:period_lock', args=[2026, 10])),
                ('post', reverse('payroll:period_send', args=[2026, 10])), ('post', reverse('payroll:detail_add', args=[g.pk]))]
        for nguoi in (self.ql, self.gv, self.pt):
            self.dang_nhap(nguoi)
            for cach, url in urls:
                self.assertEqual(getattr(self.client, cach)(url).status_code, 403, (nguoi, url))
        self.dang_nhap(self.sa)
        self.assertEqual(self.client.get(reverse('payroll:period_list')).status_code, 403)
        self.dang_nhap(self.kt)
        for cach, url in urls[:3]:
            self.assertEqual(getattr(self.client, cach)(url).status_code, 200, url)
        self.assertEqual(self.client.get(reverse('payroll:period_create')).status_code, 405)     # chỉ nhận POST
        self.assertEqual(self.client.get(reverse('payroll:period', args=[2026, 13])).status_code, 302)   # tháng 13: về danh sách


# ---------------------------------------------------------------------------------- Thuế TNCN tự tính
class ThueTncnTest(NenTangLuong):
    def test_thue_full_time_luy_tien_theo_bac(self):
        for thu_nhap, thue in ((0, 0), (15_500_000, 0), (16_500_000, 50_000),       # chỉ phần vượt giảm trừ mới chịu thuế
                               (22_000_000, 325_000),                                # 6,5 triệu × 5%
                               (30_000_000, 950_000),                                # 10 triệu × 5% + 4,5 triệu × 10%
                               (45_500_000, 2_500_000),                              # 10 triệu × 5% + 20 triệu × 10%
                               (80_000_000, 9_850_000)):                             # + 30 triệu × 20% + 4,5 triệu × 30%
            self.assertEqual(services.tinh_thue_tncn(thu_nhap, True), D(thue), thu_nhap)

    def test_thue_part_time_khau_tru_co_dinh_tu_nguong(self):
        self.assertEqual(services.tinh_thue_tncn(1_999_999, False), D(0))
        self.assertEqual(services.tinh_thue_tncn(2_000_000, False), D(200_000))      # từ ngưỡng thì trừ 10% trên TOÀN BỘ thu nhập
        self.assertEqual(services.tinh_thue_tncn(5_000_000, False), D(500_000))

    def test_bang_luong_co_dong_thue_tu_tinh_va_thuc_nhan_da_tru_thue(self):
        self.du_lieu_thang_10()
        self.lap()
        q = self.bang(self.ql)
        thue = q.details.get(category=Nhom.PERSONAL_INCOME_TAX)
        self.assertEqual((thue.detail_type, thue.amount), (Loai.TAX, D(325_000)))
        self.assertTrue(thue.description.startswith('Thuế TNCN (tự tính)'))
        self.assertEqual(q.net_pay, q.gross_pay - q.total_deduction - q.total_tax)
        self.assertFalse(self.bang(self.gv).details.filter(category=Nhom.PERSONAL_INCOME_TAX).exists())   # dưới mức giảm trừ: không có dòng thuế

    def test_part_time_du_nguong_bi_khau_tru(self):
        SalaryConfig.objects.filter(employee=self.pt).update(hourly_rate=100_000)
        for ngay in self.ngay_lam(3):                                                 # 3 ngày × 9 giờ = 27 giờ × 100.000 = 2.700.000
            self.di_lam(self.pt, ngay, time(8), time(17), datetime.combine(ngay, time(8)), datetime.combine(ngay, time(17)))
        self.lap()
        p = self.bang(self.pt)
        self.assertEqual((p.gross_pay, p.total_tax, p.net_pay), (D(2_700_000), D(270_000), D(2_430_000)))

    def test_thue_tu_cap_nhat_khi_them_xoa_khoan_va_giu_dong_thue_nhap_tay(self):
        self.du_lieu_thang_10()
        self.lap()
        q = self.bang(self.ql)                                                         # gross 22.000.000, thuế 325.000
        thuong = services.them_khoan_thu_cong(self.kt.user, q, Nhom.BONUS, '', '', D(8_000_000))
        q.refresh_from_db()
        self.assertEqual((q.gross_pay, q.total_tax), (D(30_000_000), D(950_000)))      # thưởng làm tăng thuế
        self.assertEqual(q.details.filter(category=Nhom.PERSONAL_INCOME_TAX).count(), 1)   # chỉ MỘT dòng thuế tự tính, không nhân đôi
        services.xoa_khoan_thu_cong(self.kt.user, thuong)
        q.refresh_from_db()
        self.assertEqual((q.gross_pay, q.total_tax), (D(22_000_000), D(325_000)))      # xóa thưởng: thuế về lại
        # Kế toán nhập thêm một khoản thuế tay (ví dụ truy thu): cộng vào total_tax, và còn nguyên sau khi tính lại
        tay = services.them_khoan_thu_cong(self.kt.user, q, Nhom.PERSONAL_INCOME_TAX, '', 'Truy thu tháng trước', D(100_000))
        q.refresh_from_db()
        self.assertEqual((q.total_tax, q.net_pay), (D(425_000), D(22_000_000 - 425_000)))
        services.tinh_lai_bang_luong(self.kt.user, 10, 2026)
        q.refresh_from_db()
        self.assertTrue(PayrollDetail.objects.filter(pk=tay.pk).exists())
        self.assertEqual((q.total_tax, q.details.filter(category=Nhom.PERSONAL_INCOME_TAX).count()), (D(425_000), 2))

    def test_khong_xoa_tay_duoc_dong_thue_tu_tinh_nhung_xoa_duoc_thue_nhap_tay(self):
        self.du_lieu_thang_10()
        self.lap()
        q = self.bang(self.ql)
        tu_tinh = q.details.get(category=Nhom.PERSONAL_INCOME_TAX)
        self.assertTrue(services.la_dong_tu_dong(tu_tinh))
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.CHI_XOA_KHOAN_THU_CONG):
            services.xoa_khoan_thu_cong(self.kt.user, tu_tinh)
        tay = services.them_khoan_thu_cong(self.kt.user, q, Nhom.PERSONAL_INCOME_TAX, '', 'Thuế nhập tay', D(1_000))
        self.assertFalse(services.la_dong_tu_dong(tay))
        services.xoa_khoan_thu_cong(self.kt.user, tay)

    def test_man_hinh_chi_tiet_va_phieu_luong_hien_thue(self):
        self.du_lieu_thang_10()
        self.lap()
        q = self.bang(self.ql)
        self.dang_nhap(self.kt)
        r = self.client.get(reverse('payroll:payroll_detail', args=[q.pk]))
        self.assertContains(r, 'Thuế TNCN (tự tính)')
        self.assertContains(r, '325.000 đ')
        self.assertContains(r, '(tự động)')
        services.chot_bang_luong(self.kt.user, 10, 2026)
        services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)
        self.dang_nhap(self.ql)
        r = self.client.get(reverse('payroll:payslip', args=[q.pk]))
        self.assertContains(r, '−325.000 đ')
        self.assertContains(r, '21.675.000 đ')                                          # thực nhận đã trừ thuế

    def test_tham_so_thue_doi_duoc_trong_settings(self):
        from django.test import override_settings
        with override_settings(THUE_GIAM_TRU_BAN_THAN=20_000_000):
            self.assertEqual(services.tinh_thue_tncn(22_000_000, True), D(100_000))     # (22 − 20) triệu × 5%


# ---------------------------------------------------------------------------------- UC 7.3
class Uc73Test(NenTangLuong):
    def phat_hanh(self, thang=10):
        self.lap(thang)
        services.chot_bang_luong(self.kt.user, thang, 2026)
        services.phat_hanh_phieu_luong(self.kt.user, thang, 2026)

    def test_uc7_3_basic_xem_phieu_da_phat_hanh(self):
        self.du_lieu_thang_10()
        self.phat_hanh()
        g = self.bang(self.gv)
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:my_payslips'))
        self.assertEqual(r.context['bang'], g)
        for chu in ('Lương ngày công', 'Phụ cấp lớp', 'THU NHẬP', 'KHẤU TRỪ', 'THUẾ', 'Thực nhận', '10.653.846 đ', 'gv@icls.vn', 'In / Lưu PDF'):
            self.assertContains(r, chu)
        self.assertContains(self.client.get(reverse('payroll:payslip', args=[g.pk])), 'Phiếu lương tháng 10/2026')

    def test_phieu_luong_chia_thu_nhap_khau_tru_thue(self):
        self.lap()
        g = self.bang(self.gv)
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.BONUS, '', '', D(1_000_000))
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.ADJUSTMENT_DECREASE, '', '', D(200_000))
        services.them_khoan_thu_cong(self.kt.user, g, Nhom.PERSONAL_INCOME_TAX, '', '', D(300_000))
        ct = services.chi_tiet_phieu(g)
        self.assertEqual([d.category for d in ct['thu_nhap']], [Nhom.BONUS, ])
        self.assertEqual([d.category for d in ct['khau_tru']], [Nhom.ADJUSTMENT_DECREASE])
        self.assertEqual([d.category for d in ct['thue']], [Nhom.PERSONAL_INCOME_TAX])
        services.chot_bang_luong(self.kt.user, 10, 2026)
        services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:payslip', args=[g.pk]))
        self.assertContains(r, '+1.000.000 đ')
        self.assertContains(r, '−200.000 đ')
        self.assertContains(r, '−300.000 đ')
        self.assertContains(r, 'Thực nhận')

    def test_uc7_3_exc_1_1_chua_phat_hanh_thi_khong_thay_gi(self):
        self.lap()                                                                # DRAFT
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:my_payslips'))
        self.assertContains(r, 'Chưa có phiếu lương nào được phát hành.')
        self.assertIsNone(r.context['bang'])
        services.chot_bang_luong(self.kt.user, 10, 2026)                          # LOCKED vẫn chưa hiện
        self.assertContains(self.client.get(reverse('payroll:my_payslips')), 'Chưa có phiếu lương nào được phát hành.')
        services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)
        self.assertNotContains(self.client.get(reverse('payroll:my_payslips')), 'Chưa có phiếu lương nào được phát hành.')

    def test_uc7_3_exc_3_1_khong_xem_phieu_nguoi_khac_hoac_chua_phat_hanh(self):
        self.lap()
        phieu_cua_gv, phieu_cua_pt = self.bang(self.gv), self.bang(self.pt)
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:payslip', args=[phieu_cua_gv.pk]))      # phiếu của mình nhưng chưa phát hành
        self.assertContains(r, 'Bạn không có quyền xem phiếu lương này.', status_code=403)
        services.chot_bang_luong(self.kt.user, 10, 2026)
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[phieu_cua_gv.pk])).status_code, 403)   # LOCKED cũng không
        services.phat_hanh_phieu_luong(self.kt.user, 10, 2026)
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[phieu_cua_gv.pk])).status_code, 200)
        r = self.client.get(reverse('payroll:payslip', args=[phieu_cua_pt.pk]))     # sửa URL xem phiếu người khác
        self.assertContains(r, 'Bạn không có quyền xem phiếu lương này.', status_code=403)
        self.dang_nhap(self.ql)                                                    # kể cả Quản lý
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[phieu_cua_gv.pk])).status_code, 403)
        self.dang_nhap(self.kt)                                                    # và Kế toán chỉ xem phiếu của chính mình
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[phieu_cua_gv.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[self.bang(self.kt).pk])).status_code, 200)

    def test_danh_sach_cac_thang_chi_cua_chinh_minh_moi_nhat_truoc(self):
        self.phat_hanh(9)
        self.phat_hanh(10)
        self.assertEqual([(b.period_month, b.employee) for b in services.phieu_luong_da_phat_hanh(self.gv)], [(10, self.gv), (9, self.gv)])
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:my_payslips'))
        self.assertEqual(r.context['bang'].period_month, 10)                       # mặc định phiếu mới nhất
        self.assertEqual(len(r.context['cac_thang']), 2)
        phieu_9 = self.bang(self.gv, 9)
        self.assertEqual(self.client.get(reverse('payroll:payslip', args=[phieu_9.pk])).context['bang'], phieu_9)

    def test_uc7_3_phan_quyen_moi_vai_tro_co_ho_so_xem_phieu_cua_minh(self):
        self.phat_hanh()
        for nguoi in (self.ql, self.kt, self.gv, self.pt):
            self.dang_nhap(nguoi)
            self.assertEqual(self.client.get(reverse('payroll:my_payslips')).context['bang'].employee, nguoi)
        self.dang_nhap(self.sa)                                                    # Super Admin không thuộc phân hệ Lương
        self.assertEqual(self.client.get(reverse('payroll:my_payslips')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('payroll:my_payslips')).status_code, 302)

    def test_menu_payroll_da_bat(self):
        self.dang_nhap(self.gv)
        r = self.client.get(reverse('payroll:my_payslips'))
        self.assertTrue(any(m['url'] == reverse('payroll:my_payslips') for m in r.context['menu_chinh']))
