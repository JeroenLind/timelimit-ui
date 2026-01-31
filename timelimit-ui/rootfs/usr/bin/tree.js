/**
 * tree.js - Bouwt de hiërarchische categorieboom
 */

function buildCategoryTree(categories) {
    const categoryMap = {};
    const tree = [];

    // 1. Maak een map van alle categorieën voor snelle toegang
    categories.forEach(cat => {
        categoryMap[cat.categoryId] = { ...cat, children: [] };
    });

    // 2. Koppel kinderen aan hun parents
    categories.forEach(cat => {
        const current = categoryMap[cat.categoryId];
        if (cat.parentCategoryId && categoryMap[cat.parentCategoryId]) {
            categoryMap[cat.parentCategoryId].children.push(current);
        } else {
            // Geen parent (of parent niet in lijst), dit is een root-node
            tree.push(current);
        }
    });

    // Sorteer op de 'sort' property van de API
    const sortFn = (a, b) => (a.sort || 0) - (b.sort || 0);
    tree.sort(sortFn);
    tree.forEach(node => node.children.sort(sortFn));

    return tree;
}

function renderTreeHTML(nodes, level = 0) {
    let html = '';
    nodes.forEach(node => {
        const indent = level * 20;
        html += `
            <div class="tree-item" style="margin-left: ${indent}px">
                <span class="tree-icon">${node.children.length > 0 ? '📂' : '📄'}</span>
                <span class="tree-title">${node.title}</span>
                <span class="tree-id">(${node.categoryId})</span>
            </div>
        `;
        if (node.children.length > 0) {
            html += renderTreeHTML(node.children, level + 1);
        }
    });
    return html;
}

// Global function om aan te roepen vanuit je dashboard
function updateCategoryDisplay(data) {
    const container = document.getElementById('category-tree-container');
    if (!container || !data.categoryBase) return;

    const tree = buildCategoryTree(data.categoryBase);
    container.innerHTML = `<h3>Categorie Structuur</h3>` + renderTreeHTML(tree);
} 