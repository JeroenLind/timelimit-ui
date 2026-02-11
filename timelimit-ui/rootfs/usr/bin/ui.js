/**
 * ui.js - Gedeelde interface functies
 */

function addLog(m, isError = false) { 
    const log = document.getElementById('log-area');
    if (!log) return;

    // Voorkom een oneindig lange lijst: verwijder oudste logs boven de 50 regels
    if (log.children.length > 50) {
        log.removeChild(log.firstChild);
    }

    const div = document.createElement('div');
    div.style.color = isError ? '#ff4444' : '#00ff00';
    div.innerHTML = `[${new Date().toLocaleTimeString()}] ${m}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

const HA_STORAGE_ENDPOINT = 'ha-storage';
const HA_STORAGE_KEYS = [
    'timelimit_token',
    'timelimit_parentPasswordHash',
    'timelimit_account_history',
    'timelimit_last_email',
    'selected_timelimit_server',
    'timelimit_debugMode',
    'timelimit_nextSyncSequenceNumber',
    'timelimit_serverApiLevel'
];

let haShadowTimer = null;

function buildHaStorageSnapshot() {
    const data = {};
    HA_STORAGE_KEYS.forEach((key) => {
        const value = localStorage.getItem(key);
        data[key] = value === null ? null : value;
    });
    return {
        version: 1,
        updatedAt: Date.now(),
        data
    };
}

async function pushHaStorageSnapshot(reason) {
    try {
        const payload = buildHaStorageSnapshot();
        payload.reason = reason || 'unknown';
        const res = await fetch(HA_STORAGE_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res && res.ok && typeof loadHaStorageStatus === 'function') {
            loadHaStorageStatus();
        }
    } catch (e) {
        // Shadow copy only; ignore failures.
    }
}

function scheduleHaStorageShadowSync(reason) {
    if (haShadowTimer) {
        clearTimeout(haShadowTimer);
    }
    haShadowTimer = setTimeout(() => {
        haShadowTimer = null;
        pushHaStorageSnapshot(reason);
    }, 300);
}

window.scheduleHaStorageShadowSync = scheduleHaStorageShadowSync;

function formatTokenShort(token) {
    if (!token) return '';
    if (token.length <= 10) return token;
    return `${token.substring(0, 6)}...${token.substring(token.length - 4)}`;
}

function formatTimestamp(ts) {
    if (!ts || !Number.isFinite(Number(ts))) return '-';
    return new Date(Number(ts)).toLocaleString();
}

function renderHaStorageDetails(storage) {
    const statusEl = document.getElementById('ha-storage-status');
    const detailsEl = document.getElementById('ha-storage-details');
    const historyBody = document.getElementById('ha-storage-history-body');

    if (!statusEl || !detailsEl || !historyBody) return;

    window.haStorageCache = storage || null;

    if (!storage || !storage.data) {
        statusEl.textContent = 'Geen HA storage data gevonden.';
        detailsEl.textContent = '';
        historyBody.innerHTML = '<tr><td colspan="6" style="padding: 8px; color: #666;">Geen geschiedenis</td></tr>';
        return;
    }

    const data = storage.data;
    const token = data.timelimit_token || '';
    const lastEmail = data.timelimit_last_email || '';
    const selectedServer = data.selected_timelimit_server || '';
    const debugMode = data.timelimit_debugMode === '1' ? 'On' : 'Off';
    const sequence = data.timelimit_nextSyncSequenceNumber || '0';
    const apiLevel = data.timelimit_serverApiLevel || '-';

    statusEl.textContent = `Laatst bijgewerkt: ${formatTimestamp(storage.updatedAt || storage.serverTimestamp)}`;

    const parentHashPresent = data.timelimit_parentPasswordHash ? 'ja' : 'nee';
    const historyRaw = data.timelimit_account_history || '[]';

    detailsEl.innerHTML = `
        <div style="margin-bottom:6px;">Token: <span style="color:#fff; font-family: monospace;">${formatTokenShort(token) || '-'}</span></div>
        <div style="margin-bottom:6px;">Parent hash aanwezig: <span style="color:#fff;">${parentHashPresent}</span></div>
        <div style="margin-bottom:6px;">Laatste e-mail: <span style="color:#fff;">${lastEmail || '-'}</span></div>
        <div style="margin-bottom:6px;">Server: <span style="color:#fff;">${selectedServer || '-'}</span></div>
        <div style="margin-bottom:6px;">Debug: <span style="color:#fff;">${debugMode}</span></div>
        <div style="margin-bottom:6px;">Sequence: <span style="color:#fff; font-family: monospace;">${sequence}</span></div>
        <div>Server API Level: <span style="color:#fff; font-family: monospace;">${apiLevel}</span></div>
    `;

    let history = [];
    try {
        const parsed = JSON.parse(historyRaw);
        if (Array.isArray(parsed)) history = parsed;
    } catch (e) {
        history = [];
    }

    if (history.length === 0) {
        historyBody.innerHTML = '<tr><td colspan="6" style="padding: 8px; color: #666;">Geen geschiedenis</td></tr>';
        return;
    }

    historyBody.innerHTML = history.map((entry, index) => {
        const email = entry.email || '-';
        const server = entry.serverLabel || entry.serverUrl || '-';
        const seq = Number.isFinite(Number(entry.seq)) ? entry.seq : 0;
        const lastUsed = formatTimestamp(entry.lastUsedAt);
        const tokenShort = formatTokenShort(entry.token || '');
        return `
            <tr>
                <td style="padding: 6px;">${server}</td>
                <td style="padding: 6px;">${email}</td>
                <td style="padding: 6px; font-family: monospace;">${tokenShort}</td>
                <td style="padding: 6px;">${seq}</td>
                <td style="padding: 6px;">${lastUsed}</td>
                <td style="padding: 6px;"><button class="btn" style="padding:4px 8px; font-size:10px;" onclick="applyHaStorageHistory(${index})">Herstel</button></td>
            </tr>
        `;
    }).join('');
}

function applyHaStorageHistory(index) {
    const storage = window.haStorageCache;
    const historyRaw = storage && storage.data ? storage.data.timelimit_account_history : null;
    if (!historyRaw) return;

    let history = [];
    try {
        const parsed = JSON.parse(historyRaw);
        if (Array.isArray(parsed)) history = parsed;
    } catch (e) {
        history = [];
    }

    const entry = history[index];
    if (!entry) return;

    if (entry.token) {
        TOKEN = entry.token;
        localStorage.setItem('timelimit_token', TOKEN);
    }

    if (entry.email) {
        localStorage.setItem('timelimit_last_email', entry.email);
    }

    if (Number.isFinite(Number(entry.seq))) {
        setSequenceNumber(entry.seq);
    }

    if (entry.serverUrl) {
        localStorage.setItem('selected_timelimit_server', entry.serverUrl);
        if (typeof switchServer === 'function') {
            switchServer(entry.serverUrl);
            return;
        }
    }

    updateTokenDisplay();
    updateSequenceDisplay();
    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('ha-restore');
    }
    runSync();
}

async function loadHaStorageStatus() {
    try {
        const res = await fetch(HA_STORAGE_ENDPOINT, { method: 'GET' });
        if (!res.ok) throw new Error('status');
        const data = await res.json();
        renderHaStorageDetails(data);
    } catch (e) {
        const statusEl = document.getElementById('ha-storage-status');
        const detailsEl = document.getElementById('ha-storage-details');
        const historyBody = document.getElementById('ha-storage-history-body');
        if (statusEl) statusEl.textContent = 'Kon HA storage niet laden.';
        if (detailsEl) detailsEl.textContent = '';
        if (historyBody) {
            historyBody.innerHTML = '<tr><td colspan="5" style="padding: 8px; color: #666;">Geen geschiedenis</td></tr>';
        }
    }
}

window.loadHaStorageStatus = loadHaStorageStatus;
window.applyHaStorageHistory = applyHaStorageHistory;

function exportHaStorage() {
    fetch(HA_STORAGE_ENDPOINT, { method: 'GET' })
        .then((res) => {
            if (!res.ok) throw new Error('status');
            return res.json();
        })
        .then((data) => {
            const payload = JSON.stringify(data, null, 2);
            const blob = new Blob([payload], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            a.href = url;
            a.download = `timelimit-ha-storage-${ts}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        })
        .catch(() => {
            addLog('❌ Export mislukt. Controleer verbinding.', true);
        });
}

function applyHaStorageDataToLocal(storage) {
    if (!storage || !storage.data) return;
    const data = storage.data;

    HA_STORAGE_KEYS.forEach((key) => {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            const value = data[key];
            if (value === null || typeof value === 'undefined') {
                localStorage.removeItem(key);
            } else {
                localStorage.setItem(key, String(value));
            }
        }
    });

    if (data.timelimit_token) {
        TOKEN = data.timelimit_token;
    }

    updateTokenDisplay();
    updateSequenceDisplay();
}

function importHaStorageFromFile(event) {
    const input = event && event.target ? event.target : null;
    const file = input && input.files ? input.files[0] : null;
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const parsed = JSON.parse(String(reader.result || ''));
            if (!parsed || typeof parsed !== 'object') {
                throw new Error('invalid');
            }

            await fetch(HA_STORAGE_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(parsed)
            });

            applyHaStorageDataToLocal(parsed);
            if (typeof scheduleHaStorageShadowSync === 'function') {
                scheduleHaStorageShadowSync('import');
            }
            if (typeof loadHaStorageStatus === 'function') {
                loadHaStorageStatus();
            }
            addLog('✅ Import voltooid.', false);
        } catch (e) {
            addLog('❌ Import mislukt. Ongeldig bestand.', true);
        } finally {
            if (input) input.value = '';
        }
    };
    reader.readAsText(file);
}

window.exportHaStorage = exportHaStorage;
window.importHaStorageFromFile = importHaStorageFromFile;

const DEBUG_MODE_KEY = 'timelimit_debugMode';

function isDebugMode() {
    return localStorage.getItem(DEBUG_MODE_KEY) === '1';
}

function applyDebugMode(enabled) {
    document.body.classList.toggle('debug-mode', enabled);

    const debugOnlyElements = document.querySelectorAll('[data-debug-only="true"]');
    debugOnlyElements.forEach((el) => {
        el.style.display = enabled ? '' : 'none';
    });

    const toggle = document.getElementById('debug-toggle');
    if (toggle) toggle.checked = enabled;

    const label = document.getElementById('debug-toggle-label');
    if (label) label.textContent = enabled ? 'On' : 'Off';
}

function setDebugMode(enabled) {
    localStorage.setItem(DEBUG_MODE_KEY, enabled ? '1' : '0');
    scheduleHaStorageShadowSync('debug-mode');
    applyDebugMode(enabled);
}

function initDebugToggle() {
    const toggle = document.getElementById('debug-toggle');
    if (!toggle) return;

    toggle.addEventListener('change', () => {
        setDebugMode(toggle.checked);
    });

    applyDebugMode(isDebugMode());
}

function showStep(s) {
    const wizardUi = document.getElementById('wizard-ui');
    if (!wizardUi) return;

    wizardUi.style.display = s > 0 ? 'block' : 'none';
    const steps = document.querySelectorAll('.wizard-step');
    steps.forEach((el, idx) => el.style.display = (idx + 1 === s) ? 'block' : 'none');
}

function renderUsers(data) {
    const list = document.getElementById('user-list');
    if (!list) return;

    if (data && data.users && data.users.data && data.users.data.length > 0) {
        let html = "<ul style='list-style: none; padding: 0;'>";
        data.users.data.forEach(u => {
            const icon = u.type === 'parent' ? '🛡️' : '👤';
            html += `<li style='background: #151921; margin-bottom: 5px; padding: 10px; border-radius: 4px; border-left: 3px solid #03a9f4;'>
                        ${icon} <strong>${u.name}</strong> <span style='color: #888; font-size: 0.8em;'>(${u.type})</span>
                     </li>`;
        });
        html += "</ul>";
        list.innerHTML = html;
    } else {
        list.innerHTML = "<p style='color: #888;'>Geen gebruikers gevonden in deze familie.</p>";
    }
}

function copyInspectorToClipboard() {
    const inspector = document.getElementById('json-view');
    if (!inspector) return;

    const text = inspector.textContent || '';
    if (!text.trim()) {
        addLog('⚠️ Geen data om te kopieren.', true);
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(() => addLog('✅ Data Inspector gekopieerd naar klembord.'))
            .catch(() => addLog('❌ Kopieren mislukt. Probeer opnieuw.', true));
        return;
    }

    // Fallback for older browsers
    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        addLog('✅ Data Inspector gekopieerd naar klembord.');
    } catch (e) {
        addLog('❌ Kopieren mislukt. Probeer opnieuw.', true);
    }
}

function showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
    resetLoginModal();
    renderAccountHistory();
}

function hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function showManualTokenField() {
    const choice = document.getElementById('login-choice');
    const form = document.getElementById('manual-token-form');
    if (choice) choice.style.display = 'none';
    if (form) form.style.display = 'block';

    const input = document.getElementById('manual-token-input');
    if (input) {
        input.value = '';
        input.focus();
    }
}

function resetLoginModal() {
    const choice = document.getElementById('login-choice');
    const form = document.getElementById('manual-token-form');
    if (choice) choice.style.display = 'block';
    if (form) form.style.display = 'none';

    const input = document.getElementById('manual-token-input');
    if (input) input.value = '';
}

function loginWithToken() {
    const input = document.getElementById('manual-token-input');
    const tokenValue = input ? input.value.trim() : '';

    if (!tokenValue) {
        addLog('❌ Voer een geldige token in.', true);
        return;
    }

    const emailInput = prompt('E-mailadres (optioneel):', loadLastEmail() || '');
    if (emailInput === null) return;
    const emailValue = emailInput.trim();
    if (emailValue) {
        saveLastEmail(emailValue);
    }

    TOKEN = tokenValue;
    localStorage.setItem('timelimit_token', TOKEN);
    scheduleHaStorageShadowSync('login-token');
    updateTokenDisplay();
    hideLoginModal();
    recordAccountHistory({
        token: TOKEN,
        email: emailValue || loadLastEmail(),
        serverUrl: getCurrentServerUrl(),
        seq: peekNextSequenceNumber()
    });
    addLog('✅ Token ingesteld en opgeslagen.');
    runSync();
}

const HISTORY_STORAGE_KEY = 'timelimit_account_history';
const LAST_EMAIL_STORAGE_KEY = 'timelimit_last_email';

function loadLastEmail() {
    return localStorage.getItem(LAST_EMAIL_STORAGE_KEY) || '';
}

function saveLastEmail(email) {
    if (!email) return;
    localStorage.setItem(LAST_EMAIL_STORAGE_KEY, email);
    scheduleHaStorageShadowSync('last-email');
}

function getCurrentServerUrl() {
    const saved = localStorage.getItem('selected_timelimit_server');
    if (saved) return saved;
    const selector = document.getElementById('server-select');
    if (selector) return selector.value;
    return '';
}

function getServerLabelFromUrl(url) {
    const selector = document.getElementById('server-select');
    if (selector) {
        const match = Array.from(selector.options).find((opt) => opt.value === url);
        if (match) return match.textContent.trim();
    }
    if (url.includes('timelimit.io')) return 'Officieel';
    if (url) return 'Lokaal';
    return '';
}

function loadAccountHistory() {
    try {
        const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed;
    } catch (e) {
        return [];
    }
}

function saveAccountHistory(entries) {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(entries));
    scheduleHaStorageShadowSync('account-history');
}

function recordAccountHistory({ token, email, serverUrl, seq }) {
    if (!token) return;
    const entries = loadAccountHistory();
    const now = Date.now();
    const serverLabel = getServerLabelFromUrl(serverUrl);
    const normalizedSeq = Number.isFinite(Number(seq)) ? Number(seq) : 0;

    const existingIndex = entries.findIndex((entry) => entry.token === token);
    const entry = {
        token,
        email: email || '',
        serverUrl: serverUrl || '',
        serverLabel: serverLabel || '',
        seq: normalizedSeq,
        lastUsedAt: now
    };

    if (existingIndex >= 0) {
        entries[existingIndex] = { ...entries[existingIndex], ...entry };
    } else {
        entries.unshift(entry);
    }

    saveAccountHistory(entries.slice(0, 20));
    renderAccountHistory();
}

function updateHistorySeqForToken(token, seq) {
    if (!token) return;
    const entries = loadAccountHistory();
    const index = entries.findIndex((entry) => entry.token === token);
    if (index < 0) return;
    const normalizedSeq = Number.isFinite(Number(seq)) ? Number(seq) : entries[index].seq;
    entries[index] = { ...entries[index], seq: normalizedSeq, lastUsedAt: Date.now() };
    saveAccountHistory(entries);
    renderAccountHistory();
}

function renderAccountHistory() {
    const tableBody = document.getElementById('account-history-body');
    if (!tableBody) return;

    const entries = loadAccountHistory();
    if (entries.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" style="color:#666;">Geen geschiedenis</td></tr>';
        return;
    }

    tableBody.innerHTML = entries.map((entry, index) => {
        const tokenShort = entry.token ? `${entry.token.substring(0, 6)}...${entry.token.substring(entry.token.length - 4)}` : '';
        const email = entry.email || '-';
        const server = entry.serverLabel || entry.serverUrl || '-';
        const seq = Number.isFinite(Number(entry.seq)) ? entry.seq : 0;
        return `
            <tr>
                <td>${server}</td>
                <td>${email}</td>
                <td>${tokenShort}</td>
                <td>${seq}</td>
                <td><button class="btn" style="padding:4px 8px; font-size:10px;" onclick="applyAccountHistory(${index})">Switch</button></td>
            </tr>
        `;
    }).join('');
}

function applyAccountHistory(index) {
    const entries = loadAccountHistory();
    const entry = entries[index];
    if (!entry) return;

    if (entry.token) {
        TOKEN = entry.token;
        localStorage.setItem('timelimit_token', TOKEN);
        scheduleHaStorageShadowSync('account-switch-token');
    }

    if (Number.isFinite(Number(entry.seq))) {
        setSequenceNumber(entry.seq);
    }

    if (entry.serverUrl) {
        localStorage.setItem('selected_timelimit_server', entry.serverUrl);
        scheduleHaStorageShadowSync('account-switch-server');
        if (typeof switchServer === 'function') {
            switchServer(entry.serverUrl);
            return;
        }
    }

    updateTokenDisplay();
    updateSequenceDisplay();
    runSync();
}

function recordAccountHistoryFromCurrent() {
    recordAccountHistory({
        token: TOKEN,
        email: loadLastEmail(),
        serverUrl: getCurrentServerUrl(),
        seq: peekNextSequenceNumber()
    });
}

function ensureAccountHistoryForCurrent() {
    try {
        if (typeof TOKEN === 'undefined' || !TOKEN) return;
        const entries = loadAccountHistory();
        const exists = entries.some((entry) => entry && entry.token === TOKEN);
        if (!exists) {
            recordAccountHistoryFromCurrent();
        }
    } catch (e) {
        // Best-effort only.
    }
}

window.recordAccountHistoryFromCurrent = recordAccountHistoryFromCurrent;
window.ensureAccountHistoryForCurrent = ensureAccountHistoryForCurrent;
window.recordAccountHistory = recordAccountHistory;
window.updateHistorySeqForToken = updateHistorySeqForToken;
window.renderAccountHistory = renderAccountHistory;
window.applyAccountHistory = applyAccountHistory;
window.saveLastEmail = saveLastEmail;

/**
 * Toont een samenvatting van alle gewijzigde regels
 */
function showChangesSummary() {
    const changes = getChangedRules();
    
    console.log("[DEBUG] showChangesSummary() aangeroepen. Aantal wijzigingen:", changes.length);
    
    if (changes.length === 0) {
        alert('❌ Geen wijzigingen aangebracht.');
        console.log("[DEBUG] Geen wijzigingen gevonden!");
        return;
    }

    let html = `<div class="changes-summary">
        <h3>📋 Wijzigingen (${changes.length})</h3>
        <ul>`;

    changes.forEach(change => {
        const catId = change.categoryId;
        const ruleId = change.ruleId;
        const original = change.original;
        const current = change.current;

        // Zoek de categorie-naam (title) op uit de huidige data snapshot
        let catTitle = catId;
        try {
            if (typeof currentDataDraft !== 'undefined' && currentDataDraft && currentDataDraft.categoryBase) {
                const cat = currentDataDraft.categoryBase.find(c => c.categoryId == catId);
                if (cat && cat.title) catTitle = cat.title;
            }
        } catch (e) {
            console.warn('[DEBUG] kon categorie-naam niet ophalen', e);
        }

        // Bepaal wat er gewijzigd is - controleer elk veld
        let details = [];
        
        if (original.maxTime !== current.maxTime) {
            details.push(`Limiet: ${formatDuration(original.maxTime)} → ${formatDuration(current.maxTime)}`);
        }
        if (original.start !== current.start || original.end !== current.end) {
            details.push(`Tijd: ${formatClockTime(original.start)}-${formatClockTime(original.end)} → ${formatClockTime(current.start)}-${formatClockTime(current.end)}`);
        }
        if (original.dayMask !== current.dayMask) {
            details.push(`Dagen: ${formatDays(original.dayMask)} → ${formatDays(current.dayMask)}`);
        }
        if (original.perDay !== current.perDay) {
            details.push(`Per dag: ${original.perDay ? 'ja' : 'nee'} → ${current.perDay ? 'ja' : 'nee'}`);
        }

        // Toon ook de ruwe waarden voor volledigheid
        html += `<li>
            <strong>Regel ${ruleId}</strong> (Categorie: ${catTitle})
            <div class="change-detail">${details.length > 0 ? details.join(' | ') : 'Geen wijzigingen gedetecteerd'}</div>
            <div class="change-detail" style="color: #888; font-size: 10px; margin-top: 4px;">
                Origineel: maxTime=${original.maxTime}ms, start=${original.start}min, end=${original.end}min, dayMask=${original.dayMask}, perDay=${original.perDay}
                <br>Huidig: maxTime=${current.maxTime}ms, start=${current.start}min, end=${current.end}min, dayMask=${current.dayMask}, perDay=${current.perDay}
            </div>
        </li>`;
    });

    html += `</ul>
        <button class="btn reset-changes-btn" style="width: 100%; margin-top: 10px;" onclick="resetAllChanges(); location.reload();">↶ Wijzigingen ongedaan maken</button>
    </div>`;

    const container = document.getElementById('category-tree-container');
    if (container) {
        // Verwijder eerdere samenvatting als deze al bestaat
        const existing = container.parentElement.querySelector('.changes-summary');
        if (existing) existing.remove();
        
        container.insertAdjacentHTML('beforebegin', html);
        addLog(`✏️ ${changes.length} wijziging${changes.length !== 1 ? 'en' : ''} gedetecteerd!`);
    } else {
        console.error("[ERROR] category-tree-container niet gevonden!");
    }
}

/**
 * Toont het aantal wijzigingen in de header
 */
function updateChangeIndicator() {
    const changes = getChangedRules();
    const indicator = document.getElementById('change-indicator');
    
    if (indicator) {
        if (changes.length > 0) {
            indicator.textContent = `📝 ${changes.length} wijziging${changes.length !== 1 ? 'en' : ''}`;
            indicator.style.display = 'inline-block';
        } else {
            indicator.style.display = 'none';
        }
    }
}

/**
 * Toont de modal voor wachtwoord reset/bijwerken
 */
function showPasswordResetModal() {
    const modal = document.getElementById('password-reset-modal');
    if (modal) {
        modal.style.display = 'flex';
        const input = document.getElementById('password-reset-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        const status = document.getElementById('password-reset-status');
        if (status) status.textContent = '';
    }
}

/**
 * Verbergt de modal voor wachtwoord reset
 */
function hidePasswordResetModal() {
    const modal = document.getElementById('password-reset-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Verwerkt het wachtwoord: genereert hashes en slaat ze op
 */
async function submitPasswordReset() {
    const password = document.getElementById('password-reset-input').value;
    const statusDiv = document.getElementById('password-reset-status');
    
    if (!password) {
        if (statusDiv) statusDiv.textContent = "❌ Voer een wachtwoord in.";
        return;
    }
    
    if (statusDiv) statusDiv.textContent = "⏳ Wachtwoord verwerken...";
    
    try {
        // Check of we een secondPasswordSalt hebben uit de sync data
        let secondSalt = null;
        let secondHash = null;
        
        if (currentDataDraft && currentDataDraft.users && currentDataDraft.users.data) {
            const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
            if (parentUser && parentUser.secondPasswordSalt) {
                secondSalt = parentUser.secondPasswordSalt;
                console.log("[PASSWORD-RESET] secondPasswordSalt gevonden in sync data:", secondSalt);
            }
        }
        
        if (secondSalt) {
            // SCENARIO 1: We hebben de salt van de server, regenereer de exacte hash
            if (statusDiv) statusDiv.textContent = "⏳ Hash regenereren met server salt...";
            
            const regenRes = await fetch('regenerate-hash', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    password: password,
                    secondSalt: secondSalt
                })
            });
            
            if (!regenRes.ok) {
                const errorText = await regenRes.text();
                throw new Error(`Hash regeneratie gefaald: ${errorText}`);
            }
            
            const regenData = await regenRes.json();
            secondHash = regenData.secondHash;
            
            console.log("[PASSWORD-RESET] secondHash geregenereerd (first 30 chars):", secondHash.substring(0, 30) + "...");
            
        } else {
            // SCENARIO 2: Geen salt beschikbaar, genereer nieuwe hashes (alleen bij create)
            if (statusDiv) statusDiv.textContent = "⏳ Nieuwe hashes genereren...";
            
            const hRes = await fetch('generate-hashes', {
                method: 'POST',
                body: JSON.stringify({ password: password })
            });
            
            if (!hRes.ok) {
                const errorText = await hRes.text();
                throw new Error(`Fout bij hash generatie: ${errorText}`);
            }
            
            const hashes = await hRes.json();
            
            // STRIKTE VALIDATIE: Alleen echte bcrypt waarden accepteren
            if (!hashes.secondHash || !hashes.secondHash.includes('$2')) {
                throw new Error("Server retourneerde geen geldige secondHash");
            }
            if (!hashes.secondSalt || !hashes.secondSalt.includes('$2')) {
                throw new Error("Server retourneerde geen geldige secondSalt");
            }
            
            secondHash = hashes.secondHash.replace('$2b$', '$2a$');
            secondSalt = hashes.secondSalt.replace('$2b$', '$2a$');
            
            console.log("[PASSWORD-RESET] Nieuwe hashes gegenereerd");
        }
        
        // Converteer salt naar base64 voor HMAC (legacy - secundaire verificatie)
        const base64Salt = bcryptSaltToBase64(secondSalt);
        
        // Sla op in state.js - GEBRUIK DE BCRYPT HASH ALS KEY!
        if (typeof storeparentPasswordHashForSync === 'function') {
            storeparentPasswordHashForSync({
                hash: secondHash, // Gebruik secondHash als primary hash
                secondHash: secondHash,
                secondSalt: base64Salt || secondSalt
            });
            
            if (statusDiv) {
                statusDiv.innerHTML = "✅ Hashes succesvol bijgewerkt!<br><span style='font-size:11px;'>secondHash: " + secondHash.substring(0, 30) + "...</span>";
                statusDiv.style.color = '#4ade80';
            }
            
            addLog("✅ Wachtwoord hashes bijgewerkt met server secondHash!");
            
            // Sluit modal na 2 seconden
            setTimeout(() => {
                hidePasswordResetModal();
            }, 2000);
        } else {
            throw new Error("State functie niet beschikbaar");
        }
    } catch (e) {
        if (statusDiv) {
            statusDiv.textContent = "❌ Fout: " + e.message;
            statusDiv.style.color = '#ff4444';
        }
        addLog("Fout bij wachtwoord bijwerken: " + e.message, true);
    }
}