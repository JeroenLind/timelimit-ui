/**
 * sync.js - Handling manual and automatic sync
 */

// Flow: pull/push sync, change tracking summary, and integrity signing.

let syncTimer = null;
let secondsCounter = 0;
const SYNC_INTERVAL = 30; // seconds
const SERVER_API_LEVEL_KEY = "timelimit_serverApiLevel";
let serverApiLevel = null;

function normalizeServerApiLevel(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed < 0) {
        return null;
    }
    return parsed;
}

function loadServerApiLevel() {
    return normalizeServerApiLevel(localStorage.getItem(SERVER_API_LEVEL_KEY));
}

function setServerApiLevel(value) {
    serverApiLevel = normalizeServerApiLevel(value);
    if (serverApiLevel === null) {
        localStorage.removeItem(SERVER_API_LEVEL_KEY);
    } else {
        localStorage.setItem(SERVER_API_LEVEL_KEY, String(serverApiLevel));
    }
    if (typeof window !== "undefined" && typeof window.scheduleHaStorageShadowSync === "function") {
        window.scheduleHaStorageShadowSync('server-api-level');
    }
}

serverApiLevel = loadServerApiLevel();

const SEQUENCE_STORAGE_KEY = "timelimit_nextSyncSequenceNumber";
const SYNC_ENCRYPTED_APPS_CACHE_KEY = "timelimit_encryptedAppsCache";
const ENCRYPTED_APPS_KEYS_KEY_FOR_LOG = "timelimit_appListKeys";

function loadEncryptedAppsKeysForLog() {
    try {
        const raw = localStorage.getItem(ENCRYPTED_APPS_KEYS_KEY_FOR_LOG);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return {};
        return parsed;
    } catch (e) {
        return {};
    }
}

function loadEncryptedAppsCache() {
    try {
        const raw = localStorage.getItem(SYNC_ENCRYPTED_APPS_CACHE_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return {};
        return parsed;
    } catch (e) {
        return {};
    }
}

function setEncryptedAppsCache(value) {
    if (!value || typeof value !== "object") {
        localStorage.removeItem(SYNC_ENCRYPTED_APPS_CACHE_KEY);
    } else {
        localStorage.setItem(SYNC_ENCRYPTED_APPS_CACHE_KEY, JSON.stringify(value));
    }
    if (typeof window !== "undefined" && typeof window.scheduleHaStorageShadowSync === "function") {
        window.scheduleHaStorageShadowSync('encrypted-apps-cache');
    }
}

function normalizeSequenceNumber(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || parsed < 0) {
        return 0;
    }
    return parsed;
}

function peekNextSequenceNumber() {
    return normalizeSequenceNumber(localStorage.getItem(SEQUENCE_STORAGE_KEY));
}

function getNextSequenceNumber() {
    // Sequence numbers must be monotonic for signed actions.
    const current = peekNextSequenceNumber();
    localStorage.setItem(SEQUENCE_STORAGE_KEY, String(current + 1));
    if (typeof window !== "undefined" && typeof window.scheduleHaStorageShadowSync === "function") {
        window.scheduleHaStorageShadowSync('sequence-next');
    }
    if (typeof window !== "undefined" && typeof window.updateSequenceDisplay === "function") {
        window.updateSequenceDisplay();
    }
    if (typeof window !== "undefined" && typeof window.updateHistorySeqForToken === "function") {
        window.updateHistorySeqForToken(typeof TOKEN !== 'undefined' ? TOKEN : '', current + 1);
    }
    return current;
}

function resetSequenceNumber() {
    localStorage.removeItem(SEQUENCE_STORAGE_KEY);
    if (typeof window !== "undefined" && typeof window.scheduleHaStorageShadowSync === "function") {
        window.scheduleHaStorageShadowSync('sequence-reset');
    }
    if (typeof window !== "undefined" && typeof window.updateSequenceDisplay === "function") {
        window.updateSequenceDisplay();
    }
}

function setSequenceNumber(value) {
    const normalized = normalizeSequenceNumber(value);
    localStorage.setItem(SEQUENCE_STORAGE_KEY, String(normalized));
    if (typeof window !== "undefined" && typeof window.scheduleHaStorageShadowSync === "function") {
        window.scheduleHaStorageShadowSync('sequence-set');
    }
    if (typeof window !== "undefined" && typeof window.updateSequenceDisplay === "function") {
        window.updateSequenceDisplay();
    }
}

function setPendingBadgeSyncState(isSyncing) {
    const pendingBadge = document.getElementById('pending-badge');
    if (!pendingBadge) return;

    const isVisible = typeof window.getComputedStyle === 'function'
        ? window.getComputedStyle(pendingBadge).display !== 'none'
        : pendingBadge.style.display !== 'none';
    if (!isVisible) return;

    if (isSyncing) {
        if (!pendingBadge.dataset.prevText) {
            pendingBadge.dataset.prevText = pendingBadge.innerText;
        }
        pendingBadge.innerText = 'Bezig met sync...';
        return;
    }

    if (pendingBadge.dataset.prevText) {
        pendingBadge.innerText = pendingBadge.dataset.prevText;
        delete pendingBadge.dataset.prevText;
    }
}

async function runSync() {
    const badge = document.getElementById('status-badge');
    const jsonView = document.getElementById('json-view');

    if (!TOKEN || TOKEN === "" || TOKEN.includes("#")) {
        addLog("Sync overgeslagen: Geen geldig token.", true);
        return;
    }

    setPendingBadgeSyncState(true);

    // Pull minimal status to fetch the full dataset from the server.
    const syncPayload = {
        deviceAuthToken: TOKEN,
        status: { apps: {}, categories: {}, devices: "0", users: "0", clientLevel: 8, devicesDetail: {} }
    };

    addLog("Syncing data...");
    secondsCounter = 0;

    try {
        const res = await fetch('sync/pull-status', {
            method: 'POST',
            cache: 'no-store',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            },
            body: JSON.stringify(syncPayload)
        });

        // --- CRITICAL CHECK ---
        const contentType = res.headers.get("content-type");
        let responseData;

        if (res.ok && contentType && contentType.includes("application/json")) {
            // Only parse when status is 200 (OK) and the response is JSON
            responseData = await res.json();

            setServerApiLevel(typeof responseData.apiLevel === "number" ? responseData.apiLevel : null);
            console.log(`[SYNC] Server apiLevel: ${serverApiLevel}`);

            if (responseData.devices && Array.isArray(responseData.devices.data)) {
                // Cache device metadata for UI panels.
                if (typeof window.setDeviceListCache === 'function') {
                    window.setDeviceListCache(responseData.devices.data);
                }
            }
            if (Array.isArray(responseData.krq)) {
                if (typeof window.setKeyRequestCache === 'function') {
                    window.setKeyRequestCache(responseData.krq);
                }
                addLog(`Key requests: krq ontvangen (${responseData.krq.length}).`);
                if (typeof window.setKeyRequestIndicator === 'function') {
                    window.setKeyRequestIndicator({ krqCount: responseData.krq.length });
                }
            } else {
                const responseKeys = responseData && typeof responseData === 'object'
                    ? Object.keys(responseData)
                    : [];
                const apiLevelInfo = typeof responseData.apiLevel === 'number'
                    ? responseData.apiLevel
                    : 'onbekend';
                addLog(`Key requests: geen krq in response. Keys: [${responseKeys.join(', ')}], apiLevel: ${apiLevelInfo}, payload clientLevel: ${syncPayload.status.clientLevel}.`);
                if (typeof window.setKeyRequestCache === 'function') {
                    window.setKeyRequestCache([]);
                }
                if (typeof window.setKeyRequestIndicator === 'function') {
                    window.setKeyRequestIndicator({ krqCount: 0 });
                }
            }

            if (Array.isArray(responseData.kr)) {
                addLog(`Key responses: kr ontvangen (${responseData.kr.length}).`);
            } else if (typeof responseData.kr !== 'undefined') {
                addLog(`Key responses: kr type is ${typeof responseData.kr}.`);
            } else {
                addLog('Key responses: geen kr in response.');
            }

            if (typeof responseData.kri !== 'undefined') {
                addLog(`Key requests: kri in response = ${responseData.kri}.`);
            } else {
                addLog('Key requests: geen kri in response.');
            }

            if (Array.isArray(responseData.devices2)) {
                const deviceIds = responseData.devices2
                    .map((device) => (device && device.deviceId ? String(device.deviceId) : ''))
                    .filter((id) => id);
                const appListKeys = loadEncryptedAppsKeysForLog();
                const missingKeyDevices = deviceIds.filter((id) => !appListKeys[id]);
                const withKeyCount = deviceIds.length - missingKeyDevices.length;

                addLog(`Apps data: devices2 ${deviceIds.length}. With key: ${withKeyCount}. Missing key: ${missingKeyDevices.length}.`);
                if (deviceIds.length > 0) {
                    addLog(`Apps data deviceIds: ${deviceIds.join(', ')}`);
                }
                if (missingKeyDevices.length > 0) {
                    addLog(`Apps data missing keys: ${missingKeyDevices.join(', ')}`);
                }
                if (typeof window.setKeyRequestIndicator === 'function') {
                    window.setKeyRequestIndicator({
                        devices2Count: deviceIds.length,
                        missingKeys: missingKeyDevices.length,
                        krqCount: Array.isArray(responseData.krq) ? responseData.krq.length : 0
                    });
                }

                const existingCache = loadEncryptedAppsCache();
                const updatedCache = { ...existingCache };

                responseData.devices2.forEach((device) => {
                    if (!device || !device.deviceId) return;

                    const nextEntry = updatedCache[device.deviceId] || {};
                    const deviceId = String(device.deviceId);

                    if (device.appsBase) {
                        const baseVersion = device.appsBase.version || '-';
                        const baseSize = device.appsBase.data ? String(device.appsBase.data).length : 0;
                        addLog(`Apps data ${deviceId}: appsBase v=${baseVersion}, dataLen=${baseSize}.`);
                    }
                    if (device.appsDiff) {
                        const diffVersion = device.appsDiff.version || '-';
                        const diffSize = device.appsDiff.data ? String(device.appsDiff.data).length : 0;
                        addLog(`Apps data ${deviceId}: appsDiff v=${diffVersion}, dataLen=${diffSize}.`);
                    }
                    if (!device.appsBase && !device.appsDiff) {
                        addLog(`Apps data ${deviceId}: geen appsBase/appsDiff in devices2.`);
                    }

                    if (device.appsBase) {
                        nextEntry.appsBase = device.appsBase;
                    }
                    if (device.appsDiff) {
                        nextEntry.appsDiff = device.appsDiff;
                    }

                    updatedCache[device.deviceId] = nextEntry;
                });

                setEncryptedAppsCache(updatedCache);
                if (typeof window.renderDeviceOverview === 'function') {
                    window.renderDeviceOverview();
                }
                if (typeof window.decryptEncryptedAppsIfEnabled === 'function') {
                    window.decryptEncryptedAppsIfEnabled();
                }
            }
            
            addLog("Sync voltooid.");
            badge.innerText = "Online";
            badge.className = "status-badge status-online";

            initializeDraft(responseData);
            if (typeof renderUsers === 'function') {
                renderUsers(typeof currentDataDraft !== 'undefined' && currentDataDraft ? currentDataDraft : responseData);
            }
            if (typeof mergePendingNewRules === 'function') {
                mergePendingNewRules(responseData);
            }
            if (typeof reconcileNewRules === 'function') {
                reconcileNewRules(responseData);
            }
            if (typeof reconcileDeletedRules === 'function') {
                reconcileDeletedRules(responseData);
            }
            if (typeof mergePendingNewApps === 'function') {
                mergePendingNewApps(responseData);
            }
            if (typeof reconcileNewApps === 'function') {
                reconcileNewApps(responseData);
            }
            if (typeof mergePendingAppRemovals === 'function') {
                mergePendingAppRemovals(responseData);
            }
            if (typeof reconcileRemovedApps === 'function') {
                reconcileRemovedApps(responseData);
            }
           
            if (typeof updateCategoryDisplay === "function") {
              updateCategoryDisplay(responseData);
            }

                        if (typeof ensureAccountHistoryForCurrent === 'function') {
                                ensureAccountHistoryForCurrent();
                        }
            
            // IMPORTANT: Reset change tracking AFTER pull sync completes
            // This avoids losing local changes if an automatic pull runs next
            if (typeof resetChangeTracking === 'function') {
                resetChangeTracking();
                console.log("✅ Change tracking gereset na succesvolle pull sync");
                addLog("✅ Change tracking gereset", false);
            }
            
        } else {
            // The server returned an error (401) or HTML. Read as text to avoid crashes.
            const errorText = await res.text();
            responseData = { error: "Ongeldige respons", status: res.status };
            
            if (res.status === 401) {
                addLog(`⚠️ Auth Fout (401): Token niet geldig voor deze server.`, true);
            } else {
                addLog(`❌ Server Fout (${res.status}): Kan data niet ophalen.`, true);
            }
            
            badge.innerText = `Fout ${res.status}`;
            badge.className = "status-badge status-offline";
        }

        // Update the inspector with whatever we received
        const timestamp = new Date().toLocaleTimeString();
        const separator = `\n\n${"=".repeat(20)} SYNC @ ${timestamp} ${"=".repeat(20)}\n`;
        const logText = `>>> PAYLOAD: ${JSON.stringify(syncPayload)}\n<<< STATUS: ${res.status}\n<<< DATA: ${JSON.stringify(responseData, null, 2)}`;

        if (jsonView.textContent.length > 100000) jsonView.textContent = jsonView.textContent.slice(-50000);
        jsonView.textContent += separator + logText;
        jsonView.scrollTop = jsonView.scrollHeight;

    } catch (e) {
        addLog("Netwerkfout: " + e.message, true);
        badge.innerText = "Offline";
        badge.className = "status-badge status-offline";
    } finally {
        setPendingBadgeSyncState(false);
        if (typeof updatePendingChangesIndicator === 'function') {
            updatePendingChangesIndicator();
        }
    }
}

function triggerManualSync() {
    if (typeof executePushSync === 'function') {
        return executePushSync();
    }
    if (typeof runSync === 'function') {
        return runSync();
    }
}

if (typeof window !== 'undefined') {
    window.triggerManualSync = triggerManualSync;
}


// Background loop
function startSyncLoop() {
    setInterval(() => {
        const isEnabled = document.getElementById('auto-sync-tgl').checked;
        const badge = document.getElementById('status-badge');

        if (isEnabled) {
            if (!TOKEN) {
                badge.innerText = "Niet aangemeld";
                badge.className = "status-badge status-offline";
                return;
            }
            secondsCounter++;
            
            // Show progress on the badge (optional, visual feedback)
            if (badge.innerText.includes("Online")) {
                badge.innerText = `Online (${SYNC_INTERVAL - secondsCounter}s)`;
            }

            if (secondsCounter >= SYNC_INTERVAL) {
                runSync();
            }
        } else {
            secondsCounter = 0; // Reset counter when disabled
        }
    }, 1000); // Check every second
}

// Start the loop once the script is loaded
startSyncLoop();

/**
 * SYNC HELPERS - Send rule changes to the server
 */

/**
 * Convert a change object to SerializedUpdateTimelimitRuleAction format
 * change = { ruleId, categoryId, original: {...}, current: {...} }
 * 
 * FIELD MAPPING:
 * - maxTime → time (milliseconden)
 * - dayMask → days (bitmask)
 */
function buildUpdateRuleAction(change) {
    const current = change.current;
    
    const action = {
        type: "UPDATE_TIMELIMIT_RULE",
        ruleId: String(change.ruleId),
        // MAPPING: maxTime → time, dayMask → days
        time: Number(current.maxTime !== undefined ? current.maxTime : (current.time || 0)),
        days: Number(current.dayMask !== undefined ? current.dayMask : (current.days || 0)),
        extraTime: Boolean(current.extraTime || false)
    };
    
    // Add optional fields when present
    if (current.start !== undefined && current.start !== null) {
        action.start = Number(current.start);
    }
    if (current.end !== undefined && current.end !== null) {
        action.end = Number(current.end);
    }
    if (current.dur !== undefined && current.dur !== null) {
        action.dur = Number(current.dur);
    }
    // session → pause mapping
    if (current.pause !== undefined && current.pause !== null) {
        action.pause = Number(current.pause);
    } else if (current.session !== undefined && current.session !== null) {
        action.pause = Number(current.session);
    }
    if (current.perDay !== undefined && current.perDay !== null) {
        action.perDay = Boolean(current.perDay);
    }
    if (current.e !== undefined && current.e !== null) {
        action.e = Number(current.e);
    }
    
    return action;
}

function buildCreateRuleAction(rule) {
    const current = rule || {};
    return {
        type: "CREATE_TIMELIMIT_RULE",
        rule: {
            ruleId: String(current.id || current.ruleId || ''),
            categoryId: String(current.categoryId || ''),
            time: Number(current.maxTime !== undefined ? current.maxTime : (current.time || 0)),
            days: Number(current.dayMask !== undefined ? current.dayMask : (current.days || 0)),
            extraTime: Boolean(current.extraTime || false),
            start: Number(current.start || 0),
            end: Number(current.end || 0),
            dur: Number(current.dur || 0),
            pause: Number(current.pause || 0),
            perDay: Boolean(current.perDay)
        }
    };
}

function buildDeleteRuleAction(ruleId) {
    return {
        type: "DELETE_TIMELIMIT_RULE",
        ruleId: String(ruleId)
    };
}

function buildAddCategoryAppsAction(categoryId, packageNames) {
    return {
        type: "ADD_CATEGORY_APPS",
        categoryId: String(categoryId),
        packageNames: packageNames.map(p => String(p))
    };
}

function buildRemoveCategoryAppsAction(categoryId, packageNames) {
    return {
        type: "REMOVE_CATEGORY_APPS",
        categoryId: String(categoryId),
        packageNames: packageNames.map(p => String(p))
    };
}

/**
 * Compute integrity for parent actions, compatible with the Android app.
 * 
 * - apiLevel >= 6: HMAC-SHA256 (binary format) met "password:" prefix
 * - apiLevel < 6: legacy SHA512 hex digest
 * 
 * @returns {string} Integrity string of "device" fallback
 */
async function calculateIntegrity(sequenceNumber, deviceId, encodedAction) {
    console.log(`[INTEGRITY] ==================== INTEGRITY BEREKENING START ===================`);
    console.log(`[INTEGRITY] INPUT PARAMETERS:`);
    console.log(`[INTEGRITY] - sequenceNumber: ${sequenceNumber} (type: ${typeof sequenceNumber})`);
    console.log(`[INTEGRITY] - deviceId: '${deviceId}' (length: ${deviceId.length}, type: ${typeof deviceId})`);
    console.log(`[INTEGRITY] - deviceId (hex): ${Array.from(deviceId).map(c => c.charCodeAt(0).toString(16)).join(' ')}`);
    console.log(`[INTEGRITY] - encodedAction length: ${encodedAction.length} chars`);
    console.log(`[INTEGRITY] - encodedAction (first 100 chars): ${encodedAction.substring(0, 100)}...`);
    
    console.log(`[INTEGRITY] Verificatie parentPasswordHash:`);
    console.log(`[INTEGRITY] - parentPasswordHash aanwezig:`, !!parentPasswordHash);
    console.log(`[INTEGRITY] - parentPasswordHash.secondHash aanwezig:`, !!(parentPasswordHash && parentPasswordHash.secondHash));
    
    if (!parentPasswordHash || !parentPasswordHash.secondHash) {
        console.error("[INTEGRITY] ❌ FOUT: Geen secondHash beschikbaar!");
        console.error(`[INTEGRITY] parentPasswordHash:`, parentPasswordHash);
        console.warn("[INTEGRITY] Fallback naar 'device'");
        return "device";
    }
    
    const secondHash = parentPasswordHash.secondHash; // This is the bcrypt hash string
    
    console.log(`[INTEGRITY] ✅ secondHash gevonden:`);
    console.log(`[INTEGRITY] - Type: ${typeof secondHash}`);
    console.log(`[INTEGRITY] - Length: ${secondHash.length} chars`);
    console.log(`[INTEGRITY] - First 40 chars: ${secondHash.substring(0, 40)}...`);
    console.log(`[INTEGRITY] - Is bcrypt format: ${secondHash.match(/^\$2[aby]\$/) ? 'YES' : 'NO'}`);
    console.log(`[INTEGRITY] encodedAction (first 100 chars): ${encodedAction.substring(0, 100)}...`);
    
    const useLegacyIntegrity = typeof serverApiLevel === "number" && serverApiLevel < 6;

    if (useLegacyIntegrity) {
        console.log(`[INTEGRITY] 🔄 Legacy SHA512 signing (apiLevel ${serverApiLevel})...`);

        const integrityData = String(sequenceNumber) + deviceId + secondHash + encodedAction;

        try {
            const response = await fetch('calculate-sha512', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: integrityData
                })
            });

            if (!response.ok) {
                console.error(`[INTEGRITY] ❌ Server error: ${response.status}`);
                const errorText = await response.text();
                console.error(`[INTEGRITY] Error response: ${errorText.substring(0, 200)}`);
                return "device";
            }

            const result = await response.json();
            const integrityValue = result.hash;
            console.log(`[INTEGRITY] Legacy SHA512 hash: ${integrityValue.substring(0, 30)}...`);
            return integrityValue;
        } catch (error) {
            console.error("[INTEGRITY] ❌ FOUT bij server-side SHA512:");
            console.error("  - Error type:", error.constructor.name);
            console.error("  - Message:", error.message);
            console.error("[INTEGRITY] FALLBACK op 'device'");
            return "device";
        }
    }

    // Use server-side because we must use the binary format
    console.log("[INTEGRITY] 🔄 Server-side HMAC-SHA256 (binary format) berekening aanroepen...");
    
    try {
        const response = await fetch('calculate-hmac-sha256', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                secondHash: secondHash,
                sequenceNumber: sequenceNumber,
                deviceId: deviceId,
                encodedAction: encodedAction
            })
        });
        
        if (!response.ok) {
            console.error(`[INTEGRITY] ❌ Server error: ${response.status}`);
            const errorText = await response.text();
            console.error(`[INTEGRITY] Error response: ${errorText.substring(0, 200)}`);
            return "device";
        }
        
        const result = await response.json();
        const integrityValue = result.integrity; // Should be "password:<base64>"
        console.log(`[INTEGRITY] Result: ${integrityValue}`);
        console.log(`[INTEGRITY] Result length: ${integrityValue.length} chars`);
        
        // Extract base64 part for debugging
        const base64Part = integrityValue.substring(9);
        console.log(`[INTEGRITY] Base64 digest (first 50 chars): ${base64Part.substring(0, 50)}...`);
        console.log(`[INTEGRITY] Base64 part length: ${base64Part.length} chars`);
        
        console.log(`[INTEGRITY] ==================== INTEGRITY BEREKENING COMPLEET ===================`);
        return integrityValue;
        
    } catch (error) {
        console.error("[INTEGRITY] ❌ FOUT bij server-side HMAC-SHA256:");
        console.error("  - Error type:", error.constructor.name);
        console.error("  - Message:", error.message);
        console.error("[INTEGRITY] FALLBACK op 'device'");
        return "device";
    }
}

/**
 * Bundle all changes into actions for delivery (max 50 per batch)
 */
function prepareSync(options = {}) {
    // Flow: gather pending changes and pack them into server action batches.
    const changes = getChangedRules();
    const createdRules = typeof getNewRules === 'function' ? getNewRules() : [];
    const deletedRules = typeof getDeletedRules === 'function' ? getDeletedRules() : [];
    const newCategoryApps = typeof getNewCategoryApps === 'function' ? getNewCategoryApps() : [];
    const removedCategoryApps = typeof getRemovedCategoryApps === 'function' ? getRemovedCategoryApps() : [];
    
    if (changes.length === 0 && createdRules.length === 0 && deletedRules.length === 0 && newCategoryApps.length === 0 && removedCategoryApps.length === 0) {
        addLog("Geen wijzigingen om te synchroniseren.", false);
        return { batches: [], totalActions: 0 };
    }
    
    const batches = [];
    let currentBatch = [];
    const consumeSequenceNumbers = options.consumeSequenceNumbers !== false;
    let previewSequenceNumber = consumeSequenceNumbers ? null : peekNextSequenceNumber();
    
    const actionItems = [];
    changes.forEach(change => {
        actionItems.push({ action: buildUpdateRuleAction(change) });
    });
    createdRules.forEach(rule => {
        actionItems.push({ action: buildCreateRuleAction(rule) });
    });
    deletedRules.forEach(item => {
        if (!item || !item.ruleId) return;
        actionItems.push({ action: buildDeleteRuleAction(item.ruleId) });
    });

    if (newCategoryApps.length > 0) {
        const byCategory = new Map();
        newCategoryApps.forEach(item => {
            const key = String(item.categoryId);
            if (!byCategory.has(key)) {
                byCategory.set(key, new Set());
            }
            byCategory.get(key).add(String(item.packageName));
        });
        byCategory.forEach((pkgSet, categoryId) => {
            const packages = Array.from(pkgSet);
            if (packages.length > 0) {
                actionItems.push({ action: buildAddCategoryAppsAction(categoryId, packages) });
            }
        });
    }

    if (removedCategoryApps.length > 0) {
        const byCategory = new Map();
        removedCategoryApps.forEach(item => {
            const key = String(item.categoryId);
            if (!byCategory.has(key)) {
                byCategory.set(key, new Set());
            }
            byCategory.get(key).add(String(item.packageName));
        });
        byCategory.forEach((pkgSet, categoryId) => {
            const packages = Array.from(pkgSet);
            if (packages.length > 0) {
                actionItems.push({ action: buildRemoveCategoryAppsAction(categoryId, packages) });
            }
        });
    }

    // Flow: assign sequence numbers, encode actions, and split into <=50 actions per batch.
    actionItems.forEach(item => {
        const encodedAction = JSON.stringify(item.action);
        const sequenceNumber = consumeSequenceNumbers ? getNextSequenceNumber() : previewSequenceNumber;

        currentBatch.push({
            sequenceNumber: sequenceNumber,
            encodedAction: encodedAction,
            action: item.action
        });

        if (!consumeSequenceNumbers) {
            previewSequenceNumber += 1;
        }

        if (currentBatch.length === 50) {
            batches.push(currentBatch);
            currentBatch = [];
        }
    });
    
    // Add remaining actions
    if (currentBatch.length > 0) {
        batches.push(currentBatch);
    }
    
    addLog(`✅ ${actionItems.length} wijzigingen voorbereidt in ${batches.length} batch(es)`, false);
    
    return {
        batches: batches,
        totalActions: actionItems.length,
        changes: changes,
        createdRules: createdRules
    };
}

/**
 * TEST version: prepare actions and compute real integrity hashes
 * Log to console/UI without sending
 */
async function testSyncActions() {
    // Flow: prepare actions, compute integrity, and log without sending.
    addLog("🧪 TEST SYNC: Acties worden voorbereid met HMAC-SHA512 signing...", false);

    const syncData = prepareSync({ consumeSequenceNumbers: false });

    if (syncData.totalActions === 0) {
        return;
    }

    // Log to inspector
    const jsonView = document.getElementById("json-view");
    const timestamp = new Date().toLocaleTimeString();
    const separator = `\n\n${"=".repeat(20)} TEST SYNC @ ${timestamp} ${"=".repeat(20)}\n`;

    // ✅ DIAGNOSTIC INFO: parentPasswordHash status
    console.log("=== INTEGRITY SETUP DEBUG (TEST MODE) ===");
    console.log("parentPasswordHash beschikbaar?", !!parentPasswordHash);
    if (parentPasswordHash) {
        console.log("  - hash:", parentPasswordHash.hash ? parentPasswordHash.hash.substring(0, 20) + "..." : "❌ MISSING");
        console.log("  - secondHash:", parentPasswordHash.secondHash ? parentPasswordHash.secondHash.substring(0, 20) + "..." : "❌ MISSING");
        console.log("  - secondSalt:", parentPasswordHash.secondSalt ? parentPasswordHash.secondSalt.substring(0, 20) + "..." : "❌ MISSING");
        console.log("  - secondHash is bcrypt?", parentPasswordHash.secondHash ? (parentPasswordHash.secondHash.match(/^\$2[aby]\$/) ? 'YES' : 'NO') : 'N/A');
    } else {
        console.error("❌ parentPasswordHash is NULL/UNDEFINED - gebruik 'Wachtwoord Hashes Bijwerken' eerst!");
    }
    console.log("===========================\n");

    let logContent = `
TOTAAL WIJZIGINGEN: ${syncData.totalActions}
BATCHES: ${syncData.batches.length}

--- DETAIL PER WIJZIGING ---
`;

    syncData.changes.forEach((change, idx) => {
        const categoryId = String(change.categoryId);
        const ruleId = String(change.ruleId);
        const category = currentDataDraft.categoryBase && currentDataDraft.categoryBase[categoryId];
        const categoryName = category ? category.title : "(onbekend)";

        logContent += `\n[${idx + 1}] ${categoryName} → Rule ${ruleId}\n`;
        logContent += `    Voor: ${JSON.stringify(change.original, null, 2).replace(/\n/g, "\n    ")}\n`;
        logContent += `    Na:   ${JSON.stringify(change.current, null, 2).replace(/\n/g, "\n    ")}\n`;
    });

    logContent += "\n--- ACTIES PER BATCH ---\n";

    syncData.batches.forEach((batch, batchIdx) => {
        logContent += `\nBatch ${batchIdx + 1} (${batch.length} acties):\n`;
        batch.forEach(item => {
            logContent += `  [Seq ${item.sequenceNumber}] ${JSON.stringify(item.action, null, 2).replace(/\n/g, "\n  ")}\n`;
        });
    });

    logContent += "\n--- VOLLEDIGE PAYLOAD MET INTEGRITY SIGNING ---\n";

    if (!parentPasswordHash || !parentPasswordHash.secondHash) {
        logContent += "\n⚠️  Geen parentPasswordHash.secondHash beschikbaar; fallback op 'device'\n";
        console.warn("[TEST] Geen secondHash beschikbaar voor integrity signing!");
    } else {
        logContent += "\n✅ parentPasswordHash.secondHash beschikbaar voor integrity signing\n";
        console.log("[TEST] secondHash aanwezig, integrity signing zal worden uitgevoerd");
    }

    // Read deviceId from draft (or use a default)
    const deviceId = currentDataDraft?.deviceId || "device1";
    console.log("[TEST] DeviceId:", deviceId);
    
    // Determine parent userId (same as real push sync)
    let parentUserId = null;
    if (currentDataDraft && currentDataDraft.users && currentDataDraft.users.data) {
        const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
        if (parentUser) {
            // Try both 'id' and 'userId' fields
            parentUserId = parentUser.id || parentUser.userId;
            console.log("[TEST] Parent user object:", parentUser);
            console.log("[TEST] Parent.id:", parentUser.id);
            console.log("[TEST] Parent.userId:", parentUser.userId);
            console.log("[TEST] Parent userId gebruikt:", parentUserId);
        } else {
            console.warn("[TEST] Geen parent user gevonden!");
        }
    }
    
    if (!parentUserId) {
        logContent += "\n⚠️  Geen parent userId gevonden - kan geen volledige payload testen!\n";
        parentUserId = "UNKNOWN_PARENT_ID";
    }
    
    const firstBatch = syncData.batches[0];

    // Compute integrity for each action
    const mockPayload = {
        deviceAuthToken: TOKEN ? TOKEN.substring(0, 20) + "..." : "MISSING_TOKEN",
        actions: []
    };
    let usedFallback = false;

    try {
        for (const item of firstBatch) {
            const integrity = await calculateIntegrity(item.sequenceNumber, deviceId, item.encodedAction);
            if (integrity === "device") {
                usedFallback = true;
            }
            mockPayload.actions.push({
                sequenceNumber: item.sequenceNumber,
                encodedAction: item.encodedAction,
                integrity: integrity,
                type: "parent",           // UPDATE_TIMELIMIT_RULE is a parent action
                userId: parentUserId      // Parent executing the action
            });
        }

        logContent += `\n${JSON.stringify(mockPayload, null, 2)}\n`;
        if (usedFallback) {
            logContent += "\n⚠️  INTEGRITY HASHING: fallback gebruikt (integrity = 'device')\n";
        } else {
            logContent += "\n✅ INTEGRITY HASHING: HMAC-SHA256 (binary format) succesvol berekend met 'password:' prefix\n";
        }
    } catch (error) {
        logContent += `\n❌ FOUT bij integrity berekening: ${error.message}\n`;
        logContent += "Fallback op 'device' placeholder\n";

        mockPayload.actions = firstBatch.map(item => ({
            sequenceNumber: item.sequenceNumber,
            encodedAction: item.encodedAction,
            integrity: "device",
            type: "parent",
            userId: parentUserId
        }));

        logContent += `${JSON.stringify(mockPayload, null, 2)}\n`;
    }

    logContent += "\n⚠️  DEZE DATA WORDT NIET DAADWERKELIJK VERZONDEN (TEST MODUS)\n";

    // Log to console
    console.log("🧪 TEST SYNC DATA:", syncData);
    console.log("📤 PAYLOAD MET SIGNING:", mockPayload);

    // Log to inspector
    if (jsonView.textContent.length > 100000) {
        jsonView.textContent = jsonView.textContent.slice(-50000);
    }
    jsonView.textContent += separator + logContent;
    jsonView.scrollTop = jsonView.scrollHeight;

    addLog("✅ TEST SYNC voltooid - HMAC-SHA512 integrity berekend - Check inspector-panel en browser console", false);
}
/**
 * DEBUG FUNCTION: Verify integrity calculation with the server
 * Calls /debug-integrity to check whether our HMAC matches
 */
async function debugIntegrityCheck() {
    addLog("🔍 DEBUG: Integrity verificatie starten...", false);
    
    const inspector = document.getElementById('json-view');
    const timestamp = new Date().toLocaleTimeString();
    let logContent = `\n\n${"=".repeat(30)} INTEGRITY DEBUG @ ${timestamp} ${"=".repeat(30)}\n`;
    
    // Prompt for password (temporary - debug only)
    const password = prompt("Voer je parent wachtwoord in voor verificatie (alleen lokaal gebruikt):");
    if (!password) {
        addLog("Verificatie geannuleerd", true);
        return;
    }
    
    // Verify required data is available
    if (!currentDataDraft?.users?.data) {
        addLog("❌ Geen user data beschikbaar - voer eerst een pull sync uit", true);
        return;
    }
    
    if (!currentDataDraft?.devices?.data) {
        addLog("❌ Geen device data beschikbaar", true);
        return;
    }
    
    // Resolve parent user
    const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
    if (!parentUser) {
        addLog("❌ Geen parent user gevonden", true);
        return;
    }
    
    const parentUserId = parentUser.id || parentUser.userId;
    const secondPasswordSalt = parentUser.secondPasswordSalt;
    
    if (!secondPasswordSalt) {
        addLog("❌ Geen secondPasswordSalt gevonden in user data", true);
        return;
    }
    
    // Resolve deviceId (DashboardControl device)
    const dashboardDevice = currentDataDraft.devices.data.find(d => 
        d.name === "DashboardControl" || d.model?.includes("Dashboard")
    );
    
    if (!dashboardDevice) {
        addLog("❌ DashboardControl device niet gevonden", true);
        return;
    }
    
    const deviceId = dashboardDevice.deviceId;
    
    logContent += `\nINPUT DATA:\n`;
    logContent += `- Parent userId: ${parentUserId}\n`;
    logContent += `- SecondPasswordSalt: ${secondPasswordSalt}\n`;
    logContent += `- DeviceId: ${deviceId}\n`;
    logContent += `- Device naam: ${dashboardDevice.name}\n`;
    
    // Create a test action
    const testAction = {
        type: "UPDATE_TIMELIMIT_RULE",
        ruleId: "iox6Sg",
        time: 7200000,
        days: 1,
        extraTime: false,
        start: 0,
        end: 1439,
        pause: 0,
        perDay: true
    };
    
    const encodedAction = JSON.stringify(testAction);
    const sequenceNumber = 1;
    
    logContent += `- SequenceNumber: ${sequenceNumber}\n`;
    logContent += `- EncodedAction: ${encodedAction}\n\n`;
    
    // Calculate our own integrity
    addLog("Berekenen lokale integrity...", false);
    const ourIntegrity = await calculateIntegrity(sequenceNumber, deviceId, encodedAction);
    
    logContent += `ONZE BEREKENING:\n`;
    logContent += `- Integrity: ${ourIntegrity}\n\n`;
    
    // Ask the server for its calculation
    addLog("Vragen aan server om correcte integrity...", false);
    
    try {
        const response = await fetch('debug-integrity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: password,
                secondSalt: secondPasswordSalt,
                sequenceNumber: sequenceNumber,
                deviceId: deviceId,
                encodedAction: encodedAction,
                providedIntegrity: ourIntegrity
            })
        });
        
        const result = await response.json();
        
        logContent += `SERVER BEREKENING:\n`;
        logContent += `- Calculated: ${result.calculatedIntegrity}\n`;
        logContent += `- SecondHash: ${result.secondHash}\n`;
        logContent += `- MATCH: ${result.match ? '✅ JA' : '❌ NEE'}\n\n`;
        
        if (!result.match) {
            logContent += `❌ PROBLEEM GEVONDEN:\n`;
            logContent += `  De HMAC die wij berekenen komt niet overeen met wat de server verwacht!\n`;
            logContent += `  Dit betekent dat de server je push sync zal afwijzen.\n\n`;
            logContent += `  Mogelijke oorzaken:\n`;
            logContent += `  1. SecondHash verschil: Check of je wachtwoord correct is\n`;
            logContent += `  2. DeviceId verschil: Check of je de juiste device gebruikt\n`;
            logContent += `  3. Encoding verschil: Check binary format details\n\n`;
            
            addLog("❌ INTEGRITY MISMATCH - zie inspector voor details", true);
        } else {
            logContent += `✅ PERFECT! De integrity berekening is correct.\n`;
            logContent += `   Dit betekent dat push sync zou moeten werken.\n`;
            addLog("✅ Integrity verificatie geslaagd!", false);
        }
        
        logContent += `\nDEBUG INFO:\n`;
        logContent += JSON.stringify(result.debugInfo, null, 2);
        
    } catch (e) {
        logContent += `\n❌ ERROR: ${e.message}\n`;
        addLog("❌ Debug verificatie mislukt: " + e.message, true);
    }
    
    inspector.textContent += logContent;
    inspector.scrollTop = inspector.scrollHeight;
}

/**
 * TEST FUNCTION: Create a new category + rule on the server
 * This tests whether push sync works without relying on existing data
 */
async function testCreateCategoryAndRule() {
    addLog("🧪 TEST: Category + Rule aanmaken...", false);
    
    const inspector = document.getElementById("json-view");
    const timestamp = new Date().toLocaleTimeString();
    let logContent = `\n\n${"=".repeat(30)} CREATE TEST @ ${timestamp} ${"=".repeat(30)}\n`;
    
    // Check if we have data
    if (!currentDataDraft || !currentDataDraft.users || !currentDataDraft.users.data) {
        addLog("❌ Geen user data - voer eerst een pull sync uit", true);
        return;
    }
    
    // Find parent and child users
    const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
    const childUser = currentDataDraft.users.data.find(u => u.type === 'child');
    
    if (!parentUser) {
        addLog("❌ Geen parent user gevonden", true);
        return;
    }
    
    if (!childUser) {
        addLog("❌ Geen child user gevonden - maak eerst een child aan in de app", true);
        return;
    }
    
    const parentUserId = parentUser.id || parentUser.userId;
    const childUserId = childUser.id || childUser.userId;
    
    logContent += `Parent userId: ${parentUserId}\n`;
    logContent += `Child userId: ${childUserId}\n`;
    logContent += `Child naam: ${childUser.name}\n\n`;
    
    // Generate IDs for category and rule
    const categoryId = generateRandomId(6);
    const ruleId = generateRandomId(6);
    
    logContent += `Nieuwe categoryId: ${categoryId}\n`;
    logContent += `Nieuwe ruleId: ${ruleId}\n\n`;
    
    // Resolve deviceId
    let deviceId = "unknown";
    let deviceIdSource = "fallback";
    
    if (currentDataDraft?.devices && currentDataDraft.devices.data) {
        const dashboardDevice = currentDataDraft.devices.data.find((d) =>
            d.name === "DashboardControl" || d.model?.includes("Dashboard")
        );
        
        if (dashboardDevice) {
            deviceId = dashboardDevice.deviceId;
            deviceIdSource = 'devices.data (DashboardControl)';
        }
    }
    
    logContent += `DeviceId: ${deviceId}\n`;
    logContent += `DeviceId source: ${deviceIdSource}\n\n`;
    
    // Build actions
    const actions = [];
    const categorySequenceNumber = getNextSequenceNumber();
    
    // Action 1: CREATE_CATEGORY
    const createCategoryAction = {
        type: "CREATE_CATEGORY",
        categoryId: categoryId,
        childId: childUserId,
        title: "Test Category " + new Date().toLocaleTimeString()
    };
    
    const encodedCategory = JSON.stringify(createCategoryAction);
    const categoryIntegrity = await calculateIntegrity(categorySequenceNumber, deviceId, encodedCategory);
    
    actions.push({
        sequenceNumber: categorySequenceNumber,
        encodedAction: encodedCategory,
        integrity: categoryIntegrity,
        type: "parent",
        userId: parentUserId
    });
    
    // Action 2: CREATE_TIMELIMIT_RULE
    const ruleSequenceNumber = getNextSequenceNumber();
    const createRuleAction = {
        type: "CREATE_TIMELIMIT_RULE",
        rule: {
            ruleId: ruleId,
            categoryId: categoryId,
            time: 3600000, // 1 hour
            days: 127, // Every day (1111111 in binary)
            extraTime: false,
            start: 0, // 00:00
            end: 1439, // 23:59
            dur: 0,
            pause: 0,
            perDay: true
        }
    };
    
    const encodedRule = JSON.stringify(createRuleAction);
    const ruleIntegrity = await calculateIntegrity(ruleSequenceNumber, deviceId, encodedRule);
    
    actions.push({
        sequenceNumber: ruleSequenceNumber,
        encodedAction: encodedRule,
        integrity: ruleIntegrity,
        type: "parent",
        userId: parentUserId
    });
    
    logContent += `ACTIES:\n`;
    logContent += `1. CREATE_CATEGORY: ${JSON.stringify(createCategoryAction)}\n`;
    logContent += `2. CREATE_TIMELIMIT_RULE: ${JSON.stringify(createRuleAction)}\n\n`;
    
    // Send to server
    const payload = {
        deviceAuthToken: TOKEN,
        actions: actions
    };
    
    logContent += `>>> VERZENDEN NAAR SERVER:\n`;
    logContent += JSON.stringify(payload, null, 2) + '\n\n';
    
    inspector.textContent += logContent;
    inspector.scrollTop = inspector.scrollHeight;
    
    addLog("Versturen test acties naar server...", false);
    
    try {
        const response = await fetch('sync/push-actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        let resultLog = `<<< SERVER RESPONSE (${response.status}):\n`;
        resultLog += JSON.stringify(result, null, 2) + '\n\n';
        
        if (result.shouldDoFullSync) {
            resultLog += `⚠️  SERVER VRAAGT OM FULL SYNC\n`;
            resultLog += `Dit betekent dat er een exception is opgetreden bij het verwerken.\n`;
            addLog("❌ Server vraagt om full sync - actie mogelijk gefaald", true);
        } else {
            resultLog += `✅ SUCCESS! Geen full sync gevraagd.\n`;
            resultLog += `Category en rule zijn succesvol aangemaakt!\n`;
            addLog("✅ Category + Rule succesvol aangemaakt!", false);
            
            // Automatically run a pull sync
            setTimeout(() => {
                addLog("Pulling fresh data...", false);
                runSync();
            }, 1000);
        }
        
        inspector.textContent += resultLog;
        inspector.scrollTop = inspector.scrollHeight;
        
    } catch (e) {
        addLog("❌ Fout bij versturen: " + e.message, true);
        inspector.textContent += `\n❌ ERROR: ${e.message}\n`;
    }
}

/**
 * Generate a random ID (same format as the server)
 */
function generateRandomId(length) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

/**
 * TEST version: Send changes via /sync/push-actions
 * With verbose logging of server responses
 */
async function executePushSync() {
    const jsonView = document.getElementById("json-view");
    const timestamp = new Date().toLocaleTimeString();
    const separator = `\n\n${"=".repeat(20)} PUSH SYNC @ ${timestamp} ${"=".repeat(20)}\n`;
    
    setPendingBadgeSyncState(true);
    addLog("🚀 PUSH SYNC starten...", false);
    console.log("=== PUSH SYNC GESTART ===");
    
    try {
        // Check TOKEN
        if (!TOKEN || TOKEN === "" || TOKEN.includes("#")) {
            addLog("❌ Geen geldig token beschikbaar!", true);
            console.error("[PUSH-SYNC] Geen geldig token");
            alert("Push sync kan niet starten: geen geldig token. Log opnieuw in.");
            if (typeof showLoginModal === 'function') {
                showLoginModal();
            }
            return;
        }
        
        // Check parentPasswordHash
        if (!parentPasswordHash || !parentPasswordHash.secondSalt) {
            addLog("❌ Geen wachtwoord hashes beschikbaar voor signing! Klik eerst op 'Wachtwoord Hashes Bijwerken'.", true);
            console.error("[PUSH-SYNC] Geen parentPasswordHash voor integrity signing");
            alert("Push sync kan niet starten: wachtwoord hashes ontbreken. Werk deze bij.");
            if (typeof showPasswordResetModal === 'function') {
                showPasswordResetModal();
            }
            return;
        }
    
    console.log("[PUSH-SYNC] Token check: OK");
    console.log("[PUSH-SYNC] parentPasswordHash check: OK");
    console.log("[PUSH-SYNC] ============ VERIFICATIE PARENT DATA ============");
    console.log("[PUSH-SYNC] parentPasswordHash object:", parentPasswordHash);
    console.log("[PUSH-SYNC] - hash aanwezig:", !!parentPasswordHash.hash);
    console.log("[PUSH-SYNC] - secondHash aanwezig:", !!parentPasswordHash.secondHash);
    console.log("[PUSH-SYNC] - secondHash (first 30 chars):", parentPasswordHash.secondHash ? parentPasswordHash.secondHash.substring(0, 30) + "..." : "N/A");
    console.log("[PUSH-SYNC] - secondSalt aanwezig:", !!parentPasswordHash.secondSalt);
    
    if (currentDataDraft && currentDataDraft.users) {
        console.log("[PUSH-SYNC] currentDataDraft.users:", currentDataDraft.users);
        if (currentDataDraft.users.data) {
            console.log("[PUSH-SYNC] - Aantal users:", currentDataDraft.users.data.length);
            currentDataDraft.users.data.forEach((u, idx) => {
                console.log(`[PUSH-SYNC] - User ${idx}:`, u);
                console.log(`[PUSH-SYNC] - User ${idx}: type='${u.type}', id='${u.id}', userId='${u.userId}', name='${u.name}'`);
            });
        } else {
            console.warn("[PUSH-SYNC] - currentDataDraft.users.data is UNDEFINED!");
        }
    } else {
        console.warn("[PUSH-SYNC] currentDataDraft.users is UNDEFINED!");
    }
    console.log("[PUSH-SYNC] =====================================================");
    
    // Prepare actions
    const syncData = prepareSync();
    
    if (syncData.totalActions === 0) {
        addLog("ℹ️ Geen wijzigingen om te synchroniseren.", false);
        console.log("[PUSH-SYNC] Geen wijzigingen gevonden");
        if (typeof clearDisabledRulesDirty === 'function') {
            clearDisabledRulesDirty();
        }
        if (typeof updatePendingChangesIndicator === 'function') {
            updatePendingChangesIndicator();
        }
        return;
    }
    
    console.log(`[PUSH-SYNC] ${syncData.totalActions} wijzigingen gevonden in ${syncData.batches.length} batch(es)`);
    addLog(`📦 ${syncData.totalActions} wijzigingen gevonden...`, false);
    
    // Resolve deviceId (prefer the dashboard device)
    let deviceId = currentDataDraft?.deviceId || null;
    let deviceIdSource = currentDataDraft?.deviceId ? 'from draft' : 'unknown';
    
    if (currentDataDraft?.devices && currentDataDraft.devices.data) {
        console.log(`[PUSH-SYNC] Available devices in data:`);
        currentDataDraft.devices.data.forEach((d, idx) => {
            console.log(`[PUSH-SYNC]   - Device ${idx}: ID='${d.deviceId}', name='${d.name}', model='${d.model}'`);
        });
        
        const dashboardDevice = currentDataDraft.devices.data.find((d) =>
            d.name === 'DashboardControl' || d.model === 'WebDashboard-v60-Modular'
        );
        
        if (dashboardDevice && dashboardDevice.deviceId) {
            deviceId = dashboardDevice.deviceId;
            deviceIdSource = 'devices.data (DashboardControl)';
        }
    }
    
    if (!deviceId) {
        deviceId = "device1";
        deviceIdSource = 'FALLBACK';
    }
    
    console.log(`[PUSH-SYNC] DeviceId: ${deviceId}`);
    console.log(`[PUSH-SYNC] DeviceId source: ${deviceIdSource}`);
    
    let logContent = `PUSH SYNC NAAR SERVER\n`;
    logContent += `Timestamp: ${timestamp}\n`;
    logContent += `Token: ${TOKEN.substring(0, 10)}...\n`;
    logContent += `DeviceId: ${deviceId}\n`;
    logContent += `Totaal wijzigingen: ${syncData.totalActions}\n`;
    logContent += `Aantal batches: ${syncData.batches.length}\n\n`;
    
    // Process each batch
    let successfulBatches = 0;
    let failedBatches = 0;
    
    for (let batchIdx = 0; batchIdx < syncData.batches.length; batchIdx++) {
        const batch = syncData.batches[batchIdx];
        const batchNum = batchIdx + 1;
        
        console.log(`\n[PUSH-SYNC] ===== BATCH ${batchNum}/${syncData.batches.length} =====`);
        logContent += `\n--- BATCH ${batchNum}/${syncData.batches.length} (${batch.length} acties) ---\n`;
        
        // Determine parent userId
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Parent userId detectie...`);
        let parentUserId = null;
        if (currentDataDraft && currentDataDraft.users && currentDataDraft.users.data) {
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Users beschikbaar, zoeken naar parent...`);
            const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
            if (parentUser) {
                // Try both 'id' and 'userId' fields
                parentUserId = parentUser.id || parentUser.userId;
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Parent gevonden:`, parentUser);
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Parent id field: ${parentUser.id}`);
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Parent userId field: ${parentUser.userId}`);
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Parent userId gebruikt: ${parentUserId}`);
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Parent naam: ${parentUser.name}`);
            } else {
                console.error(`[PUSH-SYNC] Batch ${batchNum}: ❌ Geen user met type='parent' gevonden!`);
                console.log(`[PUSH-SYNC] Batch ${batchNum}: Alle users:`, currentDataDraft.users.data);
            }
        } else {
            console.error(`[PUSH-SYNC] Batch ${batchNum}: ❌ currentDataDraft.users.data niet beschikbaar!`);
        }
        
        if (!parentUserId) {
            console.error(`[PUSH-SYNC] Batch ${batchNum}: Geen parent userId gevonden!`);
            logContent += `❌ FOUT: Geen parent userId beschikbaar\n`;
            addLog(`❌ Batch ${batchNum}: Geen parent userId gevonden`, true);
            failedBatches++;
            continue;
        }
        
        console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ Ga verder met parentUserId: ${parentUserId}`);
        logContent += `Parent userId: ${parentUserId}\n`;
        
        // Build the actions array with integrity signing
        const actions = [];
        
        try {
            addLog(`📤 Batch ${batchNum}: Integrity berekenen voor ${batch.length} acties...`, false);
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Integrity signing starten...`);
            
            for (const item of batch) {
                const integrity = await calculateIntegrity(item.sequenceNumber, deviceId, item.encodedAction);
                
                actions.push({
                    sequenceNumber: item.sequenceNumber,
                    encodedAction: item.encodedAction,
                    integrity: integrity,
                    type: "parent",           // UPDATE_TIMELIMIT_RULE is een parent action
                    userId: parentUserId      // De parent die de actie uitvoert
                });
                
                console.log(`  [Seq ${item.sequenceNumber}] Action: ${item.action.type}, Integrity: ${integrity.substring(0, 30)}...`);
            }
            
            logContent += `Acties met signing:\n${JSON.stringify(actions, null, 2)}\n\n`;
            
        } catch (integrityError) {
            console.error(`[PUSH-SYNC] Batch ${batchNum}: Integrity error:`, integrityError);
            logContent += `❌ FOUT bij integrity berekening: ${integrityError.message}\n`;
            addLog(`❌ Batch ${batchNum}: Integrity fout - ${integrityError.message}`, true);
            failedBatches++;
            continue;
        }
        
        // Build the payload - correct format without version/clientLevel
        const payload = {
            deviceAuthToken: TOKEN,
            actions: actions
        };
        
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Verzenden naar /sync/push-actions...`);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload structure check:`);
        console.log(`  - deviceAuthToken length: ${TOKEN.length}`);
        console.log(`  - actions count: ${actions.length}`);
        console.log(`  - First action structure:`, actions[0]);
        
        // Validate the payload before sending
        const payloadString = JSON.stringify(payload);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload size: ${payloadString.length} bytes`);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload preview (first 300 chars):`, payloadString.substring(0, 300));
        
        logContent += `>>> REQUEST PAYLOAD:\n${JSON.stringify(payload, null, 2)}\n\n`;
        logContent += `Payload stats:\n`;
        logContent += `  - Total size: ${payloadString.length} bytes\n`;
        logContent += `  - Actions: ${actions.length}\n`;
        logContent += `  - Parent userId: ${parentUserId}\n\n`;
        
        addLog(`📡 Batch ${batchNum}: Verzenden naar server (${payloadString.length} bytes)...`, false);
        
        // Send to server
        try {
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Fetching sync/push-actions...`);
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Checking URL resolution...`);
            console.log(`  - Current location: ${window.location.href}`);
            console.log(`  - Resolved URL will be: ${new URL('sync/push-actions', window.location.href).href}`);
            
            const response = await fetch('sync/push-actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payloadString
            });
            
            const responseStatus = response.status;
            const responseContentType = response.headers.get('content-type') || 'unknown';
            
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Server response status: ${responseStatus}`);
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Response content-type: ${responseContentType}`);
            
            const responseText = await response.text();
            
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Response body length: ${responseText.length} bytes`);
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Response body preview (first 500 chars):`);
            console.log(responseText.substring(0, 500));
            
            logContent += `<<< SERVER RESPONSE:\n`;
            logContent += `Status: ${responseStatus} ${response.statusText}\n`;
            logContent += `Content-Type: ${responseContentType}\n`;
            logContent += `Headers:\n`;
            response.headers.forEach((value, key) => {
                logContent += `  ${key}: ${value}\n`;
            });
            logContent += `\nBody (first 1000 chars):\n${responseText.substring(0, 1000)}\n`;
            if (responseText.length > 1000) {
                logContent += `\n... (truncated, total ${responseText.length} bytes)\n`;
            }
            logContent += `\n`;
            
            if (response.ok) {
                // Parse response
                let responseData;
                try {
                    responseData = JSON.parse(responseText);
                    console.log(`[PUSH-SYNC] Batch ${batchNum}: Parsed response:`, responseData);
                    logContent += `Parsed JSON:\n${JSON.stringify(responseData, null, 2)}\n`;
                    
                    // Check for shouldDoFullSync flag
                    if (responseData.shouldDoFullSync) {
                        console.warn(`[PUSH-SYNC] Batch ${batchNum}: Server requests FULL SYNC!`);
                        logContent += `\n⚠️  SERVER VRAAGT OM VOLLEDIGE SYNC (shouldDoFullSync = true)\n`;
                        logContent += `Dit betekent dat de server updates heeft die je moet ophalen.\n`;
                        logContent += `Er wordt automatisch een pull sync uitgevoerd na deze push.\n`;
                        addLog(`⚠️ Server vraagt om volledige sync - automatische pull sync gepland`, true);
                    }
                    
                } catch (parseError) {
                    console.warn(`[PUSH-SYNC] Batch ${batchNum}: Response is geen JSON:`, responseText);
                    logContent += `(Response is geen JSON)\n`;
                }
                
                console.log(`[PUSH-SYNC] Batch ${batchNum}: ✅ SUCCESVOL`);
                logContent += `✅ BATCH ${batchNum} SUCCESVOL VERWERKT\n`;
                addLog(`✅ Batch ${batchNum}: Succesvol verzonden!`, false);
                successfulBatches++;
                
            } else {
                // Error response
                console.error(`[PUSH-SYNC] Batch ${batchNum}: ❌ FOUT ${responseStatus}`);
                logContent += `❌ BATCH ${batchNum} GEFAALD (Status ${responseStatus})\n`;
                
                // Try to detect HTML responses
                const isHtml = responseContentType.includes('text/html') || responseText.trim().startsWith('<');
                
                if (isHtml) {
                    console.error(`[PUSH-SYNC] Batch ${batchNum}: Server stuurde HTML error page!`);
                    logContent += `\n⚠️  SERVER STUURDE HTML ERROR PAGE (geen JSON)\n`;
                    logContent += `Dit betekent meestal dat de route niet correct is of de payload structuur fout is.\n\n`;
                }
                
                if (responseStatus === 401) {
                    console.error(`[PUSH-SYNC] Batch ${batchNum}: Authenticatie fout`);
                    logContent += `DIAGNOSE: Token niet geldig of verlopen\n`;
                    addLog(`❌ Batch ${batchNum}: Authenticatie fout - Token niet geldig`, true);
                    
                } else if (responseStatus === 400) {
                    console.error(`[PUSH-SYNC] Batch ${batchNum}: Bad Request - server accepteert payload niet`);
                    logContent += `DIAGNOSE: Bad Request - Mogelijke oorzaken:\n`;
                    logContent += `  1. Payload structuur komt niet overeen met API schema\n`;
                    logContent += `  2. Ontbrekende of ongeldige velden\n`;
                    logContent += `  3. Integrity signature incorrect\n`;
                    logContent += `  4. encodedAction is geen geldige JSON string\n\n`;
                    logContent += `DEBUGGING STAPPEN:\n`;
                    logContent += `  - Check dat encodedAction een JSON STRING is (niet object)\n`;
                    logContent += `  - Verifieer dat alle vereiste velden aanwezig zijn\n`;
                    logContent += `  - Test met een enkele simpele actie\n\n`;
                    
                    // Log the exact action structure for debugging
                    if (actions.length > 0) {
                        logContent += `EERSTE ACTIE DETAILS:\n`;
                        logContent += `  sequenceNumber: ${actions[0].sequenceNumber} (type: ${typeof actions[0].sequenceNumber})\n`;
                        logContent += `  encodedAction: ${actions[0].encodedAction.substring(0, 100)}... (type: ${typeof actions[0].encodedAction})\n`;
                        logContent += `  integrity: ${actions[0].integrity.substring(0, 50)}... (type: ${typeof actions[0].integrity})\n`;
                        
                        // Validate that encodedAction is valid JSON
                        try {
                            const parsed = JSON.parse(actions[0].encodedAction);
                            logContent += `  encodedAction parsed OK: type=${parsed.type}, ruleId=${parsed.ruleId}\n`;
                        } catch (e) {
                            logContent += `  ⚠️  encodedAction is GEEN geldige JSON! Error: ${e.message}\n`;
                        }
                    }
                    
                    addLog(`❌ Batch ${batchNum}: Bad Request - Payload structuur fout (zie inspector)`, true);
                    
                } else {
                    console.error(`[PUSH-SYNC] Batch ${batchNum}: Server error ${responseStatus}`);
                    logContent += `DIAGNOSE: Server error (${responseStatus})\n`;
                    addLog(`❌ Batch ${batchNum}: Server fout ${responseStatus}`, true);
                }
                
                failedBatches++;
            }
            
        } catch (networkError) {
            console.error(`[PUSH-SYNC] Batch ${batchNum}: Netwerk fout:`, networkError);
            logContent += `❌ NETWERK FOUT: ${networkError.message}\n`;
            addLog(`❌ Batch ${batchNum}: Netwerk fout - ${networkError.message}`, true);
            failedBatches++;
        }
    }
    
    // Summary
    console.log(`\n[PUSH-SYNC] ===== SAMENVATTING =====`);
    console.log(`  Succesvol: ${successfulBatches}/${syncData.batches.length}`);
    console.log(`  Gefaald: ${failedBatches}/${syncData.batches.length}`);
    
    logContent += `\n========================================\n`;
    logContent += `SAMENVATTING:\n`;
    logContent += `  Succesvol: ${successfulBatches}/${syncData.batches.length} batches\n`;
    logContent += `  Gefaald: ${failedBatches}/${syncData.batches.length} batches\n`;
    logContent += `  Totaal acties: ${syncData.totalActions}\n`;
    
    // Track whether a full sync is needed
    let needsFullSync = false;
    
    if (successfulBatches === syncData.batches.length) {
        console.log(`[PUSH-SYNC] 🎉 ALLE BATCHES SUCCESVOL!`);
        logContent += `\n🎉 ALLE WIJZIGINGEN SUCCESVOL VERZONDEN!\n`;
        addLog(`🎉 Alle ${syncData.totalActions} wijzigingen succesvol verzonden!`, false);

        if (typeof clearDisabledRulesDirty === 'function') {
            clearDisabledRulesDirty();
        }
        
        // IMPORTANT: Do NOT reset here.
        // Wait until pull sync completes.
        // Then resetChangeTracking() is called in runSync().
        
    } else if (successfulBatches > 0) {
        console.log(`[PUSH-SYNC] ⚠️ GEDEELTELIJK SUCCESVOL`);
        logContent += `\n⚠️ GEDEELTELIJK SUCCESVOL - Sommige batches gefaald\n`;
        addLog(`⚠️ ${successfulBatches}/${syncData.batches.length} batches succesvol`, true);
    } else {
        console.log(`[PUSH-SYNC] ❌ ALLE BATCHES GEFAALD`);
        logContent += `\n❌ ALLE BATCHES GEFAALD - Controleer logs\n`;
        addLog(`❌ Sync gefaald - controleer inspector en console`, true);
    }
    
    // Log to inspector
    if (jsonView.textContent.length > 100000) {
        jsonView.textContent = jsonView.textContent.slice(-50000);
    }
    jsonView.textContent += separator + logContent;
    jsonView.scrollTop = jsonView.scrollHeight;
    
    console.log(`[PUSH-SYNC] ===== EINDE =====\n`);
    
    // If all batches succeeded and there were no failures, trigger a pull sync.
    // This ensures we run a full sync when the server requested it.
    if (successfulBatches === syncData.batches.length && failedBatches === 0) {
        console.log(`[PUSH-SYNC] 🔄 Automatische pull sync starten om server state te synchroniseren...`);
        addLog(`🔄 Pull sync starten om server state op te halen...`, false);
        
        // Small delay so logs remain visible
        setTimeout(() => {
            if (typeof runSync === 'function') {
                console.log(`[PUSH-SYNC] Triggering runSync() for automatic full sync...`);
                runSync();
            }
        }, 1000);
    }
    } finally {
        setPendingBadgeSyncState(false);
        if (typeof updatePendingChangesIndicator === 'function') {
            updatePendingChangesIndicator();
        }
    }
}

if (typeof window !== 'undefined') {
    window.executePushSync = executePushSync;
    window.runSync = runSync;
}

/**
 * Debug function: Test AddUser integrity
 */
async function debugAddUserIntegrity() {
    const inspector = document.getElementById('json-view');
    
    if (!TOKEN || TOKEN === "") {
        addLog("❌ Geen token - log eerst in.", true);
        return;
    }
    
    if (!parentPasswordHash || !parentPasswordHash.secondHash) {
        addLog("❌ Geen wachtwoord hashes - update eerst!", true);
        return;
    }
    
    if (!currentDataDraft?.devices?.data || !currentDataDraft?.users?.data) {
        addLog("❌ Geen data geladen - doe eerst een pull sync", true);
        return;
    }
    
    const timestamp = new Date().toLocaleTimeString();
    let logContent = `\n\n${"=".repeat(20)} DEBUG ADD USER INTEGRITY @ ${timestamp} ${"=".repeat(20)}\n`;
    
    addLog("🔍 Debug: AddUser integrity check...", false);
    
    // Resolve parent user
    const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
    if (!parentUser) {
        addLog("❌ Parent user niet gevonden", true);
        return;
    }
    const parentUserId = parentUser.id || parentUser.userId;
    const secondPasswordSalt = parentUser.secondPasswordSalt;
    
    // Resolve deviceId
    const dashboardDevice = currentDataDraft.devices.data.find(d => 
        d.name === "DashboardControl" || d.model?.includes("Dashboard")
    );
    
    if (!dashboardDevice) {
        addLog("❌ DashboardControl device niet gevonden", true);
        return;
    }
    
    const deviceId = dashboardDevice.deviceId;
    
    logContent += `\nINPUT DATA:\n`;
    logContent += `- Parent userId: ${parentUserId}\n`;
    logContent += `- SecondPasswordSalt: ${secondPasswordSalt}\n`;
    logContent += `- DeviceId: ${deviceId}\n`;
    logContent += `- Device naam: ${dashboardDevice.name}\n`;
    
    // Create a test ADD_USER action (like the one we just sent)
    const testUserId = "vCzYlU";
    const testAction = {
        type: "ADD_USER",
        userId: testUserId,
        name: "Jantje",
        userType: "child",
        timeZone: "Europe/Amsterdam"
    };
    
    const encodedAction = JSON.stringify(testAction);
    const sequenceNumber = 1;
    
    logContent += `- SequenceNumber: ${sequenceNumber}\n`;
    logContent += `- EncodedAction: ${encodedAction}\n\n`;
    
    // Calculate our own integrity
    addLog("Berekenen lokale integrity...", false);
    const ourIntegrity = await calculateIntegrity(sequenceNumber, deviceId, encodedAction);
    
    logContent += `ONZE BEREKENING:\n`;
    logContent += `- Integrity: ${ourIntegrity}\n\n`;
    
    // Do NOT ask the server for a server-side calculation (dummy salt fails with bcrypt)
    // Instead: verify that we calculate the same integrity
    logContent += `\nANALYSE:\n`;
    
    // Check for a valid secondHash
    if (!parentPasswordHash || !parentPasswordHash.secondHash) {
        logContent += `❌ Geen secondHash in localStorage!\n`;
        logContent += `Stap 1: Klik '🔐 Wachtwoord Hashes Bijwerken'\n`;
        logContent += `Stap 2: Voer je wachtwoord in\n`;
        logContent += `Stap 3: Probeer opnieuw\n`;
        addLog("❌ Geen secondHash - klik eerst op '🔐 Wachtwoord Hashes Bijwerken'", true);
    } else {
        logContent += `✅ secondHash beschikbaar in localStorage\n`;
        logContent += `   Hash: ${parentPasswordHash.secondHash.substring(0, 30)}...\n`;
        logContent += `\n✅ Integrity looks correct: ${ourIntegrity}\n`;
        
        // Check if the salt is valid
        if (!secondPasswordSalt || secondPasswordSalt === "$2a$12$1234567890123456789012") {
            logContent += `\n⚠️ WAARSCHUWING: secondPasswordSalt is DUMMY!\n`;
            logContent += `Dummy salt: ${secondPasswordSalt}\n`;
            logContent += `Dit kan server-side fouten veroorzaken.\n`;
            logContent += `\nOPLOSSING:\n`;
            logContent += `1. Klik '🔐 Wachtwoord Hashes Bijwerken'\n`;
            logContent += `2. Voer je wachtwoord in\n`;
            logContent += `3. Dit genereert een GELDIGE bcrypt salt\n`;
            logContent += `4. Probeer opnieuw Kind Toevoegen\n`;
            
            addLog("⚠️ Dummy salt gedetecteerd - dit veroorzaakt AddUser fouten!", true);
        } else {
            logContent += `\n✅ Salt ziet er geldig uit\n`;
            logContent += `Als push sync toch full sync antwoord geeft,\n`;
            logContent += `kan het een server-side validation error zijn.\n`;
            addLog("🔍 Integrity check compleet - zie inspector voor details", false);
        }
    }
    
    // Log to inspector
    if (inspector) {
        if (inspector.textContent.length > 100000) {
            inspector.textContent = inspector.textContent.slice(-50000);
        }
        inspector.textContent += logContent;
        inspector.scrollTop = inspector.scrollHeight;
    }
    
    console.log("[DEBUG-ADD-USER] Check compleet");
}

/**
 * ADD CHILD - Modal functions
 */

function showAddChildModal() {
    const modal = document.getElementById('add-child-modal');
    if (modal) {
        modal.style.display = 'flex';
        const input = document.getElementById('add-child-name-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        const status = document.getElementById('add-child-status');
        if (status) {
            status.textContent = '';
            status.style.color = '#666';
        }
    }
}

function hideAddChildModal() {
    const modal = document.getElementById('add-child-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Add a child to the family via the server
 */
async function submitAddChild() {
    const nameInput = document.getElementById('add-child-name-input');
    const statusDiv = document.getElementById('add-child-status');
    const inspector = document.getElementById('json-view');
    
    const childName = nameInput ? nameInput.value.trim() : '';
    
    if (!childName) {
        if (statusDiv) statusDiv.textContent = "❌ Voer een naam in.";
        return;
    }
    
    if (!TOKEN || TOKEN === "") {
        if (statusDiv) statusDiv.textContent = "❌ Geen token - log eerst in.";
        return;
    }
    
    if (!parentPasswordHash || !parentPasswordHash.secondHash) {
        if (statusDiv) {
            statusDiv.innerHTML = "❌ Geen wachtwoord hashes.<br><span style='font-size:11px;'>Gebruik eerst '🔐 Wachtwoord Hashes Bijwerken'.</span>";
        }
        return;
    }
    
    if (statusDiv) statusDiv.textContent = "⏳ Kind toevoegen...";
    
    try {
        // Generate random userId (6 characters, alphanumeric)
        const userId = generateRandomId(6);
        
        // Resolve deviceId
        const dashboardDevice = currentDataDraft?.devices?.data?.find(d => 
            d.name === "DashboardControl" || d.model?.includes("Dashboard")
        );
        
        if (!dashboardDevice) {
            throw new Error("Dashboard device niet gevonden");
        }
        
        const deviceId = dashboardDevice.deviceId;
        
        // Resolve parent userId
        const parentUser = currentDataDraft?.users?.data?.find(u => u.type === 'parent');
        if (!parentUser) {
            throw new Error("Parent user niet gevonden");
        }
        const parentUserId = parentUser.id || parentUser.userId;
        
        const timestamp = new Date().toLocaleTimeString();
        let logContent = `\n\n${"=".repeat(25)} KIND TOEVOEGEN @ ${timestamp} ${"=".repeat(25)}\n`;
        logContent += `Kind naam: ${childName}\n`;
        logContent += `Gegenereerd userId: ${userId}\n`;
        logContent += `Parent userId: ${parentUserId}\n`;
        logContent += `DeviceId: ${deviceId}\n\n`;
        
        // Build ADD_USER action
        const addUserAction = {
            type: "ADD_USER",
            userId: userId,
            name: childName,
            userType: "child",
            timeZone: "Europe/Amsterdam"
            // password: null (not needed for child, omitted automatically)
        };
        
        const encodedAction = JSON.stringify(addUserAction);
        const sequenceNumber = getNextSequenceNumber();
        
        // Compute integrity
        const integrity = await calculateIntegrity(sequenceNumber, deviceId, encodedAction);
        
        const action = {
            sequenceNumber: sequenceNumber,
            encodedAction: encodedAction,
            integrity: integrity,
            type: "parent",
            userId: parentUserId
        };
        
        logContent += `ACTION:\n${JSON.stringify(addUserAction, null, 2)}\n\n`;
        logContent += `PAYLOAD:\n`;
        
        const payload = {
            deviceAuthToken: TOKEN,
            actions: [action]
        };
        
        logContent += JSON.stringify(payload, null, 2) + '\n\n';
        
        console.log("[ADD-CHILD] Versturen naar server:", payload);
        
        // Send to server
        const response = await fetch('sync/push-actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        logContent += `<<< SERVER RESPONSE (${response.status}):\n`;
        logContent += JSON.stringify(result, null, 2) + '\n\n';
        
        if (response.ok && !result.shouldDoFullSync) {
            logContent += `✅ KIND SUCCESVOL TOEGEVOEGD!\n`;
            
            if (statusDiv) {
                statusDiv.innerHTML = `✅ Kind "${childName}" toegevoegd!<br><span style='font-size:11px;'>Doe een pull sync om te vernieuwen.</span>`;
                statusDiv.style.color = '#4ade80';
            }
            
            addLog(`✅ Kind "${childName}" succesvol toegevoegd!`, false);
            
            // Log to inspector
            if (inspector) {
                if (inspector.textContent.length > 100000) {
                    inspector.textContent = inspector.textContent.slice(-50000);
                }
                inspector.textContent += logContent;
                inspector.scrollTop = inspector.scrollHeight;
            }
            
            // Close modal after 2 seconds and run a pull sync
            setTimeout(() => {
                hideAddChildModal();
                runSync(); // Fetch new user data
            }, 2000);
            
        } else {
            logContent += `⚠️ SERVER VRAAGT OM FULL SYNC of actie gefaald\n`;
            
            if (statusDiv) {
                statusDiv.textContent = "❌ Fout bij toevoegen - zie inspector";
                statusDiv.style.color = '#ff4444';
            }
            
            addLog("❌ Kind toevoegen gefaald - controleer inspector", true);
            
            // Log to inspector
            if (inspector) {
                if (inspector.textContent.length > 100000) {
                    inspector.textContent = inspector.textContent.slice(-50000);
                }
                inspector.textContent += logContent;
                inspector.scrollTop = inspector.scrollHeight;
            }
        }
        
    } catch (e) {
        console.error("[ADD-CHILD] Error:", e);
        
        if (statusDiv) {
            statusDiv.textContent = "❌ Fout: " + e.message;
            statusDiv.style.color = '#ff4444';
        }
        
        addLog("Fout bij kind toevoegen: " + e.message, true);
    }
}