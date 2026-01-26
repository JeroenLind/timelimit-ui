import http.server
import socketserver
import os
import json

PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template()
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Control Panel</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #111; color: #eee; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding-bottom: 15px; }
        .card { background: #222; border-radius: 8px; padding: 20px; margin-bottom: 20px; border-left: 4px solid #03a9f4; }
        .setup-box { background: #1a1a1a; border: 1px solid #444; padding: 20px; border-radius: 8px; }
        input { background: #333; border: 1px solid #555; color: #fff; padding: 10px; width: calc(100% - 22px); margin: 10px 0; border-radius: 4px; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #0288d1; }
        #log { background: #000; color: #0f0; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 12px; border: 1px solid #333; }
        .hidden { display: none; }
        .status-online { color: #4caf50; }
        .status-offline { color: #f44336; }
        .user-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚀 TimeLimit NextGen</h2>
            <div id="conn-status" class="status-offline">● Disconnected</div>
        </div>

        <div id="setup-ui" class="setup-box hidden">
            <h3>Initial Setup</h3>
            <p>Geen actieve sessie gevonden. Voer je Device Auth Token in:</p>
            <input type="text" id="token-input" placeholder="DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY...">
            <button onclick="saveToken()">Start WebSocket Connectie</button>
            <hr style="border: 0; border-top: 1px solid #333; margin: 20px 0;">
            <p style="font-size: 0.8em; color: #888;">Nog geen familie? Gebruik de PowerShell scripts uit het dossier om eerst een account aan te maken.</p>
        </div>

        <div id="main-ui" class="hidden">
            <div class="card">
                <h3>Familie Leden</h3>
                <div id="user-list" class="user-grid">
                    <p>Wachten op data van server...</p>
                </div>
            </div>
            
            <button onclick="clearToken()" style="background: #444; font-size: 0.8em;">Token Reset / Uitloggen</button>
        </div>

        <h4>Systeem Log:</h4>
        <div id="log"></div>
    </div>

    <script>
const serverUrl = "###SERVER_URL###";
let socket;

// Fix: Definieer logEl globaal zodat addLog het kan vinden
const logEl = document.getElementById('log');

function addLog(msg) {
    const entry = document.createElement('div');
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    if (logEl) {
        logEl.appendChild(entry);
        logEl.scrollTop = logEl.scrollHeight;
    }
    console.log(msg); // Ook naar browser console voor backup
}

function saveToken() {
    const token = document.getElementById('token-input').value.trim();
    if (token) {
        localStorage.setItem('tl_device_token', token);
        location.reload();
    }
}

function clearToken() {
    localStorage.removeItem('tl_device_token');
    location.reload();
}

const token = localStorage.getItem('tl_device_token');

if (!token) {
    document.getElementById('setup-ui').classList.remove('hidden');
    addLog("Wachten op token invoer...");
} else {
    document.getElementById('main-ui').classList.remove('hidden');
    initWebSocket(token);
}

function initWebSocket(authToken) {
    addLog("Verbinden met WebSocket op: " + serverUrl);
    
    // Debug configuratie
    socket = io(serverUrl, { 
        transports: ['websocket'],
        query: { deviceAuthToken: authToken },
        reconnectionAttempts: 5,
        timeout: 10000
    });

    socket.on('connect', () => {
        document.getElementById('conn-status').className = 'status-online';
        document.getElementById('conn-status').textContent = '● Online';
        addLog("✅ Verbonden! Handshake geslaagd.");
    });

    socket.on('connect_error', (err) => {
        document.getElementById('conn-status').className = 'status-offline';
        addLog("❌ Verbindingsfout: " + err.message);
        
        // Specifieke check voor CORS of 404
        if (err.message === "xhr poll error") {
            addLog("Tip: Controleer of de TimeLimit server (192.168.68.30) bereikbaar is vanaf dit apparaat.");
        }
    });

    socket.onAny((event, data) => {
        addLog(`Event ontvangen: ${event}`);
        if (data && (data.users || data.state)) {
            renderUsers(data.users?.data || data.users || []);
        }
    });
}

function renderUsers(users) {
    const list = document.getElementById('user-list');
    if (!Array.isArray(users)) return;
    
    list.innerHTML = users.map(u => `
        <div style="background: #333; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50;">
            <strong>${u.name}</strong><br>
            <span style="font-size: 0.8em; color: #aaa;">ID: ${u.id} | Type: ${u.type}</span>
        </div>
    `).join('');
}
    </script>
</body>
</html>
""".replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)

if __name__ == "__main__":
    print(f"HA Frontend draait op http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()