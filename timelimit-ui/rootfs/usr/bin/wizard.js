/**
 * wizard.js - Afhandeling van de "Nieuwe Familie" workflow
 * Bevat de stappen voor e-mail, verificatie en wachtwoord hashing.
 */

let wizardSession = {};

async function runStep1() {
    const mailInput = document.getElementById('mail').value;
    if (!mailInput) return addLog("Voer een e-mailadres in.", true);

    addLog("Stap 1: Code aanvragen voor " + mailInput);
    try {
        const res = await fetch('wizard-step1', { 
            method: 'POST', 
            body: JSON.stringify({ mail: mailInput, locale: 'nl' }) 
        });
        const data = await res.json();
        
        if (data.mailLoginToken) {
            wizardSession.mailLoginToken = data.mailLoginToken;
            showStep(2);
            addLog("Code verzonden naar e-mail.");
        } else {
            addLog("Fout bij aanvragen: " + JSON.stringify(data), true);
        }
    } catch (e) {
        addLog("Netwerkfout Stap 1: " + e.message, true);
    }
}

async function runStep2() {
    const codeInput = document.getElementById('code').value;
    addLog("Stap 2: Code valideren...");

    try {
        const res = await fetch('wizard-step2', { 
            method: 'POST', 
            body: JSON.stringify({ 
                receivedCode: codeInput, 
                mailLoginToken: wizardSession.mailLoginToken 
            }) 
        });
        const data = await res.json();
        
        document.getElementById('json-view').textContent = "--- STAP 2 RESPONSE ---\n" + JSON.stringify(data, null, 2);

        if (data.mailAuthToken) {
            wizardSession.mailAuthToken = data.mailAuthToken;
            showStep(3);
            addLog("Code geaccepteerd.");
        } else {
            addLog("Ongeldige code.", true);
        }
    } catch (e) {
        addLog("Netwerkfout Stap 2: " + e.message, true);
    }
}

async function runStep3() {
    const password = document.getElementById('pass').value;
    addLog("Stap 3: Hashes genereren en familie finaliseren...");

    try {
        const hRes = await fetch('generate-hashes', { 
            method: 'POST', 
            body: JSON.stringify({ password: password }) 
        });
        const hashes = await hRes.json();
        
        let cleanHash = hashes.hash.replace('$2b$', '$2a$');
        const validDummySalt = "$2a$12$1234567890123456789012";
        const finalSalt = (hashes.salt && hashes.salt.includes('$2a$')) ? hashes.salt : validDummySalt;

        const payload = {
            mailAuthToken: wizardSession.mailAuthToken,
            parentPassword: {
                hash: cleanHash,
                secondHash: cleanHash,
                secondSalt: finalSalt
            },
            parentDevice: { model: "WebDashboard-v60-Modular" },
            deviceName: "DashboardControl",
            timeZone: "Europe/Amsterdam",
            parentName: "Beheerder"
        };

        const inspector = document.getElementById('json-view');
        inspector.textContent = ">>> VERZONDEN PAYLOAD (WIZARD):\n" + JSON.stringify(payload, null, 2);

        const res = await fetch('wizard-step3', { 
            method: 'POST', 
            body: JSON.stringify(payload) 
        });
        
        const text = await res.text();
        inspector.textContent += "\n\n<<< SERVER ANTWOORD:\n" + text;

        if (res.ok) { 
            const finalData = JSON.parse(text);
            
            // --- NIEUWE TOKEN LOGICA ---
            if (finalData.deviceAuthToken) {
                // 1. Update de globale variabele (voor de actieve runtime)
                TOKEN = finalData.deviceAuthToken; 
                
                // 2. Sla op in de browser (voor na een refresh)
                localStorage.setItem('timelimit_token', TOKEN); 
                
                // 3. Update de UI (het blauwe kader bovenin)
                updateTokenDisplay(); 
                
                addLog("🎉 SUCCES! Gezin aangemaakt en automatisch ingelogd.");
            } else {
                addLog("🎉 Gezin aangemaakt, maar geen token ontvangen?", true);
            }

            showStep(0); // Sluit de wizard
            runSync();   // Start direct de eerste sync met het nieuwe gezin
            
        } else {
            addLog("Fout bij aanmaken. Zie inspector.", true);
        }
    } catch (e) {
        addLog("Systeemfout Stap 3: " + e.message, true);
    }
}
