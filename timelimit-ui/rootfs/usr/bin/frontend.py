from flask import Flask, render_template_string, jsonify
import requests
import json
import os

app = Flask(__name__)

# URL's van de externe Timelimit server
SERVER_URL = "http://192.168.68.30:8080/time"
STATUS_URL = "http://192.168.68.30:8080/admin/status"

def get_server_password():
    """Leest het wachtwoord uit de add-on configuratie in Home Assistant."""
    options_path = "/data/options.json"
    if os.path.exists(options_path):
        try:
            with open(options_path, "r") as f:
                options = json.load(f)
                return options.get("server_password", "test")
        except Exception as e:
            print(f"Fout bij lezen options.json: {e}")
    return "test"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Timelimit UI</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background-color: #1c1c1c; color: white; }
        .container { max-width: 600px; margin: auto; }
        .status-box { font-size: 20px; margin-bottom: 20px; padding: 15px; border-radius: 8px; background: #2c2c2c; }
        .time { color: #03a9f4; font-weight: bold; font-size: 28px; }
        .admin-box { margin-top: 30px; padding: 15px; border: 1px solid #444; border-radius: 8px; }
        pre { text-align: left; background: #000; padding: 15px; color: #00ff00; overflow-x: auto; border-radius: 5px; font-size: 12px; }
        h1 { color: #fff; }
        h3 { color: #ccc; margin-top: 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Timelimit Dashboard</h1>
        
        <div class="status-box">
            <div>Server Verbinding: <span id="status-text">Laden...</span></div>
            <div class="time" id="time-display">-- ms</div>
        </div>

        <div class="admin-box">
            <h3>Admin Server Status</h3>
            <pre id="admin-status">Wachten op data...</pre>
        </div>
    </div>
    
    <script>
        async function updateData() {
            try {
                const response = await fetch('./api/data');
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                document.getElementById('status-text').innerText = "Online";
                document.getElementById('status-text').style.color = "#4caf50";
                document.getElementById('time-display').innerText = data.ms + " ms";
            } catch (e) {
                document.getElementById('status-text').innerText = "Offline";
                document.getElementById('status-text').style.color = "#f44336";
            }
        }

        async function updateAdminStatus() {
            try {
                const response = await fetch('./api/status');
                if (!response.ok) throw new Error('Authenticatie mislukt of server onbereikbaar');
                const data = await response.json();
                document.getElementById('admin-status').innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                document.getElementById('admin-status').innerText = "Fout: " + e.message;
                document.getElementById('admin-status').style.color = "#f44336";
            }
        }

        // Updates instellen
        setInterval(updateData, 5000);
        setInterval(updateAdminStatus, 10000);
        
        // Direct eerste keer uitvoeren
        updateData();
        updateAdminStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    """Haalt simpele tijd-data op zonder auth."""
    try:
        r = requests.get(SERVER_URL, timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status')
def get_status():
    """Haalt admin status op met Basic Auth (lege username)."""
    password = get_server_password()
    try:
        # Authenticatie met lege username en wachtwoord uit config
        r = requests.get(STATUS_URL, auth=('', password), timeout=3)
        if r.status_code == 401:
            return jsonify({"error": "Ongeldig wachtwoord"}), 401
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Luister op poort 8099 voor Ingress en lokale toegang
    app.run(host='0.0.0.0', port=8099, debug=False)