# Contributing to Moni System Monitor

First off, thank you for considering contributing to Moni! It's people like you that make Moni a great tool for the community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Security Vulnerability Reporting](#security-vulnerability-reporting)

---

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Basic understanding of system monitoring concepts
- (Optional) Docker for containerized development

### Development Setup

1. **Fork and Clone**

   ```bash
   # Fork repository on GitHub, then:
   git clone https://github.com/YOUR_USERNAME/moni.git
   cd moni
   git remote add upstream https://github.com/original-owner/moni.git
   ```

2. **Create Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   ```

4. **Install Pre-commit Hooks**

   ```bash
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

5. **Verify Installation**

   ```bash
   pytest
   moni --version
   ```

---

## Development Workflow

### Branching Strategy

We follow the **Git Flow** branching model:

- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/**: New features (`feature/add-prometheus-exporter`)
- **bugfix/**: Bug fixes (`bugfix/fix-memory-leak`)
- **hotfix/**: Critical production fixes (`hotfix/security-patch`)

### Creating a Feature Branch

```bash
git checkout develop
git pull upstream develop
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Write Code**: Follow our [Coding Standards](#coding-standards)
2. **Add Tests**: Maintain >85% code coverage
3. **Update Documentation**: Keep docs in sync with code changes
4. **Run Quality Checks**:

   ```bash
   # Linting
   ruff check src/ tests/
   ruff format src/ tests/

   # Type checking
   mypy src/moni/

   # Security scan
   bandit -r src/moni/

   # Run tests
   pytest --cov=src/moni --cov-report=html
   ```

### Keeping Your Fork Updated

```bash
git fetch upstream
git checkout develop
git merge upstream/develop
git push origin develop
```

---

## Coding Standards

### Python Style Guide

We use **Ruff** for linting and formatting (configured in `pyproject.toml`):

- Line length: 100 characters
- Follow PEP 8 with Ruff's modern defaults
- Use type hints for all functions
- Write docstrings for public APIs (Google style)

**Example:**

```python
def calculate_cpu_usage(interval: float = 1.0) -> float:
    """Calculate CPU usage percentage.

    Args:
        interval: Measurement interval in seconds

    Returns:
        CPU usage percentage (0-100)

    Raises:
        ValueError: If interval is negative
    """
    if interval < 0:
        raise ValueError("Interval must be non-negative")
    return psutil.cpu_percent(interval=interval)
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import Optional, Dict, List

def get_metrics(
    interval: float,
    include_gpu: bool = False
) -> Dict[str, float]:
    """Retrieve system metrics."""
    ...
```

### Documentation

- **Docstrings**: Use Google-style for all public APIs
- **Comments**: Explain *why*, not *what*
- **README updates**: For user-facing changes
- **API docs**: Update OpenAPI spec for API changes

---

## Testing Guidelines

### Test Structure

```
tests/
├── unit/                 # Unit tests
├── integration/          # Integration tests
├── performance/          # Performance benchmarks
└── conftest.py          # Pytest fixtures
```

### Writing Tests

```python
import pytest
from moni.metrics import CPUMonitor

def test_cpu_monitor_initialization():
    """Test CPUMonitor initializes correctly."""
    monitor = CPUMonitor()
    assert monitor is not None
    assert monitor.interval > 0

def test_cpu_usage_range():
    """Test CPU usage returns valid percentage."""
    monitor = CPUMonitor()
    usage = monitor.get_usage()
    assert 0 <= usage <= 100

@pytest.mark.security
def test_input_validation():
    """Test input validation prevents injection."""
    with pytest.raises(ValueError):
        monitor = CPUMonitor(interval=-1)
```

### Running Tests

```bash
# All tests
pytest

# Specific marker
pytest -m security

# With coverage
pytest --cov=src/moni --cov-report=html

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Target**: 85%+ for new code
- **Exceptions**: GUI code, platform-specific features

---

## Commit Message Guidelines

We follow **Conventional Commits** specification:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Formatting (no code change)
- **refactor**: Code restructuring
- **perf**: Performance improvement
- **test**: Adding tests
- **chore**: Build process/tooling changes
- **security**: Security improvements

### Examples

```
feat(billing): add usage-based metering support

Implement Stripe usage records API integration for metered billing.
Adds endpoint tracking and automatic reporting.

Closes #123
```

```
fix(metrics): resolve memory leak in GPU monitoring

Fixed continuous memory growth in NVML polling loop by properly
releasing GPU handles after each query.

Fixes #456
```

```
security(auth): patch authentication bypass vulnerability

CVE-2025-XXXXX: Input validation was insufficient for API key
verification. Added comprehensive sanitization.

BREAKING CHANGE: API key format now requires 'sk_' prefix
```

### Rules

- Use imperative mood ("add" not "added")
- First line ≤72 characters
- Reference issues/PRs in footer
- Mark breaking changes with `BREAKING CHANGE:`

---

## Pull Request Process

### Before Submitting

1. **Rebase on Latest**:

   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

2. **Run Full Test Suite**:

   ```bash
   pytest --cov=src/moni --cov-report=term-missing
   ```

3. **Verify Quality Checks**:

   ```bash
   ruff check src/ tests/
   mypy src/moni/
   bandit -r src/moni/
   ```

4. **Update Documentation**:
   - Add CHANGELOG.md entry
   - Update relevant docs
   - Update OpenAPI spec if needed

### Creating Pull Request

1. **Push to Your Fork**:

   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open PR on GitHub**:
   - Use descriptive title
   - Fill out PR template completely
   - Link related issues
   - Request reviewers

### PR Template

```markdown
## Description
<!-- What does this PR do? Why is it needed? -->

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Testing
<!-- How was this tested? -->

## Screenshots (if applicable)
<!-- Add screenshots for UI changes -->

## Related Issues
<!-- Link related issues: Closes #123 -->
```

### Review Process

- **Minimum 1 approval** from maintainer
- **All CI checks must pass**
- **Code coverage** must not decrease
- **Security scans** must show no new issues
- **Documentation** must be updated

### After Approval

- **Squash commits** if needed
- **Maintainer will merge** to develop
- **Delete feature branch** after merge

---

## Security Vulnerability Reporting

**DO NOT** create public issues for security vulnerabilities.

See [SECURITY.md](SECURITY.md) for responsible disclosure process.

---

## Project Structure

Understanding the codebase:

```
moni/
├── src/moni/              # Source code
│   ├── ui/                # User interface
│   ├── billing/           # Stripe integration
│   ├── config.py          # Configuration management
│   ├── metrics.py         # Metrics collection
│   ├── security.py        # Security utilities
│   └── main.py            # Entry point
├── tests/                 # Test suite
├── docs/                  # Documentation
├── .github/               # CI/CD workflows
└── configs/               # Configuration templates
```

---

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/yourusername/moni/discussions)
- **Bugs**: File an [Issue](https://github.com/yourusername/moni/issues)
- **Chat**: Join our [Discord](https://discord.gg/moni) (if available)
- **Email**: dev@moni-monitor.example.com

---

## Recognition

Contributors are acknowledged in:
- CHANGELOG.md for their contributions
- GitHub Contributors page
- Special recognition for significant contributions

Thank you for making Moni better! 🎉

---

**License**: By contributing, you agree that your contributions will be licensed under the MIT License.
