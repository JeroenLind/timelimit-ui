// Dit is ons "werkgeheugen"
let currentDataDraft = null;

/**
 * Initialiseert het concept
 */
function initializeDraft(data) {
    if (!data) return;
    currentDataDraft = JSON.parse(JSON.stringify(data));
    console.log("Concept-modus actief. Data geladen.");
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
            Object.assign(rule, newValues);
            console.log(`Regel ${ruleId} bijgewerkt in concept.`);
        }
    }
}

/**
 * Opent de modal en vertaalt ms naar uren/minuten voor de UI
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

    // 2. TIJD CONVERSIE: ms naar uren en minuten
    const totalMs = rule.maxTime || 0;
    const totalMinutes = Math.floor(totalMs / 60000); // 60.000 ms = 1 minuut
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;

    document.getElementById('input-hours').value = hours;
    document.getElementById('input-minutes').value = mins;
    document.getElementById('field-maxTime').value = totalMs; // hidden field

    // 3. Blokkade tijden (start/end blijven voor nu even ms in hidden fields)
    document.getElementById('field-start').value = rule.start || 0;
    document.getElementById('field-end').value = rule.end || 0;
    document.getElementById('field-perDay').checked = !!rule.perDay;

    // 4. Dag-masker
    const mask = rule.dayMask || 0;
    document.getElementById('field-dayMask').value = mask;
    setButtonsFromMask(mask); 

    const modal = document.getElementById('rule-modal');
    if (modal) modal.classList.add('is-visible');
}

/**
 * Slaat de wijzigingen op en vertaalt uren/minuten terug naar ms
 */
function saveModalChanges() {
    const catId = document.getElementById('edit-cat-id').value;
    const ruleId = document.getElementById('edit-rule-id').value;

    // Bereken MS: ((uren * 60) + minuten) * 60.000
    const hours = parseInt(document.getElementById('input-hours').value) || 0;
    const mins = parseInt(document.getElementById('input-minutes').value) || 0;
    const totalMs = ((hours * 60) + mins) * 60000;

    const updatedValues = {
        dayMask: parseInt(document.getElementById('field-dayMask').value),
        maxTime: totalMs,
        start: parseInt(document.getElementById('field-start').value),
        end: parseInt(document.getElementById('field-end').value),
        perDay: document.getElementById('field-perDay').checked
    };

    updateRuleInDraft(catId, ruleId, updatedValues);
    closeModal();
    
    if (typeof updateCategoryDisplay === "function") {
        updateCategoryDisplay(currentDataDraft);
    }
}

/**
 * Helptools voor de dag-knoppen
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

// Event Listeners
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('day-btn')) {
        e.target.classList.toggle('active');
        updateMaskFromButtons();
    }
});