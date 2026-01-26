import http.server
import socketserver
import urllib.request
import json
import sys

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
        # We maken de proxy flexibel zodat de JS kan kiezen welk pad hij test
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # Haal het doel-pad uit de headers die we vanuit JS meesturen
        target_path = self.headers.get('X-Target-Path', '/sync/get-family-data')
        target_url = f"{TIMELIMIT_SERVER_URL}{target_path}"
        
        log_to_ha(f"Proxying POST to: {target_url}")
        
        try:
            req = urllib.request.Request(
                target_url,
                data=post_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req) as response:
                res_raw = response.read()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(res_raw)
                log_to_ha(f"✅ Success on {target_path}")
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "404"}).encode())
            log_to_ha(f"❌ Failed on {target_path} (Code {e.code})")

    def get_template_string(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit API Discovery</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0b0e14; color: #e1e1e1; padding: 20px; }
        .card { background: #151921; border-radius: 12px; padding: 20px; border: 1px solid #232a35; margin-bottom: 20px; }
        #log { background: #000; color: #00ff00; padding: 12px; height: 200px; overflow-y: auto; font-family: monospace; border: 1px solid #333; }
        .user-card { background: #1c232d; padding: 12px; border-radius: 8px; border-left: 4px solid #03a9f4; margin-bottom: 8px; }
        button { background: #03a9f4; border: none; color: white; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container" style="max-width:800px; margin:0 auto;">
        <h2>🔍 API Discovery Mode <span id="status" style="color:gray; font-size:0.5em;">OFFLINE</span></h2>
        
        <div class="card">
            <button onclick="startDiscovery()">🚀 Start Discovery Scan</button>
            <p id="scan-status" style="font-size: 0.9em; color: #aaa; margin-top: 10px;">Klik op de knop om de juiste API route te vinden.</p>
        </div>

        <div class="card">
            <h3>👥 Gevonden Familieleden</h3>
            <div id="user-list">Nog geen data...</div>
        </div>

        <h4>Console:</h4>
        <div id="log"></div>
    </div>

    <script>
        const logEl = document.getElementById('log');
        function addLog(msg, color = "#00ff00") {
            const d = document.createElement('div');
            d.style.color = color;
            d.textContent = "[" + new Date().toLocaleTimeString() + "] " + msg;
            logEl.appendChild(d);
            logEl.scrollTop = logEl.scrollHeight;
        }

        const token = localStorage.getItem('tl_device_token') || 'DAPBULbE...'; // Gebruik je eigen token hier

        // Lijst met endpoints om te scannen
        const endpoints = [
            '/sync/get-family-data',
            '/parent/get-family-data',
            '/sync/get-data',
            '/parent/get-data',
            '/sync/all'
        ];

        async function startDiscovery() {
            document.getElementById('scan-status').textContent = "Bezig met scannen van endpoints...";
            addLog("🔎 Start scan op " + endpoints.length + " mogelijke routes...");
            
            for (let path of endpoints) {
                addLog("Testen: " + path + " ...", "#aaa");
                const success = await tryEndpoint(path);
                if (success) {
                    document.getElementById('scan-status').textContent = "✅ Gevonden! Werkende route: " + path;
                    document.getElementById('scan-status').style.color = "#4caf50";
                    break;
                }
            }
        }

        async function tryEndpoint(path) {
            try {
                const res = await fetch("/proxy/sync-data", {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Target-Path': path 
                    },
                    body: JSON.stringify({ deviceAuthToken: token })
                });
                
                if (res.ok) {
                    const json = await res.json();
                    const users = json.data?.users?.data || json.data?.users || [];
                    if (users.length > 0) {
                        renderUsers(users);
                        addLog("🎯 SUCCESS op " + path, "#4caf50");
                        return true;
                    }
                }
            } catch (e) {}
            return false;
        }

        function renderUsers(users) {
            document.getElementById('user-list').innerHTML = users.map(u => 
                `<div class="user-card"><b>${u.name}</b> (ID: ${u.id})</div>`
            ).join('');
        }

        // Socket voor live status
        const socket = io("###SERVER_URL###", { transports: ['websocket'], path: "/socket.io" });
        socket.on('connect', () => {
            document.getElementById('status').textContent = "● ONLINE";
            document.getElementById('status').style.color = "#4caf50";
            addLog("✅ WebSocket verbonden.");
        });
    </script>
</body>
</html>"""

if __name__ == "__main__":
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        pass

    log_to_ha("Discovery Server gestart op poort 8099")
    with ThreadedHTTPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()