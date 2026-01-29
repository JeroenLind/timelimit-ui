import http.server
import socketserver
import json
import os
import sys
from api_client import TimeLimitAPI

CONFIG_PATH = "/data/options.json"
HTML_PATH = "/usr/bin/dashboard.html" 

def get_config():
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
        
        # Gezondheidscheck voor de API call
        if not config['server_url']:
            self._send_raw(500, b"Geen server_url geconfigureerd in HA opties")
            return

        routes = {
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/sync': '/sync/pull-status'
        }
        
        target_path = routes.get(self.path, '/sync/pull-status')
        status, body = api.post(target_path, post_data)
        self._send_raw(status, body)

    def do_GET(self):
        if self.path in ['/', '', '/index.html']:
            try:
                config = get_config()
                with open(HTML_PATH, 'r', encoding='utf-8') as f:
                    html = f.read().replace("###TOKEN###", config.get('auth_token', ''))
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
            except Exception as e:
                self.send_response(500); self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            super().do_GET()

    def _send_raw(self, status, body):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        sys.stderr.write("=== TimeLimit Debug-Backend v41 gestart op poort 8099 ===\n")
        httpd.serve_forever()