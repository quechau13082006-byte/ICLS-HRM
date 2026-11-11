from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ClassStatus(models.TextChoices):
    UPCOMING = 'UPCOMING', 'Sắp khai giảng'
    ACTIVE = 'ACTIVE', 'Đang học'
    COMPLETED = 'COMPLETED', 'Đã kết thúc'
    CANCELLED = 'CANCELLED', 'Đã hủy'


class AssignmentRole(models.TextChoices):
    MAIN_TEACHER = 'MAIN_TEACHER', 'Giáo viên chính'
    TEACHING_ASSISTANT = 'TEACHING_ASSISTANT', 'Trợ giảng'


class TeachingSessionStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Đã lên lịch'
    COMPLETED = 'COMPLETED', 'Đã dạy'
    CANCELLED = 'CANCELLED', 'Đã hủy'


class ShiftStatus(models.TextChoices):
    OPEN = 'OPEN', 'Trống'
    PENDING = 'PENDING', 'Đã giữ chỗ'
    SCHEDULED = 'SCHEDULED', 'Đã chốt'
    CANCELLED = 'CANCELLED', 'Đã hủy'


class SubstituteStatus(models.TextChoices):
    SEARCHING = 'SEARCHING', 'Đang tìm người'
    COMPLETED = 'COMPLETED', 'Đã có người thay'
    FAILED = 'FAILED', 'Không có người thay'


class StudyClass(models.Model):
    """Bảng classes – lớp học (§7.3.8). weekdays dạng "0,2,4" (0 = Thứ 2)."""
    class_name = models.CharField(max_length=150)
    subject = models.CharField(max_length=100)
    room_name = models.CharField(max_length=100, blank=True)
    max_students = models.PositiveIntegerField(default=0)
    weekdays = models.CharField(max_length=20)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=ClassStatus.choices, default=ClassStatus.UPCOMING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'classes'
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F('start_date')), name='class_end_date_ok'),
            models.CheckConstraint(condition=Q(end_time__gt=F('start_time')), name='class_end_time_ok'),
        ]

    def __str__(self):
        return self.class_name


class ClassAssignment(models.Model):
    """Bảng class_assignments – phân công nhân sự cho lớp (§7.3.9)."""
    study_class = models.ForeignKey(StudyClass, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='class_assignments')
    assignment_role = models.CharField(max_length=30, choices=AssignmentRole.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'class_assignments'

    def __str__(self):
        return f'{self.employee} – {self.study_class} ({self.get_assignment_role_display()})'


class TeachingSession(models.Model):
    """Bảng teaching_sessions – buổi dạy (§7.3.10). Chấm công và lương dùng người thực tế."""
    study_class = models.ForeignKey(StudyClass, on_delete=models.CASCADE, related_name='teaching_sessions')
    session_date = models.DateField()
    planned_start = models.TimeField()
    planned_end = models.TimeField()
    room_name = models.CharField(max_length=100, blank=True)
    planned_teacher = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, related_name='planned_sessions')
    actual_teacher = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='actual_sessions')
    planned_assistant = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='planned_assist_sessions')
    actual_assistant = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='actual_assist_sessions')
    status = models.CharField(max_length=20, choices=TeachingSessionStatus.choices,
                              default=TeachingSessionStatus.SCHEDULED)
    lesson_note = models.TextField(blank=True)

    class Meta:
        db_table = 'teaching_sessions'
        constraints = [
            models.CheckConstraint(condition=Q(planned_end__gt=F('planned_start')), name='session_end_after_start'),
        ]

    def __str__(self):
        return f'{self.study_class} – {self.session_date:%d/%m/%Y} {self.planned_start:%H:%M}'


class ShiftAssignment(models.Model):
    """Bảng shift_assignments – mỗi dòng là một chỗ trong khung ca Part-time (§7.3.11)."""
    slot_group = models.CharField(max_length=36, db_index=True)
    employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='shift_assignments')
    shift_role = models.CharField(max_length=50)
    work_date = models.DateField()
    planned_start = models.TimeField()
    planned_end = models.TimeField()
    registration_deadline = models.DateTimeField()
    registered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ShiftStatus.choices, default=ShiftStatus.OPEN)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_shift_assignments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shift_assignments'
        constraints = [
            models.UniqueConstraint(fields=['slot_group', 'employee'], condition=Q(employee__isnull=False),
                                    name='one_seat_per_person_per_slot'),
            models.CheckConstraint(condition=Q(planned_end__gt=F('planned_start')), name='shift_end_after_start'),
        ]

    def __str__(self):
        return f'{self.shift_role} {self.work_date:%d/%m/%Y} {self.planned_start:%H:%M}–{self.planned_end:%H:%M}'


class SubstituteRequest(models.Model):
    """Bảng substitute_requests – yêu cầu dạy thay (§7.3.15)."""
    teaching_session = models.ForeignKey(TeachingSession, on_delete=models.PROTECT,
                                         related_name='substitute_requests')
    leave_request = models.ForeignKey('leave.LeaveRequest', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='substitute_requests')
    substitute_employee = models.ForeignKey('employees.Employee', on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='accepted_substitutions')
    status = models.CharField(max_length=20, choices=SubstituteStatus.choices, default=SubstituteStatus.SEARCHING)
    manager_confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                             blank=True, related_name='confirmed_substitutions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'substitute_requests'
        constraints = [
            models.UniqueConstraint(fields=['teaching_session'], condition=Q(status='SEARCHING'),
                                    name='one_searching_request_per_session'),
        ]

    def __str__(self):
        return f'Dạy thay: {self.teaching_session} ({self.get_status_display()})'
