"""
Mimir long-term metrics storage integration

Mimir provides scalable, highly available metrics storage.
Key features:
- Long-term metrics retention
- Multi-tenant support
- Prometheus-compatible API
- PromQL querying support
- Horizontal scalability
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


@dataclass
class MetricSeries:
    """Prometheus/Mimir metric series"""
    metric_name: str
    labels: Dict[str, str]
    values: List[Tuple[int, str]]  # List of (timestamp, value) tuples
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram, summary


@dataclass
class QueryResult:
    """Query result from Mimir"""
    metric_name: str
    labels: Dict[str, str]
    samples: List[Tuple[int, float]]  # List of (timestamp, value) tuples
    result_type: str  # instant, range, matrix


@dataclass
class RuleGroup:
    """Prometheus recording/alerting rule group"""
    name: str
    interval: str  # e.g., "1m", "5m"
    rules: List[Dict[str, Any]]


class MimirClient:
    """Mimir metrics storage client"""

    def __init__(
        self,
        endpoint: str = "http://localhost:9009",
        tenant_id: str = "default",
        username: str = "",
        password: str = "",
    ):
        """
        Initialize Mimir client

        Args:
            endpoint: Mimir distributor endpoint
            tenant_id: Tenant ID for multi-tenancy
            username: Basic auth username (if enabled)
            password: Basic auth password (if enabled)
        """
        self.endpoint = endpoint
        self.tenant_id = tenant_id
        self.username = username
        self.password = password

        self._verify_connection()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for Mimir API"""
        return {
            "X-Scope-OrgID": self.tenant_id,
            "Content-Type": "application/json",
        }

    def _verify_connection(self) -> bool:
        """Verify Mimir distributor is accessible"""
        try:
            response = requests.get(
                f"{self.endpoint}/ready",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"Connected to Mimir at {self.endpoint}")
                return True
        except requests.RequestException as e:
            logger.warning(f"Mimir connection failed: {e}")
            return False

    def push_metrics(self, series_list: List[MetricSeries]) -> bool:
        """
        Push metrics to Mimir (Prometheus format)

        Args:
            series_list: List of metric series

        Returns:
            True if successful, False otherwise
        """
        if not series_list:
            return True

        try:
            # Convert to Prometheus remote write format
            timeseries = []

            for series in series_list:
                # Build Prometheus labels
                labels = [
                    {"name": "__name__", "value": series.metric_name}
                ]

                for label_name, label_value in series.labels.items():
                    labels.append({
                        "name": label_name,
                        "value": label_value
                    })

                # Convert values to samples
                samples = [
                    {
                        "timestamp": ts,
                        "value": float(value)
                    }
                    for ts, value in series.values
                ]

                timeseries.append({
                    "labels": labels,
                    "samples": samples,
                })

            payload = {"timeseries": timeseries}

            response = requests.post(
                f"{self.endpoint}/api/prom/push",
                json=payload,
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code in (200, 204):
                logger.debug(f"Pushed {len(series_list)} metric series to Mimir")
                return True
            else:
                logger.error(f"Push failed: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Push error: {e}")
            return False

    def query(
        self,
        promql: str,
        time: Optional[int] = None,
    ) -> List[QueryResult]:
        """
        Execute instant PromQL query

        Args:
            promql: PromQL query string
            time: Unix timestamp (default: now)

        Returns:
            List of query results
        """
        params = {"query": promql}

        if time:
            params["time"] = time

        try:
            response = requests.get(
                f"{self.endpoint}/api/prom/query",
                params=params,
                headers=self._get_headers(),
                timeout=30,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code == 200:
                return self._parse_query_response(response.json())
            else:
                logger.error(f"Query failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"Query error: {e}")
            return []

    def query_range(
        self,
        promql: str,
        start: int,
        end: int,
        step: str = "15s",
    ) -> List[QueryResult]:
        """
        Execute range PromQL query

        Args:
            promql: PromQL query string
            start: Start Unix timestamp
            end: End Unix timestamp
            step: Query step (e.g., "15s", "1m")

        Returns:
            List of query results
        """
        params = {
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        }

        try:
            response = requests.get(
                f"{self.endpoint}/api/prom/query_range",
                params=params,
                headers=self._get_headers(),
                timeout=30,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code == 200:
                return self._parse_query_response(response.json())
            else:
                logger.error(f"Query range failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"Query range error: {e}")
            return []

    @staticmethod
    def _parse_query_response(data: Dict[str, Any]) -> List[QueryResult]:
        """Parse Prometheus query response"""
        results = []
        result_data = data.get("data", {}).get("result", [])

        for item in result_data:
            metric = item.get("metric", {})
            metric_name = metric.pop("__name__", "unknown")

            # Handle instant query (single value)
            if "value" in item:
                value = item["value"]
                results.append(QueryResult(
                    metric_name=metric_name,
                    labels=metric,
                    samples=[(int(value[0]), float(value[1]))],
                    result_type="instant",
                ))

            # Handle range query (multiple values)
            elif "values" in item:
                samples = [
                    (int(v[0]), float(v[1]))
                    for v in item["values"]
                ]
                results.append(QueryResult(
                    metric_name=metric_name,
                    labels=metric,
                    samples=samples,
                    result_type="range",
                ))

        return results

    def list_metrics(self) -> List[str]:
        """
        List all metric names in Mimir

        Returns:
            List of metric names
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/prom/label/__name__/values",
                headers=self._get_headers(),
                timeout=30,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"List metrics failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"List metrics error: {e}")
            return []

    def list_label_values(self, label_name: str) -> List[str]:
        """
        List all values for a specific label

        Args:
            label_name: Label name

        Returns:
            List of label values
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/prom/label/{label_name}/values",
                headers=self._get_headers(),
                timeout=30,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"List label values failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"List label values error: {e}")
            return []

    def create_recording_rule(
        self,
        rule_group: RuleGroup,
        namespace: str = "default",
    ) -> bool:
        """
        Create recording rule in Mimir

        Args:
            rule_group: Rule group configuration
            namespace: Rule namespace

        Returns:
            True if successful, False otherwise
        """
        payload = {
            "name": rule_group.name,
            "interval": rule_group.interval,
            "rules": rule_group.rules,
        }

        try:
            response = requests.post(
                f"{self.endpoint}/api/prom/rules/{namespace}",
                json=payload,
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code in (200, 201):
                logger.info(f"Created rule group: {rule_group.name}")
                return True
            else:
                logger.error(f"Create rule failed: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Create rule error: {e}")
            return False

    def get_metric_metadata(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get metric metadata (help text, type)

        Returns:
            Dictionary of metric metadata
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/prom/metadata",
                headers=self._get_headers(),
                timeout=30,
                auth=(self.username, self.password) if self.username else None,
            )

            if response.status_code == 200:
                return response.json().get("data", {})
            else:
                logger.error(f"Get metadata failed: {response.status_code}")
                return {}

        except requests.RequestException as e:
            logger.error(f"Get metadata error: {e}")
            return {}
