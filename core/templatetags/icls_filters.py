from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.filter
def vnd(value):
    """Định dạng tiền: 1234567 -> 1.234.567 đ (làm tròn đến đồng, ROUND_HALF_UP)."""
    if value in (None, ''):
        return ''
    so = Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return f'{so:,}'.replace(',', '.') + ' đ'


@register.filter
def mau_avatar(so):
    """Chọn một trong 6 màu pastel (class av-0 … av-5) cho ảnh đại diện chữ cái, theo số id."""
    return f'av-{int(so) % 6}'


@register.filter
def add_days(ngay, so_ngay):
    """Cộng thêm số ngày vào một ngày (dùng so sánh "sắp hết hạn" trong template)."""
    from datetime import timedelta
    return ngay + timedelta(days=int(so_ngay))
