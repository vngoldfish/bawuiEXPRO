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

// Tab Switching (BAWUI vs vidIQ Vision)
const tabBtnBawui = document.getElementById("tabBtnBawui");
const tabBtnVidiq = document.getElementById("tabBtnVidiq");
const paneBawui = document.getElementById("paneBawui");
const paneVidiq = document.getElementById("paneVidiq");

function switchTab(target) {
    if (target === "vidiq") {
        if (tabBtnVidiq) tabBtnVidiq.classList.add("active");
        if (tabBtnBawui) tabBtnBawui.classList.remove("active");
        if (paneVidiq) paneVidiq.classList.add("active");
        if (paneBawui) paneBawui.classList.remove("active");
        document.body.classList.add("vidiq-active");
        try { localStorage.setItem("active_popup_tab", "vidiq"); } catch(e) {}
    } else {
        if (tabBtnBawui) tabBtnBawui.classList.add("active");
        if (tabBtnVidiq) tabBtnVidiq.classList.remove("active");
        if (paneBawui) paneBawui.classList.add("active");
        if (paneVidiq) paneVidiq.classList.remove("active");
        document.body.classList.remove("vidiq-active");
        try { localStorage.setItem("active_popup_tab", "bawui"); } catch(e) {}
    }
}

if (tabBtnBawui && tabBtnVidiq) {
    tabBtnBawui.addEventListener("click", () => switchTab("bawui"));
    tabBtnVidiq.addEventListener("click", () => switchTab("vidiq"));

    try {
        const savedTab = localStorage.getItem("active_popup_tab");
        if (savedTab === "vidiq") {
            switchTab("vidiq");
        }
    } catch(e) {}
}

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
