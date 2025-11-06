"""
OpenTelemetry統合モジュール

2025年業界標準に準拠したテレメトリ収集システム
- 85%の組織がOpenTelemetryに投資
- Prometheus 3.0ネイティブOTLPサポート
- ベンダー中立の監視フレームワーク
"""

from __future__ import annotations

import logging
import socket
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class OpenTelemetryIntegration:
    """
    OpenTelemetry統合マネージャー

    業界標準のテレメトリ収集とエクスポート機能を提供
    """

    def __init__(
        self,
        service_name: str = "moni-system-monitor",
        service_version: str = "2.0.0",
        otlp_endpoint: str = "http://localhost:4317",
        environment: str = "production",
        enabled: bool = True
    ):
        """
        初期化

        Args:
            service_name: サービス名
            service_version: サービスバージョン
            otlp_endpoint: OTLPコレクターエンドポイント
            environment: デプロイメント環境
            enabled: OpenTelemetry有効化フラグ
        """
        self.enabled = enabled and OTEL_AVAILABLE

        if not self.enabled:
            if not OTEL_AVAILABLE:
                logger.warning("OpenTelemetry not available - install: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")
            else:
                logger.info("OpenTelemetry integration disabled")
            return

        self.service_name = service_name
        self.service_version = service_version
        self.otlp_endpoint = otlp_endpoint
        self.environment = environment

        # リソース属性設定
        self.resource = Resource.create({
            SERVICE_NAME: self.service_name,
            SERVICE_VERSION: self.service_version,
            "deployment.environment": self.environment,
            "host.name": socket.gethostname(),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        })

        # トレーシングプロバイダー
        self._setup_tracing()

        # メトリクスプロバイダー
        self._setup_metrics()

        logger.info(
            f"OpenTelemetry initialized: service={service_name}, "
            f"endpoint={otlp_endpoint}, environment={environment}"
        )

    def _setup_tracing(self) -> None:
        """トレーシングプロバイダー設定"""
        try:
            # トレーサープロバイダー作成
            tracer_provider = TracerProvider(resource=self.resource)
            trace.set_tracer_provider(tracer_provider)

            # OTLPスパンエクスポーター設定
            otlp_trace_exporter = OTLPSpanExporter(
                endpoint=self.otlp_endpoint,
                insecure=True  # 本番環境ではTLS有効化
            )

            # バッチスパンプロセッサー追加
            tracer_provider.add_span_processor(
                BatchSpanProcessor(otlp_trace_exporter)
            )

            self.tracer = trace.get_tracer(
                __name__,
                self.service_version
            )

            logger.info("OpenTelemetry tracing configured successfully")

        except Exception as e:
            logger.error(f"Failed to setup OpenTelemetry tracing: {e}")
            self.enabled = False

    def _setup_metrics(self) -> None:
        """メトリクスプロバイダー設定"""
        try:
            # OTLPメトリクスエクスポーター設定
            otlp_metric_exporter = OTLPMetricExporter(
                endpoint=self.otlp_endpoint,
                insecure=True  # 本番環境ではTLS有効化
            )

            # 定期エクスポートリーダー
            metric_reader = PeriodicExportingMetricReader(
                otlp_metric_exporter,
                export_interval_millis=60000  # 60秒間隔
            )

            # メーターブロバイダー作成
            meter_provider = MeterProvider(
                resource=self.resource,
                metric_readers=[metric_reader]
            )
            metrics.set_meter_provider(meter_provider)

            self.meter = metrics.get_meter(
                __name__,
                self.service_version
            )

            # システムメトリクス用の計測器作成
            self._create_instruments()

            logger.info("OpenTelemetry metrics configured successfully")

        except Exception as e:
            logger.error(f"Failed to setup OpenTelemetry metrics: {e}")
            self.enabled = False

    def _create_instruments(self) -> None:
        """メトリクス計測器作成"""
        if not self.enabled:
            return

        # CPU使用率ゲージ
        self.cpu_gauge = self.meter.create_gauge(
            name="system.cpu.usage",
            description="CPU usage percentage",
            unit="percent"
        )

        # メモリ使用率ゲージ
        self.memory_gauge = self.meter.create_gauge(
            name="system.memory.usage",
            description="Memory usage percentage",
            unit="percent"
        )

        # ディスクI/Oカウンター
        self.disk_io_counter = self.meter.create_counter(
            name="system.disk.io.bytes",
            description="Disk I/O bytes",
            unit="bytes"
        )

        # ネットワークI/Oカウンター
        self.network_io_counter = self.meter.create_counter(
            name="system.network.io.bytes",
            description="Network I/O bytes",
            unit="bytes"
        )

        # メトリクス収集カウンター
        self.collection_counter = self.meter.create_counter(
            name="moni.metrics.collected",
            description="Number of metrics collected",
            unit="1"
        )

    def record_cpu_usage(self, usage: float, cpu_id: Optional[int] = None) -> None:
        """
        CPU使用率を記録

        Args:
            usage: CPU使用率 (0-100)
            cpu_id: CPU ID (None = 全体)
        """
        if not self.enabled:
            return

        try:
            attributes = {"cpu.id": str(cpu_id) if cpu_id is not None else "all"}
            self.cpu_gauge.set(usage, attributes)
        except Exception as e:
            logger.debug(f"Failed to record CPU usage: {e}")

    def record_memory_usage(self, usage: float, memory_type: str = "physical") -> None:
        """
        メモリ使用率を記録

        Args:
            usage: メモリ使用率 (0-100)
            memory_type: メモリタイプ (physical, swap, virtual)
        """
        if not self.enabled:
            return

        try:
            attributes = {"memory.type": memory_type}
            self.memory_gauge.set(usage, attributes)
        except Exception as e:
            logger.debug(f"Failed to record memory usage: {e}")

    def record_disk_io(self, bytes_value: int, operation: str, device: str) -> None:
        """
        ディスクI/Oを記録

        Args:
            bytes_value: バイト数
            operation: 操作タイプ (read, write)
            device: デバイス名
        """
        if not self.enabled:
            return

        try:
            attributes = {
                "disk.operation": operation,
                "disk.device": device
            }
            self.disk_io_counter.add(bytes_value, attributes)
        except Exception as e:
            logger.debug(f"Failed to record disk I/O: {e}")

    def record_network_io(
        self, bytes_value: int, direction: str, interface: str
    ) -> None:
        """
        ネットワークI/Oを記録

        Args:
            bytes_value: バイト数
            direction: 方向 (sent, received)
            interface: インターフェース名
        """
        if not self.enabled:
            return

        try:
            attributes = {
                "network.direction": direction,
                "network.interface": interface
            }
            self.network_io_counter.add(bytes_value, attributes)
        except Exception as e:
            logger.debug(f"Failed to record network I/O: {e}")

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        トレーシングスパン開始

        Args:
            name: スパン名
            attributes: スパン属性

        Returns:
            Span context manager
        """
        if not self.enabled:
            # ダミーコンテキストマネージャー
            class DummySpan:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def set_attribute(self, key, value):
                    pass
                def add_event(self, name, attributes=None):
                    pass
                def record_exception(self, exception):
                    pass
            return DummySpan()

        span = self.tracer.start_span(name)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        return span

    def record_metric_collection(self, metric_type: str, count: int = 1) -> None:
        """
        メトリクス収集を記録

        Args:
            metric_type: メトリクスタイプ
            count: 収集数
        """
        if not self.enabled:
            return

        try:
            attributes = {"metric.type": metric_type}
            self.collection_counter.add(count, attributes)
        except Exception as e:
            logger.debug(f"Failed to record metric collection: {e}")

    def shutdown(self) -> None:
        """シャットダウン処理"""
        if not self.enabled:
            return

        try:
            # トレーサープロバイダーのシャットダウン
            if hasattr(self, 'tracer'):
                trace_provider = trace.get_tracer_provider()
                if hasattr(trace_provider, 'shutdown'):
                    trace_provider.shutdown()

            # メータープロバイダーのシャットダウン
            if hasattr(self, 'meter'):
                meter_provider = metrics.get_meter_provider()
                if hasattr(meter_provider, 'shutdown'):
                    meter_provider.shutdown()

            logger.info("OpenTelemetry shutdown completed")

        except Exception as e:
            logger.error(f"Failed to shutdown OpenTelemetry: {e}")


# グローバルインスタンス (オプション)
_global_otel: Optional[OpenTelemetryIntegration] = None


def get_otel_integration() -> Optional[OpenTelemetryIntegration]:
    """グローバルOpenTelemetry統合インスタンス取得"""
    return _global_otel


def initialize_otel(
    service_name: str = "moni-system-monitor",
    otlp_endpoint: str = "http://localhost:4317",
    enabled: bool = True
) -> OpenTelemetryIntegration:
    """
    OpenTelemetry統合を初期化

    Args:
        service_name: サービス名
        otlp_endpoint: OTLPエンドポイント
        enabled: 有効化フラグ

    Returns:
        OpenTelemetryIntegrationインスタンス
    """
    global _global_otel
    _global_otel = OpenTelemetryIntegration(
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
        enabled=enabled
    )
    return _global_otel
