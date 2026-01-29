import urllib.request
import ssl
import json
import sys
import time

class TimeLimitAPI:
    def __init__(self, server_url):
        self.server_url = server_url.strip().rstrip('/')
        self.ssl_context = ssl._create_unverified_context()

    def _log(self, category, message):
        timestamp = time.strftime("%H:%M:%S")
        sys.stderr.write(f"[{timestamp}] [{category}] {message}\n")

    def post(self, path, data):
        target_url = f"{self.server_url}{path}"
        
        # 1. Logging van de uitgaande oproep
        self._log("API-CALL", f"Verbinding maken met: {target_url}")
        
        try:
            # Controleer of data valide JSON is voor we het sturen
            payload_str = data.decode('utf-8') if isinstance(data, bytes) else data
            self._log("PAYLOAD", f"Body: {payload_str}")

            req = urllib.request.Request(
                target_url, 
                data=data if isinstance(data, bytes) else data.encode('utf-8'), 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )

            with urllib.request.urlopen(req, context=self.ssl_context, timeout=10) as response:
                res_body = response.read()
                self._log("SUCCESS", f"Status: {response.status} - Data ontvangen ({len(res_body)} bytes)")
                return response.status, res_body

        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            self._log("HTTP-ERROR", f"Code: {e.code}")
            self._log("SERVER-RESPONSE", f"Detail: {err_body}")
            return e.code, err_body.encode()
            
        except urllib.error.URLError as e:
            self._log("CONN-ERROR", f"Kan server niet bereiken: {e.reason}")
            return 503, str(e.reason).encode()
            
        except Exception as e:
            self._log("CRITICAL", f"Onverwachte fout: {str(e)}")
            return 500, str(e).encode()