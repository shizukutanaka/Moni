"""
アプリケーション依存関係マップ - Moni System Monitor

プロセス間、サービス間、ネットワーク接続の依存関係を分析・視覚化し、
根本原因分析を支援する機能を提供します。
"""

from __future__ import annotations

import json
import logging
import psutil
import socket
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """依存関係ノード"""
    id: str
    name: str
    node_type: str  # "process", "service", "network", "database", "file"
    status: str = "unknown"  # "healthy", "warning", "critical", "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    connections: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class DependencyEdge:
    """依存関係エッジ"""
    source: str
    target: str
    edge_type: str  # "network", "file", "process", "service"
    protocol: Optional[str] = None
    port: Optional[int] = None
    direction: str = "bidirectional"  # "unidirectional", "bidirectional"
    strength: float = 1.0  # 接続強度（0.0-1.0）


@dataclass
class DependencySnapshot:
    """依存関係スナップショット"""
    timestamp: float
    nodes: Dict[str, DependencyNode]
    edges: List[DependencyEdge]
    alerts: List[Dict[str, Any]] = field(default_factory=list)


class ProcessDependencyMapper:
    """プロセス依存関係マッパー"""

    def __init__(self):
        self.process_cache: Dict[int, Dict[str, Any]] = {}
        self.connection_cache: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        self.scan_interval = 30  # 秒
        self.history_size = 100
        self.snapshots: deque[DependencySnapshot] = deque(maxlen=self.history_size)
        self._lock = threading.Lock()
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None

    def start_mapping(self) -> None:
        """依存関係マッピングを開始"""
        if self._running:
            return

        self._running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        logger.info("プロセス依存関係マッピングを開始しました")

    def stop_mapping(self) -> None:
        """依存関係マッピングを停止"""
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5)
        logger.info("プロセス依存関係マッピングを停止しました")

    def _scan_loop(self) -> None:
        """スキャンループ"""
        while self._running:
            try:
                snapshot = self._create_snapshot()
                if snapshot:
                    with self._lock:
                        self.snapshots.append(snapshot)

            except Exception as e:
                logger.error(f"依存関係スキャンエラー: {e}")

            time.sleep(self.scan_interval)

    def _create_snapshot(self) -> Optional[DependencySnapshot]:
        """スナップショットを作成"""
        try:
            nodes = {}
            edges = []

            # プロセス依存関係を分析
            process_nodes, process_edges = self._analyze_process_dependencies()
            nodes.update(process_nodes)
            edges.extend(process_edges)

            # ネットワーク依存関係を分析
            network_nodes, network_edges = self._analyze_network_dependencies()
            nodes.update(network_nodes)
            edges.extend(network_edges)

            # ファイル依存関係を分析
            file_nodes, file_edges = self._analyze_file_dependencies()
            nodes.update(file_nodes)
            edges.extend(file_edges)

            # アラートを生成
            alerts = self._generate_dependency_alerts(nodes, edges)

            return DependencySnapshot(
                timestamp=time.time(),
                nodes=nodes,
                edges=edges,
                alerts=alerts
            )

        except Exception as e:
            logger.error(f"スナップショット作成エラー: {e}")
            return None

    def _analyze_process_dependencies(self) -> Tuple[Dict[str, DependencyNode], List[DependencyEdge]]:
        """プロセス依存関係を分析"""
        nodes = {}
        edges = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'connections']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name'] or f"PID:{pid}"

                    # ノード作成
                    node_id = f"process_{pid}"
                    node = DependencyNode(
                        id=node_id,
                        name=name,
                        node_type="process",
                        status=self._get_process_status(proc.info['status']),
                        metadata={
                            'pid': pid,
                            'cmdline': proc.info.get('cmdline', []),
                            'cpu_percent': proc.cpu_percent(),
                            'memory_percent': proc.memory_percent(),
                        }
                    )
                    nodes[node_id] = node

                    # 接続を分析
                    connections = proc.info.get('connections', [])
                    for conn in connections:
                        if conn.status == psutil.CONN_ESTABLISHED:
                            remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "unknown"
                            edge = DependencyEdge(
                                source=node_id,
                                target=f"network_{remote_addr}",
                                edge_type="network",
                                protocol=self._get_protocol_name(conn.family, conn.type),
                                port=conn.raddr.port if conn.raddr else None,
                                direction="outgoing"
                            )
                            edges.append(edge)

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            logger.error(f"プロセス依存関係分析エラー: {e}")

        return nodes, edges

    def _analyze_network_dependencies(self) -> Tuple[Dict[str, DependencyNode], List[DependencyEdge]]:
        """ネットワーク依存関係を分析"""
        nodes = {}
        edges = []

        try:
            # ネットワーク接続を分析
            connections = psutil.net_connections()

            for conn in connections:
                if conn.status == psutil.CONN_LISTEN:
                    local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "unknown"

                    node_id = f"network_{local_addr}"
                    node = DependencyNode(
                        id=node_id,
                        name=f"Listening Port {conn.laddr.port}",
                        node_type="network",
                        metadata={
                            'local_address': local_addr,
                            'protocol': self._get_protocol_name(conn.family, conn.type),
                            'status': 'listening'
                        }
                    )
                    nodes[node_id] = node

        except Exception as e:
            logger.error(f"ネットワーク依存関係分析エラー: {e}")

        return nodes, edges

    def _analyze_file_dependencies(self) -> Tuple[Dict[str, DependencyNode], List[DependencyEdge]]:
        """ファイル依存関係を分析"""
        nodes = {}
        edges = []

        try:
            # 重要なシステムファイルを監視
            important_files = [
                "/etc/passwd", "/etc/shadow", "/etc/hosts",
                "/var/log/syslog", "/var/log/auth.log"
            ]

            for file_path in important_files:
                try:
                    path = Path(file_path)
                    if path.exists():
                        node_id = f"file_{file_path.replace('/', '_')}"
                        node = DependencyNode(
                            id=node_id,
                            name=f"File: {path.name}",
                            node_type="file",
                            metadata={
                                'path': str(path),
                                'size': path.stat().st_size,
                                'modified': path.stat().st_mtime
                            }
                        )
                        nodes[node_id] = node

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"ファイル依存関係分析エラー: {e}")

        return nodes, edges

    def _get_process_status(self, psutil_status: str) -> str:
        """プロセスステータスを変換"""
        status_map = {
            psutil.STATUS_RUNNING: "healthy",
            psutil.STATUS_SLEEPING: "healthy",
            psutil.STATUS_IDLE: "healthy",
            psutil.STATUS_STOPPED: "warning",
            psutil.STATUS_ZOMBIE: "critical",
            psutil.STATUS_DEAD: "critical"
        }
        return status_map.get(psutil_status, "unknown")

    def _get_protocol_name(self, family: int, type: int) -> str:
        """プロトコル名を取得"""
        if family == socket.AF_INET:
            if type == socket.SOCK_STREAM:
                return "TCP"
            elif type == socket.SOCK_DGRAM:
                return "UDP"
        elif family == socket.AF_INET6:
            if type == socket.SOCK_STREAM:
                return "TCP6"
            elif type == socket.SOCK_DGRAM:
                return "UDP6"

        return "UNKNOWN"

    def _generate_dependency_alerts(self, nodes: Dict[str, DependencyNode],
                                  edges: List[DependencyEdge]) -> List[Dict[str, Any]]:
        """依存関係アラートを生成"""
        alerts = []

        # 重要なプロセスが停止している場合
        for node_id, node in nodes.items():
            if node.node_type == "process" and node.status == "critical":
                alerts.append({
                    'type': 'critical_process',
                    'severity': 'critical',
                    'message': f"重要なプロセスが異常状態です: {node.name}",
                    'node_id': node_id,
                    'timestamp': time.time()
                })

        # 予期しないネットワーク接続
        suspicious_connections = [e for e in edges if e.edge_type == "network" and e.port and e.port < 1024]
        if suspicious_connections:
            alerts.append({
                'type': 'suspicious_network',
                'severity': 'warning',
                'message': f"疑わしいネットワーク接続が検出されました: {len(suspicious_connections)}件",
                'edges': [e.source for e in suspicious_connections],
                'timestamp': time.time()
            })

        return alerts

    def get_latest_snapshot(self) -> Optional[DependencySnapshot]:
        """最新のスナップショットを取得"""
        with self._lock:
            return self.snapshots[-1] if self.snapshots else None

    def get_snapshots(self, limit: int = 10) -> List[DependencySnapshot]:
        """スナップショット一覧を取得"""
        with self._lock:
            return list(self.snapshots)[-limit:]

    def export_dependency_map(self, format: str = "json") -> Union[Dict[str, Any], str]:
        """依存関係マップをエクスポート"""
        snapshot = self.get_latest_snapshot()
        if not snapshot:
            return {}

        if format == "json":
            return {
                'timestamp': snapshot.timestamp,
                'nodes': {node_id: {
                    'id': node.id,
                    'name': node.name,
                    'type': node.node_type,
                    'status': node.status,
                    'metadata': node.metadata,
                    'connections': list(node.connections)
                } for node_id, node in snapshot.nodes.items()},
                'edges': [{
                    'source': edge.source,
                    'target': edge.target,
                    'type': edge.edge_type,
                    'protocol': edge.protocol,
                    'port': edge.port,
                    'direction': edge.direction,
                    'strength': edge.strength
                } for edge in snapshot.edges],
                'alerts': snapshot.alerts
            }
        else:
            return json.dumps(snapshot, default=str, indent=2)


class RootCauseAnalyzer:
    """根本原因分析機能"""

    def __init__(self, dependency_mapper: ProcessDependencyMapper):
        self.dependency_mapper = dependency_mapper
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timeout = 300  # 5分

    def analyze_root_cause(self, problem_node: str, max_depth: int = 5) -> Dict[str, Any]:
        """根本原因を分析"""
        cache_key = f"{problem_node}_{max_depth}_{time.time() // self.cache_timeout}"

        if cache_key in self.analysis_cache:
            return self.analysis_cache[cache_key]

        snapshot = self.dependency_mapper.get_latest_snapshot()
        if not snapshot or problem_node not in snapshot.nodes:
            return {'error': 'スナップショットまたはノードが見つかりません'}

        # 影響を受けるノードを特定
        affected_nodes = self._find_affected_nodes(problem_node, snapshot, max_depth)

        # 根本原因候補を特定
        root_causes = self._identify_root_causes(problem_node, snapshot, affected_nodes)

        result = {
            'problem_node': problem_node,
            'affected_nodes': affected_nodes,
            'root_cause_candidates': root_causes,
            'analysis_timestamp': time.time(),
            'recommendations': self._generate_recommendations(root_causes)
        }

        self.analysis_cache[cache_key] = result
        return result

    def _find_affected_nodes(self, problem_node: str, snapshot: DependencySnapshot,
                           max_depth: int) -> List[Dict[str, Any]]:
        """影響を受けるノードを探索"""
        affected = []
        visited = set()
        queue = deque([(problem_node, 0)])

        while queue:
            current_node, depth = queue.popleft()
            if current_node in visited or depth > max_depth:
                continue

            visited.add(current_node)

            if current_node in snapshot.nodes:
                node = snapshot.nodes[current_node]
                affected.append({
                    'node_id': current_node,
                    'name': node.name,
                    'type': node.node_type,
                    'status': node.status,
                    'depth': depth
                })

                # 接続されたノードを追加
                for edge in snapshot.edges:
                    if edge.source == current_node:
                        queue.append((edge.target, depth + 1))
                    elif edge.target == current_node and edge.direction == "bidirectional":
                        queue.append((edge.source, depth + 1))

        return affected

    def _identify_root_causes(self, problem_node: str, snapshot: DependencySnapshot,
                            affected_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根本原因候補を特定"""
        root_causes = []

        # ステータスがcriticalのプロセスを優先
        for node_info in affected_nodes:
            node_id = node_info['node_id']
            if node_id in snapshot.nodes:
                node = snapshot.nodes[node_id]
                if node.status == "critical" and node.node_type == "process":
                    root_causes.append({
                        'node_id': node_id,
                        'name': node.name,
                        'type': 'critical_process',
                        'confidence': 0.9,
                        'reason': f"プロセスが異常状態です: {node.metadata.get('status', 'unknown')}"
                    })

        # ネットワーク接続の問題をチェック
        for edge in snapshot.edges:
            if edge.target == problem_node and edge.edge_type == "network":
                root_causes.append({
                    'node_id': edge.source,
                    'name': f"Network Connection {edge.port}",
                    'type': 'network_issue',
                    'confidence': 0.7,
                    'reason': f"ネットワーク接続に問題がある可能性があります: {edge.protocol}"
                })

        # 依存関係の深さを考慮してスコアリング
        root_causes.sort(key=lambda x: x['confidence'], reverse=True)

        return root_causes[:5]  # 上位5件を返す

    def _generate_recommendations(self, root_causes: List[Dict[str, Any]]) -> List[str]:
        """改善提案を生成"""
        recommendations = []

        for cause in root_causes:
            if cause['type'] == 'critical_process':
                recommendations.append(f"プロセス '{cause['name']}' を再起動してください")
            elif cause['type'] == 'network_issue':
                recommendations.append("ネットワーク接続を確認してください")
            else:
                recommendations.append(f"ノード '{cause['node_id']}' を調査してください")

        return list(set(recommendations))  # 重複を削除

    def get_analysis_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """分析履歴を取得"""
        return list(self.analysis_cache.values())[-limit:]


# グローバルインスタンス
dependency_mapper = ProcessDependencyMapper()
root_cause_analyzer = RootCauseAnalyzer(dependency_mapper)


def start_dependency_mapping() -> None:
    """依存関係マッピングを開始（便利関数）"""
    dependency_mapper.start_mapping()


def stop_dependency_mapping() -> None:
    """依存関係マッピングを停止（便利関数）"""
    dependency_mapper.stop_mapping()


def analyze_root_cause(problem_node: str, max_depth: int = 5) -> Dict[str, Any]:
    """根本原因を分析（便利関数）"""
    return root_cause_analyzer.analyze_root_cause(problem_node, max_depth)


def get_dependency_map() -> Union[Dict[str, Any], str]:
    """依存関係マップを取得（便利関数）"""
    return dependency_mapper.export_dependency_map("json")
