"""Test của app dashboard – tên test bám mã luồng ở §10 (§12.1).

UC 9.1: Dashboard theo vai trò (SA, Quản lý, Kế toán, Nhân viên), luồng 1.1 (nút chạy tác vụ), 1.2 (chưa có số liệu),
        1.3 (chưa có hồ sơ nhân sự).
UC 9.2: tác vụ hằng ngày – luồng chính, luồng 1.1 (chạy lần hai không trùng), luồng 1.2 (một bước lỗi).
Các hàm từng bước (employees.het_han_giay_to, attendance.ghi_nhan_cham_cong_ngay, …) được test riêng trong tests.py
của app sở hữu bảng (§11); ở đây test việc ghép các bước.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from attendance.models import Attendance, AttendanceStatus
from contracts.models import Contract
from core import thong_bao
from core.mau_test import tao_lop, tao_nhan_su_hoat_dong as hoat_dong
from core.models import ActivityLog, Notification
from dashboard import services
from employees.models import DocumentStatus, EmployeeDocument, EmploymentType, Position, WorkShift
from leave.models import LeaveBalance, LeaveRequest
from payroll.models import Payroll
from schedule.models import StudyClass, SubstituteRequest, TeachingSession

HOM_NAY = date(2026, 10, 27)          # Thứ 3; hôm qua 26/10 là Thứ 2 (ngày làm việc)


class NenTangDashboard(TestCase):
    """Một Super Admin (không có hồ sơ, Q1), một Quản lý, một Kế toán, một giáo viên Full-time, một Part-time."""

    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN, full_name='Super Admin')
        self.ql = hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER, EmploymentType.FULL_TIME, WorkShift.SHIFT_1)
        self.kt = hoat_dong('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT, EmploymentType.FULL_TIME, WorkShift.SHIFT_1)
        self.gv = hoat_dong('gv@icls.vn', UserRole.EMPLOYEE, Position.TEACHER, EmploymentType.FULL_TIME, WorkShift.SHIFT_1)
        self.pt = hoat_dong('pt@icls.vn', UserRole.EMPLOYEE, Position.STAFF, EmploymentType.PART_TIME, '')

    def vao(self, nguoi):
        self.client.force_login(nguoi.user if hasattr(nguoi, 'user') else nguoi)

    def cac_the(self, nguoi, tab=''):
        self.vao(nguoi)
        r = self.client.get(reverse('dashboard:dashboard'), {'tab': tab})
        self.assertEqual(r.status_code, 200)
        return r, {t['nhan']: t for t in r.context.get('cac_the', [])}


# ============================================================ UC 9.1 – Dashboard theo vai trò
class Uc91DashboardTest(NenTangDashboard):
    def test_uc9_1_basic_super_admin_thay_tai_khoan_nhat_ky_va_nut_chay_tac_vu(self):
        for _ in range(3):
            ActivityLog.objects.create(action='LOGIN_FAILED', model_name='User', description='Sai mật khẩu')
        khoa = User.objects.get(email='pt@icls.vn')
        khoa.is_active = False
        khoa.save()
        # Một lần thất bại cách đây 10 ngày: ngoài khung 7 ngày, không được đếm
        cu = ActivityLog.objects.create(action='LOGIN_FAILED', model_name='User')
        ActivityLog.objects.filter(pk=cu.pk).update(created_at=datetime.now() - timedelta(days=10))
        r, the = self.cac_the(self.sa)
        self.assertEqual(r.context['loai'], 'sa')
        self.assertContains(r, 'Chạy tác vụ hằng ngày')
        self.assertEqual(the['Đăng nhập thất bại']['so'], 3)                                  # không tính bản 10 ngày trước
        self.assertLessEqual(len(r.context['nhat_ky']), 10)                                   # tối đa 10 dòng nhật ký
        theo_ten = {d['ten']: d for d in r.context['tai_khoan']}
        self.assertEqual(theo_ten['Nhân viên']['hoat_dong'], 1)                               # gv; pt đã bị khóa
        self.assertEqual(theo_ten['Nhân viên']['bi_khoa'], 1)
        self.assertEqual(theo_ten['Super Admin']['hoat_dong'], 1)
        self.assertEqual(r.context['tong_tai_khoan'], 5)

    def test_uc9_1_basic_super_admin_dem_viec_cua_quan_ly_cho_duyet(self):
        LeaveRequest.objects.create(employee=self.ql, leave_type='ANNUAL', duration_type='FULL_DAY', start_date=HOM_NAY,
                                    end_date=HOM_NAY, total_days=1, reason='Việc riêng')          # đơn của Quản lý → SA duyệt
        LeaveRequest.objects.create(employee=self.gv, leave_type='ANNUAL', duration_type='FULL_DAY', start_date=HOM_NAY,
                                    end_date=HOM_NAY, total_days=1, reason='Của nhân viên')       # không thuộc phạm vi SA
        EmployeeDocument.objects.create(employee=self.ql, document_type='CERTIFICATION', document_name='CC',
                                        file_url='x.pdf')
        Attendance.objects.create(employee=self.ql, work_date=HOM_NAY, planned_start=time(8), planned_end=time(17),
                                  attendance_status=AttendanceStatus.ABSENT, explanation_status='PENDING')
        _, the = self.cac_the(self.sa)
        self.assertEqual(the['Đơn nghỉ của Quản lý']['so'], 1)
        self.assertEqual(the['Giải trình của Quản lý']['so'], 1)
        self.assertEqual(the['Giấy tờ của Quản lý']['so'], 1)
        self.assertEqual(the['Đơn nghỉ của Quản lý']['url'], reverse('leave:review'))        # mỗi thẻ có link tới trang xử lý

    def test_uc9_1_basic_quan_ly_thay_nhan_su_cho_duyet_va_sap_het_han(self):
        EmployeeDocument.objects.create(employee=self.gv, document_type='CERTIFICATION', document_name='TOPIK',
                                        file_url='x.pdf')                                      # PENDING
        EmployeeDocument.objects.create(employee=self.gv, document_type='CERTIFICATION', document_name='CC cũ',
                                        issue_date=date(2025, 1, 1), expiry_date=date.today() + timedelta(days=10),
                                        file_url='x.pdf', status=DocumentStatus.APPROVED)
        Contract.objects.create(employee=self.gv, contract_number='HD1', employment_type='FULL_TIME',
                                start_date=date(2026, 1, 1), end_date=date.today() + timedelta(days=20), file_url='x.pdf')
        LeaveRequest.objects.create(employee=self.gv, leave_type='SICK', duration_type='FULL_DAY', start_date=HOM_NAY,
                                    end_date=HOM_NAY, total_days=1, reason='Ốm')
        lop = tao_lop('Lớp A')
        lop.status = 'ACTIVE'
        lop.save()
        buoi = TeachingSession.objects.create(study_class=lop, session_date=date.today(), planned_start=time(9),
                                              planned_end=time(11), planned_teacher=self.gv, actual_teacher=self.gv)
        SubstituteRequest.objects.create(teaching_session=buoi)
        r, the = self.cac_the(self.ql)
        self.assertEqual(r.context['loai'], 'ql')
        self.assertEqual(the['Tổng nhân sự']['so'], 4)
        self.assertIn('3 toàn thời gian · 1 bán thời gian', the['Tổng nhân sự']['phu'])        # tỉ lệ Full-time / Part-time
        self.assertEqual(r.context['co_cau']['full_time'], 3)
        self.assertEqual(the['Lớp đang hoạt động']['so'], 1)
        self.assertEqual(the['Hợp đồng / giấy tờ sắp hết hạn']['phu'], '1 hợp đồng · 1 giấy tờ')
        cho_xu_ly = {t['nhan']: t['so'] for t in r.context['cho_xu_ly']}
        self.assertEqual(cho_xu_ly, {'Giấy tờ chờ duyệt': 1, 'Đơn nghỉ chờ duyệt': 1, 'Giải trình chờ duyệt': 0,
                                     'Buổi dạy cần người thay': 1})
        self.assertEqual(len(r.context['chu_y']), 2)

    def test_uc9_1_basic_ke_toan_thay_bang_luong_gan_nhat_va_cham_cong_thang(self):
        for nv, thuc_nhan, loai in ((self.gv, Decimal('10000000'), 'FULL_TIME'), (self.pt, Decimal('2000000'), 'PART_TIME')):
            Payroll.objects.create(employee=nv, period_month=9, period_year=2026, gross_pay=thuc_nhan + 500000,
                                   total_tax=Decimal('500000'), net_pay=thuc_nhan, status='SENT')
        Attendance.objects.create(employee=self.gv, work_date=date.today(), planned_start=time(8), planned_end=time(17),
                                  attendance_status=AttendanceStatus.LATE)
        r, _ = self.cac_the(self.kt)
        self.assertEqual(r.context['loai'], 'kt')
        luong = r.context['luong']
        self.assertEqual((luong['thang'], luong['nam'], luong['trang_thai']), (9, 2026, 'SENT'))
        self.assertEqual((luong['gross'], luong['thue'], luong['thuc_nhan']),
                         (Decimal('13000000'), Decimal('1000000'), Decimal('12000000')))
        self.assertEqual(r.context['cham_cong']['LATE'], 1)
        self.assertContains(r, 'Đã phát hành')
        self.assertContains(r, 'Theo dõi quỹ lương trong kỳ')

    def test_uc9_1_basic_nhan_vien_thay_lich_cham_cong_quy_phep_va_thong_bao(self):
        LeaveBalance.objects.create(employee=self.gv, year=HOM_NAY.year, total_days=12, used_days=3)
        Notification.objects.create(recipient=self.gv.user, title='Tin 1', message='Nội dung', notification_type='SYSTEM')
        Notification.objects.create(recipient=self.gv.user, title='Tin đã đọc', message='x', notification_type='SYSTEM',
                                    is_read=True)
        du_lieu = services.du_lieu_dashboard(self.gv.user, HOM_NAY)                           # Thứ 3, Ca 1 (08:00–17:00)
        self.assertEqual(du_lieu['loai'], 'ca_nhan')
        the = {t['nhan']: t for t in du_lieu['cac_the']}
        self.assertEqual(the['Ngày nghỉ còn lại']['so'], '9')
        self.assertEqual(the['Thông báo chưa đọc']['so'], 1)
        self.assertEqual(the['Lịch hôm nay']['so'], 1)
        self.assertEqual([(c['ten'], c['trang_thai']) for c in du_lieu['cham_cong']], [('Ca 1 (08:00–17:00)', 'Chưa check-in')])
        self.assertEqual(len(du_lieu['tuan']), 7)
        self.assertEqual(du_lieu['tuan'][0]['ngay'], date(2026, 10, 26))                      # tuần bắt đầu Thứ 2
        self.vao(self.gv)
        self.assertContains(self.client.get(reverse('dashboard:dashboard')), 'Xin chào, gv@icls.vn')

    def test_uc9_1_nhan_vien_part_time_khong_co_phep_nam(self):
        _, the = self.cac_the(self.pt)
        self.assertEqual(the['Ngày nghỉ còn lại']['so'], 'Không áp dụng')

    def test_uc9_1_nhan_vien_da_check_in_thay_trang_thai_cham_cong(self):
        Attendance.objects.create(employee=self.gv, work_date=HOM_NAY, planned_start=time(8), planned_end=time(17),
                                  check_in=datetime(2026, 10, 27, 8, 0), attendance_status=AttendanceStatus.ON_TIME)
        du_lieu = services.du_lieu_dashboard(self.gv.user, HOM_NAY)
        self.assertEqual(du_lieu['cham_cong'][0]['trang_thai'], 'Đã check-in 08:00')

    def test_uc9_1_tab_cua_vai_tro_va_tab_sai_quay_ve_mac_dinh(self):
        for nguoi, cac_tab in ((self.ql, ['tong_quan', 'ca_nhan']), (self.kt, ['ke_toan', 'ca_nhan']),
                               (self.gv, ['ca_nhan']), (self.sa, ['tong_quan'])):
            du_lieu = services.du_lieu_dashboard(nguoi.user if hasattr(nguoi, 'user') else nguoi, HOM_NAY, tab='sai')
            self.assertEqual([m for m, _ in du_lieu['tabs']], cac_tab)
            self.assertEqual(du_lieu['tab'], cac_tab[0])                                       # tab sai → tab đầu tiên
        du_lieu = services.du_lieu_dashboard(self.ql.user, HOM_NAY, tab='ca_nhan')             # Quản lý có tab Cá nhân
        self.assertEqual(du_lieu['loai'], 'ca_nhan')
        du_lieu = services.du_lieu_dashboard(self.gv.user, HOM_NAY, tab='ke_toan')             # NV không xem được tab Kế toán
        self.assertEqual(du_lieu['loai'], 'ca_nhan')

    def test_uc9_1_alt_1_1_super_admin_bam_nut_chay_tac_vu_hien_ket_qua(self):
        """UC 9.1 – luồng 1.1: nút trên Dashboard của Super Admin chạy UC 9.2 và hiện kết quả từng bước."""
        self.vao(self.sa)
        self.assertContains(self.client.get(reverse('dashboard:dashboard')), reverse('dashboard:run_daily_job'))
        r = self.client.post(reverse('dashboard:run_daily_job'), follow=True)
        self.assertContains(r, 'Đã chạy tác vụ hằng ngày')
        self.assertContains(r, 'Quỹ phép:')
        self.assertTrue(ActivityLog.objects.filter(action='RUN_DAILY_JOB', user=self.sa).exists())

    def test_uc9_1_exc_1_2_chua_co_so_lieu_hien_so_0_khong_loi(self):
        r, the = self.cac_the(self.kt)
        self.assertIsNone(r.context['luong'])
        self.assertContains(r, thong_bao.CHUA_CO_DU_LIEU)
        r, the = self.cac_the(self.ql)
        self.assertEqual(the['Lịch hôm nay']['so'] >= 0, True)
        self.assertEqual({t['so'] for t in r.context['cho_xu_ly']}, {0})
        r, the = self.cac_the(self.sa)
        self.assertEqual(the['Đăng nhập thất bại']['so'], 0)
        r, the = self.cac_the(self.pt)
        self.assertEqual(the['Lương kỳ gần nhất']['so'], 'Chưa có')

    def test_uc9_1_exc_1_3_khong_phai_sa_ma_chua_co_ho_so_nhan_su(self):
        for vai_tro in (UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE):
            nguoi = User.objects.create_user(f'khong-ho-so-{vai_tro}@icls.vn', 'x', role=vai_tro)
            self.vao(nguoi)
            r = self.client.get(reverse('dashboard:dashboard'))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Tài khoản chưa có hồ sơ nhân sự. Vui lòng liên hệ Quản trị viên.')
            self.assertEqual(r.context['loai'], 'thieu_ho_so')

    def test_uc9_1_phan_quyen_chua_dang_nhap_chuyen_ve_dang_nhap(self):
        r = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('accounts:login'), r['Location'])

    def test_uc9_1_menu_overview_dang_chon(self):
        self.vao(self.gv)
        r = self.client.get(reverse('dashboard:dashboard'))
        self.assertTrue(next(m for m in r.context['menu_chinh'] if m['ten_anh'] == 'Overview')['dang_chon'])


# ============================================================ UC 9.2 – Tác vụ hằng ngày
class Uc92TacVuNgayTest(NenTangDashboard):
    def du_lieu_day_du(self):
        """Dựng một ngày "bận rộn": mỗi bước của UC 9.2 đều có việc để làm."""
        EmployeeDocument.objects.create(employee=self.gv, document_type='CERTIFICATION', document_name='TOPIK',
                                        issue_date=date(2025, 1, 1), expiry_date=HOM_NAY + timedelta(days=7),
                                        file_url='x.pdf', status=DocumentStatus.APPROVED)           # bước 2: nhắc còn 7 ngày
        EmployeeDocument.objects.create(employee=self.gv, document_type='CERTIFICATION', document_name='CC cũ',
                                        issue_date=date(2025, 1, 1), expiry_date=HOM_NAY - timedelta(days=1),
                                        file_url='x.pdf', status=DocumentStatus.APPROVED)           # bước 2: hết hạn → EXPIRED
        Contract.objects.create(employee=self.gv, contract_number='HD1', employment_type='FULL_TIME',
                                start_date=date(2026, 1, 1), end_date=HOM_NAY + timedelta(days=30), file_url='x.pdf')   # bước 3
        # bước 4: gv, ql, kt đều là Full-time Ca 1 và không chấm công hôm qua → 3 người vắng (pt không có ca)
        lop = tao_lop('Lớp A')
        lop.status = 'UPCOMING'
        lop.start_date = HOM_NAY                                                                   # bước 5: lớp bắt đầu
        lop.save()
        TeachingSession.objects.create(study_class=lop, session_date=HOM_NAY - timedelta(days=1), planned_start=time(9),
                                       planned_end=time(11), planned_teacher=self.gv, actual_teacher=self.gv)   # buổi đã qua

    def test_uc9_2_basic_chay_du_cac_buoc_va_ghi_nhat_ky(self):
        self.du_lieu_day_du()
        ket_qua = services.chay_tac_vu_ngay(HOM_NAY, self.sa)
        self.assertEqual([b['ten'] for b in ket_qua], ['Giấy tờ', 'Hợp đồng', 'Chấm công', 'Lịch học', 'Quỹ phép'])
        self.assertTrue(all(b['loi'] is None for b in ket_qua))
        so = {b['ten']: b['so'] for b in ket_qua}
        self.assertEqual(so['Giấy tờ'], 1 + 2)         # 1 hết hạn + nhắc nhân sự và Quản lý (còn 7 ngày)
        self.assertEqual(so['Hợp đồng'], 1)             # 1 Quản lý nhận nhắc mốc 30 ngày
        self.assertEqual(so['Chấm công'], 3)             # 3 vắng mặt
        self.assertEqual(so['Lịch học'], 1 + 1)           # 1 buổi COMPLETED + 1 lớp ACTIVE
        self.assertEqual(EmployeeDocument.objects.get(document_name='CC cũ').status, DocumentStatus.EXPIRED)
        self.assertEqual(Attendance.objects.filter(attendance_status=AttendanceStatus.ABSENT).count(), 3)
        self.assertEqual(StudyClass.objects.get().status, 'ACTIVE')
        self.assertEqual(TeachingSession.objects.get().status, 'COMPLETED')
        self.assertEqual(Contract.objects.get().status, 'ACTIVE')                                   # hợp đồng không bị tự đổi
        self.assertEqual(LeaveBalance.objects.filter(year=2026).count(), 3)                          # gv, ql, kt (Full-time)
        self.assertEqual(so['Quỹ phép'], 3)
        log = ActivityLog.objects.filter(action='RUN_DAILY_JOB').latest('pk')
        self.assertEqual(log.user, self.sa)
        self.assertIn('27/10/2026', log.description)
        self.assertIn(f'xử lý {sum(so.values())} bản ghi', log.description)                        # ghi kèm số bản ghi đã xử lý

    def test_uc9_2_alt_1_1_chay_lan_hai_trong_ngay_khong_tao_trung(self):
        self.du_lieu_day_du()
        services.chay_tac_vu_ngay(HOM_NAY, self.sa)
        so_thong_bao = Notification.objects.count()
        so_cham_cong = Attendance.objects.count()
        lan_hai = services.chay_tac_vu_ngay(HOM_NAY, self.sa)
        self.assertEqual({b['ten']: b['so'] for b in lan_hai},
                         {'Giấy tờ': 0, 'Hợp đồng': 0, 'Chấm công': 0, 'Lịch học': 0, 'Quỹ phép': 0})
        self.assertEqual(Notification.objects.count(), so_thong_bao)
        self.assertEqual(Attendance.objects.count(), so_cham_cong)
        self.assertEqual(LeaveBalance.objects.count(), 3)

    def test_uc9_2_exc_1_2_mot_buoc_loi_cac_buoc_con_lai_van_chay(self):
        self.du_lieu_day_du()
        with mock.patch('dashboard.services._buoc_hop_dong', side_effect=RuntimeError('hỏng')):
            ket_qua = services.chay_tac_vu_ngay(HOM_NAY, self.sa)
        theo_ten = {b['ten']: b for b in ket_qua}
        self.assertIn('hỏng', theo_ten['Hợp đồng']['loi'])
        self.assertTrue(all(b['loi'] is None for ten, b in theo_ten.items() if ten != 'Hợp đồng'))
        self.assertEqual(theo_ten['Quỹ phép']['so'], 3)                                            # bước sau vẫn chạy xong
        self.assertTrue(LeaveBalance.objects.exists())
        tb = Notification.objects.get(recipient=self.sa, notification_type='SYSTEM')
        self.assertEqual(tb.message, 'Tác vụ hằng ngày: bước Hợp đồng gặp lỗi.')                     # nguyên văn §10
        self.assertTrue(ActivityLog.objects.filter(action='RUN_DAILY_JOB', description__contains='Hợp đồng gặp lỗi').exists())

    def test_uc9_2_exc_1_2_buoc_loi_giua_chung_hoan_tac_phan_da_ghi_cua_buoc_do(self):
        """Bước Chấm công tạo được 1 bản ghi rồi lỗi → giao dịch của bước đó bị hoàn tác (không để lại dữ liệu dở dang)."""
        self.du_lieu_day_du()
        with mock.patch('attendance.services.tao_thong_bao', side_effect=RuntimeError('gửi thông báo hỏng')):
            ket_qua = services.chay_tac_vu_ngay(HOM_NAY, None)
        self.assertIsNotNone({b['ten']: b for b in ket_qua}['Chấm công']['loi'])
        self.assertFalse(Attendance.objects.exists())

    def test_uc9_2_tu_dong_khong_co_nguoi_thuc_hien_ghi_nhat_ky_user_none(self):
        services.chay_tac_vu_ngay(HOM_NAY)
        self.assertIsNone(ActivityLog.objects.filter(action='RUN_DAILY_JOB').latest('pk').user)

    def test_uc9_2_lenh_chay_tac_vu_ngay_dung_chung_ham_voi_nut(self):
        self.du_lieu_day_du()
        ra = StringIO()
        call_command('chay_tac_vu_ngay', '--ngay', '2026-10-27', stdout=ra)
        self.assertIn('Tác vụ hằng ngày – 27/10/2026', ra.getvalue())
        self.assertIn('Chấm công: 3', ra.getvalue())
        self.assertEqual(Attendance.objects.filter(attendance_status='ABSENT').count(), 3)
        with self.assertRaises(CommandError):
            call_command('chay_tac_vu_ngay', '--ngay', '27-10-2026')

    def test_uc9_2_nut_cua_super_admin_hien_ket_qua_tung_buoc(self):
        self.vao(self.sa)
        r = self.client.post(reverse('dashboard:run_daily_job'), follow=True)
        self.assertRedirects(r, reverse('dashboard:dashboard'))
        self.assertContains(r, 'Đã chạy tác vụ hằng ngày')
        for ten in ('Giấy tờ', 'Hợp đồng', 'Chấm công', 'Lịch học', 'Quỹ phép'):
            self.assertContains(r, f'{ten}:')
        self.assertTrue(ActivityLog.objects.filter(action='RUN_DAILY_JOB', user=self.sa).exists())

    def test_uc9_2_nut_hien_bao_loi_dung_cau_khi_buoc_hong(self):
        self.vao(self.sa)
        with mock.patch('dashboard.services._buoc_quy_phep', side_effect=RuntimeError('x')):
            r = self.client.post(reverse('dashboard:run_daily_job'), follow=True)
        self.assertContains(r, 'Tác vụ hằng ngày: bước Quỹ phép gặp lỗi.')

    def test_uc9_2_phan_quyen_chi_super_admin_bam_nut(self):
        for nguoi in (self.ql, self.kt, self.gv):
            self.vao(nguoi)
            self.assertEqual(self.client.post(reverse('dashboard:run_daily_job')).status_code, 403)
        self.assertFalse(ActivityLog.objects.filter(action='RUN_DAILY_JOB').exists())
        self.vao(self.sa)
        self.assertEqual(self.client.get(reverse('dashboard:run_daily_job')).status_code, 405)      # chỉ nhận POST
        self.client.logout()
        self.assertEqual(self.client.post(reverse('dashboard:run_daily_job')).status_code, 302)

    def test_uc9_2_nut_chi_hien_cho_super_admin_tren_dashboard(self):
        self.vao(self.ql)
        self.assertNotContains(self.client.get(reverse('dashboard:dashboard')), 'Chạy tác vụ hằng ngày')
