import http.server
import socketserver
import urllib.request
import json
import os
import ssl
from datetime import datetime

# --- CONFIGURATIE ---
CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json" # Hier blijven je tokens bewaard

def get_ha_config():
    defaults = {"server_url": "http://192.168.68.30:8080", "auth_token": ""}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**defaults, **json.load(f)}
        except: pass
    return defaults

def save_to_history(email, token, client_id):
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, 'r') as f: history = json.load(f)
        except: pass
    
    # Voeg nieuwe toe aan het begin van de lijst
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "email": email,
        "token": token,
        "clientId": client_id
    }
    history.insert(0, entry)
    # Bewaar alleen de laatste 10
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history[:10], f)

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
                        # Automatisch opslaan in geschiedenis bij succes
                        req_data = json.loads(post_data)
                        save_to_history(req_data.get('email'), data['deviceAuthToken'], req_data.get('clientId'))
                    
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(res_body)
                return
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode()); return

        # Default proxy naar pull-status
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
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; margin: 0; display: flex; flex-direction: column; height: 100vh; }
        header { padding: 15px 20px; background: #151921; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; }
        .main-container { display: grid; grid-template-columns: 1fr 450px; flex: 1; overflow: hidden; }
        .dashboard-view { padding: 20px; overflow-y: auto; }
        .inspector-panel { background: #050505; border-left: 1px solid #232a35; display: flex; flex-direction: column; }
        .card { background: #1c232d; border-radius: 12px; padding: 15px; border-left: 4px solid #03a9f4; margin-bottom: 15px; }
        .history-item { font-size: 0.8em; padding: 8px; border-bottom: 1px solid #333; cursor: pointer; }
        .history-item:hover { background: #232a35; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 120px; overflow-y: auto; font-family: monospace; font-size: 11px; border-top: 1px solid #232a35; }
        .btn { background: #03a9f4; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 8px; border-radius: 4px; margin-bottom: 5px; }
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
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <h3>Nieuwe Login</h3>
                    <input type="email" id="email" placeholder="E-mail" style="width:90%"><br>
                    <input type="password" id="password" placeholder="Wachtwoord" style="width:90%"><br>
                    <button class="btn" onclick="doLogin()">Start Verse Sessie</button>
                </div>
                <div>
                    <h3>Geschiedenis (Max 10)</h3>
                    <div id="history-list" style="max-height: 150px; overflow-y: auto;">Laden...</div>
                </div>
            </div>
        </div>
        <div id="user-list"></div>
        <div id="log-area"></div>
    </div>
    <div class="inspector-panel">
        <div style="padding:10px; background:#151921; font-size:12px; border-bottom:1px solid #232a35;">RAW JSON INSPECTOR</div>
        <div id="json-view" style="padding:15px; font-family:monospace; font-size:11px; color:#03a9f4; white-space:pre-wrap; overflow-y:auto;"></div>
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
        const res = await fetch(window.location.href.replace(/\/$/, "") + "/history");
        const history = await res.json();
        const list = document.getElementById('history-list');
        if(history.length === 0) { list.innerHTML = "Geen geschiedenis."; return; }
        list.innerHTML = history.map(h => `
            <div class="history-item" onclick="useHistoryToken('${h.token}')">
                <strong>${h.timestamp}</strong><br>${h.email}<br>
                <code style="color:#03a9f4">${h.token.substring(0,10)}...</code>
            </div>
        `).join('');
    }

    function useHistoryToken(token) {
        addLog("📋 Token uit geschiedenis geselecteerd!", "#ff9800");
        addLog("Kopieer dit naar HA: " + token, "#03a9f4");
        alert("Token gekopieerd naar de log hieronder. Plak deze in je HA Add-on configuratie.");
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
            const response = await fetch(window.location.href.replace(/\/$/, "") + "/login", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, clientId, deviceName: "HA Dashboard" })
            });
            const data = await response.json();
            if (data.deviceAuthToken) {
                addLog("✅ LOGIN SUCCES!", "#4caf50");
                addLog("NIEUW TOKEN: " + data.deviceAuthToken);
                loadHistory(); // Ververs lijst
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
            document.getElementById('user-list').innerHTML = users.map(u => `<div class="card"><strong>${u.name}</strong></div>`).join('');
        } catch (e) { addLog("❌ Sync fout", "red"); }
    }
    fetchFullStatus();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()