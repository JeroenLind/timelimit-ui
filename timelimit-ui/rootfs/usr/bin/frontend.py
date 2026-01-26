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
        body { font-family: -apple-system, system-ui, sans-serif; background: #111; color: #eee; padding: 20px; margin: 0; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 20px; }
        
        .card { background: #222; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 4px solid #03a9f4; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        .setup-box { background: #1a1a1a; border: 1px solid #444; padding: 30px; border-radius: 12px; text-align: center; }
        
        input { background: #333; border: 1px solid #555; color: #fff; padding: 12px; width: 80%; margin: 15px 0; border-radius: 6px; font-family: monospace; }
        button { background: #03a9f4; border: none; color: white; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        button:hover { background: #0288d1; transform: translateY(-1px); }
        button.secondary { background: #444; margin-top: 10px; font-size: 0.8em; }
        
        #log { background: #000; color: #0f0; padding: 15px; height: 180px; overflow-y: auto; font-family: 'Cascadia Code', monospace; font-size: 12px; border: 1px solid #333; border-radius: 8px; }
        
        .status-badge { padding: 5px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .online { background: rgba(76, 175, 80, 0.2); color: #4caf50; border: 1px solid #4caf50; }
        .offline { background: rgba(244, 67, 54, 0.2); color: #f44336; border: 1px solid #f44336; }
        
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
        .user-card { background: #333; padding: 15px; border-radius: 8px; border-bottom: 3px solid #03a9f4; }
        .hidden { display: none; }
        hr { border: 0; border-top: 1px solid #333; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 style="margin:0; color:#03a9f4;">TimeLimit <span style="color:#eee; font-weight:300;">NextGen</span></h1>
                <small style="color:#666;">Home Assistant Integration Interface</small>
            </div>
            <div id="conn-status" class="status-badge offline">● DISCONNECTED</div>
        </div>

        <div id="setup-ui" class="setup-box hidden">
            <h3>Nieuwe Sessie Starten</h3>
            <p>Voer de <b>Device Auth Token</b> in die je via PowerShell hebt gegenereerd:</p>
            <input type="text" id="token-input" placeholder="DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY...">
            <br>
            <button onclick="saveToken()">Verbinding Activeren</button>
        </div>

        <div id="main-ui" class="hidden">
            <div style="margin-bottom: 20px; display: flex; gap: 10px;">
                <button onclick="requestRefresh()">🔄 Data Verversen</button>
                <button class="secondary" onclick="clearToken()">Token Resetten</button>
            </div>

            <div class="card">
                <h3 style="margin-top:0;">👨‍👩‍👧‍👦 Familie & Gebruikers</h3>
                <div id="user-list" class="user-grid">
                    <p style="color:#888;">Wachten op data van WebSocket...</p>
                </div>
            </div>
        </div>

        <h4>🖥️ Systeem Console:</h4>
        <div id="log"></div>
    </div>

    <script>
        const serverUrl = "###SERVER_URL###";
        let socket;
        const logEl = document.getElementById('log');

        function addLog(msg) {
            const entry = document.createElement('div');
            entry.style.marginBottom = "4px";
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
            console.log(msg);
        }

        function saveToken() {
            const token = document.getElementById('token-input').value.trim();
            if (token) {
                localStorage.setItem('tl_device_token', token);
                addLog("Token opgeslagen. Pagina herladen...");
                location.reload();
            }
        }

        function clearToken() {
            if(confirm("Weet je zeker dat je wilt uitloggen?")) {
                localStorage.removeItem('tl_device_token');
                location.reload();
            }
        }

        const token = localStorage.getItem('tl_device_token');

        if (!token) {
            document.getElementById('setup-ui').classList.remove('hidden');
            addLog("Geen token gevonden. Wachten op configuratie...");
        } else {
            document.getElementById('main-ui').classList.remove('hidden');
            initWebSocket(token);
        }

        function initWebSocket(authToken) {
            addLog("Verbinden met WebSocket op: " + serverUrl);
            
            // Handshake via query parameter deviceAuthToken
            socket = io(serverUrl, { 
                transports: ['websocket'],
                query: { deviceAuthToken: authToken } 
            });

            socket.on('connect', () => {
                const badge = document.getElementById('conn-status');
                badge.className = 'status-badge online';
                badge.textContent = '● ONLINE';
                addLog("✅ Verbonden! Handshake geaccepteerd.");
                
                // Forceer direct data-opvraag
                socket.emit('get-state');
            });

            socket.on('disconnect', () => {
                const badge = document.getElementById('conn-status');
                badge.className = 'status-badge offline';
                badge.textContent = '● DISCONNECTED';
                addLog("⚠️ Verbinding verbroken.");
            });

            socket.on('connect_error', (err) => {
                addLog("❌ WebSocket Fout: " + err.message);
            });

            // Universele listener voor alle binnenkomende events
            socket.onAny((event, data) => {
                addLog(`Inkomend event: [${event}]`);
                
                // Verschillende servers sturen data onder verschillende namen
                if (event === 'state' || event === 'users' || event === 'family-data') {
                    // Diep graven in het object als het verpakt is (data.users.data)
                    let users = [];
                    if (data.users && data.users.data) users = data.users.data;
                    else if (data.users) users = data.users;
                    else if (Array.isArray(data)) users = data;
                    
                    if (users.length > 0) {
                        renderUsers(users);
                    }
                }
            });
        }

        function requestRefresh() {
            if (socket && socket.connected) {
                addLog("Handmatige update aangevraagd...");
                socket.emit('get-state');
                socket.emit('get-users');
            }
        }

        function renderUsers(users) {
            const list = document.getElementById('user-list');
            list.innerHTML = users.map(u => `
                <div class="user-card">
                    <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 4px;">${u.name}</div>
                    <div style="color: #03a9f4; font-size: 0.85em; font-family: monospace;">ID: ${u.id}</div>
                    <div style="color: #888; font-size: 0.8em; margin-top: 5px;">Type: ${u.type}</div>
                </div>
            `).join('');
            addLog(`UI bijgewerkt: ${users.length} gebruikers getoond.`);
        }
    </script>
</body>
</html>
""".replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)

if __name__ == "__main__":
    print(f"TimeLimit Dashboard live op http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()