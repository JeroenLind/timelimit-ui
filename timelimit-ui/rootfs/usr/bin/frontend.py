import http.server
import socketserver
import json
import os
from crypto_utils import generate_family_hashes
from api_client import TimeLimitAPI

# Bestandspaden voor HA
CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json"
# Gebruik het volledige pad voor stabiliteit in de container
HTML_PATH = "/usr/bin/dashboard.html" 

def get_config():
    """Haalt de configuratie op. Altijd een dict teruggeven."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f: return json.load(f)
        except: pass
    return {"server_url": "http://192.168.68.30:8080", "auth_token": ""}

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        config = get_config()
        api = TimeLimitAPI(config['server_url'])

        # 1. Hashing actie (Wizard stap 3 voorbereiding)
        if self.path == '/generate-hashes':
            try:
                data = json.loads(post_data)
                res = generate_family_hashes(data['password'])
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            
        # 2. Proxy acties naar de TimeLimit Server
        else:
            routes = {
                '/wizard-step1': '/auth/send-mail-login-code-v2',
                '/wizard-step2': '/auth/sign-in-by-mail-code',
                '/wizard-step3': '/parent/create-family',
                '/sync': '/sync/pull-status'
            }
            
            target = routes.get(self.path)
            if target:
                status, body = api.post(target, post_data)
                self._send_raw(status, body)
            else:
                self._send_json(404, {"error": "Route niet gevonden"})

    def do_GET(self):
        # Serveer de hoofdpagina
        if self.path == '/':
            try:
                config = get_config()
                with open(HTML_PATH, 'r', encoding='utf-8') as f:
                    html = f.read().replace("###TOKEN###", config.get('auth_token', ''))
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"HTML bestand niet gevonden: {e}".encode())

        # Serveer geschiedenis (optioneel, voor de toekomst)
        elif self.path == '/history':
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f: self._send_raw(200, f.read())
            else:
                self._send_json(200, [])
        
        # Voor statische bestanden/icoontjes die de browser soms aanvraagt
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, status, data):
        self._send_raw(status, json.dumps(data).encode())

    def _send_raw(self, status, body):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    # Gebruik Allow Reuse Address om 'Address already in use' fouten bij herstarten te voorkomen
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        print("TimeLimit Control Panel draait op poort 8099")
        httpd.serve_forever()