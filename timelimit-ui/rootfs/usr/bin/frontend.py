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
            with open(CONFIG_PATH, 'r') as f: return {**defaults, **json.load(f)}
        except: pass
    return defaults

def save_to_history(email, token, client_id):
    if not token or len(token) < 5: return
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, 'r') as f: history = json.load(f)
        except: pass
    
    # Update bestaande entry als token al bestaat (om bijv. email toe te voegen)
    for h in history:
        if h.get('token') == token:
            if email and h['email'] == "HA Config": h['email'] = email
            if client_id and h['clientId'] == "Initial": h['clientId'] = client_id
            with open(HISTORY_PATH, 'w') as f: json.dump(history, f)
            return

    entry = {
        "timestamp": datetime.now().strftime("%d-%m %H:%M"), 
        "email": email or "HA Config", 
        "token": token, 
        "clientId": client_id or "Initial"
    }
    history.insert(0, entry)
    with open(HISTORY_PATH, 'w') as f: json.dump(history[:10], f)

# Bij start de huidige staat opslaan
current_cfg = get_ha_config()
save_to_history(None, current_cfg['auth_token'], None)

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
        return r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        header { height: 60px; padding: 0 20px; background: #151921; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
        .main-container { display: grid; grid-template-columns: 1fr 450px; flex: 1; min-height: 0; }
        .dashboard-view { padding: 20px; overflow-y: auto; display: flex; flex-direction: column; }
        .inspector-panel { background: #050505; border-left: 1px solid #232a35; display: flex; flex-direction: column; min-height: 0; }
        #json-view { flex: 1; padding: 15px; font-family: monospace; font-size: 11px; color: #03a9f4; white-space: pre-wrap; overflow-y: auto; }
        .card { background: #1c232d; border-radius: 12px; padding: 15px; border-left: 4px solid #03a9f4; margin-bottom: 15px; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 130px; overflow-y: auto; font-family: monospace; font-size: 11px; border: 1px solid #232a35; flex-shrink: 0; margin-top: auto; }
        .btn { background: #03a9f4; color: white; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .btn-info { background: #607d8b; margin-right: 5px; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 8px; border-radius: 4px; margin-bottom: 8px; width: 100%; box-sizing: border-box; }
        .history-item { font-size: 0.8em; padding: 10px; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; }
        .help-box { background: #232a35; padding: 10px; border-radius: 4px; font-size: 0.85em; color: #ff9800; border: 1px solid #444; margin-top: 10px; }
    </style>
</head>
<body>
<header>
    <div><strong>TimeLimit Control v23</strong></div>
    <div>
        <button class="btn" onclick="toggleLogin()">Geschiedenis & Login</button>
        <button class="btn" style="background:#444" onclick="fetchFullStatus()">Sync</button>
    </div>
</header>
<div class="main-container">
    <div class="dashboard-view">
        <div id="login-form" style="display:none; background:#151921; padding:15px; border-radius:8px; margin-bottom:15px; border:1px solid #333;">
            <div style="display:grid; grid-template-columns: 1fr 1.5fr; gap: 15px;">
                <div>
                    <h4>Nieuwe Login</h4>
                    <input type="email" id="email" placeholder="E-mail">
                    <input type="password" id="password" placeholder="Wachtwoord">
                    <button class="btn" onclick="doLogin()">Start Login</button>
                    <div class="help-box">
                        <strong>Backup Info:</strong> Als je teruggaat naar een oud token, hoef je <u>geen</u> email of wachtwoord in te vullen in de add-on. Alleen het token is genoeg voor de sync.
                    </div>
                </div>
                <div>
                    <h4>Token Geschiedenis</h4>
                    <div id="history-list" style="max-height: 300px; overflow-y: auto; background:#000; border-radius:4px;"></div>
                </div>
            </div>
        </div>
        <div id="user-list" style="flex: 1; overflow-y: auto;"></div>
        <div id="log-area"></div>
    </div>
    <div class="inspector-panel">
        <div id="inspector-title" style="padding:10px; font-size:10px; border-bottom:1px solid #232a35; color:#888;">RAW JSON INSPECTOR</div>
        <div id="json-view"></div>
    </div>
</div>
<script>
    const TOKEN = "###TOKEN###";
    let historyData = [];

    function addLog(msg, color="#00ff00") {
        const d = document.createElement('div');
        d.style.color = color;
        d.innerHTML = `[${new Date().toLocaleTimeString()}] ${msg}`;
        document.getElementById('log-area').appendChild(d);
        document.getElementById('log-area').scrollTop = 99999;
    }

    async function loadHistory() {
        const res = await fetch(window.location.href.split('?')[0].replace(/\/$/, "") + "/history");
        historyData = await res.json();
        document.getElementById('history-list').innerHTML = historyData.map((h, idx) => `
            <div class="history-item">
                <div><small>${h.timestamp}</small><br><strong>${h.email}</strong></div>
                <div>
                    <button class="btn btn-info" style="padding:4px 8px; font-size:10px;" onclick="showHistoryInfo(${idx})">Info</button>
                    <button class="btn" style="padding:4px 8px; font-size:10px;" onclick="restoreToken('${h.token}')">Gebruik</button>
                </div>
            </div>`).join('');
    }

    function showHistoryInfo(index) {
        const data = historyData[index];
        document.getElementById('inspector-title').textContent = "HISTORY POINT: " + data.timestamp;
        document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
    }

    function restoreToken(t) {
        addLog("--- HERSTEL TOKEN ---", "#ff9800");
        addLog(t, "#03a9f4");
        alert("Token gekopieerd naar log.");
    }

    function toggleLogin() {
        const f = document.getElementById('login-form');
        f.style.display = f.style.display === 'none' ? 'block' : 'none';
        if(f.style.display === 'block') loadHistory();
    }

    async function doLogin() {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        if(!email || !password) { alert("Vul email en wachtwoord in voor een nieuwe login."); return; }
        
        addLog("Nieuwe login gestart voor " + email);
        const response = await fetch(window.location.href.split('?')[0].replace(/\/$/, "") + "/login", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, clientId: "ha-"+Math.random().toString(36).substr(2, 5), deviceName: "HA Dashboard" })
        });
        const data = await response.json();
        if(data.deviceAuthToken) { addLog("✅ Login succes!", "#4caf50"); loadHistory(); }
        else { addLog("❌ Fout: " + JSON.stringify(data), "red"); }
    }

    async function fetchFullStatus() {
        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ deviceAuthToken: TOKEN, status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 3 } })
            });
            const data = await response.json();
            document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
            document.getElementById('user-list').innerHTML = (data.users?.data || []).map(u => `
                <div class="card"><strong>${u.name}</strong><br><small style="color:gray">ID: ${u.id}</small></div>`).join('');
        } catch(e) { addLog("Sync fout", "red"); }
    }
    fetchFullStatus();
</script>
</body>
</html>"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()