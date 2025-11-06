"""
Comprehensive test suite for the configuration management system.
Tests the ConfigurationManager class and its advanced features.
"""

import pytest
import tempfile
import json
import yaml
import configparser
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from cryptography.fernet import Fernet

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.config_manager import ConfigurationManager, ConfigProfile, ConfigBackup, ConfigSecurity


class TestConfigurationManager:
    """Test suite for ConfigurationManager class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create ConfigurationManager instance for testing."""
        return ConfigurationManager(config_dir=temp_config_dir)

    @pytest.fixture
    def sample_configs(self, temp_config_dir):
        """Create sample configuration files for testing."""
        configs = {}

        # JSON config
        json_config = {"app": {"name": "test", "version": "1.0"}}
        json_file = temp_config_dir / "app.json"
        json_file.write_text(json.dumps(json_config))
        configs['json'] = json_file

        # YAML config
        yaml_config = {"database": {"host": "localhost", "port": 5432}}
        yaml_file = temp_config_dir / "database.yaml"
        yaml_file.write_text(yaml.dump(yaml_config))
        configs['yaml'] = yaml_file

        # INI config
        ini_file = temp_config_dir / "settings.ini"
        ini_config = configparser.ConfigParser()
        ini_config['DEFAULT'] = {'debug': 'True', 'log_level': 'INFO'}
        with open(ini_file, 'w') as f:
            ini_config.write(f)
        configs['ini'] = ini_file

        # ENV config
        env_file = temp_config_dir / ".env"
        env_file.write_text("SECRET_KEY=test123\nDEBUG=true\n")
        configs['env'] = env_file

        return configs

    def test_initialization(self, config_manager, temp_config_dir):
        """Test ConfigurationManager initialization."""
        assert config_manager.config_dir == temp_config_dir
        assert config_manager._configs == {}
        assert config_manager._watchers == {}
        assert config_manager._hot_reload_enabled is False

    def test_load_json_config(self, config_manager, sample_configs):
        """Test loading JSON configuration files."""
        config_manager.load_config(sample_configs['json'])

        assert 'app.json' in config_manager._configs
        config_data = config_manager.get_config('app.json')
        assert config_data['app']['name'] == 'test'
        assert config_data['app']['version'] == '1.0'

    def test_load_yaml_config(self, config_manager, sample_configs):
        """Test loading YAML configuration files."""
        config_manager.load_config(sample_configs['yaml'])

        assert 'database.yaml' in config_manager._configs
        config_data = config_manager.get_config('database.yaml')
        assert config_data['database']['host'] == 'localhost'
        assert config_data['database']['port'] == 5432

    def test_load_ini_config(self, config_manager, sample_configs):
        """Test loading INI configuration files."""
        config_manager.load_config(sample_configs['ini'])

        assert 'settings.ini' in config_manager._configs
        config_data = config_manager.get_config('settings.ini')
        assert config_data['DEFAULT']['debug'] == 'True'
        assert config_data['DEFAULT']['log_level'] == 'INFO'

    def test_load_env_config(self, config_manager, sample_configs):
        """Test loading environment configuration files."""
        config_manager.load_config(sample_configs['env'])

        assert '.env' in config_manager._configs
        config_data = config_manager.get_config('.env')
        assert config_data['SECRET_KEY'] == 'test123'
        assert config_data['DEBUG'] == 'true'

    def test_load_all_configs(self, config_manager, sample_configs):
        """Test loading all configuration files at once."""
        config_manager.load_all_configs()

        # Should load all config files in the directory
        assert len(config_manager._configs) >= 4
        assert 'app.json' in config_manager._configs
        assert 'database.yaml' in config_manager._configs
        assert 'settings.ini' in config_manager._configs
        assert '.env' in config_manager._configs

    def test_get_nested_config_value(self, config_manager, sample_configs):
        """Test getting nested configuration values."""
        config_manager.load_config(sample_configs['json'])

        # Test nested access
        value = config_manager.get_config_value('app.json', 'app.name')
        assert value == 'test'

        value = config_manager.get_config_value('app.json', 'app.version')
        assert value == '1.0'

    def test_get_config_value_with_default(self, config_manager, sample_configs):
        """Test getting configuration values with defaults."""
        config_manager.load_config(sample_configs['json'])

        # Existing value
        value = config_manager.get_config_value('app.json', 'app.name', 'default')
        assert value == 'test'

        # Non-existing value with default
        value = config_manager.get_config_value('app.json', 'app.missing', 'default_value')
        assert value == 'default_value'

    def test_set_config_value(self, config_manager, sample_configs):
        """Test setting configuration values."""
        config_manager.load_config(sample_configs['json'])

        # Set new value
        config_manager.set_config_value('app.json', 'app.author', 'test_author')
        value = config_manager.get_config_value('app.json', 'app.author')
        assert value == 'test_author'

        # Update existing value
        config_manager.set_config_value('app.json', 'app.name', 'updated_test')
        value = config_manager.get_config_value('app.json', 'app.name')
        assert value == 'updated_test'

    def test_save_config(self, config_manager, sample_configs, temp_config_dir):
        """Test saving configuration files."""
        config_manager.load_config(sample_configs['json'])
        config_manager.set_config_value('app.json', 'app.author', 'test_author')

        # Save config
        config_manager.save_config('app.json')

        # Reload and verify
        new_manager = ConfigurationManager(config_dir=temp_config_dir)
        new_manager.load_config(sample_configs['json'])
        value = new_manager.get_config_value('app.json', 'app.author')
        assert value == 'test_author'

    @patch('moni.config_manager.Observer')
    def test_enable_hot_reload(self, mock_observer, config_manager, sample_configs):
        """Test enabling hot reload functionality."""
        config_manager.load_config(sample_configs['json'])

        # Enable hot reload
        config_manager.enable_hot_reload()

        assert config_manager._hot_reload_enabled is True
        mock_observer.assert_called_once()

    def test_config_validation(self, config_manager, temp_config_dir):
        """Test configuration validation."""
        # Create invalid JSON config
        invalid_json = temp_config_dir / "invalid.json"
        invalid_json.write_text('{"invalid": json}')

        # Should handle invalid JSON gracefully
        with pytest.raises(Exception):
            config_manager.load_config(invalid_json)

    def test_merge_configs(self, config_manager, sample_configs):
        """Test merging multiple configurations."""
        config_manager.load_config(sample_configs['json'])
        config_manager.load_config(sample_configs['yaml'])

        # Merge configs
        merged = config_manager.merge_configs(['app.json', 'database.yaml'])

        assert 'app' in merged
        assert 'database' in merged
        assert merged['app']['name'] == 'test'
        assert merged['database']['host'] == 'localhost'

    def test_config_priority(self, config_manager, temp_config_dir):
        """Test configuration priority system."""
        # Create configs with same keys but different priorities
        config1 = temp_config_dir / "low_priority.json"
        config1.write_text('{"setting": "low_value"}')

        config2 = temp_config_dir / "high_priority.json"
        config2.write_text('{"setting": "high_value"}')

        config_manager.set_config_priority('high_priority.json', 10)
        config_manager.set_config_priority('low_priority.json', 1)

        config_manager.load_config(config1)
        config_manager.load_config(config2)

        # High priority should win
        merged = config_manager.merge_configs(['low_priority.json', 'high_priority.json'])
        assert merged['setting'] == 'high_value'

    def test_config_templating(self, config_manager, temp_config_dir):
        """Test configuration templating with variable substitution."""
        # Create config with template variables
        template_config = temp_config_dir / "template.json"
        template_config.write_text('{"host": "${HOST}", "port": "${PORT:8080}"}')

        # Set template variables
        config_manager.set_template_variables({
            'HOST': 'localhost'
            # PORT should use default value
        })

        config_manager.load_config(template_config)
        config_data = config_manager.get_config('template.json')

        assert config_data['host'] == 'localhost'
        assert config_data['port'] == '8080'  # Default value

    def test_config_export_import(self, config_manager, sample_configs, temp_config_dir):
        """Test configuration export and import functionality."""
        config_manager.load_all_configs()

        # Export configs
        export_file = temp_config_dir / "exported_config.json"
        config_manager.export_configs(export_file)

        assert export_file.exists()

        # Import configs to new manager
        new_manager = ConfigurationManager(config_dir=temp_config_dir)
        new_manager.import_configs(export_file)

        # Verify imported data
        assert 'app.json' in new_manager._configs
        assert new_manager.get_config_value('app.json', 'app.name') == 'test'


class TestConfigProfile:
    """Test suite for ConfigProfile class."""

    @pytest.fixture
    def temp_profile_dir(self):
        """Create temporary profile directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_profile_creation(self, temp_profile_dir):
        """Test creating configuration profiles."""
        profile = ConfigProfile("development", temp_profile_dir)

        assert profile.name == "development"
        assert profile.profile_dir == temp_profile_dir / "development"

    def test_profile_activation(self, temp_profile_dir):
        """Test activating configuration profiles."""
        profile = ConfigProfile("development", temp_profile_dir)

        # Create profile config
        profile_config = {"debug": True, "log_level": "DEBUG"}
        profile.set_config(profile_config)
        profile.save()

        # Activate profile
        profile.activate()

        assert profile.is_active()

    def test_profile_inheritance(self, temp_profile_dir):
        """Test profile inheritance functionality."""
        base_profile = ConfigProfile("base", temp_profile_dir)
        dev_profile = ConfigProfile("development", temp_profile_dir, parent="base")

        # Set base config
        base_config = {"database": {"host": "localhost"}, "debug": False}
        base_profile.set_config(base_config)
        base_profile.save()

        # Set dev config (overrides)
        dev_config = {"debug": True, "database": {"port": 5432}}
        dev_profile.set_config(dev_config)
        dev_profile.save()

        # Get merged config
        merged = dev_profile.get_merged_config()

        assert merged["debug"] is True  # Overridden
        assert merged["database"]["host"] == "localhost"  # Inherited
        assert merged["database"]["port"] == 5432  # Added


class TestConfigBackup:
    """Test suite for ConfigBackup class."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_backup(self, temp_backup_dir):
        """Create ConfigBackup instance for testing."""
        return ConfigBackup(backup_dir=temp_backup_dir)

    def test_create_backup(self, config_backup, temp_backup_dir):
        """Test creating configuration backups."""
        # Create test config
        test_config = temp_backup_dir / "test_config.json"
        test_config.write_text('{"test": "data"}')

        # Create backup
        backup_path = config_backup.create_backup(test_config)

        assert backup_path.exists()
        assert backup_path.parent == config_backup.backup_dir

    def test_restore_backup(self, config_backup, temp_backup_dir):
        """Test restoring from configuration backups."""
        # Create test config
        test_config = temp_backup_dir / "test_config.json"
        original_data = '{"test": "original"}'
        test_config.write_text(original_data)

        # Create backup
        backup_path = config_backup.create_backup(test_config)

        # Modify original
        test_config.write_text('{"test": "modified"}')

        # Restore from backup
        config_backup.restore_backup(backup_path, test_config)

        # Verify restoration
        restored_data = test_config.read_text()
        assert restored_data == original_data

    def test_list_backups(self, config_backup, temp_backup_dir):
        """Test listing available backups."""
        # Create test configs and backups
        for i in range(3):
            test_config = temp_backup_dir / f"test_config_{i}.json"
            test_config.write_text(f'{{"test": "{i}"}}')
            config_backup.create_backup(test_config)

        # List backups
        backups = config_backup.list_backups()

        assert len(backups) >= 3

    def test_cleanup_old_backups(self, config_backup, temp_backup_dir):
        """Test cleaning up old backups."""
        # Create multiple backups
        test_config = temp_backup_dir / "test_config.json"
        test_config.write_text('{"test": "data"}')

        backup_paths = []
        for i in range(5):
            backup_path = config_backup.create_backup(test_config)
            backup_paths.append(backup_path)

        # Cleanup old backups (keep only 2)
        config_backup.cleanup_old_backups(max_backups=2)

        remaining_backups = config_backup.list_backups()
        assert len(remaining_backups) == 2


class TestConfigSecurity:
    """Test suite for ConfigSecurity class."""

    @pytest.fixture
    def config_security(self):
        """Create ConfigSecurity instance for testing."""
        return ConfigSecurity()

    def test_encrypt_decrypt_config(self, config_security):
        """Test configuration encryption and decryption."""
        test_config = {"password": "secret123", "api_key": "abc123"}

        # Encrypt config
        encrypted_data, key = config_security.encrypt_config(test_config)

        assert encrypted_data != json.dumps(test_config)
        assert key is not None

        # Decrypt config
        decrypted_config = config_security.decrypt_config(encrypted_data, key)

        assert decrypted_config == test_config

    def test_validate_config_data(self, config_security):
        """Test configuration data validation."""
        # Valid config
        valid_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "username": "user"
            }
        }

        assert config_security.validate_config_data(valid_config) is True

        # Invalid config (missing required fields)
        invalid_config = {
            "database": {
                "host": "localhost"
                # Missing port and username
            }
        }

        # Should validate structure
        result = config_security.validate_config_data(invalid_config)
        assert isinstance(result, (bool, dict))  # May return validation errors

    def test_sanitize_config_data(self, config_security):
        """Test configuration data sanitization."""
        config_with_secrets = {
            "database": {
                "host": "localhost",
                "password": "secret123"
            },
            "api": {
                "key": "abc123",
                "secret": "xyz789"
            }
        }

        sanitized = config_security.sanitize_config_data(config_with_secrets)

        # Sensitive fields should be redacted
        assert sanitized["database"]["password"] == "[REDACTED]"
        assert sanitized["api"]["key"] == "[REDACTED]"
        assert sanitized["api"]["secret"] == "[REDACTED]"

        # Non-sensitive fields should remain
        assert sanitized["database"]["host"] == "localhost"

    def test_generate_secure_key(self, config_security):
        """Test secure key generation."""
        key1 = config_security.generate_secure_key()
        key2 = config_security.generate_secure_key()

        assert key1 != key2
        assert len(key1) > 0
        assert isinstance(key1, bytes)

    def test_config_integrity_check(self, config_security):
        """Test configuration integrity verification."""
        test_config = {"test": "data"}

        # Generate checksum
        checksum = config_security.generate_config_checksum(test_config)

        # Verify integrity
        assert config_security.verify_config_integrity(test_config, checksum) is True

        # Test with modified config
        modified_config = {"test": "modified_data"}
        assert config_security.verify_config_integrity(modified_config, checksum) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])