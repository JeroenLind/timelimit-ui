/**
 * ui.js - Gedeelde interface functies
 */

function addLog(m, isError = false) { 
    const log = document.getElementById('log-area');
    if (!log) return;

    // Voorkom een oneindig lange lijst: verwijder oudste logs boven de 50 regels
    if (log.children.length > 50) {
        log.removeChild(log.firstChild);
    }

    const div = document.createElement('div');
    div.style.color = isError ? '#ff4444' : '#00ff00';
    div.innerHTML = `[${new Date().toLocaleTimeString()}] ${m}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function showStep(s) {
    const wizardUi = document.getElementById('wizard-ui');
    if (!wizardUi) return;

    wizardUi.style.display = s > 0 ? 'block' : 'none';
    const steps = document.querySelectorAll('.wizard-step');
    steps.forEach((el, idx) => el.style.display = (idx + 1 === s) ? 'block' : 'none');
}

function renderUsers(data) {
    const list = document.getElementById('user-list');
    if (!list) return;

    if (data && data.users && data.users.data && data.users.data.length > 0) {
        let html = "<ul style='list-style: none; padding: 0;'>";
        data.users.data.forEach(u => {
            const icon = u.type === 'parent' ? '🛡️' : '👤';
            html += `<li style='background: #151921; margin-bottom: 5px; padding: 10px; border-radius: 4px; border-left: 3px solid #03a9f4;'>
                        ${icon} <strong>${u.name}</strong> <span style='color: #888; font-size: 0.8em;'>(${u.type})</span>
                     </li>`;
        });
        html += "</ul>";
        list.innerHTML = html;
    } else {
        list.innerHTML = "<p style='color: #888;'>Geen gebruikers gevonden in deze familie.</p>";
    }
}

/**
 * Toont een samenvatting van alle gewijzigde regels
 */
function showChangesSummary() {
    const changes = getChangedRules();
    
    console.log("[DEBUG] showChangesSummary() aangeroepen. Aantal wijzigingen:", changes.length);
    
    if (changes.length === 0) {
        alert('❌ Geen wijzigingen aangebracht.');
        console.log("[DEBUG] Geen wijzigingen gevonden!");
        return;
    }

    let html = `<div class="changes-summary">
        <h3>📋 Wijzigingen (${changes.length})</h3>
        <ul>`;

    changes.forEach(change => {
        const catId = change.categoryId;
        const ruleId = change.ruleId;
        const original = change.original;
        const current = change.current;

        // Zoek de categorie-naam (title) op uit de huidige data snapshot
        let catTitle = catId;
        try {
            if (typeof currentDataDraft !== 'undefined' && currentDataDraft && currentDataDraft.categoryBase) {
                const cat = currentDataDraft.categoryBase.find(c => c.categoryId == catId);
                if (cat && cat.title) catTitle = cat.title;
            }
        } catch (e) {
            console.warn('[DEBUG] kon categorie-naam niet ophalen', e);
        }

        // Bepaal wat er gewijzigd is - controleer elk veld
        let details = [];
        
        if (original.maxTime !== current.maxTime) {
            details.push(`Limiet: ${formatDuration(original.maxTime)} → ${formatDuration(current.maxTime)}`);
        }
        if (original.start !== current.start || original.end !== current.end) {
            details.push(`Tijd: ${formatClockTime(original.start)}-${formatClockTime(original.end)} → ${formatClockTime(current.start)}-${formatClockTime(current.end)}`);
        }
        if (original.dayMask !== current.dayMask) {
            details.push(`Dagen: ${formatDays(original.dayMask)} → ${formatDays(current.dayMask)}`);
        }
        if (original.perDay !== current.perDay) {
            details.push(`Per dag: ${original.perDay ? 'ja' : 'nee'} → ${current.perDay ? 'ja' : 'nee'}`);
        }

        // Toon ook de ruwe waarden voor volledigheid
        html += `<li>
            <strong>Regel ${ruleId}</strong> (Categorie: ${catTitle})
            <div class="change-detail">${details.length > 0 ? details.join(' | ') : 'Geen wijzigingen gedetecteerd'}</div>
            <div class="change-detail" style="color: #888; font-size: 10px; margin-top: 4px;">
                Origineel: maxTime=${original.maxTime}ms, start=${original.start}min, end=${original.end}min, dayMask=${original.dayMask}, perDay=${original.perDay}
                <br>Huidig: maxTime=${current.maxTime}ms, start=${current.start}min, end=${current.end}min, dayMask=${current.dayMask}, perDay=${current.perDay}
            </div>
        </li>`;
    });

    html += `</ul>
        <button class="btn reset-changes-btn" style="width: 100%; margin-top: 10px;" onclick="resetAllChanges(); location.reload();">↶ Wijzigingen ongedaan maken</button>
    </div>`;

    const container = document.getElementById('category-tree-container');
    if (container) {
        // Verwijder eerdere samenvatting als deze al bestaat
        const existing = container.parentElement.querySelector('.changes-summary');
        if (existing) existing.remove();
        
        container.insertAdjacentHTML('beforebegin', html);
        addLog(`✏️ ${changes.length} wijziging${changes.length !== 1 ? 'en' : ''} gedetecteerd!`);
    } else {
        console.error("[ERROR] category-tree-container niet gevonden!");
    }
}

/**
 * Toont het aantal wijzigingen in de header
 */
function updateChangeIndicator() {
    const changes = getChangedRules();
    const indicator = document.getElementById('change-indicator');
    
    if (indicator) {
        if (changes.length > 0) {
            indicator.textContent = `📝 ${changes.length} wijziging${changes.length !== 1 ? 'en' : ''}`;
            indicator.style.display = 'inline-block';
        } else {
            indicator.style.display = 'none';
        }
    }
}

/**
 * Toont de modal voor wachtwoord reset/bijwerken
 */
function showPasswordResetModal() {
    const modal = document.getElementById('password-reset-modal');
    if (modal) {
        modal.style.display = 'flex';
        const input = document.getElementById('password-reset-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        const status = document.getElementById('password-reset-status');
        if (status) status.textContent = '';
    }
}

/**
 * Verbergt de modal voor wachtwoord reset
 */
function hidePasswordResetModal() {
    const modal = document.getElementById('password-reset-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Verwerkt het wachtwoord: genereert hashes en slaat ze op
 */
async function submitPasswordReset() {
    const password = document.getElementById('password-reset-input').value;
    const statusDiv = document.getElementById('password-reset-status');
    
    if (!password) {
        if (statusDiv) statusDiv.textContent = "❌ Voer een wachtwoord in.";
        return;
    }
    
    if (statusDiv) statusDiv.textContent = "⏳ Wachtwoord verwerken...";
    
    try {
        // Check of we een secondPasswordSalt hebben uit de sync data
        let secondSalt = null;
        let secondHash = null;
        
        if (currentDataDraft && currentDataDraft.users && currentDataDraft.users.data) {
            const parentUser = currentDataDraft.users.data.find(u => u.type === 'parent');
            if (parentUser && parentUser.secondPasswordSalt) {
                secondSalt = parentUser.secondPasswordSalt;
                console.log("[PASSWORD-RESET] secondPasswordSalt gevonden in sync data:", secondSalt);
            }
        }
        
        if (secondSalt) {
            // SCENARIO 1: We hebben de salt van de server, regenereer de exacte hash
            if (statusDiv) statusDiv.textContent = "⏳ Hash regenereren met server salt...";
            
            const regenRes = await fetch('regenerate-hash', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    password: password,
                    secondSalt: secondSalt
                })
            });
            
            if (!regenRes.ok) {
                throw new Error("Hash regeneratie gefaald");
            }
            
            const regenData = await regenRes.json();
            secondHash = regenData.secondHash;
            
            console.log("[PASSWORD-RESET] secondHash geregenereerd (first 30 chars):", secondHash.substring(0, 30) + "...");
            
        } else {
            // SCENARIO 2: Geen salt beschikbaar, genereer nieuwe hashes (alleen bij create)
            if (statusDiv) statusDiv.textContent = "⏳ Nieuwe hashes genereren...";
            
            const hRes = await fetch('generate-hashes', {
                method: 'POST',
                body: JSON.stringify({ password: password })
            });
            
            if (!hRes.ok) {
                throw new Error("Fout bij hash generatie");
            }
            
            const hashes = await hRes.json();
            secondHash = hashes.secondHash.replace('$2b$', '$2a$');
            secondSalt = hashes.secondSalt || "$2a$12$1234567890123456789012";
            
            console.log("[PASSWORD-RESET] Nieuwe hashes gegenereerd");
        }
        
        // Converteer salt naar base64 voor HMAC (legacy - secundaire verificatie)
        const base64Salt = bcryptSaltToBase64(secondSalt);
        
        // Sla op in state.js - GEBRUIK DE BCRYPT HASH ALS KEY!
        if (typeof storeparentPasswordHashForSync === 'function') {
            storeparentPasswordHashForSync({
                hash: secondHash, // Gebruik secondHash als primary hash
                secondHash: secondHash,
                secondSalt: base64Salt || secondSalt
            });
            
            if (statusDiv) {
                statusDiv.innerHTML = "✅ Hashes succesvol bijgewerkt!<br><span style='font-size:11px;'>secondHash: " + secondHash.substring(0, 30) + "...</span>";
                statusDiv.style.color = '#4ade80';
            }
            
            addLog("✅ Wachtwoord hashes bijgewerkt met server secondHash!");
            
            // Sluit modal na 2 seconden
            setTimeout(() => {
                hidePasswordResetModal();
            }, 2000);
        } else {
            throw new Error("State functie niet beschikbaar");
        }
    } catch (e) {
        if (statusDiv) {
            statusDiv.textContent = "❌ Fout: " + e.message;
            statusDiv.style.color = '#ff4444';
        }
        addLog("Fout bij wachtwoord bijwerken: " + e.message, true);
    }
}