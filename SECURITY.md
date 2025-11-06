# Security Policy

## Supported Versions

We take security seriously and provide security updates for the following versions:

| Version | Supported          | Notes                    |
| ------- | ------------------ | ------------------------ |
| 2.0.x   | :white_check_mark: | Current stable release   |
| 1.9.x   | :warning:          | Security patches only    |
| < 1.9   | :x:                | No longer supported      |

## Security Features

Moni implements comprehensive security measures:

### Data Protection
- **AES-256-GCM Encryption**: All sensitive data is encrypted using government-grade algorithms
- **Key Rotation**: Encryption keys can be rotated on demand with `moni-config rotate-key`, enabling scheduled rotation via external orchestration
- **Data Validation**: All input is validated and sanitized
- **Secure Storage**: Configuration and logs use encrypted storage with integrity checks

### Authentication & Authorization
- **Multi-Factor Authentication**: TOTP-based 2FA support
- **Session Management**: Secure session handling with configurable timeouts
- **Role-Based Access Control**: Granular permissions system
- **Audit Logging**: Comprehensive activity logging with tamper protection

### Network Security
- **TLS 1.3**: All network communication uses the latest TLS protocol
- **Certificate Validation**: Strict certificate chain verification
- **No Default External URLs**: External connections are disabled by default

## Reporting a Vulnerability

We appreciate responsible disclosure of security vulnerabilities. Please follow these steps:

### How to Report

1. **DO NOT** open a public issue for security vulnerabilities
2. Report security issues through GitHub Security Advisories at your repository's security tab
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

### What to Expect

- **Initial Response**: Within 24 hours
- **Assessment**: Within 72 hours
- **Updates**: Weekly progress reports
- **Resolution**: Target 30 days for critical issues

### Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1**: Acknowledgment sent
3. **Day 3**: Initial assessment complete
4. **Day 30**: Target resolution
5. **Day 90**: Public disclosure (if resolved)

## Security Best Practices

### For Administrators

1. **Keep Updated**: Always use the latest version
2. **Secure Configuration**: Enable encryption and authentication
3. **Network Isolation**: Use firewalls and network segmentation
4. **Regular Audits**: Perform security audits regularly
5. **Backup Strategy**: Implement secure backup procedures

### For Developers

1. **Secure Coding**: Follow secure coding practices
2. **Input Validation**: Validate all user inputs
3. **Error Handling**: Don't expose sensitive information in errors
4. **Dependencies**: Keep dependencies updated
5. **Testing**: Include security tests in your test suite

## Compliance

Moni meets or exceeds the following security standards:

- **NIST Cybersecurity Framework**: Full compliance
- **ISO 27001**: Information security management
- **SOC 2 Type II**: Security, availability, and confidentiality
- **GDPR**: Data protection and privacy
- **FIPS 140-2**: Cryptographic module validation

## Security Configuration

### High-Security Environment

```json
{
  "security": {
    "mode": "high",
    "encryption_at_rest": true,
    "mfa_required": true,
    "session_timeout": 900,
    "audit_level": "comprehensive",
    "network_isolation": true,
    "key_rotation_command": "moni-config rotate-key"
  }
}
```

### Government/Critical Infrastructure

```json
{
  "security": {
    "mode": "government",
    "fips_mode": true,
    "air_gapped": true,
    "multi_factor_auth": true,
    "key_rotation_workflow": {
      "rotation_frequency_days": 7,
      "rotation_tool": "moni-config rotate-key"
    },
    "audit_retention_years": 7
  }
}
```

## Known Security Considerations

### Permissions Required
- **Windows**: Administrator rights for low-level system access
- **Linux**: Root access for certain hardware monitoring
- **macOS**: Full disk access permission

### Data Collection
- Only system performance metrics are collected
- No personal or application data is accessed
- All data remains local unless explicitly configured otherwise

### Network Activity
- No telemetry sent by default
- Updates check can be disabled
- All external connections require user consent

## Security Updates

Security updates are distributed through:
- **GitHub Releases**: Primary distribution
- **Security Mailing List**: Critical vulnerability notifications
- **RSS Feed**: Security advisory feed available

## Contact

- **Security Team**: Report through GitHub Security Advisories
- **General Support**: Open an issue on GitHub

## Attribution

We acknowledge security researchers who help improve Moni:
- Responsible disclosure appreciated
- Credit given with researcher permission

---

**Remember**: Security is a shared responsibility. Help us keep Moni secure by following best practices and reporting vulnerabilities responsibly.