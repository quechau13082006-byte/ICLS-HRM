def thong_bao_chua_doc(request):
    """Số thông báo chưa đọc cho biểu tượng chuông ở mọi trang."""
    if request.user.is_authenticated:
        return {'so_thong_bao_chua_doc': request.user.notifications.filter(is_read=False).count()}
    return {'so_thong_bao_chua_doc': 0}
