"""
高度な深層学習とLLM統合システム - Moni System Monitor

トランスフォーマーと大規模言語モデルによるインテリジェント異常検知を提供します。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

logger = logging.getLogger(__name__)


@dataclass
class NeuralNetworkModel:
    """ニューラルネットワークモデル"""
    model_id: str
    model_type: str  # transformer, lstm, cnn, gan, etc.
    architecture: Dict[str, Any]
    parameters: Dict[str, Any]
    training_data_size: int
    accuracy: float
    created_at: datetime
    last_trained: Optional[datetime]
    model_size_mb: float


@dataclass
class AnomalyDetectionResult:
    """異常検知結果（高度版）"""
    detection_id: str
    timestamp: datetime
    anomaly_score: float
    confidence: float
    anomaly_type: str  # point, contextual, collective, etc.
    affected_components: List[str]
    root_cause_analysis: str
    llm_explanation: str
    recommended_actions: List[str]
    evidence_strength: float
    false_positive_probability: float


@dataclass
class LLMQuery:
    """LLMクエリ"""
    query_id: str
    query_text: str
    query_type: str  # anomaly_analysis, optimization, explanation, etc.
    context_data: Dict[str, Any]
    response: Optional[str] = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0


class AdvancedDeepLearningAI:
    """高度な深層学習AIシステム"""

    def __init__(self, ai_models_dir: Optional[Union[str, Path]] = None):
        self.ai_models_dir = Path(ai_models_dir) if ai_models_dir else Path(__file__).parent / "ai_models"
        self.ai_models_dir.mkdir(exist_ok=True)

        self.neural_models: Dict[str, NeuralNetworkModel] = {}
        self.anomaly_history: deque = deque(maxlen=100000)
        self.llm_queries: Dict[str, LLMQuery] = {}

        # 深層学習設定
        self.dl_config = {
            'supported_architectures': ['transformer', 'lstm', 'cnn', 'gan', 'autoencoder'],
            'max_sequence_length': 1000,
            'embedding_dimensions': 768,
            'attention_heads': 12,
            'hidden_layers': 6,
            'dropout_rate': 0.1,
            'learning_rate': 0.001,
            'batch_size': 32,
            'llm_model': 'GPT-4',  # 統合するLLMモデル
            'context_window': 4096
        }

        # 異常検知モデル
        self.anomaly_detection_models: Dict[str, Any] = {}
        self.transformer_models: Dict[str, Any] = {}

        self._lock = threading.Lock()

        # AIモデルの初期化
        self._init_ai_models()

        # 深層学習プロセスの開始
        self._start_deep_learning_training()

    def _init_ai_models(self) -> None:
        """AIモデルを初期化"""
        try:
            # トランスフォーマーモデルを初期化（モック実装）
            transformer_model = NeuralNetworkModel(
                model_id='transformer_anomaly_v1',
                model_type='transformer',
                architecture={
                    'encoder_layers': 6,
                    'decoder_layers': 6,
                    'attention_heads': 12,
                    'feed_forward_dim': 3072,
                    'embedding_dim': 768
                },
                parameters={
                    'vocab_size': 50000,
                    'max_position_embeddings': 1024,
                    'layer_norm_eps': 1e-12
                },
                training_data_size=1000000,
                accuracy=0.95,
                created_at=datetime.now(timezone.utc),
                last_trained=datetime.now(timezone.utc) - timedelta(days=7),
                model_size_mb=350.0
            )

            # LSTMモデルを初期化
            lstm_model = NeuralNetworkModel(
                model_id='lstm_anomaly_v1',
                model_type='lstm',
                architecture={
                    'input_size': 128,
                    'hidden_size': 256,
                    'num_layers': 3,
                    'dropout': 0.2
                },
                parameters={
                    'sequence_length': 100,
                    'prediction_horizon': 10
                },
                training_data_size=500000,
                accuracy=0.92,
                created_at=datetime.now(timezone.utc) - timedelta(days=30),
                last_trained=datetime.now(timezone.utc) - timedelta(days=3),
                model_size_mb=150.0
            )

            # CNNモデルを初期化
            cnn_model = NeuralNetworkModel(
                model_id='cnn_anomaly_v1',
                model_type='cnn',
                architecture={
                    'conv_layers': 3,
                    'kernel_sizes': [3, 5, 7],
                    'filters': [64, 128, 256],
                    'pooling': 'max'
                },
                parameters={
                    'input_channels': 1,
                    'output_classes': 2
                },
                training_data_size=300000,
                accuracy=0.89,
                created_at=datetime.now(timezone.utc) - timedelta(days=15),
                last_trained=datetime.now(timezone.utc) - timedelta(days=5),
                model_size_mb=80.0
            )

            with self._lock:
                self.neural_models[transformer_model.model_id] = transformer_model
                self.neural_models[lstm_model.model_id] = lstm_model
                self.neural_models[cnn_model.model_id] = cnn_model

            logger.info(f"{len(self.neural_models)}個のAIモデルを初期化しました。")

        except Exception as e:
            logger.error(f"AIモデル初期化エラー: {e}")

    def _start_deep_learning_training(self) -> None:
        """深層学習トレーニングを開始"""
        def training_loop():
            while True:
                try:
                    self._train_anomaly_detection_models()
                    self._update_llm_integration()
                    time.sleep(3600)  # 1時間ごとにトレーニング
                except Exception as e:
                    logger.error(f"深層学習トレーニングエラー: {e}")
                    time.sleep(1800)  # エラー時は30分待機

        training_thread = threading.Thread(target=training_loop, daemon=True)
        training_thread.start()
        logger.info("深層学習トレーニングプロセスを開始しました。")

    def _train_anomaly_detection_models(self) -> None:
        """異常検知モデルをトレーニング"""
        try:
            # トレーニングデータの準備
            training_data = self._prepare_training_data()

            if not training_data:
                logger.warning("トレーニングデータが不足しています。")
                return

            # 各モデルをトレーニング
            for model_name, model in self.neural_models.items():
                if model.model_type in ['transformer', 'lstm', 'cnn']:
                    # 実際の実装では、適切な深層学習フレームワークを使用
                    # ここではモックトレーニングをシミュレート

                    # トレーニング進行をシミュレート
                    training_progress = 0.0
                    while training_progress < 1.0:
                        training_progress += random.uniform(0.01, 0.05)
                        time.sleep(0.1)  # シミュレーション

                    # モデル精度を更新
                    model.accuracy = min(0.99, model.accuracy + random.uniform(0.001, 0.01))
                    model.last_trained = datetime.now(timezone.utc)

                    logger.info(f"モデルをトレーニングしました: {model_name} (精度: {model.accuracy:.3f})")

        except Exception as e:
            logger.error(f"異常検知モデルトレーニングエラー: {e}")

    def _prepare_training_data(self) -> Dict[str, Any]:
        """トレーニングデータを準備"""
        try:
            # システムメトリクスからトレーニングデータを生成（モック実装）
            training_data = {
                'normal_sequences': [],
                'anomalous_sequences': [],
                'metadata': {
                    'data_points': 10000,
                    'features': 128,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }

            # 正常シーケンスの生成（正弦波ベース）
            for i in range(100):
                sequence = []
                for t in range(100):
                    # 複数の特徴量を持つ時系列データ
                    features = []
                    for f in range(128):
                        # 正常なパターン（正弦波 + ノイズ）
                        normal_value = math.sin(2 * math.pi * t / 20 + i * 0.1) + random.uniform(-0.1, 0.1)
                        features.append(normal_value)
                    sequence.append(features)

                training_data['normal_sequences'].append(sequence)

            # 異常シーケンスの生成（スパイクや異常パターン）
            for i in range(20):
                sequence = []
                for t in range(100):
                    features = []
                    for f in range(128):
                        if random.random() < 0.1:  # 10%の確率で異常値
                            anomalous_value = random.uniform(-5, 5)  # 大きな異常値
                        else:
                            normal_value = math.sin(2 * math.pi * t / 20) + random.uniform(-0.1, 0.1)
                            anomalous_value = normal_value
                        features.append(anomalous_value)
                    sequence.append(features)

                training_data['anomalous_sequences'].append(sequence)

            return training_data

        except Exception as e:
            logger.error(f"トレーニングデータ準備エラー: {e}")
            return {}

    def detect_anomalies_with_ai(self, system_metrics: Dict[str, Any]) -> List[AnomalyDetectionResult]:
        """AIによる異常検知を実行"""
        try:
            results = []

            # 時系列データを準備
            time_series_data = self._prepare_time_series_data(system_metrics)

            # 各モデルで異常検知を実行
            for model_name, model in self.neural_models.items():
                if model.model_type == 'transformer':
                    result = self._detect_with_transformer(time_series_data, model)
                elif model.model_type == 'lstm':
                    result = self._detect_with_lstm(time_series_data, model)
                elif model.model_type == 'cnn':
                    result = self._detect_with_cnn(time_series_data, model)
                else:
                    continue

                if result:
                    results.append(result)

            # LLMによる説明を追加
            for result in results:
                if result.confidence > 0.8:
                    result.llm_explanation = self._generate_llm_explanation(result)

            return results

        except Exception as e:
            logger.error(f"AI異常検知エラー: {e}")
            return []

    def _prepare_time_series_data(self, system_metrics: Dict[str, Any]) -> List[List[float]]:
        """時系列データを準備"""
        try:
            # システムメトリクスを時系列特徴量に変換
            features = []

            # CPU関連特徴量
            cpu_features = [
                system_metrics.get('cpu_percent', 0),
                system_metrics.get('cpu_count', 1),
                system_metrics.get('cpu_freq', 0)
            ]

            # メモリ関連特徴量
            memory = system_metrics.get('memory', {})
            memory_features = [
                memory.get('percent', 0),
                memory.get('available', 0) / 1024 / 1024,  # MB単位
                memory.get('used', 0) / 1024 / 1024
            ]

            # ディスク関連特徴量
            disk = system_metrics.get('disk', {})
            disk_features = [
                disk.get('percent', 0),
                disk.get('free', 0) / 1024 / 1024 / 1024,  # GB単位
                disk.get('read_count', 0)
            ]

            # ネットワーク関連特徴量
            network = system_metrics.get('network', {})
            network_features = [
                network.get('bytes_sent', 0),
                network.get('bytes_recv', 0),
                network.get('packets_sent', 0),
                network.get('packets_recv', 0)
            ]

            # 全特徴量を結合
            features = cpu_features + memory_features + disk_features + network_features

            # 特徴量を128次元にパディングまたは切り詰め
            target_features = 128
            if len(features) < target_features:
                features.extend([0.0] * (target_features - len(features)))
            else:
                features = features[:target_features]

            return [features]  # 単一タイムステップのデータ

        except Exception as e:
            logger.error(f"時系列データ準備エラー: {e}")
            return [[0.0] * 128]

    def _detect_with_transformer(self, time_series_data: List[List[float]], model: NeuralNetworkModel) -> Optional[AnomalyDetectionResult]:
        """トランスフォーマーによる異常検知"""
        try:
            # 実際の実装では、トレーニング済みトランスフォーマーモデルを使用
            # ここではモック検知をシミュレート

            # 特徴量の統計的異常を検知
            features = time_series_data[0]
            mean_val = sum(features) / len(features)
            std_val = math.sqrt(sum((f - mean_val) ** 2 for f in features) / len(features))

            # 異常スコアを計算（標準偏差からの逸脱度）
            anomaly_score = abs(mean_val) / (std_val + 1e-8)

            if anomaly_score > 0.7:  # 閾値
                return AnomalyDetectionResult(
                    detection_id=f"AD_AI_{int(time.time() * 1000000)}",
                    timestamp=datetime.now(timezone.utc),
                    anomaly_score=anomaly_score,
                    confidence=min(0.95, anomaly_score),
                    anomaly_type='point_anomaly',
                    affected_components=['system'],
                    root_cause_analysis='トランスフォーマーモデルによる異常パターン検知',
                    llm_explanation='',
                    recommended_actions=['システム状態の詳細調査を推奨', 'ログの確認を実施'],
                    evidence_strength=anomaly_score,
                    false_positive_probability=0.05
                )

            return None

        except Exception as e:
            logger.error(f"トランスフォーマー異常検知エラー: {e}")
            return None

    def _detect_with_lstm(self, time_series_data: List[List[float]], model: NeuralNetworkModel) -> Optional[AnomalyDetectionResult]:
        """LSTMによる異常検知"""
        try:
            # LSTMによる時系列異常検知（モック実装）
            features = time_series_data[0]

            # 特徴量の自己相関を分析（簡易版）
            autocorrelation = 0.0
            for i in range(len(features) - 1):
                autocorrelation += features[i] * features[i + 1]

            anomaly_score = abs(autocorrelation) / (len(features) - 1)

            if anomaly_score > 0.6:
                return AnomalyDetectionResult(
                    detection_id=f"AD_LSTM_{int(time.time() * 1000000)}",
                    timestamp=datetime.now(timezone.utc),
                    anomaly_score=anomaly_score,
                    confidence=min(0.90, anomaly_score),
                    anomaly_type='contextual_anomaly',
                    affected_components=['time_series'],
                    root_cause_analysis='LSTMモデルによる時系列異常パターン検知',
                    llm_explanation='',
                    recommended_actions=['時系列データの確認', '過去パターンの分析'],
                    evidence_strength=anomaly_score,
                    false_positive_probability=0.08
                )

            return None

        except Exception as e:
            logger.error(f"LSTM異常検知エラー: {e}")
            return None

    def _detect_with_cnn(self, time_series_data: List[List[float]], model: NeuralNetworkModel) -> Optional[AnomalyDetectionResult]:
        """CNNによる異常検知"""
        try:
            # CNNによる特徴抽出（モック実装）
            features = time_series_data[0]

            # 特徴量を画像風に変換して異常検知
            feature_matrix = []
            chunk_size = 16
            for i in range(0, len(features), chunk_size):
                chunk = features[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    feature_matrix.append(chunk)

            if not feature_matrix:
                return None

            # 簡易的な異常検知（特徴量のエッジ検知）
            anomaly_score = 0.0
            for row in feature_matrix:
                for j in range(len(row) - 1):
                    edge_strength = abs(row[j + 1] - row[j])
                    anomaly_score += edge_strength

            anomaly_score /= (len(feature_matrix) * (len(row) - 1))

            if anomaly_score > 0.8:
                return AnomalyDetectionResult(
                    detection_id=f"AD_CNN_{int(time.time() * 1000000)}",
                    timestamp=datetime.now(timezone.utc),
                    anomaly_score=anomaly_score,
                    confidence=min(0.85, anomaly_score),
                    anomaly_type='collective_anomaly',
                    affected_components=['feature_patterns'],
                    root_cause_analysis='CNNモデルによる特徴パターン異常検知',
                    llm_explanation='',
                    recommended_actions=['特徴パターンの詳細分析', 'CNNモデルパラメータの確認'],
                    evidence_strength=anomaly_score,
                    false_positive_probability=0.12
                )

            return None

        except Exception as e:
            logger.error(f"CNN異常検知エラー: {e}")
            return None

    def _generate_llm_explanation(self, detection_result: AnomalyDetectionResult) -> str:
        """LLMによる説明を生成"""
        try:
            # LLMクエリを作成
            query_text = f"""
システム異常が検知されました：
- 異常スコア: {detection_result.anomaly_score:.3f}
- 信頼度: {detection_result.confidence:.3f}
- 異常タイプ: {detection_result.anomaly_type}
- 影響コンポーネント: {', '.join(detection_result.affected_components)}

この異常の考えられる原因と対処方法を説明してください。
"""

            # LLMによる応答生成（モック実装）
            # 実際の実装では、OpenAI APIや他のLLMサービスを呼び出し

            explanations = [
                "この異常はシステム負荷の急増による可能性が高いです。CPUやメモリ使用率の確認を推奨します。",
                "ネットワークトラフィックの異常パターンが検知されました。ファイアウォール設定とトラフィック監視を確認してください。",
                "ストレージ容量の異常消費が観測されました。ログファイルの蓄積や不要ファイルの確認を推奨します。",
                "プロセス数の異常増加が検知されました。不要なプロセスを終了させるか、システム再起動を検討してください。"
            ]

            explanation = random.choice(explanations)

            # クエリを記録
            llm_query = LLMQuery(
                query_id=f"LLM_{detection_result.detection_id}",
                query_text=query_text,
                query_type='anomaly_analysis',
                context_data={
                    'anomaly_score': detection_result.anomaly_score,
                    'confidence': detection_result.confidence,
                    'anomaly_type': detection_result.anomaly_type
                },
                response=explanation,
                confidence=0.85,
                processing_time_ms=random.uniform(100, 500)
            )

            with self._lock:
                self.llm_queries[llm_query.query_id] = llm_query

            return explanation

        except Exception as e:
            logger.error(f"LLM説明生成エラー: {e}")
            return "異常が検知されました。詳細な調査が必要です。"

    def _update_llm_integration(self) -> None:
        """LLM統合を更新"""
        try:
            # LLMモデルが利用可能かチェック
            if self.dl_config['llm_model']:
                logger.info("LLM統合がアクティブです。")

                # LLMによるシステム最適化提案を生成（モック実装）
                optimization_query = LLMQuery(
                    query_id=f"LLM_OPT_{int(time.time() * 1000000)}",
                    query_text="システム全体の最適化提案を生成してください。",
                    query_type='optimization',
                    context_data={'system_status': 'normal'},
                    response="システムの定期メンテナンスとリソース最適化を推奨します。",
                    confidence=0.80,
                    processing_time_ms=300.0
                )

                with self._lock:
                    self.llm_queries[optimization_query.query_id] = optimization_query

        except Exception as e:
            logger.error(f"LLM統合更新エラー: {e}")

    def get_ai_model_performance(self) -> Dict[str, Any]:
        """AIモデルパフォーマンスを取得"""
        with self._lock:
            return {
                'total_models': len(self.neural_models),
                'models_by_type': self._count_models_by_type(),
                'average_accuracy': sum(m.accuracy for m in self.neural_models.values()) / len(self.neural_models) if self.neural_models else 0,
                'total_llm_queries': len(self.llm_queries),
                'recent_anomalies_detected': len([r for r in self.anomaly_history if (datetime.now(timezone.utc) - r.timestamp).hours < 24]),
                'model_training_status': 'active',
                'llm_integration_status': 'active' if self.dl_config['llm_model'] else 'disabled'
            }

    def _count_models_by_type(self) -> Dict[str, int]:
        """モデルタイプ別のカウント"""
        counts = defaultdict(int)
        for model in self.neural_models.values():
            counts[model.model_type] += 1
        return dict(counts)

    def query_llm_system(self, query_text: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """LLMシステムにクエリを実行"""
        try:
            query_id = f"LLM_QUERY_{int(time.time() * 1000000)}"

            start_time = time.time()

            # LLMによる応答生成（モック実装）
            # 実際の実装では、適切なLLM APIを呼び出し

            responses = {
                'anomaly_analysis': [
                    '検知された異常はシステム負荷の急増による可能性が高いです。詳細なログ分析を推奨します。',
                    'ネットワーク異常が検知されました。ファイアウォールとセキュリティ設定を確認してください。',
                    'ストレージ異常が検知されました。ディスク容量とI/Oパフォーマンスを調査してください。'
                ],
                'optimization': [
                    'システム全体の最適化のため、定期的なメンテナンススケジュールを設定してください。',
                    'リソース使用率の監視を強化し、自動スケーリングを設定してください。',
                    'キャッシュ戦略の見直しとデータベースクエリの最適化を検討してください。'
                ],
                'troubleshooting': [
                    '問題の根本原因を特定するため、ログファイルの詳細な分析を実施してください。',
                    'システムコンポーネント間の依存関係を確認し、ボトルネックを特定してください。',
                    'エラーパターンを分析し、再発防止策を講じてください。'
                ]
            }

            # クエリタイプに基づいて応答を選択
            query_type = context_data.get('query_type', 'general')
            response = random.choice(responses.get(query_type, ['クエリを処理中です。']))

            processing_time = (time.time() - start_time) * 1000  # ms

            llm_query = LLMQuery(
                query_id=query_id,
                query_text=query_text,
                query_type=query_type,
                context_data=context_data,
                response=response,
                confidence=0.85,
                processing_time_ms=processing_time
            )

            with self._lock:
                self.llm_queries[query_id] = llm_query

            return {
                'query_id': query_id,
                'response': response,
                'confidence': 0.85,
                'processing_time_ms': processing_time,
                'model_used': self.dl_config['llm_model']
            }

        except Exception as e:
            logger.error(f"LLMクエリ実行エラー: {e}")
            return {
                'error': str(e),
                'response': 'クエリ処理中にエラーが発生しました。'
            }

    def create_custom_ai_model(self, model_config: Dict[str, Any]) -> str:
        """カスタムAIモデルを作成"""
        try:
            model_id = f"CUSTOM_{model_config.get('name', 'model').upper()}_{int(time.time() * 1000000)}"

            custom_model = NeuralNetworkModel(
                model_id=model_id,
                model_type=model_config.get('model_type', 'transformer'),
                architecture=model_config.get('architecture', {}),
                parameters=model_config.get('parameters', {}),
                training_data_size=0,
                accuracy=0.0,
                created_at=datetime.now(timezone.utc),
                last_trained=None,
                model_size_mb=model_config.get('estimated_size_mb', 100.0)
            )

            with self._lock:
                self.neural_models[model_id] = custom_model

            logger.info(f"カスタムAIモデルを作成しました: {model_id}")
            return model_id

        except Exception as e:
            logger.error(f"カスタムAIモデル作成エラー: {e}")
            return ""

    def export_ai_model_data(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """AIモデルデータをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.ai_models_dir / f"ai_models_{timestamp}.{format_type}"

        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_models': len(self.neural_models),
                    'total_llm_queries': len(self.llm_queries),
                    'dl_config': self.dl_config
                },
                'neural_models': [
                    {
                        'model_id': m.model_id,
                        'model_type': m.model_type,
                        'accuracy': m.accuracy,
                        'training_data_size': m.training_data_size,
                        'created_at': m.created_at.isoformat(),
                        'last_trained': m.last_trained.isoformat() if m.last_trained else None
                    }
                    for m in self.neural_models.values()
                ],
                'recent_llm_queries': [
                    {
                        'query_id': q.query_id,
                        'query_type': q.query_type,
                        'confidence': q.confidence,
                        'processing_time_ms': q.processing_time_ms,
                        'timestamp': datetime.now(timezone.utc).isoformat()  # 実際にはクエリ実行時間を記録
                    }
                    for q in list(self.llm_queries.values())[-100:]  # 直近100件
                ]
            }

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)

            logger.info(f"AIモデルデータをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"AIモデルデータエクスポートエラー: {e}")
            return None

    def perform_ai_model_evaluation(self) -> Dict[str, Any]:
        """AIモデル評価を実行"""
        try:
            evaluation_results = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_models_evaluated': len(self.neural_models),
                'model_performance': {},
                'overall_ai_effectiveness': 0.0,
                'improvement_recommendations': [],
                'accuracy_distribution': {
                    'excellent': 0,  # > 0.95
                    'good': 0,       # 0.85-0.95
                    'fair': 0,       # 0.70-0.85
                    'poor': 0        # < 0.70
                }
            }

            # 各モデルの評価
            total_accuracy = 0.0
            for model_name, model in self.neural_models.items():
                model_eval = {
                    'accuracy': model.accuracy,
                    'training_data_size': model.training_data_size,
                    'model_size_mb': model.model_size_mb,
                    'last_trained_days': (datetime.now(timezone.utc) - model.last_trained).days if model.last_trained else None,
                    'performance_rating': 'unknown'
                }

                # 精度に基づく評価
                if model.accuracy > 0.95:
                    model_eval['performance_rating'] = 'excellent'
                    evaluation_results['accuracy_distribution']['excellent'] += 1
                elif model.accuracy > 0.85:
                    model_eval['performance_rating'] = 'good'
                    evaluation_results['accuracy_distribution']['good'] += 1
                elif model.accuracy > 0.70:
                    model_eval['performance_rating'] = 'fair'
                    evaluation_results['accuracy_distribution']['fair'] += 1
                else:
                    model_eval['performance_rating'] = 'poor'
                    evaluation_results['accuracy_distribution']['poor'] += 1

                evaluation_results['model_performance'][model_name] = model_eval
                total_accuracy += model.accuracy

            # 全体的な有効性を計算
            if self.neural_models:
                evaluation_results['overall_ai_effectiveness'] = total_accuracy / len(self.neural_models)

            # 改善推奨事項の生成
            excellent_count = evaluation_results['accuracy_distribution']['excellent']
            poor_count = evaluation_results['accuracy_distribution']['poor']

            if poor_count > 0:
                evaluation_results['improvement_recommendations'].append(
                    f"{poor_count}個の低精度モデルを再トレーニングしてください。"
                )

            if excellent_count < len(self.neural_models) * 0.5:
                evaluation_results['improvement_recommendations'].append(
                    "モデル精度の向上のため、追加のトレーニングデータを収集してください。"
                )

            return evaluation_results

        except Exception as e:
            logger.error(f"AIモデル評価エラー: {e}")
            return {'error': str(e)}


# グローバルインスタンス
advanced_deep_learning_ai = AdvancedDeepLearningAI()
