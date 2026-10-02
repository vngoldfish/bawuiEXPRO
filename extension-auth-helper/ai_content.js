/**
 * BAWUI AI — YouTube Content Script
 * Injects AI Analysis sidebar panel into YouTube watch pages.
 * Communicates with background.js via chrome.runtime.sendMessage.
 */
(function () {
    'use strict';

    // Avoid double injection
    if (document.getElementById('bawui-ai-root')) return;

    // =====================
    // State
    // =====================
    let videoData = null;
    let channelData = null;
    let isCollapsed = false;
    let currentAction = null;
    let panelEl = null;

    // =====================
    // 1. Data Extraction
    // =====================

    // Listen for data from ai_extractor.js (MAIN world)
    window.addEventListener('message', (event) => {
        if (event.source !== window) return;
        if (event.data?.type === 'BAWUI_AI_VIDEO_DATA' && event.data.source === 'extractor') {
            videoData = event.data.video || null;
            channelData = event.data.channel || null;
            updateVideoInfoCard();
        }
    });

    // Inject extractor into MAIN world
    function injectExtractor() {
        try {
            const s = document.createElement('script');
            s.src = chrome.runtime.getURL('ai_extractor.js');
            s.onload = () => s.remove();
            (document.head || document.documentElement).appendChild(s);
        } catch (e) {
            console.warn('[BAWUI AI] Failed to inject extractor:', e);
            // Fallback: extract from DOM
            extractFromDOM();
        }
    }

    // Fallback DOM extraction (limited data)
    function extractFromDOM() {
        try {
            const titleEl = document.querySelector('h1.ytd-watch-metadata yt-formatted-string, h1.title yt-formatted-string');
            const channelEl = document.querySelector('#owner #channel-name a, ytd-video-owner-renderer #channel-name a');
            const viewEl = document.querySelector('.view-count, ytd-video-view-count-renderer span');
            const descEl = document.querySelector('#description-inline-expander, #description ytd-text-inline-expander');

            videoData = {
                title: titleEl?.textContent?.trim() || document.title.replace(' - YouTube', ''),
                description: descEl?.textContent?.trim() || '',
                author: channelEl?.textContent?.trim() || '',
                viewCountText: viewEl?.textContent?.trim() || '',
                videoId: new URLSearchParams(location.search).get('v') || '',
                keywords: [],
                source: 'dom-fallback'
            };
            updateVideoInfoCard();
        } catch (e) {
            console.warn('[BAWUI AI] DOM extraction failed:', e);
        }
    }

    // Extract comments from DOM
    function extractComments(maxCount = 50) {
        const comments = [];
        const commentEls = document.querySelectorAll('ytd-comment-thread-renderer');
        for (let i = 0; i < Math.min(commentEls.length, maxCount); i++) {
            const el = commentEls[i];
            const author = el.querySelector('#author-text span')?.textContent?.trim() || '';
            const text = el.querySelector('#content-text')?.textContent?.trim() || '';
            const likes = el.querySelector('#vote-count-middle')?.textContent?.trim() || '0';
            if (text) comments.push({ author, text, likes });
        }
        return comments;
    }

    // =====================
    // 2. Simple Markdown Renderer
    // =====================

    function renderMarkdown(text) {
        if (!text) return '';
        let html = text
            // Escape HTML
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            // Headers
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // Bold & Italic
            .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // Code blocks
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Blockquotes
            .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
            // Unordered lists
            .replace(/^[*-] (.+)$/gm, '<li>$1</li>')
            // Ordered lists
            .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
            // Line breaks
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        // Wrap consecutive <li> in <ul>
        html = html.replace(/(<li>.*?<\/li>)(\s*<br>)?/g, '$1');
        html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');

        return '<p>' + html + '</p>';
    }

    // =====================
    // 3. UI Panel
    // =====================

    function createPanel() {
        const root = document.createElement('div');
        root.id = 'bawui-ai-root';
        root.className = 'bawui-ai-scope';

        root.innerHTML = `
            <div class="bawui-ai-panel">
                <!-- Header -->
                <div class="bawui-ai-header" id="bawui-ai-header">
                    <div class="bawui-ai-header-left">
                        <span class="bawui-ai-logo">🤖</span>
                        <div>
                            <div class="bawui-ai-title">BAWUI AI Analysis</div>
                            <div class="bawui-ai-subtitle">Phân tích AI độc lập</div>
                        </div>
                    </div>
                    <button class="bawui-ai-toggle" id="bawui-ai-collapse" title="Thu gọn">▼</button>
                </div>

                <!-- Status -->
                <div class="bawui-ai-status">
                    <span class="bawui-ai-status-dot" id="bawui-ai-dot"></span>
                    <span id="bawui-ai-status-text">Đang kiểm tra kết nối...</span>
                </div>

                <!-- Body -->
                <div class="bawui-ai-body" id="bawui-ai-body">
                    <!-- Provider selector -->
                    <div class="bawui-ai-provider-row">
                        <select class="bawui-ai-provider-select" id="bawui-ai-provider">
                            <option value="custom">Custom API (VPS)</option>
                            <option value="openai">OpenAI</option>
                            <option value="gemini">Google Gemini</option>
                            <option value="claude">Anthropic Claude</option>
                            <option value="groq">Groq</option>
                            <option value="deepseek">DeepSeek</option>
                        </select>
                        <button class="bawui-ai-settings-btn" id="bawui-ai-settings-btn" title="Cài đặt API">⚙️</button>
                    </div>

                    <!-- Video info card -->
                    <div class="bawui-ai-video-info" id="bawui-ai-video-info">
                        <div class="bawui-ai-video-title" id="bawui-ai-vtitle">Đang tải thông tin video...</div>
                        <div class="bawui-ai-video-meta" id="bawui-ai-vmeta"></div>
                    </div>

                    <!-- Action buttons -->
                    <div class="bawui-ai-actions">
                        <button class="bawui-ai-btn" data-action="analyzeVideo">
                            <span class="bawui-ai-btn-icon">🎯</span>
                            <span>Video SEO</span>
                        </button>
                        <button class="bawui-ai-btn" data-action="analyzeChannel">
                            <span class="bawui-ai-btn-icon">📺</span>
                            <span>Phân tích Kênh</span>
                        </button>
                        <button class="bawui-ai-btn" data-action="analyzeComments">
                            <span class="bawui-ai-btn-icon">💬</span>
                            <span>Bình luận</span>
                        </button>
                        <button class="bawui-ai-btn" data-action="suggestContent">
                            <span class="bawui-ai-btn-icon">💡</span>
                            <span>Gợi ý Nội dung</span>
                        </button>
                    </div>

                    <!-- Loading -->
                    <div class="bawui-ai-loading" id="bawui-ai-loading">
                        <div class="bawui-ai-spinner"></div>
                        <span id="bawui-ai-loading-text">Đang phân tích...</span>
                    </div>

                    <!-- Error -->
                    <div class="bawui-ai-error" id="bawui-ai-error"></div>

                    <!-- Result -->
                    <div class="bawui-ai-result" id="bawui-ai-result"></div>
                </div>
            </div>
        `;

        panelEl = root;
        return root;
    }

    function updateVideoInfoCard() {
        if (!panelEl) return;
        const titleEl = panelEl.querySelector('#bawui-ai-vtitle');
        const metaEl = panelEl.querySelector('#bawui-ai-vmeta');
        if (!titleEl || !metaEl) return;

        if (videoData) {
            titleEl.textContent = videoData.title || 'Không có tiêu đề';
            const parts = [];
            if (videoData.viewCount) parts.push(`👁 ${Number(videoData.viewCount).toLocaleString('vi-VN')} views`);
            else if (videoData.viewCountText) parts.push(`👁 ${videoData.viewCountText}`);
            if (videoData.author) parts.push(`📺 ${videoData.author}`);
            if (videoData.keywords?.length) parts.push(`🏷 ${videoData.keywords.length} tags`);
            if (videoData.lengthSeconds) {
                const min = Math.floor(videoData.lengthSeconds / 60);
                const sec = videoData.lengthSeconds % 60;
                parts.push(`⏱ ${min}:${String(sec).padStart(2, '0')}`);
            }
            metaEl.textContent = parts.join('  •  ');
        } else {
            titleEl.textContent = 'Đang tải thông tin video...';
            metaEl.textContent = '';
        }
    }

    // =====================
    // 4. Event Handlers
    // =====================

    function bindEvents() {
        if (!panelEl) return;

        // Collapse toggle
        const header = panelEl.querySelector('#bawui-ai-header');
        const collapseBtn = panelEl.querySelector('#bawui-ai-collapse');
        header.addEventListener('click', () => {
            isCollapsed = !isCollapsed;
            const body = panelEl.querySelector('#bawui-ai-body');
            body.classList.toggle('collapsed', isCollapsed);
            collapseBtn.textContent = isCollapsed ? '▶' : '▼';
        });

        // Settings button → open extension popup
        panelEl.querySelector('#bawui-ai-settings-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            chrome.runtime.sendMessage({ type: 'BAWUI_AI', action: 'getConfig' }, (res) => {
                if (res?.success) {
                    const cfg = res.data;
                    const url = prompt('AI API URL:', cfg.url || '');
                    if (url !== null) {
                        const key = prompt('API Key (để trống nếu không cần):', '');
                        const model = prompt('Model name:', cfg.model || 'default');
                        chrome.runtime.sendMessage({
                            type: 'BAWUI_AI',
                            action: 'saveConfig',
                            config: { url, key: key || '', model: model || 'default', language: 'vi' }
                        }, () => checkApiConnection());
                    }
                }
            });
        });

        // Provider change → update API URL preset
        panelEl.querySelector('#bawui-ai-provider').addEventListener('change', (e) => {
            const provider = e.target.value;
            const presets = {
                'openai': 'https://api.openai.com/v1/chat/completions',
                'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                'claude': 'https://api.anthropic.com/v1/messages',
                'groq': 'https://api.groq.com/openai/v1/chat/completions',
                'deepseek': 'https://api.deepseek.com/v1/chat/completions',
                'custom': ''
            };
            if (presets[provider]) {
                const key = prompt(`Nhập API Key cho ${provider}:`, '');
                if (key !== null) {
                    const model = prompt('Model name (ví dụ: gpt-4o, gemini-2.0-flash, llama-3.3-70b):', '');
                    chrome.runtime.sendMessage({
                        type: 'BAWUI_AI',
                        action: 'saveConfig',
                        config: {
                            url: presets[provider],
                            key: key || '',
                            model: model || 'default',
                            language: 'vi',
                            provider: provider
                        }
                    }, () => checkApiConnection());
                }
            }
        });

        // Action buttons
        panelEl.querySelectorAll('.bawui-ai-btn[data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                executeAction(action);
            });
        });
    }

    // =====================
    // 5. AI Actions
    // =====================

    function showLoading(text) {
        if (!panelEl) return;
        panelEl.querySelector('#bawui-ai-loading').classList.add('visible');
        panelEl.querySelector('#bawui-ai-loading-text').textContent = text || 'Đang phân tích...';
        panelEl.querySelector('#bawui-ai-result').classList.remove('visible');
        panelEl.querySelector('#bawui-ai-error').classList.remove('visible');

        // Highlight active button
        panelEl.querySelectorAll('.bawui-ai-btn').forEach(b => b.classList.remove('active'));
        const activeBtn = panelEl.querySelector(`.bawui-ai-btn[data-action="${currentAction}"]`);
        if (activeBtn) activeBtn.classList.add('active');
    }

    function showResult(html) {
        if (!panelEl) return;
        panelEl.querySelector('#bawui-ai-loading').classList.remove('visible');
        const resultEl = panelEl.querySelector('#bawui-ai-result');
        resultEl.innerHTML = html;
        resultEl.classList.add('visible');
        panelEl.querySelector('#bawui-ai-error').classList.remove('visible');
    }

    function showError(msg) {
        if (!panelEl) return;
        panelEl.querySelector('#bawui-ai-loading').classList.remove('visible');
        panelEl.querySelector('#bawui-ai-result').classList.remove('visible');
        const errEl = panelEl.querySelector('#bawui-ai-error');
        errEl.textContent = '❌ ' + msg;
        errEl.classList.add('visible');
        panelEl.querySelectorAll('.bawui-ai-btn').forEach(b => b.classList.remove('active'));
    }

    async function executeAction(action) {
        currentAction = action;

        const loadingTexts = {
            analyzeVideo: '🎯 Đang phân tích SEO video...',
            analyzeChannel: '📺 Đang phân tích kênh...',
            analyzeComments: '💬 Đang phân tích bình luận...',
            suggestContent: '💡 Đang tạo gợi ý nội dung...'
        };

        showLoading(loadingTexts[action]);

        const msg = { type: 'BAWUI_AI', action };

        if (action === 'analyzeVideo' || action === 'suggestContent') {
            if (!videoData) {
                showError('Không thể thu thập dữ liệu video. Hãy đảm bảo bạn đang ở trang xem video YouTube.');
                return;
            }
            msg.videoData = videoData;
        } else if (action === 'analyzeChannel') {
            msg.channelData = channelData || { name: videoData?.author, channelId: videoData?.channelId };
            msg.videoData = videoData; // context
        } else if (action === 'analyzeComments') {
            const comments = extractComments();
            if (comments.length === 0) {
                showError('Chưa tìm thấy bình luận. Hãy cuộn xuống để tải bình luận trước.');
                return;
            }
            msg.comments = comments;
            msg.videoData = videoData; // context
        }

        try {
            const response = await new Promise((resolve, reject) => {
                chrome.runtime.sendMessage(msg, (res) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else if (res?.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res?.error || 'Unknown error'));
                    }
                });
            });

            showResult(renderMarkdown(response));
        } catch (err) {
            showError(err.message || 'Lỗi không xác định');
        }
    }

    // =====================
    // 6. API Connection Check
    // =====================

    function checkApiConnection() {
        chrome.runtime.sendMessage({ type: 'BAWUI_AI', action: 'getConfig' }, (res) => {
            if (!panelEl) return;
            const dot = panelEl.querySelector('#bawui-ai-dot');
            const statusText = panelEl.querySelector('#bawui-ai-status-text');

            if (chrome.runtime.lastError || !res?.success) {
                dot.classList.remove('connected');
                statusText.textContent = 'Extension không phản hồi';
                return;
            }

            const cfg = res.data;
            if (cfg.url) {
                dot.classList.add('connected');
                statusText.textContent = `Kết nối: ${cfg.model || 'default'} @ ${new URL(cfg.url).hostname}`;
                // Load saved provider
                const providerSelect = panelEl.querySelector('#bawui-ai-provider');
                if (cfg.provider && providerSelect) {
                    providerSelect.value = cfg.provider;
                }
            } else {
                dot.classList.remove('connected');
                statusText.textContent = 'Chưa cấu hình API — nhấn ⚙️ để thiết lập';
            }
        });
    }

    // =====================
    // 7. Panel Injection into YouTube
    // =====================

    function injectPanel() {
        // Only on watch pages
        if (!location.pathname.startsWith('/watch')) return;
        if (document.getElementById('bawui-ai-root')) return;

        // Find YouTube sidebar
        const sidebar = document.querySelector('#secondary-inner, #secondary');
        if (!sidebar) return;

        // Create and inject panel
        const panel = createPanel();

        // Insert before related videos
        const relatedVideos = sidebar.querySelector('ytd-watch-next-secondary-results-renderer, #related');
        if (relatedVideos) {
            sidebar.insertBefore(panel, relatedVideos);
        } else {
            sidebar.prepend(panel);
        }

        bindEvents();
        checkApiConnection();
        injectExtractor();
    }

    // =====================
    // 8. YouTube SPA Navigation Handling
    // =====================

    function cleanup() {
        const existing = document.getElementById('bawui-ai-root');
        if (existing) existing.remove();
        videoData = null;
        channelData = null;
        currentAction = null;
        panelEl = null;
    }

    // Watch for URL changes (YouTube SPA)
    let lastPathname = location.pathname;
    let lastSearch = location.search;

    function checkNavigation() {
        if (location.pathname !== lastPathname || location.search !== lastSearch) {
            lastPathname = location.pathname;
            lastSearch = location.search;
            cleanup();
            if (location.pathname.startsWith('/watch')) {
                setTimeout(() => injectPanel(), 1500);
            }
        }
    }

    // MutationObserver for SPA navigation
    const navObserver = new MutationObserver(checkNavigation);
    navObserver.observe(document.body, { childList: true, subtree: true });

    // Also listen for yt-navigate-finish event
    window.addEventListener('yt-navigate-finish', () => {
        checkNavigation();
    });

    // =====================
    // 9. Initial injection
    // =====================

    function waitForSidebar(attempts = 0) {
        if (attempts > 30) return; // give up after 15 seconds
        if (!location.pathname.startsWith('/watch')) return;

        const sidebar = document.querySelector('#secondary-inner, #secondary');
        if (sidebar) {
            injectPanel();
        } else {
            setTimeout(() => waitForSidebar(attempts + 1), 500);
        }
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => waitForSidebar());
    } else {
        waitForSidebar();
    }

})();
