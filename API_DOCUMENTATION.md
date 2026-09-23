# 📖 HƯỚNG DẪN TÀI LIỆU KỸ THUẬT REST API (V1)
## Nền Tảng Tự Động Hóa Đăng Bài & Seeding Facebook — BAWUI EX PRO

> **Phiên bản:** `1.0.0 (RESTful v1)`  
> **Giao thức:** `HTTP / 1.1` & `JSON`  
> **Cổng mặc định:** `9999`  
> **Base URL:** `http://localhost:9999` (hoặc `http://<IP_VPS>:9999`)  
> **Mã hóa:** `UTF-8`

---

## 📑 MỤC LỤC
1. [Kiến Trúc & Cơ Chế Hoạt Động](#1-kiến-trúc--cơ-chế-hoạt-động)
2. [Xác Thực & Bảo Mật (Authentication)](#2-xác-thực--bảo-mật-authentication)
3. [Quy Chuẩn Phản Hồi & Mã Trạng Thái HTTP](#3-quy-chuẩn-phản-hồi--mã-trạng-thái-http)
4. [Danh Sách Chi Tiết Các Endpoints](#4-danh-sách-chi-tiết-các-endpoints)
   - [4.1. Tạo / Đăng Ngay / Lên Lịch Bài Viết (`POST /api/v1/posts`)](#41-tạo--đăng-ngay--lên-lịch-bài-viết-post-apiv1posts)
   - [4.2. Lấy Danh Sách Bài Đăng & Hàng Đợi (`GET /api/v1/posts`)](#42-lấy-danh-sách-bài-đăng--hàng-đợi-get-apiv1posts)
   - [4.3. Kiểm Tra Chi Tiết Trạng Thái Bài Viết (`GET /api/v1/posts/{id}`)](#43-kiểm-tra-chi-tiết-trạng-thái-bài-viết-get-apiv1postsid)
   - [4.4. Kích Hoạt Đăng Ngay Lập Tức (`POST /api/v1/posts/{id}/run`)](#44-kích-hoạt-đăng-ngay-lập-tức-post-apiv1postsidrun)
   - [4.5. Đổi Giờ Hẹn Đăng / Hủy Hẹn Giờ (`POST /api/v1/posts/{id}/schedule`)](#45-đổi-giờ-hẹn-đăng--hủy-hẹn-giờ-post-apiv1postsidschedule)
   - [4.6. Chỉnh Sửa Bài Viết Trong Hàng Đợi (`PATCH /api/v1/posts/{id}`)](#46-chỉnh-sửa-bài-viết-trong-hàng-đợi-patch-apiv1postsid)
   - [4.7. Xóa Bài Viết Khỏi Hàng Đợi (`DELETE /api/v1/posts/{id}`)](#47-xóa-bài-viết-khỏi-hàng-đợi-delete-apiv1postsid)
   - [4.8. Bắn Seeding Vào Bài Viết Đã Đăng (`POST /api/v1/posts/seeding`)](#48-bắn-seeding-vào-bài-viết-đã-đăng-post-apiv1postsseeding)
   - [4.9. Danh Sách Tài Khoản & Dự Án (`GET /api/v1/accounts`)](#49-danh-sách-tài-khoản--dự-án-get-apiv1accounts)
5. [Cơ Chế Webhook Callbacks](#5-cơ-chế-webhook-callbacks)
6. [Hỗ Trợ Định Dạng Nội Dung (Spintax & Media)](#6-hỗ-trợ-định-dạng-nội-dung-spintax--media)
7. [Mẫu Code Tích Hợp Đa Ngôn Ngữ](#7-mẫu-code-tích-hợp-đa-ngôn-ngữ)
   - [cURL (Bash / Terminal)](#71-curl-bash--terminal)
   - [Python (`requests`)](#72-python-requests)
   - [Node.js (JavaScript / Fetch)](#73-nodejs-javascript--fetch)
   - [PHP (`cURL`)](#74-php-curl)
8. [Tích Hợp n8n / Make / Zapier](#8-tích-hợp-n8n--make--zapier)

---

## 1. Kiến Trúc & Cơ Chế Hoạt Động

Hệ thống hoạt động theo mô hình **Hybrid Architecture** kết hợp giữa Backend REST API và Chrome Extension Bridge:

```
┌─────────────────────────────────┐
│ Hệ thống bên ngoài              │
│ (CRM, n8n, Make, Bot, App, ...) │
└────────────────┬────────────────┘
                 │ HTTP REST API (Port 9999)
                 ▼
┌─────────────────────────────────────────────────────┐
│ BAWUI EX PRO Backend Server (server.py)             │
│  - Tiếp nhận Request, xác thực Project Token        │
│  - Lưu hàng đợi (postQueue), xử lý Lên lịch         │
│  - Bộ máy Post Scheduler chạy ngầm (mỗi 10s)        │
└────────────────┬────────────────────────────────────┘
                 │ Long-polling / WebSocket Bridge
                 ▼
┌─────────────────────────────────────────────────────┐
│ Chrome Extension (background.js)                    │
│  - Chạy ngầm trên trình duyệt có tài khoản FB LIVE  │
│  - Nạp cookie, dtsg, EAAG token hợp lệ              │
│  - Thực thi GraphQL / Upload Media / Đăng bài       │
│  - Tự động Reshare lên Tin (Story) nếu bật cờ       │
│  - Tự động Seeding bình luận & Thả cảm xúc          │
└────────────────┬────────────────────────────────────┘
                 │ GraphQL / Facebook Comet API
                 ▼
┌─────────────────────────────────┐
│ Nền tảng Facebook               │
│ (Profile / Fanpage / Group)     │
└─────────────────────────────────┘
```

---

## 2. Xác Thực & Bảo Mật (Authentication)

Mỗi **Dự Án Cha (Project)** trong hệ thống được cấp một chuỗi khóa bí mật duy nhất:  
`token` dạng: `BW-PROJ-XXXXXX` (Ví dụ: `BW-PROJ-A9F1B2`).

Bạn có thể truyền mã token qua 4 phương thức sau (ưu tiên theo thứ tự):

1. **Header chuẩn `Authorization`:**
   ```http
   Authorization: Bearer BW-PROJ-XXXXXX
   ```
2. **Custom Header `X-Project-Token`:**
   ```http
   X-Project-Token: BW-PROJ-XXXXXX
   ```
3. **Custom Header `X-Sync-Token`:**
   ```http
   X-Sync-Token: BW-PROJ-XXXXXX
   ```
4. **Tham số trong URL Query (GET):**
   ```http
   GET /api/v1/posts?token=BW-PROJ-XXXXXX
   ```
5. **Trường trong JSON Request Body (POST / PATCH):**
   ```json
   {
     "token": "BW-PROJ-XXXXXX"
   }
   ```

*(Lưu ý: Nếu server chỉ có duy nhất 1 dự án và bạn không truyền token, server sẽ tự động trỏ về dự án mặc định).*

---

## 3. Quy Chuẩn Phản Hồi & Mã Trạng Thái HTTP

Tất cả các endpoint đều trả về dữ liệu định dạng `application/json; charset=utf-8` theo cấu trúc Envelope chuẩn:

```json
{
  "success": true,
  "message": "Thông điệp mô tả kết quả xử lý",
  "data": { ... },
  "error": null
}
```

### Bảng Mã HTTP Trạng Thái:

| Mã HTTP | Tên Trạng Thái | Ý Nghĩa & Ngữ Cảnh Sử Dụng |
| :--- | :--- | :--- |
| **`200 OK`** | Thành Công | Xử lý yêu cầu thành công (truy vấn danh sách, kích hoạt đăng ngay, cập nhật bài, xóa bài). |
| **`201 Created`** | Đã Tạo | Tạo bài viết mới thành công (đưa vào hàng đợi hoặc đã lên lịch hẹn giờ). |
| **`400 Bad Request`** | Sai Dữ Liệu | Thiếu trường bắt buộc (`content`/`mediaUrl`), thiếu `targetId` khi đăng Fanpage/Group. |
| **`401 Unauthorized`** | Không Được Phép | Token dự án bị thiếu, sai hoặc không tồn tại. |
| **`404 Not Found`** | Không Tìm Thấy | ID bài viết, ID dự án cha hoặc ID thư mục tài khoản không tồn tại. |
| **`422 Unprocessable`**| Lỗi Logic | Thời gian hẹn giờ đăng `scheduledAt` nằm ở quá khứ hoặc định dạng không nhận diện được. |
| **`500 Server Error`** | Lỗi Hệ Thống | Lỗi ngoại lệ nội bộ trên máy chủ. |

---

## 4. Danh Sách Chi Tiết Các Endpoints

---

### 4.1. Tạo / Đăng Ngay / Lên Lịch Bài Viết (`POST /api/v1/posts`)

Tạo bài viết mới cho Facebook. Hỗ trợ 3 chế độ:
- **Đăng ngay (`runNow: true`):** Chuyển lệnh ngay sang Extension để đăng lập tức.
- **Hẹn giờ (`scheduledAt: "..."`):** Tự động chuyển vào trạng thái `scheduled` và đăng khi đến giờ.
- **Lưu nháp (`runNow: false`):** Lưu vào hàng đợi chờ duyệt.

* **Endpoint:** `POST /api/v1/posts`  
  *(Alias hỗ trợ: `POST /api/v1/posts/publish`, `POST /api/posts`)*
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <PROJECT_TOKEN>
  ```

#### Bảng Tham Số Body (JSON):

| Tên Trường | Kiểu Dữ Liệu | Bắt Buộc? | Giá Trị Mặc Định | Mô Tả Chi Tiết |
| :--- | :--- | :---: | :---: | :--- |
| `content` | `string` | **Có** (hoặc `mediaUrl`) | `""` | Nội dung bài viết. **Hỗ trợ Spintax đa tầng** dạng `{A\|B\|C}` tự động xoay nội dung chống spam. |
| `title` | `string` | Không | `""` | Tiêu đề hoặc ghi chú phân loại bài viết (dùng quản lý nội bộ). |
| `postType` | `string` | Không | `"post"` | Định dạng đăng bài:<br>• `"post"`: Bài viết thường (Feed)<br>• `"video"`: Facebook Video Watch<br>• `"reel"`: Facebook Reels (Video ngắn)<br>• `"story"`: Bản tin Story 24h |
| `targetType` | `string` | Không | `"profile"` | Vị trí đăng bài:<br>• `"profile"`: Trang cá nhân<br>• `"page"`: Fanpage<br>• `"group"`: Nhóm Facebook |
| `targetId` | `string` | **Có** (khi đăng page/group) | `""` | ID Fanpage hoặc ID Nhóm Facebook cần đăng vào. |
| `targetUrl` | `string` | Không | Facebook URL | URL tùy chọn của Fanpage/Group. |
| `mediaUrl` | `string` | Không | `""` | Đường link URL trực tiếp tải ảnh/video từ xa (hệ thống sẽ tải và chuyển base64 sang Extension). |
| `mediaData` | `object` | Không | `null` | Đối tượng đính kèm media dạng base64 trực tiếp:<br>`{"base64": "...", "fileName": "img.jpg", "mimeType": "image/jpeg"}` |
| `scheduledAt` | `string / int` | Không | `null` | **Thời gian hẹn giờ xuất bản**. Nhận ISO 8601 (`"2026-09-24T18:30:00Z"`), chuỗi datetime local (`"2026-09-24 18:30"`), hoặc epoch timestamp tính bằng mili-giây. |
| `shareToFeed` | `boolean` | Không | `true` | • Với bài viết thường: **Tự động chia sẻ lên Tin (Story)** sau khi đăng thành công.<br>• Với Reels/Video: Bật cờ chia sẻ lên Bảng tin (Feed). |
| `shareToStory` | `boolean` | Không | `true` | Alias đồng nghĩa với `shareToFeed` để chỉ định chia sẻ lên Story. |
| `seedingComments`| `array[string]` | Không | `[]` | Mảng các bình luận mồi tự động (Extension sẽ lần lượt bình luận sau khi bài đăng thành công). |
| `autoReactType` | `string` | Không | `"LIKE"` | Cảm xúc thả tự động vào bài viết: `LIKE`, `LOVE`, `CARE`, `HAHA`, `WOW`, `SAD`, `ANGRY`, `NONE`. |
| `runNow` | `boolean` | Không | `true` | `true`: Phát lệnh đăng ngay. `false`: Lưu hàng đợi. (Nếu có `scheduledAt`, ưu tiên chuyển sang chế độ hẹn giờ). |
| `callbackUrl` | `string` | Không | `""` | Đường dẫn Webhook URL của bạn. Server sẽ tự động bắn POST khi bài viết hoàn thành hoặc thất bại. |
| `subProjectId` | `string` | Không | `""` | ID thư mục tài khoản Facebook con muốn đăng bài (mặc định lấy tài khoản đầu tiên). |

#### Request Mẫu (Đăng Ngay & Kèm Seeding + Chia Sẻ Story):
```json
{
  "content": "{Chào bạn|Xin chào mọi người}! {Sản phẩm|Dịch vụ} bên mình đang có chương trình {ưu đãi|khuyến mãi khủng}!",
  "postType": "post",
  "targetType": "profile",
  "mediaUrl": "https://images.unsplash.com/photo-1557804506-669a67965ba0?w=1000",
  "shareToFeed": true,
  "shareToStory": true,
  "seedingComments": [
    "Shop ơi tư vấn mình mẫu này với ạ!",
    "Hàng dùng rất ưng ý, uy tín 100%"
  ],
  "autoReactType": "LOVE",
  "runNow": true,
  "callbackUrl": "https://my-domain.com/api/facebook-webhook"
}
```

#### Request Mẫu (Lên Lịch Tự Động Hóa):
```json
{
  "title": "Chiến Dịch Khai Trương Chi Nhánh 2",
  "content": "🎉 Khai trương tưng bừng chi nhánh mới vào tối nay!",
  "postType": "post",
  "scheduledAt": "2026-09-24T19:30:00.000Z",
  "shareToStory": true,
  "autoReactType": "LIKE"
}
```

#### Response Mẫu (`201 Created`):
```json
{
  "success": true,
  "message": "Đã lên lịch đăng bài thành công vào lúc 19:30:00 24/09/2026",
  "postId": "post_1790198400_a1b2",
  "status": "scheduled",
  "data": {
    "id": "post_1790198400_a1b2",
    "title": "Chiến Dịch Khai Trương Chi Nhánh 2",
    "content": "🎉 Khai trương tưng bừng chi nhánh mới vào tối nay!",
    "postType": "post",
    "targetType": "profile",
    "status": "scheduled",
    "progressStep": "⏳ Đã lên lịch đăng lúc 19:30:00 24/09/2026",
    "scheduledAt": "2026-09-24T19:30:00+00:00",
    "scheduledTime": 1790201400000,
    "scheduledTimeStr": "19:30:00 24/09/2026",
    "shareToFeed": true,
    "autoReactType": "LIKE",
    "createdAt": 1790198400123
  },
  "targetAccount": {
    "projectId": "proj_1790190000_1234",
    "projectName": "Dự Án Bán Lẻ Chính",
    "subProjectId": "sub_fb_1790190000_5678",
    "subProjectName": "Tài Khoản FB Rin",
    "c_user": "100025898964308",
    "fbName": "Rin"
  }
}
```

---

### 4.2. Lấy Danh Sách Bài Đăng & Hàng Đợi (`GET /api/v1/posts`)

Truy vấn danh sách bài viết trong hệ thống với bộ lọc nâng cao và phân trang. **Kết quả luôn được sắp xếp bài viết mới nhất lên trên đầu (`createdAt` giảm dần)**.

* **Endpoint:** `GET /api/v1/posts`
* **Query Parameters:**

| Tham Số | Kiểu | Mặc Định | Mô Tả |
| :--- | :---: | :---: | :--- |
| `status` | `string` | `"all"` | Lọc theo trạng thái bài viết: `"all"`, `"scheduled"`, `"pending"`, `"in_progress"`, `"completed"`, `"failed"`. |
| `postType` | `string` | `"all"` | Lọc theo định dạng: `"all"`, `"post"`, `"video"`, `"reel"`, `"story"`. |
| `subProjectId`| `string`| `""` | Chỉ lấy bài viết thuộc một thư mục/tài khoản Facebook cụ thể. |
| `projectId` | `string` | `""` | Lọc theo ID dự án cha (nếu không dùng token trong header). |
| `limit` | `int` | `50` | Số lượng bài viết tối đa trên mỗi trang. |
| `offset` | `int` | `0` | Vị trí bắt đầu lấy bài (phục vụ phân trang). |

#### Request Mẫu:
```http
GET /api/v1/posts?status=scheduled&limit=10&offset=0
Authorization: Bearer BW-PROJ-XXXXXX
```

#### Response Mẫu (`200 OK`):
```json
{
  "success": true,
  "count": 1,
  "total": 35,
  "pagination": {
    "total": 35,
    "limit": 10,
    "offset": 0,
    "hasMore": true
  },
  "data": [
    {
      "id": "post_1790198400_a1b2",
      "title": "Chiến Dịch Khai Trương Chi Nhánh 2",
      "content": "🎉 Khai trương tưng bừng chi nhánh mới vào tối nay!",
      "postType": "post",
      "targetType": "profile",
      "status": "scheduled",
      "progressStep": "⏳ Đã lên lịch đăng lúc 19:30:00 24/09/2026",
      "scheduledAt": "2026-09-24T19:30:00+00:00",
      "scheduledTimeStr": "19:30:00 24/09/2026",
      "shareToFeed": true,
      "c_user": "100025898964308",
      "fbName": "Rin",
      "createdAt": 1790198400123
    }
  ]
}
```

---

### 4.3. Kiểm Tra Chi Tiết Trạng Thái Bài Viết (`GET /api/v1/posts/{id}`)

Lấy thông tin tiến độ, kết quả đăng bài, ID bài viết trên Facebook, permalink Facebook (`fbPostUrl`), trạng thái reshare lên Story, và danh sách comment seeding đã gửi.

* **Endpoint:** `GET /api/v1/posts/{id}`  
  *(Alias hỗ trợ: `GET /api/v1/posts/status?postId={id}`)*

#### Request Mẫu:
```http
GET /api/v1/posts/post_1790198400_a1b2
Authorization: Bearer BW-PROJ-XXXXXX
```

#### Response Mẫu Khi Đã Đăng Xong (`200 OK`):
```json
{
  "success": true,
  "postId": "post_1790198400_a1b2",
  "status": "completed",
  "progressStep": "✅ Đã đăng thành công lên Facebook (ID: 2151992722340672)",
  "fbPostId": "2151992722340672",
  "fbPostUrl": "https://www.facebook.com/permalink.php?story_fbid=2151992722340672&id=100025898964308",
  "fbFeedbackId": "ZmVlZGJhY2s6MjE1MTk5MjcyMjM0MDY3Mg==",
  "shareToFeed": true,
  "shareToStory": true,
  "shareToStorySuccess": true,
  "seedingIds": ["2151993815673896", "2151993949007216"],
  "publishedAt": 1790198500000,
  "publishedAtStr": "19:31:40 24/09/2026",
  "data": { ... }
}
```

---

### 4.4. Kích Hoạt Đăng Ngay Lập Tức (`POST /api/v1/posts/{id}/run`)

Dùng để cưỡng chế kích hoạt đăng một bài viết đang ở trạng thái `scheduled` (chưa đến giờ hẹn) hoặc `pending` (lưu nháp), chuyển ngay sang Extension để đăng lên Facebook tức thì.

* **Endpoint:** `POST /api/v1/posts/{id}/run`
* **Response Mẫu (`200 OK`):**
```json
{
  "success": true,
  "message": "Đã phát lệnh đăng ngay sang Extension",
  "cmdId": "cmd_1790198600_9f8e7d",
  "data": {
    "id": "post_1790198400_a1b2",
    "status": "in_progress",
    "progressStep": "Đang chuyển lệnh đăng bài sang Extension..."
  }
}
```

---

### 4.5. Đổi Giờ Hẹn Đăng / Hủy Hẹn Giờ (`POST /api/v1/posts/{id}/schedule`)

Cập nhật lại thời gian hẹn giờ xuất bản hoặc hủy lịch hẹn để đưa bài viết về hàng đợi nháp.

* **Endpoint:** `POST /api/v1/posts/{id}/schedule`
* **Body Parameters:**
  - `scheduledAt` *(string, ISO 8601 hoặc datetime)*: Thời điểm hẹn giờ mới.
  - *(Gửi `scheduledAt: null` hoặc chuỗi rỗng `""` để hủy hẹn giờ về nháp)*.

#### Request Mẫu:
```json
{
  "scheduledAt": "2026-09-25T08:00:00.000Z"
}
```

---

### 4.6. Chỉnh Sửa Bài Viết Trong Hàng Đợi (`PATCH /api/v1/posts/{id}`)

Chỉnh sửa linh hoạt bất kỳ trường thông tin nào của một bài viết đang chờ trong hàng đợi.

* **Endpoint:** `PATCH /api/v1/posts/{id}`
* **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <PROJECT_TOKEN>
  ```
* **Các trường hỗ trợ cập nhật:**
  - `title` *(string)*: Tiêu đề mới.
  - `content` *(string)*: Nội dung bài viết mới (hỗ trợ Spintax `{A|B}`).
  - `scheduledAt` *(string/null)*: Thay đổi giờ hẹn đăng hoặc hủy hẹn giờ.
  - `seedingComments` *(array[string])*: Danh sách bình luận seeding mới.
  - `autoReactType` *(string)*: Cảm xúc mới (`LIKE`, `LOVE`, v.v.).
  - `shareToFeed` *(boolean)*: Bật/tắt chia sẻ lên Bảng tin / Story.
  - `shareToStory` *(boolean)*: Bật/tắt chia sẻ lên Story.
  - `callbackUrl` *(string)*: Cập nhật đường link Webhook nhận thông báo.

#### Request Mẫu:
```json
{
  "title": "Tiêu đề đã được cập nhật",
  "content": "{Chào buổi sáng|Hello ngày mới}! Ưu đãi {hấp dẫn|cực lớn} hôm nay.",
  "scheduledAt": "2026-09-24T21:00:00Z",
  "shareToFeed": true,
  "shareToStory": true
}
```

---

### 4.7. Xóa Bài Viết Khỏi Hàng Đợi (`DELETE /api/v1/posts/{id}`)

Xóa vĩnh viễn bài viết khỏi hàng đợi của tài khoản Facebook tương ứng.

* **Endpoint:** `DELETE /api/v1/posts/{id}`
* **Response Mẫu (`200 OK`):**
```json
{
  "success": true,
  "message": "Đã xóa bài viết 'post_1790198400_a1b2' thành công"
}
```

---

### 4.8. Bắn Seeding Vào Bài Viết Đã Đăng (`POST /api/v1/posts/seeding`)

Gửi thêm danh sách bình luận seeding mồi và thả cảm xúc ngầm vào một bài viết Facebook đã xuất bản thành công.

* **Endpoint:** `POST /api/v1/posts/seeding`  
  *(Alias hỗ trợ: `POST /api/posts/seeding`)*
* **Body Parameters:**

| Tên Trường | Kiểu | Bắt Buộc? | Mô Tả |
| :--- | :---: | :---: | :--- |
| `postId` | `string` | **Có** | ID bài viết nội bộ hệ thống hoặc `fbPostId` trực tiếp trên Facebook. |
| `comments` | `array[string]` | **Có** | Danh sách các câu bình luận cần seeding. |
| `autoReactType` | `string` | Không | Cảm xúc thả kèm (`LIKE`, `LOVE`, `CARE`, `HAHA`, v.v.). Mặc định: `LIKE`. |

#### Request Mẫu:
```json
{
  "postId": "post_1790198400_a1b2",
  "comments": [
    "Dịch vụ quá chuyên nghiệp, cho mình đăng ký thêm gói nhé!",
    "Giá cả rất hợp lý, tư vấn nhiệt tình"
  ],
  "autoReactType": "LOVE"
}
```

#### Response Mẫu (`200 OK`):
```json
{
  "success": true,
  "message": "Đã phát lệnh seeding 2 câu sang Extension!",
  "cmdId": "cmd_1790199000_cc88aa",
  "postId": "post_1790198400_a1b2",
  "fbPostId": "2151992722340672"
}
```

---

### 4.9. Danh Sách Tài Khoản & Dự Án (`GET /api/v1/accounts`)

Truy vấn toàn bộ các dự án cha và tài khoản Facebook con đang được kết nối trong hệ thống, bao gồm trạng thái cookie, UID (`c_user`), tên tài khoản và mã Token.

* **Endpoint:** `GET /api/v1/accounts` *(hoặc `GET /api/v1/projects-info`)*
* **Response Mẫu (`200 OK`):**
```json
{
  "success": true,
  "accounts": [
    {
      "projectId": "proj_1790190000_1234",
      "projectName": "Dự Án Bán Lẻ Chính",
      "token": "BW-PROJ-A9F1B2",
      "subProjectId": "sub_fb_1790190000_5678",
      "subProjectName": "Tài Khoản FB Rin",
      "type": "facebook",
      "c_user": "100025898964308",
      "fbName": "Rin",
      "status": "LIVE"
    }
  ]
}
```

---

## 5. Cơ Chế Webhook Callbacks

Nếu bạn truyền trường `"callbackUrl": "https://your-crm.com/webhook"` khi tạo bài viết (`POST /api/v1/posts`), server sẽ tự động gửi một HTTP POST request ngầm đến URL của bạn ngay khi bài viết hoàn thành hoặc gặp sự cố.

### Sự Kiện `POST_COMPLETED` (Đăng Thành Công):
```json
{
  "event": "POST_COMPLETED",
  "postId": "post_1790198400_a1b2",
  "status": "completed",
  "fbPostId": "2151992722340672",
  "fbPostUrl": "https://www.facebook.com/permalink.php?story_fbid=2151992722340672&id=100025898964308",
  "fbFeedbackId": "ZmVlZGJhY2s6MjE1MTk5MjcyMjM0MDY3Mg==",
  "seedingIds": ["2151993815673896"],
  "seedingDetails": [
    { "text": "Shop tư vấn mình với", "id": "2151993815673896" }
  ],
  "publishedAt": 1790198500000,
  "account": {
    "projectId": "proj_1790190000_1234",
    "projectName": "Dự Án Bán Lẻ Chính",
    "subProjectId": "sub_fb_1790190000_5678",
    "subProjectName": "Tài Khoản FB Rin",
    "c_user": "100025898964308",
    "fbName": "Rin"
  },
  "post": { ... }
}
```

### Sự Kiện `POST_FAILED` (Đăng Thất Bại):
```json
{
  "event": "POST_FAILED",
  "postId": "post_1790198400_a1b2",
  "status": "failed",
  "error": "Cookie phiên đăng nhập Facebook đã hết hạn hoặc checkpoint",
  "account": { ... }
}
```

---

## 6. Hỗ Trợ Định Dạng Nội Dung (Spintax & Media)

### 6.1. Spintax Đa Tầng `{A|B|C}`
Hệ thống tích hợp bộ phân tích Spintax đệ quy:
```text
{Xin chào|Chào bạn|Hello quý khách}! 
{Hôm nay|Tuần này} shop mang đến {ưu đãi|giảm giá|khuyến mãi} {khủng|cực sốc} lên tới {30%|50%|70%}.
```
Mỗi khi xuất bản, thuật toán sẽ chọn ngẫu nhiên một biến thể để tạo ra nội dung độc nhất, bảo vệ tài khoản khỏi thuật toán quét bài trùng lặp của Facebook.

### 6.2. Cơ Chế Đăng & Chia Sẻ Tin (Story Reshare)
Khi tham số `shareToFeed: true` (hoặc `shareToStory: true`) được bật trên bài viết thường (`postType: "post"`), sau khi đăng thành công lên Bảng tin, Extension sẽ tự động gọi mutation:
`useCometFeedToStoryReshare_FeedToStoryMutation` (doc_id `28132359363043002`)  
để **chia sẻ ngay bài viết đó lên Tin (Story 24h) của Facebook**, nhân đôi lượng hiển thị tiếp cận tự nhiên.

---

## 7. Mẫu Code Tích Hợp Đa Ngôn Ngữ

### 7.1. cURL (Bash / Terminal)

```bash
# Đăng ngay bài viết lên Facebook kèm seeding & chia sẻ Story
curl -X POST "http://localhost:9999/api/v1/posts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer BW-PROJ-A9F1B2" \
  -d '{
    "content": "{Chào mừng|Xin chào} mọi người! Bài viết gửi từ cURL script.",
    "postType": "post",
    "shareToFeed": true,
    "shareToStory": true,
    "seedingComments": ["Tuyệt vời quá!", "Inbox shop ơi"],
    "autoReactType": "LOVE",
    "runNow": true
  }'
```

```bash
# Lấy danh sách 20 bài đăng mới nhất trong hàng đợi
curl -X GET "http://localhost:9999/api/v1/posts?limit=20&status=all" \
  -H "Authorization: Bearer BW-PROJ-A9F1B2"
```

---

### 7.2. Python (`requests`)

```python
import requests

BASE_URL = "http://localhost:9999"
PROJECT_TOKEN = "BW-PROJ-A9F1B2"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {PROJECT_TOKEN}"
}

# 1. Tạo bài viết hẹn giờ đăng lúc 20:00 tối nay
payload = {
    "title": "Chương trình Flash Sale Cuối Ngày",
    "content": "⚡ {Flash sale|Giờ vàng} giá sốc chỉ duy nhất tối nay!",
    "postType": "post",
    "scheduledAt": "2026-09-24T20:00:00Z",
    "shareToStory": True,
    "seedingComments": ["Có mẫu này không ạ?", "Shop tư vấn giúp mình"],
    "autoReactType": "LOVE"
}

response = requests.post(f"{BASE_URL}/api/v1/posts", json=payload, headers=headers)
result = response.json()
print("Kết quả:", result)

# 2. Truy vấn danh sách bài viết
res_list = requests.get(f"{BASE_URL}/api/v1/posts?status=scheduled", headers=headers)
print("Các bài đã hẹn giờ:", res_list.json()["data"])
```

---

### 7.3. Node.js (JavaScript / Fetch)

```javascript
const BASE_URL = "http://localhost:9999";
const PROJECT_TOKEN = "BW-PROJ-A9F1B2";

async function createPost() {
  const payload = {
    content: "{Sự kiện|Chương trình} đặc biệt dành cho khách hàng thân thiết!",
    postType: "post",
    targetType: "profile",
    shareToStory: true,
    runNow: true,
    callbackUrl: "https://your-domain.com/webhook"
  };

  const response = await fetch(`${BASE_URL}/api/v1/posts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${PROJECT_TOKEN}`
    },
    body: JSON.stringify(payload)
  });

  const data = await response.json();
  console.log("Đã phát lệnh đăng bài:", data);
}

createPost();
```

---

### 7.4. PHP (`cURL`)

```php
<?php
$baseUrl = "http://localhost:9999";
$token = "BW-PROJ-A9F1B2";

$payload = [
    "content" => "{Chào bạn|Hello}! Bài viết tự động từ hệ thống PHP CRM.",
    "postType" => "post",
    "shareToStory" => true,
    "runNow" => true,
    "seedingComments" => ["Quan tâm sản phẩm", "Check tin nhắn nhé shop"]
];

$ch = curl_init("$baseUrl/api/v1/posts");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Content-Type: application/json",
    "Authorization: Bearer $token"
]);

$response = curl_exec($ch);
curl_close($ch);

$result = json_decode($response, true);
echo "Post ID: " . $result["postId"];
?>
```

---

## 8. Tích Hợp n8n / Make / Zapier

1. **Trigger:** Webhook từ Google Sheets, Airtable, CRM, hoặc RSS Feed.
2. **HTTP Request Node:**
   - **Method:** `POST`
   - **URL:** `http://<IP_VPS>:9999/api/v1/posts`
   - **Authentication:** Header `Authorization` = `Bearer BW-PROJ-XXXXXX`
   - **Body Type:** JSON
   - **Fields:** Ghép nội dung từ bước trước vào `content`, thêm `scheduledAt` hoặc `runNow: true`.
3. **Response Handling:**
   - Đọc trường `result.postId` và `result.data.status` để lưu ID vào cơ sở dữ liệu.
4. **Webhook Node (Nhận kết quả):**
   - Thiết lập n8n Webhook URL làm `callbackUrl` để nhận `POST_COMPLETED` kèm đường link bài viết Facebook (`fbPostUrl`).
