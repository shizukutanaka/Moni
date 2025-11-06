from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from pydantic import ValidationError

from .secure_config import SecureConfigManager
from .unified_config import MoniConfig


def _resolve_config_dir() -> Path:
    env_value = os.environ.get("MONI_CONFIG_DIR")
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".config" / "moni"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moni-config",
        description="Secure configuration utility for Moni System Monitor",
    )

    default_config_dir = _resolve_config_dir()

    parser.add_argument(
        "--config-path",
        type=Path,
        default=default_config_dir / "config.json",
        help="Path to the encrypted Moni configuration file",
    )
    parser.add_argument(
        "--key-path",
        type=Path,
        help="Path to the encryption key file (defaults to <config-dir>/.moni_key)",
    )
    parser.add_argument(
        "--password",
        help="Password used for configuration encryption (optional)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser(
        "show",
        help="Display the decrypted configuration in JSON format",
    )
    show_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the configuration JSON",
    )

    subparsers.add_parser(
        "rotate-key",
        help="Rotate the stored encryption key while preserving configuration contents",
    )

    return parser


def _create_manager(args: argparse.Namespace) -> SecureConfigManager:
    if args.key_path is not None:
        key_path = args.key_path
    else:
        key_path = args.config_path.parent / ".moni_key"
    return SecureConfigManager(
        config_path=args.config_path,
        key_path=key_path,
    )


def _sanitize_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], list[str], bool]:
    config_core = {k: v for k, v in config.items() if k != "_signature"}

    try:
        moni_config = MoniConfig.model_validate(config_core)
    except ValidationError as exc:  # noqa: BLE001 - surface precise schema issues
        raise ValueError(f"Configuration schema invalid: {exc}") from exc

    before_dump = json.loads(
        moni_config.model_dump_json(mode="json", exclude_unset=True)
    )

    warnings = moni_config._sanitize_before_save()

    bandwidth_settings = moni_config.automation.network.bandwidth_test
    if bandwidth_settings.enabled and not bandwidth_settings.download_endpoint:
        warnings.append("Bandwidth testing enabled but no download endpoint configured")
        bandwidth_settings.enabled = False

    quality_settings = moni_config.automation.network.quality_test
    if quality_settings.enabled and not quality_settings.hosts:
        warnings.append("Network quality testing enabled but no hosts configured")
        quality_settings.enabled = False

    after_dump = json.loads(
        moni_config.model_dump_json(mode="json", exclude_unset=True)
    )

    changed = before_dump != after_dump
    return after_dump, warnings, changed


def cmd_show(args: argparse.Namespace) -> int:
    manager = _create_manager(args)

    try:
        config = manager.load_config(password=args.password)
    except Exception as exc:  # noqa: BLE001 - surface precise error to user
        print(f"Failed to load configuration: {exc}", file=sys.stderr)
        return 1

    sanitized = manager.sanitize_config(config)
    if args.pretty:
        print(json.dumps(sanitized, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")))
    return 0


def cmd_rotate_key(args: argparse.Namespace) -> int:
    manager = _create_manager(args)

    try:
        manager.rotate_encryption_key(password=args.password)
    except Exception as exc:  # noqa: BLE001 - provide clear failure to operator
        print(f"Key rotation failed: {exc}", file=sys.stderr)
        return 1

    print("Encryption key rotated successfully.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manager = _create_manager(args)

    try:
        config = manager.load_config(password=args.password)
    except Exception as exc:  # noqa: BLE001 - provide clear failure to operator
        print(f"Failed to load configuration: {exc}", file=sys.stderr)
        return 1

    try:
        sanitized_config, warnings, changed = _sanitize_config(config)
    except ValueError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1

    if warnings:
        print("Sanitization warnings detected:")
        for warning in warnings:
            print(f" - {warning}")
    else:
        print("No sanitization issues detected.")

    if args.write:
        if changed:
            try:
                manager.save_config(sanitized_config, password=args.password)
            except Exception as exc:  # noqa: BLE001 - ensure operator feedback
                print(f"Failed to save sanitized configuration: {exc}", file=sys.stderr)
                return 1
            print("Configuration sanitized and saved securely.")
        else:
            print("Configuration already compliant; no changes written.")
    else:
        if changed:
            print("Run with --write to persist sanitized changes.")

    if args.pretty:
        redacted_view = manager.sanitize_config(sanitized_config)
        print(json.dumps(redacted_view, ensure_ascii=False, indent=2))

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "show":
        return cmd_show(args)
    if args.command == "rotate-key":
        return cmd_rotate_key(args)
    if args.command == "validate":
        return cmd_validate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
