import http.server
import socketserver
import json
import os
import sys
import time
import threading
from socketserver import ThreadingMixIn
from api_client import TimeLimitAPI

CONFIG_PATH = "/data/options.json"
HTML_PATH = "/usr/bin/dashboard.html" 
STORAGE_PATH = "/data/timelimit_ui_storage.json"
STORAGE_TMP_PATH = "/data/timelimit_ui_storage.json.tmp"

# NIEUW: Globale variabele om de server-keuze in het geheugen op te slaan
SELECTED_SERVER = None
SSE_CLIENTS = []
SSE_LOCK = threading.Lock()
SSE_CLIENT_COUNTER = 0

def log(message):
    sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {message}\n")

def sse_log(message):
    log(message)

def broadcast_sse(event, data):
    sse_log(f"[SSE] Broadcast event={event} data={data}")
    payload = f"event: {event}\ndata: {data}\n\n".encode('utf-8')
    with SSE_LOCK:
        clients = list(SSE_CLIENTS)
    sse_log(f"[SSE] Clients count={len(clients)}")
    for client in clients:
        try:
            with client["lock"]:
                client["wfile"].write(payload)
                client["wfile"].flush()
            sse_log(f"[SSE] Sent event={event} to client={client.get('id', '?')}")
        except Exception as e:
            sse_log(f"[SSE] Broadcast failed: {str(e)}")
            try:
                with SSE_LOCK:
                    if client in SSE_CLIENTS:
                        SSE_CLIENTS.remove(client)
            except Exception:
                pass

def get_config():
    """Haalt de actuele configuratie op uit Home Assistant."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f: 
                return json.load(f)
        except Exception as e:
            log(f"Config Error: {str(e)}")
    return {"server_url": "http://192.168.68.30:8080", "auth_token": ""}

class ThreadedHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class TimeLimitHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, format, *args):
        log(f"WebUI: {format%args}")

    def do_POST(self):
        """Handelt alle API verzoeken van het dashboard af met uitgebreide logging."""
        global SELECTED_SERVER
        
        # DEBUG: Log welk pad wordt aangeroepen
        log(f"\n[DEBUG] Binnenkomend POST verzoek op pad: {self.path}")
        log(f"[DEBUG] Request headers: {dict(self.headers)}")
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        log(f"[DEBUG] Content-Length: {content_length} bytes")
        
        # Initialiseer SELECTED_SERVER
        if SELECTED_SERVER is None:
            SELECTED_SERVER = get_config().get('server_url', "http://192.168.68.30:8080")
            log(f"[DEBUG] SELECTED_SERVER geïnitialiseerd op: {SELECTED_SERVER}")

        # --- CHECK 1: De Server Wissel Route (Aangepast voor Ingress compatibiliteit) ---
        if self.path.endswith('/set-server'):
            log("[DEBUG] Route /set-server herkend!")
            try:
                data = json.loads(post_data)
                new_url = data.get('url')
                log(f"[DEBUG] Poging tot wisselen naar: {new_url}")
                
                SELECTED_SERVER = new_url
                log(f"✅ [SUCCESS] SERVER GEWISSELD NAAR: {SELECTED_SERVER}")
                
                # Stuur expliciet antwoord terug naar de browser
                self._send_raw(200, json.dumps({"status": "ok", "server": SELECTED_SERVER}).encode(), "application/json")
                return 
            except Exception as e:
                log(f"❌ [ERROR] Fout in /set-server: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
                return

        # --- CHECK 1b: HA storage shadow copy ---
        if self.path.endswith('/ha-storage'):
            try:
                payload = json.loads(post_data) if post_data else {}
                if not isinstance(payload, dict):
                    raise ValueError("Invalid payload")

                payload["serverTimestamp"] = int(time.time() * 1000)

                with open(STORAGE_TMP_PATH, 'w') as f:
                    json.dump(payload, f)
                os.replace(STORAGE_TMP_PATH, STORAGE_PATH)

                sse_log("[SSE] Trigger broadcast from /ha-storage")
                broadcast_sse("storage", "updated")

                self._send_raw(200, json.dumps({"status": "ok"}).encode(), "application/json")
                return
            except Exception as e:
                sse_log(f"❌ [ERROR] Fout in /ha-storage: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
                return

        # --- CHECK 2: Proxy Logica ---
        # We bepalen eerst of we naar de geselecteerde server gaan
        log(f"[DEBUG] Verzoek wordt doorgezet naar proxy: {SELECTED_SERVER}")
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
            log("[DEBUG] Interne hash generatie gestart")
            from crypto_utils import generate_family_hashes
            try:
                data = json.loads(post_data)
                log(f"[DEBUG] generate-hashes payload keys: {list(data.keys())}")
                start_ts = time.time()
                res = generate_family_hashes(data['password'])
                duration_ms = int((time.time() - start_ts) * 1000)
                log(f"[DEBUG] generate-hashes duur: {duration_ms} ms")
                log("[DEBUG] generate-hashes succesvol afgerond")
                self._send_raw(200, json.dumps(res).encode(), "application/json")
            except Exception as e:
                log(f"[ERROR] generate-hashes fout: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # Nieuwe endpoint: regenereer secondHash met bestaande salt
        if self.path.endswith('/regenerate-hash'):
            log("[DEBUG] secondHash regeneratie gestart")
            from crypto_utils import regenerate_second_hash
            try:
                data = json.loads(post_data)
                password = data['password']
                second_salt = data['secondSalt']
                
                second_hash = regenerate_second_hash(password, second_salt)
                log(f"[DEBUG] secondHash succesvol geregenereerd (first 30 chars): {second_hash[:30]}...")
                
                self._send_raw(200, json.dumps({"secondHash": second_hash}).encode(), "application/json")
            except Exception as e:
                log(f"[ERROR] Hash regeneratie fout: {str(e)}")
                self._send_raw(400, json.dumps({"error": str(e)}).encode(), "application/json")
            return
        
        # Speciale afhandeling voor HMAC-SHA512 berekening (fallback voor non-secure contexts)
        if self.path.endswith('/calculate-hmac'):
            log("[DEBUG] Server-side HMAC-SHA512 berekening gestart")
            from crypto_utils import calculate_hmac_sha512
            try:
                data = json.loads(post_data)
                key_base64 = data['key']
                message = data['message']
                
                result = calculate_hmac_sha512(key_base64, message)
                log(f"[DEBUG] HMAC berekend: {result[:30]}...")
                
                self._send_raw(200, json.dumps({"hash": result}).encode(), "application/json")
            except Exception as e:
                log(f"[ERROR] HMAC fout: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
            return

        # Legacy SHA512 hex digest (voor serverLevel < 6)
        if self.path.endswith('/calculate-sha512'):
            log("[DEBUG] Server-side SHA512 berekening gestart")
            from crypto_utils import calculate_sha512_hex
            try:
                data = json.loads(post_data)
                message = data['message']

                result = calculate_sha512_hex(message)
                log(f"[DEBUG] SHA512 berekend: {result[:30]}...")

                self._send_raw(200, json.dumps({"hash": result}).encode(), "application/json")
            except Exception as e:
                log(f"[ERROR] SHA512 fout: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # NIEUWE afhandeling voor HMAC-SHA256 met binary format (CORRECT server formaat)
        if self.path.endswith('/calculate-hmac-sha256'):
            log("[DEBUG] Server-side HMAC-SHA256 (binary format) berekening gestart")
            from crypto_utils import calculate_hmac_sha256_binary
            try:
                data = json.loads(post_data)
                second_hash = data['secondHash']
                sequence_number = data['sequenceNumber']
                device_id = data['deviceId']
                encoded_action = data['encodedAction']
                
                result = calculate_hmac_sha256_binary(second_hash, sequence_number, device_id, encoded_action)
                log(f"[DEBUG] HMAC-SHA256 berekend: {result[:50]}...")
                
                self._send_raw(200, json.dumps({"integrity": result}).encode(), "application/json")
            except Exception as e:
                log(f"[ERROR] HMAC-SHA256 fout: {str(e)}")
                self._send_raw(400, str(e).encode(), "text/plain")
            return
        
        # DEBUG endpoint: uitgebreide integrity diagnostiek
        if self.path.endswith('/debug-integrity'):
            log("[DEBUG] === INTEGRITY DIAGNOSTIEK START ===")
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
                
                log(f"[DEBUG-INT] Password: {'*' * len(password) if password else 'MISSING'}")
                log(f"[DEBUG-INT] SecondSalt: {second_salt}")
                log(f"[DEBUG-INT] SequenceNumber: {sequence_number}")
                log(f"[DEBUG-INT] DeviceId: '{device_id}' (length: {len(device_id)})")
                log(f"[DEBUG-INT] EncodedAction length: {len(encoded_action)}")
                log(f"[DEBUG-INT] ProvidedIntegrity: {provided_integrity}")
                
                # Stap 1: Regenereer secondHash
                second_hash = regenerate_second_hash(password, second_salt)
                log(f"[DEBUG-INT] Regenerated secondHash: {second_hash}")
                log(f"[DEBUG-INT] SecondHash as bytes: {second_hash.encode('utf-8')}")
                
                # Stap 2: Bereken HMAC
                calculated_integrity = calculate_hmac_sha256_binary(
                    second_hash, sequence_number, device_id, encoded_action
                )
                log(f"[DEBUG-INT] Calculated integrity: {calculated_integrity}")
                
                # Stap 3: Vergelijk
                match = (calculated_integrity == provided_integrity)
                log(f"[DEBUG-INT] MATCH: {match}")
                
                if not match:
                    log("[DEBUG-INT] ❌ MISMATCH DETAILS:")
                    log(f"[DEBUG-INT]   Expected: {calculated_integrity}")
                    log(f"[DEBUG-INT]   Got:      {provided_integrity}")
                    
                    # Decodeer beide base64 strings en vergelijk bytes
                    if provided_integrity.startswith('password:'):
                        expected_bytes = base64.b64decode(calculated_integrity.split(':')[1])
                        provided_bytes = base64.b64decode(provided_integrity.split(':')[1])
                        log(f"[DEBUG-INT]   Expected bytes (hex): {expected_bytes.hex()}")
                        log(f"[DEBUG-INT]   Provided bytes (hex): {provided_bytes.hex()}")
                
                log("[DEBUG] === INTEGRITY DIAGNOSTIEK END ===")
                
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
                log(f"[ERROR] Debug integrity fout: {str(e)}")
                log(f"{error_trace}")
                self._send_raw(400, json.dumps({"error": str(e), "trace": error_trace}).encode(), "application/json")
            return
        
        # Endpoint om deviceId op te halen die hoort bij een token
        if self.path.endswith('/get-token-device'):
            log("[DEBUG] === TOKEN DEVICE LOOKUP START ===")
            try:
                data = json.loads(post_data)
                device_auth_token = data.get('deviceAuthToken')
                
                log(f"[DEBUG] Looking up device for token: {device_auth_token[:10]}...")
                
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
                        log(f"[DEBUG] Found {len(devices)} devices in response")
                        
                        for device in devices:
                            log(f"[DEBUG] Device: {device.get('name')} - ID: {device.get('deviceId')}")
                        
                        # Probeer DashboardControl to vinden
                        dashboard_device = next((d for d in devices if 'Dashboard' in d.get('name', '')), None)
                        
                        if dashboard_device:
                            device_id = dashboard_device['deviceId']
                            log(f"[DEBUG] Found dashboard device: {device_id}")
                            
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
                    log(f"[ERROR] Pull status failed: {status}")
                    result = {"error": f"Pull status failed with {status}"}
                    self._send_raw(status, json.dumps(result).encode(), "application/json")
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                log(f"[ERROR] Token device lookup failed: {str(e)}")
                log(f"{error_trace}")
                self._send_raw(500, json.dumps({"error": str(e), "trace": error_trace}).encode(), "application/json")
            
            log("[DEBUG] === TOKEN DEVICE LOOKUP END ===")
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

        log(f"[DEBUG] === ROUTE MATCHING ===")
        log(f"[DEBUG] Incoming path: {self.path}")
        log(f"[DEBUG] Matched UI route: {matched_route}")
        log(f"[DEBUG] Target API path: {target_path}")
        log(f"[DEBUG] Final URL: {SELECTED_SERVER}{target_path}")
        log(f"[DEBUG] POST data size: {content_length} bytes")
        
        # Log de eerste 500 bytes van de payload voor debugging (niet het hele wachtwoord!)
        try:
            preview_data = post_data[:500].decode('utf-8', errors='replace')
            log(f"[DEBUG] Payload preview (first 500 bytes): {preview_data}")
        except:
            log("[DEBUG] Payload preview: (binary data)")
        
        try:
            status, body = api.post(target_path, post_data)
            log(f"[DEBUG] API Response status: {status}")
            log(f"[DEBUG] API Response body size: {len(body)} bytes")
            
            # Log de response preview
            try:
                body_preview = body[:500].decode('utf-8', errors='replace')
                log(f"[DEBUG] Response preview (first 500 bytes): {body_preview}")
            except:
                log("[DEBUG] Response preview: (binary data)")
            
            if self.path.endswith('/sync/push-actions') and 200 <= status < 300:
                sse_log("[SSE] Trigger broadcast from /sync/push-actions")
                broadcast_sse("push", "done")
            self._send_raw(status, body, "application/json")
        except Exception as e:
            log(f"❌ [PROXY ERROR]: {str(e)}")
            import traceback
            log(f"Traceback:\n{traceback.format_exc()}")
            self._send_raw(500, b"Proxy connection failed", "text/plain")

    def do_GET(self):
        # ... (do_GET blijft hetzelfde als in jouw code) ...
        if self.path.endswith('/ha-events'):
            global SSE_CLIENT_COUNTER
            with SSE_LOCK:
                SSE_CLIENT_COUNTER += 1
                client_id = SSE_CLIENT_COUNTER
                current_count = len(SSE_CLIENTS) + 1
            user_agent = self.headers.get('User-Agent', '-')
            forwarded_for = self.headers.get('X-Forwarded-For', '-')
            ingress_path = self.headers.get('X-Ingress-Path', '-')
            client_addr = f"{self.client_address[0]}:{self.client_address[1]}" if self.client_address else '-'
            sse_log(
                f"[SSE] Client connected to /ha-events (client={client_id}, clients={current_count}, addr={client_addr}, fwd={forwarded_for}, ingress={ingress_path}, ua={user_agent})"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Pragma", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Content-Encoding", "identity")
            self.end_headers()
            self.wfile.flush()
            self.close_connection = False

            client = {"wfile": self.wfile, "lock": threading.Lock(), "id": client_id}
            with SSE_LOCK:
                SSE_CLIENTS.append(client)

            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.write(b"retry: 5000\n\n")
                hello_payload = f"event: hello\ndata: clientId={client_id}\n\n".encode('utf-8')
                self.wfile.write(hello_payload)
                self.wfile.flush()
                sse_log(f"[SSE] Sent event=hello to client={client_id}")
                while True:
                    time.sleep(15)
                    with client["lock"]:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with SSE_LOCK:
                    remaining = len(SSE_CLIENTS) - 1 if client in SSE_CLIENTS else len(SSE_CLIENTS)
                sse_log(f"[SSE] Client disconnected from /ha-events (client={client_id}, clients={max(remaining, 0)})")
                with SSE_LOCK:
                    if client in SSE_CLIENTS:
                        SSE_CLIENTS.remove(client)
            return
        if self.path.endswith('/ha-storage'):
            try:
                if os.path.exists(STORAGE_PATH):
                    with open(STORAGE_PATH, 'r') as f:
                        data = json.load(f)
                else:
                    data = {"status": "empty"}
                self._send_raw(200, json.dumps(data).encode(), "application/json")
            except Exception as e:
                sse_log(f"❌ [ERROR] Fout in GET /ha-storage: {str(e)}")
                self._send_raw(500, str(e).encode(), "text/plain")
            return
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
            log(f"Response Error: {str(e)}")

if __name__ == "__main__":
    with ThreadedHTTPServer(("", 8099), TimeLimitHandler) as httpd:
        log("=== TimeLimit v60: Multi-threaded Backend met Server-Switch ===")
        httpd.serve_forever()