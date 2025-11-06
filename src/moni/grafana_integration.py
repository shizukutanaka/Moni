"""
Grafana dashboard and visualization integration

Grafana provides rich visualization and alerting capabilities.
Key features:
- Dashboard management via API
- Alert configuration
- Data source integration
- User and team management
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class Dashboard:
    """Grafana dashboard configuration"""
    title: str
    description: str
    tags: List[str]
    timezone: str = "UTC"
    panels: List[Dict[str, Any]] | None = None
    refresh: str = "30s"
    version: int = 0
    uid: str = ""


@dataclass
class Alert:
    """Grafana alert rule"""
    name: str
    condition: str  # Metric condition
    duration: str  # e.g., "5m"
    severity: str  # critical, high, medium, low
    notification_channel: str
    annotations: Dict[str, str] | None = None


@dataclass
class DataSource:
    """Grafana data source configuration"""
    name: str
    type: str  # prometheus, loki, tempo, etc.
    url: str
    is_default: bool = False
    access: str = "proxy"
    basic_auth: bool = False
    username: str = ""
    password: str = ""


class GrafanaClient:
    """Grafana API client"""

    def __init__(
        self,
        endpoint: str = "http://localhost:3000",
        api_key: str = "",
        username: str = "admin",
        password: str = "admin",
    ):
        """
        Initialize Grafana client

        Args:
            endpoint: Grafana server endpoint
            api_key: Grafana API key (alternative to username/password)
            username: Username for basic auth
            password: Password for basic auth
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.username = username
        self.password = password

        self._verify_connection()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for Grafana API"""
        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _verify_connection(self) -> bool:
        """Verify Grafana server is accessible"""
        try:
            response = requests.get(
                f"{self.endpoint}/api/health",
                headers=self._get_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"Connected to Grafana at {self.endpoint}")
                return True
        except requests.RequestException as e:
            logger.warning(f"Grafana connection failed: {e}")
            return False

    def create_datasource(self, datasource: DataSource) -> Optional[Dict[str, Any]]:
        """
        Create a data source in Grafana

        Args:
            datasource: DataSource configuration

        Returns:
            Created datasource info or None
        """
        payload = {
            "name": datasource.name,
            "type": datasource.type,
            "url": datasource.url,
            "isDefault": datasource.is_default,
            "access": datasource.access,
        }

        if datasource.basic_auth:
            payload["basicAuth"] = True
            payload["basicAuthUser"] = datasource.username
            payload["secureJsonData"] = {
                "basicAuthPassword": datasource.password
            }

        try:
            response = requests.post(
                f"{self.endpoint}/api/datasources",
                json=payload,
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                logger.info(f"Created datasource: {datasource.name}")
                return response.json()
            else:
                logger.error(f"Failed to create datasource: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Datasource creation error: {e}")
            return None

    def create_dashboard(self, dashboard: Dashboard) -> Optional[Dict[str, Any]]:
        """
        Create a dashboard in Grafana

        Args:
            dashboard: Dashboard configuration

        Returns:
            Created dashboard info or None
        """
        dashboard_json = {
            "dashboard": {
                "title": dashboard.title,
                "description": dashboard.description,
                "tags": dashboard.tags,
                "timezone": dashboard.timezone,
                "refresh": dashboard.refresh,
                "version": dashboard.version,
                "panels": dashboard.panels or [],
            },
            "overwrite": True,
        }

        try:
            response = requests.post(
                f"{self.endpoint}/api/dashboards/db",
                json=dashboard_json,
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Created dashboard: {dashboard.title}")
                return result
            else:
                logger.error(f"Failed to create dashboard: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Dashboard creation error: {e}")
            return None

    def create_alert(self, alert: Alert) -> Optional[Dict[str, Any]]:
        """
        Create an alert rule in Grafana

        Args:
            alert: Alert configuration

        Returns:
            Created alert info or None
        """
        payload = {
            "title": alert.name,
            "condition": alert.condition,
            "duration": alert.duration,
            "severity": alert.severity,
            "annotations": alert.annotations or {},
        }

        try:
            response = requests.post(
                f"{self.endpoint}/api/v1/rules",
                json=payload,
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 201:
                logger.info(f"Created alert: {alert.name}")
                return response.json()
            else:
                logger.error(f"Failed to create alert: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Alert creation error: {e}")
            return None

    def list_datasources(self) -> List[Dict[str, Any]]:
        """
        List all data sources in Grafana

        Returns:
            List of datasources
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/datasources",
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list datasources: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"List datasources error: {e}")
            return []

    def list_dashboards(self) -> List[Dict[str, Any]]:
        """
        List all dashboards in Grafana

        Returns:
            List of dashboards
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/search?type=dash-db",
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to list dashboards: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"List dashboards error: {e}")
            return []

    def get_dashboard(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get dashboard by UID

        Args:
            uid: Dashboard UID

        Returns:
            Dashboard data or None
        """
        try:
            response = requests.get(
                f"{self.endpoint}/api/dashboards/uid/{uid}",
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get dashboard: {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Get dashboard error: {e}")
            return None

    def delete_dashboard(self, uid: str) -> bool:
        """
        Delete dashboard by UID

        Args:
            uid: Dashboard UID

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.delete(
                f"{self.endpoint}/api/dashboards/uid/{uid}",
                headers=self._get_headers(),
                timeout=10,
                auth=(self.username, self.password) if not self.api_key else None,
            )

            if response.status_code == 200:
                logger.info(f"Deleted dashboard: {uid}")
                return True
            else:
                logger.error(f"Failed to delete dashboard: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Delete dashboard error: {e}")
            return False
