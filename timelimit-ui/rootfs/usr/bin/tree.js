/**
 * tree.js - Interactieve boomstructuur met Apps en Rules
 */

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

function renderTreeHTML(nodes, level = 0) {
    let html = '';
    nodes.forEach(node => {
        const hasChildren = node.children.length > 0 || node.linkedApps.length > 0 || node.linkedRules.length > 0;
        const indent = level * 20;

        html += `
            <div class="tree-node" style="margin-left: ${indent}px">
                <div class="tree-item ${hasChildren ? 'has-children' : ''}" onclick="toggleNode(this)">
                    <span class="tree-icon">${hasChildren ? '▶' : '•'}</span>
                    <span class="tree-title">${node.title}</span>
                    <span class="tree-id">${node.categoryId}</span>
                </div>
                <div class="tree-content" style="display: none;">
                    ${renderTreeHTML(node.children, 1)}
                    ${renderRulesHTML(node.linkedRules)}
                    ${renderAppsHTML(node.linkedApps)}
                </div>
            </div>
        `;
    });
    return html;
}

function renderRulesHTML(rules) {
    return rules.map(r => `
        <div class="tree-leaf rule-leaf">
            <span class="leaf-icon">⏳</span>
            <span>Regel: ${r.maxTime > 0 ? (r.maxTime / 3600000).toFixed(1) + 'u' : 'Blokkade'}</span>
        </div>
    `).join('');
}

function renderAppsHTML(apps) {
    return apps.map(app => `
        <div class="tree-leaf app-leaf">
            <span class="leaf-icon">📱</span>
            <span>${app.split('.').pop()}</span>
        </div>
    `).join('');
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