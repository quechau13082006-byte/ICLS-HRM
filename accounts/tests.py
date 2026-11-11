"""Test của app accounts (UC 1) – tên test bám mã luồng ở §10 (§12.1).

Quy ước tên: test_uc<x>_<y>_basic · _alt_<mã luồng> · _exc_<mã luồng>.
"""
import re
import shutil
import tempfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts import services
from accounts.models import User, UserRole
from core import thong_bao
from core.mau_test import tao_nhan_su
from core.models import ActivityLog, Notification

MAT_KHAU = 'Matkhau123'


def tao_user(email, vai_tro=UserRole.EMPLOYEE, **kw):
    return User.objects.create_user(email, MAT_KHAU, role=vai_tro, full_name=email, **kw)


class DangNhapTest(TestCase):          # UC 1.1
    def setUp(self):
        self.nv = tao_user('nv@icls.vn')
        self.url = reverse('accounts:login')

    def test_uc1_1_basic(self):
        r = self.client.post(self.url, {'email': 'nv@icls.vn', 'mat_khau': MAT_KHAU})
        self.assertRedirects(r, reverse('dashboard:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.nv.pk)      # có session
        self.assertTrue(ActivityLog.objects.filter(action='LOGIN', user=self.nv).exists())

    def test_uc1_1_basic_email_khong_phan_biet_hoa_thuong(self):
        r = self.client.post(self.url, {'email': 'NV@ICLS.VN', 'mat_khau': MAT_KHAU})
        self.assertEqual(r.status_code, 302)

    def test_uc1_1_alt_1_1_co_link_quen_mat_khau(self):
        r = self.client.get(self.url)
        self.assertContains(r, reverse('accounts:forgot_password'))

    def test_uc1_1_exc_3_1_de_trong_truong_bat_buoc(self):
        r = self.client.post(self.url, {'email': '', 'mat_khau': ''})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['form'].errors['email'])
        self.assertTrue(r.context['form'].errors['mat_khau'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_uc1_1_exc_3_2_sai_mat_khau(self):
        r = self.client.post(self.url, {'email': 'nv@icls.vn', 'mat_khau': 'sai'})
        self.assertContains(r, thong_bao.DANG_NHAP_SAI_THONG_TIN)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(ActivityLog.objects.filter(action='LOGIN_FAILED').exists())

    def test_uc1_1_exc_3_2_email_khong_ton_tai(self):
        r = self.client.post(self.url, {'email': 'khong@icls.vn', 'mat_khau': MAT_KHAU})
        self.assertContains(r, thong_bao.DANG_NHAP_SAI_THONG_TIN)
        log = ActivityLog.objects.get(action='LOGIN_FAILED')
        self.assertIsNone(log.user)
        self.assertIn('khong@icls.vn', log.description)

    def test_uc1_1_exc_3_3_tai_khoan_bi_khoa(self):
        self.nv.is_active = False
        self.nv.save()
        r = self.client.post(self.url, {'email': 'nv@icls.vn', 'mat_khau': MAT_KHAU})
        self.assertContains(r, thong_bao.TAI_KHOAN_BI_KHOA)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_uc1_1_chua_dat_mat_khau_khong_dang_nhap_duoc(self):
        User.objects.create_user('moi@icls.vn')            # chưa có mật khẩu (UC 1.5, 2.5)
        r = self.client.post(self.url, {'email': 'moi@icls.vn', 'mat_khau': ''})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(r.status_code, 200)

    def test_uc1_1_next_chi_chuyen_ve_dia_chi_noi_bo(self):
        r = self.client.post(self.url, {'email': 'nv@icls.vn', 'mat_khau': MAT_KHAU, 'next': 'https://evil.com/'})
        self.assertRedirects(r, reverse('dashboard:dashboard'))


class QuenMatKhauTest(TestCase):       # UC 1.2
    def setUp(self):
        self.nv = tao_user('nv@icls.vn')

    def _lay_link(self):
        return re.search(r'http://\S+/tai-khoan/dat-mat-khau/\S+/\S+/', mail.outbox[-1].body).group(0)

    def _duong_dan(self):
        return self._lay_link().replace('http://127.0.0.1:8000', '')

    def test_uc1_2_basic(self):
        r = self.client.post(reverse('accounts:forgot_password'), {'email': 'nv@icls.vn'}, follow=True)
        self.assertContains(r, thong_bao.DA_GUI_HUONG_DAN_DAT_LAI)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['nv@icls.vn'])
        r = self.client.post(self._duong_dan(), {'mat_khau_moi': 'Moi12345', 'xac_nhan': 'Moi12345'}, follow=True)
        self.assertContains(r, thong_bao.DAT_LAI_MAT_KHAU_THANH_CONG)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password('Moi12345'))
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', user=self.nv).exists())
        # Đường dẫn đã dùng không còn hiệu lực (luồng 6.1)
        r = self.client.get(self._duong_dan(), follow=True)
        self.assertContains(r, thong_bao.LINK_HET_HAN)

    def test_uc1_2_alt_3_1_co_nut_quay_lai_dang_nhap(self):
        r = self.client.get(reverse('accounts:forgot_password'))
        self.assertContains(r, reverse('accounts:login'))

    def test_uc1_2_exc_3_2_email_khong_ton_tai(self):
        r = self.client.post(reverse('accounts:forgot_password'), {'email': 'khong@icls.vn'})
        self.assertContains(r, thong_bao.EMAIL_KHONG_TON_TAI)
        self.assertEqual(len(mail.outbox), 0)

    def test_uc1_2_exc_6_1_link_sai_hoac_het_han(self):
        url = reverse('accounts:dat_mat_khau', args=['MQ', 'token-gia'])
        r = self.client.get(url, follow=True)
        self.assertContains(r, thong_bao.LINK_HET_HAN)

    def test_uc1_2_exc_6_1_link_het_han_sau_24_gio(self):
        from django.test import override_settings
        services.gui_link_dat_mat_khau(self.nv)
        duong_dan = self._duong_dan()
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):      # giả lập đã quá hạn
            r = self.client.get(duong_dan, follow=True)
        self.assertContains(r, thong_bao.LINK_HET_HAN)

    def test_uc1_2_exc_6_2_xac_nhan_khong_khop(self):
        services.gui_link_dat_mat_khau(self.nv)
        r = self.client.post(self._duong_dan(), {'mat_khau_moi': 'Moi12345', 'xac_nhan': 'Khac12345'})
        self.assertContains(r, thong_bao.MAT_KHAU_XAC_NHAN_KHONG_KHOP)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password(MAT_KHAU))     # chưa đổi

    def test_uc1_2_exc_6_2_mat_khau_chua_du_manh(self):
        services.gui_link_dat_mat_khau(self.nv)
        for yeu in ('Ab1', '12345678'):                        # quá ngắn; toàn số
            r = self.client.post(self._duong_dan(), {'mat_khau_moi': yeu, 'xac_nhan': yeu})
            self.assertContains(r, thong_bao.MAT_KHAU_CHUA_DU_MANH)

    def test_uc1_2_nhan_vien_moi_tu_dat_mat_khau_lan_dau(self):
        moi = User.objects.create_user('moi@icls.vn', full_name='Mới')
        self.assertFalse(moi.has_usable_password())
        services.gui_link_dat_mat_khau(moi)
        self.client.post(self._duong_dan(), {'mat_khau_moi': 'Moi12345', 'xac_nhan': 'Moi12345'})
        moi.refresh_from_db()
        self.assertTrue(moi.check_password('Moi12345'))


class DoiMatKhauTest(TestCase):        # UC 1.3
    def setUp(self):
        self.nv = tao_user('nv@icls.vn')
        self.client.force_login(self.nv)
        self.url = reverse('accounts:change_password')

    def _gui(self, hien_tai=MAT_KHAU, moi='Moi12345', xac_nhan='Moi12345'):
        return self.client.post(self.url, {'mat_khau_hien_tai': hien_tai, 'mat_khau_moi': moi, 'xac_nhan': xac_nhan})

    def test_uc1_3_basic(self):
        r = self.client.post(self.url, {'mat_khau_hien_tai': MAT_KHAU, 'mat_khau_moi': 'Moi12345',
                                        'xac_nhan': 'Moi12345'}, follow=True)
        self.assertRedirects(r, reverse('accounts:my_account'))
        self.assertContains(r, thong_bao.DOI_MAT_KHAU_THANH_CONG)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password('Moi12345'))
        # Phiên đăng nhập vẫn được giữ
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 200)
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', description='Đổi mật khẩu').exists())

    def test_uc1_3_exc_3_1_sai_mat_khau_hien_tai(self):
        r = self._gui(hien_tai='sai')
        self.assertContains(r, thong_bao.MAT_KHAU_HIEN_TAI_SAI)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password(MAT_KHAU))

    def test_uc1_3_exc_3_2_xac_nhan_khong_khop(self):
        r = self._gui(xac_nhan='Khac12345')
        self.assertContains(r, thong_bao.MAT_KHAU_XAC_NHAN_KHONG_KHOP)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password(MAT_KHAU))

    def test_uc1_3_exc_3_3_chua_du_manh(self):
        r = self._gui(moi='12345678', xac_nhan='12345678')
        self.assertContains(r, thong_bao.MAT_KHAU_CHUA_DU_MANH)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.check_password(MAT_KHAU))

    def test_uc1_3_phan_quyen_moi_vai_tro_deu_vao_duoc(self):
        for vai_tro in UserRole.values:
            self.client.force_login(tao_user(f'{vai_tro}@icls.vn', vai_tro))
            self.assertEqual(self.client.get(self.url).status_code, 200, vai_tro)

    def test_uc1_3_phan_quyen_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)


THU_MUC_MEDIA_TAM = tempfile.mkdtemp()      # file ảnh khi test ghi vào thư mục tạm, không làm bẩn media/


@override_settings(MEDIA_ROOT=THU_MUC_MEDIA_TAM)
class TaiKhoanCaNhanTest(TestCase):    # UC 1.4
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_MEDIA_TAM, ignore_errors=True)

    def test_uc1_4_anh_dai_dien_chi_tai_qua_view_co_kiem_tra_quyen(self):
        self.client.post(self.url, {'full_name': 'A', 'phone': '0912345678', 'avatar': self._anh()})
        self.user.refresh_from_db()
        duong_dan = reverse('core:tai_file', args=[self.user.avatar.name])
        self.assertEqual(self.client.get(duong_dan).status_code, 200)       # đã đăng nhập: xem được
        self.assertEqual(self.client_class().get(duong_dan).status_code, 302)  # chưa đăng nhập: bị chặn

    def setUp(self):
        self.nv = tao_nhan_su('nv@icls.vn')            # có hồ sơ nhân sự
        self.user = self.nv.user
        self.user.set_password(MAT_KHAU)
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse('accounts:my_account')

    def _anh(self, ten='a.png', kich_thuoc=100):
        return SimpleUploadedFile(ten, b'x' * kich_thuoc, content_type='image/png')

    def test_uc1_4_basic_dong_bo_sang_employees(self):
        r = self.client.post(self.url, {'full_name': 'Tên Mới', 'phone': '0912345678', 'avatar': self._anh()},
                             follow=True)
        self.assertRedirects(r, self.url)
        self.assertContains(r, thong_bao.CAP_NHAT_TAI_KHOAN_THANH_CONG)
        self.user.refresh_from_db(); self.nv.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.phone), ('Tên Mới', '0912345678'))
        self.assertEqual((self.nv.full_name, self.nv.phone), ('Tên Mới', '0912345678'))   # đồng bộ employees
        self.assertTrue(self.user.avatar)

    def test_uc1_4_basic_hien_thi_phong_ban_vi_tri(self):
        r = self.client.get(self.url)
        self.assertContains(r, self.nv.get_position_display())
        self.assertContains(r, self.nv.get_department_display())

    def test_uc1_4_basic_super_admin_khong_co_ho_so(self):
        sa = tao_user('sa@icls.vn', UserRole.SUPER_ADMIN)
        self.client.force_login(sa)
        r = self.client.post(self.url, {'full_name': 'Admin', 'phone': '0912345678'})
        self.assertEqual(r.status_code, 302)
        sa.refresh_from_db()
        self.assertEqual(sa.full_name, 'Admin')

    def test_uc1_4_exc_3_1_trong_ho_ten(self):
        r = self.client.post(self.url, {'full_name': '', 'phone': '0912345678'})
        self.assertTrue(r.context['form'].errors['full_name'])
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.full_name, '')

    def test_uc1_4_exc_3_1_sai_dinh_dang_sdt_va_anh(self):
        r = self.client.post(self.url, {'full_name': 'A', 'phone': '123'})
        self.assertTrue(r.context['form'].errors['phone'])
        r = self.client.post(self.url, {'full_name': 'A', 'phone': '0912345678', 'avatar': self._anh('a.gif')})
        self.assertTrue(r.context['form'].errors['avatar'])
        r = self.client.post(self.url, {'full_name': 'A', 'phone': '0912345678',
                                        'avatar': self._anh('a.png', 2 * 1024 * 1024 + 1)})
        self.assertTrue(r.context['form'].errors['avatar'])

    def test_uc1_4_exc_3_1_loi_thi_khong_luu_ca_hai_bang(self):
        self.client.post(self.url, {'full_name': 'Tên Mới', 'phone': 'abc'})
        self.nv.refresh_from_db()
        self.assertNotEqual(self.nv.full_name, 'Tên Mới')

    def test_uc1_4_exc_3_2_bo_qua_truong_bi_khoa(self):
        self.client.post(self.url, {'full_name': 'A', 'phone': '0912345678',
                                    'email': 'hack@icls.vn', 'role': 'SUPER_ADMIN', 'is_superuser': 'on'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'nv@icls.vn')
        self.assertEqual(self.user.role, UserRole.EMPLOYEE)
        self.assertFalse(self.user.is_superuser)


class QuanLyTaiKhoanTest(TestCase):    # UC 1.5
    def setUp(self):
        self.sa = tao_user('sa@icls.vn', UserRole.SUPER_ADMIN)
        self.nv = tao_user('nv@icls.vn')
        self.client.force_login(self.sa)

    def test_uc1_5_basic_doi_vai_tro(self):
        url = reverse('accounts:user_change_role', args=[self.nv.pk])
        r = self.client.post(url, {'role': UserRole.MANAGER})
        self.assertRedirects(r, reverse('accounts:user_list'))
        self.nv.refresh_from_db()
        self.assertEqual(self.nv.role, UserRole.MANAGER)
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', object_id=self.nv.pk, user=self.sa).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.nv, title=thong_bao.TB_DOI_VAI_TRO_TIEU_DE).exists())

    def test_uc1_5_basic_khoa_va_mo_khoa(self):
        url = reverse('accounts:user_toggle_lock', args=[self.nv.pk])
        self.client.post(url)
        self.nv.refresh_from_db()
        self.assertFalse(self.nv.is_active)
        self.assertTrue(ActivityLog.objects.filter(action='LOCK', object_id=self.nv.pk).exists())
        self.client.post(url)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.is_active)
        self.assertTrue(ActivityLog.objects.filter(action='UNLOCK', object_id=self.nv.pk).exists())

    def test_uc1_5_basic_khoa_co_hieu_luc_ngay_voi_phien_dang_dung(self):
        nv_client = self.client_class()
        nv_client.force_login(self.nv)
        self.assertEqual(nv_client.get(reverse('dashboard:dashboard')).status_code, 200)
        self.client.post(reverse('accounts:user_toggle_lock', args=[self.nv.pk]))
        self.assertEqual(nv_client.get(reverse('dashboard:dashboard')).status_code, 302)   # bị đẩy ra

    def test_uc1_5_basic_loc_va_tim_kiem(self):
        tao_user('ql@icls.vn', UserRole.MANAGER)
        self.assertEqual(services.danh_sach_tai_khoan(vai_tro=UserRole.MANAGER).count(), 1)
        self.assertEqual(services.danh_sach_tai_khoan(tu_khoa='nv@').count(), 1)
        self.nv.is_active = False
        self.nv.save()
        self.assertEqual(services.danh_sach_tai_khoan(trang_thai='LOCKED').count(), 1)
        r = self.client.get(reverse('accounts:user_list'), {'vai_tro': 'MANAGER'})
        self.assertContains(r, 'ql@icls.vn')
        self.assertNotContains(r, 'nv@icls.vn')

    def test_uc1_5_alt_3_1_them_tai_khoan(self):
        r = self.client.post(reverse('accounts:user_add'),
                             {'email': 'moi@icls.vn', 'full_name': 'Mới', 'role': UserRole.EMPLOYEE})
        self.assertRedirects(r, reverse('accounts:user_list'))
        moi = User.objects.get(email='moi@icls.vn')
        self.assertFalse(moi.has_usable_password())          # chưa có mật khẩu
        self.assertEqual(len(mail.outbox), 1)                  # email đường dẫn đặt mật khẩu
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', object_id=moi.pk).exists())

    def test_uc1_5_alt_3_2_mo_thang_tai_khoan_can_nang_quyen(self):
        r = self.client.get(reverse('accounts:user_change_role', args=[self.nv.pk]))
        self.assertContains(r, 'nv@icls.vn')
        self.assertEqual(r.status_code, 200)

    def test_uc1_5_alt_3_2_hien_chuc_danh_trong_ho_so(self):
        nhan_su = tao_nhan_su('gv@icls.vn')
        r = self.client.get(reverse('accounts:user_change_role', args=[nhan_su.user.pk]))
        self.assertContains(r, nhan_su.get_position_display())

    def test_uc1_5_exc_3_3_email_da_ton_tai(self):
        r = self.client.post(reverse('accounts:user_add'),
                             {'email': 'NV@icls.vn', 'full_name': 'Trùng', 'role': UserRole.EMPLOYEE})
        self.assertContains(r, thong_bao.EMAIL_DA_DUNG)
        self.assertEqual(User.objects.filter(email__iexact='nv@icls.vn').count(), 1)

    def test_uc1_5_exc_5_1_khong_tu_khoa_hoac_tu_doi_quyen(self):
        r = self.client.post(reverse('accounts:user_toggle_lock', args=[self.sa.pk]), follow=True)
        self.assertContains(r, thong_bao.KHONG_TU_KHOA)
        r = self.client.post(reverse('accounts:user_change_role', args=[self.sa.pk]), {'role': UserRole.EMPLOYEE})
        self.assertContains(r, thong_bao.KHONG_TU_KHOA)
        self.sa.refresh_from_db()
        self.assertTrue(self.sa.is_active)
        self.assertEqual(self.sa.role, UserRole.SUPER_ADMIN)

    def test_uc1_5_exc_1_1_khong_phai_super_admin_bi_403(self):
        urls = [reverse('accounts:user_list'), reverse('accounts:user_add'),
                reverse('accounts:user_change_role', args=[self.nv.pk])]
        for vai_tro in (UserRole.MANAGER, UserRole.ACCOUNTANT, UserRole.EMPLOYEE):
            self.client.force_login(tao_user(f'{vai_tro}@icls.vn', vai_tro))
            for url in urls:
                r = self.client.get(url)
                self.assertEqual(r.status_code, 403, (vai_tro, url))
                self.assertContains(r, thong_bao.KHONG_CO_QUYEN, status_code=403)
            r = self.client.post(reverse('accounts:user_toggle_lock', args=[self.nv.pk]))
            self.assertEqual(r.status_code, 403)
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.is_active)


class DangXuatTest(TestCase):          # UC 1.6
    def setUp(self):
        self.nv = tao_user('nv@icls.vn')
        self.client.force_login(self.nv)

    def test_uc1_6_basic(self):
        r = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertRedirects(r, reverse('accounts:login'))
        self.assertContains(r, thong_bao.DA_DANG_XUAT)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(ActivityLog.objects.filter(action='LOGOUT', user=self.nv).exists())
        self.assertEqual(self.client.get(reverse('dashboard:dashboard')).status_code, 302)

    def test_uc1_6_dang_xuat_chi_nhan_post(self):
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)

    def test_uc1_6_exc_1_1_phien_het_han_van_ve_trang_dang_nhap(self):
        self.client.logout()
        r = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(r, reverse('accounts:login'))
