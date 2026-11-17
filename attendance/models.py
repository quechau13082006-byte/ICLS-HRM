from django.conf import settings
from django.db import models
from django.db.models import Q


class AttendanceStatus(models.TextChoices):
    ON_TIME = 'ON_TIME', 'Đúng giờ'
    LATE = 'LATE', 'Đi trễ'
    EARLY_LEAVE = 'EARLY_LEAVE', 'Về sớm'
    ABSENT = 'ABSENT', 'Vắng mặt'
    MISSING_CHECKOUT = 'MISSING_CHECKOUT', 'Quên check-out'


class ExplanationStatus(models.TextChoices):
    NONE = 'NONE', 'Chưa giải trình'
    PENDING = 'PENDING', 'Chờ duyệt'
    APPROVED = 'APPROVED', 'Đã chấp thuận'
    REJECTED = 'REJECTED', 'Từ chối'


class Attendance(models.Model):
    """Bảng attendance – chấm công (§7.3.12)."""
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='attendance_logs')
    shift_assignment = models.ForeignKey('schedule.ShiftAssignment', on_delete=models.PROTECT, null=True,
                                         blank=True)
    work_date = models.DateField()
    planned_start = models.TimeField()
    planned_end = models.TimeField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    late_minutes = models.PositiveIntegerField(default=0)
    early_leave_minutes = models.PositiveIntegerField(default=0)
    attendance_status = models.CharField(max_length=30, choices=AttendanceStatus.choices)
    explanation_status = models.CharField(max_length=20, choices=ExplanationStatus.choices,
                                          default=ExplanationStatus.NONE)
    explanation_reason = models.TextField(blank=True)
    explanation_evidence = models.FileField(upload_to='attendance/explanations/', blank=True)
    explanation_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                                blank=True, related_name='reviewed_attendance_explanations')
    explanation_reviewed_at = models.DateTimeField(null=True, blank=True)
    explanation_review_note = models.TextField(blank=True)

    class Meta:
        db_table = 'attendance'
        constraints = [
            models.UniqueConstraint(fields=['employee', 'shift_assignment'],
                                    condition=Q(shift_assignment__isnull=False), name='one_attendance_per_shift'),
            models.UniqueConstraint(fields=['employee', 'work_date'],
                                    condition=Q(shift_assignment__isnull=True), name='one_attendance_per_day'),
        ]

    def __str__(self):
        return f'{self.employee} – {self.work_date:%d/%m/%Y} ({self.get_attendance_status_display()})'
