from django.db import models
from django.db.models import F, Q

from employees.models import EmploymentType


class ContractStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Đang hiệu lực'
    EXPIRED = 'EXPIRED', 'Đã hết hạn'
    TERMINATED = 'TERMINATED', 'Đã thanh lý'


class Contract(models.Model):
    """Bảng contracts – hợp đồng lao động (§7.3.4)."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='contracts')
    contract_number = models.CharField(max_length=50, unique=True)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    previous_contract = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='renewals')
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.ACTIVE)
    termination_date = models.DateField(null=True, blank=True)
    termination_reason = models.TextField(blank=True)
    file_url = models.FileField(upload_to='contracts/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contracts'
        constraints = [
            models.UniqueConstraint(fields=['employee'], condition=Q(status='ACTIVE'),
                                    name='one_active_contract_per_employee'),
            models.CheckConstraint(condition=Q(end_date__isnull=True) | Q(end_date__gt=F('start_date')),
                                   name='contract_end_after_start'),
        ]

    def __str__(self):
        return f'HĐ {self.contract_number} – {self.employee}'
