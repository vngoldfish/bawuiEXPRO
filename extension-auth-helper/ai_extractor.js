/**
 * BAWUI AI — YouTube Data Extractor (MAIN World)
 * Runs in page context to access YouTube's global JS variables.
 * Sends extracted data back via window.postMessage.
 */
(function() {
    'use strict';

    function extractVideoData() {
        const data = { type: 'BAWUI_AI_VIDEO_DATA', source: 'extractor' };

        try {
            // 1. Video Details from ytInitialPlayerResponse
            const player = window.ytInitialPlayerResponse;
            if (player && player.videoDetails) {
                const vd = player.videoDetails;
                data.video = {
                    videoId: vd.videoId || '',
                    title: vd.title || '',
                    description: vd.shortDescription || '',
                    author: vd.author || '',
                    channelId: vd.channelId || '',
                    viewCount: parseInt(vd.viewCount) || 0,
                    lengthSeconds: parseInt(vd.lengthSeconds) || 0,
                    keywords: vd.keywords || [],
                    thumbnail: vd.thumbnail?.thumbnails?.slice(-1)?.[0]?.url || '',
                    isLive: vd.isLiveContent || false,
                    isPrivate: vd.isPrivate || false
                };
            }

            // 2. Microformat data (category, publish date, etc.)
            const micro = player?.microformat?.playerMicroformatRenderer;
            if (micro) {
                data.video = data.video || {};
                data.video.category = micro.category || '';
                data.video.publishDate = micro.publishDate || '';
                data.video.uploadDate = micro.uploadDate || '';
                data.video.country = micro.availableCountries || [];
                data.video.isFamilySafe = micro.isFamilySafe;
                data.video.hasYtChapters = !!micro.description; // rough check
            }

            // 3. Engagement data from ytInitialData
            const ytData = window.ytInitialData;
            if (ytData) {
                // Channel info
                const owner = ytData.contents?.twoColumnWatchNextResults?.results?.results?.contents;
                if (owner) {
                    for (const item of owner) {
                        // Video primary info
                        const primary = item.videoPrimaryInfoRenderer;
                        if (primary) {
                            const viewText = primary.viewCount?.videoViewCountRenderer?.viewCount?.simpleText || '';
                            data.video = data.video || {};
                            data.video.viewCountText = viewText;

                            // Like count
                            const likeBtn = primary.videoActions?.menuRenderer?.topLevelButtons?.[0]
                                ?.segmentedLikeDislikeButtonViewModel?.likeButtonViewModel
                                ?.likeButtonViewModel?.toggleButtonViewModel?.toggleButtonViewModel
                                ?.defaultButtonViewModel?.buttonViewModel?.accessibilityText;
                            if (likeBtn) data.video.likeText = likeBtn;
                        }

                        // Channel secondary info
                        const secondary = item.videoSecondaryInfoRenderer;
                        if (secondary) {
                            const ch = secondary.owner?.videoOwnerRenderer;
                            if (ch) {
                                data.channel = {
                                    name: ch.title?.runs?.[0]?.text || '',
                                    subscriberText: ch.subscriberCountText?.simpleText || '',
                                    thumbnail: ch.thumbnail?.thumbnails?.slice(-1)?.[0]?.url || '',
                                    channelUrl: ch.navigationEndpoint?.browseEndpoint?.canonicalBaseUrl || ''
                                };
                            }
                            // Full description
                            const descRuns = secondary.attributedDescription?.content;
                            if (descRuns) {
                                data.video = data.video || {};
                                data.video.fullDescription = descRuns;
                            }
                        }
                    }
                }

                // Comments section info
                const engagementPanels = ytData.engagementPanels;
                if (engagementPanels) {
                    for (const panel of engagementPanels) {
                        const renderer = panel.engagementPanelSectionListRenderer;
                        if (renderer?.panelIdentifier === 'comment-item-section') {
                            const header = renderer.header?.engagementPanelTitleHeaderRenderer?.contextualInfo?.runs;
                            if (header) {
                                data.commentCount = header.map(r => r.text).join('');
                            }
                        }
                    }
                }
            }

            // 4. ytcfg data
            if (window.ytcfg && window.ytcfg.data_) {
                const cfg = window.ytcfg.data_;
                data.ytcfg = {
                    locale: cfg.INNERTUBE_CONTEXT_HL || '',
                    country: cfg.INNERTUBE_CONTEXT_GL || '',
                    channelId: cfg.CHANNEL_ID || ''
                };
            }

        } catch (e) {
            data.error = e.message;
        }

        window.postMessage(data, '*');
    }

    // Extract immediately
    extractVideoData();

    // Also extract on YouTube SPA navigation
    let lastUrl = location.href;
    const observer = new MutationObserver(() => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            setTimeout(extractVideoData, 1500); // wait for YouTube to update globals
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();
