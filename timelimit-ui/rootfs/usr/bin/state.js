// Dit is ons "werkgeheugen"
let currentDataDraft = null;

// Originele (niet-gewijzigde) data - opgeslagen wanneer we de sync doen
let originalDataSnapshot = null;

// Tracked welke regels zijn gewijzigd
let changedRules = new Map(); // { "categoryId_ruleId": {...originalValues} }

// Tracked welke regels nieuw zijn
let newRules = [];
let newCategoryApps = [];
let removedCategoryApps = [];

// Lokaal uitgeschakelde regels (blijven in dashboard, maar worden op server verwijderd)
const DISABLED_RULES_STORAGE_KEY = 'timelimit_disabledRules';
const DELETED_RULES_STORAGE_KEY = 'timelimit_deletedRules';
const DISABLED_RULES_DIRTY_KEY = 'timelimit_disabledRulesDirty';
let disabledRules = [];
let deletedRules = [];
let disabledRulesDirty = localStorage.getItem(DISABLED_RULES_DIRTY_KEY) === '1';

// Track nieuw toegevoegde rule terwijl modal open is
let pendingNewRule = null;
let pendingNewRuleSaved = false;

// Parent password hash - nodig voor HMAC-SHA512 signing
let parentPasswordHash = null;

function loadRulesListFromStorage(key) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function saveRulesListToStorage(key, value) {
    if (!Array.isArray(value) || value.length === 0) {
        localStorage.removeItem(key);
    } else {
        localStorage.setItem(key, JSON.stringify(value));
    }
    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('disabled-rules');
    }
}

function setDisabledRulesDirty(value) {
    disabledRulesDirty = !!value;
    if (disabledRulesDirty) {
        localStorage.setItem(DISABLED_RULES_DIRTY_KEY, '1');
    } else {
        localStorage.removeItem(DISABLED_RULES_DIRTY_KEY);
    }
    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('disabled-rules-dirty');
    }
}

function clearDisabledRulesDirty() {
    setDisabledRulesDirty(false);
}

disabledRules = loadRulesListFromStorage(DISABLED_RULES_STORAGE_KEY);
deletedRules = loadRulesListFromStorage(DELETED_RULES_STORAGE_KEY);
normalizeDisabledRules();

function getDisabledRules() {
    return Array.isArray(disabledRules) ? disabledRules.map(r => ({ ...r })) : [];
}

function getDeletedRules() {
    return Array.isArray(deletedRules) ? deletedRules.map(r => ({ ...r })) : [];
}

function isRuleDisabled(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    return disabledRules.some(r => String(r.categoryId) === catKey && String(r.id) === ruleKey);
}

function ruleExistsInSnapshot(categoryId, ruleId) {
    if (!originalDataSnapshot || !Array.isArray(originalDataSnapshot.rules)) return false;
    const category = originalDataSnapshot.rules.find(r => String(r.categoryId) === String(categoryId));
    if (!category || !Array.isArray(category.rules)) return false;
    return category.rules.some(r => String(r.id) === String(ruleId));
}

function addDeletedRule(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    if (!deletedRules.some(r => String(r.categoryId) === catKey && String(r.ruleId) === ruleKey)) {
        deletedRules.push({ categoryId: catKey, ruleId: ruleKey });
        saveRulesListToStorage(DELETED_RULES_STORAGE_KEY, deletedRules);
    }
}

function removeDeletedRule(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    deletedRules = deletedRules.filter(r => !(String(r.categoryId) === catKey && String(r.ruleId) === ruleKey));
    saveRulesListToStorage(DELETED_RULES_STORAGE_KEY, deletedRules);
}

function addDisabledRule(rule, categoryIdOverride) {
    if (!rule) return;
    const catKey = String(categoryIdOverride !== undefined ? categoryIdOverride : rule.categoryId);
    const ruleKey = String(rule.id || rule.ruleId || '');
    if (!catKey || catKey === 'undefined' || !ruleKey) return;
    if (!disabledRules.some(r => String(r.categoryId) === catKey && String(r.id) === ruleKey)) {
        disabledRules.push({ ...rule, categoryId: catKey, id: ruleKey, _disabled: true });
        saveRulesListToStorage(DISABLED_RULES_STORAGE_KEY, disabledRules);
        setDisabledRulesDirty(true);
    }
}

function normalizeDisabledRules() {
    if (!Array.isArray(disabledRules) || disabledRules.length === 0) return;

    const ruleToCategory = new Map();
    if (Array.isArray(deletedRules)) {
        deletedRules.forEach((item) => {
            if (!item || !item.ruleId || !item.categoryId) return;
            ruleToCategory.set(String(item.ruleId), String(item.categoryId));
        });
    }

    let updated = false;
    disabledRules = disabledRules.map((rule) => {
        if (!rule) return rule;
        const ruleKey = String(rule.id || rule.ruleId || '');
        const catKey = rule.categoryId ? String(rule.categoryId) : '';
        if ((!catKey || catKey === 'undefined') && ruleKey) {
            const inferredCategory = ruleToCategory.get(ruleKey);
            if (inferredCategory) {
                updated = true;
                return { ...rule, categoryId: inferredCategory, id: ruleKey, _disabled: true };
            }
        }
        return rule;
    });

    if (updated) {
        saveRulesListToStorage(DISABLED_RULES_STORAGE_KEY, disabledRules);
    }
}

function removeDisabledRule(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    disabledRules = disabledRules.filter(r => !(String(r.categoryId) === catKey && String(r.id) === ruleKey));
    saveRulesListToStorage(DISABLED_RULES_STORAGE_KEY, disabledRules);
    setDisabledRulesDirty(true);
}

/**
 * Wist de opgeslagen parent password hash
 */
function clearParentPasswordHash() {
    parentPasswordHash = null;
    localStorage.removeItem('parentPasswordHash');
    if (typeof scheduleHaStorageShadowSync === 'function') {
        scheduleHaStorageShadowSync('parent-hash-clear');
    }
    console.log("[STATE] Parent password hash gewist");
}

/**
 * Initialiseert het concept EN slaat de originele data op voor change tracking
 */
function initializeDraft(data) {
    if (!data) return;
    currentDataDraft = JSON.parse(JSON.stringify(data));
    originalDataSnapshot = JSON.parse(JSON.stringify(data));
    changedRules.clear();

    disabledRules = loadRulesListFromStorage(DISABLED_RULES_STORAGE_KEY);
    deletedRules = loadRulesListFromStorage(DELETED_RULES_STORAGE_KEY);
    normalizeDisabledRules();
    mergeDisabledRulesIntoDraft(currentDataDraft);
    mergeDeletedRulesIntoDraft(currentDataDraft);
    
    // Sla parent password hash op voor HMAC-SHA512 signing
    if (data.parentPasswordHash) {
        parentPasswordHash = data.parentPasswordHash;
        console.log("Parent password hash opgeslagen voor sync signing.");
    }
    
    console.log("Concept-modus actief. Data geladen en snapshot opgeslagen voor change tracking.");
}

function refreshRuleViews() {
    if (typeof updateCategoryDisplay === 'function') {
        updateCategoryDisplay(currentDataDraft);
    }
    mergeDeletedRulesIntoDraft(currentDataDraft);
    if (typeof renderUsers === 'function') {
        renderUsers(currentDataDraft);
    }
    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

function mergeDisabledRulesIntoDraft(draft) {
    if (!draft) return;
    if (!Array.isArray(draft.rules)) {
        draft.rules = [];
    }
    if (!Array.isArray(disabledRules) || disabledRules.length === 0) return;

    disabledRules.forEach((rule) => {
        if (!rule || !rule.categoryId || !rule.id) return;
        const catKey = String(rule.categoryId);
        const ruleKey = String(rule.id);
        let category = draft.rules.find(r => String(r.categoryId) === catKey);
        if (!category) {
            category = { categoryId: catKey, rules: [] };
            draft.rules.push(category);
        }
        if (!Array.isArray(category.rules)) category.rules = [];
        const existing = category.rules.find(r => String(r.id) === ruleKey);
        if (existing) {
            existing._disabled = true;
        } else {
            category.rules.push({ ...rule, _disabled: true });
        }
    });
}

function mergeDeletedRulesIntoDraft(draft) {
    if (!draft || !Array.isArray(draft.rules)) return;

    const deletedSet = new Set(
        Array.isArray(deletedRules)
            ? deletedRules
                .filter(item => item && item.categoryId && item.ruleId)
                .map(item => `${String(item.categoryId)}::${String(item.ruleId)}`)
            : []
    );

    draft.rules.forEach((category) => {
        if (!category || !Array.isArray(category.rules)) return;
        const catKey = String(category.categoryId);
        category.rules.forEach((rule) => {
            if (!rule) return;
            const key = `${catKey}::${String(rule.id)}`;
            if (deletedSet.has(key)) {
                rule._deletedPending = true;
            } else if (rule._deletedPending) {
                delete rule._deletedPending;
            }
        });
    });
}

function mergePendingNewRules(data) {
    if (!data || !Array.isArray(data.rules)) return;
    if (!Array.isArray(newRules) || newRules.length === 0) return;

    newRules.forEach((rule) => {
        const categoryId = String(rule.categoryId);
        let categoryRules = data.rules.find(r => String(r.categoryId) === categoryId);
        if (!categoryRules) {
            categoryRules = { categoryId: rule.categoryId, rules: [] };
            data.rules.push(categoryRules);
        }
        const exists = (categoryRules.rules || []).some(r => String(r.id) === String(rule.id));
        if (!exists) {
            categoryRules.rules.push({ ...rule, _isNew: true });
        }
    });
}

function reconcileNewRules(data) {
    if (!Array.isArray(newRules) || newRules.length === 0) return;
    if (!data || !Array.isArray(data.rules)) return;

    const byCategory = new Map();
    data.rules.forEach((entry) => {
        const rules = Array.isArray(entry.rules) ? entry.rules : [];
        byCategory.set(String(entry.categoryId), rules.map(r => String(r.id)));
    });

    newRules = newRules.filter((rule) => {
        const catKey = String(rule.categoryId);
        const ruleIds = byCategory.get(catKey);
        if (!ruleIds) return true;
        const existsOnServer = ruleIds.includes(String(rule.id));
        if (existsOnServer && currentDataDraft && Array.isArray(currentDataDraft.rules)) {
            const draftCategory = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
            if (draftCategory && Array.isArray(draftCategory.rules)) {
                const draftRule = draftCategory.rules.find(r => String(r.id) === String(rule.id));
                if (draftRule) {
                    delete draftRule._isNew;
                }
            }
        }
        return !existsOnServer;
    });
}

/**
 * Converteert een bcrypt salt naar base64 voor HMAC signing
 * Bcrypt format: $2a$12$1234567890123456789012
 * We decoderen het bcrypt-base64 naar raw bytes, dan naar standaard base64
 */
function bcryptSaltToBase64(bcryptSalt) {
    // Extract de salt: na $2a$12$ (8 chars) volgen 22 chars salt
    const saltMatch = bcryptSalt.match(/\$2[aby]\$\d{2}\$(.{22})/);
    if (!saltMatch) {
        console.warn("[CRYPTO] Ongeldige bcrypt salt format:", bcryptSalt);
        return null;
    }
    
    const saltChars = saltMatch[1]; // 22 karakter bcrypt-base64
    console.log("[CRYPTO] Bcrypt salt gevonden (22 chars):", saltChars);
    
    // Bcrypt alphabet (aanvullend base64)
    const bcryptAlpha = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    
    // Decode bcrypt-base64 naar bytes
    let bits = 0;
    let bitCount = 0;
    const bytes = [];
    
    for (let i = 0; i < saltChars.length; i++) {
        const idx = bcryptAlpha.indexOf(saltChars[i]);
        if (idx === -1) {
            console.warn("[CRYPTO] Ongeldig karakter in bcrypt salt:", saltChars[i]);
            return null;
        }
        
        bits = (bits << 6) | idx;
        bitCount += 6;
        
        while (bitCount >= 8) {
            bitCount -= 8;
            bytes.push((bits >> bitCount) & 0xFF);
        }
    }
    
    console.log("[CRYPTO] Gedecodeerde bytes:", bytes.length, "bytes");
    
    // Zet bytes om naar standaard base64
    const binaryString = String.fromCharCode(...bytes);
    const base64 = btoa(binaryString);
    
    console.log("[CRYPTO] Bcrypt salt succesvol geconverteerd naar base64");
    console.log("[CRYPTO] Base64 result (first 30 chars):", base64.substring(0, 30) + "...");
    
    return base64;
}

/**
 * Stelt de parentPasswordHash in (gebruikt bij login om wachtwoord hashes opgeslagen)
 * Deze informatie is essentieel voor het HMAC-SHA512 signing van sync actions.
 * BELANGRIJK: Wordt opgeslagen in localStorage zodat het persistent blijft.
 * 
 * @param {Object} hashObject - { hash, secondHash, secondSalt }
 */
function storeparentPasswordHashForSync(hashObject) {
    if (!hashObject || !hashObject.secondSalt) {
        console.warn("[STATE] Ongeldige hash object, niet opgeslagen.");
        return;
    }
    
    // Converteer bcrypt salt naar base64 voor HMAC
    let base64Salt = hashObject.secondSalt;
    
    // Check of dit een bcrypt salt is (starts with $2a$, $2b$, $2y$)
    if (base64Salt.match(/^\$2[aby]\$/)) {
        console.log("[STATE] Bcrypt salt gedetecteerd, converteren naar base64...");
        const converted = bcryptSaltToBase64(base64Salt);
        if (converted) {
            base64Salt = converted;
        } else {
            console.error("[STATE] Bcrypt conversie gefaald, niet opgeslagen!");
            return;
        }
    }
    
    parentPasswordHash = {
        hash: hashObject.hash,
        secondHash: hashObject.secondHash,
        secondSalt: base64Salt
    };
    
    // CRUCIAAL: Sla op in localStorage zodat het na refresh/update beschikbaar blijft
    try {
        const toStore = {
            hash: parentPasswordHash.hash,
            secondHash: parentPasswordHash.secondHash,
            secondSalt: parentPasswordHash.secondSalt
        };
        localStorage.setItem('timelimit_parentPasswordHash', JSON.stringify(toStore));
        if (typeof scheduleHaStorageShadowSync === 'function') {
            scheduleHaStorageShadowSync('parent-hash-store');
        }
        console.log("✅ [STATE] Parent password hashes opgeslagen ZOWEL in RAM als localStorage.");
        console.log("   - hash:", parentPasswordHash.hash ? parentPasswordHash.hash.substring(0, 10) + "..." : "N/A");
        console.log("   - secondSalt (base64):", base64Salt.substring(0, 30) + "...");
    } catch (e) {
        console.error("[STATE] Kon niet in localStorage opslaan:", e.message);
    }
}

/**
 * Laadt de parentPasswordHash uit localStorage (wordt aangeroepen bij pagina-load)
 */
function loadParentPasswordHashFromStorage() {
    try {
        const stored = localStorage.getItem('timelimit_parentPasswordHash');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed && parsed.secondSalt) {
                parentPasswordHash = parsed;
                console.log("✅ [STATE] Parent password hashes HERSTELD uit localStorage.");
                console.log("   - hash:", parsed.hash ? parsed.hash.substring(0, 10) + "..." : "N/A");
                console.log("   - secondSalt (base64):", parsed.secondSalt.substring(0, 30) + "...");
                return true;
            }
        }
    } catch (e) {
        console.error("[STATE] Kon niet uit localStorage laden:", e.message);
    }
    console.log("[STATE] Geen opgeslagen parentPasswordHash gevonden.");
    return false;
}

/**
 * Reset de change tracking na succesvolle sync
 * Dit maakt de changedRules Map leeg zodat nieuwe wijzigingen kunnen worden getrackt
 */
function resetChangeTracking() {
    const previousSize = changedRules.size;
    changedRules.clear();
    console.log(`♻️ [STATE] Change tracking gereset (${previousSize} wijzigingen verwijderd)`);
    addLog(`♻️ Change tracking gereset - ${previousSize} wijzigingen verwerkt`, false);
    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

function hasPendingChanges() {
    const hasChangedRules = changedRules.size > 0;
    const hasNewRules = Array.isArray(newRules) && newRules.length > 0;
    const hasDeletedRules = Array.isArray(deletedRules) && deletedRules.length > 0;
    const hasNewApps = Array.isArray(newCategoryApps) && newCategoryApps.length > 0;
    const hasRemovedApps = Array.isArray(removedCategoryApps) && removedCategoryApps.length > 0;
    const hasDisabledRules = Array.isArray(disabledRules) && disabledRules.length > 0;
    return hasChangedRules || hasNewRules || hasDeletedRules || hasNewApps || hasRemovedApps || hasDisabledRules;
}

function updatePendingChangesIndicator() {
    const badge = document.getElementById('pending-badge');
    if (!badge) return;

    const pending = hasPendingChanges();
    if (!pending) {
        badge.style.display = 'none';
        return;
    }

    badge.style.display = 'inline-block';
    badge.innerText = 'Niet gesynchroniseerd';
    badge.className = 'status-badge status-pending';
}

function getNewCategoryApps() {
    return Array.isArray(newCategoryApps) ? [...newCategoryApps] : [];
}

function getRemovedCategoryApps() {
    return Array.isArray(removedCategoryApps) ? [...removedCategoryApps] : [];
}

function addAppToCategory(categoryId, packageName) {
    if (!currentDataDraft) {
        addLog('❌ Geen data geladen - doe eerst een pull sync', true);
        return;
    }
    if (!packageName) return;

    if (!Array.isArray(currentDataDraft.categoryApp)) {
        currentDataDraft.categoryApp = [];
    }

    const targetCategoryId = String(categoryId);
    const targetPackage = String(packageName);

    currentDataDraft.categoryApp.forEach((entry) => {
        if (String(entry.categoryId) === targetCategoryId) return;
        if (!Array.isArray(entry.apps)) return;
        const idx = entry.apps.findIndex(a => String(a) === targetPackage);
        if (idx >= 0) {
            entry.apps.splice(idx, 1);
            removedCategoryApps.push({ categoryId: String(entry.categoryId), packageName: targetPackage });
        }
    });

    let entry = currentDataDraft.categoryApp.find(a => String(a.categoryId) === targetCategoryId);
    if (!entry) {
        entry = { categoryId: targetCategoryId, apps: [] };
        currentDataDraft.categoryApp.push(entry);
    }
    if (!Array.isArray(entry.apps)) {
        entry.apps = [];
    }

    const exists = entry.apps.some(a => String(a) === targetPackage);
    if (exists) return;

    entry.apps.push(targetPackage);
    newCategoryApps.push({ categoryId: targetCategoryId, packageName: targetPackage });

    refreshRuleViews();
}

function mergePendingNewApps(data) {
    if (!data || !Array.isArray(data.categoryApp)) return;
    if (!Array.isArray(newCategoryApps) || newCategoryApps.length === 0) return;

    newCategoryApps.forEach((item) => {
        let entry = data.categoryApp.find(a => String(a.categoryId) === String(item.categoryId));
        if (!entry) {
            entry = { categoryId: item.categoryId, apps: [] };
            data.categoryApp.push(entry);
        }
        if (!Array.isArray(entry.apps)) entry.apps = [];
        if (!entry.apps.some(a => String(a) === String(item.packageName))) {
            entry.apps.push(item.packageName);
        }
    });
}

function mergePendingAppRemovals(data) {
    if (!data || !Array.isArray(data.categoryApp)) return;
    if (!Array.isArray(removedCategoryApps) || removedCategoryApps.length === 0) return;

    removedCategoryApps.forEach((item) => {
        const entry = data.categoryApp.find(a => String(a.categoryId) === String(item.categoryId));
        if (!entry || !Array.isArray(entry.apps)) return;
        entry.apps = entry.apps.filter(a => String(a) !== String(item.packageName));
    });
}

function reconcileRemovedApps(data) {
    if (!Array.isArray(removedCategoryApps) || removedCategoryApps.length === 0) return;
    if (!data || !Array.isArray(data.categoryApp)) return;

    const map = new Map();
    data.categoryApp.forEach((entry) => {
        map.set(String(entry.categoryId), new Set((entry.apps || []).map(a => String(a))));
    });

    removedCategoryApps = removedCategoryApps.filter((item) => {
        const set = map.get(String(item.categoryId));
        return !!(set && set.has(String(item.packageName)));
    });
}

function reconcileNewApps(data) {
    if (!Array.isArray(newCategoryApps) || newCategoryApps.length === 0) return;
    if (!data || !Array.isArray(data.categoryApp)) return;

    const map = new Map();
    data.categoryApp.forEach((entry) => {
        map.set(String(entry.categoryId), new Set((entry.apps || []).map(a => String(a))));
    });

    newCategoryApps = newCategoryApps.filter((item) => {
        const set = map.get(String(item.categoryId));
        return !(set && set.has(String(item.packageName)));
    });
}

function getNewRules() {
    return Array.isArray(newRules) ? [...newRules] : [];
}

function addRuleToCategory(categoryId, evt) {
    if (evt && typeof evt.stopPropagation === 'function') {
        evt.stopPropagation();
    }
    if (!currentDataDraft) {
        addLog('❌ Geen data geladen - doe eerst een pull sync', true);
        return;
    }

    if (!currentDataDraft.rules) {
        currentDataDraft.rules = [];
    }

    let categoryRules = currentDataDraft.rules.find(r => r.categoryId == categoryId);
    if (!categoryRules) {
        categoryRules = { categoryId: categoryId, rules: [] };
        currentDataDraft.rules.push(categoryRules);
    }

    const existingIds = new Set((categoryRules.rules || []).map(r => String(r.id)));
    let ruleId = null;
    if (typeof generateRandomId === 'function') {
        for (let i = 0; i < 10; i++) {
            const candidate = generateRandomId(6);
            if (!existingIds.has(String(candidate))) {
                ruleId = candidate;
                break;
            }
        }
    }
    if (!ruleId) {
        ruleId = String(Date.now());
    }

    const newRule = {
        id: ruleId,
        categoryId: categoryId,
        maxTime: 3600000,
        dayMask: 127,
        start: 0,
        end: 1439,
        perDay: true,
        extraTime: false,
        dur: 0,
        pause: 0,
        _isNew: true,
        _pendingNew: true
    };

    categoryRules.rules.push(newRule);
    newRules.push(newRule);

    if (typeof updateCategoryDisplay === 'function') {
        updateCategoryDisplay(currentDataDraft);
    }
    setTimeout(() => {
        try {
            const idMatch = String(categoryId).replace(/"/g, '\\"');
            const catItem = document.querySelector(`.tree-item[style*="margin-left:"] .tree-id`);
            const allTreeItems = document.querySelectorAll('.tree-item');
            let categoryHeader = null;
            allTreeItems.forEach((item) => {
                const idSpan = item.querySelector('.tree-id');
                if (idSpan && idSpan.textContent === String(categoryId)) {
                    categoryHeader = item;
                }
            });
            if (categoryHeader && typeof toggleNode === 'function') {
                if (!categoryHeader.classList.contains('is-open')) {
                    toggleNode(categoryHeader);
                }
                const content = categoryHeader.nextElementSibling;
                if (content) {
                    const rulesHeader = content.querySelector('.tree-item.folder-node');
                    if (rulesHeader && !rulesHeader.classList.contains('is-open')) {
                        toggleNode(rulesHeader);
                    }
                }
            }
        } catch (e) {
            // Best-effort only.
        }
    }, 0);
    if (typeof openRuleModal === 'function') {
        openRuleModal(String(categoryId), String(ruleId));
    }
}

/**
 * Zoekt en update de regel in het werkgeheugen
 */
function updateRuleInDraft(categoryId, ruleId, newValues) {
    if (!currentDataDraft || !currentDataDraft.rules) return;

    const category = currentDataDraft.rules.find(r => r.categoryId == categoryId);
    if (category) {
        const rule = category.rules.find(r => r.id == ruleId);
        if (rule) {
            // Sla de ORIGINELE waarden op als dit de eerste keer is dat deze regel wordt gewijzigd
            // Zorg voor consistente string-keys
            const key = `${String(categoryId)}_${String(ruleId)}`;
            if (!changedRules.has(key)) {
                const originalRule = originalDataSnapshot.rules
                    .find(c => c.categoryId == categoryId)?.rules
                    .find(r => r.id == ruleId);
                if (originalRule) {
                    changedRules.set(key, JSON.parse(JSON.stringify(originalRule)));
                    console.log(`[TRACK] Originele waarden opgeslagen voor key: ${key}`);
                }
            }
            
            Object.assign(rule, newValues);
            console.log(`Regel ${ruleId} bijgewerkt in concept. Status: GEWIJZIGD`);
        }
    }
}

/**
 * Haalt alle gewijzigde regels op
 * @returns {Array} Array met gewijzigde regel informatie
 */
function getChangedRules() {
    const changes = [];
    
    console.log("[DEBUG] changedRules Map size:", changedRules.size);
    console.log("[DEBUG] changedRules keys:", Array.from(changedRules.keys()));
    
    changedRules.forEach((originalRule, key) => {
        const [catIdStr, ruleIdStr] = key.split('_');
        // BELANGRIJK: categoryId is een STRING, GEEN getal!
        const categoryId = catIdStr;
        
        console.log(`[DEBUG] Zoeken naar rule: catId=${categoryId}, ruleId=${ruleIdStr}`);
        
        const category = currentDataDraft.rules?.find(c => c.categoryId == categoryId);
        if (!category) {
            console.warn(`[DEBUG] Categorie ${categoryId} niet gevonden!`);
            console.log(`[DEBUG] Beschikbare categorieën:`, currentDataDraft.rules?.map(c => c.categoryId));
            return;
        }
        
        // Probeer zowel als string als als getal
        let currentRule = category.rules?.find(r => String(r.id) === ruleIdStr || r.id == ruleIdStr);
        
        if (!currentRule) {
            console.warn(`[DEBUG] Regel ${ruleIdStr} niet gevonden in categorie ${categoryId}`);
            console.log(`[DEBUG] Beschikbare rules:`, category.rules?.map(r => r.id));
            return;
        }
        
        console.log(`[DEBUG] Regel gevonden! Origineel vs Huidig opslaan...`);
        changes.push({
            key,
            categoryId: categoryId,
            ruleId: ruleIdStr,
            original: originalRule,
            current: currentRule
        });
    });
    
    console.log(`[DEBUG] getChangedRules geeft ${changes.length} wijzigingen terug`);
    return changes;
}

/**
 * Controleert of een regel gewijzigd is
 */
function isRuleChanged(categoryId, ruleId) {
    const key = `${String(categoryId)}_${String(ruleId)}`;
    return changedRules.has(key);
}

function disableRule(categoryId, ruleId) {
    if (!currentDataDraft || !Array.isArray(currentDataDraft.rules)) return;
    if (isRuleDisabled(categoryId, ruleId)) return;

    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    const category = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
    if (!category || !Array.isArray(category.rules)) return;

    const ruleIndex = category.rules.findIndex(r => String(r.id) === ruleKey);
    if (ruleIndex === -1) return;

    const rule = category.rules[ruleIndex];
    rule._disabled = true;
    addDisabledRule(rule, catKey);

    const isNewRule = !ruleExistsInSnapshot(catKey, ruleKey) || !!rule._isNew;
    if (isNewRule) {
        newRules = newRules.filter(r => String(r.id) !== ruleKey || String(r.categoryId) !== catKey);
    } else {
        removeDeletedRule(catKey, ruleKey);
        if (rule._deletedPending) {
            delete rule._deletedPending;
        }
    }

    changedRules.delete(`${catKey}_${ruleKey}`);

    if (typeof renderUsers === 'function') {
        renderUsers(currentDataDraft);
    }
    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

function enableRule(categoryId, ruleId) {
    if (!currentDataDraft || !Array.isArray(currentDataDraft.rules)) return;
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);

    const disabledRule = disabledRules.find(r => String(r.categoryId) === catKey && String(r.id) === ruleKey);
    const deletePending = deletedRules.some(r => String(r.categoryId) === catKey && String(r.ruleId) === ruleKey);

    removeDisabledRule(catKey, ruleKey);
    removeDeletedRule(catKey, ruleKey);

    let category = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
    if (!category) {
        category = { categoryId: catKey, rules: [] };
        currentDataDraft.rules.push(category);
    }
    if (!Array.isArray(category.rules)) category.rules = [];
    const existingRule = category.rules.find(r => String(r.id) === ruleKey);

    if (existingRule) {
        existingRule._disabled = false;
    } else if (disabledRule) {
        const restoredRule = { ...disabledRule };
        delete restoredRule._disabled;
        category.rules.push(restoredRule);
    }

    const existsInSnapshot = ruleExistsInSnapshot(catKey, ruleKey);
    newRules = newRules.filter(r => !(String(r.id) === ruleKey && String(r.categoryId) === catKey));

    if (deletePending || !existsInSnapshot) {
        const sourceRule = existingRule || disabledRule;
        if (sourceRule) {
            const restoredRule = { ...sourceRule };
            delete restoredRule._disabled;
            newRules.push(restoredRule);
        }
    }

    if (typeof renderUsers === 'function') {
        renderUsers(currentDataDraft);
    }
}

function toggleRuleEnabled(categoryId, ruleId, enabled) {
    if (enabled) {
        enableRule(categoryId, ruleId);
    } else {
        disableRule(categoryId, ruleId);
    }
}

function deleteRule(categoryId, ruleId) {
    if (!currentDataDraft || !Array.isArray(currentDataDraft.rules)) return;

    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    const category = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
    if (!category || !Array.isArray(category.rules)) return;

    const ruleIndex = category.rules.findIndex(r => String(r.id) === ruleKey);
    if (ruleIndex === -1) return;

    const rule = category.rules[ruleIndex];
    const isNewRule = !ruleExistsInSnapshot(catKey, ruleKey) || !!rule._isNew;

    if (!isNewRule && rule._deletedPending) return;

    removeDisabledRule(catKey, ruleKey);

    if (isNewRule) {
        category.rules.splice(ruleIndex, 1);
        newRules = newRules.filter(r => String(r.id) !== ruleKey || String(r.categoryId) !== catKey);
    } else {
        rule._deletedPending = true;
        addDeletedRule(catKey, ruleKey);
    }

    changedRules.delete(`${catKey}_${ruleKey}`);

    if (typeof refreshRuleViews === 'function') {
        refreshRuleViews();
    }
    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

function isRuleDeletePending(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);
    if (Array.isArray(deletedRules)) {
        if (deletedRules.some(r => String(r.categoryId) === catKey && String(r.ruleId) === ruleKey)) {
            return true;
        }
    }
    if (currentDataDraft && Array.isArray(currentDataDraft.rules)) {
        const category = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
        const rule = category && Array.isArray(category.rules)
            ? category.rules.find(r => String(r.id) === ruleKey)
            : null;
        if (rule && rule._deletedPending) return true;
    }
    return false;
}

function restoreDeletedRule(categoryId, ruleId) {
    const catKey = String(categoryId);
    const ruleKey = String(ruleId);

    removeDeletedRule(catKey, ruleKey);

    if (currentDataDraft && Array.isArray(currentDataDraft.rules)) {
        let category = currentDataDraft.rules.find(r => String(r.categoryId) === catKey);
        if (!category) {
            category = { categoryId: catKey, rules: [] };
            currentDataDraft.rules.push(category);
        }
        if (!Array.isArray(category.rules)) category.rules = [];

        let rule = category.rules.find(r => String(r.id) === ruleKey);
        if (rule) {
            rule._deletedPending = false;
        } else if (originalDataSnapshot && Array.isArray(originalDataSnapshot.rules)) {
            const originalCategory = originalDataSnapshot.rules.find(r => String(r.categoryId) === catKey);
            const originalRule = originalCategory && Array.isArray(originalCategory.rules)
                ? originalCategory.rules.find(r => String(r.id) === ruleKey)
                : null;
            if (originalRule) {
                category.rules.push({ ...originalRule });
            }
        }
    }

    if (typeof refreshRuleViews === 'function') {
        refreshRuleViews();
    }
    if (typeof updatePendingChangesIndicator === 'function') {
        updatePendingChangesIndicator();
    }
}

function restoreDeletedRuleFromModal() {
    const catId = document.getElementById('edit-cat-id')?.value;
    const ruleId = document.getElementById('edit-rule-id')?.value;
    if (!catId || !ruleId) return;

    restoreDeletedRule(catId, ruleId);
    closeModal();
}

function deleteRuleFromModal() {
    const catId = document.getElementById('edit-cat-id')?.value;
    const ruleId = document.getElementById('edit-rule-id')?.value;
    if (!catId || !ruleId) return;

    if (!confirm('Weet je zeker dat je deze regel wilt verwijderen?')) return;

    deleteRule(catId, ruleId);
    closeModal();
}

function reconcileDeletedRules(data) {
    if (!Array.isArray(deletedRules) || deletedRules.length === 0) return;
    if (!data || !Array.isArray(data.rules)) return;

    const byCategory = new Map();
    data.rules.forEach((entry) => {
        const rules = Array.isArray(entry.rules) ? entry.rules : [];
        byCategory.set(String(entry.categoryId), rules.map(r => String(r.id)));
    });

    deletedRules = deletedRules.filter((item) => {
        const ruleIds = byCategory.get(String(item.categoryId));
        return !!(ruleIds && ruleIds.includes(String(item.ruleId)));
    });
    saveRulesListToStorage(DELETED_RULES_STORAGE_KEY, deletedRules);
}

/**
 * Reset alle wijzigingen
 */
function resetAllChanges() {
    if (originalDataSnapshot) {
        currentDataDraft = JSON.parse(JSON.stringify(originalDataSnapshot));
        changedRules.clear();
        console.log("Alle wijzigingen teruggedraaid!");
        refreshRuleViews();
    }
}

/**
 * Opent de modal en vertaalt MS en Minuten naar leesbare UI velden
 */
function setRuleModalReadonly(isReadonly) {
    const modal = document.getElementById('rule-modal');
    const modalContent = modal ? modal.querySelector('.modal-content') : null;
    if (modalContent) {
        modalContent.classList.toggle('rule-modal-readonly', !!isReadonly);
    }

    const inputIds = [
        'input-hours',
        'input-minutes',
        'input-start-time',
        'input-end-time',
        'field-perDay',
        'field-dayMask'
    ];

    inputIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = !!isReadonly;
    });

    document.querySelectorAll('#rule-modal .day-btn').forEach((btn) => {
        btn.disabled = !!isReadonly;
    });

    const saveBtn = document.getElementById('save-rule-btn');
    if (saveBtn) saveBtn.disabled = !!isReadonly;
}

function openRuleModal(catId, ruleId) {
    console.log("Trigger: Modal openen voor Cat:", catId, "Rule:", ruleId);
    
    if (!currentDataDraft || !currentDataDraft.rules) {
        console.error("Geen data beschikbaar.");
        return;
    }

    const category = currentDataDraft.rules.find(c => c.categoryId == catId);
    const rule = category ? category.rules.find(r => r.id == ruleId) : null;

    if (!rule) {
        console.error("Regel niet gevonden.");
        return;
    }

    if (rule._isNew && rule._pendingNew) {
        pendingNewRule = { catId: String(catId), ruleId: String(ruleId) };
        pendingNewRuleSaved = false;
    } else {
        pendingNewRule = null;
        pendingNewRuleSaved = false;
    }

    const isNewRule = !ruleExistsInSnapshot(catId, ruleId) || !!rule._isNew || !!rule._pendingNew;
    const isDeleted = !!rule._deletedPending || isRuleDeletePending(catId, ruleId);

    const deleteBtn = document.getElementById('delete-rule-btn');
    if (deleteBtn) {
        deleteBtn.style.display = (isNewRule || isDeleted) ? 'none' : 'block';
    }

    const restoreBtn = document.getElementById('restore-rule-btn');
    if (restoreBtn) {
        restoreBtn.style.display = isDeleted ? 'block' : 'none';
    }

    setRuleModalReadonly(isDeleted);

    // 1. Basis ID's opslaan
    document.getElementById('edit-cat-id').value = catId;
    document.getElementById('edit-rule-id').value = ruleId;

    // 2. MAX TIME CONVERSIE: ms naar uren en minuten
    const totalMs = rule.maxTime || 0;
    const totalMinutesLimit = Math.floor(totalMs / 60000); 
    document.getElementById('input-hours').value = Math.floor(totalMinutesLimit / 60);
    document.getElementById('input-minutes').value = totalMinutesLimit % 60;
    document.getElementById('field-maxTime').value = totalMs;

    // 3. START/END CONVERSIE: minuten naar HH:mm string voor tijd-input
    const startMin = rule.start || 0;
    const endMin = rule.end || 0;
    document.getElementById('input-start-time').value = minToTimeString(startMin);
    document.getElementById('input-end-time').value = minToTimeString(endMin);
    
    // Hidden fields voor de ruwe waarden
      document.getElementById('field-perDay').checked = !!rule.perDay;

    // 4. Dag-masker
    const mask = rule.dayMask || 0;
    document.getElementById('field-dayMask').value = mask;
    setButtonsFromMask(mask); 

    const modal = document.getElementById('rule-modal');
    if (modal) modal.classList.add('is-visible');
}

/**
 * Slaat de wijzigingen op en vertaalt UI waarden terug naar MS en Minuten
 */
function saveModalChanges() {
    const catId = document.getElementById('edit-cat-id').value;
    const ruleId = document.getElementById('edit-rule-id').value;
    
    console.log(`[DEBUG] saveModalChanges - catId=${catId} (type: ${typeof catId}), ruleId=${ruleId} (type: ${typeof ruleId})`);

    // Bereken MS voor de limiet: ((uren * 60) + minuten) * 60.000
    const h = parseInt(document.getElementById('input-hours').value) || 0;
    const m = parseInt(document.getElementById('input-minutes').value) || 0;
    const totalMs = ((h * 60) + m) * 60000;

    // Bereken Minuten voor de blokkade tijden
    const startMin = timeStringToMin(document.getElementById('input-start-time').value);
    const endMin = timeStringToMin(document.getElementById('input-end-time').value);

    const updatedValues = {
        dayMask: parseInt(document.getElementById('field-dayMask').value),
        maxTime: totalMs,
        start: startMin,
        end: endMin,
        perDay: document.getElementById('field-perDay').checked
    };

    console.log(`[DEBUG] Aangepaste waarden:`, updatedValues);
    updateRuleInDraft(catId, ruleId, updatedValues);
    if (pendingNewRule && pendingNewRule.ruleId === String(ruleId)) {
        pendingNewRuleSaved = true;
        const category = currentDataDraft.rules.find(r => r.categoryId == catId);
        if (category) {
            const rule = category.rules.find(r => r.id == ruleId);
            if (rule) {
                rule._pendingNew = false;
            }
        }
    }
    closeModal();
    
    refreshRuleViews();
}

/**
 * Hulpfuncties voor TIJD (Minuten <-> String HH:mm)
 */
function minToTimeString(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

function timeStringToMin(timeString) {
    if (!timeString) return 0;
    const [hours, mins] = timeString.split(':').map(Number);
    return (hours * 60) + mins;
}

/**
 * Hulpfuncties voor de DAG-KNOPPEN
 */
function setButtonsFromMask(mask) {
    document.querySelectorAll('.day-btn').forEach(btn => {
        const bit = parseInt(btn.getAttribute('data-bit'));
        if ((mask & bit) === bit) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function updateMaskFromButtons() {
    let mask = 0;
    document.querySelectorAll('.day-btn.active').forEach(btn => {
        mask += parseInt(btn.getAttribute('data-bit'));
    });
    document.getElementById('field-dayMask').value = mask;
}

function closeModal() {
    if (pendingNewRule && !pendingNewRuleSaved) {
        const catId = pendingNewRule.catId;
        const ruleId = pendingNewRule.ruleId;

        if (currentDataDraft && Array.isArray(currentDataDraft.rules)) {
            const category = currentDataDraft.rules.find(r => r.categoryId == catId);
            if (category && Array.isArray(category.rules)) {
                category.rules = category.rules.filter(r => String(r.id) !== String(ruleId));
            }
        }

        if (Array.isArray(newRules)) {
            newRules = newRules.filter(r => String(r.id) !== String(ruleId));
        }

        refreshRuleViews();
    }

    pendingNewRule = null;
    pendingNewRuleSaved = false;
    document.getElementById('rule-modal').classList.remove('is-visible');
}

// Global scope expose
window.openRuleModal = openRuleModal;
window.addRuleToCategory = addRuleToCategory;
window.getNewRules = getNewRules;
window.mergePendingNewRules = mergePendingNewRules;
window.addAppToCategory = addAppToCategory;
window.getNewCategoryApps = getNewCategoryApps;
window.mergePendingNewApps = mergePendingNewApps;
window.reconcileNewApps = reconcileNewApps;
window.getRemovedCategoryApps = getRemovedCategoryApps;
window.mergePendingAppRemovals = mergePendingAppRemovals;
window.reconcileRemovedApps = reconcileRemovedApps;
window.disableRule = disableRule;
window.enableRule = enableRule;
window.toggleRuleEnabled = toggleRuleEnabled;
window.deleteRule = deleteRule;
window.deleteRuleFromModal = deleteRuleFromModal;
window.restoreDeletedRule = restoreDeletedRule;
window.restoreDeletedRuleFromModal = restoreDeletedRuleFromModal;
window.isRuleDisabled = isRuleDisabled;
window.getDisabledRules = getDisabledRules;
window.getDeletedRules = getDeletedRules;
window.reconcileDeletedRules = reconcileDeletedRules;
window.hasPendingChanges = hasPendingChanges;
window.updatePendingChangesIndicator = updatePendingChangesIndicator;
window.clearDisabledRulesDirty = clearDisabledRulesDirty;

// Event Listeners voor de dag-knoppen
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('day-btn')) {
        e.target.classList.toggle('active');
        updateMaskFromButtons();
    }
});