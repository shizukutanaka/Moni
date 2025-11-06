"""
Kubernetesネイティブ監視システム - Moni System Monitor

Prometheus統合によるKubernetes環境の包括的な監視を提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import time
import yaml
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class KubernetesResource:
    """Kubernetesリソース"""
    name: str
    namespace: str
    kind: str  # pod, deployment, service, etc.
    uid: str
    creation_timestamp: datetime
    status: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class PrometheusMetric:
    """Prometheusメトリクス"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str]
    help_text: Optional[str] = None


class KubernetesMonitor:
    """Kubernetesネイティブ監視システム"""

    def __init__(self, kubeconfig_path: Optional[str] = None):
        self.kubeconfig_path = kubeconfig_path or os.path.expanduser("~/.kube/config")
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')

        self.resources: Dict[str, KubernetesResource] = {}
        self.metrics_cache: Dict[str, List[PrometheusMetric]] = defaultdict(list)
        self.watchers: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

        # Kubernetesクライアントの初期化
        self._init_kubernetes_client()

        # Prometheusクライアントの初期化
        self._init_prometheus_client()

    def _init_kubernetes_client(self) -> None:
        """Kubernetesクライアントを初期化"""
        try:
            # 実際の実装ではkubernetesライブラリを使用
            # from kubernetes import client, config

            if os.path.exists(self.kubeconfig_path):
                logger.info(f"Kubernetes設定ファイルを読み込みました: {self.kubeconfig_path}")

                # 設定の読み込み（簡易版）
                with open(self.kubeconfig_path, 'r') as f:
                    kubeconfig = yaml.safe_load(f)

                logger.info("Kubernetesクライアントを初期化しました。")
            else:
                logger.warning(f"Kubernetes設定ファイルが見つかりません: {self.kubeconfig_path}")

        except Exception as e:
            logger.error(f"Kubernetesクライアント初期化エラー: {e}")

    def _init_prometheus_client(self) -> None:
        """Prometheusクライアントを初期化"""
        try:
            # 実際の実装ではprometheus-api-clientライブラリを使用
            # from prometheus_api_client import PrometheusConnect

            logger.info(f"Prometheusエンドポイントを設定しました: {self.prometheus_url}")

        except Exception as e:
            logger.error(f"Prometheusクライアント初期化エラー: {e}")

    def discover_resources(self) -> List[KubernetesResource]:
        """Kubernetesリソースを発見"""
        resources = []

        try:
            # kubectlコマンドでリソースを取得（実際の実装ではkubernetesライブラリを使用）
            cmd = ['kubectl', 'get', 'pods', '--all-namespaces', '-o', 'json']

            if os.path.exists(self.kubeconfig_path):
                cmd.extend(['--kubeconfig', self.kubeconfig_path])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)

                for item in data.get('items', []):
                    resource = KubernetesResource(
                        name=item['metadata']['name'],
                        namespace=item['metadata']['namespace'],
                        kind='pod',
                        uid=item['metadata']['uid'],
                        creation_timestamp=datetime.fromisoformat(item['metadata']['creationTimestamp'].replace('Z', '+00:00')),
                        status=item['status']['phase'],
                        labels=item['metadata'].get('labels', {}),
                        annotations=item['metadata'].get('annotations', {})
                    )
                    resources.append(resource)

                    with self._lock:
                        self.resources[resource.uid] = resource

            # 他のリソースタイプも同様に取得
            for resource_type in ['deployments', 'services', 'nodes']:
                cmd = ['kubectl', 'get', resource_type, '--all-namespaces', '-o', 'json']
                if os.path.exists(self.kubeconfig_path):
                    cmd.extend(['--kubeconfig', self.kubeconfig_path])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    data = json.loads(result.stdout)

                    for item in data.get('items', []):
                        resource = KubernetesResource(
                            name=item['metadata']['name'],
                            namespace=item['metadata']['namespace'],
                            kind=resource_type[:-1],  # 'deployments' -> 'deployment'
                            uid=item['metadata']['uid'],
                            creation_timestamp=datetime.fromisoformat(item['metadata']['creationTimestamp'].replace('Z', '+00:00')),
                            status=item.get('status', {}).get('conditions', [{'status': 'Unknown'}])[-1]['status'],
                            labels=item['metadata'].get('labels', {}),
                            annotations=item['metadata'].get('annotations', {})
                        )
                        resources.append(resource)

                        with self._lock:
                            self.resources[resource.uid] = resource

            logger.info(f"{len(resources)}個のKubernetesリソースを発見しました。")
            return resources

        except Exception as e:
            logger.error(f"Kubernetesリソース発見エラー: {e}")
            return []

    def collect_prometheus_metrics(self, resource_uid: str) -> List[PrometheusMetric]:
        """Prometheusメトリクスを収集"""
        metrics = []

        try:
            # リソースに関連するメトリクスをクエリ
            resource = self.resources.get(resource_uid)
            if not resource:
                return metrics

            # 一般的なKubernetesメトリクスをクエリ
            metric_queries = self._get_metric_queries_for_resource(resource)

            for query in metric_queries:
                # 実際の実装ではPrometheus APIを呼び出し
                # prom = PrometheusConnect(url=self.prometheus_url)
                # result = prom.custom_query(query)

                # モックメトリクス生成（実際の実装では上記を使用）
                mock_metric = PrometheusMetric(
                    name=query['name'],
                    value=query['mock_value'](),
                    timestamp=datetime.now(timezone.utc),
                    labels=query.get('labels', {}),
                    help_text=query.get('help')
                )
                metrics.append(mock_metric)

            with self._lock:
                self.metrics_cache[resource_uid] = metrics

            return metrics

        except Exception as e:
            logger.error(f"Prometheusメトリクス収集エラー: {e}")
            return []

    def _get_metric_queries_for_resource(self, resource: KubernetesResource) -> List[Dict[str, Any]]:
        """リソースのメトリクスクエリを取得"""
        queries = []

        if resource.kind == 'pod':
            queries = [
                {
                    'name': 'container_cpu_usage_seconds_total',
                    'query': f'container_cpu_usage_seconds_total{{pod="{resource.name}", namespace="{resource.namespace}"}}',
                    'mock_value': lambda: 0.5 + (time.time() % 10) / 20,  # 0.5-1.0の範囲
                    'help': 'Cumulative CPU usage in seconds'
                },
                {
                    'name': 'container_memory_usage_bytes',
                    'query': f'container_memory_usage_bytes{{pod="{resource.name}", namespace="{resource.namespace}"}}',
                    'mock_value': lambda: 100000000 + (time.time() % 100) * 1000000,  # 100MB-200MB
                    'help': 'Current memory usage in bytes'
                },
                {
                    'name': 'kube_pod_status_ready',
                    'query': f'kube_pod_status_ready{{pod="{resource.name}", namespace="{resource.namespace}"}}',
                    'mock_value': lambda: 1 if resource.status == 'Running' else 0,
                    'help': 'Pod readiness status'
                }
            ]
        elif resource.kind == 'deployment':
            queries = [
                {
                    'name': 'kube_deployment_status_replicas_available',
                    'query': f'kube_deployment_status_replicas_available{{deployment="{resource.name}", namespace="{resource.namespace}"}}',
                    'mock_value': lambda: 3,  # 仮定のレプリカ数
                    'help': 'Number of available replicas'
                },
                {
                    'name': 'kube_deployment_status_replicas_ready',
                    'query': f'kube_deployment_status_replicas_ready{{deployment="{resource.name}", namespace="{resource.namespace}"}}',
                    'mock_value': lambda: 3,
                    'help': 'Number of ready replicas'
                }
            ]

        return queries

    def watch_resources(self) -> None:
        """リソースの変更を監視"""
        def watch_loop():
            while True:
                try:
                    self.discover_resources()
                    time.sleep(30)  # 30秒ごとにポーリング
                except Exception as e:
                    logger.error(f"リソース監視エラー: {e}")
                    time.sleep(60)

        watch_thread = threading.Thread(target=watch_loop, daemon=True)
        watch_thread.start()
        self.watchers['resources'] = watch_thread

        logger.info("Kubernetesリソース監視を開始しました。")

    def get_cluster_health(self) -> Dict[str, Any]:
        """クラスターの健全性を取得"""
        try:
            # kubectl cluster-infoコマンドでクラスター情報を取得
            cmd = ['kubectl', 'cluster-info']
            if os.path.exists(self.kubeconfig_path):
                cmd.extend(['--kubeconfig', self.kubeconfig_path])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            cluster_info = {
                'cluster_accessible': result.returncode == 0,
                'master_url': None,
                'kubeconfig_valid': os.path.exists(self.kubeconfig_path),
                'namespaces_count': len(set(r.namespace for r in self.resources.values())),
                'total_resources': len(self.resources),
                'healthy_resources': len([r for r in self.resources.values() if r.status in ['Running', 'Active']])
            }

            if result.returncode == 0:
                # マスターURLを抽出（簡易版）
                for line in result.stderr.split('\n'):
                    if 'Kubernetes master' in line:
                        cluster_info['master_url'] = line.split()[-1]
                        break

            return cluster_info

        except Exception as e:
            logger.error(f"クラスター健全性チェックエラー: {e}")
            return {'error': str(e)}

    def generate_kubernetes_dashboard_data(self) -> Dict[str, Any]:
        """Kubernetesダッシュボードデータを生成"""
        with self._lock:
            return {
                'resources': [
                    {
                        'uid': r.uid,
                        'name': r.name,
                        'namespace': r.namespace,
                        'kind': r.kind,
                        'status': r.status,
                        'age': (datetime.now(timezone.utc) - r.creation_timestamp).total_seconds(),
                        'metrics': self.metrics_cache.get(r.uid, [])
                    }
                    for r in self.resources.values()
                ],
                'cluster_health': self.get_cluster_health(),
                'prometheus_connected': self._check_prometheus_connection(),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

    def _check_prometheus_connection(self) -> bool:
        """Prometheus接続をチェック"""
        try:
            # 実際の実装ではHTTPリクエストで接続確認
            # import requests
            # response = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': 'up'}, timeout=5)
            # return response.status_code == 200

            # モック実装
            return True

        except Exception:
            return False

    def export_prometheus_config(self, file_path: Optional[Path] = None) -> Optional[str]:
        """Prometheus設定をエクスポート"""
        if not file_path:
            file_path = Path.cwd() / "prometheus_kubernetes.yml"

        try:
            # Kubernetes用のPrometheus設定を生成
            config = {
                'global': {
                    'scrape_interval': '15s',
                    'evaluation_interval': '15s'
                },
                'rule_files': [],
                'scrape_configs': [
                    {
                        'job_name': 'kubernetes-pods',
                        'kubernetes_sd_configs': [
                            {
                                'role': 'pod'
                            }
                        ],
                        'relabel_configs': [
                            {
                                'source_labels': ['__meta_kubernetes_pod_annotation_prometheus_io_scrape'],
                                'action': 'keep',
                                'regex': 'true'
                            }
                        ]
                    },
                    {
                        'job_name': 'kubernetes-nodes',
                        'kubernetes_sd_configs': [
                            {
                                'role': 'node'
                            }
                        ]
                    }
                ]
            }

            with open(file_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

            logger.info(f"Prometheus設定をエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Prometheus設定エクスポートエラー: {e}")
            return None


# グローバルインスタンス
kubernetes_monitor = KubernetesMonitor()
