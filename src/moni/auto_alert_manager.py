import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta

class AutoAlertManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.alert_rules: Dict[str, Dict] = {}
        self.active_alerts: Dict[str, datetime] = {}
        self.alert_history: List[Dict] = []
        self.cooldown_period = timedelta(minutes=5)

    def add_rule(self, name: str, condition: Callable, threshold: float, message: str):
        self.alert_rules[name] = {
            'condition': condition,
            'threshold': threshold,
            'message': message,
            'enabled': True
        }
        self.logger.info(f"Added auto alert rule: {name}")

    def check_alerts(self, metrics: Dict[str, float]) -> List[str]:
        current_alerts = []
        now = datetime.now()

        for rule_name, rule in self.alert_rules.items():
            if not rule['enabled']:
                continue

            try:
                if rule['condition'](metrics, rule['threshold']):
                    # Check cooldown
                    if (rule_name not in self.active_alerts or
                        now - self.active_alerts[rule_name] > self.cooldown_period):
                        current_alerts.append(rule['message'])
                        self.active_alerts[rule_name] = now

                        alert_entry = {
                            'timestamp': now.isoformat(),
                            'rule': rule_name,
                            'message': rule['message'],
                            'metrics': metrics
                        }
                        self.alert_history.append(alert_entry)

            except Exception as e:
                self.logger.error(f"Error checking alert rule {rule_name}: {e}")

        return current_alerts

    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        return self.alert_history[-limit:] if self.alert_history else []

    def clear_alerts(self, rule_name: Optional[str] = None):
        if rule_name:
            self.active_alerts.pop(rule_name, None)
            self.logger.info(f"Cleared alert for rule: {rule_name}")
        else:
            self.active_alerts.clear()
            self.logger.info("Cleared all active alerts")

    def disable_rule(self, rule_name: str):
        if rule_name in self.alert_rules:
            self.alert_rules[rule_name]['enabled'] = False
            self.logger.info(f"Disabled alert rule: {rule_name}")

    def enable_rule(self, rule_name: str):
        if rule_name in self.alert_rules:
            self.alert_rules[rule_name]['enabled'] = True
            self.logger.info(f"Enabled alert rule: {rule_name}")
