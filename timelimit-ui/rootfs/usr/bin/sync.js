/**
 * sync.js - Afhandeling van handmatige en automatische sync
 */

let syncTimer = null;
let secondsCounter = 0;
const SYNC_INTERVAL = 30; // seconden

async function runSync() {
    const badge = document.getElementById('status-badge');
    const jsonView = document.getElementById('json-view');

    if (!TOKEN || TOKEN.includes("#") || TOKEN === "") {
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

        // --- STAP 1: Controleer of het antwoord JSON is ---
        const contentType = res.headers.get("content-type");
        let data;
        let interactionText = "";

        if (contentType && contentType.includes("application/json")) {
            data = await res.json();
            interactionText = `<<< SERVER JSON ANTWOORD:\n${JSON.stringify(data, null, 2)}`;
        } else {
            // Geen JSON? Dan lezen we het als tekst (waarschijnlijk een HTML error pagina)
            const textData = await res.text();
            data = { error: "Niet-JSON antwoord ontvangen", status: res.status };
            interactionText = `<<< SERVER HTML/TEXT ANTWOORD (Status ${res.status}):\n${textData.substring(0, 500)}...`;
        }

        // --- STAP 2: Log de interactie ---
        const timestamp = new Date().toLocaleTimeString();
        const separator = `\n\n${"=".repeat(20)} SYNC @ ${timestamp} ${"=".repeat(20)}\n`;
        const fullLog = `>>> VERZONDEN PAYLOAD:\n${JSON.stringify(syncPayload, null, 2)}\n\n${interactionText}`;

        if (jsonView.textContent.length > 100000) {
            jsonView.textContent = jsonView.textContent.slice(-50000);
        }
        jsonView.textContent += separator + fullLog;
        jsonView.scrollTop = jsonView.scrollHeight;

        // --- STAP 3: UI Status afhandeling ---
        if (res.ok) {
            addLog("Sync voltooid.");
            badge.innerText = "Online";
            badge.className = "status-badge status-online";
            if (typeof renderUsers === "function") renderUsers(data);
        } else if (res.status === 401) {
            addLog(`⚠️ Auth Fout (401): Token is ongeldig voor deze server.`, true);
            badge.innerText = "Auth Error (401)";
            badge.className = "status-badge status-offline";
        } else {
            addLog(`❌ Sync geweigerd: Status ${res.status}`, true);
            badge.innerText = `Error ${res.status}`;
            badge.className = "status-badge status-offline";
        }

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