"""
AI駆動の予測メンテナンスシステム - Moni System Monitor

機械学習による異常検知と予測メンテナンスを提供します。
"""

from __future__ import annotations

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
class AnomalyDetectionResult:
    """異常検知結果"""
    timestamp: datetime
    metric_name: str
    current_value: float
    predicted_value: float
    anomaly_score: float
    is_anomaly: bool
    confidence: float
    root_cause: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)


@dataclass
class MaintenancePrediction:
    """メンテナンス予測"""
    component: str
    predicted_failure_time: datetime
    failure_probability: float
    time_to_failure_days: float
    recommended_actions: List[str]
    urgency_level: str  # low, medium, high, critical


class PredictiveMaintenanceAI:
    """AI駆動の予測メンテナンスシステム"""

    def __init__(self, models_dir: Optional[Union[str, Path]] = None):
        self.models_dir = Path(models_dir) if models_dir else Path(__file__).parent / "ml_models"
        self.models_dir.mkdir(exist_ok=True)

        # メトリクス履歴
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.anomaly_threshold = 0.75  # 異常スコアの閾値
        self.prediction_window_hours = 24

        # 機械学習モデル（簡易実装）
        self.models: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # 学習データ収集の開始
        self._start_data_collection()

    def _start_data_collection(self) -> None:
        """データ収集を開始"""
        def collect_loop():
            while True:
                try:
                    self._collect_system_metrics()
                    time.sleep(60)  # 1分ごとに収集
                except Exception as e:
                    logger.error(f"メトリクス収集エラー: {e}")
                    time.sleep(300)  # エラー時は5分待機

        collect_thread = threading.Thread(target=collect_loop, daemon=True)
        collect_thread.start()
        logger.info("予測メンテナンスのデータ収集を開始しました。")

    def _collect_system_metrics(self) -> None:
        """システムメトリクスを収集"""
        try:
            import psutil

            timestamp = datetime.now(timezone.utc)

            # CPUメトリクス
            cpu_percent = psutil.cpu_percent(interval=1)
            self._add_metric('cpu_usage', cpu_percent, timestamp)

            # メモリメトリクス
            memory = psutil.virtual_memory()
            self._add_metric('memory_usage', memory.percent, timestamp)
            self._add_metric('memory_available', memory.available / 1024 / 1024, timestamp)  # MB

            # ディスクメトリクス
            disk = psutil.disk_usage('/')
            self._add_metric('disk_usage', disk.percent, timestamp)
            self._add_metric('disk_free', disk.free / 1024 / 1024 / 1024, timestamp)  # GB

            # ネットワークメトリクス
            network = psutil.net_io_counters()
            self._add_metric('network_bytes_sent', network.bytes_sent, timestamp)
            self._add_metric('network_bytes_recv', network.bytes_recv, timestamp)

            # プロセスメトリクス
            process_count = len(psutil.pids())
            self._add_metric('process_count', process_count, timestamp)

            # ロードアベレージ（Linuxの場合）
            try:
                import os
                if hasattr(os, 'getloadavg'):
                    load1, load5, load15 = os.getloadavg()
                    self._add_metric('load_average_1m', load1, timestamp)
                    self._add_metric('load_average_5m', load5, timestamp)
                    self._add_metric('load_average_15m', load15, timestamp)
            except:
                pass

        except Exception as e:
            logger.error(f"メトリクス収集エラー: {e}")

    def _add_metric(self, name: str, value: float, timestamp: datetime) -> None:
        """メトリクスを追加"""
        with self._lock:
            self.metric_history[name].append({
                'timestamp': timestamp,
                'value': value
            })

    def detect_anomalies(self, metric_name: str) -> List[AnomalyDetectionResult]:
        """異常を検知"""
        results = []

        if metric_name not in self.metric_history:
            return results

        history = list(self.metric_history[metric_name])

        if len(history) < 10:  # 最低10個のデータが必要
            return results

        try:
            # 統計的異常検知（簡易版）
            values = [item['value'] for item in history[-100:]]  # 直近100個の値

            # 基本統計量を計算
            mean_val = statistics.mean(values)
            std_val = statistics.stdev(values) if len(values) > 1 else 1.0

            # 直近の値を取得
            latest_item = history[-1]
            current_value = latest_item['value']

            # 予測値（移動平均）
            window_size = min(10, len(values))
            predicted_value = statistics.mean(values[-window_size:])

            # 異常スコアを計算
            if std_val > 0:
                anomaly_score = abs(current_value - predicted_value) / std_val
            else:
                anomaly_score = 0.0

            # Zスコアによる異常判定
            z_score = abs(current_value - mean_val) / std_val if std_val > 0 else 0

            is_anomaly = anomaly_score > self.anomaly_threshold or z_score > 2.5

            result = AnomalyDetectionResult(
                timestamp=latest_item['timestamp'],
                metric_name=metric_name,
                current_value=current_value,
                predicted_value=predicted_value,
                anomaly_score=anomaly_score,
                is_anomaly=is_anomaly,
                confidence=min(anomaly_score, 1.0),
                root_cause=self._analyze_root_cause(metric_name, current_value, predicted_value),
                recommendations=self._generate_recommendations(metric_name, is_anomaly, anomaly_score)
            )

            results.append(result)

        except Exception as e:
            logger.error(f"異常検知エラー ({metric_name}): {e}")

        return results

    def _analyze_root_cause(self, metric_name: str, current: float, predicted: float) -> Optional[str]:
        """根本原因を分析"""
        diff = abs(current - predicted)

        if metric_name == 'cpu_usage' and diff > 20:
            return '高負荷プロセスまたはリソース競合の可能性'
        elif metric_name == 'memory_usage' and diff > 15:
            return 'メモリリークまたは過剰なメモリ使用の可能性'
        elif metric_name == 'disk_usage' and diff > 10:
            return 'ディスク容量不足またはログ蓄積の可能性'
        elif metric_name.startswith('network_') and diff > 1000000:  # 1MB
            return 'ネットワークトラフィックの異常増加'

        return None

    def _generate_recommendations(self, metric_name: str, is_anomaly: bool, score: float) -> List[str]:
        """推奨事項を生成"""
        recommendations = []

        if not is_anomaly:
            return recommendations

        if metric_name == 'cpu_usage':
            if score > 0.9:
                recommendations.extend([
                    '高負荷プロセスの特定と最適化を実施してください',
                    'CPU使用率の制限設定を検討してください',
                    'スケーリング設定の見直しを推奨します'
                ])
        elif metric_name == 'memory_usage':
            if score > 0.9:
                recommendations.extend([
                    'メモリ使用量の多いプロセスを調査してください',
                    'メモリリークの可能性をチェックしてください',
                    'スワップ領域の増設を検討してください'
                ])
        elif metric_name == 'disk_usage':
            if score > 0.9:
                recommendations.extend([
                    '不要なファイルやログのクリーンアップを実施してください',
                    'ディスク容量の増設を検討してください',
                    'バックアップ戦略の見直しを推奨します'
                ])

        return recommendations

    def predict_maintenance(self, component: str) -> Optional[MaintenancePrediction]:
        """メンテナンスを予測"""
        try:
            if component not in self.metric_history:
                return None

            history = list(self.metric_history[component])
            if len(history) < 50:  # 最低50個のデータが必要
                return None

            # トレンド分析（簡易線形回帰）
            values = [item['value'] for item in history[-100:]]
            timestamps = [(item['timestamp'].timestamp() - history[0]['timestamp'].timestamp()) / 3600 for item in history[-100:]]

            if len(values) < 10:
                return None

            # 線形回帰の簡易計算
            n = len(values)
            sum_x = sum(timestamps)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(timestamps, values))
            sum_x2 = sum(x * x for x in timestamps)

            if n * sum_x2 - sum_x * sum_x == 0:
                return None

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n

            # 現在のトレンドに基づいて予測
            current_time = time.time()
            base_timestamp = history[0]['timestamp'].timestamp()

            # しきい値到達時間の予測
            threshold_values = self._get_thresholds(component)

            predictions = []
            for threshold_name, threshold_value in threshold_values.items():
                if slope > 0:  # 上昇傾向
                    hours_to_threshold = (threshold_value - intercept) / slope if slope > 0 else float('inf')
                else:
                    hours_to_threshold = float('inf')

                if hours_to_threshold < float('inf'):
                    predicted_time = datetime.fromtimestamp(base_timestamp + hours_to_threshold * 3600, timezone.utc)

                    # 故障確率を計算（簡易版）
                    current_value = values[-1]
                    failure_probability = min(1.0, (current_value / threshold_value) * 0.8)

                    prediction = MaintenancePrediction(
                        component=component,
                        predicted_failure_time=predicted_time,
                        failure_probability=failure_probability,
                        time_to_failure_days=hours_to_threshold / 24,
                        recommended_actions=self._get_maintenance_actions(component, failure_probability),
                        urgency_level=self._get_urgency_level(failure_probability, hours_to_threshold / 24)
                    )

                    predictions.append(prediction)

            # 最も緊急性の高い予測を返す
            if predictions:
                return max(predictions, key=lambda p: p.failure_probability)

        except Exception as e:
            logger.error(f"メンテナンス予測エラー ({component}): {e}")

        return None

    def _get_thresholds(self, component: str) -> Dict[str, float]:
        """コンポーネントのしきい値を取得"""
        thresholds = {
            'cpu_usage': {'warning': 80.0, 'critical': 95.0},
            'memory_usage': {'warning': 85.0, 'critical': 95.0},
            'disk_usage': {'warning': 80.0, 'critical': 95.0},
            'network_bytes_sent': {'warning': 1000000000, 'critical': 5000000000},  # 1GB, 5GB
            'network_bytes_recv': {'warning': 1000000000, 'critical': 5000000000},
            'process_count': {'warning': 1000, 'critical': 2000},
            'load_average_1m': {'warning': 2.0, 'critical': 5.0}
        }

        return thresholds.get(component, {'warning': 80.0, 'critical': 95.0})

    def _get_maintenance_actions(self, component: str, probability: float) -> List[str]:
        """メンテナンスアクションを取得"""
        actions = {
            'cpu_usage': [
                'CPU使用率の高いプロセスを特定・最適化してください',
                '負荷分散設定の見直しを検討してください',
                'スケーリングポリシーの調整を推奨します'
            ],
            'memory_usage': [
                'メモリ使用量の多いプロセスを調査してください',
                'メモリリークの可能性をチェックしてください',
                'メモリ制限設定の調整を検討してください'
            ],
            'disk_usage': [
                'ディスククリーンアップを実施してください',
                'ログローテーション設定を確認してください',
                'ストレージ容量の増設を検討してください'
            ]
        }

        return actions.get(component, ['システムの状態を監視してください'])

    def _get_urgency_level(self, probability: float, days_to_failure: float) -> str:
        """緊急レベルを取得"""
        if probability > 0.8 and days_to_failure < 1:
            return 'critical'
        elif probability > 0.6 and days_to_failure < 7:
            return 'high'
        elif probability > 0.4 and days_to_failure < 30:
            return 'medium'
        else:
            return 'low'

    def get_anomaly_report(self) -> Dict[str, Any]:
        """異常レポートを取得"""
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_metrics_tracked': len(self.metric_history),
            'anomalies_detected': 0,
            'predictions': [],
            'metrics_summary': {}
        }

        # 各メトリクスをチェック
        for metric_name in self.metric_history.keys():
            anomalies = self.detect_anomalies(metric_name)
            anomaly_count = len([a for a in anomalies if a.is_anomaly])

            report['anomalies_detected'] += anomaly_count

            # メンテナンス予測
            prediction = self.predict_maintenance(metric_name)
            if prediction:
                report['predictions'].append({
                    'component': prediction.component,
                    'failure_probability': prediction.failure_probability,
                    'time_to_failure_days': prediction.time_to_failure_days,
                    'urgency_level': prediction.urgency_level
                })

            # メトリクスの統計情報
            values = [item['value'] for item in self.metric_history[metric_name]]
            if values:
                report['metrics_summary'][metric_name] = {
                    'count': len(values),
                    'mean': statistics.mean(values),
                    'std': statistics.stdev(values) if len(values) > 1 else 0,
                    'min': min(values),
                    'max': max(values)
                }

        return report

    def export_training_data(self, file_path: Optional[Path] = None) -> Optional[str]:
        """学習データをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.models_dir / f"training_data_{timestamp}.json"

        try:
            training_data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'metrics_count': len(self.metric_history),
                    'total_samples': sum(len(history) for history in self.metric_history.values())
                },
                'metrics': {}
            }

            for metric_name, history in self.metric_history.items():
                training_data['metrics'][metric_name] = list(history)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(training_data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"学習データをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"学習データエクスポートエラー: {e}")
            return None


# グローバルインスタンス
predictive_maintenance_ai = PredictiveMaintenanceAI()
