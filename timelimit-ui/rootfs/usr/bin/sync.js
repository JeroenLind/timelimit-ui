/**
 * sync.js - Afhandeling van handmatige en automatische sync
 */

let syncTimer = null;
let secondsCounter = 0;
const SYNC_INTERVAL = 30; // seconden

async function runSync() {
    const badge = document.getElementById('status-badge');
    const jsonView = document.getElementById('json-view');

    if (!TOKEN || TOKEN === "" || TOKEN.includes("#")) {
        addLog("Sync overgeslagen: Geen geldig token.", true);
        return;
    }

    const syncPayload = {
        deviceAuthToken: TOKEN,
        status: { apps: {}, categories: {}, devices: "0", users: "0", clientLevel: 8 }
    };

    addLog("Syncing data...");
    secondsCounter = 0;

    try {
        const res = await fetch('sync/pull-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(syncPayload)
        });

        // --- DE CRUCIALE CHECK ---
        const contentType = res.headers.get("content-type");
        let responseData;

        if (res.ok && contentType && contentType.includes("application/json")) {
            // Alleen parsen als de status 200 (OK) is EN het JSON is
            responseData = await res.json();
            
            addLog("Sync voltooid.");
            badge.innerText = "Online";
            badge.className = "status-badge status-online";
            renderUsers(responseData);

            initializeDraft(responseData);
           
            if (typeof updateCategoryDisplay === "function") {
              updateCategoryDisplay(responseData);
            }
        } else {
            // De server stuurde een fout (401) of HTML. Lees als tekst om crash te voorkomen.
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

        // Inspector bijwerken met wat we ook maar ontvangen hebben
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
    }
}


// De achtergrond-loop
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
            
            // Toon voortgang op de badge (optioneel, voor visuele feedback)
            if (badge.innerText.includes("Online")) {
                badge.innerText = `Online (${SYNC_INTERVAL - secondsCounter}s)`;
            }

            if (secondsCounter >= SYNC_INTERVAL) {
                runSync();
            }
        } else {
            secondsCounter = 0; // Reset teller als schakelaar uit staat
        }
    }, 1000); // Check elke seconde
}

// Start de loop zodra het script geladen is
startSyncLoop();

/**
 * SYNC HELPERS - Voor rule wijzigingen versturen naar server
 */

/**
 * Zet een change object om naar SerializedUpdateTimelimitRuleAction format
 * change = { ruleId, categoryId, original: {...}, current: {...} }
 * 
 * VELDMAPPING:
 * - maxTime → time (milliseconden)
 * - dayMask → days (bitmask)
 */
function buildUpdateRuleAction(change) {
    const current = change.current;
    
    // DEBUG: Log wat we in current hebben
    console.log(`[SYNC DEBUG] Building action for rule ${change.ruleId}:`);
    console.log(`  current object:`, current);
    console.log(`  current.maxTime:`, current.maxTime);
    console.log(`  current.dayMask:`, current.dayMask);
    
    const action = {
        type: "UPDATE_TIMELIMIT_RULE",
        ruleId: String(change.ruleId),
        // MAPPING: maxTime → time, dayMask → days
        time: Number(current.maxTime !== undefined ? current.maxTime : (current.time || 0)),
        days: Number(current.dayMask !== undefined ? current.dayMask : (current.days || 0)),
        extraTime: Boolean(current.extraTime || false)
    };
    
    console.log(`  → action.time: ${action.time}, action.days: ${action.days}`);
    
    // Voeg optionele velden toe als ze aanwezig zijn
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

/**
 * Berekent HMAC-SHA512 integrity hash
 * Momenteel placeholder - geeft "device" terug zodat we kunnen testen zonder echte signing
 */
async function calculateIntegrity(sequenceNumber, deviceId, encodedAction) {
    // TODO: Implementeer echte HMAC-SHA512 met secondSalt uit parent password
    // Voor nu: return "device" zodat we kunnen testen zonder signing
    
    // In werkelijkheid zou dit zijn:
    // const crypto = require('crypto');
    // const hash = crypto.createHmac('sha512', secondSalt)
    //     .update(sequenceNumber + "|" + deviceId + "|" + encodedAction)
    //     .digest('base64');
    
    return "device"; // Placeholder voor test
}

/**
 * Bundelt alle changes in acties voor verzending (max 50 per batch)
 */
function prepareSync() {
    const changes = getChangedRules();
    
    if (changes.length === 0) {
        addLog("Geen wijzigingen om te synchroniseren.", false);
        return { batches: [], totalActions: 0 };
    }
    
    const batches = [];
    let currentBatch = [];
    let sequenceNumber = 1;
    
    changes.forEach(change => {
        const action = buildUpdateRuleAction(change);
        const encodedAction = JSON.stringify(action);
        
        currentBatch.push({
            sequenceNumber: sequenceNumber,
            encodedAction: encodedAction,
            action: action // Ook het originele object voor debugging
        });
        
        sequenceNumber++;
        
        // Start nieuwe batch als we 50 bereikt hebben
        if (currentBatch.length === 50) {
            batches.push(currentBatch);
            currentBatch = [];
        }
    });
    
    // Voeg resterende acties toe
    if (currentBatch.length > 0) {
        batches.push(currentBatch);
    }
    
    addLog(`✅ ${changes.length} wijzigingen voorbereidt in ${batches.length} batch(es)`, false);
    
    return {
        batches: batches,
        totalActions: changes.length,
        changes: changes
    };
}

/**
 * TEST versie: Bereid acties voor en log naar console/UI zonder daadwerkelijk te versturen
 */
async function testSyncActions() {
    addLog("🧪 TEST SYNC: Acties worden voorbereidt...", false);
    
    const syncData = prepareSync();
    
    if (syncData.totalActions === 0) {
        return;
    }
    
    // Log naar inspector
    const jsonView = document.getElementById('json-view');
    const timestamp = new Date().toLocaleTimeString();
    const separator = `\n\n${"=".repeat(20)} TEST SYNC @ ${timestamp} ${"=".repeat(20)}\n`;
    
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
        logContent += `    Voor: ${JSON.stringify(change.original, null, 2).replace(/\n/g, '\n    ')}\n`;
        logContent += `    Na:   ${JSON.stringify(change.current, null, 2).replace(/\n/g, '\n    ')}\n`;
    });
    
    logContent += `\n--- ACTIES PER BATCH ---\n`;
    
    syncData.batches.forEach((batch, batchIdx) => {
        logContent += `\nBatch ${batchIdx + 1} (${batch.length} acties):\n`;
        batch.forEach(item => {
            logContent += `  [Seq ${item.sequenceNumber}] ${JSON.stringify(item.action, null, 2).replace(/\n/g, '\n  ')}\n`;
        });
    });
    
    logContent += `\n--- VOLLEDIGE PAYLOAD (zou verzonden worden) ---\n`;
    
    // Simuleer integrity signing (momenteel "device" placeholder)
    const deviceId = "test-device"; // TODO: Haal echte deviceId op
    const firstBatch = syncData.batches[0];
    
    const mockPayload = {
        actions: firstBatch.map(item => ({
            sequenceNumber: item.sequenceNumber,
            encodedAction: item.encodedAction,
            integrity: "device" // Placeholder
        }))
    };
    
    logContent += `\n${JSON.stringify(mockPayload, null, 2)}\n`;
    logContent += `\n⚠️  DEZE DATA WORDT NIET DAADWERKELIJK VERZONDEN (TEST MODUS)\n`;
    
    // Log naar console
    console.log("🧪 TEST SYNC DATA:", syncData);
    console.log("📤 MOCK PAYLOAD:", mockPayload);
    
    // Log naar inspector
    if (jsonView.textContent.length > 100000) {
        jsonView.textContent = jsonView.textContent.slice(-50000);
    }
    jsonView.textContent += separator + logContent;
    jsonView.scrollTop = jsonView.scrollHeight;
    
    addLog("✅ TEST SYNC voltooid - Check inspector-panel en browser console", false);
}