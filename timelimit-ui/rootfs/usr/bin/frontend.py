import http.server
import socketserver
import os
import json

# Configuratie
PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        # We bouwen de template handmatig op om triple-quote fouten te voorkomen
        html_template = self.get_template_string()
        final_html = html_template.replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)
        
        self.wfile.write(final_html.encode("utf-8"))

    def get_template_string(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Control Panel</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px; margin: 0; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 20px; }
        .card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .setup-box { background: #1a1a1a; border: 1px solid #03a9f4; padding: 30px; border-radius: 12px; text-align: center; }
        input { background: #222; border: 1px solid #444; color: #fff; padding: 12px; width: 80%; margin: 15px 0; border-radius: 6px; font-family: monospace; outline: none; }
        button { background: #03a9f4; border: none; color: white; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        button:hover { background: #0288d1; transform: translateY(-1px); }
        button.secondary { background: #333; color: #ccc; border: 1px solid #444; margin-left: 10px; }
        #log { background: #000; color: #00ff00; padding: 15px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px; border: 1px solid #333; border-radius: 8px; margin-top: 10px; }
        .status-badge { padding: 6px 14px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
        .online { background: rgba(76, 175, 80, 0.15); color: #4caf50; border: 1px solid #4caf50; }
        .offline { background: rgba(244, 67, 54, 0.15); color: #f44336; border: 1px solid #f44336; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-top: 15px; }
        .user-card { background: #252525; padding: 20px; border-radius: 10px; border-left: 5px solid #03a9f4; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 style="margin:0; color:#03a9f4;">TimeLimit Tracer</h1>
                <small style="color:#666;">Home Assistant WebSocket Bridge</small>
            </div>
            <div id="conn-status" class="status-badge offline">● Disconnected</div>
        </div>

        <div id="setup-ui" class="setup-box hidden">
            <h3>Sessie Vereist</h3>
            <p>Plak hier je <b>deviceAuthToken</b>:</p>
            <input type="text" id="token-input" placeholder="DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY...">
            <br>
            <button onclick="saveToken()">Verbinden</button>
        </div>

        <div id="main-ui" class="hidden">
            <div style="margin-bottom: 20px;">
                <button onclick="fetchData()">🔄 Handmatige Sync</button>
                <button class="secondary" onclick="clearToken()">Reset</button>
            </div>
            <div class="card">
                <h3>👥 Familie Overzicht</h3>
                <div id="user-list" class="user-grid">Laden...</div>
            </div>
        </div>

        <h4>💬 Systeem Log:</h4>
        <div id="log"></div>
    </div>

    <script>
        const serverUrl = "###SERVER_URL###";
        let socket;
        const logEl = document.getElementById('log');

        function addLog(msg, color = "#00ff00") {
            const entry = document.createElement('div');
            entry.style.color = color;
            entry.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }

        function saveToken() {
            const val = document.getElementById('token-input').value.trim();
            if (val) { localStorage.setItem('tl_device_token', val); location.reload(); }
        }

        function clearToken() {
            localStorage.removeItem('tl_device_token'); location.reload();
        }

        const token = localStorage.getItem('tl_device_token');
        if (!token) {
            document.getElementById('setup-ui').classList.remove('hidden');
        } else {
            document.getElementById('main-ui').classList.remove('hidden');
            initWebSocket(token);
        }

        function initWebSocket(authToken) {
            addLog("Verbinden met WebSocket...");
            socket = io(serverUrl, { transports: ['websocket'], path: "/socket.io" });

            socket.on('connect', () => {
                document.getElementById('conn-status').className = 'status-badge online';
                document.getElementById('conn-status').textContent = '● Online';
                addLog("✅ Verbonden. Authenticeren...");
                socket.emit('devicelogin', authToken, (ack) => {
                    addLog("🚀 Login bevestigd!");
                    fetchData();
                });
            });

            socket.on('should sync', () => {
                addLog("🔔 Sync signaal ontvangen.");
                fetchData();
            });

            socket.on('disconnect', () => {
                document.getElementById('conn-status').className = 'status-badge offline';
                addLog("⚠️ Verbinding verbroken.", "#f44336");
            });
        }

        async function fetchData() {
            addLog("📡 API Request: /parent/get-family-data...");
            try {
                const response = await fetch(serverUrl + "/parent/get-family-data", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ deviceAuthToken: localStorage.getItem('tl_device_token') })
                });
                const result = await response.json();
                if (result.data && result.data.users) {
                    renderUsers(result.data.users.data || result.data.users);
                    addLog("✅ Sync compleet.");
                }
            } catch (err) {
                addLog("❌ API Fout: " + err.message, "#f44336");
            }
        }

        function renderUsers(users) {
            const list = document.getElementById('user-list');
            list.innerHTML = users.map(u => '<div class="user-card"><b>' + u.name + '</b><br><small>ID: ' + u.id + '</small></div>').join('');
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Server draait op poort {PORT}")
        httpd.serve_forever()