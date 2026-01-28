import http.server
import socketserver
import json
import os
import sys
from crypto_utils import generate_family_hashes
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
    def log_message(self, format, *args):
        # Forceer output naar de HA logs
        sys.stderr.write(f"HTTP: {format%args}\n")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        config = get_config()
        api = TimeLimitAPI(config['server_url'])
        path = self.path

        sys.stderr.write(f"POST ontvangen op: {path}\n")

        if 'generate-hashes' in path:
            try:
                data = json.loads(post_data)
                res = generate_family_hashes(data['password'])
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        routes = {
            'wizard-step1': '/auth/send-mail-login-code-v2',
            'wizard-step2': '/auth/sign-in-by-mail-code',
            'wizard-step3': '/parent/create-family',
            'sync': '/sync/pull-status'
        }
        
        target = next((v for k, v in routes.items() if k in path), None)

        if target:
            status, body = api.post(target, post_data)
            sys.stderr.write(f"API {target} antwoordt met status {status}\n")
            self._send_raw(status, body)
        else:
            self._send_raw(404, b"Route niet herkend")

    def do_GET(self):
        if self.path.endswith('/') or 'index.html' in self.path or self.path == "":
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
                self.wfile.write(str(e).encode())
        else:
            super().do_GET()

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
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        sys.stderr.write("Server gestart op poort 8099\n")
        httpd.serve_forever()