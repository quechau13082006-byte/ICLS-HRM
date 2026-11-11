from io import StringIO

from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from core.permissions import co_quyen_duyet


class PhanQuyenTest(TestCase):
    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN)
        self.ql1 = User.objects.create_user('ql1@icls.vn', 'x', role=UserRole.MANAGER)
        self.ql2 = User.objects.create_user('ql2@icls.vn', 'x', role=UserRole.MANAGER)
        self.kt = User.objects.create_user('kt@icls.vn', 'x', role=UserRole.ACCOUNTANT)
        self.nv = User.objects.create_user('nv@icls.vn', 'x', role=UserRole.EMPLOYEE)

    def test_co_quyen_duyet_khong_tu_duyet(self):
        self.assertFalse(co_quyen_duyet(self.ql1, self.ql1))

    def test_co_quyen_duyet_phan_cap_q2(self):
        self.assertTrue(co_quyen_duyet(self.ql1, self.nv))
        self.assertTrue(co_quyen_duyet(self.ql1, self.kt))
        self.assertTrue(co_quyen_duyet(self.sa, self.ql1))
        self.assertFalse(co_quyen_duyet(self.ql2, self.ql1))  # QL không duyệt QL
        self.assertFalse(co_quyen_duyet(self.sa, self.nv))    # SA không duyệt NV

    def test_chua_dang_nhap_chuyen_ve_dang_nhap(self):
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 302)

    def test_dang_nhap_vao_duoc_trang_chu_va_thong_bao(self):
        self.client.force_login(self.nv)
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:notifications')).status_code, 200)


class DuLieuMauTest(TestCase):
    def test_tao_du_lieu_mau_chay_lai_khong_nhan_doi(self):
        from django.core.management import call_command
        from employees.models import Employee
        from schedule.models import StudyClass
        call_command('tao_du_lieu_mau', stdout=StringIO())
        so_nhan_su, so_lop = Employee.objects.count(), StudyClass.objects.count()
        call_command('tao_du_lieu_mau', stdout=StringIO())
        self.assertEqual((so_nhan_su, so_lop), (40, 20))
        self.assertEqual((Employee.objects.count(), StudyClass.objects.count()), (40, 20))
        self.assertFalse(User.objects.get(email='sa@icls.vn').is_active is False)
        self.assertFalse(hasattr(User.objects.get(email='sa@icls.vn'), 'employee'))  # SA không có hồ sơ (Q1)

    def test_co_giao_vien_nguoi_han(self):
        from django.core.management import call_command
        from employees.models import Employee
        call_command('tao_du_lieu_mau', stdout=StringIO())
        han = Employee.objects.filter(nationality='Hàn Quốc')
        self.assertEqual(han.count(), 4)
        self.assertEqual({nv.position for nv in han}, {'TEACHER'})
        self.assertEqual({nv.work_shift for nv in han}, {'SHIFT_1', 'SHIFT_2'})
        self.assertEqual(Employee.objects.count(), 40)


class MenuTrai(TestCase):
    """Menu trái theo vai trò (§5): mỗi vai trò chỉ thấy mục mình có quyền; app chưa làm xong thì mục hiện mờ."""

    def _menu(self, vai_tro):
        user = User.objects.create_user(f'{vai_tro}@icls.vn', 'x', role=vai_tro)
        self.client.force_login(user)
        r = self.client.get(reverse('dashboard:dashboard'))
        return {m['ten_anh']: m for m in r.context['menu_chinh']}, r

    def test_menu_super_admin_khong_co_recruitment_contract_payroll(self):
        menu, r = self._menu(UserRole.SUPER_ADMIN)
        self.assertEqual(set(menu), {'Overview', 'Employees', 'Schedule', 'Attendance', 'Leave'})
        self.assertContains(r, 'User Management')          # chỉ Super Admin có mục này trong menu tài khoản

    def test_menu_quan_ly_thay_du_tat_ca(self):
        menu, r = self._menu(UserRole.MANAGER)
        self.assertEqual(len(menu), 8)
        self.assertNotContains(r, 'User Management')

    def test_menu_ke_toan_va_nhan_vien_khong_co_recruitment(self):
        for vai_tro in (UserRole.ACCOUNTANT, UserRole.EMPLOYEE):
            menu, _ = self._menu(vai_tro)
            self.assertNotIn('Recruitment', menu, vai_tro)
            self.assertIn('Payroll', menu, vai_tro)

    def test_muc_chua_co_trang_thi_hien_mo_overview_thi_bam_duoc(self):
        menu, _ = self._menu(UserRole.MANAGER)
        self.assertIsNotNone(menu['Overview']['url'])
        self.assertTrue(menu['Overview']['dang_chon'])
        self.assertIsNotNone(menu['Recruitment']['url'])     # P3 đã có trang -> mục tự bật
        self.assertIsNotNone(menu['Schedule']['url'])        # P6 đã có trang -> mục tự bật
        self.assertIsNotNone(menu['Attendance']['url'])      # P8 đã có trang -> mục tự bật
        self.assertIsNotNone(menu['Payroll']['url'])         # P9 đã có trang -> mọi mục menu đều đã bật
        self.assertTrue(all(m['url'] for m in menu.values()))

    def test_trang_chua_dang_nhap_khong_co_menu(self):
        r = self.client.get(reverse('accounts:login'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'sidebar-nav')
