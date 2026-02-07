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
        // Check crypto API beschikbaarheid
        console.log("[INTEGRITY] Crypto check - window.crypto:", !!window.crypto);
        console.log("[INTEGRITY] Crypto check - crypto.subtle:", !!(window.crypto && window.crypto.subtle));
        console.log("[INTEGRITY] Crypto check - self.crypto:", !!self.crypto);
        
        const cryptoObj = window.crypto || self.crypto || crypto;
        const hasSubtle = cryptoObj && cryptoObj.subtle;
        
        if (!hasSubtle) {
            console.warn("[INTEGRITY] WebCrypto API niet beschikbaar - gebruik server fallback");
            console.log("[INTEGRITY] Protocol =", window.location.protocol);
            console.log("[INTEGRITY] Is secure context?", window.isSecureContext);
        }
        
        // Check of we parentPasswordHash hebben
        if (!parentPasswordHash) {
            console.warn("[INTEGRITY] parentPasswordHash is null/undefined, fallback op 'device'");
            return "device";
        }
        
        if (!parentPasswordHash.secondSalt) {
            console.warn("[INTEGRITY] parentPasswordHash.secondSalt is null/undefined, fallback op 'device'");
            console.log("[INTEGRITY] parentPasswordHash beschikbare velden:", Object.keys(parentPasswordHash));
            return "device";
        }
        
        const secondSalt = parentPasswordHash.secondSalt;
        console.log("[INTEGRITY] secondSalt ontvangen (eerste 30 chars):", secondSalt.substring(0, 30) + "...");
        
        // NIEUWE LOGICA: Als crypto.subtle niet beschikbaar is, gebruik server-side berekening
        if (!hasSubtle) {
            console.log("[INTEGRITY] 🔄 Server-side HMAC berekening aanroepen...");
            
            const message = `${sequenceNumber}|${deviceId}|${encodedAction}`;
            
            try {
                const response = await fetch('calculate-hmac', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        key: secondSalt,
                        message: message
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }
                
                const result = await response.json();
                console.log(`✅ [INTEGRITY] Server-side HMAC-SHA512 succesvol voor seq ${sequenceNumber}`);
                console.log(`   Hash (eerste 30 chars): ${result.hash.substring(0, 30)}...`);
                return result.hash;
                
            } catch (serverError) {
                console.error("[INTEGRITY] Server-side HMAC fout:", serverError.message);
                return "device";
            }
        }
        
        // ORIGINELE LOGICA: Browser-side WebCrypto (alleen bij HTTPS/secure context)
        console.log("[INTEGRITY] ✨ Client-side WebCrypto HMAC berekening...");
        
        let saltBytes;
        try {
            saltBytes = Uint8Array.from(atob(secondSalt), c => c.charCodeAt(0));
            console.log("[INTEGRITY] secondSalt decodeert naar", saltBytes.length, "bytes");
        } catch (decodeError) {
            console.error("[INTEGRITY] ❌ Base64 decode fout - secondSalt is geen geldige base64!");
            console.error("[INTEGRITY] secondSalt waarde:", secondSalt.substring(0, 50));
            console.error("[INTEGRITY] Decode error:", decodeError.message);
            return "device";
        }
        
        // Bouw message: sequenceNumber|deviceId|encodedAction
        const message = `${sequenceNumber}|${deviceId}|${encodedAction}`;
        const messageBytes = new TextEncoder().encode(message);
        console.log("[INTEGRITY] Message gebouwd:", message.length, "bytes");
        
        // Importeer de key (HMAC with SHA-512)
        console.log("[INTEGRITY] Key importeren als HMAC-SHA512...");
        const key = await cryptoObj.subtle.importKey(
            "raw",
            saltBytes,
            { name: "HMAC", hash: "SHA-512" },
            false,
            ["sign"]
        );
        console.log("[INTEGRITY] Key succesvol geïmporteerd");
        
        // Bereken HMAC-SHA512
        console.log("[INTEGRITY] HMAC-SHA512 signing...");
        const hashBuffer = await cryptoObj.subtle.sign("HMAC", key, messageBytes);
        console.log("[INTEGRITY] Signing compleet, hash =", hashBuffer.byteLength, "bytes");
        
        // Encode naar base64
        const hashBytes = new Uint8Array(hashBuffer);
        const binaryString = String.fromCharCode(...hashBytes);
        const base64Hash = btoa(binaryString);
        
        console.log(`✅ [INTEGRITY] Client-side HMAC-SHA512 succesvol voor seq ${sequenceNumber}`);
        console.log(`   Hash (eerste 30 chars): ${base64Hash.substring(0, 30)}...`);
        return base64Hash;
        
    } catch (error) {
        console.error("[INTEGRITY] ❌ FOUT bij HMAC-SHA512 berekening:");
        console.error("  - Error type:", error.constructor.name);
        console.error("  - Message:", error.message);
        console.error("  - Stack:", error.stack);
        console.error("[INTEGRITY] FALLBACK op 'device'");
        return "device";
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
/**
 * ECHTE SYNC: Verstuurt wijzigingen naar de server via /sync/push-actions
 * Met uitgebreide logging van alle server responses
 */
async function executePushSync() {
    const jsonView = document.getElementById("json-view");
    const timestamp = new Date().toLocaleTimeString();
    const separator = `\n\n${"=".repeat(20)} PUSH SYNC @ ${timestamp} ${"=".repeat(20)}\n`;
    
    addLog("🚀 PUSH SYNC starten...", false);
    console.log("=== PUSH SYNC GESTART ===");
    
    // Check TOKEN
    if (!TOKEN || TOKEN === "" || TOKEN.includes("#")) {
        addLog("❌ Geen geldig token beschikbaar!", true);
        console.error("[PUSH-SYNC] Geen geldig token");
        return;
    }
    
    // Check parentPasswordHash
    if (!parentPasswordHash || !parentPasswordHash.secondSalt) {
        addLog("❌ Geen wachtwoord hashes beschikbaar voor signing! Klik eerst op 'Wachtwoord Hashes Bijwerken'.", true);
        console.error("[PUSH-SYNC] Geen parentPasswordHash voor integrity signing");
        return;
    }
    
    console.log("[PUSH-SYNC] Token check: OK");
    console.log("[PUSH-SYNC] parentPasswordHash check: OK");
    
    // Bereid acties voor
    const syncData = prepareSync();
    
    if (syncData.totalActions === 0) {
        addLog("ℹ️ Geen wijzigingen om te synchroniseren.", false);
        console.log("[PUSH-SYNC] Geen wijzigingen gevonden");
        return;
    }
    
    console.log(`[PUSH-SYNC] ${syncData.totalActions} wijzigingen gevonden in ${syncData.batches.length} batch(es)`);
    addLog(`📦 ${syncData.totalActions} wijzigingen gevonden...`, false);
    
    // Haal deviceId op (gebruik standaard als niet beschikbaar)
    const deviceId = currentDataDraft?.deviceId || "device1";
    console.log(`[PUSH-SYNC] DeviceId: ${deviceId}`);
    
    let logContent = `PUSH SYNC NAAR SERVER\n`;
    logContent += `Timestamp: ${timestamp}\n`;
    logContent += `Token: ${TOKEN.substring(0, 10)}...\n`;
    logContent += `DeviceId: ${deviceId}\n`;
    logContent += `Totaal wijzigingen: ${syncData.totalActions}\n`;
    logContent += `Aantal batches: ${syncData.batches.length}\n\n`;
    
    // Process elke batch
    let successfulBatches = 0;
    let failedBatches = 0;
    
    for (let batchIdx = 0; batchIdx < syncData.batches.length; batchIdx++) {
        const batch = syncData.batches[batchIdx];
        const batchNum = batchIdx + 1;
        
        console.log(`\n[PUSH-SYNC] ===== BATCH ${batchNum}/${syncData.batches.length} =====`);
        logContent += `\n--- BATCH ${batchNum}/${syncData.batches.length} (${batch.length} acties) ---\n`;
        
        // Bouw de actions array met integrity signing
        const actions = [];
        
        try {
            addLog(`📤 Batch ${batchNum}: Integrity berekenen voor ${batch.length} acties...`, false);
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Integrity signing starten...`);
            
            for (const item of batch) {
                const integrity = await calculateIntegrity(item.sequenceNumber, deviceId, item.encodedAction);
                
                actions.push({
                    sequenceNumber: item.sequenceNumber,
                    encodedAction: item.encodedAction,
                    integrity: integrity
                });
                
                console.log(`  [Seq ${item.sequenceNumber}] Action: ${item.action.type}, Integrity: ${integrity.substring(0, 20)}...`);
            }
            
            logContent += `Acties met signing:\n${JSON.stringify(actions, null, 2)}\n\n`;
            
        } catch (integrityError) {
            console.error(`[PUSH-SYNC] Batch ${batchNum}: Integrity error:`, integrityError);
            logContent += `❌ FOUT bij integrity berekening: ${integrityError.message}\n`;
            addLog(`❌ Batch ${batchNum}: Integrity fout - ${integrityError.message}`, true);
            failedBatches++;
            continue;
        }
        
        // Bouw de payload
        const payload = {
            deviceAuthToken: TOKEN,
            actions: actions
        };
        
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Verzenden naar /sync/push-actions...`);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload structure check:`);
        console.log(`  - deviceAuthToken length: ${TOKEN.length}`);
        console.log(`  - actions count: ${actions.length}`);
        console.log(`  - First action structure:`, actions[0]);
        
        // Valideer de payload voordat we versturen
        const payloadString = JSON.stringify(payload);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload size: ${payloadString.length} bytes`);
        console.log(`[PUSH-SYNC] Batch ${batchNum}: Payload preview (first 200 chars):`, payloadString.substring(0, 200));
        
        logContent += `>>> REQUEST PAYLOAD:\n${JSON.stringify(payload, null, 2)}\n\n`;
        logContent += `Payload stats:\n`;
        logContent += `  - Total size: ${payloadString.length} bytes\n`;
        logContent += `  - Actions: ${actions.length}\n\n`;
        
        addLog(`📡 Batch ${batchNum}: Verzenden naar server (${payloadString.length} bytes)...`, false);
        
        // Verstuur naar server
        try {
            console.log(`[PUSH-SYNC] Batch ${batchNum}: Fetching sync/push-actions...`);
            
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
                        addLog(`⚠️ Server vraagt om volledige sync - voer handmatige sync uit`, true);
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
                
                // Probeer te detecteren of het HTML is
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
                    
                    // Log de exacte actie structuur voor debugging
                    if (actions.length > 0) {
                        logContent += `EERSTE ACTIE DETAILS:\n`;
                        logContent += `  sequenceNumber: ${actions[0].sequenceNumber} (type: ${typeof actions[0].sequenceNumber})\n`;
                        logContent += `  encodedAction: ${actions[0].encodedAction.substring(0, 100)}... (type: ${typeof actions[0].encodedAction})\n`;
                        logContent += `  integrity: ${actions[0].integrity.substring(0, 50)}... (type: ${typeof actions[0].integrity})\n`;
                        
                        // Valideer dat encodedAction daadwerkelijk valid JSON is
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
    
    // Samenvatting
    console.log(`\n[PUSH-SYNC] ===== SAMENVATTING =====`);
    console.log(`  Succesvol: ${successfulBatches}/${syncData.batches.length}`);
    console.log(`  Gefaald: ${failedBatches}/${syncData.batches.length}`);
    
    logContent += `\n========================================\n`;
    logContent += `SAMENVATTING:\n`;
    logContent += `  Succesvol: ${successfulBatches}/${syncData.batches.length} batches\n`;
    logContent += `  Gefaald: ${failedBatches}/${syncData.batches.length} batches\n`;
    logContent += `  Totaal acties: ${syncData.totalActions}\n`;
    
    if (successfulBatches === syncData.batches.length) {
        console.log(`[PUSH-SYNC] 🎉 ALLE BATCHES SUCCESVOL!`);
        logContent += `\n🎉 ALLE WIJZIGINGEN SUCCESVOL VERZONDEN!\n`;
        addLog(`🎉 Alle ${syncData.totalActions} wijzigingen succesvol verzonden!`, false);
        
        // Reset change tracking
        if (typeof resetChangeTracking === 'function') {
            resetChangeTracking();
            logContent += `Change tracking gereset.\n`;
            addLog(`♻️ Change tracking gereset - voer nieuwe sync uit om laatste data op te halen`, false);
        }
        
    } else if (successfulBatches > 0) {
        console.log(`[PUSH-SYNC] ⚠️ GEDEELTELIJK SUCCESVOL`);
        logContent += `\n⚠️ GEDEELTELIJK SUCCESVOL - Sommige batches gefaald\n`;
        addLog(`⚠️ ${successfulBatches}/${syncData.batches.length} batches succesvol`, true);
    } else {
        console.log(`[PUSH-SYNC] ❌ ALLE BATCHES GEFAALD`);
        logContent += `\n❌ ALLE BATCHES GEFAALD - Controleer logs\n`;
        addLog(`❌ Sync gefaald - controleer inspector en console`, true);
    }
    
    // Log naar inspector
    if (jsonView.textContent.length > 100000) {
        jsonView.textContent = jsonView.textContent.slice(-50000);
    }
    jsonView.textContent += separator + logContent;
    jsonView.scrollTop = jsonView.scrollHeight;
    
    console.log(`[PUSH-SYNC] ===== EINDE =====\n`);
}