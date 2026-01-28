import urllib.request
import ssl
import json
import sys

class TimeLimitAPI:
    def __init__(self, server_url):
        self.server_url = server_url.strip().rstrip('/')
        self.ssl_context = ssl._create_unverified_context()

    def post(self, path, data):
        target_url = f"{self.server_url}{path}"
        # Log wat we gaan sturen
        sys.stderr.write(f"--- API REQUEST ---\n")
        sys.stderr.write(f"URL: {target_url}\n")
        sys.stderr.write(f"PAYLOAD: {data.decode('utf-8') if isinstance(data, bytes) else data}\n")
        
        try:
            req = urllib.request.Request(
                target_url, 
                data=data, 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )
            with urllib.request.urlopen(req, context=self.ssl_context) as response:
                res_body = response.read()
                return response.status, res_body
        except urllib.error.HTTPError as e:
            err_body = e.read()
            sys.stderr.write(f"--- API ERROR ---\n")
            sys.stderr.write(f"STATUS: {e.code}\n")
            sys.stderr.write(f"RESPONSE: {err_body.decode('utf-8')}\n")
            return e.code, err_body
        except Exception as e:
            sys.stderr.write(f"--- SYSTEM ERROR ---\n")
            sys.stderr.write(f"MSG: {str(e)}\n")
            return 500, str(e).encode()