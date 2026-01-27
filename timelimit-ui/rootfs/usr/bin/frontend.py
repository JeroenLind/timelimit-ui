import http.server
import socketserver

# Configuratie
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
    <title>TimeLimit Tracer v4 - Discovery</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; margin: 0; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #232a35; padding-bottom: 15px; margin-bottom: 20px; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        #console { background: #000; color: #00ff00; padding: 12px; height: 300px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 11px; border: 1px solid #333; border-radius: 6px; }
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .user-card { background: #1c232d; padding: 15px; border-radius: 8px; border-top: 4px solid #03a9f4; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        button { background: #03a9f4; border: none; color: white; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-weight: bold; margin-right: 5px; transition: 0.2s; }
        button:hover { background: #0288d1; }
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .log-orange { color: #ff9800; }
        .log-blue { color: #03a9f4; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 style="margin:0; color:#03a9f4;">TimeLimit Tracer</h1>
                <small style="color:gray;">v4 WebSocket Discovery Mode</small>
            </div>
            <div>
                <span id="dot" class="status-dot" style="background:gray;"></span>
                <span id="status-text">Initialiseren...</span>
            </div>
        </div>

        <div class="card">
            <h3>🛠️ Handmatige Probes</h3>
            <button onclick="sendProbe('sync', {clientLevel: 1})">Probe: sync</button>
            <button onclick="sendProbe('get-state', {})">Probe: get-state</button>
            <button onclick="sendProbe('refresh', {})" style="background:#444;">Probe: refresh</button>
        </div>

        <div class="card">
            <h3>👥 Familie Overzicht</h3>
            <div id="user-list" class="user-grid">Wachten op data-events van server...</div>
        </div>

        <h4>💬 Raw System Log:</h4>
        <div id="console"></div>
    </div>

    <script>
        const consoleEl = document.getElementById('console');
        const socket = io("###SERVER_URL###", { 
            transports: ['websocket'], 
            path: "/socket.io",
            reconnectionAttempts: 5
        });

        function addLog(msg, color="#00ff00", className="") {
            const d = document.createElement('div');
            if (className) d.className = className;
            d.style.color = color;
            d.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg;
            consoleEl.appendChild(d);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }

        socket.on('connect', () => {
            document.getElementById('dot').style.background = '#4caf50';
            document.getElementById('status-text').textContent = 'Verbonden';
            addLog("✅ Socket verbonden. ID: " + socket.id);
            addLog("🔑 Versturen 'devicelogin'...");
            socket.emit('devicelogin', "###TOKEN###", (ack) => {
                addLog("🚀 Login bevestigd! ACK: " + JSON.stringify(ack), "#4caf50");
                runAutoDiscovery();
            });
        });

        socket.onAny((eventName, ...args) => {
            addLog("📩 ONTVANGEN [" + eventName + "]: " + JSON.stringify(args), "#03a9f4", "log-blue");
            const potentialData = args[0]?.data || args[0];
            if (potentialData && (potentialData.users || Array.isArray(potentialData))) {
                updateUI(potentialData);
            }
        });

        function runAutoDiscovery() {
            addLog("🔎 Starten automatische probes...", "#aaa");
            sendProbe('sync', { clientLevel: 1 });
            setTimeout(() => sendProbe('get-state', {}), 1000);
        }

        function sendProbe(name, payload) {
            addLog("📤 Verzend probe: " + name + "...", "#aaa");
            socket.emit(name, payload, (response) => {
                if (response) {
                    addLog("🧡 REPLIEK op [" + name + "]: " + JSON.stringify(response), "#ff9800", "log-orange");
                    if (response.users || response.data) updateUI(response.data || response);
                }
            });
        }

        function updateUI(payload) {
            const users = payload.users?.data || payload.users || (Array.isArray(payload) ? payload : []);
            if (users.length > 0) {
                addLog("🎉 Succes! " + users.length + " gebruikers gevonden.", "#4caf50");
                document.getElementById('user-list').innerHTML = users.map(u => `
                    <div class="user-card">
                        <b>` + (u.name || 'Naamloos') + `</b><br>
                        <small style="color:gray;">ID: ` + u.id + `</small><br>
                        <div style="margin-top:8px; font-size:0.8em;">Type: ` + (u.type || 'Onbekend') + `</div>
                    </div>
                `).join('');
            }
        }

        socket.on('connect_error', (err) => {
            addLog("❌ Verbindingsfout: " + err.message, "red");
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"TimeLimit Tracer v4 gestart op poort {PORT}")
        httpd.serve_forever()