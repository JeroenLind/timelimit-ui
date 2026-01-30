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

    // UI Feedback voor de start van de sync
    addLog("Syncing data...");
    secondsCounter = 0; // Reset de teller bij elke sync (handmatig of automatisch)

    try {
        const res = await fetch('sync/pull-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(syncPayload)
        });
        
        const data = await res.json();
        
        // Update Inspector
        jsonView.textContent = ">>> VERZONDEN PAYLOAD (SYNC):\n" + JSON.stringify(syncPayload, null, 2);
        jsonView.textContent += "\n\n<<< SERVER ANTWOORD:\n" + JSON.stringify(data, null, 2);

        if (res.ok) {
            addLog("Sync voltooid.");
            badge.innerText = "Online";
            badge.className = "status-badge status-online";
            renderUsers(data);
        } else {
            addLog("Sync geweigerd (400/Auth).", true);
            badge.innerText = "Auth Error";
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