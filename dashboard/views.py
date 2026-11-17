"""View dạng hàm của app dashboard (UC 9): kiểm tra quyền → gọi service → hiển thị (§0 luật 2).

Phân quyền (§5): 9.1 mọi vai trò (nội dung khác nhau theo vai trò); 9.2 chạy thủ công chỉ Super Admin.
"""
from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserRole
from core import thong_bao
from core.permissions import role_required
from core.views import ALL_ROLES
from . import services


@role_required(*ALL_ROLES)
def dashboard(request):
    """UC 9.1 – bước 1–2: Dashboard theo vai trò (tab Tổng quan / Kế toán / Cá nhân do `?tab=` chọn)."""
    du_lieu = services.du_lieu_dashboard(request.user, tab=request.GET.get('tab', ''))
    du_lieu['thieu_ho_so_msg'] = thong_bao.CHUA_CO_HO_SO_NHAN_SU
    du_lieu['chua_co_du_lieu'] = thong_bao.CHUA_CO_DU_LIEU
    return render(request, 'dashboard/dashboard.html', du_lieu)


@role_required(UserRole.SUPER_ADMIN)
@require_POST
def chay_tac_vu(request):
    """UC 9.1 – luồng 1.1 → UC 9.2: Super Admin nhấn "Chạy tác vụ hằng ngày", hiện số bản ghi đã xử lý từng bước."""
    ket_qua = services.chay_tac_vu_ngay(nguoi_thuc_hien=request.user)
    so_loi = sum(1 for b in ket_qua if b['loi'])
    messages.success(request, thong_bao.TAC_VU_CHAY_XONG.format(ngay=date.today().strftime('%d/%m/%Y'),
                                                                tong=sum(b['so'] for b in ket_qua)))
    for b in ket_qua:
        if b['loi']:
            messages.error(request, thong_bao.TAC_VU_BUOC_LOI.format(buoc=b['ten']))
        else:
            messages.info(request, f"{b['ten']}: {b['mo_ta']}")
    if so_loi:
        messages.warning(request, thong_bao.TAC_VU_CO_BUOC_LOI.format(so=so_loi))
    return redirect('dashboard:dashboard')
