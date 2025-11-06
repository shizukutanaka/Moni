"""
エッジコンピューティング統合システム - Moni System Monitor

IoTデバイスとエッジコンピューティング環境での分散監視を提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class EdgeNode:
    """エッジノード"""
    node_id: str
    name: str
    location: str
    node_type: str  # edge_gateway, iot_device, fog_node, etc.
    ip_address: str
    capabilities: List[str]
    resources: Dict[str, Any]
    status: str
    last_seen: datetime
    connected_devices: List[str] = field(default_factory=list)


@dataclass
class IoTDevice:
    """IoTデバイス"""
    device_id: str
    name: str
    device_type: str
    edge_node_id: str
    sensors: List[str]
    capabilities: Dict[str, Any]
    location: str
    battery_level: Optional[float]
    signal_strength: Optional[float]
    status: str
    last_data_timestamp: datetime


@dataclass
class EdgeDataPacket:
    """エッジデータパケット"""
    packet_id: str
    source_node: str
    data_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    quality_score: float
    compressed: bool
    encryption_level: str


class EdgeComputingIntegrator:
    """エッジコンピューティング統合システム"""

    def __init__(self, edge_config_dir: Optional[Union[str, Path]] = None):
        self.edge_config_dir = Path(edge_config_dir) if edge_config_dir else Path(__file__).parent / "edge_config"
        self.edge_config_dir.mkdir(exist_ok=True)

        self.edge_nodes: Dict[str, EdgeNode] = {}
        self.iot_devices: Dict[str, IoTDevice] = {}
        self.data_buffer: deque = deque(maxlen=100000)
        self.edge_analytics: Dict[str, Any] = {}

        # エッジネットワーク設定
        self.network_config = {
            'mesh_network_enabled': True,
            'data_compression_enabled': True,
            'local_analytics_enabled': True,
            'cloud_sync_interval': 300,  # 5分ごと
            'max_local_storage_gb': 10
        }

        # エッジノードの検出と登録
        self._discover_edge_nodes()

        # データ収集の開始
        self._start_edge_monitoring()

        self._lock = threading.Lock()

    def _discover_edge_nodes(self) -> None:
        """エッジノードを発見"""
        try:
            # ネットワークスキャンでエッジノードを検出
            # 実際の実装では、適切なサービスディスカバリプロトコルを使用

            # 現在のホストをエッジゲートウェイとして登録
            local_node = EdgeNode(
                node_id=f"EDGE_{uuid.uuid4().hex[:8]}",
                name=f"EdgeGateway-{socket.gethostname()}",
                location="local",
                node_type="edge_gateway",
                ip_address=socket.gethostbyname(socket.gethostname()),
                capabilities=['monitoring', 'analytics', 'compression', 'encryption'],
                resources=self._get_node_resources(),
                status='active',
                last_seen=datetime.now(timezone.utc)
            )

            with self._lock:
                self.edge_nodes[local_node.node_id] = local_node

            logger.info(f"エッジノードを登録しました: {local_node.name}")

        except Exception as e:
            logger.error(f"エッジノード発見エラー: {e}")

    def _get_node_resources(self) -> Dict[str, Any]:
        """ノードリソースを取得"""
        try:
            import psutil

            return {
                'cpu_cores': psutil.cpu_count(),
                'memory_gb': round(psutil.virtual_memory().total / 1024 / 1024 / 1024, 2),
                'disk_gb': round(psutil.disk_usage('/').total / 1024 / 1024 / 1024, 2),
                'network_interfaces': len(psutil.net_if_addrs()),
                'uptime_seconds': time.time() - psutil.boot_time()
            }

        except Exception:
            return {
                'cpu_cores': 1,
                'memory_gb': 1.0,
                'disk_gb': 10.0,
                'network_interfaces': 1,
                'uptime_seconds': 0
            }

    def _start_edge_monitoring(self) -> None:
        """エッジ監視を開始"""
        def monitoring_loop():
            while True:
                try:
                    self._collect_edge_data()
                    self._process_edge_analytics()
                    self._sync_with_cloud()
                    time.sleep(60)  # 1分ごとに実行
                except Exception as e:
                    logger.error(f"エッジ監視エラー: {e}")
                    time.sleep(300)  # エラー時は5分待機

        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        logger.info("エッジコンピューティング監視を開始しました。")

    def _collect_edge_data(self) -> None:
        """エッジデータを収集"""
        try:
            # エッジノードからデータを収集
            for node in self.edge_nodes.values():
                if node.status == 'active':
                    # ノードのローカルデータを収集
                    node_data = self._collect_node_data(node)

                    if node_data:
                        packet = EdgeDataPacket(
                            packet_id=f"EDP_{int(time.time() * 1000000)}",
                            source_node=node.node_id,
                            data_type='node_metrics',
                            payload=node_data,
                            timestamp=datetime.now(timezone.utc),
                            quality_score=self._calculate_data_quality(node_data),
                            compressed=self.network_config['data_compression_enabled'],
                            encryption_level='aes256'
                        )

                        with self._lock:
                            self.data_buffer.append(packet)

        except Exception as e:
            logger.error(f"エッジデータ収集エラー: {e}")

    def _collect_node_data(self, node: EdgeNode) -> Dict[str, Any]:
        """ノードデータを収集"""
        try:
            data = {
                'node_id': node.node_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'resources': self._get_node_resources(),
                'connected_devices': len(node.connected_devices),
                'data_processing_rate': 100 + (time.time() % 50),  # モックデータ
                'network_latency_ms': 10 + (time.time() % 20),
                'error_rate': (time.time() % 100) * 0.001  # 0-0.1%
            }

            # 接続されているIoTデバイスからのデータも収集
            for device_id in node.connected_devices:
                if device_id in self.iot_devices:
                    device = self.iot_devices[device_id]
                    device_data = self._collect_device_data(device)
                    data[f'device_{device_id}'] = device_data

            return data

        except Exception as e:
            logger.error(f"ノードデータ収集エラー ({node.node_id}): {e}")
            return {}

    def _collect_device_data(self, device: IoTDevice) -> Dict[str, Any]:
        """デバイスデータを収集"""
        try:
            # 実際の実装では、デバイスからセンサーデータを取得
            device_data = {
                'device_id': device.device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sensors': {}
            }

            for sensor in device.sensors:
                # モックセンサーデータ生成
                sensor_value = self._generate_sensor_data(sensor, device.device_type)
                device_data['sensors'][sensor] = {
                    'value': sensor_value,
                    'unit': self._get_sensor_unit(sensor),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

            device.last_data_timestamp = datetime.now(timezone.utc)

            return device_data

        except Exception as e:
            logger.error(f"デバイスデータ収集エラー ({device.device_id}): {e}")
            return {}

    def _generate_sensor_data(self, sensor_type: str, device_type: str) -> float:
        """センサーデータを生成（モック）"""
        base_values = {
            'temperature': 25.0,
            'humidity': 60.0,
            'pressure': 1013.0,
            'vibration': 0.1,
            'current': 5.0,
            'voltage': 220.0,
            'motion': 0,
            'proximity': 100.0
        }

        base_value = base_values.get(sensor_type, 50.0)

        # デバイス種別による調整
        if device_type == 'sensor_node':
            variation = (time.time() % 10) / 50  # 小さな変動
        else:
            variation = (time.time() % 20) / 20  # 大きな変動

        return base_value + variation

    def _get_sensor_unit(self, sensor_type: str) -> str:
        """センサーの単位を取得"""
        units = {
            'temperature': '°C',
            'humidity': '%',
            'pressure': 'hPa',
            'vibration': 'mm/s',
            'current': 'A',
            'voltage': 'V',
            'motion': 'boolean',
            'proximity': 'cm'
        }

        return units.get(sensor_type, 'unit')

    def _calculate_data_quality(self, data: Dict[str, Any]) -> float:
        """データ品質を計算"""
        try:
            quality_factors = []

            # データ完全性チェック
            if data:
                quality_factors.append(1.0)
            else:
                quality_factors.append(0.0)

            # タイムスタンプの新しさをチェック
            if 'timestamp' in data:
                timestamp_str = data['timestamp']
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()

                    if age_seconds < 60:  # 1分以内
                        quality_factors.append(1.0)
                    elif age_seconds < 300:  # 5分以内
                        quality_factors.append(0.8)
                    else:
                        quality_factors.append(0.5)
                except:
                    quality_factors.append(0.5)

            # データの構造的品質チェック
            required_fields = ['node_id', 'resources']
            completeness = sum(1 for field in required_fields if field in data) / len(required_fields)
            quality_factors.append(completeness)

            return sum(quality_factors) / len(quality_factors)

        except Exception:
            return 0.5

    def _process_edge_analytics(self) -> None:
        """エッジ分析を処理"""
        try:
            if not self.data_buffer:
                return

            # 直近のデータを取得
            recent_packets = list(self.data_buffer)[-100:]

            # ローカル分析を実行
            analytics = {
                'data_points_analyzed': len(recent_packets),
                'average_quality_score': sum(p.quality_score for p in recent_packets) / len(recent_packets),
                'edge_processing_rate': len(recent_packets) / 60,  # データポイント/分
                'compression_ratio': 0.7 if self.network_config['data_compression_enabled'] else 1.0,
                'local_insights': self._generate_local_insights(recent_packets)
            }

            with self._lock:
                self.edge_analytics = analytics

        except Exception as e:
            logger.error(f"エッジ分析処理エラー: {e}")

    def _generate_local_insights(self, packets: List[EdgeDataPacket]) -> Dict[str, Any]:
        """ローカル洞察を生成"""
        try:
            insights = {
                'performance_trends': {},
                'anomaly_indicators': [],
                'resource_optimization': {},
                'predictive_alerts': []
            }

            # パフォーマンストレンド分析
            for packet in packets[-20:]:  # 直近20パケット
                if packet.data_type == 'node_metrics':
                    node_id = packet.payload.get('node_id')
                    if node_id:
                        cpu_usage = packet.payload.get('resources', {}).get('cpu_percent', 0)
                        memory_usage = packet.payload.get('resources', {}).get('memory_percent', 0)

                        if node_id not in insights['performance_trends']:
                            insights['performance_trends'][node_id] = {'cpu': [], 'memory': []}

                        insights['performance_trends'][node_id]['cpu'].append(cpu_usage)
                        insights['performance_trends'][node_id]['memory'].append(memory_usage)

            # 異常インジケーターの検出
            for node_id, trends in insights['performance_trends'].items():
                if len(trends['cpu']) > 5:
                    avg_cpu = sum(trends['cpu']) / len(trends['cpu'])
                    if avg_cpu > 80:
                        insights['anomaly_indicators'].append({
                            'node_id': node_id,
                            'type': 'high_cpu_usage',
                            'severity': 'warning',
                            'value': avg_cpu
                        })

            return insights

        except Exception as e:
            logger.error(f"ローカル洞察生成エラー: {e}")
            return {}

    def _sync_with_cloud(self) -> None:
        """クラウドと同期"""
        try:
            if len(self.data_buffer) > 50:  # バッファが50を超えたら同期
                # データの圧縮と暗号化
                sync_data = {
                    'edge_node_id': list(self.edge_nodes.keys())[0] if self.edge_nodes else 'unknown',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'data_packets': [self._serialize_packet(p) for p in list(self.data_buffer)[-50:]]
                }

                # クラウド同期の実行（実際の実装では適切なAPIを呼び出し）
                logger.info(f"クラウド同期を実行: {len(sync_data['data_packets'])}パケット")

                # 同期後バッファをクリア
                with self._lock:
                    # 同期済みデータを削除（直近100個を保持）
                    while len(self.data_buffer) > 100:
                        self.data_buffer.popleft()

        except Exception as e:
            logger.error(f"クラウド同期エラー: {e}")

    def _serialize_packet(self, packet: EdgeDataPacket) -> Dict[str, Any]:
        """データパケットをシリアライズ"""
        return {
            'packet_id': packet.packet_id,
            'source_node': packet.source_node,
            'data_type': packet.data_type,
            'payload': packet.payload,
            'timestamp': packet.timestamp.isoformat(),
            'quality_score': packet.quality_score,
            'compressed': packet.compressed,
            'encryption_level': packet.encryption_level
        }

    def register_iot_device(self, device_info: Dict[str, Any]) -> str:
        """IoTデバイスを登録"""
        try:
            device_id = f"IOT_{uuid.uuid4().hex[:8]}"

            device = IoTDevice(
                device_id=device_id,
                name=device_info.get('name', f'Device-{device_id}'),
                device_type=device_info.get('device_type', 'generic_sensor'),
                edge_node_id=device_info.get('edge_node_id', list(self.edge_nodes.keys())[0] if self.edge_nodes else ''),
                sensors=device_info.get('sensors', ['temperature']),
                capabilities=device_info.get('capabilities', {}),
                location=device_info.get('location', 'unknown'),
                battery_level=device_info.get('battery_level'),
                signal_strength=device_info.get('signal_strength'),
                status='active',
                last_data_timestamp=datetime.now(timezone.utc)
            )

            with self._lock:
                self.iot_devices[device_id] = device

                # エッジノードにデバイスを関連付け
                if device.edge_node_id in self.edge_nodes:
                    if device_id not in self.edge_nodes[device.edge_node_id].connected_devices:
                        self.edge_nodes[device.edge_node_id].connected_devices.append(device_id)

            logger.info(f"IoTデバイスを登録しました: {device.name}")
            return device_id

        except Exception as e:
            logger.error(f"IoTデバイス登録エラー: {e}")
            return ''

    def get_edge_dashboard(self) -> Dict[str, Any]:
        """エッジダッシュボードを取得"""
        with self._lock:
            return {
                'edge_nodes': [
                    {
                        'node_id': n.node_id,
                        'name': n.name,
                        'type': n.node_type,
                        'status': n.status,
                        'location': n.location,
                        'resources': n.resources,
                        'connected_devices': len(n.connected_devices),
                        'last_seen': n.last_seen.isoformat()
                    }
                    for n in self.edge_nodes.values()
                ],
                'iot_devices': [
                    {
                        'device_id': d.device_id,
                        'name': d.name,
                        'type': d.device_type,
                        'edge_node_id': d.edge_node_id,
                        'status': d.status,
                        'battery_level': d.battery_level,
                        'signal_strength': d.signal_strength,
                        'last_data': d.last_data_timestamp.isoformat(),
                        'sensors': d.sensors
                    }
                    for d in self.iot_devices.values()
                ],
                'data_buffer_size': len(self.data_buffer),
                'edge_analytics': self.edge_analytics,
                'network_status': self._get_network_status()
            }

    def _get_network_status(self) -> Dict[str, Any]:
        """ネットワークステータスを取得"""
        try:
            # ネットワーク接続テスト
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                internet_connected = True
            except:
                internet_connected = False

            return {
                'internet_connected': internet_connected,
                'mesh_network_enabled': self.network_config['mesh_network_enabled'],
                'data_compression': self.network_config['data_compression_enabled'],
                'local_storage_used_gb': len(self.data_buffer) * 0.001,  # 簡易計算
                'cloud_sync_status': 'active' if internet_connected else 'offline'
            }

        except Exception:
            return {'error': 'ネットワークステータス取得エラー'}

    def optimize_edge_resources(self) -> Dict[str, Any]:
        """エッジリソースを最適化"""
        try:
            optimizations = {
                'resource_allocations': {},
                'data_compression_recommendations': [],
                'bandwidth_optimization': {},
                'storage_optimization': {}
            }

            # 各エッジノードのリソース最適化を分析
            for node in self.edge_nodes.values():
                if node.status == 'active':
                    # リソース使用率の分析
                    resources = node.resources
                    cpu_usage = resources.get('cpu_percent', 0)
                    memory_usage = resources.get('memory_percent', 0)

                    # 最適化提案の生成
                    if cpu_usage > 80:
                        optimizations['resource_allocations'][node.node_id] = {
                            'action': 'scale_up',
                            'resource': 'cpu',
                            'recommendation': 'CPUリソースの増強を検討してください'
                        }

                    if memory_usage > 85:
                        optimizations['resource_allocations'][node.node_id] = {
                            'action': 'scale_up',
                            'resource': 'memory',
                            'recommendation': 'メモリリソースの増強を検討してください'
                        }

            # データ圧縮の推奨
            if len(self.data_buffer) > 50000:
                optimizations['data_compression_recommendations'].append(
                    'データ圧縮を有効化または強化してください'
                )

            return optimizations

        except Exception as e:
            logger.error(f"エッジリソース最適化エラー: {e}")
            return {}

    def export_edge_configuration(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """エッジ設定をエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.edge_config_dir / f"edge_config_{timestamp}.{format_type}"

        try:
            config = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_edge_nodes': len(self.edge_nodes),
                    'total_iot_devices': len(self.iot_devices)
                },
                'network_config': self.network_config,
                'edge_nodes': [
                    {
                        'node_id': n.node_id,
                        'name': n.name,
                        'type': n.node_type,
                        'capabilities': n.capabilities,
                        'resources': n.resources
                    }
                    for n in self.edge_nodes.values()
                ],
                'iot_devices': [
                    {
                        'device_id': d.device_id,
                        'name': d.name,
                        'type': d.device_type,
                        'sensors': d.sensors,
                        'capabilities': d.capabilities
                    }
                    for d in self.iot_devices.values()
                ]
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, default=str)

            logger.info(f"エッジ設定をエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"エッジ設定エクスポートエラー: {e}")
            return None


# グローバルインスタンス
edge_computing_integrator = EdgeComputingIntegrator()
