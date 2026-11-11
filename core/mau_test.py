"""Hàm tạo dữ liệu tối thiểu dùng chung cho test của các app (không phải file test)."""
from datetime import date, time

from accounts.models import User, UserRole
from employees.models import Department, Employee, EmployeeStatus, EmploymentType, Position, WorkShift


def tao_nhan_su(email='nv@icls.vn', vai_tro=UserRole.EMPLOYEE, chuc_danh=Position.TEACHER,
                loai_hinh=EmploymentType.FULL_TIME, ca=WorkShift.SHIFT_1):
    user = User.objects.create_user(email, 'x', role=vai_tro, full_name=email)
    return Employee.objects.create(
        user=user, full_name=email, phone='0900000000', department=Department.ACADEMIC, position=chuc_danh,
        employment_type=loai_hinh, work_shift=ca, join_date=date(2026, 1, 1))


def tao_lop(ten='Lớp A'):
    from schedule.models import StudyClass
    return StudyClass.objects.create(
        class_name=ten, subject='Tiếng Hàn Sơ cấp 1', weekdays='0,2,4', start_time=time(9), end_time=time(11),
        start_date=date(2026, 10, 1), end_date=date(2026, 12, 31))


def tao_nhan_su_hoat_dong(email='nv@icls.vn', vai_tro=UserRole.EMPLOYEE, chuc_danh=Position.STAFF,
                          loai_hinh=EmploymentType.PART_TIME, ca=''):
    """Như tao_nhan_su nhưng trạng thái ACTIVE (tao_nhan_su mặc định ONBOARDING) – dùng cho test cần nhân sự đang làm việc."""
    nv = tao_nhan_su(email, vai_tro, chuc_danh, loai_hinh, ca)
    nv.status = EmployeeStatus.ACTIVE
    nv.save()
    return nv
