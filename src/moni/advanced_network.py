"""
高度なネットワーク監視機能 - Moni System Monitor

ネットワークトラフィックの詳細分析、パケット損失、遅延、帯域使用率などを監視します。
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
class NetworkInterfaceStats:
    """ネットワークインターフェース統計"""
    name: str
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    errin: int = 0
    errout: int = 0
    dropin: int = 0
    dropout: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def total_bytes(self) -> int:
        """総バイト数"""
        return self.bytes_sent + self.bytes_recv

    @property
    def total_packets(self) -> int:
        """総パケット数"""
        return self.packets_sent + self.packets_recv

    @property
    def error_rate(self) -> float:
        """エラーレート（%）"""
        total_packets = self.total_packets
        if total_packets == 0:
            return 0.0
        return ((self.errin + self.errout) / total_packets) * 100

    @property
    def drop_rate(self) -> float:
        """ドロップレート（%）"""
        total_packets = self.total_packets
        if total_packets == 0:
            return 0.0
        return ((self.dropin + self.dropout) / total_packets) * 100


@dataclass
class NetworkLatencyStats:
    """ネットワーク遅延統計"""
    target: str
    min_rtt: float = float('inf')
    max_rtt: float = 0.0
    avg_rtt: float = 0.0
    packet_loss: float = 0.0
    jitter: float = 0.0
    timestamp: float = field(default_factory=time.time)
    samples: List[float] = field(default_factory=list)

    def update(self, rtt: Optional[float], packet_loss: float = 0.0) -> None:
        """統計を更新"""
        if rtt is not None:
            self.samples.append(rtt)
            self.min_rtt = min(self.min_rtt, rtt)
            self.max_rtt = max(self.max_rtt, rtt)

            # 平均RTTの計算
            self.avg_rtt = sum(self.samples) / len(self.samples)

            # ジッターの計算（最近のサンプルを使用）
            if len(self.samples) >= 2:
                diffs = [abs(self.samples[i] - self.samples[i-1])
                        for i in range(1, len(self.samples))]
                self.jitter = sum(diffs) / len(diffs)

        self.packet_loss = packet_loss
        self.timestamp = time.time()

        # サンプル数を制限
        if len(self.samples) > 100:
            self.samples = self.samples[-100:]


@dataclass
class BandwidthUsage:
    """帯域使用率"""
    interface: str
    upload_bps: float = 0.0
    download_bps: float = 0.0
    total_bps: float = 0.0
    upload_mbps: float = 0.0
    download_mbps: float = 0.0
    total_mbps: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class NetworkConnectionDetails:
    """ネットワーク接続詳細"""
    local_ip: str
    local_port: int
    remote_ip: str
    remote_port: int
    protocol: str
    state: str
    pid: Optional[int] = None
    process_name: Optional[str] = None
    bytes_sent: int = 0
    bytes_recv: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AdvancedNetworkConfig:
    """高度なネットワーク監視設定"""
    enabled: bool = False
    latency_targets: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])  # pingターゲット
    ping_interval_seconds: int = 60
    bandwidth_calculation_window: int = 10  # 秒
    max_connection_history: int = 1000
    monitor_dns_queries: bool = False
    monitor_http_requests: bool = False
    enable_packet_analysis: bool = False
    geolocation_enabled: bool = False


class BandwidthMonitor:
    """帯域監視クラス"""

    def __init__(self, window_seconds: int = 10):
        self.window_seconds = window_seconds
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.last_stats: Dict[str, NetworkInterfaceStats] = {}
        self.lock = threading.Lock()

    def update_stats(self) -> Dict[str, BandwidthUsage]:
        """統計を更新し、帯域使用率を計算"""
        current_stats = self._get_current_stats()

        with self.lock:
            usages = {}

            for interface, stats in current_stats.items():
                # 前回の統計を取得
                prev_stats = self.last_stats.get(interface)
                if prev_stats:
                    # 時間差を計算
                    time_diff = stats.timestamp - prev_stats.timestamp
                    if time_diff > 0:
                        # 帯域計算
                        upload_bps = (stats.bytes_sent - prev_stats.bytes_sent) / time_diff
                        download_bps = (stats.bytes_recv - prev_stats.bytes_recv) / time_diff

                        usage = BandwidthUsage(
                            interface=interface,
                            upload_bps=upload_bps,
                            download_bps=download_bps,
                            total_bps=upload_bps + download_bps,
                            upload_mbps=upload_bps / (1024 * 1024),
                            download_mbps=download_bps / (1024 * 1024),
                            total_mbps=(upload_bps + download_bps) / (1024 * 1024)
                        )

                        usages[interface] = usage

                        # 履歴に追加
                        self.history[interface].append({
                            'timestamp': stats.timestamp,
                            'upload_bps': upload_bps,
                            'download_bps': download_bps
                        })

                # 現在の統計を保存
                self.last_stats[interface] = stats

            return usages

    def _get_current_stats(self) -> Dict[str, NetworkInterfaceStats]:
        """現在のネットワーク統計を取得"""
        stats = {}
        try:
            net_stats = psutil.net_io_counters(pernic=True)
            for interface, counters in net_stats.items():
                stats[interface] = NetworkInterfaceStats(
                    name=interface,
                    bytes_sent=counters.bytes_sent,
                    bytes_recv=counters.bytes_recv,
                    packets_sent=counters.packets_sent,
                    packets_recv=counters.packets_recv,
                    errin=counters.errin,
                    errout=counters.errout,
                    dropin=counters.dropin,
                    dropout=counters.dropout
                )
        except Exception as e:
            logger.error(f"ネットワーク統計取得エラー: {e}")

        return stats

    def get_average_bandwidth(self, interface: str, seconds: int = 60) -> Optional[BandwidthUsage]:
        """指定期間の平均帯域を取得"""
        with self.lock:
            history = self.history.get(interface, [])
            if not history:
                return None

            # 指定期間のデータをフィルタリング
            cutoff_time = time.time() - seconds
            recent_data = [entry for entry in history if entry['timestamp'] >= cutoff_time]

            if not recent_data:
                return None

            # 平均計算
            avg_upload = sum(entry['upload_bps'] for entry in recent_data) / len(recent_data)
            avg_download = sum(entry['download_bps'] for entry in recent_data) / len(recent_data)

            return BandwidthUsage(
                interface=interface,
                upload_bps=avg_upload,
                download_bps=avg_download,
                total_bps=avg_upload + avg_download,
                upload_mbps=avg_upload / (1024 * 1024),
                download_mbps=avg_download / (1024 * 1024),
                total_mbps=(avg_upload + avg_download) / (1024 * 1024)
            )


class LatencyMonitor:
    """遅延監視クラス"""

    def __init__(self, targets: List[str], interval_seconds: int = 60):
        self.targets = targets
        self.interval_seconds = interval_seconds
        self.stats: Dict[str, NetworkLatencyStats] = {}
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # 初期化
        for target in targets:
            self.stats[target] = NetworkLatencyStats(target=target)

    def start_monitoring(self) -> None:
        """監視を開始"""
        if self.running:
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

        logger.info("ネットワーク遅延監視を開始しました")

    def stop_monitoring(self) -> None:
        """監視を停止"""
        if not self.running:
            return

        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)

        logger.info("ネットワーク遅延監視を停止しました")

    def _monitoring_loop(self) -> None:
        """監視ループ"""
        while self.running:
            try:
                for target in self.targets:
                    self._ping_target(target)
            except Exception as e:
                logger.error(f"遅延監視ループエラー: {e}")

            time.sleep(self.interval_seconds)

    def _ping_target(self, target: str) -> None:
        """ターゲットにpingを実行"""
        try:
            # pingコマンド実行
            result = subprocess.run(
                ['ping', '-c', '4', '-W', '2', target],
                capture_output=True,
                text=True,
                timeout=10
            )

            # 結果のパース
            rtts = []
            packet_loss = 0.0

            for line in result.stdout.split('\n'):
                if 'time=' in line:
                    # RTT抽出
                    try:
                        time_part = line.split('time=')[1].split()[0]
                        if 'ms' in time_part:
                            rtt = float(time_part.rstrip('ms'))
                            rtts.append(rtt)
                    except (ValueError, IndexError):
                        pass
                elif 'packet loss' in line:
                    # パケット損失抽出
                    try:
                        loss_part = line.split('packet loss')[0].strip().split()[-1]
                        packet_loss = float(loss_part.rstrip('%'))
                    except (ValueError, IndexError):
                        pass

            # 統計更新
            with self.lock:
                if rtts:
                    avg_rtt = sum(rtts) / len(rtts)
                    self.stats[target].update(avg_rtt, packet_loss)
                else:
                    # ping失敗
                    self.stats[target].update(None, 100.0)

        except subprocess.TimeoutExpired:
            logger.debug(f"Ping timeout for {target}")
            with self.lock:
                self.stats[target].update(None, 100.0)
        except Exception as e:
            logger.error(f"Ping error for {target}: {e}")
            with self.lock:
                self.stats[target].update(None, 100.0)

    def get_latency_stats(self, target: Optional[str] = None) -> Union[Dict[str, NetworkLatencyStats], Optional[NetworkLatencyStats]]:
        """遅延統計を取得"""
        with self.lock:
            if target:
                return self.stats.get(target)
            else:
                return dict(self.stats)


class ConnectionMonitor:
    """接続監視クラス"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.connections: deque = deque(maxlen=max_history)
        self.lock = threading.Lock()

    def scan_connections(self) -> List[NetworkConnectionDetails]:
        """接続をスキャン"""
        connections = []

        try:
            # TCP接続
            tcp_conns = psutil.net_connections(kind='tcp')
            for conn in tcp_conns:
                details = self._parse_connection(conn, 'tcp')
                if details:
                    connections.append(details)

            # UDP接続（UDPはステートレスなので基本情報のみ）
            udp_conns = psutil.net_connections(kind='udp')
            for conn in udp_conns:
                details = self._parse_connection(conn, 'udp')
                if details:
                    connections.append(details)

        except Exception as e:
            logger.error(f"接続スキャンエラー: {e}")

        # 履歴に追加
        with self.lock:
            for conn in connections:
                self.connections.append(conn)

        return connections

    def _parse_connection(self, conn: psutil._common.sconn, protocol: str) -> Optional[NetworkConnectionDetails]:
        """接続をパース"""
        try:
            if not conn.laddr or not conn.raddr:
                return None

            local_ip, local_port = conn.laddr.ip, conn.laddr.port
            remote_ip, remote_port = conn.raddr.ip, conn.raddr.port

            # プロセス情報
            process_name = None
            if conn.pid:
                try:
                    process = psutil.Process(conn.pid)
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = f"pid_{conn.pid}"

            return NetworkConnectionDetails(
                local_ip=local_ip,
                local_port=local_port,
                remote_ip=remote_ip,
                remote_port=remote_port,
                protocol=protocol,
                state=conn.status,
                pid=conn.pid,
                process_name=process_name
            )

        except Exception as e:
            logger.debug(f"接続パースエラー: {e}")
            return None

    def get_recent_connections(self, limit: int = 100) -> List[NetworkConnectionDetails]:
        """最近の接続を取得"""
        with self.lock:
            return list(self.connections)[-limit:]

    def get_connections_by_process(self, pid: int) -> List[NetworkConnectionDetails]:
        """指定プロセスの接続を取得"""
        with self.lock:
            return [conn for conn in self.connections if conn.pid == pid]

    def get_connection_summary(self) -> Dict[str, Any]:
        """接続サマリーを取得"""
        with self.lock:
            if not self.connections:
                return {}

            # プロトコル別集計
            protocols = defaultdict(int)
            states = defaultdict(int)
            processes = defaultdict(int)

            for conn in self.connections:
                protocols[conn.protocol] += 1
                states[conn.state] += 1
                if conn.pid:
                    processes[conn.process_name or f"pid_{conn.pid}"] += 1

            return {
                "total_connections": len(self.connections),
                "protocols": dict(protocols),
                "states": dict(states),
                "processes": dict(sorted(processes.items(), key=lambda x: x[1], reverse=True)[:10]),
                "timestamp": time.time()
            }


class AdvancedNetworkMonitor:
    """高度なネットワーク監視マネージャー"""

    def __init__(self, config: AdvancedNetworkConfig):
        self.config = config
        self.bandwidth_monitor = BandwidthMonitor(config.bandwidth_calculation_window)
        self.latency_monitor = LatencyMonitor(config.latency_targets, config.ping_interval_seconds)
        self.connection_monitor = ConnectionMonitor(config.max_connection_history)
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self) -> None:
        """監視を開始"""
        if self.running:
            return

        self.running = True

        # 遅延監視を開始
        self.latency_monitor.start_monitoring()

        # 監視スレッドを開始
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()

        logger.info("高度なネットワーク監視を開始しました")

    def stop_monitoring(self) -> None:
        """監視を停止"""
        if not self.running:
            return

        self.running = False

        # 遅延監視を停止
        self.latency_monitor.stop_monitoring()

        # 監視スレッドを停止
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)

        logger.info("高度なネットワーク監視を停止しました")

    def _monitoring_loop(self) -> None:
        """監視ループ"""
        while self.running:
            try:
                # 帯域使用率を更新
                self.bandwidth_monitor.update_stats()

                # 接続をスキャン
                self.connection_monitor.scan_connections()

            except Exception as e:
                logger.error(f"ネットワーク監視ループエラー: {e}")

            time.sleep(5)  # 5秒間隔

    def get_network_stats(self) -> Dict[str, Any]:
        """ネットワーク統計を取得"""
        bandwidth_stats = self.bandwidth_monitor.update_stats()
        latency_stats = self.latency_monitor.get_latency_stats()
        connection_summary = self.connection_monitor.get_connection_summary()

        return {
            "bandwidth": {interface: {
                "upload_mbps": usage.upload_mbps,
                "download_mbps": usage.download_mbps,
                "total_mbps": usage.total_mbps
            } for interface, usage in bandwidth_stats.items()},
            "latency": {target: {
                "avg_rtt": stats.avg_rtt if stats.avg_rtt != float('inf') else None,
                "packet_loss": stats.packet_loss,
                "jitter": stats.jitter
            } for target, stats in latency_stats.items()},
            "connections": connection_summary,
            "timestamp": time.time()
        }

    def get_bandwidth_history(self, interface: str, seconds: int = 300) -> List[Dict[str, Any]]:
        """帯域履歴を取得"""
        history = []
        for entry in self.bandwidth_monitor.history.get(interface, []):
            if entry['timestamp'] >= time.time() - seconds:
                history.append(entry)
        return history

    def get_detailed_connection_info(self, pid: Optional[int] = None) -> List[NetworkConnectionDetails]:
        """詳細な接続情報を取得"""
        if pid is not None:
            return self.connection_monitor.get_connections_by_process(pid)
        else:
            return self.connection_monitor.get_recent_connections(200)


# グローバルマネージャーインスタンス
_network_monitor: Optional[AdvancedNetworkMonitor] = None


def init_advanced_network_monitor(config: AdvancedNetworkConfig) -> AdvancedNetworkMonitor:
    """高度なネットワーク監視マネージャーを初期化"""
    global _network_monitor

    if _network_monitor is None:
        _network_monitor = AdvancedNetworkMonitor(config)

    return _network_monitor


def get_advanced_network_monitor() -> Optional[AdvancedNetworkMonitor]:
    """高度なネットワーク監視マネージャーを取得"""
    return _network_monitor


def shutdown_advanced_network_monitor() -> None:
    """高度なネットワーク監視マネージャーをシャットダウン"""
    global _network_monitor

    if _network_monitor:
        _network_monitor.stop_monitoring()
        _network_monitor = None
