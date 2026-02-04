/**
 * wizard.js - Afhandeling van de "Nieuwe Familie" workflow
 * Bevat de stappen voor e-mail, verificatie en wachtwoord hashing.
 */

let wizardSession = {};

function startCreateFlow() {
    console.log("Start: Flow voor NIEUWE familie.");
    const title = document.getElementById('step-1-title');
    const desc = document.getElementById('step-3-desc');
    if(title) title.innerText = "Stap 1: E-mail (Nieuwe Familie)";
    if(desc) desc.innerText = "Kies een wachtwoord voor je nieuwe account.";
    
    document.getElementById('btn-run-create').style.display = 'block';
    document.getElementById('btn-run-login').style.display = 'none';
    showStep(1);
}

function startLoginFlow() {
    console.log("Start: Inloggen op BESTAANDE familie.");
    const title = document.getElementById('step-1-title');
    const desc = document.getElementById('step-3-desc');
    if(title) title.innerText = "Stap 1: E-mail (Bestaande Familie)";
    if(desc) desc.innerText = "Voer het wachtwoord in van je bestaande account.";
    
    document.getElementById('btn-run-create').style.display = 'none';
    document.getElementById('btn-run-login').style.display = 'block';
    showStep(1);
}

function showStep(n) {
    // Verberg alle stappen
    document.querySelectorAll('.wizard-step').forEach(s => s.style.display = 'none');
    // Toon de wizard container zelf
    const container = document.getElementById('wizard-ui');
    if (n > 0) {
        container.style.display = 'block';
        document.getElementById('step-' + n).style.display = 'block';
    } else {
        container.style.display = 'none';
    }
}

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

/**
 * Specifieke functie voor het inloggen op een bestaande familie (Sign-In).
 * Wordt aangeroepen in Stap 3 als de gebruiker op "Inloggen" klikt.
 */
async function runSignInStep3() {
    // Opmerking: password wordt hier niet gebruikt voor de API call 
    // omdat het schema dit niet toestaat. 
    addLog("Stap 3: Inloggen bij bestaande familie...");

    try {
        // We sturen ALLEEN wat het schema toestaat
        const payload = {
            mailAuthToken: wizardSession.mailAuthToken,
            parentDevice: { 
                model: "WebDashboard-v60-Modular" 
                // Zorg dat NewDeviceInfo definitie overeenkomt (meestal alleen model)
            },
            deviceName: "DashboardControl"
            // Optioneel: clientLevel: 8 (als nummer, niet als string)
        };

        const inspector = document.getElementById('json-view');
        inspector.textContent = ">>> VERZONDEN PAYLOAD (CLEAN SIGN-IN):\n" + JSON.stringify(payload, null, 2);

        const res = await fetch('wizard-login', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload) 
        });
        
        const text = await res.text();
        inspector.textContent += "\n\n<<< SERVER ANTWOORD:\n" + text;

        if (res.ok) { 
            const data = JSON.parse(text);
            TOKEN = data.deviceAuthToken;
            localStorage.setItem('timelimit_token', TOKEN);
            updateTokenDisplay();
            addLog("🎉 Succesvol ingelogd!");
            showStep(0);
            runSync();
        } else {
            addLog("Fout bij inloggen. Controleer inspector.", true);
        }
    } catch (e) {
        addLog("Systeemfout: " + e.message, true);
    }
}