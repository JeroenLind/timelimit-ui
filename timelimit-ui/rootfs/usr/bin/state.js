// Dit is ons "werkgeheugen"
let currentDataDraft = null;

// Originele (niet-gewijzigde) data - opgeslagen wanneer we de sync doen
let originalDataSnapshot = null;

// Tracked welke regels zijn gewijzigd
let changedRules = new Map(); // { "categoryId_ruleId": {...originalValues} }

// Parent password hash - nodig voor HMAC-SHA512 signing
let parentPasswordHash = null;

/**
 * Initialiseert het concept EN slaat de originele data op voor change tracking
 */
function initializeDraft(data) {
    if (!data) return;
    currentDataDraft = JSON.parse(JSON.stringify(data));
    originalDataSnapshot = JSON.parse(JSON.stringify(data));
    changedRules.clear();
    
    // Sla parent password hash op voor HMAC-SHA512 signing
    if (data.parentPasswordHash) {
        parentPasswordHash = data.parentPasswordHash;
        console.log("Parent password hash opgeslagen voor sync signing.");
    }
    
    console.log("Concept-modus actief. Data geladen en snapshot opgeslagen voor change tracking.");
}

/**
 * Stelt de parentPasswordHash in (gebruikt bij login om wachtwoord hashes opgeslagen)
 * Deze informatie is essentieel voor het HMAC-SHA512 signing van sync actions.
 * 
 * @param {Object} hashObject - { hash, secondHash, secondSalt }
 */
function storeparentPasswordHashForSync(hashObject) {
    if (hashObject && hashObject.secondSalt) {
        parentPasswordHash = hashObject;
        console.log("✅ [STATE] Parent password hashes opgeslagen voor sync signing.");
        console.log("   - hash:", hashObject.hash ? hashObject.hash.substring(0, 10) + "..." : "N/A");
        console.log("   - secondSalt:", hashObject.secondSalt.substring(0, 10) + "...");
    } else {
        console.warn("[STATE] Ongeldige hash object, niet opgeslagen.");
    }
}

/**
 * Zoekt en update de regel in het werkgeheugen
 */
function updateRuleInDraft(categoryId, ruleId, newValues) {
    if (!currentDataDraft || !currentDataDraft.rules) return;

    const category = currentDataDraft.rules.find(r => r.categoryId == categoryId);
    if (category) {
        const rule = category.rules.find(r => r.id == ruleId);
        if (rule) {
            // Sla de ORIGINELE waarden op als dit de eerste keer is dat deze regel wordt gewijzigd
            // Zorg voor consistente string-keys
            const key = `${String(categoryId)}_${String(ruleId)}`;
            if (!changedRules.has(key)) {
                const originalRule = originalDataSnapshot.rules
                    .find(c => c.categoryId == categoryId)?.rules
                    .find(r => r.id == ruleId);
                if (originalRule) {
                    changedRules.set(key, JSON.parse(JSON.stringify(originalRule)));
                    console.log(`[TRACK] Originele waarden opgeslagen voor key: ${key}`);
                }
            }
            
            Object.assign(rule, newValues);
            console.log(`Regel ${ruleId} bijgewerkt in concept. Status: GEWIJZIGD`);
        }
    }
}

/**
 * Haalt alle gewijzigde regels op
 * @returns {Array} Array met gewijzigde regel informatie
 */
function getChangedRules() {
    const changes = [];
    
    console.log("[DEBUG] changedRules Map size:", changedRules.size);
    console.log("[DEBUG] changedRules keys:", Array.from(changedRules.keys()));
    
    changedRules.forEach((originalRule, key) => {
        const [catIdStr, ruleIdStr] = key.split('_');
        // BELANGRIJK: categoryId is een STRING, GEEN getal!
        const categoryId = catIdStr;
        
        console.log(`[DEBUG] Zoeken naar rule: catId=${categoryId}, ruleId=${ruleIdStr}`);
        
        const category = currentDataDraft.rules?.find(c => c.categoryId == categoryId);
        if (!category) {
            console.warn(`[DEBUG] Categorie ${categoryId} niet gevonden!`);
            console.log(`[DEBUG] Beschikbare categorieën:`, currentDataDraft.rules?.map(c => c.categoryId));
            return;
        }
        
        // Probeer zowel als string als als getal
        let currentRule = category.rules?.find(r => String(r.id) === ruleIdStr || r.id == ruleIdStr);
        
        if (!currentRule) {
            console.warn(`[DEBUG] Regel ${ruleIdStr} niet gevonden in categorie ${categoryId}`);
            console.log(`[DEBUG] Beschikbare rules:`, category.rules?.map(r => r.id));
            return;
        }
        
        console.log(`[DEBUG] Regel gevonden! Origineel vs Huidig opslaan...`);
        changes.push({
            key,
            categoryId: categoryId,
            ruleId: ruleIdStr,
            original: originalRule,
            current: currentRule
        });
    });
    
    console.log(`[DEBUG] getChangedRules geeft ${changes.length} wijzigingen terug`);
    return changes;
}

/**
 * Controleert of een regel gewijzigd is
 */
function isRuleChanged(categoryId, ruleId) {
    const key = `${String(categoryId)}_${String(ruleId)}`;
    return changedRules.has(key);
}

/**
 * Reset alle wijzigingen
 */
function resetAllChanges() {
    if (originalDataSnapshot) {
        currentDataDraft = JSON.parse(JSON.stringify(originalDataSnapshot));
        changedRules.clear();
        console.log("Alle wijzigingen teruggedraaid!");
        if (typeof updateCategoryDisplay === "function") {
            updateCategoryDisplay(currentDataDraft);
        }
    }
}

/**
 * Opent de modal en vertaalt MS en Minuten naar leesbare UI velden
 */
function openRuleModal(catId, ruleId) {
    console.log("Trigger: Modal openen voor Cat:", catId, "Rule:", ruleId);
    
    if (!currentDataDraft || !currentDataDraft.rules) {
        console.error("Geen data beschikbaar.");
        return;
    }

    const category = currentDataDraft.rules.find(c => c.categoryId == catId);
    const rule = category ? category.rules.find(r => r.id == ruleId) : null;

    if (!rule) {
        console.error("Regel niet gevonden.");
        return;
    }

    // 1. Basis ID's opslaan
    document.getElementById('edit-cat-id').value = catId;
    document.getElementById('edit-rule-id').value = ruleId;

    // 2. MAX TIME CONVERSIE: ms naar uren en minuten
    const totalMs = rule.maxTime || 0;
    const totalMinutesLimit = Math.floor(totalMs / 60000); 
    document.getElementById('input-hours').value = Math.floor(totalMinutesLimit / 60);
    document.getElementById('input-minutes').value = totalMinutesLimit % 60;
    document.getElementById('field-maxTime').value = totalMs;

    // 3. START/END CONVERSIE: minuten naar HH:mm string voor tijd-input
    const startMin = rule.start || 0;
    const endMin = rule.end || 0;
    document.getElementById('input-start-time').value = minToTimeString(startMin);
    document.getElementById('input-end-time').value = minToTimeString(endMin);
    
    // Hidden fields voor de ruwe waarden
      document.getElementById('field-perDay').checked = !!rule.perDay;

    // 4. Dag-masker
    const mask = rule.dayMask || 0;
    document.getElementById('field-dayMask').value = mask;
    setButtonsFromMask(mask); 

    const modal = document.getElementById('rule-modal');
    if (modal) modal.classList.add('is-visible');
}

/**
 * Slaat de wijzigingen op en vertaalt UI waarden terug naar MS en Minuten
 */
function saveModalChanges() {
    const catId = document.getElementById('edit-cat-id').value;
    const ruleId = document.getElementById('edit-rule-id').value;
    
    console.log(`[DEBUG] saveModalChanges - catId=${catId} (type: ${typeof catId}), ruleId=${ruleId} (type: ${typeof ruleId})`);

    // Bereken MS voor de limiet: ((uren * 60) + minuten) * 60.000
    const h = parseInt(document.getElementById('input-hours').value) || 0;
    const m = parseInt(document.getElementById('input-minutes').value) || 0;
    const totalMs = ((h * 60) + m) * 60000;

    // Bereken Minuten voor de blokkade tijden
    const startMin = timeStringToMin(document.getElementById('input-start-time').value);
    const endMin = timeStringToMin(document.getElementById('input-end-time').value);

    const updatedValues = {
        dayMask: parseInt(document.getElementById('field-dayMask').value),
        maxTime: totalMs,
        start: startMin,
        end: endMin,
        perDay: document.getElementById('field-perDay').checked
    };

    console.log(`[DEBUG] Aangepaste waarden:`, updatedValues);
    updateRuleInDraft(catId, ruleId, updatedValues);
    closeModal();
    
    if (typeof updateCategoryDisplay === "function") {
        updateCategoryDisplay(currentDataDraft);
    }
}

/**
 * Hulpfuncties voor TIJD (Minuten <-> String HH:mm)
 */
function minToTimeString(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

function timeStringToMin(timeString) {
    if (!timeString) return 0;
    const [hours, mins] = timeString.split(':').map(Number);
    return (hours * 60) + mins;
}

/**
 * Hulpfuncties voor de DAG-KNOPPEN
 */
function setButtonsFromMask(mask) {
    document.querySelectorAll('.day-btn').forEach(btn => {
        const bit = parseInt(btn.getAttribute('data-bit'));
        if ((mask & bit) === bit) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function updateMaskFromButtons() {
    let mask = 0;
    document.querySelectorAll('.day-btn.active').forEach(btn => {
        mask += parseInt(btn.getAttribute('data-bit'));
    });
    document.getElementById('field-dayMask').value = mask;
}

function closeModal() {
    document.getElementById('rule-modal').classList.remove('is-visible');
}

// Global scope expose
window.openRuleModal = openRuleModal;

// Event Listeners voor de dag-knoppen
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('day-btn')) {
        e.target.classList.toggle('active');
        updateMaskFromButtons();
    }
});