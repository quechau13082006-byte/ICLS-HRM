from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
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
            user.set_unusable_password()  # nhân viên mới tự đặt mật khẩu qua link (UC 1.2)
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
