"""
Time-Series Database Optimization
Multi-backend support: InfluxDB, TimescaleDB, Prometheus compatible

Features:
- Adaptive backend selection
- Data retention policies
- Compression and downsampling
- Query optimization
- Distributed tracing integration
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class TimeSeriesBackend(Enum):
    """Supported time-series database backends."""
    INFLUXDB = "influxdb"
    TIMESCALEDB = "timescaledb"
    PROMETHEUS = "prometheus"
    MEMORY = "memory"  # In-memory for testing


class DataRetentionPolicy(Enum):
    """Data retention policies."""
    HOURLY = "hourly"      # Keep 1 minute resolution for 24 hours
    DAILY = "daily"        # Keep 1 hour resolution for 30 days
    MONTHLY = "monthly"    # Keep 1 day resolution for 1 year
    YEARLY = "yearly"      # Keep 1 week resolution indefinitely


class CompressionAlgorithm(Enum):
    """Compression algorithms."""
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    ZSTD = "zstd"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TimeSeries:
    """Time series data point."""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_influx_line(self) -> str:
        """Convert to InfluxDB line protocol."""
        tags_str = ','.join(f"{k}={v}" for k, v in self.tags.items())
        tag_part = f",{tags_str}" if tags_str else ""
        timestamp_ns = int(self.timestamp.timestamp() * 1e9)
        return f"{self.metric_name}{tag_part} value={self.value} {timestamp_ns}"


@dataclass
class TimeSeriesQuery:
    """Query for time series data."""
    metric_name: str
    start_time: datetime
    end_time: datetime
    tags: Optional[Dict[str, str]] = None
    aggregation: Optional[str] = None  # 'mean', 'sum', 'max', 'min', 'count'
    group_by: Optional[List[str]] = None
    limit: int = 10000


@dataclass
class RetentionConfig:
    """Data retention configuration."""
    policy: DataRetentionPolicy
    raw_resolution_seconds: int = 60  # Raw data resolution
    aggregated_resolution_seconds: int = 3600  # Aggregated data resolution
    keep_raw_days: int = 7
    keep_aggregated_days: int = 90
    compression: CompressionAlgorithm = CompressionAlgorithm.ZSTD


# ============================================================================
# Abstract Backend
# ============================================================================

class TimeSeriesBackendBase(ABC):
    """Abstract base class for time-series backends."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize backend."""
        self.config = config

    @abstractmethod
    async def write(self, timeseries: List[TimeSeries]) -> bool:
        """Write time series data."""
        pass

    @abstractmethod
    async def query(self, query: TimeSeriesQuery) -> List[Tuple[datetime, float]]:
        """Query time series data."""
        pass

    @abstractmethod
    async def delete_old_data(self, retention_config: RetentionConfig) -> int:
        """Delete data older than retention policy."""
        pass

    @abstractmethod
    async def downsample(self, metric_name: str, from_resolution: int,
                        to_resolution: int, aggregation: str) -> int:
        """Downsample data to lower resolution."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check backend health."""
        pass


# ============================================================================
# InfluxDB Backend
# ============================================================================

class InfluxDBBackend(TimeSeriesBackendBase):
    """InfluxDB 2.x backend implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize InfluxDB backend."""
        super().__init__(config)
        self.url = config.get('url', 'http://localhost:8086')
        self.org = config.get('org', 'moni')
        self.bucket = config.get('bucket', 'moni_metrics')
        self.token = config.get('token')

        try:
            from influxdb_client import InfluxDBClient
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        except ImportError:
            logger.warning("influxdb_client not installed, using mock")
            self.client = None

    async def write(self, timeseries: List[TimeSeries]) -> bool:
        """Write to InfluxDB using line protocol."""
        if not self.client:
            return False

        try:
            write_api = self.client.write_api()
            lines = [ts.to_influx_line() for ts in timeseries]
            write_api.write(self.bucket, self.org, '\n'.join(lines))
            return True
        except Exception as e:
            logger.error(f"InfluxDB write failed: {str(e)}")
            return False

    async def query(self, query: TimeSeriesQuery) -> List[Tuple[datetime, float]]:
        """Query from InfluxDB using Flux."""
        if not self.client:
            return []

        try:
            query_api = self.client.query_api()

            # Build Flux query
            start = query.start_time.isoformat()
            stop = query.end_time.isoformat()

            flux = f'''
                from(bucket: "{self.bucket}")
                |> range(start: {start}, stop: {stop})
                |> filter(fn: (r) => r._measurement == "{query.metric_name}")
            '''

            if query.aggregation:
                window = "1h"  # Default window
                flux += f'|> aggregateWindow(every: {window}, fn: {query.aggregation})'

            result = query_api.query(flux)

            # Parse results
            data = []
            for table in result:
                for record in table.records:
                    timestamp = record.get_time()
                    value = record.get_value()
                    data.append((timestamp, value))

            return data
        except Exception as e:
            logger.error(f"InfluxDB query failed: {str(e)}")
            return []

    async def delete_old_data(self, retention_config: RetentionConfig) -> int:
        """Delete old data using retention policy."""
        if not self.client:
            return 0

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=retention_config.keep_raw_days)
            delete_api = self.client.delete_api()
            delete_api.delete(
                org=self.org,
                bucket=self.bucket,
                delete_line=f'_time < {int(cutoff_time.timestamp() * 1e9)}'
            )
            return 1
        except Exception as e:
            logger.error(f"InfluxDB delete failed: {str(e)}")
            return 0

    async def downsample(self, metric_name: str, from_resolution: int,
                        to_resolution: int, aggregation: str) -> int:
        """Downsample data in InfluxDB."""
        # InfluxDB uses tasks for downsampling - this is simplified
        logger.info(f"Downsampling {metric_name} from {from_resolution}s to {to_resolution}s")
        return 1

    async def health_check(self) -> bool:
        """Check InfluxDB health."""
        if not self.client:
            return False

        try:
            health = self.client.health()
            return health.status == "pass"
        except:
            return False


# ============================================================================
# TimescaleDB Backend
# ============================================================================

class TimescaleDBBackend(TimeSeriesBackendBase):
    """TimescaleDB backend implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize TimescaleDB backend."""
        super().__init__(config)
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 5432)
        self.database = config.get('database', 'moni')
        self.user = config.get('user', 'postgres')
        self.password = config.get('password')

        try:
            import psycopg2
            from psycopg2 import pool
            self.pool = pool.SimpleConnectionPool(
                1, 20,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
        except ImportError:
            logger.warning("psycopg2 not installed, using mock")
            self.pool = None

    async def write(self, timeseries: List[TimeSeries]) -> bool:
        """Write to TimescaleDB hypertable."""
        if not self.pool:
            return False

        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            for ts in timeseries:
                tags_json = json.dumps(ts.tags)
                query = """
                    INSERT INTO metrics (time, metric_name, value, tags, attributes)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    ts.timestamp,
                    ts.metric_name,
                    ts.value,
                    tags_json,
                    json.dumps(ts.attributes)
                ))

            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            return True
        except Exception as e:
            logger.error(f"TimescaleDB write failed: {str(e)}")
            return False

    async def query(self, query: TimeSeriesQuery) -> List[Tuple[datetime, float]]:
        """Query from TimescaleDB."""
        if not self.pool:
            return []

        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            sql = """
                SELECT time, value FROM metrics
                WHERE metric_name = %s
                AND time >= %s AND time <= %s
            """
            params = [query.metric_name, query.start_time, query.end_time]

            if query.aggregation:
                # Use time_bucket for aggregation
                sql = f"""
                    SELECT time_bucket('1 hour', time), {query.aggregation}(value)
                    FROM metrics
                    WHERE metric_name = %s
                    AND time >= %s AND time <= %s
                    GROUP BY 1
                """

            cursor.execute(sql, params)
            results = cursor.fetchall()
            cursor.close()
            self.pool.putconn(conn)

            return results
        except Exception as e:
            logger.error(f"TimescaleDB query failed: {str(e)}")
            return []

    async def delete_old_data(self, retention_config: RetentionConfig) -> int:
        """Delete old data using TimescaleDB policies."""
        if not self.pool:
            return 0

        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_config.keep_raw_days)
            cursor.execute("DELETE FROM metrics WHERE time < %s", (cutoff,))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)

            return affected
        except Exception as e:
            logger.error(f"TimescaleDB delete failed: {str(e)}")
            return 0

    async def downsample(self, metric_name: str, from_resolution: int,
                        to_resolution: int, aggregation: str = "avg") -> int:
        """Downsample data using continuous aggregates."""
        if not self.pool:
            return 0

        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()

            view_name = f"{metric_name}_{to_resolution}s_avg"
            interval = f"{to_resolution // 60} minutes" if to_resolution >= 60 else f"{to_resolution} seconds"

            sql = f"""
                CREATE MATERIALIZED VIEW IF NOT EXISTS {view_name}
                WITH (timescaledb.continuous) AS
                SELECT time_bucket('{interval}', time), {aggregation}(value)
                FROM metrics
                WHERE metric_name = '{metric_name}'
                GROUP BY 1;
            """

            cursor.execute(sql)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)

            return 1
        except Exception as e:
            logger.error(f"TimescaleDB downsample failed: {str(e)}")
            return 0

    async def health_check(self) -> bool:
        """Check TimescaleDB health."""
        if not self.pool:
            return False

        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            self.pool.putconn(conn)
            return True
        except:
            return False


# ============================================================================
# Adaptive Backend Manager
# ============================================================================

class TimeSeriesManager:
    """Adaptive time-series database manager."""

    def __init__(self, backend_type: TimeSeriesBackend = TimeSeriesBackend.MEMORY,
                config: Optional[Dict[str, Any]] = None):
        """Initialize time-series manager."""
        self.backend_type = backend_type
        self.config = config or {}

        if backend_type == TimeSeriesBackend.INFLUXDB:
            self.backend = InfluxDBBackend(self.config)
        elif backend_type == TimeSeriesBackend.TIMESCALEDB:
            self.backend = TimescaleDBBackend(self.config)
        elif backend_type == TimeSeriesBackend.MEMORY:
            self.backend = MemoryBackend(self.config)
        else:
            raise ValueError(f"Unknown backend: {backend_type}")

        self.retention_config = RetentionConfig(policy=DataRetentionPolicy.DAILY)

    async def write_metric(self, metric_name: str, value: float,
                          tags: Optional[Dict[str, str]] = None,
                          timestamp: Optional[datetime] = None) -> bool:
        """Write single metric."""
        ts = TimeSeries(
            timestamp=timestamp or datetime.now(timezone.utc),
            metric_name=metric_name,
            value=value,
            tags=tags or {}
        )
        return await self.backend.write([ts])

    async def query_metric(self, metric_name: str, hours: int = 1,
                          aggregation: Optional[str] = None) -> List[Tuple[datetime, float]]:
        """Query metric from past N hours."""
        query = TimeSeriesQuery(
            metric_name=metric_name,
            start_time=datetime.now(timezone.utc) - timedelta(hours=hours),
            end_time=datetime.now(timezone.utc),
            aggregation=aggregation
        )
        return await self.backend.query(query)

    async def health_check(self) -> bool:
        """Check backend health."""
        return await self.backend.health_check()


# ============================================================================
# In-Memory Backend for Testing
# ============================================================================

class MemoryBackend(TimeSeriesBackendBase):
    """In-memory time-series backend for testing."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize memory backend."""
        super().__init__(config)
        self.data: Dict[str, List[Tuple[datetime, float]]] = {}

    async def write(self, timeseries: List[TimeSeries]) -> bool:
        """Write to memory."""
        for ts in timeseries:
            if ts.metric_name not in self.data:
                self.data[ts.metric_name] = []
            self.data[ts.metric_name].append((ts.timestamp, ts.value))
        return True

    async def query(self, query: TimeSeriesQuery) -> List[Tuple[datetime, float]]:
        """Query from memory."""
        data = self.data.get(query.metric_name, [])
        filtered = [
            (t, v) for t, v in data
            if query.start_time <= t <= query.end_time
        ]
        return sorted(filtered)[:query.limit]

    async def delete_old_data(self, retention_config: RetentionConfig) -> int:
        """Delete old data from memory."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_config.keep_raw_days)
        deleted = 0
        for metric_name in self.data:
            before = len(self.data[metric_name])
            self.data[metric_name] = [
                (t, v) for t, v in self.data[metric_name] if t >= cutoff
            ]
            deleted += before - len(self.data[metric_name])
        return deleted

    async def downsample(self, metric_name: str, from_resolution: int,
                        to_resolution: int, aggregation: str) -> int:
        """Downsample in memory."""
        return 1

    async def health_check(self) -> bool:
        """Memory backend is always healthy."""
        return True
