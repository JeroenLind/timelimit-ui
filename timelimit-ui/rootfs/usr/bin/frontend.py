import http.server
import socketserver
import urllib.request
import json
import traceback

PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template_string().replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/proxy/get-family-data":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Proxy naar de echte TimeLimit server
                req = urllib.request.Request(
                    f"{TIMELIMIT_SERVER_URL}/parent/get-family-data",
                    data=post_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req) as response:
                    res_raw = response.read()
                    
                    # We sturen het antwoord direct door naar de browser
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(res_raw)
                    
            except urllib.error.HTTPError as e:
                # Vang specifieke server-fouten op (bijv. 401 Unauthorized)
                error_body = e.read().decode('utf-8')
                print(f"Server Error Body: {error_body}")
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(json.dumps({"error": error_body, "status": e.code}).encode())
            except Exception as e:
                print(f"Proxy Exception: {str(e)}")
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
        #log { background: #000; color: #00ff00; padding: 10px; height: 250px; overflow-y: auto; font-family: monospace; font-size: 12px; border: 1px solid #333; }
        .user-card { background: #252525; padding: 12px; border-radius: 6px; border-left: 4px solid #03a9f4; margin-bottom: 8px; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 18px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .status { float: right; font-weight: bold; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>TimeLimit Tracer <span id="conn-status" class="status" style="color:#f44336;">● Offline</span></h2>
        
        <div id="setup-ui" class="card hidden">
            <input type="text" id="token-input" placeholder="Voer deviceAuthToken in..." style="width:70%; padding:10px; background:#222; color:#fff; border:1px solid #444;">
            <button onclick="saveToken()">Verbinden</button>
        </div>

        <div id="main-ui" class="hidden">
            <button onclick="fetchData()">🔄 Handmatige Sync</button>
            <div class="card" style="margin-top:15px;">
                <h3>Familie Leden</h3>
                <div id="user-list">Geen data geladen.</div>
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
                addLog("✅ Verbonden met socket.");
                socket.emit('devicelogin', authToken, () => {
                    addLog("🚀 Login bevestigd!");
                    fetchData();
                });
            });

            socket.on('should sync', () => {
                addLog("🔔 Sync signaal van server ontvangen.");
                fetchData();
            });
        }

        async function fetchData() {
            addLog("📡 Data opvragen via Proxy...");
            try {
                const response = await fetch("/proxy/get-family-data", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ deviceAuthToken: localStorage.getItem('tl_device_token') })
                });
                
                const text = await response.text();
                
                try {
                    const result = JSON.parse(text);
                    if (result.data && result.data.users) {
                        const users = result.data.users.data || result.data.users;
                        document.getElementById('user-list').innerHTML = users.map(u => 
                            '<div class="user-card"><b>' + u.name + '</b> (ID: ' + u.id + ')</div>'
                        ).join('');
                        addLog("✅ Gebruikers succesvol geladen.");
                    } else if (result.error) {
                        addLog("❌ Server fout: " + result.error, "#f44336");
                    }
                } catch (e) {
                    addLog("⚠️ Server antwoordde geen JSON: " + text.substring(0, 50), "orange");
                }
            } catch (err) {
                addLog("❌ Netwerk fout: " + err.message, "#f44336");
            }
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        pass

    with ThreadedHTTPServer(("", PORT), DashboardHandler) as httpd:
        print(f"Tracer Proxy actief op poort {PORT}")
        httpd.serve_forever()