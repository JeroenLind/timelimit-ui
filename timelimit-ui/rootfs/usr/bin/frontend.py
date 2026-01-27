import http.server
import socketserver

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

    def get_template_string(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Android Bridge</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        #console { background: #000; color: #00ff00; padding: 12px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 11px; border: 1px solid #333; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .user-card { background: #1c232d; padding: 15px; border-radius: 8px; border-top: 4px solid #03a9f4; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .status-online { color: #4caf50; font-size: 0.8em; }
    </style>
</head>
<body>
    <div style="max-width:900px; margin:0 auto;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2>📱 TimeLimit Android Bridge</h2>
            <div id="socket-status">● Verbinding maken...</div>
        </div>

        <div class="card">
            <button onclick="requestRefresh()">🔄 Forceer Refresh</button>
            <button onclick="requestState()" style="background:#444;">📡 Vraag State</button>
        </div>

        <div class="card">
            <h3>👥 Familie Overzicht</h3>
            <div id="user-list" class="user-grid">Wachten op 'state' event...</div>
        </div>

        <h4>🛠️ Raw WebSocket Verkeer:</h4>
        <div id="console"></div>
    </div>

    <script>
        const consoleEl = document.getElementById('console');
        const socket = io("###SERVER_URL###", { transports: ['websocket'], path: "/socket.io" });

        function log(msg, color="#00ff00") {
            const d = document.createElement('div');
            d.style.color = color;
            d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            consoleEl.appendChild(d);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }

        socket.on('connect', () => {
            document.getElementById('socket-status').className = 'status-online';
            document.getElementById('socket-status').textContent = '● VERBONDEN';
            log("✅ Socket verbonden. Versturen 'devicelogin'...");
            
            socket.emit('devicelogin', "###TOKEN###", (ack) => {
                log("🔑 Login geaccepteerd! Server luistert nu naar commando's.", "#4caf50");
                requestState();
            });
        });

        // De kern: luister naar alle inkomende data
        socket.onAny((event, data) => {
            log(`📩 Ontvangen [${event}]: ` + JSON.stringify(data).substring(0, 100) + "...", "#03a9f4");
            
            if (event === 'state' || event === 'user-update') {
                updateUI(data);
            }
        });

        function requestRefresh() {
            log("📤 Versturen 'refresh'...");
            socket.emit('refresh', {});
        }

        function requestState() {
            log("📤 Versturen 'get-state'...");
            socket.emit('get-state', {});
        }

        function updateUI(payload) {
            // Android-app structuur: data.users of payload.users
            const users = payload.users?.data || payload.users || [];
            if (users.length > 0) {
                document.getElementById('user-list').innerHTML = users.map(u => `
                    <div class="user-card">
                        <b>${u.name}</b><br>
                        <small>ID: ${u.id}</small><br>
                        <div style="margin-top:10px; color:#aaa; font-size:0.8em;">Systeem: ${u.type}</div>
                    </div>
                `).join('');
            }
        }

        socket.on('disconnect', () => {
            document.getElementById('socket-status').style.color = 'red';
            document.getElementById('socket-status').textContent = '● DISCONNECTED';
            log("❌ Verbinding verbroken.", "red");
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"TimeLimit Bridge v3 actief op poort {PORT}")
        httpd.serve_forever()