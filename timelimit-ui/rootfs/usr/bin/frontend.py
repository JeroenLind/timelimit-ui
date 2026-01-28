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
    def log_message(self, format, *args):
        # Dit zorgt dat ELKE request in je HA Add-on log verschijnt
        print(f"HTTP LOG: {self.address_string()} - {format%args}")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        config = get_config()
        api = TimeLimitAPI(config['server_url'])

        # We kijken nu of de route VOORKOMT in het pad (flexibeler voor Ingress)
        path = self.path
        
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
        
        # Zoek of een van onze keywords in de URL staat
        target = None
        for key, val in routes.items():
            if key in path:
                target = val
                break

        if target:
            status, body = api.post(target, post_data)
            self._send_raw(status, body)
        else:
            msg = f"404: Pad '{path}' niet herkend door backend."
            print(f"WAARSCHUWING: {msg}")
            self._send_raw(404, msg.encode())

    def do_GET(self):
        # De browser vraagt vaak de root aan via Ingress
        if self.path.endswith('/') or self.path == "" or 'index.html' in self.path:
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
                self.wfile.write(f"HTML Fout: {e}".encode())
        elif 'history' in self.path:
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, 'rb') as f: self._send_raw(200, f.read())
            else:
                self._send_json(200, [])
        else:
            # Voor alle andere GET verzoeken (zoals favicon)
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
        httpd.serve_forever()