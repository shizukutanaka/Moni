"""
Loki log aggregation integration

Loki provides log aggregation compatible with Prometheus-like querying.
Key features:
- LogQL querying (like PromQL for logs)
- Cost-effective log storage
- Integration with Grafana
- Multi-tenant support
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Log entry data structure"""
    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    source: str  # application, system, network, security
    message: str
    labels: Dict[str, str]  # Loki labels for filtering
    fields: Dict[str, Any]  # Additional metadata


class LokiClient:
    """Loki log aggregation client"""

    def __init__(
        self,
        endpoint: str = "http://localhost:3100",
        tenant_id: str = "default",
        batch_size: int = 100,
        flush_interval: int = 5,
    ):
        """
        Initialize Loki client

        Args:
            endpoint: Loki server endpoint URL
            tenant_id: Multi-tenant identifier
            batch_size: Batch size for log sending
            flush_interval: Flush interval in seconds
        """
        self.endpoint = endpoint
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.logs_buffer: List[LogEntry] = []
        self.last_flush = time.time()

        # Verify connection
        self._verify_connection()

    def _verify_connection(self) -> bool:
        """Verify Loki server is accessible"""
        try:
            response = requests.get(
                f"{self.endpoint}/ready",
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"Connected to Loki at {self.endpoint}")
                return True
        except requests.RequestException as e:
            logger.warning(f"Loki connection failed: {e}")
            return False

    def send_log(self, log_entry: LogEntry) -> bool:
        """
        Send log entry to Loki

        Args:
            log_entry: LogEntry instance

        Returns:
            True if successful, False otherwise
        """
        self.logs_buffer.append(log_entry)

        # Auto-flush if buffer is full or time elapsed
        if self._should_flush():
            return self.flush()

        return True

    def _should_flush(self) -> bool:
        """Check if buffer should be flushed"""
        buffer_full = len(self.logs_buffer) >= self.batch_size
        time_elapsed = (time.time() - self.last_flush) >= self.flush_interval

        return buffer_full or time_elapsed

    def flush(self) -> bool:
        """
        Flush buffered logs to Loki

        Returns:
            True if successful, False otherwise
        """
        if not self.logs_buffer:
            return True

        try:
            # Group logs by labels (Loki stream format)
            streams = self._group_logs_by_stream()

            payload = {"streams": streams}

            response = requests.post(
                f"{self.endpoint}/loki/api/v1/push",
                json=payload,
                headers={"X-Scope-OrgID": self.tenant_id},
                timeout=10,
            )

            if response.status_code == 204:
                logger.debug(f"Flushed {len(self.logs_buffer)} logs to Loki")
                self.logs_buffer.clear()
                self.last_flush = time.time()
                return True
            else:
                logger.error(f"Loki push failed: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Failed to flush logs: {e}")
            return False

    def _group_logs_by_stream(self) -> List[Dict[str, Any]]:
        """Group logs by Loki streams (labels)"""
        streams_dict: Dict[str, List[tuple]] = {}

        for log in self.logs_buffer:
            # Create stream key from labels
            labels_str = self._format_labels(log.labels)

            if labels_str not in streams_dict:
                streams_dict[labels_str] = []

            # Convert timestamp to nanoseconds
            ts_ns = int(log.timestamp.timestamp() * 1e9)

            # Combine message with fields
            line = self._format_log_line(log)

            streams_dict[labels_str].append((ts_ns, line))

        # Convert to Loki stream format
        streams = []
        for labels_str, entries in streams_dict.items():
            stream = {
                "stream": self._parse_labels(labels_str),
                "values": entries,
            }
            streams.append(stream)

        return streams

    @staticmethod
    def _format_labels(labels: Dict[str, str]) -> str:
        """Format labels as Loki label string"""
        items = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"

    @staticmethod
    def _parse_labels(labels_str: str) -> Dict[str, str]:
        """Parse Loki label string back to dict"""
        labels_str = labels_str.strip("{}")
        labels = {}
        for item in labels_str.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                labels[k.strip()] = v.strip('"')
        return labels

    @staticmethod
    def _format_log_line(log: LogEntry) -> str:
        """Format log entry as single line with fields"""
        output = f"[{log.level}] {log.message}"

        if log.fields:
            fields_json = json.dumps(log.fields)
            output = f"{output} {fields_json}"

        return output

    def query(self, logql: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query logs using LogQL

        Args:
            logql: LogQL query string
            limit: Maximum results

        Returns:
            List of log results
        """
        try:
            response = requests.get(
                f"{self.endpoint}/loki/api/v1/query",
                params={
                    "query": logql,
                    "limit": limit,
                },
                headers={"X-Scope-OrgID": self.tenant_id},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("data", {}).get("result", [])
            else:
                logger.error(f"Query failed: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"Query error: {e}")
            return []

    def close(self) -> None:
        """Close client and flush remaining logs"""
        if self.logs_buffer:
            self.flush()
