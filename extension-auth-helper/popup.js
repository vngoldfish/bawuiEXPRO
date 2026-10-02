/**
 * BROWSER BRIDGE — POPUP CONTROLLER
 */

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const pingBadge = document.getElementById("pingBadge");
const nodeIdEl = document.getElementById("nodeId");
const backendUrlInput = document.getElementById("backendUrl");
const btnSaveUrl = document.getElementById("btnSaveUrl");
const btnOpenDashboard = document.getElementById("btnOpenDashboard");
const btnOpenOptions = document.getElementById("btnOpenOptions");
const btnPing = document.getElementById("btnPing");
const appTitle = document.getElementById("appTitle");
const appDesc = document.getElementById("appDesc");
const saveResult = document.getElementById("saveResult");
const projectBadge = document.getElementById("projectBadge");

async function syncManifestInfo(backendUrl) {
    try {
        const res = await fetch(`${backendUrl}/api/bridge/manifest`);
        if (res.ok) {
            const data = await res.json();
            if (data.name && appTitle) appTitle.textContent = `⚡ ${data.name}`;
            if (data.description && appDesc) appDesc.textContent = data.description;
        }
    } catch(e) {}
}

function updateUI() {
    chrome.runtime.sendMessage({ type: "GET_STATUS" }, (res) => {
        if (chrome.runtime.lastError || !res) {
            statusDot.className = "dot";
            statusText.textContent = "Offline";
            pingBadge.textContent = "";
            return;
        }

        if (res.connected) {
            statusDot.className = "dot online";
            statusText.textContent = "Online";
            pingBadge.textContent = `${res.latencyMs || 0}ms`;
        } else {
            statusDot.className = "dot";
            statusText.textContent = "Offline";
            pingBadge.textContent = "";
        }

        const displayName = res.nodeName ? `${res.nodeName} (${res.nodeId})` : res.nodeId;
        if (res.nodeId) nodeIdEl.textContent = displayName;
        if (projectBadge) {
            projectBadge.textContent = res.projectName ? `📁 Dự án: ${res.projectName}` : '📁 Dự án: Đang đồng bộ...';
        }
        if (res.backendUrl && document.activeElement !== backendUrlInput) {
            backendUrlInput.value = res.backendUrl;
        }

        if (res.connected && res.backendUrl) {
            syncManifestInfo(res.backendUrl);
        }
    });
}

btnSaveUrl.addEventListener("click", () => {
    const newUrl = backendUrlInput.value.trim().replace(/\/+$/, "");
    if (!newUrl) return;

    btnSaveUrl.disabled = true;
    btnSaveUrl.textContent = "...";

    chrome.runtime.sendMessage({ type: "SET_CONFIG", backendUrl: newUrl }, (res) => {
        btnSaveUrl.disabled = false;
        btnSaveUrl.textContent = "Lưu";

        if (saveResult) {
            saveResult.style.display = "block";
            if (res && res.success) {
                saveResult.textContent = res.connected ? "✅ Đã lưu & kết nối VPS thành công!" : "⚠️ Đã lưu! Đang chờ VPS phản hồi...";
                saveResult.style.color = res.connected ? "#4ade80" : "#facc15";
            } else {
                saveResult.textContent = "❌ Lỗi lưu URL!";
                saveResult.style.color = "#f87171";
            }
            setTimeout(() => { saveResult.style.display = "none"; }, 3500);
        }

        updateUI();
    });
});

btnOpenDashboard.addEventListener("click", () => {
    const url = backendUrlInput.value.trim() || "http://127.0.0.1:9999";
    chrome.tabs.create({ url });
});

btnOpenOptions.addEventListener("click", () => {
    chrome.tabs.create({ url: chrome.runtime.getURL("options.html#bawui") });
});

// Tab Switching (BAWUI vs vidIQ Vision vs AI Analysis)
const tabBtnBawui = document.getElementById("tabBtnBawui");
const tabBtnVidiq = document.getElementById("tabBtnVidiq");
const tabBtnAi = document.getElementById("tabBtnAi");
const paneBawui = document.getElementById("paneBawui");
const paneVidiq = document.getElementById("paneVidiq");
const paneAi = document.getElementById("paneAi");

function switchTab(target) {
    // Deactivate all
    [tabBtnBawui, tabBtnVidiq, tabBtnAi].forEach(b => { if (b) b.classList.remove("active"); });
    [paneBawui, paneVidiq, paneAi].forEach(p => { if (p) p.classList.remove("active"); });
    document.body.classList.remove("vidiq-active");

    if (target === "vidiq") {
        if (tabBtnVidiq) tabBtnVidiq.classList.add("active");
        if (paneVidiq) paneVidiq.classList.add("active");
        document.body.classList.add("vidiq-active");
    } else if (target === "ai") {
        if (tabBtnAi) tabBtnAi.classList.add("active");
        if (paneAi) paneAi.classList.add("active");
        loadAiConfig();
    } else {
        if (tabBtnBawui) tabBtnBawui.classList.add("active");
        if (paneBawui) paneBawui.classList.add("active");
    }

    try { localStorage.setItem("active_popup_tab", target); } catch(e) {}
}

if (tabBtnBawui) tabBtnBawui.addEventListener("click", () => switchTab("bawui"));
if (tabBtnVidiq) tabBtnVidiq.addEventListener("click", () => switchTab("vidiq"));
if (tabBtnAi) tabBtnAi.addEventListener("click", () => switchTab("ai"));

try {
    const savedTab = localStorage.getItem("active_popup_tab");
    if (savedTab === "vidiq" || savedTab === "ai") {
        switchTab(savedTab);
    }
} catch(e) {}

btnPing.addEventListener("click", () => {
    updateUI();
    if (saveResult) {
        saveResult.style.display = "block";
        saveResult.textContent = "🔄 Đang ping máy chủ...";
        saveResult.style.color = "#38bdf8";
        setTimeout(() => { saveResult.style.display = "none"; }, 2000);
    }
});

document.addEventListener("DOMContentLoaded", () => {
    updateUI();
    setInterval(updateUI, 2500);
});

// ============================================================
// AI ANALYSIS — Config & Handlers
// ============================================================

const aiApiUrl = document.getElementById("aiApiUrl");
const aiApiKey = document.getElementById("aiApiKey");
const aiModel = document.getElementById("aiModel");
const aiLanguage = document.getElementById("aiLanguage");
const btnSaveAiConfig = document.getElementById("btnSaveAiConfig");
const btnTestAi = document.getElementById("btnTestAi");
const aiTestResult = document.getElementById("aiTestResult");
const aiPopupResult = document.getElementById("aiPopupResult");
const aiPopupResultContent = document.getElementById("aiPopupResultContent");

function loadAiConfig() {
    chrome.runtime.sendMessage({ type: "BAWUI_AI", action: "getConfig" }, (res) => {
        if (chrome.runtime.lastError || !res || !res.success) return;
        const cfg = res.data;
        if (aiApiUrl) aiApiUrl.value = cfg.url || "";
        if (aiModel) aiModel.value = cfg.model || "default";
        if (aiLanguage) aiLanguage.value = cfg.language || "vi";
        // Don't overwrite key field (password) — just show placeholder if set
        if (aiApiKey && cfg.hasKey) aiApiKey.placeholder = "••••••• (đã lưu)";
    });
}

if (btnSaveAiConfig) {
    btnSaveAiConfig.addEventListener("click", () => {
        const config = {
            url: (aiApiUrl?.value || "").trim(),
            key: (aiApiKey?.value || "").trim(),
            model: (aiModel?.value || "default").trim(),
            language: aiLanguage?.value || "vi"
        };
        btnSaveAiConfig.disabled = true;
        btnSaveAiConfig.textContent = "⏳ Đang lưu...";
        chrome.runtime.sendMessage({ type: "BAWUI_AI", action: "saveConfig", config }, (res) => {
            btnSaveAiConfig.disabled = false;
            btnSaveAiConfig.textContent = "💾 Lưu";
            if (res?.success) {
                const keyMsg = res.data?.keyUpdated ? " (API key đã cập nhật)" : (config.key ? "" : " (giữ API key cũ)");
                showAiTestResult("✅ Đã lưu cấu hình AI!" + keyMsg, "#4ade80");
                // Reset key field after successful save
                if (aiApiKey && res.data?.keyUpdated) {
                    aiApiKey.value = "";
                    aiApiKey.placeholder = "••••••• (đã lưu)";
                }
            } else {
                showAiTestResult("❌ Lỗi lưu: " + (res?.error || "Unknown"), "#f87171");
            }
        });
    });
}

if (btnTestAi) {
    btnTestAi.addEventListener("click", () => {
        btnTestAi.disabled = true;
        btnTestAi.textContent = "⏳ Testing...";
        showAiTestResult("🔄 Đang kết nối AI...", "#38bdf8");
        chrome.runtime.sendMessage({ type: "BAWUI_AI", action: "testConnection" }, (res) => {
            btnTestAi.disabled = false;
            btnTestAi.textContent = "🔗 Test kết nối";
            if (res?.success) {
                showAiTestResult("✅ AI phản hồi: " + (res.data || "OK"), "#4ade80");
            } else {
                showAiTestResult("❌ " + (res?.error || "Không thể kết nối"), "#f87171");
            }
        });
    });
}

function showAiTestResult(text, color) {
    if (!aiTestResult) return;
    aiTestResult.textContent = text;
    aiTestResult.style.color = color;
    setTimeout(() => { if (aiTestResult.textContent === text) aiTestResult.textContent = ""; }, 5000);
}

// Quick Analysis from popup — extracts data from current YouTube tab
function popupAnalyze(action) {
    if (aiPopupResult) aiPopupResult.style.display = "block";
    if (aiPopupResultContent) aiPopupResultContent.innerHTML = '<div style="text-align:center;color:#94a3b8;">⏳ Đang thu thập dữ liệu từ YouTube...</div>';

    // First get the current tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs?.[0];
        if (!tab || !tab.url || !tab.url.includes("youtube.com/watch")) {
            if (aiPopupResultContent) aiPopupResultContent.innerHTML = '<div style="color:#f87171;">❌ Vui lòng mở một video YouTube trước</div>';
            return;
        }

        // Execute script on the page to get video data
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            world: "MAIN",
            func: () => {
                const vd = window.ytInitialPlayerResponse?.videoDetails || {};
                const mf = window.ytInitialPlayerResponse?.microformat?.playerMicroformatRenderer || {};
                return {
                    title: vd.title || document.title,
                    description: vd.shortDescription || "",
                    keywords: vd.keywords || [],
                    viewCount: vd.viewCount || "0",
                    author: vd.author || "",
                    channelId: vd.channelId || "",
                    lengthSeconds: vd.lengthSeconds || "0",
                    category: mf.category || "",
                    publishDate: mf.publishDate || "",
                    thumbnail: vd.thumbnail?.thumbnails?.[0]?.url || "",
                    url: window.location.href
                };
            }
        }, (results) => {
            if (chrome.runtime.lastError || !results?.[0]?.result) {
                if (aiPopupResultContent) aiPopupResultContent.innerHTML = '<div style="color:#f87171;">❌ Không thể đọc dữ liệu video. Hãy reload trang YouTube.</div>';
                return;
            }

            const videoData = results[0].result;
            if (aiPopupResultContent) aiPopupResultContent.innerHTML = '<div style="text-align:center;color:#2dd4bf;">🤖 Đang phân tích bằng AI... Vui lòng chờ</div>';

            const msg = { type: "BAWUI_AI", action };
            if (action === "analyzeVideo" || action === "suggestContent") {
                msg.videoData = videoData;
            } else if (action === "analyzeChannel") {
                msg.channelData = videoData;
            }

            chrome.runtime.sendMessage(msg, (res) => {
                if (res?.success) {
                    if (aiPopupResultContent) aiPopupResultContent.innerHTML = formatAiResult(res.data);
                } else {
                    if (aiPopupResultContent) aiPopupResultContent.innerHTML = `<div style="color:#f87171;">❌ ${res?.error || "Lỗi phân tích"}</div>`;
                }
            });
        });
    });
}

function formatAiResult(text) {
    if (!text) return "<em>Không có kết quả</em>";
    // Simple markdown → HTML
    return text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(/^### (.+)$/gm, '<h4 style="color:#2dd4bf;margin:8px 0 4px;">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 style="color:#38bdf8;margin:10px 0 4px;">$1</h3>')
        .replace(/^# (.+)$/gm, '<h2 style="color:#f1f5f9;margin:12px 0 6px;">$1</h2>')
        .replace(/^- (.+)$/gm, '• $1')
        .replace(/^\d+\. (.+)$/gm, '<span style="color:#94a3b8;">$&</span>')
        .replace(/\n/g, "<br>");
}

// Bind analysis buttons
const btnPopupAnalyzeVideo = document.getElementById("btnPopupAnalyzeVideo");
const btnPopupAnalyzeChannel = document.getElementById("btnPopupAnalyzeChannel");
const btnPopupSuggestContent = document.getElementById("btnPopupSuggestContent");

if (btnPopupAnalyzeVideo) btnPopupAnalyzeVideo.addEventListener("click", () => popupAnalyze("analyzeVideo"));
if (btnPopupAnalyzeChannel) btnPopupAnalyzeChannel.addEventListener("click", () => popupAnalyze("analyzeChannel"));
if (btnPopupSuggestContent) btnPopupSuggestContent.addEventListener("click", () => popupAnalyze("suggestContent"));
