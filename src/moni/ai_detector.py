import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class AIDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1)
        self.scaler = StandardScaler()
        self.trained = False

    def train(self, data):
        scaled_data = self.scaler.fit_transform(data)
        self.model.fit(scaled_data)
        self.trained = True

    def detect_anomaly(self, data):
        if not self.trained:
            raise ValueError("Model not trained")
        scaled_data = self.scaler.transform(data)
        return self.model.predict(scaled_data) == -1  # -1 for anomaly
