from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    LEAVE = 'LEAVE', 'Nghỉ phép'
    ATTENDANCE = 'ATTENDANCE', 'Chấm công'
    CONTRACT = 'CONTRACT', 'Hợp đồng'
    RECRUITMENT = 'RECRUITMENT', 'Tuyển dụng'
    SCHEDULE = 'SCHEDULE', 'Lịch làm việc'
    PAYROLL = 'PAYROLL', 'Lương'
    PROFILE = 'PROFILE', 'Hồ sơ'
    SYSTEM = 'SYSTEM', 'Hệ thống'


class Notification(models.Model):
    """Bảng notifications – thông báo hệ thống (§7.3.19)."""
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    is_read = models.BooleanField(default=False)
    related_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_notification_type_display()}] {self.title}'


class ActivityLog(models.Model):
    """Bảng activity_logs – nhật ký hoạt động (§7.3.20).

    action: LOGIN, LOGIN_FAILED, LOGOUT, CREATE, UPDATE, APPROVE, REJECT, LOCK, UNLOCK, REMIND, RUN_DAILY_JOB
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='activity_logs')
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%d/%m/%Y %H:%M} {self.action} {self.model_name}'
