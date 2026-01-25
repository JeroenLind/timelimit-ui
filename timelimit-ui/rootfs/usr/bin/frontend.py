from flask import Flask, render_template_string, jsonify
import requests
import json
import os

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
        except:
            pass
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
        .time { color: #03a9f4; font-weight: bold; }
        
        .grid { display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; text-align: left; }
        .panel { flex: 1; min-width: 350px; padding: 20px; border: 1px solid #444; border-radius: 8px; background: #111; }
        
        pre { background: #000; padding: 15px; color: #00ff00; overflow-y: auto; border-radius: 5px; font-size: 11px; height: 250px; border: 1px solid #333; }
        h1 { margin-bottom: 30px; }
        h3 { color: #ccc; margin-top: 0; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 10px; }
        
        .user-card { background: #222; padding: 15px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #03a9f4; }
        .empty-state { color: #888; text-align: center; padding: 40px 0; font-style: italic; }
        
        button { background: #03a9f4; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        button:hover { background: #0288d1; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Timelimit Dashboard</h1>
        
        <div class="status-header">
            <div>Verbinding: <span id="status-text">Laden...</span></div>
            <div>Server Tijd: <span class="time" id="time-display">-- ms</span></div>
        </div>

        <div class="grid">
            <div class="panel">
                <h3>
                    Gebruikers
                    <button onclick="updateUsers()">Verversen</button>
                </h3>
                <div id="users-list">
                    <div class="empty-state">Laden van gebruikers...</div>
                </div>
            </div>

            <div class="panel">
                <h3>Systeem Status</h3>
                <pre id="admin-status">Wachten op data...</pre>
            </div>
        </div>
    </div>
    
    <script>
        async function updateData() {
            try {
                const response = await fetch('./api/data');
                const data = await response.json();
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
                const data = await response.json();
                document.getElementById('admin-status').innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                document.getElementById('admin-status').innerText = "Fout: " + e.message;
            }
        }

        async function updateUsers() {
            const listDiv = document.getElementById('users-list');
            try {
                const response = await fetch('./api/users');
                const data = await response.json();
                
                listDiv.innerHTML = ''; // Maak leeg

                if (!data || data.length === 0) {
                    listDiv.innerHTML = '<div class="empty-state">Geen gebruikers aangemeld op deze server.</div>';
                } else {
                    data.forEach(user => {
                        const card = document.createElement('div');
                        card.className = 'user-card';
                        card.innerHTML = `<strong>${user.name}</strong><br><small>ID: ${user.id}</small>`;
                        listDiv.appendChild(card);
                    });
                }
            } catch (e) {
                listDiv.innerHTML = '<div class="empty-state" style="color: #f44336;">Fout bij ophalen gebruikers.</div>';
            }
        }

        // Intervalle
        setInterval(updateData, 5000);
        setInterval(updateAdminStatus, 30000);
        setInterval(updateUsers, 15000);
        
        // Init
        updateData();
        updateAdminStatus();
        updateUsers();
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
        r = requests.get(USERS_URL, auth=('', password), timeout=5)
        # De server stuurt een lege lijst [] als er geen users zijn
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8099, debug=False)