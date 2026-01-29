import requests
import time
import sys

SERVER_URL = "http://192.168.68.30:8080/time"

print(f"Checking connection to {SERVER_URL}...")

while True:
    try:
        response = requests.get(SERVER_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Verbinding succesvol! Server tijd (ms): {data['ms']}")
        else:
            print(f"Server fout: Status code {response.status_code}")
    except Exception as e:
        print(f"Kan geen verbinding maken met server: {e}")
    
    sys.stdout.flush() # Zorg dat we de logs direct zien in HA
    time.sleep(60)