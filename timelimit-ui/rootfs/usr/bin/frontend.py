import http.server
import socketserver
import json
import os
import sys
import time
from socketserver import ThreadingMixIn
from api_client import TimeLimitAPI

CONFIG_PATH = "/data/options.json"
HTML_PATH = "/usr/bin/dashboard.html" 

# NIEUW: Globale variabele om de server-keuze in het geheugen op te slaan
SELECTED_SERVER = None

def get_config():
    """Haalt de actuele configuratie op uit Home Assistant."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f: 
                return json.load(f)
        except Exception as e:
            sys.stderr.write(f"Config Error: {str(e)}\n")
    return {"server_url": "http://192.168.68.30:8080", "auth_token": ""}

class ThreadedHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write(f"WebUI [{time.strftime('%H:%M:%S')}]: {format%args}\n")

    def do_POST(self):
        """Handelt alle API verzoeken van het dashboard af."""
        global SELECTED_SERVER
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # Initialiseer de server-URL als dit de eerste keer is
        if SELECTED_SERVER is None:
            SELECTED_SERVER = get_config().get('server_url', "http://192.168.68.30:8080")

        # --- NIEUW: Route voor server-wissel ---
        if self.path == '/set-server':
            try:
                data = json.loads(post_data)
                SELECTED_SERVER = data.get('url')
                sys.stderr.write(f"Backend [{time.strftime('%H:%M:%S')}]: Server gewisseld naar {SELECTED_SERVER}\n")
                self._send_raw(200, json.dumps({"status": "ok"}).encode(), "application/json")
                return # Stop hier, stuur dit niet door naar de TimeLimit API
            except Exception as e:
                self._send_raw(400, str(e).encode(), "text/plain")
                return

        # Gebruik nu SELECTED_SERVER in plaats van config['server_url']
        api = TimeLimitAPI(SELECTED_SERVER)
        
        routes = {
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/wizard-login': '/parent/sign-in-into-family',
            '/sync': '/sync/pull-status',
            '/generate-hashes': 'INTERNAL'
        }
        
        # 1. Interne hashing logica
        if self.path == '/generate-hashes':
            from crypto_utils import generate_family_hashes
            try:
                data = json.loads(post_data)
                res = generate_family_hashes(data['password'])
                self._send_raw(200, json.dumps(res).encode(), "application/json")
            except Exception as e:
                self._send_raw(400, str(e).encode(), "text/plain")
            return

        # 2. Proxy naar TimeLimit Server
        target_path = routes.get(self.path, '/sync/pull-status')
        status, body = api.post(target_path, post_data)
        
        self._send_raw(status, body, "application/json")

    def do_GET(self):
        # ... (do_GET blijft hetzelfde als in jouw code) ...
        if self.path in ['/', '', '/index.html']:
            try:
                config = get_config()
                if not os.path.exists(HTML_PATH):
                    self.send_error(404, "Dashboard HTML niet gevonden")
                    return
                with open(HTML_PATH, 'r', encoding='utf-8') as f:
                    html = f.read().replace("###TOKEN###", config.get('auth_token', ''))
                    self._send_raw(200, html.encode('utf-8'), "text/html")
            except Exception as e:
                self.send_error(500, f"Server Error: {str(e)}")
        else:
            super().do_GET()

    def _send_raw(self, status, body, content_type):
        try:
            self.send_response(status)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            sys.stderr.write(f"Response Error: {str(e)}\n")

if __name__ == "__main__":
    with ThreadedHTTPServer(("", 8099), TimeLimitHandler) as httpd:
        sys.stderr.write("=== TimeLimit v60: Multi-threaded Backend met Server-Switch ===\n")
        httpd.serve_forever()