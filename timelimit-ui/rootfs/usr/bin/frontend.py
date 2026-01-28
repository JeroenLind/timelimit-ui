import http.server
import socketserver
import json
import os
from crypto_utils import generate_family_hashes
from api_client import TimeLimitAPI

CONFIG_PATH = "/data/options.json"
HISTORY_PATH = "/data/history.json"
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

        if self.path == '/generate-hashes':
            try:
                data = json.loads(post_data)
                res = generate_family_hashes(data['password'])
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            
        else:
            routes = {
                '/wizard-step1': '/auth/send-mail-login-code-v2',
                '/wizard-step2': '/auth/sign-in-by-mail-code',
                '/wizard-step3': '/parent/create-family',
                '/sync': '/sync/pull-status'
            }
            
            target = routes.get(self.path)
            if target:
                # api.post geeft nu (status, bytes) terug
                status, body = api.post(target, post_data)
                self._send_raw(status, body)
            else:
                self._send_json(404, {"error": "Route niet gevonden"})

    def do_GET(self):
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
                self.wfile.write(f"Fout: {e}".encode())
        
        elif self.path == '/history':
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f: self._send_raw(200, f.read())
            else:
                self._send_json(200, [])

    def _send_json(self, status, data):
        body = json.dumps(data).encode('utf-8')
        self._send_raw(status, body)

    def _send_raw(self, status, body):
        # Cruciaal: Stuur alleen de body bytes, geen extra strings
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8099), TimeLimitHandler) as httpd:
        httpd.serve_forever()