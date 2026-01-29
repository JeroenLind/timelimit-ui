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
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] [{category}] {message}\n")

    def post(self, path, data):
        target_url = f"{self.server_url}{path}"
        self._log("API-CALL", f"Target: {target_url}")
        
        try:
            req = urllib.request.Request(
                target_url, 
                data=data if isinstance(data, bytes) else data.encode('utf-8'), 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )

            with urllib.request.urlopen(req, context=self.ssl_context, timeout=10) as response:
                res_body = response.read()
                self._log("SUCCESS", f"Status {response.status}")
                return response.status, res_body

        except urllib.error.HTTPError as e:
            err_body = e.read()
            self._log("HTTP-ERROR", f"Code {e.code}")
            return e.code, err_body
            
        except Exception as e:
            self._log("CRITICAL", str(e))
            return 500, str(e).encode()