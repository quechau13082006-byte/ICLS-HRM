# Bỏ nghỉ nửa ngày: nghỉ phép luôn tính theo CẢ NGÀY.
#
# Trước khi xóa cột duration_type, chuyển các đơn nửa ngày cũ (HALF_DAY_AM / HALF_DAY_PM) thành nghỉ cả ngày:
#   - total_days 0,5 → 1;
#   - đơn phép năm ĐÃ DUYỆT thì trừ thêm 0,5 ngày vào quỹ phép (used_days) cho khớp;
#   - nếu cùng một người có hai đơn nửa ngày còn hiệu lực trong cùng một ngày (sáng + chiều) thì giữ đơn đầu,
#     đơn sau chuyển sang Đã hủy (và hoàn 0,5 ngày phép nếu đơn đó đã duyệt) để không còn hai đơn trùng ngày.
from decimal import Decimal

from django.db import migrations

NUA_NGAY = ('HALF_DAY_AM', 'HALF_DAY_PM')
CON_HIEU_LUC = ('PENDING', 'APPROVED')


def chuyen_nua_ngay_thanh_ca_ngay(apps, schema_editor):
    LeaveRequest = apps.get_model('leave', 'LeaveRequest')
    LeaveBalance = apps.get_model('leave', 'LeaveBalance')
    nua = Decimal('0.5')

    def doi_quy(don, chenh_lech):
        if don.status == 'APPROVED' and don.leave_type == 'ANNUAL':
            quy = LeaveBalance.objects.filter(employee_id=don.employee_id, year=don.start_date.year).first()
            if quy is not None:
                quy.used_days = max(Decimal('0'), quy.used_days + chenh_lech)
                quy.save(update_fields=['used_days'])

    da_giu = set()                                   # (nhân sự, ngày) đã có một đơn còn hiệu lực được giữ lại
    for don in LeaveRequest.objects.filter(duration_type__in=NUA_NGAY).order_by('created_at', 'pk'):
        khoa = (don.employee_id, don.start_date)
        if don.status in CON_HIEU_LUC and khoa in da_giu:
            doi_quy(don, -nua)
            don.status = 'CANCELLED'
            don.review_note = (don.review_note + ' ' if don.review_note else '') + \
                '[Hệ thống] Gộp vào đơn nghỉ cả ngày cùng ngày khi bỏ nghỉ nửa ngày.'
            don.save(update_fields=['status', 'review_note'])
            continue
        if don.status in CON_HIEU_LUC:
            da_giu.add(khoa)
        doi_quy(don, nua)
        don.total_days = Decimal('1')
        don.save(update_fields=['total_days'])


class Migration(migrations.Migration):

    dependencies = [
        ('leave', '0003_nua_ngay_theo_ca'),
    ]

    operations = [
        migrations.RunPython(chuyen_nua_ngay_thanh_ca_ngay, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='leaverequest',
            name='duration_type',
        ),
    ]
