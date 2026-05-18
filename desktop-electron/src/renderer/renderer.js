/**
 * SynapseAutomation - Core Renderer
 * 精致化标签管理与自动化环境适配
 */

const ICONS = {
    home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="4"></rect><path d="M8 9.5h8"></path><path d="M8 14h5"></path></svg>`,
    browser: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"></circle><path d="M12 3.5c2.8 2.2 4.2 5 4.2 8.5S14.8 18.3 12 20.5c-2.8-2.2-4.2-5-4.2-8.5S9.2 5.7 12 3.5Z"></path><path d="M3.8 12h16.4"></path></svg>`,
    hermes: `<span class="hermes-logo-icon" aria-hidden="true"></span>`,
    douyin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4v8.75a3.75 3.75 0 1 1-3.75-3.75"></path><path d="M14 4c1.1 2 2.8 3.5 5 4.25"></path></svg>`,
    kuaishou: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="5.5" y="5" width="5.5" height="5.5" rx="1.8"></rect><rect x="13" y="5" width="5.5" height="5.5" rx="1.8"></rect><rect x="5.5" y="13.5" width="5.5" height="5.5" rx="1.8"></rect><rect x="13" y="13.5" width="5.5" height="5.5" rx="1.8"></rect></svg>`,
    xiaohongshu: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="4.5" width="15" height="15" rx="4.2"></rect><path d="M8.5 8.5 15.5 15.5"></path><path d="M15.5 8.5 8.5 15.5"></path></svg>`,
    bilibili: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="6.5" width="16" height="11" rx="3"></rect><path d="M8 4 10 6.5"></path><path d="M16 4 14 6.5"></path><path d="M9.25 11h.01"></path><path d="M14.75 11h.01"></path></svg>`
};

const TAB_LABELS = {
    home: '工作台',
    browser: '浏览器',
    hermes: 'Hermes 控制台',
    douyin: '抖音',
    kuaishou: '快手',
    xiaohongshu: '小红书',
    bilibili: '哔哩哔哩'
};

class TabManager {
    constructor() {
        this.tabs = [];
        this.activeId = null;
        this.nextId = 1;
        this.hideTimeout = null;
        this.homeUrl = 'http://127.0.0.1:3000';
        this.internalRetryState = new Map();

        this.sidebar = document.getElementById('sidebar-tabs');
        this.container = document.getElementById('webview-container');
        this.urlBar = document.getElementById('url-bar');
        this.popup = document.getElementById('tab-popup');
        this.pUrlDisplay = document.getElementById('p-url-display');
        this.pUrlInput = document.getElementById('p-url-input');
        this.hermesButton = document.getElementById('hermes-dashboard-btn');

        if (this.sidebar) {
            this.sidebar.innerHTML = '';
        }
        if (this.container) {
            this.container.innerHTML = '';
        }
        if (this.popup) {
            this.popup.style.display = 'none';
            delete this.popup.dataset.tabId;
        }

        this.setupListeners();
        // 默认首页
        this.homeTabId = this.addTab(this.homeUrl, 'home', true, { initialUrl: this.homeUrl });
        setTimeout(() => {
            this.hydrateHomeTab().catch((error) => {
                console.warn('[Shell] Initial home hydration failed:', error);
            });
        }, 0);
    }

    setupListeners() {
        document.getElementById('add-tab').onclick = () => {
            this.addTab('https://www.google.com', 'browser');
        };

        if (this.hermesButton) {
            this.hermesButton.onclick = () => {
                this.openHermesDashboard();
            };
        }

        // 设置按钮点击 - 打开/关闭设置面板
        document.getElementById('settings-btn').onclick = () => {
            toggleSettingsPanel();
        };

        // 设置面板关闭按钮
        document.getElementById('settings-close').onclick = () => {
            closeSettingsPanel();
        };

        // 点击遮罩层关闭设置面板
        document.getElementById('settings-overlay').onclick = () => {
            closeSettingsPanel();
        };

        // 主地址栏监听
        this.urlBar.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                const url = this.urlBar.value.trim();
                console.log('[地址栏] 按下回车，URL:', url);
                if (url) {
                    this.performNavigation(url);
                }
                this.urlBar.blur();
            }
        });

        // 弹窗 URL 点击切换编辑态
        document.getElementById('p-url-container').onclick = (e) => {
            this.pUrlDisplay.style.display = 'none';
            this.pUrlInput.style.display = 'block';
            this.pUrlInput.focus();
            this.pUrlInput.select();
        };

        this.pUrlInput.onblur = () => {
            this.pUrlDisplay.style.display = 'block';
            this.pUrlInput.style.display = 'none';
        };

        this.pUrlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                const url = this.pUrlInput.value.trim();
                if (url) {
                    this.performNavigation(url, this.popup.dataset.tabId);
                }
                this.pUrlInput.blur();
            }
        });

        // 弹窗工具栏控制
        const popupTab = () => this.tabs.find(t => t.id === this.popup.dataset.tabId) || this.activeTab();
        const goBack = () => {
            const tab = popupTab();
            if (typeof tab?.webview?.canGoBack === 'function' && tab.webview.canGoBack()) tab.webview.goBack();
        };
        const goForward = () => {
            const tab = popupTab();
            if (typeof tab?.webview?.canGoForward === 'function' && tab.webview.canGoForward()) tab.webview.goForward();
        };
        const reload = () => {
            const tab = popupTab();
            if (typeof tab?.webview?.reload === 'function') tab.webview.reload();
        };

        document.getElementById('p-back').onclick = goBack;
        document.getElementById('p-forward').onclick = goForward;
        document.getElementById('p-reload').onclick = reload;
        document.getElementById('p-copy').onclick = () => {
            const url = this.getWebviewUrl(popupTab()?.webview);
            if (url) {
                navigator.clipboard.writeText(url);
                const originalTitle = document.getElementById('p-title').textContent;
                document.getElementById('p-title').textContent = '已复制到剪贴板 !';
                setTimeout(() => { document.getElementById('p-title').textContent = originalTitle; }, 1500);
            }
        };

        document.getElementById('p-close').onclick = () => {
            this.removeTab(this.popup.dataset.tabId);
            this.hidePopup();
        };

        // 弹窗悬浮逻辑
        this.popup.onmouseleave = () => this.hidePopup();
        this.popup.onmouseenter = () => { if (this.hideTimeout) clearTimeout(this.hideTimeout); };

        // 监听来自内部页面的消息 (用于创作者中心集成)
        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'OPEN_CREATOR_TAB') {
                this.addTabWithCookies(event.data.url, event.data.cookies || [], event.data.platform || 'browser', event.data.storageState, event.data.accountId);
            }
        });
    }

    getTabTooltip(type, pinned = false) {
        if (pinned) return '工作台';
        return TAB_LABELS[type] || '浏览器会话';
    }

    getWebviewUrl(webview, fallback = '') {
        if (!webview) return fallback;
        if (typeof webview.getURL === 'function') {
            return webview.getURL() || fallback || webview.getAttribute('src') || '';
        }
        return webview.getAttribute('src') || fallback;
    }

    getWebviewTitle(webview, fallback = '') {
        if (!webview) return fallback;
        if (typeof webview.getTitle === 'function') {
            return webview.getTitle() || fallback;
        }
        return fallback;
    }

    async resolveHomeUrl() {
        const fallbackUrl = this.homeUrl || 'http://127.0.0.1:3000';
        if (!window.electronAPI?.app?.getInfo) {
            return fallbackUrl;
        }

        try {
            const info = await window.electronAPI.app.getInfo();
            const candidate = String(info?.frontendUrl || '').trim();
            if (candidate) {
                this.homeUrl = candidate.replace(/\/+$/, '');
            }
        } catch (error) {
            console.warn('[Shell] Failed to resolve home URL, using fallback:', error);
        }

        return this.homeUrl || fallbackUrl;
    }

    async hydrateHomeTab() {
        const homeUrl = await this.resolveHomeUrl();
        const homeTab = this.tabs.find((tab) => tab.id === this.homeTabId) || this.tabs.find((tab) => tab.pinned);
        if (!homeTab) return;

        homeTab.url = homeUrl;
        this.loadWebviewUrl(homeTab.webview, homeUrl);
        if (homeTab.id === this.activeId) {
            this.urlBar.value = homeUrl;
        }
        if (this.popup.style.display === 'block' && this.popup.dataset.tabId === homeTab.id) {
            this.syncPopupInfo(homeTab);
        }
    }

    loadWebviewUrl(webview, url) {
        if (!webview || !url) return;
        const retryTab = this.tabs.find((tab) => tab.webview === webview);
        if (retryTab) {
            this.clearInternalRetry(retryTab.id);
            retryTab.url = url;
        }
        webview.setAttribute('src', url);
        webview.src = url;
        setTimeout(() => {
            if (webview.isConnected && this.getWebviewUrl(webview) !== url) {
                webview.setAttribute('src', url);
                webview.src = url;
            }
        }, 200);
    }

    clearInternalRetry(tabId) {
        const state = this.internalRetryState.get(tabId);
        if (state?.timer) {
            clearTimeout(state.timer);
        }
        this.internalRetryState.delete(tabId);
    }

    isManagedLocalUrl(url) {
        const candidate = String(url || '').trim();
        if (!candidate) return false;

        try {
            const parsed = new URL(candidate);
            return ['127.0.0.1', 'localhost'].includes(parsed.hostname);
        } catch (_) {
            return false;
        }
    }

    shouldRetryManagedTab(tab, url) {
        if (!tab || !this.isManagedLocalUrl(url)) {
            return false;
        }

        if (tab.pinned) {
            return true;
        }

        return ['hermes', 'lumenx'].includes(tab.type);
    }

    scheduleManagedTabRetry(tab, failedUrl) {
        if (!this.shouldRetryManagedTab(tab, failedUrl)) {
            return;
        }

        const existing = this.internalRetryState.get(tab.id);
        const attempts = (existing?.attempts || 0) + 1;
        if (attempts > 20) {
            this.clearInternalRetry(tab.id);
            return;
        }

        const timer = setTimeout(() => {
            const latestTab = this.tabs.find((item) => item.id === tab.id);
            if (!latestTab || !latestTab.webview?.isConnected) {
                this.clearInternalRetry(tab.id);
                return;
            }

            const retryUrl = latestTab.url || failedUrl;
            console.warn(`[Navigation] Retrying managed local tab load (${attempts}/20):`, retryUrl);
            this.loadWebviewUrl(latestTab.webview, retryUrl);
        }, 1500);

        this.internalRetryState.set(tab.id, { attempts, timer });
    }

    isShellHomeUrl(url) {
        const candidate = String(url || '').trim();
        const normalizedHomeUrl = String(this.homeUrl || '').trim();
        if (!candidate || !normalizedHomeUrl) {
            return false;
        }

        try {
            const targetUrl = new URL(candidate);
            const homeUrl = new URL(normalizedHomeUrl);
            return targetUrl.origin === homeUrl.origin;
        } catch (error) {
            return false;
        }
    }

    shouldOpenInBrowserTab(tab, url) {
        if (!tab?.pinned) return false;
        return !this.isShellHomeUrl(url);
    }

    waitForWebviewEvent(webview, eventNames = ['did-stop-loading'], timeoutMs = 15000) {
        const names = Array.isArray(eventNames) ? eventNames : [eventNames];
        return new Promise((resolve) => {
            let done = false;
            let timer = null;
            const handlers = new Map();
            const cleanup = (result) => {
                if (done) return;
                done = true;
                if (timer) clearTimeout(timer);
                names.forEach((name) => webview.removeEventListener(name, handlers.get(name)));
                resolve(result);
            };
            names.forEach((name) => {
                const handler = (event) => cleanup({ event: name, detail: event });
                handlers.set(name, handler);
                webview.addEventListener(name, handler, { once: true });
            });
            timer = setTimeout(() => cleanup({ event: 'timeout' }), timeoutMs);
        });
    }

    async injectLocalStorage(webview, storageState, targetUrl) {
        const origins = storageState?.origins || [];
        if (!origins.length) return;

        let targetOrigin = null;
        try {
            targetOrigin = new URL(targetUrl).origin;
        } catch {
            targetOrigin = null;
        }

        for (const originState of origins) {
            const items = originState.localStorage || [];
            if (!originState.origin || !items.length) continue;
            if (targetOrigin && originState.origin !== targetOrigin) continue;

            const bootstrapUrl = originState.origin.endsWith('/') ? originState.origin : `${originState.origin}/`;
            console.log(`[Shell] Preparing localStorage for ${originState.origin}: ${items.length} items`);
            webview.loadURL(bootstrapUrl);
            await this.waitForWebviewEvent(webview, ['did-stop-loading', 'did-fail-load'], 15000);
            await webview.executeJavaScript(`
                (() => {
                    const entries = ${JSON.stringify(items)};
                    for (const entry of entries) {
                        if (entry && typeof entry.name === 'string') {
                            localStorage.setItem(entry.name, String(entry.value ?? ''));
                        }
                    }
                    return true;
                })();
            `, true);
        }
    }

    getStorageStateUserAgent(storageState) {
        const origins = storageState?.origins || [];
        for (const originState of origins) {
            for (const entry of originState.localStorage || []) {
                if (entry?.name !== 'finder_ua_report_data') continue;
                try {
                    const data = JSON.parse(entry.value || '{}');
                    if (data.browser === 'Chrome' && data.browserVersion) {
                        return `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${data.browserVersion} Safari/537.36`;
                    }
                } catch {
                    // Ignore malformed platform telemetry.
                }
            }
        }
        return null;
    }

    getAccountPartition(platform, accountId) {
        const safePlatform = String(platform || 'browser').replace(/[^a-z0-9_-]/gi, '_');
        const safeAccountId = String(accountId || '').replace(/[^a-z0-9_-]/gi, '_');
        return safeAccountId ? `persist:account-${safePlatform}-${safeAccountId}` : null;
    }

    async addTabWithCookies(url, cookies, platform = 'browser', storageState = null, accountId = null) {
        const partition = this.getAccountPartition(platform, accountId);
        const id = this.addTab(url, platform, false, {
            initialUrl: url,
            partition,
            userAgent: this.getStorageStateUserAgent(storageState)
        });
        const tabPartition = partition || `persist:${id}`;
        const tab = this.tabs.find(t => t.id === id);

        if (window.electronAPI && window.electronAPI.session) {
            const stateCookies = storageState?.cookies || cookies || [];
            console.log(`[Shell] Injecting ${stateCookies.length} cookies into ${tabPartition} for ${platform}`);
            const result = await window.electronAPI.session.setCookies(tabPartition, stateCookies);
            if (!result?.success && result !== true) {
                console.warn('[Shell] Cookie injection had failures:', result);
            }
        }

        if (tab) {
            this.loadWebviewUrl(tab.webview, url);
            this.urlBar.value = url;
        }
    }

    normalizeUrl(url) {
        if (!url) return '';
        let finalUrl = url.trim();
        if (!finalUrl) return '';

        if (finalUrl.includes('localhost') || finalUrl.startsWith('http://') || finalUrl.startsWith('https://')) {
            if (finalUrl.includes('localhost') && !finalUrl.startsWith('http')) {
                finalUrl = 'http://' + finalUrl;
            }
        } else if (finalUrl.includes('.') && !finalUrl.includes(' ')) {
            finalUrl = 'https://' + finalUrl;
        } else {
            finalUrl = 'https://www.google.com/search?q=' + encodeURIComponent(finalUrl);
        }

        return finalUrl;
    }

    navigate(url, tabId = null) {
        console.log('[导航] 开始导航到:', url);
        if (!url) {
            console.log('[导航] URL 为空，取消导航');
            return;
        }

        const finalUrl = this.normalizeUrl(url);

        console.log('[导航] 最终 URL:', finalUrl);

        const active = (tabId && this.tabs.find(t => t.id === tabId)) || this.activeTab();
        if (active) {
            console.log('[导航] 活动标签页:', active.id);
            console.log('[导航] 加载 URL 到 webview...');
            this.loadWebviewUrl(active.webview, finalUrl);
            // 更新地址栏显示
            if (active.id === this.activeId) this.urlBar.value = finalUrl;
            if (this.popup.style.display === 'block' && this.popup.dataset.tabId === active.id) {
                this.pUrlDisplay.textContent = finalUrl;
                this.pUrlInput.value = finalUrl;
            }
            console.log('[导航] 导航完成');
        } else {
            console.log('[导航] 没有活动标签页！');
        }
    }

    performNavigation(url, tabId = null) {
        const finalUrl = this.normalizeUrl(url);
        if (!finalUrl) return;

        const active = (tabId && this.tabs.find(t => t.id === tabId)) || this.activeTab();
        if (active) {
            if (this.shouldOpenInBrowserTab(active, finalUrl)) {
                const browserTabId = this.addTab(finalUrl, 'browser', false, { initialUrl: finalUrl });
                if (browserTabId) {
                    this.switchTab(browserTabId);
                }
                return;
            }

            active.url = finalUrl;
            this.loadWebviewUrl(active.webview, finalUrl);
            if (active.id === this.activeId) {
                this.urlBar.value = finalUrl;
            }
            if (this.popup.style.display === 'block' && this.popup.dataset.tabId === active.id) {
                this.pUrlDisplay.textContent = finalUrl;
                this.pUrlInput.value = finalUrl;
            }
            return;
        }

        const browserTabId = this.addTab(finalUrl, 'browser', false, { initialUrl: finalUrl });
        if (browserTabId) {
            this.switchTab(browserTabId);
        }
    }

    addTab(url, type = 'browser', pinned = false, options = {}) {
        if (!url) return;
        const id = `tab-${this.nextId++}`;

        const tabItem = document.createElement('div');
        tabItem.className = 'tab-item';
        tabItem.id = `btn-${id}`;
        tabItem.dataset.id = id;
        tabItem.dataset.tooltip = this.getTabTooltip(type, pinned);
        tabItem.title = this.getTabTooltip(type, pinned);
        if (pinned) {
            tabItem.classList.add('is-pinned');
        }

        // 根据类型选择图标
        const iconHtml = pinned ? ICONS.home : (ICONS[type] || ICONS.browser);
        tabItem.innerHTML = `<span class="tab-icon">${iconHtml}</span>`;

        if (!pinned) {
            const closeBtn = document.createElement('div');
            closeBtn.className = 'tab-close';
            closeBtn.innerHTML = '&times;';
            closeBtn.onclick = (e) => { e.stopPropagation(); this.removeTab(id); };
            tabItem.appendChild(closeBtn);
        }

        tabItem.onclick = () => this.switchTab(id);
        tabItem.onmouseenter = () => {
            if (this.hideTimeout) clearTimeout(this.hideTimeout);
            this.showPopup(id);
        };
        tabItem.onmouseleave = () => {
            this.hideTimeout = setTimeout(() => {
                if (!this.popup.matches(':hover')) this.hidePopup();
            }, 300); // 稍微加长延迟，方便移动
        };

        this.sidebar.appendChild(tabItem);

        const webview = document.createElement('webview');
        webview.id = `wv-${id}`;
        webview.setAttribute('allowpopups', '');
        webview.setAttribute('partition', options.partition || (pinned ? 'persist:main' : `persist:${id}`));
        webview.setAttribute('preload', new URL('webview-preload.js', window.location.href).toString());
        if (!pinned) {
            const userAgent = options.userAgent || navigator.userAgent
                .replace(/\sSynapseAutomation\/[^\s]+/g, '')
                .replace(/\sElectron\/[^\s]+/g, '');
            webview.setAttribute('useragent', userAgent);
        }
        webview.src = options.initialUrl || url;
        this.container.appendChild(webview);

        const tabData = { id, webview, tabItem, url, title: '会话加载中...', type, pinned };
        this.tabs.push(tabData);

        // 拦截新窗口
        webview.addEventListener('new-window', (e) => {
            e.preventDefault();
            this.addTab(e.url, 'browser');
        });

        webview.addEventListener('ipc-message', (e) => {
            if (e.channel === 'OPEN_CREATOR_TAB') {
                const payload = e.args?.[0] || {};
                this.addTabWithCookies(payload.url, payload.cookies || [], payload.platform || 'browser', payload.storageState, payload.accountId);
            }
        });

        // 核心：实时同步 URL 和标题 (修复百度/Google Mismatch)
        const updateInfo = () => {
            tabData.url = this.getWebviewUrl(webview, tabData.url);
            tabData.title = this.getWebviewTitle(webview, tabData.title);
            if (id === this.activeId) {
                this.urlBar.value = tabData.url;
                if (this.popup.style.display === 'block' && this.popup.dataset.tabId === id) {
                    this.syncPopupInfo(tabData);
                }
            }
        };

        webview.addEventListener('did-finish-load', updateInfo);
        webview.addEventListener('did-finish-load', () => {
            this.clearInternalRetry(id);
        });
        webview.addEventListener('did-navigate', updateInfo);
        webview.addEventListener('did-navigate-in-page', updateInfo);
        webview.addEventListener('did-fail-load', (event) => {
            if (event.errorCode === -3) {
                return;
            }

            console.warn('[Navigation] Webview failed to load:', {
                id,
                errorCode: event.errorCode,
                errorDescription: event.errorDescription,
                url: event.validatedURL || tabData.url,
            });
            tabData.title = '等待服务启动中...';
            this.scheduleManagedTabRetry(tabData, event.validatedURL || tabData.url);
        });
        webview.addEventListener('page-title-updated', (e) => {
            tabData.title = e.title;
            if (id === this.activeId && this.popup.style.display === 'block') {
                document.getElementById('p-title').textContent = e.title;
            }
        });

        this.switchTab(id);
        return id;
    }

    async resolveHermesDashboardUrl() {
        const fallbackUrl = 'http://127.0.0.1:9119';

        try {
            if (window.electronAPI?.supervisor?.getStatus) {
                const status = await window.electronAPI.supervisor.getStatus();
                const supervisorCandidate = String(
                    status?.hermes_dashboard?.dashboard_url
                    || status?.hermes_dashboard?.url
                    || ''
                ).trim();
                if (supervisorCandidate) {
                    return supervisorCandidate;
                }
            }

            let backendBase = 'http://127.0.0.1:7000';
            if (window.electronAPI?.app?.getInfo) {
                const info = await window.electronAPI.app.getInfo();
                backendBase = String(info?.backendUrl || backendBase).replace(/\/+$/, '');
            }

            const response = await fetch(`${backendBase}/api/v1/agent/config/hermes/runtime`);
            const payload = await response.json().catch(() => ({}));
            const candidate = String(payload?.data?.dashboard_url || '').trim();
            return candidate || fallbackUrl;
        } catch (error) {
            console.warn('[Shell] Failed to resolve Hermes dashboard URL, using fallback:', error);
            return fallbackUrl;
        }
    }

    async openHermesDashboard() {
        const url = await this.resolveHermesDashboardUrl();
        const existing = this.tabs.find((tab) => tab.type === 'hermes');

        if (existing) {
            const currentUrl = this.getWebviewUrl(existing.webview, existing.url);
            if (currentUrl !== url) {
                existing.url = url;
                this.loadWebviewUrl(existing.webview, url);
            }
            this.switchTab(existing.id);
            return;
        }

        this.addTab(url, 'hermes', false, {
            initialUrl: url,
            partition: 'persist:hermes-dashboard'
        });
    }

    syncUtilityButtons() {
        if (!this.hermesButton) return;
        const active = this.activeTab();
        this.hermesButton.classList.toggle('active', active?.type === 'hermes');
    }

    switchTab(id) {
        this.tabs.forEach(t => {
            t.webview.classList.remove('active');
            t.tabItem.classList.remove('active');
        });

        const active = this.tabs.find(t => t.id === id);
        if (active) {
            active.webview.classList.add('active');
            active.tabItem.classList.add('active');
            this.urlBar.value = this.getWebviewUrl(active.webview, active.url);
            this.activeId = id;
        }

        this.syncUtilityButtons();
    }

    removeTab(id) {
        const index = this.tabs.findIndex(t => t.id === id);
        if (index === -1) return;
        const tab = this.tabs[index];
        if (tab.pinned) return;

        tab.webview.remove();
        tab.tabItem.remove();
        this.clearInternalRetry(id);
        this.tabs.splice(index, 1);

        if (this.activeId === id && this.tabs.length > 0) {
            this.switchTab(this.tabs[this.tabs.length - 1].id);
        }

        this.syncUtilityButtons();
    }

    activeTab() {
        return this.tabs.find(t => t.id === this.activeId);
    }

    showPopup(id) {
        const tab = this.tabs.find(t => t.id === id);
        if (!tab) return;

        const rect = tab.tabItem.getBoundingClientRect();
        this.popup.style.top = `${rect.top}px`;
        this.popup.style.display = 'block';
        this.popup.dataset.tabId = id;

        this.syncPopupInfo(tab);

        // 强制重置编辑态为展示态
        this.pUrlDisplay.style.display = 'block';
        this.pUrlInput.style.display = 'none';
    }

    syncPopupInfo(tab) {
        document.getElementById('p-title').textContent = tab.title || (tab.pinned ? 'SynapseAutomation' : '无标题会话');
        const currentUrl = this.getWebviewUrl(tab.webview, tab.url);
        this.pUrlDisplay.textContent = currentUrl;
        this.pUrlInput.value = currentUrl;
    }

    hidePopup() {
        this.popup.style.display = 'none';
    }
}

// ========== 设置面板功能 ==========

let API_BASE = 'http://127.0.0.1:7000/api/v1/system';

async function hydrateSystemApiBase() {
    if (!window.electronAPI?.app?.getInfo) {
        return API_BASE;
    }

    try {
        const info = await window.electronAPI.app.getInfo();
        const candidate = String(info?.systemApiBaseUrl || '').trim();
        if (candidate) {
            API_BASE = candidate.replace(/\/+$/, '');
        }
    } catch (error) {
        console.warn('[Shell] Failed to hydrate system API base:', error);
    }

    return API_BASE;
}

void hydrateSystemApiBase();

function toggleSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    const overlay = document.getElementById('settings-overlay');

    if (panel.classList.contains('open')) {
        closeSettingsPanel();
    } else {
        panel.classList.add('open');
        overlay.classList.add('open');
    }
}

function closeSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    const overlay = document.getElementById('settings-overlay');
    panel.classList.remove('open');
    overlay.classList.remove('open');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        border-radius: 8px;
        z-index: 10000;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        border: 1px solid ${type === 'error' ? '#EF5350' : '#66BB6A'};
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

async function restartAllServices() {
    try {
        const response = await fetch(`${API_BASE}/supervisor/restart`, { method: 'POST' });
        if (response.ok) {
            showToast('✅ 所有服务已重启');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '重启失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function restartBackendService() {
    try {
        const response = await fetch(`${API_BASE}/supervisor/restart/backend`, { method: 'POST' });
        if (response.ok) {
            showToast('✅ 后端服务已重启');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '重启失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function stopAllServices() {
    if (!confirm('确认停止所有服务？')) return;

    try {
        const response = await fetch(`${API_BASE}/supervisor/stop`, { method: 'POST' });
        if (response.ok) {
            showToast('⏹ 所有服务已停止');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '停止失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function clearMaterialsData() {
    if (!confirm('确认清除所有素材数据？此操作不可恢复！')) return;

    try {
        const response = await fetch(`${API_BASE}/clear-materials`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backup: false })
        });

        if (response.ok) {
            showToast('✅ 素材数据已清除');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '清除失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function clearAccountsData() {
    if (!confirm('确认清除所有账号和 Cookies？此操作不可恢复！')) return;

    try {
        const response = await fetch(`${API_BASE}/clear-accounts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backup: false })
        });

        if (response.ok) {
            showToast('✅ 账号数据已清除');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '清除失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function clearAllCache() {
    if (!confirm('确认清除所有缓存？')) return;

    try {
        const response = await fetch(`${API_BASE}/clear-cache`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backup: false })
        });

        if (response.ok) {
            showToast('✅ 缓存已清除');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '清除失败');
        }
    } catch (error) {
        showToast('❌ ' + error.message, 'error');
    }
}

async function clearVideoData() {
    if (!confirm('确认清除所有视频数据？此操作不可恢复。')) return;

    try {
        const response = await fetch(`${API_BASE}/clear-video-data`, { method: 'POST' });
        if (response.ok) {
            showToast('视频数据已清理');
        } else {
            const data = await response.json();
            throw new Error(data.detail || '清理失败');
        }
    } catch (error) {
        showToast('清理失败: ' + error.message, 'error');
    }
}

async function runSystemCheck() {
    try {
        const response = await fetch(`${API_BASE}/self-check`, { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            showToast('✅ 系统自检通过');
        } else if (data.status === 'warning') {
            showToast('⚠️ 发现问题: ' + data.issues.join(', '), 'error');
        }
    } catch (error) {
        showToast('❌ 自检失败: ' + error.message, 'error');
    }
}

async function exportSystemLogs() {
    try {
        const response = await fetch(`${API_BASE}/export-logs`, { method: 'POST' });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `synapse-logs-${new Date().toISOString().split('T')[0]}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showToast('✅ 日志已导出');
        } else {
            throw new Error('导出失败');
        }
    } catch (error) {
        showToast('❌ 导出失败: ' + error.message, 'error');
    }
}

async function forceKillAllProcesses() {
    if (!confirm('确认强制终止所有进程？')) return;

    try {
        const response = await fetch(`${API_BASE}/supervisor/stop`, { method: 'POST' });

        if (response.ok) {
            showToast('✅ 进程已强制终止');
        } else {
            throw new Error('终止失败');
        }
    } catch (error) {
        showToast('❌ 终止失败: ' + error.message, 'error');
    }
}

restartAllServices = async function () {
    try {
        if (window.electronAPI?.system?.restartAll) {
            const result = await window.electronAPI.system.restartAll();
            if (!result?.success) {
                throw new Error(result?.error || '服务重启失败');
            }
        } else {
            const response = await fetch(`${API_BASE}/supervisor/restart`, { method: 'POST' });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || '服务重启失败');
            }
        }

        showToast('所有服务已重启');
    } catch (error) {
        showToast(`重启失败: ${error.message}`, 'error');
    }
};

stopAllServices = async function () {
    if (!confirm('确认停止所有服务？')) return;

    try {
        if (window.electronAPI?.system?.stopAll) {
            const result = await window.electronAPI.system.stopAll();
            if (!result?.success) {
                throw new Error(result?.error || '停止服务失败');
            }
        } else {
            const response = await fetch(`${API_BASE}/supervisor/stop`, { method: 'POST' });
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || '停止服务失败');
            }
        }

        showToast('所有服务已停止');
    } catch (error) {
        showToast(`停止失败: ${error.message}`, 'error');
    }
};

function bootstrapShell() {
    if (window.__tabManagerInstance) {
        return window.__tabManagerInstance;
    }

    const manager = new TabManager();
    window.__tabManagerInstance = manager;
    return manager;
}

function scheduleHomeHydration(delayMs = 0) {
    const manager = bootstrapShell();
    if (!manager?.hydrateHomeTab) {
        return;
    }

    setTimeout(() => {
        manager.hydrateHomeTab().catch((error) => {
            console.warn('[Shell] Delayed home hydration failed:', error);
        });
    }, delayMs);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        bootstrapShell();
        scheduleHomeHydration(1200);
        scheduleHomeHydration(4000);
    }, { once: true });
} else {
    bootstrapShell();
    scheduleHomeHydration(1200);
    scheduleHomeHydration(4000);
}

window.addEventListener('load', () => {
    scheduleHomeHydration(0);
});
