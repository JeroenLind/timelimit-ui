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
    
    if (changes.length === 0) {
        alert('❌ Geen wijzigingen aangebracht.');
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

        // Bepaal wat er gewijzigd is
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
            details.push(`Per dag: ${original.perDay} → ${current.perDay}`);
        }

        html += `<li>
            <strong>Regel ${ruleId}</strong> (Categorie ${catId})
            <div class="change-detail">${details.join(' | ')}</div>
        </li>`;
    });

    html += `</ul>
        <button class="btn reset-changes-btn" onclick="resetAllChanges(); location.reload();">↶ Wijzigingen ongedaan maken</button>
    </div>`;

    const container = document.getElementById('category-tree-container');
    if (container) {
        container.insertAdjacentHTML('beforebegin', html);
        addLog(`✏️ ${changes.length} wijzigingen gedetecteerd!`);
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