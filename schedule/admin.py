from django.contrib import admin

from .models import ClassAssignment, ShiftAssignment, StudyClass, SubstituteRequest, TeachingSession

admin.site.register(StudyClass)
admin.site.register(ClassAssignment)
admin.site.register(TeachingSession)
admin.site.register(ShiftAssignment)
admin.site.register(SubstituteRequest)
