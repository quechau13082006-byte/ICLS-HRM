"""Test của app employees – P1: ràng buộc CSDL (§7.3.2, §7.3.3); P4 (ROADMAP): UC 2.1–2.6.

Quy ước tên: test_uc<x>_<y>_basic · _alt_<mã luồng> · _exc_<mã luồng> (§12.1).
"""
import shutil
import tempfile
from datetime import date, timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from contracts.models import Contract
from core import thong_bao
from core.mau_test import tao_nhan_su
from core.models import ActivityLog, Notification
from employees import services
from employees.models import (DocumentStatus, DocumentType, Employee, EmployeeDocument, EmployeeStatus, EmploymentType,
                              Position, WorkShift)
from leave.models import LeaveBalance
from recruitment.models import Candidate, CandidateStatus, RecruitmentCampaign

class RangBuocEmployeesTest(TestCase):
    def test_id_card_number_la_duy_nhat(self):
        a, b = tao_nhan_su('a@icls.vn'), tao_nhan_su('b@icls.vn')
        a.id_card_number = b.id_card_number = '079000000001'
        a.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            b.save()

    def test_giay_to_het_han_truoc_ngay_cap_bi_chan(self):
        nv = tao_nhan_su()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeDocument.objects.create(
                employee=nv, document_type=DocumentType.CERTIFICATION, document_name='TOPIK 6',
                issue_date=date(2026, 5, 1), expiry_date=date(2026, 4, 1), file_url='x.pdf')

    def test_ma_nhan_vien_hien_thi(self):
        self.assertEqual(tao_nhan_su().code, f'NV{tao_nhan_su("c@icls.vn").id - 1:04d}')


# ======================================================================== UC 2 – nghiệp vụ
THU_MUC_MEDIA_TAM = tempfile.mkdtemp()      # file tải lên khi test ghi vào thư mục tạm, không làm bẩn media/
HOM_NAY = date.today()


def tao_nguoi(email, vai_tro=UserRole.EMPLOYEE, chuc_danh=Position.TEACHER, loai_hinh=EmploymentType.FULL_TIME,
              ca=WorkShift.SHIFT_1):
    """Một nhân sự có tài khoản đúng vai trò (Super Admin thì chỉ có tài khoản, không có hồ sơ – Q1)."""
    if vai_tro == UserRole.SUPER_ADMIN:
        return User.objects.create_user(email, 'x', role=vai_tro, full_name=email)
    nhan_su = tao_nhan_su(email, vai_tro, chuc_danh, loai_hinh, ca if loai_hinh == EmploymentType.FULL_TIME else '')
    nhan_su.status = EmployeeStatus.ACTIVE
    nhan_su.save()
    return nhan_su


def tao_giay_to(nhan_su, ten='TOPIK 5', trang_thai=DocumentStatus.APPROVED, het_han=None, **kw):
    return EmployeeDocument.objects.create(
        employee=nhan_su, document_type=DocumentType.CERTIFICATION, document_name=ten, status=trang_thai,
        issue_date=date(2024, 1, 1), expiry_date=het_han, file_url='employee_documents/mau.pdf', **kw)


def tep(ten='a.pdf', kich_thuoc=100, loai='application/pdf'):
    return SimpleUploadedFile(ten, b'x' * kich_thuoc, content_type=loai)


class UcNhanSuCoSo(TestCase):
    """Dữ liệu chung: Super Admin, 2 Quản lý, Kế toán, hai Nhân viên."""

    def setUp(self):
        self.sa = tao_nguoi('sa@icls.vn', UserRole.SUPER_ADMIN)
        self.ql = tao_nguoi('ql@icls.vn', UserRole.MANAGER, Position.MANAGER)
        self.ql2 = tao_nguoi('ql2@icls.vn', UserRole.MANAGER, Position.MANAGER)
        self.kt = tao_nguoi('kt@icls.vn', UserRole.ACCOUNTANT, Position.ACCOUNTANT)
        self.nv = tao_nguoi('nv@icls.vn')
        self.nv2 = tao_nguoi('nv2@icls.vn')

    def vao(self, nguoi):
        self.client.force_login(nguoi.user if hasattr(nguoi, 'user') else nguoi)


class DanhSachNhanSuTest(UcNhanSuCoSo):         # UC 2.1
    def setUp(self):
        super().setUp()
        self.nghi = tao_nguoi('nghi@icls.vn')
        self.nghi.status = EmployeeStatus.RESIGNED
        self.nghi.save()
        self.url = reverse('employees:employee_list')

    def test_uc2_1_basic_quan_ly_thay_du_cot_va_moi_trang_thai(self):
        self.vao(self.ql)
        r = self.client.get(self.url)
        self.assertContains(r, 'nghi@icls.vn')                  # gồm cả nhân sự đã nghỉ
        self.assertContains(r, 'Số điện thoại')
        self.assertContains(r, 'Thêm nhân sự mới')
        self.assertEqual(r.context['trang'].paginator.count, 6)

    def test_uc2_1_basic_super_admin_xem_day_du_nhung_khong_co_nut_them(self):
        self.vao(self.sa)
        r = self.client.get(self.url)
        self.assertContains(r, 'Số điện thoại')
        self.assertNotContains(r, 'Thêm nhân sự mới')
        self.assertEqual(r.context['trang'].paginator.count, 6)

    def test_uc2_1_basic_ke_toan_nhan_vien_chi_thay_active_va_it_cot(self):
        for nguoi in (self.kt, self.nv):
            self.vao(nguoi)
            r = self.client.get(self.url)
            self.assertEqual(r.context['trang'].paginator.count, 5, nguoi)      # bỏ người đã nghỉ
            self.assertNotContains(r, 'nghi@icls.vn')
            self.assertNotContains(r, 'Số điện thoại')
            self.assertNotContains(r, 'Thêm nhân sự mới')

    def test_uc2_1_basic_tim_kiem_theo_ten_ma_va_loc(self):
        self.vao(self.ql)
        self.assertEqual(self.client.get(self.url, {'q': 'khong-co-ten-nay'}).context['trang'].paginator.count, 0)
        self.assertEqual(self.client.get(self.url, {'q': 'nv2@icls.vn'}).context['trang'].paginator.count, 1)   # tìm theo Họ tên
        self.assertEqual(self.client.get(self.url, {'q': self.nv.code}).context['trang'].paginator.count, 1)
        self.assertEqual(self.client.get(self.url, {'q': str(self.nv.id)}).context['trang'].paginator.count, 1)
        self.assertEqual(self.client.get(self.url, {'trang_thai': 'RESIGNED'}).context['trang'].paginator.count, 1)
        self.assertEqual(self.client.get(self.url, {'vi_tri': Position.MANAGER}).context['trang'].paginator.count, 2)
        self.assertEqual(self.client.get(self.url, {'loai_hinh': 'PART_TIME'}).context['trang'].paginator.count, 0)

    def test_uc2_1_basic_phan_trang_20_dong(self):
        for i in range(25):
            tao_nguoi(f'x{i}@icls.vn')
        self.vao(self.ql)
        r = self.client.get(self.url)
        self.assertEqual(len(r.context['trang']), 20)
        self.assertEqual(r.context['trang'].paginator.num_pages, 2)

    def test_uc2_1_exc_3_1_khong_co_ket_qua(self):
        self.vao(self.ql)
        r = self.client.get(self.url, {'q': 'khong-ton-tai'})
        self.assertContains(r, thong_bao.KHONG_TIM_THAY_NHAN_SU)

    def test_uc2_1_basic_bam_vao_dong_ql_mo_ho_so_ke_toan_nhan_vien_thay_lien_he(self):
        self.vao(self.ql)
        self.assertEqual(self.client.get(reverse('employees:employee_detail', args=[self.nv.pk])).status_code, 200)
        self.vao(self.kt)
        r = self.client.get(reverse('employees:employee_contact', args=[self.nv.pk]))
        self.assertContains(r, 'nv@icls.vn')
        r = self.client.get(reverse('employees:employee_contact', args=[self.kt.pk]))      # hồ sơ của chính mình → UC 2.3
        self.assertRedirects(r, reverse('employees:my_profile'))

    def test_uc2_1_exc_5_1_sua_duong_dan_xem_ho_so_chi_tiet_nguoi_khac(self):
        for nguoi in (self.kt, self.nv):
            self.vao(nguoi)
            r = self.client.get(reverse('employees:employee_detail', args=[self.nv2.pk]))
            self.assertEqual(r.status_code, 403)
            self.assertContains(r, thong_bao.KHONG_CO_QUYEN_HANH_DONG, status_code=403)

    def test_uc2_1_exc_5_1_khong_xem_lien_he_nguoi_da_nghi(self):
        self.vao(self.nv)
        self.assertEqual(self.client.get(reverse('employees:employee_contact', args=[self.nghi.pk])).status_code, 403)

    def test_uc2_1_chua_dang_nhap_bi_chuyen_ve_dang_nhap(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)


@override_settings(MEDIA_ROOT=THU_MUC_MEDIA_TAM)
class CapNhatHoSoTest(UcNhanSuCoSo):            # UC 2.2
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_MEDIA_TAM, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.url = reverse('employees:my_profile_edit')
        self.vao(self.nv)

    def _gui(self, **kw):
        du_lieu = {'phone': '0911111111', 'address': 'Đà Nẵng', 'bank_account': 'VCB – 123'}
        du_lieu.update(kw)
        return self.client.post(self.url, du_lieu)

    def test_uc2_2_basic_thong_tin_luu_ngay_giay_to_cho_duyet(self):
        r = self._gui(document_type='CERTIFICATION', document_name='TOPIK 6', issue_date='2026-01-01',
                      expiry_date='2028-01-01', file_url=tep(), follow=False)
        self.assertRedirects(r, reverse('employees:my_profile'))
        self.nv.refresh_from_db(); self.nv.user.refresh_from_db()
        self.assertEqual((self.nv.phone, self.nv.address, self.nv.bank_account), ('0911111111', 'Đà Nẵng', 'VCB – 123'))
        self.assertEqual(self.nv.user.phone, '0911111111')                      # đồng bộ users.phone
        giay_to = EmployeeDocument.objects.get(employee=self.nv, document_name='TOPIK 6')
        self.assertEqual(giay_to.status, DocumentStatus.PENDING)
        self.assertTrue(Notification.objects.filter(recipient=self.ql.user, title=thong_bao.TB_CHO_DUYET_TIEU_DE).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.sa).exists())   # NV gửi → báo Quản lý, không báo SA
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', model_name='Employee', object_id=self.nv.pk).exists())

    def test_uc2_2_basic_thong_bao_thanh_cong_co_cau_cho_duyet(self):
        r = self.client.post(self.url, {'phone': '0911111111', 'document_type': 'OTHER', 'document_name': 'Khác',
                                        'file_url': tep()}, follow=True)
        self.assertContains(r, thong_bao.CAP_NHAT_HO_SO_THANH_CONG)

    def test_uc2_2_basic_khong_tai_giay_to_thi_chi_luu_thong_tin(self):
        r = self.client.post(self.url, {'phone': '0911111111'}, follow=True)
        self.assertContains(r, thong_bao.CAP_NHAT_HO_SO_KHONG_GIAY_TO)
        self.assertEqual(EmployeeDocument.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_uc2_2_basic_quan_ly_gui_thi_bao_super_admin(self):
        self.vao(self.ql)
        self.client.post(self.url, {'phone': '0911111111', 'document_type': 'OTHER', 'document_name': 'Khác', 'file_url': tep()})
        self.assertTrue(Notification.objects.filter(recipient=self.sa, title=thong_bao.TB_CHO_DUYET_TIEU_DE).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.ql2.user).exists())     # QL không duyệt QL

    def test_uc2_2_alt_1_1_tai_ban_moi_cap_nhat_chinh_ban_ghi_cu(self):
        cu = tao_giay_to(self.nv, 'TOPIK 5', DocumentStatus.REJECTED, rejection_reason='Mờ', reviewed_by=self.ql.user)
        r = self.client.post(self.url, {'phone': '0911111111', 'giay_to_id': cu.pk, 'issue_date': '2026-05-01',
                                        'expiry_date': '2029-05-01', 'file_url': tep('moi.pdf')})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(EmployeeDocument.objects.count(), 1)                    # không tạo bản ghi mới (Q15)
        cu.refresh_from_db()
        self.assertEqual((cu.status, cu.rejection_reason, cu.reviewed_by), (DocumentStatus.PENDING, '', None))
        self.assertEqual(cu.expiry_date, date(2029, 5, 1))
        self.assertEqual(cu.document_name, 'TOPIK 5')
        self.assertTrue(Notification.objects.filter(recipient=self.ql.user).exists())

    def test_uc2_2_alt_1_1_khong_tai_lai_giay_to_cua_nguoi_khac(self):
        cua_nguoi_khac = tao_giay_to(self.nv2, 'Của NV2', DocumentStatus.REJECTED)
        r = self.client.get(self.url, {'tai_lai': cua_nguoi_khac.pk})
        self.assertIsNone(r.context['giay_to_tai_lai'])

    def test_uc2_2_exc_3_1_sdt_sai_dinh_dang(self):
        r = self._gui(phone='123')
        self.assertContains(r, thong_bao.SDT_SAI_DINH_DANG)
        self.nv.refresh_from_db()
        self.assertNotEqual(self.nv.address, 'Đà Nẵng')

    def test_uc2_2_exc_3_1_thieu_truong_bat_buoc_cua_giay_to(self):
        r = self._gui(document_name='Chỉ có tên')
        self.assertContains(r, thong_bao.THIEU_TRUONG_GIAY_TO)
        self.assertEqual(EmployeeDocument.objects.count(), 0)

    def test_uc2_2_exc_3_2_file_khong_hop_le(self):
        for tep_xau in (tep('a.exe', loai='application/octet-stream'), tep('a.pdf', 5 * 1024 * 1024 + 1)):
            r = self._gui(document_type='OTHER', document_name='Khác', file_url=tep_xau)
            self.assertContains(r, thong_bao.FILE_KHONG_HOP_LE)
        self.assertEqual(EmployeeDocument.objects.count(), 0)

    def test_uc2_2_exc_3_3_ngay_het_han_truoc_ngay_cap(self):
        r = self._gui(document_type='OTHER', document_name='Khác', issue_date='2026-05-01', expiry_date='2026-04-01',
                      file_url=tep())
        self.assertContains(r, thong_bao.NGAY_HET_HAN_SAI)
        self.assertEqual(EmployeeDocument.objects.count(), 0)

    def test_uc2_2_super_admin_khong_co_ho_so(self):
        self.vao(self.sa)
        self.assertContains(self.client.get(self.url), thong_bao.KHONG_CO_HO_SO)


class XemHoSoCaNhanTest(UcNhanSuCoSo):          # UC 2.3
    def test_uc2_3_basic_hien_thi_day_du(self):
        Contract.objects.create(employee=self.nv, contract_number='HD-77', employment_type='FULL_TIME',
                                start_date=date(2026, 1, 1), file_url='contracts/x.pdf')
        LeaveBalance.objects.create(employee=self.nv, year=HOM_NAY.year, total_days=12, used_days=2)
        tao_giay_to(self.nv, 'TOPIK 5', DocumentStatus.REJECTED, rejection_reason='Ảnh mờ')
        self.vao(self.nv)
        r = self.client.get(reverse('employees:my_profile'))
        self.assertContains(r, 'HD-77')
        self.assertContains(r, 'TOPIK 5')
        self.assertContains(r, 'Ảnh mờ')                            # lý do từ chối
        self.assertContains(r, '10')                                # 12 − 2 ngày phép còn lại
        self.assertContains(r, self.nv.get_work_shift_display())    # ca làm việc (Full-time)

    def test_uc2_3_chi_xem_du_lieu_cua_chinh_minh(self):
        tao_giay_to(self.nv2, 'Bí mật của NV2')
        self.vao(self.nv)
        self.assertNotContains(self.client.get(reverse('employees:my_profile')), 'Bí mật của NV2')

    def test_uc2_3_exc_4_1_chua_co_hop_dong_giay_to(self):
        self.vao(self.nv)
        r = self.client.get(reverse('employees:my_profile'))
        self.assertContains(r, thong_bao.CHUA_CAP_NHAT)

    def test_uc2_3_exc_1_1_super_admin_khong_co_ho_so(self):
        self.vao(self.sa)
        self.assertContains(self.client.get(reverse('employees:my_profile')), thong_bao.KHONG_CO_HO_SO)

    def test_uc2_3_menu_ho_so_khong_hien_voi_super_admin(self):
        self.vao(self.sa)
        self.assertNotContains(self.client.get(reverse('dashboard:dashboard')), reverse('employees:my_profile'))
        self.vao(self.nv)
        self.assertContains(self.client.get(reverse('dashboard:dashboard')), reverse('employees:my_profile'))


class CanhBaoGiayToTest(UcNhanSuCoSo):          # UC 2.4
    def setUp(self):
        super().setUp()
        self.sap = tao_giay_to(self.nv, 'Sắp hết hạn', het_han=HOM_NAY + timedelta(days=10))
        self.het = tao_giay_to(self.nv2, 'Đã hết hạn', het_han=HOM_NAY - timedelta(days=1))
        self.con_han = tao_giay_to(self.nv, 'Còn hạn lâu', het_han=HOM_NAY + timedelta(days=200))
        self.vao(self.ql)
        self.url = reverse('employees:document_alerts')

    def test_uc2_4_basic_hien_thi_hai_muc_va_nhac_nho(self):
        r = self.client.get(self.url)
        muc = {g.document_name: m for g, m in r.context['canh_bao']}
        self.assertEqual(muc, {'Sắp hết hạn': 'EXPIRING', 'Đã hết hạn': 'EXPIRED'})      # giấy tờ còn hạn lâu không có
        r = self.client.post(reverse('employees:document_remind', args=[self.sap.pk]), follow=True)
        self.assertContains(r, thong_bao.DA_NHAC_NHO)
        tb = Notification.objects.get(recipient=self.nv.user)
        self.assertEqual(tb.message, 'Giấy tờ Sắp hết hạn sắp hết hạn, vui lòng tải bản mới tại Hồ sơ của tôi.')
        self.assertTrue(ActivityLog.objects.filter(action='REMIND', object_id=self.sap.pk, user=self.ql.user).exists())

    def test_uc2_4_basic_nhac_nho_giay_to_da_het_han(self):
        self.client.post(reverse('employees:document_remind', args=[self.het.pk]))
        self.assertIn('đã hết hạn', Notification.objects.get(recipient=self.nv2.user).message)

    def test_uc2_4_basic_loc_theo_muc_do_va_nhan_su(self):
        self.assertEqual(len(self.client.get(self.url, {'muc': 'EXPIRED'}).context['canh_bao']), 1)
        self.assertEqual(len(self.client.get(self.url, {'q': 'nv2'}).context['canh_bao']), 1)

    def test_uc2_4_basic_giay_to_trang_thai_expired_cung_duoc_liet_ke(self):
        tao_giay_to(self.nv, 'Đã đánh dấu EXPIRED', DocumentStatus.EXPIRED, het_han=HOM_NAY - timedelta(days=40))
        self.assertEqual(len(self.client.get(self.url).context['canh_bao']), 3)

    def test_uc2_4_exc_1_1_khong_co_canh_bao(self):
        EmployeeDocument.objects.all().delete()
        self.assertContains(self.client.get(self.url), thong_bao.HIEN_KHONG_CO_CANH_BAO)

    def test_uc2_4_phan_quyen_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt, self.nv):
            self.vao(nguoi)
            self.assertEqual(self.client.get(self.url).status_code, 403, nguoi)
            self.assertEqual(self.client.post(reverse('employees:document_remind', args=[self.sap.pk])).status_code, 403)


class OnboardingTest(UcNhanSuCoSo):             # UC 2.5
    def setUp(self):
        super().setUp()
        self.vao(self.ql)
        self.url = reverse('employees:employee_add')

    def _du_lieu(self, **kw):
        du_lieu = {'full_name': 'Nguyễn Mới', 'email': 'moi@icls.vn', 'phone': '0912345678', 'gender': 'FEMALE',
                   'date_of_birth': '1999-05-05', 'id_card_number': '079099000111', 'address': 'Đà Nẵng',
                   'nationality': 'Việt Nam', 'department': 'ACADEMIC', 'position': 'TEACHER',
                   'employment_type': 'FULL_TIME', 'work_shift': 'SHIFT_2', 'join_date': '2026-11-01',
                   'bank_account': 'VCB – 999'}
        du_lieu.update(kw)
        return du_lieu

    def _ung_vien(self, trang_thai=CandidateStatus.PASSED, email='uv@x.vn'):
        dot = RecruitmentCampaign.objects.get_or_create(campaign_name='Q4', defaults={'start_date': HOM_NAY})[0]
        return Candidate.objects.create(campaign=dot, full_name='Ứng Viên', email=email, phone='0900000001',
                                        position='TEACHER', employment_type='FULL_TIME', status=trang_thai)

    def test_uc2_5_basic_tao_ho_so_full_time(self):
        r = self.client.post(self.url, self._du_lieu(), follow=True)
        moi = Employee.objects.get(user__email='moi@icls.vn')
        self.assertRedirects(r, reverse('employees:employee_detail', args=[moi.pk]))
        self.assertContains(r, thong_bao.TAO_HO_SO_THANH_CONG)
        self.assertEqual((moi.status, moi.user.role, moi.work_shift), (EmployeeStatus.ONBOARDING, UserRole.EMPLOYEE, 'SHIFT_2'))
        self.assertFalse(moi.user.has_usable_password())                           # chưa có mật khẩu (Q4)
        self.assertEqual(moi.user.phone, '0912345678')
        quy = LeaveBalance.objects.get(employee=moi)                                # Full-time: quỹ phép 12 ngày
        self.assertEqual((quy.year, quy.total_days), (HOM_NAY.year, 12))
        self.assertEqual(len(mail.outbox), 1)                                       # email đường dẫn đặt mật khẩu
        self.assertEqual(mail.outbox[0].to, ['moi@icls.vn'])
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='Employee', object_id=moi.pk).exists())

    def test_uc2_5_basic_part_time_khong_co_quy_phep(self):
        self.client.post(self.url, self._du_lieu(employment_type='PART_TIME', work_shift='', position='STAFF'))
        moi = Employee.objects.get(user__email='moi@icls.vn')
        self.assertFalse(LeaveBalance.objects.filter(employee=moi).exists())        # Q11

    def test_uc2_5_basic_vi_tri_quan_ly_ke_toan_bao_super_admin(self):
        self.client.post(self.url, self._du_lieu(position='MANAGER'))
        moi = Employee.objects.get(user__email='moi@icls.vn')
        self.assertEqual(moi.user.role, UserRole.EMPLOYEE)                          # Q3: QL không tự cấp quyền
        tb = Notification.objects.get(recipient=self.sa)
        self.assertEqual(tb.title, thong_bao.TB_CAP_QUYEN_TIEU_DE)
        self.assertEqual(tb.related_url, reverse('accounts:user_change_role', args=[moi.user.pk]))

    def test_uc2_5_basic_vi_tri_thuong_khong_bao_super_admin(self):
        self.client.post(self.url, self._du_lieu())
        self.assertFalse(Notification.objects.filter(recipient=self.sa).exists())

    def test_uc2_5_basic_tu_ung_vien_passed(self):
        uv = self._ung_vien()
        r = self.client.get(self.url, {'ung_vien': uv.pk})
        self.assertEqual(r.context['form'].initial['email'], 'uv@x.vn')             # tự điền từ ứng viên
        self.client.post(self.url, self._du_lieu(email='uv@x.vn', ung_vien=uv.pk))
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.HIRED)
        self.assertEqual(Employee.objects.get(user__email='uv@x.vn').candidate, uv)

    def test_uc2_5_alt_1_1_sua_ho_so_khong_doi_email_va_loai_hinh(self):
        nv = self.nv
        r = self.client.post(reverse('employees:employee_edit', args=[nv.pk]), self._du_lieu(
            full_name='Tên Đã Sửa', email='hack@icls.vn', employment_type='PART_TIME', work_shift='SHIFT_2',
            id_card_number='079099000222'), follow=True)
        self.assertContains(r, thong_bao.CAP_NHAT_HO_SO_NHAN_SU_THANH_CONG)
        nv.refresh_from_db(); nv.user.refresh_from_db()
        self.assertEqual((nv.full_name, nv.work_shift), ('Tên Đã Sửa', 'SHIFT_2'))
        self.assertEqual(nv.user.email, 'nv@icls.vn')                              # Email không đổi
        self.assertEqual(nv.employment_type, 'FULL_TIME')                           # Loại hình không đổi
        self.assertEqual((nv.user.full_name, nv.user.phone), ('Tên Đã Sửa', '0912345678'))   # đồng bộ users
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', object_id=nv.pk, user=self.ql.user).exists())

    def test_uc2_5_alt_3_1_huy_khong_luu(self):
        r = self.client.get(self.url)
        self.assertContains(r, reverse('employees:employee_list'))                  # nút Hủy quay về danh sách
        self.assertEqual(User.objects.filter(email='moi@icls.vn').count(), 0)

    def test_uc2_5_exc_3_2_email_hoac_cccd_da_ton_tai(self):
        r = self.client.post(self.url, self._du_lieu(email='NV@icls.vn'))
        self.assertContains(r, thong_bao.EMAIL_HOAC_CCCD_TON_TAI)
        self.nv.id_card_number = '079099000333'
        self.nv.save()
        r = self.client.post(self.url, self._du_lieu(id_card_number='079099000333'))
        self.assertContains(r, thong_bao.EMAIL_HOAC_CCCD_TON_TAI)
        self.assertEqual(User.objects.filter(email='moi@icls.vn').count(), 0)

    def test_uc2_5_exc_3_3_thieu_truong_bat_buoc_hoac_sai_dinh_dang(self):
        r = self.client.post(self.url, self._du_lieu(full_name='', position='', join_date=''))
        for ten in ('full_name', 'position', 'join_date'):
            self.assertIn(ten, r.context['form'].errors)
        r = self.client.post(self.url, self._du_lieu(phone='abc', id_card_number='12'))
        self.assertContains(r, thong_bao.SDT_SAI_DINH_DANG)
        self.assertContains(r, thong_bao.CCCD_SAI_DINH_DANG)
        self.assertFalse(Employee.objects.filter(user__email='moi@icls.vn').exists())

    def test_uc2_5_ca_lam_viec_bat_buoc_voi_full_time_va_de_trong_voi_part_time(self):
        r = self.client.post(self.url, self._du_lieu(work_shift=''))
        self.assertContains(r, thong_bao.CAN_CHON_CA_FULL_TIME)
        r = self.client.post(self.url, self._du_lieu(employment_type='PART_TIME', work_shift='SHIFT_1'))
        self.assertContains(r, thong_bao.PART_TIME_KHONG_CO_CA)

    def test_uc2_5_exc_1_2_ung_vien_da_duoc_tiep_nhan(self):
        uv = self._ung_vien()
        self.client.post(self.url, self._du_lieu(email='uv@x.vn', ung_vien=uv.pk))
        da_co = Employee.objects.get(candidate=uv)
        r = self.client.get(self.url, {'ung_vien': uv.pk}, follow=True)
        self.assertRedirects(r, reverse('employees:employee_detail', args=[da_co.pk]))   # kèm liên kết tới hồ sơ hiện có
        self.assertContains(r, thong_bao.UNG_VIEN_DA_TIEP_NHAN)
        r = self.client.post(self.url, self._du_lieu(email='khac@x.vn', ung_vien=uv.pk), follow=True)
        self.assertEqual(Employee.objects.filter(candidate=uv).count(), 1)             # không tạo lần hai

    def test_uc2_5_chi_tiep_nhan_ung_vien_da_dat(self):
        uv = self._ung_vien(CandidateStatus.SCREENING)
        r = self.client.get(self.url, {'ung_vien': uv.pk}, follow=True)
        self.assertContains(r, thong_bao.CHI_TIEP_NHAN_UNG_VIEN_DAT)

    def test_uc2_5_giao_dich_loi_giua_chung_thi_khong_luu_gi(self):
        """Ứng viên chưa PASSED → danh_dau_da_tuyen báo lỗi ở bước cuối; users và employees đã tạo phải được hoàn tác."""
        uv = self._ung_vien(CandidateStatus.REJECTED)
        du_lieu = self._du_lieu()
        with self.assertRaises(Exception):
            services.tao_ho_so_nhan_su(self.ql.user, {k: v for k, v in du_lieu.items()
                                                      if k not in ('date_of_birth', 'join_date', 'gender')} | {
                'join_date': HOM_NAY, 'gender': '', 'date_of_birth': None, 'id_card_number': None}, ung_vien=uv)
        self.assertEqual(User.objects.filter(email='moi@icls.vn').count(), 0)
        self.assertEqual(Employee.objects.filter(candidate=uv).count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_uc2_5_phan_quyen_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt, self.nv):
            self.vao(nguoi)
            self.assertEqual(self.client.get(self.url).status_code, 403, nguoi)
            self.assertEqual(self.client.get(reverse('employees:employee_edit', args=[self.nv.pk])).status_code, 403)


class DuyetGiayToTest(UcNhanSuCoSo):            # UC 2.6
    def setUp(self):
        super().setUp()
        self.gt_nv = tao_giay_to(self.nv, 'Của NV', DocumentStatus.PENDING)
        self.gt_kt = tao_giay_to(self.kt, 'Của KT', DocumentStatus.PENDING)
        self.gt_ql = tao_giay_to(self.ql, 'Của QL', DocumentStatus.PENDING)
        self.gt_ql2 = tao_giay_to(self.ql2, 'Của QL2', DocumentStatus.PENDING)

    def _url(self, giay_to):
        return reverse('employees:document_review', args=[giay_to.pk])

    def test_uc2_6_basic_quan_ly_duyet(self):
        self.vao(self.ql)
        r = self.client.post(self._url(self.gt_nv), {'hanh_dong': 'duyet'}, follow=True)
        self.assertContains(r, thong_bao.DA_DUYET_GIAY_TO)
        self.gt_nv.refresh_from_db()
        self.assertEqual((self.gt_nv.status, self.gt_nv.reviewed_by, self.gt_nv.rejection_reason),
                         (DocumentStatus.APPROVED, self.ql.user, ''))
        self.assertIsNotNone(self.gt_nv.reviewed_at)
        self.assertTrue(Notification.objects.filter(recipient=self.nv.user, title=thong_bao.TB_DA_DUYET_TIEU_DE).exists())
        self.assertTrue(ActivityLog.objects.filter(action='APPROVE', object_id=self.gt_nv.pk).exists())

    def test_uc2_6_alt_5_1_tu_choi_kem_ly_do(self):
        self.vao(self.ql)
        self.client.post(self._url(self.gt_kt), {'hanh_dong': 'tu_choi', 'ly_do': 'Ảnh mờ'})
        self.gt_kt.refresh_from_db()
        self.assertEqual((self.gt_kt.status, self.gt_kt.rejection_reason), (DocumentStatus.REJECTED, 'Ảnh mờ'))
        tb = Notification.objects.get(recipient=self.kt.user)
        self.assertIn('Ảnh mờ', tb.message)
        self.assertTrue(ActivityLog.objects.filter(action='REJECT', object_id=self.gt_kt.pk).exists())

    def test_uc2_6_exc_5_2_tu_choi_khong_nhap_ly_do(self):
        self.vao(self.ql)
        r = self.client.post(self._url(self.gt_nv), {'hanh_dong': 'tu_choi', 'ly_do': '   '})
        self.assertContains(r, thong_bao.VUI_LONG_NHAP_LY_DO_TU_CHOI)
        self.gt_nv.refresh_from_db()
        self.assertEqual(self.gt_nv.status, DocumentStatus.PENDING)

    def test_uc2_6_exc_3_1_da_duoc_nguoi_khac_xu_ly(self):
        self.vao(self.ql)
        EmployeeDocument.objects.filter(pk=self.gt_nv.pk).update(status=DocumentStatus.APPROVED)
        r = self.client.get(self._url(self.gt_nv), follow=True)
        self.assertRedirects(r, reverse('employees:pending_documents'))
        self.assertContains(r, thong_bao.YEU_CAU_DA_XU_LY)

    def test_uc2_6_exc_3_1_hai_nguoi_cung_bam_chi_mot_nguoi_duoc(self):
        """Giả lập: giấy tờ vừa bị người khác xử lý ngay sau khi trang được mở."""
        with self.assertRaises(Exception) as ngoai_le:
            giay_to = EmployeeDocument.objects.get(pk=self.gt_nv.pk)
            EmployeeDocument.objects.filter(pk=giay_to.pk).update(status=DocumentStatus.APPROVED)   # người thứ nhất
            services.duyet_giay_to(self.ql.user, giay_to)                                            # người thứ hai
        self.assertEqual(str(ngoai_le.exception), thong_bao.YEU_CAU_DA_XU_LY)

    def test_uc2_6_phan_cap_q2_khong_tu_duyet_va_ql_khong_duyet_ql(self):
        self.vao(self.ql)
        r = self.client.post(self._url(self.gt_ql), {'hanh_dong': 'duyet'})            # giấy tờ của chính mình
        self.assertEqual(r.status_code, 403)
        r = self.client.post(self._url(self.gt_ql2), {'hanh_dong': 'duyet'})           # QL không duyệt giấy tờ của QL khác
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, thong_bao.KHONG_CO_QUYEN_HANH_DONG, status_code=403)
        for g in (self.gt_ql, self.gt_ql2):
            g.refresh_from_db()
            self.assertEqual(g.status, DocumentStatus.PENDING)

    def test_uc2_6_phan_cap_q2_super_admin_chi_duyet_giay_to_cua_quan_ly(self):
        self.vao(self.sa)
        self.assertEqual(self.client.post(self._url(self.gt_ql), {'hanh_dong': 'duyet'}).status_code, 302)
        self.assertEqual(self.client.post(self._url(self.gt_nv), {'hanh_dong': 'duyet'}).status_code, 403)
        self.gt_ql.refresh_from_db()
        self.assertEqual(self.gt_ql.status, DocumentStatus.APPROVED)

    def test_uc2_6_danh_sach_theo_pham_vi(self):
        self.vao(self.ql)
        ten = {g.document_name for g in self.client.get(reverse('employees:pending_documents')).context['giay_to']}
        self.assertEqual(ten, {'Của NV', 'Của KT'})                                    # không có của QL (kể cả của mình)
        self.vao(self.sa)
        ten = {g.document_name for g in self.client.get(reverse('employees:pending_documents')).context['giay_to']}
        self.assertEqual(ten, {'Của QL', 'Của QL2'})

    def test_uc2_6_phan_quyen_ke_toan_nhan_vien_bi_chan(self):
        for nguoi in (self.kt, self.nv):
            self.vao(nguoi)
            self.assertEqual(self.client.get(reverse('employees:pending_documents')).status_code, 403, nguoi)
            self.assertEqual(self.client.get(self._url(self.gt_nv)).status_code, 403)


# ============================================================ UC 9.2 – bước 2: giấy tờ hết hạn / nhắc hạn (P10)
class TacVuNgayGiayToTest(TestCase):
    """`het_han_giay_to`, `nhac_han_giay_to` do dashboard gọi mỗi ngày (§11 P10). Hôm nay giả định 27/10/2026."""
    HOM_NAY = date(2026, 10, 27)

    def setUp(self):
        from core.mau_test import tao_nhan_su_hoat_dong
        self.nv = tao_nhan_su_hoat_dong('nv@icls.vn')
        self.ql = tao_nhan_su_hoat_dong('ql@icls.vn', UserRole.MANAGER, Position.MANAGER)

    def giay_to(self, so_ngay_con_lai, trang_thai=DocumentStatus.APPROVED, ten='TOPIK 5'):
        return EmployeeDocument.objects.create(
            employee=self.nv, document_type='CERTIFICATION', document_name=ten, issue_date=date(2026, 1, 1),
            expiry_date=self.HOM_NAY + timedelta(days=so_ngay_con_lai), file_url='x.pdf', status=trang_thai)

    def test_het_han_chuyen_approved_qua_han_sang_expired(self):
        from employees import services
        qua_han = self.giay_to(-1)
        con_han = self.giay_to(0, ten='Hôm nay còn hiệu lực')       # hết hạn HÔM NAY vẫn còn dùng được
        cho_duyet = self.giay_to(-5, DocumentStatus.PENDING, 'Chưa duyệt')
        self.assertEqual(services.het_han_giay_to(self.HOM_NAY), 1)
        for g in (qua_han, con_han, cho_duyet):
            g.refresh_from_db()
        self.assertEqual(qua_han.status, DocumentStatus.EXPIRED)
        self.assertEqual(con_han.status, DocumentStatus.APPROVED)
        self.assertEqual(cho_duyet.status, DocumentStatus.PENDING)    # chỉ giấy tờ APPROVED mới bị đổi
        self.assertEqual(services.het_han_giay_to(self.HOM_NAY), 0)    # chạy lại: không còn gì để đổi

    def test_nhac_dung_cac_moc_30_7_0_cho_nhan_su_va_quan_ly(self):
        from core.models import Notification
        from employees import services
        for so_ngay in (30, 7, 0, 15):                                 # 15 ngày không phải mốc
            self.giay_to(so_ngay, ten=f'GT{so_ngay}')
        self.assertEqual(services.nhac_han_giay_to(self.HOM_NAY), 6)   # 3 mốc × (1 nhân sự + 1 Quản lý)
        self.assertEqual(Notification.objects.filter(recipient=self.nv.user).count(), 3)
        self.assertEqual(Notification.objects.filter(recipient=self.ql.user).count(), 3)
        self.assertFalse(Notification.objects.filter(message__contains='GT15').exists())

    def test_chay_lai_trong_ngay_khong_gui_trung(self):
        from employees import services
        self.giay_to(7)
        self.assertEqual(services.nhac_han_giay_to(self.HOM_NAY), 2)
        self.assertEqual(services.nhac_han_giay_to(self.HOM_NAY), 0)

    def test_khong_nhac_nguoi_da_nghi_viec_va_giay_to_chua_duyet(self):
        from employees import services
        self.giay_to(7, DocumentStatus.PENDING, 'Chưa duyệt')
        self.assertEqual(services.nhac_han_giay_to(self.HOM_NAY), 0)
        self.giay_to(7)
        self.nv.status = EmployeeStatus.RESIGNED
        self.nv.save()
        self.assertEqual(services.nhac_han_giay_to(self.HOM_NAY), 0)
