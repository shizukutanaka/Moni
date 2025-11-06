"""
Tempo distributed tracing integration

Tempo provides cost-effective, high-scale distributed tracing.
Key features:
- OpenTelemetry native support
- Multiple backends (S3, GCS, etc.)
- Automatic span search
- Integration with Grafana
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """OpenTelemetry span representation"""
    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation_name: str
    service_name: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    status_code: int  # 0=unset, 1=ok, 2=error
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Trace:
    """Complete trace with all spans"""
    trace_id: str
    spans: List[Span]
    start_time_unix_nano: int
    duration_nano: int
    status: str  # success, error, unknown


@dataclass
class TraceSearch:
    """Trace search parameters"""
    service_name: str | None = None
    operation_name: str | None = None
    min_duration: str | None = None  # e.g., "100ms", "1s"
    max_duration: str | None = None
    status: str | None = None  # ok, error
    tags: Dict[str, str] | None = None
    limit: int = 20


class TempoClient:
    """Tempo distributed tracing client"""

    def __init__(
        self,
        endpoint: str = "http://localhost:3200",
        otlp_endpoint: str = "http://localhost:4317",
    ):
        """
        Initialize Tempo client

        Args:
            endpoint: Tempo query endpoint
            otlp_endpoint: OTLP gRPC endpoint for span ingestion
        """
        self.endpoint = endpoint
        self.otlp_endpoint = otlp_endpoint

        self._verify_connection()

    def _verify_connection(self) -> bool:
        """Verify Tempo server is accessible"""
        try:
            response = requests.get(
                f"{self.endpoint}/ready",
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"Connected to Tempo at {self.endpoint}")
                return True
        except requests.RequestException as e:
            logger.warning(f"Tempo connection failed: {e}")
            return False

    def search_traces(self, search: TraceSearch) -> List[Dict[str, Any]]:
        """
        Search for traces in Tempo

        Args:
            search: TraceSearch parameters

        Returns:
            List of traces matching search criteria
        """
        params = {
            "limit": search.limit,
        }

        if search.service_name:
            params["service.name"] = search.service_name

        if search.operation_name:
            params["name"] = search.operation_name

        if search.min_duration:
            params["minDuration"] = search.min_duration

        if search.max_duration:
            params["maxDuration"] = search.max_duration

        if search.status:
            params["status"] = search.status

        if search.tags:
            for key, value in search.tags.items():
                params[f"tags.{key}"] = value

        try:
            response = requests.get(
                f"{self.endpoint}/api/search",
                params=params,
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("traces", [])
            else:
                logger.error(f"Search failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"Search error: {e}")
            return []

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """
        Get complete trace by ID

        Args:
            trace_id: Trace ID

        Returns:
            Trace object or None
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/traces/{trace_id}",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return self._parse_trace(data)
            else:
                logger.error(f"Get trace failed: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Get trace error: {e}")
            return None

    @staticmethod
    def _parse_trace(data: Dict[str, Any]) -> Trace:
        """Parse Tempo trace response to Trace object"""
        trace_id = data.get("traceID", "")
        resource_spans = data.get("resourceSpans", [])

        spans = []
        min_start_time = float("inf")
        max_end_time = 0

        for resource_span in resource_spans:
            scope_spans = resource_span.get("scopeSpans", [])
            service_name = (
                resource_span.get("resource", {})
                .get("attributes", {})
                .get("service.name", "unknown")
            )

            for scope_span in scope_spans:
                for span_data in scope_span.get("spans", []):
                    start_time = int(span_data.get("startTimeUnixNano", 0))
                    end_time = int(span_data.get("endTimeUnixNano", 0))

                    min_start_time = min(min_start_time, start_time)
                    max_end_time = max(max_end_time, end_time)

                    span = Span(
                        trace_id=trace_id,
                        span_id=span_data.get("spanId", ""),
                        parent_span_id=span_data.get("parentSpanId"),
                        operation_name=span_data.get("name", ""),
                        service_name=service_name,
                        start_time_unix_nano=start_time,
                        end_time_unix_nano=end_time,
                        status_code=span_data.get("status", {}).get("code", 0),
                        attributes=TempoClient._parse_attributes(
                            span_data.get("attributes", [])
                        ),
                        events=span_data.get("events", []),
                        links=span_data.get("links", []),
                    )
                    spans.append(span)

        return Trace(
            trace_id=trace_id,
            spans=spans,
            start_time_unix_nano=int(min_start_time) if min_start_time != float("inf") else 0,
            duration_nano=int(max_end_time - min_start_time),
            status="success" if max_end_time > 0 else "unknown",
        )

    @staticmethod
    def _parse_attributes(attributes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert Tempo attribute format to dict"""
        result = {}
        for attr in attributes:
            key = attr.get("key", "")
            value = attr.get("value", {})

            # Handle different value types
            if "stringValue" in value:
                result[key] = value["stringValue"]
            elif "intValue" in value:
                result[key] = value["intValue"]
            elif "doubleValue" in value:
                result[key] = value["doubleValue"]
            elif "boolValue" in value:
                result[key] = value["boolValue"]
            else:
                result[key] = str(value)

        return result

    def get_service_graph(self) -> Optional[Dict[str, Any]]:
        """
        Get service topology graph

        Returns:
            Service graph data or None
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/echo",
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get service graph failed: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Get service graph error: {e}")
            return None

    def get_span_metrics(self, trace_id: str) -> Dict[str, Any]:
        """
        Calculate metrics for trace spans

        Args:
            trace_id: Trace ID

        Returns:
            Metrics dictionary
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return {}

        metrics = {
            "trace_id": trace_id,
            "span_count": len(trace.spans),
            "total_duration_ms": trace.duration_nano / 1_000_000,
            "error_count": sum(1 for s in trace.spans if s.status_code == 2),
            "service_count": len(set(s.service_name for s in trace.spans)),
            "critical_path_ms": self._calculate_critical_path(trace) / 1_000_000,
        }

        return metrics

    @staticmethod
    def _calculate_critical_path(trace: Trace) -> int:
        """Calculate critical path duration in nanoseconds"""
        if not trace.spans:
            return 0

        # Simple implementation: find longest parent-child chain
        # In production, use more sophisticated critical path analysis
        return trace.duration_nano

    def export_trace_json(self, trace_id: str, filepath: str) -> bool:
        """
        Export trace to JSON file

        Args:
            trace_id: Trace ID
            filepath: Output file path

        Returns:
            True if successful, False otherwise
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return False

        try:
            trace_dict = {
                "trace_id": trace.trace_id,
                "spans": [
                    {
                        "span_id": s.span_id,
                        "parent_span_id": s.parent_span_id,
                        "operation_name": s.operation_name,
                        "service_name": s.service_name,
                        "start_time_unix_nano": s.start_time_unix_nano,
                        "duration_nano": s.end_time_unix_nano - s.start_time_unix_nano,
                        "status_code": s.status_code,
                        "attributes": s.attributes,
                    }
                    for s in trace.spans
                ],
                "status": trace.status,
            }

            with open(filepath, "w") as f:
                json.dump(trace_dict, f, indent=2)

            logger.info(f"Exported trace to {filepath}")
            return True

        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Export trace error: {e}")
            return False
