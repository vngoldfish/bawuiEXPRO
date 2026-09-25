PRAGMA journal_mode = WAL;         -- Kích hoạt Write-Ahead Logging (Đa luồng đọc đồng thời)
PRAGMA synchronous = NORMAL;       -- Cân bằng hoàn hảo giữa an toàn dữ liệu và tốc độ ghi đĩa
PRAGMA busy_timeout = 5000;        -- Thiết lập hàng đợi chờ tối đa 5000ms khi tài nguyên đang bị khóa
PRAGMA foreign_keys = ON;          -- Bắt buộc kích hoạt ràng buộc toàn vẹn khóa ngoại (ON DELETE CASCADE)
PRAGMA cache_size = -64000;        -- Cấp phát 64MB RAM làm bộ nhớ đệm trang (Page Cache)
PRAGMA temp_store = MEMORY;        -- Lưu bảng tạm và con trỏ sort trên RAM
-- ============================================================================
-- BAWUI EX PRO: RELATIONAL DATABASE SCHEMA DDL (SQLITE WAL / POSTGRESQL READY)
-- ============================================================================

-- 1. Bảng Dự Án Cha (Projects)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    token TEXT UNIQUE NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_token ON projects(token);

-- 2. Bảng Thư Mục Con / Tài Khoản Facebook & Đa Nền Tảng (SubProjects)
CREATE TABLE IF NOT EXISTS sub_projects (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'facebook',             -- 'facebook', 'tiktok', 'instagram', 'threads', 'flow'
    description TEXT,
    account_uid TEXT,                         -- c_user (FB) hoặc open_id (TikTok)
    account_name TEXT,                        -- fbName, channelName
    avatar_url TEXT,
    profile_url TEXT,
    cookie_str TEXT,                          -- Chuỗi cookie định dạng thô
    cookies_json TEXT,                        -- Chi tiết cookies định dạng JSON
    eaag_token TEXT,                          -- Token đăng bài FB (nếu có)
    dtsg TEXT,                                -- CSRF Token bảo mật FB
    google_email TEXT,                        -- Cấu hình Google AI Flow
    google_uid TEXT,
    flow_project_id TEXT,
    flow_project_name TEXT,
    flow_child_projects_json TEXT,            -- Danh mục Google Flow Child Canvases (JSON)
    active_flow_child_id TEXT,                -- ID canvas Google Flow đang được chọn
    scraped_data_json TEXT,                   -- Dữ liệu cào bài viết / thông tin kênh (JSON)
    purpose TEXT,                             -- Mục đích sử dụng subproject
    source_url TEXT,                          -- URL nguồn tham chiếu
    source_domain TEXT,                       -- Tên miền nguồn
    is_encrypted INTEGER DEFAULT 0,           -- Cờ đánh dấu cookies đã mã hóa AES-256 hay chưa
    status TEXT DEFAULT 'CHƯA KIỂM TRA',     -- 'LIVE', 'CHECKPOINT', 'EXPIRED'
    last_extracted INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_subprojects_project_id ON sub_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_subprojects_uid ON sub_projects(account_uid);

-- 3. Bảng Bài Đăng & Hàng Đợi (Posts & Queue)
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sub_project_id TEXT NOT NULL,
    title TEXT,
    content TEXT,
    post_type TEXT DEFAULT 'post',            -- 'post', 'reel', 'video', 'story'
    target_type TEXT DEFAULT 'profile',       -- 'profile', 'page', 'group'
    target_id TEXT,
    target_url TEXT,
    share_to_feed INTEGER DEFAULT 1,
    media_url TEXT,
    media_file_path TEXT,                     -- ĐƯỜNG DẪN TỆP TRÊN ĐĨA (TÁCH BIỆT KHỎI BASE64!)
    media_mime_type TEXT,
    media_size INTEGER,
    seeding_comments_json TEXT,               -- Mảng comment seeding (JSON)
    auto_react_type TEXT DEFAULT 'LIKE',      -- 'LIKE', 'LOVE', 'CARE', 'HAHA', 'WOW'
    status TEXT DEFAULT 'pending',            -- 'pending', 'scheduled', 'in_progress', 'completed', 'failed'
    progress_step TEXT,
    fb_post_id TEXT,
    fb_post_url TEXT,
    fb_feedback_id TEXT,
    seeding_ids_json TEXT,
    seeding_details_json TEXT,
    share_to_story_success INTEGER DEFAULT 0,
    last_error TEXT,                          -- Lịch sử phản hồi lỗi từ mạng xã hội
    callback_url TEXT,                        -- Webhook URL nhận kết quả
    scraped_data_json TEXT,                   -- Dữ liệu cào đính kèm bài viết (JSON)
    purpose TEXT,                             -- Mục đích chiến dịch bài đăng
    source_url TEXT,                          -- URL nguồn bài viết gốc
    source_domain TEXT,                       -- Tên miền nguồn
    scheduled_time INTEGER DEFAULT 0,         -- Timestamp hẹn giờ (mili-giây)
    scheduled_time_str TEXT,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at INTEGER NOT NULL,
    published_at INTEGER DEFAULT 0,           -- Timestamp đăng bài thành công thực tế
    completed_at INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE
);
-- Các chỉ mục tối ưu hóa tốc độ truy vấn bài đăng:
CREATE INDEX IF NOT EXISTS idx_posts_scheduler ON posts(status, scheduled_time) WHERE status = 'scheduled';
CREATE INDEX IF NOT EXISTS idx_posts_sub_pagination ON posts(sub_project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_project_pagination ON posts(project_id, created_at DESC);

-- 4. Bảng Quản Lý Tạo Ảnh AI Google Flow (FlowImages)
CREATE TABLE IF NOT EXISTS flow_images (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sub_project_id TEXT NOT NULL,
    flow_project_id TEXT,
    flow_child_id TEXT,
    prompt TEXT,
    model TEXT,
    image_count INTEGER DEFAULT 1,
    aspect_ratio TEXT,
    status TEXT DEFAULT 'pending',
    progress_step TEXT,
    image_file_paths_json TEXT,               -- Mảng đường dẫn file ảnh trên đĩa (JSON)
    created_at INTEGER NOT NULL,
    completed_at INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_flow_images_sub ON flow_images(sub_project_id);

-- 5. Bảng Quản Lý Trạng Thái Nút Extension (Nodes)
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    project_id TEXT,
    node_name TEXT,
    version TEXT,
    ip_address TEXT,
    last_seen INTEGER NOT NULL,
    status TEXT DEFAULT 'ONLINE',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

-- 6. Bảng Quản Lý Hàng Đợi Lệnh Điều Khiển Extension (BridgeCommands)
CREATE TABLE IF NOT EXISTS bridge_commands (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    target_project_id TEXT,
    target_sub_project_id TEXT,
    target_node_id TEXT,
    payload_json TEXT,
    status TEXT DEFAULT 'pending',            -- 'pending', 'dispatched', 'completed', 'failed'
    priority INTEGER DEFAULT 0,               -- 1: Ưu tiên can thiệp tức thì, 0: Thường
    created_at INTEGER NOT NULL,
    dispatched_at INTEGER DEFAULT 0,
    completed_at INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_commands_poll ON bridge_commands(status, priority DESC, created_at ASC);

-- 7. Bảng Nhật Ký Hoạt Động Hệ Thống Bền Vững (Audit & System Logs)
CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    sub_project_id TEXT,
    log_type TEXT DEFAULT 'info',             -- 'info', 'success', 'warning', 'danger'
    message TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at DESC);
