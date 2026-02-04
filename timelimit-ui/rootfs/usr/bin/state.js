// Dit is ons "werkgeheugen"
let currentDataDraft = null;

function initializeDraft(data) {
    if (!data) return;
    currentDataDraft = JSON.parse(JSON.stringify(data));
    console.log("Concept-modus actief. Data geladen.");
}

function updateRuleInDraft(categoryId, ruleId, newValues) {
    if (!currentDataDraft || !currentDataDraft.rules) return;

    // Gebruik == in plaats van === voor type-flexibiliteit (string vs number)
    const category = currentDataDraft.rules.find(r => r.categoryId == categoryId);
    if (category) {
        const rule = category.rules.find(r => r.id == ruleId);
        if (rule) {
            Object.assign(rule, newValues);
            console.log(`Regel ${ruleId} bijgewerkt in concept.`);
        }
    }
}

function openRuleModal(catId, ruleId) {
    console.log("Trigger: Modal openen voor Cat:", catId, "Rule:", ruleId);
    
    if (!currentDataDraft || !currentDataDraft.rules) {
        console.error("Geen data beschikbaar. Voer eerst een sync uit.");
        return;
    }

    // Zoek categorie (gebruik == voor flexibele type-matching)
    const category = currentDataDraft.rules.find(c => c.categoryId == catId);
    const rule = category ? category.rules.find(r => r.id == ruleId) : null;

    if (!rule) {
        console.error("Data-fout: Regel niet gevonden in de huidige dataset.");
        return;
    }

    // 1. Basis velden vullen
    document.getElementById('edit-cat-id').value = catId;
    document.getElementById('edit-rule-id').value = ruleId;
    document.getElementById('field-maxTime').value = rule.maxTime || 0;
    document.getElementById('field-start').value = rule.start || 0;
    document.getElementById('field-end').value = rule.end || 0;
    document.getElementById('field-perDay').checked = !!rule.perDay;

    // 2. Dag-masker verwerken: vul de verborgen input én zet de knoppen goed
    const mask = rule.dayMask || 0;
    document.getElementById('field-dayMask').value = mask;
    setButtonsFromMask(mask); 

    // 3. Toon de modal
    const modal = document.getElementById('rule-modal');
    if (modal) {
        modal.classList.add('is-visible');
    }
}

/**
 * Zet de 'active' class op de juiste dag-knoppen op basis van de bitmask
 */
function setButtonsFromMask(mask) {
    const buttons = document.querySelectorAll('.day-btn');
    buttons.forEach(btn => {
        const bit = parseInt(btn.getAttribute('data-bit'));
        // Bitwise check: als de bit in de mask zit, maak knop actief
        if ((mask & bit) === bit) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

/**
 * Berekent de nieuwe mask op basis van de ingedrukte knoppen
 * Roep deze aan telkens als er op een dag-knop geklikt wordt
 */
function updateMaskFromButtons() {
    let mask = 0;
    document.querySelectorAll('.day-btn.active').forEach(btn => {
        mask += parseInt(btn.getAttribute('data-bit'));
    });
    document.getElementById('field-dayMask').value = mask;
    console.log("Nieuwe bitmask berekend:", mask);
}

function closeModal() {
    document.getElementById('rule-modal').classList.remove('is-visible');
}

function saveModalChanges() {
    const catId = document.getElementById('edit-cat-id').value;
    const ruleId = document.getElementById('edit-rule-id').value;

    const updatedValues = {
        dayMask: parseInt(document.getElementById('field-dayMask').value),
        maxTime: parseInt(document.getElementById('field-maxTime').value),
        start: parseInt(document.getElementById('field-start').value),
        end: parseInt(document.getElementById('field-end').value),
        perDay: document.getElementById('field-perDay').checked
    };

    updateRuleInDraft(catId, ruleId, updatedValues);
    closeModal();
    
    // UI verversen
    if (typeof updateCategoryDisplay === "function") {
        updateCategoryDisplay(currentDataDraft);
    }
}

// Zorg dat de functie globaal bereikbaar is voor de onclick in de HTML
window.openRuleModal = openRuleModal;

// Voeg dit ergens bovenin state.js toe of in een init sectie
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('day-btn')) {
        e.target.classList.toggle('active');
        updateMaskFromButtons();
    }
});

function updateMaskFromButtons() {
    let mask = 0;
    document.querySelectorAll('.day-btn.active').forEach(btn => {
        mask += parseInt(btn.getAttribute('data-bit'));
    });
    document.getElementById('field-dayMask').value = mask;
}

function setButtonsFromMask(mask) {
    document.querySelectorAll('.day-btn').forEach(btn => {
        const bit = parseInt(btn.getAttribute('data-bit'));
        // Controleer of de bit in de mask zit (bitwise AND)
        if ((mask & bit) === bit) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}