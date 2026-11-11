from django.contrib import admin

from .models import LeaveBalance, LeaveRequest

admin.site.register(LeaveRequest)
admin.site.register(LeaveBalance)
