# Cloud-Based Student Task Manager

Website quản lý bài tập và thời hạn nộp bài của sinh viên, viết bằng **Python (Flask)**, lưu dữ liệu trên **Cloud Database (PostgreSQL)**, giao diện responsive dùng được trên điện thoại và máy tính.

## Chức năng
- Đăng ký, đăng nhập và đăng xuất bằng email/mật khẩu
- Ghi nhớ phiên đăng nhập và tách danh sách bài tập theo tài khoản
- Dashboard học tập cá nhân với thống kê bài tập, tỷ lệ hoàn thành, biểu đồ hạn nộp 7 ngày và số bài hoàn thành trong 8 tuần gần nhất
- Chuyển đổi giao diện sáng/tối, lưu lựa chọn trên trình duyệt
- Dashboard admin với biểu đồ tình trạng bài tập, phân bố bài tập theo tài khoản, thống kê, danh sách người dùng và bài tập toàn hệ thống
- Thêm, sửa, xóa bài tập
- Đánh dấu đã hoàn thành / bỏ đánh dấu
- Cảnh báo quá hạn, sắp đến hạn
- Lọc: Tất cả / Chưa xong / Đã xong
- Tìm kiếm bài tập theo tiêu đề, môn học hoặc mô tả; hỗ trợ tiếng Việt và kết hợp với bộ lọc trạng thái
- Lưu dữ liệu trên Cloud Database
- Responsive (điện thoại + máy tính)

## Kiến trúc
```
Trình duyệt (điện thoại / PC)
        │  HTTPS
        ▼
Flask app (gunicorn) ── deploy trên Cloud PaaS (Render)
        │  SQLAlchemy (DATABASE_URL)
        ▼
PostgreSQL trên Cloud (Neon / Supabase / Render Postgres)
```

## Chạy thử ở máy local

### Windows (PowerShell)

Mở PowerShell, chạy các lệnh sau. Dùng cùng Python trong `.venv` để cài thư viện và khởi động ứng dụng:

```powershell
cd "D:\Project Điện toán đám mây\student-task-manager"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nếu lệnh `py` không có trên máy, thay `py -m venv .venv` bằng `python -m venv .venv`.
Mở http://127.0.0.1:5000. Nếu cổng 5000 đang được sử dụng, đặt biến `PORT` sang cổng khác trước khi chạy.

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Nếu chưa đặt `DATABASE_URL`, app dùng SQLite (`tasks.db`) để chạy thử.

Lần đầu mở phiên bản có đăng nhập, ứng dụng tự bổ sung các cột tài khoản và thời điểm hoàn thành cho bảng bài tập hiện có. Các bài tập cũ sẽ được chuyển cho tài khoản đầu tiên đăng ký; những tài khoản đăng ký sau có danh sách riêng. Thời điểm hoàn thành mới được ghi nhận khi đánh dấu hoàn thành sau khi cập nhật, nên dữ liệu hoàn thành cũ không được tự gán ngày giả trong biểu đồ tuần. Mật khẩu được lưu dưới dạng băm, không lưu văn bản thuần.

Đăng nhập Google/Facebook và gửi email đặt lại mật khẩu cần cấu hình OAuth/SMTP riêng nên hiện chưa được bật. Trang quên mật khẩu hướng dẫn liên hệ quản trị viên.

### Cấp quyền admin

1. Đăng ký tài khoản trong ứng dụng trước.
2. Mở PowerShell tại thư mục dự án và chạy:
   ```powershell
   .\.venv\Scripts\python.exe -m flask --app app make-admin email@example.com
   ```
   Thay `email@example.com` bằng email đã đăng ký. Nếu Python không nằm trong `.venv`, dùng `python -m flask --app app make-admin email@example.com`.
3. Khởi động ứng dụng và đăng nhập tài khoản đó. Nút **Admin** sẽ xuất hiện trên thanh điều hướng.

Dashboard chỉ đọc số liệu, tối đa 10 tài khoản và 10 bài tập mới nhất. Tài khoản không có quyền admin bị từ chối truy cập `/admin`.

## Kết nối Cloud Database
1. Tạo database PostgreSQL miễn phí trên Neon (neon.tech) hoặc Supabase.
2. Copy connection string, ví dụ `postgresql://user:pass@host/dbname`.
3. Đặt biến môi trường:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host/dbname"
   export SECRET_KEY="chuoi-bi-mat"
   python app.py
   ```
Bảng `user` và `task` được tạo tự động ở lần chạy đầu tiên.

## Deploy lên cloud (ví dụ Render)
1. Đẩy code lên GitHub.
2. Trên Render: **New → Web Service** → chọn repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Thêm Environment Variables: `DATABASE_URL`, `SECRET_KEY`.
6. Deploy xong sẽ có URL HTTPS để truy cập từ điện thoại.

## Cấu trúc thư mục
```
student-task-manager/
├── app.py
├── requirements.txt
├── Procfile
├── .env.example
├── templates/   (base.html, auth_base.html, login.html, register.html, ...)
└── static/      (style.css, auth.css)
```

## Gợi ý mở rộng (để lấy điểm cao)
- Tích hợp đăng nhập Google/Facebook bằng OAuth
- Gửi email đặt lại mật khẩu và nhắc hạn nộp
- Docker hóa + CI/CD với GitHub Actions
- API REST (`/api/tasks`) để làm app mobile
