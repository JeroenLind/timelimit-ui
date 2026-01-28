import http.server
import socketserver
import json
import os
from crypto_utils import generate_family_hashes
from api_client import TimeLimitAPI

# Paden binnen de Home Assistant Add-on container
CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json"
HTML_PATH = "/usr/bin/dashboard.html" 

def get_config():
    """Haalt de huidige configuratie op uit de add-on opties."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"server_url": "http://192.168.68.30:8080", "auth_token": ""}

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        config = get_config()
        api = TimeLimitAPI(config['server_url'])

        # Normaliseer het pad (verwijder trailing slash)
        path = self.path.rstrip('/')
        
        # 1. Interne logica: Hashing voor wachtwoorden
        if path == '/generate-hashes':
            try:
                data = json.loads(post_data)
                res = generate_family_hashes(data['password'])
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        # 2. API Proxy: Koppel UI paden aan TimeLimit API endpoints
        routes = {
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/sync': '/sync/pull-status'
        }
        
        target = routes.get(path)
        if target:
            status, body = api.post(target, post_data)
            self._send_raw(status, body)
        else:
            # Als het pad niet in de routes staat, stuur 404
            msg = f"404: Pad '{path}' niet gevonden in backend."
            self._send_raw(404, msg.encode())

    def do_GET(self):
        """Serveert de HTML interface en vervangt de token placeholder."""
        if self.path == '/':
            try:
                config = get_config()
                token = config.get('auth_token', '')
                with open(HTML_PATH, 'r', encoding='utf-8') as f:
                    html = f.read().replace("###TOKEN###", token)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Server Fout: {e}".encode())
        
        elif self.path == '/history':
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f:
                    self._send_raw(200, f.read())
            else:
                self._send_json(200, [])
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, status, data):
        body = json.dumps(data).encode('utf-8')
        self._send_raw(status, body)

    def _send_raw(self, status, body):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    # Voorkomt 'address already in use' fouten bij snelle herstarts
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        print("TimeLimit Control Panel draait op poort 8099")
        httpd.serve_forever()