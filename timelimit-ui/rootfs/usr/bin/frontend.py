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
    <title>TimeLimit Hybrid Control</title>
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
        
        .btn { background: #03a9f4; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .status-dot { font-size: 0.9em; color: gray; }
    </style>
</head>
<body>

<header>
    <div><strong>📱 TimeLimit Hybrid Control</strong></div>
    <div>
        <button class="btn" onclick="fetchFullStatus()">🔄 Vernieuw Data</button>
        <span id="socket-status" class="status-dot">WebSocket: Verbinden...</span>
    </div>
</header>

<div class="main-container">
    <div class="dashboard-view">
        <div id="user-list" class="user-grid">Laden...</div>
        <div id="log-area"></div>
    </div>
    
    <div class="inspector-panel">
        <div style="padding:10px; background:#151921; font-size:12px; font-weight:bold; border-bottom:1px solid #232a35;">RAW JSON INSPECTOR</div>
        <div id="json-view">Wachten op data sync...</div>
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

    async function fetchFullStatus() {
        addLog("📡 HTTP: Status ophalen via pull-status...");
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
            
            // Werk de Inspector bij met de ruwe data
            document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
            
            renderUI(data);
        } catch (e) {
            addLog("❌ Fout: " + e.message, "red");
            document.getElementById('json-view').textContent = "FOUT: " + e.message;
        }
    }

    function renderUI(data) {
        const users = data.users?.data || [];
        addLog(`🎉 UI: ${users.length} gebruikers geladen.`);
        document.getElementById('user-list').innerHTML = users.map(u => `
            <div class="card">
                <strong>${u.name}</strong>
                <small style="display:block; color:gray; margin-top:5px;">ID: ${u.id}</small>
            </div>
        `).join('');
    }

    const socket = io(SERVER_URL, { transports: ['websocket'], path: "/socket.io" });
    socket.on('connect', () => {
        document.getElementById('socket-status').textContent = '● WebSocket: Verbonden';
        document.getElementById('socket-status').style.color = '#4caf50';
        socket.emit('devicelogin', TOKEN, () => {
            addLog("✅ WS: Login succesvol.");
            fetchFullStatus();
        });
    });
    socket.on('should sync', () => fetchFullStatus());
</script>

</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()