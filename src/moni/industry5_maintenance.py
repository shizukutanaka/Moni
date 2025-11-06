"""
Industry 5.0予測メンテナンスシステム - Moni System Monitor

人間中心のスマート製造業向け予測メンテナンスを提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class HumanMachineCollaboration:
    """人間機械協調データ"""
    operator_id: str
    machine_id: str
    collaboration_score: float
    human_feedback: str
    machine_suggestion: str
    final_decision: str
    decision_timestamp: datetime
    outcome_rating: Optional[int] = None


@dataclass
class IndustryAsset:
    """産業資産"""
    id: str
    name: str
    asset_type: str  # machine, sensor, production_line, etc.
    location: str
    criticality: str  # low, medium, high, critical
    installation_date: datetime
    last_maintenance: Optional[datetime]
    expected_lifespan_days: int
    sensors: List[str] = field(default_factory=list)
    operators: List[str] = field(default_factory=list)


@dataclass
class PredictiveMaintenanceEvent:
    """予測メンテナンスイベント"""
    id: str
    asset_id: str
    event_type: str  # maintenance_due, anomaly_detected, efficiency_drop, etc.
    predicted_time: datetime
    confidence: float
    severity: str
    description: str
    ai_analysis: Dict[str, Any]
    human_input_required: bool
    recommended_actions: List[str]
    assigned_operator: Optional[str] = None
    status: str = 'pending'  # pending, in_progress, completed, cancelled


class Industry5MaintenanceSystem:
    """Industry 5.0予測メンテナンスシステム"""

    def __init__(self, industry_data_dir: Optional[Union[str, Path]] = None):
        self.industry_data_dir = Path(industry_data_dir) if industry_data_dir else Path(__file__).parent / "industry_data"
        self.industry_data_dir.mkdir(exist_ok=True)

        # 産業資産
        self.assets: Dict[str, IndustryAsset] = {}
        self.collaborations: List[HumanMachineCollaboration] = []
        self.maintenance_events: Dict[str, PredictiveMaintenanceEvent] = {}

        # センサーデータ履歴
        self.sensor_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

        # 機械学習モデル（Industry 5.0向け）
        self.human_ai_models: Dict[str, Any] = {}

        # 協調スコア
        self.collaboration_metrics: Dict[str, float] = defaultdict(float)

        self._lock = threading.Lock()

        # 産業資産の初期化
        self._init_industry_assets()

        # データ収集の開始
        self._start_industry_monitoring()

    def _init_industry_assets(self) -> None:
        """産業資産を初期化"""
        # サンプル産業資産（実際の実装ではデータベースから読み込み）
        sample_assets = [
            IndustryAsset(
                id='MACHINE_001',
                name='CNCマシンA',
                asset_type='cnc_machine',
                location='工場Aライン1',
                criticality='high',
                installation_date=datetime.now(timezone.utc) - timedelta(days=1000),
                last_maintenance=datetime.now(timezone.utc) - timedelta(days=30),
                expected_lifespan_days=3650,  # 10年
                sensors=['temperature', 'vibration', 'pressure', 'current'],
                operators=['operator_001', 'operator_002']
            ),
            IndustryAsset(
                id='SENSOR_001',
                name='温度センサーT1',
                asset_type='temperature_sensor',
                location='工場Aライン1マシンA',
                criticality='medium',
                installation_date=datetime.now(timezone.utc) - timedelta(days=500),
                last_maintenance=datetime.now(timezone.utc) - timedelta(days=90),
                expected_lifespan_days=1825,  # 5年
                sensors=['temperature'],
                operators=['operator_001']
            ),
            IndustryAsset(
                id='PRODUCTION_LINE_001',
                name='生産ライン1',
                asset_type='production_line',
                location='工場A',
                criticality='critical',
                installation_date=datetime.now(timezone.utc) - timedelta(days=2000),
                last_maintenance=datetime.now(timezone.utc) - timedelta(days=60),
                expected_lifespan_days=7300,  # 20年
                sensors=['flow_rate', 'pressure', 'quality', 'throughput'],
                operators=['supervisor_001', 'operator_001', 'operator_002', 'operator_003']
            )
        ]

        with self._lock:
            self.assets = {asset.id: asset for asset in sample_assets}

        logger.info(f"{len(sample_assets)}個の産業資産を初期化しました。")

    def _start_industry_monitoring(self) -> None:
        """産業監視を開始"""
        def monitoring_loop():
            while True:
                try:
                    self._collect_sensor_data()
                    self._analyze_asset_health()
                    self._generate_maintenance_predictions()
                    time.sleep(60)  # 1分ごとに実行
                except Exception as e:
                    logger.error(f"産業監視エラー: {e}")
                    time.sleep(300)  # エラー時は5分待機

        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        logger.info("Industry 5.0予測メンテナンス監視を開始しました。")

    def _collect_sensor_data(self) -> None:
        """センサーデータを収集"""
        try:
            # 各資産のセンサーデータを収集（モック実装）
            for asset in self.assets.values():
                for sensor in asset.sensors:
                    # 実際の実装ではIoTセンサーからデータを取得
                    sensor_value = self._generate_mock_sensor_data(sensor, asset.asset_type)

                    timestamp = datetime.now(timezone.utc)
                    data_point = {
                        'timestamp': timestamp,
                        'value': sensor_value,
                        'asset_id': asset.id,
                        'sensor_type': sensor
                    }

                    with self._lock:
                        self.sensor_data[sensor].append(data_point)

        except Exception as e:
            logger.error(f"センサーデータ収集エラー: {e}")

    def _generate_mock_sensor_data(self, sensor_type: str, asset_type: str) -> float:
        """モックセンサーデータを生成"""
        # 実際の実装では実際のセンサーからデータを取得
        base_values = {
            'temperature': 25.0,
            'vibration': 0.1,
            'pressure': 101.3,
            'current': 5.0,
            'flow_rate': 100.0,
            'quality': 95.0,
            'throughput': 1000.0
        }

        base_value = base_values.get(sensor_type, 50.0)

        # ランダム変動を追加（異常シミュレーション）
        import random
        variation = random.uniform(-0.1, 0.1) * base_value

        # 特定の条件下で異常値を生成
        if random.random() < 0.05:  # 5%の確率で異常
            variation += random.uniform(0.3, 0.5) * base_value

        return base_value + variation

    def _analyze_asset_health(self) -> None:
        """資産の健全性を分析"""
        try:
            for asset in self.assets.values():
                health_score = self._calculate_asset_health_score(asset)

                # 健全性スコアが低い場合、予測イベントを生成
                if health_score < 0.7:  # 70%未満で警告
                    event = PredictiveMaintenanceEvent(
                        id=f"PME_{int(time.time() * 1000000)}",
                        asset_id=asset.id,
                        event_type='health_degradation',
                        predicted_time=datetime.now(timezone.utc) + timedelta(hours=24),
                        confidence=0.8,
                        severity='medium' if health_score > 0.5 else 'high',
                        description=f"資産{asset.name}の健全性が低下しています",
                        ai_analysis={
                            'health_score': health_score,
                            'degradation_factors': self._identify_degradation_factors(asset),
                            'remaining_life_days': self._estimate_remaining_life(asset)
                        },
                        human_input_required=True,
                        recommended_actions=self._get_maintenance_recommendations(asset, health_score)
                    )

                    with self._lock:
                        self.maintenance_events[event.id] = event

        except Exception as e:
            logger.error(f"資産健全性分析エラー: {e}")

    def _calculate_asset_health_score(self, asset: IndustryAsset) -> float:
        """資産の健全性スコアを計算"""
        try:
            health_factors = []

            # 年齢ベースの劣化（0-1のスコア）
            age_days = (datetime.now(timezone.utc) - asset.installation_date).days
            age_factor = max(0, 1 - (age_days / asset.expected_lifespan_days))
            health_factors.append(age_factor)

            # センサーデータベースの健全性
            for sensor in asset.sensors:
                if sensor in self.sensor_data:
                    recent_data = list(self.sensor_data[sensor])[-100:]  # 直近100データ

                    if recent_data:
                        values = [d['value'] for d in recent_data if d['asset_id'] == asset.id]

                        if values:
                            # データの安定性をチェック
                            if len(values) > 1:
                                std_dev = statistics.stdev(values)
                                mean_val = statistics.mean(values)

                                # 変動が大きいと健全性が低い
                                stability = max(0, 1 - (std_dev / mean_val))
                                health_factors.append(stability)

            # 最終スコア（平均値）
            return sum(health_factors) / len(health_factors) if health_factors else 0.5

        except Exception as e:
            logger.error(f"健全性スコア計算エラー ({asset.id}): {e}")
            return 0.5

    def _identify_degradation_factors(self, asset: IndustryAsset) -> List[str]:
        """劣化要因を特定"""
        factors = []

        try:
            # 年齢要因
            age_days = (datetime.now(timezone.utc) - asset.installation_date).days
            if age_days > asset.expected_lifespan_days * 0.8:
                factors.append('高経年劣化')

            # センサーデータ異常
            for sensor in asset.sensors:
                if sensor in self.sensor_data:
                    recent_data = list(self.sensor_data[sensor])[-50:]

                    if recent_data:
                        values = [d['value'] for d in recent_data if d['asset_id'] == asset.id]

                        if values:
                            # 異常値の検知
                            mean_val = statistics.mean(values)
                            std_val = statistics.stdev(values) if len(values) > 1 else 1

                            abnormal_count = sum(1 for v in values if abs(v - mean_val) > 2 * std_val)

                            if abnormal_count > len(values) * 0.1:  # 10%以上異常
                                factors.append(f'{sensor}センサーの異常値増加')

            # メンテナンス間隔
            if asset.last_maintenance:
                days_since_maintenance = (datetime.now(timezone.utc) - asset.last_maintenance).days
                if days_since_maintenance > 90:  # 90日以上
                    factors.append('メンテナンス間隔超過')

        except Exception as e:
            logger.error(f"劣化要因特定エラー ({asset.id}): {e}")

        return factors

    def _estimate_remaining_life(self, asset: IndustryAsset) -> int:
        """残存寿命を推定（日数）"""
        try:
            age_days = (datetime.now(timezone.utc) - asset.installation_date).days
            remaining_days = asset.expected_lifespan_days - age_days

            # 健全性スコアに基づく調整
            health_score = self._calculate_asset_health_score(asset)
            adjusted_remaining = remaining_days * health_score

            return max(0, int(adjusted_remaining))

        except Exception:
            return asset.expected_lifespan_days // 2

    def _get_maintenance_recommendations(self, asset: IndustryAsset, health_score: float) -> List[str]:
        """メンテナンス推奨事項を取得"""
        recommendations = []

        if health_score < 0.5:
            recommendations.extend([
                f'{asset.name}の詳細点検を直ちに実施してください',
                '予防交換部品の準備をしてください',
                '予備機の準備を検討してください'
            ])
        elif health_score < 0.7:
            recommendations.extend([
                f'{asset.name}の状態監視を強化してください',
                '次回定期メンテナンスを前倒ししてください',
                '交換部品の手配を検討してください'
            ])
        else:
            recommendations.append(f'{asset.name}の状態は良好です。定期監視を継続してください。')

        return recommendations

    def _generate_maintenance_predictions(self) -> None:
        """メンテナンス予測を生成"""
        try:
            for asset in self.assets.values():
                # 故障予測モデルによる分析（簡易版）
                prediction = self._predict_asset_failure(asset)

                if prediction:
                    event = PredictiveMaintenanceEvent(
                        id=f"PME_{int(time.time() * 1000000)}",
                        asset_id=asset.id,
                        event_type='predicted_failure',
                        predicted_time=prediction['failure_time'],
                        confidence=prediction['confidence'],
                        severity=self._get_severity_from_confidence(prediction['confidence']),
                        description=f"資産{asset.name}の故障が予測されます",
                        ai_analysis=prediction,
                        human_input_required=True,
                        recommended_actions=prediction['actions']
                    )

                    with self._lock:
                        self.maintenance_events[event.id] = event

        except Exception as e:
            logger.error(f"メンテナンス予測生成エラー: {e}")

    def _predict_asset_failure(self, asset: IndustryAsset) -> Optional[Dict[str, Any]]:
        """資産故障を予測"""
        try:
            # 簡易的な故障予測モデル（実際には機械学習モデルを使用）
            health_score = self._calculate_asset_health_score(asset)

            if health_score < 0.6:  # 60%未満で予測
                # 残存寿命に基づく予測
                remaining_days = self._estimate_remaining_life(asset)

                if remaining_days < 30:  # 30日以内に故障予測
                    return {
                        'failure_time': datetime.now(timezone.utc) + timedelta(days=remaining_days),
                        'confidence': min(0.9, 1 - health_score),
                        'failure_mode': 'degradation',
                        'risk_factors': self._identify_degradation_factors(asset),
                        'actions': [
                            '予防メンテナンスの実施を推奨します',
                            '部品交換の準備をしてください',
                            '運用負荷の軽減を検討してください'
                        ]
                    }

        except Exception as e:
            logger.error(f"故障予測エラー ({asset.id}): {e}")

        return None

    def _get_severity_from_confidence(self, confidence: float) -> str:
        """信頼度から深刻度を取得"""
        if confidence > 0.8:
            return 'critical'
        elif confidence > 0.6:
            return 'high'
        elif confidence > 0.4:
            return 'medium'
        else:
            return 'low'

    def record_human_machine_collaboration(self, collaboration: HumanMachineCollaboration) -> None:
        """人間機械協調を記録"""
        try:
            with self._lock:
                self.collaborations.append(collaboration)

            # 協調スコアを更新
            key = f"{collaboration.operator_id}_{collaboration.machine_id}"
            self.collaboration_metrics[key] = collaboration.collaboration_score

            logger.info(f"人間機械協調を記録しました: {collaboration.operator_id} - {collaboration.machine_id}")

        except Exception as e:
            logger.error(f"協調記録エラー: {e}")

    def get_collaboration_analytics(self) -> Dict[str, Any]:
        """協調分析を取得"""
        with self._lock:
            recent_collaborations = [
                c for c in self.collaborations
                if (datetime.now(timezone.utc) - c.decision_timestamp).days < 7
            ]

            return {
                'total_collaborations': len(recent_collaborations),
                'average_collaboration_score': statistics.mean([c.collaboration_score for c in recent_collaborations]) if recent_collaborations else 0,
                'human_override_rate': len([c for c in recent_collaborations if c.final_decision != c.machine_suggestion]) / len(recent_collaborations) if recent_collaborations else 0,
                'top_performing_operators': self._get_top_performing_operators(),
                'collaboration_trends': self._analyze_collaboration_trends()
            }

    def _get_top_performing_operators(self) -> List[Dict[str, Any]]:
        """高パフォーマンスオペレーターを取得"""
        operator_scores = defaultdict(list)

        for collaboration in self.collaborations[-100:]:  # 直近100件
            operator_scores[collaboration.operator_id].append(collaboration.collaboration_score)

        return [
            {
                'operator_id': op_id,
                'average_score': statistics.mean(scores),
                'collaboration_count': len(scores)
            }
            for op_id, scores in operator_scores.items()
            if len(scores) >= 5  # 最低5回の協調が必要
        ][:10]  # 上位10名

    def _analyze_collaboration_trends(self) -> Dict[str, Any]:
        """協調トレンドを分析"""
        # 簡易トレンド分析
        return {
            'improving_operators': [],
            'needs_training': [],
            'optimal_collaboration_rate': 0.75
        }

    def get_maintenance_dashboard(self) -> Dict[str, Any]:
        """メンテナンスダッシュボードを取得"""
        with self._lock:
            pending_events = [e for e in self.maintenance_events.values() if e.status == 'pending']
            in_progress_events = [e for e in self.maintenance_events.values() if e.status == 'in_progress']

            return {
                'assets': [
                    {
                        'id': a.id,
                        'name': a.name,
                        'type': a.asset_type,
                        'health_score': self._calculate_asset_health_score(a),
                        'remaining_life_days': self._estimate_remaining_life(a),
                        'criticality': a.criticality,
                        'status': 'healthy' if self._calculate_asset_health_score(a) > 0.7 else 'warning'
                    }
                    for a in self.assets.values()
                ],
                'maintenance_events': [
                    {
                        'id': e.id,
                        'asset_id': e.asset_id,
                        'type': e.event_type,
                        'predicted_time': e.predicted_time.isoformat(),
                        'confidence': e.confidence,
                        'severity': e.severity,
                        'status': e.status,
                        'human_input_required': e.human_input_required
                    }
                    for e in list(self.maintenance_events.values())[-50:]  # 直近50件
                ],
                'collaboration_metrics': self.get_collaboration_analytics(),
                'system_health': self._calculate_system_health()
            }

    def _calculate_system_health(self) -> Dict[str, Any]:
        """システム全体の健全性を計算"""
        total_assets = len(self.assets)
        healthy_assets = len([a for a in self.assets.values() if self._calculate_asset_health_score(a) > 0.7])
        pending_maintenance = len([e for e in self.maintenance_events.values() if e.status == 'pending'])

        return {
            'overall_health_score': healthy_assets / total_assets if total_assets > 0 else 0,
            'healthy_assets': healthy_assets,
            'total_assets': total_assets,
            'pending_maintenance_events': pending_maintenance,
            'system_status': 'optimal' if pending_maintenance == 0 else 'needs_attention'
        }

    def assign_maintenance_task(self, event_id: str, operator_id: str) -> bool:
        """メンテナンスタスクを割り当て"""
        if event_id not in self.maintenance_events:
            return False

        try:
            self.maintenance_events[event_id].assigned_operator = operator_id
            self.maintenance_events[event_id].status = 'in_progress'

            logger.info(f"メンテナンスタスクを割り当てました: {event_id} -> {operator_id}")
            return True

        except Exception as e:
            logger.error(f"タスク割り当てエラー: {e}")
            return False

    def record_maintenance_completion(self, event_id: str, outcome_rating: int, notes: str = '') -> bool:
        """メンテナンス完了を記録"""
        if event_id not in self.maintenance_events:
            return False

        try:
            event = self.maintenance_events[event_id]
            event.status = 'completed'
            event.outcome_rating = outcome_rating

            # 関連資産の最終メンテナンス日を更新
            if event.asset_id in self.assets:
                self.assets[event.asset_id].last_maintenance = datetime.now(timezone.utc)

            logger.info(f"メンテナンス完了を記録しました: {event_id}")
            return True

        except Exception as e:
            logger.error(f"メンテナンス完了記録エラー: {e}")
            return False

    def export_industry_data(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """産業データをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.industry_data_dir / f"industry5_data_{timestamp}.{format_type}"

        try:
            data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_assets': len(self.assets),
                    'total_maintenance_events': len(self.maintenance_events),
                    'total_collaborations': len(self.collaborations)
                },
                'assets': [
                    {
                        'id': a.id,
                        'name': a.name,
                        'type': a.asset_type,
                        'location': a.location,
                        'criticality': a.criticality,
                        'installation_date': a.installation_date.isoformat(),
                        'last_maintenance': a.last_maintenance.isoformat() if a.last_maintenance else None,
                        'health_score': self._calculate_asset_health_score(a),
                        'remaining_life_days': self._estimate_remaining_life(a)
                    }
                    for a in self.assets.values()
                ],
                'maintenance_events': [
                    {
                        'id': e.id,
                        'asset_id': e.asset_id,
                        'type': e.event_type,
                        'predicted_time': e.predicted_time.isoformat(),
                        'confidence': e.confidence,
                        'severity': e.severity,
                        'status': e.status,
                        'assigned_operator': e.assigned_operator
                    }
                    for e in self.maintenance_events.values()
                ]
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"産業データをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"産業データエクスポートエラー: {e}")
            return None


# グローバルインスタンス
industry5_maintenance = Industry5MaintenanceSystem()
