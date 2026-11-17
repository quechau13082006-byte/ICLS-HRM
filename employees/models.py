from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Gender(models.TextChoices):
    MALE = 'MALE', 'Nam'
    FEMALE = 'FEMALE', 'Nữ'
    OTHER = 'OTHER', 'Khác'


class Department(models.TextChoices):
    ACADEMIC = 'ACADEMIC', 'Đào tạo'
    HR_ADMIN = 'HR_ADMIN', 'Nhân sự - Hành chính'
    ACCOUNTING = 'ACCOUNTING', 'Kế toán'


class Position(models.TextChoices):
    TEACHER = 'TEACHER', 'Giáo viên'
    TEACHING_ASSISTANT = 'TEACHING_ASSISTANT', 'Trợ giảng'
    STAFF = 'STAFF', 'Staff'
    MANAGER = 'MANAGER', 'Quản lý'
    ACCOUNTANT = 'ACCOUNTANT', 'Kế toán'


class EmploymentType(models.TextChoices):
    FULL_TIME = 'FULL_TIME', 'Full-time'
    PART_TIME = 'PART_TIME', 'Part-time'


class WorkShift(models.TextChoices):
    SHIFT_1 = 'SHIFT_1', 'Ca 1 (08:00–17:00)'
    SHIFT_2 = 'SHIFT_2', 'Ca 2 (13:00–21:00)'


class EmployeeStatus(models.TextChoices):
    ONBOARDING = 'ONBOARDING', 'Đang onboarding'
    ACTIVE = 'ACTIVE', 'Đang làm việc'
    RESIGNED = 'RESIGNED', 'Đã nghỉ việc'
    TERMINATED = 'TERMINATED', 'Đã chấm dứt'


class DocumentType(models.TextChoices):
    PERSONAL_ID = 'PERSONAL_ID', 'Giấy tờ tùy thân'
    CERTIFICATION = 'CERTIFICATION', 'Chứng chỉ'
    OTHER = 'OTHER', 'Khác'


class DocumentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Chờ duyệt'
    APPROVED = 'APPROVED', 'Đã duyệt'
    REJECTED = 'REJECTED', 'Từ chối'
    EXPIRED = 'EXPIRED', 'Hết hạn'


class Employee(models.Model):
    """Bảng employees – hồ sơ nhân sự (§7.3.2). Không bao giờ xóa, chỉ đổi status."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='employee')
    candidate = models.OneToOneField('recruitment.Candidate', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='employee')
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    id_card_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    address = models.TextField(blank=True)
    nationality = models.CharField(max_length=30, default='Việt Nam')
    department = models.CharField(max_length=30, choices=Department.choices)
    position = models.CharField(max_length=30, choices=Position.choices)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    work_shift = models.CharField(max_length=20, choices=WorkShift.choices, blank=True)
    bank_account = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=EmployeeStatus.choices, default=EmployeeStatus.ONBOARDING)
    join_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'

    @property
    def code(self):
        """Mã NV hiển thị: NV0012 (không lưu cột riêng)."""
        return f'NV{self.id:04d}'

    def __str__(self):
        return f'{self.code} – {self.full_name}'


class EmployeeDocument(models.Model):
    """Bảng employee_documents – giấy tờ, chứng chỉ (§7.3.3)."""
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    document_name = models.CharField(max_length=150)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    file_url = models.FileField(upload_to='employee_documents/')
    status = models.CharField(max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.PENDING)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_documents')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_documents'
        constraints = [
            models.CheckConstraint(
                condition=Q(expiry_date__isnull=True) | Q(expiry_date__gte=F('issue_date')),
                name='doc_expiry_after_issue'),
        ]

    def __str__(self):
        return f'{self.document_name} – {self.employee}'
