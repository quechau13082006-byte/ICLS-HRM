# ROADMAP — Website Quản lý nhân sự Trung tâm tiếng Hàn ICLS

> **File này tự đủ cho giai đoạn code.** Mọi thứ coding agent cần đều nằm ở đây: bối cảnh, công nghệ, quyết định thiết kế, phân quyền, tham số, 20 bảng dữ liệu, vòng đời trạng thái, đặc tả đầy đủ 38 use case, thứ tự làm và kiểm thử.
>
> File được sinh từ **cùng một nguồn dữ liệu** với `DAC_TA_UC_ERD.docx` (bản nộp báo cáo), nên hai tài liệu luôn khớp nhau. Không cần đính kèm file Word khi code.
>
> Mục tiêu: **ít công nghệ, code tường minh, bám sát logic vận hành**. Sinh viên phải giải thích được từng bước khi thầy hỏi.

**Mục lục**

0. Cách dùng tài liệu & luật cho coding agent
1. Bối cảnh nghiệp vụ
2. Công nghệ
3. Cấu trúc code & quy ước
4. Quyết định đã chốt, đơn giản hóa, giả định
5. Người dùng & phân quyền
6. Tham số nghiệp vụ
7. Cơ sở dữ liệu (20 bảng)
8. Vòng đời trạng thái
9. Hàm dùng chung & định nghĩa tính toán
10. Đặc tả use case (38 UC)
11. Thứ tự làm (Phase)
12. Kiểm thử & kịch bản demo
13. Hoàn thành khi

---

## 0. Cách dùng tài liệu & luật cho coding agent

**Thứ tự đọc:** §1–§4 để nắm bối cảnh và quyết định → §11 để biết thứ tự làm. Khi bắt đầu một Phase, đọc kỹ các use case (§10), các bảng (§7) và hàm dùng chung (§9) của Phase đó.

**Luật bắt buộc:**

1. **Chỉ dùng 3 công nghệ ở §2.** Không cài thêm thư viện Python/JavaScript nào. Không REST API, React, Celery, HTMX, Chart.js, thư viện lịch, thư viện PDF, Pillow, django-allauth.
2. **Code tường minh:**
   - View viết dạng hàm (function-based view).
   - Không dùng signals, không viết middleware riêng, không dùng class-based generic view.
   - Biến đặt tên rõ nghĩa; ghi chú tiếng Việt.
3. **Mỗi bước nghiệp vụ là một hàm trong `services.py`.**
   - Docstring ghi mã UC và số bước ở §10. Ví dụ: `"""UC 5.2 – bước 6–7: duyệt đơn, trừ quỹ phép, tạo yêu cầu dạy thay."""`
   - View chỉ làm: kiểm tra quyền → nhận form → gọi service → hiển thị kết quả.
4. **Ghi nhiều bảng cùng lúc thì bọc `transaction.atomic`.** §10 ghi rõ "trong một giao dịch" ở các bước này.
5. **Hàm phụ thuộc thời gian nhận tham số ngày/giờ** (`hom_nay`, `bay_gio`, mặc định là hiện tại), để test truyền ngày cố định.
6. **Câu thông báo copy đúng nguyên văn từ §10** (phần trong ngoặc kép “…”). Gom tại `core/thong_bao.py`.
7. **Tên bảng, tên trường, kiểu dữ liệu, enum, ràng buộc lấy đúng §7.** Mỗi bảng nằm đúng app ghi ở §7.3. Không tự thêm hoặc đổi tên trường.
8. **Tuân thủ ranh giới giữa các app ở §3.2:** mỗi app chỉ ghi vào bảng của chính mình; muốn thay đổi dữ liệu app khác thì gọi service của app đó.
9. **Tham số nghiệp vụ (§6) đặt trong `settings.py`**, mục `# THAM SỐ NGHIỆP VỤ`. Không ghi số cứng trong code.
10. **Xong mỗi Phase phải có:**
   - Test của Phase chạy qua (`python manage.py test`).
   - Cập nhật `docs/GIAI_THICH.md` (viết cho người không biết code): màn hình → bảng nào thay đổi → trạng thái chuyển thế nào → hàm service nào thực hiện.
   - Đánh dấu ✅ các dòng đã xong ở §12.2.
11. **Gặp điểm tài liệu chưa nói rõ:** chọn cách đơn giản nhất phù hợp với §4, ghi vào `docs/GIAI_THICH.md` mục "Giả định khi code", không tự mở rộng tính năng.

---

## 1. Bối cảnh nghiệp vụ

**ICLS** là trung tâm tiếng Hàn quy mô khoảng **40 nhân sự, 10 phòng học, 20 lớp**. Hệ thống thay thế việc quản lý nhân sự bằng giấy tờ, Excel và tin nhắn rời rạc.

**Các nhóm nhân sự:**

| Nhóm | Loại hình | Cách xếp lịch | Cách tính lương |
|---|---|---|---|
| Giáo viên | Full-time | Ca cố định: Ca 1 (08:00–17:00) hoặc Ca 2 (13:00–21:00), Thứ 2 – Thứ 7; dạy các lớp nằm trong ca | Lương cơ bản theo ngày công + phụ cấp mỗi lớp |
| Quản lý vận hành, Kế toán | Full-time | Ca cố định (thường Ca 1) | Lương cơ bản theo ngày công (+ phụ cấp trách nhiệm) |
| Trợ giảng | Part-time | Theo buổi dạy được phân công | Đơn giá giờ × giờ công |
| Staff (Lễ tân, Tư vấn…) | Part-time | Giữ chỗ vào khung ca do Quản lý mở | Đơn giá giờ × giờ công |

**Vòng đời nhân sự (luồng xuyên suốt hệ thống):**

```
Tuyển dụng (UC8) → Onboarding (UC 2.5) → Hợp đồng (UC3) → Phân công lớp / xếp ca (UC6)
→ Chấm công, giải trình (UC4) · Nghỉ phép, dạy thay (UC5, UC 6.4) → Lương (UC7)
→ Gia hạn hoặc Thanh lý hợp đồng (UC3)
```

**Bốn vai trò đăng nhập:** Super Admin (SA), Quản lý (QL), Kế toán (KT), Nhân viên (NV). Chi tiết ở §5.

---

## 2. Công nghệ (chỉ 3)

| # | Công nghệ | Dùng để làm gì |
|---|---|---|
| 1 | **Python 3.12 + Django 5.2 LTS** | Toàn bộ xử lý và giao diện HTML (Django template), đăng nhập bằng session, form, ORM, gửi email, lệnh quản trị (management command), trang admin để kiểm tra dữ liệu |
| 2 | **SQLite** | Cơ sở dữ liệu có sẵn trong Python, một file `db.sqlite3` |
| 3 | **Bootstrap 5 qua CDN** | Giao diện (menu, bảng, form, thẻ số liệu), màu xanh lá theo thiết kế Figma |

Những thứ không dùng thư viện, và cách làm thay:

| Nhu cầu | Cách làm |
|---|---|
| Lịch (UC 6.2) | Bảng HTML 7 cột theo tuần, kèm chế độ xem một ngày |
| Biểu đồ (UC 9.1) | Thẻ số liệu, bảng nhỏ, thanh `progress` của Bootstrap |
| Phiếu lương PDF (UC 7.3) | Nút "In / Lưu PDF" gọi `window.print()` với CSS `@media print` |
| Ảnh đại diện | `FileField` + kiểm tra đuôi `.jpg/.png`, ≤ 2 MB (không cần Pillow) |
| Tác vụ hằng ngày (UC 9.2) | Lệnh `python manage.py chay_tac_vu_ngay`, cộng nút của Super Admin |
| Email | Khi demo dùng `django.core.mail.backends.console.EmailBackend` (in ra terminal) |
| Xác nhận thao tác | `onclick="return confirm('…')"` |

---

## 3. Cấu trúc code & quy ước

### 3.1 Cấu trúc thư mục (10 app)

```
icls_hrm/
├─ manage.py
├─ config/          settings.py (mục THAM SỐ NGHIỆP VỤ), urls.py
├─ core/            Dùng chung: base.html + menu theo vai trò, @role_required, co_quyen_duyet,
│                   tao_thong_bao, ghi_nhat_ky, thong_bao.py, view tải file có kiểm tra quyền,
│                   trang 403, danh sách thông báo, lệnh tao_du_lieu_mau
│                   Bảng: notifications, activity_logs
├─ accounts/        UC1 Xác thực & Quản lý người dùng      Bảng: users
├─ recruitment/     UC8 Tuyển dụng                         Bảng: recruitment_campaigns, candidates, recruitment_rounds
├─ employees/       UC2 Quản lý nhân sự                    Bảng: employees, employee_documents
├─ contracts/       UC3 Quản lý hợp đồng                   Bảng: contracts
├─ schedule/        UC6 Lịch làm việc & Phân công          Bảng: classes, class_assignments, teaching_sessions,
│                                                                shift_assignments, substitute_requests
├─ leave/           UC5 Quản lý nghỉ phép                  Bảng: leave_requests, leave_balances
├─ attendance/      UC4 Quản lý chấm công                  Bảng: attendance
├─ payroll/         UC7 Quản lý lương                      Bảng: salary_configs, payrolls, payroll_details
├─ dashboard/       UC9 Dashboard (9.1) + tác vụ hằng ngày (9.2, lệnh chay_tac_vu_ngay). Không có bảng
├─ templates/       base.html, 403.html + mỗi app một thư mục con (templates/<app>/...)
├─ static/          1 file CSS chỉnh màu
└─ docs/GIAI_THICH.md
```

**Nguyên tắc chia: 1 phân hệ use case = 1 app** (UC1 → `accounts`, UC2 → `employees`, …, UC9 → `dashboard`), cộng `core` cho phần dùng chung. Hỏi "code của UC x.y ở đâu?" thì mở đúng app của phân hệ x.

Mỗi app có cùng bộ file:

| File | Chứa gì |
|---|---|
| `models.py` | Các bảng của app (§7.3) và Enum (`TextChoices`) |
| `forms.py` | Form nhập liệu, kiểm tra định dạng |
| `services.py` | Luật nghiệp vụ, mỗi bước UC một hàm, ghi nhiều bảng thì dùng transaction |
| `views.py` | Kiểm tra quyền → gọi form/service → trả template |
| `urls.py` | Địa chỉ trang, có `app_name` để đặt namespace |
| `admin.py` | Đăng ký bảng vào trang admin để kiểm tra dữ liệu |
| `tests.py` | Test của các UC thuộc app |

### 3.2 Ranh giới giữa các app (tránh lỗi import vòng, dễ kiểm soát)

Ba quy tắc bắt buộc:

1. **Khóa ngoại sang app khác viết bằng chuỗi `'app.Model'`,** ví dụ `models.ForeignKey('employees.Employee', on_delete=models.PROTECT, ...)`. Không import model của app khác vào `models.py`.
2. **Mỗi app chỉ GHI vào bảng của chính mình.** Muốn thay đổi dữ liệu app khác thì gọi hàm trong `services.py` của app đó. Được phép **ĐỌC** (truy vấn) bảng của app khác.
3. **Service gọi sang app khác thì import ngay bên trong hàm,** không import ở đầu file. Ví dụ trong `contracts/services.py`:

```python
def thanh_ly_hop_dong(hop_dong, ngay, ly_do, hinh_thuc, nguoi_thuc_hien):
    """UC 3.4 – bước 4–7."""
    from schedule.services import giai_phong_lich_tuong_lai   # import trong hàm
    from payroll.services import dong_cau_hinh_luong
    ...
```

**Các chỗ gọi chéo giữa app** (ai nhờ ai làm gì):

| Nghiệp vụ (UC) | App gọi | Gọi service của app → để làm gì |
|---|---|---|
| 1.4 Sửa tài khoản cá nhân | accounts | employees → đồng bộ họ tên, SĐT vào hồ sơ |
| 1.5, 2.5 Tạo tài khoản | accounts, employees | accounts → tạo user, gửi link đặt mật khẩu |
| 2.5 Onboarding | employees | accounts → tạo user · leave → tạo quỹ phép · recruitment → đánh dấu ứng viên HIRED |
| 3.1, 3.3 Thêm / gia hạn hợp đồng | contracts | employees → đổi `employment_type`, chuyển ONBOARDING → ACTIVE |
| 3.4 Thanh lý | contracts | employees → đổi status · accounts → khóa tài khoản · schedule → đóng phân công, giải phóng buổi/ca, tạo yêu cầu dạy thay · payroll → đóng cấu hình lương |
| 4.1, 9.2 Lịch dự kiến | attendance | đọc employees (ca), schedule (ca, buổi dạy), leave (đơn nghỉ) |
| 4.2, 4.4, 5.1, 7.1 Khóa tháng đã chốt | attendance, leave, payroll | payroll → `thang_da_chot` |
| 5.2 Duyệt đơn nghỉ | leave | schedule → tìm buổi bị ảnh hưởng, tạo yêu cầu dạy thay |
| 6.1, 6.3, 6.4, 8.2 Kiểm tra trùng lịch | schedule, recruitment | schedule → `kiem_tra_trung_lich` (hàm này đọc thêm leave, recruitment) |
| 7.2 Tính lương | payroll | attendance → `tinh_ngay_cong`, `tinh_gio_cong` · đọc schedule (số lớp), contracts (ngày thanh lý) |
| 8.3 Chuyển sang Onboarding | recruitment | chỉ chuyển trang tới form của employees, không gọi service |
| 9.1 Dashboard, 9.2 Tác vụ hằng ngày | dashboard | đọc mọi app; 9.2 gọi service của employees, schedule, leave, attendance để cập nhật trạng thái |
| Mọi UC | mọi app | core → `tao_thong_bao`, `ghi_nhat_ky`, `role_required`, `co_quyen_duyet` |

### 3.3 Đường đi của một thao tác

Ví dụ Quản lý bấm "Duyệt đơn" (UC 5.2):

```
Trình duyệt → urls.py → view: kiểm tra đăng nhập + vai trò (@role_required)
→ lấy đơn, kiểm tra phạm vi duyệt (co_quyen_duyet: không tự duyệt; QL duyệt NV/KT, SA duyệt QL)
→ leave/services.duyet_don_nghi(...) trong 1 transaction: đổi trạng thái, trừ quỹ phép,
  gọi schedule/services.tao_yeu_cau_day_thay(...), tạo thông báo, ghi nhật ký
→ view chuyển về danh sách kèm câu thông báo thành công
```

### 3.4 Quy ước Django cụ thể

- **Enum** khai báo bằng `models.TextChoices`, tên class đúng tên Enum ở §7. Giá trị lưu là chữ in hoa (ví dụ `'ACTIVE'`); nhãn hiển thị tiếng Việt.
- **Tên bảng** đặt bằng `class Meta: db_table = '...'` đúng tên ở §7.
- **Mỗi model có `__str__`** dễ đọc bằng tiếng Việt (dùng trong trang admin và form).
- **Thông báo trên màn hình** (thành công/lỗi sau khi bấm nút) dùng `django.contrib.messages`. **Thông báo hệ thống** gửi cho người khác (chuông) dùng bảng `notifications`.
- **Lỗi tại trường nhập** dùng `form.add_error(...)` để hiện ngay dưới trường đó.
- **Định dạng hiển thị:**
  - Ngày `dd/mm/yyyy`, giờ `HH:MM`.
  - Tiền viết filter template `vnd` tự làm (ví dụ `1.234.567 đ`).
  - Tiền tính bằng `Decimal`, làm tròn đến đồng (`ROUND_HALF_UP`).
- **File tải lên** lưu dưới `MEDIA_ROOT`. Không mở đường dẫn media công khai; mọi file tải về qua view `tai_file` có kiểm tra quyền.
- **Phân trang** 20 dòng bằng `django.core.paginator.Paginator`.
- **URL** đặt tên tiếng Anh không dấu, có namespace theo app (ví dụ `attendance:check_in`, `leave:approve`).
- **Template** của mỗi app đặt trong `templates/<tên app>/`, ví dụ `templates/leave/don_cho_duyet.html`.
- **Trang 403** dùng template `403.html` hiển thị câu thông báo của UC.

---

## 4. Quyết định đã chốt, đơn giản hóa, giả định

### 4.1 Quyết định đã chốt

| # | Quyết định | UC |
|---|---|---|
| Q1 | **Super Admin là quản trị hệ thống.** SA không có hồ sơ nhân sự, không vận hành nghiệp vụ, chỉ xem một số bảng tổng hợp | 1.5, 9.x |
| Q2 | **Không ai tự duyệt yêu cầu của mình.** Yêu cầu của NV và KT do QL duyệt; yêu cầu của QL (đơn nghỉ, giải trình, giấy tờ) do SA duyệt | 2.6, 4.4, 5.2 |
| Q3 | **QL chỉ tạo tài khoản role EMPLOYEE.** Nâng quyền QL/KT do SA làm, hệ thống tự báo SA | 2.5, 1.5 |
| Q4 | **Nhân viên mới tự đặt mật khẩu qua link** (hiệu lực 24 giờ), không có mật khẩu mặc định | 1.2, 2.5 |
| Q5 | **Tạo hợp đồng đầu tiên** thì nhân sự `ONBOARDING → ACTIVE` | 3.1 |
| Q6 | **Hệ thống không tự kết thúc hợp đồng quá hạn**, chỉ nhắc; QL quyết định gia hạn hay thanh lý | 3.5, 9.2 |
| Q7 | **Ngày thanh lý** nằm trong khoảng [ngày bắt đầu HĐ, hôm nay] | 3.4 |
| Q8 | **Khung ca có N chỗ = N dòng `shift_assignments`** cùng `slot_group`; ai giữ trước được trước | 6.3 |
| Q9 | **Trợ giảng làm theo buổi dạy** (`actual_assistant`); ca làm việc chỉ cho Lễ tân, Tư vấn… | 4.1, 6.x |
| Q10 | **Duyệt đơn nghỉ ảnh hưởng buổi dạy** thì tự tạo yêu cầu dạy thay; QL chọn trực tiếp người thay | 5.2, 6.4 |
| Q11 | **Chỉ Full-time có phép năm** (12 ngày) | 2.5, 5.1, 9.2 |
| Q12 | **Đi trễ không tự trừ lương**; KT dùng `ADJUSTMENT_DECREASE` nếu cần. **Thuế TNCN hệ thống tự tính** (Full-time: giảm trừ bản thân rồi lũy tiến; Part-time: khấu trừ cố định từ ngưỡng), KT vẫn nhập thêm tay được | 7.2 |
| Q13 | **Bảng lương có 2 nút:** "Chốt" (LOCKED, khóa sửa) và "Phát hành" (SENT, NV mới thấy) | 7.2 |
| Q14 | **Mỗi bản ghi chấm công chỉ được giải trình một lần** | 4.2 |
| Q15 | **"Tải bản mới" giấy tờ cập nhật chính bản ghi cũ**, chuyển về PENDING | 2.2 |
| Q16 | **Full-time làm theo ca cố định ghi trong hồ sơ** (`employees.work_shift`): Ca 1 08:00–17:00 hoặc Ca 2 13:00–21:00, Thứ 2 – Thứ 7. Nghỉ nửa ngày = nửa đầu/nửa sau ca. Giáo viên chỉ được gợi ý dạy lớp nằm trọn trong ca của mình | 2.5, 4.1, 5.1, 5.2, 6.1, 6.4 |
| Q17 | **Chia code thành 10 app: 1 phân hệ use case = 1 app**, cộng `core` dùng chung; ranh giới giữa app theo §3.2 | toàn bộ |

### 4.2 Đơn giản hóa (giải thích được với thầy)

| Nội dung | Cách làm | Lý do |
|---|---|---|
| Đăng nhập bằng Google | **Không làm** | Cần thêm thư viện và cấu hình Google Cloud, trái mục tiêu tối giản |
| Kiểm tra IP Wi-Fi khi chấm công | **Không làm**, chấm công bằng nút bấm | Đã bỏ trong đặc tả |
| Lọc GV "phù hợp chuyên môn" | Chỉ lọc GV ACTIVE, đúng ca, không trùng giờ, không nghỉ phép | Không có dữ liệu chuyên môn để so |
| Kiểm tra trùng phòng | So khớp tên phòng cùng giờ | Không có bảng phòng học |
| Dạy thay | QL chọn trực tiếp, không mời lần lượt | Đơn giản, đủ cho 40 nhân sự |
| Lịch Tháng/Tuần/Ngày | Tuần và Ngày; Quản lý/SA xem bảng theo nhân sự (gồm ca cố định Full-time) và bảng theo phòng | Không dùng thư viện lịch |
| PDF phiếu lương | In / Lưu PDF bằng trình duyệt | Không dùng thư viện PDF |
| Xuất báo cáo Excel/PDF | Không làm, chỉ có Dashboard | Đã bỏ trong đặc tả |

### 4.3 Giả định (nếu trung tâm khác thì chỉ cần sửa tham số hoặc một hàm)

- **Ca Full-time cố định theo người**, không luân phiên theo tuần/ngày. Quản lý đổi được trong hồ sơ, có hiệu lực từ ngày hôm sau.
- **Chủ nhật nghỉ; chưa xét ngày lễ.**
- **Không làm thêm giờ:** giờ công không vượt quá giờ dự kiến.
- **Cấu hình lương đổi giữa tháng:** dùng cấu hình hiệu lực vào ngày cuối tháng (hoặc ngày thanh lý).

---

## 5. Người dùng & phân quyền

**Vai trò:**

- **Super Admin:** quản trị hệ thống. Quản lý tài khoản và phân quyền, xem nhật ký hoạt động, chạy tác vụ hằng ngày. Không có hồ sơ nhân sự. Là cấp duyệt các yêu cầu của tài khoản Quản lý.
- **Quản lý:** điều hành vòng đời nhân sự: tuyển dụng, onboarding, hợp đồng, phân công lớp, xếp ca, duyệt yêu cầu của Nhân viên và Kế toán.
- **Kế toán:** cấu hình lương, lập, chốt và phát hành bảng lương; xem bảng tổng hợp công và hợp đồng (chỉ xem).
- **Nhân viên:** giáo viên, trợ giảng, staff. Chấm công, xem lịch, giữ chỗ ca (Part-time), gửi đơn nghỉ, giải trình, cập nhật hồ sơ, xem phiếu lương. Quản lý và Kế toán cũng là nhân sự nên cũng dùng các chức năng cá nhân này.

**Nguyên tắc phê duyệt (Q2):** không ai tự duyệt yêu cầu của mình; yêu cầu của NV và KT do QL duyệt; yêu cầu của tài khoản role MANAGER do SA duyệt.

**Bảng phân quyền.** Ký hiệu: ✓ = có quyền; ○ = chỉ trên dữ liệu của chính mình; Xem = chỉ xem; – = không có quyền.

| Mã UC | Chức năng | Super Admin | Quản lý | Kế toán | Nhân viên |
|---|---|---|---|---|---|
| 1.1–1.4, 1.6 | Đăng nhập, quên/đổi mật khẩu, tài khoản cá nhân, đăng xuất | ✓ | ✓ | ✓ | ✓ |
| 1.5 | Quản lý tài khoản người dùng | ✓ | – | – | – |
| 2.1 | Xem danh sách nhân sự | Xem đầy đủ | ✓ đầy đủ | Thông tin cơ bản | Thông tin cơ bản |
| 2.2, 2.3 | Cập nhật, xem hồ sơ cá nhân | – | ○ | ○ | ○ |
| 2.4, 2.5 | Cảnh báo giấy tờ; Onboarding & quản lý hồ sơ | – | ✓ | – | – |
| 2.6 | Duyệt giấy tờ, chứng chỉ | Giấy tờ của QL | Giấy tờ của NV, KT | – | – |
| 3.1, 3.3, 3.4, 3.5 | Thêm, gia hạn, thanh lý, theo dõi hợp đồng | – | ✓ | – | – |
| 3.2 | Tra cứu chi tiết hợp đồng | – | ✓ tất cả | Xem tất cả | ○ |
| 4.1, 4.2, 4.3 | Chấm công, gửi giải trình, lịch sử chấm công | – | ○ | ○ | ○ |
| 4.4 | Duyệt giải trình chấm công | Giải trình của QL | Giải trình của NV, KT | – | – |
| 4.5 | Bảng tổng hợp công | Xem | ✓ | ✓ | – |
| 5.1, 5.3 | Gửi đơn nghỉ, tra cứu quỹ phép | – | ○ | ○ | ○ |
| 5.2 | Duyệt đơn nghỉ phép | Đơn của QL | Đơn của NV, KT | – | – |
| 5.4 | Tổng hợp nghỉ phép | Xem | ✓ | – | – |
| 6.1, 6.4 | Tạo & phân công lớp; xử lý dạy thay | – | ✓ | – | – |
| 6.2 | Xem lịch làm việc & lịch lớp học | Xem toàn bộ | ✓ toàn bộ | ○ + lịch lớp | ○ + lịch lớp |
| 6.3 | Khung ca Part-time | – | Tạo, chốt ca | – | Giữ chỗ (PT) |
| 7.1, 7.2 | Cấu hình lương; lập & chốt bảng lương | – | – | ✓ | – |
| 7.3 | Tra cứu phiếu lương | – | ○ | ○ | ○ |
| 8.1–8.3 | Tuyển dụng | – | ✓ | – | – |
| 9.1 | Dashboard theo vai trò | ✓ | ✓ | ✓ | ✓ |
| 9.2 | Chạy tác vụ hằng ngày (thủ công) | ✓ | – | – | – |

**Cài đặt:**

- **`@role_required(*roles)`** chặn sai vai trò và trả trang 403.
- **Dữ liệu "của mình"** được lọc ngay trong truy vấn (`filter(employee=request.user.employee)`). Người sửa ID trên URL không lấy được dữ liệu của người khác.
- **`co_quyen_duyet(nguoi_duyet, nguoi_gui)`** dùng chung cho 2.6, 4.4, 5.2:
  - Người duyệt là người gửi → **không được**.
  - Người gửi có role MANAGER → chỉ **SUPER_ADMIN** được duyệt.
  - Người gửi là NV hoặc KT → **MANAGER** được duyệt.
- **Super Admin không có `employee`:** ẩn menu cá nhân. Mọi view cá nhân kiểm tra `hasattr(request.user, 'employee')`.

---

## 6. Tham số nghiệp vụ

| Tham số | Giá trị | Dùng ở UC |
|---|---|---|
| Ngày làm việc của Full-time | Thứ 2 – Thứ 7 | 4.1, 5.1, 9.2 |
| Ca 1 của Full-time (SHIFT_1) | 08:00 – 17:00 | 2.5, 4.1, 6.1, 9.2 |
| Ca 2 của Full-time (SHIFT_2) | 13:00 – 21:00 | 2.5, 4.1, 6.1, 9.2 |
| Mốc chia nửa ca (nghỉ nửa ngày) | Ca 1: 12:00 · Ca 2: 17:00 · Part-time: 12:00 | 4.1, 5.1, 5.2 |
| Số phút đi trễ được cho phép | 5 phút | 4.1 |
| Ngày công chuẩn của tháng | 26 ngày | 7.2 |
| Số ngày phép năm mặc định | 12 ngày (chỉ Full-time) | 2.5, 5.3, 9.2 |
| Ngưỡng cảnh báo hết hạn | 30 ngày; nhắc vào các mốc còn 30, 7 và 0 ngày | 2.4, 3.5, 9.2 |
| Đơn giá giờ Part-time mặc định | 35.000 đ/giờ | 7.1 |
| Giảm trừ bản thân khi tính thuế TNCN (Full-time) | 15.500.000 đ/tháng | 7.2 |
| Biểu thuế lũy tiến TNCN (Full-time) | đến 10 triệu 5% · 10–30 triệu 10% · 30–60 triệu 20% · 60–100 triệu 30% · trên 100 triệu 35% | 7.2 |
| Khấu trừ thuế Part-time | 10% toàn bộ thu nhập tháng, từ 2.000.000 đ trở lên | 7.2 |
| Hiệu lực đường dẫn đặt mật khẩu | 24 giờ | 1.2, 1.5, 2.5 |
| Thời lượng một vòng phỏng vấn/Demo | 60 phút (dùng khi kiểm tra trùng lịch) | 8.2 |
| Thang điểm tuyển dụng | 0 – 10 | 8.3 |
| File giấy tờ, CV, minh chứng | PDF/JPG/PNG, tối đa 5 MB (CV chỉ PDF) | 2.2, 4.2, 8.1 |
| Ảnh đại diện | .jpg/.png, tối đa 2 MB | 1.4 |
| Số dòng mỗi trang danh sách | 20 | 2.1 |
| Giờ chạy tác vụ hằng ngày | 06:00 | 9.2 |

Khai báo trong `settings.py`:

```python
# ===== THAM SỐ NGHIỆP VỤ =====
NGAY_LAM_VIEC = [0, 1, 2, 3, 4, 5]        # Thứ 2 – Thứ 7 (date.weekday(): 0 = Thứ 2)
CA_FULLTIME = {                           # (giờ bắt đầu, giờ kết thúc, mốc giữa ca)
    "SHIFT_1": ("08:00", "17:00", "12:00"),
    "SHIFT_2": ("13:00", "21:00", "17:00"),
}
MOC_NUA_NGAY_PART_TIME = "12:00"
PHUT_CHO_PHEP_TRE = 5
NGAY_CONG_CHUAN = 26
PHEP_NAM_MAC_DINH = 12
SO_NGAY_CANH_BAO = 30
CAC_MOC_NHAC = [30, 7, 0]
DON_GIA_GIO_PT_MAC_DINH = 35000
THUE_GIAM_TRU_BAN_THAN = 15500000
THUE_BAC_LUY_TIEN = [(10000000, '0.05'), (30000000, '0.10'), (60000000, '0.20'), (100000000, '0.30'), (None, '0.35')]
THUE_PART_TIME_NGUONG = 2000000
THUE_PART_TIME_TY_LE = '0.10'
THOI_LUONG_VONG_TUYEN_DUNG_PHUT = 60
DIEM_TOI_DA = 10
FILE_TOI_DA_MB = 5
ANH_TOI_DA_MB = 2
SO_DONG_MOI_TRANG = 20
PASSWORD_RESET_TIMEOUT = 86400            # 24 giờ
```

---

## 7. Cơ sở dữ liệu (20 bảng)

### 7.1 Quy ước

- **Model `User`** (app `accounts`) kế thừa `AbstractUser`:
  - Đặt `username = None`, `first_name = None`, `last_name = None`.
  - Đặt `USERNAME_FIELD = 'email'`, `REQUIRED_FIELDS = []`.
  - Viết `UserManager` riêng (`create_user`, `create_superuser` theo email).
  - Khai báo `AUTH_USER_MODEL = 'accounts.User'` **trước migration đầu tiên**.
- **Model lớp học** tên `StudyClass`, `db_table = 'classes'` (vì `class` là từ khóa Python).
- **`leave_balances.remaining_days`** là `@property` = `total_days − used_days`, không phải cột.
- **Nhân sự, hợp đồng, chấm công, bảng lương không bao giờ bị xóa;** trạng thái thể hiện bằng `status`. Vì vậy khóa ngoại tới `employees` dùng `on_delete=PROTECT`.
- **Ràng buộc nghiệp vụ** khai báo ngay trong CSDL (`UniqueConstraint`, `CheckConstraint` trong `Meta.constraints`) để dữ liệu sai không thể lưu.
- **Khóa ngoại sang app khác** viết bằng chuỗi `'app.Model'` (§3.2), ví dụ `'recruitment.Candidate'`, `'employees.Employee'`, `settings.AUTH_USER_MODEL` cho User.
- **`weekdays` của lớp** lưu chuỗi như `"0,2,4"`; số khớp với `date.weekday()` của Python (0 = Thứ 2 … 6 = Chủ nhật).

### 7.2 Quan hệ khóa ngoại

| Khóa ngoại (bảng.trường) | Bảng được tham chiếu | Quan hệ | on_delete | Ý nghĩa |
|---|---|---|---|---|
| `employees.user` | `users` | 1 – 1 | PROTECT | Tài khoản đăng nhập |
| `employees.candidate` | `candidates` | 1 – 1 | SET_NULL | Ứng viên nguồn |
| `employee_documents.employee` | `employees` | N – 1 | PROTECT | Nhân sự sở hữu |
| `employee_documents.reviewed_by` | `users` | N – 1 | SET_NULL | Người duyệt |
| `contracts.employee` | `employees` | N – 1 | PROTECT | Nhân sự ký hợp đồng |
| `contracts.previous_contract` | `contracts` | N – 1 | SET_NULL | Hợp đồng trước |
| `recruitment_campaigns.created_by` | `users` | N – 1 | SET_NULL | Người tạo |
| `candidates.campaign` | `recruitment_campaigns` | N – 1 | PROTECT | Đợt tuyển dụng |
| `recruitment_rounds.candidate` | `candidates` | N – 1 | PROTECT | Ứng viên |
| `recruitment_rounds.interviewer` | `users` | N – 1 | PROTECT | Người phỏng vấn / giám sát |
| `class_assignments.study_class` | `classes` | N – 1 | CASCADE | Lớp học |
| `class_assignments.employee` | `employees` | N – 1 | PROTECT | Nhân sự được phân công |
| `teaching_sessions.study_class` | `classes` | N – 1 | CASCADE | Lớp học |
| `teaching_sessions.planned_teacher` | `employees` | N – 1 | PROTECT | Giáo viên dự kiến |
| `teaching_sessions.actual_teacher` | `employees` | N – 1 | PROTECT | Giáo viên thực tế |
| `teaching_sessions.planned_assistant` | `employees` | N – 1 | SET_NULL | Trợ giảng dự kiến |
| `teaching_sessions.actual_assistant` | `employees` | N – 1 | SET_NULL | Trợ giảng thực tế |
| `shift_assignments.employee` | `employees` | N – 1 | PROTECT | Nhân sự nhận ca |
| `shift_assignments.assigned_by` | `users` | N – 1 | SET_NULL | Người chốt ca |
| `attendance.employee` | `employees` | N – 1 | PROTECT | Nhân sự |
| `attendance.shift_assignment` | `shift_assignments` | N – 1 | PROTECT | Ca làm việc |
| `attendance.explanation_reviewed_by` | `users` | N – 1 | SET_NULL | Người duyệt giải trình |
| `leave_requests.employee` | `employees` | N – 1 | PROTECT | Nhân sự gửi đơn |
| `leave_requests.reviewed_by` | `users` | N – 1 | SET_NULL | Người duyệt |
| `leave_balances.employee` | `employees` | N – 1 | PROTECT | Nhân sự |
| `substitute_requests.teaching_session` | `teaching_sessions` | N – 1 | PROTECT | Buổi dạy cần thay |
| `substitute_requests.leave_request` | `leave_requests` | N – 1 | SET_NULL | Đơn nghỉ gốc |
| `substitute_requests.substitute_employee` | `employees` | N – 1 | PROTECT | Giáo viên dạy thay |
| `substitute_requests.manager_confirmed_by` | `users` | N – 1 | SET_NULL | Quản lý chốt |
| `salary_configs.employee` | `employees` | N – 1 | PROTECT | Nhân sự áp dụng |
| `payrolls.employee` | `employees` | N – 1 | PROTECT | Nhân sự |
| `payrolls.created_by` | `users` | N – 1 | SET_NULL | Người lập |
| `payroll_details.payroll` | `payrolls` | N – 1 | CASCADE | Bảng lương |
| `notifications.recipient` | `users` | N – 1 | CASCADE | Người nhận |
| `activity_logs.user` | `users` | N – 1 | SET_NULL | Người thực hiện |

### 7.3 Chi tiết từng bảng

#### 7.3.1. `users` – Tài khoản hệ thống

Model `User` · app `accounts`

Kế thừa AbstractUser của Django. Bỏ các trường username, first_name, last_name (đặt = None); đăng nhập bằng email (USERNAME_FIELD = 'email') với UserManager riêng. Các trường password, last_login, is_staff, is_superuser, date_joined có sẵn từ AbstractUser.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã tài khoản | `AutoField(primary_key=True)` | PK |  |
| `email` | Email đăng nhập | `EmailField(max_length=255, unique=True)` | NOT NULL, UNIQUE | Dùng làm tên đăng nhập |
| `password` | Mật khẩu đã mã hóa | `CharField(max_length=128)` | NOT NULL | Có sẵn. Chưa dùng được khi nhân viên chưa tự đặt mật khẩu (UC 1.2) |
| `full_name` | Họ và tên hiển thị | `CharField(max_length=150, blank=True)` |  | Đồng bộ từ employees nếu có hồ sơ (UC 1.4, 2.5) |
| `phone` | Số điện thoại | `CharField(max_length=20, blank=True)` |  | Đồng bộ từ employees nếu có hồ sơ |
| `role` | Vai trò hệ thống | `CharField(max_length=20, choices=UserRole.choices, default='EMPLOYEE')` | NOT NULL | Enum UserRole; chỉ Super Admin đổi (UC 1.5) |
| `is_active` | Trạng thái tài khoản | `BooleanField(default=True)` | NOT NULL | False = bị khóa (UC 1.5, 3.4) |
| `avatar` | Ảnh đại diện | `FileField(upload_to='avatars/', blank=True)` |  | Chỉ nhận .jpg/.png ≤ 2 MB; dùng FileField để không cần cài thêm thư viện xử lý ảnh |
| `last_login` | Lần đăng nhập cuối | `DateTimeField(null=True, blank=True)` | NULL | Có sẵn |
| `is_staff, is_superuser` | Quyền vào trang quản trị Django | `BooleanField(default=False)` | NOT NULL | Có sẵn; chỉ dùng cho người phát triển, không liên quan vai trò nghiệp vụ |
| `date_joined` | Thời điểm tạo tài khoản | `DateTimeField(default=timezone.now)` | NOT NULL | Có sẵn |
| `updated_at` | Thời điểm cập nhật | `DateTimeField(auto_now=True)` | NOT NULL |  |

- **Enum `UserRole`:** SUPER_ADMIN · MANAGER · ACCOUNTANT · EMPLOYEE

#### 7.3.2. `employees` – Hồ sơ nhân sự

Model `Employee` · app `employees`

Mỗi nhân sự có đúng một tài khoản. Super Admin không có hồ sơ nhân sự. Mã NV hiển thị = “NV” + id 4 chữ số (ví dụ NV0012), không lưu cột riêng. Nhân sự không bao giờ bị xóa, chỉ đổi status.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã nhân sự | `AutoField(primary_key=True)` | PK |  |
| `user` | Tài khoản đăng nhập | `OneToOneField(User, on_delete=PROTECT, related_name='employee')` | NOT NULL, UNIQUE, FK |  |
| `candidate` | Ứng viên nguồn | `OneToOneField(Candidate, on_delete=SET_NULL, null=True, blank=True, related_name='employee')` | UNIQUE, FK, NULL | Có giá trị nếu tiếp nhận từ tuyển dụng; chặn tạo hồ sơ hai lần |
| `full_name` | Họ và tên | `CharField(max_length=150)` | NOT NULL |  |
| `phone` | Số điện thoại | `CharField(max_length=20)` | NOT NULL |  |
| `gender` | Giới tính | `CharField(max_length=10, choices=Gender.choices, blank=True)` |  | Enum Gender |
| `date_of_birth` | Ngày sinh | `DateField(null=True, blank=True)` | NULL |  |
| `id_card_number` | Số CCCD | `CharField(max_length=20, unique=True, null=True, blank=True)` | UNIQUE, NULL | 12 chữ số |
| `address` | Địa chỉ | `TextField(blank=True)` |  |  |
| `nationality` | Quốc tịch | `CharField(max_length=30, default='Việt Nam')` | NOT NULL |  |
| `department` | Phòng ban | `CharField(max_length=30, choices=Department.choices)` | NOT NULL | Enum Department |
| `position` | Chức danh | `CharField(max_length=30, choices=Position.choices)` | NOT NULL | Enum Position |
| `employment_type` | Loại hình làm việc | `CharField(max_length=20, choices=EmploymentType.choices)` | NOT NULL | Đồng bộ theo hợp đồng ACTIVE (UC 3.1, 3.3) |
| `work_shift` | Ca làm việc Full-time | `CharField(max_length=20, choices=WorkShift.choices, blank=True)` |  | Bắt buộc với Full-time, để trống với Part-time (UC 2.5); quyết định giờ chấm công (UC 4.1) và lớp được gợi ý (UC 6.1) |
| `bank_account` | Tài khoản ngân hàng | `CharField(max_length=100, blank=True)` |  | VD: Vietcombank – 0123456789 |
| `status` | Trạng thái nhân sự | `CharField(max_length=20, choices=EmployeeStatus.choices, default='ONBOARDING')` | NOT NULL | Enum EmployeeStatus |
| `join_date` | Ngày vào làm | `DateField()` | NOT NULL |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |
| `updated_at` | Thời điểm cập nhật | `DateTimeField(auto_now=True)` | NOT NULL |  |

- **Enum `Gender`:** MALE · FEMALE · OTHER
- **Enum `Department`:** ACADEMIC · HR_ADMIN · ACCOUNTING
- **Enum `Position`:** TEACHER · TEACHING_ASSISTANT · STAFF · MANAGER · ACCOUNTANT
- **Enum `EmploymentType`:** FULL_TIME · PART_TIME
- **Enum `WorkShift`:** SHIFT_1 (Ca 1: 08:00–17:00) · SHIFT_2 (Ca 2: 13:00–21:00)
- **Enum `EmployeeStatus`:** ONBOARDING · ACTIVE · RESIGNED · TERMINATED

#### 7.3.3. `employee_documents` – Giấy tờ, chứng chỉ

Model `EmployeeDocument` · app `employees`

Mỗi giấy tờ được duyệt riêng (UC 2.6). Khi “Tải bản mới” (UC 2.2), chính bản ghi được cập nhật file, ngày và chuyển lại PENDING.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã giấy tờ | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự sở hữu | `ForeignKey(Employee, on_delete=PROTECT, related_name='documents')` | NOT NULL, FK |  |
| `document_type` | Loại giấy tờ | `CharField(max_length=30, choices=DocumentType.choices)` | NOT NULL | Enum DocumentType |
| `document_name` | Tên giấy tờ | `CharField(max_length=150)` | NOT NULL | VD: TOPIK cấp 6 |
| `issue_date` | Ngày cấp | `DateField(null=True, blank=True)` | NULL |  |
| `expiry_date` | Ngày hết hạn | `DateField(null=True, blank=True)` | NULL | Trống = không thời hạn |
| `file_url` | File đính kèm | `FileField(upload_to='employee_documents/')` | NOT NULL | PDF/JPG/PNG ≤ 5 MB; chỉ tải qua trang có kiểm tra quyền |
| `status` | Trạng thái | `CharField(max_length=20, choices=DocumentStatus.choices, default='PENDING')` | NOT NULL | Enum DocumentStatus |
| `rejection_reason` | Lý do từ chối | `TextField(blank=True)` |  | Bắt buộc khi REJECTED |
| `reviewed_by` | Người duyệt | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_documents')` | FK, NULL |  |
| `reviewed_at` | Thời điểm duyệt | `DateTimeField(null=True, blank=True)` | NULL |  |
| `created_at` | Thời điểm tải lên | `DateTimeField(auto_now_add=True)` | NOT NULL |  |
| `updated_at` | Thời điểm cập nhật | `DateTimeField(auto_now=True)` | NOT NULL |  |

- **Enum `DocumentType`:** PERSONAL_ID · CERTIFICATION · OTHER
- **Enum `DocumentStatus`:** PENDING · APPROVED · REJECTED · EXPIRED
- **Ràng buộc của bảng:**
  - CheckConstraint: expiry_date IS NULL hoặc expiry_date ≥ issue_date

#### 7.3.4. `contracts` – Hợp đồng lao động

Model `Contract` · app `contracts`

Mỗi nhân sự chỉ có tối đa một hợp đồng ACTIVE. Gia hạn tạo hợp đồng mới trỏ về hợp đồng cũ qua previous_contract. Hệ thống không tự đổi trạng thái hợp đồng quá hạn (UC 3.5).

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã hợp đồng | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự ký hợp đồng | `ForeignKey(Employee, on_delete=PROTECT, related_name='contracts')` | NOT NULL, FK |  |
| `contract_number` | Số hợp đồng | `CharField(max_length=50, unique=True)` | NOT NULL, UNIQUE |  |
| `employment_type` | Loại hình | `CharField(max_length=20, choices=EmploymentType.choices)` | NOT NULL | FULL_TIME / PART_TIME |
| `start_date` | Ngày bắt đầu | `DateField()` | NOT NULL |  |
| `end_date` | Ngày kết thúc | `DateField(null=True, blank=True)` | NULL | Trống = không xác định thời hạn |
| `previous_contract` | Hợp đồng trước | `ForeignKey('self', on_delete=SET_NULL, null=True, blank=True, related_name='renewals')` | FK, NULL | Lưu vết gia hạn (UC 3.3) |
| `status` | Trạng thái | `CharField(max_length=20, choices=ContractStatus.choices, default='ACTIVE')` | NOT NULL | Enum ContractStatus |
| `termination_date` | Ngày thanh lý | `DateField(null=True, blank=True)` | NULL | UC 3.4 |
| `termination_reason` | Lý do thanh lý | `TextField(blank=True)` |  | UC 3.4 |
| `file_url` | File scan hợp đồng | `FileField(upload_to='contracts/')` | NOT NULL | PDF |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `ContractStatus`:** ACTIVE · EXPIRED · TERMINATED
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['employee'], condition=Q(status='ACTIVE')): mỗi nhân sự tối đa 1 hợp đồng ACTIVE
  - CheckConstraint: end_date IS NULL hoặc end_date > start_date

#### 7.3.5. `recruitment_campaigns` – Đợt tuyển dụng

Model `RecruitmentCampaign` · app `recruitment`

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã đợt tuyển dụng | `AutoField(primary_key=True)` | PK |  |
| `campaign_name` | Tên đợt tuyển dụng | `CharField(max_length=255)` | NOT NULL | VD: Tuyển dụng Q4-2026 |
| `start_date` | Ngày bắt đầu | `DateField()` | NOT NULL |  |
| `end_date` | Ngày kết thúc | `DateField(null=True, blank=True)` | NULL |  |
| `status` | Trạng thái | `CharField(max_length=20, choices=CampaignStatus.choices, default='OPEN')` | NOT NULL | Enum CampaignStatus |
| `created_by` | Người tạo | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_campaigns')` | FK, NULL |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `CampaignStatus`:** OPEN · CLOSED
- **Ràng buộc của bảng:**
  - CheckConstraint: end_date IS NULL hoặc end_date ≥ start_date

#### 7.3.6. `candidates` – Ứng viên

Model `Candidate` · app `recruitment`

Kết quả sơ tuyển ghi tại screening_note (không tạo vòng tuyển dụng riêng cho sơ tuyển).

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã ứng viên | `AutoField(primary_key=True)` | PK |  |
| `campaign` | Đợt tuyển dụng | `ForeignKey(RecruitmentCampaign, on_delete=PROTECT, related_name='candidates')` | NOT NULL, FK |  |
| `full_name` | Họ và tên | `CharField(max_length=150)` | NOT NULL |  |
| `email` | Email | `EmailField(max_length=255)` | NOT NULL |  |
| `phone` | Số điện thoại | `CharField(max_length=20)` | NOT NULL |  |
| `position` | Vị trí ứng tuyển | `CharField(max_length=30, choices=Position.choices)` | NOT NULL | Enum Position |
| `employment_type` | Loại hình ứng tuyển | `CharField(max_length=20, choices=EmploymentType.choices)` | NOT NULL | Quyết định có vòng Demo hay không (UC 8.3) |
| `cv_file` | CV ứng viên | `FileField(upload_to='candidates/cv/', blank=True)` |  | PDF ≤ 5 MB |
| `screening_note` | Ghi chú sơ tuyển | `TextField(blank=True)` |  | UC 8.1 |
| `status` | Trạng thái | `CharField(max_length=30, choices=CandidateStatus.choices, default='NEW')` | NOT NULL | Enum CandidateStatus |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |
| `updated_at` | Thời điểm cập nhật | `DateTimeField(auto_now=True)` | NOT NULL |  |

- **Enum `CandidateStatus`:** NEW · SCREENING (đạt sơ tuyển, chờ phỏng vấn) · INTERVIEWING · TEACHING_TRIAL · PASSED · REJECTED · HIRED
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['campaign', 'email']): một email chỉ xuất hiện một lần trong một đợt

#### 7.3.7. `recruitment_rounds` – Vòng phỏng vấn / dạy thử

Model `RecruitmentRound` · app `recruitment`

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã vòng | `AutoField(primary_key=True)` | PK |  |
| `candidate` | Ứng viên | `ForeignKey(Candidate, on_delete=PROTECT, related_name='recruitment_rounds')` | NOT NULL, FK |  |
| `round_type` | Loại vòng | `CharField(max_length=20, choices=RecruitmentRoundType.choices)` | NOT NULL | Enum RecruitmentRoundType |
| `scheduled_at` | Thời gian diễn ra | `DateTimeField()` | NOT NULL | Mỗi vòng tính 60 phút khi kiểm tra trùng lịch |
| `location` | Địa điểm / link / phòng demo | `CharField(max_length=255, blank=True)` |  |  |
| `interviewer` | Người phỏng vấn / giám sát | `ForeignKey(User, on_delete=PROTECT, related_name='recruitment_interviews')` | NOT NULL, FK | Chỉ tài khoản vai trò MANAGER |
| `status` | Trạng thái vòng | `CharField(max_length=20, choices=RecruitmentRoundStatus.choices, default='SCHEDULED')` | NOT NULL | Enum RecruitmentRoundStatus |
| `result` | Kết quả | `CharField(max_length=20, choices=RecruitmentResult.choices, default='PENDING')` | NOT NULL | Enum RecruitmentResult |
| `score` | Điểm đánh giá | `DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)` | NULL | Thang 0–10 |
| `note` | Nhận xét | `TextField(blank=True)` |  |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `RecruitmentRoundType`:** INTERVIEW · DEMO
- **Enum `RecruitmentRoundStatus`:** SCHEDULED · COMPLETED · CANCELLED
- **Enum `RecruitmentResult`:** PENDING · PASSED · FAILED
- **Ràng buộc của bảng:**
  - CheckConstraint: score IS NULL hoặc 0 ≤ score ≤ 10

#### 7.3.8. `classes` – Lớp học

Model `StudyClass` · app `schedule`

Tên model là StudyClass (vì class là từ khóa của Python), tên bảng giữ là classes. Lịch học lưu có cấu trúc (thứ trong tuần, giờ) để hệ thống tự sinh buổi dạy và kiểm tra trùng lịch.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã lớp | `AutoField(primary_key=True)` | PK |  |
| `class_name` | Tên lớp | `CharField(max_length=150)` | NOT NULL |  |
| `subject` | Môn học / Trình độ | `CharField(max_length=100)` | NOT NULL | VD: Tiếng Hàn Sơ cấp 1 |
| `room_name` | Phòng học | `CharField(max_length=100, blank=True)` |  | Dùng để kiểm tra trùng phòng |
| `max_students` | Sĩ số tối đa | `PositiveIntegerField(default=0)` | ≥ 0 |  |
| `weekdays` | Các thứ học trong tuần | `CharField(max_length=20)` | NOT NULL | VD: '0,2,4' = Thứ 2, 4, 6 (0 = Thứ 2) |
| `start_time` | Giờ bắt đầu | `TimeField()` | NOT NULL |  |
| `end_time` | Giờ kết thúc | `TimeField()` | NOT NULL |  |
| `start_date` | Ngày bắt đầu | `DateField()` | NOT NULL |  |
| `end_date` | Ngày kết thúc dự kiến | `DateField()` | NOT NULL | Có thể lùi khi thêm buổi học bù |
| `status` | Trạng thái lớp | `CharField(max_length=20, choices=ClassStatus.choices, default='UPCOMING')` | NOT NULL | Enum ClassStatus |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |
| `updated_at` | Thời điểm cập nhật | `DateTimeField(auto_now=True)` | NOT NULL |  |

- **Enum `ClassStatus`:** UPCOMING · ACTIVE · COMPLETED · CANCELLED
- **Ràng buộc của bảng:**
  - CheckConstraint: end_date ≥ start_date
  - CheckConstraint: end_time > start_time

#### 7.3.9. `class_assignments` – Phân công nhân sự cho lớp

Model `ClassAssignment` · app `schedule`

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã phân công | `AutoField(primary_key=True)` | PK |  |
| `study_class` | Lớp học | `ForeignKey(StudyClass, on_delete=CASCADE, related_name='assignments')` | NOT NULL, FK |  |
| `employee` | Nhân sự được phân công | `ForeignKey(Employee, on_delete=PROTECT, related_name='class_assignments')` | NOT NULL, FK |  |
| `assignment_role` | Vai trò trong lớp | `CharField(max_length=30, choices=AssignmentRole.choices)` | NOT NULL | Enum AssignmentRole |
| `start_date` | Ngày bắt đầu phân công | `DateField()` | NOT NULL |  |
| `end_date` | Ngày kết thúc phân công | `DateField(null=True, blank=True)` | NULL | Trống = đang phân công; đặt khi hủy lớp/thanh lý |

- **Enum `AssignmentRole`:** MAIN_TEACHER · TEACHING_ASSISTANT

#### 7.3.10. `teaching_sessions` – Buổi dạy

Model `TeachingSession` · app `schedule`

Khi sinh buổi dạy, actual_teacher = planned_teacher và actual_assistant = planned_assistant. Người thực tế chỉ đổi khi dạy thay hoặc đổi trợ giảng (UC 6.4). actual_assistant trống nghĩa là buổi không có trợ giảng. Chấm công và lương dùng người thực tế.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã buổi dạy | `AutoField(primary_key=True)` | PK |  |
| `study_class` | Lớp học | `ForeignKey(StudyClass, on_delete=CASCADE, related_name='teaching_sessions')` | NOT NULL, FK |  |
| `session_date` | Ngày dạy | `DateField()` | NOT NULL |  |
| `planned_start` | Giờ bắt đầu | `TimeField()` | NOT NULL |  |
| `planned_end` | Giờ kết thúc | `TimeField()` | NOT NULL |  |
| `room_name` | Phòng học | `CharField(max_length=100, blank=True)` |  | Sao chép từ lớp khi sinh buổi |
| `planned_teacher` | Giáo viên dự kiến | `ForeignKey(Employee, on_delete=PROTECT, related_name='planned_sessions')` | NOT NULL, FK |  |
| `actual_teacher` | Giáo viên thực tế | `ForeignKey(Employee, on_delete=PROTECT, null=True, blank=True, related_name='actual_sessions')` | FK, NULL | Đổi khi chốt dạy thay |
| `planned_assistant` | Trợ giảng dự kiến | `ForeignKey(Employee, on_delete=SET_NULL, null=True, blank=True, related_name='planned_assist_sessions')` | FK, NULL |  |
| `actual_assistant` | Trợ giảng thực tế | `ForeignKey(Employee, on_delete=SET_NULL, null=True, blank=True, related_name='actual_assist_sessions')` | FK, NULL | Dùng để chấm công, tính lương trợ giảng |
| `status` | Trạng thái | `CharField(max_length=20, choices=TeachingSessionStatus.choices, default='SCHEDULED')` | NOT NULL | Enum TeachingSessionStatus |
| `lesson_note` | Nội dung buổi học | `TextField(blank=True)` |  | Giáo viên ghi (UC 6.2) |

- **Enum `TeachingSessionStatus`:** SCHEDULED · COMPLETED · CANCELLED
- **Ràng buộc của bảng:**
  - CheckConstraint: planned_end > planned_start

#### 7.3.11. `shift_assignments` – Phân ca làm việc

Model `ShiftAssignment` · app `schedule`

Mỗi dòng là một chỗ trong một khung ca. Khung ca cần N người thì có N dòng với cùng slot_group. Dùng cho ca Lễ tân, Tư vấn… của nhân viên Part-time; trợ giảng làm theo buổi dạy (teaching_sessions).

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã chỗ trong ca | `AutoField(primary_key=True)` | PK |  |
| `slot_group` | Mã khung ca | `CharField(max_length=36, db_index=True)` | NOT NULL | Mã UUID chung cho các chỗ của một khung ca |
| `employee` | Nhân sự nhận ca | `ForeignKey(Employee, on_delete=PROTECT, null=True, blank=True, related_name='shift_assignments')` | FK, NULL | NULL = chỗ còn trống |
| `shift_role` | Vai trò ca | `CharField(max_length=50)` | NOT NULL | VD: Lễ tân, Tư vấn |
| `work_date` | Ngày làm việc | `DateField()` | NOT NULL |  |
| `planned_start` | Giờ bắt đầu | `TimeField()` | NOT NULL |  |
| `planned_end` | Giờ kết thúc | `TimeField()` | NOT NULL |  |
| `registration_deadline` | Hạn chót đăng ký | `DateTimeField()` | NOT NULL | Sau mốc này không được giữ chỗ |
| `registered_at` | Thời điểm giữ chỗ | `DateTimeField(null=True, blank=True)` | NULL | Ai giữ trước được trước |
| `status` | Trạng thái | `CharField(max_length=20, choices=ShiftStatus.choices, default='OPEN')` | NOT NULL | Enum ShiftStatus |
| `assigned_by` | Người chốt ca | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='approved_shift_assignments')` | FK, NULL |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `ShiftStatus`:** OPEN (trống) · PENDING (đã giữ chỗ) · SCHEDULED (đã chốt) · CANCELLED
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['slot_group', 'employee'], condition=Q(employee__isnull=False)): một người không giữ hai chỗ trong cùng khung ca
  - CheckConstraint: planned_end > planned_start

#### 7.3.12. `attendance` – Chấm công

Model `Attendance` · app `attendance`

Chấm công bằng nút bấm, không kiểm tra IP Wi-Fi. Nhân sự Part-time có ca: một bản ghi cho mỗi ca. Nhân sự Full-time và trợ giảng: một bản ghi mỗi ngày. Giờ dự kiến được lưu lại trên bản ghi để tính trễ/sớm và giờ công.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã chấm công | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự | `ForeignKey(Employee, on_delete=PROTECT, related_name='attendance_logs')` | NOT NULL, FK |  |
| `shift_assignment` | Ca làm việc | `ForeignKey(ShiftAssignment, on_delete=PROTECT, null=True, blank=True)` | FK, NULL | Có giá trị khi chấm công theo ca |
| `work_date` | Ngày chấm công | `DateField()` | NOT NULL |  |
| `planned_start` | Giờ bắt đầu dự kiến | `TimeField()` | NOT NULL | Giờ ca Full-time / giờ ca Part-time / giờ buổi dạy |
| `planned_end` | Giờ kết thúc dự kiến | `TimeField()` | NOT NULL |  |
| `check_in` | Giờ vào thực tế | `DateTimeField(null=True, blank=True)` | NULL |  |
| `check_out` | Giờ ra thực tế | `DateTimeField(null=True, blank=True)` | NULL |  |
| `late_minutes` | Số phút đi trễ | `PositiveIntegerField(default=0)` | ≥ 0 | Chỉ tính khi trễ quá 5 phút |
| `early_leave_minutes` | Số phút về sớm | `PositiveIntegerField(default=0)` | ≥ 0 |  |
| `attendance_status` | Trạng thái chấm công | `CharField(max_length=30, choices=AttendanceStatus.choices)` | NOT NULL | Enum AttendanceStatus |
| `explanation_status` | Trạng thái giải trình | `CharField(max_length=20, choices=ExplanationStatus.choices, default='NONE')` | NOT NULL | Enum ExplanationStatus |
| `explanation_reason` | Lý do giải trình | `TextField(blank=True)` |  | UC 4.2 |
| `explanation_evidence` | Minh chứng | `FileField(upload_to='attendance/explanations/', blank=True)` |  | Ảnh/PDF |
| `explanation_reviewed_by` | Người duyệt giải trình | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_attendance_explanations')` | FK, NULL |  |
| `explanation_reviewed_at` | Thời điểm duyệt | `DateTimeField(null=True, blank=True)` | NULL |  |
| `explanation_review_note` | Lý do từ chối giải trình | `TextField(blank=True)` |  | Bắt buộc khi REJECTED |

- **Enum `AttendanceStatus`:** ON_TIME · LATE · EARLY_LEAVE · ABSENT · MISSING_CHECKOUT
- **Enum `ExplanationStatus`:** NONE · PENDING · APPROVED · REJECTED
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['employee', 'shift_assignment'], condition=Q(shift_assignment__isnull=False)): một bản ghi mỗi ca
  - UniqueConstraint(fields=['employee', 'work_date'], condition=Q(shift_assignment__isnull=True)): một bản ghi mỗi ngày khi không theo ca

#### 7.3.13. `leave_requests` – Đơn nghỉ phép

Model `LeaveRequest` · app `leave`

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã đơn nghỉ | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự gửi đơn | `ForeignKey(Employee, on_delete=PROTECT, related_name='leave_requests')` | NOT NULL, FK |  |
| `leave_type` | Loại nghỉ | `CharField(max_length=20, choices=LeaveType.choices)` | NOT NULL | Enum LeaveType; ANNUAL chỉ cho Full-time |
| `duration_type` | Hình thức nghỉ | `CharField(max_length=20, choices=DurationType.choices, default='FULL_DAY')` | NOT NULL | Enum DurationType |
| `start_date` | Ngày bắt đầu | `DateField()` | NOT NULL |  |
| `end_date` | Ngày kết thúc | `DateField()` | NOT NULL | Nghỉ nửa ngày: bằng start_date |
| `total_days` | Tổng số ngày nghỉ | `DecimalField(max_digits=4, decimal_places=1)` | NOT NULL | Số ngày Thứ 2 – Thứ 7; nửa ngày = 0,5 |
| `reason` | Lý do | `TextField()` | NOT NULL |  |
| `status` | Trạng thái đơn | `CharField(max_length=20, choices=LeaveStatus.choices, default='PENDING')` | NOT NULL | Enum LeaveStatus |
| `reviewed_by` | Người duyệt | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_leave_requests')` | FK, NULL |  |
| `reviewed_at` | Thời điểm duyệt | `DateTimeField(null=True, blank=True)` | NULL |  |
| `review_note` | Ghi chú / lý do từ chối | `TextField(blank=True)` |  | Bắt buộc khi REJECTED |
| `needs_substitute` | Cần người dạy thay | `BooleanField(default=False)` | NOT NULL | True khi đơn ảnh hưởng buổi dạy chính (UC 5.2) |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `LeaveType`:** ANNUAL (Phép năm) · SICK (Nghỉ ốm) · UNPAID (Không lương) · OTHER (Khác)
- **Enum `DurationType`:** FULL_DAY (cả ca) · HALF_DAY_AM (nửa đầu ca) · HALF_DAY_PM (nửa sau ca)
- **Enum `LeaveStatus`:** PENDING · APPROVED · REJECTED · CANCELLED
- **Ràng buộc của bảng:**
  - CheckConstraint: end_date ≥ start_date

#### 7.3.14. `leave_balances` – Quỹ phép năm

Model `LeaveBalance` · app `leave`

Chỉ nhân sự Full-time có quỹ phép. Số ngày còn lại không lưu thành cột mà tính bằng thuộc tính remaining_days = total_days − used_days, nên không bao giờ bị lệch số liệu.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã quỹ phép | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự | `ForeignKey(Employee, on_delete=PROTECT, related_name='leave_balances')` | NOT NULL, FK |  |
| `year` | Năm áp dụng | `PositiveIntegerField()` | NOT NULL | VD: 2026 |
| `total_days` | Tổng phép năm | `DecimalField(max_digits=4, decimal_places=1, default=12)` | NOT NULL | Mặc định 12 ngày |
| `used_days` | Số ngày đã dùng | `DecimalField(max_digits=4, decimal_places=1, default=0)` | NOT NULL | Cộng khi duyệt đơn ANNUAL |

- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['employee', 'year']): mỗi nhân sự một quỹ phép mỗi năm
  - CheckConstraint: used_days ≤ total_days

#### 7.3.15. `substitute_requests` – Yêu cầu dạy thay

Model `SubstituteRequest` · app `schedule`

Được tạo tự động khi duyệt đơn nghỉ (UC 5.2) hoặc thanh lý hợp đồng (UC 3.4). Quản lý chọn trực tiếp người dạy thay (UC 6.4).

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã yêu cầu | `AutoField(primary_key=True)` | PK |  |
| `teaching_session` | Buổi dạy cần thay | `ForeignKey(TeachingSession, on_delete=PROTECT, related_name='substitute_requests')` | NOT NULL, FK |  |
| `leave_request` | Đơn nghỉ gốc | `ForeignKey(LeaveRequest, on_delete=SET_NULL, null=True, blank=True, related_name='substitute_requests')` | FK, NULL | Trống nếu phát sinh từ thanh lý hợp đồng |
| `substitute_employee` | Giáo viên dạy thay | `ForeignKey(Employee, on_delete=PROTECT, null=True, blank=True, related_name='accepted_substitutions')` | FK, NULL |  |
| `status` | Trạng thái | `CharField(max_length=20, choices=SubstituteStatus.choices, default='SEARCHING')` | NOT NULL | Enum SubstituteStatus |
| `manager_confirmed_by` | Quản lý chốt | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='confirmed_substitutions')` | FK, NULL |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `SubstituteStatus`:** SEARCHING · COMPLETED · FAILED
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['teaching_session'], condition=Q(status='SEARCHING')): mỗi buổi tối đa một yêu cầu đang tìm người

#### 7.3.16. `salary_configs` – Cấu hình lương

Model `SalaryConfig` · app `payroll`

Một nhân sự có nhiều cấu hình theo thời gian; cấu hình đang áp dụng là cấu hình có effective_to trống.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã cấu hình | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự áp dụng | `ForeignKey(Employee, on_delete=PROTECT, related_name='salary_configs')` | NOT NULL, FK |  |
| `base_salary` | Lương cơ bản | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | Full-time |
| `hourly_rate` | Đơn giá giờ | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | Part-time; mặc định 35.000 đ |
| `class_allowance_rate` | Phụ cấp mỗi lớp | `DecimalField(max_digits=12, decimal_places=2, default=0)` | ≥ 0 | Giáo viên Full-time |
| `responsibility_allowance` | Phụ cấp trách nhiệm | `DecimalField(max_digits=12, decimal_places=2, default=0)` | ≥ 0 | VD: Quản lý |
| `effective_from` | Ngày bắt đầu áp dụng | `DateField()` | NOT NULL |  |
| `effective_to` | Ngày kết thúc áp dụng | `DateField(null=True, blank=True)` | NULL | Trống = đang áp dụng |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['employee', 'effective_from'])
  - CheckConstraint: các số tiền ≥ 0; effective_to IS NULL hoặc effective_to ≥ effective_from

#### 7.3.17. `payrolls` – Bảng lương

Model `Payroll` · app `payroll`

Mỗi nhân sự một bản ghi mỗi tháng. Bảng lương tháng gồm toàn bộ bản ghi cùng period_month, period_year.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã bảng lương | `AutoField(primary_key=True)` | PK |  |
| `employee` | Nhân sự | `ForeignKey(Employee, on_delete=PROTECT, related_name='payrolls')` | NOT NULL, FK |  |
| `period_month` | Tháng lương | `PositiveSmallIntegerField()` | 1–12 |  |
| `period_year` | Năm lương | `PositiveIntegerField()` | > 0 |  |
| `gross_pay` | Tổng thu nhập | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | Tổng các khoản EARNING |
| `total_deduction` | Tổng khấu trừ | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | Tổng DEDUCTION, không gồm thuế |
| `total_tax` | Thuế TNCN | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | Tổng TAX |
| `net_pay` | Thực nhận | `DecimalField(max_digits=15, decimal_places=2, default=0)` | ≥ 0 | gross − deduction − tax |
| `status` | Trạng thái | `CharField(max_length=20, choices=PayrollStatus.choices, default='DRAFT')` | NOT NULL | Enum PayrollStatus |
| `created_by` | Người lập | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_payrolls')` | FK, NULL |  |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |
| `locked_at` | Thời điểm chốt | `DateTimeField(null=True, blank=True)` | NULL |  |
| `sent_at` | Thời điểm phát hành | `DateTimeField(null=True, blank=True)` | NULL |  |

- **Enum `PayrollStatus`:** DRAFT · LOCKED · SENT
- **Ràng buộc của bảng:**
  - UniqueConstraint(fields=['employee', 'period_month', 'period_year'])
  - CheckConstraint: 1 ≤ period_month ≤ 12

#### 7.3.18. `payroll_details` – Chi tiết bảng lương

Model `PayrollDetail` · app `payroll`

Dòng tự động (hệ thống tính lại được): WORKDAY_SALARY, PART_TIME_HOURLY_PAY, CLASS_ALLOWANCE, RESPONSIBILITY_ALLOWANCE. Dòng thủ công (Kế toán nhập, được giữ khi tính lại): BONUS, ADJUSTMENT_INCREASE, ADJUSTMENT_DECREASE, PERSONAL_INCOME_TAX, OTHER. Số tiền luôn dương; khoản cộng hay trừ do detail_type quyết định: ADJUSTMENT_DECREASE là DEDUCTION, PERSONAL_INCOME_TAX là TAX, OTHER do Kế toán chọn EARNING hoặc DEDUCTION, các nhóm còn lại là EARNING.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã chi tiết | `AutoField(primary_key=True)` | PK |  |
| `payroll` | Bảng lương | `ForeignKey(Payroll, on_delete=CASCADE, related_name='details')` | NOT NULL, FK |  |
| `detail_type` | Loại khoản | `CharField(max_length=20, choices=PayrollDetailType.choices)` | NOT NULL | EARNING: cộng; DEDUCTION: trừ; TAX: thuế |
| `category` | Nhóm khoản | `CharField(max_length=40, choices=PayrollDetailCategory.choices)` | NOT NULL | Enum PayrollDetailCategory |
| `description` | Nội dung | `CharField(max_length=255)` | NOT NULL | VD: Lương ngày công: 24/26 ngày |
| `amount` | Số tiền | `DecimalField(max_digits=15, decimal_places=2)` | NOT NULL, ≥ 0 |  |

- **Enum `PayrollDetailType`:** EARNING · DEDUCTION · TAX
- **Enum `PayrollDetailCategory`:** WORKDAY_SALARY · PART_TIME_HOURLY_PAY · CLASS_ALLOWANCE · RESPONSIBILITY_ALLOWANCE · BONUS · ADJUSTMENT_INCREASE · ADJUSTMENT_DECREASE · PERSONAL_INCOME_TAX · OTHER
- **Ràng buộc của bảng:**
  - CheckConstraint: amount ≥ 0

#### 7.3.19. `notifications` – Thông báo hệ thống

Model `Notification` · app `core`

Kênh thông báo chính trong web; số thông báo chưa đọc hiển thị trên biểu tượng chuông ở mọi trang.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã thông báo | `AutoField(primary_key=True)` | PK |  |
| `recipient` | Người nhận | `ForeignKey(User, on_delete=CASCADE, related_name='notifications')` | NOT NULL, FK |  |
| `title` | Tiêu đề | `CharField(max_length=255)` | NOT NULL |  |
| `message` | Nội dung | `TextField()` | NOT NULL |  |
| `notification_type` | Loại thông báo | `CharField(max_length=30, choices=NotificationType.choices)` | NOT NULL | Enum NotificationType |
| `is_read` | Đã đọc | `BooleanField(default=False)` | NOT NULL |  |
| `related_url` | Liên kết | `CharField(max_length=500, blank=True)` |  | Trang xử lý liên quan |
| `created_at` | Thời điểm tạo | `DateTimeField(auto_now_add=True)` | NOT NULL |  |

- **Enum `NotificationType`:** LEAVE · ATTENDANCE · CONTRACT · RECRUITMENT · SCHEDULE · PAYROLL · PROFILE · SYSTEM

#### 7.3.20. `activity_logs` – Nhật ký hoạt động

Model `ActivityLog` · app `core`

Ghi mọi thao tác quan trọng: đăng nhập, đăng xuất, tạo, sửa, duyệt, từ chối, khóa tài khoản, nhắc nhở, chạy tác vụ hằng ngày.

| Tên trường | Mô tả | Kiểu dữ liệu Django | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `id` | Mã nhật ký | `AutoField(primary_key=True)` | PK |  |
| `user` | Người thực hiện | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='activity_logs')` | FK, NULL | Trống với LOGIN_FAILED và tác vụ tự động |
| `action` | Hành động | `CharField(max_length=50)` | NOT NULL | LOGIN, LOGIN_FAILED, LOGOUT, CREATE, UPDATE, APPROVE, REJECT, LOCK, UNLOCK, REMIND, RUN_DAILY_JOB |
| `model_name` | Bảng bị tác động | `CharField(max_length=100)` | NOT NULL | VD: Employee, Contract |
| `object_id` | ID bản ghi | `PositiveIntegerField(null=True, blank=True)` | NULL |  |
| `description` | Mô tả chi tiết | `TextField(blank=True)` |  | VD: email đăng nhập thất bại |
| `created_at` | Thời điểm | `DateTimeField(auto_now_add=True)` | NOT NULL |  |


### 7.4 Tổng hợp Enum

| Enum | Giá trị | Dùng ở bảng |
|---|---|---|
| `UserRole` | SUPER_ADMIN · MANAGER · ACCOUNTANT · EMPLOYEE | users |
| `Gender` | MALE · FEMALE · OTHER | employees |
| `Department` | ACADEMIC · HR_ADMIN · ACCOUNTING | employees |
| `Position` | TEACHER · TEACHING_ASSISTANT · STAFF · MANAGER · ACCOUNTANT | employees, candidates |
| `EmploymentType` | FULL_TIME · PART_TIME | employees, contracts, candidates |
| `WorkShift` | SHIFT_1 (Ca 1: 08:00–17:00) · SHIFT_2 (Ca 2: 13:00–21:00) | employees |
| `EmployeeStatus` | ONBOARDING · ACTIVE · RESIGNED · TERMINATED | employees |
| `DocumentType` | PERSONAL_ID · CERTIFICATION · OTHER | employee_documents |
| `DocumentStatus` | PENDING · APPROVED · REJECTED · EXPIRED | employee_documents |
| `ContractStatus` | ACTIVE · EXPIRED · TERMINATED | contracts |
| `CampaignStatus` | OPEN · CLOSED | recruitment_campaigns |
| `CandidateStatus` | NEW · SCREENING (đạt sơ tuyển, chờ phỏng vấn) · INTERVIEWING · TEACHING_TRIAL · PASSED · REJECTED · HIRED | candidates |
| `RecruitmentRoundType` | INTERVIEW · DEMO | recruitment_rounds |
| `RecruitmentRoundStatus` | SCHEDULED · COMPLETED · CANCELLED | recruitment_rounds |
| `RecruitmentResult` | PENDING · PASSED · FAILED | recruitment_rounds |
| `ClassStatus` | UPCOMING · ACTIVE · COMPLETED · CANCELLED | classes |
| `AssignmentRole` | MAIN_TEACHER · TEACHING_ASSISTANT | class_assignments |
| `TeachingSessionStatus` | SCHEDULED · COMPLETED · CANCELLED | teaching_sessions |
| `ShiftStatus` | OPEN (trống) · PENDING (đã giữ chỗ) · SCHEDULED (đã chốt) · CANCELLED | shift_assignments |
| `AttendanceStatus` | ON_TIME · LATE · EARLY_LEAVE · ABSENT · MISSING_CHECKOUT | attendance |
| `ExplanationStatus` | NONE · PENDING · APPROVED · REJECTED | attendance |
| `LeaveType` | ANNUAL (Phép năm) · SICK (Nghỉ ốm) · UNPAID (Không lương) · OTHER (Khác) | leave_requests |
| `DurationType` | FULL_DAY (cả ca) · HALF_DAY_AM (nửa đầu ca) · HALF_DAY_PM (nửa sau ca) | leave_requests |
| `LeaveStatus` | PENDING · APPROVED · REJECTED · CANCELLED | leave_requests |
| `SubstituteStatus` | SEARCHING · COMPLETED · FAILED | substitute_requests |
| `PayrollStatus` | DRAFT · LOCKED · SENT | payrolls |
| `PayrollDetailType` | EARNING · DEDUCTION · TAX | payroll_details |
| `PayrollDetailCategory` | WORKDAY_SALARY · PART_TIME_HOURLY_PAY · CLASS_ALLOWANCE · RESPONSIBILITY_ALLOWANCE · BONUS · ADJUSTMENT_INCREASE · ADJUSTMENT_DECREASE · PERSONAL_INCOME_TAX · OTHER | payroll_details |
| `NotificationType` | LEAVE · ATTENDANCE · CONTRACT · RECRUITMENT · SCHEDULE · PAYROLL · PROFILE · SYSTEM | notifications |

---

## 8. Vòng đời trạng thái

Mỗi dòng dưới đây phải có đúng **một hàm service** thực hiện việc chuyển trạng thái, và hàm đó kiểm tra trạng thái hiện tại trước khi chuyển.

| Đối tượng | Chuyển trạng thái | Xảy ra khi | UC |
|---|---|---|---|
| employees.status | ONBOARDING → ACTIVE | Tạo hợp đồng đầu tiên | 3.1 |
|  | ACTIVE → RESIGNED / TERMINATED | Thanh lý hợp đồng | 3.4 |
| users.is_active | True ↔ False | Super Admin khóa/mở khóa | 1.5 |
|  | True → False | Thanh lý hợp đồng | 3.4 |
| contracts.status | ACTIVE → EXPIRED | Gia hạn (hợp đồng cũ) | 3.3 |
|  | ACTIVE → TERMINATED | Thanh lý | 3.4 |
| employee_documents.status | (mới) → PENDING | Nhân sự tải giấy tờ / tải bản mới | 2.2 |
|  | PENDING → APPROVED / REJECTED | Duyệt / từ chối | 2.6 |
|  | APPROVED → EXPIRED | Quá ngày hết hạn | 9.2 |
| recruitment_campaigns.status | OPEN → CLOSED | Quản lý đóng đợt | 8.1 |
| candidates.status | NEW → SCREENING / REJECTED | Sơ tuyển đạt / không đạt | 8.1 |
|  | SCREENING → INTERVIEWING | Xếp lịch phỏng vấn | 8.2 |
|  | INTERVIEWING → SCREENING | Hủy lịch phỏng vấn | 8.2 |
|  | INTERVIEWING → TEACHING_TRIAL | Giáo viên Full-time đạt phỏng vấn | 8.3 |
|  | INTERVIEWING → PASSED | Vị trí khác đạt phỏng vấn | 8.3 |
|  | TEACHING_TRIAL → PASSED | Đạt Demo | 8.3 |
|  | INTERVIEWING / TEACHING_TRIAL → REJECTED | Không đạt | 8.3 |
|  | PASSED → HIRED | Tạo hồ sơ nhân sự | 2.5 |
| recruitment_rounds.status | SCHEDULED → COMPLETED | Nhập kết quả | 8.3 |
|  | SCHEDULED → CANCELLED | Hủy lịch / ứng viên vắng mặt | 8.2, 8.3 |
| classes.status | UPCOMING → ACTIVE → COMPLETED | Tới ngày bắt đầu / quá ngày kết thúc | 9.2 |
|  | UPCOMING / ACTIVE → CANCELLED | Quản lý hủy lớp | 6.1 |
| teaching_sessions.status | SCHEDULED → COMPLETED | Buổi dạy đã qua | 9.2 |
|  | SCHEDULED → CANCELLED | Hủy buổi (không có người thay) / hủy lớp | 6.4, 6.1, 9.2 |
| shift_assignments.status | OPEN → PENDING | Nhân viên giữ chỗ | 6.3 |
|  | PENDING → OPEN | Hủy giữ chỗ trước hạn | 6.3 |
|  | PENDING / OPEN → SCHEDULED | Quản lý chốt ca (gán người vào chỗ trống) | 6.3 |
|  | OPEN → CANCELLED | Chốt ca mà chỗ còn trống | 6.3 |
|  | PENDING / SCHEDULED → OPEN | Thanh lý hợp đồng người nhận ca | 3.4 |
| attendance.attendance_status | (mới) → ON_TIME / LATE | Check-in | 4.1 |
|  | → EARLY_LEAVE | Check-out sớm | 4.1 |
|  | (mới) → ABSENT; → MISSING_CHECKOUT | Không chấm công / quên check-out | 9.2 |
|  | Trạng thái lỗi → ON_TIME | Giải trình được chấp thuận | 4.4 |
| attendance.explanation_status | NONE → PENDING | Gửi giải trình | 4.2 |
|  | PENDING → APPROVED / REJECTED | Duyệt / từ chối | 4.4 |
| leave_requests.status | (mới) → PENDING | Gửi đơn | 5.1 |
|  | PENDING → CANCELLED | Nhân sự hủy đơn | 5.1 |
|  | PENDING → APPROVED / REJECTED | Duyệt / từ chối | 5.2 |
| substitute_requests.status | (mới) → SEARCHING | Duyệt đơn nghỉ / thanh lý hợp đồng | 5.2, 3.4 |
|  | SEARCHING → COMPLETED | Chốt dạy thay | 6.4 |
|  | SEARCHING → FAILED | Hủy buổi / buổi đã qua mà chưa có người | 6.4, 9.2 |
| payrolls.status | (mới) → DRAFT | Khởi tạo bảng lương | 7.2 |
|  | DRAFT → LOCKED → SENT | Chốt bảng lương → Phát hành phiếu lương | 7.2 |

---

## 9. Hàm dùng chung & định nghĩa tính toán

### 9.1 Danh sách hàm dùng chung

| Hàm | Ở app | Dùng tại UC |
|---|---|---|
| `role_required(*roles)` (decorator) | core | mọi view |
| `co_quyen_duyet(nguoi_duyet, nguoi_gui)` | core | 2.6, 4.4, 5.2 |
| `tao_thong_bao(nguoi_nhan, loai, tieu_de, noi_dung, link)` | core | mọi UC có gửi thông báo |
| `ghi_nhat_ky(nguoi_dung, hanh_dong, ten_bang, id, mo_ta)` | core | mọi UC có ghi nhật ký |
| `gui_link_dat_mat_khau(user)` | accounts | 1.2, 1.5, 2.5 |
| `khoa_tai_khoan(user)` | accounts | 1.5, 3.4 |
| `dong_bo_ho_ten_sdt(employee)` | employees | 1.4, 2.5 |
| `danh_dau_da_tuyen(ung_vien)` | recruitment | 2.5 |
| `kiem_tra_trung_lich(nhan_su, ngay, bat_dau, ket_thuc)` | schedule | 6.1, 6.3, 6.4, 8.2 |
| `goi_y_giao_vien(cac_ngay, bat_dau, ket_thuc, loai_tru=None)` | schedule | 6.1, 6.4 |
| `tao_yeu_cau_day_thay(buoi_day, don_nghi=None)` | schedule | 3.4, 5.2 |
| `giai_phong_lich_tuong_lai(nhan_su, tu_ngay)` | schedule | 3.4 |
| `tinh_so_ngay_nghi(tu_ngay, den_ngay, hinh_thuc)` | leave | 5.1 |
| `tao_quy_phep(nhan_su, nam)` | leave | 2.5, 9.2 |
| `lich_du_kien(nhan_su, ngay)` | attendance | 4.1, 9.2 |
| `tinh_ngay_cong(nhan_su, thang, nam)` | attendance | 4.3, 4.5, 7.2 |
| `tinh_gio_cong(nhan_su, thang, nam)` | attendance | 4.3, 4.5, 7.2 |
| `thang_da_chot(thang, nam)` | payroll | 4.2, 4.4, 5.1, 7.1 |
| `cau_hinh_hieu_luc(nhan_su, ngay)` | payroll | 7.2 |
| `dong_cau_hinh_luong(nhan_su, ngay)` | payroll | 3.4 |
| `chay_tac_vu_ngay(hom_nay)` | dashboard | 9.1, 9.2 |

### 9.2 Định nghĩa tính toán (dùng thống nhất ở mọi màn hình)

**Lịch dự kiến `lich_du_kien(nhan_su, ngay)`.** Trả về danh sách khung giờ (có thể rỗng):

- Nếu ngày không thuộc `NGAY_LAM_VIEC`, hoặc có đơn nghỉ `FULL_DAY` đã APPROVED chứa ngày đó → rỗng.
- **Full-time:** một khung theo `work_shift` (ví dụ Ca 2 = 13:00–21:00).
  - Nghỉ nửa đầu ca đã duyệt → chỉ còn [mốc giữa ca, giờ kết thúc].
  - Nghỉ nửa sau ca đã duyệt → chỉ còn [giờ bắt đầu, mốc giữa ca].
- **Part-time:**
  - Mỗi chỗ ca `SCHEDULED` của ngày là một khung, gắn với `shift_assignment`.
  - Nếu là trợ giảng thực tế (`actual_assistant`) của các buổi dạy không CANCELLED trong ngày → thêm một khung từ đầu buổi sớm nhất đến cuối buổi muộn nhất, không gắn ca.
  - Nghỉ nửa ngày dùng mốc `MOC_NUA_NGAY_PART_TIME`.

**Đi trễ, về sớm (UC 4.1).**

- `late_minutes` = số phút từ giờ bắt đầu dự kiến đến `check_in`, chỉ ghi nếu lớn hơn `PHUT_CHO_PHEP_TRE`, ngược lại 0.
- `early_leave_minutes` = số phút từ `check_out` đến giờ kết thúc dự kiến, nếu `check_out` sớm hơn.
- **Trạng thái:** sau check-in là `ON_TIME` hoặc `LATE`; sau check-out sớm thì `EARLY_LEAVE` (vẫn giữ `late_minutes`).

**Số ngày nghỉ `total_days` (UC 5.1).** Đếm các ngày thuộc `NGAY_LAM_VIEC` từ `start_date` đến `end_date`. Hình thức nửa ngày = 0,5 (bắt buộc `start_date = end_date`).

**Ngày công trong tháng (Full-time) `tinh_ngay_cong`.**

- **Bản ghi chấm công không theo ca** có `attendance_status ∈ {ON_TIME, LATE, EARLY_LEAVE}` → 1 ngày.
  - Bản ghi được chấp thuận giải trình đã thành `ON_TIME` nên cũng được tính.
  - Nếu ngày đó có đơn nghỉ nửa ca đã duyệt → 0,5.
- **Cộng ngày nghỉ `ANNUAL` đã APPROVED** rơi vào tháng: mỗi ngày làm việc tính 1, nửa ngày tính 0,5. Đơn kéo dài qua hai tháng thì chỉ đếm phần trong tháng.
- **Không tính:** `ABSENT`, `MISSING_CHECKOUT` chưa được chấp thuận, nghỉ `SICK`/`UNPAID`/`OTHER`.
- **Kết quả tối đa** `NGAY_CONG_CHUAN` (26).

**Giờ công trong tháng (Part-time) `tinh_gio_cong`.** Cộng trên mọi bản ghi chấm công của tháng (cả theo ca và theo buổi trợ giảng):

- Giải trình `APPROVED` → tính đủ (giờ kết thúc dự kiến − giờ bắt đầu dự kiến).
- Có cả `check_in` và `check_out` → max(0, min(check_out, kết thúc dự kiến) − max(check_in, bắt đầu dự kiến)).
- Còn lại → 0.
- Đổi ra giờ, làm tròn 2 chữ số thập phân.

**Số lớp tính phụ cấp (giáo viên Full-time).** Số lớp mà giáo viên có `class_assignments` vai trò `MAIN_TEACHER` còn hiệu lực trong tháng, **và** lớp có ít nhất một buổi dạy không CANCELLED trong tháng. "Còn hiệu lực" nghĩa là `start_date ≤ cuối tháng` và (`end_date` trống hoặc `≥ đầu tháng`).

**Lương tháng (UC 7.2).**

- **Phạm vi tính:** nhân sự `ACTIVE`, cộng nhân sự `RESIGNED`/`TERMINATED` có `termination_date` trong tháng.
- **Cấu hình dùng:** `cau_hinh_hieu_luc(nhan_su, ngày cuối tháng hoặc ngày thanh lý)`.
- **Dòng tự động:**
  - Full-time: `WORKDAY_SALARY = base_salary × ngày_công / 26`.
  - Giáo viên Full-time: `CLASS_ALLOWANCE = class_allowance_rate × số_lớp`.
  - Nếu `responsibility_allowance > 0`: `RESPONSIBILITY_ALLOWANCE = responsibility_allowance`.
  - Part-time: `PART_TIME_HOURLY_PAY = hourly_rate × giờ_công`.
  - Dòng có số tiền 0 thì bỏ qua.
- **Thuế TNCN tự tính:** mỗi lần tính tổng, hệ thống xóa rồi tạo lại MỘT dòng `PERSONAL_INCOME_TAX` (TAX, mô tả bắt đầu "Thuế TNCN (tự tính)") từ tổng thu nhập EARNING: Full-time = lũy tiến trên (thu nhập − giảm trừ bản thân); Part-time = 10% toàn bộ thu nhập nếu từ 2.000.000 đ. Dòng này không xóa tay được.
- **Dòng thủ công** (Kế toán nhập): `BONUS`, `ADJUSTMENT_INCREASE` (EARNING); `ADJUSTMENT_DECREASE` (DEDUCTION); `PERSONAL_INCOME_TAX` (TAX, cộng thêm vào thuế tự tính); `OTHER` (KT chọn EARNING hoặc DEDUCTION).
- **Tổng:** `gross_pay = Σ EARNING`, `total_deduction = Σ DEDUCTION`, `total_tax = Σ TAX`, `net_pay = gross_pay − total_deduction − total_tax`.
- **"Tính lại"** chỉ xóa 4 nhóm dòng tự động rồi tính lại, giữ dòng thủ công.

**Trùng lịch `kiem_tra_trung_lich(nhan_su, ngay, bat_dau, ket_thuc)`.** Hai khoảng giờ trùng nhau khi `bat_dau < ket_thuc_khac` **và** `ket_thuc > bat_dau_khac`. Xét các lịch sau của cùng người trong ngày đó:

- Buổi dạy là `actual_teacher` hoặc `actual_assistant`, không CANCELLED.
- Chỗ ca `PENDING` hoặc `SCHEDULED`.
- Vòng tuyển dụng `SCHEDULED` mà người đó phỏng vấn (60 phút).
- Đơn nghỉ `APPROVED` (theo cả ca hoặc nửa ca).

**Gợi ý giáo viên `goi_y_giao_vien(...)`.**

- Điều kiện: `position = TEACHER`, `status = ACTIVE`, không trùng lịch ở **mọi** ngày cần dạy.
- Thêm cho giáo viên Full-time: ca làm việc **bao trọn** giờ học. Ví dụ lớp 18:00–20:00 chỉ gợi ý Ca 2; lớp 09:00–11:00 chỉ gợi ý Ca 1; lớp 14:00–16:00 gợi ý cả hai.
- UC 6.1 chỉ lấy giáo viên Full-time.

**Tháng đã chốt `thang_da_chot(thang, nam)`.** Tồn tại `payrolls` của tháng đó với `status ∈ {LOCKED, SENT}`.

**Giữ chỗ ca an toàn khi nhiều người bấm cùng lúc (UC 6.3).** Lấy id một chỗ OPEN của khung ca, rồi `ShiftAssignment.objects.filter(id=..., employee__isnull=True, status='OPEN').update(employee=..., status='PENDING', registered_at=...)`.

- Kết quả 1 → giữ chỗ thành công.
- Kết quả 0 (người khác vừa lấy) → thử chỗ OPEN tiếp theo; hết chỗ thì báo “Ca này đã đủ người.”

**Tác vụ hằng ngày chạy lại không trùng (UC 9.2).**

- Chỉ tạo `ABSENT` khi chưa có bản ghi chấm công tương ứng.
- Chỉ gửi nhắc khi số ngày còn lại đúng bằng một mốc trong `CAC_MOC_NHAC`, và chưa có thông báo cùng nội dung trong ngày.

---

## 10. Đặc tả use case (38 UC)

### 10.1 Danh sách use case

| Phân hệ | App | Mã UC | Tên use case | Ưu tiên | Tác nhân |
|---|---|---|---|---|---|
| UC1: Xác thực & Quản lý người dùng | `accounts` | 1.1 | Đăng nhập | Must Have | Super Admin, Quản lý, Kế toán, Nhân viên |
|  |  | 1.2 | Quên mật khẩu | High | Super Admin, Quản lý, Kế toán, Nhân viên |
|  |  | 1.3 | Đổi mật khẩu | Medium | Super Admin, Quản lý, Kế toán, Nhân viên |
|  |  | 1.4 | Xem & cập nhật tài khoản cá nhân | Medium | Super Admin, Quản lý, Kế toán, Nhân viên |
|  |  | 1.5 | Quản lý tài khoản người dùng | Must Have | Super Admin |
|  |  | 1.6 | Đăng xuất | Must Have | Super Admin, Quản lý, Kế toán, Nhân viên |
| UC2: Quản lý nhân sự | `employees` | 2.1 | Xem danh sách nhân sự | Must Have | Super Admin (chỉ xem), Quản lý, Kế toán, Nhân viên |
|  |  | 2.2 | Cập nhật hồ sơ cá nhân | High | Quản lý, Kế toán, Nhân viên |
|  |  | 2.3 | Xem hồ sơ cá nhân | Medium | Quản lý, Kế toán, Nhân viên |
|  |  | 2.4 | Theo dõi cảnh báo giấy tờ sắp hết hạn | Medium | Quản lý |
|  |  | 2.5 | Tiếp nhận & quản lý hồ sơ nhân sự (Onboarding) | Must Have | Quản lý |
|  |  | 2.6 | Duyệt giấy tờ, chứng chỉ | High | Quản lý, Super Admin (chỉ giấy tờ của Quản lý) |
| UC3: Quản lý hợp đồng | `contracts` | 3.1 | Quản lý danh sách hợp đồng | Must Have | Quản lý |
|  |  | 3.2 | Tra cứu chi tiết hợp đồng | Medium | Quản lý, Kế toán, Nhân viên |
|  |  | 3.3 | Cập nhật & gia hạn hợp đồng | High | Quản lý |
|  |  | 3.4 | Thanh lý hợp đồng | High | Quản lý |
|  |  | 3.5 | Theo dõi hợp đồng sắp hết hạn | High | Quản lý |
| UC4: Quản lý chấm công | `attendance` | 4.1 | Chấm công Check-in / Check-out | Must Have | Quản lý, Kế toán, Nhân viên |
|  |  | 4.2 | Gửi giải trình chấm công | High | Quản lý, Kế toán, Nhân viên |
|  |  | 4.3 | Xem lịch sử chấm công cá nhân | Medium | Quản lý, Kế toán, Nhân viên |
|  |  | 4.4 | Duyệt giải trình chấm công | High | Quản lý, Super Admin (chỉ giải trình của Quản lý) |
|  |  | 4.5 | Quản lý bảng tổng hợp công | Must Have | Quản lý, Kế toán, Super Admin (chỉ xem) |
| UC5: Quản lý nghỉ phép | `leave` | 5.1 | Gửi đơn xin nghỉ phép | High | Quản lý, Kế toán, Nhân viên |
|  |  | 5.2 | Duyệt đơn xin nghỉ phép | High | Quản lý, Super Admin (chỉ đơn của Quản lý) |
|  |  | 5.3 | Tra cứu quỹ phép cá nhân | Medium | Quản lý, Kế toán, Nhân viên |
|  |  | 5.4 | Tổng hợp lịch sử nghỉ phép | High | Quản lý, Super Admin (chỉ xem) |
| UC6: Lịch làm việc & Phân công | `schedule` | 6.1 | Tạo và phân công lớp học | High | Quản lý |
|  |  | 6.2 | Xem lịch làm việc & lịch lớp học | High | Super Admin (chỉ xem), Quản lý, Kế toán, Nhân viên |
|  |  | 6.3 | Đăng ký & phân công ca làm việc Part-time | High | Quản lý, Nhân viên Part-time |
|  |  | 6.4 | Xử lý dạy thay | Medium | Quản lý |
| UC7: Quản lý lương | `payroll` | 7.1 | Quản lý cấu hình lương | Must Have | Kế toán |
|  |  | 7.2 | Lập và chốt bảng lương | Must Have | Kế toán |
|  |  | 7.3 | Tra cứu phiếu lương cá nhân | Medium | Quản lý, Kế toán, Nhân viên |
| UC8: Quản lý tuyển dụng | `recruitment` | 8.1 | Quản lý đợt tuyển dụng & hồ sơ ứng viên | Must Have | Quản lý |
|  |  | 8.2 | Quản lý lịch phỏng vấn & dạy thử | High | Quản lý |
|  |  | 8.3 | Đánh giá kết quả & chuyển Onboarding | High | Quản lý |
| UC9: Bảng điều khiển & Tác vụ hệ thống | `dashboard` | 9.1 | Xem Dashboard theo vai trò | High | Super Admin, Quản lý, Kế toán, Nhân viên |
|  |  | 9.2 | Chạy tác vụ tự động hằng ngày | High | Hệ thống (lịch tự động), Super Admin |

### 10.2 Đặc tả chi tiết

Cách đọc: mỗi use case có bảng thông tin và ba bảng luồng. Số bước (1, 2, 3…) và mã luồng (ví dụ `3.2: (Từ bước 4)` = ngoại lệ phát sinh ở bước 3, phát hiện tại bước 4) được dùng để đặt tên hàm service và tên test.

#### Phân hệ UC1: Xác thực & Quản lý người dùng

##### UC 1.1 – Đăng nhập

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case mô tả quy trình người dùng xác thực danh tính bằng Email và Mật khẩu để truy cập vào hệ thống theo đúng vai trò được phân quyền. |
| **Kích hoạt** | Người dùng truy cập vào đường dẫn trang Đăng nhập của hệ thống. |
| **Tiền điều kiện** | • Người dùng đã có tài khoản trên hệ thống và đã đặt mật khẩu.<br>• Người dùng chưa đăng nhập. |
| **Hậu điều kiện** | • Phiên đăng nhập (session) hợp lệ được tạo.<br>• Hệ thống ghi nhật ký LOGIN vào bảng activity_logs.<br>• Người dùng được điều hướng đến Dashboard tương ứng với vai trò. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng mở trang Đăng nhập, nhập Email và Mật khẩu. | 2. Hệ thống hiển thị form đăng nhập, tiếp nhận và kiểm tra định dạng đầu vào. |
| 3. Người dùng nhấn nút “Đăng nhập”. | 4. Hệ thống tìm tài khoản theo Email trong bảng users, kiểm tra mật khẩu (đã mã hóa) và trạng thái is_active = True.<br>5. Hệ thống tạo session, nạp vai trò (role), ghi nhật ký LOGIN và điều hướng đến Dashboard theo vai trò (UC 9.1). |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Người dùng chọn “Quên mật khẩu?”. | 1.1.1. Hệ thống chuyển sang UC 1.2 Quên mật khẩu. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: Người dùng để trống trường bắt buộc rồi nhấn “Đăng nhập”. | 3.1.1: Hệ thống chặn thao tác và hiển thị cảnh báo màu đỏ tại trường còn trống. Trở lại Bước 1. |
| 3.2: (Từ bước 4) Email không tồn tại hoặc mật khẩu sai. | 3.2.1: Hệ thống từ chối đăng nhập, ghi nhật ký LOGIN_FAILED và hiển thị thông báo lỗi: “Email/Mật khẩu không đúng”. Trở lại Bước 1. |
| 3.3: (Từ bước 4) Mật khẩu đúng nhưng tài khoản có is_active = False. | 3.3.1: Hệ thống từ chối đăng nhập và hiển thị: “Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Quản trị viên.” Trở lại Bước 1. |

##### UC 1.2 – Quên mật khẩu

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép người dùng nhận đường dẫn đặt lại mật khẩu qua email đã đăng ký và tự đặt mật khẩu mới. Cơ chế này cũng được dùng để nhân viên mới tự đặt mật khẩu lần đầu (UC 2.5) và tài khoản do Super Admin tạo (UC 1.5). |
| **Kích hoạt** | Người dùng nhấn “Quên mật khẩu?” trên trang Đăng nhập, hoặc mở đường dẫn đặt mật khẩu nhận được qua email. |
| **Tiền điều kiện** | • Người dùng có tài khoản trên hệ thống.<br>• Người dùng chưa đăng nhập. |
| **Hậu điều kiện** | • Mật khẩu mới được mã hóa và lưu vào bảng users.<br>• Đường dẫn đã sử dụng không còn hiệu lực.<br>• Hệ thống ghi nhật ký đặt lại mật khẩu. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng nhấn “Quên mật khẩu?”. | 2. Hệ thống hiển thị form nhập Email. |
| 3. Người dùng nhập Email và nhấn “Gửi yêu cầu”. | 4. Hệ thống kiểm tra Email có tồn tại trong bảng users.<br>5. Hệ thống tạo đường dẫn đặt lại mật khẩu có hiệu lực 24 giờ, gửi tới Email và hiển thị: “Đã gửi hướng dẫn đặt lại mật khẩu vào email của bạn.” |
| 6. Người dùng mở đường dẫn trong email, nhập Mật khẩu mới và Xác nhận mật khẩu, nhấn “Lưu”. | 7. Hệ thống kiểm tra đường dẫn còn hiệu lực, hai mật khẩu khớp nhau và đủ mạnh; lưu mật khẩu mới, ghi nhật ký và chuyển về trang Đăng nhập với thông báo “Đặt lại mật khẩu thành công.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 3.1. Người dùng chọn “Quay lại đăng nhập”. | 3.1.1. Hệ thống điều hướng về trang Đăng nhập. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.2: (Từ bước 4) Email không tồn tại trong hệ thống. | 3.2.1: Hệ thống hiển thị: “Email không tồn tại trong hệ thống, vui lòng kiểm tra lại.” Trở lại Bước 3. |
| 6.1: (Từ bước 7) Đường dẫn đã hết hạn hoặc đã được sử dụng. | 6.1.1: Hệ thống hiển thị: “Đường dẫn đã hết hạn hoặc không hợp lệ. Vui lòng gửi lại yêu cầu.” Trở lại Bước 1. |
| 6.2: (Từ bước 7) Mật khẩu xác nhận không khớp hoặc chưa đủ mạnh. | 6.2.1: Hệ thống hiển thị lỗi tại trường tương ứng (“Mật khẩu xác nhận không khớp.” hoặc “Mật khẩu chưa đủ mạnh (tối thiểu 8 ký tự, không được toàn số).”). Trở lại Bước 6. |

##### UC 1.3 – Đổi mật khẩu

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép người dùng đã đăng nhập tự thay đổi mật khẩu của mình. |
| **Kích hoạt** | Người dùng chọn “Đổi mật khẩu” trong menu tài khoản. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập thành công. |
| **Hậu điều kiện** | • Mật khẩu mới được mã hóa và lưu vào bảng users.<br>• Phiên đăng nhập hiện tại vẫn được giữ.<br>• Hệ thống ghi nhật ký đổi mật khẩu. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Đổi mật khẩu”. | 2. Hệ thống hiển thị form gồm: Mật khẩu hiện tại, Mật khẩu mới, Xác nhận mật khẩu mới. |
| 3. Người dùng nhập thông tin và nhấn “Lưu thay đổi”. | 4. Hệ thống kiểm tra: mật khẩu hiện tại đúng; mật khẩu mới khớp với xác nhận và đủ mạnh.<br>5. Hệ thống lưu mật khẩu mới, giữ phiên đăng nhập, ghi nhật ký và hiển thị: “Đổi mật khẩu thành công.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Nhập sai mật khẩu hiện tại. | 3.1.1: Hệ thống hiển thị: “Mật khẩu hiện tại không chính xác.”, không lưu. Trở lại Bước 3. |
| 3.2: (Từ bước 4) Mật khẩu mới và xác nhận không khớp. | 3.2.1: Hệ thống hiển thị: “Mật khẩu xác nhận không khớp.”, không lưu. Trở lại Bước 3. |
| 3.3: (Từ bước 4) Mật khẩu mới chưa đủ mạnh. | 3.3.1: Hệ thống hiển thị: “Mật khẩu chưa đủ mạnh (tối thiểu 8 ký tự, không được toàn số).” Trở lại Bước 3. |

##### UC 1.4 – Xem & cập nhật tài khoản cá nhân

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép người dùng xem thông tin tài khoản và sửa các thông tin liên hệ cơ bản (Họ tên, Số điện thoại, Ảnh đại diện). |
| **Kích hoạt** | Người dùng nhấn vào ảnh đại diện ở góc phải và chọn “Tài khoản của tôi”. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập. |
| **Hậu điều kiện** | • Họ tên, Số điện thoại, Ảnh đại diện được cập nhật trong bảng users.<br>• Với người có hồ sơ nhân sự, Họ tên và Số điện thoại được cập nhật đồng thời trong bảng employees. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Tài khoản của tôi”. | 2. Hệ thống hiển thị: Email, Họ tên, Số điện thoại, Ảnh đại diện, Vai trò; nếu có hồ sơ nhân sự thì hiển thị thêm Phòng ban, Vị trí. |
| 3. Người dùng sửa Họ tên, Số điện thoại hoặc tải ảnh đại diện mới, nhấn “Lưu”. | 4. Hệ thống kiểm tra dữ liệu: Họ tên không trống; Số điện thoại gồm 10–11 chữ số; ảnh là file .jpg/.png không quá 2 MB.<br>5. Hệ thống lưu vào bảng users; nếu có hồ sơ nhân sự thì cập nhật full_name, phone trong bảng employees trong cùng một giao dịch. Hiển thị: “Cập nhật thông tin thành công.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Dữ liệu sai định dạng hoặc bỏ trống Họ tên. | 3.1.1: Hệ thống hiển thị lỗi tại trường tương ứng, không lưu. Trở lại Bước 3. |
| 3.2: Người dùng cố tình gửi kèm các trường bị khóa (Email, Vai trò) bằng cách sửa mã HTML. | 3.2.1: Hệ thống bỏ qua các trường này, chỉ lưu Họ tên, Số điện thoại, Ảnh đại diện. |

##### UC 1.5 – Quản lý tài khoản người dùng

| | |
|---|---|
| **Actor** | Super Admin |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Super Admin xem danh sách tài khoản, phân vai trò, khóa/mở khóa tài khoản và tạo tài khoản trong trường hợp ngoại lệ. Tài khoản nhân viên thông thường được tạo qua UC 2.5. |
| **Kích hoạt** | Super Admin chọn mục “Quản lý tài khoản” trên menu, hoặc mở thông báo “Yêu cầu cấp quyền” (từ UC 2.5). |
| **Tiền điều kiện** | • Người dùng đăng nhập với vai trò SUPER_ADMIN. |
| **Hậu điều kiện** | • Vai trò (role) hoặc trạng thái (is_active) của tài khoản được cập nhật và có hiệu lực ngay từ thao tác tiếp theo của tài khoản đó.<br>• Hệ thống ghi nhật ký vào activity_logs. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Super Admin chọn “Quản lý tài khoản”. | 2. Hệ thống hiển thị danh sách toàn bộ tài khoản kèm bộ lọc Vai trò, Trạng thái và ô tìm theo Email/Họ tên. |
| 3. Super Admin chọn một tài khoản và chọn “Đổi vai trò” hoặc “Khóa/Mở khóa”. | 4. Hệ thống hiển thị hộp xác nhận; khi đổi vai trò, hiển thị kèm chức danh trong hồ sơ nhân sự để đối chiếu. |
| 5. Super Admin nhấn “Xác nhận”. | 6. Hệ thống cập nhật users.role hoặc users.is_active, ghi nhật ký (UPDATE / LOCK / UNLOCK), gửi thông báo cho người được thay đổi và cập nhật danh sách. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 3.1. Super Admin chọn “Thêm tài khoản”, nhập Email, Họ tên, Vai trò. | 3.1.1. Hệ thống tạo bản ghi users chưa có mật khẩu, gửi email đường dẫn đặt mật khẩu (cơ chế UC 1.2) và ghi nhật ký. Chỉ dùng cho trường hợp ngoại lệ (ví dụ: tài khoản Super Admin khác). |
| 3.2. Super Admin mở thông báo “Yêu cầu cấp quyền” cho nhân sự có vị trí Quản lý hoặc Kế toán. | 3.2.1. Hệ thống mở thẳng tài khoản cần nâng quyền, tiếp tục từ Bước 4. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.3: (Từ bước 3.1.1) Email đã tồn tại. | 3.3.1: Hệ thống chặn lưu và hiển thị: “Email này đã được sử dụng.” |
| 5.1: Super Admin tự khóa hoặc tự đổi vai trò của chính mình. | 5.1.1: Hệ thống chặn và hiển thị: “Không thể tự khóa hoặc đổi quyền tài khoản đang đăng nhập.” |
| 1.1: Người dùng không phải Super Admin truy cập chức năng. | 1.1.1: Hệ thống hiển thị trang 403: “Bạn không có quyền truy cập chức năng này.” |

##### UC 1.6 – Đăng xuất

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép người dùng kết thúc phiên làm việc và quay về trang Đăng nhập. |
| **Kích hoạt** | Người dùng nhấn nút “Đăng xuất” trên thanh điều hướng. |
| **Tiền điều kiện** | • Người dùng đang có phiên đăng nhập hợp lệ. |
| **Hậu điều kiện** | • Session bị hủy, cookie phiên bị xóa.<br>• Hệ thống ghi nhật ký LOGOUT.<br>• Người dùng được điều hướng về trang Đăng nhập. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng nhấn “Đăng xuất”. | 2. Hệ thống ghi nhật ký LOGOUT vào activity_logs, hủy session hiện tại và xóa cookie phiên.<br>3. Hệ thống chuyển về trang Đăng nhập kèm thông báo: “Đã đăng xuất an toàn.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: Phiên đăng nhập đã hết hạn trước khi người dùng nhấn “Đăng xuất”. | 1.1.1: Hệ thống chuyển thẳng về trang Đăng nhập. |

#### Phân hệ UC2: Quản lý nhân sự

##### UC 2.1 – Xem danh sách nhân sự

| | |
|---|---|
| **Actor** | Super Admin (chỉ xem), Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép người dùng xem danh sách nhân sự của trung tâm với phạm vi dữ liệu phân theo vai trò. |
| **Kích hoạt** | Người dùng chọn mục “Nhân sự” trên menu. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập. |
| **Hậu điều kiện** | • Danh sách nhân sự hiển thị đúng phạm vi quyền của người dùng. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Nhân sự”. | 2. Hệ thống kiểm tra vai trò:<br>• Super Admin, Quản lý: hiển thị đầy đủ cột Mã NV, Họ tên, Vị trí, Phòng ban, Loại hình (FT/PT), Trạng thái, Số điện thoại, Email; gồm mọi trạng thái nhân sự.<br>• Kế toán, Nhân viên: chỉ hiển thị Mã NV, Họ tên, Vị trí, Phòng ban của nhân sự đang ACTIVE.<br>Danh sách được phân trang 20 dòng/trang. |
| 3. Người dùng nhập từ khóa (Họ tên hoặc Mã NV) hoặc chọn bộ lọc Vị trí, Loại hình, Trạng thái. | 4. Hệ thống trả về danh sách khớp điều kiện. |
| 5. Người dùng nhấn vào một dòng. | 6. Quản lý, Super Admin: hệ thống mở hồ sơ chi tiết (thông tin, giấy tờ, hợp đồng). Kế toán, Nhân viên: chỉ hiển thị thông tin liên hệ cơ bản; nếu là hồ sơ của chính mình thì chuyển sang UC 2.3. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Không có kết quả phù hợp. | 3.1.1: Hệ thống hiển thị: “Không tìm thấy nhân sự phù hợp.” |
| 5.1: Kế toán/Nhân viên sửa đường dẫn để xem hồ sơ chi tiết của người khác. | 5.1.1: Hệ thống hiển thị trang 403: “Bạn không có quyền thực hiện hành động này.” |

##### UC 2.2 – Cập nhật hồ sơ cá nhân

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép nhân sự tự cập nhật thông tin cá nhân và tải lên giấy tờ, chứng chỉ. Thông tin thông thường được cập nhật ngay; giấy tờ, chứng chỉ phải chờ duyệt (UC 2.6). |
| **Kích hoạt** | Người dùng nhấn “Chỉnh sửa” tại màn hình “Hồ sơ của tôi”. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập và có hồ sơ nhân sự. |
| **Hậu điều kiện** | • Thông tin cá nhân được cập nhật trong bảng employees (đồng bộ users.phone).<br>• Giấy tờ mới được lưu trong bảng employee_documents với trạng thái PENDING.<br>• Người duyệt nhận thông báo (Quản lý; nếu người gửi là Quản lý thì Super Admin). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng mở “Hồ sơ của tôi” và chọn “Chỉnh sửa”. | 2. Hệ thống hiển thị form gồm hai phần:<br>• Thông tin cá nhân: Số điện thoại, Địa chỉ, Tài khoản ngân hàng.<br>• Giấy tờ/Chứng chỉ: Loại giấy tờ, Tên giấy tờ, Ngày cấp, Ngày hết hạn, File đính kèm. |
| 3. Người dùng nhập thông tin và nhấn “Lưu hồ sơ”. | 4. Hệ thống kiểm tra dữ liệu.<br>5. Hệ thống cập nhật ngay thông tin cá nhân vào employees. Nếu có giấy tờ tải lên: tạo bản ghi employee_documents trạng thái PENDING và gửi thông báo cho người duyệt.<br>6. Hệ thống ghi nhật ký và hiển thị: “Cập nhật hồ sơ thành công. Giấy tờ mới đang chờ duyệt.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Người dùng chọn một giấy tờ sắp hết hạn, đã hết hạn hoặc bị từ chối và nhấn “Tải bản mới”. | 1.1.1. Hệ thống cho nhập lại Ngày cấp, Ngày hết hạn, File; cập nhật chính bản ghi đó về trạng thái PENDING, xóa lý do từ chối cũ và gửi thông báo cho người duyệt. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Số điện thoại sai định dạng hoặc thiếu trường bắt buộc của giấy tờ. | 3.1.1: Hệ thống hiển thị lỗi tại trường tương ứng, không lưu. Trở lại Bước 3. |
| 3.2: (Từ bước 4) File không phải PDF/JPG/PNG hoặc lớn hơn 5 MB. | 3.2.1: Hệ thống hiển thị: “File không hợp lệ. Chỉ chấp nhận PDF, JPG, PNG dưới 5 MB.” |
| 3.3: (Từ bước 4) Ngày hết hạn trước ngày cấp. | 3.3.1: Hệ thống hiển thị: “Ngày hết hạn phải sau ngày cấp.” |

##### UC 2.3 – Xem hồ sơ cá nhân

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép nhân sự xem toàn bộ thông tin của bản thân: lý lịch, hợp đồng hiện tại, giấy tờ kèm trạng thái duyệt và quỹ phép năm. |
| **Kích hoạt** | Người dùng chọn mục “Hồ sơ của tôi” trên menu. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập và có hồ sơ nhân sự. |
| **Hậu điều kiện** | • Thông tin hồ sơ của chính người dùng được hiển thị đầy đủ. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Hồ sơ của tôi”. | 2. Hệ thống truy vấn bảng employees, contracts (hợp đồng ACTIVE), employee_documents và leave_balances (năm hiện tại, nếu là Full-time) của chính tài khoản đang đăng nhập.<br>3. Hệ thống hiển thị: thông tin cá nhân và công việc (gồm ca làm việc nếu là Full-time); hợp đồng hiện tại (Số HĐ, Loại, Ngày bắt đầu, Ngày kết thúc, Trạng thái); danh sách giấy tờ kèm trạng thái và lý do từ chối (nếu có); số ngày phép năm còn lại. |
| 4. Người dùng chọn một giấy tờ hoặc hợp đồng. | 5. Hệ thống hiển thị chi tiết và cho phép xem file đính kèm. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 4.1: Mục được chọn chưa có dữ liệu (chưa có hợp đồng, chưa có giấy tờ). | 4.1.1: Hệ thống hiển thị: “Chưa cập nhật”. |
| 1.1: Tài khoản không có hồ sơ nhân sự (ví dụ Super Admin) truy cập bằng đường dẫn. | 1.1.1: Hệ thống hiển thị: “Tài khoản không có hồ sơ nhân sự.” Menu này không hiển thị với Super Admin. |

##### UC 2.4 – Theo dõi cảnh báo giấy tờ sắp hết hạn

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép Quản lý xem danh sách giấy tờ, chứng chỉ của nhân sự sắp hết hạn (trong 30 ngày) hoặc đã hết hạn và gửi nhắc nhở cập nhật. |
| **Kích hoạt** | Quản lý mở mục “Cảnh báo giấy tờ” hoặc nhấn vào thông báo nhắc hết hạn (tạo bởi UC 9.2). |
| **Tiền điều kiện** | • Quản lý đã đăng nhập. |
| **Hậu điều kiện** | • Quản lý nắm được danh sách giấy tờ cần xử lý.<br>• Nhân viên được nhắc nhận thông báo; nhật ký REMIND được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý mở “Cảnh báo giấy tờ”. | 2. Hệ thống truy vấn employee_documents: trạng thái APPROVED có expiry_date trong vòng 30 ngày tới, và trạng thái EXPIRED.<br>3. Hệ thống hiển thị danh sách kèm nhãn màu: Vàng “Sắp hết hạn” (còn ≤ 30 ngày), Đỏ “Đã hết hạn”; có bộ lọc theo mức độ và nhân sự. |
| 4. Quản lý chọn một giấy tờ và nhấn “Nhắc nhở cập nhật”. | 5. Hệ thống tạo thông báo cho nhân viên sở hữu: “Giấy tờ [tên] sắp hết hạn/đã hết hạn, vui lòng tải bản mới tại Hồ sơ của tôi.” và ghi nhật ký REMIND. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: (Từ bước 2) Không có giấy tờ nào sắp hết hạn hoặc đã hết hạn. | 1.1.1: Hệ thống hiển thị: “Hiện không có cảnh báo.” |

##### UC 2.5 – Tiếp nhận & quản lý hồ sơ nhân sự (Onboarding)

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Quản lý tiếp nhận ứng viên trúng tuyển (từ UC 8.3) hoặc thêm nhân sự mới thủ công: hệ thống tạo đồng thời tài khoản đăng nhập và hồ sơ nhân sự ở trạng thái ONBOARDING. Quản lý cũng dùng chức năng này để sửa hồ sơ nhân sự. |
| **Kích hoạt** | Quản lý nhấn “Chuyển sang Onboarding” tại ứng viên PASSED, hoặc nhấn “Thêm nhân sự mới”. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập.<br>• Nếu tiếp nhận từ tuyển dụng: ứng viên có trạng thái PASSED. |
| **Hậu điều kiện** | • Bản ghi users (role EMPLOYEE, chưa có mật khẩu) và employees (status ONBOARDING) được tạo.<br>• Nếu là Full-time: bản ghi leave_balances năm hiện tại (12 ngày) được tạo.<br>• Nếu từ tuyển dụng: candidate.status = HIRED.<br>• Nhân viên nhận email đường dẫn tự đặt mật khẩu; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý nhấn “Chuyển sang Onboarding” hoặc “Thêm nhân sự mới”. | 2. Hệ thống hiển thị form hồ sơ; nếu từ ứng viên thì tự điền Họ tên, Email, Số điện thoại, Vị trí, Loại hình (FT/PT). |
| 3. Quản lý bổ sung Giới tính, Ngày sinh, Số CCCD, Địa chỉ, Quốc tịch, Phòng ban, Ngày vào làm, Tài khoản ngân hàng, Ca làm việc (chỉ Full-time: Ca 1 08:00–17:00 hoặc Ca 2 13:00–21:00) và nhấn “Lưu hồ sơ”. | 4. Hệ thống kiểm tra trường bắt buộc, định dạng và tính duy nhất của Email, Số CCCD.<br>5. Trong một giao dịch, hệ thống: tạo users (role = EMPLOYEE, chưa có mật khẩu); tạo employees (status = ONBOARDING); nếu Full-time thì tạo leave_balances 12 ngày cho năm hiện tại; nếu từ ứng viên thì cập nhật candidate.status = HIRED.<br>6. Hệ thống gửi email đường dẫn đặt mật khẩu (cơ chế UC 1.2); nếu Vị trí là MANAGER hoặc ACCOUNTANT thì gửi thông báo “Yêu cầu cấp quyền” tới Super Admin (UC 1.5); ghi nhật ký và hiển thị: “Tạo hồ sơ thành công.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Quản lý chọn một nhân sự trong danh sách và nhấn “Sửa”. | 1.1.1. Hệ thống hiển thị form với dữ liệu hiện tại (không cho sửa Email và Loại hình; Loại hình chỉ thay đổi qua hợp đồng). Đổi Ca làm việc có hiệu lực từ ngày hôm sau và không ảnh hưởng dữ liệu chấm công cũ. Khi lưu: kiểm tra, cập nhật employees, đồng bộ users.full_name, users.phone, ghi nhật ký người sửa. |
| 3.1. Quản lý nhấn “Hủy”. | 3.1.1. Hệ thống không lưu dữ liệu và quay về danh sách nhân sự. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.2: (Từ bước 4) Email hoặc Số CCCD đã tồn tại. | 3.2.1: Hệ thống hiển thị: “Email hoặc số CCCD đã tồn tại trong hệ thống.”, không lưu. |
| 3.3: (Từ bước 4) Bỏ trống trường bắt buộc hoặc sai định dạng. | 3.3.1: Hệ thống hiển thị lỗi tại trường tương ứng, không lưu. |
| 1.2: Ứng viên đã được tiếp nhận trước đó (đã có hồ sơ nhân sự). | 1.2.1: Hệ thống không tạo hồ sơ lần hai, hiển thị: “Ứng viên này đã được tiếp nhận.” kèm liên kết tới hồ sơ hiện có. |

##### UC 2.6 – Duyệt giấy tờ, chứng chỉ

| | |
|---|---|
| **Actor** | Quản lý, Super Admin (chỉ giấy tờ của Quản lý) |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép người duyệt kiểm tra giấy tờ, chứng chỉ do nhân sự tải lên và duyệt hoặc từ chối. Quản lý duyệt giấy tờ của Nhân viên và Kế toán; Super Admin duyệt giấy tờ của tài khoản có vai trò Quản lý. Không ai được duyệt giấy tờ của chính mình. |
| **Kích hoạt** | Người duyệt chọn mục “Giấy tờ chờ duyệt” hoặc nhấn vào thông báo. |
| **Tiền điều kiện** | • Người duyệt đã đăng nhập.<br>• Có giấy tờ ở trạng thái PENDING thuộc phạm vi duyệt. |
| **Hậu điều kiện** | • Giấy tờ chuyển APPROVED hoặc REJECTED (kèm lý do); lưu người duyệt và thời điểm duyệt.<br>• Nhân viên nhận thông báo kết quả; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người duyệt mở “Giấy tờ chờ duyệt”. | 2. Hệ thống hiển thị danh sách giấy tờ PENDING thuộc phạm vi duyệt (Quản lý: của Nhân viên và Kế toán; Super Admin: của Quản lý), không gồm giấy tờ của chính người duyệt. |
| 3. Người duyệt chọn một giấy tờ. | 4. Hệ thống hiển thị: Nhân sự, Loại, Tên giấy tờ, Ngày cấp, Ngày hết hạn, File đính kèm. |
| 5. Người duyệt nhấn “Duyệt”. | 6. Hệ thống cập nhật status = APPROVED, reviewed_by, reviewed_at, xóa rejection_reason cũ; gửi thông báo cho nhân viên và ghi nhật ký. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Người duyệt nhấn “Từ chối” và nhập lý do. | 5.1.1. Hệ thống cập nhật status = REJECTED, lưu rejection_reason, reviewed_by, reviewed_at; gửi thông báo yêu cầu nhân viên tải lại (UC 2.2, luồng 1.1). |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.2: Từ chối nhưng không nhập lý do. | 5.2.1: Hệ thống hiển thị: “Vui lòng nhập lý do từ chối.” |
| 3.1: Giấy tờ đã được người khác xử lý trước đó. | 3.1.1: Hệ thống hiển thị: “Yêu cầu đã được xử lý.” và tải lại danh sách. |

#### Phân hệ UC3: Quản lý hợp đồng

##### UC 3.1 – Quản lý danh sách hợp đồng

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Quản lý xem, tìm kiếm, lọc và thêm mới hợp đồng lao động. Tạo hợp đồng đầu tiên cho nhân sự ONBOARDING là bước kết thúc Onboarding, nhân sự chuyển sang ACTIVE. |
| **Kích hoạt** | Quản lý chọn mục “Hợp đồng” trên menu. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập. |
| **Hậu điều kiện** | • Hợp đồng mới được lưu với trạng thái ACTIVE.<br>• employees.employment_type được đồng bộ theo hợp đồng.<br>• Nếu nhân sự đang ONBOARDING: employees.status = ACTIVE. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý mở “Hợp đồng”. | 2. Hệ thống hiển thị danh sách hợp đồng kèm bộ lọc Loại (FT/PT), Trạng thái (ACTIVE, EXPIRED, TERMINATED) và ô tìm theo tên nhân sự/số hợp đồng. |
| 3. Quản lý nhấn “Thêm hợp đồng”. | 4. Hệ thống hiển thị form: Nhân sự (chỉ ONBOARDING hoặc ACTIVE), Số hợp đồng, Loại (FT/PT), Ngày bắt đầu, Ngày kết thúc (để trống nếu không xác định thời hạn), File scan hợp đồng (PDF). |
| 5. Quản lý nhập thông tin và nhấn “Lưu hợp đồng”. | 6. Hệ thống kiểm tra: số hợp đồng chưa tồn tại; ngày kết thúc sau ngày bắt đầu; nhân sự chưa có hợp đồng ACTIVE.<br>7. Trong một giao dịch, hệ thống: tạo contracts (status = ACTIVE); cập nhật employees.employment_type theo hợp đồng; nếu nhân sự đang ONBOARDING thì chuyển ACTIVE và gửi thông báo cho nhân sự; ghi nhật ký; hiển thị: “Thêm hợp đồng thành công.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.1: (Từ bước 6) Nhân sự đang có hợp đồng ACTIVE. | 5.1.1: Hệ thống hiển thị: “Nhân sự này đang có hợp đồng có hiệu lực. Vui lòng kiểm tra lại hoặc sử dụng tính năng Gia hạn.” |
| 5.2: (Từ bước 6) Số hợp đồng đã tồn tại. | 5.2.1: Hệ thống hiển thị: “Số hợp đồng đã tồn tại.” |
| 5.3: (Từ bước 6) Ngày kết thúc trước ngày bắt đầu, hoặc thiếu file scan. | 5.3.1: Hệ thống hiển thị lỗi tại trường tương ứng: “Ngày kết thúc phải sau ngày bắt đầu.” / “Vui lòng tải file scan hợp đồng.” |

##### UC 3.2 – Tra cứu chi tiết hợp đồng

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép xem chi tiết một hợp đồng theo đúng quyền hạn: Quản lý và Kế toán xem mọi hợp đồng (Kế toán chỉ xem); Nhân viên chỉ xem hợp đồng của chính mình. |
| **Kích hoạt** | Người dùng nhấn “Xem chi tiết” tại danh sách hợp đồng (Quản lý, Kế toán) hoặc tại “Hồ sơ của tôi” (mọi người). |
| **Tiền điều kiện** | • Người dùng đã đăng nhập.<br>• Hợp đồng cần xem đã tồn tại. |
| **Hậu điều kiện** | • Thông tin hợp đồng được hiển thị đúng thẩm quyền. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng nhấn “Xem chi tiết” một hợp đồng. | 2. Hệ thống kiểm tra quyền: Nhân viên chỉ được xem hợp đồng có contract.employee.user = người đang đăng nhập; Quản lý, Kế toán được xem mọi hợp đồng.<br>3. Hệ thống hiển thị: Số hợp đồng, Nhân sự, Loại, Ngày bắt đầu, Ngày kết thúc, Trạng thái, Hợp đồng trước (nếu là gia hạn), Ngày và lý do thanh lý (nếu có), liên kết file scan. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: Nhân viên sửa mã hợp đồng trên đường dẫn để xem hợp đồng của người khác. | 1.1.1: Hệ thống chặn và hiển thị trang 403: “Bạn không có quyền xem hợp đồng này.” |

##### UC 3.3 – Cập nhật & gia hạn hợp đồng

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý gia hạn hợp đồng bằng cách tạo hợp đồng mới liên kết với hợp đồng cũ qua previous_contract, hoặc cập nhật file scan của hợp đồng đang hiệu lực. |
| **Kích hoạt** | Quản lý nhấn “Gia hạn” tại danh sách hợp đồng sắp hết hạn (UC 3.5) hoặc tại chi tiết hợp đồng ACTIVE. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập.<br>• Hợp đồng cần gia hạn đang ở trạng thái ACTIVE. |
| **Hậu điều kiện** | • Hợp đồng cũ chuyển EXPIRED; hợp đồng mới ACTIVE được tạo với previous_contract trỏ về hợp đồng cũ.<br>• employees.employment_type đồng bộ theo hợp đồng mới; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý chọn hợp đồng ACTIVE và nhấn “Gia hạn hợp đồng”. | 2. Hệ thống hiển thị form hợp đồng mới, điền sẵn nhân sự, loại hình và gán previous_contract = hợp đồng cũ. |
| 3. Quản lý nhập Số hợp đồng mới, Ngày bắt đầu mới, Ngày kết thúc mới, Loại (có thể đổi FT/PT), tải file scan và nhấn “Xác nhận gia hạn”. | 4. Hệ thống kiểm tra: số hợp đồng chưa tồn tại; ngày bắt đầu mới sau ngày bắt đầu của hợp đồng cũ; ngày kết thúc mới (nếu có) sau ngày bắt đầu mới.<br>5. Trong một giao dịch, hệ thống: chuyển hợp đồng cũ sang EXPIRED; tạo hợp đồng mới ACTIVE với previous_contract; cập nhật employees.employment_type; ghi nhật ký; gửi thông báo cho nhân sự; hiển thị: “Gia hạn hợp đồng thành công.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Quản lý chọn hợp đồng ACTIVE và nhấn “Cập nhật file scan”. | 1.1.1. Hệ thống cho tải file mới thay thế file_url và ghi nhật ký. Các thông tin khác của hợp đồng không được sửa; muốn thay đổi điều khoản thì dùng chức năng gia hạn. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Ngày bắt đầu/kết thúc không hợp lệ. | 3.1.1: Hệ thống hiển thị: “Ngày bắt đầu/kết thúc của hợp đồng mới không hợp lệ.” |
| 3.2: (Từ bước 4) Số hợp đồng đã tồn tại. | 3.2.1: Hệ thống hiển thị: “Số hợp đồng đã tồn tại.” |

##### UC 3.4 – Thanh lý hợp đồng

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý chấm dứt hợp đồng lao động, ghi nhận ngày và lý do, đồng thời hệ thống tự động cập nhật trạng thái nhân sự, khóa tài khoản và xử lý lịch làm việc tương lai của nhân sự đó. |
| **Kích hoạt** | Quản lý nhấn “Thanh lý” tại danh sách hợp đồng sắp hết hạn (UC 3.5) hoặc tại chi tiết hợp đồng ACTIVE. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập.<br>• Hợp đồng đang ở trạng thái ACTIVE. |
| **Hậu điều kiện** | • Hợp đồng chuyển TERMINATED, lưu termination_date và termination_reason.<br>• Nhân sự chuyển RESIGNED hoặc TERMINATED; tài khoản bị khóa (users.is_active = False).<br>• Lịch dạy, ca làm việc sau ngày thanh lý được giải phóng; buổi dạy chính được đưa vào danh sách cần dạy thay (UC 6.4). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý chọn hợp đồng ACTIVE và nhấn “Thanh lý hợp đồng”. | 2. Hệ thống hiển thị hộp thoại nhập: Ngày thanh lý, Lý do, Hình thức nghỉ (Nhân sự xin nghỉ → RESIGNED; Trung tâm chấm dứt → TERMINATED). |
| 3. Quản lý nhập thông tin và nhấn “Xác nhận thanh lý”. | 4. Hệ thống kiểm tra ngày thanh lý không trước ngày bắt đầu hợp đồng và không sau ngày hôm nay.<br>5. Trong một giao dịch, hệ thống: cập nhật hợp đồng status = TERMINATED, termination_date, termination_reason; cập nhật employees.status theo hình thức nghỉ; khóa tài khoản (users.is_active = False); đặt end_date = ngày thanh lý cho các phân công lớp (class_assignments) và cho cấu hình lương đang hiệu lực (salary_configs.effective_to).<br>6. Với lịch sau ngày thanh lý: buổi dạy mà nhân sự là giáo viên thực tế → tạo substitute_requests (SEARCHING); buổi mà nhân sự là trợ giảng → để trống trợ giảng; chỗ ca làm việc PENDING/SCHEDULED → trả về OPEN (employee = NULL).<br>7. Hệ thống ghi nhật ký, thông báo cho Quản lý số buổi dạy cần người thay và hiển thị: “Thanh lý hợp đồng thành công.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Ngày thanh lý trước ngày bắt đầu hợp đồng hoặc sau ngày hôm nay. | 3.1.1: Hệ thống hiển thị: “Ngày thanh lý không hợp lệ.”, chặn thao tác. |
| 3.2: Bỏ trống lý do thanh lý. | 3.2.1: Hệ thống hiển thị: “Vui lòng nhập lý do thanh lý.” |

##### UC 3.5 – Theo dõi hợp đồng sắp hết hạn

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý xem các hợp đồng sắp hết hạn hoặc đã quá ngày kết thúc mà chưa xử lý, để chủ động gia hạn hoặc thanh lý. Hệ thống không tự kết thúc hợp đồng vì việc tiếp tục hay chấm dứt là quyết định của Quản lý. |
| **Kích hoạt** | Quản lý mở trang “Hợp đồng sắp hết hạn” hoặc nhấn vào thông báo nhắc hạn (tạo bởi UC 9.2). |
| **Tiền điều kiện** | • Quản lý đã đăng nhập. |
| **Hậu điều kiện** | • Quản lý nắm được danh sách hợp đồng cần xử lý. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý mở “Hợp đồng sắp hết hạn”. | 2. Hệ thống lọc các hợp đồng có status = ACTIVE và end_date ≤ hôm nay + 30 ngày.<br>3. Hệ thống hiển thị ba nhóm: “Đã quá hạn” (end_date trước hôm nay), “Còn dưới 7 ngày”, “Còn 7–30 ngày”. Mỗi dòng có hai nút “Gia hạn” (UC 3.3) và “Thanh lý” (UC 3.4). |
| 4. Quản lý chọn một hợp đồng. | 5. Hệ thống hiển thị chi tiết hợp đồng (UC 3.2). |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: (Từ bước 2) Không có hợp đồng nào thỏa điều kiện. | 1.1.1: Hệ thống hiển thị: “Không có hợp đồng sắp hết hạn.” |

#### Phân hệ UC4: Quản lý chấm công

##### UC 4.1 – Chấm công Check-in / Check-out

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case ghi nhận giờ vào và giờ ra thực tế của nhân sự bằng nút bấm trên hệ thống (không kiểm tra IP Wi-Fi), so sánh với lịch dự kiến để xác định đi trễ, về sớm. |
| **Kích hoạt** | Nhân sự mở trang “Chấm công” và nhấn “Check-in” hoặc “Check-out”. |
| **Tiền điều kiện** | • Nhân sự đã đăng nhập, có hồ sơ ở trạng thái ACTIVE.<br>• Nhân sự có lịch làm việc trong ngày: Full-time theo ca cố định ghi trong hồ sơ (Ca 1: 08:00–17:00 hoặc Ca 2: 13:00–21:00, Thứ 2 – Thứ 7); Part-time theo ca SCHEDULED; Trợ giảng Part-time theo buổi dạy được phân công. |
| **Hậu điều kiện** | • Bản ghi attendance được tạo/cập nhật với giờ thực tế, số phút trễ/sớm và trạng thái chấm công. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự mở “Chấm công”. | 2. Hệ thống xác định lịch dự kiến hôm nay: Full-time = giờ của ca trong hồ sơ (Ca 1: 08:00–17:00; Ca 2: 13:00–21:00); Part-time có ca = giờ từng ca; Trợ giảng = từ đầu buổi dạy đầu tiên đến cuối buổi dạy cuối cùng trong ngày. Nếu có đơn nghỉ nửa ngày đã duyệt, lịch chỉ còn nửa ca còn lại (mốc chia: Ca 1 lúc 12:00, Ca 2 lúc 17:00). Hệ thống hiển thị lịch và nút “Check-in”. |
| 3. Nhân sự nhấn “Check-in” (Part-time có nhiều ca thì chọn ca). | 4. Hệ thống tạo bản ghi attendance: work_date, ca (nếu có), giờ dự kiến (planned_start, planned_end), check_in = thời điểm hiện tại.<br>5. Nếu check_in trễ hơn giờ bắt đầu quá 5 phút: attendance_status = LATE và late_minutes = số phút trễ; ngược lại attendance_status = ON_TIME. Hiển thị: “Check-in thành công lúc HH:MM.” và đổi nút sang “Check-out”. |
| 6. Khi kết thúc ca, nhân sự nhấn “Check-out”. | 7. Hệ thống lưu check_out. Nếu check_out sớm hơn giờ kết thúc: early_leave_minutes = số phút về sớm và attendance_status = EARLY_LEAVE (late_minutes vẫn được giữ).<br>8. Hệ thống hiển thị tổng thời gian làm việc trong ca/ngày. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Nhân sự có đơn nghỉ cả ngày đã được duyệt. | 1.1.1. Hệ thống hiển thị: “Hôm nay bạn nghỉ phép.” và không hiển thị nút chấm công. |
| 6.1. Nhân sự quên check-out. | 6.1.1. Tác vụ hằng ngày (UC 9.2) ghi nhận attendance_status = MISSING_CHECKOUT và gửi thông báo để nhân sự giải trình (UC 4.2). |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.2: Nhân sự không có lịch làm việc hôm nay. | 1.2.1: Hệ thống hiển thị: “Hôm nay bạn không có lịch làm việc.” và không hiển thị nút chấm công. |
| 3.1: (Từ bước 4) Nhân sự đã check-in cho ca/ngày này. | 3.1.1: Hệ thống không tạo bản ghi mới và hiển thị: “Bạn đã thực hiện Check-in hôm nay.” |
| 6.2: (Từ bước 7) Nhân sự chưa check-in. | 6.2.1: Hệ thống chặn thao tác và hiển thị: “Vui lòng thực hiện Check-in trước.” |

##### UC 4.2 – Gửi giải trình chấm công

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép nhân sự gửi giải trình kèm minh chứng (ảnh/PDF) cho ngày hoặc ca bị ghi nhận đi trễ, về sớm, vắng mặt hoặc thiếu check-out. |
| **Kích hoạt** | Nhân sự nhấn “Gửi giải trình” tại một dòng có trạng thái lỗi trong Lịch sử chấm công (UC 4.3). |
| **Tiền điều kiện** | • Bản ghi chấm công có attendance_status là LATE, EARLY_LEAVE, ABSENT hoặc MISSING_CHECKOUT và explanation_status = NONE.<br>• Bảng lương của tháng đó chưa được chốt. |
| **Hậu điều kiện** | • explanation_status = PENDING; lý do và minh chứng được lưu.<br>• Người duyệt nhận thông báo (Quản lý; nếu người gửi là Quản lý thì Super Admin). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự chọn dòng chấm công có lỗi và nhấn “Gửi giải trình”. | 2. Hệ thống hiển thị form: Lý do giải trình (bắt buộc), File minh chứng (ảnh/PDF, không bắt buộc). |
| 3. Nhân sự nhập thông tin và nhấn “Gửi đơn”. | 4. Hệ thống lưu explanation_reason, explanation_evidence và cập nhật explanation_status = PENDING.<br>5. Hệ thống gửi thông báo cho người duyệt và hiển thị: “Gửi giải trình thành công.” |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: Bỏ trống lý do. | 3.1.1: Hệ thống cảnh báo đỏ: “Vui lòng nhập lý do giải trình.” và chặn gửi. |
| 1.1: Dòng chấm công đã được giải trình trước đó (PENDING, APPROVED hoặc REJECTED). | 1.1.1: Hệ thống hiển thị: “Ca làm việc này đã được giải trình.” |
| 1.2: Bảng lương tháng đó đã chốt. | 1.2.1: Hệ thống hiển thị: “Bảng lương tháng này đã chốt, không thể thay đổi chấm công.” |

##### UC 4.3 – Xem lịch sử chấm công cá nhân

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép nhân sự xem toàn bộ dữ liệu chấm công của chính mình theo tháng. |
| **Kích hoạt** | Nhân sự chọn mục “Lịch sử chấm công”. |
| **Tiền điều kiện** | • Nhân sự đã đăng nhập và có hồ sơ nhân sự. |
| **Hậu điều kiện** | • Dữ liệu chấm công của chính nhân sự được hiển thị. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự chọn “Lịch sử chấm công”. | 2. Hệ thống truy vấn bảng attendance của chính tài khoản trong tháng hiện tại.<br>3. Hệ thống hiển thị bảng: Ngày, Ca, Giờ dự kiến, Giờ check-in, Giờ check-out, Số phút trễ/sớm, Trạng thái chấm công (tô màu), Trạng thái giải trình, nút “Gửi giải trình” cho dòng lỗi; cuối bảng hiển thị tổng số ngày công (Full-time) hoặc tổng giờ công (Part-time). |
| 4. Nhân sự chọn tháng/năm khác. | 5. Hệ thống lọc và hiển thị lại. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 4.1: Không có dữ liệu trong tháng được chọn. | 4.1.1: Hệ thống hiển thị: “Không có dữ liệu chấm công trong khoảng thời gian đã chọn.” |

##### UC 4.4 – Duyệt giải trình chấm công

| | |
|---|---|
| **Actor** | Quản lý, Super Admin (chỉ giải trình của Quản lý) |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép người duyệt xem lý do, minh chứng và chấp thuận hoặc từ chối giải trình. Quản lý duyệt giải trình của Nhân viên và Kế toán; Super Admin duyệt giải trình của Quản lý. Không ai tự duyệt giải trình của mình. |
| **Kích hoạt** | Người duyệt mở “Giải trình chờ duyệt” hoặc nhấn vào thông báo. |
| **Tiền điều kiện** | • Có giải trình ở trạng thái PENDING thuộc phạm vi duyệt.<br>• Bảng lương của tháng đó chưa được chốt. |
| **Hậu điều kiện** | • Chấp thuận: ngày/ca được tính đủ công theo giờ dự kiến.<br>• Từ chối: giữ nguyên lỗi, lưu lý do từ chối.<br>• Nhân sự nhận thông báo kết quả; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người duyệt mở “Giải trình chờ duyệt”. | 2. Hệ thống hiển thị danh sách giải trình PENDING thuộc phạm vi duyệt. |
| 3. Người duyệt chọn một giải trình. | 4. Hệ thống hiển thị giờ dự kiến, giờ check-in/check-out thực tế, lý do và file minh chứng. |
| 5. Người duyệt nhấn “Chấp thuận”. | 6. Hệ thống cập nhật explanation_status = APPROVED, late_minutes = 0, early_leave_minutes = 0, attendance_status = ON_TIME (ngày/ca được tính đủ công theo giờ dự kiến), lưu explanation_reviewed_by, explanation_reviewed_at; gửi thông báo cho nhân sự và ghi nhật ký. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Người duyệt nhấn “Từ chối” và nhập lý do. | 5.1.1. Hệ thống cập nhật explanation_status = REJECTED, lưu explanation_review_note, giữ nguyên trạng thái lỗi; gửi thông báo cho nhân sự. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.2: Từ chối nhưng không nhập lý do. | 5.2.1: Hệ thống hiển thị: “Vui lòng nhập lý do từ chối.” |
| 5.3: Bảng lương tháng đó đã chốt. | 5.3.1: Hệ thống hiển thị: “Bảng lương tháng này đã chốt, không thể thay đổi chấm công.” |

##### UC 4.5 – Quản lý bảng tổng hợp công

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Super Admin (chỉ xem) |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cung cấp bảng tổng hợp chấm công toàn trung tâm theo tháng, phục vụ đánh giá chuyên cần và làm dữ liệu đầu vào cho tính lương (UC 7.2). |
| **Kích hoạt** | Người dùng chọn mục “Bảng tổng hợp công”. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập với vai trò được phép. |
| **Hậu điều kiện** | • Bảng tổng hợp công của tháng được hiển thị. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Bảng tổng hợp công”. | 2. Hệ thống hiển thị bộ lọc: Tháng/Năm, Phòng ban, Vị trí. |
| 3. Người dùng chọn điều kiện và nhấn “Xem”. | 4. Hệ thống tổng hợp từ attendance và leave_requests cho mỗi nhân sự: Số ngày công (Full-time), Tổng giờ công (Part-time), Số lần đi trễ, Số lần về sớm, Số ngày vắng, Số lần thiếu check-out, Số giải trình chờ duyệt.<br>5. Hệ thống hiển thị bảng, tô đỏ nhân sự còn lỗi chưa giải trình hoặc giải trình đang chờ duyệt. |
| 6. Người dùng nhấn vào một nhân sự. | 7. Hệ thống hiển thị chi tiết từng ngày công của nhân sự đó. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Tháng được chọn chưa có dữ liệu. | 3.1.1: Hệ thống hiển thị bảng trống kèm thông báo: “Không có dữ liệu chấm công trong khoảng thời gian đã chọn.” |

#### Phân hệ UC5: Quản lý nghỉ phép

##### UC 5.1 – Gửi đơn xin nghỉ phép

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép nhân sự tạo đơn xin nghỉ (Phép năm, Nghỉ ốm, Nghỉ không lương, Khác) theo hình thức cả ngày hoặc nửa ngày, và hủy đơn đang chờ duyệt. |
| **Kích hoạt** | Nhân sự nhấn “Tạo đơn nghỉ phép”. |
| **Tiền điều kiện** | • Nhân sự đã đăng nhập và có hồ sơ ACTIVE. |
| **Hậu điều kiện** | • Bản ghi leave_requests được tạo với trạng thái PENDING.<br>• Người duyệt nhận thông báo (Quản lý; nếu người gửi là Quản lý thì Super Admin). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự nhấn “Tạo đơn nghỉ phép”. | 2. Hệ thống hiển thị form: Loại nghỉ (ANNUAL – chỉ Full-time, SICK, UNPAID, OTHER), Hình thức (FULL_DAY – cả ca, HALF_DAY_AM – nửa đầu ca, HALF_DAY_PM – nửa sau ca), Từ ngày, Đến ngày, Lý do; nếu là Full-time thì hiển thị số ngày phép năm còn lại. |
| 3. Nhân sự nhập thông tin và nhấn “Gửi đơn”. | 4. Hệ thống kiểm tra: ngày bắt đầu ≤ ngày kết thúc; nghỉ nửa ngày thì ngày bắt đầu = ngày kết thúc; không trùng đơn PENDING/APPROVED khác; không thuộc tháng đã chốt lương.<br>5. Hệ thống tính total_days = số ngày làm việc (Thứ 2 – Thứ 7) trong khoảng nghỉ; nửa ngày = 0,5. Nếu loại ANNUAL: kiểm tra total_days không vượt số ngày phép còn lại.<br>6. Hệ thống lưu đơn với status = PENDING, gửi thông báo cho người duyệt và hiển thị: “Gửi đơn nghỉ phép thành công.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Nhân sự mở “Đơn nghỉ của tôi”, chọn một đơn PENDING và nhấn “Hủy đơn”. | 1.1.1. Hệ thống cập nhật status = CANCELLED và gửi thông báo cho người duyệt. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 5) Số ngày phép năm xin nghỉ vượt quá số ngày còn lại. | 3.1.1: Hệ thống cảnh báo đỏ: “Quỹ phép năm của bạn không đủ (còn lại: X ngày). Vui lòng chọn loại Nghỉ không lương.” |
| 3.2: (Từ bước 4) Ngày bắt đầu sau ngày kết thúc. | 3.2.1: Hệ thống hiển thị: “Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.” |
| 3.3: (Từ bước 4) Trùng với đơn nghỉ khác đang chờ duyệt hoặc đã duyệt. | 3.3.1: Hệ thống hiển thị: “Bạn đã có đơn nghỉ trong khoảng thời gian này.” |
| 3.4: Nhân sự Part-time chọn loại Phép năm. | 3.4.1: Hệ thống hiển thị: “Chỉ nhân sự Full-time được sử dụng phép năm.” |
| 3.5: (Từ bước 5) Khoảng thời gian chọn không có ngày làm việc nào. | 3.5.1: Hệ thống hiển thị: “Khoảng thời gian đã chọn không có ngày làm việc.” |

##### UC 5.2 – Duyệt đơn xin nghỉ phép

| | |
|---|---|
| **Actor** | Quản lý, Super Admin (chỉ đơn của Quản lý) |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép người duyệt chấp thuận hoặc từ chối đơn nghỉ. Khi duyệt đơn phép năm, hệ thống trừ quỹ phép; khi đơn nghỉ ảnh hưởng tới buổi dạy, hệ thống tự tạo yêu cầu dạy thay. Quản lý duyệt đơn của Nhân viên và Kế toán; Super Admin duyệt đơn của Quản lý. |
| **Kích hoạt** | Người duyệt mở “Đơn nghỉ chờ duyệt” hoặc nhấn vào thông báo. |
| **Tiền điều kiện** | • Có đơn nghỉ ở trạng thái PENDING thuộc phạm vi duyệt; người duyệt không phải người gửi đơn. |
| **Hậu điều kiện** | • Đơn chuyển APPROVED hoặc REJECTED; lưu reviewed_by, reviewed_at, review_note.<br>• Nếu duyệt đơn ANNUAL: leave_balances.used_days tăng thêm total_days.<br>• Nếu đơn ảnh hưởng buổi dạy chính: needs_substitute = True và substitute_requests được tạo (UC 6.4). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người duyệt mở “Đơn nghỉ chờ duyệt”. | 2. Hệ thống hiển thị danh sách đơn PENDING thuộc phạm vi duyệt. |
| 3. Người duyệt chọn một đơn. | 4. Hệ thống hiển thị: nhân sự, loại nghỉ, hình thức, từ ngày – đến ngày, số ngày, lý do, quỹ phép còn lại, lịch sử nghỉ trong năm và danh sách buổi dạy/ca làm việc bị ảnh hưởng. |
| 5. Người duyệt nhấn “Duyệt đơn”. | 6. Hệ thống cập nhật status = APPROVED, reviewed_by, reviewed_at. Nếu leave_type = ANNUAL: kiểm tra lại quỹ phép và cộng total_days vào used_days.<br>7. Hệ thống xác định lịch bị ảnh hưởng trong thời gian nghỉ (nghỉ nửa đầu ca: buổi bắt đầu trước mốc giữa ca; nghỉ nửa sau ca: buổi bắt đầu từ mốc giữa ca; mốc giữa ca là 12:00 với Ca 1, 17:00 với Ca 2): với mỗi buổi dạy nhân sự là giáo viên thực tế → đặt needs_substitute = True và tạo một substitute_requests (SEARCHING); buổi nhân sự là trợ giảng hoặc ca làm việc đã chốt → gửi thông báo để Quản lý điều chỉnh người (UC 6.4, UC 6.3).<br>8. Hệ thống gửi thông báo kết quả cho nhân sự và ghi nhật ký. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Người duyệt nhấn “Từ chối” và nhập lý do. | 5.1.1. Hệ thống cập nhật status = REJECTED, lưu review_note, giữ nguyên quỹ phép và gửi thông báo kèm lý do cho nhân sự. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.2: Từ chối nhưng không nhập lý do. | 5.2.1: Hệ thống hiển thị: “Vui lòng nhập lý do từ chối.” |
| 5.3: (Từ bước 6) Quỹ phép không còn đủ tại thời điểm duyệt (do đơn khác đã được duyệt trước). | 5.3.1: Hệ thống hiển thị: “Quỹ phép của nhân sự không còn đủ. Vui lòng từ chối hoặc đề nghị nhân sự đổi loại nghỉ.” |
| 3.1: Đơn đã được xử lý hoặc đã bị hủy. | 3.1.1: Hệ thống hiển thị: “Yêu cầu đã được xử lý.” và tải lại danh sách. |

##### UC 5.3 – Tra cứu quỹ phép cá nhân

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép nhân sự Full-time xem số ngày phép năm của mình và danh sách đơn nghỉ đã gửi. |
| **Kích hoạt** | Nhân sự chọn mục “Quỹ phép & đơn nghỉ của tôi”. |
| **Tiền điều kiện** | • Nhân sự đã đăng nhập và có hồ sơ nhân sự. |
| **Hậu điều kiện** | • Số liệu quỹ phép và danh sách đơn nghỉ được hiển thị. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự chọn “Quỹ phép & đơn nghỉ của tôi”. | 2. Hệ thống truy vấn leave_balances của năm hiện tại và leave_requests của chính nhân sự.<br>3. Hệ thống hiển thị ba thẻ: Tổng phép năm (mặc định 12), Đã sử dụng, Còn lại (= Tổng − Đã sử dụng); bên dưới là danh sách đơn nghỉ trong năm kèm trạng thái. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: Nhân sự là Part-time. | 1.1.1: Hệ thống ẩn ba thẻ quỹ phép, hiển thị: “Nhân sự Part-time không có quỹ phép năm.” và chỉ hiển thị danh sách đơn nghỉ. |

##### UC 5.4 – Tổng hợp lịch sử nghỉ phép

| | |
|---|---|
| **Actor** | Quản lý, Super Admin (chỉ xem) |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý xem tình hình nghỉ phép của toàn trung tâm theo tháng/năm. |
| **Kích hoạt** | Người dùng chọn mục “Tổng hợp nghỉ phép”. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập với vai trò được phép. |
| **Hậu điều kiện** | • Bảng tổng hợp nghỉ phép được hiển thị. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Tổng hợp nghỉ phép”. | 2. Hệ thống hiển thị bộ lọc: Tháng/Năm, Phòng ban, Vị trí, Loại nghỉ. |
| 3. Người dùng chọn điều kiện. | 4. Hệ thống hiển thị danh sách đơn đã duyệt (nhân sự, loại nghỉ, từ ngày – đến ngày, số ngày), bảng tổng số ngày nghỉ theo từng loại và số ngày phép năm còn lại của từng nhân sự Full-time. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: Không có dữ liệu phù hợp. | 3.1.1: Hệ thống hiển thị: “Không có dữ liệu nghỉ phép trong khoảng thời gian đã chọn.” |

#### Phân hệ UC6: Lịch làm việc & Phân công

##### UC 6.1 – Tạo và phân công lớp học

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý tạo lớp học mới, phân công giáo viên chính Full-time và trợ giảng, hệ thống tự sinh toàn bộ buổi dạy theo lịch học. |
| **Kích hoạt** | Quản lý nhấn “Tạo lớp học mới”. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập.<br>• Hệ thống có giáo viên Full-time ở trạng thái ACTIVE. |
| **Hậu điều kiện** | • Lớp được lưu với trạng thái UPCOMING; class_assignments được tạo cho giáo viên chính (và trợ giảng nếu có).<br>• Toàn bộ teaching_sessions của khóa được sinh tự động (SCHEDULED).<br>• Giáo viên, trợ giảng nhận thông báo. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý nhấn “Tạo lớp học mới”. | 2. Hệ thống hiển thị form: Tên lớp, Môn/Trình độ, Phòng học, Sĩ số tối đa, Ngày bắt đầu, Ngày kết thúc dự kiến, Các thứ học trong tuần, Giờ bắt đầu, Giờ kết thúc. |
| 3. Quản lý nhập thông tin và nhấn “Tiếp tục”. | 4. Hệ thống kiểm tra dữ liệu và tính danh sách ngày học (các ngày từ ngày bắt đầu đến ngày kết thúc trùng với các thứ đã chọn).<br>5. Hệ thống kiểm tra phòng học không bị lớp khác dùng trùng giờ; hiển thị danh sách giáo viên gợi ý (TEACHER, FULL_TIME, ACTIVE, có ca làm việc bao trọn giờ học – ví dụ lớp 18:00–20:00 chỉ gợi ý giáo viên Ca 2 – và không có buổi dạy trùng giờ trong các ngày học) và danh sách trợ giảng phù hợp (TEACHING_ASSISTANT, ACTIVE, không trùng giờ). |
| 6. Quản lý chọn giáo viên chính (bắt buộc), trợ giảng (không bắt buộc) và nhấn “Xác nhận phân công”. | 7. Hệ thống kiểm tra lại trùng lịch; trong một giao dịch: lưu classes (UPCOMING); tạo class_assignments (MAIN_TEACHER và TEACHING_ASSISTANT); sinh teaching_sessions cho từng ngày học với giờ, phòng, planned_teacher = actual_teacher = giáo viên chính, planned_assistant = actual_assistant = trợ giảng, status = SCHEDULED.<br>8. Hệ thống gửi thông báo cho giáo viên, trợ giảng và hiển thị: “Tạo lớp và phân công thành công (N buổi).” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Quản lý chọn một lớp UPCOMING/ACTIVE và nhấn “Hủy lớp”, nhập lý do. | 1.1.1. Hệ thống chuyển lớp sang CANCELLED, các buổi SCHEDULED từ hôm nay trở đi sang CANCELLED, đặt end_date cho các phân công lớp, gửi thông báo cho giáo viên, trợ giảng. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Thiếu trường bắt buộc, giờ kết thúc không sau giờ bắt đầu, hoặc ngày kết thúc trước ngày bắt đầu. | 3.1.1: Hệ thống hiển thị lỗi tại trường tương ứng. |
| 3.2: (Từ bước 5) Phòng học đã có lớp khác trùng giờ. | 3.2.1: Hệ thống hiển thị: “Phòng [tên phòng] đã có lớp khác vào khung giờ này.” |
| 3.3: (Từ bước 5) Không có giáo viên phù hợp. | 3.3.1: Hệ thống hiển thị: “Không có giáo viên phù hợp, vui lòng điều chỉnh lịch học.” |
| 6.1: (Từ bước 7) Giáo viên vừa bị trùng lịch do thao tác khác. | 6.1.1: Hệ thống hiển thị: “Giáo viên bị trùng lịch, vui lòng chọn lại.” Trở lại Bước 6. |

##### UC 6.2 – Xem lịch làm việc & lịch lớp học

| | |
|---|---|
| **Actor** | Super Admin (chỉ xem), Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case hiển thị lịch dạng bảng theo tuần hoặc theo ngày với hai tab: Lịch làm việc (ca làm việc, buổi dạy của cá nhân) và Lịch lớp học (buổi dạy của toàn trung tâm). Giáo viên ghi nội dung buổi học tại đây. |
| **Kích hoạt** | Người dùng chọn mục “Lịch trình” trên menu. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập. |
| **Hậu điều kiện** | • Lịch được hiển thị đúng phạm vi quyền của người dùng. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng chọn “Lịch trình”. | 2. Hệ thống hiển thị tuần hiện tại với hai tab:<br>• Tab Lịch làm việc: Quản lý, Super Admin xem ca làm việc SCHEDULED của toàn trung tâm, có lọc theo tên nhân sự; Kế toán, Nhân viên chỉ xem ca làm việc và buổi dạy/trợ giảng của chính mình.<br>• Tab Lịch lớp học: mọi người xem các buổi dạy của toàn trung tâm (tên lớp, phòng, giáo viên, trợ giảng); Quản lý, Super Admin có thêm bộ lọc Giáo viên, Lớp, Phòng. |
| 3. Người dùng chuyển tuần trước/tuần sau hoặc chọn xem theo ngày. | 4. Hệ thống hiển thị lại (theo tuần: bảng 7 cột; theo ngày: danh sách theo giờ). |
| 5. Người dùng nhấn vào một mục trên lịch. | 6. Hệ thống hiển thị chi tiết: giờ bắt đầu, giờ kết thúc, phòng, giáo viên, trợ giảng, trạng thái, nội dung buổi học. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Giáo viên thực tế của buổi dạy nhấn “Ghi nội dung buổi học”. | 5.1.1. Hệ thống cho nhập và lưu lesson_note của buổi dạy. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: Khoảng thời gian không có lịch. | 3.1.1: Hệ thống hiển thị lịch trống kèm thông báo: “Không có lịch trình trong thời gian này.” |
| 1.1: Nhân viên sửa đường dẫn để xem lịch làm việc của người khác. | 1.1.1: Hệ thống từ chối và hiển thị: “Bạn không có quyền xem lịch cá nhân của người khác.” |

##### UC 6.3 – Đăng ký & phân công ca làm việc Part-time

| | |
|---|---|
| **Actor** | Quản lý, Nhân viên Part-time |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý mở khung ca có giới hạn số người và hạn chót đăng ký; nhân viên Part-time giữ chỗ theo nguyên tắc ai đăng ký trước được giữ chỗ trước; Quản lý chốt và công bố lịch. Mỗi chỗ trong khung ca là một dòng shift_assignments, các chỗ cùng khung ca có chung slot_group. |
| **Kích hoạt** | Quản lý nhấn “Tạo khung ca”; nhân viên Part-time mở “Đăng ký ca”. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập; nhân viên Part-time ở trạng thái ACTIVE. |
| **Hậu điều kiện** | • Các chỗ có người được chốt chuyển SCHEDULED, lưu assigned_by và hiển thị trên lịch (UC 6.2); chỗ trống chuyển CANCELLED.<br>• Nhân viên nhận thông báo kết quả. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý nhấn “Tạo khung ca”, nhập Vai trò ca, Ngày, Giờ bắt đầu, Giờ kết thúc, Số người cần, Hạn chót đăng ký. | 2. Hệ thống kiểm tra hạn chót trước giờ bắt đầu ca; tạo đúng N dòng shift_assignments (employee = NULL, status = OPEN) có chung slot_group; gửi thông báo mời đăng ký tới tất cả nhân viên Part-time ACTIVE. |
| 3. Nhân viên Part-time mở “Đăng ký ca”. | 4. Hệ thống hiển thị các khung ca còn hạn: vai trò, ngày giờ, số chỗ “Đã giữ x/N”, nút “Giữ chỗ”. |
| 5. Nhân viên nhấn “Giữ chỗ”. | 6. Hệ thống kiểm tra: chưa quá hạn chót; nhân viên chưa giữ chỗ trong khung ca này; không trùng giờ với ca hoặc buổi dạy khác của nhân viên.<br>7. Hệ thống tìm một dòng OPEN của khung ca và cập nhật có điều kiện (chỉ ghi nếu chỗ đó vẫn còn trống): employee = nhân viên, status = PENDING, registered_at = thời điểm hiện tại. Hiển thị: “Giữ chỗ thành công.” |
| 8. Sau hạn chót, Quản lý mở “Tổng hợp duyệt ca”, điều chỉnh (bỏ người, gán nhân viên vào chỗ trống) và nhấn “Chốt & Công bố lịch”. | 9. Hệ thống chuyển các chỗ có người sang SCHEDULED và lưu assigned_by; chuyển các chỗ còn trống sang CANCELLED; gửi thông báo kết quả cho từng nhân viên; lịch hiển thị trên UC 6.2. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Nhân viên nhấn “Hủy giữ chỗ” trước hạn chót. | 5.1.1. Hệ thống trả dòng đó về OPEN (employee = NULL, registered_at = NULL). |
| 8.1. Quản lý đổi người cho một ca đã SCHEDULED (ví dụ nhân viên nghỉ phép). | 8.1.1. Hệ thống chỉ cho chọn nhân viên Part-time ACTIVE không trùng lịch, cập nhật employee và gửi thông báo cho cả hai người. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.2: (Từ bước 6) Đăng ký sau hạn chót. | 5.2.1: Hệ thống chặn lưu và hiển thị: “Đã hết thời hạn đăng ký ca làm việc này.” |
| 5.3: (Từ bước 7) Không còn chỗ trống (kể cả trường hợp hai người cùng bấm, người còn lại đã lấy chỗ cuối). | 5.3.1: Hệ thống hiển thị: “Ca này đã đủ người.” |
| 5.4: (Từ bước 6) Trùng giờ với lịch khác hoặc đã giữ chỗ trong khung ca này. | 5.4.1: Hệ thống hiển thị: “Bạn đã có lịch làm việc trùng giờ với ca này.” hoặc “Bạn đã giữ chỗ trong ca này.” |
| 8.2: Quản lý chốt khi chưa hết hạn đăng ký. | 8.2.1: Hệ thống hiển thị: “Chưa hết hạn đăng ký, chưa thể chốt ca.” |

##### UC 6.4 – Xử lý dạy thay

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép Quản lý tìm và chốt giáo viên dạy thay cho buổi dạy bị trống (do đơn nghỉ được duyệt ở UC 5.2 hoặc thanh lý hợp đồng ở UC 3.4); nếu không có người thì hủy buổi và có thể thêm buổi học bù. Quản lý cũng điều chỉnh trợ giảng của từng buổi tại đây. |
| **Kích hoạt** | Quản lý mở “Buổi dạy cần người thay” hoặc nhấn vào thông báo. |
| **Tiền điều kiện** | • Có substitute_requests ở trạng thái SEARCHING. |
| **Hậu điều kiện** | • Thành công: teaching_sessions.actual_teacher = giáo viên dạy thay; yêu cầu COMPLETED.<br>• Không có người: yêu cầu FAILED; buổi dạy CANCELLED.<br>• Các bên liên quan nhận thông báo; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý mở “Buổi dạy cần người thay”. | 2. Hệ thống hiển thị các yêu cầu SEARCHING: lớp, ngày giờ, phòng, giáo viên vắng, nguồn (đơn nghỉ hoặc thanh lý). |
| 3. Quản lý chọn một yêu cầu và nhấn “Tìm người dạy thay”. | 4. Hệ thống gợi ý giáo viên: TEACHER, ACTIVE, khác giáo viên vắng, có ca làm việc bao trọn giờ buổi dạy (với giáo viên Full-time), không có buổi dạy/ca trùng giờ, không có đơn nghỉ đã duyệt vào ngày đó. |
| 5. Quản lý chọn một giáo viên và nhấn “Chốt dạy thay”. | 6. Trong một giao dịch, hệ thống: cập nhật teaching_sessions.actual_teacher = giáo viên được chọn; cập nhật substitute_requests.substitute_employee, manager_confirmed_by, status = COMPLETED.<br>7. Hệ thống gửi thông báo cho giáo viên dạy thay và giáo viên vắng, ghi nhật ký. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 5.1. Không có giáo viên phù hợp, Quản lý nhấn “Hủy buổi học”. | 5.1.1. Hệ thống cập nhật yêu cầu FAILED, buổi dạy CANCELLED và gửi thông báo cho giáo viên phụ trách, trợ giảng. |
| 5.2. Sau khi hủy buổi, Quản lý nhấn “Thêm buổi học bù” và chọn ngày, giờ. | 5.2.1. Hệ thống kiểm tra trùng lịch giáo viên, phòng và tạo một teaching_sessions mới (SCHEDULED) cho lớp; nếu buổi bù sau ngày kết thúc của lớp thì cập nhật classes.end_date bằng ngày buổi bù. |
| 1.1. Quản lý mở một buổi dạy và nhấn “Đổi trợ giảng”. | 1.1.1. Hệ thống cho chọn trợ giảng ACTIVE không trùng giờ hoặc để trống, cập nhật actual_assistant và gửi thông báo cho người liên quan. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.3: (Từ bước 6) Giáo viên được chọn vừa bị trùng lịch. | 5.3.1: Hệ thống hiển thị: “Giáo viên bị trùng lịch, vui lòng chọn lại.” Trở lại Bước 4. |

#### Phân hệ UC7: Quản lý lương

##### UC 7.1 – Quản lý cấu hình lương

| | |
|---|---|
| **Actor** | Kế toán |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Kế toán thiết lập và lưu lịch sử thông số tính lương của từng nhân sự: lương cơ bản, phụ cấp lớp, phụ cấp trách nhiệm (Full-time), đơn giá giờ (Part-time). |
| **Kích hoạt** | Kế toán chọn một nhân sự và nhấn “Cấu hình lương”. |
| **Tiền điều kiện** | • Kế toán đã đăng nhập.<br>• Nhân sự có hồ sơ ở trạng thái ONBOARDING hoặc ACTIVE. |
| **Hậu điều kiện** | • Cấu hình mới được lưu vào salary_configs; cấu hình trước đó được đóng hiệu lực (effective_to = ngày áp dụng mới − 1 ngày).<br>• Lịch sử cấu hình được bảo toàn; nhật ký được ghi. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Kế toán chọn nhân sự và nhấn “Cấu hình lương”. | 2. Hệ thống hiển thị thông tin nhân sự (Loại hình, Vị trí), cấu hình đang hiệu lực và lịch sử cấu hình. |
| 3. Kế toán nhấn “Thêm cấu hình mới”. | 4. Hệ thống hiển thị form theo loại hình: Full-time gồm Lương cơ bản, Phụ cấp lớp (chỉ với giáo viên), Phụ cấp trách nhiệm; Part-time gồm Đơn giá giờ (mặc định 35.000 đ); và Ngày bắt đầu áp dụng. |
| 5. Kế toán nhập thông tin và nhấn “Lưu cấu hình”. | 6. Hệ thống kiểm tra: các số tiền ≥ 0; Full-time có lương cơ bản > 0; Part-time có đơn giá giờ > 0; ngày áp dụng sau ngày áp dụng của cấu hình hiện tại và không thuộc tháng đã chốt lương.<br>7. Trong một giao dịch, hệ thống: đặt effective_to của cấu hình hiện tại = ngày áp dụng mới − 1 ngày; tạo cấu hình mới; ghi nhật ký; hiển thị: “Lưu cấu hình lương thành công.” |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Kế toán chọn “Lịch sử cấu hình lương”. | 1.1.1. Hệ thống hiển thị các cấu hình theo thứ tự thời gian, mỗi dòng gồm các mức lương, ngày bắt đầu và ngày kết thúc hiệu lực. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 5.1: (Từ bước 6) Ngày áp dụng không sau cấu hình hiện tại. | 5.1.1: Hệ thống hiển thị: “Ngày áp dụng phải sau ngày áp dụng của cấu hình hiện tại.” |
| 5.2: (Từ bước 6) Số tiền không hợp lệ. | 5.2.1: Hệ thống hiển thị lỗi tại trường tương ứng và yêu cầu nhập lại. |
| 5.3: (Từ bước 6) Ngày áp dụng thuộc tháng đã chốt lương. | 5.3.1: Hệ thống hiển thị: “Không thể áp dụng cấu hình cho tháng đã chốt lương.” |

##### UC 7.2 – Lập và chốt bảng lương

| | |
|---|---|
| **Actor** | Kế toán |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Kế toán lập bảng lương tháng: hệ thống tự tổng hợp chấm công, nghỉ phép, phân công lớp và cấu hình lương để tính lương nháp; Kế toán thêm các khoản thủ công, chốt bảng lương và phát hành phiếu lương. |
| **Kích hoạt** | Kế toán chọn chức năng “Lập bảng lương”. |
| **Tiền điều kiện** | • Kế toán đã đăng nhập.<br>• Tháng cần tính đã kết thúc; không còn giải trình chấm công PENDING trong tháng.<br>• Mọi nhân sự thuộc phạm vi tính lương có cấu hình lương hiệu lực. |
| **Hậu điều kiện** | • Mỗi nhân sự có một bản ghi payrolls và các dòng payroll_details của tháng.<br>• Sau khi chốt: status = LOCKED, chấm công tháng đó không sửa được. Sau khi phát hành: status = SENT, nhân sự xem được phiếu lương (UC 7.3). |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Kế toán chọn “Lập bảng lương”. | 2. Hệ thống hiển thị form chọn Tháng/Năm. |
| 3. Kế toán chọn tháng/năm và nhấn “Khởi tạo bảng lương”. | 4. Hệ thống kiểm tra: tháng đã kết thúc; chưa có bảng lương tháng này; không còn giải trình PENDING; mọi nhân sự trong phạm vi có cấu hình lương.<br>5. Hệ thống xác định phạm vi: nhân sự ACTIVE và nhân sự đã nghỉ (RESIGNED/TERMINATED) có ngày thanh lý trong tháng. Cấu hình lương dùng là cấu hình hiệu lực vào ngày cuối tháng (hoặc ngày thanh lý).<br>6. Với mỗi nhân sự, hệ thống tạo payrolls (DRAFT) và các dòng tự động trong payroll_details:<br>• Full-time: WORKDAY_SALARY = lương cơ bản × số ngày công / 26 (số ngày công tối đa 26, gồm ngày có chấm công hợp lệ và ngày phép năm đã duyệt; ngày nghỉ nửa ngày tính 0,5).<br>• Giáo viên Full-time: CLASS_ALLOWANCE = phụ cấp lớp × số lớp đang phân công giáo viên chính có buổi dạy trong tháng.<br>• Có phụ cấp trách nhiệm: RESPONSIBILITY_ALLOWANCE = mức phụ cấp.<br>• Part-time: PART_TIME_HOURLY_PAY = đơn giá giờ × tổng giờ công (giờ làm thực tế trong khung giờ dự kiến; dòng được chấp thuận giải trình tính đủ giờ dự kiến).<br>7. Hệ thống tính tổng: gross_pay = tổng các khoản EARNING; total_deduction = tổng các khoản DEDUCTION; total_tax = tổng các khoản TAX; net_pay = gross_pay − total_deduction − total_tax, rồi hiển thị bảng lương tổng. |
| 8. Kế toán xem chi tiết từng nhân sự và thêm khoản thủ công: Thưởng (BONUS), Điều chỉnh tăng/giảm, Thuế TNCN, Khác. | 9. Hệ thống lưu dòng chi tiết và tính lại các tổng của nhân sự đó. |
| 10. Kế toán nhấn “Chốt bảng lương”. | 11. Hệ thống kiểm tra không có net_pay âm; chuyển toàn bộ payrolls của tháng sang LOCKED, lưu locked_at. Từ thời điểm này, chấm công, giải trình, đơn nghỉ và cấu hình lương thuộc tháng đó không được thay đổi. |
| 12. Kế toán nhấn “Phát hành phiếu lương”. | 13. Hệ thống chuyển sang SENT, lưu sent_at, gửi thông báo tới từng nhân sự: “Phiếu lương tháng X/Y đã được phát hành.” và ghi nhật ký. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 8.1. Kế toán nhấn “Tính lại” khi dữ liệu thay đổi trong lúc bảng lương còn DRAFT (ví dụ giải trình mới được duyệt). | 8.1.1. Hệ thống xóa các dòng tự động (WORKDAY_SALARY, PART_TIME_HOURLY_PAY, CLASS_ALLOWANCE, RESPONSIBILITY_ALLOWANCE), tính lại, giữ nguyên các dòng thủ công và bổ sung bảng lương cho nhân sự mới thuộc phạm vi (nếu có). |
| 8.2. Kế toán xóa một khoản thủ công đã thêm. | 8.2.1. Hệ thống xóa dòng chi tiết và tính lại các tổng. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: (Từ bước 4) Bảng lương tháng này đã tồn tại. | 3.1.1: Hệ thống chặn tạo mới, hiển thị: “Bảng lương tháng này đã tồn tại.” và mở bảng lương hiện có. |
| 3.2: (Từ bước 4) Còn giải trình chấm công chờ duyệt trong tháng. | 3.2.1: Hệ thống hiển thị: “Còn N giải trình chấm công chờ duyệt trong tháng. Vui lòng xử lý trước khi lập bảng lương.” |
| 3.3: (Từ bước 4) Có nhân sự chưa có cấu hình lương. | 3.3.1: Hệ thống hiển thị danh sách: “Các nhân sự sau chưa có cấu hình lương: …” và dừng lại. |
| 3.4: (Từ bước 4) Tháng chưa kết thúc. | 3.4.1: Hệ thống hiển thị: “Chỉ lập bảng lương cho tháng đã kết thúc.” |
| 10.1: (Từ bước 11) Có nhân sự có thực nhận âm. | 10.1.1: Hệ thống hiển thị: “Thực nhận của [tên nhân sự] đang âm, vui lòng kiểm tra các khoản khấu trừ.” và không chốt. |

##### UC 7.3 – Tra cứu phiếu lương cá nhân

| | |
|---|---|
| **Actor** | Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | Medium |
| **Mô tả** | Use case cho phép nhân sự xem chi tiết phiếu lương của chính mình theo từng tháng sau khi phiếu lương đã được phát hành (SENT), và in hoặc lưu thành PDF bằng chức năng in của trình duyệt. |
| **Kích hoạt** | Nhân sự chọn mục “Phiếu lương của tôi”. |
| **Tiền điều kiện** | • Nhân sự đã đăng nhập và có hồ sơ nhân sự. |
| **Hậu điều kiện** | • Phiếu lương của chính nhân sự được hiển thị. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Nhân sự chọn “Phiếu lương của tôi”. | 2. Hệ thống hiển thị danh sách các tháng có phiếu lương của chính nhân sự ở trạng thái SENT. |
| 3. Nhân sự chọn một tháng. | 4. Hệ thống hiển thị phiếu lương: thông tin nhân sự; các khoản thu nhập (lương ngày công hoặc lương giờ, phụ cấp lớp, phụ cấp trách nhiệm, thưởng, điều chỉnh tăng); các khoản khấu trừ; thuế TNCN; thực nhận (net_pay). |
| 5. Nhân sự nhấn “In / Lưu PDF”. | 6. Hệ thống mở hộp thoại in của trình duyệt với bố cục phiếu lương; nhân sự chọn máy in hoặc “Lưu dưới dạng PDF”. |

**Luồng thay thế (Alternative Flow)**

_Không có._

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.1: Chưa có phiếu lương nào được phát hành. | 1.1.1: Hệ thống hiển thị: “Chưa có phiếu lương nào được phát hành.” Bảng lương ở trạng thái DRAFT hoặc LOCKED không hiển thị với nhân sự. |
| 3.1: Nhân sự sửa đường dẫn để xem phiếu lương của người khác hoặc phiếu chưa phát hành. | 3.1.1: Hệ thống từ chối truy cập (trang 403). |

#### Phân hệ UC8: Quản lý tuyển dụng

##### UC 8.1 – Quản lý đợt tuyển dụng & hồ sơ ứng viên

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | Must Have |
| **Mô tả** | Use case cho phép Quản lý tạo đợt tuyển dụng, nhập hồ sơ ứng viên (kèm CV) và đánh giá sơ tuyển Đạt/Không đạt. |
| **Kích hoạt** | Quản lý chọn mục “Tuyển dụng”. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập. |
| **Hậu điều kiện** | • Đợt tuyển dụng và hồ sơ ứng viên được lưu.<br>• Ứng viên đạt sơ tuyển có status = SCREENING (chờ xếp phỏng vấn); không đạt có status = REJECTED. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý nhấn “Tạo đợt tuyển dụng”, nhập Tên đợt, Ngày bắt đầu, Ngày kết thúc. | 2. Hệ thống lưu recruitment_campaigns với status = OPEN. |
| 3. Trong một đợt đang OPEN, Quản lý nhấn “Thêm ứng viên”, nhập Họ tên, Email, Số điện thoại, Vị trí ứng tuyển, Loại hình (FT/PT) và tải CV (PDF). | 4. Hệ thống kiểm tra dữ liệu và lưu candidates với status = NEW. |
| 5. Quản lý xem CV, chọn “Đạt sơ tuyển” hoặc “Không đạt” và nhập ghi chú. | 6. Hệ thống lưu screening_note; Đạt → status = SCREENING (vào danh sách chờ phỏng vấn); Không đạt → status = REJECTED (hồ sơ vẫn được lưu). |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Quản lý nhấn “Đóng đợt”. | 1.1.1. Hệ thống cập nhật status = CLOSED; đợt đã đóng không nhận thêm ứng viên. |
| 5.1. Quản lý sửa kết quả sơ tuyển của ứng viên chưa được xếp lịch phỏng vấn. | 5.1.1. Hệ thống cho phép cập nhật lại trạng thái và ghi chú. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.1: Đợt tuyển dụng đã đóng. | 3.1.1: Hệ thống hiển thị: “Đợt tuyển dụng đã đóng, không thể thêm ứng viên.” |
| 3.2: (Từ bước 4) Thiếu trường bắt buộc, sai định dạng, hoặc CV không phải PDF/lớn hơn 5 MB. | 3.2.1: Hệ thống hiển thị lỗi tại trường tương ứng, không lưu. |
| 3.3: (Từ bước 4) Email ứng viên đã có trong cùng đợt tuyển dụng. | 3.3.1: Hệ thống hiển thị: “Ứng viên với email này đã có trong đợt tuyển dụng.” |

##### UC 8.2 – Quản lý lịch phỏng vấn & dạy thử

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý xếp lịch phỏng vấn cho ứng viên đạt sơ tuyển và xếp lịch dạy thử (Demo) cho ứng viên giáo viên Full-time đã đạt phỏng vấn, chỉ định người đánh giá và gửi thông báo. |
| **Kích hoạt** | Quản lý nhấn “Xếp lịch phỏng vấn” tại ứng viên SCREENING, hoặc “Xếp lịch Demo” tại ứng viên TEACHING_TRIAL. |
| **Tiền điều kiện** | • Quản lý đã đăng nhập.<br>• Phỏng vấn: ứng viên có status = SCREENING. Demo: ứng viên có status = TEACHING_TRIAL. |
| **Hậu điều kiện** | • Bản ghi recruitment_rounds được tạo (status = SCHEDULED, result = PENDING).<br>• Người đánh giá nhận thông báo; ứng viên nhận email thông báo lịch. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý chọn ứng viên SCREENING và nhấn “Xếp lịch phỏng vấn”. | 2. Hệ thống hiển thị form: Ngày giờ, Địa điểm hoặc link online, Người phỏng vấn (chỉ các tài khoản có vai trò MANAGER). |
| 3. Quản lý nhập thông tin và nhấn “Xác nhận”. | 4. Hệ thống kiểm tra thời gian sau hiện tại và người phỏng vấn không có vòng tuyển dụng khác trong khoảng 60 phút quanh giờ đó.<br>5. Hệ thống tạo recruitment_rounds (round_type = INTERVIEW), cập nhật candidate.status = INTERVIEWING, gửi thông báo cho người phỏng vấn và email cho ứng viên. |
| 6. Với ứng viên TEACHING_TRIAL, Quản lý nhấn “Xếp lịch Demo”, nhập ngày giờ, lớp/phòng demo, người giám sát. | 7. Hệ thống kiểm tra như Bước 4, tạo recruitment_rounds (round_type = DEMO), gửi thông báo cho người giám sát và email cho ứng viên. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 3.1. Quản lý sửa lịch của một vòng đang SCHEDULED. | 3.1.1. Hệ thống kiểm tra lại như Bước 4, cập nhật và gửi lại thông báo, email. |
| 3.2. Quản lý hủy một vòng đang SCHEDULED. | 3.2.1. Hệ thống cập nhật status = CANCELLED; phỏng vấn bị hủy thì ứng viên quay về SCREENING, Demo bị hủy thì ứng viên giữ TEACHING_TRIAL để xếp lại. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.3: (Từ bước 4) Người phỏng vấn đã có lịch trong khung giờ đó. | 3.3.1: Hệ thống hiển thị: “Người phỏng vấn đã có lịch vào thời gian này.” |
| 3.4: (Từ bước 4) Thời gian chọn ở quá khứ. | 3.4.1: Hệ thống hiển thị: “Thời gian phải sau thời điểm hiện tại.” |

##### UC 8.3 – Đánh giá kết quả & chuyển Onboarding

| | |
|---|---|
| **Actor** | Quản lý |
| **Ưu tiên** | High |
| **Mô tả** | Use case cho phép Quản lý nhập điểm, nhận xét, kết quả của vòng phỏng vấn/Demo; hệ thống cập nhật trạng thái ứng viên theo quy tắc và chuyển ứng viên trúng tuyển sang Onboarding (UC 2.5). |
| **Kích hoạt** | Quản lý mở danh sách “Vòng tuyển dụng cần đánh giá”. |
| **Tiền điều kiện** | • Vòng tuyển dụng đang SCHEDULED và đã tới giờ diễn ra. |
| **Hậu điều kiện** | • recruitment_rounds chuyển COMPLETED kèm điểm, nhận xét, kết quả.<br>• candidate.status được cập nhật theo quy tắc; ứng viên PASSED có thể được chuyển sang Onboarding. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Quản lý mở “Vòng tuyển dụng cần đánh giá”. | 2. Hệ thống hiển thị các vòng SCHEDULED đã tới giờ diễn ra. |
| 3. Quản lý chọn một vòng, nhập Điểm (0–10), Nhận xét, Kết quả (Đạt/Không đạt) và nhấn “Lưu kết quả”. | 4. Hệ thống kiểm tra điểm hợp lệ; cập nhật vòng: status = COMPLETED, score, note, result.<br>5. Hệ thống cập nhật candidate.status theo quy tắc: đạt phỏng vấn và là giáo viên Full-time → TEACHING_TRIAL (chờ xếp Demo, UC 8.2); đạt phỏng vấn ở vị trí khác → PASSED; đạt Demo → PASSED; không đạt ở bất kỳ vòng nào → REJECTED. Gửi email kết quả cho ứng viên. |
| 6. Với ứng viên PASSED, Quản lý nhấn “Chuyển sang Onboarding”. | 7. Hệ thống mở form UC 2.5 với thông tin ứng viên đã điền sẵn. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 3.1. Quản lý đánh dấu ứng viên vắng mặt. | 3.1.1. Hệ thống cập nhật vòng status = CANCELLED; Quản lý có thể xếp lịch lại (UC 8.2) hoặc đánh giá Không đạt. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 3.2: (Từ bước 4) Điểm ngoài khoảng 0–10. | 3.2.1: Hệ thống hiển thị: “Điểm đánh giá phải từ 0 đến 10.” và không lưu. |
| 3.3: Vòng tuyển dụng chưa tới giờ diễn ra. | 3.3.1: Hệ thống hiển thị: “Vòng tuyển dụng chưa diễn ra.” |
| 6.1: Ứng viên đã được tiếp nhận (status = HIRED). | 6.1.1: Hệ thống không cho tạo hồ sơ lần hai và hiển thị liên kết tới hồ sơ nhân sự hiện có. |

#### Phân hệ UC9: Bảng điều khiển & Tác vụ hệ thống

##### UC 9.1 – Xem Dashboard theo vai trò

| | |
|---|---|
| **Actor** | Super Admin, Quản lý, Kế toán, Nhân viên |
| **Ưu tiên** | High |
| **Mô tả** | Use case cung cấp màn hình tổng quan với các thẻ số liệu, bảng nhỏ và danh sách việc cần xử lý, hiển thị riêng theo vai trò người dùng. Mỗi thẻ có liên kết tới trang xử lý tương ứng. |
| **Kích hoạt** | Người dùng đăng nhập thành công hoặc nhấn “Dashboard” trên menu. |
| **Tiền điều kiện** | • Người dùng đã đăng nhập. |
| **Hậu điều kiện** | • Dashboard hiển thị đúng các chỉ số thuộc phạm vi quyền. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Người dùng mở Dashboard. | 2. Hệ thống xác định vai trò và hiển thị:<br>• Super Admin: số tài khoản theo vai trò và trạng thái; 10 dòng nhật ký hoạt động mới nhất; số lần đăng nhập thất bại trong 7 ngày; số đơn nghỉ, giải trình, giấy tờ của Quản lý đang chờ duyệt; nút “Chạy tác vụ hằng ngày” (UC 9.2).<br>• Quản lý: tổng số nhân sự, tỉ lệ Full-time/Part-time; số giấy tờ, đơn nghỉ, giải trình chờ duyệt; số hợp đồng và giấy tờ sắp hết hạn trong 30 ngày; số buổi dạy cần người thay; số lớp đang diễn ra và số ca làm việc hôm nay.<br>• Kế toán: tổng thu nhập, tổng thực nhận, tổng thuế của bảng lương gần nhất; trạng thái bảng lương (DRAFT/LOCKED/SENT); tóm tắt chấm công tháng hiện tại.<br>• Nhân viên: lịch dạy/ca làm việc tuần này; trạng thái chấm công hôm nay; số ngày phép năm còn lại (Full-time); các thông báo chưa đọc. |
| 3. Người dùng nhấn vào một thẻ (ví dụ “3 đơn nghỉ chờ duyệt”). | 4. Hệ thống chuyển tới trang nghiệp vụ tương ứng. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Super Admin nhấn “Chạy tác vụ hằng ngày”. | 1.1.1. Hệ thống thực hiện UC 9.2 và hiển thị kết quả. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.2: Chưa có số liệu cho kỳ hiện tại. | 1.2.1: Thẻ hiển thị số 0 hoặc thông báo “Chưa có dữ liệu phát sinh”, giao diện không bị lỗi. |
| 1.3: Tài khoản không phải Super Admin nhưng chưa có hồ sơ nhân sự. | 1.3.1: Hệ thống hiển thị: “Tài khoản chưa có hồ sơ nhân sự. Vui lòng liên hệ Quản trị viên.” |

##### UC 9.2 – Chạy tác vụ tự động hằng ngày

| | |
|---|---|
| **Actor** | Hệ thống (lịch tự động), Super Admin |
| **Ưu tiên** | High |
| **Mô tả** | Use case mô tả các xử lý hệ thống tự thực hiện mỗi ngày một lần: nhắc hạn giấy tờ, hợp đồng; ghi nhận vắng mặt, thiếu check-out; cập nhật trạng thái buổi dạy, lớp học; tạo quỹ phép năm. Chạy theo lịch tự động của máy chủ hoặc khi Super Admin nhấn nút. |
| **Kích hoạt** | Đến 06:00 mỗi ngày theo lịch chạy của máy chủ, hoặc Super Admin nhấn “Chạy tác vụ hằng ngày”. |
| **Tiền điều kiện** | • Hệ thống đang hoạt động. |
| **Hậu điều kiện** | • Các trạng thái được cập nhật, thông báo được gửi; nhật ký RUN_DAILY_JOB được ghi kèm số bản ghi đã xử lý. |

**Luồng chính (Basic Flow)**

| Actor Action | System Response |
|---|---|
| 1. Đến giờ chạy theo lịch, hoặc Super Admin nhấn nút. | 2. Giấy tờ: chuyển giấy tờ APPROVED có expiry_date trước hôm nay sang EXPIRED; gửi nhắc cho nhân sự và Quản lý với giấy tờ còn đúng 30 ngày, 7 ngày hoặc hết hạn hôm nay.<br>3. Hợp đồng: gửi thông báo cho Quản lý với hợp đồng ACTIVE còn đúng 30 ngày, 7 ngày hoặc vừa quá ngày kết thúc (hệ thống không tự đổi trạng thái hợp đồng).<br>4. Chấm công của ngày hôm qua: người có lịch làm việc nhưng không có bản ghi chấm công và không có đơn nghỉ cả ngày đã duyệt → tạo attendance với attendance_status = ABSENT; bản ghi có check-in nhưng không có check-out → attendance_status = MISSING_CHECKOUT; gửi thông báo để nhân sự giải trình (UC 4.2).<br>5. Lịch học: buổi dạy SCHEDULED có ngày trước hôm nay → COMPLETED; buổi đã qua mà còn yêu cầu dạy thay SEARCHING → yêu cầu FAILED, buổi CANCELLED; lớp UPCOMING đến ngày bắt đầu → ACTIVE; lớp ACTIVE quá ngày kết thúc → COMPLETED.<br>6. Quỹ phép: tạo leave_balances (12 ngày) cho nhân sự Full-time ACTIVE chưa có quỹ phép của năm hiện tại.<br>7. Hệ thống ghi nhật ký RUN_DAILY_JOB và (nếu Super Admin chạy) hiển thị số bản ghi đã xử lý ở từng bước. |

**Luồng thay thế (Alternative Flow)**

| Actor Action | System Response |
|---|---|
| 1.1. Tác vụ được chạy lần thứ hai trong cùng ngày. | 1.1.1. Mỗi bước chỉ xử lý dữ liệu chưa được xử lý; hệ thống không tạo bản ghi hay thông báo trùng lặp. |

**Luồng ngoại lệ (Exception Flow)**

| Actor Action | System Response |
|---|---|
| 1.2: Một bước gặp lỗi khi chạy. | 1.2.1: Hệ thống ghi nhật ký lỗi của bước đó, các bước còn lại vẫn chạy; Super Admin nhận thông báo “Tác vụ hằng ngày: bước [tên bước] gặp lỗi.” |


---

## 11. Thứ tự làm (Phase)

**Ý tưởng:** dựng **toàn bộ cơ sở dữ liệu trước** (P1), sau đó làm chức năng **từng app một**. Vì mọi bảng đã có từ đầu nên app nào cũng tham chiếu được app khác, không phải chờ đợi hay sửa migration về sau.

Trong mỗi Phase chức năng: **services → forms → views + templates → tests → GIAI_THICH.md**.

| Phase | App làm chính | UC | Ghi chú |
|---|---|---|---|
| P0 | `core` + khung 10 app | – | Khởi tạo dự án |
| P1 | cả 10 app (chỉ `models.py`, `admin.py`) | – | Dựng đủ 20 bảng + dữ liệu mẫu |
| P2 | `accounts` | 1.1–1.6 | |
| P3 | `recruitment` | 8.1–8.3 | Nút "Chuyển sang Onboarding" trỏ tới trang của P4 |
| P4 | `employees` | 2.1–2.6 | Viết thêm `leave.tao_quy_phep`, `recruitment.danh_dau_da_tuyen` |
| P5 | `contracts` | 3.1–3.5 | Viết thêm `schedule.giai_phong_lich_tuong_lai`, `schedule.tao_yeu_cau_day_thay`, `payroll.dong_cau_hinh_luong` |
| P6 | `schedule` | 6.1–6.3 | |
| P7 | `leave` + `schedule` | 5.1–5.4, 6.4 | 6.4 làm cùng vì yêu cầu dạy thay phát sinh từ 5.2. Viết `payroll.thang_da_chot` |
| P8 | `attendance` | 4.1–4.5 | |
| P9 | `payroll` | 7.1–7.3 | |
| P10 | `dashboard` | 9.1, 9.2 | |
| P11 | toàn bộ | – | Kiểm thử tổng, chuẩn bị bảo vệ |

> Khi một Phase cần "viết thêm" hàm ở app khác (cột Ghi chú), hàm đó đặt trong `services.py` của **app sở hữu bảng**, đúng quy tắc §3.2, kèm test trong `tests.py` của app đó.

### P0 — Khởi tạo dự án

- **Tạo dự án và app:** dự án `config`; 10 app: `core`, `accounts`, `recruitment`, `employees`, `contracts`, `schedule`, `leave`, `attendance`, `payroll`, `dashboard`. Khai báo cả 10 trong `INSTALLED_APPS`.
- **`settings.py`:** `LANGUAGE_CODE = 'vi'`, `TIME_ZONE = 'Asia/Ho_Chi_Minh'`, `USE_TZ = False` (một múi giờ, đơn giản), `AUTH_USER_MODEL = 'accounts.User'`, email ra console, `LOGIN_URL`, `MEDIA_ROOT`, tham số §6.
- **`core/`:**
  - `base.html`: Bootstrap CDN, menu trái theo vai trò (mỗi mục menu trỏ tới một app), chuông thông báo qua context processor.
  - Các hàm dùng chung: `role_required`, `co_quyen_duyet`, `tao_thong_bao`, `ghi_nhat_ky`, `thong_bao.py`.
  - View `tai_file` có kiểm tra quyền; trang 403; danh sách thông báo (đánh dấu đã đọc).
- **Xong khi:** `python manage.py runserver` chạy được, mở trang chủ thấy khung giao diện.

### P1 — Dựng toàn bộ cơ sở dữ liệu

- **Viết `models.py` của cả 10 app** đúng §7.3: tên bảng (`db_table`), trường, kiểu, `on_delete`, `default`, Enum, `Meta.constraints`. Khóa ngoại sang app khác viết bằng chuỗi (§3.2).
- **`accounts.User`** viết đầu tiên, cùng `UserManager` (§7.1). Chạy `makemigrations` + `migrate` một lần cho cả dự án.
- **`admin.py`:** đăng ký mọi bảng để xem dữ liệu.
- **Lệnh `tao_du_lieu_mau`** (đặt ở `core/management/commands/`, chạy lại không nhân đôi):
  - Tài khoản: 1 SA, 2 QL, 1 KT.
  - Khoảng 40 nhân sự: GV Full-time Ca 1 và Ca 2, trợ giảng Part-time, Staff Part-time; mỗi người có hợp đồng ACTIVE, cấu hình lương, quỹ phép (Full-time).
  - Một đợt tuyển dụng với vài ứng viên, 20 lớp kèm buổi dạy, vài khung ca, chấm công một tháng.
  - Mật khẩu demo đặt bằng `set_password` trong lệnh này.
- **Test P1:** mỗi `UniqueConstraint`/`CheckConstraint` có một test chứng minh dữ liệu sai bị chặn (ví dụ: tạo hợp đồng ACTIVE thứ hai cho cùng một người phải lỗi).
- **Xong khi:** migration sạch; trang admin xem được đủ 20 bảng với dữ liệu mẫu.

### P2 — `accounts` (UC 1)

- **1.1 Đăng nhập:** tự viết view để phân biệt "sai thông tin" (3.2) với "bị khóa" (3.3); ghi `LOGIN` / `LOGIN_FAILED`.
- **1.2 Quên mật khẩu:** link tạo bằng `default_token_generator` + `urlsafe_base64_encode`; trang đặt mật khẩu dùng `PasswordResetConfirmView` có sẵn. Hàm `gui_link_dat_mat_khau` dùng chung cho 1.5 và 2.5.
- **1.4 Tài khoản cá nhân:** form chỉ nhận Họ tên, SĐT, Avatar; nếu có hồ sơ thì gọi `employees.dong_bo_ho_ten_sdt`.
- **1.5 Quản lý tài khoản (SA):** chặn tự khóa, tự đổi quyền; viết `khoa_tai_khoan` (dùng lại ở 3.4).
- **1.6 Đăng xuất:** dùng POST.

### P3 — `recruitment` (UC 8)

- **Quy tắc trạng thái ứng viên** theo UC 8.3 bước 5. Demo chỉ cho ứng viên `position = TEACHER` và `employment_type = FULL_TIME`.
- **Người phỏng vấn:** chỉ tài khoản role MANAGER; kiểm tra trùng 60 phút. Ở Phase này kiểm tra trùng giữa các vòng tuyển dụng với nhau; P6 bổ sung trùng với buổi dạy qua `kiem_tra_trung_lich`.
- **Email cho ứng viên:** dùng `send_mail` (ra console khi demo).
- **Viết `danh_dau_da_tuyen(ung_vien)`** để P4 gọi.

### P4 — `employees` (UC 2)

- **2.5 Onboarding:**
  - Form có trường Ca làm việc, bắt buộc với Full-time, để trống với Part-time.
  - Một transaction gọi `accounts` (tạo user), tạo employees, gọi `leave.tao_quy_phep` (Full-time) và `recruitment.danh_dau_da_tuyen`.
  - Gửi link đặt mật khẩu; báo SA nếu vị trí là QL/KT.
- **2.2 Cập nhật hồ sơ:** thông tin thường lưu ngay; giấy tờ → PENDING; luồng 1.1 "Tải bản mới".
- **2.6 Duyệt giấy tờ:** dùng `co_quyen_duyet`.
- **Viết `dong_bo_ho_ten_sdt`** (dùng ở 1.4) và các hàm đổi trạng thái nhân sự để `contracts` gọi.

### P5 — `contracts` (UC 3)

- **3.1 Thêm hợp đồng:** gọi employees để đồng bộ `employment_type`, chuyển ONBOARDING → ACTIVE.
- **3.3 Gia hạn:** HĐ cũ EXPIRED, HĐ mới ACTIVE với `previous_contract`.
- **3.4 Thanh lý:** điều phối đủ bước 5–6 bằng cách gọi employees, accounts, schedule, payroll (§3.2). Viết luôn các hàm `schedule.giai_phong_lich_tuong_lai`, `schedule.tao_yeu_cau_day_thay`, `payroll.dong_cau_hinh_luong` vì bảng đã có từ P1.
- **3.5 Hợp đồng sắp hết hạn:** ba nhóm thời gian.

### P6 — `schedule` (UC 6.1–6.3)

- **Sinh buổi dạy:** duyệt từng ngày từ `start_date` đến `end_date`; ngày nào có `weekday()` nằm trong `weekdays` thì tạo một buổi, với `actual_* = planned_*`.
- **`kiem_tra_trung_lich`, `goi_y_giao_vien`** theo §9.2 (gợi ý chỉ GV có ca bao trọn giờ học).
- **Giữ chỗ ca:** cập nhật có điều kiện như §9.2.
- **Lịch 6.2:** bảng tuần 7 cột và chế độ ngày; GV ghi `lesson_note`.

### P7 — `leave` (UC 5) + dạy thay (UC 6.4 trong `schedule`)

- **`tinh_so_ngay_nghi`** theo §9.2; quỹ phép kiểm tra ở cả lúc gửi (5.1) và lúc duyệt (5.2).
- **5.2 Duyệt đơn:** dùng `co_quyen_duyet`; gọi `schedule.tao_yeu_cau_day_thay` cho các buổi bị ảnh hưởng.
- **6.4 Xử lý dạy thay:** màn hình trong `schedule`: chốt người thay, hủy buổi, thêm buổi bù, đổi trợ giảng.
- **Viết `payroll.thang_da_chot`** để chặn đơn nghỉ thuộc tháng đã chốt lương.

### P8 — `attendance` (UC 4)

- **`lich_du_kien`, `tinh_ngay_cong`, `tinh_gio_cong`** theo §9.2 (đọc employees, schedule, leave).
- **Check-in/out, giải trình, duyệt giải trình** (dùng `co_quyen_duyet`), lịch sử cá nhân, bảng tổng hợp công.
- **Khóa theo tháng đã chốt:** gọi `payroll.thang_da_chot`.

### P9 — `payroll` (UC 7)

- **Công thức** theo §9.2; số liệu công lấy từ `attendance.tinh_ngay_cong` / `tinh_gio_cong`.
- **Kiểm tra trước khi khởi tạo:** tháng đã kết thúc, chưa có bảng lương, không còn giải trình PENDING, đủ cấu hình lương.
- **Kiểm tra trước khi chốt:** không có `net_pay` âm.
- **Phiếu lương:** template có CSS `@media print`.

### P10 — `dashboard` (UC 9)

- **9.1 Dashboard:** mỗi thẻ có link tới trang xử lý của app tương ứng; chưa có dữ liệu thì hiện 0.
- **9.2 `chay_tac_vu_ngay(hom_nay)`:** đủ bước 2–6; mỗi bước gọi service của app sở hữu bảng (employees, contracts chỉ nhắc, schedule, attendance, leave), bọc try/except riêng. Lệnh `dashboard/management/commands/chay_tac_vu_ngay.py` và nút của SA gọi cùng một hàm.

### P11 — Hoàn thiện

- Chạy toàn bộ test; chạy kịch bản demo §12.3; rà `GIAI_THICH.md` đủ 38 UC.

---

## 12. Kiểm thử & kịch bản demo

### 12.1 Quy ước

- **Công cụ:** chỉ dùng `django.test.TestCase`, chạy `python manage.py test` (hoặc từng app: `python manage.py test leave`).
- **Test đặt trong `tests.py` của app chứa UC** (UC 5.x trong `leave/tests.py`, UC 6.4 trong `schedule/tests.py`).
- **Tên test bám mã luồng ở §10:**
  - `test_uc<x>_<y>_basic` cho luồng chính.
  - `test_uc<x>_<y>_alt_<mã>` cho luồng thay thế.
  - `test_uc<x>_<y>_exc_<mã>` cho luồng ngoại lệ.
  - Ví dụ: `test_uc1_1_exc_3_3_tai_khoan_bi_khoa`, `test_uc6_3_exc_5_3_ca_da_du_nguoi`.
- **Test thông báo:** kiểm tra câu hiển thị đúng như §10.
- **Test phân quyền:** mỗi dòng của bảng phân quyền §5 có ít nhất một test "được phép" và một test "bị chặn".
- **Test tính toán** (`tinh_ngay_cong`, `tinh_gio_cong`, lương): so với số tính tay trong comment của test.

### 12.2 Ma trận truy vết

| UC | App (tests.py) | Luồng cần test | Kiểm tra thêm | Phase |
|---|---|---|---|---|
| 1.1 | `accounts` | basic · alt 1.1 · exc 3.1, 3.2, 3.3 |  | P2 ✅ |
| 1.2 | `accounts` | basic · alt 3.1 · exc 3.2, 6.1, 6.2 |  | P2 ✅ |
| 1.3 | `accounts` | basic · exc 3.1, 3.2, 3.3 |  | P2 ✅ |
| 1.4 | `accounts` | basic · exc 3.1, 3.2 |  | P2 ✅ |
| 1.5 | `accounts` | basic · alt 3.1, 3.2 · exc 3.3, 5.1, 1.1 |  | P2 ✅ |
| 1.6 | `accounts` | basic · exc 1.1 |  | P2 ✅ |
| 2.1 | `employees` | basic · exc 3.1, 5.1 |  | P4 ✅ |
| 2.2 | `employees` | basic · alt 1.1 · exc 3.1, 3.2, 3.3 |  | P4 ✅ |
| 2.3 | `employees` | basic · exc 4.1, 1.1 |  | P4 ✅ |
| 2.4 | `employees` | basic · exc 1.1 |  | P4 ✅ |
| 2.5 | `employees` | basic · alt 1.1, 3.1 · exc 3.2, 3.3, 1.2 | QL không tạo được role khác EMPLOYEE; Full-time thiếu ca làm việc → lỗi; một ứng viên chỉ một hồ sơ | P4 ✅ |
| 2.6 | `employees` | basic · alt 5.1 · exc 5.2, 3.1 | Phân cấp duyệt Q2; không tự duyệt | P4 ✅ |
| 3.1 | `contracts` | basic · exc 5.1, 5.2, 5.3 |  | P5 ✅ |
| 3.2 | `contracts` | basic · exc 1.1 |  | P5 ✅ |
| 3.3 | `contracts` | basic · alt 1.1 · exc 3.1, 3.2 |  | P5 ✅ |
| 3.4 | `contracts` | basic · exc 3.1, 3.2 | Đủ bước 5–6: lớp, buổi dạy, ca làm, cấu hình lương, khóa tài khoản | P5 ✅ |
| 3.5 | `contracts` | basic · exc 1.1 |  | P5 ✅ |
| 4.1 | `attendance` | basic · alt 1.1, 6.1 · exc 1.2, 3.1, 6.2 | Ca 1 và Ca 2; nghỉ nửa ca; Part-time nhiều ca/ngày; trợ giảng theo buổi | P8 ✅ |
| 4.2 | `attendance` | basic · exc 3.1, 1.1, 1.2 |  | P8 ✅ |
| 4.3 | `attendance` | basic · exc 4.1 |  | P8 ✅ |
| 4.4 | `attendance` | basic · alt 5.1 · exc 5.2, 5.3 | Phân cấp duyệt Q2; không tự duyệt | P8 ✅ |
| 4.5 | `attendance` | basic · exc 3.1 | Số liệu khớp tinh_ngay_cong / tinh_gio_cong | P8 ✅ |
| 5.1 | `leave` | basic · alt 1.1 · exc 3.1, 3.2, 3.3, 3.4, 3.5 | total_days đúng (bỏ Chủ nhật, nửa ngày = 0,5) | P7 ✅ |
| 5.2 | `leave` | basic · alt 5.1 · exc 5.2, 5.3, 3.1 | Phân cấp duyệt Q2; nghỉ nửa ca chỉ ảnh hưởng đúng buổi | P7 ✅ |
| 5.3 | `leave` | basic · exc 1.1 |  | P7 ✅ |
| 5.4 | `leave` | basic · exc 3.1 |  | P7 ✅ |
| 6.1 | `schedule` | basic · alt 1.1 · exc 3.1, 3.2, 3.3, 6.1 | Sinh đúng số buổi; chỉ gợi ý GV có ca bao trọn giờ học | P6 ✅ |
| 6.2 | `schedule` | basic · alt 5.1 · exc 3.1, 1.1 |  | P6 ✅ |
| 6.3 | `schedule` | basic · alt 5.1, 8.1 · exc 5.2, 5.3, 5.4, 8.2 | Hai người cùng giữ chỗ cuối cùng: chỉ một người được | P6 ✅ |
| 6.4 | `schedule` | basic · alt 5.1, 5.2, 1.1 · exc 5.3 |  | P7 ✅ |
| 7.1 | `payroll` | basic · alt 1.1 · exc 5.1, 5.2, 5.3 |  | P9 ✅ |
| 7.2 | `payroll` | basic · alt 8.1, 8.2 · exc 3.1, 3.2, 3.3, 3.4, 10.1 | FT, GV FT, QL, PT so với số tính tay; tính lại giữ dòng thủ công | P9 ✅ |
| 7.3 | `payroll` | basic · exc 1.1, 3.1 |  | P9 ✅ |
| 8.1 | `recruitment` | basic · alt 1.1, 5.1 · exc 3.1, 3.2, 3.3 |  | P3 ✅ |
| 8.2 | `recruitment` | basic · alt 3.1, 3.2 · exc 3.3, 3.4 |  | P3 ✅ |
| 8.3 | `recruitment` | basic · alt 3.1 · exc 3.2, 3.3, 6.1 |  | P3 ✅ |
| 9.1 | `dashboard` | basic · alt 1.1 · exc 1.2, 1.3 |  | P10 ✅ |
| 9.2 | `dashboard` | basic · alt 1.1 · exc 1.2 | Chạy 2 lần trong ngày không tạo dữ liệu trùng | P10 ✅ |

### 12.3 Kịch bản demo khi bảo vệ

1. **Tuyển dụng:** QL tạo đợt, thêm ứng viên GV Full-time, sơ tuyển đạt, phỏng vấn đạt (TEACHING_TRIAL), Demo đạt (PASSED).
2. **Onboarding:** "Chuyển sang Onboarding", tạo hồ sơ với Ca 2; link đặt mật khẩu hiện ở terminal. GV đặt mật khẩu, tải chứng chỉ; QL duyệt; QL tạo hợp đồng, GV chuyển ACTIVE.
3. **Phân công:** QL tạo lớp T2-T4-T6 18:00–20:00; hệ thống chỉ gợi ý GV Ca 2 và sinh buổi. QL mở khung ca Lễ tân 2 chỗ; ba NV Part-time cùng giữ chỗ, người thứ ba nhận "Ca này đã đủ người"; QL chốt.
4. **Vận hành:** GV check-in trễ, gửi giải trình, QL chấp thuận. GV xin nghỉ một ngày có lớp; QL duyệt, hệ thống tạo yêu cầu dạy thay; QL chốt người thay. QL xin nghỉ, **SA** duyệt. SA bấm "Chạy tác vụ hằng ngày" và xem kết quả.
5. **Lương:** KT cấu hình lương, lập bảng lương tháng, thêm thưởng, tính lại, chốt, phát hành; GV mở phiếu lương và bấm In / Lưu PDF.
6. **Kết thúc:** QL thanh lý hợp đồng một nhân sự. Tài khoản bị khóa, buổi dạy tương lai hiện trong "Buổi dạy cần người thay".

---

## 13. Hoàn thành khi

- 10 app đúng §3.1; 20 bảng khớp §7 và nằm đúng app; migration chạy sạch trên SQLite.
- Không app nào ghi trực tiếp vào bảng của app khác (rà theo §3.2).
- Toàn bộ dòng ở §12.2 có test chạy qua; kịch bản §12.3 chạy trọn vẹn trên dữ liệu mẫu.
- Không có thư viện nào ngoài Django; Bootstrap chỉ nhúng qua CDN.
- `docs/GIAI_THICH.md` có đủ 38 UC, mỗi UC trả lời được: màn hình nào → bảng nào thay đổi → trạng thái chuyển thế nào → hàm service nào thực hiện.
