import http.server
import socketserver
import os
import json

# Configuratie
PORT = 8099
TIMELIMIT_SERVER_URL = "http://192.168.68.30:8080"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = self.get_template()
        self.wfile.write(html.encode("utf-8"))

    def get_template(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TimeLimit Control Panel</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 20px; margin: 0; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 20px; }
        
        .card { background: #1a1a1a; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .setup-box { background: #1a1a1a; border: 1px solid #03a9f4; padding: 30px; border-radius: 12px; text-align: center; }
        
        input { background: #222; border: 1px solid #444; color: #fff; padding: 12px; width: 80%; margin: 15px 0; border-radius: 6px; font-family: monospace; outline: none; }
        input:focus { border-color: #03a9f4; }
        
        button { background: #03a9f4; border: none; color: white; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        button:hover { background: #0288d1; transform: translateY(-1px); }
        button.secondary { background: #333; color: #ccc; border: 1px solid #444; margin-left: 10px; }
        
        #log { background: #000; color: #00ff00; padding: 15px; height: 200px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; border: 1px solid #333; border-radius: 8px; margin-top: 10px; }
        
        .status-badge { padding: 6px 14px; border-radius: 20px; font-size: 0.85em; font-weight: bold; text-transform: uppercase; }
        .online { background: rgba(76, 175, 80, 0.15); color: #4caf50; border: 1px solid #4caf50; }
        .offline { background: rgba(244, 67, 54, 0.15); color: #f44336; border: 1px solid #f44336; }
        
        .user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1