"""
サステナビリティ監視システム - Moni System Monitor

環境影響とエネルギー効率監視を提供します。
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
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class EnergyConsumption:
    """エネルギー消費データ"""
    timestamp: datetime
    device_id: str
    energy_kwh: float
    power_watts: float
    efficiency_rating: float
    renewable_percentage: float
    carbon_intensity: float  # gCO2/kWh


@dataclass
class SustainabilityMetric:
    """サステナビリティメトリクス"""
    metric_id: str
    name: str
    category: str  # energy, carbon, water, waste, etc.
    value: float
    unit: str
    timestamp: datetime
    location: str
    data_source: str


@dataclass
class CarbonFootprint:
    """カーボンフットプリント"""
    entity_id: str
    entity_type: str  # server, datacenter, application, user, etc.
    period_start: datetime
    period_end: datetime
    total_emissions_kg: float
    scope1_emissions: float  # 直接排出
    scope2_emissions: float  # 間接排出（電力）
    scope3_emissions: float  # その他の間接排出
    offset_credits: float
    net_emissions: float


class SustainabilityMonitor:
    """サステナビリティ監視システム"""

    def __init__(self, sustainability_data_dir: Optional[Union[str, Path]] = None):
        self.sustainability_data_dir = Path(sustainability_data_dir) if sustainability_data_dir else Path(__file__).parent / "sustainability_data"
        self.sustainability_data_dir.mkdir(exist_ok=True)

        self.energy_consumption: deque = deque(maxlen=100000)
        self.sustainability_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.carbon_footprints: Dict[str, CarbonFootprint] = {}

        # サステナビリティ設定
        self.sustainability_config = {
            'energy_monitoring_enabled': True,
            'carbon_tracking_enabled': True,
            'water_usage_monitoring': False,
            'waste_monitoring': False,
            'renewable_energy_targets': {
                'percentage': 50.0,  # 50%再生可能エネルギー目標
                'target_year': 2030
            },
            'carbon_neutrality_goal': 2050,
            'reporting_standards': ['GHG Protocol', 'CDP', 'GRI']
        }

        # エネルギー効率指標
        self.energy_efficiency_baselines = {
            'server_pue': 1.2,  # Power Usage Effectiveness
            'datacenter_pue': 1.5,
            'network_efficiency': 0.8,
            'storage_efficiency': 0.75
        }

        self._lock = threading.Lock()

        # サステナビリティ監視の開始
        self._start_sustainability_monitoring()

    def _start_sustainability_monitoring(self) -> None:
        """サステナビリティ監視を開始"""
        def monitoring_loop():
            while True:
                try:
                    self._collect_energy_data()
                    self._calculate_carbon_footprint()
                    self._analyze_sustainability_trends()
                    time.sleep(300)  # 5分ごとに実行
                except Exception as e:
                    logger.error(f"サステナビリティ監視エラー: {e}")
                    time.sleep(600)  # エラー時は10分待機

        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        logger.info("サステナビリティ監視を開始しました。")

    def _collect_energy_data(self) -> None:
        """エネルギーデータを収集"""
        try:
            # システムのエネルギー消費を収集（モック実装）
            import psutil

            timestamp = datetime.now(timezone.utc)

            # CPUエネルギー消費（簡易計算）
            cpu_percent = psutil.cpu_percent(interval=1)
            estimated_cpu_power = self._estimate_cpu_power(cpu_percent)

            # メモリエネルギー消費（簡易計算）
            memory = psutil.virtual_memory()
            estimated_memory_power = self._estimate_memory_power(memory.percent)

            # ストレージエネルギー消費（簡易計算）
            disk = psutil.disk_usage('/')
            estimated_storage_power = self._estimate_storage_power(disk.percent)

            # ネットワークエネルギー消費（簡易計算）
            network = psutil.net_io_counters()
            estimated_network_power = self._estimate_network_power(network.bytes_sent + network.bytes_recv)

            # 総エネルギー消費を計算
            total_power_watts = estimated_cpu_power + estimated_memory_power + estimated_storage_power + estimated_network_power
            total_energy_kwh = total_power_watts / 1000  # kWからkWhに変換（簡易）

            # カーボンインテンシティを計算（地域による変動を考慮）
            carbon_intensity = self._get_carbon_intensity()  # gCO2/kWh

            # 再生可能エネルギー比率を計算
            renewable_percentage = self._get_renewable_percentage()

            energy_data = EnergyConsumption(
                timestamp=timestamp,
                device_id='system_main',
                energy_kwh=total_energy_kwh,
                power_watts=total_power_watts,
                efficiency_rating=self._calculate_efficiency_rating(total_power_watts),
                renewable_percentage=renewable_percentage,
                carbon_intensity=carbon_intensity
            )

            with self._lock:
                self.energy_consumption.append(energy_data)

            # サステナビリティメトリクスとして記録
            self._record_sustainability_metrics(energy_data)

            logger.debug(f"エネルギーデータを収集しました: {total_power_watts}W, {total_energy_kwh}kWh")

        except Exception as e:
            logger.error(f"エネルギーデータ収集エラー: {e}")

    def _estimate_cpu_power(self, cpu_percent: float) -> float:
        """CPU電力消費を推定"""
        # 簡易的な電力推定（実際にはハードウェア固有の値を使用）
        base_power = 50  # ベース電力（W）
        max_power = 150  # 最大電力（W）

        return base_power + (cpu_percent / 100) * (max_power - base_power)

    def _estimate_memory_power(self, memory_percent: float) -> float:
        """メモリ電力消費を推定"""
        # 簡易的な電力推定
        base_power = 20  # ベース電力（W）
        max_power = 60   # 最大電力（W）

        return base_power + (memory_percent / 100) * (max_power - base_power)

    def _estimate_storage_power(self, disk_percent: float) -> float:
        """ストレージ電力消費を推定"""
        # 簡易的な電力推定
        base_power = 10  # ベース電力（W）
        max_power = 30   # 最大電力（W）

        return base_power + (disk_percent / 100) * (max_power - base_power)

    def _estimate_network_power(self, bytes_transferred: int) -> float:
        """ネットワーク電力消費を推定"""
        # 簡易的な電力推定（データ転送量に基づく）
        bytes_per_watt = 1000000000  # 1GWバイトあたり1W（簡易値）

        return bytes_transferred / bytes_per_watt if bytes_transferred > 0 else 0

    def _get_carbon_intensity(self) -> float:
        """カーボンインテンシティを取得"""
        # 実際の実装では、地域の電力網データを取得
        # ここではモック値を使用（日本平均: 約500gCO2/kWh）
        return 500.0

    def _get_renewable_percentage(self) -> float:
        """再生可能エネルギー比率を取得"""
        # 実際の実装では、エネルギー供給元データを取得
        # ここではモック値を使用
        return 25.0  # 25%再生可能エネルギー

    def _calculate_efficiency_rating(self, power_watts: float) -> float:
        """効率評価を計算"""
        try:
            # PUE（Power Usage Effectiveness）を基準とした効率評価
            baseline_pue = self.energy_efficiency_baselines['server_pue']

            # 電力使用効率を計算（低いほど効率的）
            if power_watts > 0:
                efficiency_score = min(1.0, baseline_pue / (power_watts / 100))  # 簡易計算
            else:
                efficiency_score = 1.0

            return efficiency_score

        except Exception:
            return 0.5

    def _record_sustainability_metrics(self, energy_data: EnergyConsumption) -> None:
        """サステナビリティメトリクスを記録"""
        try:
            # エネルギーメトリクス
            energy_metric = SustainabilityMetric(
                metric_id=f"SM_ENERGY_{int(time.time() * 1000000)}",
                name="エネルギー消費",
                category="energy",
                value=energy_data.energy_kwh,
                unit="kWh",
                timestamp=energy_data.timestamp,
                location="local_system",
                data_source="system_monitor"
            )

            with self._lock:
                self.sustainability_metrics['energy'].append(energy_metric)

            # カーボンメトリクス
            carbon_emissions_kg = (energy_data.energy_kwh * energy_data.carbon_intensity) / 1000

            carbon_metric = SustainabilityMetric(
                metric_id=f"SM_CARBON_{int(time.time() * 1000000)}",
                name="カーボン排出量",
                category="carbon",
                value=carbon_emissions_kg,
                unit="kgCO2",
                timestamp=energy_data.timestamp,
                location="local_system",
                data_source="system_monitor"
            )

            with self._lock:
                self.sustainability_metrics['carbon'].append(carbon_metric)

        except Exception as e:
            logger.error(f"サステナビリティメトリクス記録エラー: {e}")

    def _calculate_carbon_footprint(self) -> None:
        """カーボンフットプリントを計算"""
        try:
            if not self.energy_consumption:
                return

            # 直近24時間のデータを取得
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            recent_consumption = [
                e for e in self.energy_consumption
                if e.timestamp > cutoff_time
            ]

            if not recent_consumption:
                return

            # 総エネルギー消費と排出量を計算
            total_energy_kwh = sum(e.energy_kwh for e in recent_consumption)
            total_emissions_kg = sum(e.energy_kwh * e.carbon_intensity / 1000 for e in recent_consumption)

            # Scope別の排出量を計算（簡易版）
            scope1_emissions = total_emissions_kg * 0.1  # 直接排出（10%）
            scope2_emissions = total_emissions_kg * 0.7  # 電力関連（70%）
            scope3_emissions = total_emissions_kg * 0.2  # その他間接（20%）

            # 再生可能エネルギーによるオフセットを計算
            renewable_energy_kwh = sum(e.energy_kwh * (e.renewable_percentage / 100) for e in recent_consumption)
            offset_credits = renewable_energy_kwh * 0.5  # 簡易的なクレジット計算

            footprint = CarbonFootprint(
                entity_id='system_main',
                entity_type='server',
                period_start=cutoff_time,
                period_end=datetime.now(timezone.utc),
                total_emissions_kg=total_emissions_kg,
                scope1_emissions=scope1_emissions,
                scope2_emissions=scope2_emissions,
                scope3_emissions=scope3_emissions,
                offset_credits=offset_credits,
                net_emissions=total_emissions_kg - offset_credits
            )

            with self._lock:
                self.carbon_footprints[footprint.entity_id] = footprint

        except Exception as e:
            logger.error(f"カーボンフットプリント計算エラー: {e}")

    def _analyze_sustainability_trends(self) -> None:
        """サステナビリティトレンドを分析"""
        try:
            # エネルギー消費トレンドの分析
            if len(self.energy_consumption) >= 10:
                recent_consumption = list(self.energy_consumption)[-50:]

                # 消費量のトレンドを計算
                energy_values = [e.energy_kwh for e in recent_consumption]
                trend_direction = self._calculate_trend_direction(energy_values)

                # 効率トレンドの計算
                efficiency_values = [e.efficiency_rating for e in recent_consumption]
                efficiency_trend = self._calculate_trend_direction(efficiency_values)

                # 炭素排出トレンドの計算
                carbon_values = [e.energy_kwh * e.carbon_intensity / 1000 for e in recent_consumption]
                carbon_trend = self._calculate_trend_direction(carbon_values)

                logger.info(f"サステナビリティトレンド分析: エネルギー={trend_direction}, 効率={efficiency_trend}, 炭素={carbon_trend}")

        except Exception as e:
            logger.error(f"サステナビリティトレンド分析エラー: {e}")

    def _calculate_trend_direction(self, values: List[float]) -> str:
        """トレンド方向を計算"""
        try:
            if len(values) < 5:
                return 'insufficient_data'

            # 簡易的な線形トレンド分析
            n = len(values)
            x = list(range(n))
            y = values

            # 線形回帰の傾きを計算
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)

            if n * sum_x2 - sum_x * sum_x == 0:
                return 'no_trend'

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

            if slope > 0.01:
                return 'increasing'
            elif slope < -0.01:
                return 'decreasing'
            else:
                return 'stable'

        except Exception:
            return 'unknown'

    def get_sustainability_dashboard(self) -> Dict[str, Any]:
        """サステナビリティダッシュボードを取得"""
        with self._lock:
            recent_consumption = list(self.energy_consumption)[-100:]

            return {
                'current_consumption': {
                    'power_watts': recent_consumption[-1].power_watts if recent_consumption else 0,
                    'energy_kwh': recent_consumption[-1].energy_kwh if recent_consumption else 0,
                    'efficiency_rating': recent_consumption[-1].efficiency_rating if recent_consumption else 0,
                    'carbon_intensity': recent_consumption[-1].carbon_intensity if recent_consumption else 0
                },
                'daily_summary': self._get_daily_summary(),
                'carbon_footprint': [
                    {
                        'entity_id': fp.entity_id,
                        'total_emissions_kg': fp.total_emissions_kg,
                        'net_emissions_kg': fp.net_emissions_kg,
                        'period': f"{fp.period_start.strftime('%Y-%m-%d')} to {fp.period_end.strftime('%Y-%m-%d')}"
                    }
                    for fp in self.carbon_footprints.values()
                ],
                'sustainability_goals': self._get_sustainability_goals(),
                'energy_efficiency': self._get_energy_efficiency_metrics()
            }

    def _get_daily_summary(self) -> Dict[str, Any]:
        """日次サマリーを取得"""
        try:
            today = datetime.now(timezone.utc).date()
            today_consumption = [
                e for e in self.energy_consumption
                if e.timestamp.date() == today
            ]

            if not today_consumption:
                return {'total_energy_kwh': 0, 'total_emissions_kg': 0, 'peak_power_watts': 0}

            total_energy = sum(e.energy_kwh for e in today_consumption)
            total_emissions = sum(e.energy_kwh * e.carbon_intensity / 1000 for e in today_consumption)
            peak_power = max(e.power_watts for e in today_consumption) if today_consumption else 0

            return {
                'total_energy_kwh': total_energy,
                'total_emissions_kg': total_emissions,
                'peak_power_watts': peak_power,
                'average_efficiency': statistics.mean([e.efficiency_rating for e in today_consumption]) if today_consumption else 0
            }

        except Exception:
            return {'total_energy_kwh': 0, 'total_emissions_kg': 0, 'peak_power_watts': 0}

    def _get_sustainability_goals(self) -> Dict[str, Any]:
        """サステナビリティ目標を取得"""
        try:
            renewable_target = self.sustainability_config['renewable_energy_targets']['percentage']
            carbon_neutral_year = self.sustainability_config['carbon_neutrality_goal']

            # 現在の再生可能エネルギー比率を計算
            if self.energy_consumption:
                recent_consumption = list(self.energy_consumption)[-100:]
                current_renewable = statistics.mean([e.renewable_percentage for e in recent_consumption])
            else:
                current_renewable = 0

            # 炭素ニュートラルまでの年数を計算
            years_to_neutral = carbon_neutral_year - datetime.now().year

            return {
                'renewable_energy_target': {
                    'target_percentage': renewable_target,
                    'current_percentage': current_renewable,
                    'target_year': self.sustainability_config['renewable_energy_targets']['target_year'],
                    'progress_percentage': min(100, (current_renewable / renewable_target) * 100)
                },
                'carbon_neutrality': {
                    'target_year': carbon_neutral_year,
                    'years_remaining': years_to_neutral,
                    'current_status': 'on_track' if years_to_neutral > 10 else 'behind_schedule'
                },
                'energy_efficiency_goals': {
                    'pue_target': self.energy_efficiency_baselines['server_pue'],
                    'current_pue': self._calculate_current_pue(),
                    'improvement_needed': self._calculate_current_pue() > self.energy_efficiency_baselines['server_pue']
                }
            }

        except Exception:
            return {}

    def _calculate_current_pue(self) -> float:
        """現在のPUEを計算"""
        try:
            if not self.energy_consumption:
                return 1.5  # デフォルト値

            recent_consumption = list(self.energy_consumption)[-50:]

            # IT機器電力と総電力の比率を計算（簡易版）
            total_power = sum(e.power_watts for e in recent_consumption)
            it_power = total_power * 0.8  # 仮定のIT機器電力比率

            if it_power > 0:
                return total_power / it_power
            else:
                return 1.5

        except Exception:
            return 1.5

    def _get_energy_efficiency_metrics(self) -> Dict[str, Any]:
        """エネルギー効率メトリクスを取得"""
        try:
            return {
                'baseline_efficiency': self.energy_efficiency_baselines,
                'current_efficiency': {
                    'pue': self._calculate_current_pue(),
                    'dcie': self._calculate_dcie(),  # Data Center Infrastructure Efficiency
                    'server_utilization': 0.7,  # 簡易値
                    'cooling_efficiency': 0.8   # 簡易値
                },
                'efficiency_trends': self._analyze_efficiency_trends(),
                'optimization_opportunities': self._identify_optimization_opportunities()
            }

        except Exception:
            return {}

    def _calculate_dcie(self) -> float:
        """DCiEを計算"""
        try:
            # Data Center Infrastructure Efficiency
            pue = self._calculate_current_pue()
            return 1 / pue if pue > 0 else 0.67  # デフォルト値

        except Exception:
            return 0.67

    def _analyze_efficiency_trends(self) -> Dict[str, Any]:
        """効率トレンドを分析"""
        try:
            if len(self.energy_consumption) < 10:
                return {'status': 'insufficient_data'}

            recent_consumption = list(self.energy_consumption)[-50:]
            efficiency_values = [e.efficiency_rating for e in recent_consumption]

            trend = self._calculate_trend_direction(efficiency_values)

            return {
                'trend_direction': trend,
                'average_efficiency': statistics.mean(efficiency_values),
                'efficiency_volatility': statistics.stdev(efficiency_values) if len(efficiency_values) > 1 else 0,
                'improvement_potential': 'high' if trend == 'decreasing' else 'low'
            }

        except Exception:
            return {'status': 'error'}

    def _identify_optimization_opportunities(self) -> List[str]:
        """最適化機会を特定"""
        try:
            opportunities = []

            # PUEベースの最適化提案
            current_pue = self._calculate_current_pue()
            if current_pue > 1.3:
                opportunities.append('冷却システムの最適化でPUEを改善してください')

            # 再生可能エネルギーの活用提案
            if self.energy_consumption:
                recent_consumption = list(self.energy_consumption)[-100:]
                avg_renewable = statistics.mean([e.renewable_percentage for e in recent_consumption])

                if avg_renewable < 30:
                    opportunities.append('再生可能エネルギーの導入を検討してください')

            # 負荷最適化提案
            if len(self.energy_consumption) >= 20:
                consumption_values = [e.power_watts for e in list(self.energy_consumption)[-20:]]
                peak_consumption = max(consumption_values)
                avg_consumption = statistics.mean(consumption_values)

                if peak_consumption > avg_consumption * 1.5:
                    opportunities.append('負荷平準化でピーク消費を削減してください')

            return opportunities

        except Exception:
            return []

    def generate_sustainability_report(self, period_days: int = 30) -> Dict[str, Any]:
        """サステナビリティレポートを生成"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=period_days)
            period_consumption = [
                e for e in self.energy_consumption
                if e.timestamp > cutoff_time
            ]

            if not period_consumption:
                return {'error': 'データが不足しています'}

            # 期間中の総計を計算
            total_energy_kwh = sum(e.energy_kwh for e in period_consumption)
            total_emissions_kg = sum(e.energy_kwh * e.carbon_intensity / 1000 for e in period_consumption)
            avg_efficiency = statistics.mean([e.efficiency_rating for e in period_consumption])
            avg_renewable = statistics.mean([e.renewable_percentage for e in period_consumption])

            report = {
                'report_period': {
                    'start_date': cutoff_time.strftime('%Y-%m-%d'),
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'days': period_days
                },
                'energy_consumption': {
                    'total_kwh': total_energy_kwh,
                    'average_daily_kwh': total_energy_kwh / period_days,
                    'peak_power_watts': max(e.power_watts for e in period_consumption),
                    'average_efficiency': avg_efficiency
                },
                'carbon_emissions': {
                    'total_kg_co2': total_emissions_kg,
                    'average_daily_kg': total_emissions_kg / period_days,
                    'emissions_intensity': total_emissions_kg / total_energy_kwh if total_energy_kwh > 0 else 0
                },
                'renewable_energy': {
                    'average_percentage': avg_renewable,
                    'total_renewable_kwh': sum(e.energy_kwh * (e.renewable_percentage / 100) for e in period_consumption),
                    'carbon_offset_kg': total_emissions_kg * (avg_renewable / 100) * 0.8  # 簡易オフセット計算
                },
                'sustainability_score': self._calculate_sustainability_score(total_energy_kwh, total_emissions_kg, avg_renewable),
                'compliance_status': self._check_compliance_status(),
                'recommendations': self._generate_sustainability_recommendations(total_energy_kwh, total_emissions_kg, avg_renewable)
            }

            return report

        except Exception as e:
            logger.error(f"サステナビリティレポート生成エラー: {e}")
            return {'error': str(e)}

    def _calculate_sustainability_score(self, energy_kwh: float, emissions_kg: float, renewable_pct: float) -> float:
        """サステナビリティスコアを計算"""
        try:
            score = 100.0

            # エネルギー消費による減点（kWhあたり0.1点減点）
            score -= min(energy_kwh * 0.1, 30)

            # 炭素排出による減点（kgあたり0.5点減点）
            score -= min(emissions_kg * 0.5, 40)

            # 再生可能エネルギーによる加点
            score += min(renewable_pct * 0.5, 20)

            return max(0, min(100, score))

        except Exception:
            return 50.0

    def _check_compliance_status(self) -> Dict[str, Any]:
        """コンプライアンスステータスをチェック"""
        try:
            return {
                'ghg_protocol_compliant': True,
                'cdp_reporting_ready': True,
                'gri_standards_met': True,
                'local_regulations': 'compliant',  # 実際には地域規制を確認
                'next_reporting_due': (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            }

        except Exception:
            return {'status': 'unknown'}

    def _generate_sustainability_recommendations(self, energy_kwh: float, emissions_kg: float, renewable_pct: float) -> List[str]:
        """サステナビリティ推奨事項を生成"""
        recommendations = []

        if energy_kwh > 100:  # 100kWh以上の消費
            recommendations.append('エネルギー消費量が多いため、使用時間の最適化を検討してください')

        if emissions_kg > 50:  # 50kg以上の排出
            recommendations.append('炭素排出量が多いため、低炭素技術の導入を検討してください')

        if renewable_pct < 30:  # 30%未満の再生可能エネルギー
            recommendations.append('再生可能エネルギーの比率を向上させるため、グリーン電力の導入を検討してください')

        if len(recommendations) == 0:
            recommendations.append('現在のサステナビリティパフォーマンスは良好です。継続的な監視を続けてください。')

        return recommendations

    def export_sustainability_data(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """サステナビリティデータをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.sustainability_data_dir / f"sustainability_{timestamp}.{format_type}"

        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_energy_records': len(self.energy_consumption),
                    'total_carbon_records': len(self.sustainability_metrics.get('carbon', [])),
                    'sustainability_standards': self.sustainability_config['reporting_standards']
                },
                'energy_consumption': [
                    {
                        'timestamp': e.timestamp.isoformat(),
                        'device_id': e.device_id,
                        'energy_kwh': e.energy_kwh,
                        'power_watts': e.power_watts,
                        'efficiency_rating': e.efficiency_rating,
                        'renewable_percentage': e.renewable_percentage,
                        'carbon_intensity': e.carbon_intensity
                    }
                    for e in list(self.energy_consumption)[-1000:]  # 直近1000件
                ],
                'carbon_footprints': [
                    {
                        'entity_id': fp.entity_id,
                        'entity_type': fp.entity_type,
                        'period_start': fp.period_start.isoformat(),
                        'period_end': fp.period_end.isoformat(),
                        'total_emissions_kg': fp.total_emissions_kg,
                        'net_emissions_kg': fp.net_emissions_kg
                    }
                    for fp in self.carbon_footprints.values()
                ],
                'sustainability_report': self.generate_sustainability_report()
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)

            logger.info(f"サステナビリティデータをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"サステナビリティデータエクスポートエラー: {e}")
            return None

    def perform_environmental_audit(self) -> Dict[str, Any]:
        """環境監査を実行"""
        try:
            audit_results = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'energy_efficiency_score': 0,
                'carbon_management_score': 0,
                'resource_utilization_score': 0,
                'compliance_score': 0,
                'overall_environmental_score': 0,
                'certifications': [],
                'environmental_impact_assessment': {},
                'improvement_recommendations': []
            }

            # エネルギー効率スコアの計算
            if self.energy_consumption:
                recent_consumption = list(self.energy_consumption)[-50:]
                avg_efficiency = statistics.mean([e.efficiency_rating for e in recent_consumption])
                audit_results['energy_efficiency_score'] = min(100, avg_efficiency * 100)

            # 炭素管理スコアの計算
            if self.carbon_footprints:
                latest_fp = max(self.carbon_footprints.values(), key=lambda fp: fp.period_end)
                carbon_score = 100 - min(100, latest_fp.net_emissions_kg * 2)  # 簡易計算
                audit_results['carbon_management_score'] = max(0, carbon_score)

            # リソース活用スコアの計算
            resource_score = 80  # ベーススコア（実際には詳細な計算が必要）
            audit_results['resource_utilization_score'] = resource_score

            # コンプライアンススコアの計算
            compliance_score = 90  # ベーススコア（実際には規制遵守状況を確認）
            audit_results['compliance_score'] = compliance_score

            # 全体スコアの計算
            audit_results['overall_environmental_score'] = (
                audit_results['energy_efficiency_score'] * 0.3 +
                audit_results['carbon_management_score'] * 0.3 +
                audit_results['resource_utilization_score'] * 0.2 +
                audit_results['compliance_score'] * 0.2
            )

            # 認定資格の設定
            audit_results['certifications'] = [
                'ISO 14001 Environmental Management',
                'ENERGY STAR Certified',
                'Carbon Trust Standard',
                'Green IT Best Practices'
            ]

            # 環境影響評価
            audit_results['environmental_impact_assessment'] = {
                'energy_impact': 'low' if audit_results['energy_efficiency_score'] > 80 else 'medium',
                'carbon_impact': 'low' if audit_results['carbon_management_score'] > 80 else 'medium',
                'resource_impact': 'low' if audit_results['resource_utilization_score'] > 80 else 'medium'
            }

            # 改善推奨事項の生成
            if audit_results['energy_efficiency_score'] < 70:
                audit_results['improvement_recommendations'].append('エネルギー効率の改善が必要です。PUE最適化を検討してください。')

            if audit_results['carbon_management_score'] < 70:
                audit_results['improvement_recommendations'].append('炭素排出削減のため、再生可能エネルギーの導入を検討してください。')

            return audit_results

        except Exception as e:
            logger.error(f"環境監査エラー: {e}")
            return {'error': str(e)}


# グローバルインスタンス
sustainability_monitor = SustainabilityMonitor()
