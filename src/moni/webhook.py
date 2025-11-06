"""
Webhook通知システム - Moni System Monitor

アラートとイベントを外部サービスに通知するためのWebhookシステム。
Slack、Discord、Microsoft Teams、Webhook URLなどの統合をサポート。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx

from .enhanced_security import AdvancedInputValidator, EnhancedValidationError

logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Webhook設定"""
    enabled: bool = False
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_per_minute: int = 60
    template: str = "default"
    custom_payload_template: Optional[str] = None

    def sanitize(self) -> None:
        """Sanitize URL and headers prior to validation."""
        validator = AdvancedInputValidator()

        url_candidate = (self.url or "").strip()
        if url_candidate:
            try:
                self.url = validator.validate_https_url(url_candidate)
            except EnhancedValidationError as exc:
                logger.warning(
                    "Webhook URL rejected during sanitization",
                    extra={"url": url_candidate, "error": str(exc)},
                )
                self.url = ""
                self.enabled = False
        else:
            self.url = ""
            self.enabled = False

        sanitized_headers: Dict[str, str] = {}
        for key, value in (self.headers or {}).items():
            key_candidate = (key or "").strip()
            if not key_candidate:
                continue
            if len(key_candidate) > 64:
                logger.warning(
                    "Webhook header key trimmed due to length",
                    extra={"header": key_candidate},
                )
                continue
            sanitized_value = value if isinstance(value, str) else str(value)
            sanitized_headers[key_candidate] = sanitized_value.strip()

        if self.enabled and "Content-Type" not in sanitized_headers:
            sanitized_headers["Content-Type"] = "application/json"

        self.headers = sanitized_headers

    def validate(self) -> None:
        """設定の検証"""
        self.sanitize()

        if self.enabled:
            if not self.url:
                raise ValueError("Webhook URLが必要です")

            if self.timeout_seconds < 1:
                raise ValueError("タイムアウトは1秒以上である必要があります")

            if self.retry_attempts < 0:
                raise ValueError("リトライ回数は0以上である必要があります")

            if self.retry_delay_seconds < 0:
                raise ValueError("リトライ遅延は0以上である必要があります")

            if self.rate_limit_per_minute < 1:
                raise ValueError("レート制限は1回/分以上である必要があります")


@dataclass
class WebhookEvent:
    """Webhookイベント"""
    event_type: str  # "alert", "metric", "system"
    title: str
    message: str
    timestamp: float
    severity: str = "info"  # "info", "warning", "error", "critical"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """イベントを辞書に変換"""
        return {
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "metadata": self.metadata,
            "tags": self.tags,
        }


class WebhookTemplate:
    """Webhookテンプレート"""

    @staticmethod
    def default_slack(event: WebhookEvent) -> Dict[str, Any]:
        """Slackデフォルトテンプレート"""
        color_map = {
            "info": "#36a64f",
            "warning": "#ffcc00",
            "error": "#ff6b6b",
            "critical": "#dc3545"
        }

        return {
            "attachments": [{
                "color": color_map.get(event.severity, "#808080"),
                "title": event.title,
                "text": event.message,
                "fields": [
                    {"title": "Type", "value": event.event_type, "short": True},
                    {"title": "Severity", "value": event.severity, "short": True},
                    {"title": "Time", "value": datetime.fromtimestamp(event.timestamp).isoformat(), "short": True}
                ],
                "footer": "Moni System Monitor",
                "ts": event.timestamp
            }]
        }

    @staticmethod
    def default_discord(event: WebhookEvent) -> Dict[str, Any]:
        """Discordデフォルトテンプレート"""
        embed_color_map = {
            "info": 0x36a64f,
            "warning": 0xffcc00,
            "error": 0xff6b6b,
            "critical": 0xdc3545
        }

        return {
            "embeds": [{
                "title": event.title,
                "description": event.message,
                "color": embed_color_map.get(event.severity, 0x808080),
                "fields": [
                    {"name": "Type", "value": event.event_type, "inline": True},
                    {"name": "Severity", "value": event.severity, "inline": True},
                    {"name": "Time", "value": datetime.fromtimestamp(event.timestamp).isoformat(), "inline": True}
                ],
                "footer": {"text": "Moni System Monitor"},
                "timestamp": datetime.fromtimestamp(event.timestamp).isoformat()
            }]
        }

    @staticmethod
    def default_teams(event: WebhookEvent) -> Dict[str, Any]:
        """Microsoft Teamsデフォルトテンプレート"""
        theme_color_map = {
            "info": "36a64f",
            "warning": "ffcc00",
            "error": "ff6b6b",
            "critical": "dc3545"
        }

        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color_map.get(event.severity, "808080"),
            "title": event.title,
            "text": event.message,
            "sections": [{
                "facts": [
                    {"name": "Type", "value": event.event_type},
                    {"name": "Severity", "value": event.severity},
                    {"name": "Time", "value": datetime.fromtimestamp(event.timestamp).isoformat()}
                ]
            }]
        }

    @staticmethod
    def default_generic(event: WebhookEvent) -> Dict[str, Any]:
        """汎用JSONテンプレート"""
        return event.to_dict()


class WebhookNotifier:
    """Webhook通知クラス"""

    def __init__(self, config: WebhookConfig):
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.rate_limiter = RateLimiter(self.config.rate_limit_per_minute)
        self.templates = {
            "slack": WebhookTemplate.default_slack,
            "discord": WebhookTemplate.default_discord,
            "teams": WebhookTemplate.default_teams,
            "generic": WebhookTemplate.default_generic,
        }

        # カスタムテンプレートの登録
        if self.config.custom_payload_template:
            try:
                # カスタムテンプレートはJSON文字列として扱う
                custom_template = json.loads(self.config.custom_payload_template)
                self.templates["custom"] = lambda event: custom_template
            except json.JSONDecodeError as e:
                logger.error(f"カスタムテンプレートの解析エラー: {e}")

    async def initialize(self) -> None:
        """初期化"""
        if not self.config.enabled:
            return

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout_seconds),
            headers=self.config.headers
        )

        logger.info(f"Webhook通知を初期化しました: {self.config.url}")

    async def shutdown(self) -> None:
        """シャットダウン"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def send_event(self, event: WebhookEvent) -> bool:
        """イベントを送信"""
        if not self.config.enabled or not self.client:
            return False

        # レート制限チェック
        if not self.rate_limiter.allow():
            logger.warning("レート制限によりWebhook通知をスキップしました")
            return False

        # ペイロード生成
        payload = self._create_payload(event)

        # 送信
        for attempt in range(self.config.retry_attempts + 1):
            try:
                response = await self.client.post(
                    self.config.url,
                    json=payload,
                    headers=self.config.headers
                )

                if response.status_code in (200, 201, 202, 204):
                    logger.debug(f"Webhook通知を送信しました: {event.title}")
                    return True
                else:
                    logger.warning(f"Webhook送信失敗 (ステータス: {response.status_code}): {response.text}")

            except Exception as e:
                logger.warning(f"Webhook送信エラー (試行 {attempt + 1}/{self.config.retry_attempts + 1}): {e}")

                if attempt < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2 ** attempt))  # 指数バックオフ

        logger.error(f"Webhook送信に失敗しました: {event.title}")
        return False

    def _create_payload(self, event: WebhookEvent) -> Dict[str, Any]:
        """イベントからペイロードを作成"""
        template_func = self.templates.get(self.config.template, WebhookTemplate.default_generic)
        return template_func(event)

    def send_event_sync(self, event: WebhookEvent) -> bool:
        """同期版イベント送信（バックグラウンドスレッド用）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self.send_event(event))
        finally:
            loop.close()


class RateLimiter:
    """レート制限クラス"""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.requests: List[float] = []
        self.lock = threading.Lock()

    def allow(self) -> bool:
        """リクエストを許可するかチェック"""
        with self.lock:
            now = time.time()

            # 1分以上前のリクエストを削除
            cutoff = now - 60
            self.requests = [t for t in self.requests if t > cutoff]

            # 制限チェック
            if len(self.requests) >= self.max_per_minute:
                return False

            # リクエストを記録
            self.requests.append(now)
            return True


class WebhookManager:
    """Webhookマネージャー"""

    def __init__(self):
        self.notifiers: Dict[str, WebhookNotifier] = {}
        self.event_queue: asyncio.Queue[WebhookEvent] = asyncio.Queue()
        self.running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.lock = threading.Lock()

    def add_webhook(self, name: str, config: WebhookConfig) -> None:
        """Webhookを追加"""
        try:
            config.sanitize()
            config.validate()
            notifier = WebhookNotifier(config)
            self.notifiers[name] = notifier
            logger.info(f"Webhook '{name}' を追加しました")
        except Exception as e:
            logger.error(f"Webhook '{name}' の追加に失敗しました: {e}")

    def remove_webhook(self, name: str) -> None:
        """Webhookを削除"""
        if name in self.notifiers:
            del self.notifiers[name]
            logger.info(f"Webhook '{name}' を削除しました")

    async def start(self) -> None:
        """マネージャーを開始"""
        if self.running:
            return

        self.running = True

        # 全Notifierを初期化
        for notifier in self.notifiers.values():
            await notifier.initialize()

        # ワーカータスクを開始
        self.worker_task = asyncio.create_task(self._process_events())

        logger.info("Webhookマネージャーを開始しました")

    async def stop(self) -> None:
        """マネージャーを停止"""
        if not self.running:
            return

        self.running = False

        # ワーカータスクを停止
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        # 全Notifierをシャットダウン
        for notifier in self.notifiers.values():
            await notifier.shutdown()

        logger.info("Webhookマネージャーを停止しました")

    async def send_notification(self, event: WebhookEvent, webhook_names: Optional[List[str]] = None) -> None:
        """通知を送信"""
        if not self.running:
            return

        # 指定されたWebhookのみ、または全てのWebhookに送信
        targets = webhook_names if webhook_names else list(self.notifiers.keys())

        for name in targets:
            if name in self.notifiers:
                notifier = self.notifiers[name]

                # 非同期で送信
                asyncio.create_task(self._send_to_webhook(notifier, event))

    async def _send_to_webhook(self, notifier: WebhookNotifier, event: WebhookEvent) -> None:
        """指定されたWebhookにイベントを送信"""
        try:
            await notifier.send_event(event)
        except Exception as e:
            logger.error(f"Webhook送信中にエラーが発生しました: {e}")

    async def _process_events(self) -> None:
        """イベント処理ワーカー"""
        while self.running:
            try:
                # キューからイベントを取得（タイムアウト付き）
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # 全Webhookに送信
                await self.send_notification(event)

                self.event_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"イベント処理中にエラーが発生しました: {e}")

    def send_notification_sync(self, event: WebhookEvent, webhook_names: Optional[List[str]] = None) -> None:
        """同期版通知送信"""
        if not self.running:
            return

        # 新しいイベントループを作成して実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.send_notification(event, webhook_names))
        finally:
            loop.close()

    def get_status(self) -> Dict[str, Any]:
        """ステータスを取得"""
        return {
            "running": self.running,
            "webhook_count": len(self.notifiers),
            "queue_size": self.event_queue.qsize(),
            "webhooks": list(self.notifiers.keys())
        }


# グローバルマネージャーインスタンス
_webhook_manager: Optional[WebhookManager] = None
_webhook_background_thread: Optional[threading.Thread] = None
_background_loop: Optional[asyncio.AbstractEventLoop] = None
_background_lock = threading.Lock()
_background_started = threading.Event()


def init_webhook_manager() -> WebhookManager:
    """Webhookマネージャーを初期化"""
    global _webhook_manager

    if _webhook_manager is None:
        _webhook_manager = WebhookManager()

    return _webhook_manager


def get_webhook_manager() -> Optional[WebhookManager]:
    """Webhookマネージャーを取得"""
    return _webhook_manager


def start_webhook_manager_background() -> None:
    """Webhookマネージャーをバックグラウンドスレッドで起動"""
    global _webhook_background_thread
    global _background_loop
    global _background_started
    global _webhook_manager

    with _background_lock:
        if _webhook_background_thread and _webhook_background_thread.is_alive():
            return

        manager = init_webhook_manager()

        def _run_loop() -> None:
            global _background_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _background_loop = loop
            _background_started.set()

            async def _runner() -> None:
                await manager.start()

            try:
                loop.create_task(_runner())
                loop.run_forever()
            finally:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                with suppress(Exception):
                    loop.run_until_complete(loop.shutdown_asyncgens())
                asyncio.set_event_loop(None)
                _background_loop = None
                loop.close()

        _background_started.clear()
        _webhook_background_thread = threading.Thread(target=_run_loop, name="moni-webhook", daemon=True)
        _webhook_background_thread.start()
        _background_started.wait(timeout=5)
        if not _background_started.is_set():
            logger.warning("Webhook background thread did not start within timeout")


def send_webhook_notification(event: WebhookEvent, webhook_names: Optional[List[str]] = None) -> None:
    """Webhook通知を送信（便利関数）"""
    manager = get_webhook_manager()
    if manager:
        manager.send_notification_sync(event, webhook_names)


def create_alert_event(title: str, message: str, severity: str = "warning",
                      metadata: Optional[Dict[str, Any]] = None) -> WebhookEvent:
    """アラートイベントを作成"""
    return WebhookEvent(
        event_type="alert",
        title=title,
        message=message,
        timestamp=time.time(),
        severity=severity,
        metadata=metadata or {},
        tags=["alert"]
    )


def create_metric_event(title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> WebhookEvent:
    """メトリクスイベントを作成"""
    return WebhookEvent(
        event_type="metric",
        title=title,
        message=message,
        timestamp=time.time(),
        severity="info",
        metadata=metadata or {},
        tags=["metric"]
    )


def create_system_event(title: str, message: str, severity: str = "info",
                       metadata: Optional[Dict[str, Any]] = None) -> WebhookEvent:
    """システムイベントを作成"""
    return WebhookEvent(
        event_type="system",
        title=title,
        message=message,
        timestamp=time.time(),
        severity=severity,
        metadata=metadata or {},
        tags=["system"]
    )


def shutdown_webhook_manager() -> None:
    """Webhookマネージャーをシャットダウン"""
    global _webhook_manager
    global _webhook_background_thread
    global _background_loop
    global _background_started

    with _background_lock:
        loop = _background_loop
        thread = _webhook_background_thread
        manager = _webhook_manager

    if loop and manager:
        async def _stop_manager() -> None:
            await manager.stop()

        future = asyncio.run_coroutine_threadsafe(_stop_manager(), loop)
        try:
            future.result(timeout=5)
        except Exception as exc:
            logger.error(f"Webhook停止中にエラーが発生しました: {exc}")

    if loop:
        loop.call_soon_threadsafe(loop.stop)

    if thread:
        thread.join(timeout=5)

    with _background_lock:
        _webhook_background_thread = None
        _background_loop = None
        _background_started.clear()
        _webhook_manager = None
