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
    <title>TimeLimit Tracer v6</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: 'Consolas', monospace; background: #0b0e14; color: #00ff00; padding: 20px; }
        .card { background: #151921; border-radius: 8px; padding: 15px; border: 1px solid #333; margin-bottom: 20px; }
        #console { background: #000; padding: 10px; height: 400px; overflow-y: auto; border: 1px solid #444; font-size: 12px; }
        .out { color: #888; }
        .in { color: #03a9f4; }
        .success { color: #4caf50; font-weight: bold; }
        .err { color: #ff5252; }
        .user-card { border-left: 4px solid #03a9f4; background: #1c232d; padding: 10px; margin: 5px 0; }
    </style>
</head>
<body>
    <h3>🕵️ Protocol Matcher v6</h3>
    
    <div class="card" id="user-list">Wachten op login resultaat...</div>

    <div id="console"></div>

    <script>
        const consoleEl = document.getElementById('console');
        const socket = io("###SERVER_URL###", { transports: ['websocket'], path: "/socket.io" });

        function log(msg, type='info') {
            const d = document.createElement('div');
            d.className = type;
            d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            consoleEl.appendChild(d);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }

        socket.on('connect', () => {
            log("CONNECTED: " + socket.id, "success");
            
            // PAYLOAD: De server verwacht een object, geen string!
            const loginObj = { 
                deviceAuthToken: "###TOKEN###",
                clientLevel: 2 
            };
            
            log("OUT -> devicelogin | " + JSON.stringify(loginObj), "out");
            socket.emit('devicelogin', loginObj); 
        });

        // LUISTEREN NAAR HET RESULTAAT (Specifiek voor deze server versie)
        socket.on('login-result', (data) => {
            log("IN  <- login-result | " + JSON.stringify(data), "in");
            if (data.success || data.familyId) {
                log("🚀 LOGIN SUCCESVOL! Room joined.", "success");
                // Nu de sync aanvragen
                log("OUT -> sync", "out");
                socket.emit('sync', { clientLevel: 2 });
            } else {
                log("❌ LOGIN GEWEIGERD: " + JSON.stringify(data), "err");
            }
        });

        // ALGEMENE STATE LISTENER
        socket.on('state', (data) => {
            log("IN  <- state | Data ontvangen!", "success");
            renderUsers(data);
        });

        socket.onAny((event, ...args) => {
            if (event !== 'login-result' && event !== 'state') {
                log(`IN  <- ${event} | ` + JSON.stringify(args), "in");
            }
        });

        function renderUsers(payload) {
            const users = payload.users?.data || payload.users || [];
            document.getElementById('user-list').innerHTML = users.map(u => 
                `<div class="user-card"><b>${u.name}</b> (ID: ${u.id})</div>`
            ).join('');
        }

        socket.on('connect_error', (err) => log("ERROR: " + err.message, "err"));
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Tracer v6 actief op poort {PORT}")
        httpd.serve_forever()