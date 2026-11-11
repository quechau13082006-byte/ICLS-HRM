from django.conf import settings
from django.db import models
from django.db.models import F, Q

from employees.models import EmploymentType, Position


class CampaignStatus(models.TextChoices):
    OPEN = 'OPEN', 'Đang mở'
    CLOSED = 'CLOSED', 'Đã đóng'


class CandidateStatus(models.TextChoices):
    NEW = 'NEW', 'Mới'
    SCREENING = 'SCREENING', 'Đạt sơ tuyển'
    INTERVIEWING = 'INTERVIEWING', 'Đang phỏng vấn'
    TEACHING_TRIAL = 'TEACHING_TRIAL', 'Dạy thử'
    PASSED = 'PASSED', 'Đạt'
    REJECTED = 'REJECTED', 'Không đạt'
    HIRED = 'HIRED', 'Đã tuyển'


class RecruitmentRoundType(models.TextChoices):
    INTERVIEW = 'INTERVIEW', 'Phỏng vấn'
    DEMO = 'DEMO', 'Dạy thử (Demo)'


class RecruitmentRoundStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Đã lên lịch'
    COMPLETED = 'COMPLETED', 'Hoàn thành'
    CANCELLED = 'CANCELLED', 'Đã hủy'


class RecruitmentResult(models.TextChoices):
    PENDING = 'PENDING', 'Chờ kết quả'
    PASSED = 'PASSED', 'Đạt'
    FAILED = 'FAILED', 'Không đạt'


class RecruitmentCampaign(models.Model):
    """Bảng recruitment_campaigns – đợt tuyển dụng (§7.3.5)."""
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=CampaignStatus.choices, default=CampaignStatus.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_campaigns')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_campaigns'
        constraints = [
            models.CheckConstraint(condition=Q(end_date__isnull=True) | Q(end_date__gte=F('start_date')),
                                   name='campaign_end_after_start'),
        ]

    def __str__(self):
        return self.campaign_name


class Candidate(models.Model):
    """Bảng candidates – ứng viên (§7.3.6). Kết quả sơ tuyển ghi ở screening_note."""
    campaign = models.ForeignKey(RecruitmentCampaign, on_delete=models.PROTECT, related_name='candidates')
    full_name = models.CharField(max_length=150)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20)
    position = models.CharField(max_length=30, choices=Position.choices)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    cv_file = models.FileField(upload_to='candidates/cv/', blank=True)
    screening_note = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=CandidateStatus.choices, default=CandidateStatus.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'candidates'
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'email'], name='one_email_per_campaign'),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.get_status_display()})'


class RecruitmentRound(models.Model):
    """Bảng recruitment_rounds – vòng phỏng vấn / dạy thử (§7.3.7)."""
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT, related_name='recruitment_rounds')
    round_type = models.CharField(max_length=20, choices=RecruitmentRoundType.choices)
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='recruitment_interviews')
    status = models.CharField(max_length=20, choices=RecruitmentRoundStatus.choices,
                              default=RecruitmentRoundStatus.SCHEDULED)
    result = models.CharField(max_length=20, choices=RecruitmentResult.choices, default=RecruitmentResult.PENDING)
    score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_rounds'
        constraints = [
            models.CheckConstraint(condition=Q(score__isnull=True) | Q(score__gte=0, score__lte=10),
                                   name='round_score_0_10'),
        ]

    def __str__(self):
        return f'{self.get_round_type_display()} – {self.candidate.full_name}'
