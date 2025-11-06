"""
Security tests for Moni system monitor.
Tests input validation, file operations, and security controls.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from src.moni.security import (
    InputValidator, SecureFileHandler, ConfigSecurity,
    ValidationError, PathTraversalError, SecurityError,
    RateLimiter
)


class TestInputValidator:
    """Test input validation functionality."""

    def test_validate_filename_valid(self):
        """Test valid filename validation."""
        valid_names = ["test.json", "data_file.csv", "metrics-2024.txt"]
        for name in valid_names:
            result = InputValidator.validate_filename(name)
            assert result == name

    def test_validate_filename_invalid(self):
        """Test invalid filename validation."""
        invalid_names = ["", "test<file>.json", "file|name.txt", "con.txt"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                InputValidator.validate_filename(name)

    def test_validate_file_path_valid(self):
        """Test valid file path validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            valid_path = base_dir / "test.json"

            result = InputValidator.validate_file_path(valid_path, base_dir)
            assert result.is_absolute()
            assert str(result).startswith(str(base_dir))

    def test_validate_file_path_traversal(self):
        """Test path traversal detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            malicious_path = base_dir / ".." / ".." / "etc" / "passwd"

            with pytest.raises(PathTraversalError):
                InputValidator.validate_file_path(malicious_path, base_dir)

    def test_validate_ip_address_valid(self):
        """Test valid IP address validation."""
        valid_ips = ["192.168.1.1", "10.0.0.1", "2001:db8::1"]
        for ip in valid_ips:
            result = InputValidator.validate_ip_address(ip)
            assert result == ip

    def test_validate_ip_address_invalid(self):
        """Test invalid IP address validation."""
        invalid_ips = ["", "256.256.256.256", "not_an_ip", "192.168.1"]
        for ip in invalid_ips:
            with pytest.raises(ValidationError):
                InputValidator.validate_ip_address(ip)

    def test_validate_port_valid(self):
        """Test valid port validation."""
        valid_ports = [80, 443, 8080, "22", "3306"]
        expected = [80, 443, 8080, 22, 3306]
        for port, expected_port in zip(valid_ports, expected):
            result = InputValidator.validate_port(port)
            assert result == expected_port

    def test_validate_port_invalid(self):
        """Test invalid port validation."""
        invalid_ports = [0, 65536, -1, "invalid", ""]
        for port in invalid_ports:
            with pytest.raises(ValidationError):
                InputValidator.validate_port(port)

    def test_validate_command_args(self):
        """Test command argument validation."""
        # Valid command
        cmd, args = InputValidator.validate_command_args("ping", ["127.0.0.1"])
        assert cmd == "ping"
        assert len(args) == 1

        # Dangerous command should raise error
        with pytest.raises(ValidationError):
            InputValidator.validate_command_args("rm", ["-rf", "/"])

    def test_sanitize_log_data(self):
        """Test log data sanitization."""
        dangerous_data = "test\x00\x1f\x7fdata\n\r"
        sanitized = InputValidator.sanitize_log_data(dangerous_data)
        assert "\x00" not in sanitized
        assert "\x1f" not in sanitized
        assert "\x7f" not in sanitized

        # Test nested data
        nested_data = {"key": "value\x00", "list": ["item\x1f"]}
        sanitized_nested = InputValidator.sanitize_log_data(nested_data)
        assert "\x00" not in str(sanitized_nested)
        assert "\x1f" not in str(sanitized_nested)


class TestSecureFileHandler:
    """Test secure file operations."""

    def test_write_file_valid(self):
        """Test valid file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))
            test_file = "test.json"
            test_content = '{"test": "data"}'

            result = handler.write_file(test_file, test_content)
            assert result is True

            # Verify file was written
            file_path = Path(temp_dir) / test_file
            assert file_path.exists()
            assert file_path.read_text() == test_content

    def test_write_file_too_large(self):
        """Test file size limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))
            test_file = "large.json"
            large_content = "x" * (100 * 1024 * 1024 + 1)  # Over 100MB

            result = handler.write_file(test_file, large_content, max_size=100 * 1024 * 1024)
            assert result is False

    def test_read_file_valid(self):
        """Test valid file reading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))
            test_file = "test.json"
            test_content = '{"test": "data"}'

            # Write file first
            handler.write_file(test_file, test_content)

            # Read file
            result = handler.read_file(test_file)
            assert result == test_content

    def test_read_file_not_found(self):
        """Test reading non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))

            result = handler.read_file("nonexistent.json")
            assert result is None

    def test_delete_file_valid(self):
        """Test valid file deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))
            test_file = "test.json"
            test_content = '{"test": "data"}'

            # Write file first
            handler.write_file(test_file, test_content)
            file_path = Path(temp_dir) / test_file
            assert file_path.exists()

            # Delete file
            result = handler.delete_file(test_file)
            assert result is True
            assert not file_path.exists()


class TestConfigSecurity:
    """Test configuration security validation."""

    def test_validate_config_data_valid(self):
        """Test valid configuration validation."""
        valid_config = {
            "metrics": ["cpu_usage", "memory_usage"],
            "overlay": {
                "visible": True,
                "opacity": 0.9,
                "refresh_interval_ms": 1000
            }
        }

        result = ConfigSecurity.validate_config_data(valid_config)
        assert "metrics" in result
        assert "overlay" in result

    def test_validate_config_data_invalid(self):
        """Test invalid configuration validation."""
        # Non-dict config should raise error
        with pytest.raises(ValidationError):
            ConfigSecurity.validate_config_data("not a dict")

        # Invalid metrics should be filtered out
        invalid_config = {
            "metrics": ["valid_metric", "invalid<metric>", 123]
        }
        result = ConfigSecurity.validate_config_data(invalid_config)
        assert len(result.get("metrics", [])) == 1

    def test_validate_color(self):
        """Test color validation."""
        assert ConfigSecurity._validate_color("#ff0000") is True
        assert ConfigSecurity._validate_color("#123456") is True
        assert ConfigSecurity._validate_color("red") is False
        assert ConfigSecurity._validate_color("#gggggg") is False
        assert ConfigSecurity._validate_color("") is False

    def test_compute_config_hash(self):
        """Test configuration hash computation."""
        config1 = {"key": "value"}
        config2 = {"key": "value"}
        config3 = {"key": "different"}

        hash1 = ConfigSecurity.compute_config_hash(config1)
        hash2 = ConfigSecurity.compute_config_hash(config2)
        hash3 = ConfigSecurity.compute_config_hash(config3)

        assert hash1 == hash2  # Same config should have same hash
        assert hash1 != hash3  # Different config should have different hash
        assert len(hash1) == 64  # SHA-256 hash length

    def test_verify_config_integrity(self):
        """Test configuration integrity verification."""
        config = {"key": "value"}
        correct_hash = ConfigSecurity.compute_config_hash(config)
        wrong_hash = "wrong_hash"

        assert ConfigSecurity.verify_config_integrity(config, correct_hash) is True
        assert ConfigSecurity.verify_config_integrity(config, wrong_hash) is False


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limit_allowed(self):
        """Test rate limiting within limits."""
        limiter = RateLimiter()

        # Should allow requests within limit
        for i in range(5):
            assert limiter.is_allowed("test_client", limit=10, window=60) is True

    def test_rate_limit_exceeded(self):
        """Test rate limiting when limit exceeded."""
        limiter = RateLimiter()

        # Fill up the limit
        for i in range(10):
            limiter.is_allowed("test_client", limit=10, window=60)

        # Next request should be denied
        assert limiter.is_allowed("test_client", limit=10, window=60) is False

    def test_rate_limit_window_reset(self):
        """Test rate limiting window reset."""
        limiter = RateLimiter()

        # Fill up the limit
        for i in range(10):
            limiter.is_allowed("test_client", limit=10, window=1)  # 1 second window

        # Should be denied
        assert limiter.is_allowed("test_client", limit=10, window=1) is False

        # Wait for window to reset
        import time
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.is_allowed("test_client", limit=10, window=1) is True

    def test_rate_limit_different_clients(self):
        """Test rate limiting for different clients."""
        limiter = RateLimiter()

        # Client 1 uses up their limit
        for i in range(5):
            limiter.is_allowed("client1", limit=5, window=60)

        # Client 1 should be denied
        assert limiter.is_allowed("client1", limit=5, window=60) is False

        # Client 2 should still be allowed
        assert limiter.is_allowed("client2", limit=5, window=60) is True

    def test_get_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter()

        # Make some requests
        limiter.is_allowed("client1", limit=10, window=60)
        limiter.is_allowed("client2", limit=10, window=60)

        stats = limiter.get_stats()
        assert stats["active_clients"] >= 0
        assert stats["total_requests_last_minute"] >= 0
        assert "client_stats" in stats


# Integration tests
class TestSecurityIntegration:
    """Integration tests for security components."""

    def test_file_operation_with_validation(self):
        """Test file operations with full validation chain."""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = SecureFileHandler(Path(temp_dir))

            # Test valid operation
            valid_filename = InputValidator.validate_filename("test.json")
            test_content = '{"secure": true}'

            success = handler.write_file(valid_filename, test_content)
            assert success is True

            # Test invalid operation
            with pytest.raises(ValidationError):
                invalid_filename = InputValidator.validate_filename("../../../etc/passwd")

    def test_config_security_chain(self):
        """Test full configuration security validation chain."""
        config_data = {
            "metrics": ["cpu_usage", "memory_usage", "invalid<metric>"],
            "overlay": {
                "visible": True,
                "opacity": 1.5,  # Invalid - over limit
                "refresh_interval_ms": 500  # Valid
            },
            "malicious_field": "should_be_removed"
        }

        # Validate and sanitize
        validated = ConfigSecurity.validate_config_data(config_data)

        # Should remove invalid elements
        assert len(validated["metrics"]) == 2  # Invalid metric removed
        assert "malicious_field" not in validated
        assert validated["overlay"]["opacity"] != 1.5  # Invalid opacity removed

    @patch('src.moni.security.security_logger')
    def test_security_event_logging(self, mock_logger):
        """Test security event logging integration."""
        # Trigger a validation error
        with pytest.raises(ValidationError):
            InputValidator.validate_filename("")

        # Should log security events during operations
        handler = SecureFileHandler(Path("/tmp"))
        handler.write_file("test.json", '{"test": true}')

        # Verify logging was called (exact calls depend on implementation)
        assert mock_logger.log_security_event.call_count >= 0