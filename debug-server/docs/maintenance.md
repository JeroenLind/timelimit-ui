# Maintenance Guide

## Overview

This document provides comprehensive maintenance procedures for the TimeLimit Debug Server, including routine tasks, troubleshooting, and upgrade procedures.

---

## Routine Maintenance Tasks

### Daily Tasks

#### Log Monitoring

Check for errors and warnings in the logs:

```bash
# View recent errors
grep "ERROR" logs/debug-server.log | tail -20

# View recent warnings
grep "WARNING" logs/debug-server.log | tail -20

# Count errors in last 24 hours
grep "ERROR" logs/debug-server.log | grep "$(date -d 'yesterday' +%Y-%m-%d)" | wc -l
```

#### Health Check

Verify server health:

```bash
curl -s http://localhost:8080/api/v1/health | jq .
```

Expected response:
```json
{
  "status": "healthy"
}
```

#### Disk Space

Check available disk space:

```bash
# Linux/macOS
df -h /

# Windows PowerShell
Get-PSDrive C | Select-Object Used, Free
```

### Weekly Tasks

#### Log Rotation

Logs are automatically rotated when they exceed 10MB (configurable via `LOG_MAX_BYTES`). Verify rotation:

```bash
# Check log files
ls -la logs/

# Expected output:
# debug-server.log
# debug-server.log.1
# debug-server.log.2
# ... up to LOG_BACKUP_COUNT (default: 5)
```

#### Dependency Updates

Check for outdated dependencies:

```bash
pip list --outdated
```

Update dependencies:

```bash
pip install --upgrade -r requirements.txt
```

#### Security Audit

Run security checks:

```bash
# Check for security vulnerabilities
pip install safety
safety check -r requirements.txt
```

### Monthly Tasks

#### Performance Review

Analyze server performance:

```bash
# Run log analysis
python scripts/analyze_logs.py --analyze-performance

# Check response times
python scripts/analyze_logs.py --response-times
```

#### Backup Verification

Verify backup integrity:

```bash
# Check log backup files
ls -la logs/*.tar.gz 2>/dev/null || echo "No backups found"

# Verify backup integrity (if backups exist)
tar -tzf logs-backup-*.tar.gz > /dev/null && echo "Backup OK"
```

#### Configuration Review

Review configuration settings:

```bash
# Check current configuration
python -c "from app.core.config import get_settings; print(get_settings().model_dump())"
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Server Won't Start

**Symptoms**: Server exits immediately with error

**Diagnosis**:
```bash
# Check error logs
tail -50 logs/debug-server.log

# Check for import errors
python -c "import app"
```

**Solution**:
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python version
python --version  # Must be 3.11+
```

#### Issue: Authentication Failures

**Symptoms**: 401 Unauthorized errors

**Diagnosis**:
```bash
# Check token validity
python -c "
from app.core.security import validate_token
token = 'your_token_here'
result = validate_token(token)
print('Valid' if result else 'Invalid')
"

# Check secret key
echo $SECRET_KEY
```

**Solution**:
1. Verify `SECRET_KEY` is set correctly in `.env`
2. Check token hasn't expired
3. Verify token format

#### Issue: Rate Limiting

**Symptoms**: 429 Too Many Requests

**Diagnosis**:
```bash
# Check rate limit configuration
python -c "from app.core.config import get_settings; s = get_settings(); print(f'Rate limit: {s.rate_limit_requests_per_minute}')"
```

**Solution**:
```bash
# Temporarily disable rate limiting (development only)
echo "RATE_LIMIT_ENABLED=false" >> .env
```

#### Issue: Gzip Compression Issues

**Symptoms**: Malformed request bodies, decompression errors

**Diagnosis**:
```bash
# Check if client is sending gzip
curl -H "Content-Encoding: gzip" --data-binary @compressed.json http://localhost:8080/api/v1/sync/push-actions
```

**Solution**:
1. Verify client is properly compressing request body
2. Check `Content-Encoding: gzip` header is present
3. Verify gzip middleware is enabled

#### Issue: WebSocket Connection Failures

**Symptoms**: Socket.IO connection refused or disconnects

**Diagnosis**:
```bash
# Check if WebSocket is enabled
python -c "from app.core.config import get_settings; s = get_settings(); print(f'WebSocket: {s.enable_websocket}')"

# Check server logs for WebSocket errors
grep -i websocket logs/debug-server.log
```

**Solution**:
1. Verify `ENABLE_WEBSOCKET=true` in `.env`
2. Check firewall allows WebSocket connections
3. Verify client is using correct transport (WebSocket)

#### Issue: Memory Leaks

**Symptoms**: Increasing memory usage over time

**Diagnosis**:
```bash
# Monitor memory usage
watch -n 5 'ps aux | grep python | grep -v grep'

# Check state size
python -c "
from app.core.state import get_state_manager
import asyncio

async def check_state():
    sm = await get_state_manager()
    print(f'Families: {len(sm.families)}')
    print(f'Users: {len(sm.users)}')
    print(f'Devices: {len(sm.devices)}')
    print(f'Categories: {len(sm.categories)}')

asyncio.run(check_state())
"
```

**Solution**:
1. Restart server to clear state
2. Check for memory leaks in custom code
3. Consider implementing state cleanup for old data

### Error Code Reference

| Error | HTTP Code | Description | Resolution |
|-------|-----------|-------------|------------|
| `UNAUTHORIZED` | 401 | Invalid or missing token | Check token validity, SECRET_KEY |
| `FORBIDDEN` | 403 | Access denied | Check permissions, token scope |
| `NOT_FOUND` | 404 | Resource not found | Verify resource ID exists |
| `CONFLICT` | 409 | Duplicate resource | Check for existing resource |
| `RATE_LIMITED` | 429 | Too many requests | Wait or reduce request rate |
| `BAD_REQUEST` | 400 | Invalid request | Check request format |
| `VALIDATION_ERROR` | 400 | Validation failed | Fix input data |
| `INTERNAL_ERROR` | 500 | Server error | Check logs, restart server |

---

## Upgrading

### Version Upgrade Procedure

#### 1. Backup Current Version

```bash
# Create backup
tar -czf backup-$(date +%Y%m%d).tar.gz \
    .env \
    logs/ \
    --exclude='logs/*.log' \
    --exclude='logs/*.log.*'
```

#### 2. Pull Latest Changes

```bash
git fetch origin
git checkout <new-version-tag>
```

#### 3. Update Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Update Configuration

```bash
# Check for new environment variables
diff .env.example .env
```

#### 5. Run Migrations (if applicable)

```bash
# Check for migration scripts
ls scripts/migrations/
```

#### 6. Restart Server

```bash
# Graceful restart
systemctl restart timelimit-server  # Linux
nssm restart TimeLimitServer        # Windows
```

#### 7. Verify Upgrade

```bash
# Check version
curl http://localhost:8080/api/v1/health

# Run tests
pytest tests/ -v
```

### Rollback Procedure

If upgrade fails:

```bash
# Stop server
systemctl stop timelimit-server

# Restore previous version
git checkout <previous-tag>

# Restore configuration
cp .env.backup .env

# Restart server
systemctl start timelimit-server
```

---

## Adding New Endpoints

### Step-by-Step Guide

#### 1. Create Model

Create a new model file in `app/models/`:

```python
# app/models/new_resource.py
from pydantic import BaseModel

class NewResourceRequest(BaseModel):
    name: str
    value: int

class NewResourceResponse(BaseModel):
    id: str
    name: str
    value: int
```

#### 2. Create Service

Create a service file in `app/services/`:

```python
# app/services/new_resource_service.py
from app.models.new_resource import NewResourceRequest, NewResourceResponse
from app.core.state import StateManager

class NewResourceService:
    def __init__(self, state: StateManager = None):
        self.state = state
    
    async def create(self, request: NewResourceRequest) -> NewResourceResponse:
        # Implementation
        pass
```

#### 3. Create Controller

Create a controller file in `app/api/`:

```python
# app/api/new_resource.py
from fastapi import APIRouter
from app.models.new_resource import NewResourceRequest, NewResourceResponse

router = APIRouter()

@router.post("/new-resource", response_model=NewResourceResponse)
async def create_new_resource(request: NewResourceRequest):
    # Implementation
    pass
```

#### 4. Register Router

Update `app/api/__init__.py`:

```python
from app.api.new_resource import router as new_resource_router

api_router.include_router(new_resource_router, prefix="/api/v1")
```

#### 5. Update Models Export

Update `app/models/__init__.py`:

```python
from app.models.new_resource import NewResourceRequest, NewResourceResponse
```

#### 6. Add Tests

Create test file `tests/test_new_resource_endpoints.py`:

```python
from tests.client import TestClient

def test_create_new_resource(client: TestClient):
    response = client.create_new_resource({"name": "test", "value": 123})
    assert response["status"] == 0
```

#### 7. Update Documentation

Update `docs/api.md` with the new endpoint documentation.

---

## Updating Mock Data

### Mock Data Generator

The `MockDataGenerator` class in `app/services/mock_data.py` generates reproducible mock data.

#### Configuration

Update mock data parameters in `.env`:

```env
MOCK_FAMILY_COUNT=2
MOCK_CHILD_COUNT=3
MOCK_DEVICE_COUNT=5
MOCK_CATEGORY_COUNT=5
MOCK_APP_COUNT=20
```

#### Custom Mock Data

Modify the generator in `app/services/mock_data.py`:

```python
class MockDataGenerator:
    def generate_family(self, family_id: str) -> Dict[str, Any]:
        # Customize family data
        return {
            "id": family_id,
            "name": f"Family {family_id}",
            # Add custom fields
        }
```

#### Regenerate Mock Data

```bash
# Restart server to regenerate mock data
systemctl restart timelimit-server
```

---

## Log Management

### Log Analysis Script

Use the provided log analysis script:

```bash
# Show usage
python scripts/analyze_logs.py --help

# Analyze errors
python scripts/analyze_logs.py --analyze-errors

# Generate report
python scripts/analyze_logs.py --report
```

### Log Rotation Configuration

Log rotation is handled by Python's `RotatingFileHandler`:

```python
# app/utils/logger.py
handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=LOG_MAX_BYTES,  # Default: 10MB
    backupCount=LOG_BACKUP_COUNT  # Default: 5
)
```

### Custom Log Retention

To change log retention:

```bash
# Edit .env
LOG_MAX_BYTES=20971520  # 20MB
LOG_BACKUP_COUNT=10     # Keep 10 backup files
```

---

## Performance Tuning

### Server Configuration

#### Worker Processes

For production, use multiple workers:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

#### Timeout Settings

Adjust timeout settings in `.env`:

```env
LONGPOLL_TIMEOUT_SECONDS=30
```

### Memory Optimization

#### State Cleanup

Implement periodic state cleanup:

```python
# Add to state management
async def cleanup_old_data(self, max_age_hours: int = 24):
    # Remove old entries
    pass
```

#### Connection Limits

Configure connection limits:

```python
# In main.py
app = FastAPI(
    # ...
    lifespan=lifespan,
    # Add connection limits
)
```

---

## Security Maintenance

### Regular Security Tasks

#### 1. Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

#### 2. Check for Vulnerabilities

```bash
pip install safety
safety check -r requirements.txt
```

#### 3. Rotate Secrets

```bash
# Generate new secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env
# Restart server
```

#### 4. Review Access Logs

```bash
# Check for suspicious activity
grep -i "error\|warning\|failed" logs/debug-server.log
```

---

## Monitoring and Alerting

### Health Check Endpoint

```bash
# Monitor with cron
*/5 * * * * curl -f http://localhost:8080/api/v1/health || systemctl restart timelimit-server
```

### Log Monitoring

Set up log monitoring with tools like:

- **Filebeat** + **Elasticsearch** + **Kibana**
- **Fluentd** + **Prometheus** + **Grafana**
- **Splunk**

### Alerting Rules

Configure alerts for:

- Server health check failures
- High error rates
- Memory usage > 80%
- Disk usage > 90%
- Response time > 5 seconds

---

## Backup and Recovery

### Backup Strategy

#### Daily Backups

```bash
# Create daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf backups/debug-server-$DATE.tar.gz \
    .env \
    --exclude='*.log' \
    --exclude='logs/*'
```

#### Configuration Backup

```bash
# Backup configuration only
cp .env .env.backup
cp -r config/ config.backup/
```

### Recovery Procedure

#### 1. Stop Server

```bash
systemctl stop timelimit-server
```

#### 2. Restore Files

```bash
# Restore configuration
cp .env.backup .env

# Restore data (if using persistent storage)
tar -xzf backup.tar.gz
```

#### 3. Start Server

```bash
systemctl start timelimit-server
```

#### 4. Verify Recovery

```bash
curl http://localhost:8080/api/v1/health
```

---

## Documentation Updates

### Keeping Documentation Current

When making changes, update documentation:

1. **API changes**: Update `docs/api.md`
2. **Security changes**: Update `docs/security.md`
3. **Deployment changes**: Update `docs/deployment.md`
4. **Configuration changes**: Update `docs/maintenance.md`

### Documentation Review

Review documentation quarterly:

```bash
# Check documentation coverage
grep -r "TODO" docs/
```

---

## Support and Contact

### Emergency Contacts

- **Primary**: Development Team Lead
- **Secondary**: DevOps Team

### Support Channels

1. **Logs**: `logs/debug-server.log`
2. **Documentation**: `docs/` directory
3. **Issues**: GitHub Issues
4. **Emergency**: Contact support team

### Escalation Procedure

1. **Level 1**: Check logs and documentation
2. **Level 2**: Restart server, check configuration
3. **Level 3**: Rollback to previous version
4. **Level 4**: Contact development team