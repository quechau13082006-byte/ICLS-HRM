"""Lệnh `python manage.py chay_tac_vu_ngay` – UC 9.2, gọi dashboard.services.chay_tac_vu_ngay.

Máy chủ đặt lịch chạy lệnh này lúc 06:00 mỗi ngày (cron). Nút "Chạy tác vụ hằng ngày" của Super Admin cũng gọi
đúng hàm này (§11 P10), nên hai đường chạy cho cùng một kết quả.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from dashboard.services import chay_tac_vu_ngay


class Command(BaseCommand):
    help = 'Chạy tác vụ tự động hằng ngày: nhắc hạn, chấm công hôm qua, trạng thái lịch học, quỹ phép năm.'

    def add_arguments(self, parser):
        parser.add_argument('--ngay', help='Chạy như thể hôm nay là ngày này (YYYY-MM-DD), mặc định là hôm nay.')

    def handle(self, *args, **options):
        try:
            hom_nay = date.fromisoformat(options['ngay']) if options['ngay'] else date.today()
        except ValueError:
            raise CommandError('Ngày phải có dạng YYYY-MM-DD, ví dụ 2026-10-27.')
        ket_qua = chay_tac_vu_ngay(hom_nay)
        self.stdout.write(f'Tác vụ hằng ngày – {hom_nay:%d/%m/%Y}')
        for buoc in ket_qua:
            if buoc['loi']:
                self.stdout.write(self.style.ERROR(f"  {buoc['ten']}: LỖI {buoc['loi']}"))
            else:
                self.stdout.write(f"  {buoc['ten']}: {buoc['so']} ({buoc['mo_ta']})")
