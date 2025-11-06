"""
Tests for LGTM Stack integration components

Phase 2 integration tests for Loki, Grafana, Tempo, and Mimir
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from moni.loki_integration import (
    LokiClient,
    LogEntry,
)
from moni.grafana_integration import (
    GrafanaClient,
    Dashboard,
    DataSource,
    Alert,
)
from moni.tempo_integration import (
    TempoClient,
    Trace,
    Span,
    TraceSearch,
)
from moni.mimir_integration import (
    MimirClient,
    MetricSeries,
    QueryResult,
    RuleGroup,
)


class TestLokiClient:
    """Tests for Loki log aggregation client"""

    @pytest.fixture
    def loki_client(self):
        """Create Loki client instance"""
        with patch('moni.loki_integration.requests.get'):
            return LokiClient(endpoint="http://localhost:3100")

    def test_loki_init(self, loki_client):
        """Test Loki client initialization"""
        assert loki_client.endpoint == "http://localhost:3100"
        assert loki_client.tenant_id == "default"
        assert loki_client.batch_size == 100
        assert loki_client.flush_interval == 5

    def test_loki_format_labels(self):
        """Test label formatting"""
        labels = {"service": "moni", "env": "prod"}
        formatted = LokiClient._format_labels(labels)
        assert formatted == '{env="prod",service="moni"}'

    def test_loki_parse_labels(self):
        """Test label parsing"""
        labels_str = '{env="prod",service="moni"}'
        parsed = LokiClient._parse_labels(labels_str)
        assert parsed["env"] == "prod"
        assert parsed["service"] == "moni"

    def test_loki_format_log_line(self):
        """Test log line formatting"""
        log = LogEntry(
            timestamp=datetime.now(),
            level="ERROR",
            source="system",
            message="Test error",
            labels={"service": "moni"},
            fields={"error_code": 500}
        )
        formatted = LokiClient._format_log_line(log)
        assert "[ERROR] Test error" in formatted
        assert "error_code" in formatted

    @patch('moni.loki_integration.requests.post')
    def test_loki_flush_success(self, mock_post, loki_client):
        """Test successful log flush"""
        mock_post.return_value = Mock(status_code=204)

        log = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            source="app",
            message="Test log",
            labels={"service": "moni"},
            fields={}
        )

        loki_client.logs_buffer = [log]
        result = loki_client.flush()

        assert result is True
        assert len(loki_client.logs_buffer) == 0
        mock_post.assert_called_once()

    @patch('moni.loki_integration.requests.post')
    def test_loki_flush_failure(self, mock_post, loki_client):
        """Test failed log flush"""
        mock_post.return_value = Mock(status_code=500)

        log = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            source="app",
            message="Test log",
            labels={"service": "moni"},
            fields={}
        )

        loki_client.logs_buffer = [log]
        result = loki_client.flush()

        assert result is False

    @patch('moni.loki_integration.requests.get')
    def test_loki_query(self, mock_get, loki_client):
        """Test LogQL query"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": {
                    "result": [
                        {
                            "stream": {"service": "moni"},
                            "values": [["1234567890000000000", "test message"]]
                        }
                    ]
                }
            }
        )

        results = loki_client.query('{service="moni"}')
        assert len(results) > 0


class TestGrafanaClient:
    """Tests for Grafana integration client"""

    @pytest.fixture
    def grafana_client(self):
        """Create Grafana client instance"""
        with patch('moni.grafana_integration.requests.get'):
            return GrafanaClient(endpoint="http://localhost:3000")

    def test_grafana_init(self, grafana_client):
        """Test Grafana client initialization"""
        assert grafana_client.endpoint == "http://localhost:3000"
        assert grafana_client.username == "admin"
        assert grafana_client.password == "admin"

    def test_grafana_get_headers_with_api_key(self):
        """Test headers with API key"""
        with patch('moni.grafana_integration.requests.get'):
            client = GrafanaClient(api_key="test-key")
            headers = client._get_headers()
            assert headers["Authorization"] == "Bearer test-key"

    @patch('moni.grafana_integration.requests.post')
    def test_grafana_create_datasource(self, mock_post, grafana_client):
        """Test datasource creation"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"id": 1, "name": "prometheus"}
        )

        ds = DataSource(
            name="prometheus",
            type="prometheus",
            url="http://localhost:9090"
        )

        result = grafana_client.create_datasource(ds)
        assert result is not None
        assert result["id"] == 1

    @patch('moni.grafana_integration.requests.post')
    def test_grafana_create_dashboard(self, mock_post, grafana_client):
        """Test dashboard creation"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "id": 1,
                "uid": "abc123",
                "title": "Test Dashboard"
            }
        )

        dashboard = Dashboard(
            title="Test Dashboard",
            description="Test dashboard for unit tests",
            tags=["test"]
        )

        result = grafana_client.create_dashboard(dashboard)
        assert result is not None

    @patch('moni.grafana_integration.requests.get')
    def test_grafana_list_datasources(self, mock_get, grafana_client):
        """Test listing datasources"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [
                {"id": 1, "name": "prometheus"},
                {"id": 2, "name": "loki"}
            ]
        )

        results = grafana_client.list_datasources()
        assert len(results) == 2

    @patch('moni.grafana_integration.requests.delete')
    def test_grafana_delete_dashboard(self, mock_delete, grafana_client):
        """Test dashboard deletion"""
        mock_delete.return_value = Mock(status_code=200)

        result = grafana_client.delete_dashboard("abc123")
        assert result is True


class TestTempoClient:
    """Tests for Tempo distributed tracing client"""

    @pytest.fixture
    def tempo_client(self):
        """Create Tempo client instance"""
        with patch('moni.tempo_integration.requests.get'):
            return TempoClient(endpoint="http://localhost:3200")

    def test_tempo_init(self, tempo_client):
        """Test Tempo client initialization"""
        assert tempo_client.endpoint == "http://localhost:3200"
        assert tempo_client.otlp_endpoint == "http://localhost:4317"

    @patch('moni.tempo_integration.requests.get')
    def test_tempo_search_traces(self, mock_get, tempo_client):
        """Test trace search"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "traces": [
                    {
                        "traceID": "trace-123",
                        "spans": 5,
                        "duration": "1234ms"
                    }
                ]
            }
        )

        search = TraceSearch(service_name="moni")
        results = tempo_client.search_traces(search)
        assert len(results) > 0

    def test_tempo_parse_attributes(self):
        """Test attribute parsing"""
        attributes = [
            {"key": "service.name", "value": {"stringValue": "moni"}},
            {"key": "span.kind", "value": {"intValue": 1}},
        ]

        parsed = TempoClient._parse_attributes(attributes)
        assert parsed["service.name"] == "moni"
        assert parsed["span.kind"] == 1

    @patch('moni.tempo_integration.requests.get')
    def test_tempo_get_trace(self, mock_get, tempo_client):
        """Test getting trace by ID"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "traceID": "trace-123",
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {"key": "service.name", "value": {"stringValue": "moni"}}
                            ]
                        },
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "spanId": "span-123",
                                        "name": "test-operation",
                                        "startTimeUnixNano": 1000000000,
                                        "endTimeUnixNano": 2000000000,
                                        "status": {"code": 0},
                                        "attributes": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        )

        trace = tempo_client.get_trace("trace-123")
        assert trace is not None
        assert trace.trace_id == "trace-123"

    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_tempo_export_trace_json(self, mock_dump, mock_open, tempo_client):
        """Test trace export to JSON"""
        # Mock the trace retrieval
        with patch.object(tempo_client, 'get_trace') as mock_get_trace:
            trace = Trace(
                trace_id="trace-123",
                spans=[],
                start_time_unix_nano=1000000000,
                duration_nano=1000000000,
                status="success"
            )
            mock_get_trace.return_value = trace

            result = tempo_client.export_trace_json("trace-123", "/tmp/trace.json")
            assert result is True


class TestMimirClient:
    """Tests for Mimir metrics storage client"""

    @pytest.fixture
    def mimir_client(self):
        """Create Mimir client instance"""
        with patch('moni.mimir_integration.requests.get'):
            return MimirClient(endpoint="http://localhost:9009")

    def test_mimir_init(self, mimir_client):
        """Test Mimir client initialization"""
        assert mimir_client.endpoint == "http://localhost:9009"
        assert mimir_client.tenant_id == "default"

    def test_mimir_get_headers(self, mimir_client):
        """Test headers with tenant ID"""
        headers = mimir_client._get_headers()
        assert headers["X-Scope-OrgID"] == "default"

    @patch('moni.mimir_integration.requests.post')
    def test_mimir_push_metrics(self, mock_post, mimir_client):
        """Test pushing metrics"""
        mock_post.return_value = Mock(status_code=204)

        series = MetricSeries(
            metric_name="cpu_usage",
            labels={"instance": "server1"},
            values=[(1234567890, "45.5")],
            metric_type="gauge"
        )

        result = mimir_client.push_metrics([series])
        assert result is True
        mock_post.assert_called_once()

    @patch('moni.mimir_integration.requests.get')
    def test_mimir_query(self, mock_get, mimir_client):
        """Test PromQL instant query"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": {
                    "result": [
                        {
                            "metric": {"__name__": "cpu_usage"},
                            "value": [1234567890, "45.5"]
                        }
                    ]
                }
            }
        )

        results = mimir_client.query("cpu_usage")
        assert len(results) > 0

    @patch('moni.mimir_integration.requests.get')
    def test_mimir_list_metrics(self, mock_get, mimir_client):
        """Test listing metrics"""
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": ["cpu_usage", "memory_usage", "network_io"]
            }
        )

        results = mimir_client.list_metrics()
        assert len(results) == 3

    @patch('moni.mimir_integration.requests.post')
    def test_mimir_create_recording_rule(self, mock_post, mimir_client):
        """Test creating recording rule"""
        mock_post.return_value = Mock(status_code=201)

        rule_group = RuleGroup(
            name="cpu_rules",
            interval="1m",
            rules=[
                {
                    "record": "cpu:average",
                    "expr": "avg(cpu_usage)"
                }
            ]
        )

        result = mimir_client.create_recording_rule(rule_group)
        assert result is True


class TestLGTMIntegration:
    """Integration tests for full LGTM stack"""

    @pytest.mark.integration
    def test_lgtm_stack_logging_pipeline(self):
        """Test complete logging pipeline"""
        # Create clients
        with patch('moni.loki_integration.requests.get'):
            with patch('moni.loki_integration.requests.post'):
                loki = LokiClient()

                # Create log entry
                log = LogEntry(
                    timestamp=datetime.now(),
                    level="ERROR",
                    source="system",
                    message="Integration test error",
                    labels={"service": "moni", "env": "test"},
                    fields={"error_code": 500}
                )

                # Send log
                result = loki.send_log(log)
                assert result is True

    @pytest.mark.integration
    def test_lgtm_stack_metrics_pipeline(self):
        """Test complete metrics pipeline"""
        with patch('moni.mimir_integration.requests.get'):
            with patch('moni.mimir_integration.requests.post'):
                mimir = MimirClient()

                # Push metrics
                series = MetricSeries(
                    metric_name="test_metric",
                    labels={"env": "test"},
                    values=[(int(datetime.now().timestamp()), "123.45")],
                    metric_type="gauge"
                )

                result = mimir.push_metrics([series])
                assert result is True

                # Query metrics
                with patch('moni.mimir_integration.requests.get') as mock_get:
                    mock_get.return_value = Mock(
                        status_code=200,
                        json=lambda: {
                            "data": {"result": []}
                        }
                    )

                    results = mimir.query("test_metric")
                    assert isinstance(results, list)
