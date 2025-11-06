"""
ネットワーク依存関係マップ - Moni System Monitor

プロセス間のネットワーク接続と依存関係を分析・視覚化します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil

from .enhanced_security import AdvancedInputValidator, EnhancedValidationError

logger = logging.getLogger(__name__)


@dataclass
class NetworkConnection:
    """ネットワーク接続情報"""
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    pid: Optional[int] = None
    process_name: Optional[str] = None
    direction: str = "outbound"  # "inbound", "outbound", "listening"
    protocol: str = "tcp"  # "tcp", "udp"
    bytes_sent: int = 0
    bytes_recv: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProcessDependency:
    """プロセス依存関係"""
    source_pid: int
    source_name: str
    target_pid: Optional[int] = None
    target_name: Optional[str] = None
    target_address: Optional[str] = None
    target_port: Optional[int] = None
    connection_type: str = "network"  # "network", "ipc", "file"
    strength: float = 1.0  # 依存関係の強さ（0.0-1.0）
    last_seen: float = field(default_factory=time.time)


@dataclass
class DependencyMapConfig:
    """依存関係マップ設定"""
    enabled: bool = False
    scan_interval_seconds: int = 30
    max_connections_per_process: int = 100
    include_local_connections: bool = True
    include_listening_ports: bool = True
    track_process_lifecycle: bool = True
    export_graphviz: bool = False
    max_history_entries: int = 1000


class NetworkScanner:
    """ネットワーク接続スキャナー"""

    def __init__(self, config: DependencyMapConfig):
        self.config = config
        self.connections: Dict[Tuple[str, int, str, int], NetworkConnection] = {}
        self.process_cache: Dict[int, str] = {}
        self.lock = threading.Lock()

    def scan_connections(self) -> List[NetworkConnection]:
        """全ネットワーク接続をスキャン"""
        connections = []

        try:
            # TCP接続の取得
            tcp_connections = psutil.net_connections(kind='tcp')
            for conn in tcp_connections:
                connection = self._parse_connection(conn, "tcp")
                if connection:
                    connections.append(connection)

            # UDP接続の取得
            udp_connections = psutil.net_connections(kind='udp')
            for conn in udp_connections:
                connection = self._parse_connection(conn, "udp")
                if connection:
                    connections.append(connection)

        except Exception as e:
            logger.error(f"ネットワーク接続スキャンエラー: {e}")

        # プロセス名を解決
        self._resolve_process_names(connections)

        return connections

    def _parse_connection(self, conn: psutil._common.sconn, protocol: str) -> Optional[NetworkConnection]:
        """psutil接続オブジェクトをパース"""
        try:
            # ローカルアドレス
            local_addr = conn.laddr
            if not local_addr:
                return None

            local_address, local_port = local_addr.ip, local_addr.port

            # リモートアドレス
            remote_addr = conn.raddr
            if remote_addr:
                remote_address, remote_port = remote_addr.ip, remote_addr.port
            else:
                # LISTEN状態の場合
                if conn.status == psutil.CONN_LISTEN:
                    remote_address, remote_port = "*", local_port
                else:
                    return None

            # 方向の判定
            direction = self._determine_direction(local_address, remote_address, conn.status)

            # フィルタリング
            if not self._should_include_connection(local_address, remote_address, direction):
                return None

            return NetworkConnection(
                local_address=local_address,
                local_port=local_port,
                remote_address=remote_address,
                remote_port=remote_port,
                status=conn.status,
                pid=conn.pid,
                protocol=protocol,
                direction=direction
            )

        except Exception as e:
            logger.debug(f"接続パースエラー: {e}")
            return None

    def _determine_direction(self, local_addr: str, remote_addr: str, status: str) -> str:
        """接続の方向を判定"""
        if status == psutil.CONN_LISTEN:
            return "listening"
        elif remote_addr in ("127.0.0.1", "localhost", "::1") or local_addr in ("127.0.0.1", "localhost", "::1"):
            return "local"
        elif remote_addr == "*":
            return "listening"
        else:
            return "outbound"

    def _should_include_connection(self, local_addr: str, remote_addr: str, direction: str) -> bool:
        """接続を含めるべきか判定"""
        # ローカル接続のフィルタリング
        if not self.config.include_local_connections:
            if direction == "local" or local_addr.startswith("127.") or remote_addr.startswith("127."):
                return False

        # リスニングポートのフィルタリング
        if not self.config.include_listening_ports and direction == "listening":
            return False

        return True

    def _resolve_process_names(self, connections: List[NetworkConnection]) -> None:
        """プロセス名を解決"""
        for conn in connections:
            if conn.pid and conn.pid not in self.process_cache:
                try:
                    process = psutil.Process(conn.pid)
                    self.process_cache[conn.pid] = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    self.process_cache[conn.pid] = f"pid_{conn.pid}"
                except Exception as e:
                    logger.debug(f"プロセス名解決エラー (PID: {conn.pid}): {e}")
                    self.process_cache[conn.pid] = f"pid_{conn.pid}"

            if conn.pid:
                conn.process_name = self.process_cache.get(conn.pid)


class DependencyAnalyzer:
    """依存関係アナライザー"""

    def __init__(self, config: DependencyMapConfig):
        self.config = config
        self.dependencies: Dict[Tuple[int, str], List[ProcessDependency]] = defaultdict(list)
        self.process_history: Dict[int, Dict[str, Any]] = {}
        self.scanner = NetworkScanner(config)
        self.lock = threading.Lock()

    def analyze_dependencies(self) -> List[ProcessDependency]:
        """依存関係を分析"""
        connections = self.scanner.scan_connections()
        dependencies = []

        # プロセスごとの接続を集計
        process_connections: Dict[int, List[NetworkConnection]] = defaultdict(list)

        for conn in connections:
            if conn.pid:
                process_connections[conn.pid].append(conn)

        # 依存関係の抽出
        for pid, conns in process_connections.items():
            if len(conns) > self.config.max_connections_per_process:
                # 接続数が多すぎる場合は制限
                conns = conns[:self.config.max_connections_per_process]

            process_name = conns[0].process_name or f"pid_{pid}"

            for conn in conns:
                if conn.direction in ("outbound", "local"):
                    # 外部サービスへの依存関係
                    dep = ProcessDependency(
                        source_pid=pid,
                        source_name=process_name,
                        target_address=conn.remote_address,
                        target_port=conn.remote_port,
                        connection_type="network",
                        strength=min(1.0, len(conns) / 10.0),  # 接続数に基づく強さ
                        last_seen=time.time()
                    )
                    dependencies.append(dep)

                elif conn.direction == "listening":
                    # サービス提供
                    dep = ProcessDependency(
                        source_pid=pid,
                        source_name=process_name,
                        target_address=conn.local_address,
                        target_port=conn.local_port,
                        connection_type="service",
                        strength=0.8,  # サービスは強い依存関係
                        last_seen=time.time()
                    )
                    dependencies.append(dep)

        # プロセス履歴の更新
        if self.config.track_process_lifecycle:
            self._update_process_history(dependencies)

        return dependencies

    def _update_process_history(self, dependencies: List[ProcessDependency]) -> None:
        """プロセス履歴を更新"""
        current_time = time.time()

        # 既存プロセスを更新
        for dep in dependencies:
            if dep.source_pid not in self.process_history:
                self.process_history[dep.source_pid] = {
                    "name": dep.source_name,
                    "first_seen": current_time,
                    "last_seen": current_time,
                    "connection_count": 0
                }

            self.process_history[dep.source_pid]["last_seen"] = current_time
            self.process_history[dep.source_pid]["connection_count"] = len(dependencies)

        # 古いプロセスをクリーンアップ
        cutoff_time = current_time - (24 * 3600)  # 24時間以上
        to_remove = [
            pid for pid, info in self.process_history.items()
            if info["last_seen"] < cutoff_time
        ]

        for pid in to_remove:
            del self.process_history[pid]

    def get_dependency_graph(self) -> Dict[str, Any]:
        """依存関係グラフを取得"""
        dependencies = self.analyze_dependencies()

        # ノードの収集
        nodes = set()
        edges = []

        for dep in dependencies:
            nodes.add(f"process_{dep.source_pid}")

            if dep.target_address:
                target_node = f"service_{dep.target_address}:{dep.target_port}"
                nodes.add(target_node)

                edges.append({
                    "source": f"process_{dep.source_pid}",
                    "target": target_node,
                    "type": dep.connection_type,
                    "strength": dep.strength
                })

        return {
            "nodes": [{"id": node, "type": node.split("_")[0]} for node in nodes],
            "edges": edges,
            "timestamp": time.time(),
            "process_count": len([n for n in nodes if n.startswith("process_")]),
            "service_count": len([n for n in nodes if n.startswith("service_")])
        }

    def export_graphviz(self, filename: str) -> bool:
        """GraphViz形式でエクスポート"""
        try:
            graph = self.get_dependency_graph()

            with open(filename, 'w', encoding='utf-8') as f:
                f.write("digraph DependencyMap {\n")
                f.write("  rankdir=LR;\n")
                f.write("  node [shape=box];\n\n")

                # ノード定義
                for node in graph["nodes"]:
                    node_type = node["type"]
                    if node_type == "process":
                        f.write(f'  "{node["id"]}" [label="{node["id"]}", shape=ellipse];\n')
                    else:
                        f.write(f'  "{node["id"]}" [label="{node["id"]}", shape=box];\n')

                f.write("\n")

                # エッジ定義
                for edge in graph["edges"]:
                    style = "solid" if edge["type"] == "network" else "dashed"
                    f.write(f'  "{edge["source"]}" -> "{edge["target"]}" [style={style}];\n')

                f.write("}\n")

            logger.info(f"依存関係グラフを{filename}にエクスポートしました")
            return True

        except Exception as e:
            logger.error(f"GraphVizエクスポートエラー: {e}")
            return False


class DependencyMapManager:
    """依存関係マップマネージャー"""

    def __init__(self, config: DependencyMapConfig):
        self.config = config
        self.analyzer = DependencyAnalyzer(config)
        self.history: deque = deque(maxlen=config.max_history_entries)
        self.running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

    def start_monitoring(self) -> None:
        """監視を開始"""
        if self.running:
            return

        self.running = True
        self.scan_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.scan_thread.start()

        logger.info("依存関係マップ監視を開始しました")

    def stop_monitoring(self) -> None:
        """監視を停止"""
        if not self.running:
            return

        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)

        logger.info("依存関係マップ監視を停止しました")

    def _monitoring_loop(self) -> None:
        """監視ループ"""
        while self.running:
            try:
                # 依存関係分析
                graph = self.analyzer.get_dependency_graph()

                with self.lock:
                    self.history.append({
                        "timestamp": time.time(),
                        "graph": graph
                    })

                # GraphVizエクスポート
                if self.config.export_graphviz:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"dependency_map_{timestamp}.dot"
                    self.analyzer.export_graphviz(filename)

            except Exception as e:
                logger.error(f"依存関係分析エラー: {e}")

            # 次回のスキャンまで待機
            time.sleep(self.config.scan_interval_seconds)

    def get_current_graph(self) -> Dict[str, Any]:
        """現在の依存関係グラフを取得"""
        return self.analyzer.get_dependency_graph()

    def get_historical_graphs(self, hours: int = 1) -> List[Dict[str, Any]]:
        """過去の依存関係グラフを取得"""
        cutoff_time = time.time() - (hours * 3600)

        with self.lock:
            return [
                entry for entry in self.history
                if entry["timestamp"] >= cutoff_time
            ]

    def get_process_details(self, pid: int) -> Optional[Dict[str, Any]]:
        """指定されたプロセスの詳細を取得"""
        return self.analyzer.process_history.get(pid)

    def get_top_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """接続数が多い上位プロセスを取得"""
        processes = []

        for pid, info in self.analyzer.process_history.items():
            processes.append({
                "pid": pid,
                "name": info["name"],
                "connection_count": info["connection_count"],
                "last_seen": info["last_seen"]
            })

        # 接続数でソート
        processes.sort(key=lambda x: x["connection_count"], reverse=True)
        return processes[:limit]

    def get_network_summary(self) -> Dict[str, Any]:
        """ネットワーク接続のサマリーを取得"""
        graph = self.get_current_graph()

        # 接続タイプの集計
        connection_types = defaultdict(int)
        for edge in graph["edges"]:
            connection_types[edge["type"]] += 1

        return {
            "total_processes": graph["process_count"],
            "total_services": graph["service_count"],
            "total_connections": len(graph["edges"]),
            "connection_types": dict(connection_types),
            "timestamp": time.time()
        }


# グローバルマネージャーインスタンス
_dependency_manager: Optional[DependencyMapManager] = None


def init_dependency_manager(config: DependencyMapConfig) -> DependencyMapManager:
    """依存関係マップマネージャーを初期化"""
    global _dependency_manager

    if _dependency_manager is None:
        _dependency_manager = DependencyMapManager(config)

    return _dependency_manager


def get_dependency_manager() -> Optional[DependencyMapManager]:
    """依存関係マップマネージャーを取得"""
    return _dependency_manager


def shutdown_dependency_manager() -> None:
    """依存関係マップマネージャーをシャットダウン"""
    global _dependency_manager

    if _dependency_manager:
        _dependency_manager.stop_monitoring()
        _dependency_manager = None
