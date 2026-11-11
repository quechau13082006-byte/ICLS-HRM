from django.contrib import admin

from .models import Candidate, RecruitmentCampaign, RecruitmentRound

admin.site.register(RecruitmentCampaign)
admin.site.register(Candidate)
admin.site.register(RecruitmentRound)
