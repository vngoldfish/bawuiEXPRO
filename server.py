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
import json
import time
import uuid
import platform
import random
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

def get_projects():
    if os.path.exists(PROJECTS_PATH):
        try:
            with open(PROJECTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
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
    try:
        with open(PROJECTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"projects": projects_list}, f, ensure_ascii=False, indent=2)
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
            padding: 12px 10px;
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .menu-label {
            font-size: 10px;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            padding: 10px 12px 4px;
        }

        .menu-item a, .menu-item button {
            width: 100%;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 9px 12px;
            border-radius: 8px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.15s ease-in-out;
            background: transparent;
            border: none;
            text-align: left;
            cursor: pointer;
        }

        .menu-item a:hover, .menu-item button:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
        }

        .menu-item.active a, .menu-item.active button {
            background: rgba(2, 132, 199, 0.18);
            color: var(--accent);
            border-left: 3px solid var(--accent);
            border-radius: 4px 8px 8px 4px;
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
                        <span>📁</span>
                        <span>Danh Sách Dự Án</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-vps">
                    <button onclick="switchHubRoute('hub-vps')">
                        <span>☁️</span>
                        <span>Cài Đặt VPS & Hướng Dẫn</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-manifest">
                    <button onclick="switchHubRoute('hub-manifest')">
                        <span>⚙️</span>
                        <span>Đổi Tên & Cấu Hình Extension</span>
                    </button>
                </li>
                <li class="menu-item" data-hub-route="hub-system">
                    <button onclick="switchHubRoute('hub-system')">
                        <span>ℹ️</span>
                        <span>Thông Tin Hệ Thống</span>
                    </button>
                </li>
            </ul>
        </div>

        <!-- 1B. SIDEBAR: TẦNG 2 (TRONG DỰ ÁN CHA - FOLDER MANAGER) -->
        <div id="sidebar-parent-nav" style="display:none;">
            <div class="sidebar-context-card">
                <button class="btn-nav-back" onclick="exitToHub()">
                    <span>⬅️</span>
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
                        <span>📂</span>
                        <span>Danh Sách Dự Án Con</span>
                    </button>
                </li>
                <li class="menu-label">Máy & Trình Duyệt</li>
                <li class="menu-item" data-parent-route="parent-machine">
                    <button onclick="switchParentRoute('parent-machine')">
                        <span>🖥️</span>
                        <span>Thông Tin Máy & Chrome</span>
                    </button>
                </li>
                <li class="menu-item" data-parent-route="parent-logs">
                    <button onclick="switchParentRoute('parent-logs')">
                        <span>📜</span>
                        <span>Nhật Ký Máy (Logs)</span>
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
                <li class="menu-item active" data-sub-menu="sub-account-info">
                    <button onclick="switchSubMenu('sub-account-info')">
                        <span>👤</span>
                        <span id="sideMenuAccountTitle">Thông Tin Tài Khoản</span>
                    </button>
                </li>

                <!-- BỘ TỰ ĐỘNG HÓA (PHÂN BIỆT THEO NỀN TẢNG) -->
                <li class="menu-label" id="sideMenuAutomationLabel">Bộ Tự Động Hóa Facebook</li>
                <li class="menu-item" data-sub-menu="sub-scraper" id="sideMenuScraperItem">
                    <button onclick="switchSubMenu('sub-scraper')">
                        <span>📥</span>
                        <span id="sideMenuScraperTitle">Cào Dữ Liệu Facebook</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-autopost" id="sideMenuAutopostItem">
                    <button onclick="switchSubMenu('sub-autopost')">
                        <span>🚀</span>
                        <span id="sideMenuAutopostTitle">Tự Động Đăng Bài Facebook</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-interaction" id="sideMenuInteractionItem">
                    <button onclick="switchSubMenu('sub-interaction')">
                        <span>💬</span>
                        <span id="sideMenuInteractionTitle">Tương Tác / Nuôi Nick FB</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-other-notice" id="sideMenuOtherNoticeItem" style="display:none;">
                    <button onclick="switchSubMenu('sub-other-notice')">
                        <span>💡</span>
                        <span id="sideMenuOtherNoticeTitle">Trạng Thái Tự Động Hóa</span>
                    </button>
                </li>

                <li class="menu-label">Điều Khiển Trình Duyệt</li>
                <li class="menu-item" data-sub-menu="sub-browser">
                    <button onclick="switchSubMenu('sub-browser')">
                        <span>🌐</span>
                        <span id="sideMenuBrowserTitle">Điều Khiển Tab Nguồn</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-scripts">
                    <button onclick="switchSubMenu('sub-scripts')">
                        <span>💻</span>
                        <span>JavaScript Console</span>
                    </button>
                </li>
                <li class="menu-item" data-sub-menu="sub-logs">
                    <button onclick="switchSubMenu('sub-logs')">
                        <span>📜</span>
                        <span>Nhật Ký Lệnh</span>
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

    <!-- 2. MAIN CONTENT WRAPPER -->
    <div class="main-wrapper">
        <!-- TOP HEADER -->
        <header class="top-header">
            <div class="header-title-box">
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
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
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
                <div id="hubProjectsListContainer" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:18px;">
                    <div style="color:var(--text-muted); font-size:13px;">Đang tải danh sách dự án...</div>
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
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; font-size:13px;">
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
                    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;" id="subProjectsFilterTabs">
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

                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px;">
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
                <div id="foldersGrid" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:18px;">
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

                    <div style="display:grid; grid-template-columns: 2fr 1fr 1fr; gap:12px; align-items:end; margin-bottom:12px;">
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
                <!-- BANNER -->
                <div class="card" style="margin-bottom:20px; background:linear-gradient(135deg, #022c22 0%, #064e3b 100%); border-color:#34d399;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:800; color:#fff; display:flex; align-items:center; gap:8px;">
                                <span>🚀</span> <span id="autopostBannerTitle">Studio Đăng Bài Viết & Seeding Facebook Tự Động</span>
                            </h2>
                            <p style="font-size:13px; color:#cbd5e1; margin-top:4px;" id="autopostBannerDesc">
                                Soạn thảo bài đăng đa định dạng (Post, Video, Reels, Story), nạp tệp media trực tiếp hoặc link, tự động seeding bình luận và thả cảm xúc ngầm qua Direct GraphQL Engine.
                            </p>
                        </div>
                        <span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; border:1px solid rgba(52,211,153,0.4); padding:6px 14px; font-size:12px;">
                            ⚡ DIRECT GRAPHQL FB ENGINE
                        </span>
                    </div>
                </div>

                <!-- 4 KPI CARDS -->
                <div class="grid-cards" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
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

                    <!-- 1. CHỌN ĐỊNH DẠNG ĐĂNG BÀI (POST TYPE PILLS) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            📌 1. Định Dạng Bài Đăng Facebook:
                        </label>
                        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px;">
                            <button type="button" class="type-pill-btn active" data-type="post" onclick="selectPostTypePill('post', this)">
                                <span>📝</span> <span>Bài Viết Thường / Ảnh</span>
                            </button>
                            <button type="button" class="type-pill-btn" data-type="video" onclick="selectPostTypePill('video', this)">
                                <span>🎬</span> <span>Facebook Video (Watch)</span>
                            </button>
                            <button type="button" class="type-pill-btn" data-type="reel" onclick="selectPostTypePill('reel', this)">
                                <span>⚡</span> <span>Facebook Reels (Ngắn)</span>
                            </button>
                            <button type="button" class="type-pill-btn" data-type="story" onclick="selectPostTypePill('story', this)">
                                <span>📖</span> <span>Facebook Story (24h)</span>
                            </button>
                        </div>
                    </div>

                    <!-- 2. CHỌN ĐÍCH ĐĂNG (TARGET TYPE PILLS) -->
                    <div style="margin-bottom:14px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🎯 2. Đích Đăng Bài Viết (Target):
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

                    <!-- 3. TIÊU ĐỀ BÀI ĐĂNG (TÙY CHỌN) -->
                    <div style="margin-bottom:12px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">📝 Tiêu Đề Bài Viết / Ghi Chú Chiến Dịch:</label>
                        <input type="text" id="postTitleInput" placeholder="Ví dụ: Bài đăng giới thiệu sản phẩm #01 / Flash Sale" />
                    </div>

                    <!-- 4. NỘI DUNG VĂN BẢN (CAPTION & SPINTAX) -->
                    <div style="margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">
                                ✍️ Nội Dung Chi Tiết (Hỗ trợ Spintax {A|B|C}):
                            </label>
                            <div style="display:flex; gap:10px; align-items:center;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#38bdf8;" onclick="testSpintaxPreview()">🎲 Thử Xoay Spintax</button>
                                <span id="postCharCount" style="font-size:11px; color:var(--text-muted);">0 ký tự</span>
                            </div>
                        </div>
                        <textarea id="postContentInput" rows="5" placeholder="{Chào bạn|Hello quý khách|Hi cả nhà}! Hôm nay bên mình {giảm giá|ưu đãi khủng|tri ân khách hàng}...&#10;#sanpham #khuyenmai" oninput="updatePostCharCount(this)"></textarea>
                    </div>

                    <!-- 5. TỆP MEDIA (HÌNH ẢNH / VIDEO) -->
                    <div style="margin-bottom:16px;">
                        <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px; display:block;">
                            🖼️ 3. Tệp Hình Ảnh / Video (Media Attachment):
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

                    <!-- 6. KỊCH BẢN BÌNH LUẬN SEEDING & CẢM XÚC -->
                    <div style="margin-bottom:16px; background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                            <label style="font-size:12px; font-weight:700; color:#34d399; display:flex; align-items:center; gap:6px;">
                                <span>💬</span> <span>4. Kịch Bản Bình Luận Seeding Ngay Sau Khi Đăng:</span>
                            </label>
                            <div style="display:flex; gap:6px;">
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#a78bfa;" onclick="insertSeedingPreset('inquiry')">✨ Mẫu Hỏi Giá</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#34d399;" onclick="insertSeedingPreset('feedback')">✨ Mẫu Khen Hàng</button>
                                <button type="button" class="btn-sm" style="background:#1e293b; color:#94a3b8;" onclick="insertSeedingPreset('clear')">✕ Xóa</button>
                            </div>
                        </div>
                        <textarea id="postSeedingCommentsInput" rows="3" placeholder="💬 Mỗi dòng một bình luận seeding tự động...&#10;Sản phẩm này còn hàng không shop?&#10;Đã nhận được hàng, rất ưng ý ạ!&#10;Shop tư vấn nhiệt tình lắm nha"></textarea>

                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px;">
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

                    <!-- SUBMIT BUTTONS -->
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div style="display:flex; gap:10px; flex-wrap:wrap;">
                            <button type="button" class="btn-green btn-lg" onclick="submitAutoPost(true)" style="background:linear-gradient(135deg,#059669,#10b981); box-shadow:0 4px 15px rgba(16,185,129,0.35);">
                                <span>🚀</span> <span>PHÁT LỆNH ĐĂNG BÀI & SEEDING NGAY</span>
                            </button>
                            <button type="button" class="btn-purple btn-lg" onclick="submitAutoPost(false)">
                                <span>➕</span> <span>Thêm Vào Hàng Đợi (Post Queue)</span>
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
                        <div style="display:flex; gap:8px; align-items:center; min-width:260px;">
                            <input type="text" id="postSearchInput" placeholder="🔍 Tìm theo nội dung, ID..." oninput="filterPostList(this.value)" style="margin:0; padding:6px 12px; font-size:12px;" />
                        </div>
                    </div>

                    <!-- FILTER TABS -->
                    <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
                        <button type="button" class="preset-chip active" id="filterBtnAll" onclick="setPostFilter('all', this)">🌐 Tất Cả</button>
                        <button type="button" class="preset-chip" id="filterBtnCompleted" onclick="setPostFilter('completed', this)">✅ Đã Đăng Thành Công</button>
                        <button type="button" class="preset-chip" id="filterBtnPending" onclick="setPostFilter('pending', this)">⏳ Đang Chờ / Đang Đăng</button>
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

                <div class="grid-cards" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:18px; margin-bottom:20px;">
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
            "hub-vps": { title: "☁️ Cài Đặt VPS & Hướng Dẫn", el: document.getElementById("view-hub-vps") },
            "hub-manifest": { title: "⚙️ Đổi Tên & Cấu Hình Extension", el: document.getElementById("view-hub-manifest") },
            "hub-system": { title: "ℹ️ Thông Tin Hệ Thống", el: document.getElementById("view-hub-system") }
        };

        function switchHubRoute(targetKey) {
            document.querySelectorAll("#sidebar-hub-nav .menu-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-hub-route") === targetKey);
            });
            document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
            if (hubRoutes[targetKey] && hubRoutes[targetKey].el) {
                hubRoutes[targetKey].el.classList.add("active");
                document.getElementById("pageTitle").innerHTML = hubRoutes[targetKey].title;
            }
        }

        // 2. PARENT PROJECT NAVIGATION (LEVEL 2)
        const parentRoutes = {
            "parent-subprojects": { title: "📂 Danh Sách Dự Án Con", el: document.getElementById("view-parent-subprojects") },
            "parent-machine": { title: "🖥️ Thông Tin Máy & Chrome", el: document.getElementById("view-parent-machine") },
            "parent-logs": { title: "📜 Nhật Ký Hoạt Động Máy", el: document.getElementById("view-parent-logs") }
        };

        function switchParentRoute(targetKey) {
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
        }

        // 3. SUB-PROJECT MENU NAVIGATION (LEVEL 3)
        const subMenus = {
            "sub-account-info": { title: "👤 Kiểm Tra Thông Tin Tài Khoản", el: document.getElementById("view-sub-account-info") },
            "sub-scraper": { title: "📥 Cào Dữ Liệu Facebook (Scraper)", el: document.getElementById("view-sub-scraper") },
            "sub-autopost": { title: "🚀 Tự Động Đăng Bài Facebook (Auto Poster)", el: document.getElementById("view-sub-autopost") },
            "sub-interaction": { title: "💬 Studio Tương Tác / Nuôi Nick FB", el: document.getElementById("view-sub-interaction") },
            "sub-other-notice": { title: "💡 Trạng Thái Tự Động Hóa Nền Tảng", el: document.getElementById("view-sub-other-notice") },
            "sub-browser": { title: "🌐 Điều Khiển Tab Web", el: document.getElementById("view-sub-browser") },
            "sub-scripts": { title: "💻 JavaScript Console", el: document.getElementById("view-sub-scripts") },
            "sub-logs": { title: "📜 Nhật Ký Lệnh", el: document.getElementById("view-sub-logs") }
        };

        function switchSubMenu(targetKey) {
            if (targetKey === "sub-cookies" || targetKey === "sub-token") targetKey = "sub-account-info";

            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            const subType = sub ? (sub.type || 'facebook') : 'facebook';

            // Phân biệt rõ: Nếu không phải Facebook, không mở các menu tự động hóa của Facebook
            if (subType !== 'facebook') {
                if (targetKey === 'sub-scraper' || targetKey === 'sub-autopost' || targetKey === 'sub-interaction') {
                    targetKey = 'sub-other-notice';
                }
            } else {
                if (targetKey === 'sub-other-notice') {
                    targetKey = 'sub-account-info';
                }
            }

            document.querySelectorAll("#sidebar-sub-nav .menu-item").forEach(item => {
                item.classList.toggle("active", item.getAttribute("data-sub-menu") === targetKey);
            });
            document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
            if (subMenus[targetKey] && subMenus[targetKey].el) {
                subMenus[targetKey].el.classList.add("active");
                const pName = p ? p.name : "Dự Án Cha";
                const subName = sub ? sub.name : "Dự Án Con";
                const pCfg = PLATFORM_CONFIG[subType] || PLATFORM_CONFIG["facebook"];
                document.getElementById("pageTitle").innerHTML = `📁 ${pName} &gt; 📂 <b>${subName}</b> [${pCfg.icon} ${pCfg.name}] &rarr; ${subMenus[targetKey].title}`;
            }
        }

        // =========================================================
        // TRANSITIONS BETWEEN LEVELS
        // =========================================================

        function enterParentProject(projId) {
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
            document.getElementById("parentSubHeaderTitle").textContent = `Các Thư Mục / Dự Án Con Của [${projName}]`;

            switchParentRoute("parent-subprojects");

            fetchParentProjectData(projId);
            if (projectPollInterval) clearInterval(projectPollInterval);
            projectPollInterval = setInterval(() => {
                if (currentProjectId) fetchParentProjectData(currentProjectId);
            }, 2500);

            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        function exitToHub() {
            currentLevel = "hub";
            currentProjectId = null;
            currentSubProjectId = null;
            localStorage.removeItem("active_parent_id");
            localStorage.removeItem("active_sub_id");
            if (projectPollInterval) clearInterval(projectPollInterval);

            document.getElementById("sidebar-hub-nav").style.display = "block";
            document.getElementById("sidebar-parent-nav").style.display = "none";
            document.getElementById("sidebar-sub-nav").style.display = "none";

            switchHubRoute("hub-projects");
            fetchProjects();
        }

        function enterSubProject(subId) {
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

            // Mặc định mở Thông Tin Tài Khoản & Session
            switchSubMenu("sub-account-info");

            if (sub) renderSubProjectWorkspace(sub);

            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        function adaptSubMenuForPlatform(subType, pCfg, subId) {
            const isFb = (subType === 'facebook');

            const autoLabel = document.getElementById("sideMenuAutomationLabel");
            const scraperItem = document.getElementById("sideMenuScraperItem");
            const autopostItem = document.getElementById("sideMenuAutopostItem");
            const interactionItem = document.getElementById("sideMenuInteractionItem");
            const otherNoticeItem = document.getElementById("sideMenuOtherNoticeItem");
            const sideAccount = document.getElementById("sideMenuAccountTitle");
            const sideBrowser = document.getElementById("sideMenuBrowserTitle");

            if (isFb) {
                // FACEBOOK: ĐẦY ĐỦ 100% CÔNG CỤ TỰ ĐỘNG HÓA FB
                if (autoLabel) { autoLabel.textContent = "Bộ Tự Động Hóa Facebook"; autoLabel.style.display = "block"; }
                if (scraperItem) scraperItem.style.display = "block";
                if (autopostItem) autopostItem.style.display = "block";
                if (interactionItem) interactionItem.style.display = "block";
                if (otherNoticeItem) otherNoticeItem.style.display = "none";
                if (sideAccount) sideAccount.textContent = "Thông Tin & Cookie FB";
                if (sideBrowser) sideBrowser.textContent = "Điều Khiển Tab Facebook";
            } else {
                // CÁC NỀN TẢNG KHÁC (TIKTOK, FLOW, X...): ẨN CÁC TOOL FB ĐỂ KHÔNG BỊ TRỘN LẪN
                if (autoLabel) { autoLabel.textContent = `Tự Động Hóa ${pCfg.name}`; autoLabel.style.display = "block"; }
                if (scraperItem) scraperItem.style.display = "none";
                if (autopostItem) autopostItem.style.display = "none";
                if (interactionItem) interactionItem.style.display = "none";
                if (otherNoticeItem) {
                    otherNoticeItem.style.display = "block";
                    const otherNoticeTitle = document.getElementById("sideMenuOtherNoticeTitle");
                    if (otherNoticeTitle) otherNoticeTitle.textContent = `Kịch Bản ${pCfg.name}`;
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
        }

        function exitToParentProject() {
            if (currentProjectId) {
                enterParentProject(currentProjectId);
            } else {
                exitToHub();
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

                const statsHtml = isFb ? `
                    <div style="background:#050914; border:1px solid #1e293b; border-radius:8px; padding:10px 12px; font-size:12px; margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Web nguồn:</span>
                            <span style="font-family:monospace; font-weight:700; color:#38bdf8;">facebook.com</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:var(--text-muted);">Phiên Cookie FB:</span>
                            <b style="color:${hasCookie ? 'var(--success)' : 'var(--warning)'};">${hasCookie ? '🟢 Sẵn sàng (' + cookieCount + ' cookies)' : '⚪ Chưa quét'}</b>
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

                if (cUser) {
                    if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot online"></span> <span style="color:var(--success);">LIVE (Đã Đăng Nhập)</span>';
                    if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:var(--success);">🟢 ĐÃ ĐĂNG NHẬP</span>';
                    if (accLoginSub) accLoginSub.textContent = "Tài khoản đang active trên Chrome";
                } else if (hasCookies) {
                    if (accStatusBadge) accStatusBadge.innerHTML = '<span class="dot"></span> <span style="color:var(--warning);">CHƯA ĐĂNG NHẬP FB</span>';
                    if (accLoginStatus) accLoginStatus.innerHTML = '<span style="color:var(--warning);">⚠️ CHƯA ĐĂNG NHẬP</span>';
                    if (accLoginSub) accLoginSub.textContent = "Đăng nhập tài khoản trên facebook.com";
                } else {
                    if (accStatusBadge) accStatusBadge.innerHTML = '⚪ Chưa quét tài khoản';
                    if (accLoginStatus) accLoginStatus.innerHTML = '⚪ Chưa quét';
                    if (accLoginSub) accLoginSub.textContent = "Bấm nút Quét & Lấy Thông Tin ở trên";
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
                    alert("Lỗi khi lưu cookie: " + (data.error || "Không xác định"));
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

        function setPostFilter(filterType, btn) {
            _currentPostFilter = filterType;
            document.querySelectorAll(".preset-chip").forEach(b => {
                if (b.id && b.id.startsWith("filterBtn")) b.classList.remove("active");
            });
            if (btn) btn.classList.add("active");
            const p = allProjects.find(x => x.id === currentProjectId);
            const sub = p ? (p.subProjects || []).find(s => s.id === currentSubProjectId) : null;
            if (sub) {
                const pCfg = getPlatformConfig(sub.type || "facebook");
                renderAutoPosterStudio(sub, pCfg);
            }
        }

        function filterPostList(query) {
            _postSearchQuery = query;
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
                    alert("❌ Lỗi: " + (data.error || "Không thể gửi seeding"));
                }
            } catch(e) {
                alert("❌ Lỗi kết nối: " + e.message);
            }
        }

        async function runPostNow(postId) {
            if (!currentProjectId || !currentSubProjectId || !postId) return;
            try {
                const res = await fetch("/api/subprojects/run-post", {
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
                    alert("❌ Lỗi: " + (data.error || "Không thể thực thi"));
                }
            } catch(e) {
                alert("❌ Lỗi kết nối: " + e.message);
            }
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
                selectPostTypePill(post.postType, btn);
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

        function renderAutoPosterStudio(sub, pCfg) {
            const bannerTitle = document.getElementById("autopostBannerTitle");
            const targetUrlInput = document.getElementById("postTargetUrlInput");
            const countBadge = document.getElementById("postQueueCountBadge");
            const container = document.getElementById("postQueueTableContainer");

            const sourceDomain = sub.sourceDomain || pCfg.domain || "facebook.com";
            if (bannerTitle) bannerTitle.textContent = `Studio Tự Động Đăng Bài Lên: ${pCfg.name} (${sourceDomain})`;
            if (targetUrlInput && (!targetUrlInput.value || targetUrlInput.value === "https://...")) {
                targetUrlInput.value = "https://www.facebook.com";
            }

            const queue = sub.postQueue || [];
            if (countBadge) countBadge.textContent = `${queue.length} Bài`;

            // Calculate KPIs
            let pendingCount = 0;
            let completedCount = 0;
            let seedingTotal = 0;

            queue.forEach(p => {
                if (p.status === "completed") completedCount++;
                else if (p.status === "in_progress" || p.status === "pending" || !p.status || p.status.includes("Chờ") || p.status.includes("Đang")) pendingCount++;
                if (p.seedingComments && Array.isArray(p.seedingComments)) {
                    seedingTotal += p.seedingComments.length;
                }
            });

            const kpiTotal = document.getElementById("kpiTotalPosts");
            const kpiPending = document.getElementById("kpiPendingPosts");
            const kpiCompleted = document.getElementById("kpiCompletedPosts");
            const kpiSeeding = document.getElementById("kpiTotalSeeding");

            if (kpiTotal) kpiTotal.textContent = queue.length;
            if (kpiPending) kpiPending.textContent = pendingCount;
            if (kpiCompleted) kpiCompleted.textContent = completedCount;
            if (kpiSeeding) kpiSeeding.textContent = seedingTotal;

            if (!container) return;

            if (queue.length === 0) {
                container.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:36px 20px; text-align:center;">
                        <span style="font-size:32px;">🚀</span>
                        <div style="font-weight:700; color:#cbd5e1; margin-top:8px;">Hàng đợi bài đăng đang trống</div>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                            Soạn nội dung ở khung bên trên rồi bấm <b>[🚀 PHÁT LỆNH ĐĂNG BÀI & SEEDING NGAY]</b> hoặc <b>[➕ Thêm Vào Hàng Đợi]</b>!
                        </div>
                    </div>
                `;
                return;
            }

            // Filter queue
            let filtered = queue.filter(p => {
                if (_currentPostFilter === "completed") return p.status === "completed";
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

            if (filtered.length === 0) {
                container.innerHTML = `
                    <div style="color:var(--text-muted); font-size:13px; padding:24px 20px; text-align:center;">
                        Không tìm thấy bài đăng nào phù hợp với bộ lọc hiện tại.
                    </div>
                `;
                return;
            }

            container.innerHTML = filtered.map((p, idx) => {
                const isCompleted = p.status === "completed";
                const isInProgress = p.status === "in_progress" || (p.status && p.status.includes("Đang"));
                const isFailed = p.status === "failed";

                let statusBadgeHtml = `<span class="badge-folder" style="background:rgba(251,191,36,0.2); color:#fbbf24; border:1px solid rgba(251,191,36,0.4);">⏳ Đang Chờ</span>`;
                if (isCompleted) {
                    statusBadgeHtml = `<span class="badge-folder" style="background:rgba(52,211,153,0.2); color:#34d399; border:1px solid rgba(52,211,153,0.4);">✅ Hoàn Thành</span>`;
                } else if (isInProgress) {
                    statusBadgeHtml = `<span class="badge-folder" style="background:rgba(56,189,248,0.2); color:#38bdf8; border:1px solid rgba(56,189,248,0.4); display:inline-flex; align-items:center; gap:5px;"><div class="pulse-spinner"></div> Đang Xử Lý</span>`;
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

                return `
                    <div class="smart-post-card" style="${isInProgress ? 'border-color: #38bdf8; box-shadow: 0 0 15px rgba(56,189,248,0.2);' : (isCompleted ? 'border-color: rgba(52,211,153,0.3);' : '')}">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                                <span class="badge-folder" style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(168,85,247,0.4);">${typeBadge}</span>
                                <span class="badge-folder" style="background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3);">${targetBadge}</span>
                                ${p.targetId ? `<span class="badge-folder" style="background:rgba(255,255,255,0.06); color:#cbd5e1;">Target ID: ${escapeHtml(p.targetId)}</span>` : ''}
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

                        ${fbPostUrl ? `
                            <div style="margin-top:10px;">
                                <a href="${escapeHtml(fbPostUrl)}" target="_blank" rel="noopener" class="btn-sm btn-green" style="text-decoration:none;">
                                    🔗 Xem Bài Viết Trực Tiếp Trên Facebook (ID: ${escapeHtml(fbPostId || 'Xem')})
                                </a>
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
                                <button type="button" class="btn-sm ${isCompleted ? 'btn-purple' : 'btn-green'}" onclick="runPostNow('${p.id}')">
                                    ${isCompleted ? '🔄 Đăng Lại' : '⚡ Đăng Ngay'}
                                </button>
                                <button type="button" class="btn-sm" style="background:#0284c7;" onclick="openAddSeedingModal('${p.id}')">
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
            }).join("");
        }

        async function submitAutoPost(runNow) {
            if (!currentProjectId || !currentSubProjectId) return;
            const title = document.getElementById("postTitleInput")?.value.trim() || "";
            const rawContent = document.getElementById("postContentInput")?.value.trim() || "";
            const mediaUrl = document.getElementById("postMediaInput")?.value.trim() || "";
            const targetUrl = document.getElementById("postTargetUrlInput")?.value.trim() || "https://www.facebook.com";
            const targetId = document.getElementById("postTargetIdInput")?.value.trim() || "";
            const rawSeeding = document.getElementById("postSeedingCommentsInput")?.value.trim() || "";
            const autoReactType = document.getElementById("postAutoReactInput")?.value || "LIKE";
            const statusEl = document.getElementById("autopostStatusText");

            if (!rawContent && !title && !_adminMediaData && !mediaUrl) {
                alert("Vui lòng nhập nội dung bài viết hoặc đính kèm ảnh/video!");
                return;
            }

            const content = parseSpintax(rawContent);
            const seedingComments = rawSeeding ? rawSeeding.split("\\n").map(s => s.trim()).filter(Boolean) : [];

            if (statusEl) {
                statusEl.textContent = runNow ? "⏳ Đang chuyển lệnh đăng ngầm sang Extension..." : "⏳ Đang lưu vào hàng đợi...";
                statusEl.style.color = "var(--accent)";
            }

            try {
                const payload = {
                    title,
                    content,
                    postType: _currentPostType,
                    targetType: _currentTargetType,
                    targetId,
                    targetUrl,
                    mediaUrl,
                    mediaData: _adminMediaData ? {
                        base64: _adminMediaData.base64,
                        fileName: _adminMediaData.fileName,
                        mimeType: _adminMediaData.mimeType,
                        size: _adminMediaData.size
                    } : null,
                    seedingComments,
                    autoReactType,
                    runNow: !!runNow
                };

                const res = await fetch("/api/subprojects/add-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        post: payload,
                        runNow: !!runNow
                    })
                });

                const data = await res.json();
                if (data.success) {
                    if (statusEl) {
                        statusEl.textContent = runNow ? "🚀 Đã phát lệnh đăng bài & seeding ngầm lên Facebook!" : "✅ Đã lưu vào hàng đợi bài đăng!";
                        statusEl.style.color = "var(--success)";
                    }

                    document.getElementById("postTitleInput").value = "";
                    document.getElementById("postContentInput").value = "";
                    document.getElementById("postMediaInput").value = "";
                    document.getElementById("postSeedingCommentsInput").value = "";
                    clearAdminMedia();
                    updatePostCharCount(document.getElementById("postContentInput"));

                    setTimeout(() => {
                        if (currentProjectId) fetchParentProjectData(currentProjectId);
                    }, 600);
                } else {
                    if (statusEl) {
                        statusEl.textContent = "❌ " + (data.error || "Lỗi tạo bài đăng");
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
            try {
                await fetch("/api/subprojects/delete-post", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        projectId: currentProjectId,
                        subProjectId: currentSubProjectId,
                        postId
                    })
                });
                if (currentProjectId) fetchParentProjectData(currentProjectId);
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
                    statusEl.textContent = "❌ Lỗi: " + data.error;
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
                    alert("❌ Lỗi: " + data.error);
                }
            } catch(e) {
                alert("❌ Lỗi: " + e.message);
            }
        }

        // QUÉT & LẤY TOÀN BỘ THÔNG TIN TÀI KHOẢN FACEBOOK
        let isExtractingFbInfo = false;
        async function extractAllFbAccountInfo() {
            if (!currentProjectId || !currentSubProjectId) return;
            if (isExtractingFbInfo) return;

            const bannerBtn = document.getElementById("subAccBannerBtn");
            const oldBtnHtml = bannerBtn ? bannerBtn.innerHTML : "";

            const nodes = (latestParentData && latestParentData.nodes) || [];
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
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; font-size:13px;">
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
                    statusEl.textContent = "❌ Lỗi: " + data.error;
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
                    alert("❌ Lỗi: " + data.error);
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
                    alert("❌ Lỗi: " + data.error);
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
                    statusEl.textContent = "❌ Lỗi: " + data.error;
                    statusEl.style.color = "var(--danger)";
                }
            } catch(e) {
                statusEl.textContent = "❌ Lỗi: " + e.message;
                statusEl.style.color = "var(--danger)";
            }
        }

        // INITIALIZE APP
        window.addEventListener("DOMContentLoaded", async () => {
            await fetchProjects();
            fetchStatus();
            loadManifestConfig();

            const savedParentId = localStorage.getItem("active_parent_id");
            const savedSubId = localStorage.getItem("active_sub_id");

            if (savedParentId && allProjects.some(p => p.id === savedParentId)) {
                enterParentProject(savedParentId);
                if (savedSubId) {
                    const p = allProjects.find(x => x.id === savedParentId);
                    if (p && (p.subProjects || []).some(s => s.id === savedSubId)) {
                        enterSubProject(savedSubId);
                    }
                }
            } else {
                switchHubRoute("hub-projects");
            }

            setInterval(() => {
                fetchStatus();
                if (currentLevel === "hub") {
                    fetchProjects();
                }
            }, 3000);
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Sync-Token, X-Project-Key, X-Worker-Id")

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

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

        # Thêm bài đăng vào hàng đợi & Hỗ trợ Đăng Ngay
        if pathname == "/api/subprojects/add-post":
            proj_id = body.get("projectId")
            sub_id = body.get("subProjectId")
            post = body.get("post", {})
            run_now = body.get("runNow", False) or post.get("runNow", False)

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

            if "postQueue" not in target_sub:
                target_sub["postQueue"] = []

            post_id = f"post_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            post_entry = {
                "id": post_id,
                "title": post.get("title", ""),
                "content": post.get("content", ""),
                "postType": post.get("postType", "post"),
                "targetType": post.get("targetType", "profile"),
                "targetId": post.get("targetId", ""),
                "targetUrl": post.get("targetUrl", ""),
                "mediaUrl": post.get("mediaUrl", ""),
                "mediaData": post.get("mediaData"),
                "seedingComments": post.get("seedingComments", []),
                "autoReactType": post.get("autoReactType", "LIKE"),
                "status": "in_progress" if run_now else "pending",
                "progressStep": "Đang chuyển lệnh sang Extension..." if run_now else "Đã thêm vào hàng đợi",
                "fbPostId": "",
                "fbPostUrl": "",
                "scheduledTime": post.get("scheduledTime", 0),
                "lastError": "",
                "createdAt": int(time.time() * 1000)
            }
            target_sub["postQueue"].append(post_entry)
            save_projects(projs)

            cmd_id = None
            if run_now:
                cmd_id = f"cmd_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                cmd = {
                    "id": cmd_id,
                    "action": "POST_STORY",
                    "targetProjectId": proj_id,
                    "targetSubProjectId": sub_id,
                    "targetNodeId": "*",
                    "post": post_entry
                }
                pending_commands.append(cmd)
                recent_issued_commands[cmd_id] = cmd
                push_log(f"Đã phát lệnh đăng ngay bài viết '{post_id}' lên Facebook cho '{target_sub['name']}'", "step", project_id=proj_id, subproject_id=sub_id)
            else:
                push_log(f"Đã thêm bài viết mới vào hàng đợi đăng của '{target_sub['name']}'", "success", project_id=proj_id, subproject_id=sub_id)

            self._send_json(200, {"success": True, "post": post_entry, "cmdId": cmd_id})
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
                    "lastSeen": int(time.time() * 1000)
                }

            has_pending = any(
                (c.get("targetNodeId") == node_id or c.get("targetNodeId") == "*") and
                (not c.get("targetProjectId") or c.get("targetProjectId") == proj["id"])
                for c in pending_commands
            )

            self._send_json(200, {
                "success": True,
                "projectId": proj["id"],
                "projectName": proj["name"],
                "hasPendingCommands": has_pending
            })
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
                                            p_item["progressStep"] = body.get("progressStep") or "✅ Đã xuất bản thành công lên Facebook"
                                            p_item["lastError"] = ""
                                        else:
                                            p_item["status"] = "failed"
                                            p_item["lastError"] = body.get("error", "Lỗi không xác định")
                                            p_item["progressStep"] = f"❌ Thất bại: {p_item['lastError']}"
                                        save_projects(projs)
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


def run():
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
