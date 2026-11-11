"""Hàm nghiệp vụ của app dashboard (UC 9): mỗi bước nghiệp vụ là một hàm, docstring ghi mã UC (§0 luật 3).

App này KHÔNG có bảng riêng (§3.2): chỉ ĐỌC các app khác để dựng Dashboard, và khi chạy tác vụ hằng ngày thì GỌI
service của app sở hữu bảng (employees, contracts, attendance, schedule, leave) – không tự ghi vào bảng của họ.
Các nhóm hàm: 1. UC 9.2 tác vụ hằng ngày · 2. UC 9.1 số liệu Dashboard theo vai trò.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.urls import reverse

from accounts.models import User, UserRole
from attendance.models import Attendance, AttendanceStatus, ExplanationStatus
from core import thong_bao
from core.models import ActivityLog, NotificationType
from core.services import ghi_nhat_ky, tao_thong_bao
from employees.models import Employee, EmployeeStatus, EmploymentType
from leave.models import DurationType, LeaveRequest, LeaveStatus
from schedule.models import ClassStatus, StudyClass


# ============================================================ 1. UC 9.2 – TÁC VỤ HẰNG NGÀY
# Mỗi bước là một hàm nhận `hom_nay`, gọi service của app sở hữu bảng, trả về (số bản ghi đã xử lý, mô tả ngắn).
# Import service ngay trong hàm (§3.2) để tránh vòng import giữa các app.
def _buoc_giay_to(hom_nay):
    """Bước 2: giấy tờ quá hạn → EXPIRED; nhắc nhân sự và Quản lý ở các mốc 30, 7, 0 ngày."""
    from employees import services
    so_het_han = services.het_han_giay_to(hom_nay)
    so_nhac = services.nhac_han_giay_to(hom_nay)
    return so_het_han + so_nhac, f'{so_het_han} giấy tờ hết hạn, {so_nhac} thông báo nhắc'


def _buoc_hop_dong(hom_nay):
    """Bước 3: nhắc Quản lý về hợp đồng sắp hết hạn (không tự đổi trạng thái hợp đồng, Q6)."""
    from contracts import services
    so_nhac = services.nhac_hop_dong_het_han(hom_nay)
    return so_nhac, f'{so_nhac} thông báo nhắc'


def _buoc_cham_cong(hom_nay):
    """Bước 4: chấm công của ngày hôm qua → ABSENT, MISSING_CHECKOUT."""
    from attendance import services
    so_vang, so_thieu = services.ghi_nhan_cham_cong_ngay(hom_nay - timedelta(days=1))
    return so_vang + so_thieu, f'{so_vang} vắng mặt, {so_thieu} quên check-out'


def _buoc_lich_hoc(hom_nay):
    """Bước 5: buổi dạy, yêu cầu dạy thay, lớp học."""
    from schedule import services
    kq = services.cap_nhat_lich_hang_ngay(hom_nay)
    tong = sum(kq.values())
    return tong, (f"{kq['buoi_hoan_thanh']} buổi đã dạy, {kq['that_bai']} yêu cầu dạy thay thất bại, "
                  f"{kq['lop_bat_dau']} lớp bắt đầu, {kq['lop_ket_thuc']} lớp kết thúc")


def _buoc_quy_phep(hom_nay):
    """Bước 6: tạo quỹ phép năm cho nhân sự Full-time chưa có."""
    from leave import services
    so_moi = services.tao_quy_phep_hang_loat(hom_nay.year)
    return so_moi, f'{so_moi} quỹ phép mới'


def _cac_buoc():
    """Danh sách (tên bước, hàm) theo đúng thứ tự UC 9.2 (lấy hàm tại thời điểm chạy để test thay thế được)."""
    return [('Giấy tờ', _buoc_giay_to), ('Hợp đồng', _buoc_hop_dong), ('Chấm công', _buoc_cham_cong),
            ('Lịch học', _buoc_lich_hoc), ('Quỹ phép', _buoc_quy_phep)]


def chay_tac_vu_ngay(hom_nay=None, nguoi_thuc_hien=None):
    """UC 9.2 – §9.1: chạy lần lượt các bước 2–6, mỗi bước bọc try/except riêng (luồng ngoại lệ 1.2).

    Trả về list dict {ten, so, mo_ta, loi} theo thứ tự bước (`loi` là None nếu bước chạy tốt).
    - Bước lỗi: giao dịch của bước đó được hoàn tác, ghi nhật ký lỗi, các bước sau VẪN chạy; cuối cùng mọi Super Admin
      nhận thông báo "Tác vụ hằng ngày: bước [tên bước] gặp lỗi."
    - Bước 7: ghi nhật ký RUN_DAILY_JOB kèm số bản ghi đã xử lý.
    `nguoi_thuc_hien` là Super Admin bấm nút (None khi máy chủ tự chạy lúc 06:00 qua lệnh `chay_tac_vu_ngay`).
    Chạy lại cùng ngày không tạo trùng vì từng bước chỉ xử lý dữ liệu chưa xử lý (§9.2).
    """
    hom_nay = hom_nay or date.today()
    ket_qua = []
    for ten, ham in _cac_buoc():
        try:
            with transaction.atomic():
                so, mo_ta = ham(hom_nay)
            ket_qua.append({'ten': ten, 'so': so, 'mo_ta': mo_ta, 'loi': None})
        except Exception as loi:        # noqa: BLE001 – một bước hỏng không được làm sập các bước còn lại
            ghi_nhat_ky(nguoi_thuc_hien, 'RUN_DAILY_JOB', 'dashboard', None, f'Bước {ten} gặp lỗi: {loi!r}')
            ket_qua.append({'ten': ten, 'so': 0, 'mo_ta': '', 'loi': repr(loi)})
    for buoc in ket_qua:
        if buoc['loi']:
            for sa in User.objects.filter(role=UserRole.SUPER_ADMIN, is_active=True):
                tao_thong_bao(sa, NotificationType.SYSTEM, thong_bao.TB_TAC_VU_LOI_TIEU_DE,
                              thong_bao.TAC_VU_BUOC_LOI.format(buoc=buoc['ten']), reverse('dashboard:dashboard'))
    tong = sum(b['so'] for b in ket_qua)
    chi_tiet = '; '.join(f"{b['ten']}: {b['so']}" if not b['loi'] else f"{b['ten']}: LỖI" for b in ket_qua)
    ghi_nhat_ky(nguoi_thuc_hien, 'RUN_DAILY_JOB', 'dashboard', None,
                f'Ngày {hom_nay:%d/%m/%Y}: xử lý {tong} bản ghi ({chi_tiet})')
    return ket_qua


# ============================================================ 2. UC 9.1 – SỐ LIỆU DASHBOARD
def _the(nhan, so, phu='', url=None, icon='ri-bar-chart-box-line', can_chu_y=False):
    """Một thẻ số liệu (Figma): nhãn, số lớn, dòng phụ, link tới trang xử lý. `can_chu_y` tô vàng khi số > 0."""
    return {'nhan': nhan, 'so': so, 'phu': phu, 'url': url, 'icon': icon, 'can_chu_y': can_chu_y and bool(so)}


def _phan_tram(phan, tong):
    return round(phan * 100 / tong, 1) if tong else 0


def du_lieu_dashboard(nguoi_dung, hom_nay=None, tab=''):
    """UC 9.1 – bước 2: xác định vai trò, trả về dict context cho template.

    Khóa `loai` cho template biết dựng phần nào: 'sa', 'ql', 'kt', 'ca_nhan', hoặc 'thieu_ho_so' (luồng 1.3: tài khoản
    không phải Super Admin mà chưa có hồ sơ nhân sự). `tabs` là các tab được xem (Figma): Quản lý có Tổng quan + Cá nhân,
    Kế toán có Kế toán + Cá nhân, Nhân viên chỉ Cá nhân, Super Admin chỉ Tổng quan.
    """
    hom_nay = hom_nay or date.today()
    vai_tro = nguoi_dung.role
    if vai_tro == UserRole.SUPER_ADMIN:
        tabs = [('tong_quan', 'Tổng quan')]
    elif getattr(nguoi_dung, 'employee', None) is None:
        return {'loai': 'thieu_ho_so', 'tabs': [], 'tab': '', 'hom_nay': hom_nay}
    elif vai_tro == UserRole.MANAGER:
        tabs = [('tong_quan', 'Tổng quan'), ('ca_nhan', 'Cá nhân')]
    elif vai_tro == UserRole.ACCOUNTANT:
        tabs = [('ke_toan', 'Kế toán'), ('ca_nhan', 'Cá nhân')]
    else:
        tabs = [('ca_nhan', 'Cá nhân')]
    cac_ma = [ma for ma, _ in tabs]
    tab = tab if tab in cac_ma else cac_ma[0]
    ham = {'tong_quan': du_lieu_quan_ly, 'ke_toan': du_lieu_ke_toan, 'ca_nhan': du_lieu_ca_nhan}
    if vai_tro == UserRole.SUPER_ADMIN:
        du_lieu = du_lieu_super_admin(nguoi_dung, hom_nay)
        du_lieu['loai'] = 'sa'
    else:
        du_lieu = ham[tab](nguoi_dung, hom_nay)
        du_lieu['loai'] = {'tong_quan': 'ql', 'ke_toan': 'kt', 'ca_nhan': 'ca_nhan'}[tab]
    du_lieu.update({'tabs': tabs, 'tab': tab, 'hom_nay': hom_nay})
    return du_lieu


# ---------------------------------------------------------------- Super Admin
def du_lieu_super_admin(nguoi_dung, hom_nay):
    """Super Admin: tài khoản theo vai trò/trạng thái, 10 nhật ký mới nhất, đăng nhập thất bại 7 ngày gần nhất,
    số đơn nghỉ / giải trình / giấy tờ của Quản lý đang chờ Super Admin duyệt (Q2), nút chạy tác vụ (UC 9.2)."""
    from attendance.services import danh_sach_giai_trinh
    from employees.services import giay_to_cho_duyet
    from leave.services import danh_sach_don_duyet
    dem = {}
    for vai_tro, hoat_dong in User.objects.values_list('role', 'is_active'):
        dong = dem.setdefault(vai_tro, {'hoat_dong': 0, 'bi_khoa': 0})
        dong['hoat_dong' if hoat_dong else 'bi_khoa'] += 1
    tai_khoan = [{'ten': nhan, 'hoat_dong': dem.get(ma, {}).get('hoat_dong', 0), 'bi_khoa': dem.get(ma, {}).get('bi_khoa', 0)}
                 for ma, nhan in UserRole.choices]
    tu_ngay = hom_nay - timedelta(days=6)           # 7 ngày gần nhất, tính cả hôm nay
    that_bai = ActivityLog.objects.filter(action='LOGIN_FAILED', created_at__date__gte=tu_ngay).count()
    cac_the = [
        _the('Đăng nhập thất bại', that_bai, '7 ngày gần nhất', icon='ri-shield-keyhole-line', can_chu_y=True),
        _the('Đơn nghỉ của Quản lý', danh_sach_don_duyet(nguoi_dung).count(), 'Chờ bạn duyệt',
             reverse('leave:review'), 'ri-calendar-close-line', True),
        _the('Giải trình của Quản lý', danh_sach_giai_trinh(nguoi_dung).count(), 'Chờ bạn duyệt',
             reverse('attendance:review'), 'ri-verified-badge-line', True),
        _the('Giấy tờ của Quản lý', giay_to_cho_duyet(nguoi_dung).count(), 'Chờ bạn duyệt',
             reverse('employees:pending_documents'), 'ri-file-list-3-line', True)]
    return {'tai_khoan': tai_khoan, 'tong_tai_khoan': sum(d['hoat_dong'] + d['bi_khoa'] for d in tai_khoan),
            'cac_the': cac_the, 'nhat_ky': list(ActivityLog.objects.select_related('user')[:10])}


# ---------------------------------------------------------------- Quản lý (Figma "DB tổng quan")
def du_lieu_quan_ly(nguoi_dung, hom_nay):
    """Quản lý: nhân sự (tỉ lệ Full/Part-time), việc chờ duyệt, hợp đồng và giấy tờ sắp hết hạn (30 ngày),
    buổi dạy cần người thay, lớp đang diễn ra, ca làm việc hôm nay, lịch hôm nay, mục cần chú ý."""
    from attendance.services import danh_sach_giai_trinh
    from contracts.services import hop_dong_sap_het_han
    from employees.services import danh_sach_canh_bao, giay_to_cho_duyet
    from leave.services import danh_sach_don_duyet
    from schedule.services import lich_lam_viec, yeu_cau_day_thay_dang_tim

    cac_nv = list(Employee.objects.values_list('status', 'employment_type'))
    tong = len(cac_nv)
    full_time = sum(1 for _, loai in cac_nv if loai == EmploymentType.FULL_TIME)
    dang_lam = sum(1 for st, _ in cac_nv if st == EmployeeStatus.ACTIVE)
    da_nghi = sum(1 for st, _ in cac_nv if st in (EmployeeStatus.RESIGNED, EmployeeStatus.TERMINATED))
    nghi_hom_nay = (LeaveRequest.objects.filter(status=LeaveStatus.APPROVED, duration_type=DurationType.FULL_DAY,
                                                start_date__lte=hom_nay, end_date__gte=hom_nay,
                                                employee__status=EmployeeStatus.ACTIVE).values('employee').distinct().count())
    lop_dang_day = StudyClass.objects.filter(status=ClassStatus.ACTIVE).count()
    lich = sorted(lich_lam_viec(nguoi_dung, hom_nay, hom_nay), key=lambda m: m['bd'])
    so_ca = sum(1 for m in lich if m['loai'] in ('ca', 'ca_ft'))
    so_buoi = sum(1 for m in lich if m['loai'] == 'buoi')
    nhom_hd = hop_dong_sap_het_han(hom_nay=hom_nay)
    ds_hop_dong = [x for nhom in nhom_hd.values() for x in nhom]
    ds_giay_to = danh_sach_canh_bao(hom_nay=hom_nay)
    ds_hop_dong.sort(key=lambda x: x[0].end_date)
    cac_the = [
        _the('Tổng nhân sự', tong, f'{full_time} toàn thời gian · {tong - full_time} bán thời gian',
             reverse('employees:employee_list'), 'ri-team-line'),
        _the('Nhân sự đang làm việc', dang_lam, f'{nghi_hom_nay} nghỉ phép hôm nay · {da_nghi} đã nghỉ',
             reverse('employees:employee_list'), 'ri-user-follow-line'),
        _the('Lớp đang hoạt động', lop_dang_day, 'Lớp có trạng thái Đang học', reverse('schedule:calendar'),
             'ri-graduation-cap-line'),
        _the('Lịch hôm nay', so_ca, f'ca làm việc · {so_buoi} buổi dạy', reverse('schedule:calendar'),
             'ri-calendar-event-line'),
        _the('Hợp đồng / giấy tờ sắp hết hạn', len(ds_hop_dong) + len(ds_giay_to),
             f'{len(ds_hop_dong)} hợp đồng · {len(ds_giay_to)} giấy tờ', reverse('contracts:contract_expiring'),
             'ri-file-warning-line', True)]
    cho_xu_ly = [
        _the('Giấy tờ chờ duyệt', giay_to_cho_duyet(nguoi_dung).count(), '', reverse('employees:pending_documents'),
             'ri-file-list-3-line', True),
        _the('Đơn nghỉ chờ duyệt', danh_sach_don_duyet(nguoi_dung).count(), '', reverse('leave:review'),
             'ri-calendar-close-line', True),
        _the('Giải trình chờ duyệt', danh_sach_giai_trinh(nguoi_dung).count(), '', reverse('attendance:review'),
             'ri-verified-badge-line', True),
        _the('Buổi dạy cần người thay', yeu_cau_day_thay_dang_tim().count(), '', reverse('schedule:substitute_list'),
             'ri-user-shared-line', True)]
    chu_y = []
    if ds_hop_dong:
        hd, con_lai = ds_hop_dong[0]
        chu_y.append({'tieu_de': f'{len(ds_hop_dong)} hợp đồng sắp hết hạn',
                      'phu': f'Gần nhất: {hd.end_date:%d/%m} · {hd.employee.full_name}',
                      'url': reverse('contracts:contract_expiring')})
    if ds_giay_to:
        gt, _muc = ds_giay_to[0]
        chu_y.append({'tieu_de': f'{len(ds_giay_to)} giấy tờ sắp hết hạn hoặc đã hết hạn',
                      'phu': f'Gần nhất: {gt.expiry_date:%d/%m} · {gt.employee.full_name}',
                      'url': reverse('employees:document_alerts')})
    return {'cac_the': cac_the, 'cho_xu_ly': cho_xu_ly, 'chu_y': chu_y,
            'co_cau': {'tong': tong, 'full_time': full_time, 'part_time': tong - full_time,
                       'pt_full': _phan_tram(full_time, tong), 'pt_part': _phan_tram(tong - full_time, tong)},
            'lich_hom_nay': [m for m in lich if m['loai'] in ('buoi', 'ca')][:8]}


# ---------------------------------------------------------------- Kế toán (Figma "DB kế toán")
def du_lieu_ke_toan(nguoi_dung, hom_nay):
    """Kế toán: tổng thu nhập, tổng thực nhận, tổng thuế của bảng lương gần nhất; trạng thái bảng lương;
    tóm tắt chấm công tháng hiện tại. Chưa có bảng lương → các số 0 và `co_bang_luong` = False (luồng 1.2)."""
    from payroll.services import danh_sach_thang, tong_ket_thang
    cac_thang = danh_sach_thang()
    luong = None
    if cac_thang:
        gan_nhat = cac_thang[0]
        tk = tong_ket_thang(gan_nhat['thang'], gan_nhat['nam'])
        ft = sum((b.net_pay for b in tk['cac_bang'] if b.employee.employment_type == EmploymentType.FULL_TIME), Decimal('0'))
        luong = {'thang': gan_nhat['thang'], 'nam': gan_nhat['nam'], 'trang_thai': gan_nhat['trang_thai'],
                 'gross': tk['gross'], 'thue': tk['thue'], 'thuc_nhan': tk['thuc_nhan'], 'khau_tru': tk['khau_tru'],
                 'so_nhan_su': len(tk['cac_bang']), 'dong': tk['cac_bang'][:6],
                 'pt_ft': _phan_tram(ft, tk['thuc_nhan']), 'ft': ft, 'pt': tk['thuc_nhan'] - ft,
                 'url': reverse('payroll:period', args=[gan_nhat['nam'], gan_nhat['thang']])}
    sau_thang = list(reversed(cac_thang[:6]))
    lon_nhat = max((t['tong_thuc_nhan'] for t in sau_thang), default=Decimal('0'))
    cot = [{'nhan': f"T{t['thang']}", 'so': t['tong_thuc_nhan'], 'cao': _phan_tram(t['tong_thuc_nhan'], lon_nhat),
            'moi_nhat': i == len(sau_thang) - 1} for i, t in enumerate(sau_thang)]
    cham_cong = Attendance.objects.filter(work_date__year=hom_nay.year, work_date__month=hom_nay.month)
    dem = {ma: cham_cong.filter(attendance_status=ma).count() for ma in AttendanceStatus.values}
    cho_duyet = cham_cong.filter(explanation_status=ExplanationStatus.PENDING).count()
    return {'luong': luong, 'cot': cot, 'cham_cong': dem, 'tong_cham_cong': cham_cong.count(),
            'gt_cho_duyet': cho_duyet, 'thang_nay': hom_nay.month, 'nam_nay': hom_nay.year}


# ---------------------------------------------------------------- Nhân viên / cá nhân (Figma "DB cá nhân")
def du_lieu_ca_nhan(nguoi_dung, hom_nay):
    """Nhân viên (và tab Cá nhân của Quản lý, Kế toán): lịch tuần này, chấm công hôm nay, quỹ phép (Full-time),
    thông báo chưa đọc, phiếu lương đã phát hành gần nhất. Chỉ đọc dữ liệu của chính mình (§5)."""
    from attendance.services import man_hinh_cham_cong
    from leave.services import dinh_dang_so_ngay, thong_tin_quy_phep
    from payroll.services import phieu_luong_da_phat_hanh
    from schedule.services import dau_tuan, lich_lam_viec
    nhan_su = nguoi_dung.employee
    thu_hai = dau_tuan(hom_nay)
    cac_muc = [m for m in lich_lam_viec(nguoi_dung, thu_hai, thu_hai + timedelta(days=6)) if m['loai'] != 'nghi']
    cac_muc.sort(key=lambda m: (m['ngay'], m['bd']))
    tuan = [{'ngay': thu_hai + timedelta(days=i), 'muc': [m for m in cac_muc if m['ngay'] == thu_hai + timedelta(days=i)]}
            for i in range(7)]
    hom_nay_muc = [m for m in cac_muc if m['ngay'] == hom_nay]
    man_hinh = man_hinh_cham_cong(nhan_su, hom_nay)
    cham_cong = []
    for k in man_hinh['khung']:
        b = k['ban_ghi']
        if b is None:
            trang_thai, mau = 'Chưa check-in', 'secondary'
        elif b.check_out is None:
            trang_thai, mau = f'Đã check-in {b.check_in:%H:%M}', 'warning'
        else:
            trang_thai, mau = f'Hoàn tất {b.check_in:%H:%M}–{b.check_out:%H:%M}', 'success'
        cham_cong.append({'ten': k['khung']['ten'], 'bd': k['khung']['bd'], 'kt': k['khung']['kt'],
                          'trang_thai': trang_thai, 'mau': mau})
    quy = thong_tin_quy_phep(nhan_su, hom_nay.year)
    chua_doc = nguoi_dung.notifications.filter(is_read=False)
    phieu = phieu_luong_da_phat_hanh(nhan_su).first()
    cac_the = [
        _the('Lịch hôm nay', len(hom_nay_muc), 'hoạt động', reverse('schedule:calendar'), 'ri-calendar-event-line'),
        _the('Chấm công hôm nay', 'Nghỉ phép' if man_hinh['nghi_phep'] else len(cham_cong),
             'Hôm nay bạn nghỉ phép' if man_hinh['nghi_phep'] else 'khung giờ cần chấm công',
             reverse('attendance:my_attendance'), 'ri-time-line'),
        _the('Ngày nghỉ còn lại', 'Không áp dụng' if quy is None else dinh_dang_so_ngay(quy.total_days - quy.used_days),
             'Chỉ Full-time có phép năm' if quy is None else f'Quỹ phép năm {hom_nay.year}',
             reverse('leave:my_leaves'), 'ri-calendar-check-line'),
        _the('Thông báo chưa đọc', chua_doc.count(), '', reverse('core:notifications'), 'ri-notification-3-line', True),
        _the('Lương kỳ gần nhất', 'Chưa có' if phieu is None else f'{phieu.net_pay:,.0f} đ'.replace(',', '.'),
             'Chưa có phiếu lương phát hành' if phieu is None else f'Tháng {phieu.period_month:02d}/{phieu.period_year}',
             reverse('payroll:my_payslips'), 'ri-wallet-3-line')]
    return {'nhan_su': nhan_su, 'cac_the': cac_the, 'tuan': tuan, 'hom_nay_muc': hom_nay_muc, 'cham_cong': cham_cong,
            'khong_co_lich': man_hinh['khong_co_lich'], 'nghi_phep': man_hinh['nghi_phep'],
            'thong_bao_moi': list(chua_doc[:5]), 'thu_hai': thu_hai}
