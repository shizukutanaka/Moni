"""
LGTM Stack initialization and orchestration

Coordinates Loki, Grafana, Tempo, and Mimir components
for complete observability pipeline
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from moni.loki_integration import LokiClient, LogEntry
from moni.grafana_integration import GrafanaClient, DataSource, Dashboard
from moni.tempo_integration import TempoClient
from moni.mimir_integration import MimirClient, MetricSeries

logger = logging.getLogger(__name__)


class LGTMStack:
    """LGTM Stack orchestrator"""

    def __init__(
        self,
        loki_endpoint: str = "http://localhost:3100",
        grafana_endpoint: str = "http://localhost:3000",
        tempo_endpoint: str = "http://localhost:3200",
        mimir_endpoint: str = "http://localhost:9009",
        grafana_api_key: str = "",
    ):
        """
        Initialize LGTM stack

        Args:
            loki_endpoint: Loki server endpoint
            grafana_endpoint: Grafana server endpoint
            tempo_endpoint: Tempo server endpoint
            mimir_endpoint: Mimir server endpoint
            grafana_api_key: Grafana API key for authentication
        """
        self.loki_client: Optional[LokiClient] = None
        self.grafana_client: Optional[GrafanaClient] = None
        self.tempo_client: Optional[TempoClient] = None
        self.mimir_client: Optional[MimirClient] = None

        self.loki_endpoint = loki_endpoint
        self.grafana_endpoint = grafana_endpoint
        self.tempo_endpoint = tempo_endpoint
        self.mimir_endpoint = mimir_endpoint
        self.grafana_api_key = grafana_api_key

        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize all LGTM stack clients"""
        try:
            self.loki_client = LokiClient(endpoint=self.loki_endpoint)
            logger.info("Loki client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Loki client: {e}")

        try:
            self.grafana_client = GrafanaClient(
                endpoint=self.grafana_endpoint,
                api_key=self.grafana_api_key,
            )
            logger.info("Grafana client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Grafana client: {e}")

        try:
            self.tempo_client = TempoClient(endpoint=self.tempo_endpoint)
            logger.info("Tempo client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Tempo client: {e}")

        try:
            self.mimir_client = MimirClient(endpoint=self.mimir_endpoint)
            logger.info("Mimir client initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Mimir client: {e}")

    def log_event(
        self,
        message: str,
        level: str = "INFO",
        source: str = "application",
        labels: Optional[Dict[str, str]] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log event through Loki

        Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source: Event source
            labels: Loki labels for filtering
            fields: Additional fields

        Returns:
            True if successful, False otherwise
        """
        if not self.loki_client:
            return False

        try:
            from datetime import datetime

            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                source=source,
                message=message,
                labels=labels or {},
                fields=fields or {},
            )

            return self.loki_client.send_log(log_entry)

        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False

    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[int] = None,
    ) -> bool:
        """
        Record metric through Mimir

        Args:
            metric_name: Metric name
            value: Metric value
            labels: Metric labels
            timestamp: Unix timestamp (default: now)

        Returns:
            True if successful, False otherwise
        """
        if not self.mimir_client:
            return False

        try:
            import time

            if timestamp is None:
                timestamp = int(time.time())

            series = MetricSeries(
                metric_name=metric_name,
                labels=labels or {},
                values=[(timestamp, str(value))],
                metric_type="gauge",
            )

            return self.mimir_client.push_metrics([series])

        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
            return False

    def setup_default_dashboards(self) -> bool:
        """
        Setup default monitoring dashboards in Grafana

        Returns:
            True if successful, False otherwise
        """
        if not self.grafana_client:
            return False

        try:
            # Setup data sources
            self._setup_datasources()

            # Create system dashboard
            system_dashboard = self._create_system_dashboard()
            self.grafana_client.create_dashboard(system_dashboard)

            # Create application dashboard
            app_dashboard = self._create_application_dashboard()
            self.grafana_client.create_dashboard(app_dashboard)

            logger.info("Default dashboards created")
            return True

        except Exception as e:
            logger.error(f"Failed to setup dashboards: {e}")
            return False

    def _setup_datasources(self) -> bool:
        """Setup Grafana data sources"""
        if not self.grafana_client:
            return False

        try:
            # Prometheus/Mimir datasource
            prometheus_ds = DataSource(
                name="Mimir",
                type="prometheus",
                url=self.mimir_endpoint,
                is_default=True,
            )
            self.grafana_client.create_datasource(prometheus_ds)

            # Loki datasource
            loki_ds = DataSource(
                name="Loki",
                type="loki",
                url=self.loki_endpoint,
            )
            self.grafana_client.create_datasource(loki_ds)

            # Tempo datasource
            tempo_ds = DataSource(
                name="Tempo",
                type="tempo",
                url=self.tempo_endpoint,
            )
            self.grafana_client.create_datasource(tempo_ds)

            logger.info("Data sources created")
            return True

        except Exception as e:
            logger.error(f"Failed to setup datasources: {e}")
            return False

    @staticmethod
    def _create_system_dashboard() -> Dashboard:
        """Create system metrics dashboard"""
        return Dashboard(
            title="System Metrics",
            description="System CPU, memory, and network metrics",
            tags=["system", "monitoring"],
            panels=[
                {
                    "title": "CPU Usage",
                    "targets": [
                        {
                            "expr": "cpu_usage",
                            "refId": "A",
                        }
                    ],
                },
                {
                    "title": "Memory Usage",
                    "targets": [
                        {
                            "expr": "memory_usage",
                            "refId": "A",
                        }
                    ],
                },
                {
                    "title": "Network I/O",
                    "targets": [
                        {
                            "expr": "network_io",
                            "refId": "A",
                        }
                    ],
                },
            ],
        )

    @staticmethod
    def _create_application_dashboard() -> Dashboard:
        """Create application metrics dashboard"""
        return Dashboard(
            title="Application Metrics",
            description="Application performance and health metrics",
            tags=["application", "monitoring"],
            panels=[
                {
                    "title": "Request Rate",
                    "targets": [
                        {
                            "expr": "rate(http_requests_total[5m])",
                            "refId": "A",
                        }
                    ],
                },
                {
                    "title": "Error Rate",
                    "targets": [
                        {
                            "expr": "rate(http_errors_total[5m])",
                            "refId": "A",
                        }
                    ],
                },
                {
                    "title": "Response Time",
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, http_request_duration_seconds)",
                            "refId": "A",
                        }
                    ],
                },
            ],
        )

    def get_health_status(self) -> Dict[str, bool]:
        """
        Get health status of all LGTM components

        Returns:
            Dictionary with health status of each component
        """
        return {
            "loki": self.loki_client is not None,
            "grafana": self.grafana_client is not None,
            "tempo": self.tempo_client is not None,
            "mimir": self.mimir_client is not None,
        }

    def shutdown(self) -> None:
        """Shutdown and cleanup LGTM stack"""
        if self.loki_client:
            self.loki_client.close()
            logger.info("Loki client closed")

        logger.info("LGTM stack shutdown complete")
