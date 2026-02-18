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
    'timelimit_parentPublicKey',
    'timelimit_parentPrivateKey',
    'timelimit_account_history',
    'timelimit_last_email',
    'selected_timelimit_server',
    'timelimit_debugMode',
    'timelimit_useEncryptedApps',
    'timelimit_nextSyncSequenceNumber',
    'timelimit_serverApiLevel',
    'timelimit_disabledRules',
    'timelimit_disabledRulesDirty'
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
    const encryptedAppsMode = data.timelimit_useEncryptedApps === '1' ? 'On' : 'Off';
    const sequence = data.timelimit_nextSyncSequenceNumber || '0';
    const apiLevel = data.timelimit_serverApiLevel || '-';
    const parentPublicPresent = data.timelimit_parentPublicKey ? 'ja' : 'nee';
    const parentPrivatePresent = data.timelimit_parentPrivateKey ? 'ja' : 'nee';
    const disabledRulesRaw = data.timelimit_disabledRules || '[]';
    const disabledRulesDirty = data.timelimit_disabledRulesDirty === '1' ? 'ja' : 'nee';

    statusEl.textContent = `Laatst bijgewerkt: ${formatTimestamp(storage.updatedAt || storage.serverTimestamp)}`;

    const parentHashPresent = data.timelimit_parentPasswordHash ? 'ja' : 'nee';
    const historyRaw = data.timelimit_account_history || '[]';
    let disabledRulesCount = 0;
    try {
        const parsed = JSON.parse(disabledRulesRaw);
        if (Array.isArray(parsed)) disabledRulesCount = parsed.length;
    } catch (e) {
        disabledRulesCount = 0;
    }

    detailsEl.innerHTML = `
        <div style="margin-bottom:6px;">Token: <span style="color:#fff; font-family: monospace;">${formatTokenShort(token) || '-'}</span></div>
        <div style="margin-bottom:6px;">Parent hash aanwezig: <span style="color:#fff;">${parentHashPresent}</span></div>
        <div style="margin-bottom:6px;">Laatste e-mail: <span style="color:#fff;">${lastEmail || '-'}</span></div>
        <div style="margin-bottom:6px;">Server: <span style="color:#fff;">${selectedServer || '-'}</span></div>
        <div style="margin-bottom:6px;">Debug: <span style="color:#fff;">${debugMode}</span></div>
        <div style="margin-bottom:6px;">Encrypted apps: <span style="color:#fff;">${encryptedAppsMode}</span></div>
        <div style="margin-bottom:6px;">Parent public key: <span style="color:#fff;">${parentPublicPresent}</span></div>
        <div style="margin-bottom:6px;">Parent private key: <span style="color:#fff;">${parentPrivatePresent}</span></div>
        <div style="margin-bottom:6px;">Uitgeschakelde regels: <span style="color:#fff;">${disabledRulesCount}</span></div>
        <div style="margin-bottom:6px;">Uitgeschakelde regels dirty: <span style="color:#fff;">${disabledRulesDirty}</span></div>
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
        return data;
    } catch (e) {
        const statusEl = document.getElementById('ha-storage-status');
        const detailsEl = document.getElementById('ha-storage-details');
        const historyBody = document.getElementById('ha-storage-history-body');
        if (statusEl) statusEl.textContent = 'Kon HA storage niet laden.';
        if (detailsEl) detailsEl.textContent = '';
        if (historyBody) {
            historyBody.innerHTML = '<tr><td colspan="5" style="padding: 8px; color: #666;">Geen geschiedenis</td></tr>';
        }
        return null;
    }
}

window.loadHaStorageStatus = loadHaStorageStatus;
window.applyHaStorageHistory = applyHaStorageHistory;

let haEventSource = null;
let haEventLastSyncAt = 0;

function initHaEventStream() {
    if (haEventSource || typeof EventSource === 'undefined') return;

    const scheduleSync = (evt) => {
        if (evt && evt.type) {
            addLog(`🔔 HA event: ${evt.type}`, false);
        } else {
            addLog('🔔 HA event: message', false);
        }
        const now = Date.now();
        if (now - haEventLastSyncAt < 2000) return;
        haEventLastSyncAt = now;
        if (typeof runSync === 'function') {
            addLog('🔄 HA event: trigger pull sync', false);
            runSync();
        }
    };

    try {
        haEventSource = new EventSource('ha-events');
        addLog('📡 HA event stream verbonden', false);
        haEventSource.onmessage = scheduleSync;
        haEventSource.addEventListener('push', scheduleSync);
        haEventSource.addEventListener('storage', scheduleSync);
        haEventSource.onerror = () => {
            addLog('⚠️ HA event stream fout/timeout', true);
        };
    } catch (e) {
        addLog(`❌ HA event stream niet gestart: ${e.message}`, true);
        haEventSource = null;
    }
}

window.initHaEventStream = initHaEventStream;

async function loadHaStorageAndApply() {
    const data = await loadHaStorageStatus();
    if (data && data.data) {
        applyHaStorageDataToLocal(data);
        return true;
    }
    return false;
}

window.loadHaStorageAndApply = loadHaStorageAndApply;

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
const ENCRYPTED_APPS_TOGGLE_KEY = 'timelimit_useEncryptedApps';
const ENCRYPTED_APPS_CACHE_KEY = 'timelimit_encryptedAppsCache';
const DECRYPTED_APPS_CACHE_KEY = 'timelimit_decryptedAppsCache';
const ENCRYPTED_APPS_STATUS_KEY = 'timelimit_encryptedAppsStatus';
const ENCRYPTED_APPS_KEYS_KEY = 'timelimit_appListKeys';
const DEVICE_LIST_CACHE_KEY = 'timelimit_deviceListCache';
const PARENT_PUBLIC_KEY_STORAGE = 'timelimit_parentPublicKey';
const PARENT_PRIVATE_KEY_STORAGE = 'timelimit_parentPrivateKey';
const KEY_REQUESTS_CACHE_KEY = 'timelimit_keyRequestsCache';

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

function isEncryptedAppsEnabled() {
    return localStorage.getItem(ENCRYPTED_APPS_TOGGLE_KEY) === '1';
}

function applyEncryptedAppsToggle(enabled) {
    const toggle = document.getElementById('encrypted-apps-toggle');
    if (toggle) toggle.checked = enabled;

    const label = document.getElementById('encrypted-apps-toggle-label');
    if (label) {
        label.textContent = enabled ? 'AAN' : 'UIT';
        label.style.borderColor = enabled ? '#2d5a2d' : '#333';
        label.style.background = enabled ? '#123116' : '#111';
        label.style.color = enabled ? '#8fe39b' : '#bbb';
    }
}

function setEncryptedAppsEnabled(enabled) {
    localStorage.setItem(ENCRYPTED_APPS_TOGGLE_KEY, enabled ? '1' : '0');
    scheduleHaStorageShadowSync('encrypted-apps-toggle');
    applyEncryptedAppsToggle(enabled);
}

function initEncryptedAppsToggle() {
    const toggle = document.getElementById('encrypted-apps-toggle');
    if (!toggle) return;

    toggle.addEventListener('change', () => {
        setEncryptedAppsEnabled(toggle.checked);
    });

    applyEncryptedAppsToggle(isEncryptedAppsEnabled());
}

window.isEncryptedAppsEnabled = isEncryptedAppsEnabled;
window.setEncryptedAppsEnabled = setEncryptedAppsEnabled;

function loadEncryptedAppsCache() {
    try {
        const raw = localStorage.getItem(ENCRYPTED_APPS_CACHE_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return {};
        return parsed;
    } catch (e) {
        return {};
    }
}

function loadDecryptedAppsCache() {
    try {
        const raw = localStorage.getItem(DECRYPTED_APPS_CACHE_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return {};
        return parsed;
    } catch (e) {
        return {};
    }
}

function setDecryptedAppsCache(value) {
    if (!value || typeof value !== 'object') {
        localStorage.removeItem(DECRYPTED_APPS_CACHE_KEY);
    } else {
        localStorage.setItem(DECRYPTED_APPS_CACHE_KEY, JSON.stringify(value));
    }
    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('decrypted-apps-cache');
    }
}

function setEncryptedAppsStatus(value) {
    if (!value || typeof value !== 'object') {
        localStorage.removeItem(ENCRYPTED_APPS_STATUS_KEY);
    } else {
        localStorage.setItem(ENCRYPTED_APPS_STATUS_KEY, JSON.stringify(value));
    }
}

function loadEncryptedAppsKeys() {
    try {
        const raw = localStorage.getItem(ENCRYPTED_APPS_KEYS_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return {};
        return parsed;
    } catch (e) {
        return {};
    }
}

function loadDeviceListCache() {
    try {
        const raw = localStorage.getItem(DEVICE_LIST_CACHE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function setDeviceListCache(devices) {
    if (!Array.isArray(devices)) {
        localStorage.removeItem(DEVICE_LIST_CACHE_KEY);
    } else {
        localStorage.setItem(DEVICE_LIST_CACHE_KEY, JSON.stringify(devices));
    }
    renderEncryptedAppsDeviceOptions();
    renderKeyRequestList();
    renderDeviceOverview();
}

function loadKeyRequestsCache() {
    try {
        const raw = localStorage.getItem(KEY_REQUESTS_CACHE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function setKeyRequestsCache(items) {
    if (!Array.isArray(items)) {
        localStorage.removeItem(KEY_REQUESTS_CACHE_KEY);
    } else {
        localStorage.setItem(KEY_REQUESTS_CACHE_KEY, JSON.stringify(items));
    }
    renderKeyRequestList();
    renderDeviceOverview();
}

function setEncryptedAppsKeys(value) {
    if (!value || typeof value !== 'object') {
        localStorage.removeItem(ENCRYPTED_APPS_KEYS_KEY);
    } else {
        localStorage.setItem(ENCRYPTED_APPS_KEYS_KEY, JSON.stringify(value));
    }
    renderDeviceOverview();
}

function loadParentKeyPair() {
    return {
        publicKey: localStorage.getItem(PARENT_PUBLIC_KEY_STORAGE) || '',
        privateKey: localStorage.getItem(PARENT_PRIVATE_KEY_STORAGE) || ''
    };
}

function setParentKeyPair({ publicKey, privateKey }) {
    if (publicKey) {
        localStorage.setItem(PARENT_PUBLIC_KEY_STORAGE, publicKey);
    } else {
        localStorage.removeItem(PARENT_PUBLIC_KEY_STORAGE);
    }

    if (privateKey) {
        localStorage.setItem(PARENT_PRIVATE_KEY_STORAGE, privateKey);
    } else {
        localStorage.removeItem(PARENT_PRIVATE_KEY_STORAGE);
    }

    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('parent-keypair');
    }
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatKeyShort(value) {
    if (!value) return '-';
    if (value.length <= 10) return value;
    return `${value.slice(0, 4)}...${value.slice(-4)} (${value.length})`;
}

function renderEncryptedAppsDeviceOptions() {
    const select = document.getElementById('encrypted-apps-device-id');
    const manualInput = document.getElementById('encrypted-apps-device-id-manual');
    if (!select) return;

    const currentValue = select.value || '';
    const devices = loadDeviceListCache();
    const options = [];

    options.push({ value: '', label: 'Kies device...' });
    if (devices.length > 0) {
        devices.forEach((device) => {
            const deviceId = device && device.deviceId ? String(device.deviceId) : '';
            if (!deviceId) return;
            const name = device && device.name ? String(device.name) : 'Onbekend';
            options.push({ value: deviceId, label: `${name} (${deviceId})` });
        });
    }
    options.push({ value: '__manual__', label: 'Handmatig invoeren...' });

    select.innerHTML = options.map((opt) => {
        return `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`;
    }).join('');

    if (currentValue) {
        select.value = currentValue;
    }

    if (!select.value) {
        select.value = '';
    }

    select.onchange = () => {
        const isManual = select.value === '__manual__';
        if (manualInput) {
            manualInput.style.display = isManual ? '' : 'none';
            if (!isManual) manualInput.value = '';
        }
    };

    if (manualInput) {
        manualInput.style.display = select.value === '__manual__' ? '' : 'none';
    }
}

function formatBase64Short(value) {
    if (!value) return '-';
    if (value.length <= 12) return value;
    return `${value.slice(0, 6)}...${value.slice(-4)} (${value.length})`;
}

function getDevicePublicKeyBase64(deviceId) {
    if (!deviceId) return '';
    const devices = loadDeviceListCache();
    for (let i = 0; i < devices.length; i += 1) {
        const device = devices[i];
        if (!device || !device.deviceId) continue;
        if (String(device.deviceId) !== String(deviceId)) continue;
        return device.pk ? String(device.pk) : '';
    }
    return '';
}

function isNaclAvailable() {
    return typeof nacl !== 'undefined'
        && nacl.sign
        && nacl.sign.detached
        && typeof nacl.sign.detached.verify === 'function';
}

function pushInt32BE(buffer, value) {
    buffer.push((value >>> 24) & 0xff);
    buffer.push((value >>> 16) & 0xff);
    buffer.push((value >>> 8) & 0xff);
    buffer.push(value & 0xff);
}

function pushInt64BE(buffer, value) {
    let big = typeof value === 'bigint' ? value : BigInt(value);
    if (big < 0) big = 0n;
    for (let i = 7; i >= 0; i -= 1) {
        buffer.push(Number((big >> BigInt(i * 8)) & 0xffn));
    }
}

function pushBytes(buffer, bytes) {
    for (let i = 0; i < bytes.length; i += 1) {
        buffer.push(bytes[i]);
    }
}

function writeBool(buffer, value) {
    buffer.push(value ? 1 : 0);
}

function writeString(buffer, value) {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(String(value));
    pushInt32BE(buffer, bytes.length);
    pushBytes(buffer, bytes);
}

function writeOptionalString(buffer, value) {
    if (value === null || typeof value === 'undefined') {
        writeBool(buffer, false);
        return;
    }
    writeBool(buffer, true);
    writeString(buffer, value);
}

function buildKeyRequestSignedDataBytes(item, tempKeyBytes) {
    const bytes = [];
    writeString(bytes, 'KeyRequestSignedData');

    const seq = item && typeof item.senSeq !== 'undefined' ? item.senSeq : 0;
    pushInt64BE(bytes, seq);

    const deviceId = item && item.deviceId ? String(item.deviceId) : null;
    writeBool(bytes, deviceId !== null);
    writeOptionalString(bytes, deviceId);

    const categoryId = item && item.categoryId ? String(item.categoryId) : null;
    writeOptionalString(bytes, categoryId);

    const typeValue = item && typeof item.type !== 'undefined' ? Number(item.type) : 0;
    pushInt32BE(bytes, typeValue | 0);

    const tempKey = tempKeyBytes || (item && item.tempKey ? base64ToBytes(item.tempKey) : new Uint8Array());
    pushBytes(bytes, tempKey);

    return new Uint8Array(bytes);
}

function verifyKeyRequestSignature(item) {
    if (!item) return { ok: false, reason: 'missing item' };
    if (!isNaclAvailable()) return { ok: false, reason: 'no nacl' };

    const senderId = item.senId ? String(item.senId) : '';
    if (!senderId) return { ok: false, reason: 'missing sender' };

    const senderPublicKeyBase64 = getDevicePublicKeyBase64(senderId);
    if (!senderPublicKeyBase64) return { ok: false, reason: 'no sender pk' };

    let signatureBytes;
    let publicKeyBytes;
    let tempKeyBytes;
    let messageBytes;

    try {
        signatureBytes = base64ToBytes(item.signature || '');
        publicKeyBytes = base64ToBytes(senderPublicKeyBase64);
        tempKeyBytes = item.tempKey ? base64ToBytes(item.tempKey) : new Uint8Array();
        messageBytes = buildKeyRequestSignedDataBytes(item, tempKeyBytes);
    } catch (e) {
        return { ok: false, reason: 'bad base64' };
    }

    if (publicKeyBytes.length !== 32) return { ok: false, reason: `pk len ${publicKeyBytes.length}` };
    if (signatureBytes.length !== 64) return { ok: false, reason: `sig len ${signatureBytes.length}` };
    if (tempKeyBytes.length !== 32) return { ok: false, reason: `tempKey len ${tempKeyBytes.length}` };

    const ok = nacl.sign.detached.verify(messageBytes, signatureBytes, publicKeyBytes);
    return ok ? { ok: true, reason: 'ok' } : { ok: false, reason: 'sig invalid' };
}

function getKeyRequestSignatureLabel(item) {
    const result = verifyKeyRequestSignature(item);
    return result.ok ? 'ok' : result.reason;
}

function renderParentKeyPairStatus() {
    const status = document.getElementById('parent-keypair-status');
    if (!status) return;

    const { publicKey, privateKey } = loadParentKeyPair();
    if (!publicKey || !privateKey) {
        status.textContent = 'Geen keypair opgeslagen.';
        return;
    }

    status.textContent = `Public: ${formatBase64Short(publicKey)} | Private: ${formatBase64Short(privateKey)}`;
}

function formatKeyRequestItem(item) {
    const deviceId = item && item.deviceId ? String(item.deviceId) : '-';
    const categoryId = item && item.categoryId ? String(item.categoryId) : '-';
    const type = item && typeof item.type !== 'undefined' ? String(item.type) : '-';
    const sender = item && item.senId ? String(item.senId) : '-';
    const seq = item && typeof item.senSeq !== 'undefined' ? String(item.senSeq) : '-';
    const sigLabel = getKeyRequestSignatureLabel(item);
    return `Device: ${deviceId} | Category: ${categoryId} | Type: ${type} | Sender: ${sender}/${seq} | Sig: ${sigLabel}`;
}

function renderKeyRequestList() {
    const list = document.getElementById('key-request-list');
    const count = document.getElementById('key-request-count');
    if (!list || !count) return;

    const items = loadKeyRequestsCache();
    count.textContent = String(items.length);

    if (items.length === 0) {
        list.innerHTML = '<div style="color:#666;">Geen key requests.</div>';
        return;
    }

    list.innerHTML = items.map((item) => {
        return `<div style="padding:4px 0; border-top:1px solid #1b232c;">${escapeHtml(formatKeyRequestItem(item))}</div>`;
    }).join('');
}

function setKeyRequestIndicator(state) {
    const indicator = document.getElementById('key-request-indicator');
    if (!indicator) return;

    const data = state && typeof state === 'object' ? state : {};
    const devices2Count = Number.isFinite(data.devices2Count) ? data.devices2Count : null;
    const missingKeys = Number.isFinite(data.missingKeys) ? data.missingKeys : null;
    const krqCount = Number.isFinite(data.krqCount) ? data.krqCount : null;

    if (krqCount !== null && krqCount > 0) {
        indicator.textContent = `Key requests ontvangen: ${krqCount}.`;
        return;
    }

    if (devices2Count === null) {
        indicator.textContent = 'Nog geen status.';
        return;
    }

    if (devices2Count === 0) {
        indicator.textContent = 'Geen apps data (devices2 leeg).';
        return;
    }

    if (missingKeys !== null && missingKeys > 0) {
        indicator.textContent = `Apps data ontvangen, maar ${missingKeys} device(s) missen key. Wacht op key request van child.`;
        return;
    }

    indicator.textContent = 'Apps data aanwezig en keys zijn compleet.';
}

function clearParentKeyPairInputs() {
    const publicInput = document.getElementById('parent-public-key');
    const privateInput = document.getElementById('parent-private-key');
    if (publicInput) publicInput.value = '';
    if (privateInput) privateInput.value = '';
}

function saveParentKeyPair() {
    const publicInput = document.getElementById('parent-public-key');
    const privateInput = document.getElementById('parent-private-key');
    const publicKey = publicInput ? publicInput.value.trim() : '';
    const privateKey = privateInput ? privateInput.value.trim() : '';

    if (!publicKey || !privateKey) {
        if (typeof addLog === 'function') addLog('❌ Public en private key zijn verplicht.', true);
        return;
    }

    let publicBytes;
    let privateBytes;
    try {
        publicBytes = base64ToBytes(publicKey);
        privateBytes = base64ToBytes(privateKey);
    } catch (e) {
        if (typeof addLog === 'function') addLog('❌ Ongeldige base64 key(s).', true);
        return;
    }

    if (publicBytes.length !== 32 || privateBytes.length !== 32) {
        if (typeof addLog === 'function') addLog(`❌ Keys moeten 32 bytes zijn. Public: ${publicBytes.length}, Private: ${privateBytes.length}.`, true);
        return;
    }

    setParentKeyPair({ publicKey, privateKey });
    renderParentKeyPairStatus();
    if (typeof addLog === 'function') addLog('✅ Parent keypair opgeslagen.');
}

function clearParentKeyPair() {
    setParentKeyPair({ publicKey: '', privateKey: '' });
    renderParentKeyPairStatus();
    if (typeof addLog === 'function') addLog('✅ Parent keypair verwijderd.');
}

function initParentKeyPairPanel() {
    const { publicKey, privateKey } = loadParentKeyPair();
    const publicInput = document.getElementById('parent-public-key');
    const privateInput = document.getElementById('parent-private-key');
    if (publicInput) publicInput.value = publicKey;
    if (privateInput) privateInput.value = privateKey;
    renderParentKeyPairStatus();
    renderKeyRequestList();
}

function renderEncryptedAppsKeyList() {
    const container = document.getElementById('encrypted-apps-keys');
    if (!container) return;

    const keys = loadEncryptedAppsKeys();
    const deviceIds = Object.keys(keys);
    if (deviceIds.length === 0) {
        container.innerHTML = '<div style="color:#666;">Geen keys opgeslagen.</div>';
        return;
    }

    container.innerHTML = deviceIds.map((deviceId) => {
        const key = keys[deviceId];
        const safeId = escapeHtml(deviceId);
        const btnArg = escapeHtml(JSON.stringify(deviceId));
        return `
            <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; padding:4px 0; border-top:1px solid #1b232c;">
                <div style="font-family: monospace; color:#bbb;">${safeId}</div>
                <div style="color:#8ab4f8;">${escapeHtml(formatKeyShort(key))}</div>
                <button class="btn" style="padding:2px 6px; font-size:10px; background:#333;" onclick="if (window.removeEncryptedAppsKey) window.removeEncryptedAppsKey(${btnArg});">Verwijder</button>
            </div>
        `;
    }).join('');
}

function getDeviceDisplayName(device) {
    if (!device || typeof device !== 'object') return 'Onbekend';
    return device.name || device.title || device.model || device.deviceId || 'Onbekend';
}

function getDeviceKeyStatus(deviceId, keyRequests, appKeys) {
    const hasKey = !!appKeys[deviceId];
    const pending = keyRequests.some((item) => item && item.deviceId && String(item.deviceId) === String(deviceId));
    return { hasKey, pending };
}

function formatAppsDataSummary(entry) {
    if (!entry || typeof entry !== 'object') return 'Geen apps data.';
    const parts = [];
    if (entry.appsBase) {
        const baseVersion = entry.appsBase.version || '-';
        const baseLen = entry.appsBase.data ? String(entry.appsBase.data).length : 0;
        parts.push(`appsBase v=${baseVersion}, len=${baseLen}`);
    }
    if (entry.appsDiff) {
        const diffVersion = entry.appsDiff.version || '-';
        const diffLen = entry.appsDiff.data ? String(entry.appsDiff.data).length : 0;
        parts.push(`appsDiff v=${diffVersion}, len=${diffLen}`);
    }
    return parts.length > 0 ? parts.join(' | ') : 'Geen apps data.';
}

function renderDeviceOverview() {
    const container = document.getElementById('device-overview-container');
    if (!container) return;

    const devices = loadDeviceListCache();
    if (!devices.length) {
        container.innerHTML = '<div style="color:#666;">Geen devices beschikbaar.</div>';
        return;
    }

    const keyRequests = loadKeyRequestsCache();
    const appKeys = loadEncryptedAppsKeys();
    const appsCache = loadEncryptedAppsCache();

    const html = devices.map((device) => {
        const deviceId = device && device.deviceId ? String(device.deviceId) : '';
        const safeName = escapeHtml(getDeviceDisplayName(device));
        const safeId = escapeHtml(deviceId || '-');
        const status = getDeviceKeyStatus(deviceId, keyRequests, appKeys);
        const appsSummary = escapeHtml(formatAppsDataSummary(appsCache[deviceId]));
        const keyLabel = status.hasKey ? 'key: yes' : 'key: no';
        const pendingLabel = status.pending ? 'pending request: yes' : 'pending request: no';

        const infoRows = [];
        const addRow = (label, value) => {
            if (value === null || typeof value === 'undefined' || value === '') return;
            infoRows.push(`<div style="display:flex; gap:8px; padding:2px 0;">
                <div style="min-width:120px; color:#888;">${escapeHtml(label)}</div>
                <div style="color:#bbb; word-break: break-all;">${escapeHtml(String(value))}</div>
            </div>`);
        };

        addRow('DeviceId', deviceId);
        addRow('Name', device.name || device.title || device.model || '');
        addRow('Type', device.type || device.platformType || '');
        addRow('Platform', device.platformLevel || '');
        addRow('UserId', device.currentUserId || '');
        addRow('PublicKey', device.pk ? formatBase64Short(device.pk) : '');

        return `
            <details style="border:1px solid #1b232c; border-radius:6px; padding:8px; margin-bottom:8px; background:#0f141b;">
                <summary style="cursor:pointer; color:#bbb; font-size:12px;">
                    ${safeName} (${safeId}) - ${keyLabel}, ${pendingLabel}
                </summary>
                <div style="margin-top:6px; font-size:11px;">
                    ${infoRows.join('')}
                    <div style="margin-top:6px; color:#8ab4f8;">Apps data</div>
                    <div style="color:#aaa;">${appsSummary}</div>
                    <div style="margin-top:6px; color:#8ab4f8;">Key status</div>
                    <div style="color:#aaa;">${keyLabel} | ${pendingLabel}</div>
                </div>
            </details>
        `;
    }).join('');

    container.innerHTML = html;
}

function clearEncryptedAppsKeyInputs() {
    const deviceInput = document.getElementById('encrypted-apps-device-id');
    const manualInput = document.getElementById('encrypted-apps-device-id-manual');
    const keyInput = document.getElementById('encrypted-apps-key');
    if (deviceInput) deviceInput.value = '';
    if (manualInput) manualInput.value = '';
    if (keyInput) keyInput.value = '';
}

function saveEncryptedAppsKey() {
    const deviceInput = document.getElementById('encrypted-apps-device-id');
    const manualInput = document.getElementById('encrypted-apps-device-id-manual');
    const keyInput = document.getElementById('encrypted-apps-key');
    const selectedValue = deviceInput ? deviceInput.value.trim() : '';
    const manualValue = manualInput ? manualInput.value.trim() : '';
    const deviceId = selectedValue === '__manual__' ? manualValue : selectedValue;
    const keyBase64 = keyInput ? keyInput.value.trim() : '';

    if (!deviceId || !keyBase64) {
        if (typeof addLog === 'function') addLog('❌ DeviceId en key zijn verplicht.', true);
        return;
    }

    let keyBytes;
    try {
        keyBytes = base64ToBytes(keyBase64);
    } catch (e) {
        if (typeof addLog === 'function') addLog('❌ Ongeldige base64 key.', true);
        return;
    }

    if (keyBytes.length !== 16) {
        if (typeof addLog === 'function') addLog(`❌ Key moet 16 bytes zijn, nu ${keyBytes.length}.`, true);
        return;
    }

    const keys = loadEncryptedAppsKeys();
    keys[deviceId] = keyBase64;
    setEncryptedAppsKeys(keys);
    renderEncryptedAppsKeyList();
    if (typeof addLog === 'function') addLog('✅ Encrypted app key opgeslagen.');
    if (typeof decryptEncryptedAppsIfEnabled === 'function') {
        decryptEncryptedAppsIfEnabled();
    }
}

function removeEncryptedAppsKey(deviceId) {
    const keys = loadEncryptedAppsKeys();
    if (!keys[deviceId]) return;
    delete keys[deviceId];
    setEncryptedAppsKeys(keys);
    renderEncryptedAppsKeyList();
    if (typeof addLog === 'function') addLog('✅ Encrypted app key verwijderd.');
}

function initEncryptedAppsKeyPanel() {
    renderEncryptedAppsKeyList();
    renderEncryptedAppsDeviceOptions();
    renderDeviceOverview();
}

function base64ToBytes(value) {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
}

function readInt64BE(view, offset) {
    const high = view.getUint32(offset, false);
    const low = view.getUint32(offset + 4, false);
    return BigInt(high) << 32n | BigInt(low);
}

async function decryptCryptContainer(keyBytes, base64Data) {
    const input = base64ToBytes(base64Data);
    if (input.length < 20 + 16) {
        throw new Error('crypt-container-too-short');
    }

    const view = new DataView(input.buffer, input.byteOffset, input.byteLength);
    const generation = readInt64BE(view, 0);
    const counter = readInt64BE(view, 8);
    const ivPart = view.getInt32(16, false);

    const iv = new Uint8Array(12);
    const ivView = new DataView(iv.buffer);
    ivView.setInt32(0, ivPart, false);
    ivView.setBigInt64(4, counter, false);

    const aad = new Uint8Array(8);
    new DataView(aad.buffer).setBigInt64(0, generation, false);

    const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, ['decrypt']);
    const cipherText = input.slice(20);

    return new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: aad, tagLength: 128 }, key, cipherText));
}

async function inflateDeflate(data) {
    if (!('DecompressionStream' in window)) {
        throw new Error('decompression-not-supported');
    }

    const stream = new DecompressionStream('deflate');
    const writer = stream.writable.getWriter();
    writer.write(data);
    writer.close();

    const response = new Response(stream.readable);
    const buffer = await response.arrayBuffer();
    return new Uint8Array(buffer);
}

function ProtoReader(bytes) {
    this.bytes = bytes;
    this.pos = 0;
    this.length = bytes.length;
}

ProtoReader.prototype.eof = function () {
    return this.pos >= this.length;
};

ProtoReader.prototype.readVarint = function () {
    let result = 0n;
    let shift = 0n;
    while (this.pos < this.length) {
        const byte = this.bytes[this.pos++];
        result |= BigInt(byte & 0x7f) << shift;
        if ((byte & 0x80) === 0) break;
        shift += 7n;
    }
    return result;
};

ProtoReader.prototype.readBytes = function () {
    const length = Number(this.readVarint());
    const start = this.pos;
    this.pos += length;
    return this.bytes.slice(start, start + length);
};

ProtoReader.prototype.readString = function () {
    const bytes = this.readBytes();
    return new TextDecoder('utf-8').decode(bytes);
};

function decodeInstalledAppProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { package_name: '', title: '', is_launchable: false, recommendation: 0 };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.package_name = reader.readString();
        else if (field === 2 && wire === 2) result.title = reader.readString();
        else if (field === 3 && wire === 0) result.is_launchable = reader.readVarint() !== 0n;
        else if (field === 4 && wire === 0) result.recommendation = Number(reader.readVarint());
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function decodeInstalledAppActivityProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { package_name: '', class_name: '', title: '' };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.package_name = reader.readString();
        else if (field === 2 && wire === 2) result.class_name = reader.readString();
        else if (field === 3 && wire === 2) result.title = reader.readString();
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function decodeRemovedAppActivityProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { package_name: '', class_name: '' };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.package_name = reader.readString();
        else if (field === 2 && wire === 2) result.class_name = reader.readString();
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function decodeInstalledAppsProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { apps: [], activities: [] };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.apps.push(decodeInstalledAppProto(reader.readBytes()));
        else if (field === 2 && wire === 2) result.activities.push(decodeInstalledAppActivityProto(reader.readBytes()));
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function decodeInstalledAppsDifferenceProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { added: null, removed_packages: [], removed_activities: [] };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.added = decodeInstalledAppsProto(reader.readBytes());
        else if (field === 2 && wire === 2) result.removed_packages.push(reader.readString());
        else if (field === 3 && wire === 2) result.removed_activities.push(decodeRemovedAppActivityProto(reader.readBytes()));
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function decodeSavedAppsDifferenceProto(bytes) {
    const reader = new ProtoReader(bytes);
    const result = { apps: null };
    while (!reader.eof()) {
        const tag = Number(reader.readVarint());
        const field = tag >> 3;
        const wire = tag & 7;
        if (field === 1 && wire === 2) result.apps = decodeInstalledAppsDifferenceProto(reader.readBytes());
        else if (wire === 2) reader.readBytes();
        else reader.readVarint();
    }
    return result;
}

function applyAppsDifference(base, diff) {
    const appsByPackage = new Map();
    const activitiesByKey = new Map();

    base.apps.forEach((app) => {
        if (app && app.package_name) appsByPackage.set(app.package_name, app);
    });
    base.activities.forEach((activity) => {
        const key = `${activity.package_name}::${activity.class_name}`;
        activitiesByKey.set(key, activity);
    });

    if (diff && diff.added) {
        diff.added.apps.forEach((app) => {
            if (app && app.package_name) appsByPackage.set(app.package_name, app);
        });
        diff.added.activities.forEach((activity) => {
            const key = `${activity.package_name}::${activity.class_name}`;
            activitiesByKey.set(key, activity);
        });
    }

    if (diff && Array.isArray(diff.removed_packages)) {
        diff.removed_packages.forEach((pkg) => {
            appsByPackage.delete(pkg);
        });
    }

    if (diff && Array.isArray(diff.removed_activities)) {
        diff.removed_activities.forEach((activity) => {
            const key = `${activity.package_name}::${activity.class_name}`;
            activitiesByKey.delete(key);
        });
    }

    return {
        apps: Array.from(appsByPackage.values()),
        activities: Array.from(activitiesByKey.values())
    };
}

async function decryptEncryptedAppsIfEnabled() {
    if (!isEncryptedAppsEnabled()) return;
    if (!window.crypto || !window.crypto.subtle) {
        setEncryptedAppsStatus({ error: 'webcrypto-not-available', updatedAt: Date.now() });
        if (typeof addLog === 'function') addLog('❌ WebCrypto niet beschikbaar voor decryptie.', true);
        return;
    }

    const encryptedCache = loadEncryptedAppsCache();
    const decryptedCache = loadDecryptedAppsCache();
    const keys = loadEncryptedAppsKeys();
    const status = { updatedAt: Date.now(), devices: {} };

    const deviceIds = Object.keys(encryptedCache || {});
    for (let i = 0; i < deviceIds.length; i += 1) {
        const deviceId = deviceIds[i];
        const entry = encryptedCache[deviceId];
        if (!entry) continue;

        const keyBase64 = keys[deviceId];
        if (!keyBase64) {
            status.devices[deviceId] = { ok: false, reason: 'missing-key' };
            continue;
        }

        const cached = decryptedCache[deviceId];
        const baseVersion = entry.appsBase && entry.appsBase.version ? entry.appsBase.version : null;
        const diffVersion = entry.appsDiff && entry.appsDiff.version ? entry.appsDiff.version : null;
        if (cached && cached.baseVersion === baseVersion && cached.diffVersion === diffVersion) {
            status.devices[deviceId] = { ok: true, cached: true };
            continue;
        }

        if (!entry.appsBase || !entry.appsBase.data) {
            status.devices[deviceId] = { ok: false, reason: 'missing-base' };
            continue;
        }

        try {
            const keyBytes = base64ToBytes(keyBase64);
            const baseDecrypted = await decryptCryptContainer(keyBytes, entry.appsBase.data);
            const baseInflated = await inflateDeflate(baseDecrypted);
            const baseApps = decodeInstalledAppsProto(baseInflated);

            let finalApps = baseApps;
            if (entry.appsDiff && entry.appsDiff.data) {
                const diffDecrypted = await decryptCryptContainer(keyBytes, entry.appsDiff.data);
                const diffInflated = await inflateDeflate(diffDecrypted);
                const savedDiff = decodeSavedAppsDifferenceProto(diffInflated);
                if (savedDiff && savedDiff.apps) {
                    finalApps = applyAppsDifference(baseApps, savedDiff.apps);
                }
            }

            decryptedCache[deviceId] = {
                baseVersion,
                diffVersion,
                updatedAt: Date.now(),
                apps: finalApps.apps,
                activities: finalApps.activities
            };
            status.devices[deviceId] = { ok: true, apps: finalApps.apps.length };
        } catch (e) {
            status.devices[deviceId] = { ok: false, reason: String(e && e.message ? e.message : e) };
        }
    }

    setDecryptedAppsCache(decryptedCache);
    setEncryptedAppsStatus(status);
}

window.decryptEncryptedAppsIfEnabled = decryptEncryptedAppsIfEnabled;
window.getDecryptedAppsCache = loadDecryptedAppsCache;
window.saveEncryptedAppsKey = saveEncryptedAppsKey;
window.removeEncryptedAppsKey = removeEncryptedAppsKey;
window.clearEncryptedAppsKeyInputs = clearEncryptedAppsKeyInputs;
window.initEncryptedAppsKeyPanel = initEncryptedAppsKeyPanel;
window.setDeviceListCache = setDeviceListCache;
window.saveParentKeyPair = saveParentKeyPair;
window.clearParentKeyPair = clearParentKeyPair;
window.clearParentKeyPairInputs = clearParentKeyPairInputs;
window.initParentKeyPairPanel = initParentKeyPairPanel;
window.setKeyRequestCache = setKeyRequestsCache;
window.setKeyRequestIndicator = setKeyRequestIndicator;
window.renderDeviceOverview = renderDeviceOverview;

function showStep(s) {
    const wizardUi = document.getElementById('wizard-ui');
    if (!wizardUi) return;

    wizardUi.style.display = s > 0 ? 'block' : 'none';
    const steps = document.querySelectorAll('.wizard-step');
    steps.forEach((el, idx) => el.style.display = (idx + 1 === s) ? 'block' : 'none');
}

function mergeRulesWithDisabled(rules, disabledList) {
    const byCategory = new Map();
    (rules || []).forEach((entry) => {
        const categoryId = String(entry.categoryId);
        const nextRules = Array.isArray(entry.rules) ? entry.rules.map(r => ({ ...r })) : [];
        byCategory.set(categoryId, { categoryId, rules: nextRules });
    });

    (disabledList || []).forEach((rule) => {
        if (!rule || !rule.categoryId || !rule.id) return;
        const categoryId = String(rule.categoryId);
        const entry = byCategory.get(categoryId) || { categoryId, rules: [] };
        const exists = entry.rules.some(r => String(r.id) === String(rule.id));
        if (!exists) {
            entry.rules.push({ ...rule, _disabled: true });
        }
        byCategory.set(categoryId, entry);
    });

    return Array.from(byCategory.values());
}

let lastRenderedUsersData = null;

function expandDisabledRulesForUser(userId) {
    const data = lastRenderedUsersData;
    if (!data || !userId) return;

    const disabledList = typeof getDisabledRules === 'function' ? getDisabledRules() : [];
    const scopedCategories = (data.categoryBase || []).filter(cat => String(cat.childId) === String(userId));
    const scopedCategoryIds = new Set(scopedCategories.map(cat => String(cat.categoryId)));
    if (scopedCategoryIds.size === 0) return;

    const disabledCategories = disabledList
        .map(rule => String(rule.categoryId))
        .filter(categoryId => scopedCategoryIds.has(categoryId));

    if (disabledCategories.length === 0) return;

    const uniqueCategoryIds = Array.from(new Set(disabledCategories));
    const sectionKeys = uniqueCategoryIds.map(categoryId => `${categoryId}::rules`);

    if (typeof storeOpenCategoryKey === 'function') {
        uniqueCategoryIds.forEach(categoryId => storeOpenCategoryKey(categoryId, true));
    }
    if (typeof storeOpenSectionKey === 'function') {
        sectionKeys.forEach(key => storeOpenSectionKey(key, true));
    }
    if (typeof restoreOpenCategoryIds === 'function') {
        restoreOpenCategoryIds(uniqueCategoryIds);
    }
    if (typeof restoreOpenSectionState === 'function') {
        restoreOpenSectionState(sectionKeys);
    }
}

function renderUsers(data) {
    lastRenderedUsersData = data;
    const list = document.getElementById('user-list');
    if (!list) return;

    if (!data || !data.users || !data.users.data || data.users.data.length === 0) {
        list.innerHTML = "<p style='color: #888;'>Geen gebruikers gevonden in deze familie.</p>";
        return;
    }

    const openCategoryIds = typeof getOpenCategoryIds === 'function' ? getOpenCategoryIds() : [];
    const persistedCategoryIds = typeof getPersistedOpenCategoryIds === 'function' ? getPersistedOpenCategoryIds() : [];
    const openSectionKeys = typeof getOpenSectionState === 'function' ? getOpenSectionState() : [];
    const persistedSectionKeys = typeof getPersistedOpenSectionKeys === 'function' ? getPersistedOpenSectionKeys() : [];
    const disabledList = typeof getDisabledRules === 'function' ? getDisabledRules() : [];
    const users = data.users.data;
    let html = "<div style='display:flex; flex-direction:column; gap:10px;'>";

    users.forEach(u => {
        const icon = u.type === 'parent' ? '🛡️' : '👤';
        const userName = escapeHtml(u.name || 'Onbekend');
        const userType = escapeHtml(u.type || 'onbekend');
        const userId = u.id || u.userId || '';
        const isParent = u.type === 'parent';
        const scopedCategories = (data.categoryBase || []).filter(cat => String(cat.childId) === String(userId));
        const scopedRules = mergeRulesWithDisabled(data.rules || [], disabledList);
        const scopedCategoryIds = new Set(scopedCategories.map(cat => String(cat.categoryId)));
        const hasDisabledRules = !isParent && scopedCategoryIds.size > 0
            ? disabledList.some(rule => scopedCategoryIds.has(String(rule.categoryId)))
            : false;
        const disabledBadge = hasDisabledRules
            ? `<button type="button" onclick="event.stopPropagation(); expandDisabledRulesForUser('${userId}')" style="margin-left:8px; padding:2px 6px; font-size:10px; border-radius:4px; background:#3a2400; color:#f7c35b; border:1px solid #6b4300; cursor:pointer;">Regel uit</button>`
            : "";
        const childTree = (!isParent && userId && typeof buildCategoryTree === 'function')
            ? buildCategoryTree({
                ...data,
                categoryBase: scopedCategories,
                rules: scopedRules
            })
            : [];
        let treeHtml = "<div style='color:#666;'>Geen categorieen gevonden.</div>";
        if (isParent) {
            treeHtml = "<div style='color:#666;'>Geen categorieen voor parent.</div>";
        } else if (!userId) {
            treeHtml = "<div style='color:#666;'>Geen childId gevonden voor deze gebruiker.</div>";
        } else if (childTree && childTree.length > 0 && typeof renderTreeHTML === 'function') {
            treeHtml = renderTreeHTML(childTree, 0, data);
        }

        const appIndexId = userId ? `app-index-${userId}` : '';
        const appSearchId = userId ? `app-index-search-${userId}` : '';
        const appListId = userId ? `app-index-list-${userId}` : '';
        const appIndexHtml = isParent
            ? "<div style='color:#666;'>App overzicht alleen voor child gebruikers.</div>"
            : userId
                ? `
                    <input type="text" id="${appSearchId}" placeholder="Zoek app of package..." class="app-index-search">
                    <div id="${appListId}" class="app-index-list">Wachtend op app data...</div>
                `
                : "<div style='color:#666;'>Geen childId voor app overzicht.</div>";

        html += `
            <div style='background: #151921; padding: 12px; border-radius: 6px; border-left: 3px solid #03a9f4;'>
                <div style='display:flex; align-items:center; gap:8px; margin-bottom: 8px;'>
                    <div>${icon}</div>
                    <div>
                        <strong>${userName}</strong>${disabledBadge}
                        <span style='color: #888; font-size: 0.8em;'>(${userType})</span>
                    </div>
                </div>
                <div class='tree-container' style='padding: 8px; background:#0f141b; border:1px solid #1b232c; border-radius:6px;'>
                    ${treeHtml}
                </div>
                <details style="margin-top: 10px;">
                    <summary style="cursor:pointer; font-size: 11px; color: #8ab4f8; text-transform: uppercase;">App Overzicht</summary>
                    <div id="${appIndexId}" class="tree-container app-index-container" style="margin-top: 6px; padding: 8px; background:#0f141b; border:1px solid #1b232c; border-radius:6px;">
                        ${appIndexHtml}
                    </div>
                </details>
            </div>
        `;
    });

    html += "</div>";
    list.innerHTML = html;

    if (typeof restoreOpenCategoryIds === 'function') {
        const mergedIds = Array.from(new Set([...(openCategoryIds || []), ...(persistedCategoryIds || [])]));
        restoreOpenCategoryIds(mergedIds);
    }
    if (typeof restoreOpenSectionState === 'function') {
        const mergedSections = Array.from(new Set([...(openSectionKeys || []), ...(persistedSectionKeys || [])]));
        restoreOpenSectionState(mergedSections);
    }

    if (typeof buildAppIndex === 'function') {
        users.forEach(u => {
            if (u.type === 'parent') return;
            const userId = u.id || u.userId || '';
            if (!userId) return;

            const input = document.getElementById(`app-index-search-${userId}`);
            const listEl = document.getElementById(`app-index-list-${userId}`);
            if (!listEl) return;

            const filteredCategories = (data.categoryBase || []).filter(cat => String(cat.childId) === String(userId));
            const categoryIds = new Set(filteredCategories.map(cat => cat.categoryId));
            const filteredApps = (data.categoryApp || []).filter(entry => categoryIds.has(entry.categoryId));
            const items = buildAppIndex({
                ...data,
                categoryBase: filteredCategories,
                categoryApp: filteredApps
            });

            const renderList = (query) => {
                const normalized = (query || '').trim().toLowerCase();
                const filtered = normalized
                    ? items.filter(item => {
                        const catText = item.categories.join(' ').toLowerCase();
                        return item.readableName.toLowerCase().includes(normalized)
                            || item.packageName.toLowerCase().includes(normalized)
                            || catText.includes(normalized);
                    })
                    : items;

                if (filtered.length === 0) {
                    listEl.innerHTML = '<div class="app-index-item">Geen apps gevonden.</div>';
                    return;
                }

                listEl.innerHTML = filtered.map(item => {
                    const categoriesText = item.categories.length > 0 ? item.categories.join(', ') : '(geen categorie)';
                    return `
                        <div class="app-index-item">
                            <span class="app-index-name">${escapeHtml(item.readableName)}</span>
                            <span class="app-index-package">${escapeHtml(item.packageName)}</span>
                            <span class="app-index-categories">${escapeHtml(categoriesText)}</span>
                        </div>
                    `;
                }).join('');
            };

            renderList(input ? input.value : '');

            if (input) {
                input.oninput = () => renderList(input.value);
            }
        });
    }

    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

window.expandDisabledRulesForUser = expandDisabledRulesForUser;

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
    const createdRules = typeof getNewRules === 'function' ? getNewRules() : [];
    const deletedRules = typeof getDeletedRules === 'function' ? getDeletedRules() : [];
    const newCategoryApps = typeof getNewCategoryApps === 'function' ? getNewCategoryApps() : [];
    const removedCategoryApps = typeof getRemovedCategoryApps === 'function' ? getRemovedCategoryApps() : [];
    
    console.log("[DEBUG] showChangesSummary() aangeroepen. Aantal wijzigingen:", changes.length);
    
    if (
        changes.length === 0
        && createdRules.length === 0
        && deletedRules.length === 0
        && newCategoryApps.length === 0
        && removedCategoryApps.length === 0
    ) {
        alert('❌ Geen wijzigingen aangebracht.');
        console.log("[DEBUG] Geen wijzigingen gevonden!");
        return;
    }

    const totalChanges = changes.length
        + createdRules.length
        + deletedRules.length
        + newCategoryApps.length
        + removedCategoryApps.length;

    const getCategoryTitle = (catId) => {
        let catTitle = catId;
        try {
            if (typeof currentDataDraft !== 'undefined' && currentDataDraft && currentDataDraft.categoryBase) {
                const cat = currentDataDraft.categoryBase.find(c => c.categoryId == catId);
                if (cat && cat.title) catTitle = cat.title;
            }
        } catch (e) {
            console.warn('[DEBUG] kon categorie-naam niet ophalen', e);
        }
        return catTitle;
    };
    let html = `<div class="changes-summary">
        <h3>📋 Wijzigingen (${totalChanges})</h3>
        <ul>`;

    changes.forEach(change => {
        const catId = change.categoryId;
        const ruleId = change.ruleId;
        const original = change.original;
        const current = change.current;

        // Zoek de categorie-naam (title) op uit de huidige data snapshot
        let catTitle = getCategoryTitle(catId);

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

    createdRules.forEach((rule) => {
        const catId = rule.categoryId;
        const ruleId = rule.id;
        let catTitle = getCategoryTitle(catId);

        const details = [];
        if (rule.maxTime !== undefined) {
            details.push(`Limiet: ${formatDuration(rule.maxTime)}`);
        }
        if (rule.start !== undefined && rule.end !== undefined) {
            details.push(`Tijd: ${formatClockTime(rule.start)}-${formatClockTime(rule.end)}`);
        }
        if (rule.dayMask !== undefined) {
            details.push(`Dagen: ${formatDays(rule.dayMask)}`);
        }
        if (rule.perDay !== undefined) {
            details.push(`Per dag: ${rule.perDay ? 'ja' : 'nee'}`);
        }

        html += `<li>
            <strong>Nieuwe regel ${ruleId}</strong> (Categorie: ${catTitle})
            <div class="change-detail">${details.length > 0 ? details.join(' | ') : 'Nieuwe regel'}</div>
        </li>`;
    });

    deletedRules.forEach((item) => {
        if (!item) return;
        const catId = item.categoryId;
        const ruleId = item.ruleId;
        const catTitle = getCategoryTitle(catId);
        html += `<li>
            <strong>Verwijderde regel ${ruleId}</strong> (Categorie: ${catTitle})
            <div class="change-detail">Wordt verwijderd bij volgende sync</div>
        </li>`;
    });

    if (newCategoryApps.length > 0) {
        const byCategory = new Map();
        newCategoryApps.forEach((item) => {
            if (!item) return;
            const key = String(item.categoryId);
            if (!byCategory.has(key)) byCategory.set(key, []);
            byCategory.get(key).push(String(item.packageName));
        });
        byCategory.forEach((packages, catId) => {
            const catTitle = getCategoryTitle(catId);
            html += `<li>
                <strong>Apps toegevoegd</strong> (Categorie: ${catTitle})
                <div class="change-detail">${packages.join(', ')}</div>
            </li>`;
        });
    }

    if (removedCategoryApps.length > 0) {
        const byCategory = new Map();
        removedCategoryApps.forEach((item) => {
            if (!item) return;
            const key = String(item.categoryId);
            if (!byCategory.has(key)) byCategory.set(key, []);
            byCategory.get(key).push(String(item.packageName));
        });
        byCategory.forEach((packages, catId) => {
            const catTitle = getCategoryTitle(catId);
            html += `<li>
                <strong>Apps verwijderd</strong> (Categorie: ${catTitle})
                <div class="change-detail">${packages.join(', ')}</div>
            </li>`;
        });
    }

    html += `</ul>
        <button class="btn reset-changes-btn" style="width: 100%; margin-top: 10px;" onclick="resetAllChanges(); location.reload();">↶ Wijzigingen ongedaan maken</button>
    </div>`;

    const container = document.getElementById('category-tree-container');
    if (container) {
        // Verwijder eerdere samenvatting als deze al bestaat
        const existing = container.parentElement.querySelector('.changes-summary');
        if (existing) existing.remove();
        
        container.insertAdjacentHTML('beforebegin', html);
        addLog(`✏️ ${totalChanges} wijziging${totalChanges !== 1 ? 'en' : ''} gedetecteerd!`);
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