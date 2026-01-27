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
        # Proxy voor de pull-status request
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        target_url = f"{TIMELIMIT_SERVER_URL}/sync/pull-status"
        
        try:
            req = urllib.request.Request(target_url, data=post_data, 
                                       headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req) as response:
                res_raw = response.read()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(res_raw)
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
    <title>TimeLimit Hybrid Bridge</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: system-ui, sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
        .user-card { background: #1c232d; padding: 15px; border-radius: 8px; border-left: 4px solid #03a9f4; }
        #log { background: #000; color: #00ff00; padding: 10px; height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-top: 20px; border: 1px solid #333; }
        .online-tag { background: #4caf50; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; float: right; }
    </style>
</head>
<body>
    <h2>📱 TimeLimit Hybrid Control</h2>
    
    <div class="card">
        <button onclick="fetchFullStatus()" style="background:#03a9f4; color:white; border:none; padding:10px 20px; border-radius:6px; cursor:pointer;">
            🔄 Vernieuw Data (HTTP Pull)
        </button>
        <span id="socket-status" style="margin-left:15px; font-size:0.9em; color:gray;">WebSocket: Verbinden...</span>
    </div>

    <div class="user-grid" id="user-list">Laden...</div>

    <div id="log"></div>

    <script>
        const logEl = document.getElementById('log');
        let connectedDeviceIds = new Set();

        function addLog(msg, color="#00ff00") {
            const d = document.createElement('div');
            d.style.color = color;
            d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logEl.appendChild(d);
            logEl.scrollTop = logEl.scrollHeight;
        }

        // --- WEBSOCKET LOGICA ---
        const socket = io("###SERVER_URL###", { transports: ['websocket'], path: "/socket.io" });

        socket.on('connect', () => {
            document.getElementById('socket-status').textContent = '● WebSocket: Verbonden';
            document.getElementById('socket-status').style.color = '#4caf50';
            
            // STAP 1: Login met platte string (vlgns server index.ts)
            addLog("📤 WS: devicelogin verzenden...");
            socket.emit('devicelogin', "###TOKEN###", () => {
                addLog("✅ WS: Login geaccepteerd door server (Ack ontvangen!)", "#4caf50");
                fetchFullStatus(); // Eerste data ophalen
            });
        });

        socket.on('connected devices', (devices) => {
            addLog("📩 WS: Online apparaten update: " + JSON.stringify(devices), "#03a9f4");
            connectedDeviceIds = new Set(devices);
            // We hoeven niet de hele UI te refreshen, alleen de status tags
        });

        socket.on('should sync', (data) => {
            addLog("🔔 WS: Server vraagt om sync! (isImportant: " + data.isImportant + ")", "#ff9800");
            fetchFullStatus();
        });

        // --- HTTP PULL LOGICA ---
        async function fetchFullStatus() {
            addLog("📡 HTTP: Status ophalen via pull-status...");
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
                renderUI(data);
            } catch (e) {
                addLog("❌ HTTP Fout: " + e.message, "red");
            }
        }

        function renderUI(data) {
            const users = data.users?.data || [];
            addLog(`🎉 UI: ${users.length} gebruikers geladen.`);
            
            document.getElementById('user-list').innerHTML = users.map(u => `
                <div class="user-card">
                    ${u.name}
                    <small style="display:block; color:gray;">ID: ${u.id}</small>
                </div>
            `).join('');
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Hybrid Bridge actief op poort {PORT}")
        httpd.serve_forever()