import http.server
import socketserver
import urllib.request
import json
import sys

# Configuratie
PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

def log_to_ha(message):
    print(f"[TimeLimit-Bridge] {message}", file=sys.stdout, flush=True)

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template_string().replace("###SERVER_URL###", TIMELIMIT_SERVER_URL)
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        if self.path == "/proxy/sync-data":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Volgens de router-code is /sync/get-family-data de meest logische plek
            target_url = f"{TIMELIMIT_SERVER_URL}/sync/get-family-data"
            
            log_to_ha(f"Sync poging gestart naar: {target_url}")
            
            try:
                req = urllib.request.Request(
                    target_url,
                    data=post_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req) as response:
                    res_raw = response.read()
                    log_to_ha(f"✅ Server antwoord ontvangen ({len(res_raw)} bytes)")
                    
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(res_raw)
                    
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode('utf-8')
                log_to_ha(f"❌ Server Fout ({e.code}): {err_msg}")
                # Als /sync niet werkt, probeer /parent als fallback
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(json.dumps({"error": err_msg, "code": e.code}).encode())
            except Exception as e:
                log_to_ha(f"⚠️ Proxy Exception: {str(e)}")
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
        body { font-family: sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        #log { background: #000; color: #00ff00; padding: 12px; height: 180px; overflow-y: auto; font-family: monospace; font-size: 11px; border-radius: 6px; border: 1px solid #333; }
        .user-card { background: #1c232d; padding: 15px; border-radius: 8px; border-left: 4px solid #03a9f4; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .badge { background: #232a35; padding: 4px 8px; border-radius: 4px; font-size: 0.75em; color: #03a9f4; border: 1px solid #03a9f4; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #03a9f4;">TimeLimit Tracer <span id="status-text" style="font-size: 0.5em; color: gray;">● OFFLINE</span></h2>
        
        <div id="setup-ui" class="card hidden">
            <h3>Geen token gevonden</h3>
            <input type="text" id="token-input" placeholder="Device Auth Token..." style="width:70%; padding:10px; background:#0b0e14; border:1px solid #333; color:white;">
            <button onclick="saveToken()">Verbinden</button>
        </div>

        <div id="main-ui" class="hidden">
            <button onclick="fetchData()">🔄 Nu Synchroniseren</button>
            <div class="card" style="margin-top:20px;">
                <h3 style="margin-top:0;">Familieleden</h3>
                <div id="user-list">Data ophalen uit TimeLimit...</div>
            </div>
        </div>

        <h4>HA System Log:</h4>
        <div id="log"></div>
    </div>

    <script>
        const socketUrl = "###SERVER_URL###";
        const logEl = document.getElementById('log');

        function addLog(msg, color = "#00ff00") {
            const d = document.createElement('div');
            d.style.color = color;
            d.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg;
            logEl.appendChild(d);
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
            const v = document.getElementById('token-input').value.trim();
            if (v) { localStorage.setItem('tl_device_token', v); location.reload(); }
        }

        function initWebSocket(authToken) {
            const socket = io(socketUrl, { transports: ['websocket'], path: "/socket.io" });

            socket.on('connect', () => {
                document.getElementById('status-text').style.color = '#4caf50';
                document.getElementById('status-text').textContent = '● ONLINE';
                addLog("✅ WebSocket verbonden.");
                socket.emit('devicelogin', authToken, () => {
                    addLog("🚀 Ingelogd op server.");
                    fetchData();
                });
            });

            socket.on('should sync', () => {
                addLog("🔔 Server verzoek: synchroniseren...");
                fetchData();
            });
        }

        async function fetchData() {
            addLog("📡 Sync verzoek versturen via proxy...");
            try {
                const res = await fetch("/proxy/sync-data", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ deviceAuthToken: localStorage.getItem('tl_device_token') })
                });
                
                const raw = await res.text();
                try {
                    const json = JSON.parse(raw);
                    // De data structuur van TimeLimit: json.data.users.data
                    const users = json.data?.users?.data || json.data?.users || [];
                    
                    if (users.length > 0) {
                        document.getElementById('user-list').innerHTML = users.map(u => 
                            `<div class="user-card">
                                <div><b>${u.name}</b><br><small style="color:gray;">ID: ${u.id}</small></div>
                                <div class="badge">${u.type}</div>
                            </div>`
                        ).join('');
                        addLog("✅ Data succesvol bijgewerkt.");
                    } else {
                        addLog("⚠️ Geen gebruikers in antwoord: " + raw.substring(0, 40), "orange");
                    }
                } catch(e) {
                    addLog("❌ API Error: " + raw, "#f44336");
                }
            } catch(e) {
                addLog("❌ Netwerkfout: " + e.message, "#f44336");
            }
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        pass

    log_to_ha("TimeLimit Bridge gestart op poort 8099")
    with ThreadedHTTPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()