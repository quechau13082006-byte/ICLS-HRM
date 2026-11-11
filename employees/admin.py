from django.contrib import admin

from .models import Employee, EmployeeDocument

admin.site.register(Employee)
admin.site.register(EmployeeDocument)
