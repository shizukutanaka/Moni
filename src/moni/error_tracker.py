"""
エラートラッキングシステム - Moni System Monitor

包括的なエラーキャプチャ、レポート、分析機能を提供します。
"""

from __future__ import annotations

import json
import logging
import threading
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ErrorEvent:
    """エラーイベント"""
    id: str
    timestamp: datetime
    exception_type: str
    message: str
    stack_trace: str
    file_name: str
    line_number: int
    function_name: str
    severity: str = 'error'
    tags: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    environment: str = 'production'
    release: Optional[str] = None


class ErrorTracker:
    """エラートラッカー"""

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else Path(__file__).parent / "error_logs"
        self.storage_dir.mkdir(exist_ok=True)

        self.errors: deque = deque(maxlen=10000)  # メモリ内エラーキュー
        self.error_groups: Dict[str, List[str]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

        # エラーグループ化のための設定
        self.grouping_window = 300  # 5分以内の同じエラーはグループ化
        self.max_groups = 1000

        # 自動レポート設定
        self.auto_report_enabled = True
        self.report_interval = 3600  # 1時間ごと

    def capture_error(self, error: Exception, **kwargs) -> str:
        """エラーをキャプチャ"""
        try:
            # スタックトレースを取得
            stack_trace = traceback.format_exc()

            # エラー情報を抽出
            tb = traceback.extract_tb(error.__traceback__)[-1] if error.__traceback__ else None

            error_event = ErrorEvent(
                id=f"err_{int(time.time() * 1000000)}",
                timestamp=datetime.now(timezone.utc),
                exception_type=type(error).__name__,
                message=str(error),
                stack_trace=stack_trace,
                file_name=tb.name if tb else 'unknown',
                line_number=tb.lineno if tb else 0,
                function_name=tb.name if tb else 'unknown',
                **kwargs
            )

            with self._lock:
                self.errors.append(error_event)
                self._group_error(error_event)
                self.error_counts[error_event.exception_type] += 1

            logger.error(f"エラーをキャプチャしました: {error_event.id} - {error_event.message}")

            # 自動レポート
            if self.auto_report_enabled:
                self._schedule_report()

            return error_event.id

        except Exception as e:
            logger.error(f"エラーキャプチャ中にエラーが発生しました: {e}")
            return ''

    def _group_error(self, error_event: ErrorEvent) -> None:
        """エラーをグループ化"""
        group_key = self._generate_group_key(error_event)

        if group_key not in self.error_groups:
            if len(self.error_groups) >= self.max_groups:
                # 古いグループを削除
                oldest_key = min(self.error_groups.keys(), key=lambda k: self.error_groups[k][0] if self.error_groups[k] else time.time())
                del self.error_groups[oldest_key]

        self.error_groups[group_key].append(error_event.id)

    def _generate_group_key(self, error_event: ErrorEvent) -> str:
        """グループキーを生成"""
        # 同じファイル、関数、エラーメッセージのエラーはグループ化
        return f"{error_event.file_name}:{error_event.function_name}:{hash(error_event.message) % 10000}"

    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        with self._lock:
            return {
                'total_errors': len(self.errors),
                'error_types': dict(self.error_counts),
                'recent_errors': [self._serialize_error(e) for e in list(self.errors)[-10:]],
                'error_groups': len(self.error_groups)
            }

    def get_errors(self, limit: int = 100, error_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """エラーリストを取得"""
        with self._lock:
            errors = list(self.errors)
            if error_type:
                errors = [e for e in errors if e.exception_type == error_type]

            return [self._serialize_error(e) for e in errors[-limit:]]

    def _serialize_error(self, error_event: ErrorEvent) -> Dict[str, Any]:
        """エラーをシリアライズ"""
        return {
            'id': error_event.id,
            'timestamp': error_event.timestamp.isoformat(),
            'type': error_event.exception_type,
            'message': error_event.message,
            'file': error_event.file_name,
            'line': error_event.line_number,
            'function': error_event.function_name,
            'severity': error_event.severity,
            'tags': error_event.tags,
            'user_id': error_event.user_id,
            'session_id': error_event.session_id,
            'environment': error_event.environment,
            'release': error_event.release
        }

    def export_errors(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """エラーをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.storage_dir / f"errors_{timestamp}.{format_type}"

        try:
            if format_type == 'json':
                data = [self._serialize_error(e) for e in self.errors]
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            elif format_type == 'csv':
                import csv
                data = [self._serialize_error(e) for e in self.errors]
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if data:
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)

            logger.info(f"エラーをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"エクスポートエラー: {e}")
            return None

    def _schedule_report(self) -> None:
        """レポートをスケジュール"""
        # 実際の実装では、バックグラウンドスレッドで定期レポートを実装
        pass


# グローバルインスタンス
error_tracker = ErrorTracker()
