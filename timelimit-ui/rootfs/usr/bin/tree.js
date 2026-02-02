/**
 * tree.js - Interactieve boomstructuur met Apps en Rules
 * Verwerkt de hiërarchische weergave van categorieën, limieten en applicaties.
 */

/**
 * Helper: Formatteert milliseconden naar een leesbare u/m notatie
 * @param {number} ms - Tijd in milliseconden
 */
function formatTime(ms) {
    if (ms === undefined || ms < 0) return null;
    const totalMinutes = Math.floor(ms / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}u ${minutes}m` : `${minutes}m`;
}

/**
 * Helper: Vertaalt een array van dag-indexen naar tekst
 * @param {Array} days - Array met getallen 0 (Ma) t/m 6 (Zo)
 */
function formatDays(days) {
    // Standaardwaarde als alle dagen geselecteerd zijn of de lijst leeg is
    if (!days || days.length === 0 || days.length === 7) return "Dagelijks";
    
    const names = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];
    
    // Controleer of de reeks exact overeenkomt met werkdagen (0 t/m 4)
    const isWorkdays = [0, 1, 2, 3, 4].every(d => days.includes(d)) && days.length === 5;
    if (isWorkdays) return "Werkdagen";
    
    // Controleer of de reeks exact overeenkomt met het weekend (5 en 6)
    const isWeekend = [5, 6].every(d => days.includes(d)) && days.length === 2;
    if (isWeekend) return "Weekend";

    // Als het een specifieke selectie is, toon dan de afzonderlijke namen
    return days.map(d => names[d]).join(", ");
}

/**
 * Helper: Zet technische package namen om naar een scanbare naam
 * Voorbeeld: "com.android.chrome" -> "Chrome"
 */
function getReadableAppName(packageName) {
    if (!packageName) return "Onbekende App";
    
    // Split op de punt en pak het laatste segment
    let parts = packageName.split('.');
    let name = parts[parts.length - 1];

    // Zorg dat de naam altijd netjes met een hoofdletter begint
    return name.charAt(0).toUpperCase() + name.slice(1);
}

/**
 * Transformeert de platte API data naar een geneste boomstructuur
 * @param {Object} data - De volledige JSON response van de API
 */
function buildCategoryTree(data) {
    const categories = data.categoryBase || [];
    const appsMap = data.categoryApp || [];
    const rulesMap = data.rules || [];
    
    const categoryMap = {};
    const tree = [];

    // STAP 1: Maak een object-map voor snelle opzoeking en koppel Apps/Rules direct aan de categorie
    categories.forEach(cat => {
        // Zoek de bijbehorende apps en regels voor deze specifieke categoryId
        const catApps = appsMap.find(a => a.categoryId === cat.categoryId)?.apps || [];
        const catRules = rulesMap.find(r => r.categoryId === cat.categoryId)?.rules || [];
        
        // Sla de categorie op in de map met extra arrays voor kinderen, apps en regels
        categoryMap[cat.categoryId] = { 
            ...cat, 
            linkedApps: catApps,
            linkedRules: catRules,
            children: [] 
        };
    });

    // STAP 2: Bouw de hiërarchie door kinderen aan hun ouders te koppelen
    categories.forEach(cat => {
        const current = categoryMap[cat.categoryId];
        // Als er een parentCategoryId is, voeg de huidige categorie toe aan de 'children' van de parent
        if (cat.parentCategoryId && categoryMap[cat.parentCategoryId]) {
            categoryMap[cat.parentCategoryId].children.push(current);
        } else {
            // Geen parent? Dan is dit een hoofdcategorie (root node)
            tree.push(current);
        }
    });

    return tree;
}

/**
 * Genereert de HTML voor de gebruiksregels (tijdslimieten/blokkades)
 */
function renderRulesHTML(rules) {
    if (!rules || rules.length === 0) return '';
    
    return rules.map(r => {
        let title = "Beperking";
        let detail = "";

        // Logica om te bepalen wat de belangrijkste info van de regel is
        if (r.maxTime !== undefined && r.maxTime > 0) {
            title = `Limiet: ${formatTime(r.maxTime)}`;
        } else if (r.start !== undefined && r.end !== undefined) {
            title = `Blokkade: ${r.start} - ${r.end}`;
        } else {
            title = "Blokkade actief";
        }

        // Formatteer de secundaire regel (bijv: "Werkdagen (Prio 1)")
        const dayLabel = formatDays(r.days);
        const prioLabel = r.prio ? `(Prio ${r.prio})` : "";
        detail = `${dayLabel} ${prioLabel}`.trim();

        return `
            <div class="tree-leaf rule-leaf">
                <span class="leaf-icon">⚖️</span>
                <div class="rule-content">
                    <div class="rule-title">${title}</div>
                    <div class="rule-subtitle">${detail}</div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Genereert de HTML voor de lijst met applicaties binnen een categorie
 */
function renderAppsHTML(apps) {
    if (!apps || apps.length === 0) return '';

    return apps.map(app => {
        const readableName = getReadableAppName(app);
        
        return `
            <div class="tree-leaf app-leaf" title="${app}">
                <span class="leaf-icon">📱</span>
                <div class="app-info">
                    <span class="app-name">${readableName}</span>
                    <span class="app-package">(${app})</span>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Regelt het in- en uitklappen van de boom-nodes in de UI
 * @param {HTMLElement} element - Het aangeklikte .tree-item
 */
function toggleNode(element) {
    // De 'content' is de div direct na de header die we hebben aangeklikt
    const content = element.nextElementSibling;
    const icon = element.querySelector('.tree-icon');
    
    if (content.style.display === "none") {
        content.style.display = "block";
        icon.innerText = "▼";
        element.classList.add('is-open'); // Trigger voor CSS animaties/kleuren
    } else {
        content.style.display = "none";
        icon.innerText = "▶";
        element.classList.remove('is-open');
    }
}

/**
 * Update de volledige categorie-weergave op het dashboard
 * @param {Object} data - De API status data
 */
function updateCategoryDisplay(data) {
    const container = document.getElementById('category-tree-container');
    if (!container) return;
    
    // Bouw eerst de logische boom en render deze daarna naar HTML
    const tree = buildCategoryTree(data);
    container.innerHTML = renderTreeHTML(tree);
}