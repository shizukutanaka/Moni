"""
Container Monitoring Module for Docker and Kubernetes

This module provides comprehensive monitoring for containerized environments,
including Docker containers and Kubernetes pods/deployments.
"""

import logging
import time
import subprocess
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import threading

logger = logging.getLogger(__name__)


@dataclass
class ContainerInfo:
    """Information about a container."""
    id: str
    name: str
    image: str
    status: str
    ports: List[str]
    cpu_percent: float
    memory_usage: float
    memory_limit: float
    network_rx: int
    network_tx: int
    created: float
    health_status: Optional[str] = None


@dataclass
class KubernetesPod:
    """Information about a Kubernetes pod."""
    name: str
    namespace: str
    status: str
    node: str
    containers: List[str]
    cpu_usage: float
    memory_usage: float
    restart_count: int
    age: str
    cpu_cost_per_hour: float = 0.0
    memory_cost_per_hour: float = 0.0
    total_cost_per_hour: float = 0.0


@dataclass
class CostBreakdown:
    """Cost breakdown for Kubernetes resources."""
    namespace: str
    pods_cost: float
    services_cost: float
    storage_cost: float
    network_cost: float
    total_cost: float
    efficiency_score: float  # 0-100, higher is better


@dataclass
class CloudCostConfig:
    """Configuration for cloud cost calculations."""
    cpu_cost_per_core_hour: float = 0.0464  # AWS EC2 c5.large example
    memory_cost_per_gb_hour: float = 0.0053  # AWS EC2 memory cost
    storage_cost_per_gb_hour: float = 0.00011  # AWS EBS gp3
    network_cost_per_gb: float = 0.09  # AWS data transfer
    region: str = "us-east-1"
    provider: str = "aws"


class ContainerMonitor:
    """
    Monitor Docker containers and Kubernetes resources.

    Provides real-time monitoring of container metrics including
    CPU, memory, network usage, and health status.
    Kubecost-style cost monitoring and optimization.
    """

    def __init__(self):
        self.docker_available = self._check_docker_available()
        self.kubectl_available = self._check_kubectl_available()
        self._cache = {}
        self._cache_timeout = 30  # seconds
        self._last_update = 0
        self.cost_config = CloudCostConfig()
        self._cost_cache = {}
        self._cost_cache_timeout = 300  # 5 minutes for cost data

    def _check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_kubectl_available(self) -> bool:
        """Check if kubectl is available."""
        try:
            result = subprocess.run(
                ['kubectl', 'version', '--client', '--short'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_docker_containers(self) -> List[ContainerInfo]:
        """Get information about all Docker containers."""
        if not self.docker_available:
            return []

        try:
            # Get container stats
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"Docker stats failed: {result.stderr}")
                return []

            containers = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        data = json.loads(line)
                        container = self._parse_docker_stats(data)
                        if container:
                            containers.append(container)
                    except json.JSONDecodeError:
                        continue

            return containers

        except (subprocess.TimeoutExpired, Exception) as e:
            logger.error(f"Failed to get Docker containers: {e}")
            return []

    def _parse_docker_stats(self, data: Dict[str, Any]) -> Optional[ContainerInfo]:
        """Parse Docker stats JSON data."""
        try:
            # Get basic container info
            container_id = data.get('Container', '')
            name = data.get('Name', '').lstrip('/')

            if not container_id or not name:
                return None

            # Parse CPU percentage
            cpu_str = data.get('CPUPerc', '0%')
            cpu_percent = float(cpu_str.rstrip('%'))

            # Parse memory usage
            mem_usage_str = data.get('MemUsage', '0B / 0B')
            mem_parts = mem_usage_str.split(' / ')
            if len(mem_parts) == 2:
                memory_usage = self._parse_bytes(mem_parts[0])
                memory_limit = self._parse_bytes(mem_parts[1])
            else:
                memory_usage = 0
                memory_limit = 0

            # Parse network I/O
            net_str = data.get('NetIO', '0B / 0B')
            net_parts = net_str.split(' / ')
            if len(net_parts) == 2:
                network_rx = self._parse_bytes(net_parts[0])
                network_tx = self._parse_bytes(net_parts[1])
            else:
                network_rx = 0
                network_tx = 0

            # Get additional container details
            details = self._get_container_details(container_id)
            image = details.get('image', '')
            status = details.get('status', 'unknown')
            ports = details.get('ports', [])
            created = details.get('created', 0)
            health_status = details.get('health', None)

            return ContainerInfo(
                id=container_id,
                name=name,
                image=image,
                status=status,
                ports=ports,
                cpu_percent=cpu_percent,
                memory_usage=memory_usage,
                memory_limit=memory_limit,
                network_rx=network_rx,
                network_tx=network_tx,
                created=created,
                health_status=health_status
            )

        except Exception as e:
            logger.error(f"Failed to parse Docker stats: {e}")
            return None

    def _get_container_details(self, container_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific container."""
        try:
            result = subprocess.run(
                ['docker', 'inspect', container_id],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return {}

            data = json.loads(result.stdout)
            if not data:
                return {}

            container = data[0]
            config = container.get('Config', {})
            state = container.get('State', {})

            # Extract port mappings
            ports = []
            port_bindings = container.get('HostConfig', {}).get('PortBindings', {})
            for container_port, host_bindings in port_bindings.items():
                if host_bindings:
                    for binding in host_bindings:
                        host_ip = binding.get('HostIp', '0.0.0.0')
                        host_port = binding.get('HostPort', '')
                        ports.append(f"{host_ip}:{host_port}->{container_port}")

            return {
                'image': config.get('Image', ''),
                'status': state.get('Status', 'unknown'),
                'ports': ports,
                'created': container.get('Created', ''),
                'health': state.get('Health', {}).get('Status') if state.get('Health') else None
            }

        except Exception as e:
            logger.error(f"Failed to get container details: {e}")
            return {}

    def _parse_bytes(self, size_str: str) -> int:
        """Parse human-readable size string to bytes."""
        try:
            size_str = size_str.strip()
            if not size_str or size_str == '0B':
                return 0

            # Extract number and unit
            import re
            match = re.match(r'([\d.]+)\s*([KMGTPEZY]?i?B?)', size_str.upper())
            if not match:
                return 0

            number = float(match.group(1))
            unit = match.group(2)

            # Convert to bytes
            units = {
                'B': 1,
                'KB': 1024,
                'MB': 1024**2,
                'GB': 1024**3,
                'TB': 1024**4,
                'PB': 1024**5,
                'EB': 1024**6,
                'ZB': 1024**7,
                'YB': 1024**8,
                'KIB': 1024,
                'MIB': 1024**2,
                'GIB': 1024**3,
                'TIB': 1024**4,
                'PIB': 1024**5,
                'EIB': 1024**6,
                'ZIB': 1024**7,
                'YIB': 1024**8,
            }

            multiplier = units.get(unit, 1)
            return int(number * multiplier)

        except Exception:
            return 0

    def get_kubernetes_pods(self, namespace: Optional[str] = None) -> List[KubernetesPod]:
        """Get information about Kubernetes pods."""
        if not self.kubectl_available:
            return []

        try:
            # Build kubectl command
            cmd = ['kubectl', 'get', 'pods', '--output=json']
            if namespace:
                cmd.extend(['--namespace', namespace])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"kubectl get pods failed: {result.stderr}")
                return []

            data = json.loads(result.stdout)
            pods = []

            for item in data.get('items', []):
                pod = self._parse_kubernetes_pod(item)
                if pod:
                    pods.append(pod)

            return pods

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to get Kubernetes pods: {e}")
            return []

    def _parse_kubernetes_pod(self, data: Dict[str, Any]) -> Optional[KubernetesPod]:
        """Parse Kubernetes pod data."""
        try:
            metadata = data.get('metadata', {})
            status = data.get('status', {})
            spec = data.get('spec', {})

            name = metadata.get('name', '')
            namespace = metadata.get('namespace', 'default')
            pod_status = status.get('phase', 'Unknown')

            # Get node name
            node = spec.get('nodeName', 'Unknown')

            # Get containers
            containers = []
            container_specs = spec.get('containers', [])
            for container in container_specs:
                containers.append(container.get('name', ''))

            # Calculate restart count
            restart_count = 0
            container_statuses = status.get('containerStatuses', [])
            for container_status in container_statuses:
                restart_count += container_status.get('restartCount', 0)

            # Get age
            creation_timestamp = metadata.get('creationTimestamp', '')
            age = self._calculate_age(creation_timestamp)

        # Calculate resource usage (simplified - would need metrics server for real data)
        cpu_usage = 0.0
        memory_usage = 0

        # Calculate costs using Kubecost-style methodology
        cpu_cost, memory_cost, total_cost = self._calculate_pod_cost(cpu_usage, memory_usage)

        return KubernetesPod(
            name=name,
            namespace=namespace,
            status=pod_status,
            node=node,
            containers=containers,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            restart_count=restart_count,
            age=age,
            cpu_cost_per_hour=cpu_cost,
            memory_cost_per_hour=memory_cost,
            total_cost_per_hour=total_cost
        )

        except Exception as e:
            logger.error(f"Failed to parse Kubernetes pod: {e}")
            return "Unknown"

    def _calculate_age(self, timestamp_str: str) -> str:
        """Calculate age from Kubernetes timestamp."""
        try:
            from datetime import datetime
            import dateutil.parser

            if not timestamp_str:
                return "Unknown"

            dt = dateutil.parser.parse(timestamp_str)
            now = datetime.now(dt.tzinfo)
            diff = now - dt

            if diff.days > 0:
                return f"{diff.days}d"
            elif diff.seconds >= 3600:
                return f"{diff.seconds // 3600}h"
            elif diff.seconds >= 60:
                return f"{diff.seconds // 60}m"
            else:
                return f"{diff.seconds}s"

        except Exception:
            return "Unknown"

    def get_container_summary(self) -> Dict[str, Any]:
        """Get a summary of container monitoring data."""
        summary = {
            'docker_available': self.docker_available,
            'kubectl_available': self.kubectl_available,
            'docker_containers': [],
            'kubernetes_pods': [],
            'kubernetes_costs': {}
        }

        if self.docker_available:
            containers = self.get_docker_containers()
            summary['docker_containers'] = [
                {
                    'name': c.name,
                    'status': c.status,
                    'cpu_percent': c.cpu_percent,
                    'memory_usage': c.memory_usage,
                    'memory_limit': c.memory_limit
                } for c in containers
            ]

        if self.kubectl_available:
            pods = self.get_kubernetes_pods()
            summary['kubernetes_pods'] = [
                {
                    'name': p.name,
                    'namespace': p.namespace,
                    'status': p.status,
                    'restart_count': p.restart_count,
                    'cpu_cost_per_hour': p.cpu_cost_per_hour,
                    'memory_cost_per_hour': p.memory_cost_per_hour,
                    'total_cost_per_hour': p.total_cost_per_hour
                } for p in pods
            ]

            # Add cost analysis
            cost_analysis = self.get_kubernetes_cost_analysis()
            if 'error' not in cost_analysis:
                summary['kubernetes_costs'] = {
                    'cluster_total_cost_per_hour': cost_analysis['cluster_total_cost_per_hour'],
                    'cluster_total_cost_per_month': cost_analysis['cluster_total_cost_per_month'],
                    'recommendations': cost_analysis['recommendations']
                }

        return summary


# Global container monitor instance
_container_monitor = ContainerMonitor()


def get_container_monitor() -> ContainerMonitor:
    """Get the global container monitor instance."""
    return _container_monitor


def container_monitor_collector() -> Dict[str, str]:
    """
    Metric collector for container monitoring.
    This function integrates with the main metrics system.
    """
    try:
        monitor = get_container_monitor()
        summary = monitor.get_container_summary()

        result = {}

        # Docker status
        if summary['docker_available']:
            docker_containers = summary['docker_containers']
            result["🐳 Docker"] = f"{len(docker_containers)} containers running"

            # Show top containers by CPU usage
            if docker_containers:
                sorted_containers = sorted(docker_containers, key=lambda x: x['cpu_percent'], reverse=True)
                for i, container in enumerate(sorted_containers[:3], 1):
                    cpu = container['cpu_percent']
                    mem_mb = container['memory_usage'] / (1024**2)
                    result[f"  {i}. {container['name']}"] = f"CPU: {cpu:.1f}% | MEM: {mem_mb:.1f}MB"
        else:
            result["🐳 Docker"] = "Not available"

        # Kubernetes status and costs
        if summary['kubectl_available']:
            k8s_pods = summary['kubernetes_pods']
            result["☸️ Kubernetes"] = f"{len(k8s_pods)} pods"

            # Show cost information (Kubecost style)
            costs = summary.get('kubernetes_costs', {})
            if costs:
                hourly_cost = costs.get('cluster_total_cost_per_hour', 0)
                monthly_cost = costs.get('cluster_total_cost_per_month', 0)
                result["💰 Cluster Cost"] = f"${hourly_cost:.4f}/hr (${monthly_cost:.2f}/mo)"

                # Show top cost pods
                if k8s_pods:
                    sorted_pods = sorted(k8s_pods, key=lambda x: x['total_cost_per_hour'], reverse=True)
                    for i, pod in enumerate(sorted_pods[:2], 1):
                        cost = pod['total_cost_per_hour']
                        result[f"  Top Cost {i}"] = f"{pod['name']}: ${cost:.4f}/hr"

                # Show recommendations
                recommendations = costs.get('recommendations', [])
                if recommendations:
                    result["💡 Recommendation"] = recommendations[0][:50] + "..." if len(recommendations[0]) > 50 else recommendations[0]
            else:
                # Count pod statuses
                status_counts = {}
                for pod in k8s_pods:
                    status = pod['status']
                    status_counts[status] = status_counts.get(status, 0) + 1

                if status_counts:
                    status_str = " | ".join([f"{status}: {count}" for status, count in status_counts.items()])
                    result["  Pod Status"] = status_str
        else:
            result["☸️ Kubernetes"] = "Not available"

        return result

    except Exception as e:
        return {"Error": f"Container monitoring failed: {str(e)}"}
