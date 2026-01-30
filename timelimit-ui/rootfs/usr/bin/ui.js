function addLog(m, isError = false) { 
    const log = document.getElementById('log-area');
    log.innerHTML += `<div style="color:${isError ? '#ff4444':'#00ff00'}">[${new Date().toLocaleTimeString()}] ${m}</div>`;
    log.scrollTop = log.scrollHeight;
}

function showStep(s) {
    document.getElementById('wizard-ui').style.display = s > 0 ? 'block' : 'none';
    const steps = document.querySelectorAll('.wizard-step');
    steps.forEach((el, idx) => el.style.display = (idx+1 === s) ? 'block' : 'none');
}

function renderUsers(data) {
    const list = document.getElementById('user-list');
    if(data.users && data.users.data) {
        let html = "<ul>";
        data.users.data.forEach(u => html += `<li><strong>${u.name}</strong> (${u.type})</li>`);
        html += "</ul>";
        list.innerHTML = html;
    }
}