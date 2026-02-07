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
    
    const action = {
        type: "UPDATE_TIMELIMIT_RULE",
        ruleId: String(change.ruleId),
        // MAPPING: maxTime → time, dayMask → days
        time: Number(current.maxTime !== undefined ? current.maxTime : (current.time || 0)),
        days: Number(current.dayMask !== undefined ? current.dayMask : (current.days || 0)),
        extraTime: Boolean(current.extraTime || false)
    };
    
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
 * Berekent HMAC-SHA512 integrity hash met WebCrypto API
 * 
 * HMAC-SHA512(
 *   key = parentPasswordHash.secondSalt (base64),
 *   message = sequenceNumber + "|" + deviceId + "|" + encodedAction
 * )
 * 
 * @returns {string} Base64-encoded HMAC hash of "device" fallback
 */
async function calculateIntegrity(sequenceNumber, deviceId, encodedAction) {
    try {
        // Check of we parentPasswordHash hebben
        if (!parentPasswordHash || !parentPasswordHash.secondSalt) {
            console.warn("[INTEGRITY] Geen parentPasswordHash beschikbaar, fallback op 'device'");
            return "device";
        }
        
        // Decode secondSalt van base64
        const secondSalt = parentPasswordHash.secondSalt;
        
        let saltBytes;
        try {
            saltBytes = Uint8Array.from(atob(secondSalt), c => c.charCodeAt(0));
        } catch (decodeError) {
            console.error("[INTEGRITY] DECODE ERROR - secondSalt is geen geldige base64:", secondSalt.substring(0, 30) + "...");
            console.error("[INTEGRITY] atob() failed:", decodeError.message);
            return "device"; // Fallback
        }
        
        // Bouw message: sequenceNumber|deviceId|encodedAction
        const message = `${sequenceNumber}|${deviceId}|${encodedAction}`;
        const messageBytes = new TextEncoder().encode(message);
        
        // Importeer de key (HMAC with SHA-512)
        const key = await crypto.subtle.importKey(
            "raw",
            saltBytes,
            { name: "HMAC", hash: "SHA-512" },
            false,
            ["sign"]
        );
        
        // Bereken HMAC-SHA512
        const hashBuffer = await crypto.subtle.sign("HMAC", key, messageBytes);
        
        // Encode naar base64
        const hashBytes = new Uint8Array(hashBuffer);
        const binaryString = String.fromCharCode(...hashBytes);
        const base64Hash = btoa(binaryString);
        
        console.log(`✅ [INTEGRITY] HMAC-SHA512 succesvol berekend voor seq ${sequenceNumber}`);
        return base64Hash;
        
    } catch (error) {
        console.error("[INTEGRITY] Fout bij HMAC-SHA512 berekening:", error.message);
        console.error("[INTEGRITY] FALLBACK op 'device'");
        return "device"; // Fallback
    }
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
 * TEST versie: Bereid acties voor EN bereken echte integrity hashes
 * Log naar console/UI zonder daadwerkelijk te versturen
 */
async function testSyncActions() {
    addLog("🧪 TEST SYNC: Acties worden voorbereid met HMAC-SHA512 signing...", false);

    const syncData = prepareSync();

    if (syncData.totalActions === 0) {
        return;
    }

    // Log naar inspector
    const jsonView = document.getElementById("json-view");
    const timestamp = new Date().toLocaleTimeString();
    const separator = `\n\n${"=".repeat(20)} TEST SYNC @ ${timestamp} ${"=".repeat(20)}\n`;

    // ✅ DIAGNOSTISCHE INFO: parentPasswordHash status
    console.log("=== INTEGRITY SETUP DEBUG ===");
    console.log("parentPasswordHash beschikbaar?", !!parentPasswordHash);
    if (parentPasswordHash) {
        console.log("  - hash:", parentPasswordHash.hash ? parentPasswordHash.hash.substring(0, 20) + "..." : "❌ MISSING");
        console.log("  - secondHash:", parentPasswordHash.secondHash ? parentPasswordHash.secondHash.substring(0, 20) + "..." : "❌ MISSING");
        console.log("  - secondSalt:", parentPasswordHash.secondSalt ? parentPasswordHash.secondSalt.substring(0, 20) + "..." : "❌ MISSING");
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

    if (!parentPasswordHash || !parentPasswordHash.secondSalt) {
        logContent += "\n⚠️  Geen parentPasswordHash.secondSalt beschikbaar; fallback op 'device'\n";
    }

    // Haal deviceId (standaard gok: "device1")
    const deviceId = "device1"; // TODO: Haal echte deviceId op
    const firstBatch = syncData.batches[0];

    // Bereken integrity voor elke actie
    const mockPayload = {
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
                integrity: integrity
            });
        }

        logContent += `\n${JSON.stringify(mockPayload, null, 2)}\n`;
        if (usedFallback) {
            logContent += "\n⚠️  INTEGRITY HASHING: fallback gebruikt (integrity = 'device')\n";
        } else {
            logContent += "\n✅ INTEGRITY HASHING: HMAC-SHA512 berekend\n";
        }
    } catch (error) {
        logContent += `\n❌ FOUT bij integrity berekening: ${error.message}\n`;
        logContent += "Fallback op 'device' placeholder\n";

        mockPayload.actions = firstBatch.map(item => ({
            sequenceNumber: item.sequenceNumber,
            encodedAction: item.encodedAction,
            integrity: "device"
        }));

        logContent += `${JSON.stringify(mockPayload, null, 2)}\n`;
    }

    logContent += "\n⚠️  DEZE DATA WORDT NIET DAADWERKELIJK VERZONDEN (TEST MODUS)\n";

    // Log naar console
    console.log("🧪 TEST SYNC DATA:", syncData);
    console.log("📤 PAYLOAD MET SIGNING:", mockPayload);

    // Log naar inspector
    if (jsonView.textContent.length > 100000) {
        jsonView.textContent = jsonView.textContent.slice(-50000);
    }
    jsonView.textContent += separator + logContent;
    jsonView.scrollTop = jsonView.scrollHeight;

    addLog("✅ TEST SYNC voltooid - HMAC-SHA512 integrity berekend - Check inspector-panel en browser console", false);
}
