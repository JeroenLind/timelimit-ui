/**
 * tree.js - Interactieve boomstructuur met Apps en Rules
 */
function formatTime(ms) {
    if (ms === undefined || ms < 0) return null;
    const totalMinutes = Math.floor(ms / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}u ${minutes}m` : `${minutes}m`;
}

function formatDays(days) {
    if (!days || days.length === 0 || days.length === 7) return "Dagelijks";
    
    const names = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];
    
    // Check voor werkdagen (0,1,2,3,4)
    const isWorkdays = [0, 1, 2, 3, 4].every(d => days.includes(d)) && days.length === 5;
    if (isWorkdays) return "Werkdagen";
    
    // Check voor weekend (5,6)
    const isWeekend = [5, 6].every(d => days.includes(d)) && days.length === 2;
    if (isWeekend) return "Weekend";

    // Anders: lijstje van dagen
    return days.map(d => names[d]).join(", ");
}

/**
 * Helper: Zet package namen om naar leesbare namen
 * Voorbeeld: "com.android.chrome" -> "Chrome"
 */
function getReadableAppName(packageName) {
    if (!packageName) return "Onbekende App";
    
    // Pak het laatste deel na de punt
    let parts = packageName.split('.');
    let name = parts[parts.length - 1];

    // Maak de eerste letter een hoofdletter
    return name.charAt(0).toUpperCase() + name.slice(1);
}

function buildCategoryTree(data) {
    const categories = data.categoryBase || [];
    const appsMap = data.categoryApp || [];
    const rulesMap = data.rules || [];
    
    const categoryMap = {};
    const tree = [];

    // 1. Map maken en Apps/Rules koppelen
    categories.forEach(cat => {
        const catApps = appsMap.find(a => a.categoryId === cat.categoryId)?.apps || [];
        const catRules = rulesMap.find(r => r.categoryId === cat.categoryId)?.rules || [];
        
        categoryMap[cat.categoryId] = { 
            ...cat, 
            linkedApps: catApps,
            linkedRules: catRules,
            children: [] 
        };
    });

    // 2. Hiërarchie bouwen
    categories.forEach(cat => {
        const current = categoryMap[cat.categoryId];
        if (cat.parentCategoryId && categoryMap[cat.parentCategoryId]) {
            categoryMap[cat.parentCategoryId].children.push(current);
        } else {
            tree.push(current);
        }
    });

    return tree;
}

/**
 * Hoofdfunctie voor het renderen van de regels in de boomstructuur
 */
function renderRulesHTML(rules) {
    if (!rules || rules.length === 0) return '';
    
    return rules.map(r => {
        let title = "Beperking";
        let detail = "";

        // Bepaal de hoofdtekst van de regel
        if (r.maxTime !== undefined && r.maxTime > 0) {
            title = `Limiet: ${formatTime(r.maxTime)}`;
        } else if (r.start !== undefined && r.end !== undefined) {
            title = `Blokkade: ${r.start} - ${r.end}`;
        } else {
            title = "Blokkade actief";
        }

        // Bepaal de secundaire info (Dagen + Prio)
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
 * Renders de lijst met apps binnen een categorie
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

function toggleNode(element) {
    const content = element.nextElementSibling;
    const icon = element.querySelector('.tree-icon');
    
    if (content.style.display === "none") {
        content.style.display = "block";
        icon.innerText = "▼";
        element.classList.add('is-open');
    } else {
        content.style.display = "none";
        icon.innerText = "▶";
        element.classList.remove('is-open');
    }
}

function updateCategoryDisplay(data) {
    const container = document.getElementById('category-tree-container');
    if (!container) return;
    const tree = buildCategoryTree(data);
    container.innerHTML = renderTreeHTML(tree);
}