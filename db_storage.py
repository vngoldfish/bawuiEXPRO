#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BAWUI EX PRO — SQLite WAL Database Storage Adapter & Media Manager
Thay thế mô hình lưu trữ file JSON cồng kềnh bằng SQLite WAL + Đĩa nhị phân.
"""

import os
import sys
import json
import time
import uuid
import shutil
import base64
import sqlite3
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "bawui_ex.db")
UPLOAD_DIR = os.path.join(DB_DIR, "uploads")
MEDIA_DIR = os.path.join(UPLOAD_DIR, "media")
FLOW_DIR = os.path.join(UPLOAD_DIR, "flow")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
JSON_PATH = os.path.join(BASE_DIR, "projects.json")

# Đảm bảo các thư mục vật lý luôn tồn tại
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(FLOW_DIR, exist_ok=True)

# Khóa luồng ứng dụng cho SQLite
DB_LOCK = threading.RLock()
_local = threading.local()

def get_connection():
    """Tạo hoặc tái sử dụng kết nối SQLite theo từng luồng (Thread-local connection)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA cache_size = -64000;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        _local.conn = conn
    return _local.conn

def init_db():
    """Khởi tạo cấu trúc bảng từ schema.sql nếu CSDL chưa có."""
    with DB_LOCK:
        conn = get_connection()
        cursor = conn.cursor()
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                cursor.executescript(f.read())
        print(f"[*] SQLite WAL Database Initialized at {DB_PATH}")

def save_uploaded_media(b64_string, filename=None, mime_type=None, prefix="media"):
    """
    Bóc tách chuỗi Base64 ảnh/video ra lưu thành tệp thực tế trên ổ đĩa.
    Trả về tuple: (đường_dẫn_tương_đối, url_phục_vụ_web)
    """
    if not b64_string:
        return None, ""
    try:
        ext = "jpg"
        if "base64," in b64_string:
            header, raw_b64 = b64_string.split("base64,", 1)
            if "image/png" in header: ext = "png"
            elif "image/webp" in header: ext = "webp"
            elif "image/gif" in header: ext = "gif"
            elif "video/mp4" in header: ext = "mp4"
            elif "video/webm" in header: ext = "webm"
        else:
            raw_b64 = b64_string
            if mime_type:
                if "png" in mime_type: ext = "png"
                elif "webp" in mime_type: ext = "webp"
                elif "mp4" in mime_type: ext = "mp4"
            elif filename:
                m = filename.rsplit(".", 1)
                if len(m) > 1 and len(m[1]) <= 4:
                    ext = m[1].lower()

        missing_padding = len(raw_b64) % 4
        if missing_padding:
            raw_b64 += "=" * (4 - missing_padding)

        file_bytes = base64.b64decode(raw_b64)
        saved_filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        target_folder = FLOW_DIR if prefix.startswith("flow") else MEDIA_DIR
        abs_path = os.path.join(target_folder, saved_filename)
        with open(abs_path, "wb") as f:
            f.write(file_bytes)

        rel_path = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
        subfolder = "flow" if prefix.startswith("flow") else "media"
        web_url = f"/uploads/{subfolder}/{saved_filename}"
        return rel_path, web_url
    except Exception as e:
        print(f"[Media Save Error] {e}")
        return None, ""

def get_all_projects_from_db():
    """
    Đọc toàn bộ dữ liệu từ SQLite WAL và đóng gói thành cấu trúc List các Project
    tương thích 100% với giao diện hiện tại của Web Dashboard và Extension.
    """
    with DB_LOCK:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # 1. Đọc danh sách Projects
            cursor.execute("SELECT * FROM projects ORDER BY created_at ASC")
            proj_rows = cursor.fetchall()
            if not proj_rows:
                return []

            # 2. Đọc danh sách SubProjects
            cursor.execute("SELECT * FROM sub_projects ORDER BY created_at ASC")
            sub_rows = cursor.fetchall()
            subs_by_proj = {}
            for s in sub_rows:
                p_id = s["project_id"]
                if p_id not in subs_by_proj:
                    subs_by_proj[p_id] = []
                subs_by_proj[p_id].append(s)

            # 3. Đọc danh sách Posts
            cursor.execute("SELECT * FROM posts ORDER BY created_at DESC")
            post_rows = cursor.fetchall()
            posts_by_sub = {}
            for post in post_rows:
                s_id = post["sub_project_id"]
                if s_id not in posts_by_sub:
                    posts_by_sub[s_id] = []
                posts_by_sub[s_id].append(post)

            # 4. Đọc danh sách Flow Images
            cursor.execute("SELECT * FROM flow_images ORDER BY created_at DESC")
            flow_rows = cursor.fetchall()
            flow_by_sub = {}
            for fl in flow_rows:
                s_id = fl["sub_project_id"]
                if s_id not in flow_by_sub:
                    flow_by_sub[s_id] = []
                flow_by_sub[s_id].append(fl)

            # 5. Tái cấu trúc thành JSON-compatible dicts
            results = []
            for p in proj_rows:
                p_id = p["id"]
                p_dict = {
                    "id": p_id,
                    "name": p["name"],
                    "description": p["description"] or "",
                    "token": p["token"],
                    "createdAt": p["created_at"],
                    "subProjects": []
                }

                for s in subs_by_proj.get(p_id, []):
                    s_id = s["id"]
                    cookies_list = []
                    try:
                        if s["cookies_json"]:
                            cookies_list = json.loads(s["cookies_json"])
                    except Exception:
                        pass

                    flow_children = []
                    try:
                        if s["flow_child_projects_json"]:
                            flow_children = json.loads(s["flow_child_projects_json"])
                    except Exception:
                        pass

                    scraped_data = {}
                    try:
                        if s["scraped_data_json"]:
                            scraped_data = json.loads(s["scraped_data_json"])
                    except Exception:
                        pass

                    # Parse PostQueue
                    post_queue = []
                    for post in posts_by_sub.get(s_id, []):
                        seeding_comments = []
                        try:
                            if post["seeding_comments_json"]:
                                seeding_comments = json.loads(post["seeding_comments_json"])
                        except Exception:
                            pass

                        seeding_ids = []
                        try:
                            if post["seeding_ids_json"]:
                                seeding_ids = json.loads(post["seeding_ids_json"])
                        except Exception:
                            pass

                        seeding_details = []
                        try:
                            if post["seeding_details_json"]:
                                seeding_details = json.loads(post["seeding_details_json"])
                        except Exception:
                            pass

                        # Xác định mediaUrl công khai để web và extension hiển thị/tải
                        media_url = post["media_url"] or ""
                        if not media_url and post["media_file_path"]:
                            fname = os.path.basename(post["media_file_path"])
                            media_url = f"/uploads/media/{fname}"

                        post_item = {
                            "id": post["id"],
                            "title": post["title"] or "",
                            "content": post["content"] or "",
                            "postType": post["post_type"] or "post",
                            "targetType": post["target_type"] or "profile",
                            "targetId": post["target_id"] or "",
                            "targetUrl": post["target_url"] or "https://www.facebook.com",
                            "shareToFeed": bool(post["share_to_feed"]),
                            "mediaUrl": media_url,
                            "mediaFilePath": post["media_file_path"] or "",
                            "seedingComments": seeding_comments,
                            "autoReactType": post["auto_react_type"] or "LIKE",
                            "status": post["status"] or "pending",
                            "progressStep": post["progress_step"] or "",
                            "fbPostId": post["fb_post_id"] or "",
                            "fbPostUrl": post["fb_post_url"] or "",
                            "fbFeedbackId": post["fb_feedback_id"] or "",
                            "seedingIds": seeding_ids,
                            "seedingDetails": seeding_details,
                            "shareToStorySuccess": bool(post["share_to_story_success"]),
                            "lastError": post["last_error"] or "",
                            "scheduledTime": post["scheduled_time"] or 0,
                            "scheduledTimeStr": post["scheduled_time_str"] or "",
                            "createdAt": post["created_at"] or int(time.time() * 1000),
                            "publishedAt": post["published_at"] or 0,
                            "completedAt": post["completed_at"] or 0
                        }
                        post_queue.append(post_item)

                    # Parse ImageQueue (AI Google Flow)
                    image_queue = []
                    for fl in flow_by_sub.get(s_id, []):
                        img_paths = []
                        try:
                            if fl["image_file_paths_json"]:
                                img_paths = json.loads(fl["image_file_paths_json"])
                        except Exception:
                            pass

                        images = []
                        for ip in img_paths:
                            fname = os.path.basename(ip)
                            images.append({"url": f"/uploads/flow/{fname}"})

                        image_queue.append({
                            "id": fl["id"],
                            "prompt": fl["prompt"] or "",
                            "model": fl["model"] or "",
                            "imageCount": fl["image_count"] or 1,
                            "aspectRatio": fl["aspect_ratio"] or "1:1",
                            "status": fl["status"] or "completed",
                            "progressStep": fl["progress_step"] or "",
                            "images": images,
                            "createdAt": fl["created_at"] or int(time.time() * 1000),
                            "completedAt": fl["completed_at"] or 0
                        })

                    s_dict = {
                        "id": s_id,
                        "name": s["name"],
                        "type": s["type"] or "facebook",
                        "description": s["description"] or "",
                        "c_user": s["account_uid"] or "",
                        "fbName": s["account_name"] or "",
                        "avatar": s["avatar_url"] or "",
                        "profileUrl": s["profile_url"] or "",
                        "cookieStr": s["cookie_str"] or "",
                        "cookies": cookies_list,
                        "eaagToken": s["eaag_token"] or "",
                        "dtsg": s["dtsg"] or "",
                        "status": s["status"] or "Chưa kiểm tra",
                        "lastExtracted": s["last_extracted"] or 0,
                        "createdAt": s["created_at"] or int(time.time() * 1000),
                        "googleEmail": s["google_email"] or "",
                        "googleUid": s["google_uid"] or "",
                        "flowProjectId": s["flow_project_id"] or "",
                        "flowProjectName": s["flow_project_name"] or "",
                        "flowChildProjects": flow_children,
                        "activeFlowChildId": s["active_flow_child_id"] or "",
                        "scrapedData": scraped_data,
                        "postQueue": post_queue,
                        "imageQueue": image_queue
                    }
                    p_dict["subProjects"].append(s_dict)

                results.append(p_dict)
            return results
        except Exception as e:
            print(f"[DB Get Projects Error] {e}")
            return []

def save_projects_to_db(projects_list):
    """
    Lưu toàn bộ danh sách Projects vào SQLite WAL bằng Transaction nguyên tử (BEGIN IMMEDIATE).
    Đồng thời tự động bóc tách Base64 nếu có và duy trì file projects.json siêu nhẹ (<150KB).
    """
    if not isinstance(projects_list, list):
        print(f"[DB Save Warning] projects_list không phải list: {type(projects_list)}")
        return

    with DB_LOCK:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            now_ms = int(time.time() * 1000)

            # Lưu từng project
            for p in projects_list:
                proj_id = p.get("id") or f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                cursor.execute("""
                    INSERT OR REPLACE INTO projects (id, name, description, token, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    proj_id,
                    p.get("name", "Dự án"),
                    p.get("description", ""),
                    p.get("token", f"BW-{uuid.uuid4().hex[:12].upper()}"),
                    p.get("createdAt", now_ms),
                    now_ms
                ))

                for s in p.get("subProjects", []):
                    sub_id = s.get("id") or f"sub_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                    cookies_json = json.dumps(s.get("cookies", []), ensure_ascii=False)
                    flow_children_json = json.dumps(s.get("flowChildProjects", []), ensure_ascii=False)
                    scraped_json = json.dumps(s.get("scrapedData", {}), ensure_ascii=False) if s.get("scrapedData") else ""

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
                        s.get("name", "Thư mục"),
                        s.get("type", "facebook"),
                        s.get("description", ""),
                        s.get("c_user") or s.get("uid", ""),
                        s.get("fbName") or s.get("accountName", ""),
                        s.get("avatar", ""),
                        s.get("profileUrl", ""),
                        s.get("cookieStr", ""),
                        cookies_json,
                        s.get("eaagToken", ""),
                        s.get("dtsg", ""),
                        s.get("googleEmail", ""),
                        s.get("googleUid", ""),
                        s.get("flowProjectId", ""),
                        s.get("flowProjectName", ""),
                        flow_children_json,
                        s.get("activeFlowChildId", ""),
                        scraped_json,
                        s.get("purpose", ""),
                        s.get("sourceUrl", ""),
                        s.get("sourceDomain", ""),
                        0,
                        s.get("status", "Chưa kiểm tra"),
                        s.get("lastExtracted", 0),
                        s.get("createdAt", now_ms),
                        now_ms
                    ))

                    # Lưu postQueue
                    for post in s.get("postQueue", []):
                        post_id = post.get("id") or f"post_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                        media_path = post.get("mediaFilePath") or ""

                        # Tách Base64 nếu phát hiện có Base64 mới gửi lên
                        media_data = post.get("mediaData")
                        if isinstance(media_data, dict) and media_data.get("base64"):
                            rel_p, web_u = save_uploaded_media(
                                media_data.get("base64"),
                                filename=media_data.get("fileName"),
                                mime_type=media_data.get("mimeType"),
                                prefix=f"post_{post_id}"
                            )
                            if rel_p:
                                media_path = rel_p
                                post["mediaUrl"] = web_u
                                post["mediaFilePath"] = rel_p
                                # Xóa Base64 khổng lồ để giải phóng RAM
                                media_data["base64"] = ""

                        seeding_comments_json = json.dumps(post.get("seedingComments", []), ensure_ascii=False)
                        seeding_ids_json = json.dumps(post.get("seedingIds", []), ensure_ascii=False)
                        seeding_details_json = json.dumps(post.get("seedingDetails", []), ensure_ascii=False)
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
                            seeding_comments_json,
                            post.get("autoReactType", "LIKE"),
                            post.get("status", "pending"),
                            post.get("progressStep", ""),
                            post.get("fbPostId", ""),
                            post.get("fbPostUrl", ""),
                            post.get("fbFeedbackId", ""),
                            seeding_ids_json,
                            seeding_details_json,
                            1 if post.get("shareToStorySuccess") else 0,
                            last_err,
                            post.get("callbackUrl", ""),
                            "",
                            post.get("purpose", ""),
                            post.get("sourceUrl", ""),
                            post.get("sourceDomain", ""),
                            post.get("scheduledTime", 0),
                            post.get("scheduledTimeStr", ""),
                            last_err,
                            post.get("createdAt", now_ms),
                            pub_ts,
                            pub_ts
                        ))

            cursor.execute("COMMIT;")
        except Exception as e:
            cursor.execute("ROLLBACK;")
            print(f"[DB Save Projects Error] {e}")

        # Đồng bộ ra file projects.json siêu nhẹ (đã bóc tách base64)
        try:
            _sync_lightweight_json(projects_list)
        except Exception as sync_e:
            print(f"[Sync JSON Warning] {sync_e}")

def _sync_lightweight_json(projects_list):
    """Lưu bản snapshot siêu nhẹ của projects.json làm backup dự phòng."""
    clean_list = []
    for p in projects_list:
        p_copy = {k: v for k, v in p.items() if k != "subProjects"}
        p_copy["subProjects"] = []
        for s in p.get("subProjects", []):
            s_copy = {k: v for k, v in s.items() if k not in ("postQueue", "imageQueue")}
            # Lọc bỏ base64 khỏi postQueue
            clean_posts = []
            for post in s.get("postQueue", []):
                post_copy = dict(post)
                if isinstance(post_copy.get("mediaData"), dict):
                    mData = dict(post_copy["mediaData"])
                    mData["base64"] = ""  # Loại bỏ chuỗi base64 khổng lồ
                    post_copy["mediaData"] = mData
                clean_posts.append(post_copy)
            s_copy["postQueue"] = clean_posts

            # Lọc bỏ base64 data URL khỏi imageQueue
            clean_images = []
            for fl in s.get("imageQueue", []):
                fl_copy = dict(fl)
                clean_imgs = []
                for img in fl_copy.get("images", []):
                    u = img.get("url", "")
                    if u.startswith("data:image"):
                        clean_imgs.append({"url": "/uploads/flow/image.jpg"})
                    else:
                        clean_imgs.append(img)
                fl_copy["images"] = clean_imgs
                clean_images.append(fl_copy)
            s_copy["imageQueue"] = clean_images
            p_copy["subProjects"].append(s_copy)
        clean_list.append(p_copy)

    tmp_path = JSON_PATH + f".tmp.{os.getpid()}_{uuid.uuid4().hex[:6]}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"projects": clean_list}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(tmp_path, JSON_PATH)
    except OSError:
        shutil.copyfile(tmp_path, JSON_PATH)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
