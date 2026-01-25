from flask import Flask, render_template_string, jsonify
import requests
import json
import os
import sys

app = Flask(__name__)

# URL's van de Timelimit server met de juiste v1 prefix
SERVER_URL = "http://192.168.68.30:8080/time"
STATUS_URL = "http://192.168.68.30:8080/admin/status"
USERS_URL  = "http://192.168.68.30:8080/v1/users"  # Toegevoegd: /v1/

def get_server_password():
    options_path = "/data/options.json"
    if os.path.exists(options_path):
        try:
            with open(options_path, "r") as f:
                options = json.load(f)
                return options.get("server_password", "test")
        except Exception as e:
            print(f"[ERROR] Fout bij lezen options: {e}", file=sys.stderr)
    return "test"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Timelimit UI</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background-color: #1c1c1c; color: white; text-align: center; }
        .container { max-width: 900px; margin: auto; }
        .status-header { font-size: 18px; margin-bottom: 20px; padding: 15px; border-radius: 8px; background: #2c2c2c; display: flex; justify-content: space-around; align-items: center; }
        .grid { display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; text-align: left; }
        .panel { flex: 1; min-width: 350px; padding: 20px; border: 1px solid #444; border-radius: 8px; background: #111; }
        pre { background: #000; padding: 15px; color: #00ff00; overflow-y: auto; border-radius: 5px; font-size: 11px; height: 250px; border: 1px solid #333; }
        .user-card { background: #222; padding: 15px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #03a9f4; }
        .empty-state { color: #888; text-align: center; padding: 40px 0; font-style: italic; }
        button { background: #03a9f4; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Timelimit Dashboard</h1>
        <div class="status-header">
            <div>Verbinding: <span id="status-text">Laden...</span></div>
            <div>Server Tijd: <span id="time-display">-- ms</span></div>
        </div>
        <div class="grid">
            <div class="panel">
                <h3>Gebruikers <button onclick="updateUsers()">Verversen</button></h3>
                <div id="users-list"><div class="empty-state">Laden...</div></div>
            </div>
            <div class="panel">
                <h3>Systeem Status</h3>
                <pre id="admin-status">Wachten...</pre>
            </div>
        </div>
    </div>
    <script>
        async function updateData() {
            try {
                const r = await fetch('./api/data');
                const d = await r.json();
                document.getElementById('status-text').innerText = "Online";
                document.getElementById('status-text').style.color = "#4caf50";
                document.getElementById('time-display').innerText = d.ms + " ms";
            } catch (e) {
                document.getElementById('status-text').innerText = "Offline";
                document.getElementById('status-text').style.color = "#f44336";
            }
        }
        async function updateAdminStatus() {
            try {
                const r = await fetch('./api/status');
                const d = await r.json();
                document.getElementById('admin-status').innerText = JSON.stringify(d, null, 2);
            } catch (e) { document.getElementById('admin-status').innerText = "Fout: " + e; }
        }
        async function updateUsers() {
            const list = document.getElementById('users-list');
            try {
                const r = await fetch('./api/users');
                const d = await r.json();
                list.innerHTML = '';
                if (d.error) {
                    list.innerHTML = `<div class="empty-state" style="color:red">Fout: ${d.error}</div>`;
                } else if (!d || d.length === 0) {
                    list.innerHTML = '<div class="empty-state">Geen gebruikers.</div>';
                } else {
                    d.forEach(u => {
                        const c = document.createElement('div');
                        c.className = 'user-card';
                        c.innerHTML = `<strong>${u.name}</strong><br><small>ID: ${u.id}</small>`;
                        list.appendChild(c);
                    });
                }
            } catch (e) { list.innerHTML = '<div class="empty-state" style="color:red">Netwerkfout</div>'; }
        }
        setInterval(updateData, 5000);
        setInterval(updateAdminStatus, 30000);
        setInterval(updateUsers, 15000);
        updateData(); updateAdminStatus(); updateUsers();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    try:
        r = requests.get(SERVER_URL, timeout=2)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status')
def get_status():
    password = get_server_password()
    try:
        r = requests.get(STATUS_URL, auth=('', password), timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users')
def get_users():
    password = get_server_password()
    try:
        # Debugging print naar HA logs
        print(f"[DEBUG] Vraag users aan via {USERS_URL}", file=sys.stderr)
        r = requests.get(USERS_URL, auth=('', password), timeout=5)
        print(f"[DEBUG] Status code: {r.status_code}", file=sys.stderr)
        
        if r.status_code != 200:
            return jsonify({"error": f"Server status {r.status_code}"}), r.status_code
            
        return jsonify(r.json())
    except Exception as e:
        print(f"[ERROR] API Call gefaald: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8099, debug=False)