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

    // Zoek categorie (gebruik ==)
    const category = currentDataDraft.rules.find(c => c.categoryId == catId);
    const rule = category ? category.rules.find(r => r.id == ruleId) : null;

    if (!rule) {
        console.error("Data-fout: Regel niet gevonden in de huidige dataset.");
        return;
    }

    // Velden vullen in de HTML
    document.getElementById('edit-cat-id').value = catId;
    document.getElementById('edit-rule-id').value = ruleId;
    document.getElementById('field-dayMask').value = rule.dayMask || 0;
    document.getElementById('field-maxTime').value = rule.maxTime || 0;
    document.getElementById('field-start').value = rule.start || 0;
    document.getElementById('field-end').value = rule.end || 0;
    document.getElementById('field-perDay').checked = !!rule.perDay;

    // Toon de modal
    const modal = document.getElementById('rule-modal');
    if (modal) {
        modal.classList.add('is-visible');
    }
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