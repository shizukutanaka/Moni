"""
Advanced Intrusion Detection System (IDS) for government-grade security monitoring.
Real-time threat detection, behavioral analysis, and security event correlation.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttackType(Enum):
    """Types of security attacks."""
    BRUTE_FORCE = "brute_force"
    PORT_SCAN = "port_scan"
    DDOS = "ddos"
    MALWARE = "malware"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    NETWORK_INTRUSION = "network_intrusion"
    SYSTEM_COMPROMISE = "system_compromise"


@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_id: str
    timestamp: datetime
    threat_level: ThreatLevel
    attack_type: AttackType
    source_ip: Optional[str]
    target_ip: Optional[str]
    source_port: Optional[int]
    target_port: Optional[int]
    process_name: Optional[str]
    process_pid: Optional[int]
    description: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    mitigation_actions: List[str] = field(default_factory=list)


@dataclass
class NetworkBaseline:
    """Network behavior baseline."""
    connections_per_minute: float
    bytes_sent_per_minute: float
    bytes_received_per_minute: float
    unique_ports_accessed: Set[int] = field(default_factory=set)
    established_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BehavioralAnalysis:
    """Advanced behavioral analysis for anomaly detection."""

    def __init__(self, window_size: int = 1000):
        """Initialize behavioral analysis."""
        self.window_size = window_size
        self.process_behavior = defaultdict(lambda: {
            'cpu_history': deque(maxlen=window_size),
            'memory_history': deque(maxlen=window_size),
            'io_history': deque(maxlen=window_size),
            'network_history': deque(maxlen=window_size)
        })
        self.network_baseline: Optional[NetworkBaseline] = None
        self.suspicious_patterns = {
            'rapid_connections': 50,  # connections per minute
            'unusual_ports': {21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995},
            'high_cpu_threshold': 90.0,
            'memory_leak_threshold': 1.5  # 150% increase
        }
        self._lock = threading.RLock()

    def establish_network_baseline(self, duration: int = 300) -> None:
        """Establish network behavior baseline over specified duration."""
        logger.info(f"Establishing network baseline over {duration} seconds")

        start_time = time.time()
        connection_counts = []
        bytes_sent_samples = []
        bytes_recv_samples = []
        all_ports = set()

        while time.time() - start_time < duration:
            try:
                # Sample network activity
                net_io = psutil.net_io_counters()
                connections = psutil.net_connections(kind='inet')

                connection_counts.append(len(connections))
                bytes_sent_samples.append(net_io.bytes_sent)
                bytes_recv_samples.append(net_io.bytes_recv)

                for conn in connections:
                    if conn.laddr:
                        all_ports.add(conn.laddr.port)
                    if conn.raddr:
                        all_ports.add(conn.raddr.port)

                time.sleep(10)  # Sample every 10 seconds

            except Exception as e:
                logger.warning(f"Error during baseline establishment: {e}")
                continue

        if connection_counts:
            self.network_baseline = NetworkBaseline(
                connections_per_minute=statistics.mean(connection_counts) * 6,  # Scale to per minute
                bytes_sent_per_minute=statistics.mean(bytes_sent_samples) * 6,
                bytes_received_per_minute=statistics.mean(bytes_recv_samples) * 6,
                unique_ports_accessed=all_ports
            )
            logger.info("Network baseline established successfully")

    def analyze_process_behavior(self, process: psutil.Process) -> Optional[SecurityEvent]:
        """Analyze individual process behavior for anomalies."""
        try:
            with self._lock:
                pid = process.pid
                proc_info = process.as_dict(['name', 'cpu_percent', 'memory_percent', 'io_counters'])

                # Update behavior history
                behavior = self.process_behavior[pid]
                behavior['cpu_history'].append(proc_info.get('cpu_percent', 0))
                behavior['memory_history'].append(proc_info.get('memory_percent', 0))

                io_counters = proc_info.get('io_counters')
                if io_counters:
                    behavior['io_history'].append(io_counters.read_bytes + io_counters.write_bytes)

                # Detect anomalies
                if len(behavior['cpu_history']) >= 10:
                    # High sustained CPU usage
                    recent_cpu = list(behavior['cpu_history'])[-10:]
                    if statistics.mean(recent_cpu) > self.suspicious_patterns['high_cpu_threshold']:
                        return SecurityEvent(
                            event_id=hashlib.md5(f"{pid}_high_cpu_{time.time()}".encode()).hexdigest()[:16],
                            timestamp=datetime.now(timezone.utc),
                            threat_level=ThreatLevel.MEDIUM,
                            attack_type=AttackType.SYSTEM_COMPROMISE,
                            source_ip=None,
                            target_ip=None,
                            source_port=None,
                            target_port=None,
                            process_name=proc_info.get('name'),
                            process_pid=pid,
                            description=f"Sustained high CPU usage detected: {statistics.mean(recent_cpu):.1f}%",
                            indicators={'avg_cpu': statistics.mean(recent_cpu)}
                        )

                    # Memory leak detection
                    if len(behavior['memory_history']) >= 20:
                        early_memory = statistics.mean(list(behavior['memory_history'])[:10])
                        recent_memory = statistics.mean(list(behavior['memory_history'])[-10:])

                        if recent_memory > early_memory * self.suspicious_patterns['memory_leak_threshold']:
                            return SecurityEvent(
                                event_id=hashlib.md5(f"{pid}_memory_leak_{time.time()}".encode()).hexdigest()[:16],
                                timestamp=datetime.now(timezone.utc),
                                threat_level=ThreatLevel.HIGH,
                                attack_type=AttackType.MALWARE,
                                source_ip=None,
                                target_ip=None,
                                source_port=None,
                                target_port=None,
                                process_name=proc_info.get('name'),
                                process_pid=pid,
                                description=f"Potential memory leak detected: {early_memory:.1f}% -> {recent_memory:.1f}%",
                                indicators={'early_memory': early_memory, 'recent_memory': recent_memory}
                            )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
        except Exception as e:
            logger.error(f"Process behavior analysis error: {e}")
            return None

        return None

    def analyze_network_behavior(self) -> List[SecurityEvent]:
        """Analyze network behavior for anomalies."""
        events = []

        try:
            connections = psutil.net_connections(kind='inet')
            current_time = datetime.now(timezone.utc)

            # Analyze connection patterns
            connection_analysis = self._analyze_connections(connections, current_time)
            events.extend(connection_analysis)

            # Port scan detection
            port_scan_events = self._detect_port_scans(connections, current_time)
            events.extend(port_scan_events)

            # Unusual traffic patterns
            if self.network_baseline:
                traffic_events = self._detect_unusual_traffic(connections, current_time)
                events.extend(traffic_events)

        except Exception as e:
            logger.error(f"Network behavior analysis error: {e}")

        return events

    def _analyze_connections(self, connections: List, current_time: datetime) -> List[SecurityEvent]:
        """Analyze network connections for suspicious patterns."""
        events = []
        connection_by_ip = defaultdict(list)

        for conn in connections:
            if conn.raddr:
                try:
                    ip = ipaddress.ip_address(conn.raddr.ip)
                    if not ip.is_private:  # Focus on external connections
                        connection_by_ip[conn.raddr.ip].append(conn)
                except ValueError:
                    continue

        # Detect rapid connections to same IP
        for ip, conns in connection_by_ip.items():
            if len(conns) > self.suspicious_patterns['rapid_connections']:
                events.append(SecurityEvent(
                    event_id=hashlib.md5(f"rapid_conn_{ip}_{time.time()}".encode()).hexdigest()[:16],
                    timestamp=current_time,
                    threat_level=ThreatLevel.HIGH,
                    attack_type=AttackType.DDOS,
                    source_ip=ip,
                    target_ip=self._get_local_ip(),
                    source_port=None,
                    target_port=None,
                    process_name=None,
                    process_pid=None,
                    description=f"Rapid connections detected from {ip}: {len(conns)} connections",
                    indicators={'connection_count': len(conns), 'target_ip': ip}
                ))

        return events

    def _detect_port_scans(self, connections: List, current_time: datetime) -> List[SecurityEvent]:
        """Detect potential port scanning activities."""
        events = []
        ip_port_map = defaultdict(set)

        for conn in connections:
            if conn.raddr:
                ip_port_map[conn.raddr.ip].add(conn.laddr.port if conn.laddr else 0)

        # Detect scanning of multiple ports from same IP
        for ip, ports in ip_port_map.items():
            if len(ports) > 10:  # Scanning threshold
                try:
                    ip_obj = ipaddress.ip_address(ip)
                    if not ip_obj.is_private:
                        events.append(SecurityEvent(
                            event_id=hashlib.md5(f"port_scan_{ip}_{time.time()}".encode()).hexdigest()[:16],
                            timestamp=current_time,
                            threat_level=ThreatLevel.HIGH,
                            attack_type=AttackType.PORT_SCAN,
                            source_ip=ip,
                            target_ip=self._get_local_ip(),
                            source_port=None,
                            target_port=None,
                            process_name=None,
                            process_pid=None,
                            description=f"Port scan detected from {ip}: {len(ports)} ports accessed",
                            indicators={'ports_scanned': len(ports), 'source_ip': ip}
                        ))
                except ValueError:
                    continue

        return events

    def _detect_unusual_traffic(self, connections: List, current_time: datetime) -> List[SecurityEvent]:
        """Detect unusual traffic patterns based on baseline."""
        events = []

        if not self.network_baseline:
            return events

        current_connection_count = len(connections)
        baseline_connections = self.network_baseline.connections_per_minute

        # Detect connection count anomalies
        if current_connection_count > baseline_connections * 3:  # 300% of baseline
            events.append(SecurityEvent(
                event_id=hashlib.md5(f"traffic_anomaly_{time.time()}".encode()).hexdigest()[:16],
                timestamp=current_time,
                threat_level=ThreatLevel.MEDIUM,
                attack_type=AttackType.NETWORK_INTRUSION,
                source_ip=None,
                target_ip=None,
                source_port=None,
                target_port=None,
                process_name=None,
                process_pid=None,
                description=f"Unusual traffic pattern: {current_connection_count} vs baseline {baseline_connections:.0f}",
                indicators={'current_connections': current_connection_count, 'baseline_connections': baseline_connections}
            ))

        return events

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"


class SignatureDetection:
    """Signature-based detection system for known threats."""

    def __init__(self):
        """Initialize signature detection."""
        self.malware_signatures = self._load_malware_signatures()
        self.network_signatures = self._load_network_signatures()
        self.file_hashes = set()

    def _load_malware_signatures(self) -> Dict[str, Dict[str, Any]]:
        """Load malware signatures database."""
        return {
            'suspicious_processes': {
                'patterns': [
                    r'.*\.(exe|scr|com|bat|pif)\.exe$',  # Double extensions
                    r'^[a-f0-9]{8,}\.exe$',  # Random hex names
                    r'(miner|mining|crypto)',  # Cryptocurrency miners
                    r'(keylog|logger|stealer)',  # Malicious tools
                    r'(trojan|backdoor|rootkit)',  # Known malware types
                ],
                'threat_level': ThreatLevel.HIGH
            },
            'suspicious_network': {
                'c2_domains': [
                    'malicious-domain.com',
                    'c2-server.net',
                    'botnet-command.org'
                ],
                'suspicious_ports': [6667, 6668, 6669, 1337, 31337],  # IRC, elite ports
                'threat_level': ThreatLevel.CRITICAL
            }
        }

    def _load_network_signatures(self) -> Dict[str, Any]:
        """Load network attack signatures."""
        return {
            'sql_injection': {
                'patterns': [
                    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
                    r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
                    r"w*((\%27)|(\')){1,}((\%6F)|o|(\%4F))((\%72)|r|(\%52))"
                ],
                'threat_level': ThreatLevel.HIGH
            },
            'xss_attempt': {
                'patterns': [
                    r"<script[^>]*>.*?</script>",
                    r"javascript:",
                    r"on\w+\s*="
                ],
                'threat_level': ThreatLevel.MEDIUM
            }
        }

    def check_process_signatures(self, process: psutil.Process) -> Optional[SecurityEvent]:
        """Check process against malware signatures."""
        try:
            proc_info = process.as_dict(['name', 'exe', 'cmdline'])
            process_name = proc_info.get('name', '')
            process_exe = proc_info.get('exe', '')
            cmdline = ' '.join(proc_info.get('cmdline', []))

            # Check suspicious process patterns
            for pattern in self.malware_signatures['suspicious_processes']['patterns']:
                if re.search(pattern, process_name, re.IGNORECASE) or \
                   re.search(pattern, process_exe, re.IGNORECASE) or \
                   re.search(pattern, cmdline, re.IGNORECASE):

                    return SecurityEvent(
                        event_id=hashlib.md5(f"signature_{process.pid}_{time.time()}".encode()).hexdigest()[:16],
                        timestamp=datetime.now(timezone.utc),
                        threat_level=self.malware_signatures['suspicious_processes']['threat_level'],
                        attack_type=AttackType.MALWARE,
                        source_ip=None,
                        target_ip=None,
                        source_port=None,
                        target_port=None,
                        process_name=process_name,
                        process_pid=process.pid,
                        description=f"Suspicious process signature detected: {process_name}",
                        indicators={'pattern_matched': pattern, 'executable': process_exe}
                    )

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            logger.error(f"Process signature check error: {e}")

        return None

    def check_network_signatures(self, data: str, source_ip: str = None) -> List[SecurityEvent]:
        """Check network data against attack signatures."""
        events = []
        current_time = datetime.now(timezone.utc)

        for attack_type, signature_data in self.network_signatures.items():
            for pattern in signature_data['patterns']:
                if re.search(pattern, data, re.IGNORECASE):
                    events.append(SecurityEvent(
                        event_id=hashlib.md5(f"network_sig_{attack_type}_{time.time()}".encode()).hexdigest()[:16],
                        timestamp=current_time,
                        threat_level=signature_data['threat_level'],
                        attack_type=AttackType.NETWORK_INTRUSION,
                        source_ip=source_ip,
                        target_ip=None,
                        source_port=None,
                        target_port=None,
                        process_name=None,
                        process_pid=None,
                        description=f"Network attack signature detected: {attack_type}",
                        indicators={'pattern_matched': pattern, 'attack_type': attack_type}
                    ))

        return events


class IntrusionDetectionSystem:
    """Comprehensive intrusion detection system."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize IDS."""
        self.config_dir = config_dir or Path.home() / ".config" / "moni"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.behavioral_analysis = BehavioralAnalysis()
        self.signature_detection = SignatureDetection()
        self.events = deque(maxlen=10000)  # Store last 10,000 events
        self.event_correlator = EventCorrelator()
        self.is_monitoring = False
        self._monitor_thread = None
        self._lock = threading.RLock()

    def start_monitoring(self, baseline_duration: int = 300) -> None:
        """Start continuous intrusion detection monitoring."""
        if self.is_monitoring:
            logger.warning("IDS monitoring is already active")
            return

        logger.info("Starting intrusion detection system")

        # Establish baseline
        logger.info("Establishing behavioral baseline...")
        self.behavioral_analysis.establish_network_baseline(baseline_duration)

        self.is_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("IDS monitoring started successfully")

    def stop_monitoring(self) -> None:
        """Stop intrusion detection monitoring."""
        logger.info("Stopping intrusion detection system")
        self.is_monitoring = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                detected_events = []

                # Process behavior analysis
                for proc in psutil.process_iter():
                    try:
                        # Behavioral analysis
                        behavioral_event = self.behavioral_analysis.analyze_process_behavior(proc)
                        if behavioral_event:
                            detected_events.append(behavioral_event)

                        # Signature detection
                        signature_event = self.signature_detection.check_process_signatures(proc)
                        if signature_event:
                            detected_events.append(signature_event)

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Network behavior analysis
                network_events = self.behavioral_analysis.analyze_network_behavior()
                detected_events.extend(network_events)

                # Store and correlate events
                with self._lock:
                    for event in detected_events:
                        self.events.append(event)
                        logger.info(f"Security event detected: {event.description}")

                # Event correlation
                correlated_events = self.event_correlator.correlate_events(list(self.events)[-100:])
                for corr_event in correlated_events:
                    logger.warning(f"Correlated threat detected: {corr_event.description}")

                time.sleep(10)  # Monitor every 10 seconds

            except Exception as e:
                logger.error(f"IDS monitoring error: {e}")
                time.sleep(30)  # Wait longer on error

    def get_recent_events(self, limit: int = 100, threat_level: Optional[ThreatLevel] = None) -> List[SecurityEvent]:
        """Get recent security events."""
        with self._lock:
            events = list(self.events)

            if threat_level:
                events = [e for e in events if e.threat_level == threat_level]

            return events[-limit:]

    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        with self._lock:
            events = list(self.events)

        current_time = datetime.now(timezone.utc)

        # Event statistics
        event_stats = defaultdict(int)
        threat_stats = defaultdict(int)
        attack_stats = defaultdict(int)

        for event in events:
            event_stats['total'] += 1
            threat_stats[event.threat_level.value] += 1
            attack_stats[event.attack_type.value] += 1

        # Recent critical events (last 24 hours)
        recent_critical = [
            event for event in events
            if event.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH] and
               event.timestamp > current_time - timedelta(hours=24)
        ]

        return {
            'report_generated': current_time.isoformat(),
            'monitoring_active': self.is_monitoring,
            'total_events': len(events),
            'event_statistics': dict(event_stats),
            'threat_level_distribution': dict(threat_stats),
            'attack_type_distribution': dict(attack_stats),
            'recent_critical_events': len(recent_critical),
            'top_threats': [
                {'description': event.description, 'threat_level': event.threat_level.value}
                for event in recent_critical[:10]
            ]
        }


class EventCorrelator:
    """Advanced event correlation engine."""

    def __init__(self):
        """Initialize event correlator."""
        self.correlation_rules = self._load_correlation_rules()

    def _load_correlation_rules(self) -> Dict[str, Any]:
        """Load event correlation rules."""
        return {
            'coordinated_attack': {
                'events': [AttackType.PORT_SCAN, AttackType.BRUTE_FORCE, AttackType.UNAUTHORIZED_ACCESS],
                'time_window': 3600,  # 1 hour
                'minimum_events': 2,
                'threat_level': ThreatLevel.CRITICAL
            },
            'data_breach_sequence': {
                'events': [AttackType.PRIVILEGE_ESCALATION, AttackType.DATA_EXFILTRATION],
                'time_window': 1800,  # 30 minutes
                'minimum_events': 2,
                'threat_level': ThreatLevel.CRITICAL
            },
            'malware_infection': {
                'events': [AttackType.MALWARE, AttackType.NETWORK_INTRUSION],
                'time_window': 600,  # 10 minutes
                'minimum_events': 2,
                'threat_level': ThreatLevel.HIGH
            }
        }

    def correlate_events(self, events: List[SecurityEvent]) -> List[SecurityEvent]:
        """Correlate events to detect complex attack patterns."""
        correlated_events = []

        for rule_name, rule_config in self.correlation_rules.items():
            matching_events = self._find_matching_events(events, rule_config)

            if len(matching_events) >= rule_config['minimum_events']:
                # Create correlated event
                correlated_event = SecurityEvent(
                    event_id=hashlib.md5(f"correlated_{rule_name}_{time.time()}".encode()).hexdigest()[:16],
                    timestamp=datetime.now(timezone.utc),
                    threat_level=rule_config['threat_level'],
                    attack_type=AttackType.SYSTEM_COMPROMISE,
                    source_ip=self._extract_common_source(matching_events),
                    target_ip=None,
                    source_port=None,
                    target_port=None,
                    process_name=None,
                    process_pid=None,
                    description=f"Correlated attack pattern detected: {rule_name}",
                    indicators={
                        'correlated_rule': rule_name,
                        'matching_events': [e.event_id for e in matching_events],
                        'event_count': len(matching_events)
                    }
                )
                correlated_events.append(correlated_event)

        return correlated_events

    def _find_matching_events(self, events: List[SecurityEvent], rule_config: Dict[str, Any]) -> List[SecurityEvent]:
        """Find events matching correlation rule."""
        current_time = datetime.now(timezone.utc)
        time_threshold = current_time - timedelta(seconds=rule_config['time_window'])

        matching_events = []
        for event in events:
            if (event.attack_type in rule_config['events'] and
                event.timestamp > time_threshold):
                matching_events.append(event)

        return matching_events

    def _extract_common_source(self, events: List[SecurityEvent]) -> Optional[str]:
        """Extract common source IP from events."""
        source_ips = [event.source_ip for event in events if event.source_ip]
        if source_ips:
            # Return most common source IP
            return max(set(source_ips), key=source_ips.count)
        return None


# Global IDS instance
_ids_instance: Optional[IntrusionDetectionSystem] = None


def get_ids() -> IntrusionDetectionSystem:
    """Get or create global IDS instance."""
    global _ids_instance
    if _ids_instance is None:
        _ids_instance = IntrusionDetectionSystem()
    return _ids_instance


def initialize_ids(config_dir: Optional[Path] = None) -> IntrusionDetectionSystem:
    """Initialize the intrusion detection system."""
    global _ids_instance
    _ids_instance = IntrusionDetectionSystem(config_dir)
    logger.info("Intrusion Detection System initialized")
    return _ids_instance