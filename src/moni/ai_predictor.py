"""
AI/ML Prediction Module for System Monitoring

This module provides AI-powered predictions and anomaly detection for system metrics.
It uses machine learning models to forecast future system behavior and detect
abnormal patterns that may indicate issues.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import threading

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller
try:
    import nltk
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    HAS_NLP = True
except ImportError:
    HAS_NLP = False
    logger.warning("NLTK not available, NLP features disabled")

from .metrics import get_history, add_to_history

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Container for prediction results."""
    metric_name: str
    predicted_value: float
    confidence: float
    trend: str
    anomaly_score: float
    is_anomaly: bool
    timestamp: float
    seasonality_detected: bool = False
    forecast_values: Optional[List[float]] = None
    forecast_timestamps: Optional[List[float]] = None


@dataclass
class TimeSeriesAnalysis:
    """Container for time series analysis results."""
    trend: str
    seasonality: bool
    stationarity: bool
    forecast_accuracy: float
    components: Dict[str, Any]


class AIPredictor:
    """
    AI-powered predictor for system metrics using machine learning models.

    This class provides:
    - Time series forecasting for system metrics (ARIMA, Prophet)
    - Anomaly detection using isolation forests
    - Trend analysis and confidence scoring
    - Seasonality detection and decomposition
    """

    def __init__(self, history_window: int = 100, prediction_horizon: int = 5):
        """
        Initialize the AI predictor.

        Args:
            history_window: Number of historical data points to use for training
            prediction_horizon: Number of steps ahead to predict
        """
        self.history_window = history_window
        self.prediction_horizon = prediction_horizon

        # Models for different metrics
        self.regression_models: Dict[str, LinearRegression] = {}
        self.arima_models: Dict[str, ARIMA] = {}
        self.prophet_models: Dict[str, Any] = {}
        self.anomaly_models: Dict[str, IsolationForest] = {}
        self.scalers: Dict[str, StandardScaler] = {}

        # Thread safety
        self._lock = threading.Lock()

        # Prediction cache
        self._prediction_cache: Dict[str, PredictionResult] = {}
        self._analysis_cache: Dict[str, TimeSeriesAnalysis] = {}
        self._cache_timeout = 60  # seconds
        self._last_prediction_time: Dict[str, float] = {}

    def predict_metric(self, metric_name: str) -> Optional[PredictionResult]:
        """
        Predict future values for a given metric using historical data.

        Args:
            metric_name: Name of the metric to predict

        Returns:
            PredictionResult if successful, None if insufficient data
        """
        try:
            # Check cache first
            current_time = time.time()
            if (metric_name in self._prediction_cache and
                current_time - self._last_prediction_time.get(metric_name, 0) < self._cache_timeout):
                return self._prediction_cache[metric_name]

            # Get historical data
            history = get_history(metric_name, max_age_seconds=3600)  # Last hour

            if len(history) < self.history_window:
                logger.debug(f"Insufficient data for {metric_name}: {len(history)}/{self.history_window}")
                return None

            with self._lock:
                # Perform time series analysis
                analysis = self._analyze_time_series(history)

                # Choose best forecasting method
                forecast_result = self._forecast_time_series(metric_name, history, analysis)

                # Anomaly detection
                anomaly_score, is_anomaly = self._detect_anomaly(metric_name, history)

                result = PredictionResult(
                    metric_name=metric_name,
                    predicted_value=forecast_result['value'],
                    confidence=forecast_result['confidence'],
                    trend=analysis.trend,
                    anomaly_score=anomaly_score,
                    is_anomaly=is_anomaly,
                    timestamp=current_time,
                    seasonality_detected=analysis.seasonality,
                    forecast_values=forecast_result.get('forecast_values'),
                    forecast_timestamps=forecast_result.get('forecast_timestamps')
                )

                # Cache result
                self._prediction_cache[metric_name] = result
                self._analysis_cache[metric_name] = analysis
                self._last_prediction_time[metric_name] = current_time

                return result

        except Exception as e:
            logger.error(f"Prediction failed for {metric_name}: {e}")
            return None

    def _analyze_time_series(self, values: List[float]) -> TimeSeriesAnalysis:
        """Perform comprehensive time series analysis."""
        try:
            if len(values) < 20:
                return TimeSeriesAnalysis(
                    trend="Unknown",
                    seasonality=False,
                    stationarity=False,
                    forecast_accuracy=0.0,
                    components={}
                )

            # Convert to pandas Series for analysis
            ts = pd.Series(values)

            # Test for stationarity
            try:
                adf_result = adfuller(ts.values, autolag='AIC')
                stationarity = adf_result[1] < 0.05  # p-value < 0.05
            except:
                stationarity = False

            # Detect seasonality (if enough data)
            seasonality = False
            components = {}

            if len(ts) >= 24:  # Need at least 24 points for seasonal decomposition
                try:
                    # Try to detect seasonality
                    decomposition = seasonal_decompose(ts, model='additive', period=min(12, len(ts)//2))
                    seasonal_std = decomposition.seasonal.std()
                    residual_std = decomposition.resid.std()

                    # If seasonal variation is significant compared to residual
                    seasonality = seasonal_std > residual_std * 0.5

                    components = {
                        'trend': decomposition.trend.tolist(),
                        'seasonal': decomposition.seasonal.tolist(),
                        'residual': decomposition.resid.tolist()
                    }
                except:
                    seasonality = False

            # Determine trend
            trend = self._calculate_trend(values)

            return TimeSeriesAnalysis(
                trend=trend,
                seasonality=seasonality,
                stationarity=stationarity,
                forecast_accuracy=0.8,  # Placeholder, will be updated by forecasting
                components=components
            )

        except Exception as e:
            logger.error(f"Time series analysis failed: {e}")
            return TimeSeriesAnalysis(
                trend="Unknown",
                seasonality=False,
                stationarity=False,
                forecast_accuracy=0.0,
                components={}
            )

    def _forecast_time_series(self, metric_name: str, values: List[float],
                            analysis: TimeSeriesAnalysis) -> Dict[str, Any]:
        """Choose and execute the best forecasting method."""
        try:
            if len(values) < 10:
                return {'value': values[-1], 'confidence': 0.0}

            # Choose forecasting method based on data characteristics
            if HAS_PROPHET and analysis.seasonality and len(values) >= 50:
                # Use Prophet for seasonal data
                return self._forecast_with_prophet(metric_name, values)
            elif analysis.stationarity or len(values) >= 30:
                # Use ARIMA for stationary or longer series
                return self._forecast_with_arima(metric_name, values)
            else:
                # Use linear regression as fallback
                return self._forecast_with_regression(metric_name, values)

        except Exception as e:
            logger.error(f"Forecasting failed for {metric_name}: {e}")
            return {'value': values[-1], 'confidence': 0.0}

    def _forecast_with_prophet(self, metric_name: str, values: List[float]) -> Dict[str, Any]:
        """Forecast using Facebook Prophet."""
        try:
            # Create DataFrame for Prophet
            timestamps = pd.date_range(start='2020-01-01', periods=len(values), freq='1min')
            df = pd.DataFrame({'ds': timestamps, 'y': values})

            # Initialize and fit model
            if metric_name not in self.prophet_models:
                model = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=False,
                    daily_seasonality=True if len(values) >= 1440 else False,  # Daily if we have enough data
                    changepoint_prior_scale=0.05
                )
                self.prophet_models[metric_name] = model
            else:
                model = self.prophet_models[metric_name]

            model.fit(df)

            # Make forecast
            future = model.make_future_dataframe(periods=self.prediction_horizon, freq='1min')
            forecast = model.predict(future)

            # Extract predictions
            forecast_values = forecast['yhat'].tail(self.prediction_horizon).tolist()
            forecast_timestamps = [t.timestamp() for t in future['ds'].tail(self.prediction_horizon)]

            return {
                'value': forecast_values[0],
                'confidence': 0.85,  # Prophet typically has good accuracy
                'forecast_values': forecast_values,
                'forecast_timestamps': forecast_timestamps
            }

        except Exception as e:
            logger.error(f"Prophet forecasting failed: {e}")
            # Fallback to regression
            return self._forecast_with_regression(metric_name, values)

    def _forecast_with_arima(self, metric_name: str, values: List[float]) -> Dict[str, Any]:
        """Forecast using ARIMA model."""
        try:
            # Fit ARIMA model (simple order for now)
            if metric_name not in self.arima_models:
                # Auto-select order (simplified)
                p, d, q = 1, 0, 1  # Simple ARIMA(1,0,1)
                model = ARIMA(values, order=(p, d, q))
                fitted_model = model.fit()
                self.arima_models[metric_name] = fitted_model
            else:
                fitted_model = self.arima_models[metric_name]

            # Forecast
            forecast_result = fitted_model.forecast(steps=self.prediction_horizon)

            # Calculate confidence
            try:
                conf_int = fitted_model.get_forecast(steps=self.prediction_horizon).conf_int()
                confidence = min(0.9, 1.0 - (conf_int.iloc[0, 1] - conf_int.iloc[0, 0]) / abs(forecast_result.iloc[0]))
            except:
                confidence = 0.7

            return {
                'value': float(forecast_result.iloc[0]),
                'confidence': confidence,
                'forecast_values': forecast_result.tolist(),
                'forecast_timestamps': None  # ARIMA doesn't provide timestamps
            }

        except Exception as e:
            logger.error(f"ARIMA forecasting failed: {e}")
            return self._forecast_with_regression(metric_name, values)

    def _forecast_with_regression(self, metric_name: str, values: List[float]) -> Dict[str, Any]:
        """Forecast using linear regression (fallback method)."""
        try:
            data = np.array(values[-self.history_window:]).reshape(-1, 1)

            if metric_name not in self.regression_models:
                self.regression_models[metric_name] = LinearRegression()
                self.scalers[metric_name] = StandardScaler()

            scaler = self.scalers[metric_name]
            scaled_data = scaler.fit_transform(data)

            X = np.arange(len(scaled_data)).reshape(-1, 1)
            y = scaled_data.flatten()

            model = self.regression_models[metric_name]
            model.fit(X, y)

            # Make prediction
            future_time = np.array([[len(scaled_data) + self.prediction_horizon - 1]])
            predicted_scaled = model.predict(future_time)[0]
            predicted_value = float(scaler.inverse_transform([[predicted_scaled]])[0][0])

            confidence = max(0.0, min(1.0, model.score(X, y)))

            return {
                'value': predicted_value,
                'confidence': confidence
            }

        except Exception as e:
            logger.error(f"Regression forecasting failed: {e}")
            return {'value': values[-1], 'confidence': 0.0}

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from historical values."""
        if len(values) < 10:
            return "Unknown"

        # Compare first and second half
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        diff = second_avg - first_avg
        threshold = max(values) * 0.05  # 5% of max value

        if diff > threshold:
            return "Increasing"
        elif diff < -threshold:
            return "Decreasing"
        else:
            return "Stable"

    def _detect_anomaly(self, metric_name: str, values: List[float]) -> Tuple[float, bool]:
        """
        Detect anomalies in the metric data.

        Returns:
            Tuple of (anomaly_score, is_anomaly)
        """
        try:
            if len(values) < 20:  # Need minimum data for anomaly detection
                return 0.0, False

            with self._lock:
                # Train/update anomaly detection model
                if metric_name not in self.anomaly_models:
                    self.anomaly_models[metric_name] = IsolationForest(
                        contamination=0.1,  # Expect 10% anomalies
                        random_state=42,
                        n_estimators=50
                    )

                model = self.anomaly_models[metric_name]

                # Prepare data
                data = np.array(values).reshape(-1, 1)

                # Fit model (if not already fitted or data has changed significantly)
                model.fit(data)

                # Get anomaly scores for recent values
                scores = model.decision_function(data)

                # Use the most recent score
                anomaly_score = float(scores[-1])

                # IsolationForest returns negative scores for anomalies
                # Convert to 0-1 scale where 1 is most anomalous
                is_anomaly = anomaly_score < -0.5  # Threshold for anomaly detection

                return anomaly_score, is_anomaly

        except Exception as e:
            logger.error(f"Anomaly detection failed for {metric_name}: {e}")
            return 0.0, False

    def get_predictions_for_metrics(self, metric_names: List[str]) -> Dict[str, PredictionResult]:
        """Get predictions for multiple metrics."""
        results = {}
        for metric_name in metric_names:
            prediction = self.predict_metric(metric_name)
            if prediction:
                results[metric_name] = prediction
        return results

    def analyze_log_text(self, log_text: str) -> Dict[str, Any]:
        """
        Analyze log text using NLP for anomaly detection and pattern recognition.

        Args:
            log_text: Raw log text to analyze

        Returns:
            Dictionary with analysis results
        """
        if not HAS_NLP:
            return {"error": "NLP not available"}

        try:
            # Tokenize and preprocess text
            sentences = sent_tokenize(log_text)
            words = word_tokenize(log_text.lower())

            # Remove stopwords and lemmatize
            stop_words = set(stopwords.words('english'))
            lemmatizer = WordNetLemmatizer()

            filtered_words = [
                lemmatizer.lemmatize(word)
                for word in words
                if word.isalpha() and word not in stop_words
            ]

            # Extract key features
            error_keywords = ['error', 'exception', 'failed', 'timeout', 'crash']
            warning_keywords = ['warning', 'deprecated', 'unusual', 'slow']

            error_count = sum(1 for word in filtered_words if word in error_keywords)
            warning_count = sum(1 for word in filtered_words if word in warning_keywords)

            # Sentiment analysis (simple rule-based)
            negative_words = ['fail', 'error', 'problem', 'issue', 'broken']
            positive_words = ['success', 'completed', 'ok', 'normal']

            negative_score = sum(1 for word in filtered_words if word in negative_words)
            positive_score = sum(1 for word in filtered_words if word in positive_words)

            # Calculate anomaly score based on error density and sentiment
            total_words = len(filtered_words)
            error_density = error_count / max(total_words, 1)
            sentiment_score = (positive_score - negative_score) / max(total_words, 1)

            anomaly_score = max(0, error_density + max(0, -sentiment_score))

            return {
                "error_count": error_count,
                "warning_count": warning_count,
                "error_density": error_density,
                "sentiment_score": sentiment_score,
                "anomaly_score": anomaly_score,
                "is_anomalous": anomaly_score > 0.1,
                "key_phrases": filtered_words[:10],  # Top words
                "sentence_count": len(sentences)
            }

        except Exception as e:
            logger.error(f"NLP analysis failed: {e}")
            return {"error": str(e)}
        # Define key metrics to monitor
        key_metrics = [
            "cpu_percent", "memory_percent", "disk_usage",
            "network_bytes_sent", "network_bytes_recv"
        ]

        anomalies = []
        total_predictions = 0

        for metric in key_metrics:
            prediction = self.predict_metric(metric)
            if prediction and prediction.is_anomaly:
                anomalies.append({
                    "metric": metric,
                    "score": prediction.anomaly_score,
                    "current_trend": prediction.trend
                })
            if prediction:
                total_predictions += 1

        return {
            "total_anomalies": len(anomalies),
            "anomalies": anomalies[:5],  # Top 5 anomalies
            "total_monitored": total_predictions
        }


# Global AI predictor instance
_ai_predictor = AIPredictor()


def get_ai_predictor() -> AIPredictor:
    """Get the global AI predictor instance."""
    return _ai_predictor


def ai_prediction_collector() -> Dict[str, str]:
    """
    Metric collector for AI predictions and anomaly detection.
    This function integrates with the main metrics system.
    """
    try:
        predictor = get_ai_predictor()
        summary = predictor.get_anomaly_summary()

        result = {}

        # Anomaly summary
        anomaly_count = summary["total_anomalies"]
        if anomaly_count > 0:
            result["🚨 Anomalies Detected"] = f"{anomaly_count} metrics showing unusual patterns"
        else:
            result["✅ System Normal"] = "No anomalies detected"

        # Individual predictions for key metrics
        key_metrics = ["cpu_percent", "memory_percent"]
        predictions = predictor.get_predictions_for_metrics(key_metrics)

        for metric, prediction in predictions.items():
            if prediction.is_anomaly:
                status_icon = "⚠️"
            elif prediction.trend == "Increasing":
                status_icon = "📈"
            elif prediction.trend == "Decreasing":
                status_icon = "📉"
            else:
                status_icon = "📊"

            metric_display = metric.replace("_", " ").title()
            result[f"{status_icon} {metric_display}"] = (
                f"Pred: {prediction.predicted_value:.1f} | "
                f"Trend: {prediction.trend} | "
                f"Conf: {prediction.confidence:.2f}"
            )

        return result

    except Exception as e:
        return {"Error": f"AI prediction failed: {str(e)}"}
