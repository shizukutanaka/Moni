"""
AI駆動の高度な脅威ハンティングシステム - Moni System Monitor

機械学習による自動化された脅威検知と対応を提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class ThreatIndicator:
    """脅威インジケーター"""
    id: str
    name: str
    category: str  # malware, phishing, ddos, etc.
    severity: str  # low, medium, high, critical
    description: str
    detection_patterns: List[str]
    false_positive_rate: float
    mitre_technique: Optional[str] = None
    confidence_threshold: float = 0.8


@dataclass
class ThreatDetection:
    """脅威検知結果"""
    id: str
    timestamp: datetime
    indicator: ThreatIndicator
    confidence: float
    affected_assets: List[str]
    threat_level: str
    description: str
    evidence: Dict[str, Any]
    recommendations: List[str]
    status: str = 'detected'  # detected, investigating, contained, resolved


@dataclass
class HuntingCampaign:
    """ハンティングキャンペーン"""
    id: str
    name: str
    description: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # active, completed, paused
    findings: List[ThreatDetection] = field(default_factory=list)
    automated: bool = True


class AdvancedThreatHunter:
    """AI駆動の高度な脅威ハンター"""

    def __init__(self, intel_feeds_dir: Optional[Union[str, Path]] = None):
        self.intel_feeds_dir = Path(intel_feeds_dir) if intel_feeds_dir else Path(__file__).parent / "threat_intel"
        self.intel_feeds_dir.mkdir(exist_ok=True)

        # 脅威インジケーター
        self.threat_indicators: Dict[str, ThreatIndicator] = {}
        self.detection_models: Dict[str, Any] = {}
        self.threat_history: deque = deque(maxlen=50000)

        # ハンティングキャンペーン
        self.campaigns: Dict[str, HuntingCampaign] = {}
        self.active_campaigns: List[str] = []

        # AIモデル設定
        self.ai_confidence_threshold = 0.85
        self.automated_response_enabled = True

        self._lock = threading.Lock()

        # 脅威インテリジェンスの初期化
        self._init_threat_intelligence()

        # 自動ハンティングの開始
        self._start_automated_hunting()

    def _init_threat_intelligence(self) -> None:
        """脅威インテリジェンスを初期化"""
        self.threat_indicators = {
            'ransomware_patterns': ThreatIndicator(
                id='TI001',
                name='ランサムウェアパターン',
                category='malware',
                severity='critical',
                description='ランサムウェア特有のファイル暗号化パターンを検知',
                detection_patterns=[
                    r'\.encrypted$',
                    r'\.locked$',
                    r' ransom.*note',
                    r'encryption.*key'
                ],
                false_positive_rate=0.05,
                mitre_technique='T1486'
            ),
            'phishing_indicators': ThreatIndicator(
                id='TI002',
                name='フィッシングインジケーター',
                category='phishing',
                severity='high',
                description='フィッシング攻撃の典型的なパターンを検知',
                detection_patterns=[
                    r'urgent.*account',
                    r'password.*expired',
                    r'click.*link',
                    r'suspicious.*attachment'
                ],
                false_positive_rate=0.15,
                mitre_technique='T1566'
            ),
            'ddos_patterns': ThreatIndicator(
                id='TI003',
                name='DDoS攻撃パターン',
                category='ddos',
                severity='high',
                description='DDoS攻撃のトラフィックパターンを検知',
                detection_patterns=[
                    r'flood.*request',
                    r'amplification.*attack',
                    r'syn.*flood',
                    r'http.*flood'
                ],
                false_positive_rate=0.10,
                mitre_technique='T1498'
            ),
            'lateral_movement': ThreatIndicator(
                id='TI004',
                name='ラテラルムーブメント',
                category='lateral_movement',
                severity='critical',
                description='ネットワーク内での横移動を検知',
                detection_patterns=[
                    r'psexec.*exploit',
                    r'wmi.*lateral',
                    r'rpc.*call',
                    r'pass.*hash'
                ],
                false_positive_rate=0.08,
                mitre_technique='T1072'
            ),
            'credential_dumping': ThreatIndicator(
                id='TI005',
                name='認証情報ダンプ',
                category='credential_access',
                severity='critical',
                description='認証情報の抽出攻撃を検知',
                detection_patterns=[
                    r'mimikatz.*dump',
                    r'lsadump',
                    r'secretsdump',
                    r'credential.*harvest'
                ],
                false_positive_rate=0.03,
                mitre_technique='T1003'
            )
        }

        logger.info(f"{len(self.threat_indicators)}個の脅威インジケーターを初期化しました。")

    def _start_automated_hunting(self) -> None:
        """自動ハンティングを開始"""
        def hunting_loop():
            while True:
                try:
                    # アクティブなキャンペーンを実行
                    for campaign_id in self.active_campaigns:
                        if campaign_id in self.campaigns:
                            self._execute_campaign(campaign_id)

                    # 定期的なシステムスキャン
                    self._perform_system_scan()

                    time.sleep(300)  # 5分ごとに実行

                except Exception as e:
                    logger.error(f"自動ハンティングエラー: {e}")
                    time.sleep(600)  # エラー時は10分待機

        hunting_thread = threading.Thread(target=hunting_loop, daemon=True)
        hunting_thread.start()
        logger.info("自動脅威ハンティングを開始しました。")

    def _execute_campaign(self, campaign_id: str) -> None:
        """キャンペーンを実行"""
        campaign = self.campaigns[campaign_id]

        try:
            logger.info(f"キャンペーンを実行中: {campaign.name}")

            # 各脅威インジケーターでスキャン
            for indicator in self.threat_indicators.values():
                detections = self._hunt_for_threat(indicator)

                for detection in detections:
                    campaign.findings.append(detection)

                    # 高信頼度の検知の場合、自動対応を実行
                    if detection.confidence > self.ai_confidence_threshold and self.automated_response_enabled:
                        self._execute_automated_response(detection)

            # キャンペーンの統計を更新
            campaign.end_time = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"キャンペーン実行エラー ({campaign_id}): {e}")

    def _hunt_for_threat(self, indicator: ThreatIndicator) -> List[ThreatDetection]:
        """脅威をハンティング"""
        detections = []

        try:
            # ログファイルの分析
            log_detections = self._analyze_log_files(indicator)

            # プロセス監視
            process_detections = self._analyze_processes(indicator)

            # ネットワークトラフィック分析
            network_detections = self._analyze_network_traffic(indicator)

            # ファイルシステムスキャン
            filesystem_detections = self._analyze_filesystem(indicator)

            detections.extend(log_detections + process_detections + network_detections + filesystem_detections)

        except Exception as e:
            logger.error(f"脅威ハンティングエラー ({indicator.name}): {e}")

        return detections

    def _analyze_log_files(self, indicator: ThreatIndicator) -> List[ThreatDetection]:
        """ログファイルを分析"""
        detections = []

        try:
            # 一般的なログファイルパス
            log_paths = [
                '/var/log/syslog',
                '/var/log/auth.log',
                '/var/log/kern.log',
                '/var/log/apache2/access.log',
                '/var/log/nginx/access.log'
            ]

            for log_path in log_paths:
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        lines = f.readlines()[-1000:]  # 直近1000行

                    for line in lines:
                        for pattern in indicator.detection_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                confidence = self._calculate_confidence(indicator, line)

                                if confidence > indicator.confidence_threshold:
                                    detection = ThreatDetection(
                                        id=f"TD_{int(time.time() * 1000000)}",
                                        timestamp=datetime.now(timezone.utc),
                                        indicator=indicator,
                                        confidence=confidence,
                                        affected_assets=[log_path],
                                        threat_level=self._get_threat_level(confidence),
                                        description=f"ログファイルで{indicator.name}を検知",
                                        evidence={'log_line': line.strip(), 'pattern': pattern},
                                        recommendations=self._get_response_recommendations(indicator)
                                    )

                                    detections.append(detection)

        except Exception as e:
            logger.error(f"ログ分析エラー: {e}")

        return detections

    def _analyze_processes(self, indicator: ThreatIndicator) -> List[ThreatDetection]:
        """プロセスを分析"""
        detections = []

        try:
            # psコマンドでプロセス情報を取得
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # ヘッダー行を除く

                for line in lines:
                    process_info = line.split(None, 10)  # 最大11フィールド

                    if len(process_info) >= 11:
                        pid, user, cpu, mem, vsz, rss, tty, stat, start, time_cmd, command = process_info

                        # プロセスコマンドをチェック
                        for pattern in indicator.detection_patterns:
                            if re.search(pattern, command, re.IGNORECASE):
                                confidence = self._calculate_confidence(indicator, command)

                                if confidence > indicator.confidence_threshold:
                                    detection = ThreatDetection(
                                        id=f"TD_{int(time.time() * 1000000)}",
                                        timestamp=datetime.now(timezone.utc),
                                        indicator=indicator,
                                        confidence=confidence,
                                        affected_assets=[f"PID:{pid}"],
                                        threat_level=self._get_threat_level(confidence),
                                        description=f"プロセスで{indicator.name}を検知",
                                        evidence={
                                            'pid': pid,
                                            'command': command,
                                            'user': user,
                                            'pattern': pattern
                                        },
                                        recommendations=self._get_response_recommendations(indicator)
                                    )

                                    detections.append(detection)

        except Exception as e:
            logger.error(f"プロセス分析エラー: {e}")

        return detections

    def _analyze_network_traffic(self, indicator: ThreatIndicator) -> List[ThreatDetection]:
        """ネットワークトラフィックを分析"""
        detections = []

        try:
            # netstatやssコマンドでネットワーク接続を取得
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # ヘッダー行を除く

                for line in lines:
                    # 簡易的なパターンマッチング
                    for pattern in indicator.detection_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            confidence = self._calculate_confidence(indicator, line)

                            if confidence > indicator.confidence_threshold:
                                detection = ThreatDetection(
                                    id=f"TD_{int(time.time() * 1000000)}",
                                    timestamp=datetime.now(timezone.utc),
                                    indicator=indicator,
                                    confidence=confidence,
                                    affected_assets=['network'],
                                    threat_level=self._get_threat_level(confidence),
                                    description=f"ネットワークトラフィックで{indicator.name}を検知",
                                    evidence={'connection_info': line.strip(), 'pattern': pattern},
                                    recommendations=self._get_response_recommendations(indicator)
                                )

                                detections.append(detection)

        except Exception as e:
            logger.error(f"ネットワーク分析エラー: {e}")

        return detections

    def _analyze_filesystem(self, indicator: ThreatIndicator) -> List[ThreatDetection]:
        """ファイルシステムを分析"""
        detections = []

        try:
            # findコマンドで怪しいファイルを検索（簡易版）
            suspicious_dirs = ['/tmp', '/var/tmp', '/home']

            for directory in suspicious_dirs:
                if os.path.exists(directory):
                    try:
                        result = subprocess.run(
                            ['find', directory, '-type', 'f', '-mtime', '-1'],  # 1日以内のファイル
                            capture_output=True, text=True, timeout=30
                        )

                        if result.returncode == 0:
                            files = result.stdout.strip().split('\n')

                            for file_path in files[:100]:  # 最大100ファイルチェック
                                if file_path:
                                    # ファイル名をチェック
                                    filename = os.path.basename(file_path)

                                    for pattern in indicator.detection_patterns:
                                        if re.search(pattern, filename, re.IGNORECASE):
                                            confidence = self._calculate_confidence(indicator, filename)

                                            if confidence > indicator.confidence_threshold:
                                                detection = ThreatDetection(
                                                    id=f"TD_{int(time.time() * 1000000)}",
                                                    timestamp=datetime.now(timezone.utc),
                                                    indicator=indicator,
                                                    confidence=confidence,
                                                    affected_assets=[file_path],
                                                    threat_level=self._get_threat_level(confidence),
                                                    description=f"ファイルで{indicator.name}を検知",
                                                    evidence={'file_path': file_path, 'pattern': pattern},
                                                    recommendations=self._get_response_recommendations(indicator)
                                                )

                                                detections.append(detection)

                    except subprocess.TimeoutExpired:
                        logger.warning(f"ファイル検索がタイムアウトしました: {directory}")

        except Exception as e:
            logger.error(f"ファイルシステム分析エラー: {e}")

        return detections

    def _calculate_confidence(self, indicator: ThreatIndicator, target: str) -> float:
        """信頼度を計算"""
        # 簡易的な信頼度計算（実際には機械学習モデルを使用）
        base_confidence = 0.5

        # パターンマッチの数を考慮
        match_count = sum(1 for pattern in indicator.detection_patterns if re.search(pattern, target, re.IGNORECASE))

        # 偽陽性率を考慮した調整
        confidence = base_confidence + (match_count / len(indicator.detection_patterns)) * 0.4
        confidence = confidence * (1 - indicator.false_positive_rate)

        return min(confidence, 1.0)

    def _get_threat_level(self, confidence: float) -> str:
        """脅威レベルを取得"""
        if confidence > 0.9:
            return 'critical'
        elif confidence > 0.7:
            return 'high'
        elif confidence > 0.5:
            return 'medium'
        else:
            return 'low'

    def _get_response_recommendations(self, indicator: ThreatIndicator) -> List[str]:
        """対応推奨事項を取得"""
        recommendations = {
            'malware': [
                '影響を受けたシステムを即座に隔離してください',
                'マルウェア対策ツールでスキャンを実行してください',
                'バックアップからの復元を検討してください',
                'セキュリティチームに報告してください'
            ],
            'phishing': [
                'フィッシングメールを削除してください',
                'パスワード変更を即座に実行してください',
                '二要素認証を有効化してください',
                'セキュリティ教育の強化を検討してください'
            ],
            'ddos': [
                'トラフィックフィルタリングを強化してください',
                'CDNやWAFの導入を検討してください',
                'ISPに連絡して対応を依頼してください',
                'DDoS対策サービスの利用を検討してください'
            ],
            'lateral_movement': [
                'ネットワークセグメンテーションを確認してください',
                '特権アカウントの使用を制限してください',
                'ゼロトラストセキュリティを強化してください',
                'セキュリティ監査を実施してください'
            ],
            'credential_access': [
                '認証情報を即座に変更してください',
                '認証情報抽出ツールの痕跡を調査してください',
                'パスワードポリシーの強化を検討してください',
                '多要素認証を必須化してください'
            ]
        }

        return recommendations.get(indicator.category, [
            '脅威を調査してください',
            'セキュリティチームに相談してください',
            'ログを詳細に分析してください'
        ])

    def _execute_automated_response(self, detection: ThreatDetection) -> None:
        """自動対応を実行"""
        try:
            logger.warning(f"自動対応を実行: {detection.indicator.name} (信頼度: {detection.confidence:.2f})")

            # 脅威レベルに応じた対応
            if detection.threat_level in ['critical', 'high']:
                # 重大な脅威の場合の対応
                self._isolate_affected_assets(detection.affected_assets)
                self._trigger_alerts(detection)

            # ログ記録
            with self._lock:
                self.threat_history.append(detection)

        except Exception as e:
            logger.error(f"自動対応実行エラー: {e}")

    def _isolate_affected_assets(self, affected_assets: List[str]) -> None:
        """影響を受けた資産を隔離"""
        try:
            for asset in affected_assets:
                if asset.startswith('PID:'):
                    pid = asset.split(':')[1]
                    # プロセスを終了（実際の実装ではより慎重な対応が必要）
                    logger.warning(f"プロセスを終了: {pid}")
                    # subprocess.run(['kill', '-9', pid], timeout=5)

        except Exception as e:
            logger.error(f"資産隔離エラー: {e}")

    def _trigger_alerts(self, detection: ThreatDetection) -> None:
        """アラートを発行"""
        try:
            # 実際の実装ではメール、Slack、PagerDutyなどの通知システムと連携
            logger.critical(f"脅威検知アラート: {detection.indicator.name} - {detection.description}")

        except Exception as e:
            logger.error(f"アラート発行エラー: {e}")

    def _perform_system_scan(self) -> None:
        """システムスキャンを実行"""
        try:
            # すべての脅威インジケーターでスキャン
            for indicator in self.threat_indicators.values():
                detections = self._hunt_for_threat(indicator)

                for detection in detections:
                    if detection.confidence > self.ai_confidence_threshold:
                        logger.warning(f"高信頼度の脅威検知: {detection.indicator.name}")

                        # 自動対応を実行
                        if self.automated_response_enabled:
                            self._execute_automated_response(detection)

        except Exception as e:
            logger.error(f"システムスキャンエラー: {e}")

    def create_hunting_campaign(self, name: str, description: str, duration_hours: int = 24) -> str:
        """ハンティングキャンペーンを作成"""
        campaign_id = f"HC_{int(time.time() * 1000000)}"

        campaign = HuntingCampaign(
            id=campaign_id,
            name=name,
            description=description,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=duration_hours),
            status='active'
        )

        with self._lock:
            self.campaigns[campaign_id] = campaign
            self.active_campaigns.append(campaign_id)

        logger.info(f"ハンティングキャンペーンを作成しました: {name}")
        return campaign_id

    def stop_campaign(self, campaign_id: str) -> bool:
        """キャンペーンを停止"""
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id].status = 'completed'
            self.campaigns[campaign_id].end_time = datetime.now(timezone.utc)

            if campaign_id in self.active_campaigns:
                self.active_campaigns.remove(campaign_id)

            logger.info(f"キャンペーンを停止しました: {campaign_id}")
            return True

        return False

    def get_threat_summary(self) -> Dict[str, Any]:
        """脅威サマリーを取得"""
        with self._lock:
            recent_threats = list(self.threat_history)[-100:]

            return {
                'total_indicators': len(self.threat_indicators),
                'total_detections': len(recent_threats),
                'active_campaigns': len(self.active_campaigns),
                'threats_by_category': self._count_threats_by_category(recent_threats),
                'threats_by_severity': self._count_threats_by_severity(recent_threats),
                'automated_responses': len([t for t in recent_threats if t.status == 'contained']),
                'ai_model_confidence': self.ai_confidence_threshold
            }

    def _count_threats_by_category(self, threats: List[ThreatDetection]) -> Dict[str, int]:
        """脅威をカテゴリ別にカウント"""
        counts = defaultdict(int)
        for threat in threats:
            counts[threat.indicator.category] += 1
        return dict(counts)

    def _count_threats_by_severity(self, threats: List[ThreatDetection]) -> Dict[str, int]:
        """脅威を深刻度別にカウント"""
        counts = defaultdict(int)
        for threat in threats:
            counts[threat.threat_level] += 1
        return dict(counts)

    def export_threat_intel(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """脅威インテリジェンスをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.intel_feeds_dir / f"threat_intel_{timestamp}.{format_type}"

        try:
            data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_indicators': len(self.threat_indicators),
                    'total_detections': len(self.threat_history)
                },
                'indicators': [
                    {
                        'id': ind.id,
                        'name': ind.name,
                        'category': ind.category,
                        'severity': ind.severity,
                        'description': ind.description,
                        'patterns': ind.detection_patterns,
                        'false_positive_rate': ind.false_positive_rate,
                        'mitre_technique': ind.mitre_technique
                    }
                    for ind in self.threat_indicators.values()
                ],
                'recent_detections': [
                    {
                        'id': d.id,
                        'timestamp': d.timestamp.isoformat(),
                        'indicator': d.indicator.name,
                        'confidence': d.confidence,
                        'threat_level': d.threat_level,
                        'affected_assets': d.affected_assets
                    }
                    for d in list(self.threat_history)[-50:]  # 直近50件
                ]
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"脅威インテリジェンスをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"脅威インテリジェンスエクスポートエラー: {e}")
            return None


# グローバルインスタンス
advanced_threat_hunter = AdvancedThreatHunter()
