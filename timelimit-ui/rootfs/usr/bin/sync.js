/**
 * sync.js - Afhandeling van de periodieke data synchronisatie
 */
async function runSync() {
    const badge = document.getElementById('status-badge');
    const jsonView = document.getElementById('json-view');

    if (!TOKEN || TOKEN.includes("#") || TOKEN === "") {
        addLog("Sync overgeslagen: Geen geldig token geconfigureerd.", true);
        if(badge) badge.innerText = "Geen Token";
        return;
    }

    // Payload exact volgens de ontdekte AJV-validator eisen
    const syncPayload = {
        deviceAuthToken: TOKEN,
        status: { 
            apps: {}, 
            categories: {}, 
            devices: "0", 
            users: "0", 
            clientLevel: 8 
        }
    };

    addLog("Syncing...");
    // Toon de verzonden data in de blauwe inspector
    jsonView.textContent = ">>> VERZONDEN PAYLOAD (SYNC):\n" + JSON.stringify(syncPayload, null, 2);

    try {
        const res = await fetch('sync/pull-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(syncPayload)
        });
        
        const data = await res.json();
        
        // Voeg het antwoord toe aan de inspector
        jsonView.textContent += "\n\n<<< SERVER ANTWOORD:\n" + JSON.stringify(data, null, 2);

        if (res.ok) {
            addLog("Sync voltooid.");
            if(badge) {
                badge.innerText = "Online";
                badge.className = "status-badge status-online";
            }
            // Update de gebruikerslijst in het dashboard via ui.js
            renderUsers(data);
        } else {
            addLog("Sync geweigerd door server (400/Unauthorized).", true);
            if(badge) {
                badge.innerText = "Sync Error";
                badge.className = "status-badge status-offline";
            }
        }
    } catch (e) {
        addLog("Netwerkfout tijdens sync: " + e.message, true);
        console.error("Sync error", e);
        if(badge) {
            badge.innerText = "Offline";
            badge.className = "status-badge status-offline";
        }
    }
}