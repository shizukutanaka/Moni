"""Enhanced export functionality for metrics data with multiple formats and scheduling."""

from __future__ import annotations

import csv
import json
import logging
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import threading
import time

from .metrics import MetricHistory, MetricRegistry
from .security import (
    InputValidator, SecureFileHandler, ValidationError,
    rate_limiter, security_logger, MAX_FILE_SIZE
)

logger = logging.getLogger(__name__)


@dataclass
class ExportFormat:
    """Configuration for export format options."""
    name: str
    extension: str
    description: str
    export_function: Callable


class MetricExporter:
    """Enhanced metric exporter with multiple format support and scheduling."""

    def __init__(self, history: MetricHistory, registry: MetricRegistry, base_export_dir: Optional[Path] = None):
        self.history = history
        self.registry = registry
        self.scheduled_exports: Dict[str, Dict] = {}
        self.export_thread: Optional[threading.Thread] = None
        self._scheduler_lock = threading.RLock()
        self._stop_event = threading.Event()

        # Set up secure file handler
        if base_export_dir is None:
            from .config import DEFAULT_CONFIG_DIR
            base_export_dir = DEFAULT_CONFIG_DIR / "exports"

        self.file_handler = SecureFileHandler(base_export_dir)
        self.base_export_dir = base_export_dir

        # Define available export formats
        self.formats = {
            'json': ExportFormat(
                name='JSON',
                extension='json',
                description='JSON format with full metadata',
                export_function=self._export_json
            ),
            'csv': ExportFormat(
                name='CSV',
                extension='csv',
                description='CSV format for spreadsheet analysis',
                export_function=self._export_csv
            ),
            'detailed_json': ExportFormat(
                name='Detailed JSON',
                extension='json',
                description='JSON with metric descriptions and metadata',
                export_function=self._export_detailed_json
            ),
            'summary_json': ExportFormat(
                name='Summary JSON',
                extension='json',
                description='Condensed JSON with latest values only',
                export_function=self._export_summary_json
            )
        }

    def _resolve_export_path(self, file_path: Path | str, format_type: str) -> Path:
        """Resolve and validate export destinations within the exporter sandbox."""

        expected_extension = f".{self.formats[format_type].extension.lower()}"

        candidate = Path(file_path) if not isinstance(file_path, Path) else file_path
        if not candidate.is_absolute():
            candidate = self.base_export_dir / candidate

        candidate = candidate.resolve(strict=False)

        if candidate.suffix.lower() != expected_extension:
            raise ValidationError(
                f"Export path extension '{candidate.suffix}' does not match required "
                f"'{expected_extension}' for format '{format_type}'"
            )
        return InputValidator.validate_file_path(candidate, self.base_export_dir)

    def _write_text_with_limit(self, target: Path, content: str) -> bool:
        payload_size = len(content.encode("utf-8"))
        if payload_size > MAX_FILE_SIZE:
            logger.error(
                "Export payload exceeds size limit",
                extra={"path": str(target), "bytes": payload_size, "limit": MAX_FILE_SIZE},
            )
            return False
        return self.file_handler.write_file(target, content, MAX_FILE_SIZE)

    @staticmethod
    def _serialize_json(payload: Any, pretty: bool = False) -> str:
        if pretty:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _write_csv_stream(self, target: Path, rows: Iterable[List[str]]) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_suffix(target.suffix + '.tmp')

        class _CountingWriter:
            def __init__(self, wrapped: Any, size_limit: int) -> None:
                self.wrapped = wrapped
                self.size_limit = size_limit
                self.bytes_written = 0

            def write(self, data: str) -> int:
                encoded = data.encode('utf-8')
                self.bytes_written += len(encoded)
                if self.bytes_written > self.size_limit:
                    raise ValidationError(
                        f"CSV export exceeds size limit ({self.bytes_written} > {self.size_limit})"
                    )
                return self.wrapped.write(data)

        try:
            with temp_path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(_CountingWriter(handle, MAX_FILE_SIZE))
                for row in rows:
                    writer.writerow(row)
            temp_path.replace(target)
            return True
        except ValidationError as exc:
            logger.error("CSV export aborted due to size limit", extra={"path": str(target), "error": str(exc)})
        except Exception as exc:
            logger.error("CSV export failed", exc_info=True, extra={"path": str(target), "error": str(exc)})
        finally:
            if temp_path.exists():
                with suppress(OSError):
                    temp_path.unlink()
        return False

    def export_metrics(
        self,
        file_path: Path | str,
        format_type: str = 'json',
        metric_filter: Optional[List[str]] = None,
        time_range: Optional[tuple[Optional[int], Optional[int]]] = None
    ) -> bool:
        """Export metrics data in the specified format."""
        try:
            # Rate limiting for exports
            rate_limit_key = f"export_metrics:{format_type}"
            if not rate_limiter.is_allowed(rate_limit_key, limit=10, window=300):  # Max 10 exports per 5 minutes
                logger.warning("Rate limit exceeded for metrics export")
                security_logger.log_rate_limit_exceeded("export_metrics", "metrics_export")
                return False

            # Validate format type
            if format_type not in self.formats:
                raise ValidationError(f"Unsupported format: {format_type}")

            secure_path = self._resolve_export_path(file_path, format_type)

            # Validate metric filter
            if metric_filter:
                validated_metrics = []
                for metric in metric_filter:
                    if not InputValidator.PATTERNS['metric_id'].match(metric):
                        logger.warning(f"Invalid metric ID in filter: {metric}")
                        continue
                    validated_metrics.append(metric)
                metric_filter = validated_metrics

            # Validate time range
            if time_range:
                start_time, end_time = time_range
                if start_time is not None and not isinstance(start_time, int):
                    raise ValidationError("Invalid start time format")
                if end_time is not None and not isinstance(end_time, int):
                    raise ValidationError("Invalid end time format")
                if start_time and end_time and start_time > end_time:
                    raise ValidationError("Start time cannot be after end time")

            export_func = self.formats[format_type].export_function
            result = export_func(secure_path, metric_filter, time_range)

            if result:
                security_logger.log_security_event(
                    'METRICS_EXPORTED',
                    {
                        'file_path': str(secure_path),
                        'format': format_type,
                        'metric_count': len(metric_filter) if metric_filter else 'all'
                    }
                )

            return result

        except Exception as e:
            logger.error(
                "Export failed",
                exc_info=True,
                extra={"file_path": str(file_path), "format": format_type},
            )
            security_logger.log_security_event(
                'EXPORT_FAILED',
                {
                    'error': str(e),
                    'file_path': str(file_path),
                    'format': format_type
                },
                'WARNING'
            )
            return False

    def _export_json(
        self,
        file_path: Path,
        metric_filter: Optional[List[str]] = None,
        time_range: Optional[tuple[Optional[int], Optional[int]]] = None
    ) -> bool:
        """Export metrics as standard JSON format."""
        try:
            # Validate and secure the file path
            secure_path = InputValidator.validate_file_path(file_path, self.base_export_dir)

            if time_range:
                start_time, end_time = time_range
                data = self.history.get_data_range(start_time, end_time)
            else:
                data = self.history.get_data_range()

            if metric_filter:
                data = {k: v for k, v in data.items() if k in metric_filter}

            export_payload = {
                "export_timestamp": int(time.time() * 1000),
                "export_format": "json",
                "total_metrics": len(data),
                "metrics": data,
                "metadata": {
                    "exporter_version": "1.0",
                    "source": "Moni System Monitor"
                }
            }

            # Use secure file writing
            serialized_data = self._serialize_json(export_payload, pretty=True)
            return self._write_text_with_limit(secure_path, serialized_data)
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    def _export_csv(
        self,
        file_path: Path,
        metric_filter: Optional[List[str]] = None,
        time_range: Optional[tuple[Optional[int], Optional[int]]] = None
    ) -> bool:
        """Export metrics as CSV format for spreadsheet analysis."""
        try:
            # Validate and secure the file path
            secure_path = InputValidator.validate_file_path(file_path, self.base_export_dir)

            if time_range:
                start_time, end_time = time_range
                data = self.history.get_data_range(start_time, end_time)
            else:
                data = self.history.get_data_range()

            if metric_filter:
                data = {k: v for k, v in data.items() if k in metric_filter}

            if not data:
                return False

            # Get all timestamps from the first metric
            first_metric = next(iter(data.values()))
            timestamps = first_metric.get('timestamps', [])

            def row_generator() -> Iterable[List[str]]:
                header = ['timestamp', 'datetime']
                for metric_id in data.keys():
                    header.extend([f"{metric_id}_key", f"{metric_id}_value"])
                yield header

                for i, timestamp in enumerate(timestamps):
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    row: List[str] = [str(timestamp), dt.isoformat()]

                    for metric_id, metric_data in data.items():
                        values = metric_data.get('values', [])
                        if i < len(values) and values[i]:
                            value_dict = values[i]
                            if isinstance(value_dict, dict):
                                first_key, first_value = next(iter(value_dict.items())) if value_dict else ('', '')
                                row.extend([first_key, str(first_value)])
                            else:
                                row.extend(['', str(value_dict)])
                        else:
                            row.extend(['', ''])

                    yield row

            return self._write_csv_stream(secure_path, row_generator())
        except Exception as e:
            logger.error("CSV export failed", exc_info=True, extra={'export_path': str(secure_path)})
            return False

    def _export_detailed_json(
        self,
        file_path: Path,
        metric_filter: Optional[List[str]] = None,
        time_range: Optional[tuple[Optional[int], Optional[int]]] = None
    ) -> bool:
        """Export metrics with full metadata and descriptions."""
        try:
            # Validate and secure the file path
            secure_path = InputValidator.validate_file_path(file_path, self.base_export_dir)

            if time_range:
                start_time, end_time = time_range
                data = self.history.get_data_range(start_time, end_time)
            else:
                data = self.history.get_data_range()

            if metric_filter:
                data = {k: v for k, v in data.items() if k in metric_filter}

            # Add metric metadata
            detailed_data = {}
            for metric_id, metric_data in data.items():
                if metric_id in self.registry:
                    metric = self.registry.get(metric_id)
                    detailed_data[metric_id] = {
                        "name": metric.name,
                        "description": metric.description,
                        "identifier": metric.identifier,
                        "data": metric_data,
                        "sample_count": len(metric_data.get('values', [])),
                        "time_range": {
                            "start": min(metric_data.get('timestamps', [])) if metric_data.get('timestamps') else None,
                            "end": max(metric_data.get('timestamps', [])) if metric_data.get('timestamps') else None
                        }
                    }
                else:
                    detailed_data[metric_id] = {
                        "name": metric_id,
                        "description": "Unknown metric",
                        "identifier": metric_id,
                        "data": metric_data
                    }

            export_payload = {
                "export_timestamp": int(time.time() * 1000),
                "export_format": "detailed_json",
                "total_metrics": len(detailed_data),
                "metrics": detailed_data,
                "metadata": {
                    "exporter_version": "1.0",
                    "source": "Moni System Monitor",
                    "export_type": "detailed_with_metadata"
                }
            }

            # Use secure file writing
            serialized_data = self._serialize_json(export_payload, pretty=True)
            return self._write_text_with_limit(secure_path, serialized_data)
        except Exception as e:
            logger.error(f"Detailed JSON export failed: {e}")
            return False

    def _export_summary_json(
        self,
        file_path: Path,
        metric_filter: Optional[List[str]] = None,
        time_range: Optional[tuple[Optional[int], Optional[int]]] = None
    ) -> bool:
        """Export condensed summary with latest values only."""
        try:
            # Validate and secure the file path
            secure_path = InputValidator.validate_file_path(file_path, self.base_export_dir)

            # Get current metrics data
            current_data = {}
            for metric_id in self.registry._metrics.keys():
                if metric_filter and metric_id not in metric_filter:
                    continue

                try:
                    metric_data = self.registry.collect_metric(metric_id)
                    if metric_id in self.registry:
                        metric = self.registry.get(metric_id)
                        current_data[metric_id] = {
                            "name": metric.name,
                            "current_values": metric_data,
                            "timestamp": int(time.time() * 1000)
                        }
                except Exception:
                    continue

            export_payload = {
                "export_timestamp": int(time.time() * 1000),
                "export_format": "summary_json",
                "total_metrics": len(current_data),
                "current_metrics": current_data,
                "metadata": {
                    "exporter_version": "1.0",
                    "source": "Moni System Monitor",
                    "export_type": "current_values_summary"
                }
            }

            # Use secure file writing
            serialized_data = self._serialize_json(export_payload)
            return self._write_text_with_limit(secure_path, serialized_data)
        except Exception as e:
            logger.error(f"Summary JSON export failed: {e}")
            return False

    def schedule_export(
        self,
        schedule_id: str,
        file_pattern: str,
        format_type: str = 'json',
        interval_minutes: int = 60,
        metric_filter: Optional[List[str]] = None
    ) -> bool:
        """Schedule periodic exports."""
        try:
            if format_type not in self.formats:
                return False

            # Validate pattern immediately to surface issues early
            sample_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                sample_path = file_pattern.format(timestamp=sample_timestamp)
                self._resolve_export_path(sample_path, format_type)
            except (KeyError, IndexError, ValueError, ValidationError) as exc:
                logger.error(
                    "Invalid file pattern for scheduled export",
                    exc_info=True,
                    extra={"schedule_id": schedule_id, "file_pattern": file_pattern, "error": str(exc)},
                )
                return False

            if interval_minutes <= 0:
                logger.error(
                    "Invalid interval for scheduled export",
                    extra={"schedule_id": schedule_id, "interval_minutes": interval_minutes},
                )
                return False

            next_export_time = time.time() + (interval_minutes * 60)

            with self._scheduler_lock:
                self.scheduled_exports[schedule_id] = {
                    'file_pattern': file_pattern,
                    'format_type': format_type,
                    'interval_minutes': interval_minutes,
                    'metric_filter': metric_filter,
                    'next_export': next_export_time,
                    'last_export': None
                }

                self._stop_event.clear()

                if not self.export_thread or not self.export_thread.is_alive():
                    self.export_thread = threading.Thread(target=self._export_scheduler_loop, daemon=True)
                    self.export_thread.start()

            return True
        except Exception as e:
            logger.error(
                "Failed to schedule export",
                exc_info=True,
                extra={'schedule_id': schedule_id, 'file_pattern': file_pattern, 'format_type': format_type},
            )
            return False

    def unschedule_export(self, schedule_id: str) -> bool:
        """Remove a scheduled export."""
        removed = False
        should_stop = False

        with self._scheduler_lock:
            if schedule_id in self.scheduled_exports:
                del self.scheduled_exports[schedule_id]
                removed = True
                should_stop = not self.scheduled_exports

        if should_stop:
            self.stop_scheduler()

        return removed

    def _export_scheduler_loop(self):
        """Background thread for scheduled exports."""
        try:
            while not self._stop_event.is_set():
                current_time = time.time()
                due_exports: List[tuple[str, Dict[str, Any]]] = []

                with self._scheduler_lock:
                    for schedule_id, config in self.scheduled_exports.items():
                        if current_time >= config['next_export']:
                            due_exports.append((schedule_id, dict(config)))

                for schedule_id, config_snapshot in due_exports:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    try:
                        formatted_path = config_snapshot['file_pattern'].format(timestamp=timestamp)
                        success = self.export_metrics(
                            formatted_path,
                            format_type=config_snapshot['format_type'],
                            metric_filter=config_snapshot.get('metric_filter')
                        )
                    except Exception as exc:
                        logger.error(
                            "Scheduled export failed", 
                            exc_info=True,
                            extra={"schedule_id": schedule_id, "error": str(exc)},
                        )
                        success = False

                    next_target = time.time() + (config_snapshot['interval_minutes'] * 60 if success else 300)

                    with self._scheduler_lock:
                        if schedule_id not in self.scheduled_exports:
                            continue
                        config_ref = self.scheduled_exports[schedule_id]
                        config_ref['next_export'] = next_target
                        if success:
                            config_ref['last_export'] = time.time()
                            logger.info(
                                "Scheduled export completed",
                                extra={
                                    "schedule_id": schedule_id,
                                    "file_pattern": config_ref['file_pattern'],
                                    "timestamp": timestamp,
                                },
                            )

                with self._scheduler_lock:
                    if not self.scheduled_exports:
                        if not self._stop_event.is_set():
                            self._stop_event.set()
                        continue
                    upcoming = min(config['next_export'] for config in self.scheduled_exports.values())

                wait_seconds = max(1, min(30, upcoming - time.time()))
                if self._stop_event.wait(wait_seconds):
                    break
        finally:
            with self._scheduler_lock:
                self.export_thread = None

    def stop_scheduler(self):
        """Stop the export scheduler thread."""
        self._stop_event.set()

        thread: Optional[threading.Thread]
        with self._scheduler_lock:
            thread = self.export_thread

        if thread and thread.is_alive():
            thread.join(timeout=1)

        with self._scheduler_lock:
            self.export_thread = None

    def get_export_status(self) -> Dict[str, Any]:
        """Get status of all scheduled exports."""
        status = {
            'scheduled_exports': len(self.scheduled_exports),
            'scheduler_running': self.export_thread and self.export_thread.is_alive(),
            'exports': {}
        }

        current_time = time.time()
        for schedule_id, config in self.scheduled_exports.items():
            next_export_in = max(0, config['next_export'] - current_time)
            last_export_ago = None
            if config['last_export']:
                last_export_ago = current_time - config['last_export']

            status['exports'][schedule_id] = {
                'format': config['format_type'],
                'interval_minutes': config['interval_minutes'],
                'next_export_in_seconds': int(next_export_in),
                'last_export_ago_seconds': int(last_export_ago) if last_export_ago else None,
                'file_pattern': config['file_pattern']
            }

        return status