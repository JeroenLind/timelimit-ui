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
    entry = {"timestamp": datetime.now().strftime("%d-%m %H:%M"), "email": email or "Nieuwe Familie", "token": token, "clientId": client_id or "Wizard"}
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
        
        # Routing voor de Wizard en Sync
        routes = {
            '/login': '/parent/sign-in-to-family',
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/sync': '/sync/pull-status'
        }
        
        target_path = routes.get(self.path, '/sync/pull-status')
        status, body = self.proxy_request(target_path, post_data)
        
        # Als stap 3 slaagt, slaan we het token op in history
        if self.path == '/wizard-step3' and status == 200:
            data = json.loads(body)
            if "deviceAuthToken" in data:
                save_to_history("Nieuwe Familie", data['deviceAuthToken'], "Created-via-Wizard")

        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith('/history'):
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            history = []
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
        .card { background: #1c232d; border-radius: 12px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #03a9f4; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 120px; overflow-y: auto; font-family: monospace; font-size: 11px; border-top: 1px solid #232a35; }
        .btn { background: #03a9f4; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-right: 5px; }
        .btn-wizard { background: #9c27b0; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 10px; border-radius: 4px; margin-bottom: 10px; width: 100%; box-sizing: border-box; }
        .wizard-step { display: none; background: #151921; padding: 20px; border-radius: 12px; border: 1px solid #9c27b0; margin-bottom: 20px; }
    </style>
</head>
<body>
<header>
    <div><strong>TimeLimit Control v24</strong></div>
    <div>
        <button class="btn btn-wizard" onclick="showWizard(1)">🆕 Nieuwe Familie</button>
        <button class="btn" onclick="toggleLogin()">History</button>
        <button class="btn" style="background:#444" onclick="fetchFullStatus()">Sync</button>
    </div>
</header>

<div class="main-container">
    <div class="dashboard-view">
        <div id="step-1" class="wizard-step">
            <h3>Stap 1: E-mail verificatie</h3>
            <p>Vul je e-mail in om een verificatiecode te ontvangen.</p>
            <input type="email" id="wiz-email" placeholder="naam@voorbeeld.nl">
            <button class="btn" onclick="wizStep1()">Verstuur Code</button>
        </div>

        <div id="step-2" class="wizard-step">
            <h3>Stap 2: Code invoeren</h3>
            <p>Voer de 3 woorden (of code) in die je per e-mail hebt ontvangen.</p>
            <input type="text" id="wiz-code" placeholder="Woord1 Woord2 Woord3">
            <button class="btn" onclick="wizStep2()">Valideer Code</button>
        </div>

        <div id="step-3" class="wizard-step">
            <h3>Stap 3: Familie aanmaken</h3>
            <input type="text" id="wiz-name" placeholder="Naam Beheerder" value="Beheerder">
            <input type="password" id="wiz-pass" placeholder="Kies een Wachtwoord">
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
        addLog("Stap 1: Code aanvragen voor " + email);
        const res = await fetch('/wizard-step1', {
            method: 'POST',
            body: JSON.stringify({ mail: email, locale: "nl" })
        });
        const data = await res.json();
        if(data.mailLoginToken) {
            wizardData.mailLoginToken = data.mailLoginToken;
            addLog("Code is verzonden! Check je mail.", "#4caf50");
            showWizard(2);
        } else { addLog("Fout: " + JSON.stringify(data), "red"); }
    }

    async function wizStep2() {
        const code = document.getElementById('wiz-code').value;
        const res = await fetch('/wizard-step2', {
            method: 'POST',
            body: JSON.stringify({ receivedCode: code, mailLoginToken: wizardData.mailLoginToken })
        });
        const data = await res.json();
        if(data.mailAuthToken) {
            wizardData.mailAuthToken = data.mailAuthToken;
            addLog("Code geaccepteerd!", "#4caf50");
            showWizard(3);
        } else { addLog("Fout: " + JSON.stringify(data), "red"); }
    }

    async function wizStep3() {
        const name = document.getElementById('wiz-name').value;
        // We gebruiken de vaste hashes uit je scenario om de server te pleasen
        const dummyHash = "$2a$12$12345678901234567890123456789012345678901234567890123";
        const dummySalt = "$2a$12$1234567890123456789012";

        const res = await fetch('/wizard-step3', {
            method: 'POST',
            body: JSON.stringify({
                mailAuthToken: wizardData.mailAuthToken,
                parentName: name,
                parentPassword: { hash: dummyHash, secondHash: dummyHash, secondSalt: dummySalt },
                timeZone: "Europe/Amsterdam",
                deviceName: "Dashboard Wizard",
                parentDevice: { model: "WebBrowser" },
                clientLevel: 1
            })
        });
        const data = await res.json();
        if(data.deviceAuthToken) {
            addLog("🎉 FAMILIE AANGEMAAKT!", "#4caf50");
            addLog("Nieuw Token: " + data.deviceAuthToken, "#03a9f4");
            showWizard(null);
        } else { addLog("Fout: " + JSON.stringify(data), "red"); }
    }

    async function fetchFullStatus() {
        const res = await fetch('/sync', { method: 'POST', body: JSON.stringify({ deviceAuthToken: TOKEN, status: { users: "", clientLevel: 3 } }) });
        const data = await res.json();
        document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
    }
    fetchFullStatus();
</script>
</body>
</html>"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()