# 🚀 AUTOPOSTFB — Facebook Automation, Post Studio & Auto-Seeding Engine

Hệ thống tự động hóa đăng bài, lên lịch, tạo seeding và quản lý chiến dịch Facebook toàn diện thông qua kiến trúc **Python Backend Server + Chrome Extension Bridge (Manifest V3) + Direct GraphQL API**.

---

## 🌟 Tính Năng Nổi Bật

### 1. 📝 Studio Đăng Bài Đa Định Dạng (Multi-Format)
- Hỗ trợ 4 định dạng bài đăng:
  - **Bài Viết Thường (Post/Feed)**
  - **Thước Phim (Reels)**
  - **Video Bảng Tin**
  - **Bản Tin (Story)**
- Hỗ trợ 3 đích đăng tải:
  - **Trang Cá Nhân (Profile)**
  - **Fanpage** (nhập Page ID)
  - **Nhóm Facebook (Group)** (nhập Group ID)
- Soạn thảo nội dung với tính năng **Spintax `{A|B|C}` ngẫu nhiên** chống trùng lặp content kèm nút xoay thử trực tiếp.
- Kéo thả tệp Media (Ảnh &le; 10MB, Video &le; 100MB) hoặc dán liên kết URL media direct.

### 2. 💬 Tự Động Seeding Bình Luận & Thả Cảm Xúc (Auto-Seeding & Reaction)
- Tự động bóc tách **Feedback ID** ngay sau khi bài được đăng.
- Tự động bắn bình luận seeding mồi (hỗ trợ nhiều dòng, mẫu hỏi giá, khen hàng).
- Tự động thả cảm xúc bài viết: 👍 LIKE, ❤️ LOVE, 🥰 CARE, 😆 HAHA, 😮 WOW, 😢 SAD, 😡 ANGRY.
- Cửa sổ Popup Modal cho phép thêm kịch bản seeding mới cho bất kỳ bài viết nào đã tồn tại trong danh sách.

### 3. ⚡ Thực Thi Trực Tiếp Qua Facebook GraphQL & Native Media Upload
- **Upload Ảnh**: Tương thích hoàn toàn chuẩn Facebook Comet qua `upload.facebook.com`.
- **Upload Video**: Tích hợp giao thức 3 bước native `vupload-edge` (`start` ➔ `rupload` ➔ `receive`).
- **Direct GraphQL Mutation**: Sử dụng `ComposerStoryCreateMutation` (doc_id `28329575890036120`) kết hợp kỹ thuật quét động `doc_id` từ các thẻ script đang chạy trên tab Facebook để tự động thích ứng với các bản cập nhật mới của Facebook.
- **Xác thực trạng thái**: Gọi `fetchComposerPostCreationStatusQuery` (doc_id `28107101955652613`) để kiểm tra trạng thái và lấy link bài viết (`pfbid...`) ngay sau khi đăng.

### 4. 📊 Quản Lý Bài Viết & Hàng Đợi (Post Manager)
- 4 thẻ thống kê KPI: Tổng số bài, Đang chờ, Đã đăng thành công, Tổng bình luận seeding.
- Bộ lọc trạng thái (`Tất Cả`, `Đã Đăng Thành Công`, `Đang Chờ`, `Thất Bại`) và tìm kiếm thời gian thực theo từ khóa/Post ID.
- Thẻ bài viết thông minh hiển thị tiến trình thời gian thực (`progressStep`), nút mở bài trực tiếp trên Facebook, nút `Đăng Lại`, `Nhân Bản` và `Xóa`.

---

## 🏗️ Cấu Trúc Thư Mục

```text
AUTOPOSTFB/
├── extension-auth-helper/         # Extension Google Chrome (Manifest V3)
│   ├── background.js              # Service worker xử lý lệnh đăng bài, upload, seeding
│   ├── manifest.json              # Khai báo extension
│   ├── popup.html / popup.js      # Giao diện popup extension
│   └── options.html / options.js  # Cài đặt cấu hình extension
├── server.py                      # Backend server Python (chạy trên port 9999)
├── bridge_config.json             # Cấu hình kết nối giữa Server và Extension
├── projects.json                  # Dữ liệu dự án và hàng đợi bài đăng
├── projects.example.json          # File dữ liệu mẫu khởi tạo ban đầu
├── requirements.txt               # Yêu cầu môi trường Python
├── .gitignore                     # Cấu hình bỏ qua các tệp không cần thiết trên Git
├── .gitattributes                 # Chuẩn hóa line-ending và encoding
└── README.md                      # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### Bước 1: Khởi Động Server Backend
Server được tối ưu chạy hoàn toàn trên thư viện chuẩn của Python (không bắt buộc cài thêm thư viện ngoài):

```bash
# Yêu cầu: Python 3.8+
python server.py
```
> Server sẽ chạy tại địa chỉ: `http://127.0.0.1:9999/`

### Bước 2: Cài Đặt Extension Trên Chrome
1. Mở trình duyệt Chrome và truy cập: `chrome://extensions/`
2. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
3. Nhấp vào nút **Tải tiện ích đã giải nén (Load unpacked)**.
4. Chọn thư mục `extension-auth-helper` trong thư mục dự án này.
5. Mở tab Facebook (`https://www.facebook.com`) và đăng nhập sẵn tài khoản cần tự động hóa.

### Bước 3: Sử Dụng Hệ Thống
1. Mở trình duyệt truy cập: `http://127.0.0.1:9999/`
2. Chọn dự án và dự án con Facebook.
3. Soạn nội dung bài viết, đính kèm media hoặc kịch bản seeding tùy thích.
4. Nhấp **🚀 PHÁT LỆNH ĐĂNG BÀI & SEEDING NGAY** hoặc **➕ Thêm Vào Hàng Đợi**.

---

## 📌 Hướng Dẫn Đẩy Code Lên GitHub / GitLab

Để đẩy toàn bộ mã nguồn này lên kho lưu trữ Git mới:

```bash
# 1. Khởi tạo repository git (nếu chưa có)
git init

# 2. Thêm tất cả các file cần thiết
git add .

# 3. Tạo commit đầu tiên
git commit -m "feat: initial commit AUTOPOSTFB core engine, extension bridge, and studio dashboard"

# 4. Đổi tên nhánh chính thành main
git branch -M main

# 5. Liên kết tới repository từ xa của bạn (thay URL bên dưới bằng URL kho lưu trữ của bạn)
git remote add origin https://github.com/<tai-khoan>/<ten-repo>.git

# 6. Đẩy code lên Git
git push -u origin main
```

---

## 📄 Bản Quyền & Giấy Phép
Dự án được phát triển phục vụ tự động hóa quản lý nội dung và tiếp thị số trên nền tảng Facebook.
