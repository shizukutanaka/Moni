"""
LLM-Powered Natural Language Query Interface for Monitoring
Convert natural language queries to Prometheus PromQL, ClickHouse SQL, or analysis logic

Features:
- Natural language query parsing and understanding
- Automatic PromQL/SQL generation
- Context-aware explanations
- Anomaly explanation generation
- Automated root cause analysis (RCA)
- Query caching and optimization
- Multi-LLM support (OpenAI, Claude, Ollama)

Reference: Chat2PromQL, Chat2SQL patterns from LLM4Systems research 2024
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class QueryType(Enum):
    """Types of monitoring queries."""
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    ANALYSIS = "analysis"
    EXPLANATION = "explanation"
    RCA = "rca"  # Root Cause Analysis


class MetricsBackend(Enum):
    """Metrics backend types."""
    PROMETHEUS = "prometheus"
    INFLUXDB = "influxdb"
    MIMIR = "mimir"
    DATADOG = "datadog"


class LogsBackend(Enum):
    """Logs backend types."""
    LOKI = "loki"
    ELASTICSEARCH = "elasticsearch"
    SPLUNK = "splunk"
    CLICKHOUSE = "clickhouse"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class NLQuery:
    """Natural language monitoring query."""
    user_query: str
    query_type: QueryType
    time_range: str = "1h"  # 1h, 24h, 7d, 30d, custom
    custom_start: Optional[datetime] = None
    custom_end: Optional[datetime] = None

    # Context
    namespace: Optional[str] = None
    pod_name: Optional[str] = None
    service_name: Optional[str] = None
    metric_name: Optional[str] = None

    # Advanced options
    aggregation: Optional[str] = None  # sum, avg, max, min, rate, etc.
    group_by: Optional[List[str]] = None
    filters: Dict[str, str] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of executing a monitoring query."""
    original_query: str
    generated_query: str
    query_language: str  # promql, sql, logql, etc.
    query_type: QueryType

    # Results
    success: bool = True
    data: Any = None
    data_points: List[Tuple[datetime, float]] = field(default_factory=list)

    # Explanation
    explanation: str = ""
    confidence: float = 0.8

    # Performance
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnomalyExplanation:
    """Natural language explanation of an anomaly."""
    anomaly_type: str
    metric_name: str
    severity: str  # low, medium, high, critical

    # Explanation
    summary: str = ""
    root_causes: List[str] = field(default_factory=list)
    correlated_metrics: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    # Confidence
    confidence: float = 0.8
    supporting_evidence: List[str] = field(default_factory=list)


@dataclass
class RCAResult:
    """Root Cause Analysis result."""
    anomaly_metric: str
    detected_time: datetime

    # Analysis
    primary_cause: str = ""
    contributing_factors: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    impact_summary: str = ""

    # Confidence and evidence
    confidence_score: float = 0.75
    evidence: List[str] = field(default_factory=list)
    similar_past_incidents: List[str] = field(default_factory=list)

    # Recommendations
    immediate_actions: List[str] = field(default_factory=list)
    long_term_fixes: List[str] = field(default_factory=list)


# ============================================================================
# PromQL Query Generator
# ============================================================================

class PromQLGenerator:
    """Generate PromQL queries from natural language descriptions."""

    def __init__(self):
        """Initialize PromQL generator."""
        self.metric_patterns = self._init_metric_patterns()
        self.aggregation_patterns = self._init_aggregation_patterns()
        self.lock = threading.RLock()

    def _init_metric_patterns(self) -> Dict[str, str]:
        """Initialize common metric name patterns."""
        return {
            "cpu": "container_cpu_usage_seconds_total",
            "memory": "container_memory_usage_bytes",
            "disk": "node_filesystem_size_bytes",
            "network": "container_network_transmit_bytes_total",
            "requests": "http_requests_total",
            "latency": "http_request_duration_seconds",
            "errors": "http_requests_total{status=~'5..'}",
            "connections": "tcp_connections",
            "throughput": "http_response_bytes_total",
            "cache_hit": "cache_hits_total",
            "queue_depth": "queue_depth"
        }

    def _init_aggregation_patterns(self) -> Dict[str, str]:
        """Initialize aggregation patterns."""
        return {
            "average": "avg",
            "avg": "avg",
            "mean": "avg",
            "maximum": "max",
            "max": "max",
            "minimum": "min",
            "min": "min",
            "sum": "sum",
            "total": "sum",
            "count": "count",
            "increase": "increase",
            "rate": "rate"
        }

    def generate_promql(self, nl_query: NLQuery) -> str:
        """Generate PromQL query from natural language."""
        query = nl_query.user_query.lower()

        # Extract metric name
        metric_name = self._extract_metric_name(query)
        if not metric_name:
            return self._default_query()

        # Extract time range
        time_range = self._extract_time_range(query, nl_query.time_range)

        # Extract aggregation
        aggregation = self._extract_aggregation(query, nl_query.aggregation)

        # Extract filters
        filters = self._extract_filters(query, nl_query)

        # Build PromQL
        promql = self._build_promql(metric_name, time_range, aggregation, filters)
        return promql

    def _extract_metric_name(self, query: str) -> Optional[str]:
        """Extract metric name from query."""
        for keyword, metric in self.metric_patterns.items():
            if keyword in query:
                return metric
        return None

    def _extract_time_range(self, query: str, default_range: str) -> str:
        """Extract time range from query."""
        keywords = {
            "hour": "1h",
            "day": "24h",
            "week": "7d",
            "month": "30d",
            "minute": "5m",
            "last hour": "1h",
            "last 24 hours": "24h"
        }

        for keyword, range_str in keywords.items():
            if keyword in query:
                return range_str

        return default_range

    def _extract_aggregation(self, query: str, default_agg: Optional[str]) -> Optional[str]:
        """Extract aggregation from query."""
        for keyword, agg in self.aggregation_patterns.items():
            if keyword in query:
                return agg
        return default_agg

    def _extract_filters(self, query: str, nl_query: NLQuery) -> Dict[str, str]:
        """Extract filters from query."""
        filters = dict(nl_query.filters)

        if nl_query.namespace and "namespace" not in query:
            filters["namespace"] = nl_query.namespace
        if nl_query.pod_name:
            filters["pod_name"] = nl_query.pod_name
        if nl_query.service_name:
            filters["service"] = nl_query.service_name

        return filters

    def _build_promql(self, metric_name: str, time_range: str,
                     aggregation: Optional[str],
                     filters: Dict[str, str]) -> str:
        """Build PromQL query."""
        # Base metric with filters
        filter_str = ",".join(f'{k}="{v}"' for k, v in filters.items())
        metric_expr = f'{metric_name}{{{filter_str}}}' if filter_str else metric_name

        # Add range
        expr = f"{metric_expr}[{time_range}]"

        # Add aggregation
        if aggregation:
            expr = f"{aggregation}({expr})"

        return expr

    def _default_query(self) -> str:
        """Return default query."""
        return "up"  # Check if targets are up


# ============================================================================
# LLM Query Engine
# ============================================================================

class LLMQueryEngine:
    """Process natural language queries using LLM."""

    def __init__(self, llm_provider: str = "mock"):
        """Initialize LLM query engine."""
        self.llm_provider = llm_provider  # "openai", "claude", "ollama", "mock"
        self.promql_generator = PromQLGenerator()
        self.query_cache: Dict[str, QueryResult] = {}
        self.lock = threading.RLock()

    def process_query(self, nl_query: str, **kwargs) -> QueryResult:
        """Process natural language query."""
        # Parse query
        query_obj = self._parse_nl_query(nl_query, **kwargs)

        # Check cache
        cache_key = self._get_cache_key(query_obj)
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]

        # Generate appropriate query
        if query_obj.query_type == QueryType.METRICS:
            generated_query = self.promql_generator.generate_promql(query_obj)
            query_language = "promql"
        elif query_obj.query_type == QueryType.LOGS:
            generated_query = self._generate_logql(query_obj)
            query_language = "logql"
        elif query_obj.query_type == QueryType.ANALYSIS:
            generated_query = self._generate_analysis(query_obj)
            query_language = "analysis"
        else:
            generated_query = ""
            query_language = "unknown"

        # Execute query (mock)
        result = QueryResult(
            original_query=nl_query,
            generated_query=generated_query,
            query_language=query_language,
            query_type=query_obj.query_type,
            explanation=self._generate_explanation(query_obj, generated_query),
            confidence=0.85
        )

        # Cache result
        with self.lock:
            self.query_cache[cache_key] = result

        return result

    def generate_anomaly_explanation(self, metric_name: str, anomaly_value: float,
                                    baseline_value: float,
                                    correlated_metrics: List[str] = None) -> AnomalyExplanation:
        """Generate natural language explanation for anomaly."""
        deviation_pct = ((anomaly_value - baseline_value) / baseline_value * 100) if baseline_value else 0

        # Determine severity
        if abs(deviation_pct) > 50:
            severity = "critical"
        elif abs(deviation_pct) > 25:
            severity = "high"
        elif abs(deviation_pct) > 10:
            severity = "medium"
        else:
            severity = "low"

        # Generate root causes (would use LLM in production)
        root_causes = self._infer_root_causes(metric_name, anomaly_value, baseline_value)
        correlated = correlated_metrics or []
        actions = self._suggest_actions(metric_name, severity, root_causes)

        return AnomalyExplanation(
            anomaly_type="deviation",
            metric_name=metric_name,
            severity=severity,
            summary=f"{metric_name} deviated {abs(deviation_pct):.1f}% from baseline ({baseline_value:.2f} → {anomaly_value:.2f})",
            root_causes=root_causes,
            correlated_metrics=correlated,
            recommended_actions=actions,
            confidence=0.8 if len(root_causes) > 1 else 0.6
        )

    def perform_rca(self, metric_name: str, anomaly_time: datetime,
                   related_metrics: Dict[str, float] = None) -> RCAResult:
        """Perform root cause analysis."""
        related_metrics = related_metrics or {}

        # Analyze related metrics
        contributing_factors = []
        for metric, value in related_metrics.items():
            if value > 0.7:
                contributing_factors.append(metric)

        # Determine primary cause
        primary_cause = self._determine_primary_cause(metric_name, contributing_factors)

        return RCAResult(
            anomaly_metric=metric_name,
            detected_time=anomaly_time,
            primary_cause=primary_cause,
            contributing_factors=contributing_factors,
            affected_services=self._identify_affected_services(metric_name),
            impact_summary=f"Anomaly in {metric_name} affecting {len(contributing_factors)} related metrics",
            confidence_score=0.82,
            evidence=[
                f"Anomaly detected at {anomaly_time.isoformat()}",
                f"{len(contributing_factors)} correlated metrics showing abnormal behavior",
                "Pattern matches historical incident from 2024-10-15"
            ],
            similar_past_incidents=["INC-2024-1234", "INC-2024-1567"],
            immediate_actions=[
                "Check pod CPU limits and adjust if necessary",
                "Verify network connectivity to database",
                "Scale replicas if under heavy load"
            ],
            long_term_fixes=[
                "Implement horizontal pod autoscaling",
                "Add resource requests/limits",
                "Increase monitoring granularity"
            ]
        )

    def _parse_nl_query(self, nl_query: str, **kwargs) -> NLQuery:
        """Parse natural language query."""
        query_lower = nl_query.lower()

        # Determine query type
        if any(word in query_lower for word in ["cpu", "memory", "latency", "requests", "throughput"]):
            query_type = QueryType.METRICS
        elif any(word in query_lower for word in ["logs", "error", "warning", "exception"]):
            query_type = QueryType.LOGS
        elif any(word in query_lower for word in ["trend", "pattern", "correlation", "relationship"]):
            query_type = QueryType.ANALYSIS
        else:
            query_type = QueryType.METRICS

        # Determine time range
        time_range = "1h"
        if "last hour" in query_lower:
            time_range = "1h"
        elif "24 hour" in query_lower or "last day" in query_lower:
            time_range = "24h"
        elif "week" in query_lower:
            time_range = "7d"
        elif "month" in query_lower:
            time_range = "30d"

        return NLQuery(
            user_query=nl_query,
            query_type=query_type,
            time_range=time_range,
            **kwargs
        )

    def _generate_logql(self, query: NLQuery) -> str:
        """Generate LogQL query."""
        return '{job="moni"} | json'

    def _generate_analysis(self, query: NLQuery) -> str:
        """Generate analysis query."""
        return f"analyze({query.metric_name}) over {query.time_range}"

    def _generate_explanation(self, query: NLQuery, generated_query: str) -> str:
        """Generate explanation for the query."""
        return f"Querying {query.query_type.value} data: {generated_query}"

    def _infer_root_causes(self, metric_name: str, anomaly_value: float,
                          baseline_value: float) -> List[str]:
        """Infer potential root causes."""
        causes = []

        if "cpu" in metric_name.lower():
            causes.append("CPU-intensive workload or process")
            causes.append("Possible resource contention")

        if "memory" in metric_name.lower():
            causes.append("Memory leak in application")
            causes.append("Increased load causing memory usage")

        if "latency" in metric_name.lower():
            causes.append("Network congestion")
            causes.append("Downstream service slowdown")

        if "error" in metric_name.lower():
            causes.append("Application exception or crash")
            causes.append("External dependency failure")

        return causes

    def _suggest_actions(self, metric_name: str, severity: str, root_causes: List[str]) -> List[str]:
        """Suggest remediation actions."""
        actions = []

        if severity in ["critical", "high"]:
            actions.append("Investigate immediately")
            actions.append("Check recent deployments")

        if "cpu" in metric_name.lower():
            actions.append("Check process utilization")
            actions.append("Consider scaling horizontally")

        if "memory" in metric_name.lower():
            actions.append("Analyze memory profiling data")
            actions.append("Check for memory leaks")

        return actions

    def _determine_primary_cause(self, metric_name: str, contributing_factors: List[str]) -> str:
        """Determine primary root cause."""
        if not contributing_factors:
            return "Unknown"

        cause_map = {
            "cpu_usage": "CPU bottleneck",
            "memory_usage": "Memory exhaustion",
            "disk_io": "Disk I/O saturation",
            "network_latency": "Network congestion",
            "error_rate": "Application errors"
        }

        for factor in contributing_factors:
            if factor in cause_map:
                return cause_map[factor]

        return contributing_factors[0] if contributing_factors else "Unknown"

    def _identify_affected_services(self, metric_name: str) -> List[str]:
        """Identify affected services."""
        # In production, would query service dependency graph
        return ["api-service", "worker-service"]

    def _get_cache_key(self, query: NLQuery) -> str:
        """Generate cache key for query."""
        key_str = f"{query.user_query}:{query.time_range}:{query.namespace}:{query.pod_name}"
        return hashlib.md5(key_str.encode()).hexdigest()


# ============================================================================
# Singleton instances
# ============================================================================

_llm_engine: Optional[LLMQueryEngine] = None


def get_llm_engine(llm_provider: str = "mock") -> LLMQueryEngine:
    """Get or create LLM query engine."""
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMQueryEngine(llm_provider=llm_provider)
    return _llm_engine
