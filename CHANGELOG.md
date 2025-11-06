# Changelog

All notable changes to Moni System Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Production-ready packaging infrastructure
- Comprehensive changelog tracking
- Security policy documentation
- Dependency audit workflows

## [2.0.0] - 2025-10-31

### Added
- **Stripe Billing Integration**: Full subscription and usage-based metering system
  - Essential ($29/month), Professional ($99/month), Enterprise ($299/month) tiers
  - Checkout, upgrade/downgrade, pause/resume functionality
  - Usage-based metering for endpoints and API calls
  - Feature gating and quota enforcement
  - Billing portal integration
- **Advanced Security Features**
  - AES-256-GCM encryption at rest
  - TOTP 2FA support
  - RBAC (Role-Based Access Control)
  - HMAC-signed audit logging
  - Rate limiting and DoS protection
- **2025 Security Compliance**
  - AI-powered attack detection
  - Zero-day threat monitoring
  - Zero Trust Architecture implementation
  - EDR/EPP integration
  - Cloud security (IAM/CASB)
- **DevOps Integrations**
  - ClickUp/Jira project management sync
  - Slack real-time notifications
  - GitHub integration
  - Docker monitoring capabilities
- **Enterprise Features**
  - Multi-endpoint monitoring
  - Configurable metrics retention (7-90 days)
  - Compliance exports (ISO 27001, NIST CSF, GDPR, FIPS 140-2)
  - Production-grade error recovery
  - Advanced performance profiling
- **Machine Learning Capabilities**
  - AI-based anomaly detection
  - Predictive analytics with ARIMA/Prophet
  - Time series forecasting
  - Resource usage predictions
- **Advanced Monitoring**
  - 5G network security monitoring
  - Fire detection via video analysis (OpenCV)
  - BCI (Brain-Computer Interface) integration placeholder
  - AIOps engine for automated operations
- **Configuration Management**
  - Profile system (gaming, development, minimal, enterprise)
  - YAML-based billing tier configuration
  - Comprehensive validation system
  - Export directory sandboxing
- **Multi-language Support**
  - English, Japanese, Spanish documentation
  - Internationalization infrastructure

### Changed
- Migrated configuration to structured YAML format
- Enhanced Docker deployment with multi-stage builds
- Improved CI/CD pipeline with security scanning
- Upgraded to Python 3.10+ minimum requirement

### Security
- Implemented path traversal protection
- Added command injection prevention
- Enhanced input validation across all endpoints
- Sandboxed file operations
- Comprehensive security audit capabilities

## [1.0.0] - 2025-09-01

### Added
- Initial public release
- Real-time system monitoring (CPU, memory, GPU, network, disk)
- PySide6-based overlay UI
- Cross-platform support (Windows, macOS, Linux)
- Basic configuration management
- GPU monitoring via NVML
- Export functionality (JSON, CSV, HTML)
- Alert system with configurable thresholds
- Keyboard shortcuts for overlay control

### Security
- Basic encryption for configuration data
- Input validation framework
- Secure subprocess execution

---

## Version History Summary

- **v2.0.0**: Enterprise-grade features, billing system, advanced security
- **v1.0.0**: Initial release with core monitoring capabilities

---

## Release Notes

### Upgrading from 1.x to 2.x

**Breaking Changes:**
- Configuration format migrated to YAML (automatic migration available via `migrate_configs.py`)
- Minimum Python version increased from 3.8 to 3.10
- Some API endpoints restructured for billing integration

**Migration Steps:**
```bash
# Backup existing configuration
cp ~/.config/moni/config.json ~/.config/moni/config.json.backup

# Run migration script
python migrate_configs.py

# Verify new configuration
moni --validate-config
```

**New Dependencies:**
- `stripe>=10.0.0` - Billing integration
- `fastapi>=0.111.0` - Billing API server
- `scikit-learn>=1.3.0` - ML predictions
- `opencv-python>=4.8.0` - Video analysis

---

## Maintenance Policy

- **Security patches**: Released as needed, applied to current major version
- **Bug fixes**: Released in minor versions (x.Y.0)
- **New features**: Released in major versions (X.0.0)
- **LTS support**: Version 2.x will receive security updates until 2027-10-31

---

## Links

- [GitHub Repository](https://github.com/yourusername/moni)
- [Documentation](https://moni.readthedocs.io)
- [Issue Tracker](https://github.com/yourusername/moni/issues)
- [Security Policy](SECURITY.md)

[Unreleased]: https://github.com/yourusername/moni/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/yourusername/moni/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/yourusername/moni/releases/tag/v1.0.0
