import http.server
import socketserver
import urllib.request
import json
import os
import ssl
from datetime import datetime
from crypto_utils import generate_family_hashes

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
    entry = {"timestamp": datetime.now().strftime("%d-%m %H:%M"), "email": email or "Wizard Session", "token": token, "clientId": client_id or "Wizard"}
    history.insert(0, entry)
    with open(HISTORY_PATH, 'w') as f: json.dump(history[:10], f)

ssl_context = ssl._create_unverified_context()

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def proxy_request(self, path, post_data):
        config = get_ha_config()
        target_url = f"{config['server_url'].strip().rstrip('/')}{path}"
        try:
            req = urllib.request.Request(target_url, data=post_data, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, context=ssl_context) as response:
                return 200, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            return 500, str(e).encode()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # Interne route voor veilige Python-hashing
        if self.path == '/generate-hashes':
            try:
                data = json.loads(post_data)
                hashes = generate_family_hashes(data['password'])
                self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps(hashes).encode())
            except Exception as e:
                self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode())
            return

        # Routing voor API proxy
        routes = {
            '/login': '/parent/sign-in-to-family',
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/sync': '/sync/pull-status'
        }
        
        target_path = routes.get(self.path, '/sync/pull-status')
        status, body = self.proxy_request(target_path, post_data)
        
        if self.path == '/wizard-step3' and status == 200:
            data = json.loads(body)
            if "deviceAuthToken" in data:
                save_to_history("Nieuwe Familie", data['deviceAuthToken'], "Wizard-Created")

        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith('/history'):
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f: self.wfile.write(f.read())
            else: self.wfile.write(b"[]")
            return
        
        self.send_response(200); self.send_header("Content-type", "text/html"); self.end_headers()
        config = get_ha_config()
        html = self.get_template().replace("###TOKEN###", config["auth_token"])
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
        .dashboard-view { padding: 20px; overflow-y: auto; }
        .inspector-panel { background: #050505; border-left: 1px solid #232a35; display: flex; flex-direction: column; }
        #json-view { flex: 1; padding: 15px; font-family: monospace; font-size: 11px; color: #03a9f4; white-space: pre-wrap; overflow-y: auto; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 130px; overflow-y: auto; font-family: monospace; font-size: 11px; border-top: 1px solid #232a35; }
        .btn { background: #03a9f4; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-right: 5px; }
        .btn-wizard { background: #9c27b0; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 10px; border-radius: 4px; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        .wizard-step { display: none; background: #151921; padding: 20px; border-radius: 12px; border: 1px solid #9c27b0; margin-bottom: 20px; }
    </style>
</head>
<body>
<header>
    <div><strong>TimeLimit Control v26</strong></div>
    <div>
        <button class="btn btn-wizard" onclick="showWizard(1)">🆕 Nieuwe Familie</button>
        <button class="btn" style="background:#444" onclick="fetchFullStatus()">Sync</button>
    </div>
</header>

<div class="main-container">
    <div class="dashboard-view">
        <div id="step-1" class="wizard-step">
            <h3>Stap 1: E-mail verificatie</h3>
            <input type="email" id="wiz-email" placeholder="naam@voorbeeld.nl">
            <button class="btn" onclick="wizStep1()">Verstuur Code</button>
        </div>
        <div id="step-2" class="wizard-step">
            <h3>Stap 2: Code invoeren</h3>
            <input type="text" id="wiz-code" placeholder="Drie woorden uit email">
            <button class="btn" onclick="wizStep2()">Valideer Code</button>
        </div>
        <div id="step-3" class="wizard-step">
            <h3>Stap 3: Beheerder instellen</h3>
            <input type="text" id="wiz-name" placeholder="Naam Beheerder" value="Beheerder">
            <input type="password" id="wiz-pass" placeholder="Kies een wachtwoord">
            <button class="btn" onclick="wizStep3()">Maak Familie Aan</button>
        </div>
        <div id="user-list"></div>
        <div id="log-area"></div>
    </div>
    <div class="inspector-panel">
        <div style="padding:10px; font-size:10px; color:#888;">RAW JSON</div>
        <div id="json-view"></div>
    </div>
</div>

<script>
    const TOKEN = "###TOKEN###";
    let wizardData = { mailLoginToken: "", mailAuthToken: "" };

    function addLog(msg, color="#00ff00") {
        const d = document.createElement('div');
        d.style.color = color;
        d.innerHTML = `[${new Date().toLocaleTimeString()}] ${msg}`;
        const log = document.getElementById('log-area');
        log.appendChild(d); log.scrollTop = log.scrollHeight;
    }

    function showWizard(step) {
        document.querySelectorAll('.wizard-step').forEach(s => s.style.display = 'none');
        if(step) document.getElementById('step-'+step).style.display = 'block';
    }

    async function wizStep1() {
        const email = document.getElementById('wiz-email').value;
        const res = await fetch('/wizard-step1', { method: 'POST', body: JSON.stringify({ mail: email, locale: "nl" }) });