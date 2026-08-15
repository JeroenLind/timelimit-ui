# Deployment Guide

## Overview

This document provides comprehensive instructions for deploying the TimeLimit Debug Server in various environments.

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Operating System | Windows 11, Linux, macOS | Windows 11, Ubuntu 22.04+ |
| Python | 3.11 | 3.12+ |
| Memory | 512 MB | 1 GB |
| Disk Space | 100 MB | 500 MB |
| Network | Port 8080 open | Port 8080 open |

### Python Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt
```

---

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd debug-server
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example configuration
copy .env.example .env  # Windows
cp .env.example .env    # Linux/macOS

# Edit .env with your configuration
notepad .env  # Windows
nano .env     # Linux/macOS
```

### 5. Generate Secret Key

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add the generated key to your `.env` file:

```env
SECRET_KEY=your_generated_secret_key_here
```

### 6. Start the Server

```bash
# Using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8080

# Using the run script
python run.py

# Using module entry point
python -m app
```

The server will be available at `http://localhost:8080`.

---

## Docker Deployment

### Using Docker

#### Build the Image

```bash
docker build -t timelimit-debug-server .
```

#### Run the Container

```bash
docker run -d \
  --name timelimit-server \
  -p 8080:8080 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/logs:/app/logs \
  timelimit-debug-server
```

#### Environment Variables in Docker

```bash
docker run -d \
  --name timelimit-server \
  -p 8080:8080 \
  -e SECRET_KEY=your_secret_key \
  -e ACCESS_TOKEN_EXPIRE_MINUTES=60 \
  -e LOG_LEVEL=INFO \
  timelimit-debug-server
```

### Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  timelimit-server:
    build: .
    container_name: timelimit-server
    ports:
      - "8080:8080"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - ACCESS_TOKEN_EXPIRE_MINUTES=60
      - LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
```

Run with Docker Compose:

```bash
# Create .env file with SECRET_KEY
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" > .env

# Start services
docker-compose up -d
```

---

## Production Deployment

### Reverse Proxy Setup (Nginx)

Create an Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd Service (Linux)

Create a systemd service file `/etc/systemd/system/timelimit-server.service`:

```ini
[Unit]
Description=TimeLimit Debug Server
After=network.target

[Service]
Type=simple
User=timelimit
Group=timelimit
WorkingDirectory=/opt/timelimit-server
Environment="PATH=/opt/timelimit-server/.venv/bin"
ExecStart=/opt/timelimit-server/.venv/bin/python -m app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable timelimit-server
sudo systemctl start timelimit-server
```

### Windows Service

Use NSSM (Non-Sucking Service Manager):

```powershell
# Download NSSM
# Install the service
nssm install TimeLimitServer "C:\path\to\python.exe" "-m app"
nssm start TimeLimitServer
```

---

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SECRET_KEY` | string | (required) | Secret key for JWT signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | 60 | Token expiration in minutes |
| `JWT_ALGORITHM` | string | HS256 | JWT signing algorithm |
| `BCRYPT_COST` | int | 12 | Bcrypt cost factor |
| `LOG_LEVEL` | string | INFO | Logging level |
| `LOG_FILE_PATH` | string | logs/debug-server.log | Log file path |
| `ENABLE_HTTPS` | bool | false | Enable HTTPS |
| `SERVER_HOST` | string | 0.0.0.0 | Server host |
| `SERVER_PORT` | int | 8080 | Server port |
| `MOCK_DATA_SEED` | int | 42 | Seed for reproducible mock data |
| `ENABLE_WEBSOCKET` | bool | true | Enable WebSocket support |
| `LONGPOLL_TIMEOUT_SECONDS` | int | 25 | Long-poll timeout |
| `RATE_LIMIT_ENABLED` | bool | true | Enable rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | int | 60 | Rate limit threshold |
| `LOG_MAX_BYTES` | int | 10485760 | Max log file size (10MB) |
| `LOG_BACKUP_COUNT` | int | 5 | Number of backup log files |
| `LOG_FORMAT` | string | json | Log format (json or console) |
| `TEST_MODE` | bool | false | Test mode (returns dummy data) |

### Mock Data Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_FAMILY_COUNT` | 1 | Number of families to generate |
| `MOCK_CHILD_COUNT` | 2 | Children per family |
| `MOCK_DEVICE_COUNT` | 3 | Devices per family |
| `MOCK_CATEGORY_COUNT` | 3 | Categories per child |
| `MOCK_APP_COUNT` | 10 | Apps per device |

---

## HTTPS Configuration

### Self-Signed Certificate (Development)

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Enable HTTPS in .env
ENABLE_HTTPS=true
```

### Let's Encrypt (Production)

```bash
# Install certbot
sudo apt install certbot

# Obtain certificate
sudo certbot certonly --standalone -d your-domain.com

# Update .env
ENABLE_HTTPS=true
```

---

## Load Balancing

### Multiple Server Instances

```bash
# Start multiple instances on different ports
uvicorn app.main:app --host 0.0.0.0 --port 8080 &
uvicorn app.main:app --host 0.0.0.0 --port 8081 &
uvicorn app.main:app --host 0.0.0.0 --port 8082 &
```

### Nginx Load Balancer

```nginx
upstream timelimit_backend {
    server localhost:8080;
    server localhost:8081;
    server localhost:8082;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://timelimit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Monitoring

### Health Checks

```bash
# Check server health
curl http://localhost:8080/health

# Check readiness
curl http://localhost:8080/ready
```

### Log Monitoring

```bash
# View logs
tail -f logs/debug-server.log

# Search for errors
grep "ERROR" logs/debug-server.log

# Analyze logs
python scripts/analyze_logs.py
```

### Prometheus Metrics (Future)

Add a metrics endpoint for Prometheus scraping:

```python
@app.get("/metrics")
async def metrics():
    # Return Prometheus-formatted metrics
    pass
```

---

## Backup and Recovery

### State Persistence (Future Enhancement)

Currently, the server uses in-memory state. For production, consider:

1. **SQLite**: Lightweight file-based database
2. **PostgreSQL**: Full-featured relational database
3. **Redis**: In-memory data structure store

### Log Backup

```bash
# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# Restore logs
tar -xzf logs-backup-20240101.tar.gz -C /
```

---

## Scaling

### Horizontal Scaling

For horizontal scaling, use a shared state backend:

1. **Redis**: For session storage and caching
2. **PostgreSQL**: For persistent data storage
3. **Message Queue**: For async processing (Celery, RabbitMQ)

### Vertical Scaling

Increase server resources:

- CPU: More cores for concurrent requests
- Memory: More RAM for larger in-memory state
- Disk: More space for logs and potential persistence

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port 8080
netstat -ano | findstr :8080  # Windows
lsof -i :8080                 # Linux/macOS

# Kill the process
taskkill /PID <pid> /F        # Windows
kill -9 <pid>                 # Linux/macOS
```

#### Permission Denied

```bash
# Check file permissions
ls -la logs/

# Fix permissions
chmod 755 logs/
```

#### Module Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### Memory Issues

```bash
# Check memory usage
free -h  # Linux/macOS
Get-Process | Sort-Object WS -Descending  # Windows PowerShell

# Increase swap (Linux)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Log Analysis

Use the provided log analysis script:

```bash
python scripts/analyze_logs.py --help
```

---

## Security Considerations

### Production Checklist

- [ ] Set a strong `SECRET_KEY`
- [ ] Enable HTTPS (`ENABLE_HTTPS=true`)
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Enable rate limiting
- [ ] Use environment variables for secrets
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity

### Firewall Configuration

```bash
# Allow only necessary ports
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw enable
```

---

## Rollback Procedures

### Version Rollback

```bash
# Stop current server
pkill -f "python -m app"

# Checkout previous version
git checkout <previous-tag>

# Reinstall dependencies
pip install -r requirements.txt

# Start server
python run.py
```

### Configuration Rollback

```bash
# Restore previous .env
cp .env.backup .env

# Restart server
systemctl restart timelimit-server
```

---

## Maintenance Schedule

| Task | Frequency | Description |
|------|-----------|-------------|
| Log rotation | Daily | Rotate logs when > 10MB |
| Security updates | Weekly | Update Python and dependencies |
| Backup verification | Weekly | Verify backup integrity |
| Performance review | Monthly | Review server performance |
| Dependency audit | Monthly | Check for security vulnerabilities |

---

## Support

For issues and questions:

1. Check the logs: `logs/debug-server.log`
2. Review this documentation
3. Check GitHub issues
4. Contact the development team
