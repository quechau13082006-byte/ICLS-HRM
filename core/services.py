"""Hàm nghiệp vụ dùng chung của core (§9.1)."""
from .models import ActivityLog, Notification


class LoiNghiepVu(Exception):
    """Lỗi vi phạm luật nghiệp vụ. Service ném lỗi này kèm câu thông báo (§10);
    view bắt lại và hiển thị cho người dùng, thay vì để web sập."""


def tao_thong_bao(nguoi_nhan, loai, tieu_de, noi_dung, link=''):
    """Tạo thông báo hiện trên chuông của người nhận."""
    return Notification.objects.create(
        recipient=nguoi_nhan, notification_type=loai, title=tieu_de, message=noi_dung, related_url=link)


def ghi_nhat_ky(nguoi_dung, hanh_dong, ten_bang, id=None, mo_ta=''):
    """Ghi một dòng nhật ký hoạt động. nguoi_dung có thể là None (LOGIN_FAILED, tác vụ tự động)."""
    return ActivityLog.objects.create(
        user=nguoi_dung, action=hanh_dong, model_name=ten_bang, object_id=id, description=mo_ta)



class KhongCoQuyen(LoiNghiepVu):
    """Người thao tác không thuộc phạm vi được phép (vd duyệt giấy tờ của chính mình). View đổi thành trang 403."""


class LoiTruongNhap(LoiNghiepVu):
    """Lỗi nghiệp vụ gắn với một ô nhập: view dùng `form.add_error(loi.truong, ...)` để hiện ngay dưới ô (§3.4)."""

    def __init__(self, thong_diep, truong=None):
        super().__init__(thong_diep)
        self.truong = truong
