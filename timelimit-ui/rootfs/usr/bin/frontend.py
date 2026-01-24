from flask import Flask, render_template_string, jsonify
import requests
import json
import os

app = Flask(__name__)

# URL's van de externe Timelimit server
SERVER_URL = "http://192.168.68.30:8080/time"
STATUS_URL = "http://192.168.68.30:8080/admin/status"
LOGS_URL = "http://192.168.68.30:8080/admin/logs"

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
        body { font-family: sans-serif; text-align: center; padding: 20px; background-color: #1c1c1c; color: white; }
        .container { max-width: 800px; margin: auto; }
        .status-box { font-size: 20px; margin-bottom: 20px; padding: 15px; border-radius: 8px; background: #2c2c2c; }
        .time { color: #03a9f4; font-weight: bold; font-size: 28px; }
        
        .grid { display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; }
        .panel { flex: 1; min-width: 300px; padding: 15px; border: 1px solid #444; border-radius: 8px; background: #111; }
        
        pre { text-align: left; background: #000; padding: 15px; color: #00ff00; overflow-y: auto; border-radius: 5px; font-size: 11px; height: 300px; border: 1px solid #333; }
        h1 { color: #fff; }
        h3 { color: #ccc; margin-top: 0; display: flex; justify-content: space-between; align-items: center; }
        
        button { background: #03a9f4; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        button:hover { background: #0288d1; }
        button:disabled { background: #555; }
        .log-error { color: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Timelimit Dashboard</h1>
        
        <div class="status-box">
            <div>Server: <span id="status-text">Laden...</span> | <span class="time" id="time-display">-- ms</span></div>
        </div>

        <div class="grid">
            <div class="panel">
                <h3>Systeem Status</h3>
                <pre id="admin-status">Wachten op data...</pre>
            </div>

            <div class="panel">
                <h3>
                    Server Logs 
                    <button id="log-btn" onclick="updateLogs()">Vernieuwen</button>
                </h3>
                <pre id="server-logs">Klik op vernieuwen om logs op te halen...</pre>
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

        async function updateLogs() {
            const btn = document.getElementById('log-btn');
            const logBox = document.getElementById('server-logs');
            btn.disabled = true;
            btn.innerText = "Laden...";
            
            try {
                const response = await fetch('./api/logs');
                const data = await response.json();
                
                if (data.error) {
                    logBox.innerHTML = `<span class="log-error">Fout: ${data.error}</span>`;
                } else {
                    // Logs zijn vaak een lijst of een lange string
                    logBox.innerText = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
                    // Scroll naar beneden voor de nieuwste logs
                    logBox.scrollTop = logBox.scrollHeight;
                }
            } catch (e) {
                logBox.innerHTML = `<span class="log-error">Netwerkfout bij ophalen logs.</span>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "Vernieuwen";
            }
        }

        setInterval(updateData, 5000);
        setInterval(updateAdminStatus, 30000); // Iets minder vaak voor status
        
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

@app.route('/api/logs')
def get_logs():
    password = get_server_password()
    try:
        r = requests.get(LOGS_URL, auth=('', password), timeout=5)
        # Sommige servers sturen tekst, anderen JSON. We proberen beide.
        try:
            return jsonify(r.json())
        except:
            return jsonify(r.text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8099, debug=False)