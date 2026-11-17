from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'        # chỉ phần kỹ thuật: tài khoản, nhật ký, tác vụ hằng ngày
    DIRECTOR = 'DIRECTOR', 'Giám đốc'                 # quản lý cấp cao: duyệt yêu cầu của Quản lý, xem toàn trung tâm
    MANAGER = 'MANAGER', 'Quản lý'
    ACCOUNTANT = 'ACCOUNTANT', 'Kế toán'
    EMPLOYEE = 'EMPLOYEE', 'Nhân viên'


class UserManager(BaseUserManager):
    """Quản lý tạo tài khoản theo email (không có username)."""
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Phải có email')
        user = self.model(email=self.normalize_email(email), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()  # chỉ dùng khi tạo bằng lệnh quản trị không kèm mật khẩu
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', UserRole.SUPER_ADMIN)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    """Bảng users – tài khoản hệ thống (§7.3.1)."""
    username = None
    first_name = None
    last_name = None

    email = models.EmailField(max_length=255, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.EMPLOYEE)
    avatar = models.FileField(upload_to='avatars/', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f'{self.full_name or self.email} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        # Chỉ Super Admin được vào trang quản trị Django (/admin/) với toàn quyền; đổi vai trò thì quyền này tự đổi theo.
        self.is_staff = self.is_superuser = self.role == UserRole.SUPER_ADMIN
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'role' in update_fields:
            kwargs['update_fields'] = set(update_fields) | {'is_staff', 'is_superuser'}
        super().save(*args, **kwargs)
