"""Advanced network monitoring with geo-location, quality metrics, and security analysis."""

from __future__ import annotations

import copy
import gzip
import io
import ipaddress
import json
import logging
import socket
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set, Union
import threading
import shutil
import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
import psutil

from .security import (
    ALLOWED_FILE_EXTENSIONS,
    InputValidator,
    SAFE_HTTP_ENDPOINTS,
    SecurityError,
    ValidationError,
    SecureFileHandler,
    rate_limiter,
    security_logger,
)


DEFAULT_QUALITY_HOSTS: Tuple[str, ...] = ("8.8.8.8", "1.1.1.1")
DEFAULT_THREAT_INTEL: Tuple[Dict[str, Any], ...] = (
    {
        "indicator": "Reserved test network monitoring baseline",
        "value": "198.51.100.0/24",
        "risk": 0.6,
        "threat_type": "test-range",
        "source": "internal-baseline",
    },
)

try:
    import geoip2.database
    import geoip2.errors
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False


@dataclass
class NetworkConnection:
    """Detailed network connection information."""
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    pid: Optional[int]
    process_name: str
    family: str  # IPv4/IPv6
    type: str    # TCP/UDP
    country: Optional[str] = None
    city: Optional[str] = None
    organization: Optional[str] = None
    is_private: bool = False
    is_suspicious: bool = False
    bytes_sent: int = 0
    bytes_recv: int = 0
    threat_indicator: Optional[str] = None
    risk_score: Optional[float] = None


@dataclass
class NetworkInterface:
    """Network interface statistics and information."""
    name: str
    is_up: bool
    speed: Optional[int]  # Mbps
    mtu: int
    mac_address: str
    ip_addresses: List[str]
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int
    duplex: str
    signal_strength: Optional[int] = None  # WiFi only
    frequency: Optional[float] = None      # WiFi only


@dataclass
class NetworkQualityMetrics:
    """Network quality and performance metrics."""
    latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    bandwidth_mbps: float
    dns_resolution_time_ms: float
    download_speed_mbps: float
    upload_speed_mbps: float
    connection_stability: float  # 0-100 score


@dataclass
class NetworkHealthReport:
    """Aggregated health assessment for operational and compliance reviews."""
    timestamp: float
    risk_level: str
    advisories: List[str]
    connection_count: int
    suspicious_connection_count: int
    interfaces_up: int
    interfaces_down: int
    vpn_detected: bool
    proxy_detected: bool
    bandwidth_tests_enabled: bool
    firewall_status: Dict[str, Any]
    quality_snapshot: Dict[str, float]
    metadata: Dict[str, Any]


logger = logging.getLogger(__name__)


class NetworkMonitor:
    """Advanced network monitoring with security and performance analysis."""

    def __init__(self):
        self.geoip_db: Optional[geoip2.database.Reader] = None
        self.suspicious_ports = {
            22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995,
            1433, 1521, 3306, 3389, 5432, 5900, 6379, 27017
        }
        self.private_networks = [
            ipaddress.IPv4Network('10.0.0.0/8'),
            ipaddress.IPv4Network('172.16.0.0/12'),
            ipaddress.IPv4Network('192.168.0.0/16'),
            ipaddress.IPv4Network('127.0.0.0/8'),
            ipaddress.IPv6Network('::1/128'),
            ipaddress.IPv6Network('fc00::/7'),
        ]
        self.connection_cache: Dict[str, Tuple[float, Dict[str, Optional[str]]]] = {}
        self.interface_stats_history: Dict[str, List[Tuple[float, Dict]]] = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._history_max_age = 3600  # 1 hour max history
        self._initialize_geoip()
        self._http_session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=2,
            pool_maxsize=4,
            max_retries=Retry(
                total=1,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "POST"}),
                raise_on_redirect=False,
                raise_on_status=False,
            ),
        )
        self._http_session.mount("https://", adapter)
        self._http_session.trust_env = False
        self._http_headers = {
            "User-Agent": "Moni-NetworkMonitor/1.0",
            "Accept": "application/json"
        }
        self._bandwidth_tests_enabled = False
        self._bandwidth_continuous = False
        self._bandwidth_cooldown = 900
        self._bandwidth_last_run: Optional[float] = None
        self._bandwidth_endpoints: Dict[str, str] = {}
        self._bandwidth_failure_streak = 0
        self._http_timeout = 10
        self._max_http_response_bytes = 4 * 1024 * 1024
        self._connection_cache_max_entries = 2048
        self._default_quality_hosts: Tuple[str, ...] = DEFAULT_QUALITY_HOSTS
        self._quality_cache: Optional[Tuple[Tuple[str, ...], float, NetworkQualityMetrics]] = None
        self._quality_cache_ttl = 120
        self._cache_lock = threading.RLock()
        self._http_lock = threading.RLock()
        self._bandwidth_lock = threading.RLock()
        self._quality_lock = threading.RLock()
        self._allowed_http_lock = threading.RLock()
        self._firewall_lock = threading.RLock()
        self._vpn_lock = threading.RLock()
        self._health_lock = threading.RLock()
        self._threat_intel_lock = threading.RLock()
        self._config_lock = threading.RLock()
        self._interface_cache_lock = threading.RLock()
        self._export_lock = threading.RLock()
        self._base_http_whitelist: Set[str] = set(SAFE_HTTP_ENDPOINTS)
        self._approved_http_urls: Set[str] = set()
        self._approved_http_hosts: Set[str] = set()
        self._interface_cache: Optional[Tuple[float, List[NetworkInterface]]] = None
        self._interface_cache_ttl = 3
        self._export_base_dir = self._initialize_export_directory()
        self._file_handler = SecureFileHandler(self._export_base_dir)
        self._update_http_allowlist(())
        self._firewall_cache: Optional[Tuple[float, Dict[str, Any]]] = None
        self._firewall_cache_ttl = 300
        self._vpn_cache: Optional[Tuple[float, Dict[str, Any]]] = None
        self._vpn_cache_ttl = 180
        self._health_cache: Optional[Tuple[float, NetworkHealthReport]] = None
        self._health_cache_ttl = 60
        self._threat_indicators: List[Dict[str, Any]] = []
        self._threat_risk_threshold = 0.5
        self._threat_event_lock = threading.RLock()
        self._threat_event_log: Dict[str, float] = {}
        self._recent_threat_events: List[Tuple[float, Dict[str, Any]]] = []
        self._threat_event_ttl = 600
        self.configure_threat_intelligence(DEFAULT_THREAT_INTEL)

    def _initialize_export_directory(self) -> Path:
        """Create a secure default directory for data exports."""

        candidates = [
            Path.home() / ".moni" / "exports",
            Path.cwd() / "moni_exports",
        ]

        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                resolved = candidate.resolve()
                security_logger.debug(
                    "Export directory initialized",
                    extra={"path": InputValidator.sanitize_log_data(str(resolved))},
                )
                return resolved
            except Exception as exc:
                security_logger.warning(
                    "Failed to prepare export directory candidate",
                    extra={
                        "path": InputValidator.sanitize_log_data(str(candidate)),
                        "error": str(exc),
                    },
                )

        fallback = Path.cwd()
        fallback.mkdir(parents=True, exist_ok=True)
        resolved = fallback.resolve()
        security_logger.warning(
            "Falling back to current working directory for exports",
            extra={"path": InputValidator.sanitize_log_data(str(resolved))},
        )
        return resolved

    def _update_http_allowlist(self, extra_urls: Iterable[str]) -> None:
        """Refresh cached allowlist for outbound HTTPS requests."""

        sanitized_urls: Set[str] = set()

        def _sanitize_source(iterable: Iterable[str], source_label: str) -> None:
            for entry in iterable:
                if not entry:
                    continue
                try:
                    sanitized = InputValidator.validate_https_url(entry)
                except ValidationError as exc:
                    security_logger.warning(
                        "Rejected URL from allowlist",
                        extra={"url": entry, "source": source_label, "error": str(exc)},
                    )
                    continue
                sanitized_urls.add(sanitized)

        _sanitize_source(self._base_http_whitelist, "base")
        _sanitize_source(extra_urls or (), "dynamic")

        hosts: Set[str] = set()
        for entry in sanitized_urls:
            try:
                parsed = urlparse(entry)
            except ValueError:
                continue
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())

        with self._allowed_http_lock:
            self._approved_http_urls = sanitized_urls
            self._approved_http_hosts = hosts

    def _is_allowed_https_target(self, url: str) -> bool:
        """Check whether the requested HTTPS target is on the allowlist."""

        try:
            parsed = urlparse(url)
        except ValueError:
            return False

        if parsed.scheme.lower() != "https":
            return False

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False

        if parsed.port not in (None, 443):
            return False

        with self._allowed_http_lock:
            if url in self._approved_http_urls:
                return True
            if hostname in self._approved_http_hosts:
                return True

        return False

    def clear_caches(self) -> None:
        """Reset volatile caches for deterministic diagnostics."""

        with self._cache_lock:
            self.connection_cache.clear()
            self.interface_stats_history.clear()
        with self._quality_lock:
            self._quality_cache = None
        with self._firewall_lock:
            self._firewall_cache = None
        with self._vpn_lock:
            self._vpn_cache = None
        with self._health_lock:
            self._health_cache = None
        with self._threat_event_lock:
            self._threat_event_log.clear()
            self._recent_threat_events.clear()
        with self._bandwidth_lock:
            self._bandwidth_last_run = None
            self._bandwidth_failure_streak = 0

        security_logger.info("Volatile caches cleared", extra={"operation": "clear_caches"})
        with self._interface_cache_lock:
            self._interface_cache = None

    def configure_export_directory(self, directory: Union[str, Path]) -> Path:
        """Update export directory with validation and sandboxing."""

        if not directory:
            raise ValidationError("Export directory path cannot be empty")

        try:
            candidate = Path(directory).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise ValidationError(f"Invalid export directory: {exc}") from exc

        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValidationError(f"Unable to prepare export directory: {exc}") from exc

        with self._config_lock:
            self._export_base_dir = candidate
            self._file_handler = SecureFileHandler(candidate)

        security_logger.info(
            "Export directory configured",
            extra={"path": InputValidator.sanitize_log_data(str(candidate))},
        )
        return candidate

    def _resolve_export_path(
        self,
        file_path: Union[str, Path],
        *,
        default_suffix: str = ".json",
        allowed_suffixes: Optional[Set[str]] = None,
    ) -> Path:
        """Resolve and validate an export path within the sandbox."""

        if not file_path:
            raise ValidationError("Export path is required")

        if isinstance(file_path, Path):
            candidate = file_path
        else:
            candidate = Path(str(file_path).strip())

        if not str(candidate):
            raise ValidationError("Export path cannot be empty")

        if candidate.suffix == "" and default_suffix:
            candidate = candidate.with_suffix(default_suffix)

        try:
            InputValidator.validate_filename(candidate.name)
        except ValidationError as exc:
            raise ValidationError(f"Invalid export filename: {exc}") from exc

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self._export_base_dir / candidate).resolve()

        suffixes = allowed_suffixes or ALLOWED_FILE_EXTENSIONS
        if suffixes and resolved.suffix.lower() not in {s.lower() for s in suffixes}:
            raise ValidationError("Export file extension is not permitted")

        try:
            resolved.relative_to(self._export_base_dir)
        except ValueError as exc:
            raise ValidationError("Export path must reside within the configured export directory") from exc

        return resolved

    def _compress_payload(self, payload: bytes, *, compresslevel: int = 5) -> bytes:
        """Compress export payload using gzip with safe defaults."""

        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=compresslevel) as gz:
            gz.write(payload)
        return buffer.getvalue()

    def configure_threat_intelligence(self, indicators: Iterable[Dict[str, Any]]) -> None:
        """Configure in-memory threat intelligence indicators."""

        sanitized: List[Dict[str, Any]] = []
        for entry in indicators or []:
            if not isinstance(entry, dict):
                continue

            raw_value = entry.get("value")
            if not isinstance(raw_value, str):
                continue

            candidate = raw_value.strip()
            if not candidate:
                continue

            network: Optional[ipaddress._BaseNetwork]
            try:
                network = ipaddress.ip_network(candidate, strict=False)
            except ValueError:
                try:
                    ip_addr = ipaddress.ip_address(candidate)
                    network = ipaddress.ip_network(f"{ip_addr}/{ip_addr.max_prefixlen}", strict=False)
                except ValueError:
                    continue

            try:
                risk_raw = float(entry.get("risk", 1.0))
            except (TypeError, ValueError):
                risk_raw = 1.0
            risk_score = max(0.0, min(1.0, risk_raw))

            sanitized_entry = {
                "network": network,
                "indicator": InputValidator.sanitize_log_data(entry.get("indicator") or "unspecified"),
                "threat_type": InputValidator.sanitize_log_data(entry.get("threat_type") or "unspecified"),
                "source": InputValidator.sanitize_log_data(entry.get("source") or "unspecified"),
                "risk": risk_score,
            }
            sanitized.append(sanitized_entry)

        with self._threat_intel_lock:
            self._threat_indicators = sanitized

    def set_threat_risk_threshold(self, threshold: float) -> None:
        """Adjust the threat risk threshold (0.0 - 1.0)."""

        if not isinstance(threshold, (int, float)):
            raise ValidationError("Threat risk threshold must be numeric")

        normalized = max(0.0, min(1.0, float(threshold)))
        with self._config_lock:
            self._threat_risk_threshold = normalized

        security_logger.info(
            "Threat risk threshold updated",
            extra={"threshold": normalized},
        )

    def set_threat_event_ttl(self, ttl_seconds: int) -> None:
        """Configure retention window for threat audit events."""

        if not isinstance(ttl_seconds, int) or ttl_seconds < 60 or ttl_seconds > 86_400:
            raise ValidationError("Threat event TTL must be an integer between 60 and 86400 seconds")

        with self._config_lock:
            self._threat_event_ttl = ttl_seconds

        with self._threat_event_lock:
            self._prune_threat_events_locked()

        security_logger.info(
            "Threat event TTL updated",
            extra={"ttl_seconds": ttl_seconds},
        )

    def set_suspicious_ports(self, ports: Iterable[int]) -> None:
        """Override suspicious port list with validated entries."""

        validated: Set[int] = set()
        for port in ports or []:
            try:
                value = int(port)
            except (TypeError, ValueError):
                continue
            if 0 <= value <= 65535:
                validated.add(value)

        if not validated:
            raise ValidationError("At least one valid TCP/UDP port must be provided")

        with self._config_lock:
            self.suspicious_ports = validated

        security_logger.info(
            "Suspicious port list updated",
            extra={
                "port_count": len(validated),
                "sample": sorted(validated)[:10],
            },
        )

    def add_private_networks(self, networks: Iterable[str]) -> None:
        """Add additional private or trusted networks."""

        additions: List[ipaddress._BaseNetwork] = []
        for candidate in networks or []:
            if not candidate:
                continue
            try:
                network = ipaddress.ip_network(str(candidate).strip(), strict=False)
            except ValueError:
                continue
            additions.append(network)

        if not additions:
            raise ValidationError("No valid network definitions were provided")

        with self._config_lock:
            known = {str(net) for net in self.private_networks}
            for network in additions:
                if str(network) not in known:
                    self.private_networks.append(network)
                    known.add(str(network))

        security_logger.info(
            "Private network definitions extended",
            extra={
                "added_count": len(additions),
                "samples": [str(net) for net in additions[:5]],
            },
        )

    def tune_cache_policy(
        self,
        *,
        cache_ttl: Optional[int] = None,
        history_max_age: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> None:
        """Adjust cache retention policies with validation."""

        with self._config_lock:
            if cache_ttl is not None:
                if not isinstance(cache_ttl, int) or cache_ttl < 30 or cache_ttl > 3_600:
                    raise ValidationError("cache_ttl must be between 30 and 3600 seconds")
                self._cache_ttl = cache_ttl
            if history_max_age is not None:
                if not isinstance(history_max_age, int) or history_max_age < 60 or history_max_age > 86_400:
                    raise ValidationError("history_max_age must be between 60 and 86400 seconds")
                self._history_max_age = history_max_age
            if max_entries is not None:
                if not isinstance(max_entries, int) or max_entries < 128 or max_entries > 16_384:
                    raise ValidationError("max_entries must be between 128 and 16384")
                self._connection_cache_max_entries = max_entries

        with self._cache_lock:
            self._prune_cache()

        security_logger.info(
            "Cache policy updated",
            extra={
                "cache_ttl": cache_ttl if cache_ttl is not None else "unchanged",
                "history_max_age": history_max_age if history_max_age is not None else "unchanged",
                "max_entries": max_entries if max_entries is not None else "unchanged",
            },
        )

    def get_configuration_snapshot(self) -> Dict[str, Any]:
        """Provide a sanitized snapshot of critical configuration state."""

        with self._config_lock:
            snapshot = {
                "suspicious_port_count": len(self.suspicious_ports),
                "suspicious_ports_sample": sorted(self.suspicious_ports)[:10],
                "private_network_count": len(self.private_networks),
                "private_network_sample": [str(net) for net in self.private_networks[:5]],
                "cache_ttl": self._cache_ttl,
                "history_max_age": self._history_max_age,
                "connection_cache_max_entries": self._connection_cache_max_entries,
                "threat_risk_threshold": self._threat_risk_threshold,
                "threat_event_ttl": self._threat_event_ttl,
                "bandwidth_tests_enabled": self._bandwidth_tests_enabled,
                "approved_url_count": len(self._approved_http_urls),
                "approved_host_count": len(self._approved_http_hosts),
            }

        return copy.deepcopy(snapshot)

    def list_recent_threat_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Expose recent threat events for UX or reporting layers."""

        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")

        events = self._get_recent_threat_events(limit=limit)
        return [copy.deepcopy(event) for event in events]

    def _lookup_threat_indicator(self, address: str) -> Optional[Dict[str, Any]]:
        """Lookup threat intelligence data for a given IP address."""

        try:
            ip_obj = ipaddress.ip_address(address)
        except ValueError:
            return None

        with self._threat_intel_lock:
            for entry in self._threat_indicators:
                network = entry.get("network")
                if network and ip_obj in network:
                    return entry

        return None

    def _handle_threat_detection(
        self,
        remote_addr: str,
        threat_info: Optional[Dict[str, Any]],
    ) -> None:
        if not threat_info:
            return

        timestamp = time.time()
        indicator = InputValidator.sanitize_log_data(threat_info.get("indicator"))
        threat_type = InputValidator.sanitize_log_data(threat_info.get("threat_type"))
        source = InputValidator.sanitize_log_data(threat_info.get("source"))
        risk = threat_info.get("risk")

        key = f"{remote_addr}:{indicator}"
        with self._threat_event_lock:
            last_logged = self._threat_event_log.get(key)
            if last_logged and timestamp - last_logged < self._threat_event_ttl:
                return
            self._threat_event_log[key] = timestamp

            payload = {
                "remote_address": InputValidator.sanitize_log_data(remote_addr),
                "indicator": indicator,
                "threat_type": threat_type,
                "source": source,
                "risk": risk,
                "timestamp": timestamp,
            }

            self._recent_threat_events.append((timestamp, payload))
            self._prune_threat_events_locked()

        security_logger.warning(
            "Threat intelligence flagged active connection",
            extra=payload,
        )

    def _prune_threat_events_locked(self) -> None:
        cutoff = time.time() - self._threat_event_ttl
        self._recent_threat_events = [
            (ts, data) for ts, data in self._recent_threat_events if ts >= cutoff
        ]
        keys_to_delete = [
            key for key, logged_at in self._threat_event_log.items() if logged_at < cutoff
        ]
        for key in keys_to_delete:
            del self._threat_event_log[key]

    def _get_recent_threat_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        with self._threat_event_lock:
            self._prune_threat_events_locked()
            return [
                dict(event_data)
                for _, event_data in sorted(
                    self._recent_threat_events,
                    key=lambda item: item[0],
                    reverse=True,
                )[:limit]
            ]

    def configure_bandwidth_endpoints(
        self,
        overrides: Dict[str, str],
        *,
        enabled: bool = False,
        continuous: bool = False,
        cooldown: int = 900,
    ) -> None:
        """Apply sanitized bandwidth test endpoints."""

        self._bandwidth_tests_enabled = enabled
        self._bandwidth_continuous = continuous and enabled
        self._bandwidth_cooldown = max(60, min(cooldown, 86_400))
        self._quality_cache = None
        if not enabled:
            with self._bandwidth_lock:
                self._bandwidth_endpoints.clear()
                self._bandwidth_last_run = None
                self._bandwidth_failure_streak = 0
            self._update_http_allowlist(())
            return

        allowed_keys = {"download", "upload"}
        sanitized: Dict[str, str] = {}
        for key, value in overrides.items():
            if key not in allowed_keys or not isinstance(value, str):
                continue
            try:
                sanitized[key] = InputValidator.validate_https_url(value)
            except ValidationError as exc:
                security_logger.warning(
                    "Rejected bandwidth endpoint",
                    extra={
                        "key": key,
                        "error": str(exc),
                    },
                )

        with self._bandwidth_lock:
            self._bandwidth_endpoints = sanitized
            self._bandwidth_last_run = None
            self._bandwidth_failure_streak = 0
            self._update_http_allowlist(sanitized.values())
        if self._bandwidth_tests_enabled and not self._bandwidth_endpoints:
            self._bandwidth_tests_enabled = False
            self._bandwidth_continuous = False
            with self._bandwidth_lock:
                self._bandwidth_last_run = None
                self._bandwidth_failure_streak = 0
            security_logger.warning(
                "Disabled bandwidth testing due to absence of approved endpoints",
            )

    def close(self) -> None:
        """Release network resources held by the monitor."""
        try:
            self._http_session.close()
        except Exception:
            pass

    def __del__(self):  # pragma: no cover - best effort cleanup
        self.close()

    def _http_request(
        self,
        method: str,
        url: str,
        *,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Optional[Response]:
        # Early validation before acquiring locks
        if not url or not isinstance(url, str):
            return None

        url_lower = url.lower()
        if not url_lower.startswith("https://"):
            security_logger.warning(
                "Blocked non-HTTPS request",
                extra={"method": method, "url": url},
            )
            return None

        if not self._is_allowed_https_target(url):
            security_logger.warning(
                "Rejected HTTPS request to non-allowlisted endpoint",
                extra={"method": method, "url": url},
            )
            return None

        request_headers = dict(self._http_headers)
        if headers:
            request_headers.update(headers)

        actual_timeout = timeout if timeout is not None else self._http_timeout
        kwargs.setdefault("allow_redirects", False)
        kwargs.setdefault("stream", True)

        try:
            start = time.time()
            with self._http_lock:
                response = self._http_session.request(
                    method,
                    url,
                    headers=request_headers,
                    timeout=actual_timeout,
                    verify=True,
                    **kwargs,
                )
            duration = time.time() - start

            if duration > actual_timeout:
                security_logger.warning(
                    "HTTP request exceeded timeout threshold",
                    extra={
                        "method": method,
                        "url": url,
                        "timeout": actual_timeout,
                        "duration": duration,
                    },
                )

            response.raise_for_status()

            if 300 <= response.status_code < 400:
                security_logger.warning(
                    "Rejected redirect response",
                    extra={
                        "method": method,
                        "url": url,
                        "status": response.status_code,
                        "location": response.headers.get("Location"),
                    },
                )
                response.close()
                return None

            total_bytes = 0
            body_chunks = []
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > self._max_http_response_bytes:
                    security_logger.warning(
                        "HTTP response exceeded size limit",
                        extra={
                            "method": method,
                            "url": url,
                            "bytes": total_bytes,
                        },
                    )
                    response.close()
                    return None
                body_chunks.append(bytes(chunk))

            response._content = b"".join(body_chunks)
            response._content_consumed = True
            response.close()
            return response

        except requests.Timeout:
            logger.warning(
                "HTTP request timeout",
                extra={"method": method, "url": url, "timeout": actual_timeout},
            )
            return None
        except requests.ConnectionError as exc:
            logger.warning(
                "HTTP connection failed",
                exc_info=False,
                extra={"method": method, "url": url, "error": str(exc)},
            )
            return None
        except requests.RequestException as exc:
            logger.warning(
                "HTTP request failed",
                exc_info=False,
                extra={"method": method, "url": url, "error": str(exc)},
            )
            security_logger.warning(
                "HTTP request failure recorded",
                extra={"method": method, "url": url, "error": str(exc)},
            )
            return None

    def _safe_run_command(
        self,
        command: str,
        args: List[str],
        *,
        timeout: int = 5,
    ) -> Optional[subprocess.CompletedProcess[str]]:
        """Execute a system command with validation and safety checks."""

        base_command = Path(command).name
        try:
            _, safe_args = InputValidator.validate_command_args(base_command, args)
        except ValidationError:
            logger.warning(
                "Blocked execution of command due to validation error",
                exc_info=True,
                extra={"command": base_command, "args": args},
            )
            return None

        command_path: Optional[str]
        if Path(command).is_absolute():
            path_obj = Path(command)
            command_path = str(path_obj) if path_obj.exists() else None
        else:
            command_path = shutil.which(base_command)

        if not command_path:
            logger.debug("Command not available", extra={"command": command})
            return None

        normalized_args = []
        for arg in safe_args:
            if len(arg) >= 2 and arg[0] == arg[-1] == "'":
                normalized_args.append(arg[1:-1])
            else:
                normalized_args.append(arg)

        try:
            result = subprocess.run(
                [command_path, *normalized_args],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode not in (0, None):
                security_logger.warning(
                    "Command returned non-zero exit status",
                    extra={
                        "command": command_path,
                        "code": result.returncode,
                        "stderr": InputValidator.sanitize_log_data(result.stderr),
                    },
                )
            return result
        except subprocess.TimeoutExpired:
            logger.warning(
                "Command execution timed out",
                extra={"command": command_path, "args": normalized_args, "timeout": timeout},
            )
        except OSError as exc:
            logger.warning(
                "Command execution failed",
                exc_info=True,
                extra={"command": command_path, "args": normalized_args, "error": str(exc)},
            )

        return None

    def _initialize_geoip(self):
        """Initialize GeoIP database for location lookups."""
        if not GEOIP_AVAILABLE:
            return

        # Common GeoIP database locations
        possible_paths = [
            Path('/usr/share/GeoIP/GeoLite2-City.mmdb'),
            Path('/opt/GeoIP/GeoLite2-City.mmdb'),
            Path('./GeoLite2-City.mmdb'),
            Path.home() / '.geoip' / 'GeoLite2-City.mmdb'
        ]

        for path in possible_paths:
            if path.exists():
                try:
                    self.geoip_db = geoip2.database.Reader(str(path))
                    break
                except Exception:
                    continue

    def get_network_connections(self, include_localhost: bool = False) -> List[NetworkConnection]:
        """Get detailed network connections with geo-location data."""
        connections = []

        # Clean up old cache entries
        with self._cache_lock:
            self._prune_cache()

        connection_keys: Set[Tuple[str, int, str, int, Optional[int]]] = set()
        proc_info_cache: Dict[int, Dict[str, Any]] = {}

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                pid = proc.info.get('pid')
                if pid is None:
                    continue
                proc_info_cache[pid] = {
                    'pid': pid,
                    'name': proc.info.get('name') or 'Unknown',
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        system_scan_failed = False
        try:
            net_connections = psutil.net_connections(kind='inet')
        except (psutil.AccessDenied, NotImplementedError):
            net_connections = []
            system_scan_failed = True

        def process_connection(conn, proc_info: Dict[str, Any]) -> None:
            if not include_localhost and self._is_localhost_connection(conn):
                return

            connection = self._analyze_connection(conn, proc_info)
            if not connection:
                return

            key = (
                connection.local_address,
                connection.local_port,
                connection.remote_address,
                connection.remote_port,
                connection.pid,
            )

            if key in connection_keys:
                return

            connection_keys.add(key)
            connections.append(connection)

        if not system_scan_failed:
            for conn in net_connections:
                pid = getattr(conn, 'pid', None)
                proc_info = self._get_process_info(pid, proc_info_cache)
                process_connection(conn, proc_info)
        else:
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    pid = proc.info.get('pid')
                    if pid is None:
                        continue
                    proc_info = self._get_process_info(pid, proc_info_cache)
                    try:
                        for conn in proc.connections(kind='inet'):
                            process_connection(conn, proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return connections

    def _prune_cache(self) -> None:
        """Remove expired entries from connection cache."""
        current_time = time.time()

        # Prune connection cache
        self.connection_cache = {
            k: v for k, v in self.connection_cache.items()
            if current_time - v[0] < self._cache_ttl
        }
        if len(self.connection_cache) > self._connection_cache_max_entries:
            sorted_entries = sorted(
                self.connection_cache.items(),
                key=lambda item: item[1][0],
                reverse=True,
            )[: self._connection_cache_max_entries]
            self.connection_cache = dict(sorted_entries)

        # Prune history data
        for interface in list(self.interface_stats_history.keys()):
            history = self.interface_stats_history[interface]
            pruned = [
                entry for entry in history
                if current_time - entry[0] < self._history_max_age
            ]
            if pruned:
                self.interface_stats_history[interface] = pruned
            else:
                del self.interface_stats_history[interface]

    def _get_process_info(
        self,
        pid: Optional[int],
        cache: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        if pid is None:
            return {'pid': None, 'name': 'System'}

        if pid in cache:
            return cache[pid]

        try:
            proc = psutil.Process(pid)
            name = proc.name() or 'Unknown'
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            name = 'Unknown'

        info = {'pid': pid, 'name': name}
        cache[pid] = info
        return info

    def _analyze_connection(self, conn, proc_info: Dict) -> Optional[NetworkConnection]:
        """Analyze a single network connection."""
        try:
            if not getattr(conn, 'raddr', None):
                return None

            local_addr, local_port = self._extract_endpoint(conn.laddr)
            remote_addr, remote_port = self._extract_endpoint(conn.raddr)

            # Determine IP version and type
            family = 'IPv6' if ':' in local_addr else 'IPv4'
            conn_type = 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP'

            # Check if remote address is private
            is_private = self._is_private_address(remote_addr)

            # Geo-location lookup for public IPs (with caching)
            country, city, organization = None, None, None
            if not is_private:
                with self._cache_lock:
                    cache_entry = self.connection_cache.get(remote_addr)
                    cache_valid = False
                    if cache_entry:
                        cached_ts, cached_payload = cache_entry
                        if time.time() - cached_ts < self._cache_ttl:
                            country = cached_payload.get("country")
                            city = cached_payload.get("city")
                            organization = cached_payload.get("organization")
                            cache_valid = True

                if not cache_valid and self.geoip_db:
                    try:
                        response = self.geoip_db.city(remote_addr)
                        country = response.country.name
                        city = response.city.name
                        if hasattr(response, 'traits') and hasattr(response.traits, 'organization'):
                            organization = response.traits.organization
                    except (geoip2.errors.AddressNotFoundError, Exception):
                        pass

                with self._cache_lock:
                    self.connection_cache[remote_addr] = (
                        time.time(),
                        {
                            "country": country,
                            "city": city,
                            "organization": organization,
                        },
                    )

            # Threat intelligence lookup
            threat_info = self._lookup_threat_indicator(remote_addr)
            threat_indicator = threat_info.get("indicator") if threat_info else None
            threat_risk = threat_info.get("risk") if threat_info else None

            # Security analysis
            is_suspicious = self._is_suspicious_connection(
                remote_addr,
                remote_port,
                proc_info.get('name', ''),
                threat_info=threat_info,
                threat_risk=threat_risk,
            )

            connection = NetworkConnection(
                local_address=local_addr,
                local_port=local_port,
                remote_address=remote_addr,
                remote_port=remote_port,
                status=getattr(conn, 'status', 'UNKNOWN'),
                pid=proc_info.get('pid'),
                process_name=proc_info.get('name', 'Unknown'),
                family=family,
                type=conn_type,
                country=country,
                city=city,
                organization=organization,
                is_private=is_private,
                is_suspicious=is_suspicious,
                threat_indicator=threat_indicator,
                risk_score=threat_risk,
            )

            return connection

        except Exception:
            return None

    def _is_localhost_connection(self, conn) -> bool:
        """Check if connection is localhost only."""
        if not getattr(conn, 'raddr', None):
            return True

        try:
            local_addr, _ = self._extract_endpoint(conn.laddr)
            remote_addr, _ = self._extract_endpoint(conn.raddr)
        except ValueError:
            return False

        localhost_addresses = {'127.0.0.1', '::1', 'localhost'}
        return (local_addr in localhost_addresses or
                remote_addr in localhost_addresses or
                local_addr == remote_addr)

    @staticmethod
    def _extract_endpoint(endpoint: Any) -> Tuple[str, int]:
        """Normalize psutil connection endpoint to (address, port)."""
        if endpoint is None:
            raise ValueError("Endpoint is missing")

        if isinstance(endpoint, tuple):
            if len(endpoint) >= 2:
                return endpoint[0], endpoint[1]
            raise ValueError("Endpoint tuple is incomplete")

        addr = getattr(endpoint, 'ip', None)
        port = getattr(endpoint, 'port', None)
        if addr is not None and port is not None:
            return addr, port

        raise ValueError("Unsupported endpoint format")

    def _is_private_address(self, address: str) -> bool:
        """Check if an IP address is in private range."""
        try:
            ip = ipaddress.ip_address(address)
            return any(ip in network for network in self.private_networks)
        except ValueError:
            return True  # Invalid IP is considered private for safety

    def _is_suspicious_connection(
        self,
        remote_addr: str,
        remote_port: int,
        process_name: str,
        *,
        threat_info: Optional[Dict[str, Any]] = None,
        threat_risk: Optional[float] = None,
    ) -> bool:
        """Analyze if a connection might be suspicious."""
        effective_risk: Optional[float]
        if threat_info is not None and "risk" in threat_info:
            effective_risk = threat_info.get("risk")  # type: ignore[assignment]
        else:
            effective_risk = threat_risk

        if effective_risk is not None and effective_risk >= self._threat_risk_threshold:
            if threat_info is None:
                threat_info = self._lookup_threat_indicator(remote_addr)
            self._handle_threat_detection(remote_addr, threat_info)
            return True

        # Check for suspicious ports
        if remote_port in self.suspicious_ports and not self._is_private_address(remote_addr):
            return True

        # Check for unusual process names
        suspicious_processes = {
            'cmd.exe', 'powershell.exe', 'nc.exe', 'netcat.exe',
            'telnet.exe', 'ftp.exe'
        }
        if process_name.lower() in suspicious_processes:
            return True

        # Check for connections to known malicious patterns
        if remote_port in {4444, 5555, 6666, 7777, 8888, 9999}:
            return True

        return False

    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get detailed network interface information."""
        now = time.time()
        with self._interface_cache_lock:
            cached_snapshot = self._interface_cache
            if cached_snapshot and now - cached_snapshot[0] < self._interface_cache_ttl:
                return copy.deepcopy(cached_snapshot[1])

        interfaces: List[NetworkInterface] = []

        try:
            net_io = psutil.net_io_counters(pernic=True)
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
        except Exception:
            net_io = {}
            net_if_addrs = {}
            net_if_stats = {}

        af_link = getattr(psutil, "AF_LINK", None)

        for interface_name, io_stats in net_io.items():
            try:
                if_stats = net_if_stats.get(interface_name)
                addresses = net_if_addrs.get(interface_name, [])

                ip_addresses: List[str] = []
                mac_address = ""
                for addr in addresses:
                    if addr.family in (socket.AF_INET, socket.AF_INET6):
                        ip_addresses.append(addr.address)
                    elif af_link is not None and addr.family == af_link:
                        mac_address = addr.address

                if self._is_wireless_interface(interface_name):
                    signal_strength, frequency = self._get_wifi_info(interface_name)
                else:
                    signal_strength, frequency = (None, None)

                interface = NetworkInterface(
                    name=interface_name,
                    is_up=if_stats.isup if if_stats else False,
                    speed=if_stats.speed if if_stats and if_stats.speed > 0 else None,
                    mtu=if_stats.mtu if if_stats else 0,
                    mac_address=mac_address,
                    ip_addresses=ip_addresses,
                    bytes_sent=getattr(io_stats, "bytes_sent", 0),
                    bytes_recv=getattr(io_stats, "bytes_recv", 0),
                    packets_sent=getattr(io_stats, "packets_sent", 0),
                    packets_recv=getattr(io_stats, "packets_recv", 0),
                    errors_in=getattr(io_stats, "errin", 0),
                    errors_out=getattr(io_stats, "errout", 0),
                    drops_in=getattr(io_stats, "dropin", 0),
                    drops_out=getattr(io_stats, "dropout", 0),
                    duplex=getattr(if_stats, 'duplex', 'unknown') if if_stats else 'unknown',
                    signal_strength=signal_strength,
                    frequency=frequency
                )

                interfaces.append(interface)

            except Exception:
                continue

        snapshot = copy.deepcopy(interfaces)
        with self._interface_cache_lock:
            self._interface_cache = (time.time(), snapshot)

        return copy.deepcopy(snapshot)

    def _is_wireless_interface(self, interface_name: str) -> bool:
        """Heuristically determine if an interface represents a wireless adapter."""

        lowered = interface_name.lower()
        wireless_tokens = ("wifi", "wlan", "wireless", "wi-fi", "wl")
        return any(token in lowered for token in wireless_tokens)

    def _get_wifi_info(self, interface_name: str) -> Tuple[Optional[int], Optional[float]]:
        """Get WiFi-specific information (signal strength, frequency)."""
        try:
            # Try different methods based on platform
            import platform
            system = platform.system().lower()

            if system == 'linux':
                return self._get_wifi_info_linux(interface_name)
            elif system == 'windows':
                return self._get_wifi_info_windows(interface_name)
            elif system == 'darwin':  # macOS
                return self._get_wifi_info_macos(interface_name)

        except Exception:
            pass

        return None, None

    def _get_wifi_info_linux(self, interface_name: str) -> Tuple[Optional[int], Optional[float]]:
        """Get WiFi info on Linux systems."""
        try:
            # Validate interface name for security
            safe_interface = InputValidator.validate_interface_name(interface_name)

            # Secure command execution
            result = self._safe_run_command('iwconfig', [safe_interface], timeout=5)

            if result and result.returncode == 0:
                output = result.stdout
                signal_strength = None
                frequency = None

                # Parse signal strength
                if 'Signal level=' in output:
                    signal_line = output.split('Signal level=')[1].split()[0]
                    signal_strength = int(signal_line.split('/')[0])

                # Parse frequency
                if 'Frequency:' in output:
                    freq_line = output.split('Frequency:')[1].split()[0]
                    frequency = float(freq_line)

                return signal_strength, frequency

        except Exception:
            pass

        return None, None

    def _get_wifi_info_windows(self, interface_name: str) -> Tuple[Optional[int], Optional[float]]:
        """Get WiFi info on Windows systems."""
        try:
            # Validate interface name for security
            safe_interface = InputValidator.validate_interface_name(interface_name)

            # Use netsh - no interface name in command for security
            result = self._safe_run_command(
                'netsh',
                ['wlan', 'show', 'interfaces'],
                timeout=5,
            )

            if result and result.returncode == 0:
                output = result.stdout
                signal_strength = None

                # Parse signal strength
                for line in output.split('\n'):
                    if 'Signal' in line and '%' in line:
                        signal_strength = int(line.split(':')[1].strip().replace('%', ''))
                        break

                return signal_strength, None

        except Exception:
            pass

        return None, None

    def _get_wifi_info_macos(self, interface_name: str) -> Tuple[Optional[int], Optional[float]]:
        """Get WiFi info on macOS systems."""
        try:
            # Validate interface name for security
            safe_interface = InputValidator.validate_interface_name(interface_name)

            # Use airport utility with fixed path
            airport_path = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
            result = self._safe_run_command(airport_path, ['-I'], timeout=5)

            if result and result.returncode == 0:
                output = result.stdout
                signal_strength = None

                # Parse RSSI (signal strength)
                for line in output.split('\n'):
                    if 'RSSI:' in line:
                        rssi = int(line.split(':')[1].strip())
                        # Convert RSSI to percentage (approximate)
                        signal_strength = max(0, min(100, 2 * (rssi + 100)))
                        break

                return signal_strength, None

        except Exception:
            pass

        return None, None

    def measure_network_quality(
        self,
        target_hosts: Optional[List[str]] = None,
        *,
        force_refresh: bool = False,
    ) -> NetworkQualityMetrics:
        """Measure comprehensive network quality metrics with caching and validation."""

        raw_hosts = tuple(target_hosts) if target_hosts else self._default_quality_hosts

        validated_hosts: List[str] = []
        for host in raw_hosts:
            if not isinstance(host, str):
                continue

            candidate = host.strip()
            if not candidate:
                continue

            try:
                sanitized = (
                    InputValidator.validate_ip_address(candidate)
                    if self._is_ip_address(candidate)
                    else self._validate_hostname(candidate)
                )
                validated_hosts.append(sanitized)
            except (ValidationError, SecurityError) as exc:
                logger.warning(
                    "Skipping invalid target host",
                    extra={"host": candidate, "error": str(exc)},
                )

        hosts_to_test = tuple(validated_hosts) if validated_hosts else self._default_quality_hosts

        if not force_refresh:
            with self._quality_lock:
                if (
                    self._quality_cache
                    and self._quality_cache[0] == hosts_to_test
                    and time.time() - self._quality_cache[1] < self._quality_cache_ttl
                ):
                    return self._quality_cache[2]

        latencies: List[float] = []
        dns_times: List[float] = []
        packet_loss_count = 0
        total_tests = 0

        for host in hosts_to_test:
            total_tests += 1
            try:
                if self._is_ip_address(host):
                    dns_times.append(0.0)
                else:
                    start_time = time.time()
                    socket.gethostbyname(host)
                    dns_times.append((time.time() - start_time) * 1000)

                latency, packet_loss = self._ping_host(host)
                if latency is not None:
                    latencies.append(latency)
                if packet_loss:
                    packet_loss_count += 1
            except Exception as exc:
                packet_loss_count += 1
                logger.debug(
                    "Network quality test failed",
                    exc_info=False,
                    extra={"host": host, "error": str(exc)},
                )

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        jitter = self._calculate_jitter(latencies) if len(latencies) > 1 else 0.0
        packet_loss_percent = (packet_loss_count / total_tests * 100.0) if total_tests else 100.0
        avg_dns_time = sum(dns_times) / len(dns_times) if dns_times else 0.0

        download_speed, upload_speed = self._test_bandwidth()
        stability = self._calculate_stability_score(avg_latency, jitter, packet_loss_percent)

        metrics = NetworkQualityMetrics(
            latency_ms=avg_latency,
            jitter_ms=jitter,
            packet_loss_percent=packet_loss_percent,
            bandwidth_mbps=max(download_speed, upload_speed),
            dns_resolution_time_ms=avg_dns_time,
            download_speed_mbps=download_speed,
            upload_speed_mbps=upload_speed,
            connection_stability=stability,
        )

        with self._quality_lock:
            self._quality_cache = (hosts_to_test, time.time(), metrics)
        return metrics

    def _ping_host(self, host: str, count: int = 4) -> Tuple[Optional[float], bool]:
        """Ping a host and return average latency and packet loss."""
        try:
            # Validate and sanitize inputs
            safe_host = InputValidator.validate_ip_address(host) if self._is_ip_address(host) else self._validate_hostname(host)
            safe_count = max(1, min(10, int(count)))  # Limit count for DoS protection

            # Rate limiting for ping operations
            if not rate_limiter.is_allowed(f"ping_{safe_host}", limit=5, window=60):
                logger.warning(f"Rate limit exceeded for ping to {safe_host}")
                return None, True

            import platform
            system = platform.system().lower()

            if system == 'windows':
                result = self._safe_run_command(
                    'ping',
                    ['-n', str(safe_count), safe_host],
                    timeout=30,
                )
            else:
                result = self._safe_run_command(
                    'ping',
                    ['-c', str(safe_count), safe_host],
                    timeout=30,
                )

            if result and result.returncode == 0:
                output = result.stdout
                latencies = []

                # Parse latencies
                for line in output.split('\n'):
                    if 'time=' in line or 'time<' in line:
                        try:
                            time_part = line.split('time')[1].split('ms')[0]
                            if '<' in time_part:
                                latency = 1.0  # Very fast response
                            else:
                                time_part = time_part.replace('=', '').replace('<', '').strip()
                                latency = float(time_part)
                            latencies.append(latency)
                        except ValueError:
                            continue

                if latencies:
                    avg_latency = sum(latencies) / len(latencies)
                    packet_loss = len(latencies) < safe_count
                    return avg_latency, packet_loss

        except Exception:
            pass

        return None, True

    def _calculate_jitter(self, latencies: List[float]) -> float:
        """Calculate network jitter from latency measurements."""
        if len(latencies) < 2:
            return 0

        differences = []
        for i in range(1, len(latencies)):
            differences.append(abs(latencies[i] - latencies[i-1]))

        return sum(differences) / len(differences)

    def _test_bandwidth(self) -> Tuple[float, float]:
        """Test network bandwidth (simplified test)."""
        if not self._bandwidth_tests_enabled:
            with self._bandwidth_lock:
                self._bandwidth_failure_streak = 0
            return 0.0, 0.0

        current_time = time.time()

        # Check cooldown before acquiring lock
        if (
            not self._bandwidth_continuous
            and self._bandwidth_last_run is not None
            and current_time - self._bandwidth_last_run < self._bandwidth_cooldown
        ):
            return 0.0, 0.0

        # Rate limiting for bandwidth tests
        if not rate_limiter.is_allowed("bandwidth_test", limit=1, window=300):
            logger.warning("Rate limit exceeded for bandwidth test")
            return 0.0, 0.0

        # Get endpoints under lock
        with self._bandwidth_lock:
            test_url = self._bandwidth_endpoints.get("download")
            upload_url = self._bandwidth_endpoints.get("upload")

        if not test_url:
            with self._bandwidth_lock:
                self._bandwidth_failure_streak = 0
            return 0.0, 0.0

        # Validate endpoints
        if not self._is_allowed_https_target(test_url):
            security_logger.warning(
                "Blocked bandwidth test due to non-allowlisted download endpoint",
                extra={"download": test_url},
            )
            with self._bandwidth_lock:
                self._bandwidth_failure_streak = min(self._bandwidth_failure_streak + 1, 10)
            return 0.0, 0.0

        if upload_url and not self._is_allowed_https_target(upload_url):
            security_logger.warning(
                "Blocked bandwidth test due to non-allowlisted upload endpoint",
                extra={"upload": upload_url},
            )
            upload_url = None

        try:
            start_time = time.time()
            response = self._http_request("GET", test_url, timeout=15)
            download_time = time.time() - start_time

            if not response or download_time <= 0:
                logger.debug(
                    "Bandwidth test did not receive a valid response",
                    extra={
                        "download_url": test_url,
                        "download_time": download_time,
                        "response_received": bool(response),
                    },
                )
                with self._bandwidth_lock:
                    self._bandwidth_failure_streak = min(self._bandwidth_failure_streak + 1, 10)
                return 0.0, 0.0

            data_size_mb = len(response.content) / (1024 * 1024)
            download_speed = (data_size_mb / download_time) * 8 if download_time > 0 else 0.0

            # Simplified upload test
            upload_speed = 0.0
            if upload_url:
                try:
                    payload = response.content[:65536] if response.content else b"0" * 1024
                    upload_start = time.time()
                    upload_response = self._http_request(
                        "POST",
                        upload_url,
                        timeout=15,
                        data=payload,
                    )
                    upload_time = time.time() - upload_start
                    if upload_response and upload_time > 0:
                        upload_speed = (len(payload) / (1024 * 1024)) / upload_time * 8
                except Exception as exc:
                    logger.debug("Upload bandwidth test failed", exc_info=False, extra={"error": str(exc)})

            with self._bandwidth_lock:
                self._bandwidth_last_run = time.time()
                self._bandwidth_failure_streak = 0

            return download_speed, upload_speed

        except Exception as exc:
            with self._bandwidth_lock:
                self._bandwidth_failure_streak = min(self._bandwidth_failure_streak + 1, 10)
            logger.debug("Bandwidth test raised exception", exc_info=False, extra={"error": str(exc)})
            return 0.0, 0.0

    def _calculate_stability_score(self, latency: float, jitter: float, packet_loss: float) -> float:
        """Calculate connection stability score (0-100)."""
        if latency == float('inf'):
            return 0.0

        # Base score
        score = 100.0

        # Penalize high latency
        if latency > 100:
            score -= min(50, (latency - 100) / 10)
        elif latency > 50:
            score -= min(25, (latency - 50) / 5)

        # Penalize jitter
        if jitter > 20:
            score -= min(30, jitter - 20)

        # Penalize packet loss heavily
        score -= packet_loss * 2

        return max(0, score)

    def get_firewall_status(self) -> Dict[str, any]:
        """Get system firewall status and rules."""
        now = time.time()
        with self._firewall_lock:
            if (
                self._firewall_cache
                and now - self._firewall_cache[0] < self._firewall_cache_ttl
            ):
                return copy.deepcopy(self._firewall_cache[1])

        try:
            import platform
            system = platform.system().lower()

            if system == 'windows':
                status = self._get_windows_firewall_status()
            elif system == 'linux':
                status = self._get_linux_firewall_status()
            elif system == 'darwin':
                status = self._get_macos_firewall_status()
            else:
                status = {"status": "unknown", "platform": "unsupported"}
        except Exception as e:
            status = {"error": f"Could not check firewall status: {str(e)}"}

        with self._firewall_lock:
            self._firewall_cache = (time.time(), copy.deepcopy(status))
        return status

    def _get_windows_firewall_status(self) -> Dict[str, any]:
        """Get Windows Firewall status."""
        try:
            # Rate limit firewall status checks
            if not rate_limiter.is_allowed("firewall_check", limit=5, window=60):
                return {"error": "Rate limit exceeded"}

            result = self._safe_run_command(
                'netsh',
                ['advfirewall', 'show', 'allprofiles', 'state'],
                timeout=10,
            )

            status = {"platform": "windows", "profiles": {}}

            if result and result.returncode == 0:
                output = result.stdout
                current_profile = None

                for line in output.split('\n'):
                    if 'Profile' in line and 'Settings' in line:
                        current_profile = line.strip()
                    elif 'State' in line and current_profile:
                        state = line.split(':')[1].strip()
                        status["profiles"][current_profile] = state

            return status

        except Exception as e:
            return {"error": f"Windows firewall check failed: {str(e)}"}

    def _get_linux_firewall_status(self) -> Dict[str, any]:
        """Get Linux firewall status (ufw, iptables)."""
        try:
            # Rate limit firewall status checks
            if not rate_limiter.is_allowed("firewall_check", limit=5, window=60):
                return {"error": "Rate limit exceeded"}

            status = {"platform": "linux"}

            # Check ufw
            try:
                result = self._safe_run_command('ufw', ['status'], timeout=5)
                if result and result.returncode == 0:
                    status["ufw"] = "active" if "Status: active" in result.stdout else "inactive"
            except FileNotFoundError:
                status["ufw"] = "not_installed"

            # Check iptables
            try:
                result = self._safe_run_command('iptables', ['-L'], timeout=5)
                if result and result.returncode == 0:
                    rules_count = len([line for line in result.stdout.split('\n') if line.strip() and not line.startswith('Chain')])
                    status["iptables"] = f"{rules_count} rules"
            except (FileNotFoundError, PermissionError):
                status["iptables"] = "no_access"

            return status

        except Exception as e:
            return {"error": f"Linux firewall check failed: {str(e)}"}

    def _get_macos_firewall_status(self) -> Dict[str, any]:
        """Get macOS firewall status."""
        try:
            # Rate limit firewall status checks
            if not rate_limiter.is_allowed("firewall_check", limit=5, window=60):
                return {"error": "Rate limit exceeded"}

            # Avoid sudo for security - try without privileges first
            result = self._safe_run_command('pfctl', ['-s', 'info'], timeout=10)

            status = {"platform": "macos"}

            if result and result.returncode == 0:
                output = result.stdout
                if "Status: Enabled" in output:
                    status["pf_firewall"] = "enabled"
                else:
                    status["pf_firewall"] = "disabled"
            else:
                status["pf_firewall"] = "no_access"

            return status

        except Exception as e:
            return {"error": f"macOS firewall check failed: {str(e)}"}

    def detect_vpn_proxy(self) -> Dict[str, any]:
        """Detect VPN and proxy connections."""
        now = time.time()
        with self._vpn_lock:
            cached = self._vpn_cache
        if cached and now - cached[0] < self._vpn_cache_ttl:
            return copy.deepcopy(cached[1])

        detection_results = {
            "vpn_detected": False,
            "proxy_detected": False,
            "vpn_interfaces": [],
            "proxy_settings": {},
            "public_ip": None,
            "detected_location": None
        }

        try:
            # Check for VPN interfaces
            interfaces = self.get_network_interfaces()
            vpn_keywords = ['vpn', 'tun', 'tap', 'ppp', 'wg', 'openvpn']

            for interface in interfaces:
                if any(keyword in interface.name.lower() for keyword in vpn_keywords):
                    detection_results["vpn_interfaces"].append(interface.name)
                    detection_results["vpn_detected"] = True

            # Check system proxy settings
            proxy_settings = self._get_system_proxy_settings()
            if proxy_settings:
                detection_results["proxy_settings"] = proxy_settings
                detection_results["proxy_detected"] = True

            # Derive approximate location information from cached connection metadata
            location_snapshot = self._derive_location_snapshot()
            if location_snapshot:
                detection_results["public_ip"] = location_snapshot.get("address")
                detection_results["detected_location"] = {
                    "country": location_snapshot.get("country"),
                    "city": location_snapshot.get("city"),
                    "organization": location_snapshot.get("organization"),
                    "last_seen": location_snapshot.get("timestamp"),
                }

        except Exception as e:
            detection_results["error"] = str(e)

        with self._vpn_lock:
            self._vpn_cache = (time.time(), copy.deepcopy(detection_results))
        return detection_results

    def _derive_location_snapshot(self) -> Optional[Dict[str, Any]]:
        """Derive a representative location snapshot from cached connection metadata."""

        with self._cache_lock:
            if not self.connection_cache:
                return None

            freshest_entry = max(self.connection_cache.items(), key=lambda item: item[1][0], default=None)

        if not freshest_entry:
            return None

        cache_timestamp, payload = freshest_entry[1]
        if not payload:
            return None

        country = payload.get("country")
        city = payload.get("city")
        organization = payload.get("organization")

        return {
            "address": freshest_entry[0],
            "country": country,
            "city": city,
            "organization": organization,
            "timestamp": cache_timestamp,
        }

    def generate_network_health_report(self, *, force_refresh: bool = False) -> NetworkHealthReport:
        """Produce a consolidated health assessment with risk classification."""

        snapshot_time = time.time()
        if not force_refresh:
            with self._health_lock:
                if (
                    self._health_cache
                    and snapshot_time - self._health_cache[0] < self._health_cache_ttl
                ):
                    return copy.deepcopy(self._health_cache[1])

        connections = self.get_network_connections()
        interfaces = self.get_network_interfaces()
        quality = self.measure_network_quality(force_refresh=force_refresh)
        vpn_proxy = self.detect_vpn_proxy()
        firewall_status = self.get_firewall_status()

        suspicious_count = sum(1 for c in connections if c.is_suspicious)
        interfaces_up = sum(1 for iface in interfaces if iface.is_up)
        interfaces_down = len(interfaces) - interfaces_up
        max_risk_score = max((c.risk_score or 0.0) for c in connections) if connections else 0.0
        recent_threat_events = self._get_recent_threat_events()

        advisories: List[str] = []
        risk_score = 0

        if suspicious_count:
            advisories.append(
                f"Detected {suspicious_count} connection(s) flagged as suspicious"
            )
            risk_score += min(40, suspicious_count * 10)

        if quality.packet_loss_percent > 5:
            advisories.append(
                f"Packet loss at {quality.packet_loss_percent:.1f}% exceeds 5% threshold"
            )
            risk_score += 25

        if quality.latency_ms > 120:
            advisories.append(
                f"Average latency {quality.latency_ms:.1f} ms is above nominal range"
            )
            risk_score += 15

        if interfaces_down:
            advisories.append(f"{interfaces_down} network interface(s) reported as down")
            risk_score += min(20, interfaces_down * 5)

        if vpn_proxy.get("vpn_detected"):
            advisories.append("VPN interface detected; validate authorized usage")
            risk_score += 10

        if vpn_proxy.get("proxy_detected"):
            advisories.append("System proxy settings detected; confirm policy compliance")
            risk_score += 10

        if max_risk_score >= self._threat_risk_threshold:
            advisories.append(
                f"Threat intelligence flagged active connection with risk {max_risk_score:.2f}"
            )
            risk_score += min(30, max_risk_score * 60)

        firewall_state = firewall_status.get("profiles") or firewall_status.get("status")
        if isinstance(firewall_state, dict):
            disabled_profiles = [
                name for name, state in firewall_state.items()
                if isinstance(state, str) and state.lower() != "on"
            ]
            if disabled_profiles:
                advisories.append(
                    "Firewall profiles disabled: " + ", ".join(disabled_profiles)
                )
                risk_score += min(25, len(disabled_profiles) * 10)
        elif isinstance(firewall_state, str) and firewall_state.lower() != "enabled":
            advisories.append("Firewall reported as disabled or unknown")
            risk_score += 20

        if firewall_status.get("error"):
            advisories.append("Firewall status retrieval error; investigate permissions")

        risk_level = "low"
        if risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"

        quality_snapshot = {
            "latency_ms": quality.latency_ms,
            "jitter_ms": quality.jitter_ms,
            "packet_loss_percent": quality.packet_loss_percent,
            "bandwidth_mbps": quality.bandwidth_mbps,
            "stability_score": quality.connection_stability,
        }

        with self._bandwidth_lock:
            bandwidth_failure_streak = self._bandwidth_failure_streak
            bandwidth_last_run = self._bandwidth_last_run

        if self._bandwidth_tests_enabled and bandwidth_failure_streak >= 3:
            advisories.append(
                "Bandwidth diagnostics have failed repeatedly; verify test endpoints and connectivity"
            )
            risk_score += min(10, bandwidth_failure_streak * 2)

        metadata = {
            "vpn_interfaces": vpn_proxy.get("vpn_interfaces", []),
            "proxy_settings_present": bool(vpn_proxy.get("proxy_settings")),
            "bandwidth_last_run": bandwidth_last_run,
            "bandwidth_failure_streak": bandwidth_failure_streak,
            "geoip_available": self.geoip_db is not None,
            "peak_connection_risk": max_risk_score,
            "recent_threat_events": recent_threat_events,
        }

        report = NetworkHealthReport(
            timestamp=snapshot_time,
            risk_level=risk_level,
            advisories=advisories,
            connection_count=len(connections),
            suspicious_connection_count=suspicious_count,
            interfaces_up=interfaces_up,
            interfaces_down=interfaces_down,
            vpn_detected=bool(vpn_proxy.get("vpn_detected")),
            proxy_detected=bool(vpn_proxy.get("proxy_detected")),
            bandwidth_tests_enabled=self._bandwidth_tests_enabled,
            firewall_status=firewall_status,
            quality_snapshot=quality_snapshot,
            metadata=metadata,
        )

        with self._health_lock:
            self._health_cache = (time.time(), copy.deepcopy(report))

        return report

    def _is_ip_address(self, host: str) -> bool:
        """Check if host is an IP address."""
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    def _validate_hostname(self, hostname: str) -> str:
        """Validate and sanitize hostname."""
        if not hostname or len(hostname) > 255:
            raise SecurityError("Invalid hostname length")

        # Check for dangerous characters
        if any(char in hostname for char in ['&', '|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r']):
            raise SecurityError("Invalid hostname characters")

        # Basic hostname validation
        import re
        hostname_pattern = re.compile(r'^[a-zA-Z0-9.-]+$')
        if not hostname_pattern.match(hostname):
            raise SecurityError("Invalid hostname format")

        return hostname

    def _get_system_proxy_settings(self) -> Dict[str, any]:
        """Get system proxy settings."""
        try:
            import platform
            system = platform.system().lower()

            if system == 'windows':
                return self._get_windows_proxy_settings()
            elif system == 'linux':
                return self._get_linux_proxy_settings()
            elif system == 'darwin':
                return self._get_macos_proxy_settings()

        except Exception:
            pass

        return {}

    def _get_windows_proxy_settings(self) -> Dict[str, any]:
        """Get Windows proxy settings from registry."""
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            )

            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            proxy_server = ""

            if proxy_enable:
                try:
                    proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                except FileNotFoundError:
                    pass

            winreg.CloseKey(key)

            return {
                "enabled": bool(proxy_enable),
                "server": proxy_server
            }

        except Exception:
            return {}

    def _get_linux_proxy_settings(self) -> Dict[str, any]:
        """Get Linux proxy settings from environment variables."""
        import os

        proxy_vars = ['http_proxy', 'https_proxy', 'ftp_proxy', 'all_proxy']
        settings = {}

        for var in proxy_vars:
            value = os.environ.get(var) or os.environ.get(var.upper())
            if value:
                settings[var] = value

        return settings

    def _get_macos_proxy_settings(self) -> Dict[str, any]:
        """Get macOS proxy settings."""
        try:
            result = self._safe_run_command('scutil', ['--proxy'], timeout=5)

            if result and result.returncode == 0:
                settings = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        settings[key.strip()] = value.strip()
                return settings

        except Exception:
            pass

        return {}

    def export_network_data(
        self,
        file_path: Path,
        *,
        compress: bool = False,
        max_bytes: Optional[int] = None,
        compresslevel: int = 5,
    ) -> bool:
        """Export comprehensive network data to JSON."""
        with self._export_lock:
            try:
                resolved_path = self._resolve_export_path(
                    file_path,
                    default_suffix=".json.gz" if compress else ".json",
                )
            except ValidationError as exc:
                security_logger.warning(
                    "Rejected network data export request",
                    extra={"error": str(exc), "path": InputValidator.sanitize_log_data(str(file_path))},
                )
                return False

            try:
                connections = self.get_network_connections(include_localhost=True)
                interfaces = self.get_network_interfaces()
                quality_metrics = self.measure_network_quality()
                firewall_status = self.get_firewall_status()
                vpn_proxy_info = self.detect_vpn_proxy()
                health_report = self.generate_network_health_report(force_refresh=True)

                export_data = {
                    "timestamp": int(time.time() * 1000),
                    "connections": [InputValidator.sanitize_log_data(asdict(conn)) for conn in connections],
                    "interfaces": [InputValidator.sanitize_log_data(asdict(iface)) for iface in interfaces],
                    "quality_metrics": InputValidator.sanitize_log_data(asdict(quality_metrics)),
                    "firewall_status": InputValidator.sanitize_log_data(firewall_status),
                    "vpn_proxy_detection": InputValidator.sanitize_log_data(vpn_proxy_info),
                    "health_report": InputValidator.sanitize_log_data(asdict(health_report)),
                    "metadata": {
                        "total_connections": len(connections),
                        "active_interfaces": len([i for i in interfaces if i.is_up]),
                        "geoip_available": self.geoip_db is not None,
                    },
                }

                payload_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")

                if max_bytes is not None and len(payload_bytes) > max_bytes:
                    security_logger.warning(
                        "Export aborted due to size limit",
                        extra={
                            "path": InputValidator.sanitize_log_data(str(resolved_path)),
                            "size_bytes": len(payload_bytes),
                            "max_bytes": max_bytes,
                            "compress": compress,
                        },
                    )
                    return False

                if compress:
                    try:
                        payload_bytes = self._compress_payload(payload_bytes, compresslevel=compresslevel)
                    except OSError as exc:
                        security_logger.warning(
                            "Compression failed for network export",
                            extra={
                                "error": str(exc),
                                "path": InputValidator.sanitize_log_data(str(resolved_path)),
                            },
                        )
                        return False

                if max_bytes is not None and len(payload_bytes) > max_bytes:
                    security_logger.warning(
                        "Compressed export exceeds size limit",
                        extra={
                            "path": InputValidator.sanitize_log_data(str(resolved_path)),
                            "size_bytes": len(payload_bytes),
                            "max_bytes": max_bytes,
                            "compress": compress,
                        },
                    )
                    return False

                if not self._file_handler.write_file(resolved_path, payload_bytes):
                    security_logger.warning(
                        "Secure file handler rejected network export",
                        extra={"path": InputValidator.sanitize_log_data(str(resolved_path))},
                    )
                    return False

                security_logger.info(
                    "Network data export completed",
                    extra={"path": InputValidator.sanitize_log_data(str(resolved_path))},
                )
                return True

            except Exception as exc:
                security_logger.warning(
                    "Network data export failed",
                    extra={"error": str(exc), "path": InputValidator.sanitize_log_data(str(resolved_path))},
                )
                return False