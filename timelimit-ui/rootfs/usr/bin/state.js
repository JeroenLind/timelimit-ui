// Dit is ons "werkgeheugen"
let currentDataDraft = null;

/**
 * Initialiseert de bewerk-modus met de binnengekomen data
 */
function initializeDraft(data) {
    // We maken een 'deep clone' zodat de originele data veilig blijft
    currentDataDraft = JSON.parse(JSON.stringify(data));
    console.log("Concept-modus actief. Wijzigingen worden lokaal opgeslagen.");
}

/**
 * Update een specifieke regel in het concept
 */
function updateRuleInDraft(categoryId, ruleId, newValues) {
    const category = currentDataDraft.rules.find(r => r.categoryId === categoryId);
    if (category) {
        const rule = category.rules.find(r => r.id === ruleId);
        if (rule) {
            Object.assign(rule, newValues);
            console.log(`Regel ${ruleId} bijgewerkt in concept.`);
        }
    }
}

function openRuleModal(catId, ruleId) {
    const category = currentDataDraft.rules.find(c => c.categoryId === catId);
    const rule = category.rules.find(r => r.id === ruleId);

    // Vul de velden in de modal
    document.getElementById('edit-cat-id').value = catId;
    document.getElementById('edit-rule-id').value = ruleId;
    document.getElementById('field-dayMask').value = rule.dayMask;
    document.getElementById('field-maxTime').value = rule.maxTime;
    document.getElementById('field-start').value = rule.start;
    document.getElementById('field-end').value = rule.end;
    document.getElementById('field-perDay').checked = rule.perDay;

    document.getElementById('rule-modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('rule-modal').style.display = 'none';
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
    
    // Optioneel: Refresh de UI om de nieuwe waarden in de boom te zien
    updateCategoryDisplay(currentDataDraft);
} 