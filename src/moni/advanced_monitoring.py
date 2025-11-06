"""
Advanced monitoring and alerting system for enterprise-grade system oversight.
Implements AI-powered anomaly detection, predictive analytics, and intelligent alerting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats
import smtplib
import ssl
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

from .security import rate_limiter, security_logger
from .performance import performance_tracker

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    SNMP = "snmp"
    SYSLOG = "syslog"


@dataclass
class MetricPoint:
    """Single metric measurement point."""
    timestamp: float
    value: float
    tags: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class Alert:
    """Alert definition and state."""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    condition: str
    threshold: float
    duration_seconds: int
    enabled: bool
    channels: List[AlertChannel]
    created_at: float
    triggered_at: Optional[float] = None
    resolved_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    count: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AnomalyDetector:
    """AI-powered anomaly detection using statistical methods."""

    def __init__(self, sensitivity: float = 2.5, window_size: int = 100):
        self.sensitivity = sensitivity  # Standard deviations for anomaly threshold
        self.window_size = window_size
        self.metric_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.anomaly_scores: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))

    def add_measurement(self, metric_name: str, point: MetricPoint) -> float:
        """Add measurement and return anomaly score (0-1, higher = more anomalous)."""
        buffer = self.metric_buffers[metric_name]
        buffer.append(point.value)

        if len(buffer) < 10:  # Need minimum data for analysis
            return 0.0

        # Calculate baseline statistics
        values = list(buffer)
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0

        # Calculate anomaly score using z-score
        if stdev > 0:
            z_score = abs(point.value - mean) / stdev
            anomaly_score = min(z_score / self.sensitivity, 1.0)
        else:
            anomaly_score = 0.0

        # Store anomaly score
        self.anomaly_scores[metric_name].append(anomaly_score)

        # Update baseline
        self.baselines[metric_name] = {
            'mean': mean,
            'stdev': stdev,
            'min': min(values),
            'max': max(values),
            'percentile_95': np.percentile(values, 95),
            'percentile_99': np.percentile(values, 99)
        }

        return anomaly_score

    def get_prediction(self, metric_name: str, horizon_minutes: int = 30) -> Optional[Dict[str, float]]:
        """Predict future metric values using linear regression."""
        buffer = self.metric_buffers[metric_name]
        if len(buffer) < 20:  # Need sufficient data for prediction
            return None

        # Prepare data for regression
        values = list(buffer)
        timestamps = list(range(len(values)))

        try:
            # Perform linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, values)

            # Predict future value
            future_timestamp = len(values) + (horizon_minutes * 60 / 300)  # Assuming 5-minute intervals
            predicted_value = slope * future_timestamp + intercept

            # Calculate confidence interval
            confidence_interval = 1.96 * std_err * np.sqrt(1 + 1/len(values))

            return {
                'predicted_value': predicted_value,
                'confidence_lower': predicted_value - confidence_interval,
                'confidence_upper': predicted_value + confidence_interval,
                'r_squared': r_value ** 2,
                'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
            }
        except Exception as e:
            logger.error(f"Prediction failed for {metric_name}: {e}")
            return None

    def detect_seasonal_patterns(self, metric_name: str) -> Dict[str, Any]:
        """Detect seasonal patterns in metric data."""
        buffer = self.metric_buffers[metric_name]
        if len(buffer) < 50:
            return {}

        values = np.array(list(buffer))

        try:
            # Simple seasonal decomposition
            # For more advanced analysis, could use statsmodels.tsa.seasonal_decompose
            trend = np.convolve(values, np.ones(7)/7, mode='same')  # 7-point moving average
            seasonal = values - trend
            residual = values - trend - seasonal

            return {
                'has_trend': abs(np.corrcoef(range(len(trend)), trend)[0, 1]) > 0.5,
                'seasonality_strength': np.std(seasonal) / np.std(values),
                'noise_level': np.std(residual) / np.std(values),
                'dominant_frequency': self._find_dominant_frequency(seasonal)
            }
        except Exception as e:
            logger.error(f"Seasonal analysis failed for {metric_name}: {e}")
            return {}

    def _find_dominant_frequency(self, signal: np.ndarray) -> Optional[float]:
        """Find dominant frequency in signal using FFT."""
        try:
            fft = np.fft.fft(signal)
            freqs = np.fft.fftfreq(len(signal))
            magnitude = np.abs(fft)

            # Find peak frequency (excluding DC component)
            peak_idx = np.argmax(magnitude[1:len(magnitude)//2]) + 1
            return freqs[peak_idx]
        except Exception:
            return None


class IntelligentAlerting:
    """Intelligent alerting system with correlation and suppression."""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.suppression_rules: List[Dict[str, Any]] = []
        self.escalation_policies: Dict[str, Dict[str, Any]] = {}
        self.notification_channels: Dict[AlertChannel, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def add_alert(self, alert: Alert) -> None:
        """Add or update alert definition."""
        with self._lock:
            self.alerts[alert.id] = alert
            logger.info(f"Added alert: {alert.name} ({alert.id})")

    def evaluate_alerts(self, metric_name: str, current_value: float,
                       anomaly_score: float) -> List[Alert]:
        """Evaluate all alerts for a metric and return triggered alerts."""
        triggered_alerts = []

        with self._lock:
            for alert in self.alerts.values():
                if not alert.enabled or alert.metric_name != metric_name:
                    continue

                if self._evaluate_alert_condition(alert, current_value, anomaly_score):
                    if alert.triggered_at is None:
                        alert.triggered_at = time.time()
                        alert.count += 1
                        triggered_alerts.append(alert)

                        # Log alert trigger
                        self.alert_history.append({
                            'timestamp': alert.triggered_at,
                            'alert_id': alert.id,
                            'alert_name': alert.name,
                            'severity': alert.severity.value,
                            'metric': metric_name,
                            'value': current_value,
                            'anomaly_score': anomaly_score,
                            'action': 'triggered'
                        })

                        logger.warning(
                            f"Alert triggered: {alert.name} - {metric_name}={current_value}, "
                            f"threshold={alert.threshold}, severity={alert.severity.value}"
                        )
                else:
                    if alert.triggered_at is not None:
                        # Alert resolved
                        alert.resolved_at = time.time()
                        alert.triggered_at = None

                        self.alert_history.append({
                            'timestamp': alert.resolved_at,
                            'alert_id': alert.id,
                            'alert_name': alert.name,
                            'severity': alert.severity.value,
                            'metric': metric_name,
                            'value': current_value,
                            'action': 'resolved'
                        })

                        logger.info(f"Alert resolved: {alert.name}")

        return triggered_alerts

    def _evaluate_alert_condition(self, alert: Alert, current_value: float,
                                anomaly_score: float) -> bool:
        """Evaluate if alert condition is met."""
        try:
            condition = alert.condition.lower()

            if condition == "greater_than" or condition == ">":
                return current_value > alert.threshold
            elif condition == "less_than" or condition == "<":
                return current_value < alert.threshold
            elif condition == "equals" or condition == "==":
                return abs(current_value - alert.threshold) < 0.001
            elif condition == "anomaly":
                return anomaly_score > alert.threshold
            elif condition == "change_rate":
                # Rate of change evaluation would need historical context
                return False
            else:
                logger.error(f"Unknown alert condition: {condition}")
                return False

        except Exception as e:
            logger.error(f"Error evaluating alert condition for {alert.name}: {e}")
            return False

    def correlate_alerts(self, alerts: List[Alert]) -> List[List[Alert]]:
        """Group related alerts to reduce noise."""
        if not alerts:
            return []

        # Simple correlation by time window and severity
        correlated_groups = []
        time_window = 300  # 5 minutes

        for alert in alerts:
            placed = False
            for group in correlated_groups:
                if any(abs(alert.triggered_at - a.triggered_at) < time_window for a in group):
                    group.append(alert)
                    placed = True
                    break

            if not placed:
                correlated_groups.append([alert])

        return correlated_groups

    def should_suppress_alert(self, alert: Alert) -> bool:
        """Check if alert should be suppressed based on rules."""
        current_time = time.time()

        # Check maintenance windows
        for rule in self.suppression_rules:
            if rule.get('type') == 'maintenance_window':
                start_time = rule.get('start_time', 0)
                end_time = rule.get('end_time', 0)
                if start_time <= current_time <= end_time:
                    affected_alerts = rule.get('alerts', [])
                    if not affected_alerts or alert.id in affected_alerts:
                        return True

        # Check rate limiting
        recent_alerts = [
            h for h in self.alert_history
            if h['alert_id'] == alert.id and current_time - h['timestamp'] < 3600
        ]

        if len(recent_alerts) > 10:  # More than 10 alerts in last hour
            return True

        return False


class NotificationManager:
    """Manages delivery of notifications across multiple channels."""

    def __init__(self):
        self.channels: Dict[AlertChannel, Any] = {}
        self.delivery_queue = asyncio.Queue()
        self.retry_queue = asyncio.Queue()
        self.delivery_stats = defaultdict(int)

    def configure_email(self, smtp_server: str, port: int, username: str,
                       password: str, use_tls: bool = True) -> None:
        """Configure email notification channel."""
        self.channels[AlertChannel.EMAIL] = {
            'smtp_server': smtp_server,
            'port': port,
            'username': username,
            'password': password,
            'use_tls': use_tls
        }

    def configure_webhook(self, url: str, headers: Optional[Dict[str, str]] = None,
                         timeout: int = 30) -> None:
        """Configure webhook notification channel."""
        self.channels[AlertChannel.WEBHOOK] = {
            'url': url,
            'headers': headers or {},
            'timeout': timeout
        }

    async def send_notification(self, alert: Alert, message: str,
                              channels: Optional[List[AlertChannel]] = None) -> Dict[AlertChannel, bool]:
        """Send notification to specified channels."""
        if channels is None:
            channels = alert.channels

        results = {}

        for channel in channels:
            try:
                if channel not in self.channels:
                    logger.error(f"Channel {channel.value} not configured")
                    results[channel] = False
                    continue

                success = await self._send_to_channel(channel, alert, message)
                results[channel] = success
                self.delivery_stats[f"{channel.value}_{'success' if success else 'failure'}"] += 1

            except Exception as e:
                logger.error(f"Failed to send notification via {channel.value}: {e}")
                results[channel] = False
                self.delivery_stats[f"{channel.value}_failure"] += 1

        return results

    async def _send_to_channel(self, channel: AlertChannel, alert: Alert,
                             message: str) -> bool:
        """Send notification to specific channel."""
        config = self.channels[channel]

        if channel == AlertChannel.EMAIL:
            return await self._send_email(config, alert, message)
        elif channel == AlertChannel.WEBHOOK:
            return await self._send_webhook(config, alert, message)
        elif channel == AlertChannel.SLACK:
            return await self._send_slack(config, alert, message)
        elif channel == AlertChannel.TEAMS:
            return await self._send_teams(config, alert, message)
        else:
            logger.error(f"Unsupported notification channel: {channel.value}")
            return False

    async def _send_email(self, config: Dict[str, Any], alert: Alert,
                         message: str) -> bool:
        """Send email notification."""
        try:
            # Create message
            msg = MimeMultipart()
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.name}"
            msg['From'] = config['username']
            msg['To'] = config.get('recipients', config['username'])

            # Create HTML content
            html_content = self._create_email_html(alert, message)
            msg.attach(MimeText(html_content, 'html'))

            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(config['smtp_server'], config['port']) as server:
                if config.get('use_tls', True):
                    server.starttls(context=context)
                server.login(config['username'], config['password'])
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False

    async def _send_webhook(self, config: Dict[str, Any], alert: Alert,
                          message: str) -> bool:
        """Send webhook notification."""
        import aiohttp

        try:
            payload = {
                'alert_id': alert.id,
                'alert_name': alert.name,
                'severity': alert.severity.value,
                'metric': alert.metric_name,
                'threshold': alert.threshold,
                'condition': alert.condition,
                'message': message,
                'triggered_at': alert.triggered_at,
                'timestamp': time.time()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config['url'],
                    json=payload,
                    headers=config.get('headers', {}),
                    timeout=config.get('timeout', 30)
                ) as response:
                    return response.status < 400

        except Exception as e:
            logger.error(f"Webhook sending failed: {e}")
            return False

    async def _send_slack(self, config: Dict[str, Any], alert: Alert,
                         message: str) -> bool:
        """Send Slack notification."""
        # Implement Slack API integration
        return await self._send_webhook(config, alert, message)

    async def _send_teams(self, config: Dict[str, Any], alert: Alert,
                         message: str) -> bool:
        """Send Microsoft Teams notification."""
        # Implement Teams webhook integration
        return await self._send_webhook(config, alert, message)

    def _create_email_html(self, alert: Alert, message: str) -> str:
        """Create HTML email content."""
        severity_colors = {
            AlertSeverity.LOW: "#28a745",
            AlertSeverity.MEDIUM: "#ffc107",
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545",
            AlertSeverity.EMERGENCY: "#6f42c1"
        }

        color = severity_colors.get(alert.severity, "#6c757d")

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
            <div style="border-left: 5px solid {color}; padding-left: 20px;">
                <h2 style="color: {color}; margin-top: 0;">
                    {alert.severity.value.upper()} Alert: {alert.name}
                </h2>
                <p><strong>Description:</strong> {alert.description}</p>
                <p><strong>Metric:</strong> {alert.metric_name}</p>
                <p><strong>Condition:</strong> {alert.condition} {alert.threshold}</p>
                <p><strong>Triggered:</strong> {datetime.fromtimestamp(alert.triggered_at).isoformat()}</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Details</h3>
                    <p>{message}</p>
                </div>
                <p style="color: #6c757d; font-size: 0.9em;">
                    Alert ID: {alert.id}<br>
                    Generated by Moni Professional System Monitor
                </p>
            </div>
        </body>
        </html>
        """


class AdvancedMonitoringSystem:
    """Main advanced monitoring system coordinating all components."""

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.alerting_system = IntelligentAlerting()
        self.notification_manager = NotificationManager()
        self.metric_store: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.running = False
        self._monitoring_task: Optional[asyncio.Task] = None

    def add_metric_point(self, metric_name: str, value: float,
                        tags: Optional[Dict[str, str]] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a metric measurement point."""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )

        # Store metric
        self.metric_store[metric_name].append(point)

        # Detect anomalies
        anomaly_score = self.anomaly_detector.add_measurement(metric_name, point)

        # Evaluate alerts
        triggered_alerts = self.alerting_system.evaluate_alerts(
            metric_name, value, anomaly_score
        )

        # Send notifications for triggered alerts
        if triggered_alerts:
            asyncio.create_task(self._process_triggered_alerts(triggered_alerts, point))

        # Track performance
        performance_tracker.track_metric(f"monitoring_{metric_name}", value)

    async def _process_triggered_alerts(self, alerts: List[Alert],
                                      metric_point: MetricPoint) -> None:
        """Process triggered alerts and send notifications."""
        # Correlate alerts to reduce noise
        alert_groups = self.alerting_system.correlate_alerts(alerts)

        for group in alert_groups:
            for alert in group:
                # Check suppression rules
                if self.alerting_system.should_suppress_alert(alert):
                    continue

                # Create notification message
                message = self._create_alert_message(alert, metric_point)

                # Send notifications
                await self.notification_manager.send_notification(alert, message)

    def _create_alert_message(self, alert: Alert, metric_point: MetricPoint) -> str:
        """Create alert notification message."""
        return (
            f"Alert '{alert.name}' has been triggered.\n\n"
            f"Metric: {alert.metric_name}\n"
            f"Current Value: {metric_point.value}\n"
            f"Threshold: {alert.threshold}\n"
            f"Condition: {alert.condition}\n"
            f"Severity: {alert.severity.value}\n"
            f"Time: {datetime.fromtimestamp(metric_point.timestamp).isoformat()}\n\n"
            f"Description: {alert.description}"
        )

    def get_system_health_score(self) -> Dict[str, Any]:
        """Calculate overall system health score."""
        current_time = time.time()
        health_score = 100.0
        issues = []

        # Check for active critical alerts
        critical_alerts = [
            alert for alert in self.alerting_system.alerts.values()
            if alert.triggered_at and alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
        ]

        if critical_alerts:
            health_score -= len(critical_alerts) * 20
            issues.extend([f"Critical alert: {alert.name}" for alert in critical_alerts])

        # Check anomaly levels
        recent_anomalies = []
        for metric_name, scores in self.anomaly_detector.anomaly_scores.items():
            if scores and scores[-1] > 0.8:  # High anomaly score
                recent_anomalies.append(metric_name)
                health_score -= 10

        if recent_anomalies:
            issues.append(f"High anomaly scores: {', '.join(recent_anomalies)}")

        # Check monitoring system health
        monitoring_metrics = [
            'cpu_usage', 'memory_usage', 'disk_usage', 'network_latency'
        ]

        healthy_metrics = 0
        for metric in monitoring_metrics:
            if metric in self.metric_store and self.metric_store[metric]:
                recent_point = self.metric_store[metric][-1]
                if current_time - recent_point.timestamp < 300:  # Updated within 5 minutes
                    healthy_metrics += 1

        metric_health_ratio = healthy_metrics / len(monitoring_metrics)
        health_score *= metric_health_ratio

        if metric_health_ratio < 0.8:
            issues.append(f"Stale metrics detected ({healthy_metrics}/{len(monitoring_metrics)} healthy)")

        return {
            'health_score': max(0, health_score),
            'status': 'healthy' if health_score > 80 else 'degraded' if health_score > 50 else 'critical',
            'issues': issues,
            'metrics_count': len(self.metric_store),
            'active_alerts': len([a for a in self.alerting_system.alerts.values() if a.triggered_at]),
            'timestamp': current_time
        }

    def export_monitoring_data(self, start_time: Optional[float] = None,
                             end_time: Optional[float] = None) -> Dict[str, Any]:
        """Export monitoring data for analysis or backup."""
        if end_time is None:
            end_time = time.time()
        if start_time is None:
            start_time = end_time - 86400  # Last 24 hours

        export_data = {
            'export_timestamp': time.time(),
            'time_range': {'start': start_time, 'end': end_time},
            'metrics': {},
            'alerts': {},
            'anomalies': {},
            'baselines': {}
        }

        # Export metric data
        for metric_name, points in self.metric_store.items():
            filtered_points = [
                asdict(point) for point in points
                if start_time <= point.timestamp <= end_time
            ]
            if filtered_points:
                export_data['metrics'][metric_name] = filtered_points

        # Export alert definitions and history
        export_data['alerts'] = {
            alert_id: asdict(alert) for alert_id, alert in self.alerting_system.alerts.items()
        }

        # Export anomaly detection data
        for metric_name, scores in self.anomaly_detector.anomaly_scores.items():
            if scores:
                export_data['anomalies'][metric_name] = list(scores)

        # Export baselines
        export_data['baselines'] = self.anomaly_detector.baselines.copy()

        return export_data


# Global advanced monitoring system instance
monitoring_system = AdvancedMonitoringSystem()