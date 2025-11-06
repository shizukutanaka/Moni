"""
Test suite for government-grade security framework.
"""

import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import security modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from moni.government_security import (
    GovernmentSecurityManager,
    SecurityLevel,
    SecurityContext,
    FIPS140_2_Encryption,
    MultiFactorAuthentication,
    ThreatIntelligence,
    ComplianceFramework,
    ThreatIndicator
)


class TestFIPS140_2_Encryption(unittest.TestCase):
    """Test FIPS 140-2 compliant encryption."""

    def setUp(self):
        self.encryption = FIPS140_2_Encryption()

    def test_key_generation(self):
        """Test secure key generation."""
        key = self.encryption.generate_key("test")
        self.assertEqual(len(key), 32)  # 256-bit key

        # Keys should be different each time
        key2 = self.encryption.generate_key("test2")
        self.assertNotEqual(key, key2)

    def test_encryption_decryption(self):
        """Test encryption and decryption."""
        key = self.encryption.generate_key("test")
        plaintext = "Classified government data"

        # Encrypt
        ciphertext, iv, tag = self.encryption.encrypt_data(plaintext, key)

        # Verify components exist
        self.assertIsInstance(ciphertext, bytes)
        self.assertIsInstance(iv, bytes)
        self.assertIsInstance(tag, bytes)
        self.assertEqual(len(iv), 12)  # GCM IV length
        self.assertEqual(len(tag), 16)  # GCM tag length

        # Decrypt
        decrypted = self.encryption.decrypt_data(ciphertext, key, iv, tag)
        self.assertEqual(decrypted.decode(), plaintext)

    def test_encryption_with_additional_data(self):
        """Test encryption with additional authenticated data."""
        key = self.encryption.generate_key("test")
        plaintext = "Secret document"
        additional_data = b"classification:top_secret"

        # Encrypt with additional data
        ciphertext, iv, tag = self.encryption.encrypt_data(
            plaintext, key, additional_data
        )

        # Decrypt with additional data
        decrypted = self.encryption.decrypt_data(
            ciphertext, key, iv, tag, additional_data
        )
        self.assertEqual(decrypted.decode(), plaintext)

    def test_key_derivation(self):
        """Test password-based key derivation."""
        password = "secure_government_password"
        salt = b"random_salt_16_bytes"

        key1 = self.encryption.derive_key(password, salt)
        key2 = self.encryption.derive_key(password, salt)

        # Same password and salt should produce same key
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 32)  # 256-bit key


class TestMultiFactorAuthentication(unittest.TestCase):
    """Test MFA system."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mfa = MultiFactorAuthentication(Path(self.temp_dir) / "test_mfa.db")

    def test_totp_setup(self):
        """Test TOTP setup for user."""
        user_id = "test_user"
        secret, totp_uri, backup_codes = self.mfa.setup_totp(user_id)

        # Verify setup results
        self.assertIsInstance(secret, str)
        self.assertIn("otpauth://", totp_uri)
        self.assertIn(user_id, totp_uri)
        self.assertEqual(len(backup_codes), 10)

        # Verify MFA status
        status = self.mfa.get_mfa_status(user_id)
        self.assertTrue(status["enabled"])
        self.assertEqual(status["backup_codes_remaining"], 10)

    @patch('pyotp.TOTP.verify')
    def test_totp_verification(self, mock_verify):
        """Test TOTP token verification."""
        user_id = "test_user"
        self.mfa.setup_totp(user_id)

        # Mock successful verification
        mock_verify.return_value = True

        result = self.mfa.verify_totp(user_id, "123456")
        self.assertTrue(result)
        mock_verify.assert_called_once()

    def test_backup_code_verification(self):
        """Test backup code verification."""
        user_id = "test_user"
        _, _, backup_codes = self.mfa.setup_totp(user_id)

        # Use first backup code
        code = backup_codes[0]
        result = self.mfa.verify_backup_code(user_id, code)
        self.assertTrue(result)

        # Code should be invalidated after use
        result = self.mfa.verify_backup_code(user_id, code)
        self.assertFalse(result)

        # Verify remaining backup codes
        status = self.mfa.get_mfa_status(user_id)
        self.assertEqual(status["backup_codes_remaining"], 9)


class TestThreatIntelligence(unittest.TestCase):
    """Test threat intelligence system."""

    def setUp(self):
        self.threat_intel = ThreatIntelligence()

    def test_threat_indicator_management(self):
        """Test adding and checking threat indicators."""
        # Add malicious IP indicator
        indicator = ThreatIndicator(
            indicator_type="ip",
            value="192.168.1.100",
            severity="high",
            confidence=0.9,
            source="test",
            timestamp=time.time(),
            description="Test malicious IP"
        )

        self.threat_intel.add_threat_indicator(indicator)

        # Check IP reputation
        is_threat, score, reason = self.threat_intel.check_ip_reputation("192.168.1.100")
        self.assertTrue(is_threat)
        self.assertEqual(score, 0.9)
        self.assertEqual(reason, "Test malicious IP")

    def test_behavior_analysis(self):
        """Test user behavior analysis."""
        user_id = "test_user"
        actions = [
            {"timestamp": time.time(), "resource": "file1.txt"},
            {"timestamp": time.time(), "resource": "file2.txt"},
            {"timestamp": time.time(), "resource": "file1.txt"},
        ]

        analysis = self.threat_intel.analyze_behavior(user_id, actions)

        self.assertIn("user_id", analysis)
        self.assertIn("anomaly_score", analysis)
        self.assertEqual(analysis["user_id"], user_id)
        self.assertIsInstance(analysis["anomaly_score"], float)

    def test_attack_pattern_detection(self):
        """Test attack pattern detection."""
        # Simulate brute force attack events
        events = []
        for i in range(6):  # 6 failed login attempts
            events.append({
                "event_type": "AUTHENTICATION_ATTEMPT",
                "user_id": "target_user",
                "details": {"authorized": False},
                "timestamp": time.time()
            })

        attacks = self.threat_intel.detect_attack_patterns(events)

        self.assertEqual(len(attacks), 1)
        self.assertEqual(attacks[0]["pattern"], "brute_force_login")
        self.assertEqual(attacks[0]["user_id"], "target_user")
        self.assertEqual(attacks[0]["severity"], "high")


class TestComplianceFramework(unittest.TestCase):
    """Test compliance assessment framework."""

    def setUp(self):
        self.compliance = ComplianceFramework()

    def test_framework_loading(self):
        """Test compliance framework loading."""
        self.assertIn("NIST_CSF", self.compliance.frameworks)
        self.assertIn("ISO_27001", self.compliance.frameworks)
        self.assertIn("SOC_2", self.compliance.frameworks)
        self.assertIn("FedRAMP", self.compliance.frameworks)

    def test_compliance_assessment(self):
        """Test compliance assessment."""
        # Create mock security manager
        mock_security_manager = MagicMock()
        mock_security_manager.encryption.standard.value = "fips_140_2_level_2"
        mock_security_manager.mfa = MagicMock()
        mock_security_manager.zero_trust = MagicMock()
        mock_security_manager.threat_intelligence = MagicMock()
        mock_security_manager.audit_log = MagicMock()

        report = self.compliance.assess_compliance("NIST_CSF", mock_security_manager)

        self.assertEqual(report.standard, "NIST_CSF")
        self.assertIsInstance(report.compliance_score, float)
        self.assertGreaterEqual(report.compliance_score, 0.0)
        self.assertLessEqual(report.compliance_score, 1.0)
        self.assertIsInstance(report.findings, list)
        self.assertIsInstance(report.recommendations, list)


class TestGovernmentSecurityManager(unittest.TestCase):
    """Test main government security manager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Mock the Path.home() to use temp directory
        with patch('pathlib.Path.home', return_value=Path(self.temp_dir)):
            self.security_manager = GovernmentSecurityManager(SecurityLevel.CONFIDENTIAL)

    def test_initialization(self):
        """Test security manager initialization."""
        self.assertEqual(self.security_manager.security_level, SecurityLevel.CONFIDENTIAL)
        self.assertIsNotNone(self.security_manager.encryption)
        self.assertIsNotNone(self.security_manager.zero_trust)
        self.assertIsNotNone(self.security_manager.mfa)
        self.assertIsNotNone(self.security_manager.threat_intelligence)

    def test_authentication_operation(self):
        """Test operation authentication."""
        context = SecurityContext(
            user_id="test_user",
            clearance_level=SecurityLevel.CONFIDENTIAL,
            session_id="test_session",
            classification=SecurityLevel.UNCLASSIFIED,
            compartments=[],
            timestamp=time.time(),
            source_ip="192.168.1.1",
            mfa_verified=True
        )

        # Test normal operation
        authorized, reason = self.security_manager.authenticate_operation(
            context, "read", "normal_file.txt"
        )

        # Should be authorized for basic operations
        self.assertIsInstance(authorized, bool)
        self.assertIsInstance(reason, str)

    def test_mfa_setup(self):
        """Test MFA setup through security manager."""
        user_id = "test_user"
        mfa_data = self.security_manager.setup_user_mfa(user_id)

        self.assertIn("secret", mfa_data)
        self.assertIn("qr_uri", mfa_data)
        self.assertIn("backup_codes", mfa_data)
        self.assertEqual(len(mfa_data["backup_codes"]), 10)

    def test_threat_indicator_management(self):
        """Test threat indicator management."""
        self.security_manager.add_threat_indicator(
            "ip", "10.0.0.1", "high", 0.8, "test_source", "Test threat"
        )

        # Verify indicator was added
        is_threat, score, reason = self.security_manager.threat_intelligence.check_ip_reputation("10.0.0.1")
        self.assertTrue(is_threat)

    def test_compliance_assessment(self):
        """Test compliance assessment."""
        report = self.security_manager.assess_compliance("NIST_CSF")

        self.assertEqual(report.standard, "NIST_CSF")
        self.assertIsInstance(report.compliance_score, float)
        self.assertGreaterEqual(report.requirements_met, 0)
        self.assertGreaterEqual(report.requirements_total, 0)

    def test_security_report_generation(self):
        """Test comprehensive security report generation."""
        report = self.security_manager.generate_security_report()

        # Verify report structure
        self.assertIn("timestamp", report)
        self.assertIn("security_level", report)
        self.assertIn("system_integrity", report)
        self.assertIn("recent_attacks", report)
        self.assertIn("compliance", report)
        self.assertIn("threat_intelligence", report)
        self.assertIn("encryption_standard", report)

        self.assertEqual(report["security_level"], "confidential")
        self.assertEqual(report["encryption_standard"], "fips_140_2_level_2")

    def test_data_encryption(self):
        """Test sensitive data encryption."""
        data = "Top Secret Government Information"
        classification = SecurityLevel.TOP_SECRET

        encrypted_data = self.security_manager.encrypt_sensitive_data(data, classification)

        self.assertIn("ciphertext", encrypted_data)
        self.assertIn("iv", encrypted_data)
        self.assertIn("tag", encrypted_data)
        self.assertIn("classification", encrypted_data)
        self.assertIn("encryption_standard", encrypted_data)

        self.assertEqual(encrypted_data["classification"], "top_secret")
        self.assertEqual(encrypted_data["encryption_standard"], "fips_140_2_level_2")


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_cases = [
        TestFIPS140_2_Encryption,
        TestMultiFactorAuthentication,
        TestThreatIntelligence,
        TestComplianceFramework,
        TestGovernmentSecurityManager
    ]

    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Print summary
    print(f"\n{'='*60}")
    print("GOVERNMENT SECURITY TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")

    if result.errors:
        print(f"\nERRORs:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")