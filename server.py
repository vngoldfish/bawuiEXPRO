#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
⚡ BAWUI EXTENSION PRO — PYTHON CONTROLLER BACKEND
=============================================================
Cổng dịch vụ: 9999 (http://127.0.0.1:9999)
Kiến trúc 3 Tầng Dạng Thư Mục (Folder Hierarchy):
- Tầng 1 (Sảnh Ngoài): Quản lý Danh Sách Dự Án Cha (Mỗi Dự án = 1 Máy Chrome / Token).
- Tầng 2 (Trong Dự Án Cha): Quản lý các Thư Mục / Dự Án Con (Sub-Projects).
- Tầng 3 (Trong Dự Án Con):
  1. Menu đầu tiên: 👤 Kiểm Tra Thông Tin Tài Khoản Facebook (Quét UID, Tên, Avatar, Cookie, Token EAAG).
  2. Menu Cookie Facebook (Quản lý chuỗi cookie text & JSON).
  3. Menu Token Facebook EAAG.
  4. Menu Điều Khiển Tab Facebook.
  5. Menu JavaScript Console & Logs.
"""

import os
import sys
import re
import json
import time
import uuid
import platform
import random
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PORT = 9999
SERVER_START_TIME = time.time()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(BASE_DIR, "extension-auth-helper", "manifest.json")
CONFIG_PATH = os.path.join(BASE_DIR, "bridge_config.json")
PROJECTS_PATH = os.path.join(BASE_DIR, "projects.json")

def generate_project_token():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    rand_str = "".join(random.choice(chars) for _ in range(8))
    return f"BW-PROJ-{rand_str}"

def resolve_spintax(text):
    """Xử lý tự động spintax đa tầng {A|B|C} cho các bài viết gửi qua API"""
    if not text or "{" not in text or "}" not in text:
        return text or ""
    pattern = re.compile(r"\{([^{}]+)\}")
    for _ in range(10):
        if not pattern.search(text):
            break
        text = pattern.sub(lambda m: random.choice(m.group(1).split("|")), text)
    return text

def parse_scheduled_time(val):
    """
    Phân tích linh hoạt giá trị thời gian đặt lịch từ client/API.
    Hỗ trợ:
    - Số timestamp (giây hoặc mili-giây)
    - Chuỗi ISO 8601: '2026-09-24T15:30:00Z', '2026-09-24T15:30:00+07:00', '2026-09-24T15:30:00'
    - Chuỗi HTML5 datetime-local: '2026-09-24T15:30'
    - Chuỗi thông dụng: '2026-09-24 15:30:00', '2026-09-24 15:30'
    Trả về timestamp mili-giây (int) hoặc None nếu không hợp lệ / không có.
    """
    if not val:
        return None
    if isinstance(val, (int, float)):
        return int(val * 1000) if val < 10000000000 else int(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        if val.isdigit():
            v = int(val)
            return int(v * 1000) if v < 10000000000 else v
        clean_val = val.replace("Z", "+00:00")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M"
        ):
            try:
                dt = datetime.strptime(clean_val, fmt)
                if dt.tzinfo is not None:
                    return int(dt.timestamp() * 1000)
                else:
                    return int(dt.astimezone().timestamp() * 1000)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is not None:
                return int(dt.timestamp() * 1000)
            else:
                return int(dt.astimezone().timestamp() * 1000)
        except Exception:
            pass
    return None

def format_scheduled_time(ms):
    """Định dạng timestamp mili-giây sang chuỗi hiển thị 'HH:mm:ss dd/MM/yyyy'"""
    if not ms or ms <= 0:
        return ""
    try:
        dt = datetime.fromtimestamp(ms / 1000.0)
        return dt.strftime("%H:%M:%S %d/%m/%Y")
    except Exception:
        return ""

PROJECTS_LOCK = threading.RLock()

def get_projects():
    with PROJECTS_LOCK:
        if os.path.exists(PROJECTS_PATH):
            try:
                with open(PROJECTS_PATH, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        projs = []
                        if isinstance(data, list):
                            projs = data
                        elif isinstance(data, dict) and "projects" in data:
                            projs = data["projects"]

                        modified = False
                        for p in projs:
                            if "subProjects" not in p or not isinstance(p["subProjects"], list):
                                p["subProjects"] = [
                                    {
                                        "id": f"sub_fb_{int(time.time())}_{uuid.uuid4().hex[:4]}",
                                        "name": "Dự Án Facebook 01",
                                        "type": "facebook",
                                        "description": "Thư mục quản lý cookie & tài khoản Facebook",
                                        "c_user": "",
                                        "fbName": "",
                                        "avatar": "",
                                        "profileUrl": "",
                                        "cookieStr": "",
                                        "cookies": [],
                                        "eaagToken": "",
                                        "dtsg": "",
                                        "status": "Chưa kiểm tra",
                                        "lastExtracted": 0,
                                        "createdAt": int(time.time() * 1000)
                                    }
                                ]
                                modified = True
                        if modified:
                            save_projects(projs)
                        return projs
            except Exception as e:
                print(f"[Projects Error] {e}")

        default_proj = [
            {
                "id": "proj_main",
                "name": "Dự Án Mặc Định (Máy Chrome 01)",
                "description": "Quản lý máy Chrome và các thư mục dự án con",
                "token": "BW-PROJ-MAIN9999",
                "createdAt": int(time.time() * 1000),
                "subProjects": [
                    {
                        "id": f"sub_fb_{int(time.time())}_init",
                        "name": "Dự Án Facebook 01",
                        "type": "facebook",
                        "description": "Thư mục quản lý cookie & tài khoản Facebook",
                        "c_user": "",
                        "fbName": "",
                        "avatar": "",
                        "profileUrl": "",
                        "cookieStr": "",
                        "cookies": [],
                        "eaagToken": "",
                        "dtsg": "",
                        "status": "Chưa kiểm tra",
                        "lastExtracted": 0,
                        "createdAt": int(time.time() * 1000)
                    }
                ]
            }
        ]
        save_projects(default_proj)
        return default_proj

def save_projects(projects_list):
    with PROJECTS_LOCK:
        try:
            tmp_path = PROJECTS_PATH + f".tmp.{os.getpid()}_{uuid.uuid4().hex[:6]}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"projects": projects_list}, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, PROJECTS_PATH)
        except Exception as e:
            print(f"[Save Projects Error] {e}")

def find_project_by_token(token):
    if not token:
        return None
    token_clean = token.strip()
    for proj in get_projects():
        if proj.get("token") and proj.get("token").strip() == token_clean:
            return proj
    return None

def find_project_by_id(proj_id):
    if not proj_id:
        return None
    for proj in get_projects():
        if proj.get("id") == proj_id:
            return proj
    return None

def find_subproject(proj_id, sub_id):
    proj = find_project_by_id(proj_id)
    if not proj:
        return None, None
    for sub in proj.get("subProjects", []):
        if sub.get("id") == sub_id:
            return proj, sub
    return proj, None

def get_server_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"authToken": ""}

def save_server_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# In-memory storage
connected_nodes = {}
pending_commands = []
recent_issued_commands = {}
pending_extension_reloads = set()
live_logs = []
latest_project_results = {}

def push_log(message, log_type="", project_id=None, subproject_id=None):
    live_logs.append({
        "time": int(time.time() * 1000),
        "message": message,
        "type": log_type,
        "projectId": project_id,
        "subProjectId": subproject_id
    })
    if len(live_logs) > 300:
        live_logs.pop(0)

def create_post_entry(proj_id=None, sub_id=None, post_data=None, run_now=False, source="dashboard", token=None):
    """
    Tạo hoặc lên lịch bài viết mới theo chuẩn REST API.
    Hỗ trợ: Đăng ngay (run_now=True), Lên lịch (scheduledAt / scheduledTime), hoặc Lưu nháp (pending).
    Trả về tuple: (status_code, response_dict)
    """
    if post_data is None:
        post_data = {}

    all_projs = get_projects()
    target_proj = None

    if token:
        token_clean = token.strip()
        for p in all_projs:
            if p.get("token") and p.get("token").strip() == token_clean:
                target_proj = p
                break
        if not target_proj:
            return (401, {
                "success": False,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Token dự án không hợp lệ hoặc không tồn tại!"
                }
            })
    elif proj_id:
        for p in all_projs:
            if p.get("id") == proj_id:
                target_proj = p
                break
    else:
        if len(all_projs) == 1:
            target_proj = all_projs[0]

    if not target_proj:
        return (404, {
            "success": False,
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Không tìm thấy dự án tương ứng"
            }
        })

    target_sub = None
    subs = target_proj.get("subProjects", [])
    if sub_id:
        for s in subs:
            if s.get("id") == sub_id:
                target_sub = s
                break
    else:
        for s in subs:
            if s.get("type", "facebook") == "facebook":
                target_sub = s
                break
        if not target_sub and len(subs) > 0:
            target_sub = subs[0]

    if not target_sub:
        return (404, {
            "success": False,
            "error": {
                "code": "SUBPROJECT_NOT_FOUND",
                "message": f"Dự án '{target_proj.get('name')}' chưa có tài khoản Facebook / thư mục con nào"
            }
        })

    raw_content = post_data.get("content", "")
    media_url = (post_data.get("mediaUrl") or "").strip()
    media_data = post_data.get("mediaData")

    if not raw_content and not media_url and not media_data and not post_data.get("title"):
        return (400, {
            "success": False,
            "error": {
                "code": "MISSING_CONTENT",
                "message": "Vui lòng nhập nội dung bài viết ('content') hoặc đính kèm tệp media ('mediaUrl')!"
            }
        })

    content = resolve_spintax(raw_content)

    post_type = str(post_data.get("postType", "post")).lower()
    if post_type not in ("post", "reel", "video", "story"):
        post_type = "post"

    target_type = str(post_data.get("targetType", "profile")).lower()
    if target_type not in ("profile", "page", "group"):
        target_type = "profile"

    target_id = str(post_data.get("targetId", "")).strip()
    if target_type in ("page", "group") and not target_id:
        return (400, {
            "success": False,
            "error": {
                "code": "MISSING_TARGET_ID",
                "message": f"Khi đăng bài lên {target_type.upper()}, bắt buộc phải cung cấp 'targetId' (ID Fanpage hoặc ID Nhóm)!"
            }
        })

    raw_seeding = post_data.get("seedingComments", [])
    seeding_comments = []
    if isinstance(raw_seeding, str):
        seeding_comments = [c.strip() for c in raw_seeding.split("\n") if c.strip()]
    elif isinstance(raw_seeding, list):
        seeding_comments = [str(c).strip() for c in raw_seeding if str(c).strip()]

    auto_react = str(post_data.get("autoReactType") or "LIKE").upper()
    if auto_react not in ("LIKE", "LOVE", "CARE", "HAHA", "WOW", "SAD", "ANGRY", "NONE"):
        auto_react = "LIKE"

    share_to_feed_raw = post_data.get("shareToFeed")
    if share_to_feed_raw is None:
        share_to_feed_raw = post_data.get("shareToStory")
    share_to_feed = True if share_to_feed_raw is None else bool(share_to_feed_raw)

    # Xử lý Đặt Giờ Đăng (Post Scheduling)
    sched_val = post_data.get("scheduledAt") or post_data.get("scheduledTime")
    sched_ms = parse_scheduled_time(sched_val)
    now_ms = int(time.time() * 1000)

    is_scheduled = False
    if sched_ms:
        if sched_ms > now_ms:
            is_scheduled = True
            run_now = False
        else:
            if not run_now:
                return (422, {
                    "success": False,
                    "error": {
                        "code": "INVALID_SCHEDULE_TIME",
                        "message": "Thời gian đặt lịch phải ở thời điểm tương lai!"
                    }
                })

    if "postQueue" not in target_sub:
        target_sub["postQueue"] = []

    post_id = f"post_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    scheduled_iso = datetime.fromtimestamp(sched_ms / 1000.0, tz=timezone.utc).isoformat() if sched_ms else ""

    if is_scheduled:
        status = "scheduled"
        formatted_sched = format_scheduled_time(sched_ms)
        progress_step = f"⏳ Đã lên lịch đăng lúc {formatted_sched}"
    elif run_now:
        status = "in_progress"
        progress_step = "Đang chuyển lệnh sang Extension..."
    else:
        status = "pending"
        progress_step = "Đã lưu vào hàng đợi (chờ phát lệnh)"

    post_entry = {
        "id": post_id,
        "title": post_data.get("title", ""),
        "content": content,
        "postType": post_type,
        "targetType": target_type,
        "targetId": target_id,
        "targetUrl": post_data.get("targetUrl") or "https://www.facebook.com",
        "shareToFeed": share_to_feed,
        "mediaUrl": media_url,
        "mediaData": media_data,
        "seedingComments": seeding_comments,
        "autoReactType": auto_react,
        "status": status,
        "progressStep": progress_step,
        "fbPostId": "",
        "fbPostUrl": "",
        "scheduledTime": sched_ms if is_scheduled else 0,
        "scheduledTimeStr": format_scheduled_time(sched_ms) if is_scheduled else "",
        "scheduledAt": scheduled_iso if is_scheduled else "",
        "lastError": "",
        "createdAt": now_ms,
        "callbackUrl": post_data.get("callbackUrl", ""),
        "source": source
    }

    target_sub["postQueue"].insert(0, post_entry)
    save_projects(all_projs)

    cmd_id = None
    if run_now and status == "in_progress":
        cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        cmd = {
            "id": cmd_id,
            "action": "POST_STORY",
            "targetProjectId": target_proj["id"],
            "targetSubProjectId": target_sub["id"],
            "targetNodeId": "*",
            "post": post_entry
        }
        pending_commands.append(cmd)
        recent_issued_commands[cmd_id] = cmd
        push_log(f"Đã phát lệnh đăng ngay bài viết '{post_id}' lên Facebook cho '{target_sub['name']}'", "step", project_id=target_proj["id"], subproject_id=target_sub["id"])
    elif is_scheduled:
        push_log(f"⏰ Đã lên lịch đăng bài '{post_entry['title'] or post_id}' vào lúc {format_scheduled_time(sched_ms)} cho '{target_sub['name']}'", "step", project_id=target_proj["id"], subproject_id=target_sub["id"])
    else:
        push_log(f"Đã thêm bài viết mới vào hàng đợi của '{target_sub['name']}'", "success", project_id=target_proj["id"], subproject_id=target_sub["id"])

    msg = f"Đã lên lịch đăng bài thành công vào lúc {format_scheduled_time(sched_ms)}" if is_scheduled else ("Đã phát lệnh đăng ngay sang Extension!" if run_now else "Đã thêm bài viết vào hàng đợi đăng!")

    response_payload = {
        "success": True,
        "message": msg,
        "data": post_entry,
        "post": post_entry,
        "postId": post_id,
        "cmdId": cmd_id,
        "status": status,
        "targetAccount": {
            "projectId": target_proj["id"],
            "projectName": target_proj["name"],
            "subProjectId": target_sub["id"],
            "subProjectName": target_sub["name"],
            "c_user": target_sub.get("c_user", ""),
            "fbName": target_sub.get("fbName", "")
        }
    }
    return (201 if is_scheduled or not run_now else 200, response_payload)

def start_post_scheduler():
    """Bộ máy lập lịch chạy ngầm quét hàng đợi bài viết mỗi 10 giây"""
    def _scheduler_loop():
        while True:
            try:
                now_ms = int(time.time() * 1000)
                projs = get_projects()
                modified = False
                for p in projs:
                    proj_id = p.get("id")
                    for s in p.get("subProjects", []):
                        sub_id = s.get("id")
                        for post in s.get("postQueue", []):
                            if post.get("status") == "scheduled":
                                sched_time = post.get("scheduledTime", 0)
                                if sched_time and sched_time <= now_ms:
                                    post["status"] = "in_progress"
                                    post["progressStep"] = "⏰ Đến giờ hẹn! Đang chuyển lệnh đăng sang Extension..."
                                    modified = True
                                    cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                                    cmd = {
                                        "id": cmd_id,
                                        "action": "POST_STORY",
                                        "targetProjectId": proj_id,
                                        "targetSubProjectId": sub_id,
                                        "targetNodeId": "*",
                                        "post": post
                                    }
                                    pending_commands.append(cmd)
                                    recent_issued_commands[cmd_id] = cmd
                                    post_title = post.get("title") or post.get("id")
                                    push_log(f"⏰ ĐẾN GIỜ HẸN: Tự động kích hoạt đăng bài '{post_title}' lên Facebook cho '{s.get('name')}'", "success", project_id=proj_id, subproject_id=sub_id)
                if modified:
                    save_projects(projs)
            except Exception as e:
                print(f"[Scheduler Error] {e}")
            time.sleep(10)

    sched_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="PostSchedulerThread")
    sched_thread.start()
    print("[*] POST SCHEDULER STARTED (interval: 10s)")

def read_manifest_info():
    try:
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "name": data.get("name", "⚡ BAWUI EXTENSION PRO"),
                    "description": data.get("description", ""),
                    "version": data.get("version", "1.0.0")
                }
    except Exception as e:
        print(f"[Manifest Error] {e}")
    return {
        "name": "⚡ BAWUI EXTENSION PRO",
        "description": "⚡ BAWUI EXTENSION PRO — Cầu nối trực tiếp và đồng bộ lệnh giữa Backend Server và Trình duyệt Chrome.",
        "version": "1.0.0"
    }

def update_manifest_info(name, description, version=None):
    try:
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            data["name"] = name.strip()
            data["description"] = description.strip()
            if version:
                data["version"] = version.strip()

            with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            push_log(f"Cập nhật Manifest thành công: '{name}'", "success")
            return True, "Cập nhật thành công!"
    except Exception as e:
        push_log(f"Lỗi ghi file manifest.json: {e}", "warn")
        return False, str(e)
    return False, "Không tìm thấy file manifest.json"

def resolve_fb_profile_data(cookie_str, c_user=""):
    import urllib.request
    import re
    result = {"name": "", "avatar": "", "profileUrl": ""}
    if not cookie_str and not c_user:
        return result

    if cookie_str:
        try:
            req = urllib.request.Request(
                'https://www.facebook.com/me',
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Cookie': cookie_str,
                    'Sec-Fetch-Site': 'none'
                }
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                final_url = res.geturl()
                if final_url and 'facebook.com' in final_url and '/me' not in final_url:
                    result['profileUrl'] = final_url
                html = res.read().decode('utf-8', errors='replace')
                names = re.findall(r'"NAME":"([^"]+)"', html)
                if names:
                    result['name'] = names[0]
                pics = re.findall(r'"profile_picture":\{"uri":"([^"]+)"', html)
                if pics:
                    result['avatar'] = pics[0].replace('\\/', '/')
        except Exception as e:
            print(f"[Resolve FB Profile Error] {e}")

    if not result['avatar'] and c_user:
        try:
            g_req = urllib.request.Request(f'https://graph.facebook.com/{c_user}/picture?type=large', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(g_req, timeout=4) as g_res:
                direct = g_res.geturl()
                if direct and 'fbcdn.net' in direct:
                    result['avatar'] = direct
        except Exception:
            pass
    return result


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ BAWUI EXTENSION PRO — Multi-Folder Controller</title>
    <style>
        :root {
            --bg-body: #070b14;
            --bg-sidebar: #0f172a;
            --bg-header: #0f172a;
            --bg-card: #131d33;
            --bg-card-hover: #182542;
            --border-color: #202d46;
            --primary: #0284c7;
            --primary-hover: #0369a1;
            --accent: #38bdf8;
            --accent-purple: #a855f7;
            --accent-green: #10b981;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --sidebar-width: 260px;
            --header-height: 64px;
            --footer-height: 44px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-body);
            color: var(--text-main);
            overflow-x: hidden;
            display: flex;
            height: 100vh;
        }

        /* SIDEBAR */
        aside.sidebar {
            width: var(--sidebar-width);
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            z-index: 20;
            overflow-y: auto;
        }

        .sidebar-brand {
            height: var(--header-height);
            display: flex;
            align-items: center;
            padding: 0 18px;
            gap: 12px;
            border-bottom: 1px solid var(--border-color);
            text-decoration: none;
            color: var(--text-main);
            cursor: pointer;
        }

        .sidebar-brand-icon {
            font-size: 20px;
            background: linear-gradient(135deg, #0284c7, #8b5cf6);
            border-radius: 8px;
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 15px rgba(2, 132, 199, 0.4);
            flex-shrink: 0;
        }

        .sidebar-brand-title {
            font-size: 13px;
            font-weight: 800;
            letter-spacing: -0.2px;
            color: #fff;
            line-height: 1.25;
        }
        .sidebar-brand-title span {
            color: var(--accent);
            font-size: 11px;
            display: block;
            font-weight: 600;
        }

        .sidebar-menu {
            list-style: none;
            padding: 12px 8px;
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .menu-label {
            font-size: 10px;
            font-weight: 800;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            padding: 14px 12px 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .menu-item {
            position: relative;
        }

        .menu-item a, .menu-item button {
            width: 100%;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            border-radius: 8px;
            color: #94a3b8;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.15s ease-in-out;
            background: transparent;
            border: 1px solid transparent;
            border-left: 3px solid transparent; /* ĐẢM BẢO KHÔNG BỊ NHẢY THỤT LỀ KHI ACTIVE */
            text-align: left;
            cursor: pointer;
            box-sizing: border-box;
        }

        /* KHUNG CHỨA ICON CỐ ĐỊNH KÍCH THƯỚC GIÚP MỌI CHỮ THẲNG HÀNG 100% TUYỆT ĐỐI */
        .menu-item .nav-icon,
        .menu-item > a > span:first-child,
        .menu-item > button > span:first-child {
            width: 22px;
            min-width: 22px;
            height: 22px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 15px;
            line-height: 1;
            text-align: center;
            flex-shrink: 0;
        }

        .menu-item .menu-title {
            flex: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .menu-item a:hover, .menu-item button:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #f1f5f9;
        }

        .menu-item.active > a, .menu-item.active > button {
            background: rgba(2, 132, 199, 0.18);
            color: #38bdf8;
            border-left: 3px solid #38bdf8;
            border-radius: 4px 8px 8px 4px;
            font-weight: 700;
        }

        /* MỤC CHA ACCORDION (POST FACEBOOK) */
        .menu-item.menu-parent > button {
            color: #e2e8f0;
            font-weight: 700;
        }
        .menu-item.menu-parent.expanded > button {
            color: #fff;
            background: rgba(255, 255, 255, 0.04);
        }
        .menu-item.menu-parent.active-parent > button {
            background: rgba(2, 132, 199, 0.12);
            color: #38bdf8;
            border-left: 3px solid rgba(56, 189, 248, 0.5);
        }
        .menu-chevron {
            font-size: 9px;
            color: #64748b;
            transition: transform 0.2s ease;
            margin-left: auto;
            flex-shrink: 0;
        }
        .menu-item.menu-parent.expanded .menu-chevron {
            transform: rotate(180deg);
            color: #38bdf8;
        }

        /* CÂY MENU CON THỤT LỀ CHUẨN (NESTED TREE) */
        .menu-sub-tree {
            display: flex;
            flex-direction: column;
            gap: 2px;
            margin-left: 18px;
            padding-left: 8px;
            border-left: 2px solid #1e293b;
            margin-top: 2px;
            margin-bottom: 4px;
        }
        .menu-sub-tree.collapsed {
            display: none;
        }
        .menu-sub-item a, .menu-sub-item button {
            padding: 7px 10px;
            font-size: 12.5px;
            gap: 8px;
            border-radius: 6px;
        }
        .menu-sub-item .nav-icon {
            width: 18px;
            min-width: 18px;
            height: 18px;
            font-size: 13px;
        }
        .menu-sub-item.active a, .menu-sub-item.active button {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border-left: 3px solid #38bdf8;
        }

        /* SIDEBAR CARD BANNERS */
        .sidebar-context-card {
            background: linear-gradient(180deg, #161a33 0%, #0d1222 100%);
            border: 1px solid rgba(139, 92, 246, 0.35);
            border-radius: 10px;
            padding: 12px;
            margin: 12px 10px 6px;
        }
        .btn-nav-back {
            width: 100%;
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            padding: 7px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: 0.15s;
            margin-bottom: 10px;
        }
        .btn-nav-back:hover {
            background: #334155;
            color: #fff;
            border-color: var(--accent);
        }

        .type-card-option, .purpose-card-option, .source-card-option {
            background: #0f172a;
            border: 2px solid #1e293b;
            border-radius: 10px;
            padding: 12px 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }
        .type-card-option:hover, .purpose-card-option:hover, .source-card-option:hover {
            border-color: #38bdf8;
            background: #152238;
        }
        .type-card-option.active, .source-card-option.active {
            border-color: #38bdf8;
            background: linear-gradient(135deg, #0c2340 0%, #15325b 100%);
            box-shadow: 0 0 14px rgba(56, 189, 248, 0.25);
        }
        .purpose-card-option.active {
            border-color: #a855f7;
            background: linear-gradient(135deg, #2e1065 0%, #3b0764 100%);
            box-shadow: 0 0 14px rgba(168, 85, 247, 0.35);
        }

        .sidebar-footer-info {
            padding: 12px 16px;
            border-top: 1px solid var(--border-color);
            background: rgba(0, 0, 0, 0.25);
            font-size: 11px;
            color: var(--text-muted);
            margin-top: auto;
        }

        /* MAIN WRAPPER */
        .main-wrapper {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: var(--bg-body);
        }

        /* HEADER */
        header.top-header {
            height: var(--header-height);
            background: var(--bg-header);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            z-index: 10;
        }

        .header-title-box {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .header-page-title {
            font-size: 14px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            background: #151f33;
            border: 1px solid var(--border-color);
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--danger); }
        .dot.online { background: var(--success); box-shadow: 0 0 10px var(--success); }
        
        .port-badge {
            background: rgba(56, 189, 248, 0.12);
            color: var(--accent);
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            font-family: monospace;
        }

        /* CONTENT VIEWPORT */
        main.content-area {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }

        /* ROUTE VIEWS */
        .route-view {
            display: none;
            animation: fadeIn 0.15s ease-in-out;
        }
        .route-view.active {
            display: block;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* FOOTER */
        footer.bottom-footer {
            height: var(--footer-height);
            background: var(--bg-header);
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            font-size: 12px;
            color: var(--text-muted);
            flex-shrink: 0;
        }

        /* CARDS & UI COMPONENTS */
        .grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
            transition: all 0.2s;
        }
        .card:hover {
            border-color: rgba(56, 189, 248, 0.35);
        }
        .card-title {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        .card-value {
            font-size: 22px;
            font-weight: 800;
            color: #fff;
        }
        .card-sub {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* BUTTONS */
        button, .btn {
            background: var(--primary);
            color: #fff;
            border: none;
            padding: 8px 15px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            text-decoration: none;
        }
        button:hover, .btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
        .btn-green { background: #059669; }
        .btn-green:hover { background: #047857; }
        .btn-purple { background: #7c3aed; }
        .btn-purple:hover { background: #6d28d9; }
        .btn-orange { background: #ea580c; }
        .btn-orange:hover { background: #c2410c; }
        .btn-danger { background: #dc2626; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 6px; }
        .btn-lg { padding: 11px 20px; font-size: 14px; font-weight: 700; border-radius: 10px; }

        .btn-enter-card {
            background: linear-gradient(135deg, #0284c7 0%, #7c3aed 100%);
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4);
            color: #fff;
            font-size: 14px;
            font-weight: 800;
            padding: 10px 18px;
            border-radius: 8px;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-enter-card:hover {
            box-shadow: 0 6px 22px rgba(124, 58, 237, 0.6);
            transform: translateY(-2px);
        }

        input, textarea, select {
            width: 100%;
            background: #090e1c;
            border: 1px solid var(--border-color);
            color: #fff;
            padding: 9px 12px;
            border-radius: 8px;
            font-size: 13px;
            margin-top: 5px;
            margin-bottom: 12px;
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus, textarea:focus, select:focus {
            border-color: var(--accent);
        }

        /* FOLDER CARD STYLES */
        .folder-card {
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
            cursor: pointer;
            position: relative;
        }
        .folder-card:hover {
            border-color: #38bdf8;
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .folder-icon-box {
            font-size: 32px;
            margin-bottom: 10px;
        }
        .badge-folder {
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
            font-size: 10px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .raw-data-box {
            background: #050811;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 12px;
            font-family: Consolas, monospace;
            font-size: 12px;
            color: #38bdf8;
            max-height: 200px;
            overflow-y: auto;
            word-break: break-all;
            white-space: pre-wrap;
            user-select: all;
        }

        .log-container {
            background: #050811;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 12px;
            max-height: 380px;
            overflow-y: auto;
            color: #94a3b8;
        }
        .log-line { margin-bottom: 6px; word-break: break-all; }
        .log-success { color: #34d399; }
        .log-step { color: #38bdf8; }
        .log-warn { color: #fbbf24; }
        .log-err { color: #f87171; }

        .preset-chip {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border-color);
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 12px;
            color: var(--text-muted);
            cursor: pointer;
            transition: 0.15s;
        }
        .preset-chip:hover {
            background: rgba(56, 189, 248, 0.15);
            border-color: var(--accent);
            color: #fff;
        }

        /* POST STUDIO & SEEDING STYLES (FROM AUTOFB) */
        .type-pill-btn, .target-pill-btn {
            padding: 10px 14px;
            border-radius: 12px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            cursor: pointer;
            font-family: inherit;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            user-select: none;
        }
        .type-pill-btn:hover, .target-pill-btn:hover {
            color: #fff;
            border-color: rgba(56, 189, 248, 0.4);
            background: rgba(56, 189, 248, 0.1);
        }
        .type-pill-btn.active {
            color: #fff;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(168, 85, 247, 0.25));
            border: 1px solid #38bdf8;
            box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
        }
        .target-pill-btn.active {
            color: #fff;
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(56, 189, 248, 0.25));
            border: 1px solid #10b981;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.25);
        }
        .dropzone {
            padding: 18px;
            border: 2px dashed rgba(56, 189, 248, 0.4);
            border-radius: 12px;
            text-align: center;
            cursor: pointer;
            background: rgba(0, 0, 0, 0.25);
            transition: all 0.25s;
        }
        .dropzone:hover {
            border-color: #38bdf8;
            background: rgba(56, 189, 248, 0.05);
        }
        .smart-post-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 14px;
            transition: all 0.2s;
        }
        .smart-post-card:hover {
            border-color: rgba(56, 189, 248, 0.4);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        .pulse-spinner {
            width: 14px;
            height: 14px;
            border: 2px solid rgba(56, 189, 248, 0.3);
            border-top-color: #38bdf8;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(4px);
            z-index: 9999;
            display: none;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal-box {
            background: #0d1527;
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 16px;
            width: 90%;
            max-width: 580px;
            padding: 24px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7);
            animation: fadeIn 0.2s ease;
        }
        /* ============================================================= */
        /* MOBILE RESPONSIVE: HAMBURGER, SIDEBAR DRAWER, MEDIA QUERIES   */
        /* ============================================================= */

        /* Hamburger Menu Button (hidden on desktop) */
        .hamburger-btn {
            display: none;
            background: transparent;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 22px;
            width: 40px;
            height: 40px;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
            transition: background 0.15s;
        }
        .hamburger-btn:hover {
            background: rgba(255,255,255,0.08);
        }

        /* Sidebar Overlay (dark backdrop when sidebar open on mobile) */
        .sidebar-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(2px);
            z-index: 19;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .sidebar-overlay.active {
            display: block;
            opacity: 1;
        }

        /* ===== TABLET & MOBILE: max-width 768px ===== */
        @media (max-width: 768px) {
            /* Sidebar → fixed drawer, hidden by default */
            aside.sidebar {
                position: fixed;
                top: 0; left: 0;
                height: 100vh;
                width: 280px;
                transform: translateX(-100%);
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 100;
                box-shadow: none;
            }
            body.sidebar-open aside.sidebar {
                transform: translateX(0);
                box-shadow: 4px 0 30px rgba(0, 0, 0, 0.5);
            }
            body.sidebar-open .sidebar-overlay {
                display: block;
                opacity: 1;
            }

            /* Show hamburger button */
            .hamburger-btn {
                display: inline-flex;
            }

            /* Header adjustments */
            header.top-header {
                padding: 0 12px;
                gap: 8px;
            }
            .header-title-box {
                gap: 8px;
                min-width: 0;
                flex: 1;
            }
            .header-page-title {
                font-size: 13px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                min-width: 0;
            }
            .header-actions {
                gap: 6px;
                flex-shrink: 0;
            }
            /* Hide PORT badge and status text on mobile */
            .port-badge {
                display: none;
            }
            .status-pill span:not(.dot) {
                display: none;
            }
            .status-pill {
                padding: 5px 8px;
                min-width: 28px;
            }

            /* Content area → reduce padding */
            main.content-area {
                padding: 12px;
            }

            /* All 2-column grids → stack to 1 column */
            .grid-responsive {
                grid-template-columns: 1fr !important;
            }
            .grid-responsive-sm {
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)) !important;
            }

            /* Card padding reduction */
            .card {
                padding: 14px;
            }

            /* POST FACEBOOK quick-switch toolbar → horizontal scroll */
            .post-fb-toolbar {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                flex-wrap: nowrap !important;
                gap: 6px !important;
                padding-bottom: 4px;
            }
            .post-fb-toolbar::-webkit-scrollbar { display: none; }
            .post-fb-toolbar .btn-sm {
                white-space: nowrap;
                flex-shrink: 0;
                font-size: 11px !important;
                padding: 5px 10px !important;
            }

            /* Filter tabs → horizontal scroll */
            .filter-tabs-row {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                flex-wrap: nowrap !important;
                padding-bottom: 4px;
            }
            .filter-tabs-row::-webkit-scrollbar { display: none; }
            .filter-tabs-row .btn-sm,
            .filter-tabs-row button {
                white-space: nowrap;
                flex-shrink: 0;
            }

            /* Search bar → full width */
            .mobile-full-width {
                min-width: 100% !important;
                width: 100% !important;
            }

            /* Button groups → wrap and full width */
            .btn-group-responsive {
                flex-direction: column !important;
                width: 100%;
            }
            .btn-group-responsive > button,
            .btn-group-responsive > .btn,
            .btn-group-responsive > .btn-green,
            .btn-group-responsive > .btn-sm {
                width: 100% !important;
            }

            /* Modal adjustments */
            .modal-box {
                width: 95%;
                max-width: none;
                padding: 16px;
                max-height: 90vh;
                overflow-y: auto;
            }

            /* Touch-friendly: larger tap targets */
            .menu-item a, .menu-item button {
                padding: 12px 12px;
                min-height: 44px;
            }
            .btn-sm {
                padding: 8px 14px;
                min-height: 36px;
            }
            button, select, input, textarea {
                min-height: 38px;
                font-size: 14px;
            }

            /* Tables → scrollable container */
            table {
                display: block;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            thead, tbody, tr {
                display: revert;
            }

            /* Footer adjustments */
            footer.bottom-footer {
                padding: 0 12px;
                font-size: 11px;
            }

            /* Section titles */
            h2 { font-size: 16px !important; }

            /* Info grids within cards */
            .info-grid-responsive {
                grid-template-columns: 1fr !important;
            }

            /* Smaller badge font */
            .badge-folder {
                font-size: 10px;
                padding: 2px 8px;
            }
        }

        /* ===== SMALL PHONE: max-width 480px ===== */
        @media (max-width: 480px) {
            /* Even more compact header */
            header.top-header {
                height: 52px;
                padding: 0 8px;
            }
            .header-page-title {
                font-size: 12px;
            }
            .hamburger-btn {
                width: 36px;
                height: 36px;
                font-size: 20px;
            }

            /* Even tighter content padding */
            main.content-area {
                padding: 8px;
            }

            /* Card compact mode */
            .card {
                padding: 10px;
                border-radius: 10px;
            }

            /* Smaller sidebar on very small phones */
            aside.sidebar {
                width: 260px;
            }

            /* Stack action buttons vertically */
            .header-actions .btn-sm {
                font-size: 11px;
                padding: 4px 8px;
            }

            /* KPI stat cards */
            .grid-responsive-sm {
                grid-template-columns: 1fr 1fr !important;
            }

            /* Font size floors */
            p, span, div, label {
                /* Ensure minimum readable size on small screens */
            }
            .sidebar-brand-title {
                font-size: 12px;
            }

            /* Full-width buttons */
            .btn-green.btn-lg,
            .btn-orange.btn-lg {
                width: 100%;
                font-size: 13px;
            }
        }
    </style>
</head>
<body>
    <!-- 1. SIDEBAR MENU -->
    <aside class="sidebar">
        <!-- BRAND LOGO -->
        <div class="sidebar-brand" onclick="exitToHub()">
            <div class="sidebar-brand-icon">⚡</div>
            <div class="sidebar-brand-title">
                BAWUI EXTENSION
                <span>PRO CONTROLLER</span>
            </div>
        </div>

        <!-- 1A. SIDEBAR: TẦNG 1 (SẢNH NGOÀI - HUB) -->
        <div id="sidebar-hub-nav">
            <ul class="sidebar-menu">
                <li class="menu-label">Sảnh Quản Trị Hệ Thống</li>
                <li class="menu-item active" data-hub-route="hub-projects">
                    <button onclick="switchHubRoute('hub-projects')">
                        <span class="nav-icon">📁</span>
                        <span class="menu-title">Danh Sách Dự Án</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-api">
                    <button onclick="switchHubRoute('hub-api')">
                        <span class="nav-icon">🔌</span>
                        <span class="menu-title">Tài Liệu API & Webhook</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-vps">
                    <button onclick="switchHubRoute('hub-vps')">
                        <span class="nav-icon">☁️</span>
                        <span class="menu-title">Cài Đặt VPS & Hướng Dẫn</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-manifest">
                    <button onclick="switchHubRoute('hub-manifest')">
                        <span class="nav-icon">⚙️</span>
                        <span class="menu-title">Đổi Tên & Cấu Hình Extension</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-system">
                    <button onclick="switchHubRoute('hub-system')">
                        <span class="nav-icon">ℹ️</span>
                        <span class="menu-title">Thông Tin Hệ Thống</span>
                    </button>
                </li>
            </ul>
        </div>

        <!-- 1B. SIDEBAR: TẦNG 2 (TRONG DỰ ÁN CHA - FOLDER MANAGER) -->
        <div id="sidebar-parent-nav" style="display:none;">
            <div class="sidebar-context-card">
                <button class="btn-nav-back" onclick="exitToHub()">
                    <span class="nav-icon">⬅️</span>
                    <span>Thoát Về Sảnh Ngoài</span>
                </button>
                <div style="font-size:10px; color:#a78bfa; font-weight:700; text-transform:uppercase;">Dự Án Cha (Máy Chrome):</div>
                <div style="font-size:13px; font-weight:800; color:#fff; margin-top:2px; line-height:1.3;" id="sidebarParentName">Dự án</div>
                <div style="font-size:11px; color:#38bdf8; font-family:monospace; margin-top:4px;" id="sidebarParentToken">BW-PROJ-XXXX</div>
                <div style="margin-top:8px; display:flex; align-items:center; gap:6px;">
                    <span class="dot" id="sidebarParentDot"></span>
                    <span style="font-size:11px; font-weight:600;" id="sidebarParentMachineStatus">Chờ máy...</span>
                </div>
            </div>

            <ul class="sidebar-menu">
                <li class="menu-label">Quản Lý Thư Mục Con</li>
                <li class="menu-item active" data-parent-route="parent-subprojects">
                    <button onclick="switchParentRoute('parent-subprojects')">
                        <span class="nav-icon">📂</span>
                        <span class="menu-title">Danh Sách Dự Án Con</span>
                    </button>
                </li>
                <li class="menu-label">Máy & Trình Duyệt</li>
                <li class="menu-item" data-parent-route="parent-machine">
                    <button onclick="switchParentRoute('parent-machine')">
                        <span class="nav-icon">🖥️</span>
                        <span class="menu-title">Thông Tin Máy & Chrome</span>
                    </button>
                </li>
                <li class="menu-item" data-parent-route="parent-logs">
                    <button onclick="switchParentRoute('parent-logs')">
                        <span class="nav-icon">📜</span>
                        <span class="menu-title">Nhật Ký Máy (Logs)</span>
                    </button>
                </li>
            </ul>
        </div>

        <!-- 1C. SIDEBAR: TẦNG 3 (TRONG DỰ ÁN CON - SUB-PROJECT WORKSPACE) -->
        <div id="sidebar-sub-nav" style="display:none;">
            <div class="sidebar-context-card" style="border-color:#38bdf8;">
                <button class="btn-nav-back" onclick="exitToParentProject()">
                    <span>⬅️</span>
                    <span>Quay Lại Dự Án Cha</span>
                </button>
                <div style="font-size:10px; color:#38bdf8; font-weight:700; text-transform:uppercase;">Dự Án Con Đang Chọn:</div>
                <div style="font-size:14px; font-weight:800; color:#fff; margin-top:2px; line-height:1.3;" id="sidebarSubName">Dự án con</div>
                <div style="font-size:11px; color:#94a3b8; margin-top:4px;" id="sidebarSubBelong">Thuộc máy: ---</div>
            </div>

            <ul class="sidebar-menu">
                <li class="menu-label">Tài Khoản & Phiên Làm Việc</li>
                <li class="menu-item active" data-sub-menu="sub-account-info" id="sideMenuAccountItem">
                    <button onclick="switchSubMenu('sub-account-info')">
                        <span class="nav-icon">👤</span>
                        <span class="menu-title" id="sideMenuAccountTitle">Thông Tin & Cookie FB</span>
                    </button>
                </li>

                <!-- BỘ CHỨC NĂNG TỰ ĐỘNG HÓA -->
                <li class="menu-label" id="sideMenuAutomationLabel">Chức Năng Tự Động Hóa</li>

                <!-- 1. POST FACEBOOK (CHỨC NĂNG CHÍNH VỚI SUB-MENU) -->
                <li class="menu-item menu-parent expanded" id="sideMenuPostFbGroup">
                    <button type="button" onclick="handlePostFbParentClick()">
                        <span class="nav-icon">🚀</span>
                        <span class="menu-title" style="font-weight:700;">POST FACEBOOK</span>
                        <span class="menu-chevron" id="postFbChevron">▼</span>
                    </button>
                </li>
                <div id="postFbSubTree" class="menu-sub-tree">
                    <li class="menu-item menu-sub-item active" data-sub-menu="sub-autopost" id="sideMenuAutopostItem">
                        <button onclick="switchSubMenu('sub-autopost')">
                            <span class="nav-icon">📝</span>
                            <span class="menu-title" id="sideMenuAutopostTitle">Đăng Bài Viết Thường</span>
                        </button>
                    </li>
                    <li class="menu-item menu-sub-item" data-sub-menu="sub-post-video" id="sideMenuPostVideoItem">
                        <button onclick="switchSubMenu('sub-post-video')">
                            <span class="nav-icon">🎬</span>
                            <span class="menu-title" id="sideMenuPostVideoTitle">Facebook Video Watch</span>
                        </button>
                    </li>
                    <li class="menu-item menu-sub-item" data-sub-menu="sub-post-reels" id="sideMenuPostReelsItem">
                        <button onclick="switchSubMenu('sub-post-reels')">
                            <span class="nav-icon">⚡</span>
                            <span class="menu-title" id="sideMenuPostReelsTitle">Facebook Reels</span>
                        </button>
                    </li>
                    <li class="menu-item menu-sub-item" data-sub-menu="sub-post-story" id="sideMenuPostStoryItem">
                        <button onclick="switchSubMenu('sub-post-story')">
                            <span class="nav-icon">📖</span>
                            <span class="menu-title" id="sideMenuPostStoryTitle">Facebook Story</span>
                        </button>
                    </li>
                    <li class="menu-item menu-sub-item" data-sub-menu="sub-post-manager" id="sideMenuPostManagerItem">
                        <button onclick="switchSubMenu('sub-post-manager')">
                            <span class="nav-icon">📑</span>
                            <span class="menu-title" id="sideMenuPostManagerTitle">Quản Lý Bài Viết</span>
                        </button>
                    </li>
                    <li class="menu-item menu-sub-item" data-sub-menu="sub-api-doc" id="sideMenuApiDocItem">
                        <button onclick="switchSubMenu('sub-api-doc')">
                            <span class="nav-icon">📖</span>
                            <span class="menu-title" id="sideMenuApiDocTitle">Tài Liệu Endpoint API</span>
                        </button>
                    </li>
                </div>

                <!-- 2. CÀO DỮ LIỆU FACEBOOK -->
                <li class="menu-item" data-sub-menu="sub-scraper" id="sideMenuScraperItem">
                    <button onclick="switchSubMenu('sub-scraper')">
                        <span class="nav-icon">📥</span>
                        <span class="menu-title" id="sideMenuScraperTitle">Cào Dữ Liệu Facebook</span>
                    </button>
                </li>

                <!-- 3. TƯƠNG TÁC / NUÔI NICK FB -->
                <li class="menu-item" data-sub-menu="sub-interaction" id="sideMenuInteractionItem">
                    <button onclick="switchSubMenu('sub-interaction')">
                        <span class="nav-icon">💬</span>
                        <span class="menu-title" id="sideMenuInteractionTitle">Tương Tác / Nuôi Nick FB</span>
                    </button>
                </li>

                <!-- GOOGLE FLOW: TẠO ẢNH AI -->
                <li class="menu-item" data-sub-menu="sub-flow-image" id="sideMenuFlowImageItem" style="display:none;">
                    <button onclick="switchSubMenu('sub-flow-image')">
                        <span class="nav-icon">🎨</span>
                        <span class="menu-title" id="sideMenuFlowImageTitle">Tạo Ảnh AI (Flow)</span>
                    </button>
                </li>

                <!-- NỀN TẢNG KHÁC -->
                <li class="menu-item" data-sub-menu="sub-other-notice" id="sideMenuOtherNoticeItem" style="display:none;">
                    <button onclick="switchSubMenu('sub-other-notice')">
                        <span class="nav-icon">💡</span>
                        <span class="menu-title" id="sideMenuOtherNoticeTitle">Trạng Thái Tự Động Hóa</span>
                    </button>
                </li>

                <li class="menu-label" id="sideMenuBrowserLabel">Điều Khiển Trình Duyệt</li>
                <li class="menu-item" data-sub-menu="sub-browser" id="sideMenuBrowserItem">
                    <button onclick="switchSubMenu('sub-browser')">
                        <span class="nav-icon">🌐</span>
                        <span class="menu-title" id="sideMenuBrowserTitle">Điều Khiển Tab Facebook</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-scripts" id="sideMenuScriptsItem">
                    <button onclick="switchSubMenu('sub-scripts')">
                        <span class="nav-icon">💻</span>
                        <span class="menu-title">JavaScript Console</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-logs" id="sideMenuLogsItem">
                    <button onclick="switchSubMenu('sub-logs')">
                        <span class="nav-icon">📜</span>
                        <span class="menu-title">Nhật Ký Lệnh</span>
                    </button>
                </li>
            </ul>
        </div>

        <!-- FOOTER INFO -->
        <div class="sidebar-footer-info">
            <div>🟢 Server: <b>Port 9999</b></div>
            <div style="margin-top:4px;" id="sidebarUptime">Uptime: 0m</div>
        </div>
    </aside>
    <!-- MOBILE SIDEBAR OVERLAY (backdrop) -->
    <div class="sidebar-overlay" onclick="toggleMobileSidebar()"></div>

    <!-- 2. MAIN CONTENT WRAPPER -->
    <div class="main-wrapper">
        <!-- TOP HEADER -->
        <header class="top-header">
            <div class="header-title-box">
                <button class="hamburger-btn" onclick="toggleMobileSidebar()" aria-label="Menu">☰</button>
                <div class="header-page-title" id="pageTitle">
                    <span>📁</span> <span>Danh Sách Dự Án</span>
                </div>
            </div>

            <div class="header-actions">
                <div class="status-pill">
                    <span class="dot" id="headerDot"></span>
                    <span id="headerStatusText">Chưa có kết nối</span>
                </div>
                <div class="port-badge">PORT 9999</div>
                <button class="btn-sm" onclick="fetchStatus()">🔄 Làm mới</button>
            </div>
        </header>

        <!-- CONTENT VIEWPORT -->
        <main class="content-area">

            <!-- ========================================================= -->
            <!-- TẦNG 1: SẢNH NGOÀI (HUB LEVEL)                            -->
            <!-- ========================================================= -->

            <!-- HUB: PROJECTS LIST -->
            <section class="route-view active" id="view-hub-projects">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px;">
                    <div>
                        <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                            <span>📁</span> Danh Sách Dự Án Cha (Quản Lý Máy Chrome)
                        </h2>
                        <p style="font-size:13px; color:var(--text-muted); margin-top:4px;">
                            Mỗi dự án cha đại diện cho 1 máy Chrome (kết nối qua mã Auth Token riêng).<br/>
                            Bấm nút <b>[🚀 VÀO DỰ ÁN NÀY]</b> để xem và quản lý các Thư mục / Dự án con bên trong máy đó.
                        </p>
                    </div>
                    <button class="btn-green btn-lg" onclick="toggleNewProjectForm()">➕ Tạo Dự Án Cha Mới</button>
                </div>

                <!-- FORM TẠO DỰ ÁN CHA -->
                <div id="newProjectBox" class="card" style="display:none; border-color:var(--accent); margin-bottom:22px; background:#0b1329;">
                    <h3 style="font-size:15px; color:#38bdf8; margin-bottom:12px;">✨ Thiết Lập Dự Án Cha Mới</h3>
                    <div class="grid-responsive" style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Tên Dự Án Cha (Bắt buộc):</label>
                            <input type="text" id="newProjName" placeholder="Ví dụ: Máy Chrome 01 / Cụm Máy Nuôi Nick" />
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Mô Tả:</label>
                            <input type="text" id="newProjDesc" placeholder="Ví dụ: Dàn máy chính chạy tự động" />
                        </div>
                    </div>
                    <div style="display:flex; gap:10px; align-items:center; margin-top:4px;">
                        <button class="btn-purple" onclick="submitCreateProject()">🚀 Tạo Dự Án & Sinh Mã Token</button>
                        <button class="btn-sm" style="background:#334155;" onclick="toggleNewProjectForm()">Hủy bỏ</button>
                        <span id="createProjStatus" style="font-size:12px; font-weight:600;"></span>
                    </div>
                </div>

                <!-- GRID CARDS DỰ ÁN CHA -->
                <div id="hubProjectsListContainer" class="grid-responsive" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:18px;">
                    <div style="color:var(--text-muted); font-size:13px;">Đang tải danh sách dự án...</div>
                </div>
            </section>

            <!-- HUB: API DOCUMENTATION & TESTER -->
            <section class="route-view" id="view-hub-api">
                <!-- BANNER -->
                <div class="card" style="border-color: #a855f7; margin-bottom: 20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div>
                            <h2 style="color:#c084fc; font-size:18px; font-weight:800; display:flex; align-items:center; gap:8px;">
                                <span>🔌</span> <span>Cổng Tự Động Hóa REST API & Webhook</span>
                            </h2>
                            <p style="font-size:13px; color:var(--text-muted); margin-top:4px;">
                                Bạn có thể gọi API từ bất kỳ ngôn ngữ nào (Python, Node.js, PHP, cURL) hoặc các công cụ tự động hóa như <b>n8n, Make, Zapier</b> để đăng bài và seeding tự động lên Facebook.
                            </p>
                        </div>
                        <div style="background:#090e1c; padding:8px 14px; border-radius:8px; border:1px solid var(--border-color); font-size:12px;">
                            <span style="color:var(--text-muted);">Base URL:</span> <code id="apiBaseUrlDisplay" style="color:#38bdf8; font-weight:700;">http://localhost:9999</code>
                        </div>
                    </div>
                </div>

                <!-- GRID: 2 COLUMNS (LEFT: DOCUMENTATION, RIGHT: INTERACTIVE TESTER) -->
                <div class="grid-responsive" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap:20px;">
                    <!-- LEFT COLUMN: API SPECIFICATION -->
                    <div style="display:flex; flex-direction:column; gap:16px;">
                        <!-- 1. POST PUBLISH -->
                        <div class="card">
                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
                                <span style="background:#059669; color:#fff; font-size:11px; font-weight:800; padding:3px 8px; border-radius:4px;">POST</span>
                                <code style="font-size:13px; color:#38bdf8; font-weight:700;">/api/v1/posts/publish</code>
                            </div>
                            <p style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
                                Đăng bài viết mới ngay lập tức hoặc lên lịch đăng lên Profile, Fanpage, hoặc Group. Hỗ trợ kèm ảnh/video và kịch bản Seeding.
                            </p>
                            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Headers:</div>
                            <pre style="background:#090e1c; padding:10px; border-radius:6px; font-size:12px; color:#a78bfa; margin-bottom:12px; overflow-x:auto;">Content-Type: application/json
Authorization: Bearer BW-PROJ-XXXXXX</pre>

                            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Body Parameters (JSON):</div>
                            <table style="width:100%; font-size:12px; border-collapse:collapse; margin-bottom:12px;">
                                <thead>
                                    <tr style="border-bottom:1px solid var(--border-color); text-align:left; color:var(--text-muted);">
                                        <th style="padding:6px;">Trường</th>
                                        <th style="padding:6px;">Kiểu</th>
                                        <th style="padding:6px;">Bắt buộc</th>
                                        <th style="padding:6px;">Mô tả</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>content</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:#f87171;">Có (hoặc media)</td>
                                        <td style="padding:6px; color:var(--text-muted);">Nội dung bài viết (hỗ trợ Spintax <code>{A|B|C}</code>)</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>postType</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);"><code>post</code>, <code>reel</code>, <code>video</code>, <code>story</code> (mặc định: <code>post</code>)</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>targetType</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);"><code>profile</code>, <code>page</code>, <code>group</code> (mặc định: <code>profile</code>)</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>targetId</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:#f87171;">Khi page/group</td>
                                        <td style="padding:6px; color:var(--text-muted);">ID Fanpage hoặc ID Nhóm Facebook</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>mediaUrl</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);">Đường dẫn URL trực tiếp của tệp ảnh/video</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>seedingComments</code></td>
                                        <td style="padding:6px; color:#a78bfa;">array[string]</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);">Mảng các bình luận seeding bắn mồi tự động</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>scheduledAt</code></td>
                                        <td style="padding:6px; color:#38bdf8;">string / int</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);">Hẹn giờ đăng (ISO 8601 hoặc timestamp ms)</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>shareToStory</code></td>
                                        <td style="padding:6px; color:#a78bfa;">boolean</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);">Chia sẻ lên Tin Story (mặc định: <code>true</code>)</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:6px;"><code>callbackUrl</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);">Webhook URL nhận kết quả tự động</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:6px;"><code>autoReactType</code></td>
                                        <td style="padding:6px; color:#a78bfa;">string</td>
                                        <td style="padding:6px; color:var(--text-muted);">Không</td>
                                        <td style="padding:6px; color:var(--text-muted);"><code>LIKE</code>, <code>LOVE</code>, <code>CARE</code>, <code>HAHA</code>, <code>WOW</code>, <code>NONE</code></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- 2. GET STATUS -->
                        <div class="card">
                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
                                <span style="background:#0284c7; color:#fff; font-size:11px; font-weight:800; padding:3px 8px; border-radius:4px;">GET</span>
                                <code style="font-size:13px; color:#38bdf8; font-weight:700;">/api/v1/posts/status?postId={postId}</code>
                            </div>
                            <p style="font-size:12px; color:var(--text-muted);">
                                Lấy tiến trình đăng bài thời gian thực, xác nhận trạng thái (<code>completed</code>, <code>failed</code>) và nhận link bài viết Facebook (<code>fbPostUrl</code>).
                            </p>
                        </div>

                        <!-- 3. CODE SNIPPETS -->
                        <div class="card">
                            <div style="font-size:13px; font-weight:700; color:#fff; margin-bottom:10px;">💻 Mẫu Gọi API Bằng cURL & Python:</div>
                            <div style="font-size:11px; color:#38bdf8; font-weight:700; margin-bottom:4px;">cURL (Terminal / Bash):</div>
                            <pre style="background:#090e1c; padding:10px; border-radius:6px; font-size:11px; color:#e2e8f0; overflow-x:auto; margin-bottom:12px;">curl -X POST "http://localhost:9999/api/v1/posts/publish" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_DU_AN>" \
  -d '{
    "content": "{Chào bạn|Hello}! Bài viết tự động từ API với {nhiều ưu đãi|khuyến mãi khủng}.",
    "postType": "post",
    "targetType": "profile",
    "seedingComments": ["Quan tâm", "Shop ở đâu vậy?"],
    "autoReactType": "LOVE"
  }'</pre>
                            <div style="font-size:11px; color:#38bdf8; font-weight:700; margin-bottom:4px;">Python (requests):</div>
                            <pre style="background:#090e1c; padding:10px; border-radius:6px; font-size:11px; color:#e2e8f0; overflow-x:auto;">import requests

url = "http://localhost:9999/api/v1/posts/publish"
headers = {"Authorization": "Bearer <TOKEN_DU_AN>"}
payload = {
    "content": "Nội dung bài viết {chất lượng|độc quyền} đăng từ Python API!",
    "postType": "post",
    "targetType": "profile",
    "seedingComments": ["Tuyệt vời quá shop!", "Giá sao ạ?"],
    "autoReactType": "LOVE"
}
res = requests.post(url, json=payload, headers=headers)
print(res.json())</pre>
                        </div>
                    </div>

                    <!-- RIGHT COLUMN: INTERACTIVE API TESTER -->
                    <div>
                        <div class="card" style="border-color:#38bdf8;">
                            <h3 style="color:#38bdf8; font-size:15px; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                                <span>🚀</span> <span>Thử Nghiệm Gửi API Trực Tiếp (Live Tester)</span>
                            </h3>
                            <p style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">
                                Thử nghiệm gọi endpoint <code>/api/v1/posts/publish</code> ngay tại đây để xem phản hồi thực tế của server.
                            </p>

                            <div style="display:flex; flex-direction:column; gap:12px;">
                                <div>
                                    <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Dự Án / Token:</label>
                                    <select id="apiTestProjectSelect" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;"></select>
                                </div>

                                <div class="grid-responsive" style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                                    <div>
                                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Định Dạng Bài (postType):</label>
                                        <select id="apiTestPostType" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;">
                                            <option value="post">Bài Viết Thường (post)</option>
                                            <option value="reel">Thước Phim (reel)</option>
                                            <option value="video">Video Bảng Tin (video)</option>
                                            <option value="story">Bản Tin (story)</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Nơi Đăng (targetType):</label>
                                        <select id="apiTestTargetType" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;" onchange="toggleApiTestTargetId()">
                                            <option value="profile">Trang Cá Nhân (profile)</option>
                                            <option value="page">Fanpage (page)</option>
                                            <option value="group">Nhóm (group)</option>
                                        </select>
                                    </div>
                                </div>

                                <div id="apiTestTargetIdWrap" style="display:none;">
                                    <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">ID Fanpage / Group (targetId):</label>
                                    <input type="text" id="apiTestTargetId" placeholder="Ví dụ: 10008392817283" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;" />
                                </div>

                                <div>
                                    <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Nội Dung Bài Viết (content):</label>
                                    <textarea id="apiTestContent" rows="3" placeholder="Nội dung bài viết {A|B|C} spintax..." style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px; resize:vertical;">🔥 {Chào bạn|Hello quý khách}! Đây là bài viết gửi thử nghiệm từ tính năng REST API của BAWUI EX PRO.</textarea>
                                </div>

                                <div>
                                    <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">URL Media (ảnh/video tùy chọn):</label>
                                    <input type="text" id="apiTestMediaUrl" placeholder="https://example.com/image.jpg (để trống nếu bài viết chữ)" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;" />
                                </div>

                                <div class="grid-responsive" style="display:grid; grid-template-columns: 2fr 1fr; gap:10px;">
                                    <div>
                                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Bình Luận Seeding (mỗi dòng 1 câu):</label>
                                        <textarea id="apiTestSeeding" rows="2" placeholder="Seeding 1&#10;Seeding 2" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px; resize:vertical;">Tư vấn cho mình với shop ơi
Sản phẩm tuyệt vời quá</textarea>
                                    </div>
                                    <div>
                                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); display:block; margin-bottom:4px;">Cảm Xúc:</label>
                                        <select id="apiTestReact" style="width:100%; padding:8px; background:#090e1c; border:1px solid var(--border-color); border-radius:6px; color:#fff; font-size:13px;">
                                            <option value="LOVE">❤️ LOVE</option>
                                            <option value="LIKE">👍 LIKE</option>
                                            <option value="CARE">🥰 CARE</option>
                                            <option value="HAHA">😆 HAHA</option>
                                            <option value="WOW">😮 WOW</option>
                                            <option value="NONE">Không thả</option>
                                        </select>
                                    </div>
                                </div>

                                <button class="btn btn-green btn-lg" onclick="executeApiTestPublish()" id="btnApiTestSubmit" style="width:100%; margin-top:6px;">
                                    <span>🚀</span> <span>GỬI THỬ LỆNH API ĐĂNG BÀI NGAY</span>
                                </button>

                                <div style="margin-top:10px;">
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                        <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Kết Quả Phản Hồi Từ API (Response JSON):</span>
                                        <span id="apiTestHttpStatus" style="font-size:12px; font-weight:700;"></span>
                                    </div>
                                    <pre id="apiTestResponsePre" style="background:#090e1c; padding:12px; border-radius:8px; font-size:12px; color:#38bdf8; max-height:220px; overflow-y:auto; border:1px solid var(--border-color);">Chưa có yêu cầu nào được gửi...</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- HUB: VPS CONFIG -->
            <section class="route-view" id="view-hub-vps">
                <div class="card" style="border-color: #38bdf8;">
                    <h3 style="color:#38bdf8; font-size:16px; margin-bottom:12px;">☁️ Hướng Dẫn Kết Nối VPS & Extension</h3>
                    <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:16px;">
                        Extension trên các máy Chrome chỉ cần nhập URL của Backend và mã Token của Dự Án Cha để tự động kết nối vào cụm.
                    </p>
                    <div style="background:#090e1c; padding:16px; border-radius:8px; border:1px solid var(--border-color); font-size:13px; line-height:1.8;">
                        <b>1. URL Backend:</b> <code>http://127.0.0.1:9999</code> (hoặc IP công khai VPS).<br/>
                        <b>2. Mã Token:</b> Sao chép mã <code>BW-PROJ-XXXXXX</code> từ thẻ dự án cha mong muốn.<br/>
                        <b>3. Mở cài đặt:</b> Chuột phải vào biểu tượng Extension ⚡ &rarr; Chọn "Tùy chọn" (Options) &rarr; Lưu cấu hình.
                    </div>
                </div>
            </section>

            <!-- HUB: MANIFEST -->
            <section class="route-view" id="view-hub-manifest">
                <div class="card" style="border-color: #f97316;">
                    <h3 style="color:#fdba74; font-size:16px; margin-bottom:14px;">⚙️ Đổi Tên & Cấu Hình Extension (manifest.json)</h3>
                    <label style="font-size:12px; font-weight:700; color:var(--text-muted);">Tên Extension:</label>
                    <input type="text" id="configNameInput" value="⚡ BAWUI EXTENSION PRO" />
                    <label style="font-size:12px; font-weight:700; color:var(--text-muted);">Mô tả Extension:</label>
                    <input type="text" id="configDescInput" value="⚡ BAWUI EXTENSION PRO — Cầu nối trực tiếp và đồng bộ lệnh giữa Backend Server và Trình duyệt Chrome." />
                    <label style="font-size:12px; font-weight:700; color:var(--text-muted);">Phiên bản (version):</label>
                    <input type="text" id="configVerInput" value="1.0.0" />
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <button class="btn-orange" onclick="saveManifestSettings()">💾 Lưu Cập Nhật Tên Extension</button>
                        <span id="manifestSaveStatus" style="font-weight:600; font-size:13px;"></span>
                    </div>
                </div>
            </section>

            <!-- HUB: SYSTEM -->
            <section class="route-view" id="view-hub-system">
                <div class="card">
                    <h3 style="margin-bottom:14px; font-size:15px; color:#fff;">ℹ️ Thông Tin Nền Tảng</h3>
                    <div class="grid-responsive" style="display:grid; grid-template-columns:1fr 1fr; gap:14px; font-size:13px;">
                        <div>
                            <span style="color:var(--text-muted);">Backend Server:</span>
                            <div style="font-weight:700; color:#fff; margin-top:2px;">Python 3 (Standard Library)</div>
                        </div>
                        <div>
                            <span style="color:var(--text-muted);">Port Dịch Vụ:</span>
                            <div style="font-weight:700; color:var(--accent); margin-top:2px;">9999 (HTTP REST)</div>
                        </div>
                    </div>
                </div>
            </section>


            <!-- ========================================================= -->
            <!-- TẦNG 2: BÊN TRONG DỰ ÁN CHA (FOLDER VIEW)                 -->
            <!-- ========================================================= -->

            <section class="route-view" id="view-parent-subprojects">
                <!-- TOP HEADER -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px;">
                    <div>
                        <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                            <span>📂</span> <span id="parentSubHeaderTitle">Các Thư Mục / Dự Án Con</span>
                        </h2>
                        <p style="font-size:13px; color:var(--text-muted); margin-top:4px;">
                            Bên trong dự án cha này có thể tạo nhiều thư mục / dự án con. Bấm <b>[🚀 VÀO DỰ ÁN CON NÀY]</b> để mở menu lựa chọn tính năng.
                        </p>
                    </div>
                    <button class="btn-green btn-lg" onclick="toggleNewFolderForm()">➕ Tạo Thư Mục / Dự Án Con Mới</button>
                </div>

                <!-- THANH LỌC PHÂN LOẠI: FACEBOOK VS CÁC NỀN TẢNG KHÁC -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; flex-wrap:wrap; gap:10px; background:#070d1e; border:1px solid #1e293b; padding:10px 14px; border-radius:8px;">
                    <div class="filter-tabs-row" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;" id="subProjectsFilterTabs">
                        <span style="font-size:12px; font-weight:700; color:var(--text-muted); margin-right:4px;">🔍 Lọc Phân Loại:</span>
                        <button class="btn-sm active" id="filterTabAll" onclick="filterSubProjectsByPlatform('all', this)" style="border-radius:6px; padding:4px 12px; background:#0284c7; color:#fff; font-weight:700;">
                            📁 Tất Cả (<span id="countSubAll">0</span>)
                        </button>
                        <button class="btn-sm" id="filterTabFb" onclick="filterSubProjectsByPlatform('facebook', this)" style="border-radius:6px; padding:4px 12px; background:#1e293b; color:#cbd5e1; font-weight:600;">
                            📘 Chỉ FACEBOOK (Đang phát triển) (<span id="countSubFb">0</span>)
                        </button>
                        <button class="btn-sm" id="filterTabOther" onclick="filterSubProjectsByPlatform('other', this)" style="border-radius:6px; padding:4px 12px; background:#1e293b; color:#cbd5e1; font-weight:600;">
                            🌐 Nền Tảng Khác (<span id="countSubOther">0</span>)
                        </button>
                    </div>
                    <div style="font-size:12px; color:#38bdf8; font-weight:600; display:flex; align-items:center; gap:6px;">
                        <span>⭐</span> <span>Trọng tâm phát triển: <b>Facebook Automation Studio</b></span>
                    </div>
                </div>

                <!-- FORM TẠO DỰ ÁN CON ĐƠN GIẢN DẠNG FOLDER -->
                <div id="newFolderBox" class="card" style="display:none; border-color:#38bdf8; margin-bottom:22px; background:#0b1329;">
                    <h3 style="font-size:16px; color:#38bdf8; margin-bottom:16px; display:flex; align-items:center; gap:8px;">
                        <span>📂</span> <span>Tạo Thư Mục / Dự Án Con Mới</span>
                    </h3>

                    <!-- CHỌN TRANG WEB NGUỒN (SOURCE WEBSITE) -->
                    <div style="margin-bottom:18px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                            <label style="font-size:12px; font-weight:800; color:#38bdf8; text-transform:uppercase; display:flex; align-items:center; gap:6px; margin:0;">
                                <span>🌐</span> <span>Chọn Trang Web Nguồn Cần Tự Động Hóa:</span>
                            </label>
                            <span style="font-size:11px; color:#34d399; font-weight:600;">✨ Tích hợp sẵn: Quản lý Cookie/Nick, Cào Dữ Liệu, Đăng Bài & Seeding</span>
                        </div>
                        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:10px;" id="subPlatformSelectorGroup">
                            <div class="source-card-option active" onclick="selectSourcePlatform('facebook', this)">
                                <div style="font-size:24px; margin-bottom:4px;">📘</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">FACEBOOK</div>
                                <div style="font-size:10px; color:#38bdf8; font-family:monospace; margin-top:2px;">facebook.com</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('tiktok', this)">
                                <div style="font-size:24px; margin-bottom:4px;">🎵</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">TIKTOK</div>
                                <div style="font-size:10px; color:#f472b6; font-family:monospace; margin-top:2px;">tiktok.com</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('x', this)">
                                <div style="font-size:24px; margin-bottom:4px;">𝕏</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">X (TWITTER)</div>
                                <div style="font-size:10px; color:#cbd5e1; font-family:monospace; margin-top:2px;">x.com</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('instagram', this)">
                                <div style="font-size:24px; margin-bottom:4px;">📸</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">INSTAGRAM</div>
                                <div style="font-size:10px; color:#fbbf24; font-family:monospace; margin-top:2px;">instagram.com</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('threads', this)">
                                <div style="font-size:24px; margin-bottom:4px;">🧵</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">THREADS</div>
                                <div style="font-size:10px; color:#d8b4fe; font-family:monospace; margin-top:2px;">threads.net</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('flow', this)">
                                <div style="font-size:24px; margin-bottom:4px;">🌊</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">GOOGLE FLOW</div>
                                <div style="font-size:10px; color:#22d3ee; font-family:monospace; margin-top:2px;">flow.google.com</div>
                            </div>

                            <div class="source-card-option" onclick="selectSourcePlatform('custom', this)">
                                <div style="font-size:24px; margin-bottom:4px;">⚡</div>
                                <div style="font-weight:800; font-size:13px; color:#fff;">WEB TÙY CHỌN</div>
                                <div style="font-size:10px; color:#c084fc; font-family:monospace; margin-top:2px;">Nhập URL bất kỳ</div>
                            </div>
                        </div>
                    </div>

                    <!-- Ô NHẬP URL NGUỒN NẾU CHỌN TÙY CHỌN -->
                    <div id="customSourceUrlBox" style="margin-bottom:14px; display:none;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🔗 Nhập URL hoặc Domain Nguồn (Ví dụ: https://shopee.vn hoặc https://news.ycombinator.com):</label>
                        <input type="text" id="newFolderSourceUrl" placeholder="https://..." value="https://google.com" />
                    </div>

                    <div class="grid-responsive" style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px;">
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Tên Thư Mục / Dự Án Con (Bắt buộc):</label>
                            <input type="text" id="newFolderName" placeholder="Ví dụ: Dự Án Facebook 01" />
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Mô Tả Dự Án Con:</label>
                            <input type="text" id="newFolderDesc" placeholder="Ví dụ: Quản lý nick, cookie, cào dữ liệu và tự động hóa" />
                        </div>
                    </div>
                    <div style="display:flex; gap:10px; align-items:center; margin-top:4px;">
                        <button class="btn-purple btn-lg" onclick="submitCreateFolder()">🚀 Tạo Ngay Dự Án Con</button>
                        <button class="btn-sm" style="background:#334155;" onclick="toggleNewFolderForm()">Hủy bỏ</button>
                        <span id="createFolderStatus" style="font-size:12px; font-weight:600;"></span>
                    </div>
                </div>

                <!-- GRID DANH SÁCH CÁC THƯ MỤC / DỰ ÁN CON -->
                <div id="foldersGrid" class="grid-responsive" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:18px;">
                    <div style="color:var(--text-muted); font-size:13px;">Đang tải danh sách thư mục...</div>
                </div>
            </section>

            <!-- PARENT: MACHINE INFO -->
            <section class="route-view" id="view-parent-machine">
                <div class="card" style="margin-bottom:20px;">
                    <h3 style="font-size:15px; color:#fff; margin-bottom:14px;">🖥️ Chi Tiết Máy Chrome Của Dự Án Này</h3>
                    <div id="parentMachineDetailsBox">
                        <div style="color:var(--text-muted); font-size:13px;">Đang kiểm tra kết nối máy...</div>
                    </div>
                </div>
            </section>

            <!-- PARENT: LOGS -->
            <section class="route-view" id="view-parent-logs">
                <div class="card">
                    <h3 style="margin-bottom:12px; font-size:15px; color:#fff;">📜 Nhật Ký Hoạt Động Của Máy Này</h3>
                    <div class="log-container" id="parentLogBox">Chưa có nhật ký hoạt động...</div>
                </div>
            </section>


            <!-- ========================================================= -->
            <!-- TẦNG 3: BÊN TRONG DỰ ÁN CON (SUB-PROJECT WORKSPACE)       -->
            <!-- ========================================================= -->

            <!-- MENU TỰ ĐỘNG HÓA 1: CÀO DỮ LIỆU (SCRAPER STUDIO)          -->
            <section class="route-view" id="view-sub-scraper">
                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #091e3a 0%, #172554 100%); border-color:#38bdf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span id="scraperBannerIcon">📥</span> <span id="scraperBannerTitle">Studio Cào Dữ Liệu Web Nguồn</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;" id="scraperBannerDesc">
                                Cào bài viết, bình luận, tiêu đề, liên kết và hình ảnh trực tiếp từ tab Chrome đang mở của trang web nguồn.
                            </p>
                        </div>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn-sm" style="background:#0284c7;" onclick="openScraperSourceUrl()">🌐 Mở Trang Nguồn Trên Chrome</button>
                            <button class="btn-green btn-lg" onclick="startScrapingData()" style="box-shadow: 0 4px 18px rgba(16, 185, 129, 0.4);">
                                <span>🚀</span> <span>BẮT ĐẦU CÀO DỮ LIỆU TỪ CHROME</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- BẢNG ĐIỀU KHIỂN CÀO -->
                <div class="card" style="margin-bottom:20px; border-color:#1e293b;">
                    <h3 style="font-size:15px; color:#38bdf8; margin-bottom:12px; display:flex; align-items:center; gap:6px;">
                        <span>⚙️</span> <span>Cấu Hình Tham Số Cào Dữ Liệu</span>
                    </h3>

                    <div class="grid-responsive" style="display:grid; grid-template-columns: 2fr 1fr 1fr; gap:12px; align-items:end; margin-bottom:12px;">
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🔗 URL Trang Cần Cào (Hoặc tab đang mở):</label>
                            <input type="text" id="scraperTargetUrl" placeholder="https://..." style="margin:0;" />
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎯 Loại Dữ Liệu:</label>
                            <select id="scraperDataType" style="margin:0; width:100%; padding:9px 12px; background:#0f172a; border:1px solid #334155; color:#fff; border-radius:6px; font-size:13px;">
                                <option value="posts">📝 Bài viết & Nội dung chính</option>
                                <option value="comments">💬 Bình luận / Thảo luận</option>
                                <option value="media">🖼️ Danh sách Ảnh & Video</option>
                                <option value="links">🔗 Tiêu đề & Liên kết (Links)</option>
                                <option value="all">⚡ Trích xuất toàn bộ dữ liệu</option>
                            </select>
                        </div>
                        <div>
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">📊 Số Lượng Tối Đa:</label>
                            <select id="scraperDataLimit" style="margin:0; width:100%; padding:9px 12px; background:#0f172a; border:1px solid #334155; color:#fff; border-radius:6px; font-size:13px;">
                                <option value="15">15 mục</option>
                                <option value="30" selected>30 mục</option>
                                <option value="60">60 mục</option>
                                <option value="100">100 mục</option>
                            </select>
                        </div>
                    </div>

                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <span id="scraperStatusText" style="font-size:12px; color:var(--text-muted); font-weight:600;">Sẵn sàng cào dữ liệu từ Chrome node đang kết nối.</span>
                        <div style="display:flex; gap:8px;">
                            <button class="btn-sm btn-purple" onclick="scrollAndScrape()">📜 Cuộn Trang & Cào Thêm</button>
                        </div>
                    </div>
                </div>

                <!-- BẢNG KẾT QUẢ DỮ LIỆU CÀO ĐƯỢC -->
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:12px;">
                        <div>
                            <h4 style="font-size:15px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                                <span>📊</span> <span>Kết Quả Dữ Liệu Đã Cào Được</span>
                                <span class="badge-folder" style="background:rgba(56,189,248,0.2); color:#38bdf8; border:1px solid rgba(56,189,248,0.4);" id="scrapedCountBadge">0 Mục</span>
                            </h4>
                        </div>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn-sm" style="background:#0284c7;" onclick="copyScrapedJson()">📋 Sao Chép JSON</button>
                            <button class="btn-sm btn-green" onclick="exportScrapedCsv()">📥 Xuất File CSV (Excel UTF-8)</button>
                            <button class="btn-sm btn-danger" style="background:#dc2626;" onclick="clearScrapedData()">🗑️ Xóa Dữ Liệu Cào</button>
                        </div>
                    </div>

                    <div id="scrapedTableContainer" style="overflow-x:auto; max-height:560px;">
                        <div style="color:var(--text-muted); font-size:13px; padding:20px; text-align:center;">
                            Chưa có dữ liệu nào được cào. Bấm <b>[🚀 BẮT ĐẦU CÀO DỮ LIỆU TỪ CHROME]</b> ở trên để thực thi!
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA 2: TỰ ĐỘNG ĐĂNG BÀI & SEEDING (AUTO POSTER & SEEDING STUDIO) -->
            <section class="route-view" id="view-sub-autopost">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#34d399; font-weight:600;">
                        🟢 Direct GraphQL FB Mutation Engine
                    </div>
                </div>

                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #022c22 0%, #064e3b 100%); border-color:#34d399;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>📝</span> <span id="autopostBannerTitle">Studio Đăng Bài Viết Thường & Đính Kèm Ảnh / Video</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;" id="autopostBannerDesc">
                                Soạn thảo bài đăng bảng tin (Feed) lên Profile, Fanpage hoặc Nhóm. Đính kèm nhiều ảnh hoặc video, Spintax {A|B|C} chống trùng lặp nội dung, tự động seeding bình luận và thả like cảm xúc ngầm.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; border:1px solid rgba(52,211,153,0.4); padding:6px 14px; font-size:12px;">
                            ⚡ DIRECT GRAPHQL FB ENGINE
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#38bdf8;">
                        <div class="card-title">📊 Tổng Bài Đăng</div>
                        <div class="card-value" id="kpiTotalPosts" style="color:#38bdf8;">0</div>
                        <div class="card-sub">Tổng số bài trong dự án</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Chờ / Đang Đăng</div>
                        <div class="card-value" id="kpiPendingPosts" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Bài đang chờ xử lý</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Đã Đăng Thành Công</div>
                        <div class="card-value" id="kpiCompletedPosts" style="color:#34d399;">0</div>
                        <div class="card-sub">Đã xuất bản lên Facebook</div>
                    </div>
                    <div class="card" style="border-color:#a855f7;">
                        <div class="card-title">💬 Bình Luận Seeding</div>
                        <div class="card-value" id="kpiTotalSeeding" style="color:#a855f7;">0</div>
                        <div class="card-sub">Tổng số câu seeding kèm theo</div>
                    </div>
                </div>

                <!-- SOẠN THẢO BÀI ĐĂNG (STUDIO FORM) -->
                <div class="card" style="margin-bottom:24px; border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <h3 style="font-size:16px; color:#34d399; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>✍️</span> <span>Soạn Thảo Bài Viết & Kịch Bản Seeding Mới</span>
                        </h3>
                        <span style="font-size:11px; color:var(--text-muted);">Hỗ trợ đa định dạng & Spintax</span>
                    </div>

                    <!-- 1. CHỌN ĐÍCH ĐĂNG (TARGET TYPE PILLS) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎯 1. Đích Đăng Bài Viết (Target):
                        </label>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:10px; margin-bottom:10px;">
                            <button type="button" class="target-pill-btn active" data-target="profile" onclick="selectTargetTypePill('profile', this)">
                                <span>👤</span> <span>Trang Cá Nhân (Feed)</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="page" onclick="selectTargetTypePill('page', this)">
                                <span>🚩</span> <span>Fanpage Quản Lý</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="group" onclick="selectTargetTypePill('group', this)">
                                <span>👥</span> <span>Nhóm Facebook (Group)</span>
                            </button>
                        </div>
                        <div id="targetIdContainer" style="display:none;">
                            <label style="font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase;">ID Nhóm hoặc Fanpage Đích (Target ID):</label>
                            <input type="text" id="postTargetIdInput" placeholder="Ví dụ: 123456789012345 (Group ID hoặc Page ID)" style="margin-top:4px;" />
                        </div>
                    </div>

                    <!-- 2. TIÊU ĐỀ BÀI ĐĂNG (TÙY CHỌN) -->
                    <div style="margin-bottom:12px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">📝 2. Tiêu Đề Bài Viết / Ghi Chú Chiến Dịch:</label>
                        <input type="text" id="postTitleInput" placeholder="Ví dụ: Bài đăng giới thiệu sản phẩm #01 / Flash Sale" />
                    </div>

                    <!-- 3. NỘI DUNG VĂN BẢN (CAPTION & SPINTAX) -->
                    <div style="margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">
                                ✍️ 3. Nội Dung Chi Tiết (Hỗ trợ Spintax {A|B|C}):
                            </label>
                            <div style="display:flex; gap:10px; align-items:center;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="testSpintaxPreview()">🎲 Thử Xoay Spintax</button>
                                <span id="postCharCount" style="font-size:11px; color:var(--text-muted);">0 ký tự</span>
                            </div>
                        </div>
                        <textarea id="postContentInput" rows="5" placeholder="{Chào bạn|Hello quý khách|Hi cả nhà}! Hôm nay bên mình {giảm giá|ưu đãi khủng|tri ân khách hàng}...&#10;#sanpham #khuyenmai" oninput="updatePostCharCount(this)"></textarea>
                    </div>

                    <!-- 4. TỆP MEDIA (HÌNH ẢNH / VIDEO) -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🖼️ 4. Tệp Hình Ảnh / Video (Media Attachment):
                        </label>
                        <div style="display:flex; flex-direction:column; gap:10px;">
                            <!-- File Picker Dropzone -->
                            <div id="mediaDropZone" class="dropzone" onclick="document.getElementById('mediaFileInput').click()">
                                <div id="mediaPreview" style="display:none; width:100%; max-height:180px; overflow:hidden; border-radius:10px; margin-bottom:8px;"></div>
                                <div id="mediaDropText">
                                    <div class="btn" style="background:linear-gradient(135deg,#0284c7,#2563eb); pointer-events:none; padding:8px 20px; font-weight:700;">
                                        📁 CHỌN ẢNH HOẶC VIDEO TỪ MÁY
                                    </div>
                                    <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">Bấm để chọn file hoặc kéo thả tệp trực tiếp vào đây (Ảnh &le; 10MB, Video &le; 100MB)</div>
                                </div>
                                <input type="file" id="mediaFileInput" accept="image/*,video/*" style="display:none;" onchange="handleAdminMediaFile(this.files[0])">
                            </div>

                            <div id="mediaFileInfo" style="display:none; padding:8px 12px; background:rgba(56,189,248,0.12); border:1px solid rgba(56,189,248,0.3); border-radius:8px; align-items:center; justify-content:space-between;">
                                <span id="mediaFileName" style="font-size:12px; color:#38bdf8; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80%;"></span>
                                <button type="button" class="btn-sm btn-danger" onclick="clearAdminMedia()" style="padding:3px 8px;">✕ Xóa File</button>
                            </div>

                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="font-size:11px; color:var(--text-muted); white-space:nowrap;">Hoặc Dán Link URL:</span>
                                <input type="url" id="postMediaInput" placeholder="https://domain.com/photo.jpg hoặc mp4 direct link" style="margin:0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 5. KỊCH BẢN BÌNH LUẬN SEEDING & CẢM XÚC -->
                    <div style="margin-bottom:16px; background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#34d399; display:flex; align-items:center; gap:6px;">
                                <span>💬</span> <span>5. Kịch Bản Bình Luận Seeding Ngay Sau Khi Đăng:</span>
                            </label>
                            <div style="display:flex; gap:6px;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="insertSeedingPreset('inquiry')">✨ Mẫu Hỏi Giá</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#34d399;" onclick="insertSeedingPreset('feedback')">✨ Mẫu Khen Hàng</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#94a3b8;" onclick="insertSeedingPreset('clear')">✕ Xóa</button>
                            </div>
                        </div>
                        <textarea id="postSeedingCommentsInput" rows="3" placeholder="💬 Mỗi dòng một bình luận seeding tự động...&#10;Sản phẩm này còn hàng không shop?&#10;Đã nhận được hàng, rất ưng ý ạ!&#10;Shop tư vấn nhiệt tình lắm nha"></textarea>

                        <div class="grid-responsive" style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px;">
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">❤️ Thả Cảm Xúc Tự Động (Auto-React):</label>
                                <select id="postAutoReactInput" style="margin:4px 0 0 0;">
                                    <option value="LIKE" selected>👍 LIKE (Thích)</option>
                                    <option value="LOVE">❤️ LOVE (Yêu thích)</option>
                                    <option value="CARE">🥰 CARE (Thương thương)</option>
                                    <option value="HAHA">😆 HAHA (Cười)</option>
                                    <option value="WOW">😮 WOW (Ngạc nhiên)</option>
                                    <option value="SAD">😢 SAD (Buồn)</option>
                                    <option value="ANGRY">😡 ANGRY (Phẫn nộ)</option>
                                    <option value="NONE">🚫 Không thả cảm xúc</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎯 URL Đăng Bài Đích (Target URL - Tuỳ chọn):</label>
                                <input type="text" id="postTargetUrlInput" placeholder="https://www.facebook.com" style="margin:4px 0 0 0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 6. ĐẶT GIỜ ĐĂNG BÀI TỰ ĐỘNG (LÊN LỊCH HẸN GIỜ) -->
                    <div style="margin-bottom:16px; background:rgba(15,23,42,0.6); border:1px solid #1e293b; border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#38bdf8; display:flex; align-items:center; gap:6px;">
                                <span>⏰</span> <span>6. Đặt Giờ Đăng Bài Tự Động (Lên Lịch Hẹn Giờ):</span>
                            </label>
                            <span style="font-size:11px; color:var(--text-muted);">Tùy chọn — Để trống nếu muốn đăng ngay</span>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:8px;">
                            <input type="datetime-local" id="postScheduleTimeInput" style="max-width:240px; margin:0; padding:8px 12px; font-size:13px; font-weight:600;" />
                            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(15, 'postScheduleTimeInput')">+15 phút</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(60, 'postScheduleTimeInput')">+1 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(180, 'postScheduleTimeInput')">+3 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="setSchedulePresetNamed('tomorrow_morning', 'postScheduleTimeInput')">☀️ Sáng mai 8h</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#f59e0b;" onclick="setSchedulePresetNamed('tonight_evening', 'postScheduleTimeInput')">🌙 Tối nay 20h</button>
                                <button type="button" class="btn-sm btn-danger" style="padding:4px 8px;" onclick="clearScheduleTime('postScheduleTimeInput')" title="Xóa giờ hẹn">✕ Hủy Hẹn Giờ</button>
                            </div>
                        </div>
                        <div id="autopostScheduleHint" style="font-size:11px; color:#94a3b8;">
                            ℹ️ Để trống để phát lệnh ngay. Nếu chọn thời gian, bài sẽ được lưu vào hàng đợi và tự động kích hoạt đăng lên Facebook khi đến giờ hẹn.
                        </div>
                    </div>

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div class="btn-group-responsive" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; background:rgba(30,41,59,0.7); padding:8px 14px; border-radius:8px; border:1px solid #334155; font-size:13px; font-weight:600; color:#38bdf8; user-select:none; transition:all 0.2s;" title="Tự động chia sẻ bài viết lên Bảng tin & Tin Story (theo mutation useCometFeedToStoryReshare trong sharetinfacebook.har)">
                                <input type="checkbox" id="postShareToFeed" checked style="width:17px; height:17px; accent-color:#0284c7; cursor:pointer;" />
                                <span>📰 Chia sẻ lên bảng tin / Tin (Story)</span>
                            </label>
                            <button type="button" class="btn-green btn-lg" onclick="submitAutoPost('now')" style="background:linear-gradient(135deg,#059669,#10b981); box-shadow:0 4px 15px rgba(16,185,129,0.35);">
                                <span>🚀</span> <span>PHÁT LỆNH ĐĂNG BÀI & SEEDING NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitAutoPost('schedule')" style="background:linear-gradient(135deg,#0284c7,#2563eb); box-shadow:0 4px 15px rgba(37,99,235,0.35);">
                                <span>⏰</span> <span>LÊN LỊCH ĐĂNG (SCHEDULE)</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitAutoPost('queue')">
                                <span>➕</span> <span>Thêm Vào Hàng Đợi (Lưu Nháp)</span>
                            </button>
                        </div>
                        <span id="autopostStatusText" style="font-size:13px; font-weight:700;"></span>
                    </div>
                </div>

                <!-- QUẢN LÝ BÀI ĐĂNG (POST MANAGER & FILTER) -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>📑</span> <span>Quản Lý Bài Viết Đã Đăng & Hàng Đợi</span>
                            <span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; border:1px solid rgba(52,211,153,0.4);" id="postQueueCountBadge">0 Bài</span>
                        </h4>
                        <!-- SEARCH BAR -->
                        <div class="mobile-full-width" style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" id="postSearchInput" placeholder="🔍 Tìm theo nội dung, ID..." oninput="filterPostList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div class="filter-tabs-row" style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" id="filterBtnAll" onclick="setPostFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" id="filterBtnScheduled" onclick="setPostFilter('scheduled', this)" style="border-color:#38bdf8; color:#38bdf8;">⏰ Đã Lên Lịch</button>
                        <button type="button" class="preset-chip" id="filterBtnPending" onclick="setPostFilter('pending', this)">⏳ Chờ Lệnh / Đang Đăng</button>
                        <button type="button" class="preset-chip" id="filterBtnCompleted" onclick="setPostFilter('completed', this)">✅ Đã Đăng Thành Công</button>
                        <button type="button" class="preset-chip" id="filterBtnFailed" onclick="setPostFilter('failed', this)">❌ Thất Bại</button>
                    </div>

                    <!-- SMART POST CARDS CONTAINER -->
                    <div id="postQueueTableContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            Chưa có bài đăng nào trong hàng đợi.
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA: FACEBOOK VIDEO WATCH -->
            <section class="route-view" id="view-sub-post-video">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#38bdf8; font-weight:600;">
                        🎬 Facebook Video & Watch Vupload Engine
                    </div>
                </div>

                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #172554 0%, #1e3a8a 100%); border-color:#3b82f6;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>🎬</span> <span>Studio Đăng Facebook Video Watch & Video Dài</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Đăng tải video dài chất lượng cao lên Facebook Watch, Fanpage hoặc Group. Xử lý qua giao thức Native Vupload-Edge 3 bước, tự động phân giải video, seeding tương tác.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(59,130,246,0.25); color:#60a5fa; border:1px solid rgba(59,130,246,0.4); padding:6px 14px; font-size:12px;">
                            ⚡ NATIVE VUPLOAD PROTOCOL
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#38bdf8;">
                        <div class="card-title">🎬 Tổng Video Watch</div>
                        <div class="card-value" id="kpiTotalVideoPosts" style="color:#38bdf8;">0</div>
                        <div class="card-sub">Tổng số video trong dự án</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Chờ / Đang Upload</div>
                        <div class="card-value" id="kpiPendingVideoPosts" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Video đang chờ xử lý</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Đã Đăng Thành Công</div>
                        <div class="card-value" id="kpiCompletedVideoPosts" style="color:#34d399;">0</div>
                        <div class="card-sub">Video đã xuất bản lên Watch</div>
                    </div>
                    <div class="card" style="border-color:#a855f7;">
                        <div class="card-title">💬 Bình Luận Seeding</div>
                        <div class="card-value" id="kpiTotalVideoSeeding" style="color:#a855f7;">0</div>
                        <div class="card-sub">Tổng câu seeding cho Video</div>
                    </div>
                </div>

                <!-- SOẠN THẢO VIDEO WATCH -->
                <div class="card" style="margin-bottom:24px; border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <h3 style="font-size:16px; color:#60a5fa; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>🎬</span> <span>Soạn Thảo Video Watch Mới</span>
                        </h3>
                        <span style="font-size:11px; color:var(--text-muted);">Giao thức tải lên Vupload-Edge 3 bước</span>
                    </div>

                    <!-- 1. ĐÍCH ĐĂNG (TARGET) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎯 1. Đích Đăng Video (Target):
                        </label>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:10px; margin-bottom:10px;">
                            <button type="button" class="target-pill-btn active" data-target="profile" onclick="selectCustomTargetPill('video', 'profile', this)">
                                <span>👤</span> <span>Trang Cá Nhân (Watch)</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="page" onclick="selectCustomTargetPill('video', 'page', this)">
                                <span>🚩</span> <span>Fanpage Quản Lý</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="group" onclick="selectCustomTargetPill('video', 'group', this)">
                                <span>👥</span> <span>Nhóm Facebook (Group)</span>
                            </button>
                        </div>
                        <div id="videoTargetIdContainer" style="display:none;">
                            <label style="font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase;">ID Nhóm hoặc Fanpage Đích (Target ID):</label>
                            <input type="text" id="videoTargetIdInput" placeholder="Ví dụ: 123456789012345 (Group ID hoặc Page ID)" style="margin-top:4px;" />
                        </div>
                    </div>

                    <!-- 2. TIÊU ĐỀ VIDEO WATCH -->
                    <div style="margin-bottom:12px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎬 2. Tiêu Đề Video (Hiển Thị Trên Facebook Watch):</label>
                        <input type="text" id="videoTitleInput" placeholder="Nhập tiêu đề hấp dẫn cho Video Watch..." />
                    </div>

                    <!-- 3. TỆP VIDEO -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            📁 3. Tệp Video (.mp4, .mov, .mkv &le; 100MB):
                        </label>
                        <div style="display:flex; flex-direction:column; gap:10px;">
                            <div id="videoDropZone" class="dropzone" onclick="document.getElementById('videoFileInput').click()">
                                <div id="videoPreview" style="display:none; width:100%; max-height:220px; overflow:hidden; border-radius:10px; margin-bottom:8px;"></div>
                                <div id="videoDropText">
                                    <div class="btn" style="background:linear-gradient(135deg,#2563eb,#1d4ed8); pointer-events:none; padding:8px 20px; font-weight:700;">
                                        📁 CHỌN TỆP VIDEO TỪ MÁY
                                    </div>
                                    <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">Kéo thả tệp video vào đây hoặc bấm để chọn (MP4, MOV, MKV &le; 100MB)</div>
                                </div>
                                <input type="file" id="videoFileInput" accept="video/*,.mp4,.mov,.mkv,.avi" style="display:none;" onchange="handleCustomMediaFile('video', this.files[0])">
                            </div>

                            <div id="videoFileInfo" style="display:none; padding:8px 12px; background:rgba(59,130,246,0.12); border:1px solid rgba(59,130,246,0.3); border-radius:8px; align-items:center; justify-content:space-between;">
                                <span id="videoFileName" style="font-size:12px; color:#60a5fa; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80%;"></span>
                                <button type="button" class="btn-sm btn-danger" onclick="clearCustomMedia('video')" style="padding:3px 8px;">✕ Xóa File</button>
                            </div>

                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="font-size:11px; color:var(--text-muted); white-space:nowrap;">Hoặc Dán Link Video URL:</span>
                                <input type="url" id="videoMediaInput" placeholder="https://domain.com/video.mp4 direct link" style="margin:0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 4. MÔ TẢ / CAPTION VIDEO -->
                    <div style="margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">
                                ✍️ 4. Mô Tả Nội Dung Video (Hỗ trợ Spintax {A|B|C}):
                            </label>
                            <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="testSpintaxForEl('videoContentInput')">🎲 Thử Xoay Spintax</button>
                        </div>
                        <textarea id="videoContentInput" rows="4" placeholder="{Xem ngay|Cực hot|Đừng bỏ lỡ}! Nội dung video hôm nay...&#10;#watch #video #viral"></textarea>
                    </div>

                    <!-- 5. KỊCH BẢN SEEDING & AUTO-REACT -->
                    <div style="margin-bottom:16px; background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#34d399; display:flex; align-items:center; gap:6px;">
                                <span>💬</span> <span>5. Bình Luận Seeding Video Tự Động:</span>
                            </label>
                            <div style="display:flex; gap:6px;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="insertCustomSeedingPreset('video', 'inquiry')">✨ Mẫu Hỏi Giá</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#34d399;" onclick="insertCustomSeedingPreset('video', 'feedback')">✨ Mẫu Khen Video</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#94a3b8;" onclick="insertCustomSeedingPreset('video', 'clear')">✕ Xóa</button>
                            </div>
                        </div>
                        <textarea id="videoSeedingInput" rows="3" placeholder="💬 Mỗi dòng một bình luận seeding cho video...&#10;Video hay quá shop ơi!&#10;Chia sẻ thêm nhiều nội dung như này nhé!"></textarea>

                        <div class="grid-responsive" style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px;">
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">❤️ Thả Cảm Xúc Tự Động (Auto-React):</label>
                                <select id="videoAutoReactInput" style="margin:4px 0 0 0;">
                                    <option value="LIKE" selected>👍 LIKE (Thích)</option>
                                    <option value="LOVE">❤️ LOVE (Yêu thích)</option>
                                    <option value="CARE">🥰 CARE (Thương thương)</option>
                                    <option value="HAHA">😆 HAHA (Cười)</option>
                                    <option value="WOW">😮 WOW (Ngạc nhiên)</option>
                                    <option value="NONE">🚫 Không thả cảm xúc</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎯 URL Đích (Tùy chọn):</label>
                                <input type="text" id="videoTargetUrlInput" placeholder="https://www.facebook.com" style="margin:4px 0 0 0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 6. ĐẶT GIỜ ĐĂNG VIDEO TỰ ĐỘNG (LÊN LỊCH HẸN GIỜ) -->
                    <div style="margin-bottom:16px; background:rgba(15,23,42,0.6); border:1px solid #1e293b; border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#38bdf8; display:flex; align-items:center; gap:6px;">
                                <span>⏰</span> <span>6. Đặt Giờ Đăng Video Watch (Lên Lịch Hẹn Giờ):</span>
                            </label>
                            <span style="font-size:11px; color:var(--text-muted);">Tùy chọn — Để trống nếu muốn đăng ngay</span>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:8px;">
                            <input type="datetime-local" id="videoScheduleTimeInput" style="max-width:240px; margin:0; padding:8px 12px; font-size:13px; font-weight:600;" />
                            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(15, 'videoScheduleTimeInput')">+15 phút</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(60, 'videoScheduleTimeInput')">+1 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(180, 'videoScheduleTimeInput')">+3 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="setSchedulePresetNamed('tomorrow_morning', 'videoScheduleTimeInput')">☀️ Sáng mai 8h</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#f59e0b;" onclick="setSchedulePresetNamed('tonight_evening', 'videoScheduleTimeInput')">🌙 Tối nay 20h</button>
                                <button type="button" class="btn-sm btn-danger" style="padding:4px 8px;" onclick="clearScheduleTime('videoScheduleTimeInput')" title="Xóa giờ hẹn">✕ Hủy Hẹn Giờ</button>
                            </div>
                        </div>
                        <div id="videoScheduleHint" style="font-size:11px; color:#94a3b8;">
                            ℹ️ Để trống để phát lệnh ngay. Nếu chọn thời gian, video sẽ được lưu vào hàng đợi và tự động đăng lên Facebook khi đến giờ hẹn.
                        </div>
                    </div>

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div class="btn-group-responsive" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; background:rgba(30,41,59,0.7); padding:8px 14px; border-radius:8px; border:1px solid #334155; font-size:13px; font-weight:600; color:#38bdf8; user-select:none; transition:all 0.2s;" title="Tự động chia sẻ video lên Bảng tin & Tin Story (theo mutation useCometFeedToStoryReshare trong sharetinfacebook.har)">
                                <input type="checkbox" id="videoShareToFeed" checked style="width:17px; height:17px; accent-color:#0284c7; cursor:pointer;" />
                                <span>📰 Chia sẻ lên bảng tin / Tin (Story)</span>
                            </label>
                            <button type="button" class="btn-green btn-lg" onclick="submitCustomPost('video', 'video', 'now')" style="background:linear-gradient(135deg,#1d4ed8,#2563eb); box-shadow:0 4px 15px rgba(37,99,235,0.35);">
                                <span>🎬</span> <span>PHÁT LỆNH ĐĂNG VIDEO WATCH NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('video', 'video', 'schedule')" style="background:linear-gradient(135deg,#0284c7,#2563eb); box-shadow:0 4px 15px rgba(37,99,235,0.35);">
                                <span>⏰</span> <span>LÊN LỊCH ĐĂNG VIDEO</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('video', 'video', 'queue')">
                                <span>➕</span> <span>Thêm Vào Hàng Đợi (Lưu Nháp)</span>
                            </button>
                        </div>
                        <span id="videoStatusText" style="font-size:13px; font-weight:700;"></span>
                    </div>
                </div>

                <!-- QUẢN LÝ VIDEO WATCH -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>🎬</span> <span>Danh Sách Video Watch Đã Đăng & Hàng Đợi</span>
                            <span class="badge-folder" style="background:rgba(59,130,246,0.2); color:#60a5fa; border:1px solid rgba(59,130,246,0.4);" id="videoQueueCountBadge">0 Video</span>
                        </h4>
                        <div class="mobile-full-width" style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" placeholder="🔍 Tìm video theo tiêu đề, ID..." oninput="filterPostList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div class="filter-tabs-row" style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" onclick="setPostFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('scheduled', this)" style="border-color:#38bdf8; color:#38bdf8;">⏰ Đã Lên Lịch</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('pending', this)">⏳ Chờ Lệnh / Đang Đăng</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('completed', this)">✅ Đã Đăng Thành Công</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('failed', this)">❌ Thất Bại</button>
                    </div>
                    <div id="videoPostQueueTableContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            Chưa có Video Watch nào trong hàng đợi.
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA: FACEBOOK REELS -->
            <section class="route-view" id="view-sub-post-reels">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#eab308; font-weight:600;">
                        ⚡ Facebook Reels Composer Flow
                    </div>
                </div>

                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #422006 0%, #713f12 100%); border-color:#eab308;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>⚡</span> <span>Studio Đăng Facebook Reels (Thước Phim Ngắn)</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Sáng tạo và xuất bản Thước phim Reels định dạng dọc (9:16) lên Trang cá nhân hoặc Fanpage. Tự động bật âm thanh gốc, seeding bình luận kéo lượt xem đề xuất.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(234,179,8,0.25); color:#facc15; border:1px solid rgba(234,179,8,0.4); padding:6px 14px; font-size:12px;">
                            ⚡ REELS COMPOSER ENGINE
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#facc15;">
                        <div class="card-title">⚡ Tổng Thước Phim Reels</div>
                        <div class="card-value" id="kpiTotalReelsPosts" style="color:#facc15;">0</div>
                        <div class="card-sub">Tổng số Reels trong dự án</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Chờ / Đang Đăng</div>
                        <div class="card-value" id="kpiPendingReelsPosts" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Reels đang xử lý</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Đã Đăng Thành Công</div>
                        <div class="card-value" id="kpiCompletedReelsPosts" style="color:#34d399;">0</div>
                        <div class="card-sub">Đã xuất bản lên Reels</div>
                    </div>
                    <div class="card" style="border-color:#a855f7;">
                        <div class="card-title">💬 Bình Luận Seeding</div>
                        <div class="card-value" id="kpiTotalReelsSeeding" style="color:#a855f7;">0</div>
                        <div class="card-sub">Tổng bình luận seeding Reels</div>
                    </div>
                </div>

                <!-- SOẠN THẢO REELS -->
                <div class="card" style="margin-bottom:24px; border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <h3 style="font-size:16px; color:#facc15; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>⚡</span> <span>Tạo Thước Phim Facebook Reels Mới</span>
                        </h3>
                        <span style="font-size:11px; color:var(--text-muted);">Tỉ lệ chuẩn 9:16 (1080x1920)</span>
                    </div>

                    <!-- 1. ĐÍCH ĐĂNG (TARGET) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎯 1. Đích Đăng Reels:
                        </label>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:10px; margin-bottom:10px;">
                            <button type="button" class="target-pill-btn active" data-target="profile" onclick="selectCustomTargetPill('reels', 'profile', this)">
                                <span>👤</span> <span>Trang Cá Nhân (Reels)</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="page" onclick="selectCustomTargetPill('reels', 'page', this)">
                                <span>🚩</span> <span>Fanpage Reels</span>
                            </button>
                        </div>
                        <div id="reelsTargetIdContainer" style="display:none;">
                            <label style="font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase;">ID Fanpage Đích (Page ID):</label>
                            <input type="text" id="reelsTargetIdInput" placeholder="Ví dụ: 123456789012345" style="margin-top:4px;" />
                        </div>
                    </div>

                    <!-- 2. TỆP VIDEO REELS DỌC -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎬 2. Tệp Video Reels Dọc 9:16 (MP4, MOV &le; 100MB):
                        </label>
                        <div style="display:flex; flex-direction:column; gap:10px;">
                            <div id="reelsDropZone" class="dropzone" onclick="document.getElementById('reelsFileInput').click()">
                                <div id="reelsPreview" style="display:none; width:100%; max-height:220px; overflow:hidden; border-radius:10px; margin-bottom:8px;"></div>
                                <div id="reelsDropText">
                                    <div class="btn" style="background:linear-gradient(135deg,#ca8a04,#eab308); pointer-events:none; padding:8px 20px; font-weight:700; color:#000;">
                                        📁 CHỌN VIDEO REELS DỌC
                                    </div>
                                    <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">Khuyên dùng video dọc 9:16, thời lượng 15s - 90s (.mp4, .mov)</div>
                                </div>
                                <input type="file" id="reelsFileInput" accept="video/*,.mp4,.mov" style="display:none;" onchange="handleCustomMediaFile('reels', this.files[0])">
                            </div>

                            <div id="reelsFileInfo" style="display:none; padding:8px 12px; background:rgba(234,179,8,0.12); border:1px solid rgba(234,179,8,0.3); border-radius:8px; align-items:center; justify-content:space-between;">
                                <span id="reelsFileName" style="font-size:12px; color:#facc15; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80%;"></span>
                                <button type="button" class="btn-sm btn-danger" onclick="clearCustomMedia('reels')" style="padding:3px 8px;">✕ Xóa File</button>
                            </div>

                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="font-size:11px; color:var(--text-muted); white-space:nowrap;">Hoặc Dán Link URL:</span>
                                <input type="url" id="reelsMediaInput" placeholder="https://domain.com/reels.mp4 direct link" style="margin:0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 3. CAPTION REELS -->
                    <div style="margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">
                                ✍️ 3. Caption Thước Phim & Hashtags (Spintax {A|B|C}):
                            </label>
                            <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="testSpintaxForEl('reelsContentInput')">🎲 Thử Xoay Spintax</button>
                        </div>
                        <input type="text" id="reelsTitleInput" placeholder="Tiêu đề / Ghi chú Reels (tùy chọn)" style="margin-bottom:8px;" />
                        <textarea id="reelsContentInput" rows="3" placeholder="{Bật mí|Siêu phẩm|Đỉnh chóp}! Xem ngay mẹo này...&#10;#reels #reelsfb #trending #viral #xuhuong"></textarea>
                    </div>

                    <!-- 4. SEEDING & AUTO-REACT -->
                    <div style="margin-bottom:16px; background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#34d399; display:flex; align-items:center; gap:6px;">
                                <span>💬</span> <span>4. Bình Luận Seeding Reels Tự Động:</span>
                            </label>
                            <div style="display:flex; gap:6px;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="insertCustomSeedingPreset('reels', 'feedback')">✨ Mẫu Khen Reels</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#94a3b8;" onclick="insertCustomSeedingPreset('reels', 'clear')">✕ Xóa</button>
                            </div>
                        </div>
                        <textarea id="reelsSeedingInput" rows="2" placeholder="💬 Bình luận seeding kéo tương tác Reels...&#10;Video đỉnh quá ạ!&#10;Kênh làm nội dung chất lượng ghê"></textarea>

                        <div class="grid-responsive" style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px;">
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">❤️ Thả Cảm Xúc Tự Động:</label>
                                <select id="reelsAutoReactInput" style="margin:4px 0 0 0;">
                                    <option value="LOVE" selected>❤️ LOVE (Yêu thích)</option>
                                    <option value="LIKE">👍 LIKE (Thích)</option>
                                    <option value="CARE">🥰 CARE (Thương thương)</option>
                                    <option value="HAHA">😆 HAHA (Cười)</option>
                                    <option value="NONE">🚫 Không thả cảm xúc</option>
                                </select>
                            </div>
                            <div>
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎯 URL Đích (Mặc định Facebook Reels):</label>
                                <input type="text" id="reelsTargetUrlInput" value="https://www.facebook.com/reels/create" style="margin:4px 0 0 0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 5. ĐẶT GIỜ ĐĂNG REELS TỰ ĐỘNG (LÊN LỊCH HẸN GIỜ) -->
                    <div style="margin-bottom:16px; background:rgba(15,23,42,0.6); border:1px solid #1e293b; border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#facc15; display:flex; align-items:center; gap:6px;">
                                <span>⏰</span> <span>5. Đặt Giờ Đăng Facebook Reels (Lên Lịch Hẹn Giờ):</span>
                            </label>
                            <span style="font-size:11px; color:var(--text-muted);">Tùy chọn — Để trống nếu muốn đăng ngay</span>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:8px;">
                            <input type="datetime-local" id="reelsScheduleTimeInput" style="max-width:240px; margin:0; padding:8px 12px; font-size:13px; font-weight:600;" />
                            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(15, 'reelsScheduleTimeInput')">+15 phút</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(60, 'reelsScheduleTimeInput')">+1 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(180, 'reelsScheduleTimeInput')">+3 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="setSchedulePresetNamed('tomorrow_morning', 'reelsScheduleTimeInput')">☀️ Sáng mai 8h</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#f59e0b;" onclick="setSchedulePresetNamed('tonight_evening', 'reelsScheduleTimeInput')">🌙 Tối nay 20h</button>
                                <button type="button" class="btn-sm btn-danger" style="padding:4px 8px;" onclick="clearScheduleTime('reelsScheduleTimeInput')" title="Xóa giờ hẹn">✕ Hủy Hẹn Giờ</button>
                            </div>
                        </div>
                        <div id="reelsScheduleHint" style="font-size:11px; color:#94a3b8;">
                            ℹ️ Để trống để phát lệnh ngay. Nếu chọn thời gian, Reels sẽ được lưu vào hàng đợi và tự động xuất bản lên Facebook khi đến giờ hẹn.
                        </div>
                    </div>

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div class="btn-group-responsive" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; background:rgba(30,41,59,0.7); padding:8px 14px; border-radius:8px; border:1px solid #334155; font-size:13px; font-weight:600; color:#38bdf8; user-select:none; transition:all 0.2s;" title="Tự động chia sẻ Reels lên Bảng tin & Tin Story (theo mutation useCometFeedToStoryReshare trong sharetinfacebook.har)">
                                <input type="checkbox" id="reelsShareToFeed" checked style="width:17px; height:17px; accent-color:#0284c7; cursor:pointer;" />
                                <span>📰 Chia sẻ lên bảng tin / Tin (Story)</span>
                            </label>
                            <button type="button" class="btn-green btn-lg" onclick="submitCustomPost('reel', 'reels', 'now')" style="background:linear-gradient(135deg,#d97706,#f59e0b); box-shadow:0 4px 15px rgba(245,158,11,0.35); color:#000;">
                                <span>⚡</span> <span>PHÁT LỆNH ĐĂNG REELS NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('reel', 'reels', 'schedule')" style="background:linear-gradient(135deg,#0284c7,#2563eb); box-shadow:0 4px 15px rgba(37,99,235,0.35);">
                                <span>⏰</span> <span>LÊN LỊCH ĐĂNG REELS</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('reel', 'reels', 'queue')">
                                <span>➕</span> <span>Thêm Reels Vào Hàng Đợi (Lưu Nháp)</span>
                            </button>
                        </div>
                        <span id="reelsStatusText" style="font-size:13px; font-weight:700;"></span>
                    </div>
                </div>

                <!-- QUẢN LÝ REELS -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>⚡</span> <span>Danh Sách Reels Đã Đăng & Hàng Đợi</span>
                            <span class="badge-folder" style="background:rgba(234,179,8,0.2); color:#facc15; border:1px solid rgba(234,179,8,0.4);" id="reelsQueueCountBadge">0 Reels</span>
                        </h4>
                        <div class="mobile-full-width" style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" placeholder="🔍 Tìm reels theo tiêu đề, ID..." oninput="filterPostList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div class="filter-tabs-row" style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" onclick="setPostFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('scheduled', this)" style="border-color:#38bdf8; color:#38bdf8;">⏰ Đã Lên Lịch</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('pending', this)">⏳ Chờ Lệnh / Đang Đăng</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('completed', this)">✅ Đã Đăng Thành Công</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('failed', this)">❌ Thất Bại</button>
                    </div>
                    <div id="reelsPostQueueTableContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            Chưa có Reels nào trong hàng đợi.
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA: FACEBOOK STORY -->
            <section class="route-view" id="view-sub-post-story">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#ec4899; font-weight:600;">
                        📖 Facebook Stories 24h Engine
                    </div>
                </div>

                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #500724 0%, #831843 100%); border-color:#ec4899;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>📖</span> <span>Studio Đăng Facebook Story (Bản Tin 24 Giờ)</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Đăng tải bản tin Story tự biến mất sau 24h cho Trang cá nhân hoặc Fanpage. Xuất hiện nổi bật ngay đầu trang chủ của bạn bè và khách hàng tiềm năng.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(236,72,153,0.25); color:#f472b6; border:1px solid rgba(236,72,153,0.4); padding:6px 14px; font-size:12px;">
                            ⚡ STORY COMPOSER MUTATION
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#ec4899;">
                        <div class="card-title">📖 Tổng Bản Tin Story</div>
                        <div class="card-value" id="kpiTotalStoryPosts" style="color:#ec4899;">0</div>
                        <div class="card-sub">Tổng số Story trong dự án</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Chờ / Đang Đăng</div>
                        <div class="card-value" id="kpiPendingStoryPosts" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Story đang xử lý</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Đã Đăng Thành Công</div>
                        <div class="card-value" id="kpiCompletedStoryPosts" style="color:#34d399;">0</div>
                        <div class="card-sub">Story đang phát trực tiếp 24h</div>
                    </div>
                    <div class="card" style="border-color:#38bdf8;">
                        <div class="card-title">⏱️ Chu Kỳ Hiển Thị</div>
                        <div class="card-value" style="color:#38bdf8; font-size:18px;">24 GIỜ</div>
                        <div class="card-sub">Tự động lưu trữ sau 24h</div>
                    </div>
                </div>

                <!-- SOẠN THẢO STORY -->
                <div class="card" style="margin-bottom:24px; border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <h3 style="font-size:16px; color:#f472b6; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>📖</span> <span>Tạo Bản Tin Facebook Story 24h Mới</span>
                        </h3>
                        <span style="font-size:11px; color:var(--text-muted);">Ảnh hoặc Video ngắn &le; 15s</span>
                    </div>

                    <!-- 1. ĐÍCH ĐĂNG (TARGET) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎯 1. Đích Đăng Story:
                        </label>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:10px; margin-bottom:10px;">
                            <button type="button" class="target-pill-btn active" data-target="profile" onclick="selectCustomTargetPill('story', 'profile', this)">
                                <span>👤</span> <span>Trang Cá Nhân (Story)</span>
                            </button>
                            <button type="button" class="target-pill-btn" data-target="page" onclick="selectCustomTargetPill('story', 'page', this)">
                                <span>🚩</span> <span>Fanpage Story</span>
                            </button>
                        </div>
                        <div id="storyTargetIdContainer" style="display:none;">
                            <label style="font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase;">ID Fanpage Đích (Page ID):</label>
                            <input type="text" id="storyTargetIdInput" placeholder="Ví dụ: 123456789012345" style="margin-top:4px;" />
                        </div>
                    </div>

                    <!-- 2. TỆP MEDIA STORY -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🖼️ 2. Tệp Hình Ảnh hoặc Video Ngắn Cho Story (Dọc 9:16):
                        </label>
                        <div style="display:flex; flex-direction:column; gap:10px;">
                            <div id="storyDropZone" class="dropzone" onclick="document.getElementById('storyFileInput').click()">
                                <div id="storyPreview" style="display:none; width:100%; max-height:220px; overflow:hidden; border-radius:10px; margin-bottom:8px;"></div>
                                <div id="storyDropText">
                                    <div class="btn" style="background:linear-gradient(135deg,#db2777,#ec4899); pointer-events:none; padding:8px 20px; font-weight:700; color:#fff;">
                                        📁 CHỌN ẢNH HOẶC VIDEO STORY
                                    </div>
                                    <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">Ảnh hoặc Video ngắn &le; 15s (JPG, PNG, MP4, MOV)</div>
                                </div>
                                <input type="file" id="storyFileInput" accept="image/*,video/*" style="display:none;" onchange="handleCustomMediaFile('story', this.files[0])">
                            </div>

                            <div id="storyFileInfo" style="display:none; padding:8px 12px; background:rgba(236,72,153,0.12); border:1px solid rgba(236,72,153,0.3); border-radius:8px; align-items:center; justify-content:space-between;">
                                <span id="storyFileName" style="font-size:12px; color:#f472b6; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80%;"></span>
                                <button type="button" class="btn-sm btn-danger" onclick="clearCustomMedia('story')" style="padding:3px 8px;">✕ Xóa File</button>
                            </div>

                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="font-size:11px; color:var(--text-muted); white-space:nowrap;">Hoặc Dán Link URL:</span>
                                <input type="url" id="storyMediaInput" placeholder="https://domain.com/story.jpg direct link" style="margin:0;" />
                            </div>
                        </div>
                    </div>

                    <!-- 3. CHÚ THÍCH STORY -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:4px; display:block;">
                            ✍️ 3. Chú Thích Bản Tin Story:
                        </label>
                        <input type="text" id="storyTitleInput" placeholder="Tiêu đề / Ghi chú quản lý Story (tùy chọn)" style="margin-bottom:8px;" />
                        <textarea id="storyContentInput" rows="2" placeholder="Nhập chữ hiển thị trên Story (Spintax {A|B|C})..."></textarea>
                    </div>

                    <!-- 4. ĐẶT GIỜ ĐĂNG STORY TỰ ĐỘNG (LÊN LỊCH HẸN GIỜ) -->
                    <div style="margin-bottom:16px; background:rgba(15,23,42,0.6); border:1px solid #1e293b; border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#f472b6; display:flex; align-items:center; gap:6px;">
                                <span>⏰</span> <span>4. Đặt Giờ Đăng Facebook Story (Lên Lịch Hẹn Giờ):</span>
                            </label>
                            <span style="font-size:11px; color:var(--text-muted);">Tùy chọn — Để trống nếu muốn đăng ngay</span>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:8px;">
                            <input type="datetime-local" id="storyScheduleTimeInput" style="max-width:240px; margin:0; padding:8px 12px; font-size:13px; font-weight:600;" />
                            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(15, 'storyScheduleTimeInput')">+15 phút</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(60, 'storyScheduleTimeInput')">+1 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(180, 'storyScheduleTimeInput')">+3 giờ</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="setSchedulePresetNamed('tomorrow_morning', 'storyScheduleTimeInput')">☀️ Sáng mai 8h</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#f59e0b;" onclick="setSchedulePresetNamed('tonight_evening', 'storyScheduleTimeInput')">🌙 Tối nay 20h</button>
                                <button type="button" class="btn-sm btn-danger" style="padding:4px 8px;" onclick="clearScheduleTime('storyScheduleTimeInput')" title="Xóa giờ hẹn">✕ Hủy Hẹn Giờ</button>
                            </div>
                        </div>
                        <div id="storyScheduleHint" style="font-size:11px; color:#94a3b8;">
                            ℹ️ Để trống để phát lệnh ngay. Nếu chọn thời gian, Story sẽ được lưu vào hàng đợi và tự động xuất bản lên Facebook khi đến giờ hẹn.
                        </div>
                    </div>

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div class="btn-group-responsive" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; background:rgba(30,41,59,0.7); padding:8px 14px; border-radius:8px; border:1px solid #334155; font-size:13px; font-weight:600; color:#38bdf8; user-select:none; transition:all 0.2s;" title="Tự động chia sẻ lên Bảng tin & Tin (Story 24h)">
                                <input type="checkbox" id="storyShareToFeed" checked style="width:17px; height:17px; accent-color:#0284c7; cursor:pointer;" />
                                <span>📰 Chia sẻ lên bảng tin / Tin (Story)</span>
                            </label>
                            <button type="button" class="btn-green btn-lg" onclick="submitCustomPost('story', 'story', 'now')" style="background:linear-gradient(135deg,#db2777,#ec4899); box-shadow:0 4px 15px rgba(236,72,153,0.35);">
                                <span>📖</span> <span>PHÁT LỆNH ĐĂNG STORY 24H NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('story', 'story', 'schedule')" style="background:linear-gradient(135deg,#0284c7,#2563eb); box-shadow:0 4px 15px rgba(37,99,235,0.35);">
                                <span>⏰</span> <span>LÊN LỊCH ĐĂNG STORY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitCustomPost('story', 'story', 'queue')">
                                <span>➕</span> <span>Thêm Story Vào Hàng Đợi (Lưu Nháp)</span>
                            </button>
                        </div>
                        <span id="storyStatusText" style="font-size:13px; font-weight:700;"></span>
                    </div>
                </div>

                <!-- QUẢN LÝ STORY -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>📖</span> <span>Danh Sách Story Đã Đăng & Hàng Đợi</span>
                            <span class="badge-folder" style="background:rgba(236,72,153,0.2); color:#f472b6; border:1px solid rgba(236,72,153,0.4);" id="storyQueueCountBadge">0 Story</span>
                        </h4>
                        <div class="mobile-full-width" style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" placeholder="🔍 Tìm story theo tiêu đề, ID..." oninput="filterPostList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div class="filter-tabs-row" style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" onclick="setPostFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('scheduled', this)" style="border-color:#38bdf8; color:#38bdf8;">⏰ Đã Lên Lịch</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('pending', this)">⏳ Chờ Lệnh / Đang Đăng</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('completed', this)">✅ Đã Đăng Thành Công</button>
                        <button type="button" class="preset-chip" onclick="setPostFilter('failed', this)">❌ Thất Bại</button>
                    </div>
                    <div id="storyPostQueueTableContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            Chưa có Story nào trong hàng đợi.
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA 2.5: TÀI LIỆU ENDPOINT API CHO DỰ ÁN FB NÀY -->
            <section class="route-view" id="view-sub-api-doc">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#38bdf8; font-weight:600;">
                        ⚡ REST API Gateway Port 9999
                    </div>
                </div>

                <!-- BANNER THÔNG TIN NGỮ CẢNH CỦA TÀI KHOẢN HIỆN TẠI -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border-color:#6366f1;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>📖</span> <span>Chi Tiết Các Endpoint API & Tự Động Hóa</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Kết nối trực tiếp hệ thống bên ngoài (CRM, n8n, Make, Telegram Bot, Python, cURL) để điều khiển đăng bài và seeding tự động cho tài khoản Facebook này.
                            </p>
                        </div>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-sm btn-purple" onclick="copySubApiToken()">📋 Copy Token Dự Án</button>
                            <button class="btn btn-sm" style="background:#0f172a; color:#38bdf8;" onclick="copySubApiBaseUrl()">📋 Copy Base URL</button>
                        </div>
                    </div>

                    <!-- THÔNG TIN ĐỊNH DANH DỰ ÁN NÀY -->
                    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-top:16px; background:#090e1c; padding:14px; border-radius:8px; border:1px solid rgba(99,102,241,0.3);">
                        <div>
                            <div style="font-size:11px; color:#94a3b8; font-weight:700; text-transform:uppercase;">Project Token (Mã Dự Án):</div>
                            <div style="margin-top:2px;"><code id="subApiTokenVal" style="color:#a78bfa; font-weight:800; font-size:13px;">BW-PROJ-XXXXXX</code></div>
                        </div>
                        <div>
                            <div style="font-size:11px; color:#94a3b8; font-weight:700; text-transform:uppercase;">SubProject ID (Thư Mục FB):</div>
                            <div style="margin-top:2px;"><code id="subApiSubIdVal" style="color:#38bdf8; font-weight:700; font-size:12px;">sub_fb_...</code></div>
                        </div>
                        <div>
                            <div style="font-size:11px; color:#94a3b8; font-weight:700; text-transform:uppercase;">Tài Khoản Đăng:</div>
                            <div style="margin-top:2px;"><span id="subApiAccountInfo" style="color:#34d399; font-weight:700; font-size:12px;">Rin</span></div>
                        </div>
                        <div>
                            <div style="font-size:11px; color:#94a3b8; font-weight:700; text-transform:uppercase;">Base URL Máy Chủ:</div>
                            <div style="margin-top:2px;"><code id="subApiBaseUrlVal" style="color:#f59e0b; font-weight:700; font-size:12px;">http://localhost:9999</code></div>
                        </div>
                    </div>
                </div>

                <!-- BẢNG TỔNG QUAN CHUẨN REST API & HTTP STATUS CODES -->
                <div class="card" style="margin-bottom:20px; border-color:#38bdf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <h3 style="font-size:15px; color:#38bdf8; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>🌐</span> <span>Tiêu Chuẩn REST API & Quy Ước Mã Trạng Thái HTTP</span>
                        </h3>
                        <span class="badge-folder" style="background:rgba(56,189,248,0.2); color:#38bdf8;">RESTful v1</span>
                    </div>
                    <p style="font-size:12px; color:var(--text-muted); line-height:1.6; margin-bottom:12px;">
                        Tất cả các API tuân thủ tiêu chuẩn RESTful HTTP. Mọi response đều trả về cấu trúc JSON đồng nhất: 
                        <code>{"success": true|false, "message": "...", "data": {...}, "error": null|"..."}</code>.
                    </p>
                    <div class="grid-responsive" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px;">
                        <div style="background:#090e1c; padding:10px 14px; border-radius:8px; border:1px solid var(--border-color);">
                            <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:6px;">🔑 Header Xác Thực (Authentication):</div>
                            <div style="font-size:11px; color:#cbd5e1; font-family:monospace; line-height:1.6;">
                                Content-Type: application/json<br/>
                                Authorization: Bearer <span style="color:#a78bfa;">&lt;PROJECT_TOKEN&gt;</span><br/>
                                <span style="color:var(--text-muted);">(Hoặc header: X-Project-Token: &lt;PROJECT_TOKEN&gt;)</span>
                            </div>
                        </div>
                        <div style="background:#090e1c; padding:10px 14px; border-radius:8px; border:1px solid var(--border-color);">
                            <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:6px;">🚥 Bảng Mã Phản Hồi HTTP (Status Codes):</div>
                            <div style="font-size:11px; color:#cbd5e1; line-height:1.5;">
                                <b style="color:#34d399;">200 OK</b>: Thành công truy vấn / cập nhật<br/>
                                <b style="color:#38bdf8;">201 Created</b>: Tạo bài đăng / lên lịch thành công<br/>
                                <b style="color:#f59e0b;">400 Bad Request</b>: Thiếu tham số hoặc JSON sai<br/>
                                <b style="color:#f87171;">401 Unauthorized</b>: Token không hợp lệ<br/>
                                <b style="color:#f43f5e;">404 Not Found</b>: Không tìm thấy bài viết / ID<br/>
                                <b style="color:#eab308;">422 Unprocessable</b>: Giờ hẹn ở quá khứ
                            </div>
                        </div>
                    </div>
                </div>

                <!-- DANH SÁCH CHI TIẾT CÁC ENDPOINT REST API -->
                <div style="display:flex; flex-direction:column; gap:20px;">
                    <!-- ENDPOINT 1: POST /api/v1/posts -->
                    <div class="card" style="border-left:4px solid #10b981;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#059669; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">POST</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts</code>
                            </div>
                            <span style="font-size:12px; color:#10b981; font-weight:700;">🚀 Đăng Ngay hoặc ⏰ Đặt Giờ Hẹn Lên Lịch Tự Động</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:14px;">
                            Tạo bài viết mới cho Facebook. Hỗ trợ phát lệnh đăng ngay, lưu nháp vào hàng đợi, hoặc truyền tham số <code>scheduledAt</code> để lên lịch tự động xuất bản khi đến giờ hẹn.
                        </p>

                        <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:8px;">Bảng Tham Số Body (JSON):</div>
                        <div style="overflow-x:auto; margin-bottom:16px;">
                            <table style="width:100%; font-size:12px; border-collapse:collapse;">
                                <thead>
                                    <tr style="background:#090e1c; border-bottom:1px solid var(--border-color); text-align:left; color:#94a3b8;">
                                        <th style="padding:8px 10px;">Tên Trường</th>
                                        <th style="padding:8px 10px;">Kiểu Dữ Liệu</th>
                                        <th style="padding:8px 10px;">Bắt Buộc?</th>
                                        <th style="padding:8px 10px;">Mô Tả Chi Tiết</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>content</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#f87171;">Có (hoặc media)</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Nội dung bài viết. <b>Hỗ trợ Spintax đa tầng <code>{A|B|C}</code></b> tự xoay nội dung chống trùng lặp.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05); background:rgba(14,165,233,0.07);">
                                        <td style="padding:8px 10px;"><code>scheduledAt</code></td>
                                        <td style="padding:8px 10px; color:#38bdf8; font-weight:700;">string / int</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:#cbd5e1;"><b>Thời gian hẹn giờ đăng tự động</b>. Chấp nhận ISO 8601 (ví dụ <code>"2026-09-24T18:00:00Z"</code>), <code>"YYYY-MM-DDTHH:mm"</code> hoặc epoch timestamp (giây / ms).</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>postType</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Định dạng: <code>post</code> (bài viết thường), <code>video</code> (Video Watch), <code>reel</code> (Reels ngắn), <code>story</code> (bản tin 24h). Mặc định: <code>post</code>.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>targetType</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Đích đăng: <code>profile</code> (trang cá nhân), <code>page</code> (fanpage), <code>group</code> (nhóm). Mặc định: <code>profile</code>.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>targetId</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#f87171;">Khi page/group</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">ID của Fanpage hoặc ID Nhóm Facebook cần đăng vào.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>mediaUrl</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Link URL ảnh hoặc video trực tiếp để hệ thống tự động tải và upload lên Facebook.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>seedingComments</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">array[string]</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Mảng câu bình luận seeding mồi (ví dụ: <code>["Tư vấn mình với", "Sản phẩm tốt quá"]</code>).</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>shareToFeed</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">boolean</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);"><code>true</code> = Chia sẻ bài viết/video/reels/story lên Bảng tin (Newsfeed); <code>false</code> = Không chia sẻ lên bảng tin. Mặc định: <code>true</code>.</td>
                                    </tr>
                                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                        <td style="padding:8px 10px;"><code>autoReactType</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">string</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);">Cảm xúc: <code>LOVE</code>, <code>LIKE</code>, <code>CARE</code>, <code>HAHA</code>, <code>WOW</code>, <code>NONE</code>. Mặc định: <code>LIKE</code>.</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:8px 10px;"><code>runNow</code></td>
                                        <td style="padding:8px 10px; color:#a78bfa;">boolean</td>
                                        <td style="padding:8px 10px; color:#94a3b8;">Không</td>
                                        <td style="padding:8px 10px; color:var(--text-muted);"><code>true</code> = Đăng ngay; <code>false</code> = Lưu nháp (hoặc lên lịch nếu có <code>scheduledAt</code>). Mặc định: <code>true</code>.</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- CODE MẪU SẴN SÀNG COPY -->
                        <div style="font-size:13px; font-weight:800; color:#38bdf8; margin-bottom:10px;">💻 Mẫu Code Đăng Bài & Lên Lịch Cho Tài Khoản Này:</div>
                        
                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Terminal / cURL:</div>
                        <pre id="subApiCurlCode" style="background:#090e1c; padding:12px; border-radius:6px; font-size:11px; color:#e2e8f0; overflow-x:auto; margin-bottom:12px; border:1px solid var(--border-color);"></pre>

                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Python (requests):</div>
                        <pre id="subApiPythonCode" style="background:#090e1c; padding:12px; border-radius:6px; font-size:11px; color:#e2e8f0; overflow-x:auto; margin-bottom:12px; border:1px solid var(--border-color);"></pre>

                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Node.js / JavaScript (fetch):</div>
                        <pre id="subApiJsCode" style="background:#090e1c; padding:12px; border-radius:6px; font-size:11px; color:#e2e8f0; overflow-x:auto; border:1px solid var(--border-color);"></pre>
                    </div>

                    <!-- ENDPOINT 2: GET /api/v1/posts -->
                    <div class="card" style="border-left:4px solid #f59e0b;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#d97706; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">GET</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts?status=scheduled&limit=20</code>
                            </div>
                            <span style="font-size:12px; color:#f59e0b; font-weight:700;">📋 Lấy Danh Sách Bài Đăng & Hàng Đợi (Filter & Pagination)</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:10px;">
                            Truy vấn danh sách bài viết trong hàng đợi của dự án. Hỗ trợ lọc theo <code>status</code> (<code>scheduled</code>, <code>pending</code>, <code>in_progress</code>, <code>completed</code>, <code>failed</code>), <code>postType</code> (<code>post</code>, <code>video</code>, <code>reel</code>, <code>story</code>), và phân trang với <code>limit</code>, <code>offset</code>.
                        </p>
                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Response Mẫu:</div>
                        <pre style="background:#090e1c; padding:12px; border-radius:6px; font-size:12px; color:#34d399; overflow-x:auto; border:1px solid var(--border-color);">{
  "success": true,
  "message": "Lấy danh sách bài đăng thành công",
  "data": {
    "total": 5,
    "limit": 20,
    "offset": 0,
    "posts": [
      {
        "id": "post_1790198000_1234",
        "title": "Khai trương chi nhánh mới",
        "content": "Chào mừng bạn ghé thăm...",
        "postType": "post",
        "status": "scheduled",
        "scheduledTime": 1790200800000,
        "scheduledTimeStr": "18:00:00 24/09/2026",
        "createdAt": "2026-09-24T06:00:00.000Z"
      }
    ]
  }
}</pre>
                    </div>

                    <!-- ENDPOINT 3: GET /api/v1/posts/{id} -->
                    <div class="card" style="border-left:4px solid #0284c7;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#0284c7; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">GET</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts/{id}</code>
                            </div>
                            <span style="font-size:12px; color:#38bdf8; font-weight:700;">📊 Chi Tiết Bài Đăng & Link Facebook</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:10px;">
                            Lấy thông tin chi tiết, tiến trình đăng và link bài viết Facebook (<code>fbPostUrl</code>) ngay sau khi đăng thành công.
                        </p>
                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Response Mẫu Khi Hoàn Thành:</div>
                        <pre style="background:#090e1c; padding:12px; border-radius:6px; font-size:12px; color:#34d399; overflow-x:auto; border:1px solid var(--border-color);">{
  "success": true,
  "message": "Chi tiết bài đăng",
  "data": {
    "id": "post_1790198000_1234",
    "status": "completed",
    "progressStep": "✅ Đã đăng thành công lên Facebook",
    "fbPostId": "2151992722340672",
    "fbPostUrl": "https://www.facebook.com/permalink.php?story_fbid=2151992722340672&id=100025898964308"
  }
}</pre>
                    </div>

                    <!-- ENDPOINT 4: POST /api/v1/posts/{id}/run -->
                    <div class="card" style="border-left:4px solid #10b981;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#059669; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">POST</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts/{id}/run</code>
                            </div>
                            <span style="font-size:12px; color:#10b981; font-weight:700;">⚡ Kích Hoạt Đăng Ngay Lập Tức</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6;">
                            Phát lệnh ngay lập tức cho Chrome Extension đăng bài viết này mà không cần chờ đến giờ hẹn (bỏ qua lịch trình hẹn giờ).
                        </p>
                    </div>

                    <!-- ENDPOINT 5: PATCH /api/v1/posts/{id} -->
                    <div class="card" style="border-left:4px solid #0284c7;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#0284c7; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">PATCH</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts/{id}</code>
                            </div>
                            <span style="font-size:12px; color:#38bdf8; font-weight:700;">✏️ Đổi Giờ Hẹn Đăng / Sửa Nội Dung / Hủy Hẹn Giờ</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:10px;">
                            Cập nhật thời gian hẹn giờ đăng mới (<code>scheduledAt: "2026-09-24T20:00:00Z"</code>), sửa nội dung/tiêu đề, hoặc truyền <code>scheduledAt: null</code> để hủy hẹn giờ và chuyển bài viết về dạng lưu nháp.
                        </p>
                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Body Mẫu (JSON):</div>
                        <pre style="background:#090e1c; padding:12px; border-radius:6px; font-size:12px; color:#e2e8f0; overflow-x:auto; border:1px solid var(--border-color);">{
  "scheduledAt": "2026-09-24T20:30:00Z",
  "title": "Tiêu đề bài viết sau khi sửa"
}</pre>
                    </div>

                    <!-- ENDPOINT 6: DELETE /api/v1/posts/{id} -->
                    <div class="card" style="border-left:4px solid #ef4444;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#dc2626; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">DELETE</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts/{id}</code>
                            </div>
                            <span style="font-size:12px; color:#ef4444; font-weight:700;">🗑️ Xóa Bài Viết Khỏi Hàng Đợi</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6;">
                            Xóa hoàn toàn một bài viết hoặc mục video/reels/story khỏi hàng đợi và lịch trình đăng tự động.
                        </p>
                    </div>

                    <!-- ENDPOINT 7: POST /api/v1/posts/seeding -->
                    <div class="card" style="border-left:4px solid #a855f7;">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <span style="background:#7c3aed; color:#fff; font-size:12px; font-weight:800; padding:4px 10px; border-radius:4px;">POST</span>
                                <code style="font-size:15px; color:#38bdf8; font-weight:800;">/api/v1/posts/seeding</code>
                            </div>
                            <span style="font-size:12px; color:#c084fc; font-weight:700;">💬 Bắn Thêm Seeding Vào Bài Viết Đã Đăng</span>
                        </div>
                        <p style="font-size:13px; color:var(--text-muted); line-height:1.6; margin-bottom:10px;">
                            Bắn thêm danh sách bình luận seeding mồi và thả cảm xúc vào bài viết đã được đăng trên Facebook.
                        </p>
                        <div style="font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:4px;">Body Mẫu (JSON):</div>
                        <pre style="background:#090e1c; padding:12px; border-radius:6px; font-size:12px; color:#e2e8f0; overflow-x:auto; border:1px solid var(--border-color);">{
  "postId": "post_1790198000_1234",
  "comments": ["Bình luận seeding thêm 1", "Bình luận seeding thêm 2"],
  "autoReactType": "LOVE"
}</pre>
                    </div>
                </div>
            </section>

            <!-- MENU QUẢN LÝ BÀI VIẾT ĐÃ ĐĂNG (POST MANAGER) -->
            <section class="route-view" id="view-sub-post-manager">
                <!-- THANH CHUYỂN NHANH TRONG CHỨC NĂNG POST FACEBOOK -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; background:#070d1e; border:1px solid #1e293b; padding:8px 14px; border-radius:8px; flex-wrap:wrap; gap:10px;">
                    <div class="post-fb-toolbar" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:12px; font-weight:800; color:#38bdf8; margin-right:4px;">🚀 POST FACEBOOK:</span>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-autopost')">
                            📝 Đăng Bài Viết Thường
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-video')">
                            🎬 Facebook Video Watch
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-reels')">
                            ⚡ Facebook Reels
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-story')">
                            📖 Facebook Story
                        </button>
                        <button class="btn-sm" style="background:#1e293b; color:#cbd5e1; font-weight:600; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-api-doc')">
                            📖 Tài Liệu API
                        </button>
                        <button class="btn-sm active" style="background:#0284c7; color:#fff; font-weight:700; border-radius:6px; padding:5px 12px;" onclick="switchSubMenu('sub-post-manager')">
                            📑 Quản Lý Bài Viết
                        </button>
                    </div>
                    <div style="font-size:11px; color:#a78bfa; font-weight:600;">
                        📑 Post Management Dashboard
                    </div>
                </div>

                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); border-color:#818cf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>📑</span> <span>Quản Lý Bài Viết Đã Đăng</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Theo dõi và quản lý tất cả bài viết đã đăng thành công, đã lên lịch, đang chờ, hoặc thất bại. Bao gồm tất cả loại bài: Bài viết thường, Video Watch, Reels, và Story.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(129,140,248,0.25); color:#a5b4fc; border:1px solid rgba(129,140,248,0.4); padding:6px 14px; font-size:12px;">
                            📊 ALL POST TYPES
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#818cf8;">
                        <div class="card-title">📑 Tổng Bài Viết</div>
                        <div class="card-value" id="kpiMgrTotalPosts" style="color:#818cf8;">0</div>
                        <div class="card-sub">Tất cả loại bài trong dự án</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Chờ / Đang Đăng</div>
                        <div class="card-value" id="kpiMgrPendingPosts" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Bài viết đang xử lý</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Đã Đăng Thành Công</div>
                        <div class="card-value" id="kpiMgrCompletedPosts" style="color:#34d399;">0</div>
                        <div class="card-sub">Bài viết đã đăng lên Facebook</div>
                    </div>
                    <div class="card" style="border-color:#f87171;">
                        <div class="card-title">❌ Thất Bại</div>
                        <div class="card-value" id="kpiMgrFailedPosts" style="color:#f87171;">0</div>
                        <div class="card-sub">Bài viết đăng bị lỗi</div>
                    </div>
                </div>

                <!-- FILTER & SEARCH -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>📑</span> <span>Tất Cả Bài Viết Đã Đăng</span>
                            <span class="badge-folder" style="background:rgba(129,140,248,0.2); color:#a5b4fc; border:1px solid rgba(129,140,248,0.4);" id="postManagerCountBadge">0 Bài</span>
                        </h4>
                        <!-- SEARCH BAR -->
                        <div class="mobile-full-width" style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" id="postManagerSearchInput" placeholder="🔍 Tìm theo nội dung, ID..." oninput="filterPostManagerList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div class="filter-tabs-row" style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" id="mgrFilterBtnAll" onclick="setPostManagerFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnPost" onclick="setPostManagerFilter('post', this)" style="border-color:#34d399; color:#34d399;">📝 Bài Viết Thường</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnVideo" onclick="setPostManagerFilter('video', this)" style="border-color:#38bdf8; color:#38bdf8;">🎬 Video Watch</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnReels" onclick="setPostManagerFilter('reel', this)" style="border-color:#eab308; color:#eab308;">⚡ Reels</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnStory" onclick="setPostManagerFilter('story', this)" style="border-color:#ec4899; color:#ec4899;">📖 Story</button>
                        <span style="border-left:1px solid #334155; margin:0 4px;"></span>
                        <button type="button" class="preset-chip" id="mgrFilterBtnCompleted" onclick="setPostManagerFilter('completed', this)" style="border-color:#34d399; color:#34d399;">✅ Đã Đăng</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnScheduled" onclick="setPostManagerFilter('scheduled', this)" style="border-color:#38bdf8; color:#38bdf8;">⏰ Đã Lên Lịch</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnPending" onclick="setPostManagerFilter('pending', this)">⏳ Chờ / Đang Đăng</button>
                        <button type="button" class="preset-chip" id="mgrFilterBtnFailed" onclick="setPostManagerFilter('failed', this)" style="border-color:#f87171; color:#f87171;">❌ Thất Bại</button>
                    </div>

                    <!-- POST CARDS CONTAINER -->
                    <div id="postManagerTableContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            Chưa có bài đăng nào. Hãy đăng bài từ các Studio ở trên!
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU GOOGLE FLOW: TẠO ẢNH AI -->
            <section class="route-view" id="view-sub-flow-image">
                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #042f2e 0%, #134e4a 100%); border-color:#2dd4bf;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>🎨</span> <span>Google Flow — AI Image Generator</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;">
                                Tạo ảnh AI bằng Imagen (HARBOR_SEAL) thông qua Google Flow. Nhập mô tả prompt và hệ thống sẽ gửi yêu cầu qua Chrome Extension đến flow.google.com để tạo ảnh.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(45,212,191,0.25); color:#5eead4; border:1px solid rgba(45,212,191,0.4); padding:6px 14px; font-size:12px;">
                            🌊 Imagen / HARBOR_SEAL Engine
                        </span>
                    </div>
                </div>

                <!-- 3 KPI CARDS -->
                <div class="grid-cards grid-responsive-sm" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
                    <div class="card" style="border-color:#2dd4bf;">
                        <div class="card-title">🎨 Tổng Ảnh Đã Tạo</div>
                        <div class="card-value" id="kpiFlowTotalImages" style="color:#2dd4bf;">0</div>
                        <div class="card-sub">Tổng số ảnh AI đã generate</div>
                    </div>
                    <div class="card" style="border-color:#fbbf24;">
                        <div class="card-title">⏳ Đang Xử Lý</div>
                        <div class="card-value" id="kpiFlowPendingImages" style="color:#fbbf24;">0</div>
                        <div class="card-sub">Đang chờ tạo ảnh</div>
                    </div>
                    <div class="card" style="border-color:#34d399;">
                        <div class="card-title">✅ Hoàn Thành</div>
                        <div class="card-value" id="kpiFlowCompletedImages" style="color:#34d399;">0</div>
                        <div class="card-sub">Ảnh đã tạo thành công</div>
                    </div>
                </div>

                <!-- SOẠN PROMPT TẠO ẢNH -->
                <div class="card" style="margin-bottom:24px; border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <h3 style="font-size:16px; color:#2dd4bf; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>✍️</span> <span>Nhập Prompt Tạo Ảnh AI</span>
                        </h3>
                    </div>

                    <!-- PROMPT INPUT -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin-bottom:6px; display:block;">📝 Prompt mô tả ảnh muốn tạo (Tiếng Việt hoặc Tiếng Anh)</label>
                        <textarea id="flowImagePromptInput" rows="4" style="width:100%; resize:vertical; font-size:14px; line-height:1.6; padding:12px;" placeholder="Ví dụ: Một chú mèo dễ thương đang ngồi trên đống tiền vàng, phong cách 3D render, nền gradient xanh tím..."></textarea>
                    </div>

                    <!-- OPTIONS ROW -->
                    <div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:16px; align-items:flex-end;">
                        <div style="flex:1; min-width:180px;">
                            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin-bottom:6px; display:block;">🤖 Model AI</label>
                            <select id="flowImageModelSelect" style="width:100%; padding:8px 12px; font-size:13px;">
                                <option value="HARBOR_SEAL" selected>🖼️ Imagen 3 (HARBOR_SEAL) — Chất lượng cao</option>
                            </select>
                        </div>
                        <div style="flex:1; min-width:140px;">
                            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin-bottom:6px; display:block;">🔢 Số ảnh tạo</label>
                            <select id="flowImageCountSelect" style="width:100%; padding:8px 12px; font-size:13px;">
                                <option value="4" selected>4 ảnh</option>
                                <option value="2">2 ảnh</option>
                                <option value="1">1 ảnh</option>
                            </select>
                        </div>
                        <div style="flex:1; min-width:140px;">
                            <label style="font-size:12px; font-weight:700; color:var(--text-muted); margin-bottom:6px; display:block;">📐 Tỷ lệ ảnh</label>
                            <select id="flowImageRatioSelect" style="width:100%; padding:8px 12px; font-size:13px;">
                                <option value="3:4" selected>3:4 (Dọc)</option>
                                <option value="4:3">4:3 (Ngang)</option>
                                <option value="1:1">1:1 (Vuông)</option>
                                <option value="16:9">16:9 (Widescreen)</option>
                                <option value="9:16">9:16 (Story/Reels)</option>
                            </select>
                        </div>
                    </div>

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                            <button type="button" class="btn-green btn-lg" onclick="submitFlowImageGenerate()" style="background:linear-gradient(135deg,#0d9488,#14b8a6); box-shadow:0 4px 15px rgba(20,184,166,0.35);">
                                <span>🎨</span> <span>TẠO ẢNH AI NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitFlowImageGenerate('queue')">
                                <span>➕</span> <span>Lưu Vào Hàng Đợi</span>
                            </button>
                        </div>
                        <span id="flowImageStatusText" style="font-size:13px; font-weight:700;"></span>
                    </div>
                </div>

                <!-- KẾT QUẢ ẢNH ĐÃ TẠO -->
                <div class="card" style="border-color:#202d46;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
                        <h4 style="font-size:16px; color:#fff; margin:0; display:flex; align-items:center; gap:8px;">
                            <span>🖼️</span> <span>Gallery Ảnh Đã Tạo</span>
                            <span class="badge-folder" style="background:rgba(45,212,191,0.2); color:#5eead4; border:1px solid rgba(45,212,191,0.4);" id="flowImageCountBadge">0 Ảnh</span>
                        </h4>
                    </div>

                    <!-- GALLERY CONTAINER -->
                    <div id="flowImageGalleryContainer">
                        <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                            <span style="font-size:32px;">🎨</span>
                            <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">Chưa có ảnh nào được tạo</div>
                            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Nhập prompt mô tả ở trên và bấm [🎨 TẠO ẢNH AI NGAY] để bắt đầu!</div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- MENU TỰ ĐỘNG HÓA 3: TƯƠNG TÁC / SEEDING / NUÔI NICK (INTERACTION STUDIO) -->
            <section class="route-view" id="view-sub-interaction">
                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #2e1065 0%, #3b0764 100%); border-color:#a855f7;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span id="interactionBannerIcon">💬</span> <span id="interactionBannerTitle">Studio Tương Tác & Nuôi Nick Tự Động</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;" id="interactionBannerDesc">
                                Tự động lướt web nguồn, xem bài ngẫu nhiên để nuôi tài khoản (warmup nick), thả tim/like tự động và bình luận seeding trực tiếp qua Chrome tab.
                            </p>
                        </div>
                    </div>
                </div>

                <div class="grid-cards grid-responsive" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:18px; margin-bottom:20px;">
                    <!-- CARD 1: LƯỚT WEB NGUỒN TỰ ĐỘNG (WARMUP / NUÔI NICK) -->
                    <div class="card" style="border-color:#38bdf8;">
                        <h3 style="font-size:15px; color:#38bdf8; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                            <span>🌊</span> <span>1. Lướt Web Nguồn Tự Động (Nuôi Nick / Warmup)</span>
                        </h3>
                        <p style="font-size:12px; color:var(--text-muted); line-height:1.5; margin-bottom:14px;">
                            Trình duyệt Chrome sẽ tự động cuộn trang lên xuống ngẫu nhiên, dừng lại xem bài như người thật để tạo lịch sử duyệt web tự nhiên, tránh bị khóa tài khoản.
                        </p>
                        <div style="margin-bottom:12px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">⏱️ Thời Gian Tự Động Lướt:</label>
                            <select id="interactionSurfDuration" style="margin-top:4px;">
                                <option value="30">Lướt 30 giây (Nhanh)</option>
                                <option value="60" selected>Lướt 1 phút (Chuẩn)</option>
                                <option value="120">Lướt 2 phút (Khuyên dùng)</option>
                                <option value="300">Lướt 5 phút (Nuôi nick sâu)</option>
                            </select>
                        </div>
                        <button class="btn-lg" style="background:#0284c7; width:100%;" onclick="startAutoSurf()">
                            <span>🚀</span> <span>BẮT ĐẦU LƯỚT WEB NGUỒN TRÊN CHROME</span>
                        </button>
                    </div>

                    <!-- CARD 2: TỰ ĐỘNG LIKE / THẢ TIM -->
                    <div class="card" style="border-color:#f43f5e;">
                        <h3 style="font-size:15px; color:#f43f5e; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                            <span>❤️</span> <span>2. Tự Động Thả Tim / Like Bài Viết</span>
                        </h3>
                        <p style="font-size:12px; color:var(--text-muted); line-height:1.5; margin-bottom:14px;">
                            Tự động quét các bài viết trên trang web nguồn đang mở trên Chrome và click Like/Tim ngẫu nhiên theo khoảng thời gian an toàn.
                        </p>
                        <div style="margin-bottom:12px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">🎯 Số Lượng Bài Muốn Like:</label>
                            <select id="interactionLikeCount" style="margin-top:4px;">
                                <option value="3">3 bài ngẫu nhiên</option>
                                <option value="5" selected>5 bài ngẫu nhiên</option>
                                <option value="10">10 bài ngẫu nhiên</option>
                            </select>
                        </div>
                        <button class="btn-lg" style="background:#e11d48; width:100%;" onclick="startAutoLike()">
                            <span>❤️</span> <span>TỰ ĐỘNG LIKE TRÊN TAB CHROME</span>
                        </button>
                    </div>
                </div>

                <!-- CARD 3: SEEDING BÌNH LUẬN THEO KỊCH BẢN -->
                <div class="card" style="border-color:#10b981;">
                    <h3 style="font-size:15px; color:#10b981; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                        <span>💬</span> <span>3. Tự Động Bình Luận Seeding Theo Kịch Bản</span>
                    </h3>
                    <p style="font-size:12px; color:var(--text-muted); line-height:1.5; margin-bottom:14px;">
                        Nhập danh sách nội dung bình luận (mỗi dòng 1 câu). Hệ thống sẽ chọn ngẫu nhiên một câu và tự động nhập vào ô bình luận của bài viết đang xem.
                    </p>
                    <div style="margin-bottom:12px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">📝 Danh Sách Kịch Bản Bình Luận (Mỗi dòng 1 nội dung):</label>
                        <textarea id="interactionCommentsList" rows="4" style="margin-top:4px;" placeholder="Bài viết hay quá ạ!&#10;Quan tâm, check ib mình với nhé!&#10;Tuyệt vời luôn shop ơi&#10;Inbox giá giúp mình nhé"></textarea>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                        <button class="btn-green btn-lg" onclick="startAutoComment()">
                            <span>💬</span> <span>GỬI BÌNH LUẬN VÀO BÀI ĐANG XEM TRÊN CHROME</span>
                        </button>
                        <span id="interactionStatusText" style="font-size:12px; color:var(--text-muted); font-weight:600;"></span>
                    </div>
                </div>
            </section>

            <!-- 1. KIỂM TRA THÔNG TIN TÀI KHOẢN (MENU ĐẦU TIÊN THEO YÊU CẦU) -->
            <section class="route-view" id="view-sub-account-info">
                <!-- TOP ACTION BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #0b1730 0%, #151b3d 100%); border-color:#38bdf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span id="subAccBannerIcon">👤</span> <span id="subAccBannerTitle">Kiểm Tra Thông Tin Tài Khoản Facebook</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;" id="subAccBannerDesc">
                                Trích xuất toàn bộ danh tính, UID, trạng thái nick LIVE/DIE, cookie và token của tài khoản Facebook hiện đang login trên trình duyệt.
                            </p>
                        </div>
                        <button id="subAccBannerBtn" class="btn-green btn-lg" onclick="triggerPlatformScan()" style="box-shadow: 0 4px 18px rgba(16, 185, 129, 0.4);">
                            <span>🔄</span>
                            <span>QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FB</span>
                        </button>
                    </div>
                </div>

                <!-- PROFILE CARD (HỒ SƠ TÀI KHOẢN) -->
                <div class="card" style="margin-bottom:20px; border-color:#8b5cf6; background:#0f172a;">
                    <div style="display:flex; align-items:center; gap:18px; flex-wrap:wrap; margin-bottom:18px; border-bottom:1px solid rgba(255,255,255,0.06); padding-bottom:18px;">
                        <img id="fbAccAvatar" src="https://static.xx.fbcdn.net/rsrc.php/v3/yo/r/UlIqmHJn-SK.gif" referrerpolicy="no-referrer" style="width:72px; height:72px; border-radius:50%; border:3px solid var(--accent); object-fit:cover; background:#1e293b;" alt="Avatar FB" onerror="this.src='https://static.xx.fbcdn.net/rsrc.php/v3/yo/r/UlIqmHJn-SK.gif'" />
                        <div>
                            <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                                <h3 id="fbAccName" style="font-size:20px; font-weight:800; color:#fff; margin:0;">Chưa quét thông tin tài khoản</h3>
                                <span id="fbAccStatusBadge" class="status-pill" style="font-size:11px; padding:3px 10px;">⚪ Chưa kiểm tra</span>
                            </div>
                            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                                Trang dịch vụ: <a id="fbAccProfileLink" href="https://www.facebook.com" target="_blank" style="color:#38bdf8; text-decoration:none; font-weight:600;">https://www.facebook.com</a>
                            </div>
                        </div>
                    </div>

                    <!-- CẢNH BÁO & KHÓA CHỨC NĂNG KHI LỆCH TÀI KHOẢN SO VỚI TRÌNH DUYỆT CHROME -->
                    <div id="fbAccountMismatchAlert" style="display:none; margin-bottom:20px; padding:18px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(239, 68, 68, 0.18) 0%, rgba(153, 27, 27, 0.28) 100%); border:2px solid #ef4444; color:#fca5a5; box-shadow:0 6px 20px rgba(239, 68, 68, 0.25);">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;">
                            <div style="flex:1; min-width:280px;">
                                <div style="font-size:15px; font-weight:800; color:#ff4d4f; display:flex; align-items:center; gap:8px;">
                                    <span style="font-size:18px;">🔒</span> <span>ĐÃ KHÓA TOÀN BỘ CHỨC NĂNG DO SAI TÀI KHOẢN FACEBOOK!</span>
                                </div>
                                <div id="fbAccountMismatchAlertText" style="font-size:13px; color:#fecaca; margin-top:8px; line-height:1.6;">
                                    Tài khoản đang đăng nhập trên Chrome không khớp với Facebook UID của thư mục này. Tất cả các chức năng Đăng bài, Cào dữ liệu, Tương tác và Điều khiển đều bị khóa để bảo vệ dữ liệu.
                                </div>
                                <div style="margin-top:10px; font-size:12px; color:#fbcfe8; font-weight:600;">
                                    👉 Bạn chỉ có thể chọn 1 trong 2 giải pháp bên dưới để tiếp tục:
                                </div>
                            </div>
                            <div style="display:flex; flex-direction:column; gap:10px; align-items:stretch; min-width:320px;">
                                <button class="btn-green btn-md" onclick="quickCreateSubForBrowserUid()" style="box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4); font-weight:700; text-align:left; padding:9px 14px; font-size:12.5px;">
                                    <span>➕</span> <span><b>Cách 1:</b> Tạo Dự Án Con Mới Cho Nick Chrome Này</span>
                                </button>
                                <button class="btn-sm" onclick="rescanAndOverwriteFbAccount()" style="background:#dc2626; color:#fff; border:1px solid #ef4444; box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4); font-weight:700; text-align:left; padding:9px 14px; font-size:12.5px;">
                                    <span>🔄</span> <span><b>Cách 2:</b> Quét & Nạp Đè Toàn Bộ Vào Thư Mục Này</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- 4 STATS CARDS -->
                    <div class="grid-cards" style="margin-bottom:0;">
                        <div class="card" style="background:#090e1c;">
                            <div class="card-title" id="subStat1Label">Facebook UID (c_user)</div>
                            <div class="card-value" style="color:#38bdf8; font-size:18px;" id="fbAccUid">---</div>
                            <div style="margin-top:6px;">
                                <button class="btn-sm" style="background:#0284c7; padding:2px 8px; font-size:11px;" onclick="copyFbUid()">📋 Copy</button>
                            </div>
                        </div>
                        <div class="card" style="background:#090e1c;">
                            <div class="card-title" id="subStat2Label">Trạng Thái Đăng Nhập</div>
                            <div class="card-value" style="font-size:15px; margin-top:2px;" id="fbAccLoginStatus">⚪ Chưa có</div>
                            <div class="card-sub" id="fbAccLoginSub">Kiểm tra trên Chrome</div>
                        </div>
                        <div class="card" style="background:#090e1c;">
                            <div class="card-title" id="subStat3Label">Tổng Số Cookie FB</div>
                            <div class="card-value" style="color:#34d399; font-size:18px;" id="fbAccCookiesCount">0</div>
                            <div class="card-sub" id="subStat3Sub">Domain facebook.com</div>
                        </div>
                    </div>
                </div>

                <!-- 2. GIẢI MÃ & PHÂN TÍCH CHUYÊN SÂU COOKIE (DECODER & HEALTH INSPECTOR) -->
                <div class="card" style="margin-bottom:20px; border-color:#06b6d4; background: linear-gradient(180deg, #0b1528 0%, #0d1b33 100%);">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:14px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:12px;">
                        <div>
                            <h3 style="font-size:16px; font-weight:800; color:#38bdf8; display:flex; align-items:center; gap:8px; margin:0;">
                                <span>🔍</span> <span id="subCookieDecoderTitle">Giải Mã Cookie Facebook & Kiểm Tra Sức Khỏe Phiên</span>
                            </h3>
                            <p style="font-size:12px; color:#94a3b8; margin:4px 0 0 0;" id="subCookieDecoderDesc">
                                Bóc tách và phân tích các trường cookie bảo mật tối quan trọng (c_user, xs, datr, sb, fr) giúp tài khoản vượt Checkpoint 956/282 khi chạy Tool Auto.
                            </p>
                        </div>
                        <div id="subCookieHealthBadge" class="status-pill" style="font-size:12px; font-weight:700; padding:6px 14px; background:#1e293b; border:1px solid #334155; color:#cbd5e1;">
                            ⚪ Chưa Phân Tích Cookie
                        </div>
                    </div>

                    <!-- 5 TRỤ CỘT BẢO MẬT COOKIE FB -->
                    <div id="subFbCookiePillars" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom:18px;">
                        <!-- c_user Pillar -->
                        <div class="card" style="background:#070d1e; border:1px solid #1e293b; padding:12px; margin:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; color:#38bdf8; font-size:13px;">🆔 c_user (UID)</span>
                                <span id="subPillarCUserStatus" class="badge-folder" style="font-size:10px; background:#1e293b; color:#94a3b8;">Chưa có</span>
                            </div>
                            <div style="font-size:14px; font-weight:700; color:#fff; margin-top:6px; word-break:break-all;" id="subPillarCUserVal">---</div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;">User ID tài khoản Facebook</div>
                        </div>

                        <!-- xs Pillar -->
                        <div class="card" style="background:#070d1e; border:1px solid #1e293b; padding:12px; margin:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; color:#c084fc; font-size:13px;">🔐 xs (Session)</span>
                                <span id="subPillarXsStatus" class="badge-folder" style="font-size:10px; background:#1e293b; color:#94a3b8;">Chưa có</span>
                            </div>
                            <div style="font-size:12px; font-weight:600; color:#e2e8f0; margin-top:6px; word-break:break-all;" id="subPillarXsTime">---</div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;" id="subPillarXsDesc">Phiên xác thực & Thời điểm tạo</div>
                        </div>

                        <!-- datr Pillar -->
                        <div class="card" style="background:#070d1e; border:1px solid #1e293b; padding:12px; margin:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; color:#f59e0b; font-size:13px;">🛡️ datr (Anti-CP)</span>
                                <span id="subPillarDatrStatus" class="badge-folder" style="font-size:10px; background:#1e293b; color:#94a3b8;">Chưa có</span>
                            </div>
                            <div style="font-size:12px; font-weight:600; color:#e2e8f0; margin-top:6px; word-break:break-all;" id="subPillarDatrVal">---</div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;">Chống Checkpoint 956/282 (Hardware)</div>
                        </div>

                        <!-- sb Pillar -->
                        <div class="card" style="background:#070d1e; border:1px solid #1e293b; padding:12px; margin:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; color:#10b981; font-size:13px;">💻 sb (Device ID)</span>
                                <span id="subPillarSbStatus" class="badge-folder" style="font-size:10px; background:#1e293b; color:#94a3b8;">Chưa có</span>
                            </div>
                            <div style="font-size:12px; font-weight:600; color:#e2e8f0; margin-top:6px; word-break:break-all;" id="subPillarSbVal">---</div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;">Định danh trình duyệt máy trạm</div>
                        </div>

                        <!-- fr Pillar -->
                        <div class="card" style="background:#070d1e; border:1px solid #1e293b; padding:12px; margin:0;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; color:#ec4899; font-size:13px;">🔑 fr (Auth Token)</span>
                                <span id="subPillarFrStatus" class="badge-folder" style="font-size:10px; background:#1e293b; color:#94a3b8;">Chưa có</span>
                            </div>
                            <div style="font-size:12px; font-weight:600; color:#e2e8f0; margin-top:6px; word-break:break-all;" id="subPillarFrVal">---</div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;">Mã hóa xác thực phiên liên tục</div>
                        </div>
                    </div>

                    <!-- BỘ CÔNG CỤ DÁN & GIẢI MÃ COOKIE TÙY Ý (INTERACTIVE TOOL) -->
                    <div style="background:rgba(0,0,0,0.25); border:1px dashed #334155; border-radius:8px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
                            <div style="font-weight:700; font-size:13px; color:#fff; display:flex; align-items:center; gap:6px;">
                                <span>🧪</span> <span>Bộ Giải Mã & Chuyển Đổi Cookie Tùy Ý (Dán chuỗi cookie hoặc JSON vào đây):</span>
                            </div>
                            <div style="font-size:11px; color:#94a3b8;">
                                Hỗ trợ cả định dạng Text <code>c_user=...; xs=...;</code> và mảng JSON
                            </div>
                        </div>
                        <textarea id="customCookieInput" rows="3" placeholder="Dán chuỗi cookie cần giải mã vào đây (Ví dụ: c_user=10008928374; xs=29%3Aabc%3A2%3A...; datr=...; sb=...; fr=...)" style="width:100%; box-sizing:border-box; background:#070d1b; color:#e2e8f0; border:1px solid #334155; border-radius:6px; padding:10px; font-family:monospace; font-size:12px; resize:vertical;"></textarea>
                        
                        <div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap;">
                            <button class="btn-sm btn-green" onclick="runCustomCookieDecoder()" style="padding:6px 14px; font-weight:700;">
                                <span>🔍</span> <span>Giải Mã & Phân Tích Cookie Này</span>
                            </button>
                            <button class="btn-sm btn-purple" onclick="copyCustomDecodedJson()" style="padding:6px 14px;">
                                <span>📦</span> <span>Xuất & Copy Sang JSON</span>
                            </button>
                            <button class="btn-sm" style="background:#0284c7; padding:6px 14px;" onclick="copyCustomDecodedText()">
                                <span>📋</span> <span>Copy Dạng Chuỗi Chuẩn</span>
                            </button>
                            <button class="btn-sm btn-primary" onclick="applyCustomCookieToActiveSub()" style="padding:6px 14px; background:#4f46e5;">
                                <span>💾</span> <span>Lưu & Áp Dụng Ngay Cho Dự Án Con Này</span>
                            </button>
                            <button class="btn-sm" style="background:#334155; padding:6px 10px;" onclick="document.getElementById('customCookieInput').value=''; document.getElementById('customDecoderResultBox').style.display='none';">
                                <span>🧹</span> <span>Xóa</span>
                            </button>
                        </div>

                        <!-- RESULT DISPLAY FOR CUSTOM DECODER -->
                        <div id="customDecoderResultBox" style="display:none; margin-top:14px; background:#090f20; border:1px solid #1e293b; border-radius:6px; padding:12px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                                <div style="font-weight:700; color:#38bdf8; font-size:13px;" id="customDecoderResultHeader">Kết Quả Bóc Tách Cookie</div>
                                <span class="badge-folder" id="customDecoderBadge" style="background:#1e293b; color:#38bdf8;">0 phần tử</span>
                            </div>
                            <div id="customDecoderDetails" style="font-size:12px; color:#cbd5e1; line-height:1.5;"></div>
                        </div>
                    </div>
                </div>

                <!-- 3. BẢNG CHI TIẾT TỪNG PHẦN TỬ COOKIE FACEBOOK -->
                <div class="card" style="margin-bottom:20px; border-color:#38bdf8;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
                        <div>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <h4 style="font-size:15px; font-weight:800; color:#fff; margin:0;" id="subCookiesTableTitle">📑 Chi Tiết Từng Phần Tử Cookie Facebook</h4>
                                <span class="badge-folder" id="subCookiesCountBadge" style="background:#0284c7; color:#fff; font-weight:700;">0 Cookies</span>
                            </div>
                            <p style="font-size:12px; color:#94a3b8; margin:4px 0 0 0;" id="subCookiesTableDesc">
                                Bảng liệt kê toàn bộ các cookie đang lưu trữ, tên miền, đường dẫn, hạn dùng (expires) và cờ bảo mật (HttpOnly, Secure, SameSite).
                            </p>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                            <input type="text" id="subCookieSearchInput" placeholder="🔎 Lọc theo tên cookie (vd: xs, c_user...)..." oninput="filterSubCookiesTable(this.value)" style="background:#070d1b; color:#fff; border:1px solid #334155; border-radius:6px; padding:6px 12px; font-size:12px; width:220px;" />
                            <button class="btn-sm btn-purple" onclick="copyActiveSubCookieJson()">📋 Sao Chép JSON</button>
                            <button class="btn-sm btn-green" onclick="copyActiveSubCookieString()">📋 Sao Chép Chuỗi</button>
                        </div>
                    </div>

                    <div id="subCookiesTableContainer" style="overflow-x:auto;">
                        <div style="color:var(--text-muted); font-size:12px; padding:20px; text-align:center;">Chưa có dữ liệu cookie để hiển thị bảng. Bấm [QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FB] ở trên!</div>
                    </div>
                </div>

                <!-- RAW DATA PREVIEW -->
                <div class="card" style="margin-bottom:20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <h4 style="font-size:14px; color:#fff;">📋 Chuỗi Cookie Text (name=value; ...)</h4>
                        <div style="display:flex; gap:6px;">
                            <button class="btn-sm btn-green" onclick="copyActiveSubCookieString()">📋 Sao Chép Chuỗi Cookie</button>
                            <button class="btn-sm" style="background:#334155;" onclick="downloadActiveSubCookieFile()">📄 Tải File .txt</button>
                        </div>
                    </div>
                    <div class="raw-data-box" id="fbAccCookieStrBox">Chưa có Cookie. Hãy bấm nút [QUÉT] ở trên!</div>
                </div>

                <!-- JSON COOKIE PREVIEW IN MENU 1 -->
                <div class="card" style="margin-bottom:20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <h4 style="font-size:14px; color:#fff;">📦 Cookie Định Dạng JSON Chuẩn (Import Vào Tool Auto / Antidetect)</h4>
                        <div style="display:flex; gap:6px;">
                            <button class="btn-sm btn-purple" onclick="copyActiveSubCookieJson()">📋 Sao Chép JSON</button>
                            <button class="btn-sm" style="background:#475569;" onclick="downloadActiveSubCookieJsonFile()">📄 Tải File .json</button>
                        </div>
                    </div>
                    <div class="raw-data-box" id="fbAccCookieJsonBox" style="max-height:160px;">[]</div>
                </div>

            </section>

            <!-- PHÂN TÁCH: MÀN HÌNH THÔNG BÁO CHO CÁC NỀN TẢNG KHÁC (NGOÀI FACEBOOK) -->
            <section class="route-view" id="view-sub-other-notice">
                <div class="card" style="border-color:#38bdf8; background:linear-gradient(135deg, #091224 0%, #0d1a38 100%); margin-bottom:20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div style="display:flex; align-items:center; gap:14px;">
                            <div style="font-size:36px;" id="otherNoticeIcon">🌐</div>
                            <div>
                                <h3 style="font-size:17px; font-weight:800; color:#fff; margin:0;" id="otherNoticeTitle">Phân Loại Nền Tảng Tự Động Hóa</h3>
                                <div style="display:flex; gap:8px; align-items:center; margin-top:6px;" id="otherNoticeBadges"></div>
                            </div>
                        </div>
                        <button class="btn-sm" style="background:#0284c7; padding:6px 14px; font-weight:700;" onclick="switchSubMenu('sub-account-info')">
                            <span>🍪</span> <span>Xem Session & Cookie Nền Tảng Này</span>
                        </button>
                    </div>

                    <div style="margin-top:16px; background:#070d1e; border:1px solid #1e293b; border-radius:8px; padding:16px; font-size:13px; line-height:1.7; color:#cbd5e1;">
                        <b style="color:#38bdf8;">📌 LƯU Ý PHÂN TÁCH CHỨC NĂNG DỰ ÁN:</b><br/>
                        • Hiện tại hệ thống đang <b>tập trung phát triển sâu bộ công cụ tự động hóa chuyên biệt cho FACEBOOK</b> (Cào bài viết group/page/profile, Tự động đăng bài đa kênh, Seeding bình luận, Nuôi nick tương tác Newfeed, Giải mã & kiểm tra 5 trụ cột Cookie Facebook).<br/>
                        • Dự án con này thuộc nhóm <b style="color:#34d399;" id="otherNoticePlatformName">Nền tảng khác</b> với mã ID định danh riêng.<br/>
                        • Các menu tự động hóa của Facebook được <b>tự động ẩn đi</b> trong dự án con này để tránh xung đột kịch bản và không làm lẫn lộn dữ liệu.<br/>
                        • Bạn vẫn có thể dùng đầy đủ các tính năng: <b>Quản lý Session Cookie</b>, <b>Điều khiển Tab trên Chrome</b>, và <b>Thực thi lệnh JavaScript Console</b> cho nền tảng này!
                    </div>
                </div>
            </section>

            <!-- 4. BROWSER CONTROL -->
            <section class="route-view" id="view-sub-browser">
                <div class="card" style="margin-bottom:20px;">
                    <h3 style="font-size:15px; color:#fff; margin-bottom:12px;" id="subBrowserTitle">🌐 Điều Khiển Tab & Mở Facebook</h3>
                    
                    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px;" id="subBrowserQuickButtons">
                        <button class="btn-sm" onclick="projectOpenTab('https://www.facebook.com')">🌐 Facebook Web</button>
                        <button class="btn-sm" onclick="projectOpenTab('https://m.facebook.com')">📱 Mobile Facebook</button>
                        <button class="btn-sm btn-purple" onclick="projectOpenTab('https://business.facebook.com')">🏢 Meta Business</button>
                        <button class="btn-sm btn-orange" onclick="projectOpenTab('https://adsmanager.facebook.com')">📊 Ads Manager</button>
                    </div>

                    <label style="font-size:12px; font-weight:700; color:var(--text-muted);">Mở URL Tùy Chọn Trên Máy Chrome:</label>
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="subUrlInput" value="https://www.facebook.com" style="margin:0; flex:1;" />
                        <button onclick="projectOpenTab(document.getElementById('subUrlInput').value)">Mở Tab Mới</button>
                    </div>
                </div>

                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <h4 style="font-size:14px; color:#fff;">📑 Danh Sách Tab Đang Mở Trên Chrome</h4>
                        <button class="btn-sm btn-purple" onclick="sendProjectAction('GET_TABS')">🔄 Đọc Lại Tab</button>
                    </div>
                    <div id="subTabsContainer" style="overflow-x:auto;">
                        <div style="color:var(--text-muted); font-size:12px;">Bấm "Đọc Lại Tab" để hiển thị...</div>
                    </div>
                </div>
            </section>

            <!-- 5. SCRIPT CONSOLE -->
            <section class="route-view" id="view-sub-scripts">
                <div class="card" style="margin-bottom:20px;">
                    <h3 style="font-size:15px; color:#fff; margin-bottom:10px;">💻 JavaScript Console Trên Máy Này</h3>
                    
                    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                        <span class="preset-chip" onclick="setSubScript('document.title')">📄 Tiêu đề Tab</span>
                        <span class="preset-chip" onclick="setSubScript('window.location.href')">🔗 URL Hiện Tại</span>
                        <span class="preset-chip" onclick="setSubScript('document.cookie')">🍪 document.cookie</span>
                        <span class="preset-chip" onclick="setSubScript(`(function(){ window.scrollBy({ top: 600, behavior: 'smooth' }); return 'Đã cuộn 600px'; })()`)">📜 Cuộn Trang 600px</span>
                    </div>

                    <textarea id="subJsCode" rows="4" style="font-family:Consolas, monospace;">document.title</textarea>
                    <button class="btn-purple btn-lg" onclick="runSubScript()">🚀 Chạy JavaScript Trên Chrome</button>
                </div>

                <div class="card">
                    <h4 style="font-size:14px; color:#fff; margin-bottom:8px;">📤 Output Console</h4>
                    <div class="raw-data-box" id="subScriptOutputBox">Chưa có kết quả chạy script...</div>
                </div>
            </section>

            <!-- 6. LOGS -->
            <section class="route-view" id="view-sub-logs">
                <div class="card">
                    <h3 style="margin-bottom:12px; font-size:15px; color:#fff;">📜 Nhật Ký Hoạt Động</h3>
                    <div class="log-container" id="subLogBox">Chưa có nhật ký lệnh nào...</div>
                </div>
            </section>

        </main>

        <!-- FOOTER -->
        <footer class="bottom-footer">
            <div>⚡ <b>BAWUI EXTENSION PRO</b> © 2026 — Multi-Folder Controller</div>
            <div>Trạng thái: <span style="color:var(--success);">● Sẵn sàng</span> | Port 9999</div>
        </footer>
    </div>

    <!-- JAVASCRIPT CONTROLLER -->
    <script>
        // =========================================================
        // MOBILE SIDEBAR TOGGLE
        // =========================================================
        // Helper: trích xuất thông báo lỗi từ API response (hỗ trợ cả string và object)
        function extractErrorMsg(err, fallback) {
            if (!err) return fallback || "Lỗi không xác định";
            if (typeof err === 'string') return err;
            if (typeof err === 'object' && err.message) return err.message;
            try { return JSON.stringify(err); } catch(e) { return fallback || "Lỗi không xác định"; }
        }

        function toggleMobileSidebar() {
            document.body.classList.toggle('sidebar-open');
            const overlay = document.querySelector('.sidebar-overlay');
            if (document.body.classList.contains('sidebar-open')) {
                overlay.classList.add('active');
            } else {
                overlay.classList.remove('active');
            }
        }
        function closeMobileSidebar() {
            document.body.classList.remove('sidebar-open');
            const overlay = document.querySelector('.sidebar-overlay');
            if (overlay) overlay.classList.remove('active');
        }
        // Auto-close sidebar on window resize to desktop
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                closeMobileSidebar();
            }
        });

        // CẤU HÌNH MỤC ĐÍCH TỰ ĐỘNG HÓA CHO DỰ ÁN CON
        const PURPOSE_CONFIG = {
            "scraper": {
                name: "CÀO DỮ LIỆU",
                icon: "📥",
                badgeBg: "rgba(56,189,248,0.18)",
                badgeColor: "#38bdf8",
                badgeBorder: "rgba(56,189,248,0.4)",
                defaultMenu: "sub-scraper",
                desc: "Quét bài viết, bình luận, ảnh/video, text từ web nguồn."
            },
            "autopost": {
                name: "TỰ ĐỘNG ĐĂNG BÀI",
                icon: "🚀",
                badgeBg: "rgba(16,185,129,0.18)",
                badgeColor: "#34d399",
                badgeBorder: "rgba(16,185,129,0.4)",
                defaultMenu: "sub-autopost",
                desc: "Soạn thảo bài viết, lên lịch đăng bài và xuất bản tự động lên web nguồn."
            },
            "interaction": {
                name: "TƯƠNG TÁC / SEEDING",
                icon: "💬",
                badgeBg: "rgba(245,158,11,0.18)",
                badgeColor: "#fbbf24",
                badgeBorder: "rgba(245,158,11,0.4)",
                defaultMenu: "sub-scraper",
                desc: "Bình luận tự động, thả tim reaction, nuôi nick tương tác."
            },
            "session": {
                name: "QUẢN LÝ COOKIE & NICK",
                icon: "🔑",
                badgeBg: "rgba(168,85,247,0.18)",
                badgeColor: "#c084fc",
                badgeBorder: "rgba(168,85,247,0.4)",
                defaultMenu: "sub-account-info",
                desc: "Trích xuất cookie JSON/string, kiểm tra LIVE/DIE, giải mã 5 trụ cột bảo mật."
            }
        };

        // CẤU HÌNH CÁC NỀN TẢNG WEB NGUỒN (SOURCE WEBSITES)
        const PLATFORM_CONFIG = {
            "facebook": {
                name: "FACEBOOK",
                icon: "📘",
                badgeBg: "rgba(2,132,199,0.18)",
                badgeColor: "#38bdf8",
                badgeBorder: "rgba(2,132,199,0.4)",
                defaultDesc: "Quét cookie, UID, cào bài viết và đăng bài Facebook.",
                domain: "facebook.com",
                defaultUrl: "https://www.facebook.com",
                scrapeUrl: "https://www.facebook.com",
                postUrl: "https://www.facebook.com",
                serviceName: "Facebook Account"
            },
            "tiktok": {
                name: "TIKTOK",
                icon: "🎵",
                badgeBg: "rgba(236,72,153,0.18)",
                badgeColor: "#f472b6",
                badgeBorder: "rgba(236,72,153,0.4)",
                defaultDesc: "Quản lý cookie session, cào video và đăng bài TikTok.",
                domain: "tiktok.com",
                defaultUrl: "https://www.tiktok.com",
                scrapeUrl: "https://www.tiktok.com/explore",
                postUrl: "https://www.tiktok.com/creator-center/upload",
                serviceName: "TikTok Session"
            },
            "x": {
                name: "X (TWITTER)",
                icon: "𝕏",
                badgeBg: "rgba(148,163,184,0.18)",
                badgeColor: "#f8fafc",
                badgeBorder: "rgba(148,163,184,0.4)",
                defaultDesc: "Quản lý session x.com, cào tweets bài viết và tự động đăng bài X.",
                domain: "x.com",
                defaultUrl: "https://x.com",
                scrapeUrl: "https://x.com/explore",
                postUrl: "https://x.com/compose/post",
                serviceName: "X (Twitter) Session"
            },
            "instagram": {
                name: "INSTAGRAM",
                icon: "📸",
                badgeBg: "rgba(245,158,11,0.18)",
                badgeColor: "#fbbf24",
                badgeBorder: "rgba(245,158,11,0.4)",
                defaultDesc: "Quản lý tài khoản, cookie, cào Reels/ảnh và đăng bài Instagram.",
                domain: "instagram.com",
                defaultUrl: "https://www.instagram.com",
                scrapeUrl: "https://www.instagram.com/explore/",
                postUrl: "https://www.instagram.com",
                serviceName: "Instagram Profile"
            },
            "threads": {
                name: "THREADS",
                icon: "🧵",
                badgeBg: "rgba(168,85,247,0.18)",
                badgeColor: "#d8b4fe",
                badgeBorder: "rgba(168,85,247,0.4)",
                defaultDesc: "Quản lý session threads.net, cào bài thảo luận và đăng bài Threads.",
                domain: "threads.net",
                defaultUrl: "https://www.threads.net",
                scrapeUrl: "https://www.threads.net",
                postUrl: "https://www.threads.net",
                serviceName: "Threads Session"
            },
            "flow": {
                name: "GOOGLE FLOW",
                icon: "🌊",
                badgeBg: "rgba(6,182,212,0.18)",
                badgeColor: "#22d3ee",
                badgeBorder: "rgba(6,182,212,0.4)",
                defaultDesc: "Studio AI Image Generator & Workflow Google Flow.",
                domain: "flow.google.com",
                defaultUrl: "https://flow.google.com",
                scrapeUrl: "https://flow.google.com",
                postUrl: "https://flow.google.com",
                serviceName: "Google Flow AI Studio"
            },
            "custom": {
                name: "WEB TÙY CHỌN",
                icon: "⚡",
                badgeBg: "rgba(168,85,247,0.18)",
                badgeColor: "#c084fc",
                badgeBorder: "rgba(168,85,247,0.4)",
                defaultDesc: "Cào dữ liệu hoặc automation tab trên bất kỳ website nguồn nào.",
                domain: "google.com",
                defaultUrl: "https://www.google.com",
                scrapeUrl: "https://www.google.com",
                postUrl: "https://www.google.com",
                serviceName: "Custom Web Automation"
            }
        };

        let activeSourcePlatform = "facebook";

        function selectSourcePlatform(platform, element) {
            activeSourcePlatform = platform;
            document.querySelectorAll('#subPlatformSelectorGroup .source-card-option').forEach(el => el.classList.remove('active'));
            if (element) element.classList.add('active');

            const customBox = document.getElementById("customSourceUrlBox");
            if (customBox) {
                customBox.style.display = (platform === 'custom') ? "block" : "none";
            }
            updateFolderInputSuggestions();
        }

        function updateFolderInputSuggestions() {
            const nameInput = document.getElementById("newFolderName");
            const descInput = document.getElementById("newFolderDesc");
            const pCfg = PLATFORM_CONFIG[activeSourcePlatform] || PLATFORM_CONFIG["facebook"];

            if (nameInput) {
                nameInput.value = `Dự Án ${pCfg.name} 01`;
            }
            if (descInput) {
                descInput.value = `Quản lý nick, cookie, cào dữ liệu và tự động hóa ${pCfg.name} (${pCfg.domain})`;
            }
        }

        // HIERARCHY STATE
        let currentLevel = "hub";
        let currentProjectId = null;
        let currentSubProjectId = null;
        let allProjects = [];
        let projectPollInterval = null;
        let latestParentData = null;

        // 1. HUB NAVIGATION (LEVEL 1)
        const hubRoutes = {
            "hub-projects": { title: "📁 Danh Sách Dự Án Cha (Các Máy)", el: document.getElementById("view-hub-projects") },
            "hub-api": { title: "🔌 Cổng Tự Động Hóa REST API & Webhook", el: document.getElementById("view-hub-api") },
            "hub-vps": { title: "☁️ Cài Đặt VPS & Hướng Dẫn", el: document.getElementById("view-hub-vps") },
            "hub-manifest": { title: "⚙️ Đổi Tên & Cấu Hình Extension", el: document.getElementById("view-hub-manifest") },
            "hub-system": { title: "ℹ️ Thông Tin Hệ Thống", el: document.getElementById("view-hub-system") }
        };

        let isRoutingFromHash = false;

        function setRouterHash(newHash) {
            if (isRoutingFromHash) return;
            if (window.location.hash !== newHash) {
                history.pushState(null, "", newHash);
            }
        }

        function switchHubRoute(targetKey, updateHash = true) {
            closeMobileSidebar();
            document.querySelectorAll("#sidebar-hub-nav .menu-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-hub-route") === targetKey);
            });
            document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
            if (hubRoutes[targetKey] && hubRoutes[targetKey].el) {
                hubRoutes[targetKey].el.classList.add("active");
                document.getElementById("pageTitle").innerHTML = hubRoutes[targetKey].title;
                if (targetKey === "hub-api") {
                    populateApiTestProjects();
                }
            }

            if (updateHash && !isRoutingFromHash) {
                const cleanKey = targetKey.replace(/^hub-/, '');
                setRouterHash(`#/hub/${cleanKey}`);
            }
        }

        function populateApiTestProjects() {
            const select = document.getElementById("apiTestProjectSelect");
            if (!select) return;
            const baseUrlEl = document.getElementById("apiBaseUrlDisplay");
            if (baseUrlEl) baseUrlEl.innerText = window.location.origin;

            if (!allProjects || allProjects.length === 0) {
                select.innerHTML = '<option value="">(Chưa có dự án nào)</option>';
                return;
            }
            select.innerHTML = allProjects.map(p => {
                const sub = (p.subProjects || []).find(s => s.type === "facebook") || (p.subProjects || [])[0];
                const accName = sub ? (sub.fbName || sub.c_user || sub.name) : "Mặc định";
                return `<option value="${p.token}">${p.name} [Token: ${p.token}] — TK: ${accName}</option>`;
            }).join("");
        }

        function toggleApiTestTargetId() {
            const targetType = document.getElementById("apiTestTargetType").value;
            const wrap = document.getElementById("apiTestTargetIdWrap");
            if (wrap) {
                wrap.style.display = (targetType === "page" || targetType === "group") ? "block" : "none";
            }
        }

        async function executeApiTestPublish() {
            const btn = document.getElementById("btnApiTestSubmit");
            const resPre = document.getElementById("apiTestResponsePre");
            const statusSpan = document.getElementById("apiTestHttpStatus");
            const projectSelect = document.getElementById("apiTestProjectSelect");

            const token = projectSelect ? projectSelect.value : "";
            const content = document.getElementById("apiTestContent").value;
            const postType = document.getElementById("apiTestPostType").value;
            const targetType = document.getElementById("apiTestTargetType").value;
            const targetId = document.getElementById("apiTestTargetId").value;
            const mediaUrl = document.getElementById("apiTestMediaUrl").value;
            const seedingText = document.getElementById("apiTestSeeding").value;
            const autoReactType = document.getElementById("apiTestReact").value;

            if (!content && !mediaUrl) {
                alert("Vui lòng nhập nội dung hoặc URL media!");
                return;
            }

            const seedingComments = seedingText.split("\\n").map(s => s.trim()).filter(Boolean);

            btn.disabled = true;
            btn.innerHTML = `<span>⏳</span> <span>ĐANG GỬI YÊU CẦU TỚI BACKEND API...</span>`;
            resPre.innerText = "Đang gửi yêu cầu HTTP POST /api/v1/posts/publish...";
            resPre.style.color = "#38bdf8";
            statusSpan.innerText = "";

            try {
                const payload = {
                    content,
                    postType,
                    targetType,
                    targetId: (targetType === "page" || targetType === "group") ? targetId : "",
                    mediaUrl,
                    shareToFeed: true,
                    seedingComments,
                    autoReactType,
                    runNow: true
                };

                const res = await fetch("/api/v1/posts/publish", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                statusSpan.innerText = `HTTP ${res.status}`;
                statusSpan.style.color = res.ok ? "#34d399" : "#f87171";
                resPre.innerText = JSON.stringify(data, null, 2);
                resPre.style.color = res.ok ? "#34d399" : "#f87171";

                if (data.success) {
                    showToast("✅ Đã gửi lệnh đăng bài qua API thành công! Extension sẽ nhận và xử lý ngay.", "success");
                } else {
                    showToast(`⚠️ Lỗi API: ${data.error || "Không thành công"}`, "error");
                }
            } catch(err) {
                statusSpan.innerText = "Lỗi Mạng";
                statusSpan.style.color = "#f87171";
                resPre.innerText = `Lỗi kết nối: ${err.message}`;
                resPre.style.color = "#f87171";
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<span>🚀</span> <span>GỬI THỬ LỆNH API ĐĂNG BÀI NGAY</span>`;
            }
        }

        // 2. PARENT PROJECT NAVIGATION (LEVEL 2)
        const parentRoutes = {
            "parent-subprojects": { title: "📂 Danh Sách Dự Án Con", el: document.getElementById("view-parent-subprojects") },
            "parent-machine": { title: "🖥️ Thông Tin Máy & Chrome", el: document.getElementById("view-parent-machine") },
            "parent-logs": { title: "📜 Nhật Ký Hoạt Động Máy", el: document.getElementById("view-parent-logs") }
        };

        function switchParentRoute(targetKey, updateHash = true) {
            document.querySelectorAll("#sidebar-parent-nav .menu-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-parent-route") === targetKey);
            });
            document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
            if (parentRoutes[targetKey] && parentRoutes[targetKey].el) {
                parentRoutes[targetKey].el.classList.add("active");
                const p = allProjects.find(x => x.id === currentProjectId);
                const pName = p ? p.name : "Dự Án Cha";
                document.getElementById("pageTitle").innerHTML = `📁 <b>${pName}</b> &rarr; ${parentRoutes[targetKey].title}`;
            }

            if (updateHash && !isRoutingFromHash && currentProjectId) {
                const cleanKey = targetKey.replace(/^parent-/, '');
                setRouterHash(`#/project/${currentProjectId}/${cleanKey}`);
            }
        }

        // 3. SUB-PROJECT MENU NAVIGATION (LEVEL 3)
        const subMenus = {
            "sub-account-info": { title: "👤 Thông Tin & Cookie FB", el: document.getElementById("view-sub-account-info") },
            "sub-scraper": { title: "📥 Cào Dữ Liệu Facebook (Scraper)", el: document.getElementById("view-sub-scraper") },
            "sub-autopost": { title: "📝 POST FACEBOOK — Đăng Bài Viết Thường", el: document.getElementById("view-sub-autopost") },
            "sub-post-video": { title: "🎬 POST FACEBOOK — Facebook Video Watch", el: document.getElementById("view-sub-post-video") },
            "sub-post-reels": { title: "⚡ POST FACEBOOK — Facebook Reels", el: document.getElementById("view-sub-post-reels") },
            "sub-post-story": { title: "📖 POST FACEBOOK — Facebook Story", el: document.getElementById("view-sub-post-story") },
            "sub-api-doc": { title: "📖 POST FACEBOOK — Chi Tiết Các Endpoint API", el: document.getElementById("view-sub-api-doc") },
            "sub-post-manager": { title: "📑 POST FACEBOOK — Quản Lý Bài Viết Đã Đăng", el: document.getElementById("view-sub-post-manager") },
            "sub-flow-image": { title: "🎨 GOOGLE FLOW — Tạo Ảnh AI", el: document.getElementById("view-sub-flow-image") },
            "sub-interaction": { title: "💬 Studio Tương Tác / Nuôi Nick FB", el: document.getElementById("view-sub-interaction") },
            "sub-other-notice": { title: "💡 Trạng Thái Tự Động Hóa Nền Tảng", el: document.getElementById("view-sub-other-notice") },
            "sub-browser": { title: "🌐 Điều Khiển Tab Facebook", el: document.getElementById("view-sub-browser") },
            "sub-scripts": { title: "💻 JavaScript Console", el: document.getElementById("view-sub-scripts") },
            "sub-logs": { title: "📜 Nhật Ký Lệnh", el: document.getElementById("view-sub-logs") }
        };

        // KIỂM TRA LỆCH TÀI KHOẢN FACEBOOK VỚI CHROME
        function checkSubProjectMismatch(sub) {
            if (!sub) return { isMismatch: false, cUser: "", browserFbUid: "" };
            const subType = sub.type || 'facebook';
            if (subType !== 'facebook') return { isMismatch: false, cUser: "", browserFbUid: "" };
            
            const cUser = sub.c_user ? String(sub.c_user).trim() : "";
            const nodes = (latestParentData && latestParentData.nodes) || [];
            const activeNode = nodes[0] || null;
            const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";

            const isMismatch = !!(cUser && browserFbUid && browserFbUid !== cUser);
            return { isMismatch, cUser, browserFbUid };
        }

        function switchSubMenu(targetKey, updateHash = true) {
            closeMobileSidebar();
            if (targetKey === "sub-cookies" || targetKey === "sub-token") targetKey = "sub-account-info";

            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = sub ? (sub.type || 'facebook') : 'facebook';

            // KHÓA TOÀN BỘ CHỨC NĂNG NẾU LỆCH TÀI KHOẢN TRÊN CHROME
            const mismatchStatus = checkSubProjectMismatch(sub);
            if (mismatchStatus.isMismatch && targetKey !== 'sub-account-info') {
                alert(`🔒 TÍNH NĂNG BỊ KHÓA DO KHÁC TÀI KHOẢN!\n\nThư mục này của Nick UID: ${mismatchStatus.cUser}\nTrong khi Chrome đang đăng nhập Nick UID: ${mismatchStatus.browserFbUid}\n\n👉 Bạn chỉ có thể:\n1. Tạo Dự Án Con mới cho Nick Chrome này\n2. Hoặc bấm Quét & Nạp Đè toàn bộ vào thư mục này!`);
                targetKey = 'sub-account-info';
            }

            // Phân biệt rõ: Nếu không phải Facebook, không mở các menu tự động hóa của Facebook
            if (subType !== 'facebook') {
                if (subType === 'flow') {
                    // FLOW: cho phép sub-flow-image, chặn các menu Facebook
                    if (targetKey === 'sub-scraper' || targetKey === 'sub-autopost' || targetKey === 'sub-post-video' || targetKey === 'sub-post-reels' || targetKey === 'sub-post-story' || targetKey === 'sub-api-doc' || targetKey === 'sub-post-manager' || targetKey === 'sub-interaction') {
                        targetKey = 'sub-flow-image';
                    }
                } else {
                    // CÁC NỀN TẢNG KHÁC: chặn tất cả menu FB + Flow
                    if (targetKey === 'sub-scraper' || targetKey === 'sub-autopost' || targetKey === 'sub-post-video' || targetKey === 'sub-post-reels' || targetKey === 'sub-post-story' || targetKey === 'sub-api-doc' || targetKey === 'sub-post-manager' || targetKey === 'sub-interaction' || targetKey === 'sub-flow-image') {
                        targetKey = 'sub-other-notice';
                    }
                }
            } else {
                if (targetKey === 'sub-other-notice' || targetKey === 'sub-flow-image') {
                    targetKey = 'sub-account-info';
                }
            }

            document.querySelectorAll("#sidebar-sub-nav .menu-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-sub-menu") === targetKey);
            });

            // Đồng bộ trạng thái nhóm POST FACEBOOK
            const postFbGroup = document.getElementById("sideMenuPostFbGroup");
            const postFbTree = document.getElementById("postFbSubTree");
            if (postFbGroup) {
                const isUnderPostFb = (
                    targetKey === 'sub-autopost' || 
                    targetKey === 'sub-post-video' || 
                    targetKey === 'sub-post-reels' || 
                    targetKey === 'sub-post-story' || 
                    targetKey === 'sub-api-doc' ||
                    targetKey === 'sub-post-manager'
                );
                postFbGroup.classList.toggle("active-parent", isUnderPostFb);
                if (isUnderPostFb && postFbTree) {
                    postFbTree.classList.remove("collapsed");
                    postFbGroup.classList.add("expanded");
                }
            }

            document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
            if (subMenus[targetKey] && subMenus[targetKey].el) {
                subMenus[targetKey].el.classList.add("active");
                const pName = p ? p.name : "Dự Án Cha";
                const subName = sub ? sub.name : "Dự Án Con";
                const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];
                document.getElementById("pageTitle").innerHTML = `📁 ${pName} &gt; 📂 <b>${subName}</b> [${pCfg.icon} ${pCfg.name}] &rarr; ${subMenus[targetKey].title}`;
                if (targetKey === 'sub-api-doc') {
                    updateSubApiDocView();
                }
            }

            if (updateHash && !isRoutingFromHash && currentProjectId && currentSubProjectId) {
                const cleanKey = targetKey.replace(/^sub-/, '');
                setRouterHash(`#/project/${currentProjectId}/sub/${currentSubProjectId}/${cleanKey}`);
            }
        }

        function handlePostFbParentClick() {
            const postFbTree = document.getElementById("postFbSubTree");
            const postFbGroup = document.getElementById("sideMenuPostFbGroup");
            if (postFbTree) {
                const isCollapsed = postFbTree.classList.toggle("collapsed");
                if (postFbGroup) postFbGroup.classList.toggle("expanded", !isCollapsed);
            }
            const activePostFbItem = document.querySelector("#postFbSubTree .menu-item.active");
            if (!activePostFbItem) {
                switchSubMenu('sub-autopost');
            }
        }

        function updateSubApiDocView() {
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (!p || !sub) return;

            const token = p.token || "";
            const subId = sub.id || "";
            const accName = sub.fbName || sub.name || "Facebook";
            const uid = sub.c_user || "Chưa có UID";
            const origin = window.location.origin;

            const tokenEl = document.getElementById("subApiTokenVal");
            if (tokenEl) tokenEl.innerText = token;
            const subIdEl = document.getElementById("subApiSubIdVal");
            if (subIdEl) subIdEl.innerText = subId;
            const accEl = document.getElementById("subApiAccountInfo");
            if (accEl) accEl.innerText = `${accName} (UID: ${uid})`;
            const baseEl = document.getElementById("subApiBaseUrlVal");
            if (baseEl) baseEl.innerText = origin;

            // Tính toán thời gian mẫu 1 giờ sau cho scheduledAt
            const sampleDate = new Date(Date.now() + 3600000);
            const sampleIso = sampleDate.toISOString();

            const curlEl = document.getElementById("subApiCurlCode");
            if (curlEl) {
                curlEl.innerText = `# 1. PHÁT LỆNH ĐĂNG BÀI NGAY LẬP TỨC (RUN NOW):
curl -X POST "${origin}/api/v1/posts" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${token}" \\
  -d '{
    "subProjectId": "${subId}",
    "title": "Bản tin khuyến mãi mới",
    "content": "{Chào bạn|Hello cả nhà}! Ưu đãi đặc biệt {chỉ hôm nay|trong tuần này}.",
    "postType": "post",
    "targetType": "profile",
    "seedingComments": ["Sản phẩm còn hàng không shop?", "Tư vấn mình với ạ"],
    "autoReactType": "LOVE",
    "runNow": true
  }'

# 2. LÊN LỊCH HẸN GIỜ ĐĂNG TỰ ĐỘNG (SCHEDULED POST):
curl -X POST "${origin}/api/v1/posts" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${token}" \\
  -d '{
    "subProjectId": "${subId}",
    "content": "Bài viết tự động hẹn giờ xuất bản: {Tuyệt đỉnh|Siêu hot}!",
    "scheduledAt": "${sampleIso}",
    "runNow": false
  }'

# 3. KIỂM TRA TRẠNG THÁI & LẤY LINK FACEBOOK CỦA BÀI ĐĂNG:
curl -X GET "${origin}/api/v1/posts/<POST_ID>" \\
  -H "Authorization: Bearer ${token}"

# 4. ĐỔI GIỜ HẸN ĐĂNG (RESCHEDULE) HOẶC KÍCH HOẠT ĐĂNG NGAY:
# Đổi giờ hẹn:
curl -X PATCH "${origin}/api/v1/posts/<POST_ID>" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${token}" \\
  -d '{"scheduledAt": "${sampleIso}"}'

# Kích hoạt đăng ngay không cần chờ:
curl -X POST "${origin}/api/v1/posts/<POST_ID>/run" \\
  -H "Authorization: Bearer ${token}"`;
            }

            const pyEl = document.getElementById("subApiPythonCode");
            if (pyEl) {
                pyEl.innerText = `import requests
from datetime import datetime, timedelta, timezone

BASE_URL = "${origin}"
TOKEN = "${token}"
SUB_ID = "${subId}"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

# --- 1. ĐĂNG BÀI NGAY LẬP TỨC ---
post_now_payload = {
    "subProjectId": SUB_ID,
    "title": "Ưu đãi tri ân khách hàng",
    "content": "Chào mừng bạn! {Nhiều quà tặng|Ưu đãi sốc} hôm nay!",
    "postType": "post",
    "targetType": "profile",
    "seedingComments": ["Sản phẩm tốt lắm", "Inbox giá giúp mình"],
    "autoReactType": "LOVE",
    "runNow": True
}
res = requests.post(f"{BASE_URL}/api/v1/posts", json=post_now_payload, headers=headers)
print("Kết quả đăng ngay:", res.json())

# --- 2. LÊN LỊCH HẸN GIỜ ĐĂNG TỰ ĐỘNG (Ví dụ sau 1 giờ) ---
scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
schedule_payload = {
    "subProjectId": SUB_ID,
    "title": "Bài viết lên lịch tự động",
    "content": "Bài viết được xuất bản tự động theo lịch hẹn giờ {chính xác|an toàn}.",
    "scheduledAt": scheduled_time,
    "runNow": False
}
res_sched = requests.post(f"{BASE_URL}/api/v1/posts", json=schedule_payload, headers=headers)
created = res_sched.json()
print("Kết quả lên lịch:", created)
post_id = created.get("data", {}).get("postId")

# --- 3. KIỂM TRA TRẠNG THÁI BÀI ĐĂNG ---
if post_id:
    res_status = requests.get(f"{BASE_URL}/api/v1/posts/{post_id}", headers=headers)
    print("Trạng thái bài đăng:", res_status.json())`;
            }

            const jsEl = document.getElementById("subApiJsCode");
            if (jsEl) {
                jsEl.innerText = `const BASE_URL = "${origin}";
const TOKEN = "${token}";
const SUB_ID = "${subId}";

const headers = {
  "Content-Type": "application/json",
  "Authorization": \`Bearer \${TOKEN}\`
};

// 1. Phát lệnh đăng bài ngay lập tức
async function createPostNow() {
  const res = await fetch(\`\${BASE_URL}/api/v1/posts\`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      subProjectId: SUB_ID,
      title: "Bài viết phát hành tức thì",
      content: "{Chào bạn|Hello}! Bài viết đăng tự động qua REST API với {nhiều ưu đãi|quà tặng hấp dẫn}.",
      postType: "post",
      targetType: "profile",
      seedingComments: ["Quan tâm shop ơi", "Check ib giúp mình nhé"],
      autoReactType: "LOVE",
      runNow: true
    })
  });
  return await res.json();
}

// 2. Lên lịch hẹn giờ đăng tự động (sau 1 giờ)
async function schedulePost(hoursFromNow = 1) {
  const scheduledAt = new Date(Date.now() + hoursFromNow * 3600 * 1000).toISOString();
  const res = await fetch(\`\${BASE_URL}/api/v1/posts\`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      subProjectId: SUB_ID,
      content: "Bài viết hẹn giờ xuất bản tự động trên Facebook!",
      scheduledAt: scheduledAt,
      runNow: false
    })
  });
  return await res.json();
}

// 3. Kiểm tra trạng thái bài đăng
async function getPostStatus(postId) {
  const res = await fetch(\`\${BASE_URL}/api/v1/posts/\${postId}\`, { headers });
  return await res.json();
}

// 4. Kích hoạt đăng ngay không cần chờ lịch
async function triggerRunNow(postId) {
  const res = await fetch(\`\${BASE_URL}/api/v1/posts/\${postId}/run\`, {
    method: "POST",
    headers
  });
  return await res.json();
}`;
            }
        }

        function copySubApiToken() {
            const tokenEl = document.getElementById("subApiTokenVal");
            if (tokenEl && tokenEl.innerText) {
                navigator.clipboard.writeText(tokenEl.innerText.trim());
                showToast("📋 Đã copy Project Token vào clipboard!", "success");
            }
        }

        function copySubApiBaseUrl() {
            navigator.clipboard.writeText(window.location.origin);
            showToast("📋 Đã copy Base URL vào clipboard!", "success");
        }

        // =========================================================
        // TRANSITIONS BETWEEN LEVELS
        // =========================================================

        function enterParentProject(projId, targetRoute = "parent-subprojects", updateHash = true) {
            closeMobileSidebar();
            currentProjectId = projId;
            currentSubProjectId = null;
            currentLevel = "parent";
            localStorage.setItem("active_parent_id", projId);
            localStorage.removeItem("active_sub_id");

            const proj = allProjects.find(p => p.id === projId);
            const projName = proj ? proj.name : "Dự án";
            const projToken = proj ? proj.token : "";

            document.getElementById("sidebar-hub-nav").style.display = "none";
            document.getElementById("sidebar-parent-nav").style.display = "block";
            document.getElementById("sidebar-sub-nav").style.display = "none";

            document.getElementById("sidebarParentName").textContent = projName;
            document.getElementById("sidebarParentToken").textContent = projToken;
            const parentSubHeaderTitle = document.getElementById("parentSubHeaderTitle");
            if (parentSubHeaderTitle) parentSubHeaderTitle.textContent = `Các Thư Mục / Dự Án Con Của [${projName}]`;

            switchParentRoute(targetRoute || "parent-subprojects", updateHash);

            fetchParentProjectData(projId);
            if (projectPollInterval) clearInterval(projectPollInterval);
            projectPollInterval = setInterval(() => {
                if (currentProjectId) fetchParentProjectData(currentProjectId);
            }, 2500);

            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        function exitToHub(updateHash = true) {
            closeMobileSidebar();
            currentLevel = "hub";
            currentProjectId = null;
            currentSubProjectId = null;
            localStorage.removeItem("active_parent_id");
            localStorage.removeItem("active_sub_id");
            if (projectPollInterval) clearInterval(projectPollInterval);

            document.getElementById("sidebar-hub-nav").style.display = "block";
            document.getElementById("sidebar-parent-nav").style.display = "none";
            document.getElementById("sidebar-sub-nav").style.display = "none";

            switchHubRoute("hub-projects", updateHash);
            fetchProjects();
        }

        function enterSubProject(subId, targetMenu = "sub-account-info", updateHash = true) {
            closeMobileSidebar();
            currentSubProjectId = subId;
            currentLevel = "sub";
            localStorage.setItem("active_sub_id", subId);

            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === subId) : null;
            const subName = sub ? sub.name : "Dự Án Con";
            const subType = (sub && sub.type) ? sub.type : "facebook";
            const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];

            document.getElementById("sidebar-hub-nav").style.display = "none";
            document.getElementById("sidebar-parent-nav").style.display = "none";
            document.getElementById("sidebar-sub-nav").style.display = "block";

            document.getElementById("sidebarSubName").textContent = subName;
            document.getElementById("sidebarSubBelong").innerHTML = `
                <div style="margin-bottom:6px; display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
                    <span class="badge-folder" style="background:${pCfg.badgeBg}; color:${pCfg.badgeColor}; border:1px solid ${pCfg.badgeBorder}; padding:2px 8px; font-size:11px; font-weight:800;">
                        ${pCfg.icon} ${pCfg.name}
                    </span>
                    <span class="badge-folder" style="background:#070d1e; color:#38bdf8; border:1px solid #1e293b; padding:2px 8px; font-size:10px; font-family:monospace; font-weight:700;">
                        🆔 ${subId}
                    </span>
                </div>
                <div style="font-size:11px; color:#64748b; margin-top:2px;">Máy: ${proj ? proj.name : ''}</div>
            `;

            adaptSubMenuForPlatform(subType, pCfg, subId);

            // Mở menu chỉ định (mặc định sub-account-info)
            switchSubMenu(targetMenu || "sub-account-info", updateHash);

            if (sub) renderSubProjectWorkspace(sub);

            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        function adaptSubMenuForPlatform(subType, pCfg, subId) {
            const isFb = (subType === 'facebook');

            const autoLabel = document.getElementById("sideMenuAutomationLabel");
            const postFbGroup = document.getElementById("sideMenuPostFbGroup");
            const postFbTree = document.getElementById("postFbSubTree");
            const scraperItem = document.getElementById("sideMenuScraperItem");
            const interactionItem = document.getElementById("sideMenuInteractionItem");
            const otherNoticeItem = document.getElementById("sideMenuOtherNoticeItem");
            const sideAccount = document.getElementById("sideMenuAccountTitle");
            const sideBrowser = document.getElementById("sideMenuBrowserTitle");

            if (isFb) {
                // FACEBOOK: ĐẦY ĐỦ 100% CÔNG CỤ TỰ ĐỘNG HÓA FB
                if (autoLabel) { autoLabel.textContent = "Chức Năng Tự Động Hóa"; autoLabel.style.display = "flex"; }
                if (postFbGroup) postFbGroup.style.display = "block";
                if (postFbTree) postFbTree.style.display = "flex";
                if (scraperItem) scraperItem.style.display = "block";
                if (interactionItem) interactionItem.style.display = "block";
                if (otherNoticeItem) otherNoticeItem.style.display = "none";
                const flowImageItemFb = document.getElementById("sideMenuFlowImageItem");
                if (flowImageItemFb) flowImageItemFb.style.display = "none";
                if (sideAccount) sideAccount.textContent = "Thông Tin & Cookie FB";
                if (sideBrowser) sideBrowser.textContent = "Điều Khiển Tab Facebook";
            } else {
                // CÁC NỀN TẢNG KHÁC (TIKTOK, FLOW, X...): ẨN CÁC TOOL FB ĐỂ KHÔNG BỊ TRỘN LẪN
                if (autoLabel) { autoLabel.textContent = `Chức Năng ${pCfg.name}`; autoLabel.style.display = "flex"; }
                if (postFbGroup) postFbGroup.style.display = "none";
                if (postFbTree) postFbTree.style.display = "none";
                if (scraperItem) scraperItem.style.display = "none";
                if (interactionItem) interactionItem.style.display = "none";
                if (otherNoticeItem) {
                    otherNoticeItem.style.display = "block";
                    const otherNoticeTitle = document.getElementById("sideMenuOtherNoticeTitle");
                    if (otherNoticeTitle) otherNoticeTitle.textContent = `Kịch Bản ${pCfg.name}`;
                }
                
                // Google Flow: Hiển thị menu Tạo Ảnh AI
                const flowImageItem = document.getElementById("sideMenuFlowImageItem");
                if (flowImageItem) {
                    flowImageItem.style.display = (subType === 'flow') ? 'block' : 'none';
                }
                if (subType === 'flow' && otherNoticeItem) {
                    otherNoticeItem.style.display = 'none';
                }

                if (sideAccount) sideAccount.textContent = `Tài Khoản & Cookie ${pCfg.name}`;
                if (sideBrowser) sideBrowser.textContent = `Điều Khiển Tab ${pCfg.name}`;

                // Cập nhật thông tin trong view notice nền tảng khác
                const onIcon = document.getElementById("otherNoticeIcon");
                if (onIcon) onIcon.textContent = pCfg.icon;
                const onTitle = document.getElementById("otherNoticeTitle");
                if (onTitle) onTitle.textContent = `Dự Án Con: ${pCfg.name}`;
                const onPlatform = document.getElementById("otherNoticePlatformName");
                if (onPlatform) onPlatform.textContent = pCfg.name;
                const onBadges = document.getElementById("otherNoticeBadges");
                if (onBadges) {
                    onBadges.innerHTML = `
                        <span class="badge-folder" style="background:${pCfg.badgeBg}; color:${pCfg.badgeColor}; border:1px solid ${pCfg.badgeBorder}; font-weight:700;">${pCfg.icon} ${pCfg.name}</span>
                        <span class="badge-folder" style="background:#070d1e; color:#38bdf8; border:1px solid #334155; font-family:monospace; font-weight:700;">🆔 ${subId || ''}</span>
                    `;
                }
            }

            // Cập nhật tiêu đề bảng và bộ giải mã cookie
            const cookiesTableTitle = document.getElementById("subCookiesTableTitle");
            const cookiesTableDesc = document.getElementById("subCookiesTableDesc");
            const cookieDecoderTitle = document.getElementById("subCookieDecoderTitle");
            const cookieDecoderDesc = document.getElementById("subCookieDecoderDesc");
            const pillarsBox = document.getElementById("subFbCookiePillars");

            if (cookiesTableTitle) cookiesTableTitle.textContent = `📑 Chi Tiết Từng Phần Tử Cookie ${pCfg.name}`;
            if (cookiesTableDesc) cookiesTableDesc.textContent = `Bảng liệt kê toàn bộ các cookie đang lưu trữ của ${pCfg.name} (${pCfg.domain}), hạn dùng (expires) và cờ bảo mật.`;

            if (isFb) {
                if (cookieDecoderTitle) cookieDecoderTitle.textContent = "Giải Mã Cookie Facebook & Kiểm Tra Sức Khỏe Phiên";
                if (cookieDecoderDesc) cookieDecoderDesc.textContent = "Bóc tách và phân tích các trường cookie bảo mật tối quan trọng (c_user, xs, datr, sb, fr) giúp tài khoản vượt Checkpoint 956/282 khi chạy Tool Auto.";
                if (pillarsBox) pillarsBox.style.display = "grid";
            } else {
                if (cookieDecoderTitle) cookieDecoderTitle.textContent = `Giải Mã Cookie ${pCfg.name} & Kiểm Tra Phiên`;
                if (cookieDecoderDesc) cookieDecoderDesc.textContent = `Phân tích cấu trúc session cookie và kiểm tra tính toàn vẹn của tài khoản ${pCfg.name} (${pCfg.domain}).`;
                if (pillarsBox) pillarsBox.style.display = "none";
            }

            // KHÓA / MỞ KHÓA THANH ĐIỀU HƯỚNG BÊN TRÁI NẾU SAI TÀI KHOẢN
            const projObj = allProjects.find(p => p.id === currentProjectId);
            const subObj = projObj ? (projObj.subProjects || []).find(s => s.id === (subId || currentSubProjectId)) : null;
            const mismatchStatus = checkSubProjectMismatch(subObj);

            const lockedMenuIds = [
                "sideMenuPostFbGroup",
                "postFbSubTree",
                "sideMenuScraperItem",
                "sideMenuInteractionItem",
                "sideMenuBrowserItem",
                "sideMenuScriptsItem"
            ];

            if (mismatchStatus.isMismatch) {
                lockedMenuIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.style.opacity = "0.35";
                        el.style.filter = "grayscale(100%)";
                        el.style.cursor = "not-allowed";
                        el.setAttribute("title", `🔒 Bị khóa do lệch tài khoản (Chrome: ${mismatchStatus.browserFbUid} ≠ Thư mục: ${mismatchStatus.cUser})`);
                    }
                });
                if (autoLabel) {
                    autoLabel.innerHTML = `<span>Chức Năng Tự Động Hóa</span> <span style="color:#ef4444; font-size:10px; font-weight:800; margin-left:4px;">🔒 [BỊ KHÓA]</span>`;
                }
            } else {
                lockedMenuIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.style.opacity = "1";
                        el.style.filter = "none";
                        el.style.cursor = "pointer";
                        el.removeAttribute("title");
                    }
                });
                if (autoLabel) {
                    autoLabel.textContent = isFb ? "Chức Năng Tự Động Hóa" : `Chức Năng ${pCfg.name}`;
                }
            }
        }

        function exitToParentProject(updateHash = true) {
            if (currentProjectId) {
                enterParentProject(currentProjectId, "parent-subprojects", updateHash);
            } else {
                exitToHub(updateHash);
            }
        }

        // =========================================================
        // DATA FETCHING & RENDERING
        // =========================================================

        async function fetchProjects() {
            try {
                const res = await fetch("/api/projects");
                const data = await res.json();
                if (!data.success) return;

                allProjects = data.projects || [];
                const container = document.getElementById("hubProjectsListContainer");
                if (!container) return;

                if (allProjects.length === 0) {
                    container.innerHTML = '<div style="color:var(--text-muted); font-size:13px;">Chưa có dự án nào. Hãy bấm "Tạo Dự Án Cha Mới" ở trên!</div>';
                    return;
                }

                container.innerHTML = allProjects.map(p => {
                    const isOnline = p.nodeCount > 0;
                    const nodeName = isOnline && p.nodes && p.nodes[0] ? p.nodes[0].nodeName : "";
                    const subCount = (p.subProjects || []).length;
                    return `
                    <div class="card" style="background:#0f172a; border-color:${isOnline ? 'var(--accent)' : 'var(--border-color)'}; display:flex; flex-direction:column; justify-content:space-between;">
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                                <div>
                                    <h3 style="margin:0; font-size:16px; color:#fff; font-weight:800;">📁 ${p.name}</h3>
                                    <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                                        Tạo lúc: ${new Date(p.createdAt).toLocaleDateString()} | <b>${subCount} Thư Mục Con</b>
                                    </div>
                                </div>
                                <span class="status-pill" style="color:${isOnline ? 'var(--success)' : '#94a3b8'};">
                                    <span class="dot ${isOnline ? 'online' : ''}"></span>
                                    ${isOnline ? (nodeName || p.nodeCount + ' Máy Online') : '○ 0 Máy'}
                                </span>
                            </div>

                            <p style="font-size:12px; color:#cbd5e1; margin-bottom:14px; min-height:36px; line-height:1.5;">
                                ${p.description || 'Quản lý máy Chrome và các thư mục dự án con.'}
                            </p>

                            <div style="background:#050914; border:1px solid #1e293b; padding:10px 12px; border-radius:8px; margin-bottom:16px;">
                                <div style="font-size:10px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
                                    🔑 Mã Xác Thực Máy (Token):
                                </div>
                                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                                    <span style="font-family:monospace; font-size:13px; font-weight:800; color:#38bdf8; word-break:break-all;">${p.token}</span>
                                    <div style="display:flex; gap:6px; flex-shrink:0;">
                                        <button class="btn-sm" style="background:#0284c7; padding:4px 8px; font-size:11px;" onclick="copyProjectToken('${p.token}')">📋 Chép</button>
                                        <button class="btn-sm" style="background:#334155; padding:4px 8px; font-size:11px;" onclick="regenerateProjectToken('${p.id}')">🔄</button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div style="display:flex; flex-direction:column; gap:8px; border-top:1px solid rgba(255,255,255,0.06); padding-top:12px;">
                            <button class="btn-enter-card" onclick="enterParentProject('${p.id}')">
                                <span>🚀</span>
                                <span>VÀO DỰ ÁN NÀY (${subCount} THƯ MỤC)</span>
                            </button>
                            ${allProjects.length > 1 ? `
                            <div style="text-align:right;">
                                <button class="btn-sm btn-danger" style="background:transparent; color:#ef4444; border:none; padding:2px 6px;" onclick="deleteProject('${p.id}')">
                                    🗑️ Xóa dự án này
                                </button>
                            </div>` : ''}
                        </div>
                    </div>
                `}).join('');
            } catch(e) {}
        }

        async function fetchParentProjectData(projId) {
            if (!projId) return;
            try {
                const res = await fetch(`/api/bridge/project-latest?projectId=${encodeURIComponent(projId)}`);
                const data = await res.json();
                if (!data.success) return;

                latestParentData = data;
                const nodes = data.nodes || [];
                const isOnline = nodes.length > 0;
                const node = nodes[0] || null;
                const project = data.project || {};
                const subProjects = project.subProjects || [];
                const results = data.results || {};

                if (data.project && data.project.id) {
                    const pIdx = allProjects.findIndex(p => p.id === data.project.id);
                    if (pIdx >= 0) {
                        allProjects[pIdx] = data.project;
                    } else {
                        allProjects.push(data.project);
                    }
                }

                const sbDot = document.getElementById("sidebarParentDot");
                const sbStatus = document.getElementById("sidebarParentMachineStatus");
                if (isOnline) {
                    if (sbDot) sbDot.className = "dot online";
                    if (sbStatus) sbStatus.textContent = (node.nodeName || "Chrome") + " (Online)";
                } else {
                    if (sbDot) sbDot.className = "dot";
                    if (sbStatus) sbStatus.textContent = "Chờ máy kết nối...";
                }

                renderFolderCards(subProjects);

                if (currentSubProjectId) {
                    const activeSub = subProjects.find(s => s.id === currentSubProjectId);
                    if (activeSub) renderSubProjectWorkspace(activeSub);
                }

                renderMachineOverview(node);
                renderTabsData(results.tabs || []);
                renderParentLogs(data.logs || []);

            } catch(e) {}
        }

        // FILTER & RENDER FOLDERS (LEVEL 2)
        let currentFolderFilter = 'all';
        let cachedFoldersList = [];

        function filterSubProjectsByPlatform(filter, btn) {
            currentFolderFilter = filter;
            document.querySelectorAll('#subProjectsFilterTabs button').forEach(b => {
                b.classList.remove('active');
                b.style.background = '#1e293b';
                b.style.color = '#cbd5e1';
                b.style.fontWeight = '600';
            });
            if (btn) {
                btn.classList.add('active');
                btn.style.background = '#0284c7';
                btn.style.color = '#fff';
                btn.style.fontWeight = '700';
            }
            renderFolderCards(cachedFoldersList);
        }

        function renderFolderCards(folders) {
            const container = document.getElementById("foldersGrid");
            if (!container) return;

            cachedFoldersList = folders || [];

            // Cập nhật số đếm phân loại
            const allCount = cachedFoldersList.length;
            const fbCount = cachedFoldersList.filter(f => (f.type || 'facebook') === 'facebook').length;
            const otherCount = cachedFoldersList.filter(f => (f.type || 'facebook') !== 'facebook').length;

            const cAll = document.getElementById("countSubAll");
            const cFb = document.getElementById("countSubFb");
            const cOther = document.getElementById("countSubOther");
            if (cAll) cAll.textContent = allCount;
            if (cFb) cFb.textContent = fbCount;
            if (cOther) cOther.textContent = otherCount;

            let displayFolders = cachedFoldersList;
            if (currentFolderFilter === 'facebook') {
                displayFolders = cachedFoldersList.filter(f => (f.type || 'facebook') === 'facebook');
            } else if (currentFolderFilter === 'other') {
                displayFolders = cachedFoldersList.filter(f => (f.type || 'facebook') !== 'facebook');
            }

            if (!displayFolders || displayFolders.length === 0) {
                let emptyMsg = "Chưa có Thư Mục / Dự Án Con nào";
                let emptySub = "Bấm nút <b>[➕ Tạo Thư Mục / Dự Án Con Mới]</b> ở trên để tạo một thư mục làm việc!";
                if (currentFolderFilter === 'facebook') {
                    emptyMsg = "Chưa có Dự Án Con Facebook nào";
                    emptySub = "Bấm <b>[➕ Tạo Thư Mục / Dự Án Con Mới]</b> và chọn nguồn <b>FACEBOOK</b> để bắt đầu phát triển!";
                } else if (currentFolderFilter === 'other') {
                    emptyMsg = "Chưa có Dự Án Con Nền Tảng Khác nào";
                    emptySub = "Tất cả các dự án con hiện tại đều thuộc FACEBOOK.";
                }

                container.innerHTML = `
                    <div style="grid-column: 1 / -1; background:#090e1c; padding:32px; border-radius:12px; border:1px dashed #334155; text-align:center;">
                        <span style="font-size:32px;">📂</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">${emptyMsg}</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${emptySub}</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = displayFolders.map(f => {
                const subType = f.type || 'facebook';
                const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];
                const isFb = (subType === 'facebook');
                const hasCookie = !!f.c_user || (f.cookies && f.cookies.length > 0) || (f.cookieStr && f.cookieStr.length > 10);
                const cookieCount = (f.cookies && f.cookies.length) || (f.cookieStr ? f.cookieStr.split(';').length : 0);
                const scrapedCount = (f.scrapedData || []).length;
                const postCount = (f.postQueue || []).length;

                const nodes = (latestParentData && latestParentData.nodes) || [];
                const activeNode = nodes[0] || null;
                const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";
                let fbCardStatusHtml = '<b style="color:var(--warning);">⚪ Chưa quét</b>';
                if (f.c_user) {
                    if (browserFbUid && browserFbUid === String(f.c_user).trim()) {
                        fbCardStatusHtml = '<b style="color:var(--success);">🟢 LIVE (Khớp Chrome)</b>';
                    } else if (browserFbUid && browserFbUid !== String(f.c_user).trim()) {
                        fbCardStatusHtml = '<b style="color:#ef4444;">⚠️ Khác UID Chrome</b>';
                    } else {
                        fbCardStatusHtml = `<b style="color:#38bdf8;">Đã nạp (${cookieCount} cookies)</b>`;
                    }
                } else if (hasCookie) {
                    fbCardStatusHtml = `<b style="color:var(--warning);">Chưa có c_user (${cookieCount} cookies)</b>`;
                }

                const statsHtml = isFb ? `
                    <div style="background:#050914; border:1px solid #1e293b; border-radius:8px; padding:10px 12px; font-size:12px; margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Web nguồn:</span>
                            <span style="font-family:monospace; font-weight:700; color:#38bdf8;">facebook.com</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Trạng thái Nick:</span>
                            ${fbCardStatusHtml}
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Nick FB:</span>
                            <span style="color:#fbbf24; font-weight:700; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${f.fbName || f.c_user || 'Chưa nhận diện'}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Bài đã cào:</span>
                            <span style="color:${scrapedCount > 0 ? '#38bdf8' : '#94a3b8'}; font-weight:700;">${scrapedCount} bài</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:var(--text-muted);">Hàng đợi đăng FB:</span>
                            <span style="color:${postCount > 0 ? '#34d399' : '#94a3b8'}; font-weight:700;">${postCount} bài</span>
                        </div>
                    </div>
                ` : `
                    <div style="background:#050914; border:1px solid #1e293b; border-radius:8px; padding:10px 12px; font-size:12px; margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Web nguồn:</span>
                            <span style="font-family:monospace; font-weight:700; color:#38bdf8;">${f.sourceDomain || pCfg.domain}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Phiên & Cookie:</span>
                            <b style="color:${hasCookie ? 'var(--success)' : 'var(--warning)'};">${hasCookie ? '🟢 Có sẵn (' + cookieCount + ')' : '⚪ Chưa lấy'}</b>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Phân loại:</span>
                            <span style="color:#94a3b8; font-weight:600;">🌐 Nền tảng mở rộng</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:var(--text-muted);">Chức năng:</span>
                            <span style="color:#a78bfa; font-weight:700;">Kịch bản riêng theo ${pCfg.name}</span>
                        </div>
                    </div>
                `;

                const iconOrAvatar = (isFb && f.avatar) 
                    ? `<img src="${f.avatar}" referrerpolicy="no-referrer" style="width:44px; height:44px; border-radius:50%; object-fit:cover; border:2px solid #38bdf8;" onerror="this.outerHTML='<div class=\\'folder-icon-box\\'>${pCfg.icon}</div>'" />`
                    : `<div class="folder-icon-box">${pCfg.icon}</div>`;

                const platformBadge = isFb
                    ? `<div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                         <span class="badge-folder" style="background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.4); font-size:11px; font-weight:700;">
                           📘 FACEBOOK
                         </span>
                         <span class="badge-folder" style="background:rgba(16, 185, 129, 0.15); color:#34d399; border:1px solid rgba(16, 185, 129, 0.4); font-size:10px; font-weight:700;">
                           ⭐ Trọng tâm phát triển
                         </span>
                       </div>`
                    : `<div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                         <span class="badge-folder" style="background:${pCfg.badgeBg}; color:${pCfg.badgeColor}; border:1px solid ${pCfg.badgeBorder}; font-size:11px; font-weight:700;">
                           ${pCfg.icon} ${pCfg.name}
                         </span>
                         <span class="badge-folder" style="background:rgba(255,255,255,0.05); color:#94a3b8; border:1px solid #334155; font-size:10px;">
                           🌐 Nền tảng khác
                         </span>
                       </div>`;

                return `
                <div class="folder-card" onclick="enterSubProject('${f.id}')" style="${isFb ? 'border-color:rgba(59, 130, 246, 0.35);' : 'border-color:#1e293b;'}">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                            ${iconOrAvatar}
                            ${platformBadge}
                        </div>
                        
                        <!-- ID PHÂN LOẠI DỰ ÁN CON -->
                        <div style="margin-bottom:8px;">
                            <span style="font-family:monospace; font-size:11px; padding:2px 8px; border-radius:4px; background:#050914; color:#38bdf8; border:1px solid #1e293b; font-weight:700;">
                                🆔 ${f.id}
                            </span>
                        </div>

                        <h3 style="font-size:16px; font-weight:800; color:#fff; margin-bottom:6px;">${f.name}</h3>
                        <p style="font-size:12px; color:var(--text-muted); line-height:1.4; margin-bottom:14px; min-height:32px;">
                            ${f.description || pCfg.defaultDesc}
                        </p>

                        ${statsHtml}
                    </div>

                    <div style="display:flex; gap:8px;" onclick="event.stopPropagation()">
                        <button class="btn-enter-card" style="flex:1;" onclick="enterSubProject('${f.id}')">
                            <span>🚀</span>
                            <span>VÀO DỰ ÁN CON NÀY</span>
                        </button>
                        <button class="btn-sm btn-danger" style="padding:6px 10px;" onclick="deleteFolder('${f.id}')" title="Xóa thư mục">
                            🗑️
                        </button>
                    </div>
                </div>
            `}).join('');
        }

        // RENDER SUB-PROJECT WORKSPACE (LEVEL 3)
        function renderSubProjectWorkspace(sub) {
            const cookies = sub.cookies || [];
            const cookieStr = sub.cookieStr || "";
            const cUser = sub.c_user || "";
            const fbName = sub.fbName || "";
            const avatar = sub.avatar || "";
            const subType = sub.type || "facebook";
            const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];

            // 1. Cập nhật Banner Menu 1 theo loại nền tảng
            const bannerIcon = document.getElementById("subAccBannerIcon");
            const bannerTitle = document.getElementById("subAccBannerTitle");
            const bannerDesc = document.getElementById("subAccBannerDesc");
            const bannerBtn = document.getElementById("subAccBannerBtn");

            if (bannerIcon) bannerIcon.textContent = pCfg.icon;
            if (bannerTitle) {
                if (subType === 'facebook') bannerTitle.textContent = "Kiểm Tra Thông Tin Tài Khoản Facebook";
                else if (subType === 'flow') bannerTitle.textContent = "Google Flow AI Studio & Prompt Generator";
                else if (subType === 'tiktok') bannerTitle.textContent = "Quản Lý Tài Khoản TikTok & Session Cookie";
                else if (subType === 'instagram') bannerTitle.textContent = "Quản Lý Tài Khoản Instagram & Reels";
                else bannerTitle.textContent = "Tổng Quan Dự Án Browser Automation";
            }
            if (bannerDesc) {
                if (subType === 'facebook') {
                    bannerDesc.textContent = "Trích xuất toàn bộ danh tính, UID, trạng thái nick LIVE/DIE, cookie và token của tài khoản Facebook hiện đang login trên trình duyệt.";
                } else if (subType === 'flow') {
                    bannerDesc.textContent = "Quản lý phiên làm việc Google Flow Studio, quét cookie xác thực tài khoản Google và điều khiển prompt tạo ảnh AI.";
                } else if (subType === 'tiktok') {
                    bannerDesc.textContent = "Trích xuất session cookie TikTok, kiểm tra tài khoản đang login trên trình duyệt để chuẩn bị reup video và seeding.";
                } else if (subType === 'instagram') {
                    bannerDesc.textContent = "Trích xuất cookie Instagram, kiểm tra tài khoản đang login trên trình duyệt để chuẩn bị seeding và tải ảnh/reels.";
                } else {
                    bannerDesc.textContent = "Quản lý phiên làm việc tùy chọn, điều khiển tab, thực thi mã JavaScript và quét cookie theo domain.";
                }
            }
            if (bannerBtn) {
                if (subType === 'facebook') {
                    bannerBtn.innerHTML = `<span>🔄</span> <span>QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FB</span>`;
                } else {
                    bannerBtn.innerHTML = `<span>🔄</span> <span>QUÉT & NẠP LẠI COOKIE ${pCfg.name} (${pCfg.domain})</span>`;
                }
            }

            // 2. Profile Card
            const accAvatar = document.getElementById("fbAccAvatar");
            const accName = document.getElementById("fbAccName");
            const accStatusBadge = document.getElementById("fbAccStatusBadge");
            const accProfileLink = document.getElementById("fbAccProfileLink");
            const stat1Label = document.getElementById("subStat1Label");
            const accUid = document.getElementById("fbAccUid");
            const stat2Label = document.getElementById("subStat2Label");
            const accLoginStatus = document.getElementById("fbAccLoginStatus");
            const accLoginSub = document.getElementById("fbAccLoginSub");
            const stat3Label = document.getElementById("subStat3Label");
            const stat3Sub = document.getElementById("subStat3Sub");
            const accCookiesCount = document.getElementById("fbAccCookiesCount");

            const hasCookies = (cookies && cookies.length > 0) || (cookieStr && cookieStr.length > 10);

            if (subType === 'facebook') {
                if (stat1Label) stat1Label.textContent = "Facebook UID (c_user)";
                if (stat2Label) stat2Label.textContent = "Trạng Thái Đăng Nhập";
                if (stat3Label) stat3Label.textContent = "Tổng Số Cookie FB";
                if (stat3Sub) stat3Sub.textContent = "Domain facebook.com";

                if (accAvatar) {
                    accAvatar.src = avatar || (cUser ? `https://graph.facebook.com/${cUser}/picture?type=large` : "https://static.xx.fbcdn.net/rsrc.php/v3/yo/r/UlIqmHJn-SK.gif");
                }
                const isGenericName = !fbName || fbName.includes("Trang cá nhân") || fbName.toLowerCase().includes("your profile") || fbName.toLowerCase() === "facebook";
                if (accName) {
                    accName.textContent = (!isGenericName ? fbName : (cUser ? `Tài Khoản Facebook (UID: ${cUser})` : "Chưa quét thông tin tài khoản"));
                }
                const profileUrl = sub.profileUrl || (cUser ? `https://www.facebook.com/profile.php?id=${cUser}` : "https://www.facebook.com");
                if (accProfileLink) {
                    accProfileLink.href = profileUrl;
                    accProfileLink.textContent = profileUrl;
                }
                if (accUid) accUid.textContent = cUser || "---";

                // Lấy UID Facebook hiện tại đang hoạt động trên trình duyệt Chrome từ node kết nối
                const nodes = (latestParentData && latestParentData.nodes) || [];
                const activeNode = nodes[0] || null;
                const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";
                const isBrowserOnline = nodes.length > 0;

                const mismatchAlert = document.getElementById("fbAccountMismatchAlert");
                const mismatchText = document.getElementById("fbAccountMismatchAlertText");

                if (cUser) {
                    if (browserFbUid && browserFbUid === String(cUser).trim()) {
                        // Trùng khớp hoàn toàn với trình duyệt
                        if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot online"></span> <span style="color:var(--success); font-weight:700;">LIVE (Đã Đăng Nhập)</span>';
                        if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:var(--success);">🟢 ĐÃ ĐĂNG NHẬP</span>';
                        if (accLoginSub) accLoginSub.textContent = `Tài khoản active khớp Chrome (UID: ${cUser})`;
                        if (mismatchAlert) mismatchAlert.style.display = "none";
                    } else if (browserFbUid && browserFbUid !== String(cUser).trim()) {
                        // KHÔNG TRÙNG KHỚP: Chrome đang login một UID khác!
                        if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot" style="background:#ef4444;"></span> <span style="color:#ef4444; font-weight:800;">⚠️ SAI TÀI KHOẢN (Khác Chrome)</span>';
                        if (accLoginStatus) accLoginStatus.innerHTML = `<span style="color:#ef4444; font-weight:800;">❌ KHÔNG TRÙNG KHỚP</span>`;
                        if (accLoginSub) accLoginSub.innerHTML = `<span style="color:#fca5a5;">Chrome đang login: <b>${browserFbUid}</b></span>`;
                        
                        if (mismatchAlert) {
                            mismatchAlert.style.display = "block";
                            if (mismatchText) {
                                mismatchText.innerHTML = `Thư mục này dành cho Facebook UID: <b style="color:#38bdf8;">${cUser}</b>, nhưng Chrome hiện đang đăng nhập UID: <b style="color:#fbbf24;">${browserFbUid}</b>.<br/>👉 Toàn bộ các công cụ Tự động hóa và Điều khiển trong thư mục này đã bị KHÓA để bảo vệ nick.<br/>Bạn hãy chọn <b>[Cách 1: Tạo Dự Án Con Mới Cho Nick Chrome Này]</b> hoặc <b>[Cách 2: Quét & Nạp Đè Toàn Bộ Vào Thư Mục Này]</b> ở bên cạnh để tiếp tục!`;
                            }
                        }
                        // Cập nhật trạng thái khóa của sidebar
                        adaptSubMenuForPlatform(subType, pCfg, sub.id);
                    } else if (isBrowserOnline) {
                        // Extension online nhưng chưa tìm thấy c_user trên facebook.com
                        if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot" style="background:#f59e0b;"></span> <span style="color:var(--warning); font-weight:700;">⚠️ CHƯA LOGIN FB TRÊN CHROME</span>';
                        if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:var(--warning);">⚠️ CHƯA MỞ FB</span>';
                        if (accLoginSub) accLoginSub.textContent = "Chưa có session c_user trên facebook.com";
                        if (mismatchAlert) mismatchAlert.style.display = "none";
                        adaptSubMenuForPlatform(subType, pCfg, sub.id);
                    } else {
                        // Trình duyệt offline / Extension chưa kết nối
                        if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot" style="background:#94a3b8;"></span> <span style="color:#94a3b8;">CHỜ KẾT NỐI CHROME</span>';
                        if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:#94a3b8;">⚪ CHỜ EXTENSION</span>';
                        if (accLoginSub) accLoginSub.textContent = "Mở Chrome và bật Extension để check LIVE";
                        if (mismatchAlert) mismatchAlert.style.display = "none";
                    }
                } else if (hasCookies) {
                    if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot"></span> <span style="color:var(--warning);">CHƯA ĐĂNG NHẬP FB</span>';
                    if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:var(--warning);">⚠️ CHƯA ĐĂNG NHẬP</span>';
                    if (accLoginSub) accLoginSub.textContent = "Đăng nhập tài khoản trên facebook.com";
                    if (mismatchAlert) mismatchAlert.style.display = "none";
                } else {
                    if (accStatusBadge) accStatusBadge.innerHTML = '⚪ Chưa quét tài khoản';
                    if (accLoginStatus) accLoginStatus.innerHTML = '⚪ Chưa quét';
                    if (accLoginSub) accLoginSub.textContent = "Bấm nút Quét & Lấy Thông Tin ở trên";
                    if (mismatchAlert) mismatchAlert.style.display = "none";
                }
            } else {
                // Các nền tảng: Google Flow, TikTok, Instagram, Custom
                if (accAvatar) {
                    accAvatar.src = avatar || ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect fill='%23131d33' width='100' height='100'/><text y='55' x='50' font-size='45' text-anchor='middle' dominant-baseline='central'>" + encodeURIComponent(pCfg.icon) + "</text></svg>");
                }
                if (accName) accName.textContent = sub.name;
                
                const targetUrl = subType === 'flow' ? 'https://flow.google.com' : (subType === 'tiktok' ? 'https://www.tiktok.com' : (subType === 'instagram' ? 'https://www.instagram.com' : 'https://www.google.com'));
                if (accProfileLink) {
                    accProfileLink.href = targetUrl;
                    accProfileLink.textContent = targetUrl;
                }

                if (stat1Label) stat1Label.textContent = "Nền Tảng / Dịch Vụ";
                if (accUid) accUid.textContent = pCfg.name;

                if (stat2Label) stat2Label.textContent = "Trạng Thái Cookie";
                if (accLoginStatus) {
                    accLoginStatus.innerHTML = hasCookies ? `<span style="color:var(--success);">🟢 SẴN SÀNG (${cookies.length || (cookieStr ? 'Đã có' : '')})</span>` : `<span style="color:var(--warning);">⚪ CHƯA LẤY COOKIE</span>`;
                }
                if (accLoginSub) accLoginSub.textContent = `Domain: ${pCfg.domain}`;

                if (stat3Label) stat3Label.textContent = `Tổng Số Cookie ${pCfg.name}`;
                if (stat3Sub) stat3Sub.textContent = `Domain: ${pCfg.domain}`;
                if (accStatusBadge) {
                    accStatusBadge.innerHTML = hasCookies ? `<span class="dot online"></span> <span style="color:var(--success);">ONLINE (${cookies.length} Cookies)</span>` : `⚪ Chưa lấy cookie`;
                }
            }

            if (accCookiesCount) accCookiesCount.textContent = cookies.length;

            const accCookieStrBox = document.getElementById("fbAccCookieStrBox");
            if (accCookieStrBox && cookieStr) accCookieStrBox.textContent = cookieStr;

            // 3. Cookie JSON Box (Xử lý chuẩn cho cả Menu 1 và Menu 2)
            let standardCookies = Array.isArray(cookies) && cookies.length > 0 ? cookies : [];
            if (standardCookies.length === 0 && cookieStr) {
                standardCookies = cookieStr.split(';').map(part => {
                    let [k, ...v] = part.trim().split('=');
                    if (!k) return null;
                    let name = k.trim();
                    let val = v.join('=').trim();
                    return {
                        domain: "." + pCfg.domain,
                        name: name,
                        value: val,
                        path: "/",
                        secure: true,
                        httpOnly: false
                    };
                }).filter(Boolean);
            }

            const formattedJson = standardCookies.length > 0 ? JSON.stringify(standardCookies, null, 2) : "[]";

            const accJsonBox = document.getElementById("fbAccCookieJsonBox");
            if (accJsonBox) accJsonBox.textContent = formattedJson;

            // 4. Quick browser buttons
            renderSubBrowserQuickButtons(subType);

            // 6. Cookies Decoder & Health Inspector
            renderSubCookiesDecoder(standardCookies, subType, pCfg);

            // 7. Cookies Table
            renderSubCookiesTable(standardCookies, subType, pCfg);

            // 8. Scraper Studio
            renderScraperStudio(sub, pCfg);

            // 9. Auto Poster Studio
            renderAutoPosterStudio(sub, pCfg);

            // 10. Interaction & Seeding Studio
            renderInteractionStudio(sub, pCfg);

            // 11. Google Flow: Image Gallery
            if (subType === 'flow' && typeof renderFlowImageGallery === 'function') {
                renderFlowImageGallery(sub);
            }
        }

        function renderSubBrowserQuickButtons(subType) {
            const container = document.getElementById("subBrowserQuickButtons");
            if (!container) return;
            const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];
            if (subType === 'facebook') {
                container.innerHTML = `
                    <button class="btn-sm" onclick="projectOpenTab('https://www.facebook.com')">🌐 Facebook Web</button>
                    <button class="btn-sm" onclick="projectOpenTab('https://m.facebook.com')">📱 Mobile Facebook</button>
                    <button class="btn-sm btn-purple" onclick="projectOpenTab('https://business.facebook.com')">🏢 Meta Business</button>
                    <button class="btn-sm btn-orange" onclick="projectOpenTab('https://adsmanager.facebook.com')">📊 Ads Manager</button>
                `;
            } else {
                container.innerHTML = `
                    <button class="btn-sm" onclick="projectOpenTab('https://${pCfg.domain}')">🌐 Mở ${pCfg.name}</button>
                    <button class="btn-sm btn-purple" onclick="projectOpenTab('${pCfg.defaultUrl || ('https://' + pCfg.domain)}')">🚀 Mở Studio</button>
                `;
            }
        }

        // =========================================================
        // BỘ GIẢI MÃ & BẢNG CHI TIẾT TỪNG PHẦN TỬ COOKIE
        // =========================================================

        let currentSubCookiesList = [];
        let lastParsedCustomCookies = [];

        function decodeFbXsCookie(rawXs) {
            try {
                const decoded = decodeURIComponent(rawXs);
                const parts = decoded.split(":");
                let timestamp = null;
                let is2fa = false;

                for (let p of parts) {
                    if (p.length === 10 && !isNaN(p)) {
                        let tsNum = parseInt(p, 10);
                        if (tsNum > 1500000000 && tsNum < 2200000000) {
                            timestamp = tsNum;
                            break;
                        }
                    }
                }

                if (parts.length >= 3) {
                    is2fa = (parts[2] === "2" || parts[1] === "2");
                }

                let sessionTimeText = "Phiên hoạt động";
                let ageText = "Phiên Facebook hợp lệ";
                if (timestamp) {
                    const dt = new Date(timestamp * 1000);
                    sessionTimeText = "Tạo: " + dt.toLocaleDateString() + " " + dt.toLocaleTimeString();
                    const daysAgo = Math.round((Date.now() - dt.getTime()) / (1000 * 60 * 60 * 24));
                    if (daysAgo <= 0) {
                        ageText = "Vừa tạo hôm nay (Phiên mới)";
                    } else {
                        ageText = "Tạo cách đây ~" + daysAgo + " ngày";
                    }
                }

                const twoFactorText = is2fa ? "🔐 2FA Đang Bật" : "🛡️ Phiên Thường";

                return {
                    timestamp: timestamp,
                    sessionTimeText: sessionTimeText,
                    twoFactorText: twoFactorText,
                    ageText: ageText
                };
            } catch(e) {
                return {
                    sessionTimeText: "Chuỗi XS hợp lệ",
                    twoFactorText: "Đã có Secret",
                    ageText: "Phiên Facebook"
                };
            }
        }

        let currentFilteredCookiesList = [];

        function renderSubCookiesDecoder(cookies, subType, pCfg) {
            const list = Array.isArray(cookies) ? cookies : [];
            const decTitle = document.getElementById("subCookieDecoderTitle");
            if (decTitle) {
                decTitle.textContent = subType === 'facebook' ? 'Giải Mã Cookie Facebook & Kiểm Tra Sức Khỏe Phiên' : `Giải Mã & Phân Tích Cookie ${pCfg.name}`;
            }
            const tblTitle = document.getElementById("subCookiesTableTitle");
            if (tblTitle) {
                tblTitle.textContent = subType === 'facebook' ? '📑 Chi Tiết Từng Phần Tử Cookie Facebook' : `📑 Chi Tiết Từng Phần Tử Cookie ${pCfg.name}`;
            }

            const pillarsDiv = document.getElementById("subFbCookiePillars");
            const healthBadge = document.getElementById("subCookieHealthBadge");

            if (subType !== 'facebook') {
                if (pillarsDiv) pillarsDiv.style.display = "none";
                if (healthBadge) {
                    healthBadge.innerHTML = list.length > 0 ? 
                        `<span class="dot online"></span> <span style="color:var(--success);">🟢 ĐÃ CÓ ${list.length} COOKIES (${pCfg.domain})</span>` : 
                        `⚪ Chưa có dữ liệu cookie (${pCfg.domain})`;
                    healthBadge.style.borderColor = list.length > 0 ? "var(--success)" : "#334155";
                }
                return;
            }

            if (pillarsDiv) pillarsDiv.style.display = "grid";

            let cUser = list.find(c => c.name === "c_user");
            let xs = list.find(c => c.name === "xs");
            let datr = list.find(c => c.name === "datr");
            let sb = list.find(c => c.name === "sb");
            let fr = list.find(c => c.name === "fr");

            const pCUserVal = document.getElementById("subPillarCUserVal");
            const pCUserStatus = document.getElementById("subPillarCUserStatus");
            const pXsTime = document.getElementById("subPillarXsTime");
            const pXsStatus = document.getElementById("subPillarXsStatus");
            const pXsDesc = document.getElementById("subPillarXsDesc");
            const pDatrVal = document.getElementById("subPillarDatrVal");
            const pDatrStatus = document.getElementById("subPillarDatrStatus");
            const pSbVal = document.getElementById("subPillarSbVal");
            const pSbStatus = document.getElementById("subPillarSbStatus");
            const pFrVal = document.getElementById("subPillarFrVal");
            const pFrStatus = document.getElementById("subPillarFrStatus");

            let healthScore = 0;
            if (cUser && cUser.value) healthScore += 30;
            if (xs && xs.value) healthScore += 30;
            if (datr && datr.value) healthScore += 20;
            if (sb && sb.value) healthScore += 10;
            if (fr && fr.value) healthScore += 10;

            if (healthBadge) {
                if (healthScore >= 90) {
                    healthBadge.innerHTML = '<span class="dot online"></span> <span style="color:var(--success);">🟢 SỨC KHỎE HOÀN HẢO (' + healthScore + '/100) — FULL 5 TRỤ CỘT</span>';
                    healthBadge.style.borderColor = "var(--success)";
                } else if (healthScore >= 60) {
                    healthBadge.innerHTML = '<span class="dot" style="background:#eab308;"></span> <span style="color:#eab308;">🟡 KHÁ TỐT (' + healthScore + '/100) — ĐỦ ĐĂNG NHẬP</span>';
                    healthBadge.style.borderColor = "#eab308";
                } else if (healthScore > 0) {
                    healthBadge.innerHTML = '<span class="dot" style="background:#ef4444;"></span> <span style="color:#ef4444;">🔴 YẾU (' + healthScore + '/100) — THIẾU COOKIE QUAN TRỌNG</span>';
                    healthBadge.style.borderColor = "#ef4444";
                } else {
                    healthBadge.innerHTML = '⚪ Chưa có dữ liệu cookie (' + list.length + ' Cookies)';
                    healthBadge.style.borderColor = "#334155";
                }
            }

            // 1. c_user
            if (pCUserVal) {
                if (cUser && cUser.value) {
                    pCUserVal.innerHTML = '<span style="color:#38bdf8;">' + escapeHtml(cUser.value) + '</span>';
                    if (pCUserStatus) {
                        pCUserStatus.textContent = "✅ ĐÃ CÓ UID";
                        pCUserStatus.style.background = "#0369a1";
                        pCUserStatus.style.color = "#fff";
                    }
                } else {
                    pCUserVal.innerHTML = '<span style="color:#64748b;">Chưa có UID</span>';
                    if (pCUserStatus) {
                        pCUserStatus.textContent = "❌ Thiếu";
                        pCUserStatus.style.background = "#1e293b";
                        pCUserStatus.style.color = "#94a3b8";
                    }
                }
            }

            // 2. xs
            if (pXsTime) {
                if (xs && xs.value) {
                    const decodedXs = decodeFbXsCookie(xs.value);
                    pXsTime.innerHTML = '<div style="color:#c084fc; font-weight:700;">' + decodedXs.sessionTimeText + '</div>' +
                                        '<div style="font-size:11px; color:#cbd5e1; margin-top:2px;">' + decodedXs.twoFactorText + '</div>';
                    if (pXsStatus) {
                        pXsStatus.textContent = "✅ PHIÊN HỢP LỆ";
                        pXsStatus.style.background = "#6d28d9";
                        pXsStatus.style.color = "#fff";
                    }
                    if (pXsDesc) pXsDesc.textContent = decodedXs.ageText || "Phiên xác thực Facebook";
                } else {
                    pXsTime.innerHTML = '<span style="color:#64748b;">Chưa có session</span>';
                    if (pXsStatus) {
                        pXsStatus.textContent = "❌ Thiếu";
                        pXsStatus.style.background = "#1e293b";
                        pXsStatus.style.color = "#94a3b8";
                    }
                }
            }

            // 3. datr
            if (pDatrVal) {
                if (datr && datr.value) {
                    pDatrVal.innerHTML = '<span style="color:#f59e0b; font-family:monospace; font-size:11px;">' + escapeHtml(datr.value.slice(0, 16)) + '...</span>';
                    if (pDatrStatus) {
                        pDatrStatus.textContent = "✅ ĐÃ CÓ (AN TOÀN)";
                        pDatrStatus.style.background = "#b45309";
                        pDatrStatus.style.color = "#fff";
                    }
                } else {
                    pDatrVal.innerHTML = '<span style="color:#ef4444; font-size:11px;">⚠️ Thiếu datr (Dễ bị Checkpoint 956)</span>';
                    if (pDatrStatus) {
                        pDatrStatus.textContent = "⚠️ CẢNH BÁO";
                        pDatrStatus.style.background = "#7f1d1d";
                        pDatrStatus.style.color = "#fca5a5";
                    }
                }
            }

            // 4. sb
            if (pSbVal) {
                if (sb && sb.value) {
                    pSbVal.innerHTML = '<span style="color:#10b981; font-family:monospace; font-size:11px;">' + escapeHtml(sb.value.slice(0, 16)) + '...</span>';
                    if (pSbStatus) {
                        pSbStatus.textContent = "✅ ĐÃ NHẬN DIỆN";
                        pSbStatus.style.background = "#047857";
                        pSbStatus.style.color = "#fff";
                    }
                } else {
                    pSbVal.innerHTML = '<span style="color:#64748b;">Chưa có</span>';
                    if (pSbStatus) {
                        pSbStatus.textContent = "⚪ Chưa có";
                        pSbStatus.style.background = "#1e293b";
                        pSbStatus.style.color = "#94a3b8";
                    }
                }
            }

            // 5. fr
            if (pFrVal) {
                if (fr && fr.value) {
                    pFrVal.innerHTML = '<span style="color:#ec4899; font-family:monospace; font-size:11px;">' + escapeHtml(fr.value.slice(0, 16)) + '...</span>';
                    if (pFrStatus) {
                        pFrStatus.textContent = "✅ CÓ TOKEN";
                        pFrStatus.style.background = "#be185d";
                        pFrStatus.style.color = "#fff";
                    }
                } else {
                    pFrVal.innerHTML = '<span style="color:#64748b;">Chưa có</span>';
                    if (pFrStatus) {
                        pFrStatus.textContent = "⚪ Chưa có";
                        pFrStatus.style.background = "#1e293b";
                        pFrStatus.style.color = "#94a3b8";
                    }
                }
            }
        }

        function renderSubCookiesTable(cookies, subType, pCfg) {
            currentSubCookiesList = cookies || [];
            currentFilteredCookiesList = currentSubCookiesList;
            const countBadge = document.getElementById("subCookiesCountBadge");
            if (countBadge) countBadge.textContent = currentSubCookiesList.length + " Cookies";
            const searchInput = document.getElementById("subCookieSearchInput");
            filterSubCookiesTable(searchInput ? searchInput.value : "");
        }

        function filterSubCookiesTable(query) {
            const container = document.getElementById("subCookiesTableContainer");
            if (!container) return;

            query = (query || "").trim().toLowerCase();
            const filtered = currentSubCookiesList.filter(c => {
                if (!query) return true;
                return (c.name && c.name.toLowerCase().includes(query)) ||
                       (c.value && c.value.toLowerCase().includes(query)) ||
                       (c.domain && c.domain.toLowerCase().includes(query));
            });
            currentFilteredCookiesList = filtered;

            if (filtered.length === 0) {
                container.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:24px; text-align:center;">' +
                    (currentSubCookiesList.length === 0 ? 
                        'Chưa có dữ liệu cookie để hiển thị bảng. Bấm nút [QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FB] ở trên!' : 
                        'Không tìm thấy cookie nào khớp với từ khóa "<b>' + escapeHtml(query) + '</b>"') +
                '</div>';
                return;
            }

            let rowsHtml = filtered.map((c, idx) => {
                const name = c.name || "";
                const val = c.value || "";
                const domain = c.domain || "";
                const path = c.path || "/";
                const isHttpOnly = !!c.httpOnly;
                const isSecure = !!c.secure;
                const sameSite = c.sameSite || "unspecified";

                let badgeType = '<span class="badge-folder" style="background:#1e293b; color:#94a3b8; font-size:10px;">🏷️ Thuộc tính</span>';
                if (name === "c_user") badgeType = '<span class="badge-folder" style="background:#0284c7; color:#fff; font-size:10px; font-weight:700;">🆔 UID FB</span>';
                else if (name === "xs") badgeType = '<span class="badge-folder" style="background:#7c3aed; color:#fff; font-size:10px; font-weight:700;">🔐 Session Secret</span>';
                else if (name === "datr") badgeType = '<span class="badge-folder" style="background:#d97706; color:#fff; font-size:10px; font-weight:700;">🛡️ Anti-Checkpoint</span>';
                else if (name === "sb") badgeType = '<span class="badge-folder" style="background:#059669; color:#fff; font-size:10px; font-weight:700;">💻 Machine ID</span>';
                else if (name === "fr") badgeType = '<span class="badge-folder" style="background:#db2777; color:#fff; font-size:10px; font-weight:700;">🔑 Auth Token</span>';
                else if (name === "presence") badgeType = '<span class="badge-folder" style="background:#ca8a04; color:#fff; font-size:10px;">💬 Chat Online</span>';
                else if (name === "wd") badgeType = '<span class="badge-folder" style="background:#475569; color:#fff; font-size:10px;">📐 Viewport</span>';
                else if (name === "dpr") badgeType = '<span class="badge-folder" style="background:#475569; color:#fff; font-size:10px;">📱 Screen Ratio</span>';

                let expText = "Session (Đóng trình duyệt)";
                if (c.expirationDate) {
                    const expDate = new Date(c.expirationDate * 1000);
                    const now = Date.now();
                    const diffDays = Math.round((expDate.getTime() - now) / (1000 * 60 * 60 * 24));
                    if (diffDays < 0) {
                        expText = '<span style="color:#ef4444;">Đã hết hạn (' + expDate.toLocaleDateString() + ')</span>';
                    } else {
                        expText = '<span style="color:#34d399;">' + expDate.toLocaleDateString() + '</span> <span style="font-size:10px; color:#94a3b8;">(còn ~' + diffDays + ' ngày)</span>';
                    }
                }

                const safeVal = escapeHtml(val);
                const shortVal = val.length > 35 ? escapeHtml(val.slice(0, 35)) + "..." : safeVal;

                return `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05); transition:background 0.15s;" onmouseover="this.style.background='rgba(56,189,248,0.04)'" onmouseout="this.style.background='transparent'">
                        <td style="padding:10px 8px; color:var(--text-muted); font-weight:700;">${idx + 1}</td>
                        <td style="padding:10px 8px;">
                            <div style="font-weight:700; color:#38bdf8; font-family:monospace; font-size:13px;">${escapeHtml(name)}</div>
                            <div style="margin-top:3px;">${badgeType}</div>
                        </td>
                        <td style="padding:10px 8px; max-width:280px;">
                            <div style="font-family:monospace; font-size:11px; color:#cbd5e1; word-break:break-all;" title="${safeVal}">${shortVal}</div>
                            <div style="margin-top:4px;">
                                <button class="btn-sm" style="padding:1px 6px; font-size:10px; background:#1e293b; border:1px solid #334155; color:#38bdf8;" onclick="copySingleCookieByIndex(${idx})">📋 Copy Giá Trị</button>
                            </div>
                        </td>
                        <td style="padding:10px 8px; font-size:11px; font-family:monospace; color:#94a3b8;">${escapeHtml(domain)}<br><span style="color:#64748b;">${escapeHtml(path)}</span></td>
                        <td style="padding:10px 8px; font-size:11px;">${expText}</td>
                        <td style="padding:10px 8px;">
                            <div style="display:flex; flex-direction:column; gap:2px;">
                                <span style="font-size:10px; color:${isHttpOnly ? '#c084fc' : '#64748b'};">${isHttpOnly ? '🛡️ HttpOnly' : '⚪ HttpOnly: No'}</span>
                                <span style="font-size:10px; color:${isSecure ? '#34d399' : '#64748b'};">${isSecure ? '🔒 Secure' : '⚪ Secure: No'}</span>
                                <span style="font-size:10px; color:#94a3b8;">${escapeHtml(sameSite)}</span>
                            </div>
                        </td>
                        <td style="padding:10px 8px;">
                            <button class="btn-sm" style="padding:3px 8px; font-size:11px; background:#0284c7;" onclick="copySingleCookiePairByIndex(${idx})">📋 Copy Cặp</button>
                        </td>
                    </tr>
                `;
            }).join("");

            container.innerHTML = `
                <table style="width:100%; border-collapse:collapse; font-size:12px; min-width:800px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border-color); color:var(--text-muted); text-align:left; background:#080e1e;">
                            <th style="padding:10px 8px; width:40px;">#</th>
                            <th style="padding:10px 8px; width:160px;">Tên Cookie (Key)</th>
                            <th style="padding:10px 8px; width:280px;">Giá Trị (Value)</th>
                            <th style="padding:10px 8px; width:140px;">Domain & Path</th>
                            <th style="padding:10px 8px; width:170px;">Hạn Dùng (Expires)</th>
                            <th style="padding:10px 8px; width:110px;">Bảo Mật</th>
                            <th style="padding:10px 8px; width:80px;">Thao Tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            `;
        }

        function copySingleCookieByIndex(idx) {
            const list = (currentFilteredCookiesList && currentFilteredCookiesList.length > 0) ? currentFilteredCookiesList : currentSubCookiesList;
            const c = list[idx];
            if (c) copySingleCookieVal(c.value);
        }

        function copySingleCookiePairByIndex(idx) {
            const list = (currentFilteredCookiesList && currentFilteredCookiesList.length > 0) ? currentFilteredCookiesList : currentSubCookiesList;
            const c = list[idx];
            if (c) copySingleCookiePair(c.name, c.value);
        }

        async function copySingleCookieVal(val) {
            try {
                await navigator.clipboard.writeText(val);
                alert("📋 Đã sao chép giá trị Cookie vào bộ nhớ tạm!");
            } catch(e) {
                prompt("Copy giá trị:", val);
            }
        }

        async function copySingleCookiePair(name, val) {
            const pair = name + "=" + val + ";";
            try {
                await navigator.clipboard.writeText(pair);
                alert("📋 Đã sao chép: " + name + "=" + (val.length > 25 ? val.slice(0, 25) + "..." : val));
            } catch(e) {
                prompt("Copy cặp cookie:", pair);
            }
        }

        function parseAnyCookieString(inputStr) {
            if (!inputStr) return [];
            inputStr = inputStr.trim();

            if (inputStr.startsWith("[") && inputStr.endsWith("]")) {
                try {
                    const parsed = JSON.parse(inputStr);
                    if (Array.isArray(parsed)) {
                        return parsed.map(c => ({
                            name: c.name || c.key || "",
                            value: c.value || "",
                            domain: c.domain || ".facebook.com",
                            path: c.path || "/",
                            secure: c.secure !== undefined ? c.secure : true,
                            httpOnly: c.httpOnly !== undefined ? c.httpOnly : false,
                            expirationDate: c.expirationDate || null
                        })).filter(c => c.name);
                    }
                } catch(e) {}
            }

            const rawParts = inputStr.split(";").flatMap(x => x.split(String.fromCharCode(10))).map(x => x.trim()).filter(Boolean);
            const result = [];
            const seen = new Set();

            for (let part of rawParts) {
                const eqIdx = part.indexOf("=");
                if (eqIdx <= 0) continue;
                const key = part.slice(0, eqIdx).trim();
                const val = part.slice(eqIdx + 1).trim();
                if (key && !seen.has(key)) {
                    seen.add(key);
                    result.push({
                        name: key,
                        value: val,
                        domain: ".facebook.com",
                        path: "/",
                        secure: true,
                        httpOnly: (key === "xs" || key === "datr" || key === "sb" || key === "fr")
                    });
                }
            }
            return result;
        }

        function runCustomCookieDecoder() {
            const raw = (document.getElementById("customCookieInput").value || "").trim();
            if (!raw) {
                alert("Vui lòng dán chuỗi Cookie hoặc mảng JSON vào ô trước!");
                return;
            }

            const cookies = parseAnyCookieString(raw);
            lastParsedCustomCookies = cookies;

            const resBox = document.getElementById("customDecoderResultBox");
            const resHeader = document.getElementById("customDecoderResultHeader");
            const badge = document.getElementById("customDecoderBadge");
            const details = document.getElementById("customDecoderDetails");

            if (cookies.length === 0) {
                alert("Không tìm thấy phần tử cookie hợp lệ nào trong chuỗi dán vào!");
                return;
            }

            let cUser = cookies.find(c => c.name === "c_user");
            let xs = cookies.find(c => c.name === "xs");
            let datr = cookies.find(c => c.name === "datr");
            let sb = cookies.find(c => c.name === "sb");
            let fr = cookies.find(c => c.name === "fr");

            let xsDecoded = xs ? decodeFbXsCookie(xs.value) : null;

            if (badge) badge.textContent = cookies.length + " phần tử";
            if (resHeader) resHeader.innerHTML = "✅ Bóc Tách Thành Công <b>" + cookies.length + "</b> Cookie:";

            let html = `
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin-bottom:12px;">
                    <div style="background:#050811; padding:10px; border-radius:6px; border:1px solid #1e293b;">
                        <div style="color:var(--text-muted); font-size:11px;">Facebook UID:</div>
                        <div style="font-weight:800; font-size:14px; color:${cUser ? '#38bdf8' : '#ef4444'}; margin-top:2px;">
                            ${cUser ? escapeHtml(cUser.value) : '❌ Không có c_user'}
                        </div>
                    </div>
                    <div style="background:#050811; padding:10px; border-radius:6px; border:1px solid #1e293b;">
                        <div style="color:var(--text-muted); font-size:11px;">Session Secret (xs):</div>
                        <div style="font-weight:700; font-size:12px; color:${xs ? '#c084fc' : '#ef4444'}; margin-top:2px;">
                            ${xs ? (xsDecoded ? escapeHtml(xsDecoded.sessionTimeText) : 'Có Session') : '❌ Không có xs'}
                        </div>
                    </div>
                    <div style="background:#050811; padding:10px; border-radius:6px; border:1px solid #1e293b;">
                        <div style="color:var(--text-muted); font-size:11px;">Anti-Checkpoint (datr):</div>
                        <div style="font-weight:700; font-size:12px; color:${datr ? '#f59e0b' : '#ef4444'}; margin-top:2px;">
                            ${datr ? '🛡️ Đã có datr (An toàn)' : '⚠️ Thiếu datr (Dễ dính 956)'}
                        </div>
                    </div>
                    <div style="background:#050811; padding:10px; border-radius:6px; border:1px solid #1e293b;">
                        <div style="color:var(--text-muted); font-size:11px;">Machine Binding (sb):</div>
                        <div style="font-weight:700; font-size:12px; color:${sb ? '#10b981' : '#94a3b8'}; margin-top:2px;">
                            ${sb ? '💻 Đã có sb' : '⚪ Không có'}
                        </div>
                    </div>
                </div>
                <div style="font-size:11px; color:#94a3b8; margin-bottom:8px;">Các khóa cookie tìm thấy:</div>
                <div style="display:flex; flex-wrap:wrap; gap:6px;">
                    ${cookies.map(c => `
                        <span class="badge-folder" style="background:#131d33; border:1px solid #334155; color:#cbd5e1; font-family:monospace; padding:3px 8px; font-size:11px;">
                            <b>${escapeHtml(c.name)}</b>: ${escapeHtml(c.value.slice(0, 15))}${c.value.length > 15 ? '...' : ''}
                        </span>
                    `).join('')}
                </div>
            `;

            if (details) details.innerHTML = html;
            if (resBox) resBox.style.display = "block";
        }

        async function copyCustomDecodedJson() {
            if (lastParsedCustomCookies.length === 0) {
                const raw = (document.getElementById("customCookieInput").value || "").trim();
                if (raw) lastParsedCustomCookies = parseAnyCookieString(raw);
            }
            if (lastParsedCustomCookies.length === 0) {
                alert("Vui lòng dán chuỗi cookie và bấm [Giải Mã & Phân Tích Cookie Này] trước!");
                return;
            }
            const jsonStr = JSON.stringify(lastParsedCustomCookies, null, 2);
            try {
                await navigator.clipboard.writeText(jsonStr);
                alert("📋 Đã sao chép " + lastParsedCustomCookies.length + " Cookie dạng JSON chuẩn vào bộ nhớ tạm!");
            } catch(e) {
                prompt("Copy JSON bên dưới:", jsonStr);
            }
        }

        async function copyCustomDecodedText() {
            if (lastParsedCustomCookies.length === 0) {
                const raw = (document.getElementById("customCookieInput").value || "").trim();
                if (raw) lastParsedCustomCookies = parseAnyCookieString(raw);
            }
            if (lastParsedCustomCookies.length === 0) {
                alert("Vui lòng dán chuỗi cookie và bấm [Giải Mã & Phân Tích Cookie Này] trước!");
                return;
            }
            const str = lastParsedCustomCookies.map(c => c.name + "=" + c.value).join("; ");
            try {
                await navigator.clipboard.writeText(str);
                alert("📋 Đã sao chép chuỗi Cookie dạng chuẩn (name=value; ...) vào bộ nhớ tạm!");
            } catch(e) {
                prompt("Copy chuỗi bên dưới:", str);
            }
        }

        async function applyCustomCookieToActiveSub() {
            if (!currentProjectId || !currentSubProjectId) {
                alert("Chưa chọn dự án con để áp dụng!");
                return;
            }
            if (lastParsedCustomCookies.length === 0) {
                const raw = (document.getElementById("customCookieInput").value || "").trim();
                if (raw) lastParsedCustomCookies = parseAnyCookieString(raw);
            }
            if (lastParsedCustomCookies.length === 0) {
                alert("Vui lòng dán cookie hợp lệ trước khi áp dụng!");
                return;
            }

            const cUser = (lastParsedCustomCookies.find(c => c.name === "c_user") || {}).value || "";
            const cookieStr = lastParsedCustomCookies.map(c => c.name + "=" + c.value).join("; ");

            if (!confirm("Bạn có chắc chắn muốn áp dụng " + lastParsedCustomCookies.length + " Cookie (UID: " + (cUser || 'N/A') + ") này vào Thư Mục Dự Án Con đang mở không?")) {
                return;
            }

            try {
                const res = await fetch("/api/subprojects/update-cookies", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        cookies: lastParsedCustomCookies,
                        cookieStr: cookieStr,
                        c_user: cUser
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert("💾 Đã lưu và áp dụng thành công bộ Cookie mới cho Dự Án Con này!");
                    fetchParentProjectData(currentProjectId);
                } else {
                    alert("Lỗi khi lưu cookie: " + extractErrorMsg(data.error, "Không xác định"));
                }
            } catch(e) {
                alert("Lỗi kết nối máy chủ: " + e.message);
            }
        }

        // =========================================================
        // STUDIO CÀO DỮ LIỆU (SCRAPER STUDIO)
        // =========================================================

        function renderScraperStudio(sub, pCfg) {
            const bannerTitle = document.getElementById("scraperBannerTitle");
            const bannerDesc = document.getElementById("scraperBannerDesc");
            const targetUrlInput = document.getElementById("scraperTargetUrl");
            const countBadge = document.getElementById("scrapedCountBadge");
            const tableContainer = document.getElementById("scrapedTableContainer");

            const sourceDomain = sub.sourceDomain || pCfg.domain;
            const defaultTargetUrl = sub.sourceUrl || pCfg.scrapeUrl || pCfg.defaultUrl;

            if (bannerTitle) bannerTitle.textContent = `Studio Cào Dữ Liệu: ${pCfg.name} (${sourceDomain})`;
            if (bannerDesc) bannerDesc.textContent = `Cào bài viết, bình luận, tiêu đề, liên kết và hình ảnh trực tiếp từ tab Chrome đang mở của nguồn ${pCfg.name}.`;

            if (targetUrlInput && (!targetUrlInput.value || targetUrlInput.value === "https://...")) {
                targetUrlInput.value = defaultTargetUrl;
            }

            const items = sub.scrapedData || [];
            if (countBadge) countBadge.textContent = `${items.length} Mục`;

            if (!tableContainer) return;
            if (items.length === 0) {
                tableContainer.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                        <span style="font-size:28px;">📥</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">Chưa có dữ liệu nào được cào từ nguồn ${pCfg.name}</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                            Bấm nút <b>[🌐 Mở Trang Nguồn Trên Chrome]</b> rồi bấm <b>[🚀 BẮT ĐẦU CÀO DỮ LIỆU TỪ CHROME]</b> ở trên để thực thi!
                        </div>
                    </div>
                `;
                return;
            }

            tableContainer.innerHTML = `
                <table style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border-color); color:var(--text-muted); text-align:left; background:#080e1e;">
                            <th style="padding:10px 8px; width:45px;">#</th>
                            <th style="padding:10px 8px; width:45%;">Nội Dung / Tiêu Đề Bài Viết</th>
                            <th style="padding:10px 8px; width:15%;">Người Đăng / Tác Giả</th>
                            <th style="padding:10px 8px; width:15%;">Ảnh / Media</th>
                            <th style="padding:10px 8px; width:15%;">Thời Gian</th>
                            <th style="padding:10px 8px; width:10%;">Liên Kết</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map((it, idx) => `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.04); transition:0.15s;" onmouseover="this.style.background='rgba(56,189,248,0.04)'" onmouseout="this.style.background='transparent'">
                                <td style="padding:10px 8px; color:var(--text-muted); font-weight:700;">${idx + 1}</td>
                                <td style="padding:10px 8px; color:#fff; line-height:1.4;">
                                    <div style="font-weight:700; color:#38bdf8; margin-bottom:2px;">${escapeHtml(it.title || 'Bài viết')}</div>
                                    <div style="font-size:11px; color:#cbd5e1; max-height:60px; overflow-y:auto; word-break:break-word;">${escapeHtml(it.content || '')}</div>
                                </td>
                                <td style="padding:10px 8px; font-weight:600; color:#fbbf24;">
                                    ${escapeHtml(it.author || 'User')}
                                </td>
                                <td style="padding:10px 8px;">
                                    ${it.image ? `<a href="${escapeHtml(it.image)}" target="_blank"><img src="${escapeHtml(it.image)}" style="width:50px; height:50px; object-fit:cover; border-radius:6px; border:1px solid #334155;" onerror="this.outerHTML='🖼️ Ảnh'" /></a>` : '<span style="color:#64748b;">(Không có ảnh)</span>'}
                                </td>
                                <td style="padding:10px 8px; color:#94a3b8; font-size:11px;">
                                    ${escapeHtml(it.timestamp || '')}
                                </td>
                                <td style="padding:10px 8px;">
                                    ${it.url ? `<a href="${escapeHtml(it.url)}" target="_blank" class="btn-sm" style="background:#0284c7; padding:3px 8px; font-size:11px; text-decoration:none; display:inline-block;">🔗 Mở</a>` : '---'}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        function escapeHtml(text) {
            if (!text) return '';
            return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function openScraperSourceUrl() {
            const url = document.getElementById("scraperTargetUrl")?.value.trim();
            if (url) projectOpenTab(url);
        }

        function generateScrapingScript(platform, dataType, limit) {
            return `(function() {
                try {
                    const results = [];
                    const maxItems = ${limit || 30};
                    const currentUrl = window.location.href;
                    const host = window.location.hostname.toLowerCase();

                    // 1. Twitter / X
                    if (host.includes("x.com") || host.includes("twitter.com")) {
                        const tweets = document.querySelectorAll('article[data-testid="tweet"]');
                        for (let i = 0; i < tweets.length && results.length < maxItems; i++) {
                            const tw = tweets[i];
                            const textEl = tw.querySelector('div[data-testid="tweetText"]');
                            const text = textEl ? textEl.innerText.trim() : '';
                            const userEl = tw.querySelector('div[data-testid="User-Name"]');
                            const author = userEl ? userEl.innerText.split('\\n')[0].trim() : 'Twitter User';
                            const timeEl = tw.querySelector('time');
                            const timestamp = timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText) : '';
                            const linkEl = tw.querySelector('a[href*="/status/"]');
                            const link = linkEl ? linkEl.href : currentUrl;
                            const imgEl = tw.querySelector('div[data-testid="tweetPhoto"] img');
                            const image = imgEl ? imgEl.src : '';

                            if (text || image) {
                                results.push({
                                    id: 'tw_' + (results.length + 1),
                                    title: text.slice(0, 80) + (text.length > 80 ? '...' : ''),
                                    content: text,
                                    author: author,
                                    url: link,
                                    image: image,
                                    timestamp: timestamp || new Date().toLocaleString(),
                                    source: 'X / Twitter'
                                });
                            }
                        }
                    }
                    // 2. Facebook
                    else if (host.includes("facebook.com")) {
                        const feedPosts = document.querySelectorAll('div[role="feed"] > div, div[data-ad-preview="message"], div[dir="auto"]');
                        const seenText = new Set();
                        for (let i = 0; i < feedPosts.length && results.length < maxItems; i++) {
                            const p = feedPosts[i];
                            const text = (p.innerText || '').trim();
                            if (text && text.length > 25 && !seenText.has(text.slice(0, 40))) {
                                seenText.add(text.slice(0, 40));
                                let author = 'Facebook User';
                                let ancestor = p.closest('div[role="article"]') || p.parentElement;
                                if (ancestor) {
                                    let strong = ancestor.querySelector('strong, h2, h3, a[role="link"]');
                                    if (strong && strong.innerText) author = strong.innerText.trim();
                                }
                                let img = ancestor ? ancestor.querySelector('img[src*="fbcdn"]') : null;
                                let linkEl = ancestor ? ancestor.querySelector('a[href*="/posts/"], a[href*="/permalink/"], a[href*="facebook.com"]') : null;

                                results.push({
                                    id: 'fb_' + (results.length + 1),
                                    title: text.slice(0, 80) + (text.length > 80 ? '...' : ''),
                                    content: text,
                                    author: author,
                                    url: linkEl ? linkEl.href : currentUrl,
                                    image: img ? img.src : '',
                                    timestamp: new Date().toLocaleString(),
                                    source: 'Facebook'
                                });
                            }
                        }
                    }
                    // 3. TikTok
                    else if (host.includes("tiktok.com")) {
                        const items = document.querySelectorAll('div[data-e2e="user-post-item"], div[data-e2e="recommend-list-item-container"], div.tiktok-x6f6no-DivItemContainerV2');
                        for (let i = 0; i < items.length && results.length < maxItems; i++) {
                            const it = items[i];
                            const linkEl = it.querySelector('a[href*="/video/"]');
                            const descEl = it.querySelector('div[data-e2e="user-post-item-desc"], span, a');
                            const authorEl = it.querySelector('a[data-e2e="user-title"], span[data-e2e="channel-title"]');
                            const imgEl = it.querySelector('img, video');
                            const desc = descEl ? descEl.innerText.trim() : '';

                            results.push({
                                id: 'tt_' + (results.length + 1),
                                title: desc.slice(0, 80) || ('TikTok Video ' + (results.length + 1)),
                                content: desc,
                                author: authorEl ? authorEl.innerText.trim() : 'TikTok Creator',
                                url: linkEl ? linkEl.href : currentUrl,
                                image: imgEl ? (imgEl.src || imgEl.poster || '') : '',
                                timestamp: new Date().toLocaleString(),
                                source: 'TikTok'
                            });
                        }
                    }
                    // 4. Instagram
                    else if (host.includes("instagram.com")) {
                        const articles = document.querySelectorAll('article, div[role="presentation"]');
                        for (let i = 0; i < articles.length && results.length < maxItems; i++) {
                            const art = articles[i];
                            const textEl = art.querySelector('h1, span._aacl, div._a9zs');
                            const userEl = art.querySelector('a._a9zc, header a');
                            const imgEl = art.querySelector('img[src*="instagram"], img[src*="fbcdn"]');
                            const linkEl = art.querySelector('a[href*="/p/"], a[href*="/reel/"]');
                            const text = textEl ? textEl.innerText.trim() : '';

                            if (text || imgEl) {
                                results.push({
                                    id: 'ig_' + (results.length + 1),
                                    title: text.slice(0, 80) || ('Instagram Post ' + (results.length + 1)),
                                    content: text,
                                    author: userEl ? userEl.innerText.trim() : 'Instagram User',
                                    url: linkEl ? linkEl.href : currentUrl,
                                    image: imgEl ? imgEl.src : '',
                                    timestamp: new Date().toLocaleString(),
                                    source: 'Instagram'
                                });
                            }
                        }
                    }
                    // 5. Generic Website / Web Báo / E-commerce
                    else {
                        const headings = document.querySelectorAll('h1, h2, h3, article, .post, .article');
                        const seenText = new Set();
                        for (let i = 0; i < headings.length && results.length < maxItems; i++) {
                            const el = headings[i];
                            const text = el.innerText.trim();
                            if (text && text.length > 10 && !seenText.has(text)) {
                                seenText.add(text);
                                let parent = el.closest('article') || el.parentElement;
                                let linkEl = el.querySelector('a') || (parent ? parent.querySelector('a') : null);
                                let imgEl = parent ? parent.querySelector('img') : null;
                                let pDesc = parent ? parent.querySelector('p') : null;

                                results.push({
                                    id: 'item_' + (results.length + 1),
                                    title: text.slice(0, 90),
                                    content: pDesc ? pDesc.innerText.trim() : text,
                                    author: document.title || host,
                                    url: linkEl ? linkEl.href : currentUrl,
                                    image: imgEl ? imgEl.src : '',
                                    timestamp: new Date().toLocaleString(),
                                    source: host
                                });
                            }
                        }
                    }

                    return {
                        success: true,
                        scrapedCount: results.length,
                        scrapedUrl: currentUrl,
                        items: results
                    };
                } catch(err) {
                    return { success: false, error: err.message };
                }
            })()`;
        }

        async function startScrapingData() {
            if (!currentProjectId || !currentSubProjectId) return;
            const statusEl = document.getElementById("scraperStatusText");
            const targetUrl = document.getElementById("scraperTargetUrl")?.value.trim() || "";
            const dataType = document.getElementById("scraperDataType")?.value || "posts";
            const limit = parseInt(document.getElementById("scraperDataLimit")?.value) || 30;

            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = sub ? sub.type : "facebook";

            if (statusEl) {
                statusEl.textContent = "⏳ Đang gửi lệnh cào dữ liệu DOM tới Chrome node...";
                statusEl.style.color = "var(--accent)";
            }

            const script = generateScrapingScript(subType, dataType, limit);

            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "EXECUTE_SCRIPT",
                        code: script
                    })
                });

                if (statusEl) {
                    statusEl.textContent = "⏳ Lệnh đã phát! Chrome đang trích xuất dữ liệu, đang nạp kết quả...";
                    statusEl.style.color = "#38bdf8";
                }

                setTimeout(() => {
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                    if (statusEl) statusEl.textContent = "✅ Đã đồng bộ kết quả cào mới nhất!";
                }, 1800);

            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        async function scrollAndScrape() {
            if (!currentProjectId || !currentSubProjectId) return;
            const statusEl = document.getElementById("scraperStatusText");
            if (statusEl) statusEl.textContent = "📜 Đang cuộn trang Chrome 1200px để tải thêm nội dung...";

            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "EXECUTE_SCRIPT",
                        code: "(function(){ window.scrollBy({ top: 1200, behavior: 'smooth' }); return 'Đã cuộn'; })()"
                    })
                });

                setTimeout(() => {
                    startScrapingData();
                }, 1000);
            } catch(e) {}
        }

        function copyScrapedJson() {
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const items = sub ? (sub.scrapedData || []) : [];

            if (items.length === 0) {
                alert("Chưa có dữ liệu nào để sao chép!");
                return;
            }
            navigator.clipboard.writeText(JSON.stringify(items, null, 2)).then(() => {
                alert(`📋 Đã sao chép ${items.length} mục dữ liệu JSON vào Clipboard!`);
            });
        }

        function exportScrapedCsv() {
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const items = sub ? (sub.scrapedData || []) : [];

            if (items.length === 0) {
                alert("Chưa có dữ liệu nào để xuất file CSV!");
                return;
            }

            const headers = ["STT", "Tieu_De", "Noi_Dung", "Tac_Gia", "Link_Bai_Viet", "Link_Hinh_Anh", "Thoi_Gian", "Nguon_Website"];
            const escapeCsv = (str) => {
                if (!str) return '""';
                const clean = String(str).split(String.fromCharCode(10)).join(' ').split(String.fromCharCode(13)).join(' ').replace(/"/g, '""');
                return `"${clean}"`;
            };

            const rows = items.map((it, idx) => [
                idx + 1,
                escapeCsv(it.title),
                escapeCsv(it.content),
                escapeCsv(it.author),
                escapeCsv(it.url),
                escapeCsv(it.image),
                escapeCsv(it.timestamp),
                escapeCsv(it.source || sub.type)
            ].join(','));

            const csvContent = String.fromCharCode(0xFEFF) + [headers.join(','), ...rows].join(String.fromCharCode(13, 10));
            const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `scraped_${sub.type}_${Date.now()}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        async function clearScrapedData() {
            if (!confirm("🗑️ Bạn có chắc muốn xóa toàn bộ dữ liệu cào của dự án con này?")) return;
            try {
                await fetch("/api/subprojects/clear-scraped", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: currentProjectId, subProjectId: currentSubProjectId })
                });
                if (currentProjectId) fetchParentProjectData(currentProjectId);
            } catch(e) {
                alert("Lỗi: " + e.message);
            }
        }

        // =========================================================
        // STUDIO TỰ ĐỘNG ĐĂNG BÀI & SEEDING (FROM AUTOFB)
        // =========================================================

        let _adminMediaData = null;
        let _currentPostType = "post";
        let _currentTargetType = "profile";
        let _currentPostFilter = "all";
        let _postSearchQuery = "";
        let _currentAddSeedingPostId = null;
        let _queuePaginationState = {
            postQueueTableContainer: { page: 1, pageSize: 10 },
            videoPostQueueTableContainer: { page: 1, pageSize: 10 },
            reelsPostQueueTableContainer: { page: 1, pageSize: 10 },
            storyPostQueueTableContainer: { page: 1, pageSize: 10 }
        };

        function selectPostTypePill(type, btn) {
            _currentPostType = type;
            document.querySelectorAll(".type-pill-btn").forEach(b => b.classList.remove("active"));
            if (btn) btn.classList.add("active");
        }

        function selectTargetTypePill(target, btn) {
            _currentTargetType = target;
            document.querySelectorAll(".target-pill-btn").forEach(b => b.classList.remove("active"));
            if (btn) btn.classList.add("active");
            const idContainer = document.getElementById("targetIdContainer");
            if (idContainer) {
                idContainer.style.display = (target === "page" || target === "group") ? "block" : "none";
            }
        }

        function updatePostCharCount(el) {
            const counter = document.getElementById("postCharCount");
            if (counter && el) {
                counter.textContent = `${el.value.length} ký tự`;
            }
        }

        function parseSpintax(text) {
            if (!text) return "";
            const regex = /\{([^{}]+)\}/g;
            let result = text;
            let match;
            while ((match = regex.exec(result)) !== null) {
                const options = match[1].split("|");
                const chosen = options[Math.floor(Math.random() * options.length)];
                result = result.slice(0, match.index) + chosen + result.slice(match.index + match[0].length);
                regex.lastIndex = match.index + chosen.length;
            }
            return result;
        }

        function testSpintaxPreview() {
            const input = document.getElementById("postContentInput");
            if (!input || !input.value.trim()) {
                alert("Vui lòng nhập nội dung bài viết trước!");
                return;
            }
            const spun = parseSpintax(input.value);
            alert("🎲 Xem thử nội dung xoay Spintax ngẫu nhiên:\\n\\n" + spun);
        }

        function insertSeedingPreset(type) {
            const input = document.getElementById("postSeedingCommentsInput");
            if (!input) return;
            if (type === "inquiry") {
                input.value = "Shop ơi mẫu này còn sẵn không?\\nCho mình xin bảng giá chi tiết với ạ\\nCó ship COD toàn quốc không shop?\\nTư vấn inbox giúp em nhé";
            } else if (type === "feedback") {
                input.value = "Sản phẩm chất lượng cực kỳ, đáng đồng tiền bát gạo!\\nShop giao hàng nhanh quá, 2 hôm là nhận được rồi\\nƯng ý lắm, chúc shop đắt hàng nha\\n10 điểm cho chất lượng và độ nhiệt tình của shop";
            } else if (type === "clear") {
                input.value = "";
            }
        }

        function handleAdminMediaFile(file) {
            if (!file) return;
            const isImageByType = file.type && file.type.startsWith("image/");
            const isVideoByType = file.type && file.type.startsWith("video/");
            const isImageByExt = file.name && file.name.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i);
            const isVideoByExt = file.name && file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i);
            const isImage = isImageByType || isImageByExt;
            const isVideo = isVideoByType || isVideoByExt;

            if (!isImage && !isVideo) {
                alert("⚠️ Chỉ hỗ trợ tệp hình ảnh hoặc video!");
                return;
            }

            const maxSize = isVideo ? 100 * 1024 * 1024 : 10 * 1024 * 1024;
            if (file.size > maxSize) {
                alert(`⚠️ File quá lớn! Tối đa ${isVideo ? '100MB' : '10MB'}.`);
                return;
            }

            const preview = document.getElementById("mediaPreview");
            const dropText = document.getElementById("mediaDropText");
            if (preview) {
                preview.innerHTML = "";
                if (isImage) {
                    const img = document.createElement("img");
                    img.style.cssText = "width:100%; max-height:180px; object-fit:contain; display:block; border-radius:8px;";
                    img.src = URL.createObjectURL(file);
                    preview.appendChild(img);
                } else {
                    const video = document.createElement("video");
                    video.style.cssText = "width:100%; max-height:180px; object-fit:contain; display:block; border-radius:8px;";
                    video.src = URL.createObjectURL(file);
                    video.controls = true;
                    video.muted = true;
                    preview.appendChild(video);
                }
                preview.style.display = "block";
            }
            if (dropText) dropText.style.display = "none";

            const fileInfo = document.getElementById("mediaFileInfo");
            const fileName = document.getElementById("mediaFileName");
            const sizeStr = file.size < 1024 * 1024 ? (file.size / 1024).toFixed(1) + " KB" : (file.size / (1024 * 1024)).toFixed(1) + " MB";
            if (fileName) fileName.textContent = `📎 ${file.name} (${sizeStr})`;
            if (fileInfo) fileInfo.style.display = "flex";

            const reader = new FileReader();
            reader.onload = (e) => {
                const base64Data = e.target.result.split(",")[1];
                let resolvedMime = file.type;
                if (!resolvedMime) {
                    if (file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)) resolvedMime = "video/mp4";
                    else if (file.name.match(/\.(jpg|jpeg|png|gif|webp)$/i)) resolvedMime = "image/jpeg";
                }
                _adminMediaData = {
                    base64: base64Data,
                    fileName: file.name,
                    mimeType: resolvedMime || "application/octet-stream",
                    size: file.size
                };
            };
            reader.readAsDataURL(file);
        }

        function clearAdminMedia() {
            _adminMediaData = null;
            const preview = document.getElementById("mediaPreview");
            const dropText = document.getElementById("mediaDropText");
            const fileInfo = document.getElementById("mediaFileInfo");
            const fileInput = document.getElementById("mediaFileInput");
            if (preview) { preview.innerHTML = ""; preview.style.display = "none"; }
            if (dropText) dropText.style.display = "block";
            if (fileInfo) fileInfo.style.display = "none";
            if (fileInput) fileInput.value = "";
        }

        let _videoMediaData = null;
        let _reelsMediaData = null;
        let _storyMediaData = null;
        let _targetTypeVideo = "profile";
        let _targetTypeReels = "profile";
        let _targetTypeStory = "profile";

        function selectCustomTargetPill(prefix, target, btn) {
            if (prefix === "video") _targetTypeVideo = target;
            else if (prefix === "reels") _targetTypeReels = target;
            else if (prefix === "story") _targetTypeStory = target;

            const section = document.getElementById(`view-sub-post-${prefix === 'reels' ? 'reels' : prefix}`);
            if (section) {
                section.querySelectorAll(".target-pill-btn").forEach(b => b.classList.remove("active"));
            }
            if (btn) btn.classList.add("active");

            const idContainer = document.getElementById(`${prefix}TargetIdContainer`);
            if (idContainer) {
                idContainer.style.display = (target === "page" || target === "group") ? "block" : "none";
            }
        }

        function testSpintaxForEl(id) {
            const input = document.getElementById(id);
            if (!input || !input.value.trim()) {
                alert("Vui lòng nhập nội dung trước!");
                return;
            }
            const spun = parseSpintax(input.value);
            alert("🎲 Xem thử nội dung xoay Spintax ngẫu nhiên:\\n\\n" + spun);
        }

        function insertCustomSeedingPreset(prefix, type) {
            const input = document.getElementById(`${prefix}SeedingInput`);
            if (!input) return;
            if (type === "inquiry") {
                input.value = "Shop ơi mẫu này còn sẵn không?\\nCho mình xin giá chi tiết với ạ\\nCó ship COD toàn quốc không?";
            } else if (type === "feedback") {
                input.value = "Nội dung video xuất sắc quá ạ!\\nKênh làm video chỉn chu, 10 điểm\\nTheo dõi kênh từ lâu rồi, chúc kênh phát triển nha";
            } else if (type === "clear") {
                input.value = "";
            }
        }

        function handleCustomMediaFile(prefix, file) {
            if (!file) return;
            const isImageByType = file.type && file.type.startsWith("image/");
            const isVideoByType = file.type && file.type.startsWith("video/");
            const isImageByExt = file.name && file.name.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i);
            const isVideoByExt = file.name && file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i);
            const isImage = isImageByType || isImageByExt;
            const isVideo = isVideoByType || isVideoByExt;

            if (prefix === "video" || prefix === "reels") {
                if (!isVideo) {
                    alert("⚠️ Mục này chỉ hỗ trợ tệp Video (.mp4, .mov, .mkv)!");
                    return;
                }
            } else if (!isImage && !isVideo) {
                alert("⚠️ Chỉ hỗ trợ tệp hình ảnh hoặc video!");
                return;
            }

            const maxSize = 100 * 1024 * 1024;
            if (file.size > maxSize) {
                alert("⚠️ File quá lớn! Dung lượng tối đa là 100MB.");
                return;
            }

            const preview = document.getElementById(`${prefix}Preview`);
            const dropText = document.getElementById(`${prefix}DropText`);
            if (preview) {
                preview.innerHTML = "";
                if (isImage) {
                    const img = document.createElement("img");
                    img.style.cssText = "width:100%; max-height:200px; object-fit:contain; display:block; border-radius:8px;";
                    img.src = URL.createObjectURL(file);
                    preview.appendChild(img);
                } else {
                    const video = document.createElement("video");
                    video.style.cssText = "width:100%; max-height:200px; object-fit:contain; display:block; border-radius:8px;";
                    video.src = URL.createObjectURL(file);
                    video.controls = true;
                    video.muted = true;
                    preview.appendChild(video);
                }
                preview.style.display = "block";
            }
            if (dropText) dropText.style.display = "none";

            const fileInfo = document.getElementById(`${prefix}FileInfo`);
            const fileName = document.getElementById(`${prefix}FileName`);
            const sizeStr = file.size < 1024 * 1024 ? (file.size / 1024).toFixed(1) + " KB" : (file.size / (1024 * 1024)).toFixed(1) + " MB";
            if (fileName) fileName.textContent = `📎 ${file.name} (${sizeStr})`;
            if (fileInfo) fileInfo.style.display = "flex";

            const reader = new FileReader();
            reader.onload = (e) => {
                const base64Data = e.target.result.split(",")[1];
                let resolvedMime = file.type;
                if (!resolvedMime) {
                    if (file.name.match(/\.(mp4|mov|avi|mkv|webm)$/i)) resolvedMime = "video/mp4";
                    else if (file.name.match(/\.(jpg|jpeg|png|gif|webp)$/i)) resolvedMime = "image/jpeg";
                }
                const mData = {
                    base64: base64Data,
                    fileName: file.name,
                    mimeType: resolvedMime || (isVideo ? "video/mp4" : "image/jpeg"),
                    size: file.size
                };
                if (prefix === "video") _videoMediaData = mData;
                else if (prefix === "reels") _reelsMediaData = mData;
                else if (prefix === "story") _storyMediaData = mData;
            };
            reader.readAsDataURL(file);
        }

        function clearCustomMedia(prefix) {
            if (prefix === "video") _videoMediaData = null;
            else if (prefix === "reels") _reelsMediaData = null;
            else if (prefix === "story") _storyMediaData = null;

            const preview = document.getElementById(`${prefix}Preview`);
            const dropText = document.getElementById(`${prefix}DropText`);
            const fileInfo = document.getElementById(`${prefix}FileInfo`);
            const fileInput = document.getElementById(`${prefix}FileInput`);
            if (preview) { preview.innerHTML = ""; preview.style.display = "none"; }
            if (dropText) dropText.style.display = "block";
            if (fileInfo) fileInfo.style.display = "none";
            if (fileInput) fileInput.value = "";
        }

        function setSchedulePreset(minutes, inputId) {
            const el = document.getElementById(inputId);
            if (!el) return;
            const now = new Date();
            now.setMinutes(now.getMinutes() + minutes);
            const pad = (n) => String(n).padStart(2, '0');
            el.value = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
        }

        function setSchedulePresetNamed(presetName, inputId) {
            const el = document.getElementById(inputId);
            if (!el) return;
            const now = new Date();
            const target = new Date();
            if (presetName === 'tomorrow_morning') {
                target.setDate(target.getDate() + 1);
                target.setHours(8, 0, 0, 0);
            } else if (presetName === 'tonight_evening') {
                if (now.getHours() >= 20) {
                    target.setDate(target.getDate() + 1);
                }
                target.setHours(20, 0, 0, 0);
            }
            const pad = (n) => String(n).padStart(2, '0');
            el.value = `${target.getFullYear()}-${pad(target.getMonth()+1)}-${pad(target.getDate())}T${pad(target.getHours())}:${pad(target.getMinutes())}`;
        }

        function clearScheduleTime(inputId) {
            const el = document.getElementById(inputId);
            if (el) el.value = "";
        }

        async function submitCustomPost(postType, prefix, runMode) {
            if (!currentProjectId || !currentSubProjectId) return;
            const title = document.getElementById(`${prefix}TitleInput`)?.value.trim() || "";
            const rawContent = document.getElementById(`${prefix}ContentInput`)?.value.trim() || "";
            const mediaUrl = document.getElementById(`${prefix}MediaInput`)?.value.trim() || "";
            const targetUrl = document.getElementById(`${prefix}TargetUrlInput`)?.value.trim() || "https://www.facebook.com";
            const targetId = document.getElementById(`${prefix}TargetIdInput`)?.value.trim() || "";
            const rawSeeding = document.getElementById(`${prefix}SeedingInput`)?.value.trim() || "";
            const autoReactType = document.getElementById(`${prefix}AutoReactInput`)?.value || "LIKE";
            const statusEl = document.getElementById(`${prefix}StatusText`);
            const mediaData = (prefix === "video") ? _videoMediaData : (prefix === "reels" ? _reelsMediaData : _storyMediaData);
            const targetType = (prefix === "video") ? _targetTypeVideo : (prefix === "reels" ? _targetTypeReels : _targetTypeStory);
            const scheduleInput = document.getElementById(`${prefix}ScheduleTimeInput`);
            const scheduledVal = scheduleInput ? scheduleInput.value.trim() : "";
            const shareToFeedEl = document.getElementById(`${prefix}ShareToFeed`);
            const shareToFeed = shareToFeedEl ? shareToFeedEl.checked : true;

            let runNow = false;
            let scheduledAt = null;

            if (runMode === "now" || runMode === true) {
                runNow = true;
                scheduledAt = null;
            } else if (runMode === "schedule") {
                if (!scheduledVal) {
                    alert("⏰ Vui lòng chọn thời gian hẹn giờ (hoặc bấm chọn nút nhanh +15 phút, +1 giờ...) trước khi bấm [LÊN LỊCH ĐĂNG]!");
                    if (scheduleInput) scheduleInput.focus();
                    return;
                }
                const schedDate = new Date(scheduledVal);
                if (isNaN(schedDate.getTime()) || schedDate.getTime() <= Date.now()) {
                    alert("⚠️ Thời gian lên lịch phải ở tương lai! Vui lòng chọn lại.");
                    if (scheduleInput) scheduleInput.focus();
                    return;
                }
                runNow = false;
                scheduledAt = scheduledVal;
            } else {
                runNow = false;
                scheduledAt = scheduledVal || null;
            }

            if (!rawContent && !title && !mediaData && !mediaUrl) {
                alert("Vui lòng nhập nội dung bài viết hoặc đính kèm ảnh/video!");
                return;
            }

            const content = parseSpintax(rawContent);
            const seedingComments = rawSeeding ? rawSeeding.split("\\n").map(s => s.trim()).filter(Boolean) : [];

            if (statusEl) {
                if (runNow) {
                    statusEl.textContent = "⏳ Đang chuyển lệnh đăng ngầm sang Extension...";
                } else if (scheduledAt) {
                    statusEl.textContent = "⏰ Đang lên lịch đăng bài...";
                } else {
                    statusEl.textContent = "⏳ Đang lưu vào hàng đợi...";
                }
                statusEl.style.color = "var(--accent)";
            }

            try {
                const payload = {
                    title,
                    content,
                    postType: postType,
                    targetType: targetType || "profile",
                    targetId,
                    targetUrl,
                    shareToFeed: !!shareToFeed,
                    mediaUrl,
                    mediaData: mediaData ? {
                        base64: mediaData.base64,
                        fileName: mediaData.fileName,
                        mimeType: mediaData.mimeType,
                        size: mediaData.size
                    } : null,
                    seedingComments,
                    autoReactType,
                    runNow: !!runNow,
                    scheduledAt: scheduledAt
                };

                const res = await fetch("/api/v1/posts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        ...payload
                    })
                });

                const data = await res.json();
                if (data.success) {
                    if (statusEl) {
                        if (runNow) {
                            statusEl.textContent = "🚀 Đã phát lệnh đăng thành công sang Extension!";
                        } else if (scheduledAt) {
                            statusEl.textContent = "⏰ Đã lên lịch đăng bài thành công!";
                        } else {
                            statusEl.textContent = "✅ Đã lưu vào hàng đợi!";
                        }
                        statusEl.style.color = "var(--success)";
                    }
                    if (document.getElementById(`${prefix}TitleInput`)) document.getElementById(`${prefix}TitleInput`).value = "";
                    if (document.getElementById(`${prefix}ContentInput`)) document.getElementById(`${prefix}ContentInput`).value = "";
                    if (document.getElementById(`${prefix}MediaInput`)) document.getElementById(`${prefix}MediaInput`).value = "";
                    if (document.getElementById(`${prefix}SeedingInput`)) document.getElementById(`${prefix}SeedingInput`).value = "";
                    if (scheduleInput) scheduleInput.value = "";
                    if (prefix === "video") clearCustomMedia("video");
                    else if (prefix === "reels") clearCustomMedia("reels");
                    else if (prefix === "story") clearCustomMedia("story");

                    setTimeout(() => {
                        if (currentProjectId) fetchParentProjectData(currentProjectId);
                        if (runNow) {
                            setTimeout(() => { switchSubMenu('sub-post-manager'); }, 400);
                        }
                    }, 600);
                } else {
                    if (statusEl) {
                        statusEl.textContent = "❌ " + extractErrorMsg(data.error, "Lỗi tạo bài đăng");
                        statusEl.style.color = "var(--danger)";
                    }
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        function setPostFilter(filterType, btn) {
            _currentPostFilter = filterType;
            if (typeof _queuePaginationState === "object") {
                Object.keys(_queuePaginationState).forEach(k => _queuePaginationState[k].page = 1);
            }
            document.querySelectorAll(".preset-chip").forEach(b => {
                const oc = b.getAttribute("onclick") || "";
                if (oc.includes("setPostFilter")) {
                    if (oc.includes(`'${filterType}'`)) {
                        b.classList.add("active");
                    } else {
                        b.classList.remove("active");
                    }
                }
            });
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (sub) {
                const pCfg = getPlatformConfig(sub.type || "facebook");
                renderAutoPosterStudio(sub, pCfg);
            }
        }

        function filterPostList(query) {
            _postSearchQuery = query;
            if (typeof _queuePaginationState === "object") {
                Object.keys(_queuePaginationState).forEach(k => _queuePaginationState[k].page = 1);
            }
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (sub) {
                const pCfg = getPlatformConfig(sub.type || "facebook");
                renderAutoPosterStudio(sub, pCfg);
            }
        }

        function openAddSeedingModal(postId) {
            _currentAddSeedingPostId = postId;
            const modal = document.getElementById("addSeedingModal");
            const title = document.getElementById("addSeedingModalTitle");
            const input = document.getElementById("addSeedingCommentsInput");
            if (!modal) return;
            if (title) title.innerHTML = `<span>💬</span> <span>Tạo Seeding Mới Cho Bài Viết (${escapeHtml(postId)})</span>`;
            if (input) input.value = "";
            modal.classList.add("active");
        }

        function closeAddSeedingModal() {
            const modal = document.getElementById("addSeedingModal");
            if (modal) modal.classList.remove("active");
        }

        function insertModalSeedingPreset(type) {
            const input = document.getElementById("addSeedingCommentsInput");
            if (!input) return;
            if (type === "inquiry") {
                input.value = "Shop ơi cho em xin thông tin giá với ạ!\\nSản phẩm này còn sẵn hàng giao ngay không?\\nCó những màu nào vậy shop?\\nInbox tư vấn chi tiết giúp mình với nha";
            } else if (type === "feedback") {
                input.value = "Đã nhận được hàng, sản phẩm đẹp và chất lượng lắm!\\nChủ shop tư vấn cực kỳ nhiệt tình, 5 sao nhé\\nGiao hàng nhanh, đóng gói cẩn thận\\nSẽ ủng hộ shop thêm nhiều lần nữa";
            }
        }

        async function submitAddSeedingModal() {
            if (!_currentAddSeedingPostId || !currentProjectId || !currentSubProjectId) return;
            const input = document.getElementById("addSeedingCommentsInput");
            const autoReact = document.getElementById("addSeedingAutoReactInput")?.value || "LIKE";
            const rawText = input ? input.value.trim() : "";
            if (!rawText) {
                alert("Vui lòng nhập ít nhất 1 câu bình luận seeding!");
                return;
            }
            const comments = rawText.split("\\n").map(s => s.trim()).filter(Boolean);

            try {
                const res = await fetch("/api/subprojects/add-seeding", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        postId: _currentAddSeedingPostId,
                        comments: comments,
                        autoReactType: autoReact
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(`✅ Đã gửi lệnh seeding thêm ${comments.length} bình luận lên Facebook!`);
                    closeAddSeedingModal();
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error, "Không thể gửi seeding"));
                }
            } catch(e) {
                alert("❌ Lỗi kết nối: " + e.message);
            }
        }

        async function runPostNow(postId) {
            if (!currentProjectId || !currentSubProjectId || !postId) return;
            try {
                const res = await fetch(`/api/v1/posts/${postId}/run`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        postId: postId
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert("🚀 Đã phát lệnh đăng bài ngay lên Extension Chrome!");
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error, "Không thể thực thi"));
                }
            } catch(e) {
                alert("❌ Lỗi kết nối: " + e.message);
            }
        }

        let _currentEditSchedulePostId = null;

        function openEditScheduleModal(postId, currentScheduledTime) {
            _currentEditSchedulePostId = postId;
            const modal = document.getElementById("editScheduleModal");
            const input = document.getElementById("modalEditScheduleInput");
            const title = document.getElementById("editScheduleModalTitle");
            if (!modal) return;
            if (title) title.innerHTML = `<span>⏰</span> <span>Đổi Giờ Đăng Cho Bài Viết (${escapeHtml(postId)})</span>`;
            if (input) {
                if (currentScheduledTime && currentScheduledTime > 0) {
                    const d = new Date(currentScheduledTime);
                    const pad = (n) => String(n).padStart(2, '0');
                    input.value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
                } else {
                    input.value = "";
                }
            }
            modal.classList.add("active");
        }

        function closeEditScheduleModal() {
            const modal = document.getElementById("editScheduleModal");
            if (modal) modal.classList.remove("active");
            _currentEditSchedulePostId = null;
        }

        async function submitEditScheduleModal(action) {
            if (!_currentEditSchedulePostId) return;
            const input = document.getElementById("modalEditScheduleInput");
            const val = input ? input.value.trim() : "";

            if (action === 'now') {
                const pid = _currentEditSchedulePostId;
                closeEditScheduleModal();
                await runPostNow(pid);
                return;
            }

            let scheduledAt = null;
            if (action === 'save') {
                if (!val) {
                    alert("Vui lòng chọn thời gian muốn lên lịch đăng, hoặc bấm '✕ Hủy Hẹn Giờ (Về Nháp)' nếu muốn lưu nháp!");
                    return;
                }
                const schedDate = new Date(val);
                if (isNaN(schedDate.getTime()) || schedDate.getTime() <= Date.now()) {
                    alert("⚠️ Thời gian lên lịch phải ở tương lai! Vui lòng chọn lại.");
                    return;
                }
                scheduledAt = val;
            } else if (action === 'clear') {
                scheduledAt = null;
            }

            try {
                const res = await fetch(`/api/v1/posts/${_currentEditSchedulePostId}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        scheduledAt: scheduledAt
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(scheduledAt ? "✅ Đã cập nhật giờ đăng mới thành công!" : "✅ Đã hủy lịch hẹn, chuyển bài viết thành lưu nháp!");
                    closeEditScheduleModal();
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error, "Không thể cập nhật lịch đăng"));
                }
            } catch(e) {
                alert("❌ Lỗi kết nối: " + e.message);
            }
        }

        async function viewPostDataJson(postId) {
            try {
                const res = await fetch(`/api/v1/posts/${postId}`);
                const json = await res.json();
                const data = json.data || json.post || json;
                const formatted = JSON.stringify(data, null, 2);
                
                let modalEl = document.getElementById("postJsonModal");
                if (!modalEl) {
                    modalEl = document.createElement("div");
                    modalEl.id = "postJsonModal";
                    modalEl.className = "modal-overlay";
                    modalEl.style.display = "none";
                    modalEl.innerHTML = `
                        <div class="modal-box" style="max-width:720px; width:95%;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                                <h3 style="margin:0; font-size:16px; color:#38bdf8;">📊 Dữ Liệu Bài Viết Facebook & Quản Lý</h3>
                                <button class="btn-sm" style="background:transparent; border:none; color:#cbd5e1; font-size:18px; cursor:pointer;" onclick="document.getElementById('postJsonModal').style.display='none'">&times;</button>
                            </div>
                            <div style="margin-bottom:12px; font-size:13px; color:var(--text-muted);">
                                Dữ liệu chi tiết: ID hệ thống, ID bài viết Facebook, Link bài viết, Feedback ID, Danh sách Seeding ID và thông tin tài khoản.
                            </div>
                            <pre id="postJsonContent" style="background:#0f172a; padding:12px 14px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); color:#34d399; font-family:monospace; font-size:12px; max-height:360px; overflow-y:auto; white-space:pre-wrap; word-break:break-all;"></pre>
                            <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:14px;">
                                <button class="btn-sm btn-purple" onclick="copyPostJsonContent()">📋 Sao Chép JSON</button>
                                <button class="btn-sm" style="background:#334155; color:#fff;" onclick="document.getElementById('postJsonModal').style.display='none'">Đóng</button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(modalEl);
                }
                document.getElementById("postJsonContent").textContent = formatted;
                modalEl.style.display = "flex";
            } catch(err) {
                alert("Lỗi khi tải dữ liệu bài viết: " + err.message);
            }
        }

        function copyPostJsonContent() {
            const txt = document.getElementById("postJsonContent") ? document.getElementById("postJsonContent").textContent : "";
            if (!txt) return;
            navigator.clipboard.writeText(txt).then(() => {
                alert("✅ Đã sao chép toàn bộ dữ liệu bài viết (JSON) vào Clipboard!");
            }).catch(() => {
                alert("Vui lòng bôi đen và sao chép thủ công.");
            });
        }

        function duplicatePost(postId) {
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (!sub) return;
            const post = (sub.postQueue || []).find(x => x.id === postId);
            if (!post) return;

            if (document.getElementById("postTitleInput")) document.getElementById("postTitleInput").value = (post.title || "") + " (Bản sao)";
            if (document.getElementById("postContentInput")) {
                document.getElementById("postContentInput").value = post.content || "";
                updatePostCharCount(document.getElementById("postContentInput"));
            }
            if (document.getElementById("postMediaInput")) document.getElementById("postMediaInput").value = post.mediaUrl || "";
            if (document.getElementById("postTargetUrlInput")) document.getElementById("postTargetUrlInput").value = post.targetUrl || "";
            if (document.getElementById("postTargetIdInput")) document.getElementById("postTargetIdInput").value = post.targetId || "";

            if (post.postType) {
                const btn = document.querySelector(`.type-pill-btn[data-type="${post.postType}"]`);
                if (btn) selectPostTypePill(post.postType, btn);
            }
            if (post.targetType) {
                const btn = document.querySelector(`.target-pill-btn[data-target="${post.targetType}"]`);
                selectTargetTypePill(post.targetType, btn);
            }
            if (post.seedingComments && Array.isArray(post.seedingComments)) {
                if (document.getElementById("postSeedingCommentsInput")) {
                    document.getElementById("postSeedingCommentsInput").value = post.seedingComments.join("\\n");
                }
            }
            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        function renderSinglePostCardHtml(p) {
            const isCompleted = p.status === "completed";
            const isInProgress = p.status === "in_progress" || (p.status && p.status.includes("Đang"));
            const isFailed = p.status === "failed";
            const isScheduled = p.status === "scheduled";

            let statusBadgeHtml = `<span class="badge-folder" style="background:rgba(251,191,36,0.2); color:#fbbf24; border:1px solid rgba(251,191,36,0.4);">⏳ Đang Chờ</span>`;
            if (isCompleted) {
                statusBadgeHtml = `<span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; border:1px solid rgba(52,211,153,0.4);">✅ Hoàn Thành</span>`;
            } else if (isInProgress) {
                statusBadgeHtml = `<span class="badge-folder" style="background:rgba(56,189,248,0.2); color:#38bdf8; border:1px solid rgba(56,189,248,0.4); display:inline-flex; align-items:center; gap:5px;"><div class="pulse-spinner"></div> Đang Xử Lý</span>`;
            } else if (isScheduled) {
                statusBadgeHtml = `<span class="badge-folder" style="background:rgba(14,165,233,0.25); color:#38bdf8; border:1px solid rgba(14,165,233,0.5); font-weight:700;">⏰ ĐÃ LÊN LỊCH</span>`;
            } else if (isFailed) {
                statusBadgeHtml = `<span class="badge-folder" style="background:rgba(239,68,68,0.2); color:#ef4444; border:1px solid rgba(239,68,68,0.4);">❌ Thất Bại</span>`;
            }

            const typeMap = { "post": "📝 Bài Viết", "video": "🎬 Video", "reel": "⚡ Reels", "story": "📖 Story" };
            const targetMap = { "profile": "👤 Profile", "page": "🚩 Fanpage", "group": "👥 Group" };

            const typeBadge = typeMap[p.postType || "post"] || "📝 Bài Viết";
            const targetBadge = targetMap[p.targetType || "profile"] || "👤 Profile";

            const fbPostId = p.fbPostId || "";
            let fbPostUrl = p.fbPostUrl || "";
            if (!fbPostUrl && fbPostId) {
                if (fbPostId.startsWith("pfbid")) fbPostUrl = `https://www.facebook.com/posts/${fbPostId}`;
                else if (p.postType === "reel") fbPostUrl = `https://www.facebook.com/reel/${fbPostId}`;
                else if (p.postType === "video") fbPostUrl = `https://www.facebook.com/watch/?v=${fbPostId}`;
                else fbPostUrl = `https://www.facebook.com/photo/?fbid=${fbPostId}`;
            }

            const seedingCount = (p.seedingComments && Array.isArray(p.seedingComments)) ? p.seedingComments.length : 0;
            const timeStr = p.createdAt ? new Date(p.createdAt).toLocaleString("vi-VN") : "";
            const scheduledBadge = (isScheduled && p.scheduledTimeStr) ?
                `<span class="badge-folder" style="background:rgba(14,165,233,0.2); color:#38bdf8; border:1px solid rgba(14,165,233,0.4); font-weight:700;">⏰ Hẹn Lúc: ${escapeHtml(p.scheduledTimeStr)}</span>` : '';

            return `
                <div class="smart-post-card" style="${isInProgress ? 'border-color: #38bdf8; box-shadow: 0 0 15px rgba(56,189,248,0.2);' : (isCompleted ? 'border-color: rgba(52,211,153,0.3);' : (isScheduled ? 'border-color: rgba(14,165,233,0.4); box-shadow: 0 0 12px rgba(14,165,233,0.15);' : ''))}">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                            <span class="badge-folder" style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.4);">${typeBadge}</span>
                            <span class="badge-folder" style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3);">${targetBadge}</span>
                            ${p.shareToFeed !== false ? '<span class="badge-folder" style="background:rgba(14,165,233,0.15); color:#38bdf8;" title="Chia sẻ lên Bảng tin & Tin (Story): BẬT">📰 Bảng tin / Tin: Bật</span>' : '<span class="badge-folder" style="background:rgba(148,163,184,0.15); color:#94a3b8;" title="Chia sẻ lên Bảng tin & Tin (Story): TẮT">📰 Bảng tin / Tin: Tắt</span>'}
                            ${p.targetId ? `<span class="badge-folder" style="background:rgba(255,255,255,0.06); color:#cbd5e1;">Target ID: ${escapeHtml(p.targetId)}</span>` : ''}
                            ${scheduledBadge}
                            <span style="font-size:11px; color:var(--text-muted);">⏰ ${timeStr}</span>
                        </div>
                        ${statusBadgeHtml}
                    </div>

                    ${p.title ? `<div style="font-weight:700; color:#fff; font-size:14px; margin-top:8px;">${escapeHtml(p.title)}</div>` : ''}
                    <div style="font-size:13px; color:#cbd5e1; margin-top:6px; line-height:1.5; white-space:pre-wrap; max-height:80px; overflow-y:auto;">${escapeHtml(p.content || '(Không có nội dung văn bản)')}</div>

                    <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; align-items:center;">
                        ${p.mediaData ? `<span class="badge-folder" style="background:rgba(168,85,247,0.15); color:#c084fc;">📎 Tệp: ${escapeHtml(p.mediaData.fileName || 'media')}</span>` : ''}
                        ${p.mediaUrl && !p.mediaData ? `<span class="badge-folder" style="background:rgba(56,189,248,0.15); color:#38bdf8; max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">🖼️ URL: ${escapeHtml(p.mediaUrl)}</span>` : ''}
                        ${seedingCount > 0 ? `<span class="badge-folder" style="background:rgba(52,211,153,0.15); color:#34d399;">💬 ${seedingCount} Seeding</span>` : ''}
                        ${p.autoReactType && p.autoReactType !== "NONE" ? `<span class="badge-folder" style="background:rgba(239,68,68,0.15); color:#f87171;">❤️ React: ${escapeHtml(p.autoReactType)}</span>` : ''}
                    </div>

                    ${p.progressStep ? `
                        <div style="margin-top:10px; padding:10px 14px; border-radius:10px; font-size:12px; font-weight:600; background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.3); color:#38bdf8; display:flex; align-items:center; gap:8px;">
                            ${isInProgress ? '<div class="pulse-spinner"></div>' : '✓'}
                            <span>${escapeHtml(p.progressStep)}</span>
                        </div>
                    ` : ''}

                    ${(fbPostUrl || fbPostId || (p.seedingIds && p.seedingIds.length > 0)) ? `
                        <div style="margin-top:10px; padding:10px 12px; background:rgba(15,23,42,0.6); border:1px solid rgba(56,189,248,0.25); border-radius:8px;">
                            <div style="display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
                                ${fbPostId ? `<span class="badge-folder" style="background:rgba(56,189,248,0.2); color:#38bdf8; font-family:monospace; font-weight:700;">🆔 FB Post: ${escapeHtml(fbPostId)}</span>` : ''}
                                ${p.fbFeedbackId ? `<span class="badge-folder" style="background:rgba(168,85,247,0.2); color:#c084fc; font-family:monospace;" title="${escapeHtml(p.fbFeedbackId)}">🎯 Feedback ID: ${escapeHtml(p.fbFeedbackId.length > 18 ? p.fbFeedbackId.slice(0, 16) + '...' : p.fbFeedbackId)}</span>` : ''}
                                ${(p.seedingIds && p.seedingIds.length > 0) ? `<span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; font-family:monospace;">💬 ${p.seedingIds.length} Comment IDs: ${escapeHtml(p.seedingIds.join(', '))}</span>` : ''}
                                ${p.publishedAtStr ? `<span class="badge-folder" style="background:rgba(255,255,255,0.06); color:#cbd5e1;">⏱️ Đăng lúc: ${escapeHtml(p.publishedAtStr)}</span>` : ''}
                            </div>
                            ${fbPostUrl ? `
                                <div style="margin-top:8px;">
                                    <a href="${escapeHtml(fbPostUrl)}" target="_blank" rel="noopener" class="btn-sm btn-green" style="text-decoration:none; display:inline-flex; align-items:center; gap:6px;">
                                        🔗 Xem Bài Viết Trực Tiếp Trên Facebook
                                    </a>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}

                    ${p.lastError && !isCompleted ? `
                        <div style="font-size:12px; color:#f87171; margin-top:10px; background:rgba(239,68,68,0.1); padding:8px 12px; border-radius:8px; border:1px solid rgba(239,68,68,0.3);">
                            ⚠️ Lỗi: ${escapeHtml(p.lastError)}
                        </div>
                    ` : ''}

                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.06); flex-wrap:wrap; gap:8px;">
                        <span style="font-size:11px; color:var(--text-muted); font-family:monospace;">
                            ID: ${escapeHtml(p.id)}
                        </span>
                        <div style="display:flex; gap:6px; flex-wrap:wrap;">
                            <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8; border:1px solid rgba(56,189,248,0.4);" onclick="viewPostDataJson('${p.id}')" title="Xem Toàn Bộ Dữ Liệu Quản Lý JSON">
                                📊 Dữ Liệu (JSON)
                            </button>
                            <button type="button" class="btn-sm ${isCompleted ? 'btn-purple' : 'btn-green'}" onclick="runPostNow('${p.id}')">
                                ${isCompleted ? '🔄 Đăng Lại' : (isScheduled ? '⚡ Đăng Ngay (Bỏ Hẹn)' : '⚡ Đăng Ngay')}
                            </button>
                            ${isScheduled ? `
                            <button type="button" class="btn-sm" style="background:#0284c7; color:#fff;" onclick="openEditScheduleModal('${p.id}', ${p.scheduledTime || 0})">
                                ✏️ Đổi Giờ
                            </button>` : ''}
                            <button type="button" class="btn-sm" style="background:#0891b2;" onclick="openAddSeedingModal('${p.id}')">
                                ➕ 💬 Tạo Seeding Mới
                            </button>
                            <button type="button" class="btn-sm" style="background:#334155;" onclick="duplicatePost('${p.id}')" title="Nhân Bản">
                                📋 Nhân Bản
                            </button>
                            <button type="button" class="btn-sm btn-danger" onclick="deletePostQueueItem('${p.id}')" title="Xóa">
                                🗑️
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        function renderPaginationControlsHtml(containerId, currentPage, totalPages, totalItems, startIndex, endIndex, pageSize) {
            if (totalItems <= 5 && pageSize === 10) return "";

            function getPageNumbers(curr, total) {
                if (total <= 7) {
                    const arr = [];
                    for (let i = 1; i <= total; i++) arr.push(i);
                    return arr;
                }
                const pages = [1];
                if (curr > 3) pages.push("...");
                const start = Math.max(2, curr - 1);
                const end = Math.min(total - 1, curr + 1);
                for (let i = start; i <= end; i++) {
                    if (!pages.includes(i)) pages.push(i);
                }
                if (curr < total - 2) pages.push("...");
                if (!pages.includes(total)) pages.push(total);
                return pages;
            }

            const pageNumbers = getPageNumbers(currentPage, totalPages);
            const btnsHtml = pageNumbers.map(p => {
                if (p === "...") {
                    return `<span style="padding: 4px 6px; color: #64748b; font-size: 13px;">...</span>`;
                }
                const isActive = p === currentPage;
                return `
                    <button type="button" class="btn-sm" style="${isActive ? 'background:#0284c7; color:#fff; font-weight:700; border:1px solid #38bdf8;' : 'background:#1e293b; color:#cbd5e1; border:1px solid #334155; cursor:pointer;'}" onclick="changeQueuePage('${containerId}', ${p})">
                        ${p}
                    </button>
                `;
            }).join("");

            return `
                <div class="queue-pagination-bar" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-top:16px; padding:12px 16px; background:#0b1329; border:1px solid #1e293b; border-radius:10px;">
                    <div style="display:flex; align-items:center; gap:10px; font-size:13px; color:#94a3b8; flex-wrap:wrap;">
                        <span>Hiển thị <b style="color:#38bdf8;">${totalItems === 0 ? 0 : startIndex + 1} - ${endIndex}</b> trên <b style="color:#fff;">${totalItems}</b> bài viết (Trang <b style="color:#38bdf8;">${currentPage}</b> / ${totalPages})</span>
                        <span style="color:#334155;">|</span>
                        <div style="display:inline-flex; align-items:center; gap:6px;">
                            <span style="font-size:12px;">Số bài / trang:</span>
                            <select onchange="changeQueuePageSize('${containerId}', this.value)" style="background:#1e293b; border:1px solid #334155; color:#cbd5e1; border-radius:6px; padding:3px 8px; font-size:12px; cursor:pointer;">
                                <option value="5" ${pageSize === 5 ? 'selected' : ''}>5 bài</option>
                                <option value="10" ${pageSize === 10 ? 'selected' : ''}>10 bài</option>
                                <option value="20" ${pageSize === 20 ? 'selected' : ''}>20 bài</option>
                                <option value="50" ${pageSize === 50 ? 'selected' : ''}>50 bài</option>
                                <option value="100" ${pageSize === 100 ? 'selected' : ''}>100 bài</option>
                                <option value="99999" ${pageSize >= 99999 ? 'selected' : ''}>Tất cả</option>
                            </select>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
                        <button type="button" class="btn-sm" style="background:#1e293b; color:#cbd5e1; border:1px solid #334155; padding:5px 9px; ${currentPage <= 1 ? 'opacity:0.35; pointer-events:none;' : 'cursor:pointer;'}" onclick="changeQueuePage('${containerId}', 1)" title="Trang đầu">
                            ⏮
                        </button>
                        <button type="button" class="btn-sm" style="background:#1e293b; color:#cbd5e1; border:1px solid #334155; padding:5px 9px; ${currentPage <= 1 ? 'opacity:0.35; pointer-events:none;' : 'cursor:pointer;'}" onclick="changeQueuePage('${containerId}', ${currentPage - 1})" title="Trang trước">
                            ◀ Trước
                        </button>
                        ${btnsHtml}
                        <button type="button" class="btn-sm" style="background:#1e293b; color:#cbd5e1; border:1px solid #334155; padding:5px 9px; ${currentPage >= totalPages ? 'opacity:0.35; pointer-events:none;' : 'cursor:pointer;'}" onclick="changeQueuePage('${containerId}', ${currentPage + 1})" title="Trang sau">
                            Sau ▶
                        </button>
                        <button type="button" class="btn-sm" style="background:#1e293b; color:#cbd5e1; border:1px solid #334155; padding:5px 9px; ${currentPage >= totalPages ? 'opacity:0.35; pointer-events:none;' : 'cursor:pointer;'}" onclick="changeQueuePage('${containerId}', ${totalPages})" title="Trang cuối">
                            ⏭
                        </button>
                    </div>
                </div>
            `;
        }

        function changeQueuePage(containerId, pageNum) {
            if (!_queuePaginationState[containerId]) _queuePaginationState[containerId] = { page: 1, pageSize: 10 };
            _queuePaginationState[containerId].page = parseInt(pageNum) || 1;
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (sub) {
                const pCfg = getPlatformConfig(sub.type || "facebook");
                renderAutoPosterStudio(sub, pCfg);
            }
            const container = document.getElementById(containerId);
            if (container) container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function changeQueuePageSize(containerId, newSize) {
            if (!_queuePaginationState[containerId]) _queuePaginationState[containerId] = { page: 1, pageSize: 10 };
            _queuePaginationState[containerId].pageSize = parseInt(newSize) || 10;
            _queuePaginationState[containerId].page = 1;
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (sub) {
                const pCfg = getPlatformConfig(sub.type || "facebook");
                renderAutoPosterStudio(sub, pCfg);
            }
        }

        function renderPostQueueList(posts, containerId, countBadgeId, emptyIcon, emptyTitle, emptyDesc) {
            const container = document.getElementById(containerId);
            const countBadge = document.getElementById(countBadgeId);
            if (!container) return;

            if (posts.length === 0) {
                if (countBadge) countBadge.textContent = "0 Mục";
                container.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:36px 20px; text-align:center;">
                        <span style="font-size:32px;">${emptyIcon}</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">${emptyTitle}</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${emptyDesc}</div>
                    </div>
                `;
                return;
            }

            // 1. Luôn đảo ngược / sắp xếp bài viết mới nhất lên trên đầu (Newest on Top)
            const sorted = [...posts].sort((a, b) => {
                const getTs = (item) => {
                    if (item.createdAt && Number(item.createdAt) > 0) return Number(item.createdAt);
                    if (item.scheduledTime && Number(item.scheduledTime) > 0) return Number(item.scheduledTime);
                    if (item.id) {
                        const m = String(item.id).match(/\d{9,}/);
                        if (m) {
                            const num = Number(m[0]);
                            return num < 1e11 ? num * 1000 : num;
                        }
                    }
                    return 0;
                };
                return getTs(b) - getTs(a);
            });

            // 2. Lọc theo trạng thái và từ khóa tìm kiếm
            let filtered = sorted.filter(p => {
                if (_currentPostFilter === "completed") return p.status === "completed";
                if (_currentPostFilter === "scheduled") return p.status === "scheduled";
                if (_currentPostFilter === "pending") return p.status === "in_progress" || p.status === "pending" || !p.status || p.status.includes("Chờ") || p.status.includes("Đang");
                if (_currentPostFilter === "failed") return p.status === "failed";
                return true;
            });

            if (_postSearchQuery) {
                const q = _postSearchQuery.toLowerCase().trim();
                filtered = filtered.filter(p => 
                    (p.title || "").toLowerCase().includes(q) ||
                    (p.content || "").toLowerCase().includes(q) ||
                    (p.id || "").toLowerCase().includes(q) ||
                    (p.fbPostId || "").toLowerCase().includes(q)
                );
            }

            if (countBadge) {
                countBadge.textContent = filtered.length !== posts.length ? `${filtered.length}/${posts.length} Mục` : `${posts.length} Mục`;
            }

            if (filtered.length === 0) {
                container.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:24px 20px; text-align:center;">
                        Không tìm thấy mục nào phù hợp với bộ lọc hiện tại.
                    </div>
                `;
                return;
            }

            // 3. Phân trang (Pagination)
            if (!_queuePaginationState[containerId]) {
                _queuePaginationState[containerId] = { page: 1, pageSize: 10 };
            }
            const pState = _queuePaginationState[containerId];
            const pageSize = pState.pageSize || 10;
            const totalItems = filtered.length;
            const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
            if (pState.page > totalPages) pState.page = totalPages;
            if (pState.page < 1) pState.page = 1;
            const currentPage = pState.page;
            const startIndex = (currentPage - 1) * pageSize;
            const endIndex = Math.min(startIndex + pageSize, totalItems);
            const pageItems = filtered.slice(startIndex, endIndex);

            const cardsHtml = pageItems.map(renderSinglePostCardHtml).join("");
            const paginationBarHtml = renderPaginationControlsHtml(containerId, currentPage, totalPages, totalItems, startIndex, endIndex, pageSize);

            container.innerHTML = cardsHtml + paginationBarHtml;
        }

        function updateKpis(posts, totalId, pendingId, completedId, seedingId) {
            let pendingCount = 0;
            let completedCount = 0;
            let seedingTotal = 0;
            posts.forEach(p => {
                if (p.status === "completed") completedCount++;
                else if (p.status === "scheduled" || p.status === "in_progress" || p.status === "pending" || !p.status || p.status.includes("Chờ") || p.status.includes("Đang")) pendingCount++;
                if (p.seedingComments && Array.isArray(p.seedingComments)) {
                    seedingTotal += p.seedingComments.length;
                }
            });
            const kpiTotal = document.getElementById(totalId);
            const kpiPending = document.getElementById(pendingId);
            const kpiCompleted = document.getElementById(completedId);
            const kpiSeeding = document.getElementById(seedingId);
            if (kpiTotal) kpiTotal.textContent = posts.length;
            if (kpiPending) kpiPending.textContent = pendingCount;
            if (kpiCompleted) kpiCompleted.textContent = completedCount;
            if (kpiSeeding) kpiSeeding.textContent = seedingTotal;
        }

        function renderAutoPosterStudio(sub, pCfg) {
            const bannerTitle = document.getElementById("autopostBannerTitle");
            const targetUrlInput = document.getElementById("postTargetUrlInput");

            const sourceDomain = sub.sourceDomain || pCfg.domain || "facebook.com";
            if (bannerTitle) bannerTitle.textContent = `Studio Đăng Bài Viết Thường: ${pCfg.name} (${sourceDomain})`;
            if (targetUrlInput && (!targetUrlInput.value || targetUrlInput.value === "https://...")) {
                targetUrlInput.value = "https://www.facebook.com";
            }

            const queue = sub.postQueue || [];

            // 1. Phân loại bài đăng
            const feedPosts = queue.filter(p => !p.postType || p.postType === "post");
            const videoPosts = queue.filter(p => p.postType === "video");
            const reelsPosts = queue.filter(p => p.postType === "reel");
            const storyPosts = queue.filter(p => p.postType === "story");

            // 2. Render Studio 1: Bài Viết Thường (Feed)
            updateKpis(feedPosts, "kpiTotalPosts", "kpiPendingPosts", "kpiCompletedPosts", "kpiTotalSeeding");
            renderPostQueueList(feedPosts, "postQueueTableContainer", "postQueueCountBadge", "📝", "Hàng đợi bài viết thường đang trống", "Soạn nội dung bài viết và đính kèm ảnh/video ở trên rồi bấm [🚀 PHÁT LỆNH ĐĂNG BÀI]!");

            // 3. Render Studio 2: Facebook Video Watch
            updateKpis(videoPosts, "kpiTotalVideoPosts", "kpiPendingVideoPosts", "kpiCompletedVideoPosts", "kpiTotalVideoSeeding");
            renderPostQueueList(videoPosts, "videoPostQueueTableContainer", "videoQueueCountBadge", "🎬", "Hàng đợi Video Watch đang trống", "Tải lên tệp video hoặc dán link ở khung trên rồi bấm [🎬 PHÁT LỆNH ĐĂNG VIDEO WATCH]!");

            // 4. Render Studio 3: Facebook Reels
            updateKpis(reelsPosts, "kpiTotalReelsPosts", "kpiPendingReelsPosts", "kpiCompletedReelsPosts", "kpiTotalReelsSeeding");
            renderPostQueueList(reelsPosts, "reelsPostQueueTableContainer", "reelsQueueCountBadge", "⚡", "Hàng đợi Reels đang trống", "Tải lên video Reels dọc 9:16 ở trên rồi bấm [⚡ PHÁT LỆNH ĐĂNG REELS]!");

            // 5. Render Studio 4: Facebook Story
            updateKpis(storyPosts, "kpiTotalStoryPosts", "kpiPendingStoryPosts", "kpiCompletedStoryPosts", "kpiTotalStoryPosts");
            renderPostQueueList(storyPosts, "storyPostQueueTableContainer", "storyQueueCountBadge", "📖", "Hàng đợi Story đang trống", "Chọn ảnh hoặc video ngắn 15s ở trên rồi bấm [📖 PHÁT LỆNH ĐĂNG STORY]!");

            // 6. Render Post Manager: Quản Lý Bài Viết Đã Đăng (ALL POSTS)
            renderPostManagerView(queue);
        }

        // ===== POST MANAGER (QUẢN LÝ BÀI VIẾT ĐÃ ĐĂNG) =====
        let _currentMgrFilter = "all";
        let _currentMgrSearch = "";

        function setPostManagerFilter(filter, btnEl) {
            _currentMgrFilter = filter;
            document.querySelectorAll("#view-sub-post-manager .filter-tabs-row .preset-chip").forEach(b => b.classList.remove("active"));
            if (btnEl) btnEl.classList.add("active");
            refreshPostManagerFromCache();
        }

        function filterPostManagerList(keyword) {
            _currentMgrSearch = keyword.toLowerCase().trim();
            refreshPostManagerFromCache();
        }

        function refreshPostManagerFromCache() {
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (!sub) return;
            const queue = sub.postQueue || [];
            renderPostManagerView(queue);
        }

        function renderPostManagerView(allPosts) {
            // KPIs
            let totalCount = allPosts.length;
            let pendingCount = 0, completedCount = 0, failedCount = 0;
            allPosts.forEach(p => {
                if (p.status === "completed") completedCount++;
                else if (p.status === "failed") failedCount++;
                else pendingCount++;
            });
            const kpiTotal = document.getElementById("kpiMgrTotalPosts");
            const kpiPending = document.getElementById("kpiMgrPendingPosts");
            const kpiCompleted = document.getElementById("kpiMgrCompletedPosts");
            const kpiFailed = document.getElementById("kpiMgrFailedPosts");
            if (kpiTotal) kpiTotal.textContent = totalCount;
            if (kpiPending) kpiPending.textContent = pendingCount;
            if (kpiCompleted) kpiCompleted.textContent = completedCount;
            if (kpiFailed) kpiFailed.textContent = failedCount;

            // Filter by type and status
            let filtered = allPosts;
            if (_currentMgrFilter === "post") {
                filtered = filtered.filter(p => !p.postType || p.postType === "post");
            } else if (_currentMgrFilter === "video") {
                filtered = filtered.filter(p => p.postType === "video");
            } else if (_currentMgrFilter === "reel") {
                filtered = filtered.filter(p => p.postType === "reel");
            } else if (_currentMgrFilter === "story") {
                filtered = filtered.filter(p => p.postType === "story");
            } else if (_currentMgrFilter === "completed") {
                filtered = filtered.filter(p => p.status === "completed");
            } else if (_currentMgrFilter === "scheduled") {
                filtered = filtered.filter(p => p.status === "scheduled");
            } else if (_currentMgrFilter === "pending") {
                filtered = filtered.filter(p => p.status === "in_progress" || p.status === "pending" || !p.status || (p.status && (p.status.includes("Chờ") || p.status.includes("Đang"))));
            } else if (_currentMgrFilter === "failed") {
                filtered = filtered.filter(p => p.status === "failed");
            }

            // Search
            if (_currentMgrSearch) {
                filtered = filtered.filter(p => {
                    const haystack = ((p.content || "") + " " + (p.title || "") + " " + (p.id || "") + " " + (p.postType || "")).toLowerCase();
                    return haystack.includes(_currentMgrSearch);
                });
            }

            // Sort newest first
            filtered.sort((a, b) => {
                const getTs = (item) => {
                    if (item.createdAt && Number(item.createdAt) > 0) return Number(item.createdAt);
                    if (item.scheduledTime && Number(item.scheduledTime) > 0) return Number(item.scheduledTime);
                    if (item.id) {
                        const m = String(item.id).match(/\\d{9,}/);
                        if (m) {
                            const num = Number(m[0]);
                            return num < 1e11 ? num * 1000 : num;
                        }
                    }
                    return 0;
                };
                return getTs(b) - getTs(a);
            });

            // Render
            renderPostQueueList(filtered, "postManagerTableContainer", "postManagerCountBadge", "📑", "Không có bài viết nào phù hợp bộ lọc", "Đăng bài từ các Studio (Bài Viết, Video, Reels, Story) để bắt đầu quản lý!");
        }

        // ===== GOOGLE FLOW: AI IMAGE GENERATION =====
        async function submitFlowImageGenerate(mode) {
            if (!currentProjectId || !currentSubProjectId) return;

            const prompt = document.getElementById('flowImagePromptInput')?.value.trim() || '';
            const model = document.getElementById('flowImageModelSelect')?.value || 'HARBOR_SEAL';
            const count = parseInt(document.getElementById('flowImageCountSelect')?.value || '4');
            const ratio = document.getElementById('flowImageRatioSelect')?.value || '3:4';
            const statusEl = document.getElementById('flowImageStatusText');

            if (!prompt) {
                alert('Vui lòng nhập prompt mô tả ảnh muốn tạo!');
                return;
            }

            const isQueue = (mode === 'queue');

            if (statusEl) {
                statusEl.textContent = isQueue ? '⏳ Đang lưu vào hàng đợi...' : '🎨 Đang gửi yêu cầu tạo ảnh AI qua Extension...';
                statusEl.style.color = 'var(--accent)';
            }

            try {
                const payload = {
                    projectId: currentProjectId,
                    subProjectId: currentSubProjectId,
                    prompt,
                    model,
                    imageCount: count,
                    aspectRatio: ratio,
                    runNow: !isQueue
                };

                const res = await fetch('/api/v1/flow/generate-image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (data.success) {
                    if (statusEl) {
                        statusEl.textContent = isQueue ? '✅ Đã lưu vào hàng đợi tạo ảnh!' : '🎨 Đã gửi yêu cầu tạo ảnh thành công! Đang chờ kết quả...';
                        statusEl.style.color = 'var(--success)';
                    }
                    document.getElementById('flowImagePromptInput').value = '';

                    setTimeout(() => {
                        if (currentProjectId) fetchParentProjectData(currentProjectId);
                    }, 800);
                } else {
                    if (statusEl) {
                        statusEl.textContent = '❌ ' + extractErrorMsg(data.error, 'Lỗi tạo ảnh');
                        statusEl.style.color = 'var(--danger)';
                    }
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = '❌ Lỗi: ' + e.message;
                    statusEl.style.color = 'var(--danger)';
                }
            }
        }

        function renderFlowImageGallery(sub) {
            const imageQueue = sub.imageQueue || [];
            const container = document.getElementById('flowImageGalleryContainer');
            const countBadge = document.getElementById('flowImageCountBadge');
            const kpiTotal = document.getElementById('kpiFlowTotalImages');
            const kpiPending = document.getElementById('kpiFlowPendingImages');
            const kpiCompleted = document.getElementById('kpiFlowCompletedImages');

            let pendingCount = 0, completedCount = 0;
            imageQueue.forEach(item => {
                if (item.status === 'completed') completedCount++;
                else pendingCount++;
            });

            if (kpiTotal) kpiTotal.textContent = imageQueue.length;
            if (kpiPending) kpiPending.textContent = pendingCount;
            if (kpiCompleted) kpiCompleted.textContent = completedCount;
            if (countBadge) countBadge.textContent = `${imageQueue.length} Ảnh`;

            if (!container) return;

            if (imageQueue.length === 0) {
                container.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:32px 20px; text-align:center;">
                        <span style="font-size:32px;">🎨</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">Chưa có ảnh nào được tạo</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Nhập prompt mô tả ở trên và bấm [🎨 TẠO ẢNH AI NGAY] để bắt đầu!</div>
                    </div>
                `;
                return;
            }

            const sorted = [...imageQueue].sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));

            let html = '<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:16px;">';
            sorted.forEach(item => {
                const images = item.images || [];
                const prompt = item.prompt || 'N/A';
                const status = item.status || 'pending';
                const createdAt = item.createdAt ? new Date(item.createdAt).toLocaleString('vi-VN') : '---';

                const statusBadge = status === 'completed'
                    ? '<span style="color:#34d399; font-size:11px; font-weight:700;">✅ Hoàn thành</span>'
                    : status === 'failed'
                        ? '<span style="color:#f87171; font-size:11px; font-weight:700;">❌ Thất bại</span>'
                        : '<span style="color:#fbbf24; font-size:11px; font-weight:700;">⏳ Đang xử lý</span>';

                html += `<div style="background:#0d1425; border:1px solid #1e293b; border-radius:12px; overflow:hidden;">`;

                if (images.length > 0) {
                    html += `<div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:2px;">`;
                    images.slice(0, 4).forEach(img => {
                        const imgUrl = img.url || img;
                        html += `<div style="aspect-ratio:3/4; overflow:hidden; cursor:pointer;" onclick="window.open('${imgUrl}','_blank')">`;
                        html += `<img src="${imgUrl}" style="width:100%; height:100%; object-fit:cover;" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 100 100><text y=50 x=25 font-size=30>🖼️</text></svg>';" />`;
                        html += `</div>`;
                    });
                    html += `</div>`;
                }

                html += `<div style="padding:12px;">`;
                html += `<div style="font-size:12px; color:#cbd5e1; line-height:1.5; margin-bottom:8px; max-height:48px; overflow:hidden;">${prompt.substring(0, 120)}${prompt.length > 120 ? '...' : ''}</div>`;
                html += `<div style="display:flex; justify-content:space-between; align-items:center;">`;
                html += statusBadge;
                html += `<span style="font-size:10px; color:#64748b;">${createdAt}</span>`;
                html += `</div>`;
                html += `</div></div>`;
            });
            html += '</div>';
            container.innerHTML = html;
        }

        async function submitAutoPost(runMode) {
            if (!currentProjectId || !currentSubProjectId) return;

            // Kiểm tra bảo vệ chống đăng nhầm nick khi lệch UID
            const projObj = allProjects.find(p => p.id === currentProjectId);
            const subObj = projObj ? (projObj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const mismatchStatus = checkSubProjectMismatch(subObj);
            if (mismatchStatus.isMismatch) {
                alert(`🔒 TÍNH NĂNG BỊ KHÓA DO KHÁC TÀI KHOẢN!\n\nThư mục này của UID: ${mismatchStatus.cUser}\nTrong khi Chrome đang đăng nhập UID: ${mismatchStatus.browserFbUid}\n\n👉 Vui lòng:\n1. Tạo Dự Án Con mới cho nick Chrome này\n2. Hoặc vào trang Thông Tin FB để quét nạp lại nick mới!`);
                switchSubMenu('sub-account-info');
                return;
            }

            const title = document.getElementById("postTitleInput")?.value.trim() || "";
            const rawContent = document.getElementById("postContentInput")?.value.trim() || "";
            const mediaUrl = document.getElementById("postMediaInput")?.value.trim() || "";
            const targetUrl = document.getElementById("postTargetUrlInput")?.value.trim() || "https://www.facebook.com";
            const targetId = document.getElementById("postTargetIdInput")?.value.trim() || "";
            const rawSeeding = document.getElementById("postSeedingCommentsInput")?.value.trim() || "";
            const autoReactType = document.getElementById("postAutoReactInput")?.value || "LIKE";
            const statusEl = document.getElementById("autopostStatusText");
            const scheduleInput = document.getElementById("postScheduleTimeInput");
            const scheduledVal = scheduleInput ? scheduleInput.value.trim() : "";
            const shareToFeedEl = document.getElementById("postShareToFeed");
            const shareToFeed = shareToFeedEl ? shareToFeedEl.checked : true;

            let runNow = false;
            let scheduledAt = null;

            if (runMode === "now" || runMode === true) {
                runNow = true;
                scheduledAt = null;
            } else if (runMode === "schedule") {
                if (!scheduledVal) {
                    alert("⏰ Vui lòng chọn thời gian hẹn giờ (hoặc bấm chọn nút nhanh +15 phút, +1 giờ...) trước khi bấm [LÊN LỊCH ĐĂNG]!");
                    if (scheduleInput) scheduleInput.focus();
                    return;
                }
                const schedDate = new Date(scheduledVal);
                if (isNaN(schedDate.getTime()) || schedDate.getTime() <= Date.now()) {
                    alert("⚠️ Thời gian lên lịch phải ở tương lai! Vui lòng chọn lại.");
                    if (scheduleInput) scheduleInput.focus();
                    return;
                }
                runNow = false;
                scheduledAt = scheduledVal;
            } else {
                runNow = false;
                scheduledAt = scheduledVal || null;
            }

            if (!rawContent && !title && !_adminMediaData && !mediaUrl) {
                alert("Vui lòng nhập nội dung bài viết hoặc đính kèm ảnh/video!");
                return;
            }

            const content = parseSpintax(rawContent);
            const seedingComments = rawSeeding ? rawSeeding.split("\\n").map(s => s.trim()).filter(Boolean) : [];

            if (statusEl) {
                if (runNow) {
                    statusEl.textContent = "⏳ Đang chuyển lệnh đăng ngầm sang Extension...";
                } else if (scheduledAt) {
                    statusEl.textContent = "⏰ Đang lên lịch đăng bài...";
                } else {
                    statusEl.textContent = "⏳ Đang lưu vào hàng đợi...";
                }
                statusEl.style.color = "var(--accent)";
            }

            try {
                const payload = {
                    title,
                    content,
                    postType: "post",
                    targetType: _currentTargetType,
                    targetId,
                    targetUrl,
                    shareToFeed: !!shareToFeed,
                    mediaUrl,
                    mediaData: _adminMediaData ? {
                        base64: _adminMediaData.base64,
                        fileName: _adminMediaData.fileName,
                        mimeType: _adminMediaData.mimeType,
                        size: _adminMediaData.size
                    } : null,
                    seedingComments,
                    autoReactType,
                    runNow: !!runNow,
                    scheduledAt: scheduledAt
                };

                const res = await fetch("/api/v1/posts", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        ...payload
                    })
                });

                const data = await res.json();
                if (data.success) {
                    if (statusEl) {
                        if (runNow) {
                            statusEl.textContent = "🚀 Đã phát lệnh đăng bài & seeding ngầm lên Facebook!";
                        } else if (scheduledAt) {
                            statusEl.textContent = "⏰ Đã lên lịch đăng bài thành công!";
                        } else {
                            statusEl.textContent = "✅ Đã lưu vào hàng đợi bài đăng!";
                        }
                        statusEl.style.color = "var(--success)";
                    }

                    document.getElementById("postTitleInput").value = "";
                    document.getElementById("postContentInput").value = "";
                    document.getElementById("postMediaInput").value = "";
                    document.getElementById("postSeedingCommentsInput").value = "";
                    if (scheduleInput) scheduleInput.value = "";
                    clearAdminMedia();
                    updatePostCharCount(document.getElementById("postContentInput"));

                    setTimeout(() => {
                        if (currentProjectId) fetchParentProjectData(currentProjectId);
                        if (runNow) {
                            setTimeout(() => { switchSubMenu('sub-post-manager'); }, 400);
                        }
                    }, 600);
                } else {
                    if (statusEl) {
                        statusEl.textContent = "❌ " + extractErrorMsg(data.error, "Lỗi tạo bài đăng");
                        statusEl.style.color = "var(--danger)";
                    }
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        async function deletePostQueueItem(postId) {
            if (!confirm("Bạn có chắc chắn muốn xóa bài viết / mục này khỏi hàng đợi không?")) return;
            try {
                const res = await fetch(`/api/v1/posts/${postId}`, {
                    method: "DELETE"
                });
                const data = await res.json();
                if (data.success) {
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                } else {
                    alert("Lỗi: " + extractErrorMsg(data.error, "Không thể xóa bài"));
                }
            } catch(e) {
                alert("Lỗi: " + e.message);
            }
        }

        // =========================================================
        // STUDIO TƯƠNG TÁC / SEEDING / NUÔI NICK (INTERACTION STUDIO)
        // =========================================================

        function renderInteractionStudio(sub, pCfg) {
            const bannerTitle = document.getElementById("interactionBannerTitle");
            const bannerDesc = document.getElementById("interactionBannerDesc");
            const sourceDomain = sub.sourceDomain || pCfg.domain;

            if (bannerTitle) bannerTitle.textContent = `Studio Tương Tác & Nuôi Nick: ${pCfg.name} (${sourceDomain})`;
            if (bannerDesc) bannerDesc.textContent = `Tự động lướt web nguồn, xem bài ngẫu nhiên để nuôi tài khoản (warmup nick), thả tim/like tự động và bình luận seeding trên nền tảng ${pCfg.name}.`;
        }

        async function startAutoSurf() {
            if (!currentProjectId || !currentSubProjectId) return;
            const durationSec = parseInt(document.getElementById("interactionSurfDuration")?.value) || 60;
            const statusEl = document.getElementById("interactionStatusText");

            if (statusEl) {
                statusEl.textContent = `⏳ Đang gửi lệnh lướt web tự động (${durationSec}s) tới Chrome...`;
                statusEl.style.color = "var(--accent)";
            }

            const surfScript = `(function() {
                try {
                    let totalMs = ${durationSec} * 1000;
                    let startTime = Date.now();
                    let timer = setInterval(function() {
                        if (Date.now() - startTime >= totalMs) {
                            clearInterval(timer);
                            return;
                        }
                        let distance = (Math.random() > 0.3) ? (Math.floor(Math.random() * 350) + 150) : -(Math.floor(Math.random() * 200) + 50);
                        window.scrollBy({ top: distance, behavior: 'smooth' });
                    }, 1500);
                    return { success: true };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            })()`;

            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "EXECUTE_SCRIPT",
                        code: surfScript
                    })
                });

                if (statusEl) {
                    statusEl.textContent = `🚀 Chrome đang tự động cuộn lướt web nguồn trong ${durationSec}s!`;
                    statusEl.style.color = "var(--success)";
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        async function startAutoLike() {
            if (!currentProjectId || !currentSubProjectId) return;
            const likeCount = parseInt(document.getElementById("interactionLikeCount")?.value) || 5;
            const statusEl = document.getElementById("interactionStatusText");

            if (statusEl) {
                statusEl.textContent = `⏳ Đang gửi lệnh tự động Like ${likeCount} bài viết tới Chrome...`;
                statusEl.style.color = "var(--accent)";
            }

            const likeScript = `(function() {
                try {
                    let count = 0;
                    let maxLike = ${likeCount};
                    let buttons = document.querySelectorAll('div[aria-label="Thích"], div[aria-label="Like"], div[data-testid="like"], span[data-e2e="like-icon"], svg[aria-label="Thích"], svg[aria-label="Like"]');
                    for (let i = 0; i < buttons.length && count < maxLike; i++) {
                        let btn = buttons[i];
                        let clickTarget = btn.closest('button') || btn.closest('div[role="button"]') || btn;
                        if (clickTarget) {
                            setTimeout(function() {
                                clickTarget.click();
                            }, i * 1500);
                            count++;
                        }
                    }
                    return { success: true, count: count };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            })()`;

            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "EXECUTE_SCRIPT",
                        code: likeScript
                    })
                });

                if (statusEl) {
                    statusEl.textContent = `❤️ Đã phát lệnh tự động like ${likeCount} bài trên Chrome!`;
                    statusEl.style.color = "var(--success)";
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        async function startAutoComment() {
            if (!currentProjectId || !currentSubProjectId) return;
            const commentsRaw = document.getElementById("interactionCommentsList")?.value || "";
            const statusEl = document.getElementById("interactionStatusText");
            const lines = commentsRaw.split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean);

            if (lines.length === 0) {
                alert("Vui lòng nhập ít nhất 1 nội dung bình luận vào danh sách!");
                return;
            }

            const randomComment = lines[Math.floor(Math.random() * lines.length)];

            if (statusEl) {
                statusEl.textContent = `⏳ Đang gửi bình luận: "${randomComment.slice(0, 30)}..." tới Chrome...`;
                statusEl.style.color = "var(--accent)";
            }

            const commentScript = `(function() {
                try {
                    let box = document.querySelector('div[role="textbox"], textarea[placeholder*="bình luận"], textarea[placeholder*="comment"], div[data-text="true"], textarea');
                    if (box) {
                        box.focus();
                        document.execCommand('insertText', false, ${JSON.stringify(randomComment)});
                        return { success: true, comment: ${JSON.stringify(randomComment)} };
                    }
                    return { success: false, error: 'Không tìm thấy ô nhập bình luận trên trang hiện tại' };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            })()`;

            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "EXECUTE_SCRIPT",
                        code: commentScript
                    })
                });

                if (statusEl) {
                    statusEl.textContent = `💬 Đã điền nội dung bình luận vào bài viết trên Chrome!`;
                    statusEl.style.color = "var(--success)";
                }
            } catch(e) {
                if (statusEl) {
                    statusEl.textContent = "❌ Lỗi: " + e.message;
                    statusEl.style.color = "var(--danger)";
                }
            }
        }

        // =========================================================
        // ACTIONS (CREATE / EXTRACT / COMMANDS)
        // =========================================================

        function toggleNewFolderForm() {
            const form = document.getElementById("newFolderBox");
            if (form) {
                form.style.display = form.style.display === "none" ? "block" : "none";
                if (form.style.display === "block") {
                    updateFolderInputSuggestions();
                    document.getElementById("newFolderName").focus();
                }
            }
        }

        async function submitCreateFolder() {
            const name = document.getElementById("newFolderName").value.trim();
            const desc = document.getElementById("newFolderDesc").value.trim();
            const customUrl = (document.getElementById("newFolderSourceUrl")?.value || "").trim();
            const statusEl = document.getElementById("createFolderStatus");

            if (!name) {
                statusEl.textContent = "❌ Vui lòng nhập tên thư mục / dự án con!";
                statusEl.style.color = "var(--danger)";
                return;
            }

            statusEl.textContent = "⏳ Đang tạo...";
            statusEl.style.color = "var(--accent)";

            const pCfg = PLATFORM_CONFIG[activeSourcePlatform] || PLATFORM_CONFIG["facebook"];
            const sourceUrl = (activeSourcePlatform === 'custom' && customUrl) ? customUrl : pCfg.defaultUrl;
            let sourceDomain = pCfg.domain;
            if (activeSourcePlatform === 'custom' && customUrl) {
                try {
                    const parsed = new URL(customUrl.startsWith("http") ? customUrl : ("https://" + customUrl));
                    sourceDomain = parsed.hostname;
                } catch(e) {
                    sourceDomain = customUrl.split('/')[0];
                }
            }

            try {
                const res = await fetch("/api/subprojects", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        name,
                        description: desc,
                        type: activeSourcePlatform,
                        purpose: "all",
                        sourceUrl,
                        sourceDomain
                    })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById("newFolderName").value = "";
                    document.getElementById("newFolderDesc").value = "";
                    statusEl.textContent = "✅ Đã tạo thành công!";
                    statusEl.style.color = "var(--success)";
                    setTimeout(() => {
                        toggleNewFolderForm();
                        statusEl.textContent = "";
                    }, 1000);
                    fetchParentProjectData(currentProjectId);
                } else {
                    statusEl.textContent = "❌ Lỗi: " + extractErrorMsg(data.error);
                    statusEl.style.color = "var(--danger)";
                }
            } catch(e) {
                statusEl.textContent = "❌ Lỗi: " + e.message;
                statusEl.style.color = "var(--danger)";
            }
        }

        async function deleteFolder(subId) {
            if (!confirm("🗑️ Bạn có chắc chắn muốn xóa thư mục / dự án con này?")) return;
            try {
                const res = await fetch("/api/subprojects/delete", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: currentProjectId, subProjectId: subId })
                });
                const data = await res.json();
                if (data.success) {
                    fetchParentProjectData(currentProjectId);
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error));
                }
            } catch(e) {
                alert("❌ Lỗi: " + e.message);
            }
        }

        async function quickCreateSubForBrowserUid() {
            if (!currentProjectId) return;
            const nodes = (latestParentData && latestParentData.nodes) || [];
            const activeNode = nodes[0] || null;
            const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";
            
            const defaultName = browserFbUid ? `FB Nick UID ${browserFbUid}` : `FB Nick Mới`;
            const projName = prompt(`➕ Tạo Dự Án Con Mới cho tài khoản Facebook trên trình duyệt Chrome:\n(Nhập tên cho dự án con này)`, defaultName);
            if (!projName || !projName.trim()) return;

            try {
                const res = await fetch("/api/subprojects", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        name: projName.trim(),
                        description: browserFbUid ? `Tài khoản Facebook UID: ${browserFbUid}` : "Dự án Facebook tạo từ Chrome",
                        type: "facebook",
                        purpose: "all",
                        sourceUrl: "https://www.facebook.com",
                        sourceDomain: "facebook.com"
                    })
                });
                const data = await res.json();
                if (data.success && data.subProject) {
                    await fetchParentProjectData(currentProjectId);
                    alert(`✅ Đã tạo thành công Dự Án Con [${projName.trim()}]. Đang chuyển vào dự án mới...`);
                    enterSubProject(data.subProject.id, "sub-account-info", true);
                    // Tự động quét thông tin cho dự án con mới
                    setTimeout(() => {
                        extractAllFbAccountInfo();
                    }, 500);
                } else {
                    alert("❌ Lỗi tạo dự án: " + (data.error || "Không xác định"));
                }
            } catch(e) {
                alert("❌ Lỗi: " + e.message);
            }
        }

        // HÀM QUÉT & NẠP ĐÈ TÀI KHOẢN MỚI TỪ CHROME VÀO THƯ MỤC NÀY
        async function rescanAndOverwriteFbAccount() {
            if (!currentProjectId || !currentSubProjectId) return;
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const nodes = (latestParentData && latestParentData.nodes) || [];
            const activeNode = nodes[0] || null;
            const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";
            const oldUid = sub && sub.c_user ? sub.c_user : "cũ";

            const ok = confirm(`🔄 XÁC NHẬN GHI ĐÈ TÀI KHOẢN MỚI!\n\nBạn có chắc muốn XÓA TRẮNG dữ liệu tài khoản [UID: ${oldUid}] và NẠP TOÀN BỘ thông tin nick Chrome [UID: ${browserFbUid || 'đang login'}] vào thư mục này không?\n\n(Dữ liệu nick cũ trong thư mục này sẽ bị xóa sạch)`);
            if (!ok) return;

            // Xóa trắng dữ liệu cũ
            try {
                await fetch("/api/subprojects/clear-account", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: currentProjectId, subProjectId: currentSubProjectId })
                });
                if (currentProjectId) await fetchParentProjectData(currentProjectId);
            } catch(errClear) {
                console.warn("Lỗi xóa dữ liệu cũ:", errClear);
            }

            // Quét và lấy thông tin nick mới ngay lập tức
            extractAllFbAccountInfo(true);
        }

        // QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FACEBOOK
        let isExtractingFbInfo = false;
        async function extractAllFbAccountInfo(bypassConfirm = false) {
            if (!currentProjectId || !currentSubProjectId) return;
            if (isExtractingFbInfo) return;

            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const hasExistingData = sub && (sub.c_user || sub.fbName || (sub.cookies && sub.cookies.length > 0) || sub.cookieStr || sub.eaagToken);

            const nodes = (latestParentData && latestParentData.nodes) || [];
            const activeNode = nodes[0] || null;
            const browserFbUid = (activeNode && activeNode.browserFbUid) ? String(activeNode.browserFbUid).trim() : "";

            if (!bypassConfirm) {
                // Kiểm tra xem trình duyệt Chrome có UID khác với thư mục hiện tại không
                if (hasExistingData && sub && sub.c_user && browserFbUid && browserFbUid !== String(sub.c_user).trim()) {
                    const choice = confirm(`⚠️ CẢNH BÁO LỆCH TÀI KHOẢN!\n\nThư mục này đang lưu tài khoản UID: ${sub.c_user} (${sub.fbName || 'Chưa tên'}).\nTrong khi trình duyệt Chrome hiện đang đăng nhập UID: ${browserFbUid}.\n\nNếu tiếp tục, dữ liệu của UID [${sub.c_user}] sẽ bị XÓA và THAY THẾ bằng UID [${browserFbUid}]!\n\n👉 Bấm 'OK' nếu bạn chấp nhận XÓA và GHI ĐÈ.\n👉 Bấm 'Cancel' (Hủy) để giữ nguyên (khuyến nghị tạo Dự Án Con khác).`);
                    if (!choice) {
                        const wantNew = confirm(`💡 Bạn có muốn tạo ngay một Dự Án Con Mới cho tài khoản UID [${browserFbUid}] này không?`);
                        if (wantNew) {
                            quickCreateSubForBrowserUid();
                        }
                        return;
                    }

                    // Xóa trắng dữ liệu cũ trên server trước khi quét mới
                    try {
                        await fetch("/api/subprojects/clear-account", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ projectId: currentProjectId, subProjectId: currentSubProjectId })
                        });
                        if (currentProjectId) await fetchParentProjectData(currentProjectId);
                    } catch(errClear) {
                        console.warn("Lỗi xóa dữ liệu cũ:", errClear);
                    }
                } else if (hasExistingData) {
                    const accLabel = sub.fbName || (sub.c_user ? `UID: ${sub.c_user}` : 'hiện tại');
                    const ok = confirm(`⚠️ Tài khoản này đã có thông tin [${accLabel}].\n\nBạn có muốn XÓA TRẮNG DỮ LIỆU CŨ để quét và nạp dữ liệu mới từ Chrome không?`);
                    if (!ok) return;

                    // Xóa trắng dữ liệu cũ trên server trước khi quét mới
                    try {
                        await fetch("/api/subprojects/clear-account", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ projectId: currentProjectId, subProjectId: currentSubProjectId })
                        });
                        if (currentProjectId) await fetchParentProjectData(currentProjectId);
                    } catch(errClear) {
                        console.warn("Lỗi xóa dữ liệu cũ:", errClear);
                    }
                }
            }

            const bannerBtn = document.getElementById("subAccBannerBtn");
            const oldBtnHtml = bannerBtn ? bannerBtn.innerHTML : "";

            if (nodes.length === 0) {
                alert("⚠️ Trình duyệt Chrome chưa kết nối Extension! Vui lòng mở Chrome và đảm bảo Extension Auth Helper đang chạy.");
            }

            try {
                isExtractingFbInfo = true;
                if (bannerBtn) {
                    bannerBtn.innerHTML = `<span>⏳</span> <span>ĐANG QUÉT TỪ CHROME (CHỜ 2-5S)...</span>`;
                    bannerBtn.disabled = true;
                    bannerBtn.style.opacity = "0.75";
                }

                const loginStatus = document.getElementById("fbAccLoginStatus");
                if (loginStatus) {
                    loginStatus.innerHTML = `<span style="color:#38bdf8;">🔄 Đang lấy dữ liệu từ Chrome...</span>`;
                }

                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "GET_FB_ACCOUNT",
                        domain: "facebook.com"
                    })
                });

                // Polling kiểm tra kết quả trả về từ Chrome (mỗi 1s, tối đa 7 lần)
                let attempts = 0;
                const pollInterval = setInterval(async () => {
                    attempts++;
                    if (currentProjectId) await fetchParentProjectData(currentProjectId);

                    if (attempts >= 7) {
                        clearInterval(pollInterval);
                        isExtractingFbInfo = false;
                        if (bannerBtn) {
                            bannerBtn.innerHTML = oldBtnHtml || `<span>🔄</span> <span>QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FB</span>`;
                            bannerBtn.disabled = false;
                            bannerBtn.style.opacity = "1";
                        }
                    }
                }, 1000);

            } catch(e) {
                isExtractingFbInfo = false;
                if (bannerBtn) {
                    bannerBtn.innerHTML = oldBtnHtml;
                    bannerBtn.disabled = false;
                    bannerBtn.style.opacity = "1";
                }
                alert("Lỗi: " + e.message);
            }
        }

        // TAB & SCRIPT RUNNER
        async function sendProjectAction(action, payload = {}) {
            if (!currentProjectId) return;
            try {
                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action,
                        ...payload
                    })
                });
                setTimeout(() => {
                    if (currentProjectId) fetchParentProjectData(currentProjectId);
                }, 1000);
            } catch(e) {}
        }

        function projectOpenTab(url) {
            if (!url) return;
            sendProjectAction("OPEN_TAB", { url: url.trim() });
        }

        function setSubScript(code) {
            document.getElementById("subJsCode").value = code;
        }

        function runSubScript() {
            const code = document.getElementById("subJsCode").value.trim();
            if (!code) return;
            sendProjectAction("EXECUTE_SCRIPT", { code });
            const out = document.getElementById("subScriptOutputBox");
            if (out) out.textContent = "⏳ Đang thực thi trên Chrome...";
        }

        // COPY UTILITIES
        function copyFbUid() {
            const uid = document.getElementById("fbAccUid").textContent;
            if (!uid || uid === "---") {
                alert("Chưa có UID để sao chép!");
                return;
            }
            navigator.clipboard.writeText(uid);
            alert("📋 Đã sao chép Facebook UID: " + uid);
        }

        async function copyActiveSubCookieString() {
            const str = document.getElementById("fbAccCookieStrBox").textContent;
            if (!str || str.startsWith("Chưa có")) {
                alert("Chưa có cookie để sao chép!");
                return;
            }
            try {
                await navigator.clipboard.writeText(str);
                alert("📋 Đã sao chép chuỗi Cookie Facebook vào bộ nhớ tạm!");
            } catch(e) {
                prompt("Copy cookie bên dưới:", str);
            }
        }

        async function copyActiveSubCookieJson() {
            const el = document.getElementById("subCookieJsonBox") || document.getElementById("fbAccCookieJsonBox");
            const json = el ? el.textContent : "[]";
            if (!json || json === "[]") {
                alert("Chưa có Cookie JSON để sao chép! Hãy bấm nút [QUÉT & NẠP LẠI COOKIE JSON] trước.");
                return;
            }
            try {
                await navigator.clipboard.writeText(json);
                alert("📋 Đã sao chép Cookie JSON chuẩn vào bộ nhớ tạm! Bạn có thể dán trực tiếp vào Gologin, AdsPower, MoreLogin, GenLogin hoặc tool auto.");
            } catch(e) {
                prompt("Copy JSON bên dưới:", json);
            }
        }

        function triggerPlatformScan() {
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = (sub && sub.type) ? sub.type : "facebook";
            if (subType === 'facebook') {
                extractAllFbAccountInfo();
            } else {
                extractCookiesForActiveSub();
            }
        }

        function downloadActiveSubCookieJsonFile() {
            const el = document.getElementById("subCookieJsonBox") || document.getElementById("fbAccCookieJsonBox");
            const jsonStr = el ? el.textContent : "[]";
            if (!jsonStr || jsonStr === "[]") {
                alert("Chưa có Cookie JSON để tải! Hãy bấm nút [QUÉT & NẠP LẠI COOKIE JSON] trước.");
                return;
            }
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = (sub && sub.type) ? sub.type : "sub";

            const blob = new Blob([jsonStr], { type: "application/json" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `${subType}-cookies-${currentSubProjectId || 'sub'}.json`;
            a.click();
        }

        let isExtractingCookies = false;
        async function extractCookiesForActiveSub() {
            if (!currentProjectId || !currentSubProjectId) return;
            if (isExtractingCookies) return;

            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = (sub && sub.type) ? sub.type : "facebook";
            const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];
            const domain = pCfg.domain || "facebook.com";

            const hasExistingCookies = sub && ((sub.cookies && sub.cookies.length > 0) || sub.cookieStr || sub.c_user);
            if (hasExistingCookies) {
                const ok = confirm(`⚠️ Thư mục này đã có cookie lưu trữ (${(sub.cookies && sub.cookies.length) || 0} cookies).\n\nBạn có muốn XÓA TRẮNG DỮ LIỆU CŨ để nạp lại cookie mới từ trình duyệt không?`);
                if (!ok) return;

                try {
                    await fetch("/api/subprojects/clear-account", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ projectId: currentProjectId, subProjectId: currentSubProjectId })
                    });
                    if (currentProjectId) await fetchParentProjectData(currentProjectId);
                } catch(errClear) {}
            }

            const bannerBtn = document.getElementById("subAccBannerBtn");
            const oldBtnHtml = bannerBtn ? bannerBtn.innerHTML : "";

            const nodes = (latestParentData && latestParentData.nodes) || [];
            if (nodes.length === 0) {
                alert("⚠️ Trình duyệt Chrome chưa kết nối Extension! Vui lòng mở Chrome và đảm bảo Extension Auth Helper đang chạy.");
            }

            try {
                isExtractingCookies = true;
                if (bannerBtn) {
                    bannerBtn.innerHTML = `<span>⏳</span> <span>ĐANG NẠP COOKIE TỪ CHROME (CHỜ 2-5S)...</span>`;
                    bannerBtn.disabled = true;
                    bannerBtn.style.opacity = "0.75";
                }

                await fetch("/api/bridge/command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        targetProjectId: currentProjectId,
                        targetSubProjectId: currentSubProjectId,
                        targetNodeId: "*",
                        action: "GET_COOKIES",
                        domain: domain
                    })
                });

                let attempts = 0;
                const pollInterval = setInterval(async () => {
                    attempts++;
                    if (currentProjectId) await fetchParentProjectData(currentProjectId);

                    if (attempts >= 7) {
                        clearInterval(pollInterval);
                        isExtractingCookies = false;
                        if (bannerBtn) {
                            bannerBtn.innerHTML = oldBtnHtml || `<span>🔄</span> <span>QUÉT & NẠP LẠI COOKIE ${pCfg.name}</span>`;
                            bannerBtn.disabled = false;
                            bannerBtn.style.opacity = "1";
                        }
                    }
                }, 1000);

            } catch(e) {
                isExtractingCookies = false;
                if (bannerBtn) {
                    bannerBtn.innerHTML = oldBtnHtml;
                    bannerBtn.disabled = false;
                    bannerBtn.style.opacity = "1";
                }
                alert("Lỗi: " + e.message);
            }
        }

        function downloadActiveSubCookieFile() {
            const str = document.getElementById("fbAccCookieStrBox").textContent;
            if (!str || str.startsWith("Chưa có")) return;
            const proj = allProjects.find(p => p.id === currentProjectId);
            const sub = proj ? (proj.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = (sub && sub.type) ? sub.type : "sub";

            const blob = new Blob([str], { type: "text/plain" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `${subType}-cookies-${currentSubProjectId || 'sub'}.txt`;
            a.click();
        }

        // MACHINE & TABS RENDERING
        function renderMachineOverview(node) {
            const container = document.getElementById("parentMachineDetailsBox");
            if (!container) return;

            if (!node) {
                container.innerHTML = `
                    <div style="background:#090e1c; padding:20px; border-radius:8px; border:1px dashed #334155; text-align:center;">
                        <span style="font-size:26px;">🤖</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">Chưa có máy nào kết nối vào Dự án này</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                            Hãy cài Extension trên Chrome và nhập mã Token của dự án này để bắt đầu!
                        </div>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="grid-responsive" style="display:grid; grid-template-columns:1fr 1fr; gap:14px; font-size:13px;">
                    <div>
                        <span style="color:var(--text-muted);">Tên máy:</span>
                        <div style="font-weight:700; color:#fff; font-size:15px; margin-top:2px;">${node.nodeName || 'Chrome Node'}</div>
                    </div>
                    <div>
                        <span style="color:var(--text-muted);">Node ID:</span>
                        <div style="font-weight:700; color:var(--accent); font-family:monospace; margin-top:2px;">${node.nodeId}</div>
                    </div>
                    <div>
                        <span style="color:var(--text-muted);">Số tab đang mở:</span>
                        <div style="font-weight:700; color:#34d399; margin-top:2px;">${node.tabCount || 0} tabs</div>
                    </div>
                    <div>
                        <span style="color:var(--text-muted);">Ping cuối:</span>
                        <div style="font-weight:600; color:#cbd5e1; margin-top:2px;">${new Date(node.lastSeen).toLocaleTimeString()}</div>
                    </div>
                    <div style="grid-column: span 2;">
                        <span style="color:var(--text-muted);">Tab đang kích hoạt trên máy đó:</span>
                        <div style="background:#050811; border:1px solid #1e293b; padding:10px 12px; border-radius:6px; margin-top:4px;">
                            <div style="font-weight:700; color:#fff;">${node.activeTab ? (node.activeTab.title || 'Không có tiêu đề') : 'Chưa có tab'}</div>
                            <div style="font-size:11px; color:#38bdf8; word-break:break-all; margin-top:2px;">${node.activeTab ? (node.activeTab.url || '') : ''}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        function renderTabsData(tabs) {
            const container = document.getElementById("subTabsContainer");
            if (!container) return;

            if (!tabs || tabs.length === 0) {
                container.innerHTML = '<div style="color:var(--text-muted); font-size:12px;">Chưa có danh sách tab. Bấm nút "Đọc Lại Tab" ở trên!</div>';
                return;
            }

            container.innerHTML = `
                <table style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border-color); color:var(--text-muted); text-align:left;">
                            <th style="padding:8px 10px;">TAB ID</th>
                            <th style="padding:8px 10px;">TIÊU ĐỀ TRANG</th>
                            <th style="padding:8px 10px;">ĐƯỜNG DẪN (URL)</th>
                            <th style="padding:8px 10px; text-align:right;">THAO TÁC</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tabs.map(t => `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
                                <td style="padding:8px 10px; font-family:monospace; color:#38bdf8;">${t.id}</td>
                                <td style="padding:8px 10px; font-weight:600; color:#fff; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${t.title || 'Không có tiêu đề'}</td>
                                <td style="padding:8px 10px; font-size:11px; color:#94a3b8; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${t.url || ''}</td>
                                <td style="padding:8px 10px; text-align:right;">
                                    <button class="btn-sm btn-danger" onclick="sendProjectAction('CLOSE_TAB', { tabId: ${t.id} })">Đóng Tab</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderParentLogs(logs) {
            const box = document.getElementById("parentLogBox");
            if (!box) return;
            if (!logs || logs.length === 0) {
                box.innerHTML = "Chưa có nhật ký hoạt động nào...";
                return;
            }
            box.innerHTML = logs.map(l => `
                <div class="log-line ${l.type ? 'log-' + l.type : ''}">
                    [${new Date(l.time).toLocaleTimeString()}] ${l.message}
                </div>
            `).join('');
            box.scrollTop = box.scrollHeight;
        }

        // =========================================================
        // HUB MANAGEMENT (PARENT PROJECT CREATION & TOKENS)
        // =========================================================

        function toggleNewProjectForm() {
            const form = document.getElementById("newProjectBox");
            if (form) {
                form.style.display = form.style.display === "none" ? "block" : "none";
                if (form.style.display === "block") {
                    document.getElementById("newProjName").focus();
                }
            }
        }

        async function submitCreateProject() {
            const name = document.getElementById("newProjName").value.trim();
            const desc = document.getElementById("newProjDesc").value.trim();
            const statusEl = document.getElementById("createProjStatus");

            if (!name) {
                statusEl.textContent = "❌ Vui lòng nhập tên dự án cha!";
                statusEl.style.color = "var(--danger)";
                return;
            }

            statusEl.textContent = "⏳ Đang tạo...";
            statusEl.style.color = "var(--accent)";

            try {
                const res = await fetch("/api/projects", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description: desc })
                });
                const data = await res.json();
                if (data.success) {
                    document.getElementById("newProjName").value = "";
                    document.getElementById("newProjDesc").value = "";
                    statusEl.textContent = "✅ Đã tạo thành công!";
                    statusEl.style.color = "var(--success)";
                    setTimeout(() => {
                        toggleNewProjectForm();
                        statusEl.textContent = "";
                    }, 1000);
                    fetchProjects();
                } else {
                    statusEl.textContent = "❌ Lỗi: " + extractErrorMsg(data.error);
                    statusEl.style.color = "var(--danger)";
                }
            } catch(e) {
                statusEl.textContent = "❌ Lỗi: " + e.message;
                statusEl.style.color = "var(--danger)";
            }
        }

        async function copyProjectToken(token) {
            try {
                await navigator.clipboard.writeText(token);
                alert("📋 Đã sao chép mã Token:\\n\\n" + token + "\\n\\nHãy dán mã này vào ô 'Mã Xác Thực Dự Án' trên máy Chrome!");
            } catch(e) {
                prompt("Hãy copy mã Token bên dưới:", token);
            }
        }

        async function regenerateProjectToken(id) {
            if (!confirm("⚠️ Bạn có chắc muốn tạo lại mã Token mới?\\nMáy đang dùng Token cũ sẽ bị ngắt kết nối cho đến khi nhập mã mới!")) return;
            try {
                const res = await fetch("/api/projects/regenerate-token", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: id })
                });
                const data = await res.json();
                if (data.success) {
                    alert("✅ Đã tạo mã Token mới:\\n" + data.project.token);
                    fetchProjects();
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error));
                }
            } catch(e) {
                alert("❌ Lỗi: " + e.message);
            }
        }

        async function deleteProject(id) {
            if (!confirm("🗑️ Bạn có chắc chắn muốn xóa dự án này?")) return;
            try {
                const res = await fetch("/api/projects/delete", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: id })
                });
                const data = await res.json();
                if (data.success) {
                    fetchProjects();
                } else {
                    alert("❌ Lỗi: " + extractErrorMsg(data.error));
                }
            } catch(e) {
                alert("❌ Lỗi: " + e.message);
            }
        }

        // =========================================================
        // STATUS & MANIFEST
        // =========================================================

        async function fetchStatus() {
            try {
                const res = await fetch("/api/bridge/status");
                const data = await res.json();

                const dot = document.getElementById("headerDot");
                const statusText = document.getElementById("headerStatusText");
                const sbUptime = document.getElementById("sidebarUptime");

                const nodes = data.nodes || [];
                const isOnline = nodes.length > 0;

                if (dot) dot.className = "dot " + (isOnline ? "online" : "");
                if (statusText) statusText.textContent = isOnline ? (nodes.length + " Máy Đang Online") : "Chờ Extension...";

                if (data.uptimeSec && sbUptime) {
                    const m = Math.floor(data.uptimeSec / 60);
                    const s = data.uptimeSec % 60;
                    sbUptime.textContent = "Uptime: " + m + "m " + s + "s";
                }
            } catch(e) {}
        }

        async function loadManifestConfig() {
            try {
                const res = await fetch("/api/bridge/manifest");
                const data = await res.json();
                if (data.name) document.getElementById("configNameInput").value = data.name;
                if (data.description) document.getElementById("configDescInput").value = data.description;
                if (data.version) document.getElementById("configVerInput").value = data.version;
            } catch(e) {}
        }

        async function saveManifestSettings() {
            const name = document.getElementById("configNameInput").value.trim();
            const description = document.getElementById("configDescInput").value.trim();
            const version = document.getElementById("configVerInput").value.trim();
            const statusEl = document.getElementById("manifestSaveStatus");
            statusEl.textContent = "⏳ Đang lưu...";
            statusEl.style.color = "var(--accent)";

            try {
                const res = await fetch("/api/bridge/manifest", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description, version })
                });
                const data = await res.json();
                if (data.success) {
                    statusEl.textContent = "✅ Đã lưu! Bấm Reload 🔄 trên chrome://extensions";
                    statusEl.style.color = "var(--success)";
                } else {
                    statusEl.textContent = "❌ Lỗi: " + extractErrorMsg(data.error);
                    statusEl.style.color = "var(--danger)";
                }
            } catch(e) {
                statusEl.textContent = "❌ Lỗi: " + e.message;
                statusEl.style.color = "var(--danger)";
            }
        }

        // =========================================================
        // CLIENT-SIDE ROUTER (URL HASH ROUTING & F5 PERSISTENCE)
        // =========================================================

        function parseHashRoute() {
            const raw = window.location.hash || "";
            if (!raw || raw === "#" || raw === "#/") {
                return null;
            }
            const clean = raw.replace(/^#\/?/, "");
            const parts = clean.split("/").filter(Boolean);
            if (parts.length === 0) return null;

            // 1. Hub routes: #/hub/projects, #/hub/api, #/hub/vps, #/hub/manifest, #/hub/system
            if (parts[0] === "hub") {
                const sub = parts[1] || "projects";
                return { type: "hub", routeKey: `hub-${sub}` };
            }

            // 2. Project routes:
            // #/project/:projId
            // #/project/:projId/machine
            // #/project/:projId/sub/:subId
            // #/project/:projId/sub/:subId/autopost
            // #/project/:projId/sub/:subId/api-doc
            if (parts[0] === "project" && parts[1]) {
                const projId = parts[1];
                if (parts[2] === "sub" && parts[3]) {
                    const subId = parts[3];
                    const menu = parts[4] || "account-info";
                    const subKey = menu.startsWith("sub-") ? menu : `sub-${menu}`;
                    return { type: "sub", projId: projId, subId: subId, subKey: subKey };
                } else {
                    const parentMenu = parts[2] || "subprojects";
                    const parentKey = parentMenu.startsWith("parent-") ? parentMenu : `parent-${parentMenu}`;
                    return { type: "parent", projId: projId, parentKey: parentKey };
                }
            }

            return null;
        }

        async function applyHashRoute() {
            const route = parseHashRoute();
            isRoutingFromHash = true;

            try {
                if (!route) {
                    // Khi mở URL gốc không có hash, luôn hiển thị Sảnh chính (Hub)
                    exitToHub(false);
                    return;
                }

                if (route.type === "hub") {
                    if (currentLevel !== "hub") {
                        exitToHub(false);
                    }
                    switchHubRoute(route.routeKey || "hub-projects", false);
                } else if (route.type === "parent") {
                    const proj = allProjects.find(p => p.id === route.projId);
                    if (!proj) {
                        exitToHub(true);
                        return;
                    }
                    enterParentProject(route.projId, route.parentKey || "parent-subprojects", false);
                } else if (route.type === "sub") {
                    const proj = allProjects.find(p => p.id === route.projId);
                    if (!proj) {
                        exitToHub(true);
                        return;
                    }
                    const sub = (proj.subProjects || []).find(s => s.id === route.subId);
                    if (!sub) {
                        enterParentProject(route.projId, "parent-subprojects", true);
                        return;
                    }

                    if (currentProjectId !== route.projId) {
                        currentProjectId = route.projId;
                        fetchParentProjectData(route.projId);
                    }
                    enterSubProject(route.subId, route.subKey || "sub-account-info", false);
                }
            } finally {
                isRoutingFromHash = false;
            }
        }

        // INITIALIZE APP
        window.addEventListener("DOMContentLoaded", async () => {
            await fetchProjects();
            fetchStatus();
            loadManifestConfig();

            // Thực thi Router dựa trên URL hash hiện tại (Hỗ trợ F5 lưu đúng trang)
            await applyHashRoute();

            // Lắng nghe sự kiện chuyển trang bằng Back / Forward hoặc thay đổi Hash
            window.addEventListener("popstate", () => {
                applyHashRoute();
            });
            window.addEventListener("hashchange", () => {
                applyHashRoute();
            });

            setInterval(() => {
                fetchStatus();
                if (currentLevel === "hub") {
                    fetchProjects();
                } else if (currentProjectId) {
                    fetchParentProjectData(currentProjectId);
                }
            }, 2500);
        });
    </script>

    <!-- MODAL: TẠO SEEDING MỚI CHO BÀI VIẾT ĐÃ ĐĂNG -->
    <div id="addSeedingModal" class="modal-overlay" onclick="if(event.target===this) closeAddSeedingModal()">
        <div class="modal-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--border-color); padding-bottom:10px;">
                <h3 style="font-size:16px; color:#38bdf8; margin:0; display:flex; align-items:center; gap:8px;" id="addSeedingModalTitle">
                    <span>💬</span> <span>Tạo Seeding Mới Cho Bài Viết</span>
                </h3>
                <button type="button" onclick="closeAddSeedingModal()" style="background:transparent; border:none; color:var(--text-muted); font-size:18px; cursor:pointer;">✕</button>
            </div>
            <p style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
                Nhập danh sách bình luận seeding để đẩy tương tác ngầm trực tiếp lên Facebook cho bài viết này qua Extension Bridge.
            </p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Danh Sách Bình Luận (Mỗi dòng 1 câu):</label>
                <div style="display:flex; gap:6px;">
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="insertModalSeedingPreset('inquiry')">Mẫu Hỏi Giá</button>
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#34d399;" onclick="insertModalSeedingPreset('feedback')">Mẫu Khen</button>
                </div>
            </div>
            <textarea id="addSeedingCommentsInput" rows="5" placeholder="Sản phẩm dùng tốt lắm shop!&#10;Tư vấn thêm cho mình mẫu này nhé&#10;Đã nhận hàng, đóng gói rất cẩn thận"></textarea>
            
            <div style="margin-bottom:14px;">
                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">❤️ Thả Cảm Xúc Bổ Sung (Auto-React):</label>
                <select id="addSeedingAutoReactInput" style="margin-top:4px;">
                    <option value="LIKE" selected>👍 LIKE (Thích)</option>
                    <option value="LOVE">❤️ LOVE (Yêu thích)</option>
                    <option value="CARE">🥰 CARE (Thương thương)</option>
                    <option value="HAHA">😆 HAHA (Cười)</option>
                    <option value="NONE">🚫 Không thả cảm xúc</option>
                </select>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:10px;">
                <button type="button" class="btn-sm" style="background:#334155;" onclick="closeAddSeedingModal()">Hủy Bỏ</button>
                <button type="button" class="btn-green" onclick="submitAddSeedingModal()">
                    <span>🚀</span> <span>GỬI LỆNH SEEDING NGAY</span>
                </button>
            </div>
        </div>
    </div>

    <!-- MODAL: ĐỔI GIỜ ĐĂNG / HẸN GIỜ CHO BÀI VIẾT -->
    <div id="editScheduleModal" class="modal-overlay" onclick="if(event.target===this) closeEditScheduleModal()">
        <div class="modal-box">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--border-color); padding-bottom:10px;">
                <h3 style="font-size:16px; color:#38bdf8; margin:0; display:flex; align-items:center; gap:8px;" id="editScheduleModalTitle">
                    <span>⏰</span> <span>Đổi Giờ Đăng Cho Bài Viết</span>
                </h3>
                <button type="button" onclick="closeEditScheduleModal()" style="background:transparent; border:none; color:var(--text-muted); font-size:18px; cursor:pointer;">✕</button>
            </div>
            <p style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">
                Chọn thời gian tự động xuất bản lên Facebook. Hệ thống chạy ngầm định kỳ kiểm tra hàng đợi và kích hoạt bài đăng khi đến giờ hẹn.
            </p>
            <div style="margin-bottom:14px;">
                <label style="font-size:11px; font-weight:700; color:#38bdf8; text-transform:uppercase; margin-bottom:6px; display:block;">⏰ Chọn Thời Gian Hẹn Giờ Mới:</label>
                <input type="datetime-local" id="modalEditScheduleInput" style="margin-bottom:10px; font-size:14px; font-weight:600;" />
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(15, 'modalEditScheduleInput')">+15 phút</button>
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(60, 'modalEditScheduleInput')">+1 giờ</button>
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="setSchedulePreset(180, 'modalEditScheduleInput')">+3 giờ</button>
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="setSchedulePresetNamed('tomorrow_morning', 'modalEditScheduleInput')">☀️ Sáng mai 8h</button>
                    <button type="button" class="btn-sm" style="background:#1e293b; color:#f59e0b;" onclick="setSchedulePresetNamed('tonight_evening', 'modalEditScheduleInput')">🌙 Tối nay 20h</button>
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:20px; flex-wrap:wrap; gap:10px;">
                <button type="button" class="btn-sm btn-danger" onclick="submitEditScheduleModal('clear')" title="Xóa lịch hẹn và đưa bài về trạng thái nháp">
                    ✕ Hủy Hẹn Giờ (Về Nháp)
                </button>
                <div style="display:flex; gap:8px;">
                    <button type="button" class="btn-sm" style="background:#334155;" onclick="closeEditScheduleModal()">Hủy Bỏ</button>
                    <button type="button" class="btn-sm btn-green" onclick="submitEditScheduleModal('now')">
                        <span>⚡</span> <span>ĐĂNG NGAY</span>
                    </button>
                    <button type="button" class="btn-sm btn-purple" onclick="submitEditScheduleModal('save')" style="background:linear-gradient(135deg,#0284c7,#2563eb);">
                        <span>💾</span> <span>LƯU GIỜ HẸN MỚI</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _get_request_project(self):
        auth_header = self.headers.get("Authorization", "")
        token = self.headers.get("X-Sync-Token") or (auth_header.replace("Bearer ", "").strip() if auth_header else "")
        if not token:
            return None
        return find_project_by_token(token)

    def _is_authenticated(self):
        return self._get_request_project() is not None

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Sync-Token, X-Project-Key, X-Worker-Id, X-Project-Token")

    def _send_json(self, status_code, data):
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _parse_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw_bytes = self.rfile.read(content_length)
            try:
                body = raw_bytes.decode("utf-8")
            except Exception:
                try:
                    body = raw_bytes.decode("cp1252", errors="replace")
                except Exception:
                    body = raw_bytes.decode("latin1", errors="replace")
            try:
                return json.loads(body)
            except Exception:
                return {}
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        pathname = parsed.path

        # 1. Web Controller Dashboard
        if pathname == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        # 2. Danh sách Dự Án Cha (Projects)
        if pathname == "/api/projects":
            projs = get_projects()
            now = int(time.time() * 1000)
            result = []
            for p in projs:
                pid = p.get("id")
                p_nodes = [
                    n for n in connected_nodes.values()
                    if n.get("projectId") == pid and (now - n.get("lastSeen", 0) < 15000)
                ]
                result.append({
                    **p,
                    "nodeCount": len(p_nodes),
                    "nodes": p_nodes
                })
            self._send_json(200, {"success": True, "projects": result})
            return

        # 3. Dữ liệu chi tiết của Dự Án Cha
        if pathname == "/api/bridge/project-latest":
            query_parts = parsed.query.split("&") if parsed.query else []
            query_params = {}
            for q in query_parts:
                if "=" in q:
                    k, v = q.split("=", 1)
                    query_params[k] = v

            proj_id = query_params.get("projectId")
            if not proj_id:
                self._send_json(400, {"success": False, "error": "Thiếu projectId"})
                return

            proj = find_project_by_id(proj_id)
            if not proj:
                self._send_json(404, {"success": False, "error": "Dự án không tồn tại"})
                return

            now = int(time.time() * 1000)
            p_nodes = [
                n for n in connected_nodes.values()
                if n.get("projectId") == proj_id and (now - n.get("lastSeen", 0) < 15000)
            ]
            p_logs = [l for l in live_logs if l.get("projectId") == proj_id]

            self._send_json(200, {
                "success": True,
                "project": proj,
                "nodes": p_nodes,
                "results": latest_project_results.get(proj_id, {}),
                "logs": p_logs[-50:]
            })
            return

        # 4. Token cấu hình máy chủ
        if pathname == "/api/bridge/get-token":
            cfg = get_server_config()
            self._send_json(200, {"authToken": cfg.get("authToken", "")})
            return

        # 5. Manifest config
        if pathname == "/api/bridge/manifest":
            info = read_manifest_info()
            proj = self._get_request_project()
            if proj:
                info["project"] = {
                    "id": proj["id"],
                    "name": proj["name"],
                    "token": proj["token"]
                }
            self._send_json(200, info)
            return

        # 6. Status hệ thống
        if pathname == "/api/bridge/status":
            now = int(time.time() * 1000)
            active_nodes = []
            for node_id, node in list(connected_nodes.items()):
                if now - node.get("lastSeen", 0) < 15000:
                    active_nodes.append(node)
            
            uptime_sec = int(time.time() - SERVER_START_TIME)
            projs = get_projects()
            self._send_json(200, {
                "nodes": active_nodes,
                "projectCount": len(projs),
                "pendingCount": len(pending_commands),
                "uptimeSec": uptime_sec,
                "recentLogs": live_logs[-40:]
            })
            return

        # 7. Fallback ping
        if pathname == "/api/accounts":
            self._send_json(200, {"success": True, "accounts": []})
            return

        # 8. API Kiểm tra trạng thái bài đăng theo ID hoặc query param (Public REST API)
        if pathname in ("/api/v1/posts/status", "/api/posts/status") or (pathname.startswith("/api/v1/posts/") and not pathname.startswith(("/api/v1/posts/status", "/api/v1/posts/publish", "/api/v1/posts/seeding"))):
            post_id = None
            if pathname.startswith("/api/v1/posts/") and not pathname.startswith(("/api/v1/posts/status", "/api/v1/posts/publish", "/api/v1/posts/seeding")):
                post_id = pathname[len("/api/v1/posts/"):].strip("/")
            else:
                query_parts = parsed.query.split("&") if parsed.query else []
                for q in query_parts:
                    if q.startswith("postId="):
                        post_id = q.split("=", 1)[1]
                        break

            if not post_id:
                self._send_json(400, {"success": False, "error": {"code": "MISSING_POST_ID", "message": "Thiếu tham số postId"}})
                return

            all_projs = get_projects()
            found_post = None
            found_proj = None
            found_sub = None
            for p in all_projs:
                for s in p.get("subProjects", []):
                    for post_item in s.get("postQueue", []):
                        if post_item.get("id") == post_id:
                            found_post = post_item
                            found_proj = p
                            found_sub = s
                            break
                    if found_post: break
                if found_post: break

            if not found_post:
                self._send_json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": f"Không tìm thấy bài viết có ID '{post_id}'"}})
                return

            resp_data = {
                **found_post,
                "account": {
                    "projectId": found_proj.get("id") if found_proj else "",
                    "projectName": found_proj.get("name") if found_proj else "",
                    "subProjectId": found_sub.get("id") if found_sub else "",
                    "subProjectName": found_sub.get("name") if found_sub else "",
                    "c_user": found_sub.get("c_user") if found_sub else "",
                    "fbName": found_sub.get("fbName") if found_sub else ""
                }
            }
            self._send_json(200, {
                "success": True,
                "data": resp_data,
                "post": resp_data,
                "postId": found_post.get("id"),
                "status": found_post.get("status"),
                "progressStep": found_post.get("progressStep", ""),
                "shareToFeed": found_post.get("shareToFeed", True),
                "shareToStory": found_post.get("shareToStory", found_post.get("shareToFeed", True)),
                "shareToStorySuccess": found_post.get("shareToStorySuccess", False),
                "fbPostId": found_post.get("fbPostId", ""),
                "fbPostUrl": found_post.get("fbPostUrl", ""),
                "fbFeedbackId": found_post.get("fbFeedbackId", ""),
                "seedingIds": found_post.get("seedingIds", []),
                "seedingDetails": found_post.get("seedingDetails", []),
                "publishedAt": found_post.get("publishedAt"),
                "publishedAtStr": found_post.get("publishedAtStr", "")
            })
            return

        # 9. API Lấy danh sách bài đăng & hàng đợi (Public REST API)
        if pathname in ("/api/v1/posts", "/api/posts"):
            token = self.headers.get("X-Project-Token") or self.headers.get("X-Sync-Token")
            if not token:
                auth = self.headers.get("Authorization", "")
                if auth.lower().startswith("bearer "):
                    token = auth[7:].strip()
            
            query_parts = parsed.query.split("&") if parsed.query else []
            query_params = {}
            for q in query_parts:
                if "=" in q:
                    k, v = q.split("=", 1)
                    query_params[k] = v
            if not token:
                token = query_params.get("token")
            
            target_proj = find_project_by_token(token) if token else None
            proj_id_query = query_params.get("projectId")
            if not target_proj and proj_id_query:
                all_p = get_projects()
                for p in all_p:
                    if p.get("id") == proj_id_query:
                        target_proj = p
                        break

            all_projs = [target_proj] if target_proj else get_projects()

            status_filter = query_params.get("status")
            post_type_filter = query_params.get("postType")
            sub_id_filter = query_params.get("subProjectId")
            limit = int(query_params.get("limit", 50))
            offset = int(query_params.get("offset", 0))

            all_posts = []
            for p in all_projs:
                for s in p.get("subProjects", []):
                    if sub_id_filter and s.get("id") != sub_id_filter:
                        continue
                    for post_item in s.get("postQueue", []):
                        if status_filter and status_filter != "all" and post_item.get("status") != status_filter:
                            continue
                        if post_type_filter and post_type_filter != "all" and post_item.get("postType") != post_type_filter:
                            continue
                        post_summary = dict(post_item)
                        if "mediaData" in post_summary and isinstance(post_summary["mediaData"], dict):
                            m_copy = dict(post_summary["mediaData"])
                            m_copy.pop("base64", None)
                            m_copy["hasBase64"] = bool(post_summary["mediaData"].get("base64"))
                            post_summary["mediaData"] = m_copy

                        all_posts.append({
                            **post_summary,
                            "projectId": p.get("id"),
                            "projectName": p.get("name"),
                            "subProjectId": s.get("id"),
                            "subProjectName": s.get("name"),
                            "c_user": s.get("c_user"),
                            "fbName": s.get("fbName")
                        })

            all_posts.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
            total = len(all_posts)
            paginated = all_posts[offset:offset+limit]

            self._send_json(200, {
                "success": True,
                "data": paginated,
                "posts": paginated,
                "count": len(paginated),
                "total": total,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "hasMore": (offset + limit) < total
                }
            })
            return

        # 10. API Danh sách tài khoản & dự án để tích hợp
        if pathname in ("/api/v1/accounts", "/api/v1/projects-info"):
            all_projs = get_projects()
            accounts = []
            for p in all_projs:
                for s in p.get("subProjects", []):
                    accounts.append({
                        "projectId": p.get("id"),
                        "projectName": p.get("name"),
                        "token": p.get("token"),
                        "subProjectId": s.get("id"),
                        "subProjectName": s.get("name"),
                        "type": s.get("type"),
                        "c_user": s.get("c_user"),
                        "fbName": s.get("fbName"),
                        "status": s.get("status")
                    })
            self._send_json(200, {"success": True, "accounts": accounts})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        pathname = parsed.path
        body = self._parse_body()

        # 1. Tạo dự án cha mới
        if pathname == "/api/projects":
            name = body.get("name", "").strip()
            description = body.get("description", "").strip()
            if not name:
                self._send_json(400, {"success": False, "error": "Vui lòng nhập tên dự án!"})
                return
            projs = get_projects()
            new_id = f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            new_token = generate_project_token()
            new_proj = {
                "id": new_id,
                "name": name,
                "description": description,
                "token": new_token,
                "createdAt": int(time.time() * 1000),
                "subProjects": [
                    {
                        "id": f"sub_fb_{int(time.time())}_init",
                        "name": "Dự Án Facebook 01",
                        "type": "facebook",
                        "description": "Thư mục quản lý cookie & tài khoản Facebook",
                        "c_user": "",
                        "fbName": "",
                        "avatar": "",
                        "profileUrl": "",
                        "cookieStr": "",
                        "cookies": [],
                        "eaagToken": "",
                        "dtsg": "",
                        "status": "Chưa kiểm tra",
                        "lastExtracted": 0,
                        "createdAt": int(time.time() * 1000)
                    }
                ]
            }
            projs.append(new_proj)
            save_projects(projs)
            push_log(f"Đã tạo dự án cha mới: '{name}' | Token: {new_token}", "success", project_id=new_id)
            self._send_json(200, {"success": True, "project": new_proj})
            return

        # 2. Tạo thư mục / dự án con (Sub-Project)
        if pathname == "/api/subprojects":
            proj_id = body.get("projectId")
            name = body.get("name", "").strip()
            description = body.get("description", "").strip()
            sub_type = body.get("type", "facebook")
            sub_purpose = body.get("purpose", "scraper")
            source_domain = body.get("sourceDomain", "")
            source_url = body.get("sourceUrl", "")

            if not proj_id or not name:
                self._send_json(400, {"success": False, "error": "Vui lòng nhập tên thư mục / dự án con!"})
                return

            projs = get_projects()
            target_proj = None
            for p in projs:
                if p.get("id") == proj_id:
                    target_proj = p
                    break

            if not target_proj:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án cha"})
                return

            prefix = "fb" if sub_type == "facebook" else (sub_type if sub_type in ("tiktok", "flow", "x", "instagram", "threads") else "custom")
            new_sub_id = f"sub_{prefix}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            new_sub = {
                "id": new_sub_id,
                "name": name,
                "type": sub_type,
                "purpose": sub_purpose,
                "sourceDomain": source_domain,
                "sourceUrl": source_url,
                "description": description,
                "scrapedData": [],
                "postQueue": [],
                "c_user": "",
                "fbName": "",
                "avatar": "",
                "profileUrl": "",
                "cookieStr": "",
                "cookies": [],
                "eaagToken": "",
                "dtsg": "",
                "status": "Chưa kiểm tra",
                "lastExtracted": 0,
                "createdAt": int(time.time() * 1000)
            }

            if "subProjects" not in target_proj:
                target_proj["subProjects"] = []
            target_proj["subProjects"].append(new_sub)
            save_projects(projs)

            push_log(f"Tạo thư mục dự án con '{name}' [Mục đích: {sub_purpose} | Nguồn: {sub_type}] trong '{target_proj['name']}'", "success", project_id=proj_id, subproject_id=new_sub_id)
            self._send_json(200, {"success": True, "subProject": new_sub})
            return

        # 3. Xóa thư mục / dự án con
        if pathname == "/api/subprojects/delete":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            projs = get_projects()
            target_proj = None
            for p in projs:
                if p.get("id") == proj_id:
                    target_proj = p
                    break

            if not target_proj:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án cha"})
                return

            subs = target_proj.get("subProjects", [])
            filtered_subs = [s for s in subs if s.get("id") != sub_id]
            target_proj["subProjects"] = filtered_subs
            save_projects(projs)

            push_log(f"Đã xóa thư mục dự án con '{sub_id}'", "warn", project_id=proj_id)
            self._send_json(200, {"success": True})
            return

        # Xóa trắng dữ liệu tài khoản & Cookie cũ để cập nhật mới
        if pathname == "/api/subprojects/clear-account":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            projs = get_projects()
            target_proj = None
            for p in projs:
                if p.get("id") == proj_id:
                    target_proj = p
                    break

            if not target_proj:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án cha"})
                return

            target_sub = None
            for s in target_proj.get("subProjects", []):
                if s.get("id") == sub_id:
                    target_sub = s
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            target_sub["c_user"] = ""
            target_sub["fbName"] = ""
            target_sub["avatar"] = ""
            target_sub["profileUrl"] = ""
            target_sub["cookieStr"] = ""
            target_sub["cookies"] = []
            target_sub["eaagToken"] = ""
            target_sub["dtsg"] = ""
            target_sub["status"] = "Chưa kiểm tra"
            target_sub["lastExtracted"] = 0
            save_projects(projs)

            push_log(f"Đã xóa trắng dữ liệu tài khoản & cookie cũ của '{target_sub['name']}' để chuẩn bị quét mới", "warn", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True, "subProject": target_sub})
            return

        # Cập nhật Cookie thủ công từ Bộ Giải Mã cho Sub-Project
        if pathname == "/api/subprojects/update-cookies":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            cookies = body.get("cookies", [])
            cookie_str = body.get("cookieStr", "").strip()
            c_user = body.get("c_user", "").strip()

            if not proj_id or not sub_id:
                self._send_json(400, {"success": False, "error": "Thiếu projectId hoặc subProjectId"})
                return

            projs = get_projects()
            target_proj = None
            for p in projs:
                if p.get("id") == proj_id:
                    target_proj = p
                    break

            if not target_proj:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án cha"})
                return

            target_sub = None
            for s in target_proj.get("subProjects", []):
                if s.get("id") == sub_id:
                    target_sub = s
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            # Nếu c_user chưa có, thử tìm c_user trong mảng cookies
            if not c_user and cookies:
                for c in cookies:
                    if c.get("name") == "c_user":
                        c_user = c.get("value", "")
                        break

            if cookies: target_sub["cookies"] = cookies
            if cookie_str: target_sub["cookieStr"] = cookie_str
            if c_user: target_sub["c_user"] = c_user

            # Tự động quét Tên & Avatar nếu là Facebook và có UID/Cookie
            if target_sub.get("type", "facebook") == "facebook" and (c_user or cookie_str):
                try:
                    res_profile = resolve_fb_profile_data(cookie_str, c_user)
                    if res_profile.get("name"):
                        target_sub["fbName"] = res_profile["name"]
                    if res_profile.get("avatar"):
                        target_sub["avatar"] = res_profile["avatar"]
                    if res_profile.get("profileUrl"):
                        target_sub["profileUrl"] = res_profile["profileUrl"]
                except Exception as e:
                    print(f"[Profile Resolve Error] {e}")

            target_sub["status"] = "LIVE (Đã cập nhật)" if c_user else "Đã nạp cookie"
            target_sub["lastExtracted"] = int(time.time() * 1000)
            save_projects(projs)

            push_log(f"Cập nhật {len(cookies)} cookie thủ công cho dự án con '{target_sub['name']}' [UID: {c_user}]", "success", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True, "subProject": target_sub})
            return

        # Lưu dữ liệu cào được
        if pathname == "/api/subprojects/save-scraped":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            items = body.get("items", [])
            append = body.get("append", True)

            projs = get_projects()
            target_sub = None
            for p in projs:
                if p.get("id") == proj_id:
                    for s in p.get("subProjects", []):
                        if s.get("id") == sub_id:
                            target_sub = s
                            break
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            if "scrapedData" not in target_sub:
                target_sub["scrapedData"] = []

            if append:
                existing_urls = {x.get("url") for x in target_sub["scrapedData"] if x.get("url")}
                for item in items:
                    if not item.get("url") or item.get("url") not in existing_urls:
                        target_sub["scrapedData"].append(item)
                        if item.get("url"):
                            existing_urls.add(item.get("url"))
            else:
                target_sub["scrapedData"] = items

            save_projects(projs)
            push_log(f"Đã lưu {len(items)} mục dữ liệu cào vào '{target_sub['name']}'", "success", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True, "totalScraped": len(target_sub["scrapedData"])})
            return

        # Xóa dữ liệu cào
        if pathname == "/api/subprojects/clear-scraped":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")

            projs = get_projects()
            target_sub = None
            for p in projs:
                if p.get("id") == proj_id:
                    for s in p.get("subProjects", []):
                        if s.get("id") == sub_id:
                            target_sub = s
                            break
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            target_sub["scrapedData"] = []
            save_projects(projs)
            push_log(f"Đã xóa toàn bộ dữ liệu cào của '{target_sub['name']}'", "warn", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True})
            return

        # =====================================================================
        # GOOGLE FLOW: API TẠO ẢNH AI
        # POST /api/v1/flow/generate-image
        # =====================================================================
        if pathname in ("/api/v1/flow/generate-image",):
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except:
                self._send_json(400, {"success": False, "error": "Invalid JSON"})
                return

            proj_id = body.get("projectId", "")
            sub_id = body.get("subProjectId", "")
            prompt = body.get("prompt", "").strip()
            model = body.get("model", "HARBOR_SEAL")
            image_count = body.get("imageCount", 4)
            aspect_ratio = body.get("aspectRatio", "3:4")
            run_now = body.get("runNow", True)

            if not proj_id or not sub_id:
                self._send_json(400, {"success": False, "error": "Missing projectId or subProjectId"})
                return
            if not prompt:
                self._send_json(400, {"success": False, "error": "Missing prompt"})
                return

            projs = load_projects()
            proj = next((p for p in projs if p["id"] == proj_id), None)
            if not proj:
                self._send_json(404, {"success": False, "error": "Project not found"})
                return
            sub = next((s for s in proj.get("subProjects", []) if s["id"] == sub_id), None)
            if not sub:
                self._send_json(404, {"success": False, "error": "SubProject not found"})
                return

            import time as _time
            image_request_id = f"flowimg_{int(_time.time() * 1000)}_{random.randint(1000, 9999)}"
            image_item = {
                "id": image_request_id,
                "prompt": prompt,
                "model": model,
                "imageCount": image_count,
                "aspectRatio": aspect_ratio,
                "status": "pending" if run_now else "queued",
                "images": [],
                "createdAt": int(_time.time() * 1000),
                "runNow": run_now
            }

            if "imageQueue" not in sub:
                sub["imageQueue"] = []
            sub["imageQueue"].append(image_item)
            save_projects(projs)

            push_log(f"🎨 Yêu cầu tạo ảnh AI Flow: '{prompt[:60]}...' (Model: {model}, Count: {image_count})", "info", project_id=proj_id, subproject_id=sub_id)

            # Nếu runNow, gửi lệnh tới Extension qua pendingCommands
            if run_now:
                cmd = {
                    "action": "FLOW_GENERATE_IMAGE",
                    "prompt": prompt,
                    "model": model,
                    "imageCount": image_count,
                    "aspectRatio": aspect_ratio,
                    "imageRequestId": image_request_id,
                    "projectId": proj_id,
                    "subProjectId": sub_id
                }
                if "pendingCommands" not in sub:
                    sub["pendingCommands"] = []
                sub["pendingCommands"].append(cmd)
                save_projects(projs)

            self._send_json(200, {"success": True, "imageRequestId": image_request_id})
            return

        # =====================================================================
        # PUBLIC REST API & DASHBOARD: TẠO HOẶC LÊN LỊCH BÀI VIẾT
        # POST /api/v1/posts, /api/posts, /api/v1/posts/publish, /api/subprojects/add-post
        # =====================================================================
        if pathname in ("/api/v1/posts", "/api/posts", "/api/v1/posts/publish", "/api/posts/publish", "/api/publish", "/api/subprojects/add-post"):
            auth_header = self.headers.get("Authorization", "")
            token = self.headers.get("X-Project-Token") or self.headers.get("X-Sync-Token")
            if not token and auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
            if not token:
                token = body.get("token") or body.get("projectToken")

            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId") or body.get("targetSubProjectId")
            post_data = body.get("post") if (isinstance(body.get("post"), dict) and body.get("post")) else body

            if "runNow" in body:
                run_now = bool(body.get("runNow"))
            elif "runNow" in post_data:
                run_now = bool(post_data.get("runNow"))
            else:
                run_now = False if pathname == "/api/subprojects/add-post" else True

            source = "api" if ("/api/v1/" in pathname or "/api/posts" in pathname or "/api/publish" in pathname) else "dashboard"
            status_code, res_payload = create_post_entry(
                proj_id=proj_id,
                sub_id=sub_id,
                post_data=post_data,
                run_now=run_now,
                source=source,
                token=token
            )
            self._send_json(status_code, res_payload)
            return

        # Kích hoạt đăng ngay bài viết từ REST API: POST /api/v1/posts/<id>/run
        if pathname.startswith("/api/v1/posts/") and pathname.endswith("/run"):
            parts = pathname.strip("/").split("/")
            post_id = parts[-2]
            all_projs = get_projects()
            found_post = None
            found_proj = None
            found_sub = None
            for p in all_projs:
                for s in p.get("subProjects", []):
                    for post_item in s.get("postQueue", []):
                        if post_item.get("id") == post_id:
                            found_post = post_item
                            found_proj = p
                            found_sub = s
                            break
                    if found_post: break
                if found_post: break

            if not found_post:
                self._send_json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": f"Không tìm thấy bài viết '{post_id}'"}})
                return

            found_post["status"] = "in_progress"
            found_post["progressStep"] = "Đang chuyển lệnh đăng bài sang Extension..."
            found_post["lastError"] = ""
            save_projects(all_projs)

            cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            cmd = {
                "id": cmd_id,
                "action": "POST_STORY",
                "targetProjectId": found_proj["id"],
                "targetSubProjectId": found_sub["id"],
                "targetNodeId": "*",
                "post": found_post
            }
            pending_commands.append(cmd)
            recent_issued_commands[cmd_id] = cmd
            push_log(f"Đã kích hoạt đăng ngay bài viết '{post_id}' cho '{found_sub['name']}'", "step", project_id=found_proj["id"], subproject_id=found_sub["id"])
            self._send_json(200, {
                "success": True,
                "message": "Đã phát lệnh đăng ngay sang Extension",
                "cmdId": cmd_id,
                "data": found_post,
                "post": found_post
            })
            return

        # Cập nhật giờ hẹn đăng từ REST API: POST /api/v1/posts/<id>/schedule
        if pathname.startswith("/api/v1/posts/") and pathname.endswith("/schedule"):
            parts = pathname.strip("/").split("/")
            post_id = parts[-2]
            sched_val = body.get("scheduledAt") or body.get("scheduledTime")
            all_projs = get_projects()
            found_post = None
            found_proj = None
            found_sub = None
            for p in all_projs:
                for s in p.get("subProjects", []):
                    for post_item in s.get("postQueue", []):
                        if post_item.get("id") == post_id:
                            found_post = post_item
                            found_proj = p
                            found_sub = s
                            break
                    if found_post: break
                if found_post: break

            if not found_post:
                self._send_json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": f"Không tìm thấy bài viết '{post_id}'"}})
                return

            if not sched_val:
                found_post["status"] = "pending"
                found_post["scheduledTime"] = 0
                found_post["scheduledAt"] = ""
                found_post["progressStep"] = "Đã hủy hẹn giờ, lưu trong hàng đợi"
                push_log(f"Đã hủy giờ hẹn đăng bài '{post_id}'", "step", project_id=found_proj["id"], subproject_id=found_sub["id"])
            else:
                sched_ms = parse_scheduled_time(sched_val)
                now_ms = int(time.time() * 1000)
                if not sched_ms or sched_ms <= now_ms:
                    self._send_json(422, {"success": False, "error": {"code": "INVALID_SCHEDULE_TIME", "message": "Thời gian đặt lịch phải ở thời điểm tương lai!"}})
                    return
                found_post["status"] = "scheduled"
                found_post["scheduledTime"] = sched_ms
                found_post["scheduledAt"] = datetime.fromtimestamp(sched_ms / 1000.0, tz=timezone.utc).isoformat()
                formatted = format_scheduled_time(sched_ms)
                found_post["progressStep"] = f"⏳ Đã lên lịch đăng lúc {formatted}"
                push_log(f"⏰ Đã cập nhật lịch đăng bài '{post_id}' sang {formatted}", "step", project_id=found_proj["id"], subproject_id=found_sub["id"])

            save_projects(all_projs)
            self._send_json(200, {
                "success": True,
                "message": "Cập nhật lịch đăng bài thành công",
                "data": found_post,
                "post": found_post
            })
            return

        # =====================================================================
        # PUBLIC REST API: BẮN SEEDING CHO BÀI VIẾT (CURL, BOT, WEBHOOK)
        # =====================================================================
        if pathname in ("/api/v1/posts/seeding", "/api/posts/seeding"):
            post_id = body.get("postId")
            raw_comments = body.get("comments") or body.get("seedingComments", [])
            auto_react = str(body.get("autoReactType") or "LIKE").upper()
            
            comments = []
            if isinstance(raw_comments, str):
                comments = [c.strip() for c in raw_comments.split("\n") if c.strip()]
            elif isinstance(raw_comments, list):
                comments = [str(c).strip() for c in raw_comments if str(c).strip()]

            if not comments:
                self._send_json(400, {"success": False, "error": "Thiếu danh sách bình luận seeding ('comments')!"})
                return

            all_projs = get_projects()
            found_post = None
            found_proj = None
            found_sub = None
            for p in all_projs:
                for s in p.get("subProjects", []):
                    for p_item in s.get("postQueue", []):
                        if p_item.get("id") == post_id or (p_item.get("fbPostId") and p_item.get("fbPostId") == str(post_id)):
                            found_post = p_item
                            found_proj = p
                            found_sub = s
                            break
                    if found_post: break
                if found_post: break

            if not found_post:
                self._send_json(404, {"success": False, "error": f"Không tìm thấy bài viết '{post_id}' để seeding."})
                return

            if not found_post.get("fbPostId"):
                self._send_json(400, {"success": False, "error": "Bài viết này chưa có fbPostId (chưa đăng xong lên Facebook) nên không thể seeding."})
                return

            cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            cmd = {
                "id": cmd_id,
                "action": "SEEDING",
                "targetProjectId": found_proj["id"],
                "targetSubProjectId": found_sub["id"],
                "targetNodeId": "*",
                "postId": found_post["id"],
                "fbPostId": found_post.get("fbPostId"),
                "fbFeedbackId": found_post.get("fbFeedbackId"),
                "comments": comments,
                "autoReactType": auto_react
            }
            pending_commands.append(cmd)
            recent_issued_commands[cmd_id] = cmd
            push_log(f"API: Đã phát lệnh seeding {len(comments)} câu cho bài '{found_post['id']}'", "step", project_id=found_proj["id"], subproject_id=found_sub["id"])
            self._send_json(200, {
                "success": True,
                "message": f"Đã phát lệnh seeding {len(comments)} câu sang Extension!",
                "cmdId": cmd_id,
                "postId": found_post["id"],
                "fbPostId": found_post.get("fbPostId")
            })
            return

        # Đăng ngay bài viết đã có sẵn trong hàng đợi
        if pathname == "/api/subprojects/run-post":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            post_id = body.get("postId")

            projs = get_projects()
            target_sub = None
            for p in projs:
                if p.get("id") == proj_id:
                    for s in p.get("subProjects", []):
                        if s.get("id") == sub_id:
                            target_sub = s
                            break
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            post_item = None
            for p_item in target_sub.get("postQueue", []):
                if p_item.get("id") == post_id:
                    post_item = p_item
                    break

            if not post_item:
                self._send_json(404, {"success": False, "error": "Không tìm thấy bài viết"})
                return

            post_item["status"] = "in_progress"
            post_item["progressStep"] = "Đang chuyển lệnh đăng bài sang Extension..."
            post_item["lastError"] = ""
            save_projects(projs)

            cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            cmd = {
                "id": cmd_id,
                "action": "POST_STORY",
                "targetProjectId": proj_id,
                "targetSubProjectId": sub_id,
                "targetNodeId": "*",
                "post": post_item
            }
            pending_commands.append(cmd)
            recent_issued_commands[cmd_id] = cmd
            push_log(f"Đã phát lệnh đăng lại bài viết '{post_id}' cho '{target_sub['name']}'", "step", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True, "cmdId": cmd_id, "post": post_item})
            return

        # Tạo thêm bình luận seeding cho bài viết
        if pathname == "/api/subprojects/add-seeding":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            post_id = body.get("postId")
            comments = body.get("comments", [])
            auto_react = body.get("autoReactType", "LIKE")

            projs = get_projects()
            target_sub = None
            for p in projs:
                if p.get("id") == proj_id:
                    for s in p.get("subProjects", []):
                        if s.get("id") == sub_id:
                            target_sub = s
                            break
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            post_item = None
            for p_item in target_sub.get("postQueue", []):
                if p_item.get("id") == post_id:
                    post_item = p_item
                    break

            if not post_item:
                self._send_json(404, {"success": False, "error": "Không tìm thấy bài viết"})
                return

            if "seedingComments" not in post_item or not isinstance(post_item["seedingComments"], list):
                post_item["seedingComments"] = []
            post_item["seedingComments"].extend(comments)
            post_item["progressStep"] = f"Đang gửi {len(comments)} bình luận seeding..."
            save_projects(projs)

            cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            cmd = {
                "id": cmd_id,
                "action": "SEEDING",
                "targetProjectId": proj_id,
                "targetSubProjectId": sub_id,
                "targetNodeId": "*",
                "postId": post_id,
                "fbPostId": post_item.get("fbPostId", ""),
                "comments": comments,
                "autoReactType": auto_react
            }
            pending_commands.append(cmd)
            recent_issued_commands[cmd_id] = cmd
            push_log(f"Đã phát lệnh seeding thêm {len(comments)} câu cho bài '{post_id}' của '{target_sub['name']}'", "step", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True, "cmdId": cmd_id})
            return

        # Cập nhật tiến độ đăng bài từ Extension Bridge
        if pathname == "/api/bridge/progress":
            proj_id = body.get("targetProjectId")
            sub_id = body.get("targetSubProjectId")
            post_id = body.get("postId")
            step = body.get("step", "")

            if proj_id and sub_id and post_id:
                projs = get_projects()
                for p in projs:
                    if p.get("id") == proj_id:
                        for s in p.get("subProjects", []):
                            if s.get("id") == sub_id:
                                for post_item in s.get("postQueue", []):
                                    if post_item.get("id") == post_id:
                                        post_item["progressStep"] = step
                                        post_item["status"] = "in_progress"
                                        save_projects(projs)
                                        break
                                break
                        break
            self._send_json(200, {"success": True})
            return

        # Xóa bài đăng khỏi hàng đợi
        if pathname == "/api/subprojects/delete-post":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            post_id = body.get("postId")

            projs = get_projects()
            target_sub = None
            for p in projs:
                if p.get("id") == proj_id:
                    for s in p.get("subProjects", []):
                        if s.get("id") == sub_id:
                            target_sub = s
                            break
                    break

            if not target_sub:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án con"})
                return

            if "postQueue" in target_sub:
                target_sub["postQueue"] = [x for x in target_sub["postQueue"] if x.get("id") != post_id]
                save_projects(projs)

            push_log(f"Đã xóa bài viết '{post_id}' khỏi hàng đợi của '{target_sub['name']}'", "warn", project_id=proj_id, subproject_id=sub_id)
            self._send_json(200, {"success": True})
            return

        # 4. Tạo lại token cho dự án cha
        if pathname == "/api/projects/regenerate-token":
            proj_id = body.get("projectId")
            projs = get_projects()
            target = None
            for p in projs:
                if p.get("id") == proj_id:
                    target = p
                    break
            if not target:
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án"})
                return
            new_token = generate_project_token()
            target["token"] = new_token
            save_projects(projs)
            push_log(f"Đã tạo lại mã Token cho '{target['name']}': {new_token}", "warn", project_id=proj_id)
            self._send_json(200, {"success": True, "project": target})
            return

        # 5. Xóa dự án cha
        if pathname == "/api/projects/delete":
            proj_id = body.get("projectId")
            projs = get_projects()
            if len(projs) <= 1:
                self._send_json(400, {"success": False, "error": "Hệ thống cần tối thiểu 1 dự án!"})
                return
            filtered = [p for p in projs if p.get("id") != proj_id]
            if len(filtered) == len(projs):
                self._send_json(404, {"success": False, "error": "Không tìm thấy dự án"})
                return
            save_projects(filtered)
            for nid, node in list(connected_nodes.items()):
                if node.get("projectId") == proj_id:
                    del connected_nodes[nid]
            push_log(f"Đã xóa dự án: {proj_id}", "warn")
            self._send_json(200, {"success": True})
            return

        # 6. Lưu manifest
        if pathname == "/api/bridge/manifest":
            name = body.get("name", "")
            description = body.get("description", "")
            version = body.get("version", "")
            success, msg = update_manifest_info(name, description, version)
            self._send_json(200, {"success": success, "message": msg})
            return

        # 7. Heartbeat
        if pathname == "/api/bridge/heartbeat":
            proj = self._get_request_project()
            if not proj:
                auth_header = self.headers.get("Authorization", "")
                token = self.headers.get("X-Sync-Token") or (auth_header.replace("Bearer ", "").strip() if auth_header else "")
                push_log(f"⚠️ Từ chối kết nối máy '{body.get('nodeName', 'Unknown')}': Token '{token}' không hợp lệ!", "err")
                self._send_json(401, {
                    "success": False,
                    "error": "Mã Token không hợp lệ! Hãy sao chép đúng mã Token từ mục Quản Lý Dự Án."
                })
                return

            node_id = body.get("nodeId")
            if node_id:
                connected_nodes[node_id] = {
                    "nodeId": node_id,
                    "nodeName": body.get("nodeName", "My Chrome Node"),
                    "projectId": proj["id"],
                    "projectName": proj["name"],
                    "status": "online",
                    "tabCount": body.get("tabCount", 0),
                    "activeTab": body.get("activeTab"),
                    "browserFbUid": body.get("browserFbUid", ""),
                    "lastSeen": int(time.time() * 1000)
                }

            has_pending = any(
                (c.get("targetNodeId") == node_id or c.get("targetNodeId") == "*") and
                (not c.get("targetProjectId") or c.get("targetProjectId") == proj["id"])
                for c in pending_commands
            )

            reload_req = False
            if node_id and (node_id in pending_extension_reloads or "*" in pending_extension_reloads):
                reload_req = True
                pending_extension_reloads.discard(node_id)
                pending_extension_reloads.discard("*")

            self._send_json(200, {
                "success": True,
                "projectId": proj["id"],
                "projectName": proj["name"],
                "hasPendingCommands": has_pending,
                "reloadExtension": reload_req
            })
            return

        # Reload Extension Nodes
        if pathname == "/api/bridge/reload-nodes":
            node_id = body.get("nodeId") or "*"
            pending_extension_reloads.add(node_id)
            push_log(f"Đã kích hoạt cờ yêu cầu Extension nạp lại mã mới nhất (node: {node_id})", "step")
            self._send_json(200, {"success": True, "message": "Đã gửi yêu cầu reload tới Extension"})
            return

        # 8. Poll
        if pathname == "/api/bridge/poll":
            node_id = body.get("nodeId")
            node = connected_nodes.get(node_id, {})
            node_proj_id = node.get("projectId")

            matched_idx = -1
            for idx, c in enumerate(pending_commands):
                t_node = c.get("targetNodeId")
                t_proj = c.get("targetProjectId")
                node_match = (not t_node) or (t_node == "*") or (t_node == node_id)
                proj_match = (not t_proj) or (t_proj == "*") or (t_proj == node_proj_id)
                if node_match and proj_match:
                    matched_idx = idx
                    break

            if matched_idx >= 0:
                cmd = pending_commands.pop(matched_idx)
                print(f"[Python Server] Gửi lệnh '{cmd.get('action')}' tới {node_id}")
                self._send_json(200, {"success": True, "command": cmd})
            else:
                self._send_json(200, {"success": True, "command": None})
            return

        # 9. Result (Xử lý toàn bộ thông tin Facebook)
        if pathname == "/api/bridge/result":
            action = body.get("action")
            success = body.get("success", False)
            node_id = body.get("nodeId")
            cmd_id = body.get("commandId")

            orig_cmd = recent_issued_commands.get(cmd_id, {})
            target_sub_id = body.get("targetSubProjectId") or orig_cmd.get("targetSubProjectId")

            proj = self._get_request_project()
            proj_id = body.get("targetProjectId") or (proj["id"] if proj else None) or orig_cmd.get("targetProjectId") or (connected_nodes.get(node_id, {}).get("projectId") if node_id else None)

            cookies = body.get("cookies", [])
            cookie_str = body.get("cookieStr", "")
            uid = body.get("uid", "")
            name = body.get("name", "")
            avatar = body.get("avatar", "")
            profile_url = body.get("profileUrl", "")
            token = body.get("token", "")
            dtsg = body.get("dtsg", "")

            # If uid not explicitly passed, find c_user in cookies
            c_user = uid
            if not c_user and cookies:
                for c in cookies:
                    if c.get("name") == "c_user":
                        c_user = c.get("value", "")
                        break

            # Tự động trích xuất Tên thật và Avatar trực tiếp nếu Extension trả về tên chung chung hoặc thiếu avatar
            is_placeholder_name = (not name) or ("trang cá nhân" in name.lower()) or ("your profile" in name.lower()) or (name.lower() == "facebook")
            is_placeholder_avatar = (not avatar) or ("graph.facebook.com" in avatar)
            if (is_placeholder_name or is_placeholder_avatar) and (cookie_str or c_user):
                res_profile = resolve_fb_profile_data(cookie_str, c_user)
                if res_profile.get("name") and is_placeholder_name:
                    name = res_profile["name"]
                if res_profile.get("avatar") and is_placeholder_avatar:
                    avatar = res_profile["avatar"]
                if res_profile.get("profileUrl") and not profile_url:
                    profile_url = res_profile["profileUrl"]

            # Update in-memory
            if proj_id:
                if proj_id not in latest_project_results:
                    latest_project_results[proj_id] = {}

                latest_project_results[proj_id]["lastAction"] = action
                latest_project_results[proj_id]["lastUpdated"] = int(time.time() * 1000)
                latest_project_results[proj_id]["lastSuccess"] = success

                if action in ("GET_FB_ACCOUNT", "GET_COOKIES"):
                    latest_project_results[proj_id]["cookies"] = cookies
                    latest_project_results[proj_id]["cookieStr"] = cookie_str
                    latest_project_results[proj_id]["cookieCount"] = len(cookies)
                    latest_project_results[proj_id]["c_user"] = c_user
                    if name: latest_project_results[proj_id]["fbName"] = name
                    if avatar: latest_project_results[proj_id]["avatar"] = avatar
                    if profile_url: latest_project_results[proj_id]["profileUrl"] = profile_url
                    if token: latest_project_results[proj_id]["eaagToken"] = token
                    if dtsg: latest_project_results[proj_id]["dtsg"] = dtsg

                elif action == "GET_TABS":
                    latest_project_results[proj_id]["tabs"] = body.get("tabs", [])

                elif action == "EXECUTE_SCRIPT":
                    latest_project_results[proj_id]["scriptData"] = body.get("data")
                    latest_project_results[proj_id]["scriptError"] = body.get("error")
                    latest_project_results[proj_id]["scriptSuccess"] = success
                    data_str = str(body.get("data") or "")
                    if "EAA" in data_str:
                        latest_project_results[proj_id]["eaagToken"] = data_str

            # Update specific sub-project in projects.json
            if proj_id:
                projs = get_projects()
                target_proj = None
                for p in projs:
                    if p.get("id") == proj_id:
                        target_proj = p
                        break

                if target_proj:
                    subs = target_proj.get("subProjects", [])
                    target_sub = None
                    if target_sub_id:
                        for s in subs:
                            if s.get("id") == target_sub_id:
                                target_sub = s
                                break
                    elif len(subs) > 0:
                        target_sub = subs[0]

                    if target_sub:
                        if action in ("GET_FB_ACCOUNT", "GET_COOKIES"):
                            if cookies: target_sub["cookies"] = cookies
                            if cookie_str: target_sub["cookieStr"] = cookie_str
                            if c_user: target_sub["c_user"] = c_user
                            if name:
                                is_generic = "trang cá nhân" in name.lower() or "your profile" in name.lower() or name.lower() == "facebook"
                                if not is_generic:
                                    target_sub["fbName"] = name
                                elif not target_sub.get("fbName"):
                                    target_sub["fbName"] = f"Facebook ({c_user})" if c_user else ""
                            if avatar: target_sub["avatar"] = avatar
                            if profile_url: target_sub["profileUrl"] = profile_url
                            if token: target_sub["eaagToken"] = token
                            if dtsg: target_sub["dtsg"] = dtsg
                            target_sub["status"] = "LIVE" if c_user else ("CHƯA ĐĂNG NHẬP" if cookies else "CHƯA CÓ COOKIE")
                            target_sub["lastExtracted"] = int(time.time() * 1000)
                            save_projects(projs)
                            push_log(f"Đã cập nhật thông tin tài khoản FB cho '{target_sub['name']}': UID={c_user or '---'}, Tên={name or '---'}", "success", project_id=proj_id, subproject_id=target_sub['id'])

                        elif action == "EXECUTE_SCRIPT":
                            data_str = str(body.get("data") or "")
                            if "EAA" in data_str:
                                target_sub["eaagToken"] = data_str
                                save_projects(projs)
                                push_log(f"Đã lưu Token EAAG cho '{target_sub['name']}'", "success", project_id=proj_id, subproject_id=target_sub['id'])

                        elif action in ("POST_STORY", "SEEDING"):
                            post_id = body.get("postId") or orig_cmd.get("post", {}).get("id") or orig_cmd.get("postId")
                            if "postQueue" in target_sub:
                                for p_item in target_sub["postQueue"]:
                                    if p_item.get("id") == post_id:
                                        if success:
                                            p_item["status"] = "completed"
                                            if body.get("fbPostId"): p_item["fbPostId"] = body.get("fbPostId")
                                            if body.get("fbPostUrl"): p_item["fbPostUrl"] = body.get("fbPostUrl")
                                            if body.get("fbFeedbackId"): p_item["fbFeedbackId"] = body.get("fbFeedbackId")
                                            if body.get("seedingIds"): p_item["seedingIds"] = body.get("seedingIds")
                                            if body.get("seedingDetails"): p_item["seedingDetails"] = body.get("seedingDetails")
                                            if "shareToStorySuccess" in body: p_item["shareToStorySuccess"] = bool(body.get("shareToStorySuccess"))
                                            now_ts = int(time.time() * 1000)
                                            p_item["publishedAt"] = body.get("publishedAt") or now_ts
                                            p_item["publishedAtStr"] = format_scheduled_time(p_item["publishedAt"])
                                            p_item["progressStep"] = body.get("progressStep") or "✅ Đã xuất bản thành công lên Facebook"
                                            p_item["lastError"] = ""
                                        else:
                                            p_item["status"] = "failed"
                                            p_item["lastError"] = body.get("error", "Lỗi không xác định")
                                            p_item["progressStep"] = f"❌ Thất bại: {p_item['lastError']}"
                                        save_projects(projs)

                                        # Webhook callback notification (if configured)
                                        cb_url = p_item.get("callbackUrl")
                                        if cb_url and str(cb_url).startswith("http"):
                                            def _notify_webhook(url, post_obj, prj, sub):
                                                try:
                                                    wb_payload = {
                                                        "event": "POST_COMPLETED" if post_obj.get("status") == "completed" else "POST_FAILED",
                                                        "postId": post_obj.get("id"),
                                                        "status": post_obj.get("status"),
                                                        "fbPostId": post_obj.get("fbPostId"),
                                                        "fbPostUrl": post_obj.get("fbPostUrl"),
                                                        "fbFeedbackId": post_obj.get("fbFeedbackId"),
                                                        "seedingIds": post_obj.get("seedingIds", []),
                                                        "seedingDetails": post_obj.get("seedingDetails", []),
                                                        "publishedAt": post_obj.get("publishedAt"),
                                                        "post": post_obj,
                                                        "account": {
                                                            "projectId": prj.get("id"),
                                                            "projectName": prj.get("name"),
                                                            "subProjectId": sub.get("id"),
                                                            "subProjectName": sub.get("name"),
                                                            "c_user": sub.get("c_user"),
                                                            "fbName": sub.get("fbName")
                                                        }
                                                    }
                                                    w_body = json.dumps(wb_payload).encode("utf-8")
                                                    w_req = urllib.request.Request(url, data=w_body, headers={"Content-Type": "application/json", "User-Agent": "AutoPostFB-Webhook/1.0"}, method="POST")
                                                    urllib.request.urlopen(w_req, timeout=8)
                                                except Exception as we:
                                                    print(f"[Webhook Error] {we}")
                                            threading.Thread(target=_notify_webhook, args=(cb_url, p_item.copy(), target_proj, target_sub), daemon=True).start()
                                        break

            log_msg = f"Đã thực thi [{action}]: "
            if action in ("GET_FB_ACCOUNT", "GET_COOKIES"):
                log_msg += f"Trích xuất thông tin FB thành công (UID: {c_user or '---'}, Tên: {name or '---'}, Cookies: {len(cookies)})"
            elif action == "EXECUTE_SCRIPT":
                log_msg += f"Kết quả Script: {str(body.get('data') or body.get('error'))[:60]}"
            elif action == "POST_STORY":
                log_msg += f"Đăng bài viết Facebook {'thành công' if success else 'thất bại: ' + str(body.get('error'))}"
            elif action == "SEEDING":
                log_msg += f"Seeding Facebook {'thành công' if success else 'thất bại: ' + str(body.get('error'))}"
            elif action == "GET_TABS":
                log_msg += f"Cập nhật danh sách {len(body.get('tabs', []))} tabs"
            else:
                log_msg += "Thành công" if success else f"Lỗi: {body.get('error')}"

            push_log(log_msg, "success" if success else "warn", project_id=proj_id, subproject_id=target_sub_id)
            self._send_json(200, {"success": True})
            return

        # 10. Command
        if pathname == "/api/bridge/command":
            cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            target_proj_id = body.get("targetProjectId")
            target_sub_id = body.get("targetSubProjectId")
            cmd = {
                "id": cmd_id,
                "targetProjectId": target_proj_id,
                "targetSubProjectId": target_sub_id,
                "targetNodeId": body.get("targetNodeId", "*"),
                **body
            }
            pending_commands.append(cmd)
            recent_issued_commands[cmd_id] = cmd

            if len(recent_issued_commands) > 100:
                oldest_key = next(iter(recent_issued_commands))
                del recent_issued_commands[oldest_key]

            proj_obj = find_project_by_id(target_proj_id)
            proj_name = proj_obj["name"] if proj_obj else (target_proj_id or "Tất cả")
            push_log(f"Đã phát lệnh [{cmd.get('action')}] tới: '{proj_name}'", "step", project_id=target_proj_id, subproject_id=target_sub_id)
            self._send_json(200, {"success": True, "cmdId": cmd_id})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        pathname = parsed.path
        body = self._parse_body()

        if pathname.startswith("/api/v1/posts/"):
            parts = pathname.strip("/").split("/")
            post_id = parts[-1]
            all_projs = get_projects()
            found_post = None
            found_sub = None
            found_proj = None
            for p in all_projs:
                for s in p.get("subProjects", []):
                    for post_item in s.get("postQueue", []):
                        if post_item.get("id") == post_id:
                            found_post = post_item
                            found_sub = s
                            found_proj = p
                            break
                    if found_post: break
                if found_post: break

            if not found_post:
                self._send_json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": f"Không tìm thấy bài viết '{post_id}'"}})
                return

            if "title" in body:
                found_post["title"] = body["title"]
            if "content" in body:
                found_post["content"] = resolve_spintax(body["content"])
            if "seedingComments" in body:
                raw_seeding = body["seedingComments"]
                if isinstance(raw_seeding, str):
                    found_post["seedingComments"] = [c.strip() for c in raw_seeding.split("\n") if c.strip()]
                elif isinstance(raw_seeding, list):
                    found_post["seedingComments"] = [str(c).strip() for c in raw_seeding if str(c).strip()]
            if "autoReactType" in body:
                found_post["autoReactType"] = body["autoReactType"]
            if "shareToFeed" in body:
                found_post["shareToFeed"] = bool(body["shareToFeed"])
            if "shareToStory" in body:
                found_post["shareToStory"] = bool(body["shareToStory"])
            if "callbackUrl" in body:
                found_post["callbackUrl"] = str(body["callbackUrl"])

            if "scheduledAt" in body or "scheduledTime" in body:
                new_sched_val = body.get("scheduledAt") or body.get("scheduledTime")
                if not new_sched_val:
                    found_post["status"] = "pending"
                    found_post["scheduledTime"] = 0
                    found_post["scheduledTimeStr"] = ""
                    found_post["scheduledAt"] = ""
                    found_post["progressStep"] = "Đã hủy hẹn giờ, lưu trong hàng đợi"
                    push_log(f"Đã hủy giờ hẹn đăng bài '{post_id}'", "step", project_id=found_proj.get("id"), subproject_id=found_sub.get("id"))
                else:
                    new_sched_ms = parse_scheduled_time(new_sched_val)
                    now_ms = int(time.time() * 1000)
                    if not new_sched_ms or new_sched_ms <= now_ms:
                        self._send_json(422, {"success": False, "error": {"code": "INVALID_SCHEDULE_TIME", "message": "Thời gian đặt lịch phải ở thời điểm tương lai!"}})
                        return
                    formatted = format_scheduled_time(new_sched_ms)
                    found_post["status"] = "scheduled"
                    found_post["scheduledTime"] = new_sched_ms
                    found_post["scheduledTimeStr"] = formatted
                    found_post["scheduledAt"] = datetime.fromtimestamp(new_sched_ms / 1000.0, tz=timezone.utc).isoformat()
                    found_post["progressStep"] = f"⏳ Đã lên lịch đăng lúc {formatted}"
                    push_log(f"⏰ Đã cập nhật lịch đăng bài '{post_id}' sang {formatted}", "step", project_id=found_proj.get("id"), subproject_id=found_sub.get("id"))

            save_projects(all_projs)
            self._send_json(200, {
                "success": True,
                "message": "Cập nhật bài viết thành công",
                "data": found_post,
                "post": found_post
            })
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        pathname = parsed.path

        if pathname.startswith("/api/v1/posts/"):
            parts = pathname.strip("/").split("/")
            post_id = parts[-1]
            all_projs = get_projects()
            deleted = False
            for p in all_projs:
                for s in p.get("subProjects", []):
                    queue = s.get("postQueue", [])
                    new_q = [item for item in queue if item.get("id") != post_id]
                    if len(new_q) != len(queue):
                        s["postQueue"] = new_q
                        deleted = True
                        push_log(f"Đã xóa bài viết '{post_id}' khỏi hàng đợi của '{s['name']}'", "warn", project_id=p.get("id"), subproject_id=s.get("id"))
                        break
                if deleted: break

            if deleted:
                save_projects(all_projs)
                self._send_json(200, {"success": True, "message": f"Đã xóa bài viết '{post_id}' thành công"})
            else:
                self._send_json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": f"Không tìm thấy bài viết '{post_id}'"}})
            return

        self._send_json(404, {"error": "Endpoint not found"})


def run():
    start_post_scheduler()
    host = os.environ.get("HOST", "0.0.0.0")
    server_address = (host, PORT)
    httpd = ThreadingHTTPServer(server_address, BridgeHandler)
    print("=======================================================")
    print("[*] BAWUI EXTENSION PRO -- FOLDER CONTROLLER RUNNING!")
    print(f"[*] API & DASHBOARD: http://127.0.0.1:{PORT}")
    print("=======================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    run()
