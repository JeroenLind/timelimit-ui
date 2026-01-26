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
    <title>TimeLimit Deep Debug</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; }
        .card { background: #1a1a1a; border-radius: 10px; padding: 20px; margin-top: 20px; border: 1px solid #333; }
        #log { background: #000; color: #00ff00; padding: 15px; height: 350px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; border: 1px solid #444; margin-top: 10px; }
        .status-online { color: #4caf50; font-weight: bold; }
        .status-offline { color: #f44336; font-weight: bold; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px; }
        .debug-msg { border-bottom: 1px solid #222; padding: 2px 0; }
        .event-tag { color: #ff9800; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🕵️ TimeLimit API Tracer</h2>
            <div id="status" class="status-offline">● DISCONNECTED</div>
        </div>

        <div class="card">
            <button onclick="sendProbe('get-state')">Probe: get-state</button>
            <button onclick="sendProbe('refresh')">Probe: refresh</button>
            <button onclick="sendProbe('get-users')">Probe: get-users</button>
            <button onclick="clearToken()" style="background:#444;">Token Reset</button>
        </div>

        <div class="card">
            <h3 style="margin-top:0;">Systeem Console (Deep Debug Mode)</h3>
            <div id="log"></div>
        </div>
        
        <div id="user-display" class="card" style="display:none;">
            <h3>Gevonden Gebruikers:</h3>
            <div id="user-list"></div>
        </div>
    </div>

    <script>
        const serverUrl = "###SERVER_URL###";
        const token = localStorage.getItem('tl_device_token');
        const logEl = document.getElementById('log');
        let socket;

        function addLog(msg, isEvent = false) {
            const entry = document.createElement('div');
            entry.className = 'debug-msg';
            const time = new Date().toLocaleTimeString();
            if (isEvent) {
                entry.innerHTML = `[${time}] <span class="event-tag">${msg}</span>`;
            } else {
                entry.textContent = `[${time}] ${msg}`;
            }
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }

        if (!token) {
            const inputToken = prompt("Geen token gevonden. Voer je deviceAuthToken in:");
            if (inputToken) {
                localStorage.setItem('tl_device_token', inputToken);
                location.reload();
            }
        } else {
            initWebSocket(token);
        }

        function initWebSocket(authToken) {
            addLog("Initialiseren WebSocket met token: " + authToken.substring(0, 8) + "...");
            
            socket = io(serverUrl, { 
                transports: ['websocket'],
                query: { deviceAuthToken: authToken } 
            });

            socket.on('connect', () => {
                document.getElementById('status').className = 'status-online';
                document.getElementById('status').textContent = '● ONLINE';
                addLog("✅ CONNECTED! Socket ID: " + socket.id);
                
                // We proberen direct een aantal mogelijke triggers
                addLog("Verzenden van initiële probes...");
                socket.emit('get-state');
                socket.emit('get-family-data');
            });

            // DEEP DEBUG CATCH-ALL
            socket.onAny((event, ...args) => {
                addLog(`ONTAVNGEN EVENT: ${event}`, true);
                addLog(`DATA: ${JSON.stringify(args)}`);

                // Automatische herkenning van de gebruikerslijst
                const raw = JSON.stringify(args);
                if (raw.includes('"name":') && raw.includes('"id":')) {
                    addLog("🎯 DATA MATCH! Gebruikersgegevens herkend in stream.");
                    document.getElementById('user-display').style.display = 'block';
                    renderUsers(args[0]?.users?.data || args[0]?.users || args[0]);
                }
            });

            socket.on('connect_error', (err) => {
                addLog("❌ VERBINDINGSFOUT: " + err.message);
            });

            socket.on('disconnect', () => {
                document.getElementById('status').className = 'status-offline';
                document.getElementById('status').textContent = '● DISCONNECTED';
            });
        }

        function sendProbe(eventName) {
            if (socket && socket.connected) {
                addLog(`Verzenden probe: ${eventName}...`);
                socket.emit(eventName, { timestamp: Date.now() });
            } else {
                addLog("⚠️ Kan niet verzenden: niet verbonden.");
            }
        }

        function renderUsers(users) {
            const list = document.getElementById('user-list');
            if (!Array.isArray(users)) return;
            list.innerHTML = users.map(u => `
                <div style="background:#222; padding:10px; margin:5px; border-radius:5px; border-left:3px solid #03a9f4;">
                    <b>${u.name}</b> (ID: ${u.id}) - Type: ${u.type}
                </div>
            `).join('');
        }

        function clearToken() {
            localStorage.removeItem('tl_device_token');
            location.reload();
        }
    </script>
</body>
</html>
""".replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Deep Debug UI op poort {PORT}")
        httpd.serve_forever()