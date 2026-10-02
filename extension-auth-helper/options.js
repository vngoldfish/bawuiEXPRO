/**
 * BROWSER BRIDGE — OPTIONS CONTROLLER
 */

const inputUrl = document.getElementById("inputUrl");
const inputToken = document.getElementById("inputToken");
const inputName = document.getElementById("inputName");
const liveDot = document.getElementById("liveDot");
const liveStatusText = document.getElementById("liveStatusText");
const latencyBadge = document.getElementById("latencyBadge");
const testResultText = document.getElementById("testResultText");
const btnTestPing = document.getElementById("btnTestPing");
const btnSaveConfig = document.getElementById("btnSaveConfig");
const btnOpenWeb = document.getElementById("btnOpenWeb");

function setUrl(url) {
    inputUrl.value = url;
}

if (window.location.search.includes("reload=1")) {
    console.log("[Options] Triggering chrome.runtime.reload()...");
    chrome.runtime.reload();
}

function updateStatus() {
    chrome.runtime.sendMessage({ type: "GET_STATUS" }, (res) => {
        if (chrome.runtime.lastError || !res) {
            liveDot.className = "dot";
            liveStatusText.textContent = "Không thể kết nối Service Worker";
            return;
        }

        if (document.activeElement !== inputUrl) {
            inputUrl.value = res.backendUrl || "http://127.0.0.1:9999";
        }
        if (document.activeElement !== inputToken && res.authToken) {
            inputToken.value = res.authToken;
        }
        if (document.activeElement !== inputName) {
            inputName.value = res.nodeName || "My Chrome Node";
        }

        if (res.connected) {
            liveDot.className = "dot online";
            liveStatusText.textContent = `Đã kết nối tới: ${res.backendUrl}`;
            latencyBadge.textContent = `${res.latencyMs || 0} ms`;
        } else {
            liveDot.className = "dot";
            liveStatusText.textContent = `Mất kết nối (${res.backendUrl})`;
            latencyBadge.textContent = "-- ms";
        }
    });
}

// Kiểm tra kết nối thử nghiệm (Ping Test)
btnTestPing.addEventListener("click", () => {
    const url = inputUrl.value.trim();
    const token = inputToken.value.trim();

    if (!url) {
        showResult("Vui lòng nhập địa chỉ URL máy chủ!", false);
        return;
    }

    btnTestPing.disabled = true;
    btnTestPing.textContent = "⏳ Đang kiểm tra...";

    chrome.runtime.sendMessage({ type: "TEST_CONNECTION", url, token }, (res) => {
        btnTestPing.disabled = false;
        btnTestPing.textContent = "🔍 Kiểm Tra Kết Nối (Ping)";

        if (res && res.success) {
            const projName = res.info?.project?.name ? ` | Dự Án: [${res.info.project.name}]` : '';
            showResult(`✅ Kết nối VPS thành công! Độ trễ (Ping): ${res.latencyMs}ms${projName}`, true);
        } else {
            showResult(`❌ Không thể kết nối tới ${url}: ${res?.error || "Lỗi mạng hoặc sai mã Token"}`, false);
        }
    });
});

// Lưu cấu hình
btnSaveConfig.addEventListener("click", () => {
    const backendUrl = inputUrl.value.trim();
    const authToken = inputToken.value.trim();
    const nodeName = inputName.value.trim();

    if (!backendUrl) {
        showResult("Vui lòng nhập địa chỉ URL máy chủ!", false);
        return;
    }

    btnSaveConfig.disabled = true;
    btnSaveConfig.textContent = "⏳ Đang lưu...";

    chrome.runtime.sendMessage({
        type: "SET_CONFIG",
        backendUrl,
        authToken,
        nodeName
    }, (res) => {
        btnSaveConfig.disabled = false;
        btnSaveConfig.textContent = "💾 Lưu Cấu Hình";

        if (res && res.success) {
            showResult(`✅ Đã lưu cấu hình thành công! Đang kết nối tới ${backendUrl}...`, true);
            updateStatus();
        } else {
            showResult("❌ Lỗi khi lưu cấu hình vào Storage!", false);
        }
    });
});

btnOpenWeb.addEventListener("click", () => {
    const url = inputUrl.value.trim() || "http://127.0.0.1:9999";
    chrome.tabs.create({ url });
});

function showResult(msg, isSuccess) {
    testResultText.style.display = "block";
    testResultText.textContent = msg;
    testResultText.style.color = isSuccess ? "var(--success)" : "var(--danger)";
}

// -------------------------------------------------------------
// TAB CONTROLLER & PRESET URL HANDLERS
// -------------------------------------------------------------
function initTabController() {
    const tabOptBawui = document.getElementById("tabOptBawui");
    const tabOptVidiq = document.getElementById("tabOptVidiq");
    const paneBawuiOptions = document.getElementById("paneBawuiOptions");
    const paneVidiqOptions = document.getElementById("paneVidiqOptions");

    function switchOptTab(tab) {
        if (tab === "vidiq") {
            if (tabOptVidiq) tabOptVidiq.classList.add("active");
            if (tabOptBawui) tabOptBawui.classList.remove("active");
            if (paneVidiqOptions) paneVidiqOptions.classList.add("active");
            if (paneBawuiOptions) paneBawuiOptions.classList.remove("active");
            try {
                history.replaceState(null, "", "#vidiq");
                localStorage.setItem("active_options_tab", "vidiq");
            } catch(e) {}
        } else {
            if (tabOptBawui) tabOptBawui.classList.add("active");
            if (tabOptVidiq) tabOptVidiq.classList.remove("active");
            if (paneBawuiOptions) paneBawuiOptions.classList.add("active");
            if (paneVidiqOptions) paneVidiqOptions.classList.remove("active");
            try {
                history.replaceState(null, "", "#bawui");
                localStorage.setItem("active_options_tab", "bawui");
            } catch(e) {}
        }
    }

    if (tabOptBawui) tabOptBawui.addEventListener("click", () => switchOptTab("bawui"));
    if (tabOptVidiq) tabOptVidiq.addEventListener("click", () => switchOptTab("vidiq"));

    // Check URL hash / query param / saved tab
    const hash = window.location.hash;
    const search = window.location.search;
    if (hash === "#vidiq" || search.includes("tab=vidiq")) {
        switchOptTab("vidiq");
    } else {
        // By default, or if #bawui, open BAWUI VPS Settings
        switchOptTab("bawui");
    }

    // Attach click handlers to preset URL tags
    document.querySelectorAll(".preset-tag").forEach((tag) => {
        tag.addEventListener("click", () => {
            const url = tag.getAttribute("data-url");
            if (url && inputUrl) {
                inputUrl.value = url;
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initTabController();
    updateStatus();
    setInterval(updateStatus, 3000);
});
