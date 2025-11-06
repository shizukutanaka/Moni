"""
時系列データベース統合モジュール - Moni System Monitor

Prometheus/InfluxDBとの統合により、時系列データの保存と分析を可能にします。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

try:
    import influxdb_client
    from influxdb_client.client.write_api import SYNCHRONOUS
    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False

try:
    import prometheus_client
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from .enhanced_security import AdvancedInputValidator, EnhancedValidationError

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesConfig:
    """時系列データベース設定"""
    enabled: bool = False
    provider: str = "prometheus"  # "prometheus" or "influxdb"
    url: str = ""
    token: str = ""
    org: str = ""
    bucket: str = "moni_metrics"
    database: str = "moni"
    username: str = ""
    password: str = ""
    batch_size: int = 100
    flush_interval_seconds: int = 30
    retention_days: int = 30
    labels: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """設定の検証"""
        validator = AdvancedInputValidator()

        if self.enabled:
            if not self.url:
                raise ValueError("時系列データベースURLが必要です")

            try:
                validator.validate_url(self.url)
            except EnhancedValidationError as e:
                raise ValueError(f"無効なURL: {e}")

            if self.provider == "influxdb":
                if not self.token and not (self.username and self.password):
                    raise ValueError("InfluxDBにはトークンまたはユーザー名/パスワードが必要です")
                if not self.org:
                    raise ValueError("InfluxDBには組織名が必要です")
                if not self.bucket:
                    raise ValueError("InfluxDBにはバケット名が必要です")
            elif self.provider == "prometheus":
                # Prometheusの場合、URLのみ必要
                pass
            else:
                raise ValueError(f"未対応のプロバイダー: {self.provider}")


@dataclass
class TimeSeriesPoint:
    """時系列データポイント"""
    measurement: str
    timestamp: float
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, Union[int, float, str]] = field(default_factory=dict)


class TimeSeriesBackend(ABC):
    """時系列データベースバックエンドの抽象基底クラス"""

    @abstractmethod
    def connect(self) -> bool:
        """データベース接続を確立"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """データベース接続を切断"""
        pass

    @abstractmethod
    def write_points(self, points: List[TimeSeriesPoint]) -> bool:
        """データポイントを書き込み"""
        pass

    @abstractmethod
    def query(self, query: str, start_time: Optional[datetime] = None,
              end_time: Optional[datetime] = None) -> List[TimeSeriesPoint]:
        """データをクエリ"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """ヘルスチェック"""
        pass


class PrometheusBackend(TimeSeriesBackend):
    """Prometheusバックエンド"""

    def __init__(self, config: TimeSeriesConfig):
        self.config = config
        self.registry = None
        self.metrics = {}

    def connect(self) -> bool:
        if not HAS_PROMETHEUS:
            logger.error("prometheus_clientがインストールされていません")
            return False

        try:
            from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram

            self.registry = CollectorRegistry()

            # 基本メトリクスを作成
            self.metrics = {
                'cpu_usage': Gauge('moni_cpu_usage_percent', 'CPU使用率', registry=self.registry),
                'memory_usage': Gauge('moni_memory_usage_percent', 'メモリ使用率', registry=self.registry),
                'gpu_usage': Gauge('moni_gpu_usage_percent', 'GPU使用率', registry=self.registry),
                'disk_io': Counter('moni_disk_io_bytes', 'ディスクI/Oバイト数', registry=self.registry),
                'network_io': Counter('moni_network_io_bytes', 'ネットワークI/Oバイト数', registry=self.registry),
            }

            logger.info("Prometheusバックエンドに接続しました")
            return True

        except Exception as e:
            logger.error(f"Prometheus接続エラー: {e}")
            return False

    def disconnect(self) -> None:
        """Prometheusは常時接続不要"""
        pass

    def write_points(self, points: List[TimeSeriesPoint]) -> bool:
        if not self.registry:
            return False

        try:
            for point in points:
                if point.measurement in self.metrics:
                    metric = self.metrics[point.measurement]
                    if hasattr(metric, 'set'):
                        metric.set(point.value)
                    elif hasattr(metric, 'inc'):
                        metric.inc(point.value)

            return True

        except Exception as e:
            logger.error(f"Prometheus書き込みエラー: {e}")
            return False

    def query(self, query: str, start_time: Optional[datetime] = None,
              end_time: Optional[datetime] = None) -> List[TimeSeriesPoint]:
        # PrometheusはクエリAPIをサポートしないため、空のリストを返す
        logger.warning("Prometheusバックエンドはクエリをサポートしません")
        return []

    def health_check(self) -> bool:
        return self.registry is not None


class InfluxDBBackend(TimeSeriesBackend):
    """InfluxDBバックエンド"""

    def __init__(self, config: TimeSeriesConfig):
        self.config = config
        self.client = None
        self.write_api = None
        self.query_api = None

    def connect(self) -> bool:
        if not HAS_INFLUXDB:
            logger.error("influxdb_clientがインストールされていません")
            return False

        try:
            from influxdb_client import InfluxDBClient

            # 認証設定
            if self.config.token:
                self.client = InfluxDBClient(
                    url=self.config.url,
                    token=self.config.token,
                    org=self.config.org
                )
            else:
                self.client = InfluxDBClient(
                    url=self.config.url,
                    username=self.config.username,
                    password=self.config.password,
                    org=self.config.org
                )

            # APIクライアント作成
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()

            # ヘルスチェック
            health = self.client.health()
            if health.status != "pass":
                logger.error(f"InfluxDBヘルスチェック失敗: {health}")
                return False

            logger.info(f"InfluxDBバックエンドに接続しました: {self.config.url}")
            return True

        except Exception as e:
            logger.error(f"InfluxDB接続エラー: {e}")
            return False

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.error(f"InfluxDB切断エラー: {e}")
            finally:
                self.client = None
                self.write_api = None
                self.query_api = None

    def write_points(self, points: List[TimeSeriesPoint]) -> bool:
        if not self.write_api or not self.client:
            return False

        try:
            from influxdb_client import Point

            influx_points = []
            for point in points:
                p = Point(point.measurement)

                # タグ設定
                for tag_key, tag_value in point.tags.items():
                    p.tag(tag_key, tag_value)

                # フィールド設定
                if point.fields:
                    for field_key, field_value in point.fields.items():
                        p.field(field_key, field_value)
                else:
                    p.field("value", point.value)

                # タイムスタンプ設定
                p.time(int(point.timestamp * 1e9), write_precision='ns')

                influx_points.append(p)

            # 書き込み
            self.write_api.write(bucket=self.config.bucket, record=influx_points)

            logger.debug(f"{len(points)}個のデータポイントをInfluxDBに書き込みました")
            return True

        except Exception as e:
            logger.error(f"InfluxDB書き込みエラー: {e}")
            return False

    def query(self, query: str, start_time: Optional[datetime] = None,
              end_time: Optional[datetime] = None) -> List[TimeSeriesPoint]:
        if not self.query_api:
            return []

        try:
            # Fluxクエリ構築
            flux_query = f'''
            from(bucket: "{self.config.bucket}")
            |> range(start: {start_time.isoformat() if start_time else "-30d"},
                     stop: {end_time.isoformat() if end_time else "now()"})
            |> {query}
            '''

            result = self.query_api.query(flux_query)

            points = []
            for table in result:
                for record in table.records:
                    point = TimeSeriesPoint(
                        measurement=record.get_measurement(),
                        timestamp=record.get_time().timestamp(),
                        value=record.get_value(),
                        tags={k: v for k, v in record.values.items() if k != '_value' and k != '_time'},
                        fields={'value': record.get_value()}
                    )
                    points.append(point)

            return points

        except Exception as e:
            logger.error(f"InfluxDBクエリエラー: {e}")
            return []

    def health_check(self) -> bool:
        if not self.client:
            return False

        try:
            health = self.client.health()
            return health.status == "pass"
        except Exception:
            return False


class TimeSeriesManager:
    """時系列データベースマネージャー"""

    def __init__(self, config: TimeSeriesConfig):
        self.config = config
        self.backend: Optional[TimeSeriesBackend] = None
        self.connected = False
        self._batch_queue: List[TimeSeriesPoint] = []
        self._batch_lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None
        self._shutdown_event = threading.Event()

        # バックエンド初期化
        self._init_backend()

    def _init_backend(self) -> None:
        """バックエンド初期化"""
        if not self.config.enabled:
            return

        try:
            self.config.validate()

            if self.config.provider == "prometheus":
                self.backend = PrometheusBackend(self.config)
            elif self.config.provider == "influxdb":
                self.backend = InfluxDBBackend(self.config)
            else:
                raise ValueError(f"未対応のプロバイダー: {self.config.provider}")

        except Exception as e:
            logger.error(f"時系列データベースバックエンド初期化エラー: {e}")
            self.backend = None

    def connect(self) -> bool:
        """データベース接続"""
        if not self.backend:
            return False

        self.connected = self.backend.connect()
        if self.connected:
            # 定期フラッシュタイマー開始
            self._start_flush_timer()

        return self.connected

    def disconnect(self) -> None:
        """データベース切断"""
        self._shutdown_event.set()

        if self._flush_timer:
            self._flush_timer.cancel()
            self._flush_timer = None

        if self.backend:
            self.backend.disconnect()

        self.connected = False

    def write_metric(self, measurement: str, value: Union[int, float],
                    tags: Optional[Dict[str, str]] = None,
                    fields: Optional[Dict[str, Union[int, float, str]]] = None) -> None:
        """メトリクスデータを書き込み"""
        if not self.connected or not self.backend:
            return

        point = TimeSeriesPoint(
            measurement=measurement,
            timestamp=time.time(),
            value=value,
            tags=tags or {},
            fields=fields or {}
        )

        # デフォルトタグ追加
        point.tags.update(self.config.labels)

        with self._batch_lock:
            self._batch_queue.append(point)

            # バッチサイズチェック
            if len(self._batch_queue) >= self.config.batch_size:
                self._flush_batch()

    def _start_flush_timer(self) -> None:
        """定期フラッシュタイマーを開始"""
        if self._flush_timer:
            self._flush_timer.cancel()

        self._flush_timer = threading.Timer(self.config.flush_interval_seconds, self._flush_batch)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _flush_batch(self) -> None:
        """バッチデータをフラッシュ"""
        if self._shutdown_event.is_set():
            return

        with self._batch_lock:
            if not self._batch_queue:
                return

            points = self._batch_queue.copy()
            self._batch_queue.clear()

        if self.backend and points:
            success = self.backend.write_points(points)
            if not success:
                logger.warning("時系列データベースへの書き込みに失敗しました")

        # 次のタイマーを開始
        if not self._shutdown_event.is_set():
            self._start_flush_timer()

    def query_metrics(self, measurement: str, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[TimeSeriesPoint]:
        """メトリクスデータをクエリ"""
        if not self.backend:
            return []

        # デフォルトクエリ（InfluxDB用）
        if self.config.provider == "influxdb":
            query = f'filter(fn: (r) => r._measurement == "{measurement}")'
            return self.backend.query(query, start_time, end_time)
        else:
            return []

    def health_check(self) -> bool:
        """ヘルスチェック"""
        if not self.backend:
            return False

        return self.backend.health_check()

    def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        with self._batch_lock:
            queue_size = len(self._batch_queue)

        return {
            "connected": self.connected,
            "provider": self.config.provider,
            "queue_size": queue_size,
            "batch_size": self.config.batch_size,
            "flush_interval": self.config.flush_interval_seconds,
            "retention_days": self.config.retention_days,
        }


# グローバルマネージャーインスタンス
_timeseries_manager: Optional[TimeSeriesManager] = None


def init_timeseries_manager(config: TimeSeriesConfig) -> bool:
    """時系列データベースマネージャーを初期化"""
    global _timeseries_manager

    try:
        _timeseries_manager = TimeSeriesManager(config)
        success = _timeseries_manager.connect()

        if success:
            logger.info(f"時系列データベースマネージャーを初期化しました: {config.provider}")
        else:
            logger.error("時系列データベース接続に失敗しました")

        return success

    except Exception as e:
        logger.error(f"時系列データベースマネージャー初期化エラー: {e}")
        return False


def get_timeseries_manager() -> Optional[TimeSeriesManager]:
    """時系列データベースマネージャーを取得"""
    return _timeseries_manager


def write_metric_to_timeseries(measurement: str, value: Union[int, float],
                              tags: Optional[Dict[str, str]] = None) -> None:
    """時系列データベースにメトリクスを書き込み（便利関数）"""
    manager = get_timeseries_manager()
    if manager:
        manager.write_metric(measurement, value, tags)


def shutdown_timeseries_manager() -> None:
    """時系列データベースマネージャーをシャットダウン"""
    global _timeseries_manager

    if _timeseries_manager:
        _timeseries_manager.disconnect()
        _timeseries_manager = None
