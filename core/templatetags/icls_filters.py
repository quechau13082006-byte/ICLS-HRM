from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


@register.filter
def vnd(value):
    """Định dạng tiền: 1234567 -> 1.234.567 đ (làm tròn đến đồng, ROUND_HALF_UP).
    Giữa số và "đ" là khoảng trắng KHÔNG NGẮT DÒNG (U+00A0) để "đ" không bị rớt xuống dòng dưới trong bảng."""
    if value in (None, ''):
        return ''
    so = Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return f'{so:,}'.replace(',', '.') + '\u00a0đ'


@register.simple_tag(takes_context=True)
def link_trang(context, so_trang):
    """Đường dẫn tới trang số `so_trang` của danh sách, GIỮ NGUYÊN các bộ lọc đang có trên URL (tìm kiếm, trạng thái...).
    Dùng trong core/_phan_trang.html: {% link_trang 3 %} → "?q=an&trang_thai=ACTIVE&page=3"."""
    tham_so = context['request'].GET.copy()
    tham_so['page'] = so_trang
    return '?' + tham_so.urlencode()


@register.inclusion_tag('core/_avatar.html')
def avatar(nhan_su, co='', so_chu=1):
    """Ảnh đại diện của một nhân sự (Employee): có ảnh thì hiện ảnh, chưa có thì hiện chữ cái đầu trên nền màu.
    `co`: thêm class (vd 'lg' cho cỡ 96px). Dùng: {% avatar nv %} hoặc {% avatar nv 'lg' %}."""
    user = getattr(nhan_su, 'user', None)
    return {'nv': nhan_su, 'anh': user.avatar.name if user is not None and user.avatar else '', 'co': co,
            'chu': (nhan_su.full_name or '')[:so_chu].upper() if so_chu > 1 else (nhan_su.full_name or '')[:1]}


@register.filter
def ten_goi(ho_ten):
    """Tên gọi trên thẻ sidebar: lấy tối đa HAI chữ cuối, bỏ họ. "Trần Thị Bình" → "Thị Bình",
    "Huỳnh Ngọc Quế Châu" → "Quế Châu", "Kim Min-jun" → "Min-jun". Tên chỉ có một chữ thì giữ nguyên.
    Họ tên đầy đủ vẫn hiện khi rê chuột (title)."""
    cac_chu = (ho_ten or '').split()
    if len(cac_chu) <= 1:
        return ho_ten or ''
    return ' '.join(cac_chu[-2:]) if len(cac_chu) >= 3 else cac_chu[-1]


@register.filter
def mau_avatar(so):
    """Chọn một trong 6 màu pastel (class av-0 … av-5) cho ảnh đại diện chữ cái, theo số id."""
    return f'av-{int(so) % 6}'


@register.filter
def add_days(ngay, so_ngay):
    """Cộng thêm số ngày vào một ngày (dùng so sánh "sắp hết hạn" trong template)."""
    from datetime import timedelta
    return ngay + timedelta(days=int(so_ngay))


@register.filter
def gio_gon(gio):
    """Giờ viết gọn cho ô lịch: 08:00 → 8, 13:30 → 13:30 (dùng "Lễ tân 8–12")."""
    if not gio:
        return ''
    return f'{gio.hour}' if gio.minute == 0 else f'{gio.hour}:{gio.minute:02d}'
