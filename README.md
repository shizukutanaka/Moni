# Moni System Monitor

Moni provides system monitoring with comprehensive security controls for personal and organizational use.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Security: Hardened](https://img.shields.io/badge/security-hardened-green.svg)](SECURITY.md)

[日本語版](README_JP.md) | [Security Policy](SECURITY.md)

---

## Overview

Moni is a hardened system monitoring solution designed for environments where security, stability, and performance are critical. Built with defense-in-depth principles, it provides real-time metrics without compromising system integrity.

### Core Capabilities

- **Real-Time Monitoring** - CPU, memory, GPU, network, disk I/O, temperatures
- **Security Controls** - AES-256-GCM encryption, input validation, rate limiting, audit logging
- **Strict Validation** - All inputs verified, operations sandboxed, communications encrypted
- **Role-Based Access** - RBAC, TOTP 2FA, HMAC-signed logs, compliance frameworks (ISO 27001, NIST CSF)
- **Resource Efficiency** - Minimal footprint, intelligent caching, efficient data structures
- **Fault Recovery** - Error recovery, graceful degradation, controlled failover

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04 |
| **CPU** | 2 cores @ 2.0 GHz | 4+ cores @ 2.5 GHz |
| **RAM** | 4 GB | 8+ GB |
| **Storage** | 1 GB free (SSD preferred) | 5+ GB free (NVMe SSD) |
| **Python** | 3.10+ | 3.12 |
| **Network** | Not required | Optional (for diagnostics) |

### Optional Components

- **GPU Monitoring**: NVIDIA GPU with NVML drivers (CUDA 11.0+)
- **Advanced Metrics**: SMART-capable drives, temperature sensors
- **Network Diagnostics**: Unrestricted ICMP for ping tests

---

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd moni

# Create isolated environment
python3 -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Install Moni
pip install -e .

# Verify installation
moni --version
```

### First Run

```bash
# Launch with default settings
moni

# Launch with security hardening
moni --secure

# Launch with specific profile
moni --profile gaming

# Validate configuration
moni --validate-config

# Run security audit
moni --security-audit
```

- **Linux/macOS**: `~/.config/moni/`
- **Windows**: `%APPDATA%\moni\`

---

## Billing (Stripe Subscription)

Moni provides a production-grade Stripe billing system with **hybrid subscription + usage-based metering** for scalable SaaS revenue.

### Pricing Tiers

**Essential** ($29/month)
- Single endpoint monitoring
- 7-day metrics retention
- 100 alerts/month
- Basic dashboards
- Community support

**Professional** ($99/month)
- 10 endpoints
- 30-day retention
- 1,000 alerts/month
- RBAC + compliance exports
- Email support

**Enterprise** ($299/month + usage)
- Unlimited endpoints ($10/endpoint beyond 10)
- 90-day retention (extendable)
- Unlimited alerts
- Full security suite (IDS, 2FA, encryption)
- Priority support + SLA

### Key Features

✅ **Subscription Management**
- Checkout with trial periods
- Upgrade/downgrade with proration
- Subscription pause/resume
- Billing portal for self-service

✅ **Usage-Based Metering**
- Endpoint tracking
- API call metering
- Alert volume monitoring
- Automatic Stripe reporting

✅ **Feature Gating**
- Tier-based access control
- Quota enforcement
- Soft/hard limits
- Usage warnings

✅ **Advanced Billing**
- Proration handling
- Invoice preview
- Payment recovery
- Webhook event processing

### Configuration

#### Environment Variables

```bash
export MONI_STRIPE_SECRET_KEY=sk_live_xxx
export MONI_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
export MONI_STRIPE_WEBHOOK_SECRET=whsec_xxx
export MONI_STRIPE_SUCCESS_URL=https://example.com/billing/success
export MONI_STRIPE_CANCEL_URL=https://example.com/billing/cancel
export MONI_STRIPE_CURRENCY=usd
```

#### Tier Configuration

Tiers are defined in `configs/billing_tiers.yaml`:

```yaml
tiers:
  essential:
    stripe_price_id: price_essential_monthly
    base_price: 29.00
    features:
      endpoints:
        limit: 1
      retention_days:
        limit: 7
      rbac:
        enabled: false
```

### API Endpoints

#### Subscription Management

```bash
# Create checkout session
POST /checkout
{
  "tier": "professional",
  "email": "user@example.com"
}

# Get subscription
GET /subscription/{customer_id}

# Upgrade subscription
POST /subscription/{customer_id}/upgrade
{
  "price_id": "price_enterprise_monthly",
  "prorate": true
}

# Downgrade subscription
POST /subscription/{customer_id}/downgrade
{
  "price_id": "price_essential_monthly",
  "at_period_end": true
}

# Preview plan change
GET /subscription/{customer_id}/preview-change?new_price_id=price_xxx

# Pause subscription
POST /subscription/{customer_id}/pause
{
  "resumes_at": "2025-11-01T00:00:00Z"
}

# Resume subscription
POST /subscription/{customer_id}/resume

# Access billing portal
POST /portal
{
  "customer_id": "cus_xxx",
  "return_url": "https://example.com/dashboard"
}
```

#### Webhooks

Configure Stripe webhooks to `https://<your-domain>/webhook`:

Required events:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

### Usage Tracking

```python
from moni.billing.metering import UsageMeter
from moni.billing.feature_gate import FeatureGate

# Track usage
meter = UsageMeter()
meter.record_endpoint_usage("cus_abc123", endpoint_count=5)
meter.record_api_call("cus_abc123")
meter.flush_to_stripe()  # Report to Stripe

# Enforce quotas
gate = FeatureGate("cus_abc123")
if not gate.can_add_endpoint(current_count=5):
    raise QuotaExceededError("Endpoint limit reached")

# Check features
if gate.has_feature("rbac"):
    enable_rbac_features()
```

### Deployment

```bash
# Launch billing API
moni-billing-api

# Or with uvicorn
uvicorn moni.billing_api:app --host 0.0.0.0 --port 8080

# Docker deployment
docker run -d \
  -e MONI_STRIPE_SECRET_KEY=sk_live_xxx \
  -e MONI_STRIPE_PUBLISHABLE_KEY=pk_live_xxx \
  -e MONI_STRIPE_WEBHOOK_SECRET=whsec_xxx \
  -p 8080:8080 \
  moni:latest moni-billing-api
```

**Production Recommendations**:
- Run behind reverse proxy (nginx/Envoy) with HTTPS
- Use PostgreSQL instead of JSON file storage for multi-node setups
- Enable Stripe Tax for international sales
- Implement dunning management for payment failures
- Monitor webhook processing with alerts

### Testing

```bash
# Use Stripe test keys
export MONI_STRIPE_SECRET_KEY=sk_test_xxx

# Test cards
4242424242424242  # Success
4000000000000002  # Decline
4000002500003155  # 3DS authentication required
```

---

## Usage

### Command Line Interface

```bash
{{ ... }}
# Core Operations
moni                                    # Start monitoring
moni --mode daemon                      # Run as background service
moni --mode export                      # Export metrics to file
moni --validate-config                  # Validate configuration
moni --security-audit                   # Run security assessment

# Profile Management
moni --profile gaming                   # Gaming profile (500ms refresh)
moni --profile development              # Development profile
moni --profile minimal                  # Minimal resource usage

# Export Operations
moni --mode export --export-format json --export-file report.json
moni --mode export --export-format csv --export-file data.csv
moni --mode export --export-format html --export-file dashboard.html

# Security Options
moni --secure                           # Enable all security features
moni --disable-alerts                   # Suppress alert notifications
moni --log-level debug                  # Detailed logging

# Advanced
moni --reset-config                     # Reset to defaults
moni --config-path /custom/path.json    # Custom config location
```

### Configuration Profiles

**Gaming Profile** - Optimized for real-time performance monitoring
```bash
moni --profile gaming
```
- Refresh: 500ms (2 FPS)
- Metrics: CPU, GPU, memory, temperatures
- Alerts: Minimized during fullscreen

**Development Profile** - Comprehensive metrics for developers
```bash
moni --profile development
```
- Refresh: 2000ms
- Metrics: All available
- Logging: Enabled with 5s intervals

**Minimal Profile** - Essential metrics only
```bash
moni --profile minimal
```
- Refresh: 3000ms
- Metrics: CPU, memory, uptime
- Resource usage: <50MB RAM, <1% CPU

---

## Security

### Security Architecture

- **Encryption at Rest**: AES-256-GCM for all configuration data
- **Input Validation**: Comprehensive sanitization on all user inputs
- **Path Traversal Protection**: Sandboxed file operations
- **Command Injection Prevention**: Validated subprocess execution
- **Rate Limiting**: Built-in DoS protection
- **Audit Logging**: HMAC-signed tamper-evident logs
- **TOTP 2FA**: Optional multi-factor authentication
- **RBAC**: Role-based access control for enterprise deployments

### Compliance

- **ISO 27001**: Information security management
- **NIST Cybersecurity Framework**: Security controls implementation
- **GDPR**: Data protection and privacy principles
- **FIPS 140-2**: Cryptographic module standards

### 2025年セキュリティトレンド対応

Moniは2025年の最新セキュリティトレンドに対応しています：

- **AI活用攻撃対策**: 生成AIを悪用した攻撃への防御強化
- **ゼロデイ攻撃検知**: 未知脆弱性の迅速検知システム
- **ゼロトラストセキュリティ**: 全アクセス検証とマイクロセグメンテーション
- **エンドポイント強化**: EDR/EPP統合による包括的保護
- **クラウドセキュリティ**: IAMとCASB連携による統合管理

### DevOpsツール統合

Moniは人気のDevOpsツールとシームレスに連携：

- **ClickUp/Jira統合**: プロジェクト管理と監視アラートの自動同期
- **Slack通知**: リアルタイムアラートとコラボレーション機能
- **GitHub連携**: バージョン管理と監視データの統合
- **Docker監視**: コンテナ化環境の詳細監視機能

---

## Monitoring Metrics

### System Metrics

| Category | Metrics | Update Frequency |
|----------|---------|------------------|
| **CPU** | Overall %, per-core %, load average, frequency, temperature | Real-time |
| **Memory** | RAM usage, swap usage, available, paging activity | Real-time |
| **GPU** | Utilization %, memory usage, temperature, fan speed, power | Real-time |
| **Disk** | Read/write speeds, utilization %, SMART health | 5 seconds |
| **Network** | Upload/download speeds, connections, interface status | Real-time |
| **System** | Uptime, battery status, temperatures, fan speeds | 10 seconds |

### Alert Configuration

Alerts trigger when metrics exceed configurable thresholds:

```json
{
  "automation": {
    "alerts": {
      "enabled": true,
      "cooldown_seconds": 60,
      "thresholds": {
        "cpu_percent": 85.0,
        "memory_percent": 90.0,
        "gpu_temperature_celsius": 83.0,
        "disk_usage_percent": 95.0
      }
    }
  }
}
```

---

## Data Export

### Secure Output Directory

- **Configure directory**: Use `configure_export_directory()` or the CLI flag `--export-dir` to select a writable location such as `~/.moni/exports`.
- **Sandboxed writes**: All exports are constrained within the configured directory to mitigate path traversal.
- **Validation**: Filenames must be ASCII-safe and use approved extensions (`.json`, `.csv`, `.html`, `.gz`).

### Export Formats

```bash
# JSON (full metadata)
moni --mode export --export-format json --export-file metrics.json

# CSV (spreadsheet analysis)
moni --mode export --export-format csv --export-file data.csv

# HTML (dashboard view)
moni --mode export --export-format html --export-file report.html
```

### Compressed Exports

```python
report_path = network_monitor.export_network_data(
    "daily_snapshot",  # suffix `.json` added automatically
    compress=True,
    max_bytes=5 * 1024 * 1024,  # 5 MB guardrail
    compresslevel=6,
)
```

> `compress=True` writes `*.json.gz` via gzip. Set `max_bytes` to prevent oversized artifacts.

### Scheduled Exports

```python
from moni.export import MetricExporter

exporter = MetricExporter(history, registry)
exporter.schedule_export(
    schedule_id="hourly_export",
    file_pattern="metrics_{timestamp}.json",
    format_type="json",
    interval_minutes=60
)
```

---

## Performance Optimization

### Resource Usage Guidelines

**For Always-On Monitoring**:
- Refresh interval: 2000-3000ms
- History entries: 500-1000
- Logging: Disable unless troubleshooting
- Profile: Minimal or Development

**For Gaming**:
- Refresh interval: 500-1000ms
- Compact mode: Enabled
- Alerts: Minimized
- Profile: Gaming

**For Enterprise Deployment**:
- Refresh interval: 5000-10000ms
- History entries: 10000
- Logging: Enabled with rotation
- Profile: Custom (see below)

### Custom Profile Example

```json
{
  "profiles": {
    "enterprise": {
      "name": "Enterprise",
      "description": "Production-grade monitoring",
      "metrics": [
        "cpu_usage",
        "memory_usage",
        "disk_io",
        "network_io"
      ],
      "overlay": {
        "refresh_interval_ms": 5000,
        "visible": false
      },
      "automation": {
        "logging": {
          "enabled": true,
          "interval_ms": 10000
        },
        "alerts": {
          "enabled": true,
          "thresholds": {
            "cpu_percent": 90.0,
            "memory_percent": 95.0
          }
        }
      }
    }
  }
}
```

---

## Troubleshooting

### Common Issues

**Overlay Not Showing**
```bash
# Check visibility setting
moni --validate-config

# Force show overlay
# Press Ctrl+Shift+M (global hotkey)

# Verify configuration
cat ~/.config/moni/config.json | grep visible
```

**GPU Metrics Unavailable**
```bash
# Test NVML library
python -c "import pynvml; pynvml.nvmlInit(); print('GPU detected')"

# Update GPU drivers
# Visit: https://www.nvidia.com/drivers

# Check supported GPUs
moni --list-gpus
```

**High Resource Usage**
```bash
# Switch to minimal profile
moni --profile minimal

# Increase refresh interval
# Edit config: overlay.refresh_interval_ms = 3000

# Disable logging
# Edit config: automation.logging.enabled = false
```

**Permission Errors**
```bash
# Linux/macOS: Run with elevated privileges
sudo moni

# Windows: Run as Administrator
# Right-click moni.exe → Run as Administrator

# Check file permissions
ls -la ~/.config/moni/
```

---

## Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src/moni --cov-report=html

# Run security tests only
pytest -m security

# Run performance tests
pytest -m performance
```

### Code Quality

```bash
# Linting
ruff check src/
mypy src/

# Security scanning
bandit -r src/

# Format code
ruff format src/
```

### Project Structure

```
moni/
├── src/moni/              # Core application
│   ├── ui/                # User interface components
│   ├── config.py          # Configuration management
│   ├── metrics.py         # Metric collection
│   ├── security.py        # Security utilities
│   ├── export.py          # Data export
│   └── application.py     # Main application
├── tests/                 # Test suite
├── docs/                  # Documentation
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
└── pyproject.toml         # Project metadata
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+M` | Toggle overlay visibility |
| `Ctrl+,` | Open settings |
| `F5` | Manual metrics refresh |
| `Ctrl+Q` | Quit application |

---

## Contributing

We welcome contributions! Please see our guidelines:

1. **Security First**: All code must pass security review
2. **Test Coverage**: Maintain >85% coverage
3. **Documentation**: Update docs for new features
4. **Code Style**: Follow project conventions (ruff, mypy)

### Development Workflow

```bash
# Fork repository
git clone <repository-url>
cd moni

# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
pytest
ruff check src/
mypy src/

# Commit and push
git commit -m "feat: your feature description"
git push origin feature/your-feature

# Open pull request
```

---

## License

MIT License - See [LICENSE](LICENSE) for details.

This software is provided "as-is" without warranty. Use at your own risk, especially in critical environments.

---

## Acknowledgments

Built with industry-leading technologies:

- **PySide6** - Qt for Python GUI framework
- **psutil** - Cross-platform system monitoring
- **pynvml** - NVIDIA GPU monitoring (optional)
- **cryptography** - Enterprise-grade encryption
- **pydantic** - Data validation and serialization

Special thanks to the open-source community for making secure, reliable software possible.

---

## Production Deployment

### System Administrator Guide

**Pre-Deployment Checklist**:
- [ ] Security audit completed (`moni --security-audit`)
- [ ] Configuration validated (`moni --validate-config`)
- [ ] Resource limits configured (systemd/Docker)
- [ ] Log rotation enabled
- [ ] Monitoring dashboards configured
- [ ] Backup procedures tested
- [ ] Incident response plan documented

**Docker Deployment**:
```bash
# Build production image
docker build -t moni:latest .

# Run with resource limits
docker run -d \
  --name moni \
  --memory="512m" \
  --cpus="0.5" \
  --restart=unless-stopped \
  -v /path/to/config:/root/.config/moni \
  moni:latest
```

**Systemd Service** (Linux):
```ini
[Unit]
Description=Moni System Monitor
After=network.target

[Service]
Type=simple
User=moni
Group=moni
ExecStart=/opt/moni/venv/bin/moni --mode daemon
Restart=on-failure
RestartSec=10s

# Security hardening
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/moni/.config/moni

[Install]
WantedBy=multi-user.target
```

**Kubernetes Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: moni
spec:
  replicas: 1
  selector:
    matchLabels:
      app: moni
  template:
    metadata:
      labels:
        app: moni
    spec:
      containers:
      - name: moni
        image: moni:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: config
          mountPath: /root/.config/moni
      volumes:
      - name: config
        persistentVolumeClaim:
          claimName: moni-config
```

---

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: 提出先の課題管理システムを利用してください。
- **Security**: [SECURITY.md](SECURITY.md)
- **Discussions**: 議論用のフォーラムやチャネルを運用ポリシーに合わせて設定してください。

---

**Last Updated**: 2025-10-06
**Operational Status**: Suitable for continuous monitoring
