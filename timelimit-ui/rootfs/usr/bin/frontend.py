import http.server
import socketserver
import urllib.request
import json

PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serveer de HTML pagina
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template_string().replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        # Proxy functie voor de API aanroepen om CORS te omzeilen
        if self.path == "/proxy/get-family-data":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Stuur het verzoek door naar de echte TimeLimit server
                req = urllib.request.Request(
                    f"{TIMELIMIT_SERVER_URL}/parent/get-family-data",
                    data=post_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req) as response:
                    res_data = response.read()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(res_data)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

    def get_template_string(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Tracer</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { background: #1a1a1a; border-radius: 10px; padding: 20px; border: 1px solid #333; margin-bottom: 20px; }
        #log { background: #000; color: #00ff00; padding: 15px; height: 180px; overflow-y: auto; font-family: monospace; border-radius: 8px; border: 1px solid #333; }
        .user-card { background: #252525; padding: 15px; border-radius: 8px; border-left: 4px solid #03a9f4; margin-bottom: 10px; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .status { float: right; font-size: 0.8em; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>TimeLimit Tracer <span id="conn-status" class="status" style="color:red;">● Off</span></h2>
        
        <div id="setup-ui" class="card hidden">
            <input type="text" id="token-input" placeholder="Voer deviceAuthToken in..." style="width:70%; padding:10px;">
            <button onclick="saveToken()">Starten</button>
        </div>

        <div id="main-ui" class="hidden">
            <button onclick="fetchData()">🔄 Handmatige Sync</button>
            <div class="card" style="margin-top:15px;">
                <h3>Familie Leden</h3>
                <div id="user-list">Wachten op data...</div>
            </div>
        </div>

        <h4>Systeem Log:</h4>
        <div id="log"></div>
    </div>

    <script>
        const socketUrl = "###SERVER_URL###";
        const logEl = document.getElementById('log');

        function addLog(msg, color = "#00ff00") {
            const entry = document.createElement('div');
            entry.style.color = color;
            entry.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }

        const token = localStorage.getItem('tl_device_token');
        if (!token) {
            document.getElementById('setup-ui').classList.remove('hidden');
        } else {
            document.getElementById('main-ui').classList.remove('hidden');
            initWebSocket(token);
        }

        function saveToken() {
            const val = document.getElementById('token-input').value.trim();
            if (val) { localStorage.setItem('tl_device_token', val); location.reload(); }
        }

        function initWebSocket(authToken) {
            const socket = io(socketUrl, { transports: ['websocket'], path: "/socket.io" });

            socket.on('connect', () => {
                document.getElementById('conn-status').style.color = '#4caf50';
                document.getElementById('conn-status').textContent = '● Online';
                addLog("✅ Verbonden. Inloggen...");
                socket.emit('devicelogin', authToken, () => {
                    addLog("🚀 Login bevestigd!");
                    fetchData();
                });
            });

            socket.on('should sync', () => {
                addLog("🔔 Server vraagt om sync...");
                fetchData();
            });
        }

        async function fetchData() {
            addLog("📡 Data ophalen via Proxy...");
            try {
                // We roepen onze EIGEN python server aan op /proxy/...
                const response = await fetch("/proxy/get-family-data", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ deviceAuthToken: localStorage.getItem('tl_device_token') })
                });
                const result = await response.json();
                
                if (result.data && result.data.users) {
                    const users = result.data.users.data || result.data.users;
                    document.getElementById('user-list').innerHTML = users.map(u => 
                        '<div class="user-card"><b>' + u.name + '</b> (ID: ' + u.id + ')</div>'
                    ).join('');
                    addLog("✅ Gebruikers geladen.");
                }
            } catch (err) {
                addLog("❌ Proxy Fout: " + err.message, "red");
            }
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    # Gebruik Threading om meerdere verzoeken (HTML + Proxy) tegelijk te kunnen afhandelen
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        pass

    with ThreadedHTTPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Proxy-Frontend actief op poort {PORT}")
        httpd.serve_forever()