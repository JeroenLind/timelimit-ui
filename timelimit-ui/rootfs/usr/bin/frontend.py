import http.server
import socketserver
import json
import os
from crypto_utils import generate_family_hashes
from api_client import TimeLimitAPI

# Bestandspaden voor HA
CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json"

def get_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f: return json.load(f)
    return {"server_url": "http://192.168.68.30:8080", "auth_token": ""}

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        config = get_config()
        api = TimeLimitAPI(config['server_url'])

        # 1. Hashing actie
        if self.path == '/generate-hashes':
            pwd = json.loads(post_data)['password']
            res = generate_family_hashes(pwd)
            self._send_json(200, res)
            
        # 2. Proxy acties (Wizard & Sync)
        else:
            routes = {
                '/wizard-step1': '/auth/send-mail-login-code-v2',
                '/wizard-step2': '/auth/sign-in-by-mail-code',
                '/wizard-step3': '/parent/create-family',
                '/sync': '/sync/pull-status'
            }
            status, body = api.post(routes.get(self.path, '/sync/pull-status'), post_data)
            self._send_raw(status, body)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            config = get_config()
            # Lees het losse HTML bestand in
            with open('dashboard.html', 'r', encoding='utf-8') as f:
                html = f.read().replace("###TOKEN###", config.get('auth_token', ''))
                self.wfile.write(html.encode())

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_raw(self, status, body):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        print("TimeLimit Control Panel draait op poort 8099")
        httpd.serve_forever()