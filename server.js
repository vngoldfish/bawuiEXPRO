/**
 * BROWSER BRIDGE — CONTROLLER SERVER
 * Cổng: 19823 (http://127.0.0.1:19823)
 * Chạy: node server.js
 */

const http = require("http");

const PORT = 19823;
let connectedNodes = new Map();
let pendingCommands = [];
let commandHistory = [];
let liveLogs = [];

function setCorsHeaders(res) {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Sync-Token, X-Project-Key, X-Worker-Id");
}

function sendJson(res, statusCode, data) {
    setCorsHeaders(res);
    res.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(data));
}

function parseJsonBody(req) {
    return new Promise((resolve) => {
        let body = "";
        req.on("data", chunk => { body += chunk; });
        req.on("end", () => {
            try {
                resolve(body ? JSON.parse(body) : {});
            } catch (e) {
                resolve({});
            }
        });
    });
}

function pushLog(message, type = "") {
    liveLogs.push({ time: Date.now(), message, type });
    if (liveLogs.length > 80) liveLogs.shift();
}

const server = http.createServer(async (req, res) => {
    setCorsHeaders(res);

    if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
    }

    const parsedUrl = new URL(req.url, `http://${req.headers.host}`);
    const pathname = parsedUrl.pathname;

    // 1. Giao diện Web Controller
    if (pathname === "/" && req.method === "GET") {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(`
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>BAWUI EXTENSION PRO — Controller</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f1f5f9; margin: 0; padding: 24px; }
        .container { max-width: 960px; margin: 0 auto; }
        h1 { color: #38bdf8; font-size: 22px; display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
        .card { background: #151d30; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #1e293b; }
        .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
        .badge-green { background: #064e3b; color: #34d399; }
        .badge-yellow { background: #78350f; color: #fcd34d; }
        button { background: #0284c7; color: white; border: none; padding: 9px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s; font-size: 13px; }
        button:hover { background: #0369a1; }
        .btn-green { background: #059669; }
        .btn-green:hover { background: #047857; }
        .btn-purple { background: #7c3aed; }
        .btn-purple:hover { background: #6d28d9; }
        input, textarea, select { width: 100%; box-sizing: border-box; background: #0b0f19; border: 1px solid #334155; color: white; padding: 10px; border-radius: 6px; margin: 8px 0 12px; font-size: 13px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
        .log-box { background: #050811; border: 1px solid #1e293b; border-radius: 8px; padding: 14px; font-family: Consolas, monospace; font-size: 12px; max-height: 280px; overflow-y: auto; color: #94a3b8; }
        .log-line { margin-bottom: 6px; word-break: break-all; }
        .log-success { color: #34d399; }
        .log-step { color: #38bdf8; }
        .log-warn { color: #fbbf24; }
        .actions-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ BAWUI EXTENSION PRO — Controller Dashboard</h1>
        
        <div class="card">
            <h3 style="margin-top:0;">📡 Trạng thái Trình duyệt (Chrome Extension Node)</h3>
            <div id="nodesList">Đang kiểm tra kết nối...</div>
        </div>

        <div class="card">
            <h3 style="margin-top:0;">⚡ Gửi lệnh trực tiếp sang Trình duyệt (Browser Actions)</h3>
            <div class="actions-bar">
                <button class="btn-green" onclick="sendQuickAction('GET_COOKIES', { domain: 'facebook.com' })">🍪 Lấy Cookie Facebook</button>
                <button onclick="sendQuickAction('OPEN_TAB', { url: 'https://www.facebook.com' })">🌐 Mở Tab Facebook</button>
                <button onclick="sendQuickAction('GET_TABS')">📑 Lấy Danh Sách Tab</button>
            </div>

            <div style="margin-top: 18px;">
                <label style="font-size:13px; font-weight:600; color:#cbd5e1;">Chạy Script JavaScript tùy chỉnh trên Tab đang kích hoạt:</label>
                <textarea id="scriptInput" rows="2">document.title</textarea>
                <button class="btn-purple" onclick="executeCustomScript()">Chạy JavaScript Trên Trình Duyệt</button>
            </div>
        </div>

        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h3 style="margin:0;">📜 Nhật ký phản hồi từ Trình duyệt (Live Feedback)</h3>
                <button style="padding:4px 10px; font-size:11px;" onclick="clearLogs()">Xóa log</button>
            </div>
            <div class="log-box" id="logBox">Chờ kết nối từ extension...</div>
        </div>
    </div>

    <script>
        function log(msg, type='') {
            const box = document.getElementById('logBox');
            const time = new Date().toLocaleTimeString();
            const el = document.createElement('div');
            el.className = 'log-line ' + (type ? 'log-' + type : '');
            el.textContent = '[' + time + '] ' + msg;
            box.appendChild(el);
            box.scrollTop = box.scrollHeight;
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/bridge/status');
                const data = await res.json();
                const container = document.getElementById('nodesList');
                if (!data.nodes || data.nodes.length === 0) {
                    container.innerHTML = '<span class="badge badge-yellow">⚠️ Chưa có Extension nào kết nối. Mở Chrome -> Bật extension Browser Bridge!</span>';
                } else {
                    container.innerHTML = data.nodes.map(n => \`
                        <div style="background:#0b0f19; padding:12px; border-radius:8px; border:1px solid #1e293b;">
                            <span class="badge badge-green">🟢 Node: \${n.nodeId}</span>
                            <span style="font-size:13px; color:#cbd5e1; margin-left:12px;">Số Tab: <b>\${n.tabCount || 0}</b> | Tab hiện tại: <i>\${n.activeTab ? (n.activeTab.title || n.activeTab.url) : 'Không có'}</i></span>
                        </div>
                    \`).join('');
                }

                if (data.recentLogs) {
                    data.recentLogs.forEach(l => {
                        if (!window._lastLogTime || l.time > window._lastLogTime) {
                            log(l.message, l.type);
                            window._lastLogTime = l.time;
                        }
                    });
                }
            } catch(e) {}
        }

        async function sendQuickAction(action, payload = {}) {
            log('Đang gửi lệnh ' + action + ' sang trình duyệt...', 'step');
            await fetch('/api/bridge/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, ...payload })
            });
        }

        async function executeCustomScript() {
            const code = document.getElementById('scriptInput').value.trim();
            if (!code) return;
            log('Gửi script sang trình duyệt: ' + code, 'step');
            await fetch('/api/bridge/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'EXECUTE_SCRIPT', code })
            });
        }

        function clearLogs() {
            document.getElementById('logBox').innerHTML = '';
        }

        setInterval(fetchStatus, 2000);
        fetchStatus();
    </script>
</body>
</html>
        `);
        return;
    }

    // 2. POST /api/bridge/heartbeat (Extension gửi nhịp tim)
    if (pathname === "/api/bridge/heartbeat" && req.method === "POST") {
        const body = await parseJsonBody(req);
        const nodeId = body.nodeId;
        if (nodeId) {
            connectedNodes.set(nodeId, {
                nodeId,
                status: "online",
                tabCount: body.tabCount || 0,
                activeTab: body.activeTab || null,
                lastSeen: Date.now()
            });
        }
        sendJson(res, 200, {
            success: true,
            hasPendingCommands: pendingCommands.length > 0
        });
        return;
    }

    // 3. POST /api/bridge/poll (Extension lấy lệnh)
    if (pathname === "/api/bridge/poll" && req.method === "POST") {
        const body = await parseJsonBody(req);
        if (pendingCommands.length > 0) {
            const cmd = pendingCommands.shift();
            console.log(`[Bridge Server] Gửi lệnh '${cmd.action}' tới node ${body.nodeId}`);
            sendJson(res, 200, { success: true, command: cmd });
        } else {
            sendJson(res, 200, { success: true, command: null });
        }
        return;
    }

    // 4. POST /api/bridge/result (Extension trả kết quả lệnh)
    if (pathname === "/api/bridge/result" && req.method === "POST") {
        const body = await parseJsonBody(req);
        console.log(`[Bridge Server] Nhận kết quả lệnh ${body.action}:`, body);
        
        let logMsg = `Đã thực thi [${body.action}]: `;
        if (body.action === "GET_COOKIES") {
            logMsg += `Lấy được ${body.count} cookie (${body.cookieStr ? body.cookieStr.slice(0, 100) + '...' : ''})`;
        } else if (body.action === "EXECUTE_SCRIPT") {
            logMsg += `Kết quả: ${JSON.stringify(body.data || body.error)}`;
        } else if (body.action === "GET_TABS") {
            logMsg += `Danh sách ${body.tabs ? body.tabs.length : 0} tabs`;
        } else {
            logMsg += body.success ? "Thành công" : `Lỗi: ${body.error}`;
        }

        pushLog(logMsg, body.success ? "success" : "warn");
        sendJson(res, 200, { success: true });
        return;
    }

    // 5. POST /api/bridge/command (Web Controller tạo lệnh)
    if (pathname === "/api/bridge/command" && req.method === "POST") {
        const body = await parseJsonBody(req);
        const cmdId = "cmd_" + Date.now().toString(36);
        const cmd = { id: cmdId, ...body };
        pendingCommands.push(cmd);
        console.log(`[Bridge Server] Tạo lệnh mới:`, cmd);
        sendJson(res, 200, { success: true, cmdId });
        return;
    }

    // 6. GET /api/bridge/status (Web Controller kiểm tra)
    if (pathname === "/api/bridge/status" && req.method === "GET") {
        const now = Date.now();
        const activeNodes = [];
        for (const [id, node] of connectedNodes.entries()) {
            if (now - node.lastSeen < 15000) {
                activeNodes.push(node);
            }
        }
        sendJson(res, 200, { nodes: activeNodes, recentLogs: liveLogs.slice(-25) });
        return;
    }

    // Fallback cho extension kiểm tra ping
    if (pathname === "/api/accounts" && req.method === "GET") {
        sendJson(res, 200, { success: true, accounts: [] });
        return;
    }

    sendJson(res, 404, { error: "Not found" });
});

server.listen(PORT, "127.0.0.1", () => {
    console.log(`=======================================================`);
    console.log(`🌐 BROWSER BRIDGE CONTROLLER SERVER IS RUNNING!`);
    console.log(`📡 URL API:  http://127.0.0.1:${PORT}`);
    console.log(`👉 WEB UI:   http://127.0.0.1:${PORT}`);
    console.log(`=======================================================`);
});
