#!/usr/bin/env python3
"""
Moni System Monitor - Production Entry Point
Enterprise-grade system monitoring with advanced security and performance features.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from moni.unified_config import unified_config_manager, MoniConfig


logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Setup logging configuration."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=handlers
    )


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="moni",
        description="Professional System Monitor - Enterprise-grade monitoring solution"
    )

    # Operation mode
    parser.add_argument(
        "--mode",
        choices=["gui", "daemon", "export", "validate"],
        default="gui",
        help="Operation mode (default: gui)"
    )

    # Security options
    security_group = parser.add_argument_group("Security")
    security_group.add_argument(
        "--secure",
        action="store_true",
        help="Enable secure configuration mode with encryption"
    )
    security_group.add_argument(
        "--password",
        help="Password for encrypted configuration"
    )
    security_group.add_argument(
        "--security-audit",
        action="store_true",
        help="Run security audit and exit"
    )

    # Performance options
    perf_group = parser.add_argument_group("Performance")
    perf_group.add_argument(
        "--profile",
        choices=["balanced", "low-latency", "high-throughput", "memory-efficient", "power-saving"],
        default="balanced",
        help="Performance profile (default: balanced)"
    )
    perf_group.add_argument(
        "--cache-size",
        type=int,
        default=1000,
        help="Cache size for metrics (default: 1000)"
    )
    perf_group.add_argument(
        "--refresh-interval",
        type=int,
        default=1500,
        help="Refresh interval in milliseconds (default: 1500)"
    )

    # Monitoring options
    mon_group = parser.add_argument_group("Monitoring")
    mon_group.add_argument(
        "--metrics",
        nargs="+",
        help="Specific metrics to monitor"
    )
    mon_group.add_argument(
        "--cpu-threshold",
        type=float,
        default=80.0,
        help="CPU alert threshold percentage (default: 80)"
    )
    mon_group.add_argument(
        "--memory-threshold",
        type=float,
        default=85.0,
        help="Memory alert threshold percentage (default: 85)"
    )
    mon_group.add_argument(
        "--disable-alerts",
        action="store_true",
        help="Disable all alerts"
    )

    # Export options
    export_group = parser.add_argument_group("Export")
    export_group.add_argument(
        "--export-format",
        choices=["json", "csv", "html"],
        default="json",
        help="Export format (default: json)"
    )
    export_group.add_argument(
        "--export-file",
        help="Export file path"
    )
    export_group.add_argument(
        "--export-interval",
        type=int,
        help="Auto-export interval in seconds"
    )

    # Logging options
    log_group = parser.add_argument_group("Logging")
    log_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    log_group.add_argument(
        "--log-file",
        help="Log file path"
    )

    # Configuration
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--config",
        help="Configuration file path"
    )
    config_group.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration to defaults"
    )
    config_group.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit"
    )

    # Other options
    parser.add_argument(
        "--version",
        action="version",
        version="Moni System Monitor v2.0.0"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes"
    )

    return parser


def run_security_audit() -> int:
    """Run comprehensive security audit."""
    separator = "=" * 60
    logger.info(separator)
    logger.info("MONI SECURITY AUDIT")
    logger.info(separator)

    from moni.security_manager import get_security_manager

    try:
        # Load configuration using unified config manager
        unified_config_manager.load_all_configs()

        security = get_security_manager()
        audit_result = security.perform_security_audit()

        logger.info("Security Status: %s", audit_result['security_status'].upper())
        logger.info("Metrics:")
        for key, value in audit_result['metrics'].items():
            logger.info("  %s: %s", key, value)

        if audit_result['recommendations']:
            logger.info("Recommendations:")
            for rec in audit_result['recommendations']:
                logger.info("  - %s", rec)
        else:
            logger.info("No security issues detected.")

        return 0 if audit_result['security_status'] == 'healthy' else 1

    except Exception as error:
        logger.error("Security audit failed", exc_info=True, extra={"error": str(error)})
        return 1


def validate_configuration(config_path: Optional[str] = None) -> int:
    """Validate configuration file."""
    logger.info("Validating configuration...")

    try:
        if config_path:
            path = Path(config_path)
        else:
            path = Path.home() / ".config" / "moni" / "config.json"

        if not path.exists():
            logger.error("Configuration file not found", extra={"path": str(path)})
            return 1

        # Try to load and validate
        config = MoniConfig.load(path)

        # Check for issues
        issues = []

        # Check refresh interval
        if config.overlay.refresh_interval_ms < 100:
            issues.append("Refresh interval too low (< 100ms)")

        # Check thresholds
        if config.automation.alerts.thresholds.cpu_percent > 100:
            issues.append("CPU threshold > 100%")

        if config.automation.alerts.thresholds.memory_percent > 100:
            issues.append("Memory threshold > 100%")

        if issues:
            logger.warning("Validation issues detected:")
            for issue in issues:
                logger.warning("  - %s", issue)
            return 1
        else:
            logger.info("Configuration is valid.")
            return 0

    except Exception as error:
        logger.error("Configuration validation failed", exc_info=True, extra={"error": str(error)})
        return 1


def export_metrics(args: argparse.Namespace) -> int:
    """Export system metrics."""
    logger.info("Exporting metrics", extra={"format": args.export_format})

    try:
        from moni.metrics import DEFAULT_REGISTRY
        from moni.export import MetricExporter

        # Collect current metrics
        metrics = {}
        for metric_id in ["cpu_usage", "memory_usage", "disk_io", "network_io"]:
            try:
                metric = DEFAULT_REGISTRY.get(metric_id)
                data = metric.collect()
                metrics[metric_id] = data
            except:
                pass

        # Export based on format
        output_file = args.export_file or f"metrics.{args.export_format}"
        output_path = Path(output_file)

        if args.export_format == "json":
            output_path.write_text(json.dumps(metrics, indent=2))
        elif args.export_format == "csv":
            # Simple CSV export
            import csv
            with output_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Key", "Value"])
                for metric_id, data in metrics.items():
                    for key, value in data.items():
                        writer.writerow([metric_id, key, value])
        elif args.export_format == "html":
            # Simple HTML export
            html = "<html><head><title>System Metrics</title></head><body>"
            html += "<h1>System Metrics</h1>"
            for metric_id, data in metrics.items():
                html += f"<h2>{metric_id}</h2><ul>"
                for key, value in data.items():
                    html += f"<li><b>{key}:</b> {value}</li>"
                html += "</ul>"
            html += "</body></html>"
            output_path.write_text(html)

        logger.info("Metrics exported", extra={"output": str(output_path)})
        return 0

    except Exception as error:
        logger.error(
            "Metric export failed",
            exc_info=True,
            extra={
                "format": args.export_format,
                "output": str(args.export_file or f"metrics.{args.export_format}"),
            },
        )
        return 1


def run_daemon_mode(args: argparse.Namespace) -> int:
    """Run in daemon/background mode."""
    logger.info("Starting Moni in daemon mode...")

    try:
        # Fork process (Unix only)
        if hasattr(os, 'fork'):
            pid = os.fork()
            if pid > 0:
                logger.info("Daemon started", extra={"pid": pid})
                return 0

        # Continue as daemon
        from moni.application import MoniApplication
        app = MoniApplication(sys.argv)

        # Disable GUI
        app._overlay_window.hide()

        # Start monitoring
        return app.start()

    except Exception as error:
        logger.error("Daemon mode failed", exc_info=True, extra={"error": str(error)})
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.log_file)

    # Handle special modes
    if args.security_audit:
        return run_security_audit()

    if args.validate_config:
        return validate_configuration(args.config)

    if args.reset_config:
        config_path = Path.home() / ".config" / "moni" / "config.json"
        if config_path.exists():
            config_path.unlink()
            logger.info("Configuration reset to defaults", extra={"path": str(config_path)})
        return 0

    # Handle operation modes
    if args.mode == "validate":
        return validate_configuration(args.config)

    if args.mode == "export":
        return export_metrics(args)

    if args.mode == "daemon":
        return run_daemon_mode(args)

    # GUI mode (default)
    try:
        # Load or create configuration using unified config manager
        unified_config_manager.load_all_configs()

        # Apply command-line overrides to unified config
        if args.refresh_interval:
            unified_config_manager.set("overlay.refresh_interval_ms", args.refresh_interval)

        if args.cpu_threshold:
            unified_config_manager.set("automation.alerts.thresholds.cpu_percent", args.cpu_threshold)

        if args.memory_threshold:
            unified_config_manager.set("automation.alerts.thresholds.memory_percent", args.memory_threshold)

        if args.disable_alerts:
            unified_config_manager.set("automation.alerts.enabled", False)

        if args.metrics:
            unified_config_manager.set("metrics", args.metrics)

        # Initialize performance optimizer with profile
        from moni.performance_optimizer import get_optimizer, PerformanceProfile
        profile_map = {
            "balanced": PerformanceProfile.BALANCED,
            "low-latency": PerformanceProfile.LOW_LATENCY,
            "high-throughput": PerformanceProfile.HIGH_THROUGHPUT,
            "memory-efficient": PerformanceProfile.MEMORY_EFFICIENT,
            "power-saving": PerformanceProfile.POWER_SAVING
        }
        optimizer = get_optimizer(profile_map[args.profile])

        # Initialize enhanced security system
        from moni.enhanced_security import security_monitor, advanced_encryptor, rate_limiter, advanced_validator

        # Initialize memory optimization system
        from moni.memory_optimizer import memory_optimizer
        memory_optimizer.start_memory_monitoring(interval_seconds=300)  # 5分間隔
        logger.info("メモリ最適化システムを有効化しました")

        # Initialize CPU optimization system
        from moni.cpu_optimizer import cpu_optimizer
        logger.info("CPU最適化システムを有効化しました")

        # Start application
        app = MoniApplication(sys.argv)
        return app.start()

    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
        return 0
    except Exception as error:
        logging.error("Application failed", exc_info=True, extra={"error": str(error)})
        return 1


if __name__ == "__main__":
    sys.exit(main())