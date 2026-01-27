import http.server
import socketserver
import urllib.request
import json
import os
import ssl

# --- CONFIGURATIE ---
CONFIG_PATH = "/data/options.json"

def get_ha_config():
    defaults = {
        "server_url": "http://192.168.68.30:8080",
        "auth_token": "DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**defaults, **json.load(f)}
        except Exception:
            pass
    return defaults

ssl_context = ssl._create_unverified_context()

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        config = get_ha_config()
        target_base = config["server_url"].strip().rstrip("/")
        
        # Haal de data op die de frontend stuurt
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # CRUCIAL FIX: We sturen het nu ALTIJD naar /sync/pull-status 
        target_url = f"{target_base}/sync/pull-status"
        
        try:
            req = urllib.request.Request(
                target_url,
                data=post_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, context=ssl_context) as response:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"{e.code}: {e.reason}".encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):
        config = get_ha_config()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        html = self.get_template()
        html = html.replace("###SERVER_URL###", config["server_url"])
        html = html.replace("###TOKEN###", config["auth_token"])
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Dashboard</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: sans-serif; background: #111; color: #eee; margin: 0; display: flex; flex-direction: column; height: 100vh; }
        header { padding: 10px 20px; background: #222; border-bottom: 1px solid #333; display: flex; justify-content: space-between; }
        .container { display: grid; grid-template-columns: 1fr 450px; flex: 1; overflow: hidden; }
        .view { padding: 20px; overflow-y: auto; }
        .inspector { background: #050505; border-left: 1px solid #333; display: flex; flex-direction: column; }
        #raw-log { flex: 1; padding: 15px; font-family: monospace; font-size: 11px; color: #0f0; overflow-y: auto; white-space: pre-wrap; }
        .card { background: #1a1a1a; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #03a9f4; }
    </style>
</head>
<body>
<header>
    <div><strong>TimeLimit Dashboard</strong> | <small>###SERVER_URL###</small></div>
    <div id="status">Verbinden...</div>
</header>
<div class="container">
    <div class="view" id="main-view">Laden...</div>
    <div class="inspector">
        <div style="padding:10px; font-size:12px; border-bottom:1px solid #222;">RAW JSON INSPECTOR</div>
        <div id="raw-log">Geen data ontvangen.</div>
    </div>
</div>

<script>
    const TOKEN = "###TOKEN###";
    const URL = "###SERVER_URL###";

    async function pullData() {
        try {
            const res = await fetch("/", {
                method: 'POST',
                body: JSON.stringify({
                    deviceAuthToken: TOKEN,
                    status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 2 }
                })
            });
            const text = await res.text();
            try {
                const data = JSON.parse(text);
                document.getElementById('raw-log').textContent = JSON.stringify(data, null, 2);
                render(data);
            } catch(e) {
                document.getElementById('raw-log').textContent = "FOUT BIJ PARSEN: " + e.message + "\\n\\nRAW RESPONSE:\\n" + text;
            }
        } catch(e) {
            document.getElementById('raw-log').textContent = "NETWERK FOUT: " + e.message;
        }
    }

    function render(data) {
        const users = data.users?.data || [];
        document.getElementById('main-view').innerHTML = users.length ? users.map(u => `
            <div class="card">
                <strong>${u.name}</strong><br>
                <small style="color:gray;">ID: ${u.id}</small>
            </div>
        `).join('') : "Geen gebruikers gevonden.";
    }

    const socket = io(URL, { transports: ['websocket'], path: "/socket.io" });
    socket.on('connect', () => {
        document.getElementById('status').textContent = "Live: Verbonden";
        socket.emit('devicelogin', TOKEN, () => pullData());
    });
    socket.on('should sync', () => pullData());
</script>
</body>
</html>
"""

if __name__ == "__main__":
    # Gebruik poort 8099 zoals in je Docker/config setup
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()