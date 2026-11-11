from django.conf import settings
from django.db import models
from django.db.models import F, Q


class LeaveType(models.TextChoices):
    ANNUAL = 'ANNUAL', 'Phép năm'
    SICK = 'SICK', 'Nghỉ ốm'
    UNPAID = 'UNPAID', 'Không lương'
    OTHER = 'OTHER', 'Khác'


class DurationType(models.TextChoices):
    FULL_DAY = 'FULL_DAY', 'Cả ca'
    HALF_DAY_AM = 'HALF_DAY_AM', 'Nửa đầu ca'
    HALF_DAY_PM = 'HALF_DAY_PM', 'Nửa sau ca'


class LeaveStatus(models.TextChoices):
    PENDING = 'PENDING', 'Chờ duyệt'
    APPROVED = 'APPROVED', 'Đã duyệt'
    REJECTED = 'REJECTED', 'Từ chối'
    CANCELLED = 'CANCELLED', 'Đã hủy'


class LeaveRequest(models.Model):
    """Bảng leave_requests – đơn nghỉ phép (§7.3.13)."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    duration_type = models.CharField(max_length=20, choices=DurationType.choices, default=DurationType.FULL_DAY)
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_leave_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    needs_substitute = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'leave_requests'
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F('start_date')), name='leave_end_after_start'),
        ]

    def __str__(self):
        return f'{self.employee} nghỉ {self.start_date:%d/%m/%Y}–{self.end_date:%d/%m/%Y}'


class LeaveBalance(models.Model):
    """Bảng leave_balances – quỹ phép năm, chỉ Full-time (§7.3.14)."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='leave_balances')
    year = models.PositiveIntegerField()
    total_days = models.DecimalField(max_digits=4, decimal_places=1, default=12)
    used_days = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    class Meta:
        db_table = 'leave_balances'
        constraints = [
            models.UniqueConstraint(fields=['employee', 'year'], name='one_balance_per_year'),
            models.CheckConstraint(condition=Q(used_days__lte=F('total_days')), name='used_not_over_total'),
        ]

    @property
    def remaining_days(self):
        """Số ngày còn lại – tính, không lưu cột nên không bao giờ lệch số liệu."""
        return self.total_days - self.used_days

    def __str__(self):
        return f'{self.employee} – phép {self.year}'
