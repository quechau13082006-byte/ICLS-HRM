import shutil
import tempfile
from pathlib import Path
from io import StringIO

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from core.permissions import co_quyen_duyet


class PhanQuyenTest(TestCase):
    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN)
        self.gd = User.objects.create_user('gd@icls.vn', 'x', role=UserRole.DIRECTOR)
        self.ql1 = User.objects.create_user('ql1@icls.vn', 'x', role=UserRole.MANAGER)
        self.ql2 = User.objects.create_user('ql2@icls.vn', 'x', role=UserRole.MANAGER)
        self.kt = User.objects.create_user('kt@icls.vn', 'x', role=UserRole.ACCOUNTANT)
        self.nv = User.objects.create_user('nv@icls.vn', 'x', role=UserRole.EMPLOYEE)

    def test_co_quyen_duyet_khong_tu_duyet(self):
        self.assertFalse(co_quyen_duyet(self.ql1, self.ql1))

    def test_co_quyen_duyet_phan_cap_q2(self):
        self.assertTrue(co_quyen_duyet(self.ql1, self.nv))
        self.assertTrue(co_quyen_duyet(self.ql1, self.kt))
        self.assertTrue(co_quyen_duyet(self.gd, self.ql1))    # Giám đốc duyệt Quản lý
        self.assertFalse(co_quyen_duyet(self.ql2, self.ql1))  # QL không duyệt QL
        self.assertFalse(co_quyen_duyet(self.gd, self.nv))    # Giám đốc không duyệt NV (việc của Quản lý)
        self.assertFalse(co_quyen_duyet(self.sa, self.ql1))   # Super Admin chỉ làm kỹ thuật, không duyệt gì
        self.assertFalse(co_quyen_duyet(self.sa, self.nv))

    def test_super_admin_khong_vao_trang_nghiep_vu(self):
        self.client.force_login(self.sa)
        for ten in ('employees:employee_list', 'leave:review', 'attendance:review', 'attendance:summary',
                    'employees:documents', 'contracts:contract_list'):
            self.assertEqual(self.client.get(reverse(ten)).status_code, 403, ten)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 200)

    def test_giam_doc_vao_trang_duyet_va_xem_nhung_khong_thao_tac_cua_quan_ly(self):
        self.client.force_login(self.gd)
        for ten in ('employees:employee_list', 'leave:review', 'attendance:review', 'attendance:summary',
                    'employees:documents', 'contracts:contract_list', 'leave:summary'):
            self.assertEqual(self.client.get(reverse(ten)).status_code, 200, ten)
        for ten in ('accounts:user_list', 'contracts:contract_add', 'recruitment:board'):
            self.assertEqual(self.client.get(reverse(ten)).status_code, 403, ten)

    def test_chi_super_admin_vao_trang_quan_tri_django(self):
        self.client.force_login(self.sa)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get('/admin/accounts/user/').status_code, 200)
        for nguoi in (self.gd, self.ql1, self.kt, self.nv):
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get('/admin/').status_code, 302, nguoi.role)   # đẩy về trang đăng nhập admin

    def test_doi_vai_tro_thi_quyen_admin_doi_theo(self):
        self.assertTrue(self.sa.is_staff and self.sa.is_superuser)
        self.ql1.role = UserRole.SUPER_ADMIN
        self.ql1.save(update_fields=['role'])
        self.ql1.refresh_from_db()
        self.assertTrue(self.ql1.is_staff and self.ql1.is_superuser)
        self.ql1.role = UserRole.MANAGER
        self.ql1.save(update_fields=['role'])
        self.ql1.refresh_from_db()
        self.assertFalse(self.ql1.is_staff or self.ql1.is_superuser)

    def test_chua_dang_nhap_chuyen_ve_dang_nhap(self):
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 302)

    def test_dang_nhap_vao_duoc_trang_chu_va_thong_bao(self):
        self.client.force_login(self.nv)
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:notifications')).status_code, 200)


_MEDIA_TAM = Path(tempfile.mkdtemp())


@override_settings(MEDIA_ROOT=_MEDIA_TAM)          # file giấy tờ, ảnh đại diện mẫu ghi vào thư mục tạm, không vào media/ thật
class DuLieuMauTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_TAM, ignore_errors=True)

    def test_tao_du_lieu_mau_chay_lai_khong_nhan_doi(self):
        from django.core.management import call_command
        from employees.models import Employee
        from schedule.models import StudyClass
        call_command('tao_du_lieu_mau', stdout=StringIO())
        so_nhan_su, so_lop = Employee.objects.count(), StudyClass.objects.count()
        call_command('tao_du_lieu_mau', stdout=StringIO())
        # 40 đang làm việc + 2 đang Onboarding (gv17, kt02) + 1 đã nghỉ (st10)
        self.assertEqual((so_nhan_su, so_lop), (43, 20))
        self.assertEqual((Employee.objects.count(), StudyClass.objects.count()), (43, 20))
        self.assertEqual(Employee.objects.filter(status='ACTIVE').count(), 40)
        self.assertFalse(User.objects.get(email='sa@icls.vn').is_active is False)
        self.assertFalse(hasattr(User.objects.get(email='sa@icls.vn'), 'employee'))  # SA không có hồ sơ (Q1)

    def test_co_giao_vien_nguoi_han(self):
        from django.core.management import call_command
        from employees.models import Employee
        call_command('tao_du_lieu_mau', stdout=StringIO())
        han = Employee.objects.filter(nationality='Hàn Quốc')
        self.assertEqual(han.count(), 11)                     # 11/16 giáo viên ≈ 70%
        self.assertEqual({nv.position for nv in han}, {'TEACHER'})
        self.assertEqual({nv.work_shift for nv in han}, {'SHIFT_1', 'SHIFT_2'})
        self.assertEqual(Employee.objects.filter(status='ACTIVE').count(), 40)

    def test_du_lieu_demo_bo_sung_du_kich_ban_va_khong_nhan_doi(self):
        from django.core.management import call_command
        from contracts.models import Contract
        from employees.models import EmployeeDocument
        from schedule.models import SubstituteRequest
        call_command('tao_du_lieu_mau', stdout=StringIO())
        dem = lambda: (EmployeeDocument.objects.count(), SubstituteRequest.objects.count(), Contract.objects.count())
        truoc = dem()
        call_command('tao_du_lieu_mau', stdout=StringIO())
        self.assertEqual(dem(), truoc)
        trang_thai = set(EmployeeDocument.objects.values_list('status', flat=True))
        self.assertEqual(trang_thai, {'APPROVED', 'PENDING', 'REJECTED', 'EXPIRED'})
        self.assertTrue(EmployeeDocument.objects.filter(status='PENDING', employee__user__role=UserRole.MANAGER).exists())
        self.assertFalse(User.objects.get(email='st10@icls.vn').is_active)                    # đã nghỉ → bị khóa
        from core.management.commands.tao_du_lieu_mau import MAT_KHAU_DEMO
        self.assertTrue(User.objects.get(email='kt02@icls.vn').check_password(MAT_KHAU_DEMO))   # tạo qua Onboarding
        self.assertEqual(SubstituteRequest.objects.filter(status='SEARCHING').count(), 1)
        self.assertTrue(Contract.objects.filter(previous_contract__isnull=False).exists())


class MenuTrai(TestCase):
    """Menu trái theo vai trò (§5): mỗi vai trò chỉ thấy mục mình có quyền; app chưa làm xong thì mục hiện mờ."""

    def _menu(self, vai_tro):
        user = User.objects.create_user(f'{vai_tro}@icls.vn', 'x', role=vai_tro)
        self.client.force_login(user)
        r = self.client.get(reverse('dashboard:dashboard'))
        return {m['ten_anh']: m for m in r.context['menu_chinh']}, r

    def test_menu_super_admin_chi_co_overview_va_user_management(self):
        menu, r = self._menu(UserRole.SUPER_ADMIN)
        self.assertEqual(set(menu), {'Overview', 'User Management', 'Admin'})   # chỉ phần kỹ thuật, không có mục nghiệp vụ
        self.assertEqual(menu['User Management']['url'], reverse('accounts:user_list'))   # nằm ở menu trái
        self.assertEqual(r.content.decode().count('User Management'), 1)                  # không còn lặp ở menu tài khoản

    def test_user_management_chi_sang_o_trang_quan_ly_tai_khoan(self):
        user = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN)
        self.client.force_login(user)
        for ten_url, mong_doi in (('accounts:user_list', True), ('accounts:user_add', True), ('accounts:my_account', False),
                                  ('accounts:change_password', False), ('dashboard:dashboard', False)):
            r = self.client.get(reverse(ten_url))
            menu = {m['ten_anh']: m for m in r.context['menu_chinh']}
            self.assertEqual(menu['User Management']['dang_chon'], mong_doi, ten_url)
        r = self.client.get(reverse('dashboard:dashboard'))
        self.assertTrue({m['ten_anh']: m for m in r.context['menu_chinh']}['Overview']['dang_chon'])

    def test_menu_giam_doc_khong_co_recruitment_payroll(self):
        menu, r = self._menu(UserRole.DIRECTOR)
        self.assertEqual(set(menu), {'Overview', 'Employees', 'Contract', 'Schedule', 'Attendance', 'Leave'})
        self.assertNotContains(r, 'User Management')
        self.assertNotContains(r, 'My profile')            # Giám đốc không có hồ sơ nhân sự

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


class PhanTrangDungChungTest(TestCase):
    """core/_phan_trang.html: link sang trang khác giữ nguyên bộ lọc trên URL, thay số trang cũ."""

    def test_link_trang_giu_bo_loc(self):
        from django.core.paginator import Paginator
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        request = RequestFactory().get('/nhan-su/', {'q': 'an', 'trang_thai': 'ACTIVE', 'page': '2'})
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()                                              # context processor cần user
        trang = Paginator(list(range(25)), 10).get_page(2)
        html = render_to_string('core/_phan_trang.html', {'trang': trang, 'don_vi': 'nhân sự'}, request=request)
        self.assertIn('Hiển thị 11–20 trong 25 nhân sự', html)
        self.assertIn('href="?q=an&amp;trang_thai=ACTIVE&amp;page=3"', html)      # trang sau, giữ bộ lọc
        self.assertIn('href="?q=an&amp;trang_thai=ACTIVE&amp;page=1"', html)
        self.assertNotIn('page=2&amp;page', html)                                    # không lặp tham số page
