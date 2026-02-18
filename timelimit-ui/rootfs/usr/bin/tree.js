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

function compareCategoryOrder(a, b) {
    const aSort = Number.isFinite(a.sort) ? a.sort : 0;
    const bSort = Number.isFinite(b.sort) ? b.sort : 0;
    if (aSort !== bSort) return aSort - bSort;
    const aTitle = (a.title || "").toLowerCase();
    const bTitle = (b.title || "").toLowerCase();
    if (aTitle < bTitle) return -1;
    if (aTitle > bTitle) return 1;
    return 0;
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

    // Sorteer op de server-volgorde (sort), met titel als stabiele fallback
    Object.values(categoryMap).forEach(cat => {
        if (cat.children && cat.children.length > 0) {
            cat.children.sort(compareCategoryOrder);
        }
    });
    tree.sort(compareCategoryOrder);

    return tree;
}

let appIndexItems = [];

function buildAppIndex(data) {
    const categories = data.categoryBase || [];
    const appsMap = data.categoryApp || [];

    const categoryById = new Map();
    categories.forEach(cat => {
        categoryById.set(cat.categoryId, { title: cat.title || "(onbekend)", sort: cat.sort });
    });

    const appMap = new Map();
    appsMap.forEach(entry => {
        const categoryMeta = categoryById.get(entry.categoryId) || { title: "(onbekend)", sort: 0 };
        const apps = entry.apps || [];

        apps.forEach(packageName => {
            if (!appMap.has(packageName)) {
                appMap.set(packageName, {
                    packageName,
                    readableName: getReadableAppName(packageName),
                    categories: []
                });
            }
            appMap.get(packageName).categories.push({
                title: categoryMeta.title,
                sort: categoryMeta.sort
            });
        });
    });

    const items = Array.from(appMap.values()).map(item => {
        const uniqueCategories = new Map();
        item.categories.forEach(cat => {
            uniqueCategories.set(cat.title, cat);
        });
        const categoriesSorted = Array.from(uniqueCategories.values()).sort(compareCategoryOrder);
        return {
            packageName: item.packageName,
            readableName: item.readableName,
            categories: categoriesSorted.map(cat => cat.title)
        };
    });

    items.sort((a, b) => {
        const aName = a.readableName.toLowerCase();
        const bName = b.readableName.toLowerCase();
        if (aName < bName) return -1;
        if (aName > bName) return 1;
        return a.packageName.localeCompare(b.packageName);
    });

    return items;
}

function renderAppIndexList(items, query) {
    const list = document.getElementById('app-index-list');
    if (!list) return;

    const normalized = (query || "").trim().toLowerCase();
    const filtered = normalized
        ? items.filter(item => {
            const catText = item.categories.join(' ').toLowerCase();
            return item.readableName.toLowerCase().includes(normalized)
                || item.packageName.toLowerCase().includes(normalized)
                || catText.includes(normalized);
        })
        : items;

    if (filtered.length === 0) {
        list.innerHTML = '<div class="app-index-item">Geen apps gevonden.</div>';
        return;
    }

    list.innerHTML = filtered.map(item => {
        const categoriesText = item.categories.length > 0 ? item.categories.join(', ') : '(geen categorie)';
        return `
            <div class="app-index-item">
                <span class="app-index-name">${item.readableName}</span>
                <span class="app-index-package">${item.packageName}</span>
                <span class="app-index-categories">${categoriesText}</span>
            </div>
        `;
    }).join('');
}

function initAppIndexSearch() {
    const input = document.getElementById('app-index-search');
    if (!input || input.dataset.bound === 'true') return;
    input.dataset.bound = 'true';

    input.addEventListener('input', () => {
        renderAppIndexList(appIndexItems, input.value);
    });
}

function updateAppIndexDisplay(data) {
    if (!data || !data.categoryBase || !data.categoryApp) {
        appIndexItems = [];
        const list = document.getElementById('app-index-list');
        if (list) {
            list.innerHTML = '<div class="app-index-item">Geen app data beschikbaar.</div>';
        }
        return;
    }

    appIndexItems = buildAppIndex(data);

    const list = document.getElementById('app-index-list');
    if (list) {
        initAppIndexSearch();

        const input = document.getElementById('app-index-search');
        const query = input ? input.value : '';
        if (appIndexItems.length === 0) {
            list.innerHTML = '<div class="app-index-item">Geen app data beschikbaar.</div>';
        } else {
            renderAppIndexList(appIndexItems, query);
        }
    }

    const modalSearch = document.getElementById('add-app-search');
    if (modalSearch && !modalSearch.dataset.bound) {
        modalSearch.dataset.bound = 'true';
        modalSearch.addEventListener('input', () => {
            renderAddAppList(appIndexItems || [], modalSearch.value);
        });
    }

    const onlyToggle = document.getElementById('add-app-only-uncategorized');
    if (onlyToggle && !onlyToggle.dataset.bound) {
        onlyToggle.dataset.bound = 'true';
        onlyToggle.addEventListener('change', () => {
            const searchInput = document.getElementById('add-app-search');
            const q = searchInput ? searchInput.value : '';
            renderAddAppList(appIndexItems || [], q);
        });
    }
}


/**
 * Genereert de HTML voor de gebruiksregels
 * Aangepast: categoryId wordt nu meegegeven als argument
 */
function renderRulesHTML(rules, categoryId) {
    if (!rules || rules.length === 0) {
        return '<div class="tree-leaf rule-leaf rule-empty">Geen regels. Klik op + om toe te voegen.</div>';
    }

    const deletedList = typeof getDeletedRules === 'function' ? getDeletedRules() : [];
    const deletedSet = new Set(
        deletedList
            .filter(item => item && item.categoryId && item.ruleId)
            .map(item => `${String(item.categoryId)}::${String(item.ruleId)}`)
    );
    
    return rules.map(r => {
        const isDisabled = !!r._disabled;
        const isDeleted = !isDisabled && (!!r._deletedPending || deletedSet.has(`${String(categoryId)}::${String(r.id)}`));
        let title = "Beperking";
        if (r.maxTime > 0) {
            title = `Limiet: ${formatDuration(r.maxTime)}`;
        } else {
            title = `Blokkade: ${formatClockTime(r.start)} - ${formatClockTime(r.end)}`;
        }

        // Check of deze regel gewijzigd is
        const isChanged = isRuleChanged(categoryId, r.id);
        const isNew = !!r._isNew;
        const changedClass = isChanged || isNew ? 'rule-changed' : '';
        const deletedClass = isDeleted ? 'rule-deleted' : '';
        const changedBadge = isDeleted
            ? '<span class="change-badge">🗑️ Verwijderd</span>'
            : isDisabled
                ? '<span class="change-badge">⏸️ Uitgeschakeld</span>'
                : isNew
                    ? '<span class="change-badge">🆕 Nieuw</span>'
                    : (isChanged ? '<span class="change-badge">✏️ Gewijzigd</span>' : '');

        const rowStyle = isDeleted
            ? 'opacity:0.7; border-left: 3px solid #b71c1c; background:#231216;'
            : (isDisabled ? 'opacity:0.65; border-left: 3px solid #e53935; background:#2a1212;' : '');

        const toggleHtml = isDeleted
            ? `<span style="margin-left:auto; font-size:10px; color:#d08a8a;">Verwijderd</span>`
            : `
                <label style="margin-left:auto; display:flex; align-items:center; gap:6px; font-size:10px; color:${isDisabled ? '#f48fb1' : '#8ab4f8'};" onclick="event.stopPropagation();">
                    <input type="checkbox" ${isDisabled ? '' : 'checked'} onchange="event.stopPropagation(); if (window.persistOpenCategoryState) window.persistOpenCategoryState(); if (window.persistOpenSectionState) window.persistOpenSectionState(); if (window.toggleRuleEnabled) window.toggleRuleEnabled('${categoryId}', '${r.id}', this.checked);" style="cursor:pointer;">
                    <span>${isDisabled ? 'Uit' : 'Aan'}</span>
                </label>
            `;

        // BELANGRIJK: De class 'clickable-rule' en de 'onclick' MOETEN hier staan
        return `
            <div class="tree-leaf rule-leaf clickable-rule ${changedClass} ${deletedClass}" onclick="if (window.isRuleDisabled && window.isRuleDisabled('${categoryId}', '${r.id}')) return; openRuleModal('${categoryId}', '${r.id}')" style="${rowStyle}">
                <span class="leaf-icon">⚖️</span>
                <div class="rule-content">
                    <div class="rule-title">${title} ${changedBadge}</div>
                    <div class="rule-subtitle">${formatDays(r.dayMask)}</div>
                </div>
                ${toggleHtml}
                <span class="rule-id">${r.id}</span>
            </div>
        `;
    }).join('');
}

/**
 * Genereert de HTML voor de lijst met applicaties binnen een categorie
 */
function renderAppsHTML(apps) {
    if (!apps || apps.length === 0) {
        return '<div class="tree-leaf app-leaf rule-empty">Geen apps. Klik op + om toe te voegen.</div>';
    }

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

let addAppCategoryId = null;

function getCategoryApps(categoryId) {
    if (!currentDataDraft || !Array.isArray(currentDataDraft.categoryApp)) return [];
    const entry = currentDataDraft.categoryApp.find(a => String(a.categoryId) === String(categoryId));
    return entry && Array.isArray(entry.apps) ? entry.apps : [];
}

function renderAddAppList(items, query) {
    const list = document.getElementById('add-app-list');
    if (!list) return;
    const onlyUncategorizedToggle = document.getElementById('add-app-only-uncategorized');
    const onlyUncategorized = !!(onlyUncategorizedToggle && onlyUncategorizedToggle.checked);

    const normalized = (query || '').trim().toLowerCase();
    const existingApps = new Set(getCategoryApps(addAppCategoryId).map(a => String(a)));

    const filtered = (items || []).filter(item => {
        const match = !normalized
            || item.readableName.toLowerCase().includes(normalized)
            || item.packageName.toLowerCase().includes(normalized);
        if (!match) return false;
        if (existingApps.has(String(item.packageName))) return false;
        if (onlyUncategorized) {
            return !Array.isArray(item.categories) || item.categories.length === 0;
        }
        return true;
    });

    if (filtered.length === 0) {
        list.innerHTML = '<div style="padding:10px; color:#666; font-size:12px;">Geen apps beschikbaar.</div>';
        return;
    }

    list.innerHTML = filtered.map(item => {
        const categoriesText = Array.isArray(item.categories) && item.categories.length > 0
            ? item.categories.join(', ')
            : '';
        return `
            <div class="app-select-item" onclick="selectAppForCategory('${item.packageName}')">
                <div class="app-select-name">${item.readableName}</div>
                <div class="app-select-package">${item.packageName}</div>
                ${categoriesText ? `<div class="app-select-categories">${categoriesText}</div>` : ''}
            </div>
        `;
    }).join('');
}

function showAddAppModal(categoryId) {
    addAppCategoryId = String(categoryId);
    const modal = document.getElementById('add-app-modal');
    const search = document.getElementById('add-app-search');
    if (search) search.value = '';
    const onlyToggle = document.getElementById('add-app-only-uncategorized');
    if (onlyToggle) onlyToggle.checked = false;
    renderAddAppList(appIndexItems || [], '');
    if (modal) modal.style.display = 'flex';
}

function hideAddAppModal() {
    const modal = document.getElementById('add-app-modal');
    if (modal) modal.style.display = 'none';
    addAppCategoryId = null;
}

function selectAppForCategory(packageName) {
    if (!addAppCategoryId || !packageName) return;
    if (typeof addAppToCategory === 'function') {
        addAppToCategory(addAppCategoryId, packageName);
    }
    hideAddAppModal();
}

/**
 * Regelt het in- en uitklappen van de boom-nodes in de UI
 * @param {HTMLElement} element - Het aangeklikte .tree-item
 */
function toggleNode(element) {
    // De 'content' is de div direct na de header die we hebben aangeklikt
    const content = element.nextElementSibling;
    const icon = element.querySelector('.tree-icon');
    const categoryId = element.getAttribute('data-category-id');
    const section = element.getAttribute('data-section');
    const key = categoryId && section ? `${categoryId}::${section}` : null;
    const categoryIdSpan = element.querySelector('.tree-id');
    const categoryKey = categoryIdSpan ? categoryIdSpan.textContent.trim() : null;
    
    if (content.style.display === "none") {
        content.style.display = "block";
        icon.innerText = "▼";
        element.classList.add('is-open'); // Trigger voor CSS animaties/kleuren
        if (key) storeOpenSectionKey(key, true);
        if (categoryKey) storeOpenCategoryKey(categoryKey, true);
    } else {
        content.style.display = "none";
        icon.innerText = "▶";
        element.classList.remove('is-open');
        if (key) storeOpenSectionKey(key, false);
        if (categoryKey) storeOpenCategoryKey(categoryKey, false);
    }
}

const OPEN_SECTIONS_STORAGE_KEY = 'timelimit_openSections';
const OPEN_CATEGORIES_STORAGE_KEY = 'timelimit_openCategories';

function loadOpenSectionKeys() {
    try {
        const raw = localStorage.getItem(OPEN_SECTIONS_STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function getPersistedOpenSectionKeys() {
    return loadOpenSectionKeys();
}

function loadOpenCategoryKeys() {
    try {
        const raw = localStorage.getItem(OPEN_CATEGORIES_STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function getPersistedOpenCategoryIds() {
    return loadOpenCategoryKeys();
}

function setOpenSectionKeys(keys) {
    if (!Array.isArray(keys) || keys.length === 0) {
        localStorage.removeItem(OPEN_SECTIONS_STORAGE_KEY);
        return;
    }
    const unique = Array.from(new Set(keys.map(k => String(k))));
    localStorage.setItem(OPEN_SECTIONS_STORAGE_KEY, JSON.stringify(unique));
}

function storeOpenSectionKey(key, isOpen) {
    if (!key) return;
    const current = new Set(loadOpenSectionKeys());
    if (isOpen) current.add(key);
    else current.delete(key);
    if (current.size === 0) {
        localStorage.removeItem(OPEN_SECTIONS_STORAGE_KEY);
    } else {
        localStorage.setItem(OPEN_SECTIONS_STORAGE_KEY, JSON.stringify(Array.from(current)));
    }
}

function storeOpenCategoryKey(key, isOpen) {
    if (!key) return;
    const current = new Set(loadOpenCategoryKeys());
    if (isOpen) current.add(key);
    else current.delete(key);
    if (current.size === 0) {
        localStorage.removeItem(OPEN_CATEGORIES_STORAGE_KEY);
    } else {
        localStorage.setItem(OPEN_CATEGORIES_STORAGE_KEY, JSON.stringify(Array.from(current)));
    }
}

/**
 * Genereert de HTML-structuur met aparte Rules en Apps secties per categorie
 */
function renderTreeHTML(nodes, level = 0, fullData = {}) {
    let html = '';
    const usedTimes = fullData.usedTimes || [];
    
    nodes.forEach(node => {
        const indent = level * 20;
        const subIndent = (level + 1) * 20;
        const leafIndent = (level + 2) * 20;

        const usageMs = getTodayUsage(node.categoryId, usedTimes);
        const usageText = usageMs > 0 ? ` <small class="usage-label">(${formatDuration(usageMs)})</small>` : '';

        html += `
            <div class="tree-node">
                <div class="tree-item" style="margin-left: ${indent}px" onclick="toggleNode(this)">
                    <span class="tree-icon">▶</span> <span class="tree-title">${node.title}${usageText}</span>
                    <span class="tree-id">${node.categoryId}</span>
                </div>
                
                <div class="tree-content" style="display: none;"> 
                    <div class="tree-node">
                        <div class="tree-item folder-node" data-category-id="${node.categoryId}" data-section="rules" style="margin-left: ${subIndent}px" onclick="toggleNode(this)">
                            <span class="tree-icon">▶</span>
                            <span class="tree-title folder-title">Rules</span>
                            <button class="rule-add-btn" type="button" onclick="event.stopPropagation(); addRuleToCategory('${node.categoryId}');">+</button>
                        </div>
                        <div class="tree-content" style="display: none; margin-left: ${leafIndent}px;">
                            ${renderRulesHTML(node.linkedRules, node.categoryId)}
                        </div>
                    </div>

                    <div class="tree-node">
                        <div class="tree-item folder-node" data-category-id="${node.categoryId}" data-section="apps" style="margin-left: ${subIndent}px" onclick="toggleNode(this)">
                            <span class="tree-icon">▶</span>
                            <span class="tree-title folder-title">Apps</span>
                            <button class="rule-add-btn" type="button" onclick="event.stopPropagation(); showAddAppModal('${node.categoryId}');">+</button>
                        </div>
                        <div class="tree-content" style="display: none; margin-left: ${leafIndent}px;">
                            ${renderAppsHTML(node.linkedApps)}
                        </div>
                    </div>

                    ${renderTreeHTML(node.children, level + 1, fullData)}
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

    if (!data || !data.categoryBase || !data.categoryApp || !data.rules) {
        if (container) {
            container.innerHTML = '<div style="color:#666;">Categorie data nog niet beschikbaar.</div>';
        }
        updateAppIndexDisplay(null);
        return;
    }

    if (container) {
        // Bewaar geopende categorieën (categoryId strings) zodat we ze kunnen herstellen
        const openCategoryIds = getOpenCategoryIds();

        const tree = buildCategoryTree(data);
        // Geef 'data' (de hele JSON) mee als derde argument
        container.innerHTML = renderTreeHTML(tree, 0, data);

        // Herstel geopende categorieën
        restoreOpenCategoryIds(openCategoryIds);
    }

    updateAppIndexDisplay(data);
}

window.showAddAppModal = showAddAppModal;
window.hideAddAppModal = hideAddAppModal;
window.selectAppForCategory = selectAppForCategory;

/**
 * Haal de lijst van geopende categoryId's uit de huidige DOM
 * @returns {Array<string>} Array met categoryId strings
 */
function getOpenCategoryIds() {
    const ids = [];
    try {
        document.querySelectorAll('.tree-item.is-open').forEach(item => {
            const idSpan = item.querySelector('.tree-id');
            if (idSpan) ids.push(idSpan.textContent.trim());
        });
    } catch (e) {
        console.warn('[DEBUG] getOpenCategoryIds fout:', e);
    }
    return ids;
}

/**
 * Herstelt de geopende categorieën op basis van een lijst met categoryId strings
 * @param {Array<string>} ids
 */
function restoreOpenCategoryIds(ids) {
    if (!ids || ids.length === 0) return;
    try {
        document.querySelectorAll('.tree-item').forEach(item => {
            const idSpan = item.querySelector('.tree-id');
            if (!idSpan) return;
            const cid = idSpan.textContent.trim();
            if (ids.indexOf(cid) !== -1) {
                // Open deze node
                item.classList.add('is-open');
                const icon = item.querySelector('.tree-icon');
                if (icon) icon.innerText = '▼';
                const content = item.nextElementSibling;
                if (content) content.style.display = 'block';
            }
        });
    } catch (e) {
        console.warn('[DEBUG] restoreOpenCategoryIds fout:', e);
    }
}

window.persistOpenCategoryState = persistOpenCategoryState;
window.getPersistedOpenSectionKeys = getPersistedOpenSectionKeys;
window.getPersistedOpenCategoryIds = getPersistedOpenCategoryIds;

/**
 * Haal open rules/apps secties op per categoryId.
 * @returns {Array<string>} Array met "categoryId::section" keys
 */
function getOpenSectionState() {
    const keys = [];
    try {
        document.querySelectorAll('.tree-item.folder-node.is-open').forEach(item => {
            const categoryId = item.getAttribute('data-category-id');
            const section = item.getAttribute('data-section');
            if (categoryId && section) {
                keys.push(`${categoryId}::${section}`);
            }
        });
    } catch (e) {
        console.warn('[DEBUG] getOpenSectionState fout:', e);
    }
    loadOpenSectionKeys().forEach((key) => {
        if (keys.indexOf(key) === -1) keys.push(key);
    });
    return keys;
}

function getOpenCategoryState() {
    const ids = [];
    try {
        document.querySelectorAll('.tree-item.is-open').forEach(item => {
            const idSpan = item.querySelector('.tree-id');
            if (idSpan) ids.push(idSpan.textContent.trim());
        });
    } catch (e) {
        console.warn('[DEBUG] getOpenCategoryState fout:', e);
    }
    loadOpenCategoryKeys().forEach((key) => {
        if (ids.indexOf(key) === -1) ids.push(key);
    });
    return ids;
}

function persistOpenSectionState() {
    const keys = getOpenSectionState();
    setOpenSectionKeys(keys);
}

function persistOpenCategoryState() {
    const ids = getOpenCategoryState();
    if (!ids || ids.length === 0) {
        localStorage.removeItem(OPEN_CATEGORIES_STORAGE_KEY);
        return;
    }
    localStorage.setItem(OPEN_CATEGORIES_STORAGE_KEY, JSON.stringify(ids));
}

/**
 * Herstel open rules/apps secties op basis van keys.
 * @param {Array<string>} keys
 */
function restoreOpenSectionState(keys) {
    if (!keys || keys.length === 0) return;
    try {
        document.querySelectorAll('.tree-item.folder-node').forEach(item => {
            const categoryId = item.getAttribute('data-category-id');
            const section = item.getAttribute('data-section');
            if (!categoryId || !section) return;
            const key = `${categoryId}::${section}`;
            if (keys.indexOf(key) !== -1) {
                item.classList.add('is-open');
                const icon = item.querySelector('.tree-icon');
                if (icon) icon.innerText = '▼';
                const content = item.nextElementSibling;
                if (content) content.style.display = 'block';
            }
        });
    } catch (e) {
        console.warn('[DEBUG] restoreOpenSectionState fout:', e);
    }
}

window.persistOpenSectionState = persistOpenSectionState;