(function () {
    "use strict";

    // =========================================================================
    // Instagram Rapor 3.1 - Güvenli Web Veri Çekici (%100 Read-Only)
    // - Hiçbir POST / takipten çıkma / takip etme isteği göndermez.
    // - Yalnızca kendi tarayıcı oturumunuzla liste okuma / kaydırma yapar.
    // - İnsan hızında rastgele bekleme (jitter) ve mola koruması içerir.
    // =========================================================================

    const PANEL_ID = "insta-check-safe-panel";
    const EXISTING = document.getElementById(PANEL_ID);
    if (EXISTING) {
        EXISTING.remove();
    }

    if (!location.hostname.includes("instagram.com")) {
        alert("Lütfen bu kodu https://www.instagram.com/ açıkken çalıştırın.");
        return;
    }

    const CONFIG = {
        API_MIN_DELAY_MS: 2200,
        API_MAX_DELAY_MS: 4500,
        DOM_MIN_DELAY_MS: 1800,
        DOM_MAX_DELAY_MS: 3500,
        BREAK_EVERY_STEPS: 5,
        BREAK_MIN_MS: 6000,
        BREAK_MAX_MS: 9000,
        MAX_STEPS_PER_RUN: 100,
        PAGE_SIZE: 24,
        IG_APP_ID: "936619743392459"
    };

    const RESERVED_PATHS = new Set([
        "explore", "reels", "reel", "direct", "stories", "accounts",
        "p", "tv", "tags", "locations", "about", "legal", "privacy",
        "terms", "directory", "developer", "challenge", "oauth", "nametag",
        "your_activity", "settings", "archive"
    ]);

    const state = {
        running: false,
        abortRequested: false,
        username: detectUsername(),
        followers: new Map(), // username -> { username, url, date }
        following: new Map(), // username -> { username, url, date }
        expectedFollowers: null,
        expectedFollowing: null
    };

    function getCookie(name) {
        const prefix = `${name}=`;
        const parts = document.cookie.split(";");
        for (const rawPart of parts) {
            const part = rawPart.trim();
            if (part.startsWith(prefix)) {
                return decodeURIComponent(part.slice(prefix.length));
            }
        }
        return null;
    }

    function detectUsername() {
        // 1. Profil sayfasındaysak URL yolundan algıla
        const pathMatch = location.pathname.match(/^\/([A-Za-z0-9._]+)\/?$/);
        if (pathMatch && !RESERVED_PATHS.has(pathMatch[1].toLowerCase())) {
            return pathMatch[1];
        }
        // 2. Sol menüdeki profil bağlantısından algıla
        const navLinks = document.querySelectorAll('a[href^="/"]');
        for (const link of navLinks) {
            const href = link.getAttribute("href") || "";
            const m = href.match(/^\/([A-Za-z0-9._]+)\/$/);
            if (!m) continue;
            const candidate = m[1];
            if (RESERVED_PATHS.has(candidate.toLowerCase())) continue;
            const img = link.querySelector("img[alt]");
            if (img && img.alt && !img.alt.toLowerCase().includes("instagram")) {
                return candidate;
            }
        }
        return "instagram";
    }

    function formatNowDate(includeTime = false) {
        const d = new Date();
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const yyyy = d.getFullYear();
        if (!includeTime) {
            return `${dd}.${mm}.${yyyy}`;
        }
        const hh = String(d.getHours()).padStart(2, "0");
        const min = String(d.getMinutes()).padStart(2, "0");
        return `${dd}.${mm}.${yyyy} ${hh}:${min}`;
    }

    function formatFileDate() {
        const d = new Date();
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const yyyy = d.getFullYear();
        return `${yyyy}-${mm}-${dd}`;
    }

    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function sleepWithJitter(minMs, maxMs, statusPrefix) {
        const waitMs = randomInt(minMs, maxMs);
        const waitSec = (waitMs / 1000).toFixed(1);
        if (statusPrefix) {
            setStatus(`${statusPrefix} (Güvenli bekleme: ${waitSec} sn)...`);
        }
        // İptal isteğine hızlı tepki vermek için 250ms dilimlerle bekle
        let elapsed = 0;
        while (elapsed < waitMs) {
            if (state.abortRequested) return waitMs;
            const chunk = Math.min(250, waitMs - elapsed);
            await sleep(chunk);
            elapsed += chunk;
        }
        return waitMs;
    }

    function normalizeEntry(username) {
        const clean = String(username || "").trim().replace(/^@/, "");
        return {
            username: clean,
            url: `https://www.instagram.com/${clean}`,
            date: `${formatNowDate(false)} (Web)`
        };
    }

    // -------------------------------------------------------------------------
    // UI Paneli Oluşturma
    // -------------------------------------------------------------------------
    const panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.style.cssText = [
        "position: fixed",
        "right: 18px",
        "bottom: 18px",
        "width: 350px",
        "max-width: calc(100vw - 36px)",
        "background: #181c22",
        "color: #eef2f7",
        "border: 1px solid #303846",
        "border-radius: 12px",
        "box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45)",
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-size: 13px",
        "z-index: 999999",
        "padding: 14px",
        "line-height: 1.45"
    ].join(";");

    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-weight:700;font-size:14px;color:#7ecfff;">
                🛡️ Insta Rapor 3.1 (Güvenli Mod)
            </div>
            <button id="ic-close-btn" title="Paneli Kapat"
                style="background:transparent;border:none;color:#9aa5b1;font-size:16px;cursor:pointer;padding:0 4px;">✕</button>
        </div>
        <div style="font-size:11px;color:#9aa5b1;margin-bottom:10px;">
            %100 Sadece Okuma • Rastgele İnsani Gecikme (2.2–4.5 sn)
        </div>
        <div style="display:flex;gap:8px;margin-bottom:10px;background:#23272f;padding:8px;border-radius:8px;font-size:12px;">
            <div style="flex:1;">Takipçi: <strong id="ic-followers-count" style="color:#00d2a0;">0</strong></div>
            <div style="flex:1;">Takip Edilen: <strong id="ic-following-count" style="color:#7ecfff;">0</strong></div>
        </div>
        <div style="background:#23272f;border-radius:6px;height:8px;overflow:hidden;margin-bottom:8px;">
            <div id="ic-progress-bar" style="height:100%;width:0%;background:#3a5ca8;transition:width 0.25s ease;"></div>
        </div>
        <div id="ic-status-text" style="font-size:12px;color:#d6deeb;min-height:34px;margin-bottom:10px;">
            Hazır. Başlamak için aşağıdaki modlardan birini seçin.
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;">
            <button id="ic-auto-btn"
                style="background:#3a5ca8;color:#fff;border:none;border-radius:8px;padding:8px 10px;font-weight:600;cursor:pointer;">
                ⚡ Otomatik Güvenli Okuyucu (Önerilen)
            </button>
            <div style="font-size:11px;color:#9aa5b1;margin-top:4px;">
                Yedek Mod (Profilde pencereyi açıp kullanın):
            </div>
            <div style="display:flex;gap:6px;">
                <button id="ic-dom-followers-btn"
                    style="flex:1;background:#2a313c;color:#e0e6f0;border:1px solid #3c4554;border-radius:7px;padding:6px 8px;font-size:11px;cursor:pointer;">
                    📜 Pencereyi Kaydır (Takipçiler)
                </button>
                <button id="ic-dom-following-btn"
                    style="flex:1;background:#2a313c;color:#e0e6f0;border:1px solid #3c4554;border-radius:7px;padding:6px 8px;font-size:11px;cursor:pointer;">
                    📜 Pencereyi Kaydır (Takip Edilen)
                </button>
            </div>
            <div style="display:flex;gap:6px;margin-top:4px;">
                <button id="ic-export-btn"
                    style="flex:1;background:#009975;color:#fff;border:none;border-radius:8px;padding:8px 10px;font-weight:600;cursor:pointer;">
                    💾 JSON İndir & Panoya Kopyala
                </button>
                <button id="ic-stop-btn" disabled
                    style="background:#8f3232;color:#fff;border:none;border-radius:8px;padding:8px 12px;font-weight:600;cursor:not-allowed;opacity:0.5;">
                    Durdur
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(panel);

    const els = {
        closeBtn: document.getElementById("ic-close-btn"),
        followersCount: document.getElementById("ic-followers-count"),
        followingCount: document.getElementById("ic-following-count"),
        progressBar: document.getElementById("ic-progress-bar"),
        statusText: document.getElementById("ic-status-text"),
        autoBtn: document.getElementById("ic-auto-btn"),
        domFollowersBtn: document.getElementById("ic-dom-followers-btn"),
        domFollowingBtn: document.getElementById("ic-dom-following-btn"),
        exportBtn: document.getElementById("ic-export-btn"),
        stopBtn: document.getElementById("ic-stop-btn")
    };

    function setStatus(msg, color = "#d6deeb") {
        els.statusText.textContent = msg;
        els.statusText.style.color = color;
    }

    function updateCounters(percent = null) {
        els.followersCount.textContent = String(state.followers.size);
        els.followingCount.textContent = String(state.following.size);
        if (typeof percent === "number") {
            const clamped = Math.max(0, Math.min(100, Math.round(percent)));
            els.progressBar.style.width = `${clamped}%`;
        }
    }

    function setRunning(isRunning) {
        state.running = isRunning;
        state.abortRequested = false;
        els.autoBtn.disabled = isRunning;
        els.domFollowersBtn.disabled = isRunning;
        els.domFollowingBtn.disabled = isRunning;
        els.autoBtn.style.opacity = isRunning ? "0.55" : "1";
        els.domFollowersBtn.style.opacity = isRunning ? "0.55" : "1";
        els.domFollowingBtn.style.opacity = isRunning ? "0.55" : "1";
        els.stopBtn.disabled = !isRunning;
        els.stopBtn.style.opacity = isRunning ? "1" : "0.5";
        els.stopBtn.style.cursor = isRunning ? "pointer" : "not-allowed";
    }

    function buildPayload() {
        return {
            source: "insta_check_web_collector",
            version: "3.1",
            username: state.username || "instagram",
            exported_at: formatNowDate(true),
            followers: Array.from(state.followers.values()),
            following: Array.from(state.following.values())
        };
    }

    async function exportAndCopy(autoTriggered = false) {
        if (state.followers.size === 0 && state.following.size === 0) {
            if (!autoTriggered) {
                setStatus("Henüz toplanmış veri yok. Önce tarama başlatın.", "#ffbe76");
            }
            return;
        }

        const payload = buildPayload();
        const jsonText = JSON.stringify(payload, null, 2);

        let copied = false;
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(jsonText);
                copied = true;
            }
        } catch (err) {
            copied = false;
        }

        // Fallback kopyalama (sayfa odakta değilse)
        if (!copied) {
            try {
                const ta = document.createElement("textarea");
                ta.value = jsonText;
                ta.style.position = "fixed";
                ta.style.left = "-9999px";
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                copied = document.execCommand("copy");
                ta.remove();
            } catch (e) {
                copied = false;
            }
        }

        // JSON dosyasını indir
        try {
            const blob = new Blob([jsonText], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `instagram_web_rapor_${formatFileDate()}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 5000);
        } catch (err) {
            console.warn("Dosya indirme hatası:", err);
        }

        const copyNote = copied
            ? "Panoya kopyalandı ve JSON dosyası indirildi!"
            : "JSON dosyası indirildi (Pano için sayfaya tıklayıp butona tekrar basın).";
        setStatus(
            `✅ Tamamlandı (${state.followers.size} takipçi, ${state.following.size} takip edilen). ${copyNote}`,
            "#00d2a0"
        );
    }

    // -------------------------------------------------------------------------
    // Mod 1: Otomatik Güvenli Okuyucu (Sadece GET)
    // -------------------------------------------------------------------------
    async function fetchFriendshipList(userId, endpointType, targetMap) {
        const label = endpointType === "followers" ? "Takipçiler" : "Takip edilenler";
        let nextMaxId = null;
        let step = 0;

        while (!state.abortRequested && step < CONFIG.MAX_STEPS_PER_RUN) {
            step += 1;
            const params = new URLSearchParams({ count: String(CONFIG.PAGE_SIZE) });
            if (endpointType === "followers") {
                params.set("search_surface", "follow_list_page");
            }
            if (nextMaxId) {
                params.set("max_id", String(nextMaxId));
            }

            const url = `https://www.instagram.com/api/v1/friendships/${encodeURIComponent(userId)}/${endpointType}/?${params.toString()}`;
            const headers = {
                "x-ig-app-id": CONFIG.IG_APP_ID,
                "x-requested-with": "XMLHttpRequest"
            };
            const csrf = getCookie("csrftoken");
            if (csrf) {
                headers["x-csrftoken"] = csrf;
            }

            const response = await fetch(url, {
                method: "GET",
                credentials: "include",
                headers
            });

            if (response.status === 429) {
                throw new Error("Instagram hız sınırına (HTTP 429) yaklaşıldı. Güvenlik için işlem hemen durduruldu.");
            }
            if (response.status === 401 || response.status === 403) {
                throw new Error("Oturum doğrulaması gerekli (HTTP " + response.status + "). Lütfen Yedek Mod (Pencere Kaydırıcı) kullanın.");
            }
            if (!response.ok) {
                throw new Error(`İstek başarısız oldu (HTTP ${response.status}). Yedek Modu deneyebilirsiniz.`);
            }

            const data = await response.json();
            const users = Array.isArray(data.users) ? data.users : [];
            for (const u of users) {
                if (u && u.username) {
                    const entry = normalizeEntry(u.username);
                    targetMap.set(entry.username, entry);
                }
            }

            const expected = endpointType === "followers" ? state.expectedFollowers : state.expectedFollowing;
            let pct = null;
            if (expected && expected > 0) {
                const base = endpointType === "followers" ? 0 : 50;
                pct = base + Math.min(50, (targetMap.size / expected) * 50);
            } else {
                pct = endpointType === "followers" ? Math.min(45, step * 5) : 50 + Math.min(45, step * 5);
            }
            updateCounters(pct);

            nextMaxId = data.next_max_id || null;
            if (!nextMaxId || users.length === 0) {
                break;
            }

            const countText = expected ? `${targetMap.size}/${expected}` : `${targetMap.size}`;
            if (step % CONFIG.BREAK_EVERY_STEPS === 0) {
                await sleepWithJitter(
                    CONFIG.BREAK_MIN_MS,
                    CONFIG.BREAK_MAX_MS,
                    `${label} okunuyor: ${countText} • Kısa güvenlik molası`
                );
            } else {
                await sleepWithJitter(
                    CONFIG.API_MIN_DELAY_MS,
                    CONFIG.API_MAX_DELAY_MS,
                    `${label} okunuyor: ${countText}`
                );
            }
        }
    }

    async function runAutoReader() {
        const userId = getCookie("ds_user_id");
        if (!userId) {
            setStatus("Oturum çerezi (ds_user_id) bulunamadı. Instagram'a giriş yaptığınızdan emin olun.", "#ff7675");
            return;
        }

        setRunning(true);
        state.followers.clear();
        state.following.clear();
        updateCounters(2);

        try {
            // İsteğe bağlı güvenli kullanıcı adı / sayaç tespiti (GET)
            try {
                setStatus("Hesap bilgileri okunuyor...");
                const infoRes = await fetch(`https://www.instagram.com/api/v1/users/${encodeURIComponent(userId)}/info/`, {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        "x-ig-app-id": CONFIG.IG_APP_ID,
                        "x-requested-with": "XMLHttpRequest"
                    }
                });
                if (infoRes.ok) {
                    const infoData = await infoRes.json();
                    if (infoData && infoData.user) {
                        if (infoData.user.username) {
                            state.username = infoData.user.username;
                        }
                        state.expectedFollowers = infoData.user.follower_count || null;
                        state.expectedFollowing = infoData.user.following_count || null;
                    }
                }
            } catch (_) {
                // Kritik değil, devam et
            }

            if (!state.abortRequested) {
                await sleepWithJitter(1200, 2200, "Takipçiler başlatılıyor");
                await fetchFriendshipList(userId, "followers", state.followers);
            }

            if (!state.abortRequested) {
                await sleepWithJitter(CONFIG.BREAK_MIN_MS, CONFIG.BREAK_MAX_MS, "Takip edilenlere geçmeden güvenlik molası");
                await fetchFriendshipList(userId, "following", state.following);
            }

            if (state.abortRequested) {
                setStatus(`İşlem durduruldu (${state.followers.size} takipçi, ${state.following.size} takip edilen).`, "#ffbe76");
            } else {
                updateCounters(100);
                await exportAndCopy(true);
            }
        } catch (err) {
            setStatus(`⚠️ ${err.message}`, "#ff7675");
        } finally {
            setRunning(false);
        }
    }

    // -------------------------------------------------------------------------
    // Mod 2: DOM Pencere Kaydırıcı (API Değişikliklerine %100 Dayanıklı Yedek Mod)
    // -------------------------------------------------------------------------
    function findScrollableDialogBox() {
        const dialog = document.querySelector('div[role="dialog"]');
        if (!dialog) return null;

        const candidates = dialog.querySelectorAll("div");
        let best = null;
        let maxHeight = 0;

        for (const el of candidates) {
            const style = window.getComputedStyle(el);
            const overflowY = style.overflowY;
            if ((overflowY === "auto" || overflowY === "scroll") && el.scrollHeight > el.clientHeight + 20) {
                if (el.scrollHeight > maxHeight) {
                    maxHeight = el.scrollHeight;
                    best = el;
                }
            }
        }
        return best || dialog;
    }

    function collectUsernamesFromDialog(dialog, targetMap) {
        const links = dialog.querySelectorAll('a[href^="/"]');
        let added = 0;
        for (const link of links) {
            const href = link.getAttribute("href") || "";
            const match = href.match(/^\/([A-Za-z0-9._]+)\/?$/);
            if (!match) continue;
            const username = match[1];
            if (RESERVED_PATHS.has(username.toLowerCase())) continue;
            if (username === state.username && link.closest("header")) continue;
            if (!targetMap.has(username)) {
                targetMap.set(username, normalizeEntry(username));
                added += 1;
            }
        }
        return added;
    }

    async function runDomScroller(modeType) {
        const dialog = document.querySelector('div[role="dialog"]');
        if (!dialog) {
            setStatus("⚠️ Önce profilinizden Takipçiler veya Takip Edilenler penceresini açın.", "#ffbe76");
            return;
        }

        const label = modeType === "followers" ? "Takipçiler" : "Takip Edilenler";
        const targetMap = modeType === "followers" ? state.followers : state.following;
        const scrollBox = findScrollableDialogBox();

        setRunning(true);
        targetMap.clear();
        updateCounters(5);

        let stagnantRounds = 0;
        let step = 0;

        try {
            while (!state.abortRequested && step < CONFIG.MAX_STEPS_PER_RUN) {
                step += 1;
                const prevCount = targetMap.size;
                collectUsernamesFromDialog(dialog, targetMap);
                const newCount = targetMap.size;

                const prevTop = scrollBox.scrollTop;
                const jump = Math.max(320, Math.floor(scrollBox.clientHeight * 0.8));
                scrollBox.scrollBy({ top: jump, behavior: "smooth" });
                await sleep(550);
                collectUsernamesFromDialog(dialog, targetMap);

                const moved = Math.abs(scrollBox.scrollTop - prevTop) > 4;
                if (targetMap.size === prevCount && !moved && newCount === prevCount) {
                    stagnantRounds += 1;
                } else {
                    stagnantRounds = 0;
                }

                updateCounters(Math.min(95, 10 + step * 3));

                if (stagnantRounds >= 3) {
                    break;
                }

                if (step % CONFIG.BREAK_EVERY_STEPS === 0) {
                    await sleepWithJitter(
                        CONFIG.BREAK_MIN_MS,
                        CONFIG.BREAK_MAX_MS,
                        `${label} kaydırılıyor: ${targetMap.size} kişi • Kısa mola`
                    );
                } else {
                    await sleepWithJitter(
                        CONFIG.DOM_MIN_DELAY_MS,
                        CONFIG.DOM_MAX_DELAY_MS,
                        `${label} kaydırılıyor: ${targetMap.size} kişi`
                    );
                }
            }

            collectUsernamesFromDialog(dialog, targetMap);
            updateCounters(100);

            if (state.abortRequested) {
                setStatus(`Kaydırma durduruldu (${label}: ${targetMap.size} kişi).`, "#ffbe76");
            } else {
                setStatus(
                    `✅ ${label} tamamlandı (${targetMap.size} kişi). İsterseniz diğer pencereyi açıp tarayın veya "JSON İndir & Panoya Kopyala"ya basın.`,
                    "#00d2a0"
                );
            }
        } catch (err) {
            setStatus(`⚠️ Kaydırma hatası: ${err.message}`, "#ff7675");
        } finally {
            setRunning(false);
        }
    }

    // -------------------------------------------------------------------------
    // Buton Olayları
    // -------------------------------------------------------------------------
    els.closeBtn.addEventListener("click", () => {
        state.abortRequested = true;
        panel.remove();
    });

    els.stopBtn.addEventListener("click", () => {
        state.abortRequested = true;
        setStatus("Güvenli durdurma isteniyor...", "#ffbe76");
    });

    els.autoBtn.addEventListener("click", () => {
        if (!state.running) runAutoReader();
    });

    els.domFollowersBtn.addEventListener("click", () => {
        if (!state.running) runDomScroller("followers");
    });

    els.domFollowingBtn.addEventListener("click", () => {
        if (!state.running) runDomScroller("following");
    });

    els.exportBtn.addEventListener("click", () => {
        exportAndCopy(false);
    });
})();
