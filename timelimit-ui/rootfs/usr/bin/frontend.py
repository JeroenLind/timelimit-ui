import http.server
import socketserver
import urllib.request
import json
import os
import ssl

# --- CONFIGURATIE ---
CONFIG_PATH = "/data/options.json"

def get_ha_config():
    defaults = {
        "server_url": "http://192.168.68.30:8080",
        "auth_token": "DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**defaults, **json.load(f)}
        except Exception:
            pass
    return defaults

ssl_context = ssl._create_unverified_context()

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        config = get_ha_config()
        target_base = config["server_url"].strip().rstrip("/")
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # Check welk pad de frontend vraagt
        # Als de URL eindigt op 'login', stuur naar parent endpoint
        if self.path.endswith('/login'):
            target_url = f"{target_base}/parent/sign-in-to-family"
        else:
            target_url = f"{target_base}/sync/pull-status"
        
        try:
            req = urllib.request.Request(
                target_url,
                data=post_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, context=ssl_context) as response:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        config = get_ha_config()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        html = self.get_template()
        html = html.replace("###SERVER_URL###", config["server_url"])
        html = html.replace("###TOKEN###", config["auth_token"])
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Parent Control</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; margin: 0; display: flex; flex-direction: column; height: 100vh; }
        header { padding: 15px 20px; background: #151921; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; }
        .main-container { display: grid; grid-template-columns: 1fr 450px; flex: 1; overflow: hidden; }
        .dashboard-view { padding: 20px; overflow-y: auto; }
        .inspector-panel { background: #050505; border-left: 1px solid #232a35; display: flex; flex-direction: column; }
        .card { background: #1c232d; border-radius: 12px; padding: 15px; border-left: 4px solid #03a9f4; margin-bottom: 15px; }
        #log-area { background: #000; color: #00ff00; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; border-top: 1px solid #232a35; }
        #json-view { flex: 1; padding: 15px; font-family: monospace; font-size: 11px; color: #03a9f4; overflow-y: auto; white-space: pre-wrap; }
        .btn { background: #03a9f4; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-left: 5px; }
        .btn-secondary { background: #444; }
        input { background: #2a2a2a; border: 1px solid #444; color: white; padding: 8px; border-radius: 4px; margin-right: 5px; }
        .login-box { background: #151921; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px; }
    </style>
</head>
<body>

<header>
    <div><strong>📱 TimeLimit Parent Control</strong></div>
    <div>
        <button class="btn btn-secondary" onclick="toggleLogin()">🔑 Parent Login</button>
        <button class="btn" onclick="fetchFullStatus()">🔄 Vernieuw Data</button>
        <span id="socket-status" style="margin-left:10px; font-size:0.8em; color:gray;">WebSocket: ...</span>
    </div>
</header>

<div class="main-container">
    <div class="dashboard-view">
        <div id="login-form" class="login-box" style="display:none;">
            <h3>Ouder Inloggen</h3>
            <p style="font-size:0.8em; color:gray;">Log in om een nieuw Parent Token te genereren voor dit dashboard.</p>
            <input type="email" id="email" placeholder="E-mailadres">
            <input type="password" id="password" placeholder="Wachtwoord">
            <button class="btn" onclick="doLogin()">Inloggen</button>
        </div>

        <div id="user-list">Wachten op data...</div>
        <div id="log-area"></div>
    </div>
    
    <div class="inspector-panel">
        <div style="padding:10px; background:#151921; font-size:12px; font-weight:bold; border-bottom:1px solid #232a35;">RAW JSON INSPECTOR</div>
        <div id="json-view"></div>
    </div>
</div>

<script>
    const TOKEN = "###TOKEN###";
    const SERVER_URL = "###SERVER_URL###";
    const logEl = document.getElementById('log-area');

    function addLog(msg, color="#00ff00") {
        const d = document.createElement('div');
        d.style.color = color;
        d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logEl.appendChild(d);
        logEl.scrollTop = logEl.scrollHeight;
    }

    function toggleLogin() {
        const f = document.getElementById('login-form');
        f.style.display = f.style.display === 'none' ? 'block' : 'none';
    }

    async function doLogin() {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        addLog("🔑 Inlogpoging voor " + email + "...");

        try {
            // We gebruiken een relatief pad /login dat door de proxy wordt opgevangen
            const response = await fetch(window.location.href.replace(/\/$/, "") + "/login", {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    clientId: "ha-dashboard-" + Math.random().toString(36).substring(7),
                    deviceName: "Home Assistant Dashboard"
                })
            });
            const data = await response.json();
            document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);

            if (data.deviceAuthToken) {
                addLog("✅ LOGIN SUCCES! NIEUW TOKEN ONTVANGEN.", "#4caf50");
                addLog("Kopieer dit naar je HA Config: " + data.deviceAuthToken, "#03a9f4");
                alert("Login succesvol! Kopieer het token uit de log naar je Home Assistant Add-on configuratie.");
            } else {
                addLog("❌ Login mislukt: " + JSON.stringify(data), "red");
            }
        } catch (e) {
            addLog("❌ Netwerkfout tijdens login: " + e.message, "red");
        }
    }

    async function fetchFullStatus() {
        if (!TOKEN || TOKEN === "DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY") {
            addLog("⚠️ Gebruik het 'Parent Login' knopje om eerst te koppelen.", "#ff9800");
        }
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
            renderUI(data);
        } catch (e) {
            addLog("❌ Sync fout: " + e.message, "red");
        }
    }

    function renderUI(data) {
        const users = data.users?.data || [];
        document.getElementById('user-list').innerHTML = users.length ? users.map(u => `
            <div class="card">
                <strong>${u.name}</strong>
                <small style="display:block; color:gray;">ID: ${u.id}</small>
            </div>
        `).join('') : "Geen gebruikers gevonden.";
    }

    const socket = io(SERVER_URL, { transports: ['websocket'], path: "/socket.io" });
    socket.on('connect', () => {
        document.getElementById('socket-status').textContent = '● Online';
        document.getElementById('socket-status').style.color = '#4caf50';
        socket.emit('devicelogin', TOKEN, () => {
            addLog("✅ WS: Verbonden.");
            fetchFullStatus();
        });
    });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()