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
        
        # We sturen de POST altijd naar het pull-status endpoint op de backend
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
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
        .user-card { background: #1c232d; padding: 15px; border-radius: 8px; border-left: 4px solid #03a9f4; }
        #log { background: #000; color: #00ff00; padding: 10px; height: 180px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-top: 20px; border: 1px solid #333; }
    </style>
</head>
<body>
    <h2>📱 TimeLimit Hybrid Control</h2>
    <div class="card">
        <button onclick="fetchFullStatus()" style="background:#03a9f4; color:white; border:none; padding:10px 20px; border-radius:6px; cursor:pointer;">🔄 Vernieuw Data</button>
        <span id="socket-status" style="margin-left:15px; color:gray;">WebSocket: Verbinden...</span>
    </div>
    <div class="user-grid" id="user-list">Laden...</div>
    <div id="log"></div>

    <script>
        const TOKEN = "###TOKEN###";
        const SERVER_URL = "###SERVER_URL###";
        const logEl = document.getElementById('log');

        function addLog(msg, color="#00ff00") {
            const d = document.createElement('div');
            d.style.color = color;
            d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logEl.appendChild(d);
            logEl.scrollTop = logEl.scrollHeight;
        }

        async function fetchFullStatus() {
            addLog("📡 HTTP: Status ophalen...");
            try {
                // Gebruik window.location.href voor Ingress compatibiliteit
                const response = await fetch(window.location.href, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        deviceAuthToken: TOKEN,
                        status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 3 }
                    })
                });
                const data = await response.json();
                renderUI(data);
            } catch (e) {
                addLog("❌ Fout: " + e.message, "red");
            }
        }

        function renderUI(data) {
            const users = data.users?.data || [];
            addLog(`🎉 UI: ${users.length} gebruikers geladen.`);
            document.getElementById('user-list').innerHTML = users.map(u => `
                <div class="user-card">
                    <strong>${u.name}</strong>
                    <small style="display:block; color:gray;">ID: ${u.id}</small>
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