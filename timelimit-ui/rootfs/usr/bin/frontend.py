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
        """Handelt alle API verzoeken van het dashboard af met uitgebreide logging."""
        global SELECTED_SERVER
        
        # DEBUG: Log welk pad wordt aangeroepen
        sys.stderr.write(f"\n[DEBUG] Binnenkomend POST verzoek op pad: {self.path}\n")
        sys.stderr.write(f"[DEBUG] Request headers: {dict(self.headers)}\n")
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        sys.stderr.write(f"[DEBUG] Content-Length: {content_length} bytes\n")
        
        # Initialiseer SELECTED_SERVER
        if SELECTED_SERVER is None:
            SELECTED_SERVER = get_config().get('server_url', "http://192.168.68.30:8080")
            sys.stderr.write(f"[DEBUG] SELECTED_SERVER geïnitialiseerd op: {SELECTED_SERVER}\n")

        # --- CHECK 1: De Server Wissel Route (Aangepast voor Ingress compatibiliteit) ---
        if self.path.endswith('/set-server'):
            sys.stderr.write("[DEBUG] Route /set-server herkend!\n")
            try:
                data = json.loads(post_data)
                new_url = data.get('url')
                sys.stderr.write(f"[DEBUG] Poging tot wisselen naar: {new_url}\n")
                
                SELECTED_SERVER = new_url
                sys.stderr.write(f"✅ [SUCCESS] SERVER GEWISSELD NAAR: {SELECTED_SERVER}\n")
                
                # Stuur expliciet antwoord terug naar de browser
                self._send_raw(200, json.dumps({"status": "ok", "server": SELECTED_SERVER}).encode(), "application/json")
                return 
            except Exception as e:
                sys.stderr.write(f"❌ [ERROR] Fout in /set-server: {str(e)}\n")
                self._send_raw(400, str(e).encode(), "text/plain")
                return

        # --- CHECK 2: Proxy Logica ---
        # We bepalen eerst of we naar de geselecteerde server gaan
        sys.stderr.write(f"[DEBUG] Verzoek wordt doorgezet naar proxy: {SELECTED_SERVER}\n")
        api = TimeLimitAPI(SELECTED_SERVER)
        
        routes = {
            '/wizard-step1': '/auth/send-mail-login-code-v2',
            '/wizard-step2': '/auth/sign-in-by-mail-code',
            '/wizard-step3': '/parent/create-family',
            '/wizard-login': '/parent/sign-in-into-family',
            '/sync': '/sync/pull-status',
            '/sync/push-actions': '/sync/push-actions',
            '/generate-hashes': 'INTERNAL',
            '/regenerate-hash': 'INTERNAL',
            '/calculate-hmac': 'INTERNAL',
            '/calculate-hmac-sha256': 'INTERNAL',
            '/calculate-sha512': 'INTERNAL',
            '/debug-integrity': 'INTERNAL',
            '/get-token-device': 'INTERNAL'
        }
        
        # Speciale afhandeling voor interne hashing
        if self.path.endswith('/generate-hashes'):
            sys.stderr.write("[DEBUG] Interne hash generatie gestart\n")
            from crypto_utils import generate_family_hashes
            try:
                data = json.loads(post_data)
                sys.stderr.write(f"[DEBUG] generate-hashes payload keys: {list(data.keys())}\n")
                start_ts = time.time()
                res = generate_family_hashes(data['password'])
                duration_ms = int((time.time() - start_ts) * 1000)
                sys.stderr.write(f"[DEBUG] generate-hashes duur: {duration_ms} ms\n")
                sys.stderr.write("[DEBUG] generate-hashes succesvol afgerond\n")
                self._send_raw(200, json.dumps(res).encode(), "application/json")
            except Exception as e:
                sys.stderr.write(f"[ERROR] generate-hashes fout: {str(e)}\n")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # Nieuwe endpoint: regenereer secondHash met bestaande salt
        if self.path.endswith('/regenerate-hash'):
            sys.stderr.write("[DEBUG] secondHash regeneratie gestart\n")
            from crypto_utils import regenerate_second_hash
            try:
                data = json.loads(post_data)
                password = data['password']
                second_salt = data['secondSalt']
                
                second_hash = regenerate_second_hash(password, second_salt)
                sys.stderr.write(f"[DEBUG] secondHash succesvol geregenereerd (first 30 chars): {second_hash[:30]}...\n")
                
                self._send_raw(200, json.dumps({"secondHash": second_hash}).encode(), "application/json")
            except Exception as e:
                sys.stderr.write(f"[ERROR] Hash regeneratie fout: {str(e)}\n")
                self._send_raw(400, json.dumps({"error": str(e)}).encode(), "application/json")
            return
        
        # Speciale afhandeling voor HMAC-SHA512 berekening (fallback voor non-secure contexts)
        if self.path.endswith('/calculate-hmac'):
            sys.stderr.write("[DEBUG] Server-side HMAC-SHA512 berekening gestart\n")
            from crypto_utils import calculate_hmac_sha512
            try:
                data = json.loads(post_data)
                key_base64 = data['key']
                message = data['message']
                
                result = calculate_hmac_sha512(key_base64, message)
                sys.stderr.write(f"[DEBUG] HMAC berekend: {result[:30]}...\n")
                
                self._send_raw(200, json.dumps({"hash": result}).encode(), "application/json")
            except Exception as e:
                sys.stderr.write(f"[ERROR] HMAC fout: {str(e)}\n")
                self._send_raw(400, str(e).encode(), "text/plain")
            return

        # Legacy SHA512 hex digest (voor serverLevel < 6)
        if self.path.endswith('/calculate-sha512'):
            sys.stderr.write("[DEBUG] Server-side SHA512 berekening gestart\n")
            from crypto_utils import calculate_sha512_hex
            try:
                data = json.loads(post_data)
                message = data['message']

                result = calculate_sha512_hex(message)
                sys.stderr.write(f"[DEBUG] SHA512 berekend: {result[:30]}...\n")

                self._send_raw(200, json.dumps({"hash": result}).encode(), "application/json")
            except Exception as e:
                sys.stderr.write(f"[ERROR] SHA512 fout: {str(e)}\n")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # NIEUWE afhandeling voor HMAC-SHA256 met binary format (CORRECT server formaat)
        if self.path.endswith('/calculate-hmac-sha256'):
            sys.stderr.write("[DEBUG] Server-side HMAC-SHA256 (binary format) berekening gestart\n")
            from crypto_utils import calculate_hmac_sha256_binary
            try:
                data = json.loads(post_data)
                second_hash = data['secondHash']
                sequence_number = data['sequenceNumber']
                device_id = data['deviceId']
                encoded_action = data['encodedAction']
                
                result = calculate_hmac_sha256_binary(second_hash, sequence_number, device_id, encoded_action)
                sys.stderr.write(f"[DEBUG] HMAC-SHA256 berekend: {result[:50]}...\n")
                
                self._send_raw(200, json.dumps({"integrity": result}).encode(), "application/json")
            except Exception as e:
                sys.stderr.write(f"[ERROR] HMAC-SHA256 fout: {str(e)}\n")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # DEBUG endpoint: uitgebreide integrity diagnostiek
        if self.path.endswith('/debug-integrity'):
            sys.stderr.write("[DEBUG] === INTEGRITY DIAGNOSTIEK START ===\n")
            from crypto_utils import calculate_hmac_sha256_binary, regenerate_second_hash
            import base64
            try:
                data = json.loads(post_data)
                password = data.get('password')
                second_salt = data.get('secondSalt')
                sequence_number = data.get('sequenceNumber')
                device_id = data.get('deviceId')
                encoded_action = data.get('encodedAction')
                provided_integrity = data.get('providedIntegrity')
                
                sys.stderr.write(f"[DEBUG-INT] Password: {'*' * len(password) if password else 'MISSING'}\n")
                sys.stderr.write(f"[DEBUG-INT] SecondSalt: {second_salt}\n")
                sys.stderr.write(f"[DEBUG-INT] SequenceNumber: {sequence_number}\n")
                sys.stderr.write(f"[DEBUG-INT] DeviceId: '{device_id}' (length: {len(device_id)})\n")
                sys.stderr.write(f"[DEBUG-INT] EncodedAction length: {len(encoded_action)}\n")
                sys.stderr.write(f"[DEBUG-INT] ProvidedIntegrity: {provided_integrity}\n")
                
                # Stap 1: Regenereer secondHash
                second_hash = regenerate_second_hash(password, second_salt)
                sys.stderr.write(f"[DEBUG-INT] Regenerated secondHash: {second_hash}\n")
                sys.stderr.write(f"[DEBUG-INT] SecondHash as bytes: {second_hash.encode('utf-8')}\n")
                
                # Stap 2: Bereken HMAC
                calculated_integrity = calculate_hmac_sha256_binary(
                    second_hash, sequence_number, device_id, encoded_action
                )
                sys.stderr.write(f"[DEBUG-INT] Calculated integrity: {calculated_integrity}\n")
                
                # Stap 3: Vergelijk
                match = (calculated_integrity == provided_integrity)
                sys.stderr.write(f"[DEBUG-INT] MATCH: {match}\n")
                
                if not match:
                    sys.stderr.write(f"[DEBUG-INT] ❌ MISMATCH DETAILS:\n")
                    sys.stderr.write(f"[DEBUG-INT]   Expected: {calculated_integrity}\n")
                    sys.stderr.write(f"[DEBUG-INT]   Got:      {provided_integrity}\n")
                    
                    # Decodeer beide base64 strings en vergelijk bytes
                    if provided_integrity.startswith('password:'):
                        expected_bytes = base64.b64decode(calculated_integrity.split(':')[1])
                        provided_bytes = base64.b64decode(provided_integrity.split(':')[1])
                        sys.stderr.write(f"[DEBUG-INT]   Expected bytes (hex): {expected_bytes.hex()}\n")
                        sys.stderr.write(f"[DEBUG-INT]   Provided bytes (hex): {provided_bytes.hex()}\n")
                
                sys.stderr.write("[DEBUG] === INTEGRITY DIAGNOSTIEK END ===\n")
                
                response = {
                    "calculatedIntegrity": calculated_integrity,
                    "providedIntegrity": provided_integrity,
                    "match": match,
                    "secondHash": second_hash,
                    "debugInfo": {
                        "deviceIdLength": len(device_id),
                        "actionLength": len(encoded_action),
                        "sequenceNumber": sequence_number
                    }
                }
                
                self._send_raw(200, json.dumps(response, indent=2).encode(), "application/json")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                sys.stderr.write(f"[ERROR] Debug integrity fout: {str(e)}\n")
                sys.stderr.write(f"{error_trace}\n")
                self._send_raw(400, json.dumps({"error": str(e), "trace": error_trace}).encode(), "application/json")
            return
        
        # Endpoint om deviceId op te halen die hoort bij een token
        if self.path.endswith('/get-token-device'):
            sys.stderr.write("[DEBUG] === TOKEN DEVICE LOOKUP START ===\n")
            try:
                data = json.loads(post_data)
                device_auth_token = data.get('deviceAuthToken')
                
                sys.stderr.write(f"[DEBUG] Looking up device for token: {device_auth_token[:10]}...\n")
                
                # Vraag aan server via pull-status (dit geeft ons de deviceId terug)
                pull_request = {
                    "deviceAuthToken": device_auth_token,
                    "status": {
                        "apps": {},
                        "categories": {},
                        "devices": "0",
                        "users": "0",
                        "clientLevel": 8
                    }
                }
                
                status, body = api.post('/sync/pull-status', json.dumps(pull_request).encode())
                
                if status == 200:
                    response_data = json.loads(body)
                    
                    # Zoek in devices.data naar het device dat deze token heeft
                    # Helaas bevat pull-status response geen deviceId field direct
                    # Maar we kunnen wel de devices lijst gebruiken
                    
                    if 'devices' in response_data and 'data' in response_data['devices']:
                        devices = response_data['devices']['data']
                        sys.stderr.write(f"[DEBUG] Found {len(devices)} devices in response\n")
                        
                        for device in devices:
                            sys.stderr.write(f"[DEBUG] Device: {device.get('name')} - ID: {device.get('deviceId')}\n")
                        
                        # Probeer DashboardControl to vinden
                        dashboard_device = next((d for d in devices if 'Dashboard' in d.get('name', '')), None)
                        
                        if dashboard_device:
                            device_id = dashboard_device['deviceId']
                            sys.stderr.write(f"[DEBUG] Found dashboard device: {device_id}\n")
                            
                            result = {
                                "deviceId": device_id,
                                "deviceName": dashboard_device.get('name'),
                                "allDevices": devices,
                                "note": "Dit is de deviceId die bij je token zou moeten horen"
                            }
                            
                            self._send_raw(200, json.dumps(result, indent=2).encode(), "application/json")
                        else:
                            result = {
                                "error": "DashboardControl device not found",
                                "allDevices": devices
                            }
                            self._send_raw(404, json.dumps(result, indent=2).encode(), "application/json")
                    else:
                        result = {"error": "No devices in response"}
                        self._send_raw(500, json.dumps(result).encode(), "application/json")
                else:
                    sys.stderr.write(f"[ERROR] Pull status failed: {status}\n")
                    result = {"error": f"Pull status failed with {status}"}
                    self._send_raw(status, json.dumps(result).encode(), "application/json")
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                sys.stderr.write(f"[ERROR] Token device lookup failed: {str(e)}\n")
                sys.stderr.write(f"{error_trace}\n")
                self._send_raw(500, json.dumps({"error": str(e), "trace": error_trace}).encode(), "application/json")
            
            sys.stderr.write("[DEBUG] === TOKEN DEVICE LOOKUP END ===\n")
            return

        # Bepaal het doelpad op de externe API
        # We gebruiken ook hier endswith voor de routering om robuust te blijven tegenover proxy-prefixen
        target_path = '/sync/pull-status'  # Standaard
        matched_route = None
        
        for ui_route, api_route in routes.items():
            if self.path.endswith(ui_route):
                target_path = api_route
                matched_route = ui_route
                break

        sys.stderr.write(f"[DEBUG] === ROUTE MATCHING ===\n")
        sys.stderr.write(f"[DEBUG] Incoming path: {self.path}\n")
        sys.stderr.write(f"[DEBUG] Matched UI route: {matched_route}\n")
        sys.stderr.write(f"[DEBUG] Target API path: {target_path}\n")
        sys.stderr.write(f"[DEBUG] Final URL: {SELECTED_SERVER}{target_path}\n")
        sys.stderr.write(f"[DEBUG] POST data size: {content_length} bytes\n")
        
        # Log de eerste 500 bytes van de payload voor debugging (niet het hele wachtwoord!)
        try:
            preview_data = post_data[:500].decode('utf-8', errors='replace')
            sys.stderr.write(f"[DEBUG] Payload preview (first 500 bytes): {preview_data}\n")
        except:
            sys.stderr.write(f"[DEBUG] Payload preview: (binary data)\n")
        
        try:
            status, body = api.post(target_path, post_data)
            sys.stderr.write(f"[DEBUG] API Response status: {status}\n")
            sys.stderr.write(f"[DEBUG] API Response body size: {len(body)} bytes\n")
            
            # Log de response preview
            try:
                body_preview = body[:500].decode('utf-8', errors='replace')
                sys.stderr.write(f"[DEBUG] Response preview (first 500 bytes): {body_preview}\n")
            except:
                sys.stderr.write(f"[DEBUG] Response preview: (binary data)\n")
            
            self._send_raw(status, body, "application/json")
        except Exception as e:
            sys.stderr.write(f"❌ [PROXY ERROR]: {str(e)}\n")
            import traceback
            sys.stderr.write(f"Traceback:\n{traceback.format_exc()}\n")
            self._send_raw(500, b"Proxy connection failed", "text/plain")

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