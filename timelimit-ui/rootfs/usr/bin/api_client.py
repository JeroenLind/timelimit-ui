import urllib.request
import ssl
import json

class TimeLimitAPI:
    def __init__(self, server_url):
        self.server_url = server_url.strip().rstrip('/')
        self.ssl_context = ssl._create_unverified_context()

    def post(self, path, data):
        """Verstuurt een JSON POST verzoek naar de geconfigureerde server."""
        target_url = f"{self.server_url}{path}"
        try:
            req = urllib.request.Request(
                target_url, 
                data=data, 
                headers={'Content-Type': 'application/json'}, 
                method='POST'
            )
            with urllib.request.urlopen(req, context=self.ssl_context) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            return 500, str(e).encode()