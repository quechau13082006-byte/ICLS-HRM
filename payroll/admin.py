from django.contrib import admin

from .models import Payroll, PayrollDetail, SalaryConfig

admin.site.register(SalaryConfig)
admin.site.register(Payroll)
admin.site.register(PayrollDetail)
