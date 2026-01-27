import http.server
import socketserver
import urllib.request
import json
import os
import ssl

# --- HOME ASSISTANT INTEGRATIE ---
CONFIG_PATH = "/data/options.json"

def get_config():
    """Leest de actuele instellingen uit het HA configuratie tabje."""
    defaults = {
        "server_url": "http://192.168.68.30:8080",
        "auth_token": "DAPBULbE3Uw4BLjRknOFzl50pV2QRZoY"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**defaults, **json.load(f)}
        except Exception as e:
            print(f"Fout bij lezen van HA opties: {e}")
    return defaults

# Schakel SSL verificatie uit voor lokale servers met self-signed certs
ssl_context = ssl._create_unverified_context()

class TimeLimitProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        config = get_config()
        # Zorg dat er nooit een dubbele slash ontstaat
        target_base = config["server_url"].strip().rstrip("/")
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # Consistentie met je werkende v6 screenshot: gebruik /sync/pull-status
        target_path = self.path if self.path != "/" else "/sync/pull-status"
        target_url = f"{target_base}{target_path}"
        
        try:
            req = urllib.request.Request(
                target_url,
                data=post_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, context=ssl_context) as response:
                status_code = response.getcode()
                response_data = response.read()
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response_data)
        except urllib.error.HTTPError as e:
            # Als de server een fout geeft (bijv 401), stuur de exacte body terug naar de UI
            error_body = e.read().decode('utf-8', errors='ignore')
            self.send_response(e.code)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Server Error", "detail": error_body, "code": e.code}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self):
        """Serveert de dashboard HTML en injecteert de huidige HA configuratie."""
        config = get_config()
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        html = self.get_template().replace("###SERVER_URL###", config["server_url"])
        html = html.replace("###TOKEN###", config["auth_token"])
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return """
<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TimeLimit UI</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root { --bg: #111111; --card: #1c1c1c; --accent: #03a9f4; --text: #e0e0e0; --border: #333; }
        body { font-family: 'Roboto', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; }
        header { background: var(--card); padding: 15px 25px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .main { display: grid; grid-template-columns: 1fr 400px; flex: 1; overflow: hidden; }
        .view { padding: 20px; overflow-y: auto; }
        .inspector { background: #080808; border-left: 1px solid var(--border); display: flex; flex-direction: column; }
        #json-view { flex: 1; padding: 15px; font-family: 'Fira Code', monospace; font-size: 11px; color: #a5d6a7; overflow-y: auto; white-space: pre-wrap; }
        .card { background: var(--card); border-radius: 8px; border: 1px solid var(--border); padding: 15px; margin-bottom: 15px; }
        .online-status { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .btn { background: var(--accent); color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; }
        .tag { background: #333; font-size: 11px; padding: 2px 6px; border-radius: 4px; color: #bbb; }
    </style>
</head>
<body>
    <header>
        <div>
            <h2 style="margin:0;">TimeLimit <span style="color:var(--accent);">Dashboard</span></h2>
            <small style="color:gray;">Server: ###SERVER_URL###</small>
        </div>
        <div id="ws-badge" class="tag">WebSocket: Verbinden...</div>
    </header>

    <div class="main">
        <div class="view">
            <div id="setup-msg" class="card" style="display:none; border-color: orange;">
                <strong>Geen Token!</strong> Voer je deviceAuthToken in bij de Add-on configuratie.
            </div>
            <div id="user-list">Laden van gegevens...</div>
        </div>
        <div class="inspector">
            <div style="padding: 10px; border-bottom: 1px solid #222; font-size: 12px; font-weight: bold;">RAW JSON INSPECTOR</div>
            <div id="json-view">{}</div>
        </div>
    </div>

    <script>
        const SERVER_URL = "###SERVER_URL###";
        const AUTH_TOKEN = "###TOKEN###";
        let onlineDevices = new Set();

        if (!AUTH_TOKEN || AUTH_TOKEN === "test") {
            document.getElementById('setup-msg').style.display = 'block';
        }

        async function fetchStatus() {
            if (!AUTH_TOKEN) return;
            try {
                const res = await fetch("/", {
                    method: 'POST',
                    body: JSON.stringify({
                        deviceAuthToken: AUTH_TOKEN,
                        status: { devices: "", apps: {}, categories: {}, users: "", clientLevel: 2 }
                    })
                });
                const data = await res.json();
                document.getElementById('json-view').textContent = JSON.stringify(data, null, 2);
                render(data);
            } catch (e) {
                document.getElementById('json-view').textContent = "FOUT: " + e.message;
            }
        }

        function render(data) {
            const users = data.users?.data || [];
            const container = document.getElementById('user-list');
            if (users.length === 0) {
                container.innerHTML = "<p>Geen gebruikers gevonden op deze server.</p>";
                return;
            }
            container.innerHTML = users.map(u => `
                <div class="card">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>${u.name}</strong>
                        <span class="tag">${u.type}</span>
                    </div>
                    <div style="margin-top:10px; font-size:13px; color:#888;">ID: ${u.id}</div>
                </div>
            `).join('');
        }

        // WebSocket voor live updates
        if (AUTH_TOKEN && AUTH_TOKEN !== "test") {
            const socket = io(SERVER_URL, { transports: ['websocket'], path: "/socket.io" });
            
            socket.on('connect', () => {
                document.getElementById('ws-badge').textContent = "WebSocket: Online";
                document.getElementById('ws-badge').style.color = "#4caf50";
                socket.emit('devicelogin', AUTH_TOKEN, () => fetchStatus());
            });

            socket.on('connected devices', (devices) => {
                onlineDevices = new Set(devices);
                fetchStatus();
            });

            socket.on('should sync', () => fetchStatus());

            socket.on('disconnect', () => {
                document.getElementById('ws-badge').textContent = "WebSocket: Offline";
                document.getElementById('ws-badge').style.color = "#f44336";
            });
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    PORT = 8099
    with socketserver.TCPServer(("", PORT), TimeLimitProxyHandler) as httpd:
        print(f"TimeLimit UI Server actief op poort {PORT}")
        httpd.serve_forever()