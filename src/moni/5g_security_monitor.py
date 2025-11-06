import logging
from typing import Dict, List, Optional
import time

class FiveGSecurityMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.network_slices: Dict[str, Dict] = {}
        self.threats_detected: List[Dict] = []
        self.monitoring_active = False

    def register_network_slice(self, slice_id: str, slice_info: Dict) -> bool:
        """Register a 5G network slice for monitoring"""
        self.network_slices[slice_id] = {
            'info': slice_info,
            'security_level': slice_info.get('security_level', 'standard'),
            'traffic_baseline': {},
            'alerts': [],
            'last_activity': time.time()
        }
        self.logger.info(f"Registered 5G network slice: {slice_id}")
        return True

    def monitor_slice_traffic(self, slice_id: str) -> Dict[str, str]:
        """Monitor traffic patterns in a specific network slice"""
        if slice_id not in self.network_slices:
            return {'error': 'Slice not registered'}

        slice_data = self.network_slices[slice_id]

        # Simulate traffic monitoring
        current_traffic = self._analyze_traffic_patterns(slice_id)

        # Detect anomalies
        anomalies = self._detect_anomalies(slice_id, current_traffic)

        if anomalies:
            self.threats_detected.append({
                'timestamp': time.time(),
                'slice_id': slice_id,
                'threat_type': 'traffic_anomaly',
                'severity': 'medium',
                'description': f"Unusual traffic pattern detected in slice {slice_id}"
            })

        return {
            'slice_id': slice_id,
            'status': 'active',
            'traffic_volume': current_traffic.get('volume', 0),
            'anomalies': len(anomalies),
            'security_score': self._calculate_security_score(slice_id)
        }

    def _analyze_traffic_patterns(self, slice_id: str) -> Dict:
        """Analyze traffic patterns for anomaly detection"""
        # Simulate traffic analysis
        return {
            'volume': 1000 + (hash(slice_id) % 5000),  # Simulated volume
            'packet_rate': 100 + (hash(slice_id) % 200),  # Simulated packet rate
            'protocol_distribution': {'TCP': 60, 'UDP': 30, 'ICMP': 10}
        }

    def _detect_anomalies(self, slice_id: str, traffic: Dict) -> List[str]:
        """Detect anomalous traffic patterns"""
        anomalies = []
        slice_data = self.network_slices[slice_id]

        # Check for unusual volume spikes
        baseline = slice_data.get('traffic_baseline', {})
        if baseline:
            volume_threshold = baseline.get('max_volume', 5000)
            if traffic.get('volume', 0) > volume_threshold * 1.5:
                anomalies.append('volume_spike')

        # Check for protocol anomalies
        protocols = traffic.get('protocol_distribution', {})
        if protocols.get('ICMP', 0) > 50:  # Unusual ICMP traffic
            anomalies.append('icmp_flood')

        return anomalies

    def _calculate_security_score(self, slice_id: str) -> float:
        """Calculate security score for a network slice"""
        slice_data = self.network_slices[slice_id]

        # Base score calculation
        base_score = 100.0

        # Deduct points for threats
        for threat in self.threats_detected:
            if threat['slice_id'] == slice_id:
                if threat['severity'] == 'high':
                    base_score -= 30
                elif threat['severity'] == 'medium':
                    base_score -= 15
                elif threat['severity'] == 'low':
                    base_score -= 5

        # Deduct points for configuration issues
        if slice_data['security_level'] == 'basic':
            base_score -= 10

        return max(0, min(100, base_score))

    def get_threat_summary(self) -> Dict[str, int]:
        """Get summary of detected threats"""
        summary = {'high': 0, 'medium': 0, 'low': 0}

        for threat in self.threats_detected:
            severity = threat.get('severity', 'medium')
            summary[severity] += 1

        return summary

    def start_monitoring(self):
        """Start 5G network security monitoring"""
        self.monitoring_active = True
        self.logger.info("5G network security monitoring started")

    def stop_monitoring(self):
        """Stop 5G network security monitoring"""
        self.monitoring_active = False
        self.logger.info("5G network security monitoring stopped")
