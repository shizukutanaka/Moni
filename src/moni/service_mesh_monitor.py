"""
サービスメッシュ監視システム - Moni System Monitor

Istio統合によるマイクロサービス監視を提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ServiceInstance:
    """サービスインスタンス"""
    name: str
    namespace: str
    service_name: str
    pod_name: str
    node_name: str
    ip_address: str
    status: str
    start_time: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceCommunication:
    """サービス間通信"""
    source_service: str
    destination_service: str
    source_namespace: str
    destination_namespace: str
    protocol: str
    request_count: int
    error_count: int
    latency_p50: float
    latency_p95: float
    latency_p99: float
    timestamp: datetime


class ServiceMeshMonitor:
    """サービスメッシュ監視システム"""

    def __init__(self, istio_config_path: Optional[str] = None):
        self.istio_config_path = istio_config_path or "/etc/istio/config"
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
        self.jaeger_url = os.getenv('JAEGER_URL', 'http://jaeger:16686')

        self.services: Dict[str, ServiceInstance] = {}
        self.communications: deque = deque(maxlen=10000)
        self.mesh_topology: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.Lock()

        # Istioクライアントの初期化
        self._init_istio_client()

        # データ収集の開始
        self._start_data_collection()

    def _init_istio_client(self) -> None:
        """Istioクライアントを初期化"""
        try:
            # 実際の実装ではistioctlやIstio Pythonクライアントを使用
            logger.info("Istioクライアントを初期化しました。")

        except Exception as e:
            logger.error(f"Istioクライアント初期化エラー: {e}")

    def _start_data_collection(self) -> None:
        """データ収集を開始"""
        def collect_loop():
            while True:
                try:
                    self._collect_service_data()
                    self._collect_communication_data()
                    self._collect_mesh_metrics()
                    time.sleep(30)  # 30秒ごとに収集
                except Exception as e:
                    logger.error(f"サービスメッシュデータ収集エラー: {e}")
                    time.sleep(60)

        collect_thread = threading.Thread(target=collect_loop, daemon=True)
        collect_thread.start()
        logger.info("サービスメッシュ監視のデータ収集を開始しました。")

    def _collect_service_data(self) -> None:
        """サービスデータを収集"""
        try:
            # kubectlでIstioサービスデータを取得
            cmd = ['kubectl', 'get', 'pods', '--all-namespaces',
                   '-l', 'security.istio.io/tlsMode',  # Istioサイドカーインジェクション済みポッド
                   '-o', 'json']

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)

                services = []
                for item in data.get('items', []):
                    # Istioサイドカーがあるかチェック
                    if any(container.get('name', '').startswith('istio-') for container in item['spec']['containers']):
                        service = ServiceInstance(
                            name=item['metadata']['name'],
                            namespace=item['metadata']['namespace'],
                            service_name=item['metadata'].get('labels', {}).get('app', item['metadata']['name']),
                            pod_name=item['metadata']['name'],
                            node_name=item['spec']['nodeName'],
                            ip_address=item['status']['podIP'],
                            status=item['status']['phase'],
                            start_time=datetime.fromisoformat(item['status']['startTime'].replace('Z', '+00:00'))
                        )
                        services.append(service)

                with self._lock:
                    self.services = {s.name: s for s in services}

                logger.debug(f"{len(services)}個のIstioサービスインスタンスを発見しました。")

        except Exception as e:
            logger.error(f"サービスデータ収集エラー: {e}")

    def _collect_communication_data(self) -> None:
        """通信データを収集"""
        try:
            # Istioのテレメトリデータをクエリ
            # 実際の実装ではIstioのTelemetry APIやPrometheusをクエリ

            # モック通信データ生成
            for source_service in list(self.services.keys())[:5]:  # 簡易版
                for dest_service in list(self.services.keys())[:3]:
                    if source_service != dest_service:
                        communication = ServiceCommunication(
                            source_service=source_service,
                            destination_service=dest_service,
                            source_namespace=self.services[source_service].namespace,
                            destination_namespace=self.services[dest_service].namespace,
                            protocol='http',
                            request_count=int(time.time() % 100) + 1,
                            error_count=int((time.time() % 100) * 0.1),
                            latency_p50=50 + (time.time() % 50),
                            latency_p95=100 + (time.time() % 100),
                            latency_p99=200 + (time.time() % 200),
                            timestamp=datetime.now(timezone.utc)
                        )

                        with self._lock:
                            self.communications.append(communication)
                            self.mesh_topology[source_service].append(dest_service)

        except Exception as e:
            logger.error(f"通信データ収集エラー: {e}")

    def _collect_mesh_metrics(self) -> None:
        """メッシュメトリクスを収集"""
        try:
            # PrometheusからIstioメトリクスを収集
            istio_metrics = [
                'istio_requests_total',
                'istio_request_duration_milliseconds',
                'istio_request_bytes',
                'istio_response_bytes',
                'istio_tcp_connections_opened_total',
                'istio_tcp_connections_closed_total'
            ]

            for service in self.services.values():
                # 各サービスのメトリクスを収集（モック実装）
                service.metrics = {
                    'requests_per_second': (time.time() % 10) + 1,
                    'error_rate': (time.time() % 100) * 0.01,  # 0-1%
                    'average_latency_ms': 50 + (time.time() % 100),
                    'active_connections': int(time.time() % 20) + 1,
                    'cpu_usage': 30 + (time.time() % 40),
                    'memory_usage': 100 + (time.time() % 200)
                }

        except Exception as e:
            logger.error(f"メッシュメトリクス収集エラー: {e}")

    def get_service_mesh_topology(self) -> Dict[str, Any]:
        """サービスメッシュトポロジーを取得"""
        with self._lock:
            return {
                'services': [
                    {
                        'name': s.name,
                        'namespace': s.namespace,
                        'service_name': s.service_name,
                        'status': s.status,
                        'node': s.node_name,
                        'ip': s.ip_address,
                        'metrics': s.metrics,
                        'connections': self.mesh_topology.get(s.name, [])
                    }
                    for s in self.services.values()
                ],
                'communications': [
                    {
                        'source': c.source_service,
                        'destination': c.destination_service,
                        'source_ns': c.source_namespace,
                        'dest_ns': c.destination_namespace,
                        'protocol': c.protocol,
                        'requests': c.request_count,
                        'errors': c.error_count,
                        'latency_p50': c.latency_p50,
                        'latency_p95': c.latency_p95,
                        'latency_p99': c.latency_p99
                    }
                    for c in list(self.communications)[-100:]  # 直近100件
                ],
                'mesh_health': self._calculate_mesh_health()
            }

    def _calculate_mesh_health(self) -> Dict[str, Any]:
        """メッシュ健全性を計算"""
        total_services = len(self.services)
        healthy_services = len([s for s in self.services.values() if s.status == 'Running'])
        total_communications = len(self.communications)

        # エラーレートを計算
        recent_communications = list(self.communications)[-100:]
        total_requests = sum(c.request_count for c in recent_communications)
        total_errors = sum(c.error_count for c in recent_communications)
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

        return {
            'total_services': total_services,
            'healthy_services': healthy_services,
            'service_availability': (healthy_services / total_services * 100) if total_services > 0 else 0,
            'total_communications': total_communications,
            'error_rate_percent': error_rate,
            'mesh_status': 'healthy' if error_rate < 1.0 and healthy_services == total_services else 'degraded'
        }

    def get_service_details(self, service_name: str) -> Optional[Dict[str, Any]]:
        """サービス詳細を取得"""
        if service_name not in self.services:
            return None

        service = self.services[service_name]

        # 関連通信を取得
        related_communications = [
            c for c in self.communications
            if c.source_service == service_name or c.destination_service == service_name
        ]

        return {
            'service': {
                'name': service.name,
                'namespace': service.namespace,
                'service_name': service.service_name,
                'status': service.status,
                'node': service.node_name,
                'ip': service.ip_address,
                'start_time': service.start_time.isoformat(),
                'metrics': service.metrics
            },
            'communications': [
                {
                    'source': c.source_service,
                    'destination': c.destination_service,
                    'requests': c.request_count,
                    'errors': c.error_count,
                    'latency_p50': c.latency_p50,
                    'latency_p95': c.latency_p95,
                    'latency_p99': c.latency_p99
                }
                for c in related_communications[-50:]  # 直近50件
            ],
            'dependencies': self.mesh_topology.get(service_name, [])
        }

    def detect_service_anomalies(self) -> List[Dict[str, Any]]:
        """サービス異常を検知"""
        anomalies = []

        try:
            for service_name, service in self.services.items():
                # 異常検知ロジック（簡易版）
                anomaly_score = 0.0

                # エラーレートチェック
                recent_communications = [
                    c for c in list(self.communications)[-100:]
                    if c.source_service == service_name or c.destination_service == service_name
                ]

                if recent_communications:
                    total_requests = sum(c.request_count for c in recent_communications)
                    total_errors = sum(c.error_count for c in recent_communications)

                    if total_requests > 0:
                        error_rate = total_errors / total_requests
                        if error_rate > 0.05:  # 5%以上のエラーレート
                            anomaly_score += 0.5

                # レイテンシチェック
                if recent_communications:
                    avg_latency = sum(c.latency_p95 for c in recent_communications) / len(recent_communications)
                    if avg_latency > 1000:  # 1秒以上の平均レイテンシ
                        anomaly_score += 0.3

                # リソース使用率チェック
                if service.metrics.get('cpu_usage', 0) > 90:
                    anomaly_score += 0.2

                if anomaly_score > 0.6:  # 閾値
                    anomalies.append({
                        'service_name': service_name,
                        'anomaly_score': anomaly_score,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'issues': [
                            '高エラーレート' if anomaly_score > 0.5 else '',
                            '高レイテンシ' if avg_latency > 1000 else '',
                            '高CPU使用率' if service.metrics.get('cpu_usage', 0) > 90 else ''
                        ],
                        'recommendations': self._get_service_recommendations(service_name, anomaly_score)
                    })

        except Exception as e:
            logger.error(f"サービス異常検知エラー: {e}")

        return anomalies

    def _get_service_recommendations(self, service_name: str, anomaly_score: float) -> List[str]:
        """サービス推奨事項を取得"""
        recommendations = []

        if anomaly_score > 0.8:
            recommendations.extend([
                f'{service_name}の高負荷を調査してください',
                'スケーリング設定の見直しを検討してください',
                '依存関係の確認と最適化を推奨します'
            ])
        elif anomaly_score > 0.6:
            recommendations.extend([
                f'{service_name}のパフォーマンス監視を強化してください',
                'エラーログの詳細な確認を推奨します'
            ])

        return recommendations

    def generate_istio_config(self) -> Dict[str, Any]:
        """Istio設定を生成"""
        return {
            'apiVersion': 'install.istio.io/v1alpha1',
            'kind': 'IstioOperator',
            'metadata': {
                'name': 'control-plane'
            },
            'spec': {
                'meshConfig': {
                    'enablePrometheusMerge': True,
                    'defaultConfig': {
                        'tracing': {
                            'sampling': 100.0,
                            'zipkin': {
                                'address': self.jaeger_url
                            }
                        },
                        'proxyMetadata': {
                            'PILOT_TRACE_SAMPLING': '100.0'
                        }
                    }
                },
                'components': {
                    'pilot': {
                        'enabled': True,
                        'k8s': {
                            'resources': {
                                'requests': {
                                    'cpu': '100m',
                                    'memory': '100Mi'
                                }
                            }
                        }
                    },
                    'ingressGateways': [
                        {
                            'name': 'istio-ingressgateway',
                            'enabled': True
                        }
                    ]
                }
            }
        }

    def export_service_mesh_data(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """サービスメッシュデータをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = Path.cwd() / f"service_mesh_{timestamp}.{format_type}"

        try:
            data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_services': len(self.services),
                    'total_communications': len(self.communications)
                },
                'topology': self.get_service_mesh_topology(),
                'anomalies': self.detect_service_anomalies()
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"サービスメッシュデータをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"サービスメッシュデータエクスポートエラー: {e}")
            return None


# グローバルインスタンス
service_mesh_monitor = ServiceMeshMonitor()
