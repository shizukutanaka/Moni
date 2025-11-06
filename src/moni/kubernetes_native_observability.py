"""
Kubernetes-Native Observability with eBPF Integration
Advanced monitoring for cloud-native environments

Features:
- Kubernetes event monitoring
- Pod/node health tracking
- Network observability (eBPF-ready)
- Resource utilization analysis
- OpenTelemetry integration
- CNCF best practices compliance
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class ResourceType(Enum):
    """Kubernetes resource types."""
    POD = "pod"
    NODE = "node"
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    SERVICE = "service"
    INGRESS = "ingress"
    CONFIGMAP = "configmap"


class HealthStatus(Enum):
    """Health status for K8s resources."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class EventSeverity(Enum):
    """Kubernetes event severity."""
    NORMAL = "Normal"
    WARNING = "Warning"
    ERROR = "Error"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class KubernetesEvent:
    """Kubernetes cluster event."""
    event_id: str
    resource_type: ResourceType
    resource_name: str
    namespace: str
    severity: EventSeverity
    message: str
    reason: str
    count: int = 1
    first_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PodMetrics:
    """Pod resource metrics."""
    namespace: str
    pod_name: str
    container_name: str

    cpu_usage_cores: float  # CPU usage in millicores
    memory_usage_bytes: float  # Memory in bytes
    cpu_limit_cores: float
    memory_limit_bytes: float

    disk_read_bytes: float
    disk_write_bytes: float
    network_rx_bytes: float
    network_tx_bytes: float

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def cpu_utilization_percent(self) -> float:
        """CPU utilization as percentage."""
        if self.cpu_limit_cores == 0:
            return 0.0
        return (self.cpu_usage_cores / self.cpu_limit_cores) * 100

    def memory_utilization_percent(self) -> float:
        """Memory utilization as percentage."""
        if self.memory_limit_bytes == 0:
            return 0.0
        return (self.memory_usage_bytes / self.memory_limit_bytes) * 100


@dataclass
class NodeMetrics:
    """Node cluster metrics."""
    node_name: str
    cpu_available_cores: float
    memory_available_bytes: float
    cpu_allocatable_cores: float
    memory_allocatable_bytes: float

    pods_running: int
    pods_pending: int
    pods_failed: int

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def node_capacity_percent(self) -> float:
        """Node capacity utilization."""
        if self.cpu_allocatable_cores == 0:
            return 0.0
        # Simplified calculation
        return min((self.pods_running / max(self.pods_running + self.pods_pending + 1)) * 100, 100.0)


@dataclass
class NetworkTraffic:
    """Network traffic metrics (eBPF-based)."""
    source_pod: str
    source_namespace: str
    dest_pod: str
    dest_namespace: str
    protocol: str  # TCP, UDP, etc.
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    errors: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Kubernetes Event Collector
# ============================================================================

class KubernetesEventCollector:
    """Collect and analyze Kubernetes cluster events."""

    def __init__(self):
        """Initialize event collector."""
        self.events: Dict[str, KubernetesEvent] = {}
        self.event_history: List[KubernetesEvent] = []
        self.lock = threading.RLock()

    def add_event(self, event: KubernetesEvent) -> None:
        """Add Kubernetes event."""
        with self.lock:
            # Aggregate events
            key = f"{event.resource_type.value}:{event.namespace}:{event.resource_name}"

            if key in self.events:
                existing = self.events[key]
                existing.count += event.count
                existing.last_timestamp = event.last_timestamp
            else:
                self.events[key] = event

            self.event_history.append(event)

    def get_events_by_severity(self, severity: EventSeverity) -> List[KubernetesEvent]:
        """Get events filtered by severity."""
        with self.lock:
            return [e for e in self.events.values() if e.severity == severity]

    def get_events_by_resource(self, resource_type: ResourceType,
                              namespace: Optional[str] = None) -> List[KubernetesEvent]:
        """Get events filtered by resource type."""
        with self.lock:
            events = [e for e in self.events.values() if e.resource_type == resource_type]
            if namespace:
                events = [e for e in events if e.namespace == namespace]
            return events

    def get_error_count(self, time_window_minutes: int = 60) -> int:
        """Get error event count in time window."""
        with self.lock:
            cutoff_time = datetime.now(timezone.utc) - \
                         __import__('datetime').timedelta(minutes=time_window_minutes)
            return sum(
                e.count for e in self.events.values()
                if e.severity == EventSeverity.ERROR and e.last_timestamp >= cutoff_time
            )


# ============================================================================
# Pod Health Monitor
# ============================================================================

class PodHealthMonitor:
    """Monitor pod health and resource utilization."""

    def __init__(self):
        """Initialize pod monitor."""
        self.pod_metrics: Dict[str, List[PodMetrics]] = {}
        self.health_status: Dict[str, HealthStatus] = {}
        self.lock = threading.RLock()

    def record_metrics(self, metrics: PodMetrics) -> None:
        """Record pod metrics."""
        with self.lock:
            key = f"{metrics.namespace}/{metrics.pod_name}/{metrics.container_name}"

            if key not in self.pod_metrics:
                self.pod_metrics[key] = []

            self.pod_metrics[key].append(metrics)

            # Keep only last 1000 samples
            if len(self.pod_metrics[key]) > 1000:
                self.pod_metrics[key] = self.pod_metrics[key][-1000:]

            # Update health status
            self._update_health_status(key, metrics)

    def get_pod_health(self, namespace: str, pod_name: str) -> HealthStatus:
        """Get pod health status."""
        with self.lock:
            key = f"{namespace}/{pod_name}/*"
            # Find matching pods
            matching_status = [
                self.health_status[k] for k in self.health_status
                if k.startswith(key.replace("/*", ""))
            ]
            if matching_status:
                return max(matching_status, key=lambda s: s.value == "unhealthy")
            return HealthStatus.UNKNOWN

    def _update_health_status(self, key: str, metrics: PodMetrics) -> None:
        """Update health status based on metrics."""
        cpu_util = metrics.cpu_utilization_percent()
        mem_util = metrics.memory_utilization_percent()

        if cpu_util > 95 or mem_util > 95:
            self.health_status[key] = HealthStatus.UNHEALTHY
        elif cpu_util > 80 or mem_util > 80:
            self.health_status[key] = HealthStatus.DEGRADED
        else:
            self.health_status[key] = HealthStatus.HEALTHY


# ============================================================================
# Network Observability (eBPF-ready)
# ============================================================================

class NetworkObservability:
    """Network traffic analysis for service-to-service communication."""

    def __init__(self):
        """Initialize network observability."""
        self.traffic_flows: Dict[str, List[NetworkTraffic]] = {}
        self.service_dependencies: Dict[str, Set[str]] = {}
        self.lock = threading.RLock()

    def record_traffic(self, traffic: NetworkTraffic) -> None:
        """Record network traffic flow."""
        with self.lock:
            flow_key = f"{traffic.source_pod}→{traffic.dest_pod}"

            if flow_key not in self.traffic_flows:
                self.traffic_flows[flow_key] = []

            self.traffic_flows[flow_key].append(traffic)

            # Update service dependencies
            source_key = f"{traffic.source_namespace}/{traffic.source_pod.split('-')[0]}"
            dest_key = f"{traffic.dest_namespace}/{traffic.dest_pod.split('-')[0]}"

            if source_key not in self.service_dependencies:
                self.service_dependencies[source_key] = set()

            self.service_dependencies[source_key].add(dest_key)

    def get_service_topology(self) -> Dict[str, List[str]]:
        """Get service dependency topology."""
        with self.lock:
            return {k: list(v) for k, v in self.service_dependencies.items()}

    def get_latency_for_flow(self, source: str, dest: str) -> float:
        """Get average latency for service flow."""
        with self.lock:
            flow_key = f"{source}→{dest}"
            if flow_key not in self.traffic_flows:
                return 0.0

            traffic_list = self.traffic_flows[flow_key]
            if not traffic_list:
                return 0.0

            avg_latency = sum(t.latency_ms for t in traffic_list) / len(traffic_list)
            return avg_latency


# ============================================================================
# Node Health Analyzer
# ============================================================================

class NodeHealthAnalyzer:
    """Analyze node cluster health."""

    def __init__(self):
        """Initialize node analyzer."""
        self.node_metrics: Dict[str, List[NodeMetrics]] = {}
        self.lock = threading.RLock()

    def record_node_metrics(self, metrics: NodeMetrics) -> None:
        """Record node metrics."""
        with self.lock:
            if metrics.node_name not in self.node_metrics:
                self.node_metrics[metrics.node_name] = []

            self.node_metrics[metrics.node_name].append(metrics)

            # Keep only last 100 samples per node
            if len(self.node_metrics[metrics.node_name]) > 100:
                self.node_metrics[metrics.node_name] = \
                    self.node_metrics[metrics.node_name][-100:]

    def get_cluster_health(self) -> Dict[str, Any]:
        """Get overall cluster health."""
        with self.lock:
            total_nodes = len(self.node_metrics)
            total_pods = 0
            failed_pods = 0

            for node_metrics_list in self.node_metrics.values():
                if node_metrics_list:
                    latest = node_metrics_list[-1]
                    total_pods += latest.pods_running + latest.pods_pending + latest.pods_failed
                    failed_pods += latest.pods_failed

            return {
                "total_nodes": total_nodes,
                "total_pods": total_pods,
                "failed_pods": failed_pods,
                "pod_failure_rate": (failed_pods / total_pods * 100) if total_pods > 0 else 0.0,
                "cluster_health": self._calculate_cluster_health(failed_pods, total_pods)
            }

    @staticmethod
    def _calculate_cluster_health(failed: int, total: int) -> str:
        """Calculate cluster health status."""
        if total == 0:
            return "unknown"
        failure_rate = (failed / total) * 100
        if failure_rate == 0:
            return "healthy"
        elif failure_rate < 5:
            return "degraded"
        else:
            return "unhealthy"


# ============================================================================
# OpenTelemetry Integration
# ============================================================================

class KubernetesOTelExporter:
    """Export Kubernetes metrics in OpenTelemetry format."""

    @staticmethod
    def pod_metrics_to_otel(metrics: PodMetrics) -> Dict[str, Any]:
        """Convert pod metrics to OTel format."""
        return {
            "resource": {
                "attributes": {
                    "service.name": f"{metrics.namespace}/{metrics.pod_name}",
                    "k8s.namespace.name": metrics.namespace,
                    "k8s.pod.name": metrics.pod_name,
                    "k8s.container.name": metrics.container_name
                }
            },
            "metrics": [
                {
                    "name": "k8s.pod.cpu.usage",
                    "value": metrics.cpu_usage_cores,
                    "unit": "m"  # millicores
                },
                {
                    "name": "k8s.pod.memory.usage",
                    "value": metrics.memory_usage_bytes,
                    "unit": "By"
                },
                {
                    "name": "k8s.pod.network.io",
                    "attributes": {
                        "direction": "receive"
                    },
                    "value": metrics.network_rx_bytes
                }
            ]
        }


# Singleton instances
_event_collector: Optional[KubernetesEventCollector] = None
_pod_monitor: Optional[PodHealthMonitor] = None
_network_obs: Optional[NetworkObservability] = None
_node_analyzer: Optional[NodeHealthAnalyzer] = None


def get_event_collector() -> KubernetesEventCollector:
    """Get or create event collector."""
    global _event_collector
    if _event_collector is None:
        _event_collector = KubernetesEventCollector()
    return _event_collector


def get_pod_monitor() -> PodHealthMonitor:
    """Get or create pod monitor."""
    global _pod_monitor
    if _pod_monitor is None:
        _pod_monitor = PodHealthMonitor()
    return _pod_monitor


def get_network_observability() -> NetworkObservability:
    """Get or create network observability."""
    global _network_obs
    if _network_obs is None:
        _network_obs = NetworkObservability()
    return _network_obs


def get_node_analyzer() -> NodeHealthAnalyzer:
    """Get or create node analyzer."""
    global _node_analyzer
    if _node_analyzer is None:
        _node_analyzer = NodeHealthAnalyzer()
    return _node_analyzer
