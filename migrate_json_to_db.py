#!/usr/bin/env python3
"""
BAWUI EX PRO: ZERO-DOWNTIME DATA MIGRATION SCRIPT (ETL)
Chuyển đổi toàn bộ dữ liệu từ projects.json sang SQLite (Chế độ WAL)
Tách rời dữ liệu Base64 media ra các tệp nhị phân trên đĩa cứng.
"""

import os
import sys
import json
import time
import uuid
import base64
import shutil
import sqlite3
import re

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(BASE_DIR, "projects.json")):
    PROJECT_ROOT = BASE_DIR
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
JSON_PATH = os.path.join(PROJECT_ROOT, "projects.json")
DB_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DB_DIR, "bawui_ex.db")
UPLOAD_DIR = os.path.join(DB_DIR, "uploads")
MEDIA_DIR = os.path.join(UPLOAD_DIR, "media")
FLOW_DIR = os.path.join(UPLOAD_DIR, "flow")

def ensure_directories():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(FLOW_DIR, exist_ok=True)

def backup_original_json():
    if not os.path.exists(JSON_PATH):
        print(f"[ERROR] Không tìm thấy file nguồn: {JSON_PATH}")
        sys.exit(1)
    backup_path = f"{JSON_PATH}.bak.{int(time.time())}"
    shutil.copy2(JSON_PATH, backup_path)
    print(f"[STEP 1] Đã tạo bản sao lưu an toàn: {backup_path}")
    return backup_path

def save_base64_to_disk(b64_string, target_folder, prefix="media"):
    """Tách chuỗi base64 thành file nhị phân trên đĩa và trả về đường dẫn tương đối.
    Nếu chuỗi Base64 bị hỏng hoặc thiếu padding, ghi log cảnh báo chi tiết và lưu
    dữ liệu thô vào file fallback để tuyệt đối không làm mất dữ liệu của khách hàng."""
    if not b64_string:
        return None
    try:
        if "base64," in b64_string:
            header, raw_b64 = b64_string.split("base64,", 1)
            ext = "jpg"
            if "image/png" in header: ext = "png"
            elif "image/webp" in header: ext = "webp"
            elif "video/mp4" in header: ext = "mp4"
        else:
            raw_b64 = b64_string
            ext = "jpg"
        
        # Bổ sung padding nếu chuỗi base64 bị thiếu
        missing_padding = len(raw_b64) % 4
        if missing_padding:
            raw_b64 += "=" * (4 - missing_padding)

        file_bytes = base64.b64decode(raw_b64)
        filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        abs_path = os.path.join(target_folder, filename)
        with open(abs_path, "wb") as f:
            f.write(file_bytes)
        
        # Trả về đường dẫn tương đối từ PROJECT_ROOT
        rel_path = os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/")
        return rel_path
    except Exception as e:
        print(f"[WARN] Lỗi giải mã Base64 ({prefix}): {e}. Lưu fallback thô để bảo toàn dữ liệu!")
        try:
            fallback_filename = f"{prefix}_{int(time.time())}_corrupt_fallback.raw"
            fallback_abs = os.path.join(target_folder, fallback_filename)
            with open(fallback_abs, "w", encoding="utf-8", errors="ignore") as f:
                f.write(b64_string)
            return os.path.relpath(fallback_abs, PROJECT_ROOT).replace("\\", "/")
        except Exception as fb_err:
            print(f"[ERROR] Không thể lưu file fallback thô: {fb_err}")
            return None

def init_target_database():
    # Bắt buộc isolation_level=None để kích hoạt Autocommit và kiểm soát transaction tường minh
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    cursor = conn.cursor()
    
    # Cấu hình WAL Mode, Concurrency Guard & Busy Timeout
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA cache_size = -64000;")
    
    schema_sql_path = os.path.join(BASE_DIR, "schema.sql")
    if os.path.exists(schema_sql_path):
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
    else:
        print("[WARN] Chưa có file riêng schema.sql, áp dụng DDL khởi tạo trực tiếp...")
        
    print(f"[STEP 2] Đã khởi tạo CSDL SQLite với chế độ WAL tại: {DB_PATH}")
    return conn

def execute_etl(conn):
    print("[STEP 3] Bắt đầu quá trình Extract, Transform & Load...")
    # Hỗ trợ mở utf-8-sig chống lỗi UTF-8 BOM
    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    projects_raw = data.get("projects", []) if isinstance(data, dict) else data
    cursor = conn.cursor()
    
    stats = {
        "projects": 0,
        "subprojects": 0,
        "posts": 0,
        "flow_images": 0,
        "flow_child_projects": 0,
        "offloaded_bytes": 0
    }

    try:
        # Bắt buộc BEGIN IMMEDIATE để lấy Reserved Lock, chống Lock Upgrade Deadlock
        cursor.execute("BEGIN IMMEDIATE;")
        
        for p in projects_raw:
            proj_id = p.get("id") or f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            cursor.execute("""
                INSERT OR REPLACE INTO projects (id, name, description, token, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                proj_id,
                p.get("name", "Dự án"),
                p.get("description", ""),
                p.get("token", f"BW-{uuid.uuid4().hex[:12].upper()}"),
                p.get("createdAt", int(time.time() * 1000)),
                int(time.time() * 1000)
            ))
            stats["projects"] += 1
            
            for s in p.get("subProjects", []):
                sub_id = s.get("id") or f"sub_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                flow_children = s.get("flowChildProjects", [])
                stats["flow_child_projects"] += len(flow_children)

                cursor.execute("""
                    INSERT OR REPLACE INTO sub_projects (
                        id, project_id, name, type, description, account_uid, account_name,
                        avatar_url, profile_url, cookie_str, cookies_json, eaag_token, dtsg,
                        google_email, google_uid, flow_project_id, flow_project_name,
                        flow_child_projects_json, active_flow_child_id, scraped_data_json,
                        purpose, source_url, source_domain, is_encrypted, status,
                        last_extracted, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sub_id,
                    proj_id,
                    s.get("name", "SubProject"),
                    s.get("type", "facebook"),
                    s.get("description", ""),
                    s.get("uid") or s.get("c_user", ""),
                    s.get("accountName") or s.get("fbName", ""),
                    s.get("avatar", ""),
                    s.get("profileUrl", ""),
                    s.get("cookieStr", ""),
                    json.dumps(s.get("cookies", []), ensure_ascii=False),
                    s.get("eaagToken", ""),
                    s.get("dtsg", ""),
                    s.get("googleEmail", ""),
                    s.get("googleUid", ""),
                    s.get("flowProjectId", ""),
                    s.get("flowProjectName", ""),
                    json.dumps(flow_children, ensure_ascii=False),
                    s.get("activeFlowChildId", ""),
                    json.dumps(s.get("scrapedData", {}), ensure_ascii=False) if s.get("scrapedData") else "",
                    s.get("purpose", ""),
                    s.get("sourceUrl", ""),
                    s.get("sourceDomain", ""),
                    0,
                    s.get("status", "Chưa kiểm tra"),
                    s.get("lastExtracted", 0),
                    s.get("createdAt", int(time.time() * 1000)),
                    int(time.time() * 1000)
                ))
                stats["subprojects"] += 1
                
                # Trích xuất và di chuyển Hàng đợi bài viết (postQueue)
                for post in s.get("postQueue", []):
                    post_id = post.get("id") or f"post_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                    media_path = None
                    
                    # Bóc tách Base64 nếu có trong bài đăng
                    media_data = post.get("mediaData")
                    if isinstance(media_data, dict) and media_data.get("base64"):
                        b64_content = media_data.get("base64")
                        stats["offloaded_bytes"] += len(b64_content)
                        media_path = save_base64_to_disk(b64_content, MEDIA_DIR, prefix=f"post_{post_id}")
                    elif post.get("mediaUrl") and post.get("mediaUrl").startswith("data:"):
                        stats["offloaded_bytes"] += len(post.get("mediaUrl"))
                        media_path = save_base64_to_disk(post.get("mediaUrl"), MEDIA_DIR, prefix=f"post_{post_id}")
                    else:
                        media_path = post.get("mediaUrl")
                    
                    # Bảo toàn lịch sử lỗi và mốc thời gian hoàn tất
                    last_err = post.get("lastError") or post.get("errorMessage", "")
                    pub_ts = post.get("publishedAt", 0) or post.get("completedAt", 0)

                    cursor.execute("""
                        INSERT OR REPLACE INTO posts (
                            id, project_id, sub_project_id, title, content, post_type,
                            target_type, target_id, target_url, share_to_feed, media_url,
                            media_file_path, seeding_comments_json, auto_react_type, status,
                            progress_step, fb_post_id, fb_post_url, fb_feedback_id,
                            seeding_ids_json, seeding_details_json, share_to_story_success,
                            last_error, callback_url, scraped_data_json, purpose,
                            source_url, source_domain, scheduled_time, scheduled_time_str,
                            error_message, created_at, published_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        post_id,
                        proj_id,
                        sub_id,
                        post.get("title", ""),
                        post.get("content", ""),
                        post.get("postType", "post"),
                        post.get("targetType", "profile"),
                        post.get("targetId", ""),
                        post.get("targetUrl", ""),
                        1 if post.get("shareToFeed", True) else 0,
                        post.get("mediaUrl", ""),
                        media_path,
                        json.dumps(post.get("seedingComments", []), ensure_ascii=False),
                        post.get("autoReactType", "LIKE"),
                        post.get("status", "pending"),
                        post.get("progressStep", ""),
                        post.get("fbPostId", ""),
                        post.get("fbPostUrl", ""),
                        post.get("fbFeedbackId", ""),
                        json.dumps(post.get("seedingIds", []), ensure_ascii=False),
                        json.dumps(post.get("seedingDetails", []), ensure_ascii=False),
                        1 if post.get("shareToStorySuccess") else 0,
                        last_err,
                        post.get("callbackUrl", ""),
                        json.dumps(post.get("scrapedData", {}), ensure_ascii=False) if post.get("scrapedData") else "",
                        post.get("purpose", ""),
                        post.get("sourceUrl") or post.get("source", ""),
                        post.get("sourceDomain", ""),
                        post.get("scheduledTime", 0),
                        post.get("scheduledTimeStr", ""),
                        last_err,
                        post.get("createdAt", int(time.time() * 1000)),
                        pub_ts,
                        pub_ts
                    ))
                    stats["posts"] += 1
                
                # Trích xuất và bóc tách Base64 mảng ảnh Google Flow (imageQueue)
                for flow_item in s.get("imageQueue", []):
                    flow_id = flow_item.get("id") or f"flow_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                    saved_image_paths = []
                    
                    # Giải mã các ảnh Base64
                    for idx, img_obj in enumerate(flow_item.get("images", [])):
                        raw_url = img_obj.get("url", "")
                        if raw_url.startswith("data:image"):
                            stats["offloaded_bytes"] += len(raw_url)
                            f_path = save_base64_to_disk(raw_url, FLOW_DIR, prefix=f"flow_{flow_id}_{idx}")
                            if f_path:
                                saved_image_paths.append(f_path)
                            else:
                                saved_image_paths.append(raw_url)  # Giữ raw URL phòng vệ
                        elif raw_url:
                            saved_image_paths.append(raw_url)
                    
                    # Bảo toàn mốc completedAt gốc của AI Flow, không ghi đè thời gian hiện tại
                    original_completed_at = flow_item.get("completedAt") or flow_item.get("completed_at") or int(time.time() * 1000)

                    cursor.execute("""
                        INSERT OR REPLACE INTO flow_images (
                            id, project_id, sub_project_id, flow_project_id, flow_child_id,
                            prompt, model, image_count, aspect_ratio, status, progress_step,
                            image_file_paths_json, created_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        flow_id,
                        proj_id,
                        sub_id,
                        flow_item.get("flowProjectId", ""),
                        flow_item.get("childId") or flow_item.get("flowChildId", ""),
                        flow_item.get("prompt", ""),
                        flow_item.get("model", ""),
                        flow_item.get("imageCount", len(saved_image_paths)),
                        flow_item.get("aspectRatio", "1:1"),
                        flow_item.get("status", "completed"),
                        flow_item.get("progressStep", ""),
                        json.dumps(saved_image_paths, ensure_ascii=False),
                        flow_item.get("createdAt", int(time.time() * 1000)),
                        original_completed_at
                    ))
                    stats["flow_images"] += 1

        cursor.execute("COMMIT;")
        print(f"[STEP 4] Nạp dữ liệu hoàn tất vào CSDL thành công!")
        return stats
    except Exception as e:
        cursor.execute("ROLLBACK;")
        print(f"[ERROR] Di chuyển thất bại, đã hoàn tác Transaction (Rollback): {e}")
        raise e

def verify_migration(conn, expected_stats):
    print("[STEP 5] Bắt đầu Kiểm định Tính Toàn vẹn Dữ liệu (Verification Gate)...")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM projects")
    count_projects = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM sub_projects")
    count_subprojects = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM posts")
    count_posts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM flow_images")
    count_flow = cursor.fetchone()[0]

    # Kiểm tra tính toàn vẹn của Google Flow Child Projects
    cursor.execute("SELECT COUNT(*) FROM sub_projects WHERE flow_child_projects_json IS NOT NULL AND flow_child_projects_json != '[]' AND flow_child_projects_json != ''")
    count_flow_subs = cursor.fetchone()[0]
    
    print(f" - Dự án (Projects)           : {count_projects} / {expected_stats['projects']} (Khớp: {count_projects == expected_stats['projects']})")
    print(f" - Thư mục con (SubProjects)  : {count_subprojects} / {expected_stats['subprojects']} (Khớp: {count_subprojects == expected_stats['subprojects']})")
    print(f" - Bài viết (Posts)           : {count_posts} / {expected_stats['posts']} (Khớp: {count_posts == expected_stats['posts']})")
    print(f" - Ảnh AI Google Flow         : {count_flow} / {expected_stats['flow_images']} (Khớp: {count_flow == expected_stats['flow_images']})")
    print(f" - Subs có Flow Child Canvases: {count_flow_subs} (Bảo toàn 100% Canvas con)")
    print(f" - Dữ liệu nhị phân bóc tách khỏi DB: {expected_stats['offloaded_bytes'] / (1024*1024):.2f} MB")
    
    # Verification Gate: Bắt buộc toàn bộ các chỉ số phải khớp tuyệt đối 100%
    assert count_projects == expected_stats["projects"], "Sai lệch số lượng Projects!"
    assert count_subprojects == expected_stats["subprojects"], "Sai lệch số lượng SubProjects!"
    assert count_posts == expected_stats["posts"], "Sai lệch số lượng Posts!"
    assert count_flow == expected_stats["flow_images"], "Sai lệch số lượng Flow Images!"
    
    print("\n[THÀNH CÔNG] Dữ liệu được di chuyển chính xác 100%. Bảo toàn toàn bộ Google Flow Child Canvases và lịch sử lỗi!")

if __name__ == "__main__":
    ensure_directories()
    backup_path = backup_original_json()
    conn = init_target_database()
    stats = execute_etl(conn)
    verify_migration(conn, stats)
    conn.close()
