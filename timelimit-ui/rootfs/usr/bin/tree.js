/**
 * tree.js - Interactieve boomstructuur met Apps en Rules
 * Verwerkt de hiërarchische weergave van categorieën, limieten en applicaties.
 */

/**
 * Helper: Zet milliseconden om naar een duur (bijv. 3u 30m)
 */
function formatDuration(ms) {
    if (ms === undefined || ms === null || ms < 0) return null;
    const totalMinutes = Math.floor(ms / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    
    if (hours === 0) return `${minutes}m`;
    return `${hours}u ${minutes > 0 ? minutes + 'm' : ''}`;
}

/**
 * Helper: Zet minuten vanaf middernacht om naar een kloktijd (bijv. 510 -> 08:30)
 */
function formatClockTime(minutesSinceMidnight) {
    if (minutesSinceMidnight === undefined || minutesSinceMidnight === null) return "00:00";
    
    const hours = Math.floor(minutesSinceMidnight / 60);
    const minutes = minutesSinceMidnight % 60;
    
    // Zorg voor een voorloop-nul (bijv. 08:05 in plaats van 8:5)
    const h = String(hours).padStart(2, '0');
    const m = String(minutes).padStart(2, '0');
    
    return `${h}:${m}`;
}

/**
 * Helper: Vertaalt een bitmasker (bijv. 127) naar leesbare dagen
 * @param {number} mask - Het dayMask getal uit de API
 */
function formatDays(mask) {
    if (mask === 127 || mask === 0) return "Dagelijks";
    if (mask === 31) return "Werkdagen"; // 1+2+4+8+16
    if (mask === 96) return "Weekend";   // 32+64

    const names = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];
    let selectedDays = [];

    // Loop door de 7 dagen en check of de bit "aan" staat
    for (let i = 0; i < 7; i++) {
        // Gebruik de bitwise AND operator om te kijken of de dag in het masker zit
        if (mask & (1 << i)) {
            selectedDays.push(names[i]);
        }
    }

    return selectedDays.join(", ");
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

function getTodayUsage(categoryId, usedTimes) {
    const todayEpoch = Math.floor(Date.now() / 86400000);
    const categoryUsage = usedTimes.find(u => u.categoryId === categoryId);
    
    if (!categoryUsage) return 0;

    // Zoek naar het record van vandaag dat de hele dag beslaat (0-1439)
    const todayRecord = categoryUsage.times.find(t => 
        t.day === todayEpoch && t.start === 0 && t.end === 1439
    );

    return todayRecord ? todayRecord.time : 0;
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
        
        // Gebruik formatDuration voor maxTime (ms)
        if (r.maxTime !== undefined && r.maxTime > 0) {
            title = `Limiet: ${formatDuration(r.maxTime)}`;
        } 
        // Gebruik formatClockTime voor start/end (minuten)
        else if (r.start !== undefined && r.end !== undefined) {
            const startTime = formatClockTime(r.start);
            const endTime = formatClockTime(r.end);
            title = `Blokkade: ${startTime} - ${endTime}`;
        }

        const dayLabel = formatDays(r.dayMask);
        const prioLabel = r.prio ? `(Prio ${r.prio})` : "";

        return `
            <div class="tree-leaf rule-leaf">
                <span class="leaf-icon">⚖️</span>
                <div class="rule-content">
                    <div class="rule-title">${title}</div>
                    <div class="rule-subtitle">${dayLabel} ${prioLabel}</div>
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
 * Genereert de volledige HTML-structuur voor de boom
 * @param {Array} nodes - De lijst met categorie-objecten
 * @param {number} level - Inspringniveau
 * @param {Object} fullData - De volledige API response (voor verbruiksdata)
 */
function renderTreeHTML(nodes, level = 0, fullData = {}) {
    let html = '';
    const usedTimes = fullData.usedTimes || [];
    
    nodes.forEach(node => {
        const hasChildren = node.children.length > 0 || 
                           node.linkedApps.length > 0 || 
                           node.linkedRules.length > 0;
        
        const indent = level * 20;

        // --- NIEUW: Zoek verbruik op voor deze specifieke categorie ---
        const usageMs = getTodayUsage(node.categoryId, usedTimes);
        const usageText = usageMs > 0 ? ` <small class="usage-label">(${formatDuration(usageMs)})</small>` : '';

        html += `
            <div class="tree-node">
                <div class="tree-item" style="margin-left: ${indent}px" onclick="toggleNode(this)">
                    <span class="tree-icon">${hasChildren ? '▶' : '•'}</span>
                    <span class="tree-title">${node.title}${usageText}</span>
                    <span class="tree-id">${node.categoryId}</span>
                </div>
                <div class="tree-content" style="display: none;">
                    ${renderTreeHTML(node.children, level + 1, fullData)}
                    ${renderRulesHTML(node.linkedRules)}
                    ${renderAppsHTML(node.linkedApps)}
                </div>
            </div>
        `;
    });
    
    return html;
}

/**
 * Update de volledige categorie-weergave op het dashboard
 * @param {Object} data - De API status data
 */
function updateCategoryDisplay(data) {
    const container = document.getElementById('category-tree-container');
    if (!container) return;
    
    const tree = buildCategoryTree(data);
    // Geef 'data' (de hele JSON) mee als derde argument
    container.innerHTML = renderTreeHTML(tree, 0, data);
}