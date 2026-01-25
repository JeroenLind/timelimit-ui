import http.server
import socketserver
import os
import json

# Poort moet overeenkomen met ingress_port in config.yaml
PORT = 8099
# Het IP waar de browser van de gebruiker de server kan vinden
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

def get_server_password():
    """Haalt het wachtwoord op uit de HA Add-on configuratie."""
    try:
        if os.path.exists("/data/options.json"):
            with open("/data/options.json", "r") as f:
                options = json.load(f)
                return options.get("server_password", "")
    except Exception as e:
        print(f"Kon opties niet laden: {e}")
    return ""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        password = get_server_password()
        html = self.get_template(password)
        self.wfile.write(html.encode("utf-8"))

    def get_template(self, password):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit UI</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
               background-color: #111; color: #eee; padding: 20px; margin: 0; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-top: 20px; }
        .card { background: #222; border-radius: 12px; padding: 20px; text-align: center; border-top: 4px solid #03a9f4; }
        #log { background: #000; color: #0f0; padding: 10px; height: 120px; overflow-y: auto; font-size: 11px; margin-top: 30px; border-radius: 8px; border: 1px solid #333; }
        .status-dot { height: 10px; width: 10px; background-color: #f44336; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .online { background-color: #4caf50; }
    </style>
</head>
<body>
    <div class="header">
        <h2>TimeLimit Dashboard</h2>
        <div><span id="dot" class="status-dot"></span> <span id="status">Verbinden...</span></div>
    </div>
    
    <div id="users" class="grid">
        <p>Data ophalen...</p>
    </div>

    <h4>WebSocket Debugger:</h4>
    <div id="log"></div>

    <script>
        const serverUrl = "###SERVER_URL###";
        const password = "###PASSWORD###";
        const usersEl = document.getElementById('users');
        const statusText = document.getElementById('status');
        const dot = document.getElementById('dot');
        const logEl = document.getElementById('log');

        function addLog(msg) {
            const entry = document.createElement('div');
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }

        const socket = io(serverUrl, { transports: ['websocket'] });

        socket.on('connect', () => {
            statusText.textContent = "Verbonden";
            dot.classList.add('online');
            addLog("Verbonden met server. Authenticeren...");
            
            // Stuur authenticatie met het wachtwoord uit de add-on opties
            socket.emit('auth', { password: password });
        });

        socket.onAny((event, data) => {
            addLog(`Event: ${event}`);
            if (event === 'state' || event === 'users') {
                render(data);
            }
        });

        socket.on('connect_error', (err) => {
            statusText.textContent = "Verbindingsfout";
            dot.classList.remove('online');
            addLog("FOUT: " + err.message);
        });

        function render(data) {
            const users = data.users || (Array.isArray(data) ? data : []);
            if (users.length === 0) {
                usersEl.innerHTML = "<p>Geen gebruikers gevonden in de 'state'.</p>";
                return;
            }
            usersEl.innerHTML = users.map(u => `
                <div class="card">
                    <div style="font-size: 1.2em; font-weight: bold; margin-bottom: 5px;">${u.name}</div>
                    <div style="color: #888; font-size: 0.9em;">ID: ${u.id}</div>
                </div>
            `).join('');
        }
    </script>
</body>
</html>
""".replace("###SERVER_URL###", TIMELIMIT_SERVER_URL).replace("###PASSWORD###", password)

if __name__ == "__main__":
    print(f"Timelimit UI gestart op poort {PORT}")
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()