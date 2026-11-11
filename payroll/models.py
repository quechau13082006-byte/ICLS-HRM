from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PayrollStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Nháp'
    LOCKED = 'LOCKED', 'Đã chốt'
    SENT = 'SENT', 'Đã phát hành'


class PayrollDetailType(models.TextChoices):
    EARNING = 'EARNING', 'Khoản cộng'
    DEDUCTION = 'DEDUCTION', 'Khoản trừ'
    TAX = 'TAX', 'Thuế'


class PayrollDetailCategory(models.TextChoices):
    # 4 nhóm tự động (hệ thống tính lại được)
    WORKDAY_SALARY = 'WORKDAY_SALARY', 'Lương ngày công'
    PART_TIME_HOURLY_PAY = 'PART_TIME_HOURLY_PAY', 'Lương theo giờ Part-time'
    CLASS_ALLOWANCE = 'CLASS_ALLOWANCE', 'Phụ cấp lớp'
    RESPONSIBILITY_ALLOWANCE = 'RESPONSIBILITY_ALLOWANCE', 'Phụ cấp trách nhiệm'
    # 5 nhóm thủ công (Kế toán nhập, giữ lại khi tính lại)
    BONUS = 'BONUS', 'Thưởng'
    ADJUSTMENT_INCREASE = 'ADJUSTMENT_INCREASE', 'Điều chỉnh tăng'
    ADJUSTMENT_DECREASE = 'ADJUSTMENT_DECREASE', 'Điều chỉnh giảm'
    PERSONAL_INCOME_TAX = 'PERSONAL_INCOME_TAX', 'Thuế TNCN'
    OTHER = 'OTHER', 'Khác'


class SalaryConfig(models.Model):
    """Bảng salary_configs – cấu hình lương (§7.3.16). Đang áp dụng = effective_to trống."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='salary_configs')
    base_salary = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    class_allowance_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    responsibility_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'salary_configs'
        constraints = [
            models.UniqueConstraint(fields=['employee', 'effective_from'], name='one_config_per_start_date'),
            models.CheckConstraint(
                condition=Q(base_salary__gte=0, hourly_rate__gte=0, class_allowance_rate__gte=0,
                            responsibility_allowance__gte=0)
                          & (Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from'))),
                name='salary_config_valid'),
        ]

    def __str__(self):
        return f'Lương {self.employee} từ {self.effective_from:%d/%m/%Y}'


class Payroll(models.Model):
    """Bảng payrolls – mỗi nhân sự một bản ghi mỗi tháng (§7.3.17)."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='payrolls')
    period_month = models.PositiveSmallIntegerField()
    period_year = models.PositiveIntegerField()
    gross_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deduction = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_payrolls')
    created_at = models.DateTimeField(auto_now_add=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payrolls'
        constraints = [
            models.UniqueConstraint(fields=['employee', 'period_month', 'period_year'],
                                    name='one_payroll_per_month'),
            models.CheckConstraint(condition=Q(period_month__gte=1, period_month__lte=12),
                                   name='payroll_month_1_12'),
        ]

    def __str__(self):
        return f'Lương {self.period_month:02d}/{self.period_year} – {self.employee}'


class PayrollDetail(models.Model):
    """Bảng payroll_details – chi tiết bảng lương; số tiền luôn dương (§7.3.18)."""
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='details')
    detail_type = models.CharField(max_length=20, choices=PayrollDetailType.choices)
    category = models.CharField(max_length=40, choices=PayrollDetailCategory.choices)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'payroll_details'
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name='detail_amount_not_negative'),
        ]

    def __str__(self):
        return f'{self.description}: {self.amount}'
