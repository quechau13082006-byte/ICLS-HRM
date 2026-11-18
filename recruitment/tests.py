"""Test của app recruitment – P1: ràng buộc CSDL (§7.3.5–7.3.7); P3: UC 8.1–8.3.

Quy ước tên: test_uc<x>_<y>_basic · _alt_<mã luồng> · _exc_<mã luồng> (§12.1).
"""
import shutil
import tempfile
from datetime import date, datetime, timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from core import thong_bao
from core.models import ActivityLog, Notification
from core.services import LoiNghiepVu
from employees.models import Employee
from recruitment import services
from recruitment.models import (CampaignStatus, Candidate, CandidateStatus, RecruitmentCampaign, RecruitmentResult,
                                RecruitmentRound, RecruitmentRoundStatus, RecruitmentRoundType, RecruitmentTarget)

BAY_GIO = datetime(2026, 10, 27, 9, 0)        # "bây giờ" cố định để test không phụ thuộc ngày chạy (§0 luật 5)
TUONG_LAI = datetime(2026, 10, 30, 9, 0)


class RangBuocRecruitmentTest(TestCase):
    def setUp(self):
        self.dot = RecruitmentCampaign.objects.create(campaign_name='Q4', start_date=date(2026, 10, 1))
        self.ql = User.objects.create_user('ql@icls.vn', 'x', role=UserRole.MANAGER)

    def _uv(self, email='a@x.vn'):
        return Candidate.objects.create(campaign=self.dot, full_name='A', email=email, phone='1',
                                        position='TEACHER', employment_type='FULL_TIME')

    def test_dot_ket_thuc_truoc_ngay_bat_dau_bi_chan(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecruitmentCampaign.objects.create(campaign_name='X', start_date=date(2026, 10, 2),
                                               end_date=date(2026, 10, 1))

    def test_mot_email_chi_mot_lan_trong_mot_dot(self):
        self._uv()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._uv()



THU_MUC_MEDIA_TAM = tempfile.mkdtemp()      # CV khi test ghi vào thư mục tạm, không làm bẩn media/


class UcTuyenDungCoSo(TestCase):
    """Dữ liệu chung: Giám đốc, hai Quản lý, Kế toán, Nhân viên và một đợt tuyển dụng đang mở."""

    def setUp(self):
        self.gd = User.objects.create_user('gd@icls.vn', 'x', role=UserRole.DIRECTOR, full_name='Giám đốc')
        self.ql = User.objects.create_user('ql@icls.vn', 'x', role=UserRole.MANAGER, full_name='Quản lý A')
        self.ql2 = User.objects.create_user('ql2@icls.vn', 'x', role=UserRole.MANAGER, full_name='Quản lý B')
        self.kt = User.objects.create_user('kt@icls.vn', 'x', role=UserRole.ACCOUNTANT)
        self.nv = User.objects.create_user('nv@icls.vn', 'x', role=UserRole.EMPLOYEE)
        self.dot = RecruitmentCampaign.objects.create(campaign_name='Tuyển dụng Q4', start_date=date(2026, 10, 1))
        self.client.force_login(self.ql)

    def ung_vien(self, email='uv@x.vn', trang_thai=CandidateStatus.NEW, vi_tri='TEACHER', loai='FULL_TIME'):
        return Candidate.objects.create(campaign=self.dot, full_name='Ứng Viên', email=email, phone='0900000001',
                                        position=vi_tri, employment_type=loai, status=trang_thai)


@override_settings(MEDIA_ROOT=THU_MUC_MEDIA_TAM)
class DotVaUngVienTest(UcTuyenDungCoSo):         # UC 8.1
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_MEDIA_TAM, ignore_errors=True)

    def _du_lieu(self, **kw):
        du_lieu = {'full_name': 'Nguyễn Văn A', 'email': 'a@x.vn', 'phone': '0912345678', 'position': 'TEACHER',
                   'employment_type': 'FULL_TIME', 'dot': self.dot.pk}
        du_lieu.update(kw)
        return du_lieu

    def test_uc8_1_basic_tao_dot_them_ung_vien_so_tuyen_dat(self):
        r = self.client.post(reverse('recruitment:campaign_add'),
                             {'campaign_name': 'Đợt mới', 'start_date': '2026-11-01', 'end_date': '2026-11-30',
                              'sl_TEACHER': '3', 'sl_TEACHING_ASSISTANT': '2', 'sl_STAFF': ''})
        dot = RecruitmentCampaign.objects.get(campaign_name='Đợt mới')
        self.assertEqual((dot.status, dot.created_by), (CampaignStatus.OPEN, self.ql))        # bước 2
        self.assertEqual(list(dot.targets.values_list('position', 'quantity')), [('TEACHER', 3), ('TEACHING_ASSISTANT', 2)])
        cv = SimpleUploadedFile('cv.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        r = self.client.post(reverse('recruitment:candidate_add'), self._du_lieu(dot=dot.pk, cv_file=cv))
        uv = Candidate.objects.get(email='a@x.vn')
        self.assertEqual((uv.status, uv.campaign), (CandidateStatus.NEW, dot))                # bước 4
        self.assertTrue(uv.cv_file)
        r = self.client.post(reverse('recruitment:candidate_screen', args=[uv.pk]), {'ket_qua': 'dat', 'ghi_chu': 'Hồ sơ tốt'})
        uv.refresh_from_db()
        self.assertEqual((uv.status, uv.screening_note), (CandidateStatus.SCREENING, 'Hồ sơ tốt'))   # bước 6
        self.assertTrue(ActivityLog.objects.filter(action='CREATE', model_name='RecruitmentCampaign').exists())

    def test_uc8_1_tao_dot_bat_buoc_it_nhat_mot_vi_tri(self):
        self.assertContains(self.client.get(reverse('recruitment:campaign_add')), 'Số lượng cần tuyển')
        r = self.client.post(reverse('recruitment:campaign_add'),
                             {'campaign_name': 'Đợt trống', 'start_date': '2026-11-01', 'sl_TEACHER': '0'})
        self.assertContains(r, thong_bao.THIEU_CHI_TIEU_TUYEN)
        r = self.client.post(reverse('recruitment:campaign_add'),
                             {'campaign_name': 'Đợt âm', 'start_date': '2026-11-01', 'sl_TEACHER': '-2'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(RecruitmentCampaign.objects.filter(campaign_name__in=['Đợt trống', 'Đợt âm']).exists())
        with self.assertRaisesMessage(LoiNghiepVu, thong_bao.THIEU_CHI_TIEU_TUYEN):
            services.tao_dot_tuyen_dung(self.ql, 'X', date(2026, 11, 1), None, {})

    def test_uc8_1_tien_do_so_voi_chi_tieu(self):
        RecruitmentTarget.objects.create(campaign=self.dot, position='TEACHER', quantity=3)
        RecruitmentTarget.objects.create(campaign=self.dot, position='STAFF', quantity=1)
        self.ung_vien('a@x.vn', CandidateStatus.HIRED)
        self.ung_vien('b@x.vn', CandidateStatus.PASSED)
        self.ung_vien('c@x.vn', CandidateStatus.INTERVIEWING)
        self.ung_vien('d@x.vn', CandidateStatus.HIRED, vi_tri='TEACHING_ASSISTANT', loai='PART_TIME')   # ngoài chỉ tiêu
        td = services.tien_do_tuyen_dung(self.dot)
        dong = {d['vi_tri']: d for d in td['dong']}
        self.assertEqual(list(dong), ['Giáo viên', 'Trợ giảng', 'Staff'])
        self.assertEqual((dong['Giáo viên']['can_tuyen'], dong['Giáo viên']['da_tuyen'], dong['Giáo viên']['cho_tiep_nhan'],
                          dong['Giáo viên']['con_thieu'], dong['Giáo viên']['phan_tram']), (3, 1, 1, 2, 33))
        self.assertEqual((dong['Trợ giảng']['can_tuyen'], dong['Trợ giảng']['da_tuyen']), (0, 1))
        self.assertEqual((dong['Staff']['da_tuyen'], dong['Staff']['phan_tram']), (0, 0))
        self.assertEqual((td['can_tuyen'], td['da_tuyen'], td['phan_tram']), (4, 2, 25))   # 1 người ngoài chỉ tiêu không tính %
        r = self.client.get(reverse('recruitment:board'), {'dot': self.dot.pk})
        self.assertContains(r, 'Chỉ tiêu tuyển dụng')
        self.assertContains(r, 'Đã tuyển <b>2</b> / 4')

    def test_uc8_1_dot_chua_dat_chi_tieu(self):
        r = self.client.get(reverse('recruitment:board'), {'dot': self.dot.pk})
        self.assertContains(r, 'chưa đặt chỉ tiêu')

    def test_uc8_1_basic_so_tuyen_khong_dat_van_luu_ho_so(self):
        uv = self.ung_vien()
        self.client.post(reverse('recruitment:candidate_screen', args=[uv.pk]), {'ket_qua': 'khong_dat', 'ghi_chu': 'Thiếu kinh nghiệm'})
        uv.refresh_from_db()
        self.assertEqual((uv.status, uv.screening_note), (CandidateStatus.REJECTED, 'Thiếu kinh nghiệm'))
        self.assertTrue(Candidate.objects.filter(pk=uv.pk).exists())

    def test_uc8_1_alt_1_1_dong_dot_khong_nhan_them_ung_vien(self):
        self.client.post(reverse('recruitment:campaign_close', args=[self.dot.pk]))
        self.dot.refresh_from_db()
        self.assertEqual(self.dot.status, CampaignStatus.CLOSED)
        with self.assertRaises(LoiNghiepVu):                                                   # đóng lần hai bị chặn
            services.dong_dot_tuyen_dung(self.ql, self.dot)

    def test_uc8_1_alt_5_1_sua_ket_qua_so_tuyen_chua_xep_lich(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        self.client.post(reverse('recruitment:candidate_screen', args=[uv.pk]), {'ket_qua': 'khong_dat', 'ghi_chu': 'Đổi ý'})
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.REJECTED)
        self.client.post(reverse('recruitment:candidate_screen', args=[uv.pk]), {'ket_qua': 'dat', 'ghi_chu': 'Xem lại, đạt'})
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.SCREENING)

    def test_uc8_1_alt_5_1_khong_sua_duoc_khi_da_xep_lich(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.INTERVIEWING)
        with self.assertRaises(LoiNghiepVu) as loi:
            services.danh_gia_so_tuyen(self.ql, uv, True, 'x')
        self.assertEqual(str(loi.exception), thong_bao.KHONG_SUA_SO_TUYEN)

    def test_uc8_1_exc_3_1_dot_da_dong(self):
        self.dot.status = CampaignStatus.CLOSED
        self.dot.save()
        r = self.client.get(reverse('recruitment:candidate_add'), {'dot': self.dot.pk}, follow=True)
        self.assertContains(r, thong_bao.DOT_DA_DONG)
        r = self.client.post(reverse('recruitment:candidate_add'), self._du_lieu(), follow=True)
        self.assertContains(r, thong_bao.DOT_DA_DONG)
        self.assertEqual(Candidate.objects.count(), 0)

    def test_uc8_1_exc_3_2_thieu_truong_sai_dinh_dang_cv_sai(self):
        url = reverse('recruitment:candidate_add')
        r = self.client.post(url, self._du_lieu(full_name='', position=''))
        self.assertTrue(r.context['form'].errors['full_name'])
        self.assertTrue(r.context['form'].errors['position'])
        r = self.client.post(url, self._du_lieu(phone='12'))
        self.assertContains(r, thong_bao.SDT_UNG_VIEN_SAI)
        for cv in (SimpleUploadedFile('cv.docx', b'x'), SimpleUploadedFile('cv.pdf', b'x' * (5 * 1024 * 1024 + 1))):
            r = self.client.post(url, self._du_lieu(cv_file=cv))
            self.assertContains(r, thong_bao.CV_KHONG_HOP_LE)
        self.assertEqual(Candidate.objects.count(), 0)

    def test_uc8_1_exc_3_3_email_da_co_trong_dot(self):
        self.ung_vien(email='a@x.vn')
        r = self.client.post(reverse('recruitment:candidate_add'), self._du_lieu(email='A@X.vn'))
        self.assertContains(r, thong_bao.UNG_VIEN_TRUNG_EMAIL)
        self.assertEqual(Candidate.objects.count(), 1)

    def test_uc8_1_cung_email_o_dot_khac_duoc_phep(self):
        dot2 = RecruitmentCampaign.objects.create(campaign_name='Đợt 2', start_date=date(2026, 12, 1))
        self.ung_vien(email='a@x.vn')
        self.client.post(reverse('recruitment:candidate_add'), self._du_lieu(dot=dot2.pk))
        self.assertEqual(Candidate.objects.filter(email='a@x.vn').count(), 2)

    def test_uc8_1_phan_quyen_chi_quan_ly(self):
        uv = self.ung_vien()
        urls = [reverse('recruitment:board'), reverse('recruitment:campaign_add'), reverse('recruitment:candidate_add'),
                reverse('recruitment:board') + '?can_danh_gia=1']
        for nguoi in (self.gd, self.kt, self.nv):
            self.client.force_login(nguoi)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403, (nguoi, url))
            r = self.client.post(reverse('recruitment:candidate_screen', args=[uv.pk]), {'ket_qua': 'dat'})
            self.assertEqual(r.status_code, 403)
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.NEW)

    def test_uc8_1_bang_xep_ung_vien_vao_dung_cot_va_loc(self):
        self.ung_vien('a@x.vn', CandidateStatus.NEW)
        self.ung_vien('b@x.vn', CandidateStatus.INTERVIEWING)
        self.ung_vien('c@x.vn', CandidateStatus.PASSED, vi_tri='STAFF', loai='PART_TIME')
        r = self.client.get(reverse('recruitment:board'))
        dem = {c['khoa']: len(c['the']) for c in r.context['cot']}
        self.assertEqual((dem['so_tuyen'], dem['phong_van'], dem['cho_tiep_nhan'], dem['day_thu']), (1, 1, 1, 0))
        self.assertEqual(r.context['tong'], 3)
        r = self.client.get(reverse('recruitment:board'), {'vi_tri': 'STAFF'})
        self.assertEqual(r.context['tong'], 1)
        r = self.client.get(reverse('recruitment:board'), {'q': 'b@x'})
        self.assertEqual(r.context['tong'], 1)

    def test_uc8_1_mo_ngan_ho_so_ung_vien(self):
        uv = self.ung_vien()
        r = self.client.get(reverse('recruitment:board'), {'chon': uv.pk})
        self.assertContains(r, 'Đánh giá sơ tuyển')
        self.assertContains(r, uv.email)


class LichVongTest(UcTuyenDungCoSo):             # UC 8.2
    def _xep_pv(self, uv=None, thoi_gian=TUONG_LAI, nguoi_pv=None, **kw):
        uv = uv or self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        return services.xep_lich_vong(self.ql, uv, 'INTERVIEW', thoi_gian, 'Phòng họp 1', nguoi_pv or self.ql2, bay_gio=BAY_GIO, **kw)

    def test_uc8_2_basic_xep_lich_phong_van(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        thoi_gian = datetime.now() + timedelta(days=2)
        r = self.client.post(reverse('recruitment:schedule_interview', args=[uv.pk]), {
            'scheduled_at': thoi_gian.strftime('%Y-%m-%dT%H:%M'), 'location': 'Phòng 1', 'interviewer': self.ql2.pk}, follow=True)
        self.assertContains(r, thong_bao.DA_XEP_LICH_PHONG_VAN)
        vong = RecruitmentRound.objects.get(candidate=uv)
        self.assertEqual((vong.round_type, vong.status, vong.result), ('INTERVIEW', 'SCHEDULED', 'PENDING'))
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.INTERVIEWING)
        self.assertTrue(Notification.objects.filter(recipient=self.ql2, title=thong_bao.TB_LICH_VONG_TIEU_DE).exists())
        self.assertEqual(mail.outbox[-1].to, ['uv@x.vn'])                                      # email cho ứng viên

    def test_uc8_2_basic_xep_lich_demo_cho_giao_vien_full_time(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.TEACHING_TRIAL)
        vong = services.xep_lich_vong(self.ql, uv, 'DEMO', TUONG_LAI, 'Lớp Hàn sơ cấp II', self.ql2, bay_gio=BAY_GIO)
        self.assertEqual((vong.round_type, vong.interviewer), ('DEMO', self.ql2))
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.TEACHING_TRIAL)                            # Demo không đổi trạng thái
        self.assertTrue(Notification.objects.filter(recipient=self.ql2).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_uc8_2_demo_chi_cho_giao_vien_full_time(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.TEACHING_TRIAL, vi_tri='TEACHING_ASSISTANT', loai='PART_TIME')
        with self.assertRaises(LoiNghiepVu) as loi:
            services.xep_lich_vong(self.ql, uv, 'DEMO', TUONG_LAI, 'x', self.ql2, bay_gio=BAY_GIO)
        self.assertEqual(str(loi.exception), thong_bao.CHI_DEMO_GV_FULL_TIME)

    def test_uc8_2_chi_xep_phong_van_khi_ung_vien_screening(self):
        for trang_thai in (CandidateStatus.NEW, CandidateStatus.INTERVIEWING, CandidateStatus.REJECTED):
            uv = self.ung_vien(f'{trang_thai}@x.vn', trang_thai)
            with self.assertRaises(LoiNghiepVu):
                services.xep_lich_vong(self.ql, uv, 'INTERVIEW', TUONG_LAI, 'x', self.ql2, bay_gio=BAY_GIO)

    def test_uc8_2_alt_3_2_huy_phong_van_ung_vien_ve_screening(self):
        vong = self._xep_pv()
        services.huy_vong(self.ql, vong)
        vong.refresh_from_db(); uv = vong.candidate; uv.refresh_from_db()
        self.assertEqual((vong.status, uv.status), (RecruitmentRoundStatus.CANCELLED, CandidateStatus.SCREENING))

    def test_uc8_2_alt_3_2_huy_demo_ung_vien_giu_teaching_trial(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.TEACHING_TRIAL)
        vong = services.xep_lich_vong(self.ql, uv, 'DEMO', TUONG_LAI, 'x', self.ql2, bay_gio=BAY_GIO)
        services.huy_vong(self.ql, vong)
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.TEACHING_TRIAL)
        services.xep_lich_vong(self.ql, uv, 'DEMO', TUONG_LAI + timedelta(days=1), 'x', self.ql2, bay_gio=BAY_GIO)   # xếp lại được

    def test_uc8_2_exc_3_3_nguoi_phong_van_da_co_lich(self):
        self._xep_pv()
        uv2 = self.ung_vien('uv2@x.vn', CandidateStatus.SCREENING)
        for lech in (0, 30, -30, 59):                                     # dưới 60 phút quanh giờ đó → trùng
            with self.assertRaises(LoiNghiepVu) as loi:
                services.xep_lich_vong(self.ql, uv2, 'INTERVIEW', TUONG_LAI + timedelta(minutes=lech), 'x', self.ql2, bay_gio=BAY_GIO)
            self.assertEqual(str(loi.exception), thong_bao.NGUOI_PV_DA_CO_LICH)
        services.xep_lich_vong(self.ql, uv2, 'INTERVIEW', TUONG_LAI + timedelta(minutes=60), 'x', self.ql2, bay_gio=BAY_GIO)  # đủ 60' thì được
        self.assertEqual(Candidate.objects.get(pk=uv2.pk).status, CandidateStatus.INTERVIEWING)

    def test_uc8_2_exc_3_3_vong_da_huy_khong_chan_lich(self):
        vong = self._xep_pv()
        services.huy_vong(self.ql, vong)
        self._xep_pv(self.ung_vien('uv3@x.vn', CandidateStatus.SCREENING))                   # cùng giờ, cùng người: nay hợp lệ

    def test_uc8_2_exc_3_4_thoi_gian_o_qua_khu(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        with self.assertRaises(LoiNghiepVu) as loi:
            services.xep_lich_vong(self.ql, uv, 'INTERVIEW', BAY_GIO - timedelta(hours=1), 'x', self.ql2, bay_gio=BAY_GIO)
        self.assertEqual(str(loi.exception), thong_bao.THOI_GIAN_QUA_KHU)
        self.assertEqual(RecruitmentRound.objects.count(), 0)
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.SCREENING)                               # không đổi trạng thái khi lỗi

    def test_uc8_2_exc_3_4_hien_loi_tai_truong_ngay_gio_tren_man_hinh(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        qua_khu = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        r = self.client.post(reverse('recruitment:schedule_interview', args=[uv.pk]),
                             {'scheduled_at': qua_khu, 'location': 'x', 'interviewer': self.ql2.pk})
        self.assertContains(r, thong_bao.THOI_GIAN_QUA_KHU)

    def test_uc8_2_nguoi_phong_van_chi_la_quan_ly(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        r = self.client.post(reverse('recruitment:schedule_interview', args=[uv.pk]), {
            'scheduled_at': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'location': 'x', 'interviewer': self.nv.pk})                                       # nhân viên không có trong danh sách chọn
        self.assertTrue(r.context['form_lich'].errors['interviewer'])
        with self.assertRaises(LoiNghiepVu):
            services.xep_lich_vong(self.ql, uv, 'INTERVIEW', TUONG_LAI, 'x', self.nv, bay_gio=BAY_GIO)

    def test_uc8_2_phan_quyen_chi_quan_ly(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        for nguoi in (self.gd, self.kt, self.nv):
            self.client.force_login(nguoi)
            r = self.client.post(reverse('recruitment:schedule_interview', args=[uv.pk]), {})
            self.assertEqual(r.status_code, 403, nguoi)


class DanhGiaVongTest(UcTuyenDungCoSo):          # UC 8.3
    def _vong(self, round_type='INTERVIEW', vi_tri='TEACHER', loai='FULL_TIME', trang_thai=None):
        trang_thai = trang_thai or (CandidateStatus.INTERVIEWING if round_type == 'INTERVIEW' else CandidateStatus.TEACHING_TRIAL)
        uv = self.ung_vien(f'{round_type}{vi_tri}{loai}@x.vn', trang_thai, vi_tri, loai)
        return RecruitmentRound.objects.create(candidate=uv, round_type=round_type, scheduled_at=BAY_GIO - timedelta(hours=1),
                                               interviewer=self.ql2)

    def _cham(self, vong, dat=True, nhan_xet='Tốt'):
        mail.outbox.clear()
        services.danh_gia_vong(self.ql, vong, nhan_xet, dat, bay_gio=BAY_GIO)
        vong.refresh_from_db(); vong.candidate.refresh_from_db()
        return vong.candidate.status

    def test_uc8_3_basic_giao_vien_full_time_dat_phong_van_len_teaching_trial(self):
        vong = self._vong()
        self.assertEqual(self._cham(vong), CandidateStatus.TEACHING_TRIAL)
        self.assertEqual((vong.status, vong.result, vong.note),
                         (RecruitmentRoundStatus.COMPLETED, RecruitmentResult.PASSED, 'Tốt'))
        self.assertEqual(len(mail.outbox), 1)                                                # email kết quả cho ứng viên
        self.assertIn('đạt', mail.outbox[0].body)

    def test_uc8_3_basic_vi_tri_khac_dat_phong_van_len_passed(self):
        self.assertEqual(self._cham(self._vong(vi_tri='TEACHING_ASSISTANT', loai='PART_TIME')), CandidateStatus.PASSED)
        self.assertEqual(self._cham(self._vong(vi_tri='TEACHER', loai='PART_TIME')), CandidateStatus.PASSED)   # GV Part-time không Demo

    def test_uc8_3_basic_dat_demo_len_passed(self):
        self.assertEqual(self._cham(self._vong('DEMO')), CandidateStatus.PASSED)

    def test_uc8_3_basic_khong_dat_bat_ky_vong_nao_la_rejected(self):
        self.assertEqual(self._cham(self._vong('INTERVIEW'), False), CandidateStatus.REJECTED)
        self.assertEqual(self._cham(self._vong('DEMO'), False), CandidateStatus.REJECTED)
        self.assertIn('chưa phù hợp', mail.outbox[0].body)

    def test_uc8_3_basic_danh_sach_vong_can_danh_gia(self):
        da_den_gio = self._vong()
        chua_den = RecruitmentRound.objects.create(candidate=self.ung_vien('z@x.vn', CandidateStatus.INTERVIEWING),
                                                   round_type='INTERVIEW', scheduled_at=BAY_GIO + timedelta(days=1), interviewer=self.ql2)
        ds = list(services.vong_can_danh_gia(BAY_GIO))
        self.assertEqual(ds, [da_den_gio])
        self.assertNotIn(chua_den, ds)

    def test_uc8_3_basic_qua_man_hinh(self):
        uv = self.ung_vien('man@x.vn', CandidateStatus.INTERVIEWING)
        vong = RecruitmentRound.objects.create(candidate=uv, round_type='INTERVIEW', interviewer=self.ql2,
                                               scheduled_at=datetime.now() - timedelta(hours=1))
        khac = self.ung_vien('khac@x.vn')                                              # ứng viên không có vòng tới giờ
        r = self.client.get(reverse('recruitment:board'), {'can_danh_gia': '1'})      # lọc ngay trên bảng
        self.assertEqual([t['ung_vien'] for c in r.context['cot'] for t in c['the']], [uv])
        self.assertContains(r, 'Cần đánh giá')
        self.assertNotContains(r, khac.email)
        self.assertEqual(self.client.get(reverse('recruitment:rounds_due'))['Location'], '/tuyen-dung/?can_danh_gia=1')
        r = self.client.post(reverse('recruitment:round_evaluate', args=[vong.pk]), {'note': 'Rất tốt', 'ket_qua': 'dat'}, follow=True)
        self.assertContains(r, thong_bao.DA_LUU_KET_QUA_VONG)
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.TEACHING_TRIAL)

    def test_uc8_3_alt_3_1_vang_mat_huy_vong_cho_xep_lai(self):
        vong = self._vong()
        services.huy_vong(self.ql, vong, vang_mat=True)
        vong.refresh_from_db(); uv = vong.candidate; uv.refresh_from_db()
        self.assertEqual((vong.status, uv.status), (RecruitmentRoundStatus.CANCELLED, CandidateStatus.SCREENING))
        services.xep_lich_vong(self.ql, uv, 'INTERVIEW', TUONG_LAI, 'x', self.ql2, bay_gio=BAY_GIO)     # xếp lại được
        self.assertTrue(ActivityLog.objects.filter(description__startswith='Ứng viên vắng mặt').exists())

    def test_uc8_3_alt_3_1_vang_mat_roi_danh_gia_khong_dat(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.SCREENING)
        services.loai_ung_vien(self.ql, uv, 'Vắng mặt')
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.REJECTED)

    def test_uc8_3_exc_3_3_vong_chua_toi_gio(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.INTERVIEWING)
        vong = RecruitmentRound.objects.create(candidate=uv, round_type='INTERVIEW', interviewer=self.ql2,
                                               scheduled_at=BAY_GIO + timedelta(hours=2))
        with self.assertRaises(LoiNghiepVu) as loi:
            services.danh_gia_vong(self.ql, vong, 'x', True, bay_gio=BAY_GIO)
        self.assertEqual(str(loi.exception), thong_bao.VONG_CHUA_DIEN_RA)

    def test_uc8_3_khong_danh_gia_lai_vong_da_xong(self):
        vong = self._vong()
        self._cham(vong)
        with self.assertRaises(LoiNghiepVu):
            services.danh_gia_vong(self.ql, vong, 'x', True, bay_gio=BAY_GIO)

    def test_uc8_3_exc_6_1_ung_vien_da_tiep_nhan_khong_tao_ho_so_lan_hai(self):
        uv = self.ung_vien(trang_thai=CandidateStatus.PASSED)
        r = self.client.get(reverse('recruitment:board'), {'chon': uv.pk})
        self.assertContains(r, 'Chuyển sang Onboarding')
        self.assertContains(r, f"{reverse('employees:employee_add')}?ung_vien={uv.pk}")      # bước 6–7
        # Tiếp nhận xong → HIRED: ngăn hồ sơ chỉ còn liên kết tới hồ sơ nhân sự hiện có
        self.client.post(reverse('employees:employee_add'), {
            'full_name': 'Ứng Viên', 'email': 'uv@x.vn', 'phone': '0900000001', 'department': 'ACADEMIC', 'position': 'TEACHER',
            'employment_type': 'FULL_TIME', 'work_shift': 'SHIFT_1', 'join_date': '2026-11-01', 'nationality': 'Việt Nam',
            'mat_khau': 'Moi12345', 'ung_vien': uv.pk})
        uv.refresh_from_db()
        self.assertEqual(uv.status, CandidateStatus.HIRED)
        nhan_su = Employee.objects.get(candidate=uv)
        r = self.client.get(reverse('recruitment:board'), {'chon': uv.pk})
        self.assertNotContains(r, 'Chuyển sang Onboarding')
        self.assertContains(r, reverse('employees:employee_detail', args=[nhan_su.pk]))      # liên kết tới hồ sơ hiện có

    def test_uc8_3_phan_quyen_chi_quan_ly(self):
        vong = self._vong()
        for nguoi in (self.gd, self.kt, self.nv):
            self.client.force_login(nguoi)
            for ten in ('round_evaluate', 'round_absent', 'round_cancel'):
                self.assertEqual(self.client.post(reverse(f'recruitment:{ten}', args=[vong.pk]), {}).status_code, 403, (nguoi, ten))
        vong.refresh_from_db()
        self.assertEqual(vong.status, RecruitmentRoundStatus.SCHEDULED)


# ---------------------------------------------------------------------------------- Đợt mặc định, chọn đợt khi thêm ứng viên
class DotMacDinhTest(UcTuyenDungCoSo):
    HOM_NAY = date(2026, 11, 15)

    def tao_dot(self, ten, bat_dau, ket_thuc=None, trang_thai=CampaignStatus.OPEN):
        return RecruitmentCampaign.objects.create(campaign_name=ten, start_date=bat_dau, end_date=ket_thuc, status=trang_thai)

    def test_uu_tien_dot_dang_dien_ra_bat_dau_sau_cung(self):
        self.tao_dot('Đợt cũ đã đóng', date(2026, 11, 1), trang_thai=CampaignStatus.CLOSED)
        moi = self.tao_dot('Đợt mới', date(2026, 11, 10), date(2026, 12, 31))
        self.tao_dot('Đợt sắp tới', date(2026, 12, 15))
        self.tao_dot('Đợt đã hết hạn', date(2026, 9, 1), date(2026, 10, 31))
        self.assertEqual(services.dot_mac_dinh(self.HOM_NAY), moi)              # self.dot (1/10) cũng đang diễn ra nhưng cũ hơn

    def test_chua_co_dot_dang_dien_ra_thi_lay_dot_sap_toi_gan_nhat(self):
        self.dot.status = CampaignStatus.CLOSED
        self.dot.save()
        xa = RecruitmentCampaign.objects.create(campaign_name='Xa', start_date=date(2027, 3, 1))
        gan = RecruitmentCampaign.objects.create(campaign_name='Gần', start_date=date(2026, 12, 1))
        self.assertEqual(services.dot_mac_dinh(self.HOM_NAY), gan)
        gan.status = xa.status = CampaignStatus.CLOSED
        gan.save()
        xa.save()
        self.assertEqual(services.dot_mac_dinh(self.HOM_NAY), xa)                # không còn đợt mở: đợt bắt đầu gần đây nhất

    def test_bang_mac_dinh_chi_hien_dot_mac_dinh_chon_tat_ca_thi_hien_het(self):
        khac = RecruitmentCampaign.objects.create(campaign_name='Đợt khác', start_date=date(2026, 12, 15))
        self.ung_vien(email='a@x.vn')
        Candidate.objects.create(campaign=khac, full_name='B', email='b@x.vn', phone='0900000002', position='TEACHER',
                                 employment_type='FULL_TIME', status=CandidateStatus.NEW)
        r = self.client.get(reverse('recruitment:board'))
        self.assertEqual((r.context['dot'], r.context['tong']), (self.dot, 1))
        r = self.client.get(reverse('recruitment:board'), {'dot': ''})          # chọn "Tất cả đợt"
        self.assertEqual((r.context['dot'], r.context['tong']), (None, 2))

    def test_them_ung_vien_chon_duoc_dot_chi_dot_dang_mo(self):
        khac = RecruitmentCampaign.objects.create(campaign_name='Đợt khác', start_date=date(2026, 12, 15))
        RecruitmentCampaign.objects.create(campaign_name='Đã đóng', start_date=date(2026, 1, 1), status=CampaignStatus.CLOSED)
        r = self.client.get(reverse('recruitment:candidate_add'), {'dot': khac.pk})
        self.assertEqual(set(r.context['form'].fields['dot'].queryset), {self.dot, khac})
        self.assertEqual(r.context['form']['dot'].value(), khac.pk)               # mặc định đợt đang xem trên bảng
        r = self.client.post(reverse('recruitment:candidate_add'), {
            'dot': khac.pk, 'full_name': 'C', 'email': 'c@x.vn', 'phone': '0912345678', 'position': 'TEACHER',
            'employment_type': 'FULL_TIME'})
        uv = Candidate.objects.get(email='c@x.vn')
        self.assertEqual(uv.campaign, khac)
        self.assertRedirects(r, f"{reverse('recruitment:board')}?dot={khac.pk}&chon={uv.pk}", fetch_redirect_response=False)
