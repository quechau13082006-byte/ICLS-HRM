"""Câu thông báo copy NGUYÊN VĂN từ §10 của ROADMAP.md (phần trong ngoặc kép).

Gom hết vào một chỗ để: (1) sửa câu chữ ở một nơi, (2) test so sánh đúng nguyên văn.
Thêm hằng số vào đây khi làm từng UC.
"""
# ===== Chung =====
KHONG_CO_QUYEN = 'Bạn không có quyền truy cập chức năng này.'                 # UC 1.5 – 1.1.1 (trang 403)

# ===== UC 1.1 Đăng nhập =====
DANG_NHAP_SAI_THONG_TIN = 'Email/Mật khẩu không đúng'                        # 3.2.1
TAI_KHOAN_BI_KHOA = 'Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Quản trị viên.'  # 3.3.1

# ===== UC 1.2 Quên mật khẩu / đặt mật khẩu =====
DA_GUI_HUONG_DAN_DAT_LAI = 'Đã gửi hướng dẫn đặt lại mật khẩu vào email của bạn.'    # bước 5
DAT_LAI_MAT_KHAU_THANH_CONG = 'Đặt lại mật khẩu thành công.'                          # bước 7
EMAIL_KHONG_TON_TAI = 'Email không tồn tại trong hệ thống, vui lòng kiểm tra lại.'  # 3.2.1
LINK_HET_HAN = 'Đường dẫn đã hết hạn hoặc không hợp lệ. Vui lòng gửi lại yêu cầu.'  # 6.1.1
MAT_KHAU_XAC_NHAN_KHONG_KHOP = 'Mật khẩu xác nhận không khớp.'                       # 6.2.1 và UC 1.3 – 3.2.1
MAT_KHAU_CHUA_DU_MANH = 'Mật khẩu chưa đủ mạnh (tối thiểu 8 ký tự, không được toàn số).'  # 6.2.1 và UC 1.3 – 3.3.1

# ===== UC 1.3 Đổi mật khẩu =====
DOI_MAT_KHAU_THANH_CONG = 'Đổi mật khẩu thành công.'                                  # bước 5
MAT_KHAU_HIEN_TAI_SAI = 'Mật khẩu hiện tại không chính xác.'                          # 3.1.1

# ===== UC 1.4 Tài khoản cá nhân =====
CAP_NHAT_TAI_KHOAN_THANH_CONG = 'Cập nhật thông tin thành công.'                     # bước 5

# ===== UC 1.5 Quản lý tài khoản =====
EMAIL_DA_DUNG = 'Email này đã được sử dụng.'                                          # 3.3.1
KHONG_TU_KHOA = 'Không thể tự khóa hoặc đổi quyền tài khoản đang đăng nhập.'        # 5.1.1

# ===== UC 1.6 Đăng xuất =====
DA_DANG_XUAT = 'Đã đăng xuất an toàn.'                                                # bước 3

# ===== UC 2 – Nhân sự =====
KHONG_CO_QUYEN_HANH_DONG = 'Bạn không có quyền thực hiện hành động này.'                 # UC 2.1 – 5.1.1 (trang 403)
KHONG_TIM_THAY_NHAN_SU = 'Không tìm thấy nhân sự phù hợp.'                                # UC 2.1 – 3.1.1
CAP_NHAT_HO_SO_THANH_CONG = 'Cập nhật hồ sơ thành công. Giấy tờ mới đang chờ duyệt.'       # UC 2.2 – bước 6
FILE_KHONG_HOP_LE = 'File không hợp lệ. Chỉ chấp nhận PDF, JPG, PNG dưới 5 MB.'             # UC 2.2 – 3.2.1
NGAY_HET_HAN_SAI = 'Ngày hết hạn phải sau ngày cấp.'                                       # UC 2.2 – 3.3.1
CHUA_CAP_NHAT = 'Chưa cập nhật'                                                           # UC 2.3 – 4.1.1
KHONG_CO_HO_SO = 'Tài khoản không có hồ sơ nhân sự.'                                       # UC 2.3 – 1.1.1
HIEN_KHONG_CO_CANH_BAO = 'Hiện không có cảnh báo.'                                         # UC 2.4 – 1.1.1
NHAC_NHO_GIAY_TO = 'Giấy tờ {ten} {tinh_trang}, vui lòng tải bản mới tại Hồ sơ của tôi.'   # UC 2.4 – bước 5
TAO_HO_SO_THANH_CONG = 'Tạo hồ sơ thành công.'                                             # UC 2.5 – bước 6
EMAIL_HOAC_CCCD_TON_TAI = 'Email hoặc số CCCD đã tồn tại trong hệ thống.'                  # UC 2.5 – 3.2.1
UNG_VIEN_DA_TIEP_NHAN = 'Ứng viên này đã được tiếp nhận.'                                  # UC 2.5 – 1.2.1
VUI_LONG_NHAP_LY_DO_TU_CHOI = 'Vui lòng nhập lý do từ chối.'                               # UC 2.6 – 5.2.1
YEU_CAU_DA_XU_LY = 'Yêu cầu đã được xử lý.'                                                # UC 2.6 – 3.1.1

# ===== UC 8 – Tuyển dụng =====
DOT_DA_DONG = 'Đợt tuyển dụng đã đóng, không thể thêm ứng viên.'                    # UC 8.1 – 3.1.1
UNG_VIEN_TRUNG_EMAIL = 'Ứng viên với email này đã có trong đợt tuyển dụng.'         # UC 8.1 – 3.3.1
NGUOI_PV_DA_CO_LICH = 'Người phỏng vấn đã có lịch vào thời gian này.'               # UC 8.2 – 3.3.1
THOI_GIAN_QUA_KHU = 'Thời gian phải sau thời điểm hiện tại.'                        # UC 8.2 – 3.4.1
DIEM_SAI = 'Điểm đánh giá phải từ 0 đến 10.'                                        # UC 8.3 – 3.2.1
VONG_CHUA_DIEN_RA = 'Vòng tuyển dụng chưa diễn ra.'                                 # UC 8.3 – 3.3.1

# ===== UC 3 – Hợp đồng =====
HOP_DONG_DANG_HIEU_LUC = 'Nhân sự này đang có hợp đồng có hiệu lực. Vui lòng kiểm tra lại hoặc sử dụng tính năng Gia hạn.'   # 3.1 – 5.1.1
SO_HOP_DONG_DA_TON_TAI = 'Số hợp đồng đã tồn tại.'                                  # 3.1 – 5.2.1 và 3.3 – 3.2.1
NGAY_KET_THUC_HD_SAI = 'Ngày kết thúc phải sau ngày bắt đầu.'                       # 3.1 – 5.3.1
THIEU_FILE_SCAN = 'Vui lòng tải file scan hợp đồng.'                               # 3.1 – 5.3.1
THEM_HOP_DONG_THANH_CONG = 'Thêm hợp đồng thành công.'                              # 3.1 – bước 7
KHONG_XEM_HOP_DONG = 'Bạn không có quyền xem hợp đồng này.'                         # 3.2 – 1.1.1 (trang 403)
NGAY_HOP_DONG_MOI_SAI = 'Ngày bắt đầu/kết thúc của hợp đồng mới không hợp lệ.'      # 3.3 – 3.1.1
GIA_HAN_THANH_CONG = 'Gia hạn hợp đồng thành công.'                                 # 3.3 – bước 5
NGAY_THANH_LY_SAI = 'Ngày thanh lý không hợp lệ.'                                   # 3.4 – 3.1.1
NHAP_LY_DO_THANH_LY = 'Vui lòng nhập lý do thanh lý.'                               # 3.4 – 3.2.1
THANH_LY_THANH_CONG = 'Thanh lý hợp đồng thành công.'                               # 3.4 – bước 7
KHONG_CO_HOP_DONG_SAP_HET_HAN = 'Không có hợp đồng sắp hết hạn.'                    # 3.5 – 1.1.1

# ===== UC 6 – Lịch làm việc & Phân công (nguyên văn §10) =====
TAO_LOP_THANH_CONG = 'Tạo lớp và phân công thành công ({so_buoi} buổi).'                  # 6.1 – bước 8
PHONG_BI_TRUNG = 'Phòng {phong} đã có lớp khác vào khung giờ này.'                         # 6.1 – 3.2.1
KHONG_CO_GIAO_VIEN = 'Không có giáo viên phù hợp, vui lòng điều chỉnh lịch học.'           # 6.1 – 3.3.1
GIAO_VIEN_TRUNG_LICH = 'Giáo viên bị trùng lịch, vui lòng chọn lại.'                      # 6.1 – 6.1.1
KHONG_CO_LICH = 'Không có lịch trình trong thời gian này.'                                  # 6.2 – 3.1.1
KHONG_XEM_LICH_NGUOI_KHAC = 'Bạn không có quyền xem lịch cá nhân của người khác.'         # 6.2 – 1.1.1 (trang 403)
GIU_CHO_THANH_CONG = 'Giữ chỗ thành công.'                                                  # 6.3 – bước 7
HET_HAN_DANG_KY_CA = 'Đã hết thời hạn đăng ký ca làm việc này.'                            # 6.3 – 5.2.1
CA_DA_DU_NGUOI = 'Ca này đã đủ người.'                                                      # 6.3 – 5.3.1
TRUNG_GIO_VOI_CA = 'Bạn đã có lịch làm việc trùng giờ với ca này.'                         # 6.3 – 5.4.1
DA_GIU_CHO_TRONG_CA = 'Bạn đã giữ chỗ trong ca này.'                                        # 6.3 – 5.4.1
CHUA_HET_HAN_CHOT_CA = 'Chưa hết hạn đăng ký, chưa thể chốt ca.'                           # 6.3 – 8.2.1

# ===== Câu BỔ SUNG: §10 chưa quy định nguyên văn, tự đặt theo cách đơn giản nhất (ghi ở GIAI_THICH.md) =====
TAI_KHOAN_DA_KHOA_TRUOC_DO = 'Tài khoản này đã bị khóa từ trước.'
TAI_KHOAN_DANG_MO = 'Tài khoản này đang hoạt động, không cần mở khóa.'
DA_KHOA_TAI_KHOAN = 'Đã khóa tài khoản.'
DA_MO_KHOA_TAI_KHOAN = 'Đã mở khóa tài khoản.'
DA_DOI_VAI_TRO = 'Đã đổi vai trò tài khoản.'
DA_THEM_TAI_KHOAN = 'Đã tạo tài khoản và gửi email đặt mật khẩu.'
EMAIL_DAT_MAT_KHAU_TIEU_DE = 'ICLS – Đặt mật khẩu cho tài khoản của bạn'
EMAIL_DAT_MAT_KHAU_NOI_DUNG = (
    'Xin chào {ho_ten},\n\nVui lòng mở đường dẫn sau để đặt mật khẩu (có hiệu lực 24 giờ):\n{link}\n\n'
    'Nếu bạn không yêu cầu, hãy bỏ qua email này.')
TB_KHOA_TIEU_DE = 'Tài khoản đã bị khóa'
TB_MO_KHOA_TIEU_DE = 'Tài khoản đã được mở khóa'
TB_DOI_VAI_TRO_TIEU_DE = 'Vai trò tài khoản đã thay đổi'
TB_DOI_VAI_TRO_NOI_DUNG = 'Vai trò của bạn đã được Super Admin đổi từ "{cu}" thành "{moi}".'
TB_MO_KHOA_NOI_DUNG = 'Tài khoản của bạn đã được mở khóa, bạn có thể đăng nhập lại.'

# --- Câu BỔ SUNG cho UC 2 (§10 chưa ghi nguyên văn) ---
CAP_NHAT_HO_SO_KHONG_GIAY_TO = 'Cập nhật hồ sơ thành công.'                # UC 2.2 khi không tải giấy tờ nào
CAP_NHAT_HO_SO_NHAN_SU_THANH_CONG = 'Cập nhật hồ sơ nhân sự thành công.'     # UC 2.5 luồng 1.1
DA_DUYET_GIAY_TO = 'Đã duyệt giấy tờ.'
DA_TU_CHOI_GIAY_TO = 'Đã từ chối giấy tờ.'
DA_NHAC_NHO = 'Đã gửi nhắc nhở cập nhật giấy tờ.'
CAN_CHON_CA_FULL_TIME = 'Nhân sự Full-time phải chọn ca làm việc.'
PART_TIME_KHONG_CO_CA = 'Nhân sự Part-time không có ca làm việc cố định.'
CCCD_SAI_DINH_DANG = 'Số CCCD gồm 12 chữ số.'
SDT_SAI_DINH_DANG = 'Số điện thoại gồm 10–11 chữ số.'
THIEU_TRUONG_GIAY_TO = 'Vui lòng nhập đủ Loại giấy tờ, Tên giấy tờ và chọn file.'
CHI_TIEP_NHAN_UNG_VIEN_DAT = 'Chỉ tiếp nhận ứng viên có trạng thái Đạt (PASSED).'
TB_CHO_DUYET_TIEU_DE = 'Giấy tờ chờ duyệt'
TB_CHO_DUYET_NOI_DUNG = '{nhan_su} vừa tải giấy tờ "{ten}", đang chờ duyệt.'
TB_DA_DUYET_TIEU_DE = 'Giấy tờ đã được duyệt'
TB_DA_DUYET_NOI_DUNG = 'Giấy tờ "{ten}" của bạn đã được duyệt.'
TB_TU_CHOI_TIEU_DE = 'Giấy tờ bị từ chối'
TB_TU_CHOI_NOI_DUNG = 'Giấy tờ "{ten}" bị từ chối: {ly_do}. Vui lòng tải lại tại Hồ sơ của tôi.'
TB_NHAC_NHO_TIEU_DE = 'Nhắc cập nhật giấy tờ'
TB_CAP_QUYEN_TIEU_DE = 'Yêu cầu cấp quyền'
TB_CAP_QUYEN_NOI_DUNG = '{nhan_su} được tiếp nhận với vị trí {vi_tri}. Vui lòng cấp vai trò tương ứng cho tài khoản {email}.'

# --- Câu BỔ SUNG cho UC 8 (§10 chưa ghi nguyên văn) ---
TAO_DOT_THANH_CONG = 'Đã tạo đợt tuyển dụng.'
DONG_DOT_THANH_CONG = 'Đã đóng đợt tuyển dụng.'
DOT_DA_DONG_TRUOC_DO = 'Đợt tuyển dụng này đã đóng từ trước.'
THEM_UNG_VIEN_THANH_CONG = 'Đã thêm ứng viên.'
LUU_SO_TUYEN_THANH_CONG = 'Đã lưu kết quả sơ tuyển.'
KHONG_SUA_SO_TUYEN = 'Ứng viên đã được xếp lịch phỏng vấn, không thể sửa kết quả sơ tuyển.'
CV_KHONG_HOP_LE = 'CV phải là file PDF và không quá 5 MB.'
SDT_UNG_VIEN_SAI = 'Số điện thoại gồm 10–11 chữ số.'
SAI_TRANG_THAI_UNG_VIEN = 'Trạng thái hiện tại của ứng viên không cho phép thao tác này.'
CHI_DEMO_GV_FULL_TIME = 'Chỉ xếp lịch Demo cho giáo viên Full-time.'
VONG_KHONG_CON_DANG_CHO = 'Vòng tuyển dụng này không còn ở trạng thái đã lên lịch.'
NGUOI_PV_PHAI_LA_QUAN_LY = 'Người phỏng vấn phải là tài khoản Quản lý đang hoạt động.'
DA_XEP_LICH_PHONG_VAN = 'Đã xếp lịch phỏng vấn.'
DA_XEP_LICH_DEMO = 'Đã xếp lịch Demo.'
DA_SUA_LICH = 'Đã cập nhật lịch.'
DA_HUY_VONG = 'Đã hủy vòng tuyển dụng.'
DA_DANH_DAU_VANG_MAT = 'Đã đánh dấu ứng viên vắng mặt.'
DA_LUU_KET_QUA_VONG = 'Đã lưu kết quả đánh giá.'
DA_DANH_DAU_KHONG_DAT = 'Đã đánh dấu ứng viên không đạt.'
TB_LICH_VONG_TIEU_DE = 'Lịch tuyển dụng mới'
TB_LICH_VONG_NOI_DUNG = '{loai} với ứng viên {ung_vien} vào {thoi_gian} tại {dia_diem}.'
EMAIL_LICH_TIEU_DE = 'ICLS – Lịch {loai} của bạn'
EMAIL_LICH_NOI_DUNG = 'Xin chào {ung_vien},\n\nTrung tâm ICLS mời bạn tham gia {loai} vào {thoi_gian}, địa điểm/link: {dia_diem}.\n\nTrân trọng.'
EMAIL_KET_QUA_TIEU_DE = 'ICLS – Kết quả {loai}'
EMAIL_KET_QUA_DAT = 'Xin chào {ung_vien},\n\nChúc mừng bạn đã đạt {loai}. Trung tâm sẽ liên hệ bạn ở bước tiếp theo.\n\nTrân trọng.'
EMAIL_KET_QUA_KHONG_DAT = 'Xin chào {ung_vien},\n\nCảm ơn bạn đã tham gia {loai}. Rất tiếc lần này bạn chưa phù hợp với vị trí ứng tuyển.\n\nTrân trọng.'

# --- Câu BỔ SUNG cho UC 3 (§10 chưa ghi nguyên văn) ---
HOP_DONG_KHONG_CON_HIEU_LUC = 'Hợp đồng này không còn ở trạng thái đang hiệu lực.'
CAP_NHAT_FILE_THANH_CONG = 'Đã cập nhật file scan hợp đồng.'
NHAN_SU_KHONG_DUOC_KY = 'Chỉ ký hợp đồng cho nhân sự đang Onboarding hoặc đang làm việc.'
CAN_CHON_CA_SAU_DOI_LOAI_HINH = 'Nhân sự đã chuyển sang Full-time: hãy vào hồ sơ để chọn Ca làm việc.'
TB_HD_KICH_HOAT_TIEU_DE = 'Hồ sơ đã được kích hoạt'
TB_HD_KICH_HOAT_NOI_DUNG = 'Hợp đồng {so_hd} đã được tạo, hồ sơ của bạn chuyển sang trạng thái Đang làm việc.'
TB_HD_GIA_HAN_TIEU_DE = 'Hợp đồng đã được gia hạn'
TB_HD_GIA_HAN_NOI_DUNG = 'Hợp đồng mới {so_hd} của bạn có hiệu lực từ {bat_dau}.'
TB_THANH_LY_TIEU_DE = 'Buổi dạy cần người thay'
TB_THANH_LY_NOI_DUNG = 'Thanh lý hợp đồng của {nhan_su}: có {so_buoi} buổi dạy cần người thay.'
SAI_TRANG_THAI_NHAN_SU = 'Trạng thái hiện tại của nhân sự không cho phép thao tác này.'

# --- Câu BỔ SUNG cho UC 6 (§10 chưa ghi nguyên văn) ---
KHONG_CO_NGAY_HOC = 'Không có ngày học nào trong khoảng thời gian đã chọn.'
GIO_KET_THUC_LOP_SAI = 'Giờ kết thúc phải sau giờ bắt đầu.'
NGAY_KET_THUC_LOP_SAI = 'Ngày kết thúc không được trước ngày bắt đầu.'
CHON_THU_HOC = 'Vui lòng chọn ít nhất một thứ học trong tuần.'
GIAO_VIEN_KHONG_HOP_LE = 'Giáo viên được chọn không nằm trong danh sách gợi ý.'
TRO_GIANG_KHONG_HOP_LE = 'Trợ giảng được chọn không nằm trong danh sách phù hợp.'
TRO_GIANG_TRUNG_LICH = 'Trợ giảng bị trùng lịch, vui lòng chọn lại.'
TB_LOP_MOI_TIEU_DE = 'Bạn được phân công lớp mới'
TB_LOP_MOI_NOI_DUNG = 'Lớp {lop} ({thu} {gio}, từ {tu_ngay}) – vai trò {vai_tro}, tổng {so_buoi} buổi.'
LOP_KHONG_HUY_DUOC = 'Chỉ hủy được lớp đang ở trạng thái Sắp khai giảng hoặc Đang học.'
NHAP_LY_DO_HUY_LOP = 'Vui lòng nhập lý do hủy lớp.'
HUY_LOP_THANH_CONG = 'Đã hủy lớp, {so_buoi} buổi dạy từ hôm nay trở đi đã bị hủy.'
TB_HUY_LOP_TIEU_DE = 'Lớp học đã bị hủy'
TB_HUY_LOP_NOI_DUNG = 'Lớp {lop} đã bị hủy. Lý do: {ly_do}.'
GHI_NOI_DUNG_THANH_CONG = 'Đã lưu nội dung buổi học.'
CHI_GV_GHI_NOI_DUNG = 'Chỉ giáo viên thực tế của buổi dạy mới được ghi nội dung buổi học.'
HAN_CHOT_CA_SAI = 'Hạn chót đăng ký phải trước giờ bắt đầu ca.'
SO_NGUOI_CA_SAI = 'Số người cần phải từ 1 trở lên.'
TAO_KHUNG_CA_THANH_CONG = 'Đã tạo khung ca {vai_tro} ngày {ngay} ({so_nguoi} chỗ) và gửi lời mời đăng ký.'
TB_MOI_DANG_KY_CA_TIEU_DE = 'Mở đăng ký ca làm việc'
TB_MOI_DANG_KY_CA_NOI_DUNG = 'Ca {vai_tro} ngày {ngay} {gio} cần {so_nguoi} người. Hạn đăng ký: {han_chot}.'
CHI_PART_TIME_DANG_KY = 'Chỉ nhân viên Part-time đang làm việc mới đăng ký ca.'
KHONG_TIM_THAY_KHUNG_CA = 'Không tìm thấy khung ca.'
DA_HUY_GIU_CHO = 'Đã hủy giữ chỗ.'
KHONG_CO_CHO_DE_HUY = 'Bạn chưa giữ chỗ trong ca này.'
CA_KHONG_THE_SUA = 'Chỉ sửa được chỗ trong khung ca chưa chốt.'
DA_BO_NGUOI_KHOI_CA = 'Đã bỏ nhân viên khỏi chỗ này.'
DA_GAN_NHAN_VIEN_VAO_CA = 'Đã gán nhân viên vào chỗ trống.'
CHO_KHONG_CON_TRONG = 'Chỗ này đã có người.'
NHAN_VIEN_CA_KHONG_HOP_LE = 'Chỉ chọn được nhân viên Part-time đang làm việc.'
NHAN_VIEN_TRUNG_LICH = 'Nhân viên đã có lịch trùng giờ với ca này.'
DA_DOI_NGUOI_CA = 'Đã đổi người cho ca làm việc.'
KHUNG_CA_DA_CHOT = 'Khung ca này đã được chốt.'
CHOT_CA_THANH_CONG = 'Đã chốt và công bố lịch: {so_cho} chỗ có người, {so_huy} chỗ trống đã hủy.'
KHONG_CO_CA_DE_CHOT = 'Không có khung ca nào cần chốt trong tuần này.'
TB_KET_QUA_CA_TIEU_DE = 'Kết quả đăng ký ca làm việc'
TB_KET_QUA_CA_NOI_DUNG = 'Bạn đã được xếp ca {vai_tro} ngày {ngay} {gio}.'
TB_BO_KHOI_CA_NOI_DUNG = 'Bạn không còn được xếp ca {vai_tro} ngày {ngay} {gio}.'
TB_DOI_NGUOI_CA_NOI_DUNG = 'Ca {vai_tro} ngày {ngay} {gio} đã được đổi từ {cu} sang {moi}.'

# ===== UC 5 – Nghỉ phép (nguyên văn §10) =====
GUI_DON_THANH_CONG = 'Gửi đơn nghỉ phép thành công.'                                      # 5.1 – bước 6
QUY_PHEP_KHONG_DU = 'Quỹ phép năm của bạn không đủ (còn lại: {con_lai} ngày). Vui lòng chọn loại Nghỉ không lương.'   # 5.1 – 3.1.1
NGAY_BAT_DAU_SAU_KET_THUC = 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'           # 5.1 – 3.2.1
TRUNG_DON_NGHI = 'Bạn đã có đơn nghỉ trong khoảng thời gian này.'                         # 5.1 – 3.3.1
PART_TIME_KHONG_PHEP_NAM = 'Chỉ nhân sự Full-time được sử dụng phép năm.'                 # 5.1 – 3.4.1
KHONG_CO_NGAY_LAM_VIEC = 'Khoảng thời gian đã chọn không có ngày làm việc.'               # 5.1 – 3.5.1
QUY_PHEP_NHAN_SU_KHONG_DU = 'Quỹ phép của nhân sự không còn đủ. Vui lòng từ chối hoặc đề nghị nhân sự đổi loại nghỉ.'   # 5.2 – 5.3.1
PART_TIME_KHONG_CO_QUY_PHEP = 'Nhân sự Part-time không có quỹ phép năm.'                  # 5.3 – 1.1.1
KHONG_CO_DU_LIEU_NGHI = 'Không có dữ liệu nghỉ phép trong khoảng thời gian đã chọn.'    # 5.4 – 3.1.1
# (UC 5.2 dùng lại VUI_LONG_NHAP_LY_DO_TU_CHOI và YEU_CAU_DA_XU_LY đã khai báo ở UC 2.6)

# --- Câu BỔ SUNG cho UC 5 và UC 6.4 (§10 chưa ghi nguyên văn) ---
NUA_NGAY_CUNG_NGAY = 'Nghỉ nửa ngày thì ngày bắt đầu phải bằng ngày kết thúc.'
THANG_DA_CHOT_LUONG = 'Tháng {thang}/{nam} đã chốt lương, không thể gửi đơn nghỉ trong tháng này.'
CHI_NHAN_SU_HOAT_DONG_NGHI = 'Chỉ nhân sự đang làm việc mới gửi được đơn nghỉ.'
KHONG_HUY_DON_DUOC = 'Chỉ hủy được đơn đang chờ duyệt.'
DA_HUY_DON = 'Đã hủy đơn nghỉ phép.'
DA_DUYET_DON = 'Đã duyệt đơn nghỉ phép.'
DA_TU_CHOI_DON = 'Đã từ chối đơn nghỉ phép.'
KHONG_CO_QUYEN_DUYET_DON = 'Bạn không có quyền duyệt đơn nghỉ này.'
KHONG_XEM_DON_NGHI = 'Bạn không có quyền xem đơn nghỉ này.'
TB_DON_MOI_TIEU_DE = 'Đơn nghỉ phép chờ duyệt'
TB_DON_MOI_NOI_DUNG = '{nhan_su} xin nghỉ {tu_ngay}–{den_ngay} ({so_ngay} ngày, {loai}). Lý do: {ly_do}'
TB_HUY_DON_TIEU_DE = 'Đơn nghỉ phép đã bị hủy'
TB_HUY_DON_NOI_DUNG = '{nhan_su} đã hủy đơn nghỉ {tu_ngay}–{den_ngay}.'
TB_KET_QUA_DON_TIEU_DE = 'Kết quả đơn nghỉ phép'
TB_DON_DUOC_DUYET = 'Đơn nghỉ {tu_ngay}–{den_ngay} của bạn đã được duyệt.'
TB_DON_BI_TU_CHOI = 'Đơn nghỉ {tu_ngay}–{den_ngay} của bạn bị từ chối. Lý do: {ly_do}'
TB_CAN_DAY_THAY_TIEU_DE = 'Buổi dạy cần người thay'
TB_CAN_DAY_THAY_NOI_DUNG = '{nhan_su} nghỉ phép: có {so_buoi} buổi dạy cần người thay.'
TB_DIEU_CHINH_LICH_TIEU_DE = 'Cần điều chỉnh lịch do nghỉ phép'
TB_DIEU_CHINH_LICH_NOI_DUNG = '{nhan_su} nghỉ {tu_ngay}–{den_ngay}: {so_tro_giang} buổi làm trợ giảng và {so_ca} ca làm việc cần điều chỉnh người.'
# UC 6.4
YEU_CAU_DAY_THAY_DA_XU_LY = 'Yêu cầu dạy thay đã được xử lý.'
DA_CHOT_DAY_THAY = 'Đã chốt giáo viên dạy thay.'
DA_HUY_BUOI_HOC = 'Đã hủy buổi học.'
DA_THEM_BUOI_BU = 'Đã thêm buổi học bù.'
DA_DOI_TRO_GIANG = 'Đã cập nhật trợ giảng.'
BUOI_KHONG_DOI_TRO_GIANG = 'Chỉ đổi được trợ giảng của buổi đang ở trạng thái Đã lên lịch.'
BUOI_BU_SAI_TRANG_THAI = 'Chỉ thêm buổi học bù cho buổi đã hủy của lớp chưa kết thúc.'
BUOI_BU_TRONG_QUA_KHU = 'Ngày học bù không được trước hôm nay.'
TB_DAY_THAY_TIEU_DE = 'Bạn được phân công dạy thay'
TB_DAY_THAY_NOI_DUNG = 'Lớp {lop}, {ngay} {gio}, phòng {phong}: bạn dạy thay cho {vang}.'
TB_DAY_THAY_CHO_VANG_NOI_DUNG = 'Buổi lớp {lop} ngày {ngay} {gio} đã có {nguoi} dạy thay.'
TB_HUY_BUOI_TIEU_DE = 'Buổi dạy bị hủy'
TB_HUY_BUOI_NOI_DUNG = 'Buổi lớp {lop} ngày {ngay} {gio} bị hủy do không có người dạy thay.'
TB_BUOI_BU_TIEU_DE = 'Buổi học bù mới'
TB_BUOI_BU_NOI_DUNG = 'Lớp {lop} có buổi học bù ngày {ngay} {gio}, phòng {phong}.'
TB_DOI_TRO_GIANG_TIEU_DE = 'Thay đổi trợ giảng'
TB_DOI_TRO_GIANG_NOI_DUNG = 'Buổi lớp {lop} ngày {ngay} {gio}: trợ giảng đổi từ {cu} sang {moi}.'

# ===== UC 4 – Chấm công (nguyên văn §10) =====
CHECK_IN_THANH_CONG = 'Check-in thành công lúc {gio}.'                                   # 4.1 – bước 5
NGHI_PHEP_HOM_NAY = 'Hôm nay bạn nghỉ phép.'                                              # 4.1 – 1.1.1
KHONG_CO_LICH_HOM_NAY = 'Hôm nay bạn không có lịch làm việc.'                              # 4.1 – 1.2.1
DA_CHECK_IN = 'Bạn đã thực hiện Check-in hôm nay.'                                         # 4.1 – 3.1.1
CHUA_CHECK_IN = 'Vui lòng thực hiện Check-in trước.'                                       # 4.1 – 6.2.1
GUI_GIAI_TRINH_THANH_CONG = 'Gửi giải trình thành công.'                                   # 4.2 – bước 5
NHAP_LY_DO_GIAI_TRINH = 'Vui lòng nhập lý do giải trình.'                                  # 4.2 – 3.1.1
DA_GIAI_TRINH = 'Ca làm việc này đã được giải trình.'                                      # 4.2 – 1.1.1
BANG_LUONG_DA_CHOT = 'Bảng lương tháng này đã chốt, không thể thay đổi chấm công.'        # 4.2 – 1.2.1 và 4.4 – 5.3.1
KHONG_CO_DU_LIEU_CHAM_CONG = 'Không có dữ liệu chấm công trong khoảng thời gian đã chọn.'  # 4.3 – 4.1.1 và 4.5 – 3.1.1
# (UC 4.4 dùng lại VUI_LONG_NHAP_LY_DO_TU_CHOI và YEU_CAU_DA_XU_LY đã khai báo ở UC 2.6)

# --- Câu BỔ SUNG cho UC 4 (§10 chưa ghi nguyên văn) ---
CHECK_OUT_THANH_CONG = 'Check-out thành công lúc {gio}. Tổng thời gian làm việc: {tong}.'
DA_CHECK_OUT = 'Bạn đã thực hiện Check-out cho ca này.'
CHON_CA_CHAM_CONG = 'Bạn có nhiều ca trong ngày, vui lòng chọn ca cần chấm công.'
CA_KHONG_HOP_LE = 'Ca được chọn không thuộc lịch làm việc hôm nay của bạn.'
CHI_NHAN_SU_HOAT_DONG_CHAM_CONG = 'Chỉ nhân sự đang làm việc mới chấm công.'
KHONG_CO_LOI_DE_GIAI_TRINH = 'Bản ghi chấm công này không có lỗi cần giải trình.'
KHONG_XEM_BAN_GHI_CHAM_CONG = 'Bạn không có quyền xem bản ghi chấm công này.'
KHONG_CO_QUYEN_DUYET_GIAI_TRINH = 'Bạn không có quyền duyệt giải trình này.'
DA_CHAP_THUAN_GIAI_TRINH = 'Đã chấp thuận giải trình.'
DA_TU_CHOI_GIAI_TRINH = 'Đã từ chối giải trình.'
TB_GIAI_TRINH_MOI_TIEU_DE = 'Giải trình chấm công chờ duyệt'
TB_GIAI_TRINH_MOI_NOI_DUNG = '{nhan_su} gửi giải trình cho ngày {ngay} ({loi}).'
TB_KET_QUA_GIAI_TRINH_TIEU_DE = 'Kết quả giải trình chấm công'
TB_GIAI_TRINH_DUOC_CHAP_THUAN = 'Giải trình ngày {ngay} của bạn đã được chấp thuận, ngày công được tính đủ.'
TB_GIAI_TRINH_BI_TU_CHOI = 'Giải trình ngày {ngay} của bạn bị từ chối. Lý do: {ly_do}'

# ===== UC 7 – Lương (nguyên văn §10) =====
LUU_CAU_HINH_THANH_CONG = 'Lưu cấu hình lương thành công.'                                  # 7.1 – bước 7
NGAY_AP_DUNG_SAI = 'Ngày áp dụng phải sau ngày áp dụng của cấu hình hiện tại.'             # 7.1 – 5.1.1
CAU_HINH_THANG_DA_CHOT = 'Không thể áp dụng cấu hình cho tháng đã chốt lương.'              # 7.1 – 5.3.1
BANG_LUONG_DA_TON_TAI = 'Bảng lương tháng này đã tồn tại.'                                  # 7.2 – 3.1.1
CON_GIAI_TRINH_CHO_DUYET = 'Còn {so} giải trình chấm công chờ duyệt trong tháng. Vui lòng xử lý trước khi lập bảng lương.'   # 7.2 – 3.2.1
NHAN_SU_THIEU_CAU_HINH = 'Các nhân sự sau chưa có cấu hình lương: {ds}.'                    # 7.2 – 3.3.1
THANG_CHUA_KET_THUC = 'Chỉ lập bảng lương cho tháng đã kết thúc.'                           # 7.2 – 3.4.1
THUC_NHAN_AM = 'Thực nhận của {ten} đang âm, vui lòng kiểm tra các khoản khấu trừ.'         # 7.2 – 10.1.1
PHIEU_LUONG_DA_PHAT_HANH = 'Phiếu lương tháng {thang}/{nam} đã được phát hành.'              # 7.2 – bước 13
CHUA_CO_PHIEU_LUONG = 'Chưa có phiếu lương nào được phát hành.'                              # 7.3 – 1.1.1
KHONG_XEM_PHIEU_LUONG = 'Bạn không có quyền xem phiếu lương này.'                            # 7.3 – 3.1.1 (trang 403)

# --- Câu BỔ SUNG cho UC 7 (§10 chưa ghi nguyên văn) ---
NHAN_SU_KHONG_CAU_HINH_LUONG = 'Chỉ cấu hình lương cho nhân sự đang Onboarding hoặc đang làm việc.'
SO_TIEN_AM = 'Số tiền không được âm.'
LUONG_CO_BAN_PHAI_DUONG = 'Lương cơ bản của nhân sự Full-time phải lớn hơn 0.'
DON_GIA_GIO_PHAI_DUONG = 'Đơn giá giờ của nhân sự Part-time phải lớn hơn 0.'
SO_TIEN_PHAI_DUONG = 'Số tiền phải lớn hơn 0.'
CHUA_CO_BANG_LUONG = 'Chưa có bảng lương tháng này.'
BANG_LUONG_DA_CHOT_KHONG_TINH_LAI = 'Bảng lương tháng này đã chốt, không thể tính lại.'
BANG_LUONG_KHONG_SUA_DUOC = 'Bảng lương đã chốt, không thể thêm hoặc xóa khoản nào.'
BANG_LUONG_DA_CHOT_ROI = 'Bảng lương tháng này đã được chốt.'
PHAI_CHOT_TRUOC_KHI_PHAT_HANH = 'Vui lòng chốt bảng lương trước khi phát hành phiếu lương.'
DA_PHAT_HANH_ROI = 'Phiếu lương tháng này đã được phát hành.'
NHOM_KHONG_NHAP_TAY = 'Nhóm khoản này do hệ thống tự tính, không nhập tay.'
CHON_KHOAN_CONG_HAY_TRU = 'Khoản "Khác" phải chọn là khoản cộng hay khoản trừ.'
CHI_XOA_KHOAN_THU_CONG = 'Chỉ xóa được khoản do Kế toán nhập thủ công.'
KHOI_TAO_THANH_CONG = 'Đã khởi tạo bảng lương cho {so} nhân sự.'
TINH_LAI_THANH_CONG = 'Đã tính lại bảng lương ({so} nhân sự).'
CHOT_BANG_LUONG_THANH_CONG = 'Đã chốt bảng lương ({so} nhân sự).'
PHAT_HANH_THANH_CONG = 'Đã phát hành {so} phiếu lương.'
THEM_KHOAN_THANH_CONG = 'Đã thêm khoản vào bảng lương.'
XOA_KHOAN_THANH_CONG = 'Đã xóa khoản khỏi bảng lương.'
TB_PHIEU_LUONG_TIEU_DE = 'Phiếu lương mới'

# ===== UC 9 – Dashboard & Tác vụ hằng ngày (nguyên văn §10) =====
CHUA_CO_HO_SO_NHAN_SU = 'Tài khoản chưa có hồ sơ nhân sự. Vui lòng liên hệ Quản trị viên.'   # 9.1 – 1.3.1
CHUA_CO_DU_LIEU = 'Chưa có dữ liệu phát sinh'                                                # 9.1 – 1.2.1
TAC_VU_BUOC_LOI = 'Tác vụ hằng ngày: bước {buoc} gặp lỗi.'                                   # 9.2 – 1.2.1

# --- Câu BỔ SUNG cho UC 9 (§10 chưa ghi nguyên văn) ---
TB_TAC_VU_LOI_TIEU_DE = 'Tác vụ hằng ngày gặp lỗi'
TAC_VU_CHAY_XONG = 'Đã chạy tác vụ hằng ngày cho ngày {ngay}: xử lý {tong} bản ghi.'
TAC_VU_CO_BUOC_LOI = 'Có {so} bước gặp lỗi, các bước còn lại vẫn chạy xong.'
TB_GIAY_TO_QL_TIEU_DE = 'Giấy tờ nhân sự sắp hết hạn'
TB_GIAY_TO_QL_NOI_DUNG = 'Giấy tờ {ten} của {nhan_su} {tinh_trang}.'
TB_HOP_DONG_HAN_TIEU_DE = 'Hợp đồng sắp hết hạn'
TB_HOP_DONG_HAN_NOI_DUNG = 'Hợp đồng {so_hd} của {nhan_su} {tinh_trang}.'
TB_VANG_MAT_TIEU_DE = 'Vắng mặt ngày {ngay}'
TB_VANG_MAT_NOI_DUNG = 'Hệ thống ghi nhận bạn vắng mặt ngày {ngay} ({gio}). Nếu có lý do, vui lòng gửi giải trình.'
TB_THIEU_CHECKOUT_TIEU_DE = 'Quên check-out ngày {ngay}'
TB_THIEU_CHECKOUT_NOI_DUNG = 'Bạn chưa check-out ngày {ngay} ({gio}). Vui lòng gửi giải trình.'
