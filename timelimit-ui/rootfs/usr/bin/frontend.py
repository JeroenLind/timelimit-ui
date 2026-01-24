from flask import Flask, render_template_string, jsonify
import requests
import os

app = Flask(__name__)
SERVER_URL = "http://192.168.68.30:8080/time"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Timelimit UI</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 50px; background-color: #1c1c1c; color: white; }
        .status { font-size: 24px; margin-bottom: 20px; }
        .time { color: #03a9f4; font-weight: bold; font-size: 32px; }
    </style>
</head>
<body>
    <h1>Timelimit Server Check</h1>
    <div class="status">Huidige server status: <span id="status-text">Laden...</span></div>
    <div class="time" id="time-display">--</div>
    <script>
        async function updateData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                document.getElementById('status-text').innerText = "Online";
                document.getElementById('time-display').innerText = data.ms + " ms";
            } catch (e) {
                document.getElementById('status-text').innerText = "Offline";
            }
        }
        setInterval(updateData, 5000);
        updateData();
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

if __name__ == '__main__':
    # Belangrijk: gebruik 0.0.0.0 en de poort uit je config.yaml
    app.run(host='0.0.0.0', port=8099, debug=False)