import http.server
import socketserver
import urllib.request
import json
import os
import ssl
from datetime import datetime

# --- CONFIGURATIE ---
CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json"

def get_ha_config():
    defaults = {"server_url": "http://192.168.68.30:8080", "auth_token": ""}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**defaults, **json.load(f)}
        except: pass
    return defaults

def save_to_history(email, token, client_id):
    if not token or len(token) < 5: return
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, 'r') as f: history = json.load(f)
        except: pass
    if any(h.get('token') == token for h in history): return
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "email": email or "Geïmporteerd uit HA Config",
        "token": token,
        "clientId": client_id or "N/A"
    }
    history.insert(0, entry)
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history[:10], f)

current_cfg = get_ha_config()
save_to_history(None, current_cfg['auth_token'], "Initial Config")

ssl_context = ssl._create_unverified_context()

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        config = get_ha_config()
        target_base = config["server_url"].strip().rstrip("/")
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        if self.path.endswith('/login'):
            target_url = f"{target_base}/parent/sign-in-to-family"
            try:
                req = urllib.request.Request(target_url, data=post_data, headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    res_body = response.read()
                    data = json.loads(res_body)
                    if "deviceAuthToken" in data:
                        req_data = json.loads(post_data)
                        save_to_history(req_data.get('email'), data['deviceAuthToken'], req_data.get('clientId'))
                    self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers(); self.wfile.write(res_body)
                return
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode()); return

        target_url = f"{target_base}/sync/pull-status"
        try:
            req = urllib.request.Request(target_url, data=post_data, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, context=ssl_context) as response:
                self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers(); self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500); self.end_headers(); self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        if self.path.endswith('/history'):
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f: self.wfile.write(f.read())
            else: self.wfile.write(b"[]")
            return
        config = get_ha_config()
        self.send_response(200); self.send_header("Content-type", "text/html"); self.end_headers()
        html = self.get_template().replace("###SERVER_URL###", config["server_url"]).replace("###TOKEN###", config["auth_token"])
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        header { height: 70px; padding: 0 20px; background: #151921; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
        
        /* De container vult de rest van het scherm */
        .main-container { display: grid; grid-template-columns: 1fr 450px; flex: 1; min-height: 0; }
        
        .dashboard-view { padding: 20px; overflow-y: auto; display: flex; flex-direction: column; }
        .inspector-panel { background: #050505; border-left: 1px solid #232a35; display: flex; flex-direction: column; min-height: 0; }
        
        #json-view { flex: 1; padding: 15px; font-family: 'Consolas', monospace; font-size: 11px; color: #03a9f4; white-space: pre-wrap; overflow-y: auto; background: #050505; }
        
        .card { background: #1c232d; border-radius: 12px; padding: 15px; border-left: 4px solid #03a9f4; margin-bottom: 15px; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 120px; overflow-y: auto; font-family: monospace; font-size: 11px; border: 1px solid #232a35; flex-shrink: 0; margin-top: auto; }
        
        .btn { background: #03a9f4; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 8px; border-radius: 4px; margin-bottom: 8px; width: 100%; box-sizing: border-box; }
        .history-item { font-size: 0.85em; padding: 10px; border-bottom: 1px solid #232a35; cursor: pointer; }
        .history-item:hover { background: #232a35; }
    </style>
</head>
<body>

<header>
    <div><strong>📱 TimeLimit Parent History Mode</strong></div>
    <div>
        <button class="btn" onclick="toggleLogin()">🔑 Login / History</button>
        <button class="btn" style="background:#444" onclick="fetchFullStatus()">🔄 Sync</button>
    </div>
</header>

<div class="main-container">
    <div class="dashboard-view">
        <div id="login-form" style="display:none; background:#151921; padding:20px; border-radius:12px; margin-bottom:20px; border:1px solid #333;">
            <div style="display:grid; grid-template-columns: 1fr 1.2fr; gap: 20px;">
                <div>
                    <h3>Nieuwe Login</h3>
                    <input type="email" id="email" placeholder="E-mail">
                    <input type="password" id="password" placeholder="Wachtwoord">
                    <button class="btn" onclick="doLogin()">Start Verse Sessie</button>
                </div>
                <div>
                    <h3>Tokens Geschiedenis</h3>
                    <div id="history-list" style="max-height: 200px; overflow-y: auto; background:#0b0e14; border-radius:4px;">Laden...</div>
                </div>
            </div>
        </div>
        <div id="user-list" style="flex: 1; overflow-y: auto; margin-bottom: 10px;">Laden van gebruikers...</div>
        <div id="log-area"></div>
    </div>
    
    <div class="inspector-panel">
        <div style="padding:10px; background:#151921; font-size:11px; font-weight:bold; border-bottom:1px solid #232a35; color:#888;">RAW JSON INSPECTOR</div>
        <div id="json-view">Geen data geladen.</div>
    </div>
</div>

<script>
    const TOKEN = "###TOKEN###";
    const logEl = document.getElementById('log-area');

    function addLog(msg, color="#00ff00") {
        const d = document.createElement('div');
        d.style.color = color;
        d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logEl.appendChild(d);
        logEl.scrollTop = logEl.scrollHeight;
    }

    async function loadHistory() {
        try {
            const baseUrl = window.location.href.split('?')[0].replace(/\/$/, "");
            const res = await fetch(baseUrl + "/history");
            const history = await res.json();
            const list = document.getElementById('history-list');
            list.innerHTML = history.length ? history.map(h => `
                <div class="history-item" onclick="useHistoryToken('${h.token}')">
                    <small>${h.timestamp}</small><br><strong>${h.email}</strong>
                </div>
            `).join('') : "Geen geschiedenis.";
        } catch(e) { console.error(e); }
    }

    function useHistoryToken(token) {
        addLog("📋 Token uit geschiedenis geselecteerd!", "#ff9800");
        addLog("TOKEN: " + token, "#03a9f4");
        alert("Token staat in de log. Kopieer deze naar HA Config.");
    }

    function toggleLogin() {
        const f = document.getElementById('login-form');
        f.style.display = f.style.display === 'none' ? 'block' : 'none';
        if(f.style.display === 'block') loadHistory();
    }

    async function doLogin() {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const clientId = "ha-dashboard-" + Math.random().toString(36).substring(7);
        try {
            const baseUrl = window.location.href.split('?')[0].replace(/\/$/, "");
            const response = await fetch(baseUrl + "/login", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, clientId, deviceName: "HA Dashboard" })
            });
            const data = await response.json();
            if (data.deviceAuthToken) {
                addLog("✅ LOGIN SUCCES!", "#4caf50");
                addLog("NIEUW TOKEN: " + data.deviceAuthToken);
                loadHistory(); 
            } else { addLog("❌ Fout: " + JSON.stringify(data), "red"); }
        } catch (e) { addLog("❌ Netwerkfout", "red"); }
    }

    async function fetchFullStatus() {
        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    deviceAuthToken: TOKEN,
                    status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 3 }
                })
            });
            const data = await response.json();
            document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
            const users = data.users?.data || [];
            document.getElementById('user-list').innerHTML = users.map(u => `
                <div class="card"><strong>${u.name}</strong><br><small style="color:gray;">ID: ${u.id}</small></div>
            `).join('');
        } catch (e) { addLog("❌ Sync fout", "red"); }
    }
    fetchFullStatus();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve