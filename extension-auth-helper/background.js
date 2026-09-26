/**
 * BROWSER BRIDGE — BACKGROUND SERVICE WORKER
 * Cầu nối trung chuyển lệnh giữa Backend Server (VPS / Local) và Trình duyệt Chrome
 */

let BACKEND_URL = "http://127.0.0.1:9999";
let AUTH_TOKEN = "BW-PROJ-MAIN9999";
let NODE_NAME = "My Chrome Node";
let PROJECT_NAME = "";
let NODE_ID = "bridge_" + Math.random().toString(36).slice(2, 10);
let isConnected = false;
let isPollingBridge = false;
const activeSubProjectIds = new Set();
let activeFlowCount = 0;
let activeFbCount = 0;
let lastLatencyMs = 0;

function getHeaders(extra = {}) {
    const headers = { "Content-Type": "application/json", ...extra };
    if (AUTH_TOKEN) {
        headers["Authorization"] = `Bearer ${AUTH_TOKEN}`;
        headers["X-Sync-Token"] = AUTH_TOKEN;
    }
    return headers;
}

// 1. Khởi tạo cấu hình Node từ Storage
async function initConfig() {
    try {
        const data = await chrome.storage.local.get(["backendUrl", "authToken", "nodeName", "nodeId"]);
        if (data.backendUrl && !data.backendUrl.includes("19823")) {
            BACKEND_URL = data.backendUrl.replace(/\/+$/, "");
        } else {
            BACKEND_URL = "http://127.0.0.1:9999";
            await chrome.storage.local.set({ backendUrl: BACKEND_URL });
        }

        if (data.authToken && data.authToken.trim()) {
            AUTH_TOKEN = data.authToken.trim();
        } else {
            AUTH_TOKEN = "BW-PROJ-MAIN9999";
            await chrome.storage.local.set({ authToken: AUTH_TOKEN });
        }
        if (data.nodeName) NODE_NAME = data.nodeName.trim();

        if (data.nodeId) NODE_ID = data.nodeId;
        else await chrome.storage.local.set({ nodeId: NODE_ID });

        console.log(`[Bridge] Khởi tạo Node: ${NODE_ID} (${NODE_NAME}) -> Target VPS: ${BACKEND_URL}`);
    } catch (e) {
        console.warn("[Bridge] Lỗi đọc storage:", e);
    }
}
initConfig();

chrome.storage.onChanged.addListener((changes) => {
    if (changes.backendUrl) BACKEND_URL = changes.backendUrl.newValue.replace(/\/+$/, "");
    if (changes.authToken) AUTH_TOKEN = (changes.authToken.newValue || "").trim();
    if (changes.nodeName) NODE_NAME = (changes.nodeName.newValue || "My Chrome Node").trim();
    if (changes.nodeId) NODE_ID = changes.nodeId.newValue;
});

// 2. Gửi Heartbeat lên Backend VPS / Localhost
async function sendHeartbeat() {
    try {
        const startTime = performance.now();
        const tabs = await chrome.tabs.query({});
        const activeTab = tabs.find(t => t.active) || null;

        let browserFbUid = "";
        try {
            // Thử lấy cookie c_user từ url https://www.facebook.com
            let fbCookie = await chrome.cookies.get({ url: "https://www.facebook.com", name: "c_user" });
            if (fbCookie && fbCookie.value) {
                browserFbUid = fbCookie.value.trim();
            } else {
                // Thử lấy từ m.facebook.com
                fbCookie = await chrome.cookies.get({ url: "https://m.facebook.com", name: "c_user" });
                if (fbCookie && fbCookie.value) {
                    browserFbUid = fbCookie.value.trim();
                } else {
                    // Quét toàn bộ cookies domain facebook.com
                    const fbCookies = await chrome.cookies.getAll({ domain: "facebook.com" });
                    const cUserCookie = fbCookies.find(c => c.name === "c_user");
                    if (cUserCookie && cUserCookie.value) {
                        browserFbUid = cUserCookie.value.trim();
                    }
                }
            }
        } catch(e) {
            console.warn("[Bridge] Lỗi lấy c_user cookie:", e);
        }

        // Quét thông tin phiên Google Flow đang active trên trình duyệt
        let browserFlowEmail = "";
        let browserFlowProjectId = "";
        let browserFlowLoggedIn = false;
        try {
            const flowOsid = await chrome.cookies.get({ url: "https://flow.google.com", name: "OSID" });
            const googleSid = await chrome.cookies.get({ url: "https://www.google.com", name: "SID" });
            browserFlowLoggedIn = !!((flowOsid && flowOsid.value) || (googleSid && googleSid.value));

            const flowTab = tabs.find(t => t.url && t.url.includes("flow.google.com"));
            if (flowTab && flowTab.url) {
                const pm = flowTab.url.match(/\/project\/([a-f0-9-]+)/i);
                if (pm) browserFlowProjectId = pm[1];
            }

            const cachedFlow = await chrome.storage.local.get(["cachedFlowEmail", "cachedFlowGoogleUid"]);
            browserFlowEmail = cachedFlow.cachedFlowEmail || cachedFlow.cachedFlowGoogleUid || "";

            // Nếu chưa có cached email nhưng tab flow.google.com đang mở, tự động đọc nhanh
            if (!browserFlowEmail && flowTab && flowTab.id && !flowTab.url.startsWith("chrome://")) {
                try {
                    const [res] = await chrome.scripting.executeScript({
                        target: { tabId: flowTab.id },
                        func: () => {
                            try {
                                if (window.WIZ_global_data) {
                                    const em = window.WIZ_global_data.oPEP7c || window.WIZ_global_data.o692Sc;
                                    if (em && String(em).includes("@")) return String(em).trim();
                                }
                            } catch(e) {}
                            try {
                                const av = document.querySelector('img[src*="googleusercontent.com"], a[aria-label*="@"], div[aria-label*="@"], button[aria-label*="@"]');
                                if (av) {
                                    const label = av.getAttribute('aria-label') || av.getAttribute('title') || '';
                                    const m = label.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
                                    if (m) return m[1].trim();
                                }
                            } catch(e) {}
                            return "";
                        }
                    });
                    if (res && res.result) {
                        browserFlowEmail = res.result;
                        await chrome.storage.local.set({ cachedFlowEmail: browserFlowEmail });
                    }
                } catch(e) {}
            }
        } catch(e) {}

        // Quét thông tin tài khoản X (Twitter) đang active trên Chrome
        let browserXUsername = "";
        let browserXUid = "";
        let browserXLoggedIn = false;
        try {
            const xAuth = await chrome.cookies.get({ url: "https://x.com", name: "auth_token" });
            const twAuth = (!xAuth || !xAuth.value) ? await chrome.cookies.get({ url: "https://twitter.com", name: "auth_token" }) : null;
            const activeAuth = (xAuth && xAuth.value) ? xAuth : twAuth;
            browserXLoggedIn = !!(activeAuth && activeAuth.value);

            // twid cookie (numeric user id)
            const xTwid = (await chrome.cookies.get({ url: "https://x.com", name: "twid" })) || (await chrome.cookies.get({ url: "https://twitter.com", name: "twid" }));
            if (xTwid && xTwid.value) {
                const tm = decodeURIComponent(xTwid.value).match(/u=(\d+)/);
                if (tm) browserXUid = tm[1];
            }

            const cachedX = await chrome.storage.local.get(["cachedXUsername", "cachedXUid"]);
            browserXUsername = cachedX.cachedXUsername || "";
            if (!browserXUid && cachedX.cachedXUid) browserXUid = cachedX.cachedXUid;

            // Nếu đang mở tab x.com / twitter.com nhưng chưa có username, đọc nhanh từ tab
            if (!browserXUsername && browserXLoggedIn) {
                const xTab = tabs.find(t => t.url && (t.url.includes("x.com") || t.url.includes("twitter.com")));
                if (xTab && xTab.id && !xTab.url.startsWith("chrome://")) {
                    try {
                        const [xRes] = await chrome.scripting.executeScript({
                            target: { tabId: xTab.id },
                            func: () => {
                                try {
                                    const prof = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
                                    if (prof) {
                                        const m = (prof.getAttribute("href") || "").match(/^\/([a-zA-Z0-9_]+)/);
                                        if (m && m[1] && !["home", "explore", "notifications", "messages"].includes(m[1].toLowerCase())) return m[1];
                                    }
                                    const btn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
                                    if (btn) {
                                        for (const s of btn.querySelectorAll('span, div[dir="ltr"]')) {
                                            const t = (s.innerText || '').trim();
                                            if (t.startsWith('@')) return t.substring(1);
                                        }
                                    }
                                } catch(e) {}
                                return "";
                            }
                        });
                        if (xRes && xRes.result) {
                            browserXUsername = xRes.result;
                            chrome.storage.local.set({ cachedXUsername: browserXUsername });
                        }
                    } catch(e) {}
                }
            }
        } catch(e) {}

        const payload = {
            nodeId: NODE_ID,
            nodeName: NODE_NAME,
            backendUrl: BACKEND_URL,
            status: "online",
            tabCount: tabs.length,
            activeTab: activeTab ? { id: activeTab.id, url: activeTab.url, title: activeTab.title } : null,
            browserFbUid: browserFbUid,
            browserFlowEmail: browserFlowEmail,
            browserFlowProjectId: browserFlowProjectId,
            browserFlowLoggedIn: browserFlowLoggedIn,
            browserXUsername: browserXUsername,
            browserXUid: browserXUid,
            browserXLoggedIn: browserXLoggedIn,
            isFlowBusy: activeFlowCount > 0,
            isFbBusy: activeFbCount > 0,
            busySubProjects: Array.from(activeSubProjectIds),
            timestamp: Date.now()
        };

        const res = await fetch(`${BACKEND_URL}/api/bridge/heartbeat`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(5000)
        });

        lastLatencyMs = Math.round(performance.now() - startTime);

        if (res.ok) {
            isConnected = true;
            const data = await res.json();
            if (data.reloadExtension) {
                console.log("[Bridge] Nhận lệnh reload extension từ server...");
                chrome.runtime.reload();
                return;
            }
            if (data.projectName) {
                PROJECT_NAME = data.projectName;
            }
            if (data.hasPendingCommands) {
                _currentHeartbeatInterval = 1200;
                pollAndExecuteCommand();
            } else if (activeSubProjectIds.size > 0) {
                _currentHeartbeatInterval = 1500;
            } else {
                _currentHeartbeatInterval = 3000;
            }
        } else {
            isConnected = false;
            _currentHeartbeatInterval = 5000;
        }
    } catch (err) {
        isConnected = false;
    }
}

// =========================================================================
// FACEBOOK DIRECT GRAPHQL POST & SEEDING ENGINE (Adapted from autofb)
// =========================================================================

function ensureTabLoaded(tabId, timeoutMs = 8000) {
    return new Promise(async (resolve) => {
        try {
            const tab = await chrome.tabs.get(tabId);
            if (tab && tab.status === "complete") {
                return resolve(true);
            }
        } catch(e) {}

        let timer = null;
        const listener = (tid, changeInfo) => {
            if (tid === tabId && changeInfo.status === "complete") {
                clearTimeout(timer);
                chrome.tabs.onUpdated.removeListener(listener);
                resolve(true);
            }
        };
        chrome.tabs.onUpdated.addListener(listener);
        timer = setTimeout(() => {
            chrome.tabs.onUpdated.removeListener(listener);
            resolve(false);
        }, timeoutMs);
    });
}

async function _uploadMediaToFacebook(tabId, fileBase64, fileName, mimeType) {
    try {
        const results = await chrome.scripting.executeScript({
            target: { tabId },
            func: async (b64, fName, fMime) => {
                try {
                    const byteChars = atob(b64);
                    const byteArray = new Uint8Array(byteChars.length);
                    for (let i = 0; i < byteChars.length; i++) byteArray[i] = byteChars.charCodeAt(i);
                    const blob = new Blob([byteArray], { type: fMime });
                    const isVideo = (fMime && fMime.startsWith("video/")) || (fName && fName.match(/\.(mp4|mov|avi|mkv|webm)$/i));

                    let fb_dtsg = "";
                    const html = document.documentElement.innerHTML || "";
                    if (window.DTSGInitialData && window.DTSGInitialData.token) fb_dtsg = window.DTSGInitialData.token;
                    else if (window.DTSGInitData && window.DTSGInitData.token) fb_dtsg = window.DTSGInitData.token;
                    if (!fb_dtsg) {
                        const m = html.match(/"token"\s*:\s*"([^"]{20,})"\s*,\s*"async_get_token"/);
                        if (m && m[1]) fb_dtsg = m[1];
                    }

                    let lsd = "";
                    let jazoest = "";
                    let spinR = "";
                    let spinB = "";
                    let spinT = "";
                    let hsi = "";

                    const lsdM = html.match(/\["LSD",\[\],\{"token":"([^"]+)"/) || html.match(/"lsd":"([^"]+)"/);
                    if (lsdM) lsd = lsdM[1];
                    const jazoM = html.match(/jazoest=(\d+)/);
                    if (jazoM) jazoest = jazoM[1];
                    const spinM = html.match(/"__spin_t":(\d+),"__spin_r":(\d+),"__spin_b":"([^"]+)","__hsi":"([^"]+)"/);
                    if (spinM) { spinT = spinM[1]; spinR = spinM[2]; spinB = spinM[3]; hsi = spinM[4]; }

                    const cUserMatch = document.cookie.match(/c_user=(\d+)/) || html.match(/"USER_ID":"(\d+)"/) || html.match(/"ACCOUNT_ID":"(\d+)"/);
                    const userId = cUserMatch ? cUserMatch[1] : "";

                    if (!userId || !fb_dtsg) {
                        return { success: false, error: "Không tìm thấy token fb_dtsg hoặc UID người dùng Facebook" };
                    }

                    // ===== CHUYÊN XỬ LÝ VIDEO: NATIVE VUPLOAD PROTOCOL (START -> RUPLOAD -> RECEIVE) =====
                    if (isVideo) {
                        console.log("🎬 [Background] Phát hiện file Video — Sử dụng giao thức native vupload-edge");
                        const waterfallId = (crypto.randomUUID ? crypto.randomUUID() : (([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g,c=>(c^crypto.getRandomValues(new Uint8Array(1))[0]&15>>c/4).toString(16))));
                        const fileSize = byteArray.length;
                        const fileExt = (fName.split(".").pop() || "mp4").toLowerCase();

                        // Các tham số chuẩn Facebook web
                        const fbParams = new URLSearchParams();
                        fbParams.append("__aaid", "0");
                        fbParams.append("__user", userId);
                        fbParams.append("__a", "1");
                        fbParams.append("__comet_req", "15");
                        fbParams.append("fb_dtsg", fb_dtsg);
                        if (jazoest) fbParams.append("jazoest", jazoest);
                        if (lsd) fbParams.append("lsd", lsd);
                        if (spinR) fbParams.append("__spin_r", spinR);
                        if (spinB) fbParams.append("__spin_b", spinB);
                        if (spinT) fbParams.append("__spin_t", spinT);
                        if (hsi) fbParams.append("__hsi", hsi);
                        fbParams.append("dpr", "1");
                        fbParams.append("__ccg", "EXCELLENT");
                        if (spinR) fbParams.append("__rev", spinR);

                        // --- BƯỚC 1: START (Khởi tạo phiên tải video) ---
                        const startParams = new URLSearchParams(fbParams);
                        startParams.append("waterfall_id", waterfallId);
                        startParams.append("target_id", userId);
                        startParams.append("source", "composer");
                        startParams.append("composer_entry_point_ref", "timeline");
                        startParams.append("supports_chunking", "true");
                        startParams.append("supports_file_api", "true");
                        startParams.append("file_size", fileSize.toString());
                        startParams.append("file_extension", fileExt.toUpperCase());
                        startParams.append("partition_start_offset", "0");
                        startParams.append("partition_end_offset", fileSize.toString());
                        startParams.append("has_file_been_replaced", "false");

                        const startResp = await fetch(`https://vupload-edge.facebook.com/ajax/video/upload/requests/start/?av=${userId}&__a=1`, {
                            method: "POST",
                            body: startParams.toString(),
                            headers: {
                                "Content-Type": "application/x-www-form-urlencoded",
                                "X_FB_VIDEO_WATERFALL_ID": waterfallId,
                            },
                            credentials: "include",
                        });

                        const startText = await startResp.text();
                        const startClean = startText.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                        let startData = null;
                        try { startData = JSON.parse(startClean); } catch(e) {}
                        const videoId = startData?.payload?.video_id;
                        const uploadSessionId = startData?.payload?.upload_session_id;
                        const chunkEnd = startData?.payload?.end_offset || fileSize;

                        if (!videoId || !uploadSessionId) {
                            return { success: false, error: "vupload start thất bại: " + startClean.slice(0, 200) };
                        }

                        // --- BƯỚC 2: RUPLOAD (Tải luồng nhị phân video lên cụm máy chủ Facebook) ---
                        const sessionHash = Array.from(crypto.getRandomValues(new Uint8Array(16))).map(b => b.toString(16).padStart(2,"0")).join("");
                        const ruploadUrl = `https://rupload.facebook.com/fb_video/${sessionHash}-0-${chunkEnd}?` + fbParams.toString();

                        const ruploadHeaders = {
                            "X-Entity-Name": fName,
                            "X-Entity-Length": fileSize.toString(),
                            "X-Entity-Type": fMime || "video/mp4",
                            "X-Total-Asset-Size": fileSize.toString(),
                            "Composer_Session_Id": waterfallId,
                            "Id": uploadSessionId,
                            "Product_Media_Id": videoId,
                            "Offset": "0",
                            "Start_Offset": "0",
                            "End_Offset": chunkEnd.toString(),
                        };

                        let ruploadResp = await fetch(ruploadUrl, {
                            method: "POST",
                            body: blob,
                            headers: ruploadHeaders,
                            credentials: "include",
                        });

                        if (!ruploadResp.ok) {
                            // Dự phòng endpoint edge
                            const fallbackUrl = `https://rupload-edge.facebook.com/fb_video/${sessionHash}-0-${chunkEnd}?` + fbParams.toString();
                            try {
                                ruploadResp = await fetch(fallbackUrl, {
                                    method: "POST",
                                    body: blob,
                                    headers: ruploadHeaders,
                                    credentials: "include",
                                });
                            } catch(e) {}
                        }

                        const ruploadText = await ruploadResp.text();
                        let ruploadHash = "";
                        try {
                            const ruploadData = JSON.parse(ruploadText);
                            ruploadHash = ruploadData?.h || "";
                        } catch(e) {}

                        // --- BƯỚC 3: RECEIVE (Xác nhận video upload hoàn tất & gắn chunk) ---
                        const receiveParams = new URLSearchParams(fbParams);
                        receiveParams.append("waterfall_id", waterfallId);
                        receiveParams.append("target_id", userId);
                        receiveParams.append("video_id", videoId);
                        receiveParams.append("source", "composer");
                        receiveParams.append("composer_entry_point_ref", "timeline");
                        receiveParams.append("supports_chunking", "true");
                        receiveParams.append("supports_upload_service", "true");
                        receiveParams.append("partition_start_offset", "0");
                        receiveParams.append("partition_end_offset", fileSize.toString());
                        receiveParams.append("start_offset", "0");
                        receiveParams.append("end_offset", fileSize.toString());
                        receiveParams.append("upload_speed", Math.round(fileSize / 1.5).toString());
                        if (ruploadHash) {
                            receiveParams.append("fbuploader_video_file_chunk", ruploadHash);
                        }
                        receiveParams.append("has_file_been_replaced", "false");

                        const receiveResp = await fetch(`https://vupload-edge.facebook.com/ajax/video/upload/requests/receive/?av=${userId}&__a=1`, {
                            method: "POST",
                            body: receiveParams.toString(),
                            headers: {
                                "Content-Type": "application/x-www-form-urlencoded",
                                "X_FB_VIDEO_WATERFALL_ID": waterfallId,
                            },
                            credentials: "include",
                        });

                        const receiveText = await receiveResp.text();
                        const receiveClean = receiveText.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                        let receiveData = null;
                        try { receiveData = JSON.parse(receiveClean); } catch(e) {}
                        const confirmedEnd = receiveData?.payload?.end_offset;

                        if (confirmedEnd !== undefined || receiveResp.ok) {
                            return { success: true, mediaId: String(videoId), isVideo: true };
                        }
                        return { success: false, error: "vupload receive thất bại: " + receiveClean.slice(0, 200) };
                    }

                    // ===== CHUYÊN XỬ LÝ HÌNH ẢNH: REACT COMPOSER PHOTO UPLOAD =====
                    const urlParams = new URLSearchParams();
                    urlParams.append("av", userId);
                    urlParams.append("__aaid", "0");
                    urlParams.append("__user", userId);
                    urlParams.append("__a", "1");
                    urlParams.append("__req", Math.floor(Math.random()*100).toString(36));
                    urlParams.append("__hs", hsi || "");
                    urlParams.append("dpr", "1");
                    urlParams.append("__ccg", "GOOD");
                    urlParams.append("__rev", spinR || "1048159918");
                    urlParams.append("__hsi", hsi || "");
                    urlParams.append("__comet_req", "15");
                    urlParams.append("fb_dtsg", fb_dtsg);
                    if (jazoest) urlParams.append("jazoest", jazoest);
                    if (lsd) urlParams.append("lsd", lsd);
                    if (spinR) urlParams.append("__spin_r", spinR);
                    if (spinB) urlParams.append("__spin_b", spinB);
                    if (spinT) urlParams.append("__spin_t", spinT);

                    const formData = new FormData();
                    formData.append("farr", blob, fName);
                    formData.append("file", blob, fName);
                    formData.append("photo", blob, fName);
                    formData.append("source", "8");
                    formData.append("profile_id", userId);
                    formData.append("waterfallxapp", "comet");
                    formData.append("upload_speed", "0");
                    formData.append("fb_dtsg", fb_dtsg);

                    const uploadUrl = "https://upload.facebook.com/ajax/react_composer/attachments/photo/upload?" + urlParams.toString();

                    const resp = await fetch(uploadUrl, {
                        method: "POST",
                        body: formData,
                        credentials: "include"
                    });

                    const text = await resp.text();
                    const cleanUpload = text.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                    const idPatterns = [
                        /"photoID"\s*:\s*"?(\d+)"?/,
                        /"photo_id"\s*:\s*"?(\d+)"?/,
                        /"media_id"\s*:\s*"?(\d+)"?/,
                        /"fbid"\s*:\s*"?(\d+)"?/,
                        /"id"\s*:\s*"?(\d+)"?/
                    ];
                    for (const p of idPatterns) {
                        const m = cleanUpload.match(p);
                        if (m && m[1]) return { success: true, mediaId: m[1] };
                    }
                    try {
                        const parsed = JSON.parse(cleanUpload);
                        const mid = parsed?.payload?.photoID || parsed?.payload?.fbid || parsed?.payload?.media_id || parsed?.payload?.id;
                        if (mid) return { success: true, mediaId: String(mid) };
                    } catch(e) {}
                    return { success: false, error: "Không tìm thấy photo ID trong phản hồi Facebook" };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            },
            args: [fileBase64, fileName, mimeType]
        });
        return results?.[0]?.result || { success: false, error: "Không thể upload media" };
    } catch(e) {
        return { success: false, error: e.message };
    }
}

// =========================================================================
// FACEBOOK RESHARE TO STORY ENGINE (useCometFeedToStoryReshare_FeedToStoryMutation)
// Trích xuất chính xác theo file C:\Users\Admin\Desktop\project\AUTOPOSTFB\DATA\sharetinfacebook.har
// =========================================================================

async function _sharePostToStory(tabId, postInfo, fallbackActorId) {
    try {
        const results = await chrome.scripting.executeScript({
            target: { tabId },
            func: async (pUrl, pId, numPid, sId, actId, fbActorId) => {
                try {
                    let fb_dtsg = "";
                    let lsd = "";
                    let jazoest = "";
                    let spinR = "";
                    let spinB = "";
                    let spinT = "";

                    for (let attempt = 0; attempt < 5; attempt++) {
                        const html = document.documentElement.innerHTML || "";
                        try {
                            if (window.DTSGInitialData && window.DTSGInitialData.token) fb_dtsg = window.DTSGInitialData.token;
                            else if (window.DTSGInitData && window.DTSGInitData.token) fb_dtsg = window.DTSGInitData.token;
                            else if (window.__DTSGInitialData && window.__DTSGInitialData.token) fb_dtsg = window.__DTSGInitialData.token;
                        } catch(e) {}

                        if (!fb_dtsg && typeof require !== "undefined") {
                            try {
                                const mod = require("DTSGInitData") || require("DTSGInitialData");
                                if (mod && mod.token) fb_dtsg = mod.token;
                                else if (mod && typeof mod.getAsyncParams === "function") {
                                    const params = mod.getAsyncParams();
                                    if (params && params.fb_dtsg) fb_dtsg = params.fb_dtsg;
                                }
                            } catch(e) {}
                        }

                        if (!fb_dtsg) {
                            const dtsgPatterns = [
                                /\["DTSGInitialData",\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"/,
                                /\["DTSGInitData",\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"/,
                                /"token"\s*:\s*"([^"]{20,})"\s*,\s*"async_get_token"/,
                                /name="fb_dtsg"[^>]*value="([^"]+)"/
                            ];
                            for (const p of dtsgPatterns) {
                                const m = html.match(p);
                                if (m && m[1]) { fb_dtsg = m[1]; break; }
                            }
                        }

                        if (!lsd) {
                            try {
                                if (window.LSD && window.LSD.token) lsd = window.LSD.token;
                            } catch(e) {}
                            if (!lsd) {
                                const m = html.match(/"lsd"\s*:\s*"([^"]+)"/);
                                if (m && m[1]) lsd = m[1];
                            }
                        }

                        if (fb_dtsg) break;
                        await new Promise(r => setTimeout(r, 300));
                    }

                    const finalHtml = document.documentElement.innerHTML || "";
                    const jazoM = finalHtml.match(/jazoest=(\d+)/);
                    if (jazoM) jazoest = jazoM[1];
                    const spinM = finalHtml.match(/"__spin_t":(\d+),"__spin_r":(\d+),"__spin_b":"([^"]+)","__hsi":"([^"]+)"/);
                    if (spinM) {
                        spinT = spinM[1]; spinR = spinM[2]; spinB = spinM[3];
                    }

                    let currentActorId = actId || "";
                    if (!currentActorId) {
                        try {
                            if (typeof require !== "undefined") {
                                const ca = require("CometCurrentActor");
                                if (ca) currentActorId = ca.actorId || ca.id || "";
                            }
                        } catch(e) {}
                    }
                    if (!currentActorId) {
                        try {
                            if (window.CurrentUserInitialData) currentActorId = window.CurrentUserInitialData.ACCOUNT_ID || window.CurrentUserInitialData.USER_ID || "";
                        } catch(e) {}
                    }
                    if (!currentActorId) {
                        const cUserMatch = document.cookie.match(/c_user=(\d+)/);
                        if (cUserMatch && cUserMatch[1]) currentActorId = cUserMatch[1];
                    }
                    if (!currentActorId) currentActorId = fbActorId || "";

                    if (!fb_dtsg || !currentActorId) {
                        return { success: false, error: "Thiếu token fb_dtsg hoặc actorId" };
                    }

                    if (!jazoest) {
                        jazoest = "2";
                        for (let i = 0; i < fb_dtsg.length; i++) jazoest += fb_dtsg.charCodeAt(i);
                    }

                    const candidateLinkableIds = [];

                    // Bước 1: Tra cứu menu chia sẻ CometUFIShareActionLinkMenuQuery (Entry 279 trong sharetinfacebook.har)
                    if (pUrl) {
                        try {
                            const menuParams = new URLSearchParams();
                            menuParams.append("av", currentActorId);
                            menuParams.append("__user", currentActorId);
                            menuParams.append("__a", "1");
                            menuParams.append("fb_dtsg", fb_dtsg);
                            menuParams.append("jazoest", jazoest);
                            menuParams.append("lsd", lsd);
                            menuParams.append("__spin_r", spinR || "1048289394");
                            menuParams.append("__spin_b", spinB || "trunk");
                            menuParams.append("__spin_t", spinT || String(Math.floor(Date.now()/1000)));
                            menuParams.append("fb_api_caller_class", "RelayModern");
                            menuParams.append("fb_api_req_friendly_name", "CometUFIShareActionLinkMenuQuery");
                            menuParams.append("variables", JSON.stringify({
                                feedLocation: "POST_PERMALINK_DIALOG",
                                hasParentStory: false,
                                qe_optional_share_to_page: true,
                                shareableParams: { url: pUrl },
                                storyParams: {}
                            }));
                            menuParams.append("server_timestamps", "true");
                            menuParams.append("doc_id", "26716464711295397");

                            const mResp = await fetch("/api/graphql/", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "X-FB-Friendly-Name": "CometUFIShareActionLinkMenuQuery",
                                    "X-FB-LSD": lsd,
                                    "X-ASBD-ID": "359341"
                                },
                                body: menuParams.toString(),
                                credentials: "include"
                            });

                            if (mResp.ok) {
                                const mText = await mResp.text();
                                const mClean = mText.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                                const mData = JSON.parse(mClean);
                                const shareItems = mData?.data?.link?.default_share_items_firstBatch || [];
                                for (const item of shareItems) {
                                    if (item.__typename === "ShareNowToStoryShareMenuItem" && item.link_preview_root?.story?.id) {
                                        const foundStoryId = item.link_preview_root.story.id;
                                        if (foundStoryId && !candidateLinkableIds.includes(foundStoryId)) {
                                            candidateLinkableIds.push(foundStoryId);
                                        }
                                        break;
                                    }
                                }
                            }
                        } catch(menuErr) {
                            console.warn("[Bridge] Lỗi tra cứu CometUFIShareActionLinkMenuQuery:", menuErr);
                        }
                    }

                    // Bước 2: Thêm các định danh dự phòng (đã kiểm chứng trùng khớp 100% với HAR)
                    if (sId && String(sId).startsWith("Uzpf") && !candidateLinkableIds.includes(String(sId))) {
                        candidateLinkableIds.push(String(sId));
                    }

                    const effectivePid = numPid || (pId && !String(pId).startsWith("pfbid") ? pId : "");
                    if (effectivePid) {
                        try {
                            const calculated = btoa(`S:_I${currentActorId}:${effectivePid}:${effectivePid}`);
                            if (!candidateLinkableIds.includes(calculated)) candidateLinkableIds.push(calculated);
                        } catch(e) {}
                    }

                    if (sId && !candidateLinkableIds.includes(String(sId))) {
                        try {
                            const calculatedFromStory = btoa(`S:_I${currentActorId}:${sId}:${sId}`);
                            if (!candidateLinkableIds.includes(calculatedFromStory)) candidateLinkableIds.push(calculatedFromStory);
                        } catch(e) {}
                    }

                    if (pId && !candidateLinkableIds.length) {
                        try {
                            const calculatedFromPId = btoa(`S:_I${currentActorId}:${pId}:${pId}`);
                            if (!candidateLinkableIds.includes(calculatedFromPId)) candidateLinkableIds.push(calculatedFromPId);
                        } catch(e) {}
                    }

                    if (candidateLinkableIds.length === 0) {
                        return { success: false, error: "Không xác định được linkable_id của bài viết để chia sẻ lên tin" };
                    }

                    // Bước 3: Tìm doc_id cho useCometFeedToStoryReshare_FeedToStoryMutation
                    const storyMutationDocIds = [];
                    try {
                        const scripts = Array.from(document.scripts || []);
                        for (const s of scripts) {
                            const content = s.textContent || s.innerHTML || "";
                            if (content.includes("useCometFeedToStoryReshare_FeedToStoryMutation")) {
                                const matches = content.matchAll(/"doc_id"\s*:\s*"(\d{14,})"/g);
                                for (const m of matches) {
                                    if (m && m[1] && !storyMutationDocIds.includes(m[1])) storyMutationDocIds.push(m[1]);
                                }
                            }
                        }
                    } catch(e) {}
                    if (!storyMutationDocIds.includes("28132359363043002")) {
                        storyMutationDocIds.push("28132359363043002");
                    }

                    // Bước 4: Thực thi useCometFeedToStoryReshare_FeedToStoryMutation (Entry 332 trong sharetinfacebook.har)
                    let lastError = "";
                    for (const linkId of candidateLinkableIds) {
                        const variables = {
                            input: {
                                attachments: [
                                    {
                                        link: {
                                            internal_linkable_id: linkId
                                        }
                                    }
                                ],
                                audiences: [
                                    {
                                        stories: {
                                            self: {
                                                target_id: String(currentActorId)
                                            }
                                        }
                                    }
                                ],
                                navigation_data: {
                                    attribution_id_v2: `CometSinglePostDialogRoot.react,comet.post.single_dialog,unexpected,${Date.now()},932851,,,;ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,via_cold_start,${Date.now()},730245,190055527696468,229#230#301,`
                                },
                                source: "WWW",
                                tracking: [null],
                                actor_id: String(currentActorId),
                                client_mutation_id: "1"
                            },
                            scale: 1,
                            bucketsToFetch: 8,
                            blur: 10,
                            trayType: null,
                            isFbNotesIncluded: false,
                            __relay_internal__pv__StoriesTrayTileCoverImageWidthrelayprovider: 110,
                            __relay_internal__pv__StoriesTrayTileCoverImageHeightrelayprovider: 160,
                            __relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider: true,
                            __relay_internal__pv__StoriesTrayTileShouldSkipPrefetchImageURIrelayprovider: false,
                            __relay_internal__pv__StoriesTrayProfessionalInset3DEnabledrelayprovider: true,
                            __relay_internal__pv__StoriesShouldEnableVideoAutoplayrelayprovider: true,
                            __relay_internal__pv__StoriesShouldEnablePhotosensitiveContentWarningrelayprovider: false
                        };

                        for (const docId of storyMutationDocIds) {
                            const params = new URLSearchParams();
                            params.append("av", currentActorId);
                            params.append("__aaid", "0");
                            params.append("__user", currentActorId);
                            params.append("__a", "1");
                            params.append("__req", Math.floor(Math.random()*100).toString(36));
                            params.append("dpr", "1");
                            params.append("__ccg", "GOOD");
                            params.append("__comet_req", "15");
                            params.append("fb_dtsg", fb_dtsg);
                            params.append("jazoest", jazoest);
                            params.append("lsd", lsd);
                            params.append("__spin_r", spinR || "1048289394");
                            params.append("__spin_b", spinB || "trunk");
                            params.append("__spin_t", spinT || String(Math.floor(Date.now()/1000)));
                            params.append("fb_api_caller_class", "RelayModern");
                            params.append("fb_api_req_friendly_name", "useCometFeedToStoryReshare_FeedToStoryMutation");
                            params.append("variables", JSON.stringify(variables));
                            params.append("server_timestamps", "true");
                            params.append("doc_id", docId);

                            const resp = await fetch("/api/graphql/", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "X-FB-Friendly-Name": "useCometFeedToStoryReshare_FeedToStoryMutation",
                                    "X-FB-LSD": lsd,
                                    "X-ASBD-ID": "359341"
                                },
                                body: params.toString(),
                                credentials: "include"
                            });

                            if (resp.ok) {
                                const text = await resp.text();
                                const clean = text.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                                if (clean.includes('"story_create"') || clean.includes('unified_stories_buckets') || clean.includes('StoryOverlayResharedPost')) {
                                    return { success: true, linkableId: linkId, docId };
                                }
                                try {
                                    const parsed = JSON.parse(clean);
                                    if (parsed.errors && parsed.errors.length > 0) {
                                        lastError = parsed.errors[0].message || "";
                                    }
                                } catch(e) {}
                            } else {
                                lastError = `HTTP ${resp.status}`;
                            }
                        }
                    }

                    return { success: false, error: lastError || "Không thể chia sẻ lên tin" };
                } catch(err) {
                    return { success: false, error: err.message };
                }
            },
            args: [postInfo.postUrl || "", postInfo.postId || "", postInfo.numericPostId || "", postInfo.storyId || "", postInfo.actorId || "", fallbackActorId || ""]
        });

        return results?.[0]?.result || { success: false, error: "Không nhận được phản hồi từ tab Facebook" };
    } catch(e) {
        return { success: false, error: e.message };
    }
}

async function _executeFbPost(payload, updateStep) {
    try {
        const postType = payload.postType || "post";
        await updateStep("🚀 1/4: Đã nhận lệnh, đang mở hoặc tìm tab Facebook...");

        let targetFbUrl = payload.targetUrl;
        if (!targetFbUrl || !targetFbUrl.includes("facebook.com")) {
            if (postType === "reel") {
                targetFbUrl = "https://www.facebook.com/reels/create";
            } else if (postType === "story") {
                targetFbUrl = "https://www.facebook.com/stories/create";
            } else {
                targetFbUrl = "https://www.facebook.com";
            }
        }

        const tabs = await chrome.tabs.query({});
        let targetTab = tabs.find(t => t.active && t.url && t.url.includes("facebook.com")) || tabs.find(t => t.url && t.url.includes("facebook.com"));
        if (!targetTab) {
            targetTab = await chrome.tabs.create({ url: targetFbUrl, active: false });
        }

        if (!targetTab || !targetTab.id) {
            const err = "Không thể mở hoặc kết nối tới tab Facebook";
            await updateStep(`❌ Lỗi: ${err}`);
            return { success: false, error: err };
        }

        await ensureTabLoaded(targetTab.id);
        await new Promise(r => setTimeout(r, 400));

        // Fetch media from URL if base64 data not provided
        if (!payload.mediaData && payload.mediaUrl) {
            try {
                let fetchMediaUrl = payload.mediaUrl;
                if (fetchMediaUrl.startsWith("/")) {
                    fetchMediaUrl = `${BACKEND_URL}${fetchMediaUrl}`;
                }
                await updateStep(`📥 Đang nạp media từ link: ${fetchMediaUrl.slice(0, 45)}...`);
                const res = await fetch(fetchMediaUrl);
                if (res.ok) {
                    const blob = await res.blob();
                    const b64 = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            const result = reader.result;
                            const comma = result.indexOf(",");
                            resolve(comma !== -1 ? result.slice(comma + 1) : result);
                        };
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                    const isVideoUrl = !!(payload.mediaUrl.match(/\.(mp4|mov|avi|mkv|webm)/i) || postType === "video" || postType === "reel");
                    payload.mediaData = {
                        base64: b64,
                        fileName: isVideoUrl ? "video_downloaded.mp4" : "media_downloaded.jpg",
                        mimeType: blob.type || (isVideoUrl ? "video/mp4" : "image/jpeg")
                    };
                }
            } catch(e) {
                console.warn("[Bridge] Fetch mediaUrl error:", e);
            }
        }

        if (postType === "video" || postType === "reel") {
            if (payload.mediaData && (!payload.mediaData.mimeType || payload.mediaData.mimeType === "image/jpeg" || payload.mediaData.mimeType === "application/octet-stream")) {
                payload.mediaData.mimeType = "video/mp4";
            }
        }

        // Upload Media
        let uploadedMediaId = null;
        if (payload.mediaData && payload.mediaData.base64) {
            await updateStep(`📸 2/4: Đang tải tệp lên Facebook (${payload.mediaData.fileName || 'media'})...`);
            const uploadResult = await _uploadMediaToFacebook(
                targetTab.id,
                payload.mediaData.base64,
                payload.mediaData.fileName || "upload_file",
                payload.mediaData.mimeType || "image/jpeg"
            );
            if (uploadResult && uploadResult.success) {
                uploadedMediaId = uploadResult.mediaId;
                await updateStep(`✅ 2/4: Tải tệp thành công! ID=${uploadedMediaId}`);
            } else {
                await updateStep(`⚠️ 2/4: Upload Media thất bại (${uploadResult?.error || 'Unknown'}), tiếp tục đăng text...`);
            }
        }

        let fallbackActorId = "";
        try {
            const cCookie = await chrome.cookies.get({ url: "https://www.facebook.com", name: "c_user" });
            if (cCookie && cCookie.value) fallbackActorId = cCookie.value;
        } catch(e) {}

        const isVideo = (payload.mediaData && ((payload.mediaData.mimeType && payload.mediaData.mimeType.startsWith("video/")) || (payload.mediaData.fileName && payload.mediaData.fileName.match(/\.(mp4|mov|avi|mkv|webm)$/i)))) || postType === "video" || postType === "reel";

        // Direct GraphQL Mutation
        await updateStep(`⚡ 3/4: Đang tạo bài viết qua Facebook GraphQL Direct API...`);
        const effectiveMediaId = uploadedMediaId || null;
        const shareToFeed = payload.shareToFeed !== false;

        const graphqlResults = await chrome.scripting.executeScript({
            target: { tabId: targetTab.id },
            func: async (postContent, postType, mediaId, isVideo, fallbackActorId, targetType, targetId, shareToFeed = true) => {
                try {
                    let fb_dtsg = "";
                    let lsd = "";
                    let jazoest = "";
                    let spinR = "";
                    let spinB = "";
                    let spinT = "";

                    for (let attempt = 0; attempt < 8; attempt++) {
                        const html = document.documentElement.innerHTML || "";
                        try {
                            if (window.DTSGInitialData && window.DTSGInitialData.token) fb_dtsg = window.DTSGInitialData.token;
                            else if (window.DTSGInitData && window.DTSGInitData.token) fb_dtsg = window.DTSGInitData.token;
                            else if (window.__DTSGInitialData && window.__DTSGInitialData.token) fb_dtsg = window.__DTSGInitialData.token;
                        } catch(e) {}

                        if (!fb_dtsg && typeof require !== "undefined") {
                            try {
                                const mod = require("DTSGInitData") || require("DTSGInitialData");
                                if (mod && mod.token) fb_dtsg = mod.token;
                                else if (mod && typeof mod.getAsyncParams === "function") {
                                    const params = mod.getAsyncParams();
                                    if (params && params.fb_dtsg) fb_dtsg = params.fb_dtsg;
                                }
                            } catch(e) {}
                        }

                        if (!fb_dtsg) {
                            const dtsgPatterns = [
                                /\["DTSGInitialData",\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"/,
                                /\["DTSGInitData",\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"/,
                                /"token"\s*:\s*"([^"]{20,})"\s*,\s*"async_get_token"/,
                                /name="fb_dtsg"[^>]*value="([^"]+)"/
                            ];
                            for (const p of dtsgPatterns) {
                                const m = html.match(p);
                                if (m && m[1]) { fb_dtsg = m[1]; break; }
                            }
                        }

                        if (!lsd) {
                            try {
                                if (window.LSD && window.LSD.token) lsd = window.LSD.token;
                            } catch(e) {}
                            if (!lsd) {
                                const m = html.match(/"lsd"\s*:\s*"([^"]+)"/);
                                if (m && m[1]) lsd = m[1];
                            }
                        }

                        if (fb_dtsg) break;
                        await new Promise(r => setTimeout(r, 400));
                    }

                    const finalHtml = document.documentElement.innerHTML || "";
                    const jazoM = finalHtml.match(/jazoest=(\d+)/);
                    if (jazoM) jazoest = jazoM[1];

                    const spinM = finalHtml.match(/"__spin_t":(\d+),"__spin_r":(\d+),"__spin_b":"([^"]+)","__hsi":"([^"]+)"/);
                    if (spinM) {
                        spinT = spinM[1]; spinR = spinM[2]; spinB = spinM[3];
                    }

                    let actorId = "";
                    try {
                        if (typeof require !== "undefined") {
                            const ca = require("CometCurrentActor");
                            if (ca) actorId = ca.actorId || ca.id || "";
                        }
                    } catch(e) {}
                    if (!actorId) {
                        try {
                            if (window.CurrentUserInitialData) actorId = window.CurrentUserInitialData.ACCOUNT_ID || window.CurrentUserInitialData.USER_ID || "";
                        } catch(e) {}
                    }
                    if (!actorId) {
                        const cUserMatch = document.cookie.match(/c_user=(\d+)/);
                        if (cUserMatch && cUserMatch[1]) actorId = cUserMatch[1];
                    }
                    if (!actorId) actorId = fallbackActorId || "";

                    if (!fb_dtsg || !actorId) {
                        return { success: false, error: "Không tìm thấy token fb_dtsg hoặc UID (actorId) của tài khoản" };
                    }

                    if (!jazoest) {
                        jazoest = "2";
                        for (let i = 0; i < fb_dtsg.length; i++) jazoest += fb_dtsg.charCodeAt(i);
                    }

                    const isProfile = targetType === "profile";
                    const isGroup = targetType === "group";
                    const isPage = targetType === "page";

                    let surface = "timeline";
                    let feedLoc = "TIMELINE";
                    let renderLoc = "timeline";

                    if (isGroup && targetId) {
                        surface = "group"; feedLoc = "GROUP"; renderLoc = "group";
                    } else if (isPage) {
                        surface = "page_timeline"; feedLoc = "TIMELINE"; renderLoc = "page_timeline";
                    } else {
                        // Profile
                        surface = "timeline";
                        feedLoc = "TIMELINE";
                        renderLoc = "timeline";
                    }

                    const liveDocIds = [];
                    try {
                        const scripts = Array.from(document.scripts || []);
                        for (const s of scripts) {
                            const content = s.textContent || s.innerHTML || "";
                            if (content.includes("ComposerStoryCreateMutation")) {
                                const matches = content.matchAll(/"doc_id"\s*:\s*"(\d{14,})"/g);
                                for (const m of matches) {
                                    if (m && m[1] && !liveDocIds.includes(m[1])) liveDocIds.push(m[1]);
                                }
                                const matches2 = content.matchAll(/ComposerStoryCreateMutation.*?["'](\d{14,})["']/g);
                                for (const m of matches2) {
                                    if (m && m[1] && !liveDocIds.includes(m[1])) liveDocIds.push(m[1]);
                                }
                            }
                        }
                    } catch(e) {}

                    const defaultFallbackDocIds = ["28283705131270535", "28329575890036120", "27508435028820023", "27248647231502311", "6362241860538186", "6815340158580277", "6143924765664426"];
                    const fallbackDocIds = [...liveDocIds];
                    for (const id of defaultFallbackDocIds) {
                        if (!fallbackDocIds.includes(id)) fallbackDocIds.push(id);
                    }
                    const composerSessionId = actorId + "_" + Date.now();
                    const variables = {
                        input: {
                            composer_entry_point: "inline_composer",
                            composer_source_surface: surface,
                            idempotence_token: composerSessionId + "_FEED",
                            source: "WWW",
                            ai_generated_self_disclosure_metadata: { was_self_disclosed_as_ai_generated: false },
                            ...(isProfile ? {
                                audience: {
                                    privacy: {
                                        allow: [],
                                        base_state: "EVERYONE",
                                        deny: [],
                                        tag_expansion_state: "UNSPECIFIED"
                                    }
                                }
                            } : {}),
                            message: { text: postContent || "", ranges: [] },
                            inline_activities: [],
                            text_format_preset_id: "0",
                            publishing_flow: { supported_flows: ["ASYNC_SILENT", "ASYNC_NOTIF", "FALLBACK"] },
                            reels_remix: { is_original_audio_reusable: true, remix_status: "ENABLED" },
                            post_publish_story_data: { reshare_post_as_sticker: "DISABLED" },
                            logging: { composer_session_id: composerSessionId },
                            navigation_data: {
                                attribution_id_v2: isProfile ?
                                    ("ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,via_cold_start," + Date.now() + ",609016,190055527696468,,") :
                                    ("CometHomeRoot.react,comet.home,via_cold_start," + Date.now() + ",166542,4748854339,,")
                            },
                            tracking: [null],
                            event_share_metadata: { surface: shareToFeed ? "newsfeed" : surface },
                            ...(mediaId ? {
                                attachments: [
                                    isVideo ? {
                                        video: {
                                            id: String(mediaId),
                                            audio_descriptions: null,
                                            additional_video_metadata: {
                                                translatedAudioMetadata: []
                                            },
                                            notify_when_processed: true,
                                            transcriptions: null,
                                            was_created_via_unified_video_flow: {
                                                was_created_via_unified_video_flow: true
                                            }
                                        }
                                    } : { photo: { id: String(mediaId) } }
                                ]
                            } : {}),
                            actor_id: actorId,
                            client_mutation_id: String(Math.floor(Math.random() * 10) + 1)
                        },
                        feedLocation: feedLoc,
                        feedbackSource: 0,
                        focusCommentID: null,
                        gridMediaWidth: 230,
                        groupID: isGroup ? String(targetId) : null,
                        scale: 1,
                        privacySelectorRenderLocation: "COMET_STREAM",
                        checkPhotosToReelsUpsellEligibility: true,
                        referringStoryRenderLocation: null,
                        renderLocation: renderLoc,
                        useDefaultActor: false,
                        inviteShortLinkKey: null,
                        isFeed: false,
                        isFundraiser: false,
                        isFunFactPost: false,
                        isGroup: isGroup,
                        isEvent: false,
                        isTimeline: isProfile,
                        isSocialLearning: false,
                        isPageNewsFeed: isPage,
                        isProfileReviews: false,
                        isWorkSharedDraft: false
                    };

                    if (targetType === "group" && targetId) {
                        variables.input.group_id = String(targetId);
                        delete variables.input.audience;
                    } else if (targetType === "page") {
                        delete variables.input.audience;
                    }

                    let lastErr = "";
                    for (const targetDocId of fallbackDocIds) {
                        const params = new URLSearchParams();
                        params.append("av", actorId);
                        params.append("__user", actorId);
                        params.append("__a", "1");
                        params.append("__req", Math.floor(Math.random()*100).toString(36));
                        params.append("fb_dtsg", fb_dtsg);
                        params.append("jazoest", jazoest);
                        params.append("lsd", lsd);
                        params.append("__spin_r", spinR || "1043647106");
                        params.append("__spin_b", spinB || "trunk");
                        params.append("__spin_t", spinT || String(Math.floor(Date.now()/1000)));
                        params.append("fb_api_caller_class", "RelayModern");
                        params.append("fb_api_req_friendly_name", "ComposerStoryCreateMutation");
                        params.append("variables", JSON.stringify(variables));
                        params.append("server_timestamps", "true");
                        params.append("doc_id", targetDocId);

                        const resp = await fetch("/api/graphql/", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/x-www-form-urlencoded",
                                "X-FB-Friendly-Name": "ComposerStoryCreateMutation",
                                "X-FB-LSD": lsd,
                                "X-ASBD-ID": "129477"
                            },
                            body: params.toString(),
                            credentials: "include"
                        });

                        const text = await resp.text();
                        const clean = text.replace(/^for\s*\(;+\)\s*;?\s*/, "");

                        if (resp.ok) {
                            let pid = null;
                            const pfbidM = clean.match(/"pfbid([a-zA-Z0-9]+)"/);
                            if (pfbidM) {
                                pid = "pfbid" + pfbidM[1];
                            } else {
                                const idPatterns = [
                                    /"legacy_story_id"\s*:\s*"(\d+)"/,
                                    /"story_fbid"\s*:\s*"(\d+)"/,
                                    /"post_id"\s*:\s*"(\d+)"/
                                ];
                                for (const p of idPatterns) {
                                    const m = clean.match(p);
                                    if (m && m[1]) { pid = m[1]; break; }
                                }
                            }

                            let purl = "";
                            const effectiveId = pid || mediaId;
                            if (effectiveId) {
                                if (String(effectiveId).startsWith("pfbid")) {
                                    purl = `https://www.facebook.com/posts/${effectiveId}`;
                                } else if (postType === "reel") {
                                    purl = `https://www.facebook.com/reel/${effectiveId}`;
                                } else if (postType === "video") {
                                    purl = `https://www.facebook.com/watch/?v=${effectiveId}`;
                                } else if (mediaId) {
                                    purl = `https://www.facebook.com/photo/?fbid=${effectiveId}`;
                                } else {
                                    purl = `https://www.facebook.com/permalink.php?story_fbid=${effectiveId}&id=${actorId}`;
                                }
                            }

                            let extractedFeedbackId = null;
                            const storyM = clean.match(/"story_id"\s*:\s*"([^"]+)"/);
                            const storyId = storyM ? storyM[1] : null;

                            const fM = clean.match(/"feedback"\s*:\s*\{[^}]*?"id"\s*:\s*"([^"]+)"/) || clean.match(/"subscription_target_id"\s*:\s*"(\d+)"/);
                            if (fM && fM[1]) {
                                extractedFeedbackId = fM[1].startsWith("ZmVl") ? fM[1] : btoa("feedback:" + fM[1]);
                            }

                            // Verified from POSTFACEBOOK.har: query fetchComposerPostCreationStatusQuery for confirmed post_id & feedback_id
                            if (storyId && !extractedFeedbackId) {
                                try {
                                    const statusParams = new URLSearchParams();
                                    statusParams.append("av", actorId);
                                    statusParams.append("__user", actorId);
                                    statusParams.append("__a", "1");
                                    statusParams.append("fb_dtsg", fb_dtsg);
                                    statusParams.append("jazoest", jazoest);
                                    statusParams.append("lsd", lsd);
                                    statusParams.append("fb_api_caller_class", "RelayModern");
                                    statusParams.append("fb_api_req_friendly_name", "fetchComposerPostCreationStatusQuery");
                                    statusParams.append("variables", JSON.stringify({
                                        story_id: storyId,
                                        feedLocation: feedLoc,
                                        feedbackSource: 0,
                                        scale: 1,
                                        useDefaultActor: false,
                                        renderLocation: renderLoc
                                    }));
                                    statusParams.append("doc_id", "28107101955652613");

                                    const sResp = await fetch("/api/graphql/", {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded",
                                            "X-FB-Friendly-Name": "fetchComposerPostCreationStatusQuery",
                                            "X-FB-LSD": lsd
                                        },
                                        body: statusParams.toString(),
                                        credentials: "include"
                                    });
                                    if (sResp.ok) {
                                        const sText = await sResp.text();
                                        const sClean = sText.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                                        const sFm = sClean.match(/"feedback"\s*:\s*\{[^}]*?"id"\s*:\s*"([^"]+)"/);
                                        if (sFm && sFm[1]) {
                                            extractedFeedbackId = sFm[1];
                                        }
                                        const sPostIdM = sClean.match(/"post_id"\s*:\s*"(\d+)"/);
                                        if (sPostIdM && sPostIdM[1] && !pid) {
                                            pid = sPostIdM[1];
                                        }
                                    }
                                } catch(statusErr) {}
                            }

                            const hasStoryData = clean && (
                                clean.includes('"story_create"') ||
                                clean.includes('"composer_story_create"') ||
                                clean.includes('"legacy_story_id"') ||
                                clean.includes('"story_fbid"') ||
                                clean.includes('"post_id"') ||
                                clean.includes('"pfbid') ||
                                !!pid ||
                                !!storyId
                            );

                            if (hasStoryData) {
                                let numPid = null;
                                const numM = clean.match(/"post_id"\s*:\s*"(\d+)"/) || clean.match(/"legacy_story_id"\s*:\s*"(\d+)"/) || clean.match(/"story_fbid"\s*:\s*"(\d+)"/);
                                if (numM && numM[1]) numPid = numM[1];
                                else if (pid && !String(pid).startsWith("pfbid")) numPid = String(pid);

                                return {
                                    success: true,
                                    fbPostId: effectiveId ? String(effectiveId) : (pid || storyId || null),
                                    fbPostUrl: purl || `https://www.facebook.com/posts/${effectiveId || pid || ''}`,
                                    fbFeedbackId: extractedFeedbackId,
                                    storyId: storyId || null,
                                    numericPostId: numPid,
                                    actorId: actorId
                                };
                            }

                            // If no story data was returned, check for GraphQL errors and try next doc_id
                            let gqlErrorMessage = "";
                            try {
                                const p = JSON.parse(clean);
                                if (p.errors && Array.isArray(p.errors) && p.errors.length > 0) {
                                    const msg = p.errors[0].message || p.errors[0].description || "";
                                    if (!msg.toLowerCase().includes("warning")) gqlErrorMessage = msg;
                                } else if (p.error) {
                                    gqlErrorMessage = p.error.message || "";
                                }
                            } catch(e) {}

                            if (!gqlErrorMessage && (clean.includes('"error"') || clean.includes('"errors"'))) {
                                const errM = clean.match(/"message"\s*:\s*"([^"]+)"/);
                                if (errM && errM[1] && !errM[1].toLowerCase().includes("warning")) {
                                    gqlErrorMessage = errM[1];
                                }
                            }

                            lastErr = gqlErrorMessage || "Không thể xác nhận bài đăng";
                            continue;
                        } else {
                            lastErr = `HTTP ${resp.status}`;
                        }
                    }
                    return { success: false, error: lastErr || "Tất cả GraphQL doc_id đều thất bại" };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            },
            args: [payload.content, postType, effectiveMediaId, isVideo, fallbackActorId, payload.targetType || "profile", payload.targetId || "", shareToFeed]
        });

        const gqlRes = graphqlResults?.[0]?.result;
        if (!gqlRes || !gqlRes.success) {
            const err = gqlRes?.error || "Không thể tạo bài viết trên Facebook";
            await updateStep(`❌ Lỗi: ${err}`);
            return { success: false, error: err };
        }

        const fbPostId = gqlRes.fbPostId || uploadedMediaId;
        const fbPostUrl = gqlRes.fbPostUrl || (fbPostId ? `https://www.facebook.com/posts/${fbPostId}` : "");
        const fbFeedbackId = gqlRes.fbFeedbackId || (fbPostId ? btoa("feedback:" + fbPostId) : null);
        const storyId = gqlRes.storyId || null;
        const numericPostId = gqlRes.numericPostId || null;
        const currentActorId = gqlRes.actorId || fallbackActorId;

        // Tự động chia sẻ lên Tin (Story 24h) theo mutation từ sharetinfacebook.har
        let shareToStoryResult = null;
        if (shareToFeed) {
            await updateStep(`📖 Đang chia sẻ bài viết lên Bảng tin / Tin (Story)...`);
            await new Promise(r => setTimeout(r, 1500));
            shareToStoryResult = await _sharePostToStory(targetTab.id, {
                postUrl: fbPostUrl,
                postId: fbPostId,
                numericPostId: numericPostId,
                storyId: storyId,
                actorId: currentActorId
            }, fallbackActorId);

            if (shareToStoryResult && shareToStoryResult.success) {
                await updateStep(`✅ Đã chia sẻ bài viết lên Tin (Story) thành công!`);
            } else {
                console.warn("[Bridge] Chia sẻ Tin:", shareToStoryResult?.error);
                await updateStep(`⚠️ Chia sẻ lên Tin (Story): ${shareToStoryResult?.error || 'Bỏ qua'}`);
            }
        }

        const hasSeeding = payload.seedingComments && Array.isArray(payload.seedingComments) && payload.seedingComments.length > 0;
        const hasReact = payload.autoReactType && payload.autoReactType !== "NONE";

        if (hasSeeding || hasReact) {
            // Facebook publishes posts asynchronously (ASYNC_SILENT flow).
            // We MUST allow 3.5s propagation time so Facebook commits the post & its feedback container before commenting!
            await updateStep(`⏳ Đang đợi Facebook kích hoạt bài viết (3.5s) để seeding không bị mất...`);
            if (fbPostUrl) {
                try {
                    const curTab = await chrome.tabs.get(targetTab.id);
                    if (curTab && curTab.url && !curTab.url.includes(fbPostId)) {
                        await chrome.tabs.update(targetTab.id, { url: fbPostUrl });
                        await ensureTabLoaded(targetTab.id, 8000);
                        await new Promise(r => setTimeout(r, 1500));
                    } else {
                        await new Promise(r => setTimeout(r, 3500));
                    }
                } catch(e) {
                    await new Promise(r => setTimeout(r, 3500));
                }
            } else {
                await new Promise(r => setTimeout(r, 3500));
            }
        }

        // Seeding Comments
        let seedingResultData = { seedingIds: [], seedingDetails: [] };
        if (hasSeeding) {
            await updateStep(`💬 4/4: Đang gửi ${payload.seedingComments.length} bình luận seeding tự động (giãn cách an toàn)...`);
            const seedRes = await _executeFbSeeding(targetTab.id, fbPostId, fbFeedbackId, payload.seedingComments, fallbackActorId);
            if (seedRes) {
                if (seedRes.count !== undefined) {
                    await updateStep(`💬 Đã gửi thành công ${seedRes.count}/${payload.seedingComments.length} bình luận seeding!`);
                }
                seedingResultData = {
                    seedingIds: seedRes.seedingIds || [],
                    seedingDetails: seedRes.seedingDetails || []
                };
            }
        }

        // Auto-React
        if (payload.autoReactType && payload.autoReactType !== "NONE") {
            await updateStep(`❤️ Thả cảm xúc (${payload.autoReactType}) vào bài viết...`);
            await _executeFbReaction(targetTab.id, fbFeedbackId || btoa("feedback:" + fbPostId), payload.autoReactType, fallbackActorId);
        }

        await updateStep(`✅ Hoàn tất xuất bản bài viết lên Facebook!`);
        return {
            success: true,
            fbPostId,
            fbPostUrl,
            fbFeedbackId,
            storyId,
            numericPostId,
            shareToStorySuccess: shareToStoryResult ? shareToStoryResult.success : false,
            seedingIds: seedingResultData.seedingIds,
            seedingDetails: seedingResultData.seedingDetails,
            publishedAt: Date.now(),
            progressStep: `✅ Đã đăng thành công lên Facebook (ID: ${fbPostId})`
        };

    } catch(err) {
        await updateStep(`❌ Lỗi ngoại lệ: ${err.message}`);
        return { success: false, error: err.message };
    }
}

// ==========================================
// 🚀 X (TWITTER) AUTOMATION ENGINE
// ==========================================

async function _uploadXMedia(mediaItem, updateStep, ct0) {
    try {
        let blob;
        let mediaType = "image/jpeg";
        let mediaCategory = "tweet_image";

        if (typeof mediaItem === "string" && mediaItem.startsWith("data:")) {
            const parts = mediaItem.split(",");
            const mimeMatch = parts[0].match(/:(.*?);/);
            if (mimeMatch) mediaType = mimeMatch[1];
            const byteString = atob(parts[1]);
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);
            for (let i = 0; i < byteString.length; i++) {
                ia[i] = byteString.charCodeAt(i);
            }
            blob = new Blob([ab], { type: mediaType });
        } else {
            const rawUrl = typeof mediaItem === "string" ? mediaItem : (mediaItem.url || mediaItem.originalUrl || "");
            if (!rawUrl) throw new Error("URL media không hợp lệ");
            const fetchRes = await fetch(rawUrl);
            blob = await fetchRes.blob();
            if (blob.type) mediaType = blob.type;
        }

        if (mediaType.startsWith("video/") || (typeof mediaItem === "object" && mediaItem.type === "video")) {
            mediaCategory = "tweet_video";
        } else if (mediaType.includes("gif")) {
            mediaCategory = "tweet_gif";
        } else {
            mediaCategory = "tweet_image";
        }

        // B1: INIT
        const initUrl = `https://upload.x.com/i/media/upload.json?command=INIT&total_bytes=${blob.size}&media_type=${encodeURIComponent(mediaType)}&media_category=${mediaCategory}`;
        const initRes = await fetch(initUrl, {
            method: "POST",
            headers: {
                "x-csrf-token": ct0,
                "x-twitter-auth-type": "OAuth2Session"
            },
            credentials: "include"
        });

        if (!initRes.ok) {
            const errTxt = await initRes.text();
            throw new Error(`Upload INIT thất bại (${initRes.status}): ${errTxt}`);
        }

        const initData = await initRes.json();
        const mediaId = initData.media_id_string || String(initData.media_id);

        // B2: APPEND
        const chunkSize = 4 * 1024 * 1024; // 4MB chunks
        const totalSegments = Math.ceil(blob.size / chunkSize);
        for (let seg = 0; seg < totalSegments; seg++) {
            const start = seg * chunkSize;
            const end = Math.min(start + chunkSize, blob.size);
            const chunkBlob = blob.slice(start, end);

            const fd = new FormData();
            fd.append("media", chunkBlob, "blob");

            const appendUrl = `https://upload.x.com/i/media/upload.json?command=APPEND&media_id=${mediaId}&segment_index=${seg}`;
            const appendRes = await fetch(appendUrl, {
                method: "POST",
                headers: {
                    "x-csrf-token": ct0,
                    "x-twitter-auth-type": "OAuth2Session"
                },
                credentials: "include",
                body: fd
            });

            if (!appendRes.ok) {
                throw new Error(`Upload APPEND segment ${seg} thất bại (${appendRes.status})`);
            }
        }

        // B3: FINALIZE
        const finUrl = `https://upload.x.com/i/media/upload.json?command=FINALIZE&media_id=${mediaId}&allow_async=true`;
        const finRes = await fetch(finUrl, {
            method: "POST",
            headers: {
                "x-csrf-token": ct0,
                "x-twitter-auth-type": "OAuth2Session"
            },
            credentials: "include"
        });

        if (!finRes.ok) {
            const errTxt = await finRes.text();
            throw new Error(`Upload FINALIZE thất bại (${finRes.status}): ${errTxt}`);
        }

        const finData = await finRes.json();

        // B4: STATUS (nếu media đang xử lý ngầm, đặc biệt là video)
        if (finData.processing_info) {
            let state = finData.processing_info.state;
            let checkSecs = finData.processing_info.check_after_secs || 1;
            let attempts = 0;
            while (state !== "succeeded" && attempts < 40) {
                attempts++;
                if (state === "failed") {
                    throw new Error(`Xử lý media trên X thất bại: ${JSON.stringify(finData.processing_info.error || {})}`);
                }
                await new Promise(r => setTimeout(r, checkSecs * 1000));
                const statusUrl = `https://upload.x.com/i/media/upload.json?command=STATUS&media_id=${mediaId}`;
                const sRes = await fetch(statusUrl, {
                    headers: {
                        "x-csrf-token": ct0,
                        "x-twitter-auth-type": "OAuth2Session"
                    },
                    credentials: "include"
                });
                if (sRes.ok) {
                    const sData = await sRes.json();
                    if (sData.processing_info) {
                        state = sData.processing_info.state;
                        checkSecs = sData.processing_info.check_after_secs || 1;
                        if (updateStep && sData.processing_info.progress_percent !== undefined) {
                            await updateStep(`⏳ Đang mã hóa media trên X (${sData.processing_info.progress_percent}%)...`);
                        }
                    } else {
                        break;
                    }
                }
            }
        }

        return mediaId;
    } catch(e) {
        console.error("[X Media Upload Error]:", e);
        throw e;
    }
}

async function _executeXTweet(payload, updateStep) {
    try {
        await updateStep("🔍 1/3: Đang kiểm tra phiên đăng nhập X (Twitter)...");

        const tweetText = (payload.content || payload.message || payload.title || payload.caption || payload.text || "").trim();

        // Thu thập Media (ảnh/video)
        let mediaList = [];
        if (Array.isArray(payload.images)) mediaList.push(...payload.images);
        if (payload.image) mediaList.push(payload.image);
        if (payload.videoUrl) mediaList.push({ url: payload.videoUrl, type: "video" });
        if (payload.videoFile) mediaList.push({ url: payload.videoFile, type: "video" });
        if (payload.mediaUrl) mediaList.push(payload.mediaUrl);
        mediaList = mediaList.filter(Boolean);

        // Lấy cookies X
        const allCookies = await new Promise(resolve => {
            chrome.cookies.getAll({}, (c) => resolve(c || []));
        });
        const xCookies = allCookies.filter(c => c.domain.includes("x.com") || c.domain.includes("twitter.com"));
        const authToken = xCookies.find(c => c.name === "auth_token")?.value;
        const ct0 = xCookies.find(c => c.name === "ct0")?.value;

        if (!authToken || !ct0) {
            return {
                success: false,
                error: "Chưa đăng nhập X (Twitter) trên Chrome. Vui lòng mở x.com đăng nhập trước khi đăng bài!"
            };
        }

        // Tải media lên X nếu có
        const mediaIds = [];
        if (mediaList.length > 0) {
            for (let i = 0; i < mediaList.length; i++) {
                await updateStep(`⏳ 1/3: Đang tải tệp đính kèm (${i + 1}/${mediaList.length}) lên X...`);
                const mid = await _uploadXMedia(mediaList[i], updateStep, ct0);
                if (mid) mediaIds.push(mid);
            }
        }

        await updateStep("🚀 2/3: Đang gửi yêu cầu xuất bản Tweet lên X...");

        // Chuẩn bị payload GraphQL CreateTweet chuẩn như file x.com.har
        const queryId = "GYdIGqVWfZNho79bQ2XDoA";
        const variables = {
            tweet_text: tweetText,
            media: {
                media_entities: mediaIds.map(id => ({ media_id: id, tagged_users: [] })),
                possibly_sensitive: false
            },
            semantic_annotation_ids: [],
            disallowed_reply_options: null,
            semantic_annotation_options: { source: "Htl" }
        };

        const features = {
            "communities_web_enable_tweet_community_results_fetch": true,
            "c9s_tweet_anatomy_moderator_badge_enabled": true,
            "responsive_web_edit_tweet_api_enabled": true,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": true,
            "view_counts_everywhere_api_enabled": true,
            "longform_notetweets_consumption_enabled": true,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": true,
            "responsive_web_graphql_timeline_navigation_enabled": true
        };

        const payloadGql = {
            variables,
            features,
            queryId
        };

        // Tìm hoặc mở tab x.com ngầm để thực thi request trong môi trường Same-Origin của x.com
        const tabs = await chrome.tabs.query({});
        let targetTab = tabs.find(t => t.url && (t.url.includes("x.com") || t.url.includes("twitter.com")));
        let createdTab = false;

        if (!targetTab) {
            targetTab = await chrome.tabs.create({ url: "https://x.com/home", active: false });
            createdTab = true;
            await ensureTabLoaded(targetTab.id, 8000);
            await new Promise(r => setTimeout(r, 1000));
        }

        // TẦNG 1: Gửi GraphQL CreateTweet trực tiếp từ context trang x.com (MAIN world)
        const execRes = await chrome.scripting.executeScript({
            target: { tabId: targetTab.id },
            world: "MAIN",
            func: async (payloadGql, ct0) => {
                try {
                    const res = await fetch(`https://x.com/i/api/graphql/${payloadGql.queryId}/CreateTweet`, {
                        method: "POST",
                        headers: {
                            "content-type": "application/json",
                            "x-csrf-token": ct0,
                            "x-twitter-active-user": "yes",
                            "x-twitter-auth-type": "OAuth2Session"
                        },
                        credentials: "include",
                        body: JSON.stringify(payloadGql)
                    });
                    const txt = await res.text();
                    try {
                        return { ok: res.ok, status: res.status, data: JSON.parse(txt) };
                    } catch(e) {
                        return { ok: res.ok, status: res.status, rawText: txt };
                    }
                } catch(err) {
                    return { ok: false, error: err.message };
                }
            },
            args: [payloadGql, ct0]
        });

        const apiResult = execRes?.[0]?.result;
        let restId = apiResult?.data?.data?.create_tweet?.tweet_results?.result?.rest_id;
        let screenName = apiResult?.data?.data?.create_tweet?.tweet_results?.result?.core?.user_results?.result?.core?.screen_name;

        // Nếu tạo thành công qua GraphQL API
        if (apiResult?.ok && restId) {
            if (createdTab) {
                try { chrome.tabs.remove(targetTab.id); } catch(e) {}
            }
            const sName = screenName || "i";
            const tweetUrl = `https://x.com/${sName}/status/${restId}`;
            await updateStep(`✅ 3/3: Đã xuất bản thành công lên X! (Tweet ID: ${restId})`);
            return {
                success: true,
                tweetId: restId,
                tweetUrl: tweetUrl,
                fbPostId: restId,
                fbPostUrl: tweetUrl,
                publishedAt: Date.now(),
                progressStep: `✅ Đã đăng thành công lên X (Tweet: ${restId})`
            };
        }

        // TẦNG 2 (FALLBACK): Nếu API bị hạn chế (vd do kiểm tra transaction id), dùng Native Composer
        await updateStep("⚠️ API trực tiếp yêu cầu xác thực phiên, đang chuyển sang Trình soạn thảo X Composer...");

        // Điều hướng tab tới compose page
        await chrome.tabs.update(targetTab.id, { url: "https://x.com/compose/post" });
        await ensureTabLoaded(targetTab.id, 8000);
        await new Promise(r => setTimeout(r, 2000));

        const composerRes = await chrome.scripting.executeScript({
            target: { tabId: targetTab.id },
            world: "MAIN",
            func: async (textToPost) => {
                try {
                    // 1. Tìm ô soạn thảo
                    const editor = document.querySelector('div[data-testid="tweetTextarea_0"]') || document.querySelector('div[role="textbox"]');
                    if (!editor) {
                        return { success: false, error: "Không tìm thấy ô soạn thảo Tweet trên x.com" };
                    }
                    editor.focus();

                    // Điền văn bản
                    document.execCommand("insertText", false, textToPost);
                    editor.dispatchEvent(new Event("input", { bubbles: true }));
                    editor.dispatchEvent(new Event("change", { bubbles: true }));
                    await new Promise(r => setTimeout(r, 800));

                    // 2. Tìm nút Đăng (Post / Tweet)
                    const postBtn = document.querySelector('button[data-testid="tweetButton"]') 
                                 || document.querySelector('button[data-testid="tweetButtonInline"]')
                                 || document.querySelector('button[aria-label*="Post" i]')
                                 || document.querySelector('button[aria-label*="Đăng" i]');
                    if (!postBtn) {
                        return { success: false, error: "Không tìm thấy nút Post trên x.com" };
                    }

                    if (postBtn.disabled) {
                        return { success: false, error: "Nút Đăng Tweet đang bị vô hiệu hóa (disabled)" };
                    }

                    postBtn.click();
                    await new Promise(r => setTimeout(r, 2000));

                    return { success: true };
                } catch(e) {
                    return { success: false, error: e.message };
                }
            },
            args: [tweetText]
        });

        if (createdTab) {
            // Giữ tab thêm 3s rồi đóng ngầm
            setTimeout(() => { try { chrome.tabs.remove(targetTab.id); } catch(e) {} }, 3500);
        }

        const compResult = composerRes?.[0]?.result;
        if (compResult?.success) {
            const fallbackTweetId = `x_tweet_${Date.now()}`;
            const fallbackUrl = `https://x.com/home`;
            await updateStep("✅ 3/3: Đã xuất bản thành công qua X Composer!");
            return {
                success: true,
                tweetId: fallbackTweetId,
                tweetUrl: fallbackUrl,
                fbPostId: fallbackTweetId,
                fbPostUrl: fallbackUrl,
                publishedAt: Date.now(),
                progressStep: "✅ Đã đăng thành công qua X Composer"
            };
        } else {
            const errMsg = compResult?.error || apiResult?.rawText || "Lỗi xuất bản Tweet";
            throw new Error(errMsg);
        }

    } catch(err) {
        console.error("[_executeXTweet Error]:", err);
        await updateStep(`❌ Lỗi đăng bài X: ${err.message}`);
        return {
            success: false,
            error: err.message
        };
    }
}

async function _executeFbSeeding(tabId, postId, knownFeedbackId, comments, fallbackActorId) {
    try {
        const seedingResults = await chrome.scripting.executeScript({
            target: { tabId },
            func: async (postId, knownFeedbackId, comments, fallbackActorId) => {
                let fb_dtsg = "";
                let lsd = "";
                for (let attempt = 0; attempt < 8; attempt++) {
                    const html = document.documentElement.innerHTML || "";
                    if (window.DTSGInitialData && window.DTSGInitialData.token) fb_dtsg = window.DTSGInitialData.token;
                    else if (window.DTSGInitData && window.DTSGInitData.token) fb_dtsg = window.DTSGInitData.token;
                    if (!fb_dtsg) {
                        const m = html.match(/"token"\s*:\s*"([^"]{20,})"\s*,\s*"async_get_token"/);
                        if (m && m[1]) fb_dtsg = m[1];
                    }
                    if (!lsd) {
                        const m = html.match(/"lsd"\s*:\s*"([^"]+)"/);
                        if (m && m[1]) lsd = m[1];
                    }
                    if (fb_dtsg) break;
                    await new Promise(r => setTimeout(r, 400));
                }

                let actorId = "";
                const cUserMatch = document.cookie.match(/c_user=(\d+)/);
                if (cUserMatch && cUserMatch[1]) actorId = cUserMatch[1];
                if (!actorId) actorId = fallbackActorId || "";

                if (!fb_dtsg || !actorId || !postId) {
                    return { success: false, error: "Thiếu dtsg hoặc UID để bình luận" };
                }

                let jazoest = "2";
                for (let i = 0; i < fb_dtsg.length; i++) jazoest += fb_dtsg.charCodeAt(i);

                // Determine the single authoritative feedback ID for the post
                let targetFeedbackId = "";
                if (knownFeedbackId) {
                    targetFeedbackId = knownFeedbackId.startsWith("ZmVl") ? knownFeedbackId : btoa("feedback:" + knownFeedbackId);
                } else if (postId) {
                    targetFeedbackId = btoa("feedback:" + postId);
                }

                if (!targetFeedbackId) {
                    const finalHtml = document.documentElement.innerHTML || "";
                    const m = finalHtml.match(/"(?:feedback_target_id|legacy_story_id|story_fbid|post_id)"\s*:\s*"(\d+)"/);
                    if (m && m[1]) {
                        targetFeedbackId = btoa("feedback:" + m[1]);
                    }
                }

                if (!targetFeedbackId) {
                    return { success: false, error: "Thiếu feedback ID bài viết để seeding" };
                }

                let liveCommentDocIds = [];
                try {
                    const scripts = Array.from(document.scripts || []);
                    for (const s of scripts) {
                        const content = s.textContent || s.innerHTML || "";
                        if (content.includes("CometUFICreateCommentMutation") || content.includes("CometCommentCreateMutation")) {
                            const matches = content.matchAll(/"doc_id"\s*:\s*"(\d{14,})"/g);
                            for (const m of matches) {
                                if (m && m[1] && !liveCommentDocIds.includes(m[1])) liveCommentDocIds.push(m[1]);
                            }
                        }
                    }
                } catch(e) {}

                const defaultCommentDocIds = ["27829190080054105", "5384620808298758", "5765399230165702", "5515286528574762", "7181675201948512"];
                const docIds = [...liveCommentDocIds];
                for (const id of defaultCommentDocIds) {
                    if (!docIds.includes(id)) docIds.push(id);
                }

                let successCount = 0;
                let seedingIds = [];
                let seedingDetails = [];

                for (let i = 0; i < comments.length; i++) {
                    const commentText = comments[i];
                    if (!commentText || !commentText.trim()) continue;
                    let commentSuccess = false;
                    let currentCommentId = null;
                    const randomSuffix = Math.random().toString(36).substring(2, 8);
                    const clientMutationId = Date.now() + "_" + randomSuffix;
                    const idempotenceToken = "client:" + Date.now() + "_" + randomSuffix;

                    for (const docId of docIds) {
                        try {
                            const isNewMutation = (docId === "27829190080054105" || docId.startsWith("2782") || docId.startsWith("5765"));
                            const vars = isNewMutation ? {
                                feedLocation: "POST_PERMALINK_DIALOG",
                                feedbackSource: 2,
                                groupID: null,
                                input: {
                                    client_mutation_id: clientMutationId,
                                    attachments: null,
                                    feedback_id: targetFeedbackId,
                                    formatting_style: null,
                                    is_inline_vote_enabled_for_qna: false,
                                    message: { ranges: [], text: commentText.trim() },
                                    attribution_id_v2: "CometSinglePostDialogRoot.react,comet.post.single_dialog,unexpected," + Date.now() + ",881640,,,",
                                    feedback_source: "OBJECT",
                                    idempotence_token: idempotenceToken,
                                    session_id: String(Date.now())
                                },
                                inviteShortLinkKey: null,
                                renderLocation: "permalink",
                                scale: 2,
                                useDefaultActor: false
                            } : {
                                input: {
                                    feedback_id: targetFeedbackId,
                                    message: { text: commentText.trim() },
                                    actor_id: actorId,
                                    client_mutation_id: clientMutationId
                                }
                            };

                            const params = new URLSearchParams();
                            params.append("av", actorId);
                            params.append("__user", actorId);
                            params.append("__a", "1");
                            params.append("fb_dtsg", fb_dtsg);
                            params.append("jazoest", jazoest);
                            params.append("lsd", lsd);
                            params.append("fb_api_caller_class", "RelayModern");
                            params.append("fb_api_req_friendly_name", isNewMutation ? "useCometUFICreateCommentMutation" : "CometCommentCreateMutation");
                            params.append("variables", JSON.stringify(vars));
                            params.append("doc_id", docId);

                            const resp = await fetch("/api/graphql/", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/x-www-form-urlencoded",
                                    "X-FB-Friendly-Name": isNewMutation ? "useCometUFICreateCommentMutation" : "CometCommentCreateMutation",
                                    "X-FB-LSD": lsd
                                },
                                body: params.toString(),
                                credentials: "include"
                            });

                            if (!resp.ok) continue;

                            const text = await resp.text();
                            
                            // Check clean JSON / streaming JSON lines
                            const cleanText = text.replace(/^for\s*\(;+\)\s*;?\s*/, "").trim();
                            const lines = cleanText.split("\n");
                            for (const line of lines) {
                                const tr = line.trim();
                                if (!tr) continue;
                                try {
                                    const parsed = JSON.parse(tr);
                                    if (parsed && parsed.data) {
                                        const d = parsed.data;
                                        if (d.comment_create || d.useCometUFICreateCommentMutation || d.comment || d.feedback?.id) {
                                            commentSuccess = true;
                                            const cmtNode = d.comment_create?.comment || 
                                                            d.useCometUFICreateCommentMutation?.comment || 
                                                            d.feedback_comment_edge?.node || 
                                                            d.comment_create?.feedback_comment_edge?.node || 
                                                            d.comment;
                                            if (cmtNode) {
                                                if (cmtNode.legacy_fbid) currentCommentId = String(cmtNode.legacy_fbid);
                                                else if (cmtNode.id) {
                                                    const rawId = String(cmtNode.id);
                                                    if (rawId.startsWith("Y29tbWVudD")) {
                                                        try {
                                                            const decoded = atob(rawId);
                                                            const parts = decoded.split("_");
                                                            currentCommentId = parts.length > 1 ? parts[parts.length - 1] : rawId;
                                                        } catch(e) {
                                                            currentCommentId = rawId;
                                                        }
                                                    } else {
                                                        currentCommentId = rawId;
                                                    }
                                                }
                                            }
                                            break;
                                        }
                                    }
                                } catch(e) {}
                            }

                            // String fallback check
                            if (!commentSuccess) {
                                if ((text.includes('"comment_create"') || 
                                     text.includes('"useCometUFICreateCommentMutation"') || 
                                     text.includes('"comment":{') || 
                                     text.includes('"feedback":{')) && 
                                    !text.includes('"errorSummary"')) {
                                    commentSuccess = true;
                                }
                            }

                            // Regex extraction if not yet found
                            if (commentSuccess && !currentCommentId) {
                                const legM = cleanText.match(/"legacy_fbid"\s*:\s*"(\d+)"/) || cleanText.match(/"comment_id"\s*:\s*"(\d+)"/);
                                if (legM && legM[1]) {
                                    currentCommentId = legM[1];
                                } else {
                                    const b64M = cleanText.match(/"id"\s*:\s*"(Y29tbWVudD[a-zA-Z0-9_=-]+)"/);
                                    if (b64M && b64M[1]) {
                                        try {
                                            const dec = atob(b64M[1]);
                                            const pts = dec.split("_");
                                            currentCommentId = pts.length > 1 ? pts[pts.length - 1] : b64M[1];
                                        } catch(e) {
                                            currentCommentId = b64M[1];
                                        }
                                    }
                                }
                            }

                            if (commentSuccess) {
                                break; // Success! Never retry or post duplicate
                            }
                        } catch(e) {}
                    }

                    if (commentSuccess) {
                        successCount++;
                        const finalId = currentCommentId || `cmt_${Date.now()}_${i + 1}`;
                        seedingIds.push(finalId);
                        seedingDetails.push({
                            id: finalId,
                            text: commentText.trim(),
                            status: "success",
                            timestamp: Date.now()
                        });
                    } else {
                        seedingDetails.push({
                            id: null,
                            text: commentText.trim(),
                            status: "failed",
                            timestamp: Date.now()
                        });
                    }

                    // Anti-spam interval: 2800ms between comments to prevent Facebook rate limiting
                    if (i < comments.length - 1) {
                        await new Promise(r => setTimeout(r, 2800));
                    }
                }

                return {
                    success: successCount > 0,
                    count: successCount,
                    total: comments.length,
                    seedingIds: seedingIds,
                    seedingDetails: seedingDetails
                };
            },
            args: [postId, knownFeedbackId, comments, fallbackActorId]
        });

        return seedingResults?.[0]?.result || { success: false, error: "Lỗi thực thi seeding" };
    } catch(e) {
        return { success: false, error: e.message };
    }
}

async function _executeFbReaction(tabId, feedbackId, reactType, fallbackActorId) {
    try {
        await chrome.scripting.executeScript({
            target: { tabId },
            func: async (feedbackId, reactType, fallbackActorId) => {
                let fb_dtsg = "";
                let lsd = "";
                const html = document.documentElement.innerHTML || "";
                if (window.DTSGInitialData && window.DTSGInitialData.token) fb_dtsg = window.DTSGInitialData.token;
                else if (window.DTSGInitData && window.DTSGInitData.token) fb_dtsg = window.DTSGInitData.token;
                if (!fb_dtsg) {
                    const m = html.match(/"token"\s*:\s*"([^"]{20,})"\s*,\s*"async_get_token"/);
                    if (m && m[1]) fb_dtsg = m[1];
                }
                if (!lsd) {
                    const m = html.match(/"lsd"\s*:\s*"([^"]+)"/);
                    if (m && m[1]) lsd = m[1];
                }
                let actorId = "";
                const cUserMatch = document.cookie.match(/c_user=(\d+)/);
                if (cUserMatch && cUserMatch[1]) actorId = cUserMatch[1];
                if (!actorId) actorId = fallbackActorId || "";

                if (!fb_dtsg || !actorId || !feedbackId) return { success: false };

                let jazoest = "2";
                for (let i = 0; i < fb_dtsg.length; i++) jazoest += fb_dtsg.charCodeAt(i);

                const reactionMap = { "LIKE": 1, "LOVE": 2, "CARE": 16, "HAHA": 4, "WOW": 3, "SAD": 7, "ANGRY": 8 };
                const reactionValue = reactionMap[(reactType || "").toUpperCase()] || 1;

                const vars = {
                    input: {
                        attribution_id_v2: "CometHomeRoot.react,comet.home,via_cold_start," + Date.now() + ",166542,4748854339,,",
                        feedback_id: feedbackId,
                        feedback_reaction: reactionValue,
                        feedback_source: "OBJECT",
                        is_tracking_encrypted: false,
                        tracking: [null],
                        session_id: actorId + "_" + Date.now(),
                        client_mutation_id: String(Math.floor(Math.random() * 10) + 1),
                        actor_id: actorId
                    },
                    useDefaultActor: false
                };

                const params = new URLSearchParams();
                params.append("av", actorId);
                params.append("__user", actorId);
                params.append("__a", "1");
                params.append("fb_dtsg", fb_dtsg);
                params.append("jazoest", jazoest);
                params.append("lsd", lsd);
                params.append("fb_api_caller_class", "RelayModern");
                params.append("fb_api_req_friendly_name", "CometUFIFeedbackReactMutation");
                params.append("variables", JSON.stringify(vars));
                params.append("doc_id", "27646120298312844");

                await fetch("/api/graphql/", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params.toString(),
                    credentials: "include"
                });
                return { success: true };
            },
            args: [feedbackId, reactType, fallbackActorId]
        });
    } catch(e) {}
}

let pollingStartedAt = 0;

// 3. Kéo lệnh từ Backend và thực thi trên Trình duyệt
async function pollAndExecuteCommand() {
    if (isPollingBridge) {
        if (Date.now() - pollingStartedAt > 30000) {
            isPollingBridge = false;
        } else {
            return;
        }
    }
    isPollingBridge = true;
    pollingStartedAt = Date.now();

    try {
        const res = await fetch(`${BACKEND_URL}/api/bridge/poll`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
                nodeId: NODE_ID,
                busySubProjects: Array.from(activeSubProjectIds),
                isFlowBusy: activeFlowCount > 0,
                isFbBusy: activeFbCount > 0
            }),
            signal: AbortSignal.timeout(5000)
        });

        if (!res.ok) return;
        const data = await res.json();
        const cmd = data.command;
        if (!cmd) return;

        // Thực thi lệnh trong luồng async độc lập, tách biệt hoàn toàn theo từng project con
        _executeCommandAsync(cmd);

        // Nếu còn lệnh chờ khác của các project con khác đang rảnh, kéo tiếp ngay lập tức
        if (data.hasMorePending) {
            setTimeout(pollAndExecuteCommand, 50);
        }

    } catch (e) {
        console.warn("[Bridge] Lỗi polling:", e.message);
    } finally {
        isPollingBridge = false;
    }
}

async function _executeCommandAsync(cmd) {
    const subId = cmd.targetSubProjectId || "";
    const isFlowAction = cmd.action && cmd.action.startsWith("FLOW_") && cmd.action !== "FLOW_LIST_PROJECTS";
    const isFbAction = cmd.action && (cmd.action.startsWith("POST_") || cmd.action.startsWith("SHARE_") || cmd.action === "SEEDING");

    if (subId) activeSubProjectIds.add(subId);
    if (isFlowAction) activeFlowCount++;
    if (isFbAction) activeFbCount++;

    console.log(`[Bridge] Nhận lệnh từ VPS: ${cmd.action} (ID: ${cmd.id}, SubProject: ${subId || 'global'})`);
    let cmdResult = { success: false, error: "Chưa hỗ trợ action" };

    try {
        switch (cmd.action) {
                case "GET_COOKIES": {
                    const domain = cmd.domain || "facebook.com";
                    const cookies = await chrome.cookies.getAll({ domain });
                    const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join("; ");
                    cmdResult = { success: true, count: cookies.length, domain, cookies, cookieStr };
                    break;
                }

                case "GET_FB_ACCOUNT": {
                    const cookies = await chrome.cookies.getAll({ domain: "facebook.com" });
                    const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join("; ");
                    let cUser = "";
                    let xs = "";
                    for (const c of cookies) {
                        if (c.name === "c_user") cUser = c.value;
                        if (c.name === "xs") xs = c.value;
                    }

                    let accountInfo = {
                        uid: cUser,
                        name: "",
                        avatar: "",
                        profileUrl: cUser ? `https://www.facebook.com/profile.php?id=${cUser}` : "",
                        isLoggedIn: !!cUser,
                        cookieCount: cookies.length,
                        cookieStr: cookieStr,
                        cookies: cookies,
                        token: "",
                        dtsg: ""
                    };

                    // 1. Quét từ Tab Facebook đang mở (nếu có)
                    const fbTabs = await chrome.tabs.query({ url: "*://*.facebook.com/*" });
                    let targetTabId = fbTabs.length > 0 ? fbTabs[0].id : null;
                    if (!targetTabId) {
                        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
                        if (activeTab && activeTab.url && activeTab.url.includes("facebook.com")) {
                            targetTabId = activeTab.id;
                        }
                    }

                    if (targetTabId) {
                        try {
                            const execResults = await chrome.scripting.executeScript({
                                target: { tabId: targetTabId },
                                world: "MAIN",
                                func: () => {
                                    try {
                                        let name = "";
                                        let avatar = "";
                                        let token = window.__accessToken || "";
                                        let dtsg = "";

                                        // A. Module require của Facebook
                                        if (typeof window.require === 'function') {
                                            try {
                                                const cud = window.require('CurrentUserInitialData');
                                                if (cud) {
                                                    if (cud.NAME) name = cud.NAME;
                                                    if (cud.PROFILE_PICTURE_URI) avatar = cud.PROFILE_PICTURE_URI;
                                                }
                                            } catch(e) {}
                                            try {
                                                const dtsgMod = window.require('DTSGInitialData');
                                                if (dtsgMod && dtsgMod.token) dtsg = dtsgMod.token;
                                            } catch(e) {}
                                        }

                                        // B. DTSG tokens
                                        if (!dtsg) {
                                            if (window.DTSGInitialData && window.DTSGInitialData.token) {
                                                dtsg = window.DTSGInitialData.token;
                                            } else if (window.__dtsg) {
                                                dtsg = window.__dtsg;
                                            }
                                        }

                                        // C. Quét các thẻ script tìm CurrentUserInitialData, NAME, PROFILE_PICTURE_URI
                                        const scripts = document.querySelectorAll('script');
                                        for (let s of scripts) {
                                            let txt = s.textContent || '';
                                            if (!txt) continue;

                                            if (!token) {
                                                let mToken = txt.match(/["'](EAA[A-Za-z0-9]+)["']/);
                                                if (mToken) token = mToken[1];
                                            }

                                            if (!dtsg && txt.includes('DTSGInitialData')) {
                                                let mDtsg = txt.match(/"token":"([^"]+)"/);
                                                if (mDtsg) dtsg = mDtsg[1];
                                            }

                                            if (!name && (txt.includes('CurrentUserInitialData') || txt.includes('"ACCOUNT_ID"') || txt.includes('"USER_ID"'))) {
                                                let mName = txt.match(/"NAME":"([^"]+)"/);
                                                if (mName && mName[1] && mName[1].length < 60) {
                                                    try { name = JSON.parse(`"${mName[1]}"`); } catch(e) { name = mName[1]; }
                                                }
                                            }

                                            if (!avatar && (txt.includes('CurrentUserInitialData') || txt.includes('PROFILE_PICTURE_URI'))) {
                                                let mPic = txt.match(/"PROFILE_PICTURE_URI":"([^"]+)"/);
                                                if (mPic && mPic[1]) {
                                                    avatar = mPic[1].replace(/\\\//g, '/');
                                                }
                                            }
                                            if (!avatar && txt.includes('"profile_picture"')) {
                                                let mPicObj = txt.match(/"profile_picture":\{"uri":"([^"]+)"/);
                                                if (mPicObj && mPicObj[1]) {
                                                    avatar = mPicObj[1].replace(/\\\//g, '/');
                                                }
                                            }
                                        }

                                        // D. Quét ảnh Avatar trong DOM Facebook
                                        if (!avatar) {
                                            const topSvgs = document.querySelectorAll('svg image[*|href], svg image[href]');
                                            for (let img of topSvgs) {
                                                let href = img.getAttribute('xlink:href') || img.getAttribute('href') || '';
                                                if (href && (href.includes('scontent') || href.includes('fbcdn.net')) && !href.includes('static')) {
                                                    avatar = href;
                                                    break;
                                                }
                                            }
                                        }
                                        if (!avatar) {
                                            const fbcdnImgs = document.querySelectorAll('div[role="navigation"] img, div[aria-label*="cá nhân"] img, div[aria-label*="profile"] img, img[alt*="profile"], img[alt*="cá nhân"]');
                                            for (let img of fbcdnImgs) {
                                                if (img.src && (img.src.includes('scontent') || img.src.includes('fbcdn.net')) && !img.src.includes('static')) {
                                                    avatar = img.src;
                                                    break;
                                                }
                                            }
                                        }

                                        // E. Quét tên từ cột menu trái (Left sidebar navigation)
                                        if (!name) {
                                            const navLinks = document.querySelectorAll('div[role="navigation"] a, a[role="link"]');
                                            for (let a of navLinks) {
                                                const img = a.querySelector('image, img');
                                                const span = a.querySelector('span');
                                                if (img && span) {
                                                    let text = span.textContent ? span.textContent.trim() : '';
                                                    const blacklist = ['Bạn bè', 'Nhóm', 'Bảng feed', 'Kỷ niệm', 'Đã lưu', 'Video', 'Marketplace', 'Trang cá nhân của bạn', 'Your profile', 'Watch', 'Groups', 'Feeds', 'Memories', 'Saved'];
                                                    if (text && text.length >= 2 && !blacklist.includes(text) && !text.includes('Facebook')) {
                                                        name = text;
                                                        if (!avatar) {
                                                            avatar = img.getAttribute('xlink:href') || img.getAttribute('href') || img.src || '';
                                                        }
                                                        break;
                                                    }
                                                }
                                            }
                                        }

                                        // F. Tiêu đề trang
                                        if (!name) {
                                            let title = document.title || "";
                                            if (title.includes("| Facebook")) {
                                                let clean = title.replace(/\s*\|\s*Facebook.*/i, "").trim();
                                                if (clean && !clean.toLowerCase().includes("facebook")) name = clean;
                                            }
                                        }

                                        return { name, avatar, token, dtsg };
                                    } catch (e) {
                                        return { error: e.message };
                                    }
                                }
                            });
                            const scriptRes = execResults?.[0]?.result || {};
                            if (scriptRes.name) accountInfo.name = scriptRes.name;
                            if (scriptRes.avatar) accountInfo.avatar = scriptRes.avatar;
                            if (scriptRes.token) accountInfo.token = scriptRes.token;
                            if (scriptRes.dtsg) accountInfo.dtsg = scriptRes.dtsg;
                        } catch (scriptErr) {
                            console.warn("[Bridge] Lỗi inject script lấy thông tin FB:", scriptErr);
                        }
                    }

                    // 2. Dự phòng: Fetch từ mbasic hoặc www.facebook.com/me nếu chưa có Tên hoặc Avatar
                    if (!accountInfo.name || !accountInfo.avatar) {
                        try {
                            const mbRes = await fetch("https://mbasic.facebook.com/profile.php", { credentials: "include" });
                            if (mbRes.ok) {
                                const html = await mbRes.text();
                                const tm = html.match(/<title>([^<]+)<\/title>/i);
                                if (tm && tm[1] && !tm[1].toLowerCase().includes("facebook")) {
                                    if (!accountInfo.name) accountInfo.name = tm[1].trim();
                                }
                                const imgM = html.match(/<img[^>]+src="([^">]*scontent[^">]*fbcdn\.net[^">]+)"/i);
                                if (imgM && imgM[1] && !accountInfo.avatar) {
                                    accountInfo.avatar = imgM[1].replace(/&amp;/g, '&');
                                }
                            }
                        } catch(e) {
                            console.warn("[Bridge] Lỗi fetch mbasic:", e);
                        }
                    }

                    if (!accountInfo.name || !accountInfo.avatar) {
                        try {
                            const meRes = await fetch("https://www.facebook.com/me", { credentials: "include" });
                            if (meRes.ok) {
                                const html = await meRes.text();
                                if (!accountInfo.name) {
                                    const nm = html.match(/"NAME":"([^"]+)"/);
                                    if (nm && nm[1]) {
                                        try { accountInfo.name = JSON.parse(`"${nm[1]}"`); } catch(e) { accountInfo.name = nm[1]; }
                                    }
                                }
                                if (!accountInfo.avatar) {
                                    const pm = html.match(/"PROFILE_PICTURE_URI":"([^"]+)"/);
                                    if (pm && pm[1]) accountInfo.avatar = pm[1].replace(/\\\//g, '/');
                                }
                            }
                        } catch(e) {}
                    }

                    // 3. Dự phòng 3: Lấy trực tiếp từ Graph API endpoint redirect=false (trả về URL CDN thật)
                    if (cUser && (!accountInfo.avatar || accountInfo.avatar.includes("graph.facebook.com"))) {
                        try {
                            const gRes = await fetch(`https://graph.facebook.com/${cUser}/picture?type=large&redirect=false`);
                            if (gRes.ok) {
                                const gData = await gRes.json();
                                if (gData?.data?.url) {
                                    accountInfo.avatar = gData.data.url;
                                }
                            }
                        } catch(e) {}
                    }

                    // Nếu vẫn không có avatar, gán URL graph mặc định
                    if (!accountInfo.avatar && cUser) {
                        accountInfo.avatar = `https://graph.facebook.com/${cUser}/picture?type=large`;
                    }

                    cmdResult = { success: true, ...accountInfo };
                    break;
                }

                case "GET_FLOW_ACCOUNT": {
                    // 1. Quét cookies của cả flow.google.com và .google.com
                    const flowCookies = await chrome.cookies.getAll({ domain: "flow.google.com" });
                    const googleCookies = await chrome.cookies.getAll({ domain: "google.com" });

                    // Gộp & khử trùng lặp
                    const cookieMap = new Map();
                    [...googleCookies, ...flowCookies].forEach(c => {
                        cookieMap.set(`${c.name}@${c.domain}`, c);
                    });
                    const allCookies = Array.from(cookieMap.values());
                    const cookieStr = allCookies.map(c => `${c.name}=${c.value}`).join("; ");

                    // Tìm các cookie nhận diện phiên Google quan trọng
                    let sid = "";
                    let ssid = "";
                    let hsid = "";
                    let sapisid = "";
                    let osid = "";
                    let secure1psid = "";
                    for (const c of allCookies) {
                        if (c.name === "SID") sid = c.value;
                        if (c.name === "SSID") ssid = c.value;
                        if (c.name === "HSID") hsid = c.value;
                        if (c.name === "SAPISID") sapisid = c.value;
                        if (c.name === "OSID") osid = c.value;
                        if (c.name === "__Secure-1PSID") secure1psid = c.value;
                    }

                    const isLoggedIn = !!(sid || secure1psid || osid);

                    let accountInfo = {
                        platform: "flow",
                        domain: "flow.google.com",
                        name: "",
                        email: "",
                        avatar: "",
                        googleUid: "",
                        uid: "",
                        projectId: "",
                        projectName: "",
                        profileUrl: "https://flow.google.com",
                        isLoggedIn: isLoggedIn,
                        cookieCount: allCookies.length,
                        cookieStr: cookieStr,
                        cookies: allCookies,
                        token: "",
                        wizAt: ""
                    };

                    // 2. Quét thông tin từ Tab Google Flow đang mở
                    const tabs = await chrome.tabs.query({});
                    let flowTab = tabs.find(t => t.url && t.url.includes("flow.google.com/project/"))
                        || tabs.find(t => t.url && t.url.includes("flow.google.com"));

                    let createdTabId = null;
                    if (!flowTab) {
                        try {
                            const newTab = await chrome.tabs.create({ url: "https://flow.google.com", active: false });
                            createdTabId = newTab.id;
                            await ensureTabLoaded(createdTabId);
                            await new Promise(r => setTimeout(r, 4000));
                            flowTab = newTab;
                        } catch(e) {}
                    }

                    if (flowTab && flowTab.id) {
                        try {
                            const scanRes = await chrome.scripting.executeScript({
                                target: { tabId: flowTab.id },
                                world: "MAIN",
                                func: () => {
                                    try {
                                        let name = "";
                                        let email = "";
                                        let avatar = "";
                                        let googleUid = "";
                                        let projectId = "";
                                        let projectName = "";

                                        // A. Project ID từ URL
                                        const urlMatch = location.href.match(/\/project\/([a-f0-9-]+)/i);
                                        if (urlMatch) projectId = urlMatch[1];

                                        // B. WIZ_global_data
                                        const wiz = window.WIZ_global_data || {};
                                        const at = wiz.SNlM0e || "";
                                        if (wiz.oPEP7c) googleUid = String(wiz.oPEP7c);
                                        if (!googleUid && wiz.S06Grb) googleUid = String(wiz.S06Grb);

                                        // C. Quét avatar & Google account button
                                        const profileCandidates = Array.from(document.querySelectorAll(
                                            'a[href*="accounts.google.com"], button[aria-label*="Google" i], button[aria-label*="tài khoản" i], button[aria-label*="account" i], [aria-label*="@"]'
                                        ));

                                        for (const el of profileCandidates) {
                                            const label = el.getAttribute("aria-label") || el.getAttribute("title") || "";
                                            if (label) {
                                                const em = label.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
                                                if (em && !email) email = em[1];

                                                const nm = label.match(/(?:Tài khoản Google|Google Account|Tài khoản|Account)[:\s]+([^(\n\r]+?)(?:\s*\(|\s*\n|$)/i);
                                                if (nm && nm[1] && !name) {
                                                    const cleanName = nm[1].trim();
                                                    if (!cleanName.includes("@") && cleanName.length > 1) {
                                                        name = cleanName;
                                                    }
                                                }
                                            }
                                            const img = el.querySelector("img") || (el.tagName === "IMG" ? el : null);
                                            if (img && img.src && (img.src.includes("googleusercontent.com") || img.src.includes("ggpht.com"))) {
                                                avatar = img.src;
                                            }
                                        }

                                        // D. Quét ảnh đại diện googleusercontent.com trong toàn bộ trang
                                        if (!avatar) {
                                            const gImgs = Array.from(document.querySelectorAll('img[src*="googleusercontent.com"], img[src*="ggpht.com"]'));
                                            for (const img of gImgs) {
                                                const s = img.src || "";
                                                if (!s.includes("favicon") && !s.includes("logo") && (img.naturalWidth > 16 || img.width > 16 || !img.width)) {
                                                    avatar = s;
                                                    break;
                                                }
                                            }
                                        }

                                        // E. Tên Project Flow từ DOM
                                        const pTitleEl = document.querySelector(".project-title, .title-input, [data-test-id='project-title'], header h1, header h2");
                                        if (pTitleEl) {
                                            projectName = (pTitleEl.innerText || pTitleEl.value || "").trim();
                                        }
                                        if (!projectName) {
                                            const dt = document.title || "";
                                            if (dt && !dt.toLowerCase().includes("flow")) {
                                                projectName = dt.replace(/\s*-\s*Google Flow.*/i, "").trim();
                                            }
                                        }

                                        return { name, email, avatar, googleUid, projectId, projectName, at, url: location.href };
                                    } catch(e) {
                                        return { error: e.message };
                                    }
                                }
                            });

                            const data = scanRes?.[0]?.result || {};
                            if (data.name) accountInfo.name = data.name;
                            if (data.email) accountInfo.email = data.email;
                            if (data.avatar) accountInfo.avatar = data.avatar;
                            if (data.googleUid) accountInfo.googleUid = data.googleUid;
                            if (data.projectId) accountInfo.projectId = data.projectId;
                            if (data.projectName) accountInfo.projectName = data.projectName;
                            if (data.at) accountInfo.wizAt = data.at;
                            if (data.at) accountInfo.token = data.at;

                        } catch(scanErr) {
                            console.warn("[Bridge] Lỗi inject script Flow:", scanErr);
                        }
                    }

                    // Tự động gán fallback nếu thiếu
                    if (!accountInfo.name && accountInfo.email) {
                        accountInfo.name = accountInfo.email.split("@")[0];
                    }
                    if (!accountInfo.name && accountInfo.projectName) {
                        accountInfo.name = accountInfo.projectName;
                    }
                    if (!accountInfo.name) {
                        accountInfo.name = isLoggedIn ? "Google Flow User" : "Chưa đăng nhập Flow";
                    }

                    accountInfo.uid = accountInfo.email || accountInfo.googleUid || accountInfo.projectId || (isLoggedIn ? "Google Account (LIVE)" : "");
                    if (accountInfo.projectId) {
                        accountInfo.profileUrl = `https://flow.google.com/project/${accountInfo.projectId}`;
                    }

                    // Lưu cache email & projectId để nhịp Heartbeat luôn nhận diện được tài khoản Flow trên Chrome
                    if (accountInfo.email || accountInfo.googleUid || accountInfo.projectId) {
                        try {
                            chrome.storage.local.set({
                                cachedFlowEmail: accountInfo.email || "",
                                cachedFlowGoogleUid: accountInfo.googleUid || "",
                                cachedFlowProjectId: accountInfo.projectId || ""
                            });
                        } catch(e) {}
                    }

                    // Đóng tab tạm nếu vừa mở ngầm
                    if (createdTabId) {
                        setTimeout(() => { chrome.tabs.remove(createdTabId).catch(() => {}); }, 1000);
                    }

                    cmdResult = { success: true, ...accountInfo };
                    break;
                }

                case "GET_X_ACCOUNT": {
                    // 1. Quét cookies của cả x.com và twitter.com
                    const xCookies = await chrome.cookies.getAll({ domain: "x.com" });
                    const twCookies = await chrome.cookies.getAll({ domain: "twitter.com" });

                    // Gộp & khử trùng lặp theo name@domain
                    const cookieMap = new Map();
                    [...xCookies, ...twCookies].forEach(c => {
                        cookieMap.set(`${c.name}@${c.domain}`, c);
                    });
                    const allCookies = Array.from(cookieMap.values());
                    const cookieStr = allCookies.map(c => `${c.name}=${c.value}`).join("; ");

                    // Tìm các cookie nhận diện phiên X cốt lõi
                    let authToken = "";
                    let ct0 = "";
                    let twid = "";
                    let kdt = "";
                    let guestId = "";
                    let personalizationId = "";
                    for (const c of allCookies) {
                        if (c.name === "auth_token") authToken = c.value;
                        if (c.name === "ct0") ct0 = c.value;
                        if (c.name === "twid") twid = c.value;
                        if (c.name === "kdt") kdt = c.value;
                        if (c.name === "guest_id" || c.name === "guest_id_marketing" || c.name === "guest_id_ads") guestId = c.value;
                        if (c.name === "personalization_id") personalizationId = c.value;
                    }

                    // Giải mã User ID số từ twid cookie (ví dụ "u%3D12345678" hoặc "u=12345678")
                    let numericUid = "";
                    if (twid) {
                        try {
                            const decodedTwid = decodeURIComponent(twid);
                            const m = decodedTwid.match(/u=(\d+)/);
                            if (m) numericUid = m[1];
                        } catch(e) {}
                    }

                    const isLoggedIn = !!authToken;

                    let accountInfo = {
                        platform: "x",
                        domain: "x.com",
                        name: "",
                        username: "",
                        screenName: "",
                        uid: numericUid,
                        restId: numericUid,
                        avatar: "",
                        profileUrl: "",
                        bio: "",
                        followersCount: 0,
                        followingCount: 0,
                        tweetsCount: 0,
                        isVerified: false,
                        isLoggedIn: isLoggedIn,
                        cookieCount: allCookies.length,
                        cookieStr: cookieStr,
                        cookies: allCookies,
                        authToken: authToken,
                        ct0: ct0,
                        twid: twid,
                        kdt: kdt,
                        guestId: guestId,
                        personalizationId: personalizationId
                    };

                    // 2. TẦNG 1: Gọi API xác thực chính thức của Twitter/X Web Client
                    // Bearer token chuẩn công khai được Twitter web app sử dụng
                    const TWITTER_BEARER = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA";
                    if (authToken) {
                        try {
                            const headers = {
                                "Authorization": TWITTER_BEARER,
                                "x-twitter-auth-type": "OAuth2Session",
                                "x-twitter-active-user": "yes"
                            };
                            if (ct0) headers["x-csrf-token"] = ct0;

                            const vRes = await fetch("https://x.com/i/api/1.1/account/verify_credentials.json", {
                                headers,
                                credentials: "include"
                            });

                            if (vRes.ok) {
                                const uData = await vRes.json();
                                if (uData && (uData.screen_name || uData.id_str)) {
                                    accountInfo.username = uData.screen_name || "";
                                    accountInfo.screenName = uData.screen_name || "";
                                    accountInfo.name = uData.name || uData.screen_name || "";
                                    accountInfo.uid = String(uData.id_str || uData.id || accountInfo.uid);
                                    accountInfo.restId = accountInfo.uid;
                                    accountInfo.bio = uData.description || "";
                                    accountInfo.followersCount = uData.followers_count || 0;
                                    accountInfo.followingCount = uData.friends_count || 0;
                                    accountInfo.tweetsCount = uData.statuses_count || 0;
                                    accountInfo.isVerified = !!uData.verified;
                                    if (uData.profile_image_url_https) {
                                        accountInfo.avatar = uData.profile_image_url_https.replace("_normal.", "_400x400.");
                                    }
                                    accountInfo.profileUrl = `https://x.com/${uData.screen_name}`;
                                }
                            }
                        } catch(apiErr) {
                            console.warn("[Bridge] Lỗi fetch X verify_credentials:", apiErr);
                        }
                    }

                    // 3. TẦNG 2: Nếu chưa có username hoặc avatar, quét từ tab x.com / twitter.com đang mở
                    if (!accountInfo.username || !accountInfo.avatar) {
                        const tabs = await chrome.tabs.query({});
                        let xTab = tabs.find(t => t.url && (t.url.includes("x.com") || t.url.includes("twitter.com")));

                        let createdTabId = null;
                        if (!xTab && isLoggedIn) {
                            try {
                                const newTab = await chrome.tabs.create({ url: "https://x.com/home", active: false });
                                createdTabId = newTab.id;
                                await ensureTabLoaded(createdTabId);
                                await new Promise(r => setTimeout(r, 3500));
                                xTab = newTab;
                            } catch(e) {}
                        }

                        if (xTab && xTab.id) {
                            try {
                                const scanRes = await chrome.scripting.executeScript({
                                    target: { tabId: xTab.id },
                                    world: "MAIN",
                                    func: () => {
                                        try {
                                            let name = "";
                                            let username = "";
                                            let avatar = "";
                                            let bio = "";

                                            // A. Profile Link in Sidebar: a[data-testid="AppTabBar_Profile_Link"]
                                            const profLink = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
                                            if (profLink) {
                                                const href = profLink.getAttribute("href") || "";
                                                const m = href.match(/^\/([a-zA-Z0-9_]+)/);
                                                if (m && m[1] && !["home", "explore", "notifications", "messages", "i", "settings"].includes(m[1].toLowerCase())) {
                                                    username = m[1];
                                                }
                                            }

                                            // B. Account Switcher Button in bottom navbar
                                            const accBtn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
                                            if (accBtn) {
                                                const img = accBtn.querySelector('img');
                                                if (img && img.src) {
                                                    avatar = img.src.replace('_normal.', '_400x400.');
                                                }
                                                const spans = Array.from(accBtn.querySelectorAll('span, div[dir="ltr"]'));
                                                for (const s of spans) {
                                                    const t = (s.innerText || "").trim();
                                                    if (t.startsWith("@") && !username) {
                                                        username = t.substring(1);
                                                    } else if (t && !t.startsWith("@") && !name && t.length > 1 && !t.includes("\n")) {
                                                        name = t;
                                                    }
                                                }
                                            }

                                            // C. On User Profile Page
                                            const uNameEl = document.querySelector('[data-testid="UserName"]');
                                            if (uNameEl) {
                                                const lines = (uNameEl.innerText || "").split("\n").map(l => l.trim()).filter(Boolean);
                                                for (const l of lines) {
                                                    if (l.startsWith("@") && !username) username = l.substring(1);
                                                    else if (!l.startsWith("@") && !name) name = l;
                                                }
                                            }

                                            // D. Avatar image on page
                                            if (!avatar) {
                                                const avImg = document.querySelector('img[src*="profile_images"]');
                                                if (avImg && avImg.src) avatar = avImg.src.replace('_normal.', '_400x400.');
                                            }

                                            return { name, username, avatar, bio };
                                        } catch(e) {
                                            return { error: e.message };
                                        }
                                    }
                                });

                                const tabData = scanRes?.[0]?.result || {};
                                if (tabData.username && !accountInfo.username) accountInfo.username = tabData.username;
                                if (tabData.username && !accountInfo.screenName) accountInfo.screenName = tabData.username;
                                if (tabData.name && !accountInfo.name) accountInfo.name = tabData.name;
                                if (tabData.avatar && !accountInfo.avatar) accountInfo.avatar = tabData.avatar;
                                if (tabData.bio && !accountInfo.bio) accountInfo.bio = tabData.bio;
                            } catch(errTab) {
                                console.warn("[Bridge] Lỗi inject script tab X:", errTab);
                            }
                        }

                        if (createdTabId) {
                            setTimeout(() => { chrome.tabs.remove(createdTabId).catch(() => {}); }, 1000);
                        }
                    }

                    // 4. Fallback gán giá trị mặc định nếu thiếu
                    if (accountInfo.username) {
                        accountInfo.profileUrl = `https://x.com/${accountInfo.username}`;
                        if (!accountInfo.name) accountInfo.name = `@${accountInfo.username}`;
                    } else if (numericUid) {
                        accountInfo.username = `id_${numericUid}`;
                        accountInfo.profileUrl = `https://x.com/i/user/${numericUid}`;
                        if (!accountInfo.name) accountInfo.name = `X User (${numericUid})`;
                    } else {
                        accountInfo.name = isLoggedIn ? "Tài khoản X (Đã Đăng Nhập)" : "Chưa đăng nhập X";
                    }

                    accountInfo.uid = accountInfo.uid || accountInfo.username || (isLoggedIn ? "X_SESSION_LIVE" : "");

                    // Lưu cache username & uid để heartbeat luôn nhận diện
                    if (accountInfo.username || accountInfo.uid) {
                        try {
                            chrome.storage.local.set({
                                cachedXUsername: accountInfo.username || "",
                                cachedXUid: accountInfo.uid || ""
                            });
                        } catch(e) {}
                    }

                    cmdResult = { success: true, ...accountInfo };
                    break;
                }

                case "OPEN_TAB": {
                    const newTab = await chrome.tabs.create({ url: cmd.url || "https://www.google.com", active: cmd.active !== false });
                    cmdResult = { success: true, tabId: newTab.id, url: newTab.url };
                    break;
                }

                case "CLOSE_TAB": {
                    if (cmd.tabId) {
                        await chrome.tabs.remove(cmd.tabId);
                        cmdResult = { success: true, closedTabId: cmd.tabId };
                    } else {
                        cmdResult = { success: false, error: "Thiếu tabId" };
                    }
                    break;
                }

                case "NAVIGATE_TAB": {
                    let targetTabId = cmd.tabId;
                    if (!targetTabId) {
                        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
                        targetTabId = activeTab?.id;
                    }
                    if (targetTabId && cmd.url) {
                        const updated = await chrome.tabs.update(targetTabId, { url: cmd.url });
                        cmdResult = { success: true, tabId: updated.id, url: updated.url };
                    } else {
                        cmdResult = { success: false, error: "Thiếu tabId hoặc URL" };
                    }
                    break;
                }

                case "GET_TABS": {
                    const tabs = await chrome.tabs.query({});
                    cmdResult = {
                        success: true,
                        tabs: tabs.map(t => ({ id: t.id, url: t.url, title: t.title, active: t.active }))
                    };
                    break;
                }

                case "FLOW_DEBUG_INSPECT": {
                    const tabs = await chrome.tabs.query({});
                    const targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com/project/")) || tabs.find(t => t.url && t.url.includes("flow.google.com"));
                    if (!targetTab) {
                        cmdResult = { success: false, error: "No flow tab found" };
                        break;
                    }
                    const res = await chrome.scripting.executeScript({
                        target: { tabId: targetTab.id },
                        world: "MAIN",
                        func: (testAction) => {
                            try {
                                const ed = document.querySelector(".ProseMirror");
                                const btn = document.querySelector(".generate-icon-button") 
                                         || document.querySelector('button[type="submit"]')
                                         || document.querySelector('button[aria-label="Bắt đầu tạo"]')
                                         || document.querySelector('button[aria-label*="tạo" i]')
                                         || document.querySelector('button[aria-label*="generate" i]');

                                const form = btn ? btn.closest('form') : (ed ? ed.closest('form') : null);

                                let actionResult = null;
                                const forms = Array.from(document.querySelectorAll("form")).map(f => ({
                                    action: f.action,
                                    id: f.id,
                                    className: f.className,
                                    containsBtn: btn ? f.contains(btn) : false,
                                    containsEd: ed ? f.contains(ed) : false
                                }));

                                const getZoneListeners = (element) => {
                                    if (!element) return null;
                                    const res = {};
                                    for (let k in element) {
                                        if (k.includes("zone") || k.includes("event") || k.includes("Listener") || k.includes("__ng")) {
                                            res[k] = typeof element[k] === "function" ? "[Function]" : (Array.isArray(element[k]) ? `[Array(${element[k].length})]` : typeof element[k]);
                                        }
                                    }
                                    return res;
                                };

                                const zoneInfo = {
                                    btn: getZoneListeners(btn),
                                    flowBtn: getZoneListeners(document.querySelector("flow-generate-icon-button")),
                                    ed: getZoneListeners(ed)
                                };

                                if (testAction === "pointer_sequence" && btn) {
                                    try {
                                        const evOpts = { bubbles: true, cancelable: true, view: window, pointerId: 1, isPrimary: true, button: 0 };
                                        btn.dispatchEvent(new PointerEvent("pointerdown", evOpts));
                                        btn.dispatchEvent(new MouseEvent("mousedown", evOpts));
                                        btn.dispatchEvent(new PointerEvent("pointerup", evOpts));
                                        btn.dispatchEvent(new MouseEvent("mouseup", evOpts));
                                        btn.dispatchEvent(new MouseEvent("click", evOpts));
                                        actionResult = "pointer_sequence dispatched on btn";
                                    } catch(e) {
                                        actionResult = "pointer_sequence error: " + e.message;
                                    }
                                } else if (testAction === "pointer_sequence_icon") {
                                    try {
                                        const icon = btn ? btn.querySelector("mat-icon") : null;
                                        const target = icon || btn;
                                        if (target) {
                                            const evOpts = { bubbles: true, cancelable: true, view: window, pointerId: 1, isPrimary: true, button: 0 };
                                            target.dispatchEvent(new PointerEvent("pointerdown", evOpts));
                                            target.dispatchEvent(new MouseEvent("mousedown", evOpts));
                                            target.dispatchEvent(new PointerEvent("pointerup", evOpts));
                                            target.dispatchEvent(new MouseEvent("mouseup", evOpts));
                                            target.dispatchEvent(new MouseEvent("click", evOpts));
                                            actionResult = "pointer_sequence dispatched on " + target.tagName;
                                        }
                                    } catch(e) {
                                        actionResult = "pointer_sequence_icon error: " + e.message;
                                    }
                                } else if (testAction === "press_ctrl_enter" && ed) {
                                    try {
                                        ed.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, ctrlKey: true, bubbles: true, cancelable: true }));
                                        ed.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, ctrlKey: true, bubbles: true, cancelable: true }));
                                        actionResult = "Ctrl+Enter dispatched";
                                    } catch(e) {
                                        actionResult = "Ctrl+Enter error: " + e.message;
                                    }
                                } else if (testAction === "press_cmd_enter" && ed) {
                                    try {
                                        ed.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, metaKey: true, bubbles: true, cancelable: true }));
                                        ed.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, metaKey: true, bubbles: true, cancelable: true }));
                                        actionResult = "Cmd+Enter dispatched";
                                    } catch(e) {
                                        actionResult = "Cmd+Enter error: " + e.message;
                                    }
                                } else if (testAction === "press_plain_enter" && ed) {
                                    try {
                                        ed.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }));
                                        ed.dispatchEvent(new KeyboardEvent("keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true, cancelable: true }));
                                        actionResult = "Plain Enter dispatched";
                                    } catch(e) {
                                        actionResult = "Plain Enter error: " + e.message;
                                    }
                                } else if (testAction === "click_btn" && btn) {
                                    try {
                                        btn.click();
                                        actionResult = "btn.click() called";
                                    } catch(e) {
                                        actionResult = "btn.click() error: " + e.message;
                                    }
                                }

                                let ngLView = null;
                                let p = btn;
                                while (p && !(p.__ngContext__ && Array.isArray(p.__ngContext__))) {
                                    p = p.parentElement;
                                }
                                if (p && Array.isArray(p.__ngContext__)) {
                                    ngLView = p.tagName + ": " + p.__ngContext__.map(x => x && typeof x === 'object' ? (x.constructor ? x.constructor.name : typeof x) : typeof x).slice(0, 25).join(", ");
                                }

                                let parentChain = [];
                                let curr = btn;
                                for (let i = 0; i < 5 && curr; i++) {
                                    const c = curr.getAttribute ? (curr.getAttribute('class') || '') : '';
                                    parentChain.push(`${curr.tagName}.${c.replace(/\s+/g, '.')}`);
                                    curr = curr.parentElement;
                                }

                                const imgs = Array.from(document.querySelectorAll("img")).map(i => i.src);
                                const flowImgs = imgs.filter(s => s.includes("flow-content.google") || s.includes("/asb/"));

                                const btnRect = btn ? btn.getBoundingClientRect() : null;
                                const edRect = ed ? ed.getBoundingClientRect() : null;

                                let elAtPoint = null;
                                if (btnRect) {
                                    const fx = Math.round((btnRect.left !== undefined ? btnRect.left : btnRect.x) + (btnRect.width || 0) / 2);
                                    const fy = Math.round((btnRect.top !== undefined ? btnRect.top : btnRect.y) + (btnRect.height || 0) / 2);
                                    const el = document.elementFromPoint(fx, fy);
                                    const c = el && el.getAttribute ? (el.getAttribute('class') || '') : '';
                                    elAtPoint = el ? `${el.tagName}.${c.replace(/\s+/g, '.')}` : null;
                                }

                                // Inspect CDK Overlays
                                const overlays = Array.from(document.querySelectorAll(".cdk-overlay-pane")).map(o => ({
                                    className: o.className,
                                    text: (o.innerText || '').substring(0, 100)
                                }));
                                const backdrops = document.querySelectorAll(".cdk-overlay-backdrop");

                                let backdropClosed = false;
                                if (testAction === "dismiss_overlay") {
                                    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                    document.dispatchEvent(new KeyboardEvent("keyup", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                    window.dispatchEvent(new KeyboardEvent("keyup", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                    document.querySelectorAll(".cdk-overlay-backdrop").forEach(b => {
                                        b.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
                                    });
                                    backdropClosed = true;
                                }

                                return {
                                    title: document.title,
                                    url: location.href,
                                    activeElement: document.activeElement ? document.activeElement.tagName + "." + document.activeElement.className : null,
                                    editorText: ed ? ed.innerText : null,
                                    btnFound: !!btn,
                                    btnTag: btn ? btn.tagName : null,
                                    btnType: btn ? btn.type : null,
                                    btnDisabled: btn ? (btn.disabled || btn.classList.contains("mat-mdc-button-disabled")) : null,
                                    btnAria: btn ? btn.getAttribute("aria-label") : null,
                                    btnRect: btnRect ? { x: Math.round(btnRect.left || btnRect.x), y: Math.round(btnRect.top || btnRect.y), w: Math.round(btnRect.width), h: Math.round(btnRect.height) } : null,
                                    edRect: edRect ? { x: Math.round(edRect.left || edRect.x), y: Math.round(edRect.top || edRect.y), w: Math.round(edRect.width), h: Math.round(edRect.height) } : null,
                                    elAtPoint: elAtPoint,
                                    ngInfo: null,
                                    ngLView: ngLView,
                                    overlays: overlays,
                                    backdropsCount: backdrops.length,
                                    backdropClosed: backdropClosed,
                                    btnParentChain: parentChain,
                                    hasForm: !!form,
                                    forms: forms,
                                    zoneInfo: zoneInfo,
                                    actionResult: actionResult,
                                    totalImgs: imgs.length,
                                    flowImgsCount: flowImgs.length,
                                    flowImgs: flowImgs.slice(-5),
                                    capturedImgs: (window.__capturedImages || []).slice(-5)
                                };
                            } catch(err) {
                                return { funcError: err.message, funcStack: err.stack };
                            }
                        },
                        args: [cmd.testAction || ""]
                    });
                    let cdpInfo = null;
                    if (cmd.testAction === "cdp_press_enter") {
                        let dbgAttached = false;
                        await new Promise(r => {
                            chrome.debugger.attach({ tabId: targetTab.id }, "1.3", () => {
                                if (chrome.runtime.lastError) {
                                    cdpInfo = "attach warning: " + chrome.runtime.lastError.message;
                                    r();
                                } else {
                                    dbgAttached = true;
                                    r();
                                }
                            });
                        });

                        if (dbgAttached) {
                            try {
                                const sendDbg = (m, p) => new Promise(res => {
                                    chrome.debugger.sendCommand({ tabId: targetTab.id }, m, p, (ret) => res(ret));
                                });

                                await sendDbg("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r", unmodifiedText: "\r" });
                                await sendDbg("Input.dispatchKeyEvent", { type: "char", text: "\r" });
                                await sendDbg("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
                                cdpInfo = "cdp Enter key sent";
                            } catch(e) {
                                cdpInfo = "cdp send error: " + e.message;
                            } finally {
                                try { chrome.debugger.detach({ tabId: targetTab.id }, () => {}); } catch(e) {}
                            }
                        }
                    } else if (cmd.testAction === "cdp_click_btn") {
                        let dbgAttached = false;
                        await new Promise(r => {
                            chrome.debugger.attach({ tabId: targetTab.id }, "1.3", () => {
                                if (chrome.runtime.lastError) {
                                    cdpInfo = "attach warning: " + chrome.runtime.lastError.message;
                                    r();
                                } else {
                                    dbgAttached = true;
                                    r();
                                }
                            });
                        });

                        if (dbgAttached) {
                            try {
                                const sendDbg = (m, p) => new Promise(res => {
                                    chrome.debugger.sendCommand({ tabId: targetTab.id }, m, p, (ret) => res(ret));
                                });

                                const br = res?.[0]?.result?.btnRect;
                                if (br) {
                                    const fx = br.x + Math.round(br.w / 2);
                                    const fy = br.y + Math.round(br.h / 2);
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseMoved", x: fx, y: fy });
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mousePressed", x: fx, y: fy, button: "left", clickCount: 1 });
                                    await new Promise(r => setTimeout(r, 120));
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseReleased", x: fx, y: fy, button: "left", clickCount: 1 });
                                    cdpInfo = `cdp click sent to (${fx}, ${fy})`;
                                }
                            } catch(e) {
                                cdpInfo = "cdp send error: " + e.message;
                            } finally {
                                try { chrome.debugger.detach({ tabId: targetTab.id }, () => {}); } catch(e) {}
                            }
                        }
                    } else if (cmd.testAction === "test_active_click") {
                        const tabsInWin = await chrome.tabs.query({ active: true, windowId: targetTab.windowId });
                        const origActiveTab = tabsInWin[0];

                        await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: () => {
                                document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                document.querySelectorAll(".cdk-overlay-backdrop").forEach(b => b.dispatchEvent(new MouseEvent("click", { bubbles: true })));
                            }
                        });

                        await chrome.tabs.update(targetTab.id, { active: true });
                        await new Promise(r => setTimeout(r, 120));

                        let dbgAttached = false;
                        await new Promise(r => {
                            chrome.debugger.attach({ tabId: targetTab.id }, "1.3", () => {
                                if (!chrome.runtime.lastError) dbgAttached = true;
                                r();
                            });
                        });

                        if (dbgAttached) {
                            try {
                                const sendDbg = (m, p) => new Promise(res => {
                                    chrome.debugger.sendCommand({ tabId: targetTab.id }, m, p, (ret) => res(ret));
                                });

                                const btnRes = await chrome.scripting.executeScript({
                                    target: { tabId: targetTab.id },
                                    world: "MAIN",
                                    func: () => {
                                        const btn = document.querySelector(".generate-icon-button") 
                                                 || document.querySelector('button[aria-label="Bắt đầu tạo"]')
                                                 || document.querySelector('button[aria-label*="tạo" i]');
                                        if (!btn) return null;
                                        const r = btn.getBoundingClientRect();
                                        return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), disabled: btn.disabled };
                                    }
                                });

                                const br = btnRes?.[0]?.result;
                                if (br) {
                                    const fx = br.x + Math.round(br.w / 2);
                                    const fy = br.y + Math.round(br.h / 2);
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseMoved", x: fx, y: fy });
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mousePressed", x: fx, y: fy, button: "left", clickCount: 1 });
                                    await new Promise(r => setTimeout(r, 60));
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseReleased", x: fx, y: fy, button: "left", clickCount: 1 });
                                    cdpInfo = `active click sent to (${fx}, ${fy}), disabled: ${br.disabled}`;
                                }
                            } finally {
                                try { chrome.debugger.detach({ tabId: targetTab.id }, () => {}); } catch(e) {}
                            }
                        }

                        if (origActiveTab && origActiveTab.id !== targetTab.id) {
                            await chrome.tabs.update(origActiveTab.id, { active: true });
                        }
                    } else if (cmd.testAction === "test_inactive_submit") {
                        // 1. Inject prompt without activating tab
                        await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: (promptText) => {
                                document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
                                document.querySelectorAll(".cdk-overlay-backdrop").forEach(b => b.dispatchEvent(new MouseEvent("click", { bubbles: true })));

                                const ed = document.querySelector(".ProseMirror");
                                if (ed) {
                                    ed.focus();
                                    const sel = window.getSelection();
                                    const range = document.createRange();
                                    range.selectNodeContents(ed);
                                    sel.removeAllRanges();
                                    sel.addRange(range);
                                    document.execCommand("delete");
                                    document.execCommand("insertText", false, promptText);
                                    ed.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
                                    ed.dispatchEvent(new Event("change", { bubbles: true }));
                                }
                            },
                            args: ["test chu chim bay tren troi xanh"]
                        });

                        await new Promise(r => setTimeout(r, 200));

                        // 2. Attach debugger
                        let dbgAttached = false;
                        await new Promise(r => {
                            chrome.debugger.attach({ tabId: targetTab.id }, "1.3", () => {
                                if (!chrome.runtime.lastError) dbgAttached = true;
                                r();
                            });
                        });

                        if (dbgAttached) {
                            try {
                                const sendDbg = (m, p) => new Promise(res => {
                                    chrome.debugger.sendCommand({ tabId: targetTab.id }, m, p, (ret) => res(ret));
                                });

                                const btnRes = await chrome.scripting.executeScript({
                                    target: { tabId: targetTab.id },
                                    world: "MAIN",
                                    func: () => {
                                        const btn = document.querySelector(".generate-icon-button") 
                                                 || document.querySelector('button[aria-label="Bắt đầu tạo"]')
                                                 || document.querySelector('button[aria-label*="tạo" i]');
                                        if (!btn) return null;
                                        const r = btn.getBoundingClientRect();
                                        return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), disabled: btn.disabled };
                                    }
                                });

                                const br = btnRes?.[0]?.result;
                                if (br) {
                                    const fx = br.x + Math.round(br.w / 2);
                                    const fy = br.y + Math.round(br.h / 2);
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseMoved", x: fx, y: fy });
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mousePressed", x: fx, y: fy, button: "left", clickCount: 1 });
                                    await new Promise(r => setTimeout(r, 60));
                                    await sendDbg("Input.dispatchMouseEvent", { type: "mouseReleased", x: fx, y: fy, button: "left", clickCount: 1 });
                                    cdpInfo = `inactive click sent to (${fx}, ${fy}), disabled: ${br.disabled}`;
                                }
                            } finally {
                                try { chrome.debugger.detach({ tabId: targetTab.id }, () => {}); } catch(e) {}
                            }
                        }
                    }

                    const flowInfo = res?.[0]?.result || {};
                    if (cdpInfo) flowInfo.cdpInfo = cdpInfo;
                    cmdResult = { success: true, flowInfo: flowInfo, tabId: targetTab.id };
                    break;
                }

                case "SELECT_TAB": {
                    const tabId = Number(cmd.tabId);
                    if (tabId) {
                        await chrome.tabs.update(tabId, { active: true });
                        cmdResult = { success: true, tabId };
                    } else {
                        cmdResult = { success: false, error: "Thiếu tabId" };
                    }
                    break;
                }

                case "EXECUTE_SCRIPT": {
                    let targetTabId = cmd.tabId;
                    if (!targetTabId) {
                        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
                        targetTabId = activeTab?.id;
                    }

                    if (!targetTabId) {
                        cmdResult = { success: false, error: "Không tìm thấy tab phù hợp để thực thi script" };
                        break;
                    }

                    const scriptCode = cmd.code || "document.title";
                    const execResults = await chrome.scripting.executeScript({
                        target: { tabId: targetTabId },
                        world: cmd.world || "ISOLATED",
                        func: (codeStr) => {
                            try {
                                const fn = new Function('"use strict"; return (' + codeStr + ')');
                                return { success: true, evalResult: fn() };
                            } catch (e) {
                                try {
                                    const fnStmt = new Function('"use strict"; ' + codeStr);
                                    return { success: true, evalResult: fnStmt() };
                                } catch (e2) {
                                    return { success: false, error: e2.message || e.message };
                                }
                            }
                        },
                        args: [scriptCode]
                    });

                    const resObj = execResults?.[0]?.result || { success: false, error: "Không nhận được phản hồi từ tab" };
                    cmdResult = { success: resObj.success, data: resObj.evalResult, error: resObj.error, tabId: targetTabId };
                    break;
                }

                case "INSPECT_FLOW": {
                    const tabs = await chrome.tabs.query({});
                    const flowTabs = tabs.filter(t => t.url && t.url.includes("flow.google.com"));
                    if (flowTabs.length === 0) {
                        cmdResult = { success: false, error: "Không tìm thấy tab flow.google.com nào đang mở" };
                        break;
                    }
                    const targetTab = flowTabs.find(t => t.url.includes("/project/")) || flowTabs[0];
                    // Chạy ngầm trong background, không kích hoạt tab hoặc cửa sổ Flow

                    // 1. Phân tích DOM & ProseMirror trong MAIN world
                    const execRes = await chrome.scripting.executeScript({
                        target: { tabId: targetTab.id },
                        world: "MAIN",
                        func: async () => {
                            try {
                                const wiz = window.WIZ_global_data || {};
                                const editorEl = document.querySelector(".ProseMirror");
                                const genBtn = document.querySelector(".generate-icon-button") || document.querySelector('button[aria-label="Bắt đầu tạo"]');

                                // Khám phá pmViewDesc
                                let pmInfo = {};
                                if (editorEl && editorEl.pmViewDesc) {
                                    const d = editorEl.pmViewDesc;
                                    pmInfo = {
                                        descKeys: Object.keys(d),
                                        hasView: !!d.view,
                                        viewKeys: d.view ? Object.keys(d.view) : [],
                                        hasState: !!(d.view && d.view.state),
                                        hasDispatch: !!(d.view && typeof d.view.dispatch === "function")
                                    };
                                }

                                // Danh sách tất cả button trong footer / prompt box
                                const allBtns = Array.from(document.querySelectorAll("button")).map(b => ({
                                    ariaLabel: b.getAttribute("aria-label"),
                                    className: b.className,
                                    text: (b.innerText || "").trim().substring(0, 30),
                                    disabled: b.disabled || b.classList.contains("mat-mdc-button-disabled"),
                                    rect: (() => {
                                        const r = b.getBoundingClientRect();
                                        return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
                                    })()
                                })).filter(b => b.rect.w > 0 && b.rect.h > 0);

                                const editorRect = editorEl ? (() => {
                                    const r = editorEl.getBoundingClientRect();
                                    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
                                })() : null;

                                const genBtnRect = genBtn ? (() => {
                                    const r = genBtn.getBoundingClientRect();
                                    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
                                })() : null;

                                // Danh sách tất cả ảnh và thẻ trên Flow
                                const allImages = Array.from(document.querySelectorAll("img")).map(i => ({
                                    src: i.src,
                                    w: i.naturalWidth || i.width,
                                    h: i.naturalHeight || i.height,
                                    alt: i.alt || ""
                                }));

                                // Khám phá menu Lựa chọn khác của Dự án (more-options-button)
                                const projMoreBtn = document.querySelector(".more-options-button") || document.querySelector('button[aria-label*="dự án" i]');
                                let projMenuOptions = [];
                                if (projMoreBtn) {
                                    projMoreBtn.click();
                                    await new Promise(r => setTimeout(r, 400));
                                    projMenuOptions = Array.from(document.querySelectorAll(".mat-mdc-menu-item, [role='menuitem'], .mdc-list-item")).map(m => ({
                                        text: m.innerText ? m.innerText.trim() : "",
                                        className: m.className,
                                        ariaLabel: m.getAttribute("aria-label")
                                    }));
                                    document.body.click();
                                }

                                // Khám phá menu của ô ảnh (Tile menu)
                                let tileMenuOptions = [];
                                const flowImgs = Array.from(document.querySelectorAll("img")).filter(i => i.src && (i.src.includes("/asb/") || i.src.includes("flow-content")));
                                if (flowImgs.length > 0) {
                                    let cur = flowImgs[0].parentElement;
                                    let tileMoreBtn = null;
                                    for (let d = 0; d < 5 && cur && !tileMoreBtn; d++) {
                                        tileMoreBtn = cur.querySelector('button[aria-label="Tuỳ chọn khác"], button[aria-label*="khác" i], button[aria-label*="options" i]');
                                        cur = cur.parentElement;
                                    }
                                    if (tileMoreBtn) {
                                        tileMoreBtn.click();
                                        await new Promise(r => setTimeout(r, 500));
                                        tileMenuOptions = Array.from(document.querySelectorAll(".mat-mdc-menu-item, [role='menuitem'], .mdc-list-item")).map(m => ({
                                            text: m.innerText ? m.innerText.trim() : "",
                                            className: m.className,
                                            ariaLabel: m.getAttribute("aria-label")
                                        }));
                                        document.body.click();
                                        await new Promise(r => setTimeout(r, 200));
                                    }
                                }

                                // Khám phá DOM cây phả hệ của ảnh trên Flow canvas để tìm nút xóa/menu
                                let imgHierarchy = [];
                                if (flowImgs.length > 0) {
                                    let cur = flowImgs[0];
                                    for (let depth = 0; depth < 10 && cur; depth++) {
                                        imgHierarchy.push({
                                            depth,
                                            tag: cur.tagName.toLowerCase(),
                                            className: cur.className,
                                            btns: Array.from(cur.querySelectorAll("button")).map(b => ({
                                                text: (b.innerText || "").trim().substring(0, 30),
                                                ariaLabel: b.getAttribute("aria-label"),
                                                className: b.className
                                            }))
                                        });
                                        cur = cur.parentElement;
                                    }
                                }

                                const cardsInfo = Array.from(document.querySelectorAll("flow-media-card, mat-card, .card, [class*='node'], [role='article']")).map(c => {
                                    const btns = Array.from(c.querySelectorAll("button")).map(b => ({
                                        text: b.innerText ? b.innerText.trim() : "",
                                        ariaLabel: b.getAttribute("aria-label"),
                                        className: b.className
                                    }));
                                    const imgs = Array.from(c.querySelectorAll("img")).map(i => i.src);
                                    return {
                                        tag: c.tagName,
                                        className: c.className,
                                        btns,
                                        imgCount: imgs.length,
                                        firstImg: imgs[0] ? imgs[0].substring(0, 80) : ""
                                    };
                                }).filter(c => c.imgCount > 0);

                                let testToken = null;
                                let testTokenErr = null;
                                try {
                                    if (window.grecaptcha && window.grecaptcha.enterprise && typeof window.grecaptcha.enterprise.execute === "function") {
                                        testToken = await window.grecaptcha.enterprise.execute("6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV");
                                    }
                                } catch(te) {
                                    testTokenErr = te.message || String(te);
                                }

                                return {
                                    url: window.location.href,
                                    title: document.title,
                                    testToken: testToken ? (testToken.substring(0, 40) + "...") : null,
                                    testTokenErr,
                                    recaptchaInfo: {
                                        hasGrecaptcha: !!window.grecaptcha,
                                        hasEnterprise: !!(window.grecaptcha && window.grecaptcha.enterprise),
                                        enterpriseKeys: (window.grecaptcha && window.grecaptcha.enterprise) ? Object.keys(window.grecaptcha.enterprise) : []
                                    },
                                    wizInfo: {
                                        at: wiz.SNlM0e || "",
                                        f_sid: wiz["FdrFJe"] || "",
                                        bl: wiz["cfb2h"] || "",
                                        oPEP7c: wiz["oPEP7c"] || ""
                                    },
                                    allBtns,
                                    genBtnHTML: genBtn ? genBtn.outerHTML.substring(0, 300) : null,
                                    editorHTML: editorEl ? editorEl.outerHTML.substring(0, 300) : null,
                                    allImages,
                                    imgHierarchy,
                                    cardsInfo: cardsInfo.slice(0, 10),
                                    projMenuOptions,
                                    tileMenuOptions,
                                    editorText: editorEl ? editorEl.innerText.trim() : "",
                                    genBtnDisabled: genBtn ? (genBtn.disabled || genBtn.classList.contains("mat-mdc-button-disabled")) : null
                                };
                            } catch (e) {
                                return { error: e.message };
                            }
                        }
                    });

                    const domInfo = execRes?.[0]?.result || {};

                    cmdResult = { success: true, tabId: targetTab.id, flowInfo: domInfo };
                    break;
                }

                case "RELOAD_EXTENSION": {
                    cmdResult = { success: true, message: "Reloading extension..." };
                    setTimeout(() => { chrome.runtime.reload(); }, 100);
                    break;
                }

                case "POST_STORY": {
                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    postId: cmd.post ? cmd.post.id : cmd.postId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}
                    };

                    const postPayload = cmd.post || cmd.payload || {};
                    const postRes = await _executeFbPost(postPayload, updateStep);
                    cmdResult = {
                        ...postRes,
                        postId: postPayload.id
                    };
                    if (!postRes || !postRes.success) {
                        await updateStep(`❌ Đăng bài thất bại: ${postRes?.error || "Lỗi không xác định"}`);
                    }
                    break;
                }

                case "POST_TWEET": {
                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    postId: cmd.post ? cmd.post.id : cmd.postId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}
                    };

                    const postPayload = cmd.post || cmd.payload || {};
                    const postRes = await _executeXTweet(postPayload, updateStep);
                    cmdResult = {
                        ...postRes,
                        postId: postPayload.id
                    };
                    if (!postRes || !postRes.success) {
                        await updateStep(`❌ Đăng bài X thất bại: ${postRes?.error || "Lỗi không xác định"}`);
                    }
                    break;
                }

                case "SHARE_TO_STORY": {
                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    postId: cmd.postId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}
                    };

                    await updateStep("🔍 Đang kết nối tới Facebook để chia sẻ lên Tin...");
                    const tabs = await chrome.tabs.query({});
                    let targetTab = tabs.find(t => t.active && t.url && t.url.includes("facebook.com")) || tabs.find(t => t.url && t.url.includes("facebook.com"));
                    if (!targetTab) {
                        targetTab = await chrome.tabs.create({ url: "https://www.facebook.com", active: false });
                        await ensureTabLoaded(targetTab.id);
                        await new Promise(r => setTimeout(r, 1000));
                    }

                    await updateStep(`📖 Đang chia sẻ bài viết ${cmd.postId || ''} lên Tin (Story 24h)...`);
                    const shareRes = await _sharePostToStory(targetTab.id, {
                        postUrl: cmd.postUrl || cmd.fbPostUrl,
                        postId: cmd.postId || cmd.fbPostId,
                        numericPostId: cmd.numericPostId,
                        storyId: cmd.storyId,
                        actorId: cmd.actorId
                    });

                    cmdResult = {
                        success: shareRes.success,
                        linkableId: shareRes.linkableId,
                        postId: cmd.postId,
                        error: shareRes.error,
                        progressStep: shareRes.success ? "✅ Đã chia sẻ thành công lên Tin (Story)" : `❌ Lỗi chia sẻ Tin: ${shareRes.error}`
                    };
                    if (!shareRes.success) {
                        await updateStep(`❌ Lỗi chia sẻ Tin: ${shareRes.error || "Thất bại"}`);
                    }
                    break;
                }

                case "SEEDING": {
                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    postId: cmd.postId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}
                    };

                    await updateStep("🔍 1/2: Đang tìm tab Facebook để seeding...");
                    const tabs = await chrome.tabs.query({});
                    let targetTab = tabs.find(t => t.active && t.url && t.url.includes("facebook.com")) || tabs.find(t => t.url && t.url.includes("facebook.com"));
                    if (!targetTab) {
                        targetTab = await chrome.tabs.create({ url: "https://www.facebook.com", active: false });
                        await ensureTabLoaded(targetTab.id);
                        await new Promise(r => setTimeout(r, 1000));
                    }

                    await updateStep(`💬 2/2: Đang gửi bình luận seeding cho bài viết ${cmd.postId || ''}...`);
                    const comments = Array.isArray(cmd.comments) ? cmd.comments : (cmd.comments ? [cmd.comments] : []);
                    const seedRes = await _executeFbSeeding(targetTab.id, cmd.fbPostId || cmd.postId, cmd.fbFeedbackId, comments);
                    
                    if (cmd.autoReactType && cmd.autoReactType !== "NONE") {
                        await _executeFbReaction(targetTab.id, cmd.fbFeedbackId || btoa("feedback:" + (cmd.fbPostId || cmd.postId)), cmd.autoReactType);
                    }

                    cmdResult = {
                        success: seedRes.success,
                        count: seedRes.count,
                        seedingIds: seedRes.seedingIds || [],
                        seedingDetails: seedRes.seedingDetails || [],
                        postId: cmd.postId,
                        error: seedRes.error,
                        progressStep: seedRes.success ? `✅ Đã seeding xong ${seedRes.count || comments.length} bình luận` : `❌ Lỗi seeding: ${seedRes.error}`
                    };
                    if (!seedRes.success) {
                        await updateStep(`❌ Lỗi seeding: ${seedRes.error || "Thất bại"}`);
                    }
                    break;
                }

                case "FLOW_GENERATE_IMAGE": {
                    // ===================================================================
                    // CHIẾN LƯỢC TẠO ẢNH AI CHÍNH XÁC 100%:
                    // - Định vị tab project & kích hoạt tab strip (KHÔNG focus cửa sổ OS)
                    // - Gõ Prompt bằng CDP Input.insertText (Angular nhận native input event)
                    // - Click Generate bằng CDP Input.dispatchMouseEvent (isTrusted: true)
                    // - Nhận kết quả: CHỈ nhận ảnh MỚI thực sự được tạo (interceptor + DOM diff)
                    // - TUYỆT ĐỐI KHÔNG dùng fallback lấy ảnh cũ trên canvas (tránh ảnh tùm lum)
                    // - Chuyển đổi Base64 vĩnh viễn 3 lớp bảo vệ
                    // ===================================================================
                    const prompt = cmd.prompt || "";
                    const model = cmd.model || "HARBOR_SEAL";
                    const imageCount = Math.max(1, Math.min(Number(cmd.imageCount) || 4, 4));
                    const aspectRatio = cmd.aspectRatio || "3:4";
                    const imageRequestId = cmd.imageRequestId || "";
                    const flowProjectId = cmd.flowProjectId || "";
                    let targetTab = null;

                    const showFlowShield = async (tabId, promptText, initialStep) => {
                        if (!tabId) return;
                        try {
                            await chrome.scripting.executeScript({
                                target: { tabId: tabId },
                                world: "MAIN",
                                func: (pText, sText) => {
                                    let shield = document.getElementById("__expro_flow_blocker");
                                    if (!shield) {
                                        shield = document.createElement("div");
                                        shield.id = "__expro_flow_blocker";
                                        shield.setAttribute("style", [
                                            "position: fixed !important",
                                            "top: 0 !important",
                                            "left: 0 !important",
                                            "width: 100vw !important",
                                            "height: 100vh !important",
                                            "z-index: 2147483647 !important",
                                            "background: rgba(10, 15, 29, 0.85) !important",
                                            "backdrop-filter: blur(8px) !important",
                                            "-webkit-backdrop-filter: blur(8px) !important",
                                            "display: flex !important",
                                            "flex-direction: column !important",
                                            "align-items: center !important",
                                            "justify-content: center !important",
                                            "color: #ffffff !important",
                                            "font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif !important",
                                            "user-select: none !important",
                                            "pointer-events: all !important",
                                            "transition: opacity 0.3s ease !important"
                                        ].join(";"));

                                        shield.innerHTML = `
                                            <style>
                                                @keyframes __expro_spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                                                @keyframes __expro_pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
                                            </style>
                                            <div style="
                                                background: linear-gradient(145deg, #131d31, #0c1322);
                                                border: 1px solid #14b8a6;
                                                border-radius: 20px;
                                                padding: 32px 36px;
                                                box-shadow: 0 25px 60px rgba(0, 0, 0, 0.7), 0 0 35px rgba(20, 184, 166, 0.2);
                                                text-align: center;
                                                max-width: 460px;
                                                width: 90%;
                                            ">
                                                <div style="
                                                    width: 52px; height: 52px;
                                                    margin: 0 auto 16px auto;
                                                    border: 4px solid rgba(20, 184, 166, 0.2);
                                                    border-top-color: #2dd4bf;
                                                    border-radius: 50%;
                                                    animation: __expro_spin 1s linear infinite;
                                                "></div>
                                                <h2 style="margin: 0 0 6px 0; font-size: 19px; font-weight: 800; color: #2dd4bf; letter-spacing: 0.5px;">
                                                    ⚡ BAWUI EXTENSION PRO
                                                </h2>
                                                <div style="font-size: 14px; font-weight: 600; color: #f1f5f9; margin-bottom: 14px;">
                                                    🎨 Đang tạo ảnh AI tự động từ Dashboard
                                                </div>
                                                <div id="__expro_flow_step" style="
                                                    font-size: 13px;
                                                    color: #5eead4;
                                                    background: rgba(20, 184, 166, 0.12);
                                                    border: 1px solid rgba(45, 212, 191, 0.3);
                                                    padding: 8px 14px;
                                                    border-radius: 10px;
                                                    margin-bottom: 14px;
                                                    animation: __expro_pulse 2s ease-in-out infinite;
                                                ">${sText || "Đang xử lý..."}</div>
                                                <div style="
                                                    font-size: 12px;
                                                    color: #94a3b8;
                                                    line-height: 1.5;
                                                    margin-bottom: 16px;
                                                    background: rgba(0,0,0,0.3);
                                                    padding: 10px 14px;
                                                    border-radius: 8px;
                                                    font-style: italic;
                                                    max-height: 55px;
                                                    overflow: hidden;
                                                    text-overflow: ellipsis;
                                                ">
                                                    "${pText ? (pText.length > 70 ? pText.substring(0, 70) + '...' : pText) : ''}"
                                                </div>
                                                <div style="
                                                    display: inline-flex;
                                                    align-items: center;
                                                    gap: 6px;
                                                    font-size: 11px;
                                                    font-weight: 700;
                                                    background: rgba(239, 68, 68, 0.15);
                                                    color: #fca5a5;
                                                    border: 1px solid rgba(239, 68, 68, 0.3);
                                                    padding: 6px 14px;
                                                    border-radius: 20px;
                                                ">
                                                    <span>🔒</span>
                                                    <span>ĐÃ KHÓA THAO TÁC — Vui lòng không click hoặc đóng tab này</span>
                                                </div>
                                            </div>
                                        `;

                                        const blockEvent = (e) => { e.stopPropagation(); e.preventDefault(); };
                                        ["click", "mousedown", "mouseup", "pointerdown", "contextmenu", "wheel"].forEach(evt => {
                                            shield.addEventListener(evt, blockEvent, true);
                                        });

                                        if (window.__exproShieldAbort) {
                                            try { window.__exproShieldAbort.abort(); } catch(e) {}
                                        }
                                        window.__exproShieldAbort = new AbortController();
                                        ["keydown", "keypress", "keyup"].forEach(evt => {
                                            window.addEventListener(evt, blockEvent, { capture: true, signal: window.__exproShieldAbort.signal });
                                        });

                                        document.body.appendChild(shield);
                                    } else {
                                        const stepEl = document.getElementById("__expro_flow_step");
                                        if (stepEl && sText) stepEl.textContent = sText;
                                    }
                                },
                                args: [promptText, initialStep]
                            });
                        } catch(e) {}
                    };

                    const hideFlowShield = async (tabId) => {
                        if (!tabId) return;
                        try {
                            await chrome.scripting.executeScript({
                                target: { tabId: tabId },
                                world: "MAIN",
                                func: () => {
                                    if (window.__exproShieldAbort) {
                                        try { window.__exproShieldAbort.abort(); } catch(e) {}
                                        window.__exproShieldAbort = null;
                                    }
                                    const shield = document.getElementById("__expro_flow_blocker");
                                    if (shield) {
                                        shield.style.opacity = "0";
                                        setTimeout(() => { shield.remove(); }, 300);
                                    }
                                }
                            });
                        } catch(e) {}
                    };

                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    imageRequestId: imageRequestId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}

                        // Cập nhật trực tiếp lên Popup Shield trên tab Flow nếu đang hiển thị
                        if (targetTab && targetTab.id) {
                            chrome.scripting.executeScript({
                                target: { tabId: targetTab.id },
                                world: "MAIN",
                                func: (text) => {
                                    const el = document.getElementById("__expro_flow_step");
                                    if (el) el.textContent = text;
                                },
                                args: [stepText]
                            }).catch(() => {});
                        }
                    };

                    try {
                        // ──────────── BƯỚC 1: Tìm tab Flow chính xác ────────────
                        await updateStep("🔍 1/4: Đang tìm tab Google Flow trên trình duyệt...");
                        const tabs = await chrome.tabs.query({});

                        const expectedUrl = flowProjectId 
                            ? `https://flow.google.com/project/${flowProjectId}` 
                            : "https://flow.google.com";

                        if (flowProjectId) {
                            // A. Tìm tab đã mở đúng flowProjectId này
                            targetTab = tabs.find(t => t.url && t.url.includes(flowProjectId));

                            // B. Nếu chưa có tab đúng flowProjectId, kiểm tra xem có tab flow.google.com trang chủ không để tái sử dụng
                            if (!targetTab) {
                                const homeTab = tabs.find(t => t.url && (t.url.replace(/\/$/, '') === "https://flow.google.com"));
                                if (homeTab) {
                                    await updateStep(`🌐 Đang chuyển hướng sang project ${flowProjectId.substring(0, 8)}...`);
                                    await chrome.tabs.update(homeTab.id, { url: expectedUrl });
                                    await ensureTabLoaded(homeTab.id);
                                    await new Promise(r => setTimeout(r, 4500));
                                    targetTab = homeTab;
                                }
                            }

                            // C. Nếu vẫn chưa có tab đúng flowProjectId, mở tab mới ngầm cho project này (không ảnh hưởng tab khác)
                            if (!targetTab) {
                                await updateStep(`🌐 Đang mở tab project Google Flow ngầm...`);
                                targetTab = await chrome.tabs.create({ url: expectedUrl, active: false });
                                await ensureTabLoaded(targetTab.id);
                                await new Promise(r => setTimeout(r, 5000));
                            }
                        } else {
                            // Không chỉ định flowProjectId: ưu tiên tab project bất kỳ, rồi tab flow chung
                            targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com/project/"))
                                     || tabs.find(t => t.url && t.url.includes("flow.google.com"));
                            if (!targetTab) {
                                await updateStep("🌐 Đang mở Google Flow ngầm...");
                                targetTab = await chrome.tabs.create({ url: expectedUrl, active: false });
                                await ensureTabLoaded(targetTab.id);
                                await new Promise(r => setTimeout(r, 5000));
                            }
                        }

                        // KHÔNG chuyển tab: giữ nguyên tab hiện tại người dùng đang xem
                        // Chạy hoàn toàn ngầm trong background
                        console.log("[Flow Bridge] Giữ nguyên tab của người dùng, không chuyển tab ✓");

                        // Chờ tìm ProseMirror editor (tối đa 15s)
                        let editorReady = false;
                        for (let attempt = 0; attempt < 30; attempt++) {
                            const checkRes = await chrome.scripting.executeScript({
                                target: { tabId: targetTab.id },
                                world: "MAIN",
                                func: () => {
                                    const ed = document.querySelector(".ProseMirror");
                                    return !!ed;
                                }
                            });
                            if (checkRes?.[0]?.result) {
                                editorReady = true;
                                break;
                            }
                            await new Promise(r => setTimeout(r, 500));
                        }

                        if (!editorReady) {
                            const err = "Không tìm thấy khung nhập Prompt (.ProseMirror) trên Google Flow. Hãy mở một project trên Flow trước!";
                            await updateStep("❌ Lỗi: " + err);
                            cmdResult = { success: false, error: err, imageRequestId };
                            break;
                        }

                        // ──────────── BƯỚC 2: Snapshot ảnh cũ + Cài interceptor + Chuẩn bị editor ────────────
                        await updateStep("✍️ 2/4: Đang chuẩn bị khung soạn thảo và cài đặt bộ bắt ảnh...");

                        const prepRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: () => {
                                try {
                                    // A. Snapshot TẤT CẢ ảnh hiện có trên trang để DOM diff loại trừ triệt để
                                    window.__existingImages = Array.from(document.querySelectorAll("img")).map(i => i.src);
                                    window.__capturedImages = [];

                                    // B. Cài fetch + XHR interceptor bắt link ảnh mới từ batchexecute
                                    if (!window.__exproInterceptorsInstalled) {
                                        window.__exproInterceptorsInstalled = true;

                                        const extractImgs = (text) => {
                                            if (!text || typeof text !== "string") return;
                                            const unescaped = text.replace(/\\u003d/g, "=").replace(/\\u0026/g, "&");

                                            // 1. Domain flow-content.google
                                            const regex1 = /https:\/\/flow-content\.google\/image\/[a-f0-9-]+\?[^"\\'\s}]*/g;
                                            const m1 = unescaped.match(regex1) || [];
                                            m1.forEach(m => {
                                                const clean = m.replace(/\\"/g, "").replace(/\\n/g, "");
                                                if (clean.includes("KeyName=") && !window.__capturedImages.includes(clean)) {
                                                    window.__capturedImages.push(clean);
                                                }
                                            });

                                            // 2. Domain flow.google.com/asb/
                                            const regex2 = /https:\/\/flow\.google\.com\/asb\/[A-Za-z0-9_-]+[=s0-9rw-]*/g;
                                            const m2 = unescaped.match(regex2) || [];
                                            m2.forEach(m => {
                                                const clean = m.replace(/\\"/g, "").replace(/\\n/g, "");
                                                if (!window.__capturedImages.includes(clean)) {
                                                    window.__capturedImages.push(clean);
                                                }
                                            });
                                        };

                                        const origFetch = window.fetch;
                                        window.fetch = async function(...args) {
                                            const res = await origFetch.apply(this, args);
                                            try {
                                                const u = args[0] ? String(args[0]) : "";
                                                if (u.includes("ogiZ0b") || u.includes("batchexecute")) {
                                                    res.clone().text().then(extractImgs).catch(() => {});
                                                }
                                            } catch(e) {}
                                            return res;
                                        };

                                        const origOpen = XMLHttpRequest.prototype.open;
                                        const origSend = XMLHttpRequest.prototype.send;
                                        XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                                            this.__reqUrl = url ? String(url) : "";
                                            return origOpen.call(this, method, url, ...rest);
                                        };
                                        XMLHttpRequest.prototype.send = function(...args) {
                                            this.addEventListener("load", function() {
                                                if (this.__reqUrl && (this.__reqUrl.includes("ogiZ0b") || this.__reqUrl.includes("batchexecute"))) {
                                                    extractImgs(this.responseText);
                                                }
                                            });
                                            return origSend.apply(this, args);
                                        };
                                    }

                                    const editor = document.querySelector(".ProseMirror");
                                    if (!editor) return { error: "Không tìm thấy khung nhập Prompt (.ProseMirror)" };

                                    // Xóa sạch nội dung cũ trong ProseMirror trước
                                    if (editor.pmViewDesc && editor.pmViewDesc.view) {
                                        const view = editor.pmViewDesc.view;
                                        const tr = view.state.tr;
                                        if (view.state.doc.content.size > 0) {
                                            tr.delete(0, view.state.doc.content.size);
                                            view.dispatch(tr);
                                        }
                                    }

                                    const r = editor.getBoundingClientRect();
                                    return {
                                        success: true,
                                        editorRect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
                                    };
                                } catch(err) {
                                    return { error: err.message || String(err) };
                                }
                            }
                        });

                        const prepData = prepRes?.[0]?.result || {};
                        if (prepData.error) {
                            await updateStep("❌ Lỗi: " + prepData.error);
                            cmdResult = { success: false, error: prepData.error, imageRequestId };
                            break;
                        }

                        // ──────────── BƯỚC 3: Gõ Prompt vào ProseMirror + Click Generate qua CDP ────────────
                        await updateStep(`✍️ 2/4: Đang nhập prompt: "${prompt.substring(0, 35)}..."`);

                        // A. Dọn sạch mọi backdrop/menu overlay đang che khuất màn hình và lấy toạ độ ProseMirror
                        const initEdRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: () => {
                                document.querySelectorAll(".cdk-overlay-backdrop").forEach(b => b.remove());
                                document.querySelectorAll(".cdk-overlay-pane").forEach(p => p.remove());
                                const ed = document.querySelector(".ProseMirror");
                                if (ed) ed.focus();
                                const r = ed ? ed.getBoundingClientRect() : null;
                                return r ? { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) } : null;
                            }
                        });

                        const edRect = initEdRes?.[0]?.result;
                        if (!edRect) {
                            const err = "Không tìm thấy toạ độ khung soạn thảo ProseMirror trên Flow";
                            await updateStep("❌ Lỗi: " + err);
                            cmdResult = { success: false, error: err, imageRequestId };
                            break;
                        }

                        // B. Kết nối CDP Native điều khiển Tab Ngầm (Zero Tab Switching)
                        let dbgAttached = false;
                        if (chrome.debugger && typeof chrome.debugger.attach === "function") {
                            await new Promise(r => {
                                chrome.debugger.attach({ tabId: targetTab.id }, "1.3", () => {
                                    if (!chrome.runtime.lastError) dbgAttached = true;
                                    r();
                                });
                            });
                        }

                        if (!dbgAttached) {
                            const err = "Không thể kết nối Chrome Debugger để điều khiển tab ngầm";
                            await updateStep("❌ Lỗi: " + err);
                            cmdResult = { success: false, error: err, imageRequestId };
                            break;
                        }

                        try {
                            const sendDbg = (method, params) => new Promise(res => {
                                let done = false;
                                const timer = setTimeout(() => { if (!done) { done = true; res(); } }, 1500);
                                try {
                                    chrome.debugger.sendCommand({ tabId: targetTab.id }, method, params, (ret) => {
                                        if (!done) { done = true; clearTimeout(timer); res(ret); }
                                    });
                                } catch(e) {
                                    if (!done) { done = true; clearTimeout(timer); res(); }
                                }
                            });

                            // B1. Click vào ProseMirror để đặt native focus con trỏ
                            const edClickX = edRect.x + Math.min(30, Math.round(edRect.w / 2));
                            const edClickY = edRect.y + Math.round(edRect.h / 2);
                            await sendDbg("Input.dispatchMouseEvent", { type: "mousePressed", x: edClickX, y: edClickY, button: "left", clickCount: 1 });
                            await new Promise(r => setTimeout(r, 40));
                            await sendDbg("Input.dispatchMouseEvent", { type: "mouseReleased", x: edClickX, y: edClickY, button: "left", clickCount: 1 });
                            await new Promise(r => setTimeout(r, 60));

                            // B2. Xóa sạch text cũ trong ProseMirror
                            await chrome.scripting.executeScript({
                                target: { tabId: targetTab.id },
                                world: "MAIN",
                                func: () => {
                                    const ed = document.querySelector(".ProseMirror");
                                    if (ed) {
                                        const sel = window.getSelection();
                                        const range = document.createRange();
                                        range.selectNodeContents(ed);
                                        sel.removeAllRanges();
                                        sel.addRange(range);
                                    }
                                }
                            });
                            await sendDbg("Input.dispatchKeyEvent", {
                                type: "keyDown",
                                key: "Backspace",
                                code: "Backspace",
                                windowsVirtualKeyCode: 8,
                                nativeVirtualKeyCode: 8
                            });
                            await sendDbg("Input.dispatchKeyEvent", {
                                type: "keyUp",
                                key: "Backspace",
                                code: "Backspace"
                            });
                            await new Promise(r => setTimeout(r, 50));

                            // B3. Gõ Prompt vào editor bằng CDP Native Input (hoạt động 100% trên tab ngầm!)
                            await sendDbg("Input.insertText", { text: prompt });
                            await new Promise(r => setTimeout(r, 200));

                            // B4. Kiểm tra nút Bắt đầu tạo và trạng thái kích hoạt của Angular
                            const btnCheckRes = await chrome.scripting.executeScript({
                                target: { tabId: targetTab.id },
                                world: "MAIN",
                                func: () => {
                                    document.querySelectorAll(".cdk-overlay-backdrop").forEach(b => b.remove());
                                    const ed = document.querySelector(".ProseMirror");
                                    const btn = document.querySelector(".generate-icon-button") 
                                             || document.querySelector('button[type="submit"]')
                                             || document.querySelector('button[aria-label="Bắt đầu tạo"]')
                                             || document.querySelector('button[aria-label*="tạo" i]')
                                             || document.querySelector('button[aria-label*="generate" i]');
                                    if (!btn) return { error: "Không tìm thấy nút Bắt đầu tạo" };
                                    const r = btn.getBoundingClientRect();
                                    return {
                                        editorText: ed ? ed.innerText.trim() : "",
                                        btnDisabled: btn.disabled || btn.classList.contains("mat-mdc-button-disabled"),
                                        x: Math.round(r.left),
                                        y: Math.round(r.top),
                                        w: Math.round(r.width),
                                        h: Math.round(r.height)
                                    };
                                }
                            });

                            const btnData = btnCheckRes?.[0]?.result;
                            console.log("[Flow Bridge] Trạng thái editor & nút tạo sau khi nhập CDP:", JSON.stringify(btnData));

                            // Nếu nút disabled vì Angular chưa kích hoạt change, dispatch thêm input event
                            if (btnData && btnData.btnDisabled) {
                                await chrome.scripting.executeScript({
                                    target: { tabId: targetTab.id },
                                    world: "MAIN",
                                    func: () => {
                                        const ed = document.querySelector(".ProseMirror");
                                        if (ed) {
                                            ed.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
                                            ed.dispatchEvent(new Event("change", { bubbles: true }));
                                        }
                                    }
                                });
                                await new Promise(r => setTimeout(r, 100));
                            }

                            // B5. Click nút Bắt đầu tạo 100% ngầm
                            if (btnData && btnData.x !== undefined) {
                                const fx = btnData.x + Math.round(btnData.w / 2);
                                const fy = btnData.y + Math.round(btnData.h / 2);
                                await sendDbg("Input.dispatchMouseEvent", { type: "mouseMoved", x: fx, y: fy });
                                await sendDbg("Input.dispatchMouseEvent", { type: "mousePressed", x: fx, y: fy, button: "left", clickCount: 1 });
                                await new Promise(r => setTimeout(r, 60));
                                await sendDbg("Input.dispatchMouseEvent", { type: "mouseReleased", x: fx, y: fy, button: "left", clickCount: 1 });
                                console.log(`[Flow Bridge] Đã click nút Bắt đầu tạo ngầm tại (${fx}, ${fy})`);
                            }
                        } finally {
                            if (dbgAttached) {
                                try { chrome.debugger.detach({ tabId: targetTab.id }, () => {}); } catch(e) {}
                            }
                        }

                        // Hiển thị ngay popup shield chặn click và hiển thị tiến trình trên tab Flow
                        await showFlowShield(targetTab.id, prompt, "⏳ Đang gửi yêu cầu và chờ Google Flow xử lý (15-40s)...");

                        // ──────────── BƯỚC 4: Chờ kết quả tạo ảnh (CHỈ NHẬN ẢNH MỚI) ────────────
                        await updateStep("⏳ 3/4: Đang chờ Google Flow xử lý và trả về ảnh AI (15-40 giây)...");

                        let capturedImages = [];
                        for (let wait = 0; wait < 120; wait++) {
                            await new Promise(r => setTimeout(r, 500));

                            if (wait > 0 && wait % 10 === 0) {
                                await updateStep(`⏳ 3/4: Đang chờ Google Flow xử lý... (${Math.round(wait * 0.5)}s / 60s)`);
                            }

                            const checkRes = await chrome.scripting.executeScript({
                                target: { tabId: targetTab.id },
                                world: "MAIN",
                                func: () => {
                                    // Kiểm tra xem trên trang có banner thông báo lỗi (snackbar, alert) hay không
                                    const snackbars = document.querySelectorAll("mat-snack-bar-container, [role='alert'], .mat-mdc-snack-bar-container, .error-message, .alert-danger");
                                    for (const sb of snackbars) {
                                        const txt = (sb.innerText || "").trim();
                                        if (txt && (txt.includes("error") || txt.includes("lỗi") || txt.includes("policy") || txt.includes("chính sách") || txt.includes("quota") || txt.includes("giới hạn") || txt.includes("blocked") || txt.includes("chặn") || txt.includes("failed"))) {
                                            return { error: txt };
                                        }
                                    }

                                    // A. Kiểm tra từ interceptor mạng (bắt response batchexecute của lượt này)
                                    if (window.__capturedImages && window.__capturedImages.length > 0) {
                                        return { images: window.__capturedImages, source: "interceptor" };
                                    }

                                    // B. Kiểm tra ảnh MỚI xuất hiện trên canvas DOM (src KHÔNG có trong __existingImages)
                                    const existing = new Set(window.__existingImages || []);
                                    const currentImgs = Array.from(document.querySelectorAll("img")).filter(i => {
                                        const src = i.src || "";
                                        const isFlowImg = src.includes("/asb/") || src.includes("flow-content.google");
                                        const isNew = !existing.has(src);
                                        const w = i.naturalWidth || i.width || 0;
                                        const h = i.naturalHeight || i.height || 0;
                                        return isFlowImg && isNew && (w > 50 || h > 50 || w === 0);
                                    });

                                    if (currentImgs.length > 0) {
                                        return { images: currentImgs.map(i => i.src), source: "dom_diff" };
                                    }

                                    return { images: [] };
                                }
                            });

                            if (checkRes?.[0]?.result?.error) {
                                const onScreenErr = checkRes[0].result.error;
                                console.warn("[Flow Bridge] Phát hiện thông báo lỗi trên màn hình Flow:", onScreenErr);
                                const err = `Google Flow báo lỗi: "${onScreenErr}"`;
                                await updateStep("❌ Lỗi: " + err);
                                cmdResult = { success: false, error: err, imageRequestId };
                                break;
                            }

                            const imgs = checkRes?.[0]?.result?.images || [];
                            if (imgs.length > 0) {
                                capturedImages = imgs;
                                console.log(`[Flow Bridge] Đã bắt được ${imgs.length} ảnh MỚI qua ${checkRes?.[0]?.result?.source} ✓`);
                                break;
                            }
                        }

                        // TUYỆT ĐỐI KHÔNG DÙNG FALLBACK LẤY ẢNH CŨ TRÊN CANVAS!
                        // Báo lỗi rõ ràng nếu không có ảnh MỚI nào được sinh ra cho prompt này
                        if (capturedImages.length === 0) {
                            const err = "Google Flow không tạo ảnh mới cho prompt này sau 60s (có thể prompt bị bộ lọc an toàn của Google chặn hoặc hết quota)";
                            await updateStep("❌ Lỗi: " + err);
                            cmdResult = {
                                success: false,
                                error: err,
                                imageRequestId
                            };
                            break;
                        }

                        // ──────────── BƯỚC 5: Chuyển đổi Base64 vĩnh viễn (3 lớp bảo vệ) ────────────
                        await updateStep(`📥 4/4: Đang tải ${capturedImages.length} ảnh và chuyển đổi Base64 vĩnh viễn...`);

                        const dlRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (imageUrls) => {
                                const results = [];
                                for (const url of imageUrls) {
                                    // Lớp 1: Fetch với cookie phiên
                                    try {
                                        const resp = await fetch(url, { credentials: "include" });
                                        if (resp.ok) {
                                            const blob = await resp.blob();
                                            const b64 = await new Promise((resolve, reject) => {
                                                const reader = new FileReader();
                                                reader.onloadend = () => resolve(reader.result);
                                                reader.onerror = reject;
                                                reader.readAsDataURL(blob);
                                            });
                                            if (b64 && b64.startsWith("data:")) {
                                                results.push({ url: b64, originalUrl: url });
                                                continue;
                                            }
                                        }
                                    } catch(e) {}

                                    // Lớp 2: Vẽ lên Canvas (cùng origin flow.google.com)
                                    try {
                                        const b64 = await new Promise((resolve, reject) => {
                                            const img = new Image();
                                            img.crossOrigin = "anonymous";
                                            img.onload = () => {
                                                try {
                                                    const c = document.createElement("canvas");
                                                    c.width = img.naturalWidth || img.width;
                                                    c.height = img.naturalHeight || img.height;
                                                    const ctx = c.getContext("2d");
                                                    ctx.drawImage(img, 0, 0);
                                                    resolve(c.toDataURL("image/jpeg", 0.92));
                                                } catch(ce) { reject(ce); }
                                            };
                                            img.onerror = () => reject(new Error("Canvas load error"));
                                            img.src = url;
                                        });
                                        if (b64 && b64.startsWith("data:")) {
                                            results.push({ url: b64, originalUrl: url });
                                            continue;
                                        }
                                    } catch(err2) {}

                                    results.push({ url, originalUrl: url });
                                }
                                return results;
                            },
                            args: [capturedImages]
                        });

                        let persistentImages = dlRes?.[0]?.result || [];

                        // Lớp 3: Service Worker download
                        if (persistentImages.length === 0 || persistentImages.every(p => !p.url || !p.url.startsWith("data:"))) {
                            persistentImages = [];
                            for (const imgUrl of capturedImages) {
                                try {
                                    const fetchRes = await fetch(imgUrl);
                                    if (fetchRes.ok) {
                                        const arrayBuffer = await fetchRes.arrayBuffer();
                                        const bytes = new Uint8Array(arrayBuffer);
                                        let binary = "";
                                        const len = bytes.byteLength;
                                        for (let i = 0; i < len; i += 8192) {
                                            binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + 8192, len)));
                                        }
                                        const base64 = btoa(binary);
                                        const mimeType = fetchRes.headers.get("content-type") || "image/jpeg";
                                        persistentImages.push({ url: `data:${mimeType};base64,${base64}`, originalUrl: imgUrl });
                                    } else {
                                        persistentImages.push({ url: imgUrl, originalUrl: imgUrl });
                                    }
                                } catch(e) {
                                    persistentImages.push({ url: imgUrl, originalUrl: imgUrl });
                                }
                            }
                        }

                        const validImages = persistentImages.filter(p => p.url && (p.url.startsWith("data:") || p.url.startsWith("http")));

                        await updateStep(`✅ 4/4: Đã hoàn tất tạo ${validImages.length} ảnh AI Flow thành công!`);

                        cmdResult = {
                            success: true,
                            images: validImages.length > 0 ? validImages : persistentImages,
                            imageRequestId
                        };

                    } catch(flowErr) {
                        console.error("[Flow Bridge] Fatal error:", flowErr);
                        await updateStep("❌ Lỗi: " + flowErr.message);
                        cmdResult = { success: false, error: flowErr.message, imageRequestId };
                    } finally {
                        if (targetTab && targetTab.id) {
                            try {
                                await new Promise(r => setTimeout(r, 600));
                                await hideFlowShield(targetTab.id);
                            } catch(e) {}
                        }
                    }
                    break;
                }

                case "FLOW_SYNC_PROJECT_IMAGES": {
                    // ===================================================================
                    // ĐỒNG BỘ TOÀN BỘ ẢNH TỪ GOOGLE FLOW CANVAS VÀO GALLERY DỰ ÁN
                    // ===================================================================
                    const flowProjectId = cmd.flowProjectId || "";
                    const flowChildId = cmd.flowChildId || "";

                    const updateStep = async (stepText) => {
                        try {
                            await fetch(`${BACKEND_URL}/api/bridge/progress`, {
                                method: "POST",
                                headers: getHeaders(),
                                body: JSON.stringify({
                                    commandId: cmd.id,
                                    targetProjectId: cmd.targetProjectId,
                                    targetSubProjectId: cmd.targetSubProjectId,
                                    step: stepText
                                })
                            }).catch(() => {});
                        } catch(e) {}
                    };

                    try {
                        await updateStep("🔍 Đang tìm tab Flow để quét ảnh canvas...");
                        const tabs = await chrome.tabs.query({});
                        let targetTab = null;

                        if (flowProjectId) {
                            targetTab = tabs.find(t => t.url && t.url.includes(flowProjectId));
                            if (!targetTab) {
                                targetTab = await chrome.tabs.create({
                                    url: `https://flow.google.com/project/${flowProjectId}`,
                                    active: false
                                });
                                await ensureTabLoaded(targetTab.id);
                                await new Promise(r => setTimeout(r, 4500));
                            }
                        } else {
                            targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com/project/"))
                                     || tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        }

                        if (!targetTab) {
                            cmdResult = { success: false, error: "Không tìm thấy tab Google Flow nào để quét ảnh", flowProjectId, flowChildId };
                            break;
                        }

                        await updateStep("🖼️ Đang quét toàn bộ ảnh trên Canvas Google Flow...");

                        const scanRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: () => {
                                const seenUrls = new Set();
                                const items = [];

                                // Tìm tất cả thẻ img trên Flow canvas
                                const allImgs = Array.from(document.querySelectorAll("img"));
                                allImgs.forEach(img => {
                                    const src = img.src || "";
                                    if (!src) return;
                                    const isFlowImg = src.includes("/asb/") || src.includes("flow-content.google");
                                    const isCanvasImg = img.alt && (img.alt.includes("hình ảnh") || img.alt.includes("ảnh"));
                                    const w = img.naturalWidth || img.width || 0;
                                    const h = img.naturalHeight || img.height || 0;

                                    if ((isFlowImg || isCanvasImg) && (w > 80 || h > 80)) {
                                        const cleanUrl = src.split("&Token=")[0];
                                        if (seenUrls.has(src) || seenUrls.has(cleanUrl)) return;
                                        seenUrls.add(src);
                                        seenUrls.add(cleanUrl);

                                        // Tìm kiếm text prompt ở container cha gần nhất
                                        let promptText = "";
                                        let parent = img.parentElement;
                                        for (let depth = 0; depth < 8 && parent; depth++) {
                                            const texts = Array.from(parent.querySelectorAll("p, span, div, textarea, [class*='text'], [class*='prompt']"))
                                                .map(el => el.innerText ? el.innerText.trim() : "")
                                                .filter(t => t.length > 5 && !t.includes("home") && !t.includes("search") && !t.includes("more_vert") && !t.includes("add"));
                                            if (texts.length > 0) {
                                                promptText = texts[0];
                                                break;
                                            }
                                            parent = parent.parentElement;
                                        }

                                        items.push({
                                            url: src,
                                            prompt: promptText || img.alt || "Ảnh trên Google Flow Canvas",
                                            width: w,
                                            height: h
                                        });
                                    }
                                });

                                return items;
                            }
                        });

                        const scannedImages = scanRes?.[0]?.result || [];
                        console.log(`[Flow Sync] Tìm thấy ${scannedImages.length} ảnh trên canvas tab ${targetTab.id}`);

                        if (scannedImages.length === 0) {
                            cmdResult = { success: true, count: 0, images: [], flowProjectId, flowChildId };
                            break;
                        }

                        await updateStep(`📥 Đang nạp và lưu vĩnh viễn ${scannedImages.length} ảnh từ Canvas...`);

                        // Chuyển đổi Base64 trong MAIN world để lưu vĩnh viễn
                        const b64Res = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (imgItems) => {
                                const results = [];
                                for (const item of imgItems) {
                                    let b64 = null;
                                    try {
                                        const resp = await fetch(item.url, { credentials: "include" });
                                        if (resp.ok) {
                                            const blob = await resp.blob();
                                            b64 = await new Promise((res, rej) => {
                                                const r = new FileReader();
                                                r.onloadend = () => res(r.result);
                                                r.onerror = rej;
                                                r.readAsDataURL(blob);
                                            });
                                        }
                                    } catch(e) {}

                                    results.push({
                                        url: (b64 && b64.startsWith("data:")) ? b64 : item.url,
                                        originalUrl: item.url,
                                        prompt: item.prompt,
                                        width: item.width,
                                        height: item.height
                                    });
                                }
                                return results;
                            },
                            args: [scannedImages]
                        });

                        const finalImages = b64Res?.[0]?.result || scannedImages;
                        await updateStep(`✅ Đã đồng bộ xong ${finalImages.length} ảnh từ Canvas Google Flow!`);

                        cmdResult = {
                            success: true,
                            count: finalImages.length,
                            images: finalImages,
                            flowProjectId,
                            flowChildId
                        };

                    } catch(syncErr) {
                        console.error("[Flow Sync] Error:", syncErr);
                        cmdResult = { success: false, error: syncErr.message, flowProjectId, flowChildId };
                    }
                    break;
                }

                // ===================================================================
                // 14. FLOW_LIST_PROJECTS — Lấy danh sách tất cả Project từ Google Flow qua RPC UpteDb
                // ===================================================================
                case "FLOW_LIST_PROJECTS": {
                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        if (!targetTab) {
                            targetTab = await chrome.tabs.create({ url: "https://flow.google.com", active: false });
                            await ensureTabLoaded(targetTab.id);
                            await new Promise(r => setTimeout(r, 4000));
                        }

                        const listRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async () => {
                                try {
                                    const wiz = window.WIZ_global_data || {};
                                    const at = wiz.SNlM0e || "";
                                    const fsid = wiz.FdrFJe || "";
                                    const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                    const params = new URLSearchParams({
                                        rpcids: "UpteDb",
                                        "source-path": "/",
                                        bl: bl,
                                        "f.sid": fsid,
                                        hl: "vi",
                                        _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                        rt: "c"
                                    });

                                    const freq = JSON.stringify([[["UpteDb", JSON.stringify(["projects/*", 100, null, null, null, null, [1]]), null, "generic"]]]);
                                    const body = new URLSearchParams();
                                    body.append("f.req", freq);
                                    if (at) body.append("at", at);

                                    const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "X-Same-Domain": "1"
                                        },
                                        body: body.toString(),
                                        credentials: "include"
                                    });

                                    const text = await resp.text();
                                    const lines = text.split("\n");
                                    const projects = [];
                                    for (const line of lines) {
                                        if (line.startsWith("[[") && line.includes("wrb.fr") && line.includes("UpteDb")) {
                                            const parsed = JSON.parse(line);
                                            for (const item of parsed) {
                                                if (item[0] === "wrb.fr" && item[1] === "UpteDb") {
                                                    const data = JSON.parse(item[2]);
                                                    if (data && data[0]) {
                                                        for (const p of data[0]) {
                                                            projects.push({
                                                                id: p[0],
                                                                name: (p[1] && p[1][0]) ? p[1][0] : "Dự án Flow",
                                                                thumb: (p[1] && p[1][3]) ? p[1][3] : "",
                                                                createdAt: (p[1] && p[1][2] && p[1][2][0]) ? p[1][2][0] : null
                                                            });
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    return { success: true, count: projects.length, projects };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            }
                        });

                        const resData = listRes?.[0]?.result || { success: false, error: "Không nhận được phản hồi" };
                        cmdResult = resData;
                    } catch(err) {
                        cmdResult = { success: false, error: err.message };
                    }
                    break;
                }

                // ===================================================================
                // 15. FLOW_DELETE_IMAGE — Xóa ảnh trên Google Flow Canvas (Chuyển vào thùng rác)
                // ===================================================================
                case "FLOW_DELETE_IMAGE": {
                    const flowProjectId = cmd.flowProjectId || "";
                    const imageUrl = cmd.imageUrl || "";
                    const originalUrl = cmd.originalUrl || imageUrl;
                    const imageId = cmd.imageId || "";

                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = null;
                        if (flowProjectId) {
                            targetTab = tabs.find(t => t.url && t.url.includes(flowProjectId));
                            if (!targetTab) {
                                targetTab = await chrome.tabs.create({
                                    url: `https://flow.google.com/project/${flowProjectId}`,
                                    active: false
                                });
                                await ensureTabLoaded(targetTab.id);
                                await new Promise(r => setTimeout(r, 4500));
                            }
                        } else {
                            targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com/project/"))
                                     || tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        }

                        if (!targetTab) {
                            cmdResult = { success: false, error: "Không tìm thấy tab Google Flow của dự án để xóa ảnh" };
                            break;
                        }

                        const delRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (targetUrl, origUrl, flowPid) => {
                                try {
                                    // Trích xuất UUID định danh ảnh (flow-content.google/image/<UUID>)
                                    let imgUuid = "";
                                    const m = (origUrl || targetUrl || "").match(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/i);
                                    if (m) imgUuid = m[0];

                                    // 1. Ưu tiên thực thi RPC pGCYOe (metadata.archived) trực tiếp từ Flow Cloud
                                    if (imgUuid && flowPid) {
                                        try {
                                            const wiz = window.WIZ_global_data || {};
                                            const at = wiz.SNlM0e || "";
                                            const fsid = wiz.FdrFJe || "";
                                            const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                            const params = new URLSearchParams({
                                                rpcids: "pGCYOe",
                                                "source-path": `/project/${flowPid}`,
                                                bl: bl,
                                                "f.sid": fsid,
                                                hl: "vi",
                                                _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                                rt: "c"
                                            });

                                            const freq = JSON.stringify([[["pGCYOe", JSON.stringify([[[imgUuid, null, null, [null, null, 1], flowPid]], [["metadata.archived"]]]), null, "generic"]]]);
                                            const body = new URLSearchParams();
                                            body.append("f.req", freq);
                                            if (at) body.append("at", at);

                                            const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                                method: "POST",
                                                headers: {
                                                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                                    "X-Same-Domain": "1"
                                                },
                                                body: body.toString(),
                                                credentials: "include"
                                            });

                                            const text = await resp.text();
                                            if (text.includes("pGCYOe") && !text.includes("error")) {
                                                return { success: true, deleted: true, imgUuid, method: "rpc_pGCYOe" };
                                            }
                                        } catch(rpcErr) {
                                            console.warn("[Flow Bridge] RPC pGCYOe delete warning, falling back to UI:", rpcErr);
                                        }
                                    }

                                    // 2. Fallback tìm ảnh trên canvas và click Tuỳ chọn khác -> Chuyển vào thùng rác
                                    const cleanTarget = (targetUrl || "").split("&Token=")[0].split("?Expires=")[0];
                                    const cleanOrig = (origUrl || "").split("&Token=")[0].split("?Expires=")[0];

                                    // Tìm ảnh trên canvas
                                    const allImgs = Array.from(document.querySelectorAll("img"));
                                    let matchedImg = null;

                                    for (const img of allImgs) {
                                        const src = img.src || "";
                                        if (!src) continue;
                                        const cleanSrc = src.split("&Token=")[0].split("?Expires=")[0];

                                        if ((cleanTarget && cleanSrc === cleanTarget) ||
                                            (cleanOrig && cleanSrc === cleanOrig) ||
                                            (imgUuid && cleanSrc.includes(imgUuid)) ||
                                            (cleanTarget && cleanTarget.length > 30 && cleanSrc.includes(cleanTarget.substring(0, 50)))) {
                                            matchedImg = img;
                                            break;
                                        }
                                    }

                                    if (!matchedImg) {
                                        // Nếu có imgUuid và đã cố RPC thì coi như hoàn tất
                                        if (imgUuid) return { success: true, deleted: true, imgUuid, note: "cloud_archived" };
                                        return { success: false, error: "Không tìm thấy thẻ ảnh tương ứng trên Flow canvas" };
                                    }

                                    // Tìm nút Tuỳ chọn khác trong container của ảnh
                                    let cur = matchedImg.parentElement;
                                    let tileMoreBtn = null;
                                    for (let d = 0; d < 6 && cur && !tileMoreBtn; d++) {
                                        tileMoreBtn = cur.querySelector('button[aria-label="Tuỳ chọn khác"], button[aria-label*="khác" i], button[aria-label*="options" i]');
                                        cur = cur.parentElement;
                                    }

                                    if (!tileMoreBtn) {
                                        return { success: false, error: "Không tìm thấy nút 'Tuỳ chọn khác' của ô ảnh trên Flow" };
                                    }

                                    // Click mở menu của tile
                                    tileMoreBtn.click();
                                    await new Promise(r => setTimeout(r, 450));

                                    // Tìm menu item: Chuyển vào thùng rác / Xóa
                                    const menuItems = Array.from(document.querySelectorAll(".mat-mdc-menu-item, [role='menuitem']"));
                                    const trashItem = menuItems.find(m => {
                                        const txt = (m.innerText || "").toLowerCase();
                                        return txt.includes("thùng rác") || txt.includes("trash") || txt.includes("xoá") || txt.includes("delete");
                                    });

                                    if (!trashItem) {
                                        document.body.click(); // đóng menu
                                        return { success: false, error: "Không tìm thấy mục 'Chuyển vào thùng rác' trong menu ảnh" };
                                    }

                                    trashItem.click();
                                    await new Promise(r => setTimeout(r, 450));

                                    // Nếu có popup xác nhận xóa (mat-dialog-container), bấm xác nhận
                                    const dialog = document.querySelector("mat-dialog-container, [role='dialog']");
                                    if (dialog) {
                                        const confirmBtn = Array.from(dialog.querySelectorAll("button")).find(b => {
                                            const txt = (b.innerText || "").toLowerCase();
                                            return txt.includes("xoá") || txt.includes("chuyển") || txt.includes("delete") || txt.includes("xác nhận") || b.getAttribute("color") === "warn";
                                        });
                                        if (confirmBtn) {
                                            confirmBtn.click();
                                            await new Promise(r => setTimeout(r, 300));
                                        }
                                    }

                                    return { success: true, deleted: true, imgUuid, method: "ui_trash" };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            },
                            args: [imageUrl, originalUrl, flowProjectId]
                        });

                        const resData = delRes?.[0]?.result || { success: false, error: "Không nhận được phản hồi từ tab" };
                        cmdResult = { ...resData, imageId, flowProjectId };
                    } catch(err) {
                        cmdResult = { success: false, error: err.message, imageId, flowProjectId };
                    }
                    break;
                }

                // ===================================================================
                // 16. FLOW_DELETE_PROJECT — Xóa vĩnh viễn Project trên Google Flow (RPC QI2zvc + UI fallback)
                // ===================================================================
                case "FLOW_DELETE_PROJECT": {
                    const flowProjectId = cmd.flowProjectId || "";
                    if (!flowProjectId) {
                        cmdResult = { success: false, error: "Thiếu flowProjectId" };
                        break;
                    }

                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = tabs.find(t => t.url && t.url.includes(flowProjectId))
                                     || tabs.find(t => t.url && t.url.includes("flow.google.com"));

                        if (!targetTab) {
                            targetTab = await chrome.tabs.create({ url: "https://flow.google.com", active: false });
                            await ensureTabLoaded(targetTab.id);
                            await new Promise(r => setTimeout(r, 3500));
                        }

                        // Thực thi RPC QI2zvc trực tiếp từ session Google Flow (nhanh và chuẩn 100%)
                        const rpcRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (projId) => {
                                try {
                                    const wiz = window.WIZ_global_data || {};
                                    const at = wiz.SNlM0e || "";
                                    const fsid = wiz.FdrFJe || "";
                                    const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                    const params = new URLSearchParams({
                                        rpcids: "QI2zvc",
                                        "source-path": `/project/${projId}`,
                                        bl: bl,
                                        "f.sid": fsid,
                                        hl: "vi",
                                        _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                        rt: "c"
                                    });

                                    const freq = JSON.stringify([[["QI2zvc", JSON.stringify([`projects/${projId}`]), null, "generic"]]]);
                                    const body = new URLSearchParams();
                                    body.append("f.req", freq);
                                    if (at) body.append("at", at);

                                    const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "X-Same-Domain": "1"
                                        },
                                        body: body.toString(),
                                        credentials: "include"
                                    });

                                    const text = await resp.text();
                                    const isSuccess = text.includes("QI2zvc") && !text.includes("error");
                                    return { success: isSuccess || resp.ok, text: text.substring(0, 200) };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            },
                            args: [flowProjectId]
                        });

                        // Đóng tất cả tab chứa flowProjectId đã bị xóa
                        const tabsToClose = tabs.filter(t => t.url && t.url.includes(flowProjectId));
                        for (const tab of tabsToClose) {
                            try {
                                await chrome.tabs.remove(tab.id);
                            } catch(e) {}
                        }

                        cmdResult = {
                            success: true,
                            deletedProjectId: flowProjectId,
                            rpcResult: rpcRes?.[0]?.result
                        };
                    } catch(err) {
                        cmdResult = { success: false, error: err.message, flowProjectId };
                    }
                    break;
                }

                // ===================================================================
                // 17. FLOW_CREATE_PROJECT — Tạo Project mới trên Google Flow qua RPC jHPbke
                // ===================================================================
                case "FLOW_CREATE_PROJECT": {
                    const projectName = cmd.projectName || "Dự án mới";
                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        if (!targetTab) {
                            targetTab = await chrome.tabs.create({ url: "https://flow.google.com", active: false });
                            await ensureTabLoaded(targetTab.id);
                            await new Promise(r => setTimeout(r, 4000));
                        }

                        const createRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (name) => {
                                try {
                                    const wiz = window.WIZ_global_data || {};
                                    const at = wiz.SNlM0e || "";
                                    const fsid = wiz.FdrFJe || "";
                                    const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                    const params = new URLSearchParams({
                                        rpcids: "jHPbke",
                                        "source-path": "/",
                                        bl: bl,
                                        "f.sid": fsid,
                                        hl: "vi",
                                        _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                        rt: "c"
                                    });

                                    const freq = JSON.stringify([[["jHPbke", JSON.stringify(["projects/*", [null, [name]], [null, 22]]), null, "generic"]]]);
                                    const body = new URLSearchParams();
                                    body.append("f.req", freq);
                                    if (at) body.append("at", at);

                                    const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "X-Same-Domain": "1"
                                        },
                                        body: body.toString(),
                                        credentials: "include"
                                    });

                                    const text = await resp.text();
                                    let createdId = null;
                                    const lines = text.split("\n");
                                    for (const line of lines) {
                                        if (line.startsWith("[[") && line.includes("wrb.fr") && line.includes("jHPbke")) {
                                            const parsed = JSON.parse(line);
                                            for (const item of parsed) {
                                                if (item[0] === "wrb.fr" && item[1] === "jHPbke") {
                                                    const data = JSON.parse(item[2]);
                                                    if (data && data[0]) createdId = data[0];
                                                }
                                            }
                                        }
                                    }

                                    return { success: !!createdId, flowProjectId: createdId, name, text: text.substring(0, 200) };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            },
                            args: [projectName]
                        });

                        const resData = createRes?.[0]?.result || { success: false, error: "Không nhận được phản hồi" };
                        cmdResult = resData;

                        // Chạy hoàn toàn ngầm trong background, không bao giờ tự động chuyển tab
                        if (resData.success && resData.flowProjectId && cmd.openTab === true) {
                            try {
                                const newTab = await chrome.tabs.create({
                                    url: `https://flow.google.com/project/${resData.flowProjectId}`,
                                    active: false // Luôn mở ngầm, không cướp tiêu điểm của App!
                                });
                                cmdResult.openedTabId = newTab.id;
                            } catch(e) {}
                        }
                    } catch(err) {
                        cmdResult = { success: false, error: err.message };
                    }
                    break;
                }

                // ===================================================================
                // 18. FLOW_CHECK_PROJECTS_HEALTH — Kiểm tra danh sách project còn sống hay đã bị xóa trên Flow
                // ===================================================================
                case "FLOW_CHECK_PROJECTS_HEALTH": {
                    const projectIdsToCheck = cmd.projectIds || [];
                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        if (!targetTab) {
                            targetTab = await chrome.tabs.create({ url: "https://flow.google.com", active: false });
                            await ensureTabLoaded(targetTab.id);
                            await new Promise(r => setTimeout(r, 4000));
                        }

                        // Lấy toàn bộ danh sách projects sống trên Flow qua UpteDb
                        const listRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async () => {
                                try {
                                    const wiz = window.WIZ_global_data || {};
                                    const at = wiz.SNlM0e || "";
                                    const fsid = wiz.FdrFJe || "";
                                    const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                    const params = new URLSearchParams({
                                        rpcids: "UpteDb",
                                        "source-path": "/",
                                        bl: bl,
                                        "f.sid": fsid,
                                        hl: "vi",
                                        _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                        rt: "c"
                                    });

                                    const freq = JSON.stringify([[["UpteDb", JSON.stringify(["projects/*", 100, null, null, null, null, [1]]), null, "generic"]]]);
                                    const body = new URLSearchParams();
                                    body.append("f.req", freq);
                                    if (at) body.append("at", at);

                                    const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "X-Same-Domain": "1"
                                        },
                                        body: body.toString(),
                                        credentials: "include"
                                    });

                                    const text = await resp.text();
                                    const lines = text.split("\n");
                                    const liveIds = new Set();
                                    for (const line of lines) {
                                        if (line.startsWith("[[") && line.includes("wrb.fr") && line.includes("UpteDb")) {
                                            const parsed = JSON.parse(line);
                                            for (const item of parsed) {
                                                if (item[0] === "wrb.fr" && item[1] === "UpteDb") {
                                                    const data = JSON.parse(item[2]);
                                                    if (data && data[0]) {
                                                        for (const p of data[0]) {
                                                            if (p[0]) liveIds.add(p[0]);
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    return { success: true, liveIds: Array.from(liveIds) };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            }
                        });

                        const resObj = listRes?.[0]?.result || {};
                        if (!resObj.success) {
                            cmdResult = { success: false, error: resObj.error || "Không thể lấy danh sách project từ Flow" };
                            break;
                        }

                        const liveSet = new Set(resObj.liveIds || []);
                        const aliveProjectIds = [];
                        const deadProjectIds = [];

                        for (const pid of projectIdsToCheck) {
                            if (liveSet.has(pid)) {
                                aliveProjectIds.push(pid);
                            } else {
                                deadProjectIds.push(pid);
                            }
                        }

                        cmdResult = {
                            success: true,
                            totalChecked: projectIdsToCheck.length,
                            aliveProjectIds,
                            deadProjectIds,
                            flowLiveCount: liveSet.size
                        };

                    } catch(err) {
                        cmdResult = { success: false, error: err.message };
                    }
                    break;
                }

                // ===================================================================
                // 19. FLOW_RENAME_PROJECT — Đổi tên Project trên Google Flow qua RPC o8DA4
                // ===================================================================
                case "FLOW_RENAME_PROJECT": {
                    const flowProjectId = cmd.flowProjectId;
                    const newName = cmd.newName || cmd.name;
                    if (!flowProjectId || !newName) {
                        cmdResult = { success: false, error: "Thiếu flowProjectId hoặc newName" };
                        break;
                    }
                    try {
                        const tabs = await chrome.tabs.query({});
                        let targetTab = tabs.find(t => t.url && t.url.includes("flow.google.com"));
                        if (!targetTab) {
                            targetTab = await chrome.tabs.create({ url: `https://flow.google.com/project/${flowProjectId}`, active: false });
                            await ensureTabLoaded(targetTab.id);
                            await new Promise(r => setTimeout(r, 4000));
                        }

                        const renameRes = await chrome.scripting.executeScript({
                            target: { tabId: targetTab.id },
                            world: "MAIN",
                            func: async (pid, title) => {
                                try {
                                    const wiz = window.WIZ_global_data || {};
                                    const at = wiz.SNlM0e || "";
                                    const fsid = wiz.FdrFJe || "";
                                    const bl = wiz.cfb2h || "boq_labs-ai-sandbox-frontend_20260923.06_p0";

                                    const params = new URLSearchParams({
                                        rpcids: "o8DA4",
                                        "source-path": `/project/${pid}`,
                                        bl: bl,
                                        "f.sid": fsid,
                                        hl: "vi",
                                        _reqid: String(Math.floor(Math.random() * 900000) + 100000),
                                        rt: "c"
                                    });

                                    const freq = JSON.stringify([[["o8DA4", JSON.stringify([`projects/${pid}`, [title], [["project_title"]], [null, 22]]), null, "generic"]]]);
                                    const body = new URLSearchParams();
                                    body.append("f.req", freq);
                                    if (at) body.append("at", at);

                                    const resp = await fetch(`https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?${params.toString()}`, {
                                        method: "POST",
                                        headers: {
                                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                            "X-Same-Domain": "1"
                                        },
                                        body: body.toString(),
                                        credentials: "include"
                                    });

                                    const text = await resp.text();
                                    const isSuccess = text.includes("o8DA4") && !text.includes("error");
                                    return { success: isSuccess || resp.ok, flowProjectId: pid, newName: title, text: text.substring(0, 200) };
                                } catch(e) {
                                    return { success: false, error: e.message };
                                }
                            },
                            args: [flowProjectId, newName]
                        });

                        const rData = renameRes?.[0]?.result || { success: false, error: "Không nhận được phản hồi đổi tên" };
                        cmdResult = {
                            success: rData.success,
                            flowProjectId,
                            newName,
                            error: rData.error
                        };

                        // Cập nhật title của tab nếu tab đó đang mở trong Chrome
                        const projTab = tabs.find(t => t.url && t.url.includes(flowProjectId));
                        if (projTab) {
                            try {
                                await chrome.scripting.executeScript({
                                    target: { tabId: projTab.id },
                                    func: (t) => { document.title = t + " — Google Flow"; },
                                    args: [newName]
                                });
                            } catch(e) {}
                        }
                    } catch(err) {
                        cmdResult = { success: false, error: err.message };
                    }
                    break;
                }

                // ===================================================================
                // 20. FLOW_FOCUS_PROJECT — Kích hoạt tab nếu được yêu cầu rõ ràng
                // ===================================================================
                case "FLOW_FOCUS_PROJECT": {
                    const flowProjectId = cmd.flowProjectId;
                    if (!flowProjectId) {
                        cmdResult = { success: false, error: "Thiếu flowProjectId" };
                        break;
                    }
                    try {
                        const tabs = await chrome.tabs.query({});
                        const existingTab = tabs.find(t => t.url && t.url.includes(flowProjectId));
                        if (existingTab) {
                            if (cmd.forceFocus) {
                                await chrome.tabs.update(existingTab.id, { active: true });
                                if (existingTab.windowId) {
                                    await chrome.windows.update(existingTab.windowId, { focused: true });
                                }
                            }
                            cmdResult = { success: true, tabId: existingTab.id, focusMode: "existing" };
                        } else {
                            const newTab = await chrome.tabs.create({
                                url: `https://flow.google.com/project/${flowProjectId}`,
                                active: false // Luôn mở ngầm, không nhảy tab!
                            });
                            cmdResult = { success: true, tabId: newTab.id, focusMode: "opened_bg" };
                        }
                    } catch(err) {
                        cmdResult = { success: false, error: err.message };
                    }
                    break;
                }

                default:
                    cmdResult = { success: false, error: `Action '${cmd.action}' không tồn tại` };
            }
        } catch (execErr) {
            cmdResult = { success: false, error: execErr.message };
        } finally {
            if (subId) activeSubProjectIds.delete(subId);
            if (isFlowAction) activeFlowCount = Math.max(0, activeFlowCount - 1);
            if (isFbAction) activeFbCount = Math.max(0, activeFbCount - 1);
        }

        // 4. Trả kết quả lệnh về Backend VPS (kèm cơ chế thử lại nếu mạng chập chờn)
        for (let retry = 0; retry < 3; retry++) {
            try {
                const res = await fetch(`${BACKEND_URL}/api/bridge/result`, {
                    method: "POST",
                    headers: getHeaders(),
                    body: JSON.stringify({
                        nodeId: NODE_ID,
                        commandId: cmd.id,
                        action: cmd.action,
                        targetProjectId: cmd.targetProjectId,
                        targetSubProjectId: cmd.targetSubProjectId,
                        ...cmdResult,
                        timestamp: Date.now()
                    })
                });
                if (res.ok) break;
            } catch(e) {
                console.warn(`[Bridge] Lỗi gửi kết quả lần ${retry + 1}/3:`, e);
            }
            await new Promise(r => setTimeout(r, 600 * (retry + 1)));
        }

        // Kích hoạt ngay nhịp heartbeat và polling tiếp theo để kéo lệnh kế tiếp của project con này hoặc các project khác
        scheduleNextHeartbeat(300);
        setTimeout(pollAndExecuteCommand, 100);
}

// =========================================================================
// 5. CHU KỲ HOẠT ĐỘNG THÍCH ỨNG & KEEPALIVE SERVICE WORKER (MV3)
// =========================================================================
let _heartbeatTimer = null;
let _currentHeartbeatInterval = 3500; // Mặc định chế độ nghỉ: 3.5s

function scheduleNextHeartbeat(delayMs) {
    if (_heartbeatTimer) clearTimeout(_heartbeatTimer);
    const ms = typeof delayMs === "number" ? delayMs : _currentHeartbeatInterval;
    _heartbeatTimer = setTimeout(async () => {
        try {
            await sendHeartbeat();
        } catch(e) {}
        scheduleNextHeartbeat();
    }, ms);
}

// Watchdog Alarm: Chrome MV3 quy định periodInMinutes >= 1 trong chế độ bình thường.
// Alarm này đảm bảo nếu Service Worker bị Chrome đưa vào chế độ ngủ (idle),
// thì cứ mỗi 1 phút sẽ tự động được đánh thức dậy và khôi phục nhịp polling ngay.
chrome.alarms.get("bridgeWatchdogAlarm", (alarm) => {
    if (!alarm) {
        chrome.alarms.create("bridgeWatchdogAlarm", { periodInMinutes: 1.0 });
    }
});

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "bridgeWatchdogAlarm") {
        sendHeartbeat();
        scheduleNextHeartbeat(3000);
    }
});

// Lắng nghe sự kiện trình duyệt khởi động hoặc extension nạp lại
chrome.runtime.onStartup?.addListener(() => {
    sendHeartbeat();
    scheduleNextHeartbeat(2000);
});

chrome.runtime.onInstalled?.addListener(() => {
    sendHeartbeat();
    scheduleNextHeartbeat(2000);
});

// Tự động kích hoạt Heartbeat ngay khi người dùng thao tác trên Chrome (đổi tab, mở tab, chuyển cửa sổ)
chrome.tabs?.onActivated?.addListener(() => {
    sendHeartbeat();
    scheduleNextHeartbeat(2500);
});

chrome.tabs?.onCreated?.addListener(() => {
    sendHeartbeat();
    scheduleNextHeartbeat(2500);
});

chrome.windows?.onFocusChanged?.addListener((winId) => {
    if (winId !== (chrome.windows.WINDOW_ID_NONE || -1)) {
        sendHeartbeat();
        scheduleNextHeartbeat(2500);
    }
});

// Khởi chạy vòng lặp ban đầu
scheduleNextHeartbeat(1000);

// 6. Giao tiếp với Popup & Options UI
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "GET_STATUS") {
        sendResponse({
            connected: isConnected,
            nodeId: NODE_ID,
            nodeName: NODE_NAME,
            projectName: PROJECT_NAME,
            backendUrl: BACKEND_URL,
            authToken: AUTH_TOKEN,
            latencyMs: lastLatencyMs
        });
        return true;
    }

    if (msg.type === "SET_CONFIG") {
        const newUrl = (msg.backendUrl || BACKEND_URL).trim().replace(/\/+$/, "");
        const newToken = (msg.authToken || "").trim();
        const newName = (msg.nodeName || NODE_NAME).trim();

        BACKEND_URL = newUrl;
        AUTH_TOKEN = newToken;
        NODE_NAME = newName;

        chrome.storage.local.set({
            backendUrl: BACKEND_URL,
            authToken: AUTH_TOKEN,
            nodeName: NODE_NAME
        }, () => {
            sendHeartbeat().then(() => {
                sendResponse({
                    success: true,
                    connected: isConnected,
                    latencyMs: lastLatencyMs
                });
            });
        });
        return true;
    }

    // Ping Test tới một URL chỉ định (dùng trong Options test trước khi lưu)
    if (msg.type === "TEST_CONNECTION") {
        const testUrl = (msg.url || BACKEND_URL).trim().replace(/\/+$/, "");
        const testToken = (msg.token || "").trim();
        const startTime = performance.now();

        const headers = { "Content-Type": "application/json" };
        if (testToken) {
            headers["Authorization"] = `Bearer ${testToken}`;
            headers["X-Sync-Token"] = testToken;
        }

        fetch(`${testUrl}/api/bridge/manifest`, {
            method: "GET",
            headers: headers,
            signal: AbortSignal.timeout(6000)
        })
        .then(async (res) => {
            const latency = Math.round(performance.now() - startTime);
            if (res.ok) {
                const info = await res.json();
                sendResponse({ success: true, latencyMs: latency, info });
            } else {
                sendResponse({ success: false, status: res.status, error: `HTTP ${res.status} ${res.statusText}` });
            }
        })
        .catch((err) => {
            sendResponse({ success: false, error: err.message || "Không thể kết nối" });
        });

        return true; // asynchronous response
    }
});
