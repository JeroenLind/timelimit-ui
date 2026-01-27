import http.server
import socketserver
import urllib.request
import json

PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"
SAVED_TOKEN = "DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template_string().replace("###SERVER_URL###", TIMELIMIT_SERVER_URL).replace("###TOKEN###", SAVED_TOKEN)
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        target_url = f"{TIMELIMIT_SERVER_URL}/sync/pull-status"
        try:
            req = urllib.request.Request(target_url, data=post_data, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req) as response:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def get_template_string(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Tracer - Dashboard</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root { --bg: #0b0e14; --card: #151921; --accent: #03a9f4; --text: #e1e1e1; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; }
        
        /* Header & Layout */
        header { background: var(--card); padding: 15px 25px; border-bottom: 1px solid #232a35; display: flex; justify-content: space-between; align-items: center; }
        .main-container { display: flex; flex: 1; overflow: hidden; }
        
        /* Left Side: UI */
        .ui-panel { flex: 1; padding: 25px; overflow-y: auto; border-right: 1px solid #232a35; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .child-card { background: var(--card); border-radius: 12px; padding: 20px; position: relative; border: 1px solid #232a35; transition: transform 0.2s; }
        .child-card:hover { transform: translateY(-3px); border-color: var(--accent); }
        .online-dot { height: 12px; width: 12px; background: #4caf50; border-radius: 50%; display: inline-block; margin-right: 8px; box-shadow: 0 0 8px #4caf50; }
        .offline-dot { height: 12px; width: 12px; background: #555; border-radius: 50%; display: inline-block; margin-right: 8px; }
        
        /* Right Side: Raw Debug */
        .debug-panel { width: 400px; background: #05070a; display: flex; flex-direction: column; }
        .debug-header { padding: 10px 15px; background: #111; font-size: 12px; font-weight: bold; border-bottom: 1px solid #222; color: #888; }
        #raw-log { flex: 1; padding: 15px; font-family: 'Consolas', monospace; font-size: 11px; overflow-y: auto; color: #00ff00; white-space: pre-wrap; }
        
        /* Components */
        .stat-row { display: flex; justify-content: space-between; margin-top: 10px; font-size: 0.9em; }
        .battery { color: #8bc34a; font-weight: bold; }
        .btn { background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .btn:hover { filter: brightness(1.1); }
        .badge { background: #333; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
    </style>
</head>
<body>

<header>
    <div>
        <h2 style="margin:0; color:var(--accent);">TimeLimit Live Control</h2>
        <small id="socket-status">WebSocket: Connecting...</small>
    </div>
    <button class="btn" onclick="fetchFullStatus()">🔄 Handmatige Sync</button>
</header>

<div class="main-container">
    <div class="ui-panel">
        <div class="user-grid" id="user-list">
            <p style="color:gray;">Wachten op data van de server...</p>
        </div>
    </div>

    <div class="debug-panel">
        <div class="debug-header">JSON DATA INSPECTOR</div>
        <div id="raw-log">Logging gestart...</div>
    </div>
</div>

<script>
    const rawLogEl = document.getElementById('raw-log');
    let onlineDevices = new Set();

    function logRaw(obj) {
        rawLogEl.textContent = JSON.stringify(obj, null, 2);
    }

    // WebSocket Setup
    const socket = io("###SERVER_URL###", { transports: ['websocket'], path: "/socket.io" });

    socket.on('connect', () => {
        document.getElementById('socket-status').textContent = '● WebSocket: Verbonden (' + socket.id + ')';
        document.getElementById('socket-status').style.color = '#4caf50';
        
        socket.emit('devicelogin', "###TOKEN###", () => {
            console.log("WS: Login OK");
            fetchFullStatus();
        });
    });

    socket.on('connected devices', (devices) => {
        onlineDevices = new Set(devices);
        fetchFullStatus(); // Update UI om online status te tonen
    });

    socket.on('should sync', (data) => {
        console.log("WS: Sync requested", data);
        fetchFullStatus();
    });

    // HTTP Pull
    async function fetchFullStatus() {
        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    deviceAuthToken: "###TOKEN###",
                    status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 3 }
                })
            });
            const data = await response.json();
            logRaw(data); // Stuur naar de debug panel
            renderDashboard(data);
        } catch (e) {
            rawLogEl.textContent = "Fout bij ophalen data: " + e.message;
        }
    }

    function renderDashboard(data) {
        const userListEl = document.getElementById('user-list');
        const users = data.users?.data || [];
        const devices = data.devices?.data || [];

        if (users.length === 0) {
            userListEl.innerHTML = "<p>Geen gebruikers gevonden.</p>";
            return;
        }

        userListEl.innerHTML = users.map(user => {
            // Zoek bijbehorende apparaten voor deze gebruiker
            const userDevices = devices.filter(d => d.userId === user.id);
            const isOnline = userDevices.some(d => onlineDevices.has(d.deviceId));
            
            return `
                <div class="child-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <h3 style="margin:0;">${user.name}</h3>
                            <small style="color:gray;">ID: ${user.id}</small>
                        </div>
                        <span class="${isOnline ? 'online-dot' : 'offline-dot'}"></span>
                    </div>

                    <div style="margin-top:15px; border-top: 1px solid #232a35; padding-top:10px;">
                        ${userDevices.length > 0 ? userDevices.map(d => `
                            <div class="stat-row">
                                <span>📱 ${d.model || 'Toestel'}</span>
                                <span class="battery">${d.batteryLevel || '?'}% 🔋</span>
                            </div>
                            <div style="font-size:0.75em; color:gray; margin-bottom:10px;">
                                Laatst gezien: ${new Date(d.lastConnected).toLocaleString()}
                            </div>
                        `).join('') : '<p style="font-size:0.8em; color:gray;">Geen apparaten gekoppeld</p>'}
                    </div>

                    <div class="stat-row" style="background:#000; padding:8px; border-radius:6px; margin-top:10px;">
                        <span>Status:</span>
                        <span class="badge" style="color:${isOnline ? '#4caf50' : 'gray'}">
                            ${isOnline ? 'Actief' : 'Offline'}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }
</script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"TimeLimit Dashboard v8 actief op poort {PORT}")
        httpd.serve_forever()