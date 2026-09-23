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
├── .github/workflows/
│   └── deploy.yml                 # Tự động deploy lên VPS qua GitHub Actions
├── extension-auth-helper/         # Extension Google Chrome (Manifest V3)
│   ├── background.js              # Service worker xử lý lệnh đăng bài, upload, seeding
│   ├── manifest.json              # Khai báo extension
│   ├── popup.html / popup.js      # Giao diện popup extension
│   └── options.html / options.js  # Cài đặt cấu hình extension
├── server.py                      # Backend server Python (chạy trên port 9999)
├── autopostfb.service             # File cấu hình chạy ngầm 24/7 trên Linux VPS (systemd)
├── deploy.sh                      # Shell script cập nhật và restart server trên VPS
├── Dockerfile                     # Cấu hình đóng gói container Docker
├── docker-compose.yml             # Cấu hình chạy dịch vụ với Docker Compose
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

## 🚢 Hướng Dẫn Tự Động Deploy Lên VPS (CI/CD)

Mỗi khi bạn `git push origin main`, GitHub Actions sẽ tự động SSH vào VPS, kéo code mới và restart server.

### 1. Cấu hình Secrets trên GitHub
Vào GitHub Repository: **Settings** ➔ **Secrets and variables** ➔ **Actions** ➔ **New repository secret**, thêm:
* `VPS_HOST`: Địa chỉ IP của VPS (ví dụ: `103.x.x.x`).
* `VPS_USERNAME`: Tên người dùng VPS (thường là `root` hoặc `ubuntu`).
* `VPS_SSH_KEY`: Private SSH Key của bạn (hoặc tạo biến `VPS_PASSWORD` nếu dùng mật khẩu).
* `VPS_PORT`: Cổng SSH (mặc định là `22`).

### 2. Thiết lập trên VPS lần đầu tiên
Truy cập vào VPS qua SSH và clone dự án về thư mục `/var/www/autopostfb`:
```bash
# Tạo thư mục và clone
sudo mkdir -p /var/www/autopostfb
sudo chown -R $USER:$USER /var/www/autopostfb
git clone https://github.com/vngoldfish/bawuiEXPRO.git /var/www/autopostfb
cd /var/www/autopostfb

# Cấp quyền chạy script deploy
chmod +x deploy.sh

# Cài đặt dịch vụ chạy ngầm 24/7 bằng Systemd:
sudo cp autopostfb.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable autopostfb
sudo systemctl start autopostfb
```

*(Hoặc nếu dùng Docker: `docker compose up -d --build`)*

Từ lúc này, bất cứ khi nào bạn `git push origin main` từ máy tính, code trên VPS sẽ **tự động cập nhật và khởi động lại ngay lập tức**!

---

## 🔌 Tài Liệu Cổng Tự Động Hóa REST API (Webhooks & Integration)

Hệ thống cung cấp chuẩn **RESTful API v1** đồng bộ trực tiếp với Chrome Extension Bridge để điều khiển đăng bài và seeding tự động từ mọi nền tảng bên ngoài (CRM, n8n, Make, Telegram Bot, Python Scripts, PHP, cURL).

> 💡 **Tài liệu API đầy đủ và chi tiết:** Xem file [API_DOCUMENTATION.md](file:///c:/Users/Admin/Desktop/project/AUTOPOSTFB/API_DOCUMENTATION.md) để tra cứu đầy đủ 9 endpoints, bảng mã lỗi HTTP, tham số chi tiết và mẫu tích hợp Webhook.

### 🔑 Xác Thực (Authentication)
* **Header chuẩn:** `Authorization: Bearer <TOKEN_DU_AN>` (Mã token dạng `BW-PROJ-XXXXXX` lấy từ thẻ dự án cha).
* **Hoặc header:** `X-Project-Token: <TOKEN_DU_AN>`.

---

### 1. Tạo / Đăng Ngay / Lên Lịch Bài Viết (`POST /api/v1/posts`)
* **Endpoint**: `POST /api/v1/posts` *(hỗ trợ alias `/api/v1/posts/publish`)*
* **Headers**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer BW-PROJ-XXXXXX`
* **Các tham số chính (JSON Body)**:
  - `content` *(string, bắt buộc nếu không có media)*: Nội dung bài viết (hỗ trợ **Spintax đa tầng** `{A|B|C}`).
  - `title` *(string, tùy chọn)*: Tiêu đề hoặc ghi chú quản lý nội bộ.
  - `postType` *(string, tùy chọn)*: `"post"` (bài viết thường), `"video"` (Facebook Video Watch), `"reel"` (Reels video ngắn), `"story"` (bản tin 24h). Mặc định: `"post"`.
  - `targetType` *(string, tùy chọn)*: `"profile"` (trang cá nhân), `"page"` (fanpage), `"group"` (nhóm). Mặc định: `"profile"`.
  - `targetId` *(string, bắt buộc nếu là page/group)*: ID Fanpage hoặc ID Nhóm Facebook.
  - `mediaUrl` *(string, tùy chọn)*: Đường dẫn URL trực tiếp của tệp ảnh/video.
  - `scheduledAt` *(string/int, tùy chọn)*: **Thời gian hẹn giờ xuất bản** (ISO 8601 ví dụ `"2026-09-24T19:30:00Z"` hoặc timestamp ms). Nếu có, bài viết tự động chuyển sang chế độ hẹn giờ.
  - `shareToFeed` / `shareToStory` *(boolean, tùy chọn)*: `true` để tự động chia sẻ lên Tin (Story 24h) hoặc Bảng tin. Mặc định: `true`.
  - `seedingComments` *(array[string], tùy chọn)*: Danh sách bình luận seeding mồi (ví dụ: `["Quan tâm", "Shop ơi tư vấn"]`).
  - `autoReactType` *(string, tùy chọn)*: Cảm xúc bài viết: `LIKE`, `LOVE`, `CARE`, `HAHA`, `WOW`, `SAD`, `ANGRY`, `NONE`. Mặc định: `LIKE`.
  - `runNow` *(boolean, tùy chọn)*: `true` để phát lệnh đăng ngay, `false` để đưa vào hàng đợi. Mặc định: `true`.
  - `callbackUrl` *(string, tùy chọn)*: Đường dẫn Webhook URL nhận thông báo khi bài hoàn thành hoặc thất bại.

#### Mẫu cURL Đăng Bài:
```bash
curl -X POST "http://localhost:9999/api/v1/posts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer BW-PROJ-XXXXXX" \
  -d '{
    "content": "{Chào bạn|Hello}! Bài viết tự động từ API với {nhiều ưu đãi|khuyến mãi khủng}.",
    "postType": "post",
    "targetType": "profile",
    "shareToStory": true,
    "seedingComments": ["Quan tâm", "Shop ở đâu vậy?"],
    "autoReactType": "LOVE",
    "runNow": true
  }'
```

#### Mẫu Python (`requests`):
```python
import requests

url = "http://localhost:9999/api/v1/posts"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer BW-PROJ-XXXXXX"
}
payload = {
    "title": "Flash Sale Khuyến Mãi",
    "content": "Nội dung bài viết {chất lượng|độc quyền} đăng từ Python API!",
    "postType": "post",
    "targetType": "profile",
    "scheduledAt": "2026-09-24T20:00:00Z",
    "shareToStory": True,
    "seedingComments": ["Tuyệt vời quá shop!", "Giá sao ạ?"],
    "autoReactType": "LOVE"
}
res = requests.post(url, json=payload, headers=headers)
print(res.json())
```

---

### 2. Danh Sách Bài Đăng & Phân Trang (`GET /api/v1/posts`)
* **Endpoint**: `GET /api/v1/posts?status=all&limit=20&offset=0`
* **Query Parameters**:
  - `status`: `"all"`, `"scheduled"`, `"pending"`, `"in_progress"`, `"completed"`, `"failed"`.
  - `postType`: `"all"`, `"post"`, `"video"`, `"reel"`, `"story"`.
  - `limit`: Số bài trên một trang (mặc định: 50).
  - `offset`: Vị trí phân trang (mặc định: 0).
* **Đặc điểm**: Danh sách luôn được tự động sắp xếp **bài viết mới nhất lên trên đầu**.

---

### 3. Kiểm Tra Chi Tiết Trạng Thái Bài Viết (`GET /api/v1/posts/{id}`)
* **Endpoint**: `GET /api/v1/posts/{postId}` *(hoặc `GET /api/v1/posts/status?postId={postId}`)*
* **Response Mẫu**:
```json
{
  "success": true,
  "postId": "post_1790192594_206a",
  "status": "completed",
  "progressStep": "✅ Đã đăng thành công lên Facebook (ID: 2151992722340672)",
  "fbPostId": "2151992722340672",
  "fbPostUrl": "https://www.facebook.com/permalink.php?story_fbid=2151992722340672&id=100025898964308",
  "shareToFeed": true,
  "shareToStorySuccess": true,
  "seedingIds": ["2151993815673896"]
}
```

---

### 4. Kích Hoạt Đăng Ngay Lập Tức (`POST /api/v1/posts/{id}/run`)
Phát lệnh cưỡng chế đăng bài ngay lập tức cho các bài đang hẹn giờ hoặc lưu nháp trong hàng đợi.

---

### 5. Cập Nhật Giờ Hẹn Đăng / Sửa Bài (`PATCH /api/v1/posts/{id}`)
* **Endpoint**: `PATCH /api/v1/posts/{postId}`
* **Body**: `{"scheduledAt": "2026-09-24T21:00:00Z", "title": "Tiêu đề mới"}`

---

### 6. Xóa Bài Viết Khỏi Hàng Đợi (`DELETE /api/v1/posts/{id}`)
* **Endpoint**: `DELETE /api/v1/posts/{postId}`

---

### 7. Bắn Seeding Vào Bài Viết Đã Đăng (`POST /api/v1/posts/seeding`)
* **Endpoint**: `POST /api/v1/posts/seeding`
```bash
curl -X POST "http://localhost:9999/api/v1/posts/seeding" \
  -H "Content-Type: application/json" \
  -d '{
    "postId": "post_1790192594_206a",
    "comments": ["Bình luận seeding 1", "Bình luận seeding 2"],
    "autoReactType": "LOVE"
  }'
```

---

### 8. Lấy Danh Sách Tài Khoản & Dự Án (`GET /api/v1/accounts`)
* **Endpoint**: `GET /api/v1/accounts`
* Trả về danh sách tất cả các tài khoản Facebook con đang LIVE, UID `c_user`, tên Facebook và mã token dự án.

---

---

## 📄 Bản Quyền & Giấy Phép
Dự án được phát triển phục vụ tự động hóa quản lý nội dung và tiếp thị số trên nền tảng Facebook.
