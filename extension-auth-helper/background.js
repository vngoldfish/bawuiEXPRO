/**
 * BROWSER BRIDGE — BACKGROUND SERVICE WORKER
 * Cầu nối trung chuyển lệnh giữa Backend Server (VPS / Local) và Trình duyệt Chrome
 */

let BACKEND_URL = "http://127.0.0.1:9999";
let AUTH_TOKEN = "";
let NODE_NAME = "My Chrome Node";
let PROJECT_NAME = "";
let NODE_ID = "bridge_" + Math.random().toString(36).slice(2, 10);
let isConnected = false;
let isPolling = false;
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

        if (data.authToken) AUTH_TOKEN = data.authToken.trim();
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

        const payload = {
            nodeId: NODE_ID,
            nodeName: NODE_NAME,
            backendUrl: BACKEND_URL,
            status: "online",
            tabCount: tabs.length,
            activeTab: activeTab ? { id: activeTab.id, url: activeTab.url, title: activeTab.title } : null,
            browserFbUid: browserFbUid,
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
                pollAndExecuteCommand();
            }
        } else {
            isConnected = false;
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
            return { success: false, error: "Không thể mở hoặc kết nối tới tab Facebook" };
        }

        await ensureTabLoaded(targetTab.id);
        await new Promise(r => setTimeout(r, 400));

        // Fetch media from URL if base64 data not provided
        if (!payload.mediaData && payload.mediaUrl) {
            try {
                await updateStep(`📥 Đang nạp media từ link: ${payload.mediaUrl.slice(0, 45)}...`);
                const res = await fetch(payload.mediaUrl);
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
            return { success: false, error: gqlRes?.error || "Không thể tạo bài viết trên Facebook" };
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
        return { success: false, error: err.message };
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

// 3. Kéo lệnh từ Backend và thực thi trên Trình duyệt
async function pollAndExecuteCommand() {
    if (isPolling) return;
    isPolling = true;

    try {
        const res = await fetch(`${BACKEND_URL}/api/bridge/poll`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({ nodeId: NODE_ID }),
            signal: AbortSignal.timeout(5000)
        });

        if (!res.ok) return;
        const data = await res.json();
        const cmd = data.command;
        if (!cmd) return;

        console.log(`[Bridge] Nhận lệnh từ VPS: ${cmd.action} (ID: ${cmd.id})`);
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
                                return { success: true, evalResult: eval(codeStr) };
                            } catch (e) {
                                return { success: false, error: e.message };
                            }
                        },
                        args: [scriptCode]
                    });

                    const resObj = execResults?.[0]?.result || { success: false, error: "Không nhận được phản hồi từ tab" };
                    cmdResult = { success: resObj.success, data: resObj.evalResult, error: resObj.error, tabId: targetTabId };
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
                    break;
                }

                case "FLOW_GENERATE_IMAGE": {
                    const prompt = cmd.prompt || "";
                    const model = cmd.model || "HARBOR_SEAL";
                    const imageCount = cmd.imageCount || 4;
                    const aspectRatio = cmd.aspectRatio || "3:4";
                    const imageRequestId = cmd.imageRequestId || "";

                    const FLOW_API_BASE = "https://aisandbox-pa.googleapis.com/v1";
                    const FLOW_API_KEY = "AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY";
                    const FLOW_LABS_BASE = "https://labs.google/fx/api";

                    const IMAGE_ASPECTS = {
                        "1:1": "IMAGE_ASPECT_RATIO_SQUARE",
                        "3:4": "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
                        "4:3": "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE",
                        "9:16": "IMAGE_ASPECT_RATIO_PORTRAIT",
                        "16:9": "IMAGE_ASPECT_RATIO_LANDSCAPE"
                    };

                    try {
                        // Bước 1: Lấy session_token từ cookie labs.google
                        const labsCookies = await chrome.cookies.getAll({ domain: "labs.google" });
                        const sessionCookie = labsCookies.find(c => c.name === "__Secure-next-auth.session-token");
                        if (!sessionCookie) {
                            cmdResult = { success: false, error: "Chưa đăng nhập labs.google — Hãy mở https://labs.google/fx/tools/flow trên Chrome và đăng nhập Google", imageRequestId };
                            break;
                        }
                        const sessionToken = sessionCookie.value;

                        // Bước 2: Đổi session_token → access_token qua /auth/session
                        const sessionRes = await fetch(`${FLOW_LABS_BASE}/auth/session`, {
                            headers: {
                                "Cookie": `__Secure-next-auth.session-token=${sessionToken}`,
                                "Accept": "application/json"
                            }
                        });
                        if (!sessionRes.ok) {
                            cmdResult = { success: false, error: `Session hết hạn (HTTP ${sessionRes.status}) — mở lại labs.google/fx/tools/flow và đăng nhập lại`, imageRequestId };
                            break;
                        }
                        const sessionData = await sessionRes.json();
                        const accessToken = sessionData.access_token;
                        if (!accessToken) {
                            cmdResult = { success: false, error: "Không lấy được access_token — session_token có thể hết hạn", imageRequestId };
                            break;
                        }

                        // Bước 3: Tạo project (hoặc dùng project có sẵn)
                        let projectId = "";
                        try {
                            const createRes = await fetch(`${FLOW_LABS_BASE}/trpc/project.createProject`, {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                    "Cookie": `__Secure-next-auth.session-token=${sessionToken}`
                                },
                                body: JSON.stringify({ json: { projectTitle: "EXPRO Auto", toolName: "PINHOLE" } })
                            });
                            const createData = await createRes.json();
                            projectId = createData?.result?.data?.json?.result?.projectId || "";
                        } catch(e) {}

                        if (!projectId) {
                            projectId = crypto.randomUUID();
                        }

                        // Bước 4: Gọi API tạo ảnh (REST API chuẩn)
                        const resolvedAspect = IMAGE_ASPECTS[aspectRatio] || null;
                        const requests = [];
                        for (let i = 0; i < imageCount; i++) {
                            const reqItem = {
                                clientContext: {
                                    projectId: projectId,
                                    tool: "PINHOLE",
                                    userPaygateTier: "PAYGATE_TIER_TWO",
                                    sessionId: `;${Date.now()}`,
                                    recaptchaContext: {
                                        applicationType: "RECAPTCHA_APPLICATION_TYPE_WEB",
                                        token: "bypass"
                                    }
                                },
                                seed: Math.floor(Math.random() * 999999),
                                imageModelName: model,
                                structuredPrompt: { parts: [{ text: prompt }] },
                                imageInputs: []
                            };
                            if (resolvedAspect) {
                                reqItem.imageAspectRatio = resolvedAspect;
                            }
                            requests.push(reqItem);
                        }

                        const payload = {
                            clientContext: requests[0].clientContext,
                            mediaGenerationContext: { batchId: crypto.randomUUID() },
                            useNewMedia: true,
                            requests: requests
                        };

                        const genUrl = `${FLOW_API_BASE}/projects/${projectId}/flowMedia:batchGenerateImages?key=${FLOW_API_KEY}`;
                        const genRes = await fetch(genUrl, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": `Bearer ${accessToken}`,
                                "Origin": "https://labs.google",
                                "Referer": `https://labs.google/fx/tools/flow/project/${projectId}`
                            },
                            body: JSON.stringify(payload)
                        });

                        const genText = await genRes.text();
                        let genData = {};
                        try { genData = JSON.parse(genText); } catch(e) {}

                        if (!genRes.ok) {
                            const errMsg = genData?.error?.message || genData?.message || genText.substring(0, 300);
                            cmdResult = { success: false, error: `Flow API lỗi (${genRes.status}): ${errMsg}`, imageRequestId };
                            break;
                        }

                        // Bước 5: Parse response - trích xuất ảnh base64 hoặc URL
                        const images = [];
                        const mediaResults = genData?.generatedMediaResults || genData?.results || [];

                        // Duyệt response tìm base64 encoded images
                        const findImages = (obj) => {
                            if (!obj || typeof obj !== 'object') return;
                            if (obj.encodedImage) {
                                images.push({ base64: obj.encodedImage, mediaId: obj.mediaId || "" });
                                return;
                            }
                            if (obj.imageUrl || obj.url) {
                                images.push({ url: obj.imageUrl || obj.url });
                                return;
                            }
                            if (Array.isArray(obj)) {
                                obj.forEach(item => findImages(item));
                            } else {
                                Object.values(obj).forEach(val => findImages(val));
                            }
                        };
                        findImages(genData);

                        if (images.length > 0) {
                            cmdResult = { success: true, images, imageRequestId };
                        } else {
                            cmdResult = { success: false, error: "API trả về nhưng không có ảnh (có thể prompt bị chặn)", imageRequestId, raw: genText.substring(0, 500) };
                        }

                    } catch(flowErr) {
                        cmdResult = { success: false, error: flowErr.message, imageRequestId };
                    }
                    break;
                }

                default:
                    cmdResult = { success: false, error: `Action '${cmd.action}' không tồn tại` };
            }
        } catch (execErr) {
            cmdResult = { success: false, error: execErr.message };
        }

        // 4. Trả kết quả lệnh về Backend VPS
        await fetch(`${BACKEND_URL}/api/bridge/result`, {
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
        }).catch(() => {});

    } catch (e) {
        console.warn("[Bridge] Lỗi polling:", e.message);
    } finally {
        isPolling = false;
    }
}

// 5. Chu kỳ hoạt động định kỳ (Heartbeat 4s / lần)
chrome.alarms.create("bridgeHeartbeatAlarm", { periodInMinutes: 0.1 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "bridgeHeartbeatAlarm") {
        sendHeartbeat();
    }
});

setInterval(() => {
    sendHeartbeat();
}, 4000);

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
