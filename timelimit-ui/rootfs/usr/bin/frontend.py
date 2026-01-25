from flask import Flask, render_template_string, jsonify
import requests
import json
import os
import sys

app = Flask(__name__)

# URL's van de Timelimit server
SERVER_URL = "http://192.168.68.30:8080/time"
STATUS_URL = "http://192.168.68.30:8080/admin/status"
USERS_URL = "http://192.168.68.30:8080/users"

def get_server_password():
    options_path = "/data/options.json"
    if os.path.exists(options_path):
        try:
            with open(options_path, "r") as f:
                options = json.load(f)
                return options.get("server_password", "test")
        except Exception as e:
            print(f"[ERROR] Kon options.json niet lezen: {e}", file=sys.stderr)
    return "test"

@app.route('/api/users')
def get_users():
    password = get_server_password()
    try:
        print(f"[DEBUG] Poging tot ophalen gebruikers van {USERS_URL}...", file=sys.stderr)
        r = requests.get(USERS_URL, auth=('', password), timeout=5)
        
        # Log de statuscode naar de HA Add-on logs
        print(f"[DEBUG] Server antwoordde met status: {r.status_code}", file=sys.stderr)
        
        if r.status_code != 200:
            print(f"[ERROR] Server foutmelding: {r.text}", file=sys.stderr)
            return jsonify({"error": f"Server status {r.status_code}", "details": r.text}), r.status_code
            
        return jsonify(r.json())
    except Exception as e:
        print(f"[ERROR] Exception tijdens get_users: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

# De rest van de routes (index, data, status) blijven gelijk aan de vorige versie...
# Zorg dat je de volledige HTML_TEMPLATE van de vorige keer hieronder behoudt.