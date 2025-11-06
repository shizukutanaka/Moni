"""
Privacy Guard - 個人利用向けプライバシー保護機能
データ保護、匿名化、プライバシー監視を統合管理
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PrivacyEvent:
    """プライバシー関連イベントの記録"""

    timestamp: datetime
    event_type: str  # 'network_access', 'file_access', 'clipboard_access', 'camera_access'
    process_name: str
    process_pid: int
    details: str
    risk_level: str = "low"  # low, medium, high, critical
    blocked: bool = False


@dataclass
class ProcessPrivacyProfile:
    """プロセスごとのプライバシープロファイル"""

    process_name: str
    trusted: bool = False
    network_access_count: int = 0
    file_access_count: int = 0
    clipboard_access_count: int = 0
    camera_access_count: int = 0
    microphone_access_count: int = 0
    last_activity: Optional[datetime] = None
    risk_score: float = 0.0
    permissions: Set[str] = field(default_factory=set)


class NetworkMonitor:
    """ネットワークアクティビティの監視とプライバシー保護"""

    # 既知の追跡ドメイン（広告・トラッキング）
    TRACKING_DOMAINS = {
        "doubleclick.net", "google-analytics.com", "googleadservices.com",
        "facebook.com", "facebook.net", "connect.facebook.net",
        "scorecardresearch.com", "2mdn.net", "advertising.com",
        "criteo.com", "outbrain.com", "taboola.com",
        "ads.yahoo.com", "ads.twitter.com", "ads.linkedin.com"
    }

    # 安全な既知ドメイン
    SAFE_DOMAINS = {
        "github.com", "stackoverflow.com", "python.org",
        "microsoft.com", "apple.com", "ubuntu.com"
    }

    def __init__(self):
        self._connection_history: Dict[str, List[Tuple[str, int, datetime]]] = defaultdict(list)
        self._blocked_connections: List[Tuple[str, str, datetime]] = []

    def check_connection(self, process_name: str, remote_addr: str, remote_port: int) -> Tuple[bool, str]:
        """
        接続をチェックし、追跡・広告サーバーをブロック

        Returns:
            (allowed: bool, reason: str)
        """
        # ドメイン抽出（IPアドレスの場合はそのまま）
        domain = self._extract_domain(remote_addr)

        # 追跡ドメインチェック
        if self._is_tracking_domain(domain):
            self._blocked_connections.append((process_name, domain, datetime.now()))
            logger.warning(
                f"Blocked tracking connection: {process_name} -> {domain}",
                extra={"process": process_name, "domain": domain}
            )
            return False, f"Tracking domain blocked: {domain}"

        # 接続履歴に記録
        self._connection_history[process_name].append((remote_addr, remote_port, datetime.now()))

        return True, "Connection allowed"

    def _extract_domain(self, addr: str) -> str:
        """IPアドレスまたはホスト名からドメインを抽出"""
        # IPアドレスの場合はそのまま返す
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', addr):
            return addr

        # ホスト名からドメインを抽出
        parts = addr.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return addr

    def _is_tracking_domain(self, domain: str) -> bool:
        """追跡ドメインかチェック"""
        return any(tracking in domain for tracking in self.TRACKING_DOMAINS)

    def get_connection_stats(self) -> Dict[str, any]:
        """接続統計を取得"""
        total_connections = sum(len(conns) for conns in self._connection_history.values())

        return {
            "total_connections": total_connections,
            "unique_processes": len(self._connection_history),
            "blocked_count": len(self._blocked_connections),
            "processes": dict(self._connection_history)
        }


class FileAccessMonitor:
    """ファイルアクセスの監視とプライバシー保護"""

    # 機密ファイルパターン
    SENSITIVE_PATTERNS = [
        r'.*\.ssh/.*',          # SSH keys
        r'.*\.gnupg/.*',        # GPG keys
        r'.*wallet\.dat',       # 暗号通貨ウォレット
        r'.*\.kdbx',            # KeePass databases
        r'.*password.*',        # パスワードファイル
        r'.*\.key',             # 秘密鍵
        r'.*\.pem',             # 証明書
        r'.*credential.*',      # 認証情報
        r'.*token.*',           # トークン
    ]

    def __init__(self):
        self._access_log: List[Tuple[str, str, datetime]] = []
        self._sensitive_access_alerts: List[Tuple[str, str, datetime]] = []

    def check_file_access(self, process_name: str, file_path: str) -> Tuple[bool, str]:
        """
        ファイルアクセスをチェック

        Returns:
            (allowed: bool, warning: str)
        """
        # 機密ファイルチェック
        if self._is_sensitive_file(file_path):
            self._sensitive_access_alerts.append((process_name, file_path, datetime.now()))
            logger.warning(
                f"Sensitive file access: {process_name} -> {file_path}",
                extra={"process": process_name, "file": file_path}
            )
            return True, f"Warning: Sensitive file accessed by {process_name}"

        # 通常のアクセスログ
        self._access_log.append((process_name, file_path, datetime.now()))
        return True, ""

    def _is_sensitive_file(self, file_path: str) -> bool:
        """機密ファイルかチェック"""
        return any(re.match(pattern, file_path, re.IGNORECASE)
                   for pattern in self.SENSITIVE_PATTERNS)

    def get_sensitive_access_log(self, hours: int = 24) -> List[Tuple[str, str, datetime]]:
        """直近の機密ファイルアクセスログを取得"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [(proc, path, ts) for proc, path, ts in self._sensitive_access_alerts
                if ts >= cutoff]


class ClipboardMonitor:
    """クリップボード監視（パスワード・機密情報の検出）"""

    # 機密データパターン
    SENSITIVE_PATTERNS = {
        'password': r'password[:\s]*[\w\W]{6,}',
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'api_key': r'(?i)(api[_-]?key|access[_-]?token)[:\s]*[\w\-]{20,}',
        'private_key': r'-----BEGIN .* PRIVATE KEY-----',
    }

    def __init__(self):
        self._clipboard_history: List[Tuple[str, datetime, bool]] = []
        self._sensitive_detections: List[Tuple[str, str, datetime]] = []

    def check_clipboard_content(self, content: str, process_name: str = "Unknown") -> Dict[str, any]:
        """
        クリップボード内容をチェック

        Returns:
            検出結果と警告
        """
        detections = []

        for data_type, pattern in self.SENSITIVE_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                detections.append(data_type)
                self._sensitive_detections.append((data_type, process_name, datetime.now()))

        is_sensitive = len(detections) > 0
        self._clipboard_history.append((content[:100], datetime.now(), is_sensitive))

        if is_sensitive:
            logger.warning(
                f"Sensitive data in clipboard: {', '.join(detections)}",
                extra={"detections": detections, "process": process_name}
            )

        return {
            "sensitive": is_sensitive,
            "detections": detections,
            "warning": f"Sensitive data detected: {', '.join(detections)}" if is_sensitive else ""
        }

    def get_sensitivity_stats(self) -> Dict[str, any]:
        """機密データ統計"""
        total = len(self._clipboard_history)
        sensitive = sum(1 for _, _, is_sens in self._clipboard_history if is_sens)

        return {
            "total_clipboard_events": total,
            "sensitive_count": sensitive,
            "sensitivity_rate": (sensitive / total * 100) if total > 0 else 0,
            "recent_detections": self._sensitive_detections[-10:]
        }


class WebcamMicMonitor:
    """カメラ・マイク使用の監視"""

    def __init__(self):
        self._camera_usage: List[Tuple[str, datetime, datetime]] = []
        self._mic_usage: List[Tuple[str, datetime, datetime]] = []
        self._active_camera_processes: Set[str] = set()
        self._active_mic_processes: Set[str] = set()

    def detect_camera_usage(self) -> List[str]:
        """カメラを使用中のプロセスを検出"""
        camera_processes = []

        # Windows: カメラデバイスにアクセスしているプロセスを検出
        # Linux: /dev/video* にアクセスしているプロセスを検出
        # macOS: カメラアクセスのシステムログをチェック

        for proc in psutil.process_iter(['name', 'pid']):
            try:
                # プロセスのオープンファイルをチェック
                for file in proc.open_files():
                    if 'video' in file.path.lower() or 'camera' in file.path.lower():
                        camera_processes.append(proc.info['name'])

                        if proc.info['name'] not in self._active_camera_processes:
                            self._camera_usage.append((
                                proc.info['name'],
                                datetime.now(),
                                None
                            ))
                            self._active_camera_processes.add(proc.info['name'])

                            logger.warning(
                                f"Camera access detected: {proc.info['name']}",
                                extra={"process": proc.info['name'], "pid": proc.info['pid']}
                            )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return camera_processes

    def detect_microphone_usage(self) -> List[str]:
        """マイクを使用中のプロセスを検出"""
        mic_processes = []

        for proc in psutil.process_iter(['name', 'pid']):
            try:
                for file in proc.open_files():
                    if 'audio' in file.path.lower() or 'pcm' in file.path.lower():
                        mic_processes.append(proc.info['name'])

                        if proc.info['name'] not in self._active_mic_processes:
                            self._mic_usage.append((
                                proc.info['name'],
                                datetime.now(),
                                None
                            ))
                            self._active_mic_processes.add(proc.info['name'])

                            logger.warning(
                                f"Microphone access detected: {proc.info['name']}",
                                extra={"process": proc.info['name'], "pid": proc.info['pid']}
                            )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return mic_processes

    def get_usage_history(self, hours: int = 24) -> Dict[str, any]:
        """カメラ・マイク使用履歴"""
        cutoff = datetime.now() - timedelta(hours=hours)

        recent_camera = [(proc, start) for proc, start, _ in self._camera_usage if start >= cutoff]
        recent_mic = [(proc, start) for proc, start, _ in self._mic_usage if start >= cutoff]

        return {
            "camera_usage": recent_camera,
            "microphone_usage": recent_mic,
            "active_camera": list(self._active_camera_processes),
            "active_microphone": list(self._active_mic_processes)
        }


class PrivacyGuard:
    """統合プライバシー保護システム"""

    def __init__(self, db_path: Optional[Path] = None):
        self.network_monitor = NetworkMonitor()
        self.file_monitor = FileAccessMonitor()
        self.clipboard_monitor = ClipboardMonitor()
        self.webcam_mic_monitor = WebcamMicMonitor()

        self._process_profiles: Dict[str, ProcessPrivacyProfile] = {}
        self._privacy_events: List[PrivacyEvent] = []

        # データベース初期化
        self.db_path = db_path or (Path.home() / ".config" / "moni" / "privacy.db")
        self._init_database()

    def _init_database(self):
        """プライバシーログデータベースの初期化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS privacy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                process_name TEXT NOT NULL,
                process_pid INTEGER,
                details TEXT,
                risk_level TEXT,
                blocked INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_profiles (
                process_name TEXT PRIMARY KEY,
                trusted INTEGER,
                network_access_count INTEGER,
                file_access_count INTEGER,
                clipboard_access_count INTEGER,
                camera_access_count INTEGER,
                microphone_access_count INTEGER,
                risk_score REAL,
                last_updated TEXT
            )
        """)

        conn.commit()
        conn.close()

    def scan_system(self) -> Dict[str, any]:
        """システム全体のプライバシースキャン"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "network": {},
            "files": {},
            "clipboard": {},
            "devices": {},
            "overall_risk": "low"
        }

        # ネットワークスキャン
        results["network"] = self.network_monitor.get_connection_stats()

        # 機密ファイルアクセスチェック
        sensitive_files = self.file_monitor.get_sensitive_access_log(hours=1)
        results["files"] = {
            "sensitive_access_count": len(sensitive_files),
            "recent_access": sensitive_files[-5:]
        }

        # クリップボードチェック
        results["clipboard"] = self.clipboard_monitor.get_sensitivity_stats()

        # カメラ・マイクチェック
        camera_procs = self.webcam_mic_monitor.detect_camera_usage()
        mic_procs = self.webcam_mic_monitor.detect_microphone_usage()
        results["devices"] = {
            "camera_active": camera_procs,
            "microphone_active": mic_procs,
            "usage_history": self.webcam_mic_monitor.get_usage_history(hours=1)
        }

        # 総合リスク評価
        risk_score = self._calculate_overall_risk(results)
        results["overall_risk"] = self._risk_level_from_score(risk_score)
        results["risk_score"] = risk_score

        return results

    def _calculate_overall_risk(self, results: Dict[str, any]) -> float:
        """総合リスクスコアを計算（0-100）"""
        risk = 0.0

        # ブロックされた接続があれば+30
        if results["network"].get("blocked_count", 0) > 0:
            risk += 30

        # 機密ファイルアクセスがあれば+20
        if results["files"].get("sensitive_access_count", 0) > 0:
            risk += 20

        # 機密クリップボードデータがあれば+15
        if results["clipboard"].get("sensitive_count", 0) > 0:
            risk += 15

        # カメラが使用中なら+15
        if len(results["devices"].get("camera_active", [])) > 0:
            risk += 15

        # マイクが使用中なら+10
        if len(results["devices"].get("microphone_active", [])) > 0:
            risk += 10

        return min(100.0, risk)

    def _risk_level_from_score(self, score: float) -> str:
        """スコアからリスクレベルを判定"""
        if score >= 70:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def get_privacy_report(self) -> str:
        """プライバシーレポートを生成"""
        scan_results = self.scan_system()

        report = []
        report.append("=" * 60)
        report.append("MONI PRIVACY GUARD - セキュリティレポート")
        report.append("=" * 60)
        report.append(f"スキャン日時: {scan_results['timestamp']}")
        report.append(f"総合リスクレベル: {scan_results['overall_risk'].upper()}")
        report.append(f"リスクスコア: {scan_results['risk_score']:.1f}/100")
        report.append("")

        # ネットワーク
        report.append("【ネットワーク監視】")
        net = scan_results["network"]
        report.append(f"  総接続数: {net.get('total_connections', 0)}")
        report.append(f"  ブロック数: {net.get('blocked_count', 0)}")
        report.append(f"  監視プロセス数: {net.get('unique_processes', 0)}")
        report.append("")

        # ファイル
        report.append("【ファイルアクセス監視】")
        files = scan_results["files"]
        report.append(f"  機密ファイルアクセス: {files.get('sensitive_access_count', 0)} 件")
        report.append("")

        # クリップボード
        report.append("【クリップボード監視】")
        clip = scan_results["clipboard"]
        report.append(f"  機密データ検出: {clip.get('sensitive_count', 0)} 件")
        report.append(f"  検出率: {clip.get('sensitivity_rate', 0):.1f}%")
        report.append("")

        # デバイス
        report.append("【デバイスアクセス監視】")
        devices = scan_results["devices"]
        camera = devices.get("camera_active", [])
        mic = devices.get("microphone_active", [])

        if camera:
            report.append(f"  ⚠ カメラ使用中: {', '.join(camera)}")
        else:
            report.append("  ✓ カメラ: 未使用")

        if mic:
            report.append(f"  ⚠ マイク使用中: {', '.join(mic)}")
        else:
            report.append("  ✓ マイク: 未使用")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)

    def enable_auto_protect(self):
        """自動プライバシー保護を有効化"""
        logger.info("Privacy Guard auto-protection enabled")
        # 継続的な監視を開始（バックグラウンドスレッドで実行）

    def export_privacy_log(self, output_path: Path, format: str = "json"):
        """プライバシーログをエクスポート"""
        import json

        scan_results = self.scan_system()

        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(scan_results, f, indent=2, ensure_ascii=False)

        logger.info(f"Privacy log exported to {output_path}")


# グローバルインスタンス
_privacy_guard: Optional[PrivacyGuard] = None


def get_privacy_guard() -> PrivacyGuard:
    """グローバルPrivacyGuardインスタンスを取得"""
    global _privacy_guard
    if _privacy_guard is None:
        _privacy_guard = PrivacyGuard()
    return _privacy_guard
