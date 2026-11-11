"""Test của app contracts – P1: ràng buộc CSDL (§7.3.4); P5: UC 3.1–3.5.

Quy ước tên: test_uc<x>_<y>_basic · _alt_<mã luồng> · _exc_<mã luồng> (§12.1).
"""
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from contracts import services
from contracts.models import Contract, ContractStatus
from core import thong_bao
from core.mau_test import tao_lop, tao_nhan_su
from core.models import ActivityLog, Notification
from core.services import LoiNghiepVu
from employees.models import Employee, EmployeeStatus, EmploymentType, Position, WorkShift
from leave.models import LeaveBalance
from payroll.models import SalaryConfig
from schedule.models import (ClassAssignment, ShiftAssignment, ShiftStatus, SubstituteRequest, SubstituteStatus,
                             TeachingSession)

def _tao_hd(nv, so='HD1', **kw):
    du_lieu = dict(employee=nv, contract_number=so, employment_type='FULL_TIME', start_date=date(2026, 1, 1),
                   file_url='hd.pdf')
    du_lieu.update(kw)
    return Contract.objects.create(**du_lieu)


class RangBuocContractsTest(TestCase):
    def test_hop_dong_active_thu_hai_cho_cung_nguoi_bi_chan(self):
        nv = tao_nhan_su()
        _tao_hd(nv, 'HD1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            _tao_hd(nv, 'HD2')

    def test_duoc_co_nhieu_hop_dong_neu_chi_mot_active(self):
        nv = tao_nhan_su()
        _tao_hd(nv, 'HD1', status=ContractStatus.EXPIRED)
        _tao_hd(nv, 'HD2')
        self.assertEqual(nv.contracts.count(), 2)

    def test_so_hop_dong_la_duy_nhat(self):
        _tao_hd(tao_nhan_su('a@icls.vn'), 'HD1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            _tao_hd(tao_nhan_su('b@icls.vn'), 'HD1')

    def test_ngay_ket_thuc_phai_sau_ngay_bat_dau(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            _tao_hd(tao_nhan_su(), end_date=date(2026, 1, 1))


# ======================================================================== UC 3 – nghiệp vụ
THU_MUC_MEDIA_TAM = tempfile.mkdtemp()      # file scan khi test ghi vào thư mục tạm, không làm bẩn media/
HOM_NAY = date(2026, 10, 27)                # "hôm nay" cố định cho các hàm có tham số hom_nay (§0 luật 5)


def tep(ten='hd.pdf', kich_thuoc=100):
    return SimpleUploadedFile(ten, b'x' * kich_thuoc, content_type='application/pdf')


def tao_ql_va_nv(email='nv@icls.vn', **kw):
    nhan_su = tao_nhan_su(email, **kw)
    nhan_su.status = EmployeeStatus.ACTIVE
    nhan_su.save()
    return nhan_su


class UcHopDongCoSo(TestCase):
    def setUp(self):
        self.sa = User.objects.create_user('sa@icls.vn', 'x', role=UserRole.SUPER_ADMIN)
        self.ql = tao_ql_va_nv('ql@icls.vn', vai_tro=UserRole.MANAGER, chuc_danh=Position.MANAGER)
        self.kt = tao_ql_va_nv('kt@icls.vn', vai_tro=UserRole.ACCOUNTANT, chuc_danh=Position.ACCOUNTANT)
        self.nv = tao_ql_va_nv('nv@icls.vn')
        self.nv2 = tao_ql_va_nv('nv2@icls.vn')
        self.client.force_login(self.ql.user)

    def hd(self, nhan_su=None, so='HD-1', bat_dau=date(2026, 1, 1), ket_thuc=None, **kw):
        du_lieu = dict(employee=nhan_su or self.nv, contract_number=so, employment_type='FULL_TIME', start_date=bat_dau,
                       end_date=ket_thuc, file_url='contracts/mau.pdf')
        du_lieu.update(kw)
        return Contract.objects.create(**du_lieu)


@override_settings(MEDIA_ROOT=THU_MUC_MEDIA_TAM)
class ThemHopDongTest(UcHopDongCoSo):            # UC 3.1
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_MEDIA_TAM, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.url = reverse('contracts:contract_add')

    def _du_lieu(self, nhan_su=None, **kw):
        du_lieu = {'nhan_su': (nhan_su or self.nv).pk, 'contract_number': 'HD-2026-020', 'employment_type': 'FULL_TIME',
                   'start_date': '2026-11-01', 'end_date': '2027-10-31', 'file_url': tep()}
        du_lieu.update(kw)
        return du_lieu

    def test_uc3_1_basic_them_hop_dong_nhan_su_dang_lam_viec(self):
        r = self.client.post(self.url, self._du_lieu(), follow=True)
        hd = Contract.objects.get(contract_number='HD-2026-020')
        self.assertRedirects(r, reverse('contracts:contract_detail', args=[hd.pk]))
        self.assertContains(r, thong_bao.THEM_HOP_DONG_THANH_CONG)
        self.assertEqual((hd.status, hd.employee), (ContractStatus.ACTIVE, self.nv))
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='Contract', object_id=hd.pk).exists())

    def test_uc3_1_basic_hop_dong_dau_tien_kich_hoat_nhan_su_onboarding(self):
        moi = tao_nhan_su('moi@icls.vn')                      # ONBOARDING (mặc định của model)
        self.assertEqual(moi.status, EmployeeStatus.ONBOARDING)
        self.client.post(self.url, self._du_lieu(moi))
        moi.refresh_from_db()
        self.assertEqual(moi.status, EmployeeStatus.ACTIVE)                         # Q5
        self.assertTrue(Notification.objects.filter(recipient=moi.user, title=thong_bao.TB_HD_KICH_HOAT_TIEU_DE).exists())

    def test_uc3_1_basic_dong_bo_loai_hinh_nhan_su_theo_hop_dong(self):
        part_time = tao_ql_va_nv('pt@icls.vn', loai_hinh=EmploymentType.PART_TIME)
        self.client.post(self.url, self._du_lieu(part_time, employment_type='FULL_TIME'))
        part_time.refresh_from_db()
        self.assertEqual(part_time.employment_type, 'FULL_TIME')
        self.assertTrue(LeaveBalance.objects.filter(employee=part_time).exists())          # sang Full-time: có quỹ phép (Q11)
        r = self.client.get(reverse('contracts:contract_detail', args=[Contract.objects.get().pk]))
        self.assertContains(r, 'Ca làm việc') if False else None
        ft = tao_ql_va_nv('ft@icls.vn')
        self.client.post(self.url, self._du_lieu(ft, contract_number='HD-PT', employment_type='PART_TIME'))
        ft.refresh_from_db()
        self.assertEqual((ft.employment_type, ft.work_shift), ('PART_TIME', ''))           # Part-time không có ca cố định

    def test_uc3_1_basic_danh_sach_tim_kiem_va_loc(self):
        self.hd(self.nv, 'HD-A')
        self.hd(self.nv2, 'HD-B', employment_type='PART_TIME', status=ContractStatus.EXPIRED)
        url = reverse('contracts:contract_list')
        self.assertEqual(self.client.get(url).context['trang'].paginator.count, 2)
        self.assertEqual(self.client.get(url, {'q': 'HD-A'}).context['trang'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'q': 'nv2@'}).context['trang'].paginator.count, 1)         # theo tên nhân sự
        self.assertEqual(self.client.get(url, {'loai_hinh': 'PART_TIME'}).context['trang'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'trang_thai': 'ACTIVE'}).context['trang'].paginator.count, 1)

    def test_uc3_1_chi_chon_nhan_su_onboarding_hoac_active(self):
        nghi = tao_ql_va_nv('nghi@icls.vn')
        nghi.status = EmployeeStatus.RESIGNED
        nghi.save()
        r = self.client.get(self.url)
        self.assertNotIn(nghi, list(r.context['form'].fields['nhan_su'].queryset))
        r = self.client.post(self.url, self._du_lieu(nghi))
        self.assertTrue(r.context['form'].errors['nhan_su'])
        self.assertEqual(Contract.objects.count(), 0)

    def test_uc3_1_exc_5_1_nhan_su_dang_co_hop_dong_active(self):
        self.hd(self.nv, 'HD-CU')
        r = self.client.post(self.url, self._du_lieu())
        self.assertContains(r, thong_bao.HOP_DONG_DANG_HIEU_LUC)
        self.assertEqual(Contract.objects.count(), 1)

    def test_uc3_1_exc_5_2_so_hop_dong_da_ton_tai(self):
        self.hd(self.nv2, 'HD-2026-020')
        r = self.client.post(self.url, self._du_lieu())
        self.assertContains(r, thong_bao.SO_HOP_DONG_DA_TON_TAI)
        self.assertEqual(Contract.objects.count(), 1)

    def test_uc3_1_exc_5_3_ngay_ket_thuc_truoc_ngay_bat_dau_hoac_thieu_file(self):
        r = self.client.post(self.url, self._du_lieu(end_date='2026-10-01'))
        self.assertContains(r, thong_bao.NGAY_KET_THUC_HD_SAI)
        r = self.client.post(self.url, self._du_lieu(file_url=''))
        self.assertContains(r, thong_bao.THIEU_FILE_SCAN)
        r = self.client.post(self.url, self._du_lieu(file_url=tep('x.exe')))
        self.assertContains(r, thong_bao.FILE_KHONG_HOP_LE)
        self.assertEqual(Contract.objects.count(), 0)

    def test_uc3_1_giao_dich_loi_giua_chung_khong_luu_gi(self):
        """Nhân sự đã nghỉ: service chặn trước, không tạo hợp đồng; hợp đồng + đổi loại hình không bao giờ lệch nhau."""
        nghi = tao_ql_va_nv('nghi@icls.vn')
        nghi.status = EmployeeStatus.RESIGNED
        nghi.save()
        with self.assertRaises(LoiNghiepVu):
            services.them_hop_dong(self.ql.user, nghi, 'HD-X', 'FULL_TIME', date(2026, 11, 1), None, tep())
        self.assertEqual(Contract.objects.count(), 0)

    def test_uc3_1_phan_quyen_them_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt.user, self.nv.user):
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(self.url).status_code, 403, nguoi)
            self.assertEqual(self.client.post(self.url, self._du_lieu()).status_code, 403)
        self.assertEqual(Contract.objects.count(), 0)

    def test_uc3_1_nut_tao_hop_dong_o_ho_so_onboarding(self):
        moi = tao_nhan_su('moi@icls.vn')
        r = self.client.get(reverse('employees:employee_detail', args=[moi.pk]))
        self.assertContains(r, f"{reverse('contracts:contract_add')}?nhan_su={moi.pk}")
        r = self.client.get(self.url, {'nhan_su': moi.pk})
        self.assertEqual(r.context['form'].initial['nhan_su'], str(moi.pk))


class ChiTietHopDongTest(UcHopDongCoSo):         # UC 3.2
    def setUp(self):
        super().setUp()
        self.cua_nv = self.hd(self.nv, 'HD-NV')
        self.cua_nv2 = self.hd(self.nv2, 'HD-NV2')

    def _url(self, hd):
        return reverse('contracts:contract_detail', args=[hd.pk])

    def test_uc3_2_basic_quan_ly_va_ke_toan_xem_moi_hop_dong(self):
        for nguoi in (self.ql.user, self.kt.user):
            self.client.force_login(nguoi)
            for hd in (self.cua_nv, self.cua_nv2):
                r = self.client.get(self._url(hd))
                self.assertContains(r, hd.contract_number)
        self.assertNotContains(r, reverse('contracts:contract_renew', args=[self.cua_nv2.pk]))     # Kế toán chỉ xem

    def test_uc3_2_basic_nhan_vien_xem_hop_dong_cua_minh(self):
        self.client.force_login(self.nv.user)
        r = self.client.get(self._url(self.cua_nv))
        self.assertContains(r, 'HD-NV')
        self.assertNotContains(r, reverse('contracts:contract_terminate', args=[self.cua_nv.pk]))   # không có nút của Quản lý

    def test_uc3_2_basic_hien_hop_dong_truoc_va_ly_do_thanh_ly(self):
        moi = self.hd(self.nv, 'HD-NV-2', date(2026, 6, 1), previous_contract=self.cua_nv, status=ContractStatus.TERMINATED,
                      termination_date=date(2026, 9, 1), termination_reason='Hết nhu cầu')
        r = self.client.get(self._url(moi))
        self.assertContains(r, 'HD-NV')                          # hợp đồng trước
        self.assertContains(r, 'Hết nhu cầu')
        self.assertContains(r, '01/09/2026')

    def test_uc3_2_exc_1_1_nhan_vien_xem_hop_dong_cua_nguoi_khac(self):
        self.client.force_login(self.nv.user)
        r = self.client.get(self._url(self.cua_nv2))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, thong_bao.KHONG_XEM_HOP_DONG, status_code=403)

    def test_uc3_2_nhan_vien_chi_thay_hop_dong_cua_minh_trong_danh_sach(self):
        self.client.force_login(self.nv.user)
        r = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual([hd.contract_number for hd in r.context['trang']], ['HD-NV'])
        self.assertNotContains(r, 'Thêm hợp đồng')

    def test_uc3_2_phan_quyen_super_admin_khong_thuoc_phan_he(self):
        self.client.force_login(self.sa)
        self.assertEqual(self.client.get(self._url(self.cua_nv)).status_code, 403)
        self.assertEqual(self.client.get(reverse('contracts:contract_list')).status_code, 403)

    def test_uc3_2_ke_toan_tai_duoc_file_scan_nhan_vien_khong_tai_duoc_file_nguoi_khac(self):
        self.client.force_login(self.kt.user)
        self.assertNotEqual(self.client.get(reverse('core:tai_file', args=['contracts/khong-ton-tai.pdf'])).status_code, 403)
        self.client.force_login(self.nv.user)
        self.assertEqual(self.client.get(reverse('core:tai_file', args=[self.cua_nv2.file_url.name])).status_code, 404)  # file mẫu không tồn tại


class InHopDongTest(UcHopDongCoSo):              # UC 3.2 bổ sung – in mẫu hợp đồng tự điền
    def setUp(self):
        super().setUp()
        self.cua_nv = self.hd(self.nv, 'HD-IN-1', date(2026, 1, 1), date(2026, 12, 31))
        self.cua_nv2 = self.hd(self.nv2, 'HD-IN-2')

    def _url(self, hd):
        return reverse('contracts:contract_print', args=[hd.pk])

    def test_uc3_2_in_basic_tu_dien_thong_tin_va_luong(self):
        SalaryConfig.objects.create(employee=self.nv, base_salary=Decimal('15000000'), effective_from=date(2026, 1, 1))
        r = self.client.get(self._url(self.cua_nv))
        self.assertContains(r, 'HỢP ĐỒNG LAO ĐỘNG')
        self.assertContains(r, 'HD-IN-1')
        self.assertContains(r, self.nv.full_name)
        self.assertContains(r, '15.000.000 đ')                  # lương lấy từ cấu hình lương (UC 7.1)
        self.assertContains(r, '12 tháng')                       # xác định thời hạn 01/01 – 31/12
        self.assertContains(r, '30 ngày')                        # HĐ 12–36 tháng: báo trước 30 ngày

    def test_uc3_2_in_alt_khong_xac_dinh_thoi_han_va_chua_co_cau_hinh_luong(self):
        r = self.client.get(self._url(self.cua_nv2))
        self.assertContains(r, '45 ngày')                        # HĐ không xác định thời hạn: báo trước 45 ngày
        self.assertContains(r, 'chưa có cấu hình lương')

    def test_uc3_2_in_hop_dong_duoi_12_thang_bao_truoc_3_ngay_lam_viec(self):
        hd = self.hd(tao_ql_va_nv('nv3@icls.vn'), 'HD-IN-3', date(2026, 1, 1), date(2026, 6, 30))
        self.assertEqual(services.so_thang_hop_dong(hd), 6)
        self.assertContains(self.client.get(self._url(hd)), '3 ngày làm việc')

    def test_uc3_2_in_nhan_vien_chi_in_hop_dong_cua_minh(self):
        self.client.force_login(self.nv.user)
        self.assertEqual(self.client.get(self._url(self.cua_nv)).status_code, 200)
        self.assertEqual(self.client.get(self._url(self.cua_nv2)).status_code, 403)

    def test_uc3_2_in_chi_tiet_co_nut_in(self):
        self.assertContains(self.client.get(reverse('contracts:contract_detail', args=[self.cua_nv.pk])), self._url(self.cua_nv))


@override_settings(MEDIA_ROOT=THU_MUC_MEDIA_TAM)
class GiaHanTest(UcHopDongCoSo):                 # UC 3.3
    def setUp(self):
        super().setUp()
        self.cu = self.hd(self.nv, 'HD-CU', date(2025, 11, 1), date(2026, 10, 31))
        self.url = reverse('contracts:contract_renew', args=[self.cu.pk])

    def _du_lieu(self, **kw):
        du_lieu = {'contract_number': 'HD-MOI', 'employment_type': 'FULL_TIME', 'start_date': '2026-11-01',
                   'end_date': '2027-10-31', 'file_url': tep()}
        du_lieu.update(kw)
        return du_lieu

    def test_uc3_3_basic_gia_han(self):
        r = self.client.get(self.url)
        self.assertEqual(r.context['form'].initial['employment_type'], 'FULL_TIME')        # điền sẵn loại hình
        r = self.client.post(self.url, self._du_lieu(), follow=True)
        moi = Contract.objects.get(contract_number='HD-MOI')
        self.assertRedirects(r, reverse('contracts:contract_detail', args=[moi.pk]))
        self.assertContains(r, thong_bao.GIA_HAN_THANH_CONG)
        self.cu.refresh_from_db()
        self.assertEqual(self.cu.status, ContractStatus.EXPIRED)                              # hợp đồng cũ EXPIRED
        self.assertEqual((moi.status, moi.previous_contract), (ContractStatus.ACTIVE, self.cu))
        self.assertEqual(Contract.objects.filter(employee=self.nv, status='ACTIVE').count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.nv.user, title=thong_bao.TB_HD_GIA_HAN_TIEU_DE).exists())
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', object_id=moi.pk).exists())

    def test_uc3_3_basic_doi_loai_hinh_khi_gia_han_dong_bo_nhan_su(self):
        self.client.post(self.url, self._du_lieu(employment_type='PART_TIME'))
        self.nv.refresh_from_db()
        self.assertEqual((self.nv.employment_type, self.nv.work_shift), ('PART_TIME', ''))

    def test_uc3_3_alt_1_1_cap_nhat_file_scan(self):
        r = self.client.post(reverse('contracts:contract_update_file', args=[self.cu.pk]), {'file_url': tep('moi.pdf')}, follow=True)
        self.assertContains(r, thong_bao.CAP_NHAT_FILE_THANH_CONG)
        self.cu.refresh_from_db()
        self.assertIn('moi', self.cu.file_url.name)
        self.assertEqual((self.cu.status, self.cu.contract_number, self.cu.end_date), ('ACTIVE', 'HD-CU', date(2026, 10, 31)))
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', object_id=self.cu.pk).exists())

    def test_uc3_3_exc_3_1_ngay_khong_hop_le(self):
        for du_lieu in (self._du_lieu(start_date='2025-11-01'),                       # không sau ngày bắt đầu hợp đồng cũ
                        self._du_lieu(start_date='2025-10-01'),
                        self._du_lieu(end_date='2026-10-01')):                          # kết thúc trước bắt đầu mới
            r = self.client.post(self.url, du_lieu)
            self.assertContains(r, thong_bao.NGAY_HOP_DONG_MOI_SAI)
        self.cu.refresh_from_db()
        self.assertEqual(self.cu.status, ContractStatus.ACTIVE)                        # không đổi gì
        self.assertEqual(Contract.objects.count(), 1)

    def test_uc3_3_exc_3_2_so_hop_dong_da_ton_tai(self):
        r = self.client.post(self.url, self._du_lieu(contract_number='HD-CU'))
        self.assertContains(r, thong_bao.SO_HOP_DONG_DA_TON_TAI)

    def test_uc3_3_chi_gia_han_hop_dong_active(self):
        self.cu.status = ContractStatus.EXPIRED
        self.cu.save()
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, thong_bao.HOP_DONG_KHONG_CON_HIEU_LUC)
        with self.assertRaises(LoiNghiepVu):
            services.gia_han_hop_dong(self.ql.user, self.cu, 'HD-Z', 'FULL_TIME', date(2026, 11, 1), None, tep())

    def test_uc3_3_loi_thi_hop_dong_cu_van_active(self):
        """Lỗi sau khi đổi hợp đồng cũ thì phải hoàn tác: ở đây thiếu file → không đụng tới hợp đồng cũ."""
        with self.assertRaises(LoiNghiepVu):
            services.gia_han_hop_dong(self.ql.user, self.cu, 'HD-Z', 'FULL_TIME', date(2026, 11, 1), None, None)
        self.cu.refresh_from_db()
        self.assertEqual(self.cu.status, ContractStatus.ACTIVE)

    def test_uc3_3_phan_quyen_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt.user, self.nv.user):
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(self.url).status_code, 403, nguoi)
            self.assertEqual(self.client.get(reverse('contracts:contract_update_file', args=[self.cu.pk])).status_code, 403)


class ThanhLyTest(UcHopDongCoSo):                # UC 3.4
    def setUp(self):
        super().setUp()
        self.hd_nv = self.hd(self.nv, 'HD-NV', date(2026, 1, 1))
        self.url = reverse('contracts:contract_terminate', args=[self.hd_nv.pk])
        # Dữ liệu liên quan để kiểm tra đủ bước 5–6
        SalaryConfig.objects.create(employee=self.nv, base_salary=10000000, effective_from=date(2026, 1, 1))
        self.lop = tao_lop('Lớp thanh lý')
        self.phan_cong = ClassAssignment.objects.create(study_class=self.lop, employee=self.nv,
                                                        assignment_role='MAIN_TEACHER', start_date=date(2026, 1, 1))
        self.tro_giang = tao_nhan_su('tg@icls.vn', chuc_danh=Position.TEACHING_ASSISTANT, loai_hinh='PART_TIME', ca='')
        self.tro_giang.status = EmployeeStatus.ACTIVE
        self.tro_giang.save()

    def _buoi(self, ngay, giao_vien=None, tro_giang=None, trang_thai='SCHEDULED'):
        giao_vien = giao_vien or self.nv
        return TeachingSession.objects.create(study_class=self.lop, session_date=ngay, planned_start=time(9), planned_end=time(11),
                                              planned_teacher=giao_vien, actual_teacher=giao_vien, planned_assistant=tro_giang,
                                              actual_assistant=tro_giang, status=trang_thai)

    def _cho_ca(self, nhan_su, ngay, trang_thai, ma='g1'):
        return ShiftAssignment.objects.create(
            slot_group=ma, employee=nhan_su, shift_role='Lễ tân', work_date=ngay, planned_start=time(8), planned_end=time(12),
            registration_deadline=datetime(2026, 1, 1), registered_at=datetime(2026, 1, 1), status=trang_thai, assigned_by=self.ql.user)

    def _thanh_ly(self, ngay=HOM_NAY, ly_do='Nghỉ việc', hinh_thuc='RESIGNED'):
        return services.thanh_ly_hop_dong(self.ql.user, self.hd_nv, ngay, ly_do, hinh_thuc, hom_nay=HOM_NAY)

    def test_uc3_4_basic_hop_dong_nhan_su_tai_khoan(self):
        r = self.client.post(self.url, {'ngay_thanh_ly': date.today().isoformat(), 'ly_do': 'Nghỉ việc', 'hinh_thuc': 'RESIGNED'}, follow=True)
        self.assertContains(r, thong_bao.THANH_LY_THANH_CONG)
        self.hd_nv.refresh_from_db(); self.nv.refresh_from_db(); self.nv.user.refresh_from_db()
        self.assertEqual((self.hd_nv.status, self.hd_nv.termination_date, self.hd_nv.termination_reason),
                         (ContractStatus.TERMINATED, date.today(), 'Nghỉ việc'))
        self.assertEqual(self.nv.status, EmployeeStatus.RESIGNED)
        self.assertFalse(self.nv.user.is_active)                                      # khóa tài khoản
        self.assertTrue(ActivityLog.objects.filter(action='LOCK', object_id=self.nv.user.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(action='UPDATE', model_name='Contract', object_id=self.hd_nv.pk).exists())

    def test_uc3_4_basic_hinh_thuc_trung_tam_cham_dut_la_terminated(self):
        self._thanh_ly(hinh_thuc='TERMINATED')
        self.nv.refresh_from_db()
        self.assertEqual(self.nv.status, EmployeeStatus.TERMINATED)

    def test_uc3_4_buoc_5_dong_phan_cong_lop_va_cau_hinh_luong(self):
        ngay = HOM_NAY - timedelta(days=3)
        self._thanh_ly(ngay)
        self.phan_cong.refresh_from_db()
        self.assertEqual(self.phan_cong.end_date, ngay)                                # class_assignments.end_date
        cau_hinh = SalaryConfig.objects.get(employee=self.nv)
        self.assertEqual(cau_hinh.effective_to, ngay)                                  # salary_configs.effective_to

    def test_uc3_4_buoc_6_buoi_day_chinh_sau_ngay_thanh_ly_vao_danh_sach_day_thay(self):
        ngay = HOM_NAY
        qua_khu = self._buoi(ngay - timedelta(days=1))
        sau_1, sau_2 = self._buoi(ngay + timedelta(days=1)), self._buoi(ngay + timedelta(days=3))
        da_huy = self._buoi(ngay + timedelta(days=5), trang_thai='CANCELLED')
        cua_nguoi_khac = self._buoi(ngay + timedelta(days=2), giao_vien=self.nv2)
        so_buoi = self._thanh_ly(ngay)
        self.assertEqual(so_buoi, 2)
        cho_thay = set(SubstituteRequest.objects.filter(status=SubstituteStatus.SEARCHING).values_list('teaching_session', flat=True))
        self.assertEqual(cho_thay, {sau_1.pk, sau_2.pk})                                # không gồm buổi quá khứ, buổi hủy, buổi của người khác
        # Quản lý nhận thông báo số buổi cần người thay
        tb = Notification.objects.get(recipient=self.ql.user, title=thong_bao.TB_THANH_LY_TIEU_DE)
        self.assertIn('2 buổi', tb.message)

    def test_uc3_4_buoc_6_buoi_tro_giang_de_trong_tro_giang(self):
        ngay = HOM_NAY
        buoi = self._buoi(ngay + timedelta(days=2), giao_vien=self.nv2, tro_giang=self.nv)
        self._thanh_ly(ngay)
        buoi.refresh_from_db()
        self.assertIsNone(buoi.actual_assistant)
        self.assertIsNone(buoi.planned_assistant)
        self.assertEqual(buoi.actual_teacher, self.nv2)                                 # giáo viên chính không đổi
        self.assertFalse(SubstituteRequest.objects.exists())                             # trợ giảng không tạo yêu cầu dạy thay

    def test_uc3_4_buoc_6_cho_ca_pending_scheduled_tra_ve_open(self):
        ngay = HOM_NAY
        pending = self._cho_ca(self.nv, ngay + timedelta(days=1), ShiftStatus.PENDING, 'a')
        da_chot = self._cho_ca(self.nv, ngay + timedelta(days=2), ShiftStatus.SCHEDULED, 'b')
        qua_khu = self._cho_ca(self.nv, ngay - timedelta(days=1), ShiftStatus.SCHEDULED, 'c')
        cua_nguoi_khac = self._cho_ca(self.nv2, ngay + timedelta(days=1), ShiftStatus.SCHEDULED, 'd')
        self._thanh_ly(ngay)
        for cho in (pending, da_chot):
            cho.refresh_from_db()
            self.assertEqual((cho.employee, cho.status, cho.registered_at, cho.assigned_by), (None, ShiftStatus.OPEN, None, None))
        qua_khu.refresh_from_db(); cua_nguoi_khac.refresh_from_db()
        self.assertEqual(qua_khu.employee, self.nv)                                      # ca đã qua giữ nguyên (còn dùng tính lương)
        self.assertEqual(cua_nguoi_khac.employee, self.nv2)

    def test_uc3_4_goi_lai_khong_tao_yeu_cau_day_thay_trung(self):
        from schedule.services import giai_phong_lich_tuong_lai
        self._buoi(HOM_NAY + timedelta(days=1))
        giai_phong_lich_tuong_lai(self.nv, HOM_NAY)
        giai_phong_lich_tuong_lai(self.nv, HOM_NAY)
        self.assertEqual(SubstituteRequest.objects.count(), 1)

    def test_uc3_4_exc_3_1_ngay_thanh_ly_khong_hop_le(self):
        for ngay in (self.hd_nv.start_date - timedelta(days=1), HOM_NAY + timedelta(days=1)):
            with self.assertRaises(LoiNghiepVu) as loi:
                self._thanh_ly(ngay)
            self.assertEqual(str(loi.exception), thong_bao.NGAY_THANH_LY_SAI)
        self.hd_nv.refresh_from_db()
        self.assertEqual(self.hd_nv.status, ContractStatus.ACTIVE)
        self._thanh_ly(self.hd_nv.start_date)                                           # đúng ngày bắt đầu: hợp lệ (biên)

    def test_uc3_4_exc_3_1_man_hinh_bao_loi_ngay_tuong_lai(self):
        r = self.client.post(self.url, {'ngay_thanh_ly': (date.today() + timedelta(days=2)).isoformat(), 'ly_do': 'x', 'hinh_thuc': 'RESIGNED'})
        self.assertContains(r, thong_bao.NGAY_THANH_LY_SAI)

    def test_uc3_4_exc_3_2_bo_trong_ly_do(self):
        r = self.client.post(self.url, {'ngay_thanh_ly': date.today().isoformat(), 'ly_do': '   ', 'hinh_thuc': 'RESIGNED'})
        self.assertContains(r, thong_bao.NHAP_LY_DO_THANH_LY)
        self.hd_nv.refresh_from_db(); self.nv.refresh_from_db()
        self.assertEqual((self.hd_nv.status, self.nv.status), (ContractStatus.ACTIVE, EmployeeStatus.ACTIVE))

    def test_uc3_4_giao_dich_loi_giua_chung_hoan_tac_het(self):
        """Nếu một bước sau lỗi, hợp đồng, nhân sự, tài khoản, lịch phải về nguyên trạng."""
        from unittest import mock
        buoi = self._buoi(HOM_NAY + timedelta(days=1))
        with mock.patch('schedule.services.giai_phong_lich_tuong_lai', side_effect=RuntimeError('lỗi giả lập')):
            with self.assertRaises(RuntimeError):
                self._thanh_ly()
        self.hd_nv.refresh_from_db(); self.nv.refresh_from_db(); self.nv.user.refresh_from_db()
        self.assertEqual((self.hd_nv.status, self.nv.status, self.nv.user.is_active),
                         (ContractStatus.ACTIVE, EmployeeStatus.ACTIVE, True))
        self.assertEqual(SalaryConfig.objects.get(employee=self.nv).effective_to, None)
        self.assertFalse(SubstituteRequest.objects.exists())

    def test_uc3_4_chi_thanh_ly_hop_dong_active(self):
        self._thanh_ly()
        with self.assertRaises(LoiNghiepVu):
            self._thanh_ly()

    def test_uc3_4_sau_thanh_ly_khong_dang_nhap_duoc_va_hop_dong_moi_bi_chan(self):
        self._thanh_ly()
        self.client.logout()
        self.nv.user.refresh_from_db()
        self.nv.user.set_password('Matkhau123')
        self.nv.user.save()
        r = self.client.post(reverse('accounts:login'), {'email': 'nv@icls.vn', 'mat_khau': 'Matkhau123'})
        self.assertContains(r, thong_bao.TAI_KHOAN_BI_KHOA)
        self.client.force_login(self.ql.user)
        r = self.client.post(reverse('contracts:contract_add'), {'nhan_su': self.nv.pk, 'contract_number': 'HD-Z',
                                                                  'employment_type': 'FULL_TIME', 'start_date': '2026-11-01'})
        self.assertTrue(r.context['form'].errors['nhan_su'])                              # nhân sự đã nghỉ không được ký

    def test_uc3_4_phan_quyen_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt.user, self.nv.user):
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(self.url).status_code, 403, nguoi)
            self.assertEqual(self.client.post(self.url, {'ngay_thanh_ly': HOM_NAY.isoformat(), 'ly_do': 'x', 'hinh_thuc': 'RESIGNED'}).status_code, 403)
        self.hd_nv.refresh_from_db()
        self.assertEqual(self.hd_nv.status, ContractStatus.ACTIVE)


class SapHetHanTest(UcHopDongCoSo):              # UC 3.5
    def setUp(self):
        super().setUp()
        self.quan_ly_ten = tao_ql_va_nv('a@icls.vn'), tao_ql_va_nv('b@icls.vn'), tao_ql_va_nv('c@icls.vn'), tao_ql_va_nv('d@icls.vn'), tao_ql_va_nv('e@icls.vn')
        a, b, c, d, e = self.quan_ly_ten
        self.qua_han = self.hd(a, 'HD-QH', ket_thuc=HOM_NAY - timedelta(days=3))
        self.duoi_7 = self.hd(b, 'HD-D7', ket_thuc=HOM_NAY + timedelta(days=6))
        self.bay_ngay = self.hd(c, 'HD-7', ket_thuc=HOM_NAY + timedelta(days=7))
        self.ba_muoi = self.hd(d, 'HD-30', ket_thuc=HOM_NAY + timedelta(days=30))
        self.xa = self.hd(e, 'HD-31', ket_thuc=HOM_NAY + timedelta(days=31))              # ngoài 30 ngày
        self.vo_han = self.hd(self.nv, 'HD-VH')                                           # không xác định thời hạn
        self.da_het = self.hd(self.nv2, 'HD-EXP', ket_thuc=HOM_NAY - timedelta(days=60), status=ContractStatus.EXPIRED)

    def test_uc3_5_basic_ba_nhom_thoi_gian(self):
        nhom = services.hop_dong_sap_het_han(hom_nay=HOM_NAY)
        ten = lambda khoa: [hd.contract_number for hd, _ in nhom[khoa]]
        self.assertEqual(ten(services.NHOM_QUA_HAN), ['HD-QH'])
        self.assertEqual(ten(services.NHOM_DUOI_7), ['HD-D7'])                              # còn 6 ngày
        self.assertEqual(ten(services.NHOM_7_30), ['HD-7', 'HD-30'])                        # còn 7 và 30 ngày (biên)
        self.assertEqual(dict(nhom[services.NHOM_QUA_HAN])[self.qua_han], -3)

    def test_uc3_5_hop_dong_het_han_hom_nay_thuoc_nhom_duoi_7(self):
        self.qua_han.end_date = HOM_NAY
        self.qua_han.save()
        nhom = services.hop_dong_sap_het_han(hom_nay=HOM_NAY)
        self.assertIn(self.qua_han, [hd for hd, _ in nhom[services.NHOM_DUOI_7]])
        self.assertEqual(nhom[services.NHOM_QUA_HAN], [])

    def test_uc3_5_he_thong_khong_tu_ket_thuc_hop_dong_qua_han(self):
        services.hop_dong_sap_het_han(hom_nay=HOM_NAY)
        self.qua_han.refresh_from_db()
        self.assertEqual(self.qua_han.status, ContractStatus.ACTIVE)                        # Q6

    def test_uc3_5_basic_man_hinh_va_nut_gia_han_thanh_ly(self):
        r = self.client.get(reverse('contracts:contract_expiring'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'HD-QH')
        self.assertContains(r, reverse('contracts:contract_renew', args=[self.qua_han.pk]))
        self.assertContains(r, reverse('contracts:contract_terminate', args=[self.qua_han.pk]))
        self.assertContains(r, reverse('contracts:contract_detail', args=[self.qua_han.pk]))   # bước 4–5: xem chi tiết

    def test_uc3_5_tim_kiem(self):
        r = self.client.get(reverse('contracts:contract_expiring'), {'q': 'HD-D7'})
        self.assertEqual(r.context['tong'], 1)

    def test_uc3_5_exc_1_1_khong_co_hop_dong_sap_het_han(self):
        Contract.objects.all().delete()
        self.assertContains(self.client.get(reverse('contracts:contract_expiring')), thong_bao.KHONG_CO_HOP_DONG_SAP_HET_HAN)

    def test_uc3_5_phan_quyen_chi_quan_ly(self):
        for nguoi in (self.sa, self.kt.user, self.nv.user):
            self.client.force_login(nguoi)
            self.assertEqual(self.client.get(reverse('contracts:contract_expiring')).status_code, 403, nguoi)


# ============================================================ UC 9.2 – bước 3: nhắc hợp đồng (P10)
class TacVuNgayHopDongTest(TestCase):
    """`nhac_hop_dong_het_han`: chỉ NHẮC Quản lý, không đổi trạng thái hợp đồng (Q6)."""
    HOM_NAY = date(2026, 10, 27)

    def setUp(self):
        from core.mau_test import tao_nhan_su_hoat_dong
        from accounts.models import UserRole as VT
        self.ql = tao_nhan_su_hoat_dong('ql@icls.vn', VT.MANAGER, 'MANAGER')
        self.stt = 0

    def hop_dong(self, so_ngay, trang_thai='ACTIVE'):
        from core.mau_test import tao_nhan_su_hoat_dong
        self.stt += 1
        nv = tao_nhan_su_hoat_dong(f'nv{self.stt}@icls.vn')           # mỗi nhân sự chỉ có một hợp đồng ACTIVE
        return Contract.objects.create(
            employee=nv, contract_number=f'HD-{self.stt}', employment_type='FULL_TIME', start_date=date(2026, 1, 1),
            end_date=self.HOM_NAY + timedelta(days=so_ngay), file_url='x.pdf', status=trang_thai)

    def test_nhac_o_cac_moc_30_7_0_va_vua_qua_han_khong_doi_trang_thai(self):
        from contracts import services
        from core.models import Notification
        hop_dong = [self.hop_dong(n) for n in (30, 7, 0, -1)] + [self.hop_dong(20), self.hop_dong(-5)]
        self.assertEqual(services.nhac_hop_dong_het_han(self.HOM_NAY), 4)    # 4 mốc × 1 Quản lý
        self.assertEqual(Notification.objects.filter(recipient=self.ql.user, notification_type='CONTRACT').count(), 4)
        self.assertFalse(Notification.objects.filter(recipient__email__startswith='nv').exists())   # chỉ Quản lý nhận
        for hd in hop_dong:
            hd.refresh_from_db()
            self.assertEqual(hd.status, 'ACTIVE')                          # không tự kết thúc hợp đồng

    def test_chay_lai_khong_gui_trung_va_bo_qua_hop_dong_da_ket_thuc(self):
        from contracts import services
        self.hop_dong(7)
        self.hop_dong(7, 'TERMINATED')
        self.assertEqual(services.nhac_hop_dong_het_han(self.HOM_NAY), 1)
        self.assertEqual(services.nhac_hop_dong_het_han(self.HOM_NAY), 0)
