"""
FinOps/OpenCost統合モジュール

2024-2025年トレンド:
- OpenCost: CNCF Incubation (2024年10月)
- Kubecost: IBM買収 (2024年9月)
- 採用率: 23%の組織

主要機能:
1. Kubernetesコスト監視
2. リソース最適化推奨
3. 予算管理とアラート
4. コスト配分と可視化
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("requests not available - install: pip install requests")

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """リソースタイプ"""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"


@dataclass
class CostAllocation:
    """コスト配分"""
    namespace: str
    pod_name: str
    container_name: str
    cpu_cost: float
    memory_cost: float
    storage_cost: float
    network_cost: float
    total_cost: float
    start_time: datetime
    end_time: datetime
    labels: Dict[str, str]


@dataclass
class CostOptimizationRecommendation:
    """コスト最適化推奨"""
    resource_type: ResourceType
    current_allocation: float
    recommended_allocation: float
    potential_savings: float
    confidence: float
    reason: str
    action: str


@dataclass
class BudgetAlert:
    """予算アラート"""
    namespace: str
    current_cost: float
    budget: float
    percentage: float
    severity: str  # info, warning, critical
    forecast_end_of_month: float
    timestamp: datetime


class OpenCostIntegration:
    """
    OpenCost統合クライアント

    Kubernetesコスト監視とFinOps機能
    """

    def __init__(
        self,
        opencost_url: str = "http://localhost:9003",
        enabled: bool = True
    ):
        """
        初期化

        Args:
            opencost_url: OpenCost APIエンドポイント
            enabled: 有効化フラグ
        """
        self.opencost_url = opencost_url.rstrip('/')
        self.enabled = enabled and REQUESTS_AVAILABLE

        if not self.enabled:
            if not REQUESTS_AVAILABLE:
                logger.warning("OpenCost integration disabled: requests not available")
            else:
                logger.info("OpenCost integration disabled by configuration")
            return

        # 接続テスト
        self._test_connection()

        logger.info(f"OpenCost integration initialized: {opencost_url}")

    def _test_connection(self) -> bool:
        """接続テスト"""
        try:
            response = requests.get(
                f"{self.opencost_url}/healthz",
                timeout=5
            )
            if response.status_code == 200:
                logger.info("OpenCost connection successful")
                return True
            else:
                logger.warning(f"OpenCost health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"OpenCost connection failed: {e}")
            return False

    def get_allocation_costs(
        self,
        window: str = "7d",
        aggregate: str = "namespace"
    ) -> Dict[str, Any]:
        """
        コスト配分取得

        Args:
            window: 時間窓 (例: 7d, 30d, yesterday, today)
            aggregate: 集約単位 (namespace, pod, container, label:key)

        Returns:
            コスト配分データ
        """
        if not self.enabled:
            return {}

        try:
            response = requests.get(
                f"{self.opencost_url}/allocation",
                params={
                    "window": window,
                    "aggregate": aggregate
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get allocation costs: {e}")
            return {}

    def get_cluster_costs(self) -> Dict[str, float]:
        """
        クラスター全体のコスト取得

        Returns:
            コスト情報
        """
        if not self.enabled:
            return {}

        try:
            response = requests.get(
                f"{self.opencost_url}/allocation/compute",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # 合計コスト計算
            total_cost = 0.0
            cpu_cost = 0.0
            memory_cost = 0.0
            storage_cost = 0.0

            for allocation in data.get("data", []):
                total_cost += allocation.get("totalCost", 0.0)
                cpu_cost += allocation.get("cpuCost", 0.0)
                memory_cost += allocation.get("memoryCost", 0.0)
                storage_cost += allocation.get("storageCost", 0.0)

            return {
                "total_cost": total_cost,
                "cpu_cost": cpu_cost,
                "memory_cost": memory_cost,
                "storage_cost": storage_cost,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get cluster costs: {e}")
            return {}

    def get_cost_by_label(
        self,
        label_key: str,
        window: str = "7d"
    ) -> List[Dict[str, Any]]:
        """
        ラベル別コスト取得

        Args:
            label_key: ラベルキー (例: app, env, team)
            window: 時間窓

        Returns:
            ラベル別コストリスト
        """
        if not self.enabled:
            return []

        try:
            response = requests.get(
                f"{self.opencost_url}/allocation",
                params={
                    "window": window,
                    "aggregate": f"label:{label_key}"
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            costs = []
            for key, value in data.get("data", {}).items():
                costs.append({
                    "label_value": key,
                    "total_cost": value.get("totalCost", 0.0),
                    "cpu_cost": value.get("cpuCost", 0.0),
                    "memory_cost": value.get("memoryCost", 0.0),
                    "storage_cost": value.get("storageCost", 0.0)
                })

            return costs

        except Exception as e:
            logger.error(f"Failed to get cost by label: {e}")
            return []


class CostAlertManager:
    """
    コストアラート管理

    予算超過検知と通知
    """

    def __init__(self, opencost: OpenCostIntegration):
        """
        初期化

        Args:
            opencost: OpenCost統合インスタンス
        """
        self.opencost = opencost
        self.budgets: Dict[str, float] = {}
        self.alert_thresholds = [0.5, 0.8, 0.9, 1.0]  # 50%, 80%, 90%, 100%

    def set_budget(self, namespace: str, monthly_budget: float) -> None:
        """
        予算設定

        Args:
            namespace: ネームスペース
            monthly_budget: 月次予算 (USD)
        """
        self.budgets[namespace] = monthly_budget
        logger.info(f"Budget set: {namespace} = ${monthly_budget:.2f}/month")

    def check_budget_alerts(self) -> List[BudgetAlert]:
        """
        予算超過チェック

        Returns:
            アラートリスト
        """
        if not self.opencost.enabled:
            return []

        alerts = []
        costs = self.opencost.get_allocation_costs(window="30d", aggregate="namespace")

        for namespace, budget in self.budgets.items():
            if namespace not in costs.get("data", {}):
                continue

            namespace_data = costs["data"][namespace]
            current_cost = namespace_data.get("totalCost", 0.0)
            percentage = (current_cost / budget) * 100 if budget > 0 else 0

            # 月末予測
            days_passed = datetime.now().day
            days_in_month = 30  # 簡易計算
            forecast = (current_cost / days_passed) * days_in_month if days_passed > 0 else 0

            # アラート判定
            severity = "info"
            if percentage >= 100:
                severity = "critical"
            elif percentage >= 90:
                severity = "critical"
            elif percentage >= 80:
                severity = "warning"
            elif percentage >= 50:
                severity = "info"

            if percentage >= 50:  # 50%以上でアラート
                alerts.append(BudgetAlert(
                    namespace=namespace,
                    current_cost=current_cost,
                    budget=budget,
                    percentage=percentage,
                    severity=severity,
                    forecast_end_of_month=forecast,
                    timestamp=datetime.now()
                ))

        return alerts

    def get_budget_status(self) -> Dict[str, Any]:
        """
        予算ステータス取得

        Returns:
            予算ステータス
        """
        alerts = self.check_budget_alerts()

        return {
            "total_budgets": len(self.budgets),
            "alerts": [
                {
                    "namespace": alert.namespace,
                    "current_cost": alert.current_cost,
                    "budget": alert.budget,
                    "percentage": alert.percentage,
                    "severity": alert.severity,
                    "forecast": alert.forecast_end_of_month
                }
                for alert in alerts
            ],
            "total_alerts": len(alerts),
            "critical_alerts": sum(1 for a in alerts if a.severity == "critical"),
            "warning_alerts": sum(1 for a in alerts if a.severity == "warning"),
            "timestamp": datetime.now().isoformat()
        }


class CostOptimizationEngine:
    """
    コスト最適化エンジン

    リソース効率分析と推奨生成
    """

    def __init__(self, opencost: OpenCostIntegration):
        """
        初期化

        Args:
            opencost: OpenCost統合インスタンス
        """
        self.opencost = opencost
        self.optimization_threshold = 2.0  # 2倍以上の過剰プロビジョニング

    def analyze_resource_efficiency(
        self,
        namespace: Optional[str] = None
    ) -> List[CostOptimizationRecommendation]:
        """
        リソース効率分析

        Args:
            namespace: 分析対象ネームスペース (None = 全体)

        Returns:
            最適化推奨リスト
        """
        if not self.opencost.enabled:
            return []

        recommendations = []

        # コスト配分取得
        aggregate = f"namespace/{namespace}" if namespace else "pod"
        costs = self.opencost.get_allocation_costs(
            window="7d",
            aggregate=aggregate
        )

        for pod_name, pod_data in costs.get("data", {}).items():
            # CPU過剰プロビジョニング検出
            cpu_request = pod_data.get("cpuCoreRequestAverage", 0)
            cpu_usage = pod_data.get("cpuCoreUsageAverage", 0)

            if cpu_request > 0 and cpu_usage > 0:
                cpu_ratio = cpu_request / cpu_usage

                if cpu_ratio > self.optimization_threshold:
                    recommended_cpu = cpu_usage * 1.2  # 20%バッファ
                    savings = self._calculate_savings(
                        cpu_request - recommended_cpu,
                        ResourceType.CPU
                    )

                    recommendations.append(CostOptimizationRecommendation(
                        resource_type=ResourceType.CPU,
                        current_allocation=cpu_request,
                        recommended_allocation=recommended_cpu,
                        potential_savings=savings,
                        confidence=0.8,
                        reason=f"CPU request {cpu_ratio:.1f}x higher than usage",
                        action=f"Reduce CPU request from {cpu_request:.2f} to {recommended_cpu:.2f} cores"
                    ))

            # メモリ過剰プロビジョニング検出
            mem_request = pod_data.get("ramByteRequestAverage", 0)
            mem_usage = pod_data.get("ramByteUsageAverage", 0)

            if mem_request > 0 and mem_usage > 0:
                mem_ratio = mem_request / mem_usage

                if mem_ratio > self.optimization_threshold:
                    recommended_mem = mem_usage * 1.2  # 20%バッファ
                    savings = self._calculate_savings(
                        (mem_request - recommended_mem) / (1024**3),  # GB
                        ResourceType.MEMORY
                    )

                    recommendations.append(CostOptimizationRecommendation(
                        resource_type=ResourceType.MEMORY,
                        current_allocation=mem_request / (1024**3),  # GB
                        recommended_allocation=recommended_mem / (1024**3),  # GB
                        potential_savings=savings,
                        confidence=0.8,
                        reason=f"Memory request {mem_ratio:.1f}x higher than usage",
                        action=f"Reduce memory request from {mem_request/(1024**3):.2f}GB to {recommended_mem/(1024**3):.2f}GB"
                    ))

        # 節約額でソート
        recommendations.sort(key=lambda x: x.potential_savings, reverse=True)

        return recommendations

    def _calculate_savings(
        self,
        resource_diff: float,
        resource_type: ResourceType
    ) -> float:
        """
        節約額計算

        Args:
            resource_diff: リソース差分
            resource_type: リソースタイプ

        Returns:
            月次節約額 (USD)
        """
        # 簡易価格モデル (AWS EKS概算)
        prices = {
            ResourceType.CPU: 30.0,  # $30/core/month
            ResourceType.MEMORY: 4.0,  # $4/GB/month
            ResourceType.STORAGE: 0.10,  # $0.10/GB/month
            ResourceType.GPU: 500.0,  # $500/GPU/month
        }

        unit_price = prices.get(resource_type, 0.0)
        return resource_diff * unit_price

    def get_optimization_summary(self) -> Dict[str, Any]:
        """
        最適化サマリー取得

        Returns:
            最適化サマリー
        """
        recommendations = self.analyze_resource_efficiency()

        total_savings = sum(r.potential_savings for r in recommendations)
        cpu_savings = sum(
            r.potential_savings for r in recommendations
            if r.resource_type == ResourceType.CPU
        )
        memory_savings = sum(
            r.potential_savings for r in recommendations
            if r.resource_type == ResourceType.MEMORY
        )

        return {
            "total_recommendations": len(recommendations),
            "potential_monthly_savings": total_savings,
            "cpu_savings": cpu_savings,
            "memory_savings": memory_savings,
            "top_recommendations": [
                {
                    "resource_type": r.resource_type.value,
                    "current": r.current_allocation,
                    "recommended": r.recommended_allocation,
                    "savings": r.potential_savings,
                    "action": r.action
                }
                for r in recommendations[:5]  # トップ5
            ],
            "timestamp": datetime.now().isoformat()
        }


# グローバルインスタンス
_opencost_client: Optional[OpenCostIntegration] = None
_alert_manager: Optional[CostAlertManager] = None
_optimization_engine: Optional[CostOptimizationEngine] = None


def get_opencost_client(
    opencost_url: str = "http://localhost:9003"
) -> OpenCostIntegration:
    """OpenCostクライアント取得"""
    global _opencost_client
    if _opencost_client is None:
        _opencost_client = OpenCostIntegration(opencost_url=opencost_url)
    return _opencost_client


def get_alert_manager() -> CostAlertManager:
    """アラートマネージャー取得"""
    global _alert_manager, _opencost_client
    if _alert_manager is None:
        if _opencost_client is None:
            _opencost_client = get_opencost_client()
        _alert_manager = CostAlertManager(_opencost_client)
    return _alert_manager


def get_optimization_engine() -> CostOptimizationEngine:
    """最適化エンジン取得"""
    global _optimization_engine, _opencost_client
    if _optimization_engine is None:
        if _opencost_client is None:
            _opencost_client = get_opencost_client()
        _optimization_engine = CostOptimizationEngine(_opencost_client)
    return _optimization_engine


# 使用例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # OpenCost初期化
    opencost = get_opencost_client()

    # クラスターコスト取得
    cluster_costs = opencost.get_cluster_costs()
    print(f"Cluster costs: ${cluster_costs.get('total_cost', 0):.2f}")

    # 予算管理
    alert_mgr = get_alert_manager()
    alert_mgr.set_budget("production", 1000.0)
    alert_mgr.set_budget("staging", 500.0)

    alerts = alert_mgr.check_budget_alerts()
    for alert in alerts:
        print(f"⚠️ {alert.severity.upper()}: {alert.namespace} at {alert.percentage:.1f}%")

    # 最適化推奨
    opt_engine = get_optimization_engine()
    summary = opt_engine.get_optimization_summary()
    print(f"💰 Potential savings: ${summary['potential_monthly_savings']:.2f}/month")
    print(f"📊 {summary['total_recommendations']} recommendations found")
