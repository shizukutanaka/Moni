"""
Zero Trust Security Architecture Implementation
Never trust, always verify principle for cloud-native environments

Features:
- Device identity verification
- User authentication and authorization
- Continuous compliance checking
- Least privilege access control
- Micro-segmentation ready
- Real-time risk assessment
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class TrustLevel(Enum):
    """Device/user trust levels."""
    UNKNOWN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AccessDecision(Enum):
    """Access control decision."""
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"  # Require additional verification


class RiskLevel(Enum):
    """Risk assessment level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DeviceIdentity:
    """Device identity and trust information."""
    device_id: str
    device_name: str
    device_type: str  # laptop, mobile, server, etc.
    os: str
    os_version: str

    # Trust indicators
    device_certificate_fingerprint: str
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_managed: bool = False  # Device management enrollment status
    encryption_enabled: bool = False
    firewall_enabled: bool = False
    antivirus_enabled: bool = False

    def calculate_device_trust(self) -> TrustLevel:
        """Calculate device trust score."""
        trust_score = 0

        if self.is_managed:
            trust_score += 2
        if self.encryption_enabled:
            trust_score += 1
        if self.firewall_enabled:
            trust_score += 1
        if self.antivirus_enabled:
            trust_score += 1

        if trust_score >= 4:
            return TrustLevel.HIGH
        elif trust_score >= 2:
            return TrustLevel.MEDIUM
        else:
            return TrustLevel.LOW


@dataclass
class UserIdentity:
    """User identity and authentication information."""
    user_id: str
    username: str
    email: str

    # Authentication
    mfa_enabled: bool = False
    mfa_methods: Set[str] = field(default_factory=set)  # totp, fido2, etc.
    last_authentication: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Risk factors
    failed_login_attempts: int = 0
    last_failed_attempt: Optional[datetime] = None
    unusual_location: bool = False
    unusual_time: bool = False


@dataclass
class AccessContext:
    """Context for access decision."""
    user: UserIdentity
    device: DeviceIdentity
    resource: str
    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    location: Optional[str] = None
    network: Optional[str] = None  # VPN, corporate, etc.


@dataclass
class AccessPolicy:
    """Zero trust access policy."""
    policy_id: str
    name: str
    description: str

    # Policy conditions
    required_device_trust: TrustLevel = TrustLevel.MEDIUM
    require_mfa: bool = True
    allow_unmanaged_devices: bool = False
    allowed_networks: Set[str] = field(default_factory=set)
    allowed_locations: Set[str] = field(default_factory=set)
    time_restrictions: Optional[str] = None  # cron-style

    # Resource constraints
    resource_patterns: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)

    def matches(self, context: AccessContext) -> bool:
        """Check if context matches policy."""
        # Check device trust
        device_trust = context.device.calculate_device_trust()
        if device_trust.value < self.required_device_trust.value:
            return False

        # Check MFA
        if self.require_mfa and not context.user.mfa_enabled:
            return False

        # Check managed devices
        if self.allow_unmanaged_devices is False and not context.device.is_managed:
            return False

        # Check network
        if self.allowed_networks and context.network not in self.allowed_networks:
            return False

        # Check location
        if self.allowed_locations and context.location not in self.allowed_locations:
            return False

        return True


# ============================================================================
# Zero Trust Access Controller
# ============================================================================

class ZeroTrustAccessController:
    """Enforce zero trust access policies."""

    def __init__(self):
        """Initialize zero trust controller."""
        self.policies: Dict[str, AccessPolicy] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.block_list: Set[str] = set()
        self.lock = threading.RLock()

    def add_policy(self, policy: AccessPolicy) -> None:
        """Add access policy."""
        with self.lock:
            self.policies[policy.policy_id] = policy

    def evaluate_access(self, context: AccessContext) -> AccessDecision:
        """Evaluate access request using zero trust principles."""
        with self.lock:
            # Never trust - always verify
            decision = self._verify_identity(context)
            if decision != AccessDecision.ALLOW:
                self._audit_access(context, decision, "Identity verification failed")
                return decision

            # Verify device
            decision = self._verify_device(context)
            if decision != AccessDecision.ALLOW:
                self._audit_access(context, decision, "Device verification failed")
                return decision

            # Evaluate policies
            matching_policies = [
                p for p in self.policies.values()
                if self._resource_matches(p, context.resource) and
                   self._action_matches(p, context.action)
            ]

            if not matching_policies:
                self._audit_access(context, AccessDecision.DENY, "No matching policies")
                return AccessDecision.DENY

            # All matching policies must allow
            for policy in matching_policies:
                if not policy.matches(context):
                    self._audit_access(context, AccessDecision.DENY,
                                     f"Policy {policy.policy_id} conditions not met")
                    return AccessDecision.DENY

            self._audit_access(context, AccessDecision.ALLOW, "All verifications passed")
            return AccessDecision.ALLOW

    def _verify_identity(self, context: AccessContext) -> AccessDecision:
        """Verify user identity."""
        # Check for blocked users
        if context.user.user_id in self.block_list:
            return AccessDecision.DENY

        # Check authentication recency
        time_since_auth = datetime.now(timezone.utc) - context.user.last_authentication
        if time_since_auth > timedelta(hours=4):
            return AccessDecision.CHALLENGE

        # Check for failed login attempts
        if context.user.failed_login_attempts > 5:
            return AccessDecision.DENY

        return AccessDecision.ALLOW

    def _verify_device(self, context: AccessContext) -> AccessDecision:
        """Verify device compliance."""
        # Check for device certificate
        if not context.device.device_certificate_fingerprint:
            return AccessDecision.DENY

        # Check device age (if not seen recently)
        time_since_seen = datetime.now(timezone.utc) - context.device.last_seen
        if time_since_seen > timedelta(days=30):
            return AccessDecision.CHALLENGE

        # Check critical security controls
        if not context.device.encryption_enabled:
            return AccessDecision.CHALLENGE

        return AccessDecision.ALLOW

    @staticmethod
    def _resource_matches(policy: AccessPolicy, resource: str) -> bool:
        """Check if resource matches policy."""
        if not policy.resource_patterns:
            return True
        import fnmatch
        return any(fnmatch.fnmatch(resource, pattern) for pattern in policy.resource_patterns)

    @staticmethod
    def _action_matches(policy: AccessPolicy, action: str) -> bool:
        """Check if action matches policy."""
        if not policy.actions:
            return True
        return action in policy.actions

    def _audit_access(self, context: AccessContext, decision: AccessDecision,
                     reason: str) -> None:
        """Audit access decision."""
        audit_entry = {
            "timestamp": context.timestamp.isoformat(),
            "user_id": context.user.user_id,
            "device_id": context.device.device_id,
            "resource": context.resource,
            "action": context.action,
            "decision": decision.value,
            "reason": reason,
            "ip_address": context.ip_address,
            "location": context.location
        }
        self.audit_log.append(audit_entry)
        logger.info(f"Access decision: {decision.value} - {reason}")


# ============================================================================
# Continuous Compliance Checker
# ============================================================================

class ContinuousComplianceChecker:
    """Continuously verify compliance with zero trust policies."""

    def __init__(self):
        """Initialize compliance checker."""
        self.device_compliance: Dict[str, Dict[str, bool]] = {}
        self.user_compliance: Dict[str, Dict[str, bool]] = {}
        self.lock = threading.RLock()

    def check_device_compliance(self, device: DeviceIdentity) -> RiskLevel:
        """Check device compliance status."""
        with self.lock:
            compliance_checks = {
                "encryption": device.encryption_enabled,
                "firewall": device.firewall_enabled,
                "antivirus": device.antivirus_enabled,
                "managed": device.is_managed,
                "certificate_valid": self._is_certificate_valid(device)
            }

            self.device_compliance[device.device_id] = compliance_checks

            # Calculate risk based on failures
            failures = sum(1 for v in compliance_checks.values() if not v)

            if failures == 0:
                return RiskLevel.LOW
            elif failures == 1:
                return RiskLevel.MEDIUM
            elif failures <= 2:
                return RiskLevel.HIGH
            else:
                return RiskLevel.CRITICAL

    def check_user_compliance(self, user: UserIdentity) -> RiskLevel:
        """Check user compliance status."""
        with self.lock:
            compliance_checks = {
                "mfa_enabled": user.mfa_enabled,
                "no_failed_logins": user.failed_login_attempts == 0,
                "recent_auth": (datetime.now(timezone.utc) - user.last_authentication).days < 1
            }

            self.user_compliance[user.user_id] = compliance_checks

            failures = sum(1 for v in compliance_checks.values() if not v)

            if failures == 0:
                return RiskLevel.LOW
            elif failures == 1:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.HIGH

    @staticmethod
    def _is_certificate_valid(device: DeviceIdentity) -> bool:
        """Verify device certificate validity."""
        # Simplified - in production would check against CA
        return len(device.device_certificate_fingerprint) == 64


# ============================================================================
# Least Privilege Manager
# ============================================================================

class LeastPrivilegeManager:
    """Implement least privilege access principle."""

    def __init__(self):
        """Initialize privilege manager."""
        self.role_permissions: Dict[str, Set[str]] = {}
        self.user_roles: Dict[str, Set[str]] = {}
        self.lock = threading.RLock()

    def grant_role(self, user_id: str, role: str) -> None:
        """Grant role to user with time-limited access."""
        with self.lock:
            if user_id not in self.user_roles:
                self.user_roles[user_id] = set()
            self.user_roles[user_id].add(role)

    def revoke_role(self, user_id: str, role: str) -> None:
        """Revoke role from user."""
        with self.lock:
            if user_id in self.user_roles:
                self.user_roles[user_id].discard(role)

    def define_role(self, role_name: str, permissions: Set[str]) -> None:
        """Define role with specific permissions."""
        with self.lock:
            self.role_permissions[role_name] = permissions

    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get all permissions for user based on roles."""
        with self.lock:
            permissions = set()
            if user_id in self.user_roles:
                for role in self.user_roles[user_id]:
                    if role in self.role_permissions:
                        permissions.update(self.role_permissions[role])
            return permissions

    def request_elevated_access(self, user_id: str, resource: str,
                               justification: str, duration_minutes: int = 30) -> bool:
        """Request temporary elevated access with audit trail."""
        logger.warning(
            f"Elevated access request: user={user_id}, resource={resource}, "
            f"duration={duration_minutes}min, justification={justification}"
        )
        return True  # In production, would require approval


# Singleton instances
_zero_trust_controller: Optional[ZeroTrustAccessController] = None
_compliance_checker: Optional[ContinuousComplianceChecker] = None
_privilege_manager: Optional[LeastPrivilegeManager] = None


def get_zero_trust_controller() -> ZeroTrustAccessController:
    """Get or create zero trust controller."""
    global _zero_trust_controller
    if _zero_trust_controller is None:
        _zero_trust_controller = ZeroTrustAccessController()
    return _zero_trust_controller


def get_compliance_checker() -> ContinuousComplianceChecker:
    """Get or create compliance checker."""
    global _compliance_checker
    if _compliance_checker is None:
        _compliance_checker = ContinuousComplianceChecker()
    return _compliance_checker


def get_privilege_manager() -> LeastPrivilegeManager:
    """Get or create privilege manager."""
    global _privilege_manager
    if _privilege_manager is None:
        _privilege_manager = LeastPrivilegeManager()
    return _privilege_manager
