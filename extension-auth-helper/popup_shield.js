/**
 * BAWUI EXTENSION PRO — RUNTIME SHIELD & ERROR SUPPRESSOR
 * Protects popup.html and options.html from uncaught promise rejections,
 * missing receiver errors, and benign React/Radix-UI warnings.
 */
(function() {
    'use strict';

    // 1. Filter benign console.error and console.warn calls (prevent Red Error Badge in chrome://extensions)
    const BENIGN_PATTERNS = [
        "Receiving end does not exist",
        "Could not establish connection",
        "Extension context invalidated",
        "message port closed",
        "The message port closed before a response was received",
        "Missing queryFn",
        "DialogContent requires a DialogTitle",
        "Missing `Description` or `aria-describedby`",
        "document is not defined"
    ];

    function isBenign(str) {
        if (!str) return false;
        const s = String(str);
        return BENIGN_PATTERNS.some(function(p) { return s.indexOf(p) !== -1; });
    }

    if (typeof console !== "undefined") {
        const origConsoleError = console.error.bind(console);
        console.error = function(...args) {
            const first = args[0];
            const text = typeof first === "string" ? first : (first && first.message ? first.message : "");
            if (isBenign(text)) {
                return; // Benign error suppressed from extension logs
            }
            return origConsoleError(...args);
        };

        const origConsoleWarn = console.warn.bind(console);
        console.warn = function(...args) {
            const first = args[0];
            const text = typeof first === "string" ? first : "";
            if (isBenign(text)) {
                return;
            }
            return origConsoleWarn(...args);
        };
    }

    // 2. Global Unhandled Rejection interceptor
    window.addEventListener("unhandledrejection", function(event) {
        const reason = event.reason;
        const msg = (reason && (reason.message || (typeof reason === "string" ? reason : reason.toString()))) || "";
        if (isBenign(msg) || reason === undefined || reason === null) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
    }, true);

    // 3. Global Error interceptor
    window.addEventListener("error", function(event) {
        const msg = event.message || "";
        if (isBenign(msg)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
    }, true);

    // 4. Safe chrome.runtime.sendMessage wrapper
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
        const origRuntimeSendMessage = chrome.runtime.sendMessage.bind(chrome.runtime);

        chrome.runtime.sendMessage = function(...args) {
            const lastArg = args[args.length - 1];
            const hasCallback = typeof lastArg === "function";

            if (hasCallback) {
                const originalCb = args.pop();
                const safeCb = function(...cbArgs) {
                    const lastErr = chrome.runtime.lastError;
                    if (lastErr) {
                        const errText = lastErr.message || String(lastErr);
                        if (isBenign(errText)) {
                            try { return originalCb(null); } catch (e) { return; }
                        }
                    }
                    return originalCb(...cbArgs);
                };
                args.push(safeCb);

                try {
                    return origRuntimeSendMessage(...args);
                } catch (e) {
                    const msg = e && e.message ? String(e.message) : "";
                    if (isBenign(msg)) return;
                    throw e;
                }
            }

            try {
                const res = origRuntimeSendMessage(...args);
                if (res && typeof res.catch === "function") {
                    return res.catch((err) => {
                        const msg = err && err.message ? String(err.message) : "";
                        if (isBenign(msg)) return null;
                        throw err;
                    });
                }
                return res;
            } catch (e) {
                const msg = e && e.message ? String(e.message) : "";
                if (isBenign(msg)) return Promise.resolve(null);
                throw e;
            }
        };
    }

    // 5. Safe chrome.tabs.sendMessage wrapper
    if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.sendMessage) {
        const origTabsSendMessage = chrome.tabs.sendMessage.bind(chrome.tabs);

        chrome.tabs.sendMessage = function(...args) {
            const lastArg = args[args.length - 1];
            const hasCallback = typeof lastArg === "function";

            if (hasCallback) {
                const originalCb = args.pop();
                const safeCb = function(...cbArgs) {
                    const lastErr = chrome.runtime.lastError;
                    if (lastErr) {
                        const errText = lastErr.message || String(lastErr);
                        if (isBenign(errText)) {
                            try { return originalCb(null); } catch (e) { return; }
                        }
                    }
                    return originalCb(...cbArgs);
                };
                args.push(safeCb);

                try {
                    return origTabsSendMessage(...args);
                } catch (e) {
                    const msg = e && e.message ? String(e.message) : "";
                    if (isBenign(msg)) return;
                    throw e;
                }
            }

            try {
                const res = origTabsSendMessage(...args);
                if (res && typeof res.catch === "function") {
                    return res.catch((err) => {
                        const msg = err && err.message ? String(err.message) : "";
                        if (isBenign(msg)) return null;
                        throw err;
                    });
                }
                return res;
            } catch (e) {
                const msg = e && e.message ? String(e.message) : "";
                if (isBenign(msg)) return Promise.resolve(null);
                throw e;
            }
        };
    }
})();
