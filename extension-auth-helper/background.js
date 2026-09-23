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

        const payload = {
            nodeId: NODE_ID,
            nodeName: NODE_NAME,
            backendUrl: BACKEND_URL,
            status: "online",
            tabCount: tabs.length,
            activeTab: activeTab ? { id: activeTab.id, url: activeTab.url, title: activeTab.title } : null,
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

function ensureTabLoaded(tabId, timeoutMs = 15000) {
    return new Promise((resolve) => {
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
                    const byteNumbers = new Array(byteChars.length);
                    for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
                    const byteArray = new Uint8Array(byteNumbers);
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
                    formData.append(isVideo ? "video" : "photo", blob, fName);
                    formData.append("source", "8");
                    formData.append("profile_id", userId);
                    formData.append("waterfallxapp", "comet");
                    formData.append("upload_speed", "0");
                    formData.append("fb_dtsg", fb_dtsg);

                    const endpointPath = isVideo ? "/ajax/react_composer/attachments/video/upload?" : "/ajax/react_composer/attachments/photo/upload?";
                    const uploadUrl = "https://upload.facebook.com" + endpointPath + urlParams.toString();

                    const resp = await fetch(uploadUrl, {
                        method: "POST",
                        body: formData,
                        credentials: "include"
                    });

                    const text = await resp.text();
                    const cleanUpload = text.replace(/^for\s*\(;+\)\s*;?\s*/, "");
                    const idPatterns = [
                        /"video_id"\s*:\s*"?(\d+)"?/,
                        /"videoId"\s*:\s*"?(\d+)"?/,
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
                        const mid = parsed?.payload?.photoID || parsed?.payload?.fbid || parsed?.payload?.media_id || parsed?.payload?.video_id || parsed?.payload?.id;
                        if (mid) return { success: true, mediaId: String(mid) };
                    } catch(e) {}
                    return { success: false, error: "Không tìm thấy media ID trong phản hồi Facebook" };
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
                    const arrayBuffer = await blob.arrayBuffer();
                    const bytes = new Uint8Array(arrayBuffer);
                    const chunks = [];
                    for (let i = 0; i < bytes.byteLength; i += 8192) {
                        chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + 8192, bytes.byteLength))));
                    }
                    const binary = chunks.join('');
                    payload.mediaData = {
                        base64: btoa(binary),
                        fileName: "media_downloaded",
                        mimeType: blob.type || (payload.mediaUrl.match(/\.(mp4|mov|avi)/i) ? "video/mp4" : "image/jpeg")
                    };
                }
            } catch(e) {
                console.warn("[Bridge] Fetch mediaUrl error:", e);
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

        const graphqlResults = await chrome.scripting.executeScript({
            target: { tabId: targetTab.id },
            func: async (postContent, postType, mediaId, isVideo, fallbackActorId, targetType, targetId) => {
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

                    let surface = "newsfeed";
                    let feedLoc = "NEWSFEED";
                    let renderLoc = "homepage_stream";

                    if (targetType === "group" && targetId) {
                        surface = "group"; feedLoc = "GROUP"; renderLoc = "group";
                    } else if (targetType === "page") {
                        surface = "page_timeline"; feedLoc = "TIMELINE"; renderLoc = "page_timeline";
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

                    const defaultFallbackDocIds = ["28329575890036120", "27508435028820023", "27248647231502311", "6362241860538186", "6815340158580277", "6143924765664426"];
                    const fallbackDocIds = [...liveDocIds];
                    for (const id of defaultFallbackDocIds) {
                        if (!fallbackDocIds.includes(id)) fallbackDocIds.push(id);
                    }
                    const composerSessionId = actorId + "_" + Date.now();
                    const variables = {
                        input: {
                            composer_entry_point: "inline_composer",
                            composer_source_surface: surface,
                            composer_type: targetType === "group" ? "group" : "feed",
                            idempotence_token: composerSessionId + "_FEED",
                            source: "WWW",
                            ai_generated_self_disclosure_metadata: { was_self_disclosed_as_ai_generated: false },
                            ...(targetType === "profile" ? {
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
                            navigation_data: { attribution_id_v2: "CometHomeRoot.react,comet.home,via_cold_start," + Date.now() + ",166542,4748854339,," },
                            tracking: [null],
                            event_share_metadata: { surface: surface },
                            ...(mediaId ? {
                                attachments: [
                                    isVideo ? { video: { id: String(mediaId) } } : { photo: { id: String(mediaId) } }
                                ]
                            } : {}),
                            actor_id: actorId,
                            client_mutation_id: String(Math.floor(Math.random() * 10) + 1)
                        },
                        feedLocation: feedLoc,
                        feedbackSource: 1,
                        focusCommentID: null,
                        gridMediaWidth: null,
                        groupID: targetType === "group" ? String(targetId) : null,
                        scale: 1,
                        privacySelectorRenderLocation: "COMET_STREAM",
                        checkPhotosToReelsUpsellEligibility: true,
                        referringStoryRenderLocation: null,
                        renderLocation: renderLoc,
                        useDefaultActor: false,
                        inviteShortLinkKey: null,
                        isFeed: true,
                        isGroup: targetType === "group",
                        isTimeline: targetType === "profile",
                        isPageNewsFeed: targetType === "page"
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
                                return {
                                    success: true,
                                    fbPostId: effectiveId ? String(effectiveId) : (pid || storyId || null),
                                    fbPostUrl: purl || `https://www.facebook.com/posts/${effectiveId || pid || ''}`,
                                    fbFeedbackId: extractedFeedbackId
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
            args: [payload.content, postType, effectiveMediaId, isVideo, fallbackActorId, payload.targetType || "profile", payload.targetId || ""]
        });

        const gqlRes = graphqlResults?.[0]?.result;
        if (!gqlRes || !gqlRes.success) {
            return { success: false, error: gqlRes?.error || "Không thể tạo bài viết trên Facebook" };
        }

        const fbPostId = gqlRes.fbPostId || uploadedMediaId;
        const fbPostUrl = gqlRes.fbPostUrl || (fbPostId ? `https://www.facebook.com/posts/${fbPostId}` : "");
        const fbFeedbackId = gqlRes.fbFeedbackId || (fbPostId ? btoa("feedback:" + fbPostId) : null);

        // Seeding Comments
        if (payload.seedingComments && Array.isArray(payload.seedingComments) && payload.seedingComments.length > 0) {
            await updateStep(`💬 4/4: Đang gửi ${payload.seedingComments.length} bình luận seeding tự động (giãn cách chống spam)...`);
            const seedRes = await _executeFbSeeding(targetTab.id, fbPostId, fbFeedbackId, payload.seedingComments, fallbackActorId);
            if (seedRes && seedRes.count !== undefined) {
                await updateStep(`💬 Đã gửi thành công ${seedRes.count}/${payload.seedingComments.length} bình luận seeding!`);
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

                const finalHtml = document.documentElement.innerHTML || "";
                const feedbackCandidates = [];
                if (knownFeedbackId) {
                    if (knownFeedbackId.startsWith("ZmVl")) {
                        feedbackCandidates.push(knownFeedbackId);
                    } else {
                        feedbackCandidates.push(btoa("feedback:" + knownFeedbackId));
                    }
                }
                if (postId) {
                    feedbackCandidates.push(btoa("feedback:" + postId));
                }
                const numMatches = finalHtml.matchAll(/"(?:legacy_story_id|story_fbid|post_id|story_id|subscription_target_id|feedback_target_id)"\s*:\s*"(\d+)"/g);
                for (const m of numMatches) {
                    if (m[1] && m[1].length >= 8) {
                        const b = btoa("feedback:" + m[1]);
                        if (!feedbackCandidates.includes(b)) feedbackCandidates.push(b);
                    }
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

                for (let i = 0; i < comments.length; i++) {
                    const commentText = comments[i];
                    if (!commentText || !commentText.trim()) continue;
                    let commentSuccess = false;
                    const randomSuffix = Math.random().toString(36).substring(2, 8);
                    const clientMutationId = Date.now() + "_" + randomSuffix;
                    const idempotenceToken = "client:" + Date.now() + "_" + randomSuffix;

                    for (const fbIdCandidate of feedbackCandidates) {
                        if (commentSuccess) break;
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
                                        feedback_id: fbIdCandidate,
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
                                        feedback_id: fbIdCandidate,
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

                                const text = await resp.text();
                                let json = null;
                                try { json = JSON.parse(text.replace(/^for\s*\(;+\)\s*;?\s*/, "")); } catch(e) {}

                                const hasCommentData = json && json.data && (
                                    json.data.comment_create || 
                                    json.data.useCometUFICreateCommentMutation || 
                                    json.data.comment || 
                                    json.data.feedback || 
                                    json.data.id ||
                                    text.includes('"comment"') ||
                                    text.includes('"feedback"')
                                );

                                if (resp.ok && (hasCommentData || (json && json.data && !json.errors))) {
                                    commentSuccess = true;
                                    break;
                                }
                            } catch(e) {}
                        }
                    }

                    // DOM Fallback if GraphQL didn't succeed
                    if (!commentSuccess) {
                        try {
                            const commentBox = document.querySelector(
                                'div[role="textbox"][aria-label*="bình luận"], ' +
                                'div[role="textbox"][aria-label*="Comment"], ' +
                                'div[role="textbox"][aria-label*="Viết"], ' +
                                'div[role="textbox"][contenteditable="true"], ' +
                                'form div[role="textbox"]'
                            );
                            if (commentBox) {
                                commentBox.focus();
                                document.execCommand("insertText", false, commentText.trim());
                                commentBox.dispatchEvent(new Event("input", { bubbles: true }));
                                await new Promise(r => setTimeout(r, 400));
                                const enterEvt = new KeyboardEvent("keydown", {
                                    key: "Enter", code: "Enter", keyCode: 13, which: 13,
                                    bubbles: true, cancelable: true
                                });
                                commentBox.dispatchEvent(enterEvt);
                                commentSuccess = true;
                            }
                        } catch(domErr) {}
                    }

                    if (commentSuccess) successCount++;

                    // Anti-spam interval: 2600ms between comments to prevent Facebook rate limiting
                    if (i < comments.length - 1) {
                        await new Promise(r => setTimeout(r, 2600));
                    }
                }

                return { success: successCount > 0, count: successCount, total: comments.length };
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
                        postId: cmd.postId,
                        error: seedRes.error,
                        progressStep: seedRes.success ? `✅ Đã seeding xong ${seedRes.count || comments.length} bình luận` : `❌ Lỗi seeding: ${seedRes.error}`
                    };
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
