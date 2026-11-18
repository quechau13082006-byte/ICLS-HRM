"""Bỏ vai trò Super Admin.

Quản lý tài khoản, nhật ký và tác vụ hằng ngày chuyển sang Quản lý; trang /admin/ chỉ dành cho tài khoản kỹ thuật
tạo bằng `createsuperuser` (không phải vai trò nghiệp vụ). Tài khoản có role SUPER_ADMIN bị xóa: Super Admin không có
hồ sơ nhân sự; nhật ký của họ giữ lại với người thực hiện để trống (SET_NULL), thông báo của họ bị xóa theo (CASCADE).
"""
from django.db import migrations, models


def xoa_tai_khoan_super_admin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(role='SUPER_ADMIN').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_role'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(xoa_tai_khoan_super_admin, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('DIRECTOR', 'Giám đốc'), ('MANAGER', 'Quản lý'), ('ACCOUNTANT', 'Kế toán'),
                                            ('EMPLOYEE', 'Nhân viên')], default='EMPLOYEE', max_length=20),
        ),
    ]
