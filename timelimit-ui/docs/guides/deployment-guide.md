# Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [Deployment Options](#deployment-options)
3. [Home Assistant Deployment](#home-assistant-deployment)
4. [Standalone Deployment](#standalone-deployment)
5. [Docker Deployment](#docker-deployment)
6. [Environment Variables](#environment-variables)
7. [Reverse Proxy Configuration](#reverse-proxy-configuration)
8. [SSL/TLS Configuration](#ssltls-configuration)
9. [Data Persistence](#data-persistence)
10. [Troubleshooting](#troubleshooting)
11. [Monitoring](#monitoring)

---

## Overview

Dashboard V2 is a Flask-based web application that can be deployed in multiple environments. This guide covers all deployment options and configurations.

### System Requirements

- Python 3.8 or higher
- SQLite3
- 100MB disk space minimum
- Network access to TimeLimit server

---

## Deployment Options

Dashboard V2 can be deployed in three primary environments:

1. **Home Assistant Add-on** - Integrated with Home Assistant
2. **Standalone** - Running directly on a laptop or server
3. **Docker** - Containerized deployment

---

## Home Assistant Deployment

### Installation

1. Add the repository to Home Assistant:
   - Go to **Supervisor** → **Add-on Store**
   - Click the three dots menu → **Repositories**
   - Add the repository URL

2. Install the Dashboard V2 add-on:
   - Find Dashboard V2 in the add-on store
   - Click **Install**
   - Wait for installation to complete

3. Configure the add-on:
   - Set options in the **Configuration** tab
   - Save configuration

4. Start the add-on:
   - Click **Start**
   - Wait for the log to show "Dashboard V2 application starting"

### Configuration Options

```json
{
  "log_level": "info",
  "flask_host": "0.0.0.0",
  "flask_port": 8099,
  "flask_debug": false
}
```

| Option | Description | Default |
|--------|-------------|---------|
| `log_level` | Logging level (debug, info, warning, error) | `info` |
| `flask_host` | Server host | `0.0.0.0` |
| `flask_port` | Server port | `8099` |
| `flask_debug` | Enable debug mode | `false` |

### Ingress Configuration

Dashboard V2 uses s6-overlay for process management in Home Assistant:

```
/etc/s6-overlay/
└── s6-rc.d/
    ├── dashboard-v2/
    │   ├── run
    │   └── type
    └── user/
        └── contents.d/
            └── web-server
```

### Home Assistant Integration

The add-on integrates with Home Assistant's:
- Supervisor for management
- Ingress for web interface access
- SSL for secure connections
- Log viewer for debugging

---

## Standalone Deployment

### Prerequisites

- Python 3.8 or higher
- SQLite3
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/timelimit-ui/timelimit-ui.git
cd timelimit-ui
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export FLASK_HOST=0.0.0.0
export FLASK_PORT=8099
export FLASK_DEBUG=false
export LOG_LEVEL=info
```

4. Run the application:
```bash
python app.py
```

### Running as a Service

#### Linux systemd Service

Create `/etc/systemd/system/dashboard-v2.service`:

```ini
[Unit]
Description=Dashboard V2
After=network.target

[Service]
Type=simple
User=dashboard
WorkingDirectory=/opt/dashboard-v2
Environment="FLASK_HOST=0.0.0.0"
Environment="FLASK_PORT=8099"
Environment="FLASK_DEBUG=false"
Environment="LOG_LEVEL=info"
ExecStart=/usr/bin/python3 /opt/dashboard-v2/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dashboard-v2
sudo systemctl start dashboard-v2
```

#### Windows

Run as a scheduled task or use a process manager like NSSM:

```cmd
nssm install DashboardV2 "C:\Python39\python.exe" "C:\dashboard-v2\app.py"
nssm start DashboardV2
```

#### macOS

Using launchd:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.timelimit.dashboardv2</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/usr/local/bin/dashboard-v2/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

---

## Docker Deployment

### Docker Image

Build the image:
```bash
docker build -t dashboard-v2 .
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  dashboard-v2:
    build: .
    ports:
      - "8099:8099"
    volumes:
      - ./data:/data
    environment:
      - FLASK_HOST=0.0.0.0
      - FLASK_PORT=8099
      - FLASK_DEBUG=false
      - LOG_LEVEL=info
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

### Docker Commands

```bash
# View logs
docker logs -f dashboard-v2

# Stop container
docker stop dashboard-v2

# Restart container
docker restart dashboard-v2

# Remove container
docker rm dashboard-v2
```

---

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FLASK_HOST` | Server host | `0.0.0.0` | No |
| `FLASK_PORT` | Server port | `8099` | No |
| `FLASK_DEBUG` | Debug mode | `false` | No |
| `LOG_LEVEL` | Logging level | `info` | No |
| `DATABASE_PATH` | SQLite database path | `/data/timelimit_ui_storage.json` | No |
| `LOG_FILE_PATH` | Log file path | `/data/logs/dashboard.log` | No |
| `LOG_MAX_BYTES` | Max log file size | `10485760` (10MB) | No |
| `LOG_BACKUP_COUNT` | Log backup count | `5` | No |
| `SKIP_PORT_CHECK` | Skip port check | `false` | No |

### Setting Environment Variables

#### Linux/macOS
```bash
export FLASK_HOST=0.0.0.0
export FLASK_PORT=8099
```

#### Windows (PowerShell)
```powershell
$env:FLASK_HOST="0.0.0.0"
$env:FLASK_PORT="8099"
```

#### Windows (Command Prompt)
```cmd
set FLASK_HOST=0.0.0.0
set FLASK_PORT=8099
```

---

## Reverse Proxy Configuration

### Nginx

```nginx
server {
    listen 443 ssl;
    server_name dashboard.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8099;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caddy

```caddy
dashboard.example.com {
    reverse_proxy localhost:8099
    tls you@example.com
}
```

### Traefik

```yaml
http:
  routers:
    dashboard:
      rule: Host(`dashboard.example.com`)
      service: dashboard
      tls: {}
  services:
    dashboard:
      loader:
        passHostHeader: true
      url: http://localhost:8099
```

---

## SSL/TLS Configuration

For production deployments, use HTTPS:

1. **Let's Encrypt** with reverse proxy
2. **Self-signed certificates** for local use
3. **Home Assistant SSL** for HA add-on

### Generating Self-Signed Certificates

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

---

## Data Persistence

### Database Location

- Default: `/data/timelimit_ui_storage.json`
- Configurable via `DATABASE_PATH` environment variable

### Log Files

- Default: `/data/logs/dashboard.log`
- Configurable via `LOG_FILE_PATH` environment variable

### Backup

Create a backup of the database:
```bash
cp /data/timelimit_ui_storage.json /backup/timelimit_ui_storage_$(date +%Y%m%d).json
```

### Data Directory Structure

```
/data/
├── timelimit_ui_storage.json    # Main database
├── auth_backup.json             # Auth token backup
└── logs/
    ├── dashboard.log            # Main log file
    └── dashboardV2-*.log        # Timestamped log files
```

---

## Troubleshooting

### Port Already in Use

Error: `Port 8099 on host 0.0.0.0 is already in use`

Solution:
```bash
# Find process using port 8099
lsof -i :8099

# Kill the process or change port
export FLASK_PORT=8100
```

### Database Lock

Error: `database is locked`

Solution:
```bash
# Close all instances of the app
# Remove lock file if exists
rm /data/timelimit_ui_storage.json-wal
rm /data/timelimit_ui_storage.json-shm
```

### Authentication Issues

1. Clear session: Use the "Clear Session" button in the dashboard
2. Clear all data: Use the "Clear All Data" button
3. Restart the application

### Server Connection Issues

1. Check server selection in the dashboard
2. Verify network connectivity
3. Check firewall settings
4. Review server check logs

### Docker Issues

```bash
# Check container status
docker ps -a

# View container logs
docker logs dashboard-v2

# Restart container
docker restart dashboard-v2

# Rebuild image
docker-compose build --no-cache
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8099/health
```

Expected response:
```json
{"status": "healthy"}
```

### Log Monitoring

```bash
# View logs
tail -f /data/logs/dashboard.log

# Search for errors
grep -i error /data/logs/dashboard.log

# Count log entries by level
grep -o '"level":"[^"]*"' /data/logs/dashboard.log | sort | uniq -c
```

### Server Checks

The application performs periodic server checks. View results in the dashboard or check the `server_checks` table in the database.

### Resource Monitoring

```bash
# Monitor CPU and memory
top -p $(pgrep -f "python.*app.py")

# Check disk usage
df -h /data

# Check database size
du -h /data/timelimit_ui_storage.json
```

---

## Security Considerations

### Production Deployment Checklist

- [ ] Use HTTPS (reverse proxy with SSL)
- [ ] Set strong FLASK_SECRET_KEY environment variable
- [ ] Configure firewall to restrict access
- [ ] Enable log rotation
- [ ] Set up regular backups
- [ ] Monitor logs for suspicious activity
- [ ] Keep dependencies updated

### Firewall Configuration

```bash
# Allow only local access
ufw allow from 192.168.0.0/16 to any port 8099

# Or use reverse proxy for external access
ufw allow 443/tcp