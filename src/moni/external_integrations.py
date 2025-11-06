"""
External API Integration Module for System Monitoring

This module provides integration capabilities with external IT service management
and communication tools like ServiceNow, Zendesk, Jira, and Slack.
"""

from __future__ import annotations

import logging
import time
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
import threading
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class APIIntegration:
    """Configuration for an external API integration."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    enabled: bool = True
    timeout: int = 30
    rate_limit: int = 60  # requests per minute


@dataclass
class IntegrationResult:
    """Result of an external API call."""
    success: bool
    response_data: Any
    error_message: str
    response_time: float
    timestamp: float


class ExternalAPIManager:
    """
    Manager for external API integrations.

    Provides unified interface for integrating with popular IT service management
    and communication platforms.
    """

    def __init__(self):
        self.integrations: Dict[str, APIIntegration] = {}
        self._rate_limiters: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Load default integrations
        self._load_default_integrations()

    def _load_default_integrations(self):
        """Load default integration configurations."""
        # These would typically be loaded from config files
        # For now, we'll set up the structure for future configuration
        pass

    def add_integration(self, integration: APIIntegration):
        """Add a new API integration."""
        with self._lock:
            self.integrations[integration.name] = integration
            self._rate_limiters[integration.name] = {
                'requests': [],
                'last_reset': time.time()
            }
            logger.info(f"Added API integration: {integration.name}")

    def remove_integration(self, name: str):
        """Remove an API integration."""
        with self._lock:
            if name in self.integrations:
                del self.integrations[name]
                del self._rate_limiters[name]
                logger.info(f"Removed API integration: {name}")

    def enable_integration(self, name: str, enabled: bool = True):
        """Enable or disable an integration."""
        with self._lock:
            if name in self.integrations:
                self.integrations[name].enabled = enabled
                logger.info(f"{'Enabled' if enabled else 'Disabled'} integration: {name}")

    def _check_rate_limit(self, integration_name: str) -> bool:
        """Check if we're within rate limits."""
        if integration_name not in self.integrations:
            return False

        integration = self.integrations[integration_name]
        rate_limiter = self._rate_limiters[integration_name]

        current_time = time.time()

        # Reset counter if minute has passed
        if current_time - rate_limiter['last_reset'] >= 60:
            rate_limiter['requests'] = []
            rate_limiter['last_reset'] = current_time

        # Clean old requests (older than 1 minute)
        rate_limiter['requests'] = [
            req_time for req_time in rate_limiter['requests']
            if current_time - req_time < 60
        ]

        # Check if we're under the limit
        if len(rate_limiter['requests']) >= integration.rate_limit:
            return False

        # Add current request
        rate_limiter['requests'].append(current_time)
        return True

    def call_api(self, integration_name: str, endpoint: str, method: str = 'GET',
                data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> IntegrationResult:
        """Make an API call to an external service."""
        start_time = time.time()

        try:
            if integration_name not in self.integrations:
                return IntegrationResult(
                    success=False,
                    response_data=None,
                    error_message=f"Integration '{integration_name}' not found",
                    response_time=time.time() - start_time,
                    timestamp=start_time
                )

            integration = self.integrations[integration_name]

            if not integration.enabled:
                return IntegrationResult(
                    success=False,
                    response_data=None,
                    error_message=f"Integration '{integration_name}' is disabled",
                    response_time=time.time() - start_time,
                    timestamp=start_time
                )

            # Check rate limit
            if not self._check_rate_limit(integration_name):
                return IntegrationResult(
                    success=False,
                    response_data=None,
                    error_message="Rate limit exceeded",
                    response_time=time.time() - start_time,
                    timestamp=start_time
                )

            # Build URL
            url = f"{integration.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

            # Build headers
            request_headers = headers or {}
            if integration.api_key:
                request_headers['Authorization'] = f"Bearer {integration.api_key}"
            elif integration.token:
                request_headers['Authorization'] = f"Token {integration.token}"
            elif integration.username and integration.password:
                import base64
                auth_string = base64.b64encode(f"{integration.username}:{integration.password}".encode()).decode()
                request_headers['Authorization'] = f"Basic {auth_string}"

            # Set content type for JSON data
            if data and not any('content-type' in h.lower() for h in request_headers):
                request_headers['Content-Type'] = 'application/json'

            # Prepare request data
            request_data = json.dumps(data) if data and isinstance(data, dict) else data

            # Make request
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                data=request_data,
                timeout=integration.timeout
            )

            # Check response
            if response.status_code >= 200 and response.status_code < 300:
                try:
                    response_data = response.json()
                except:
                    response_data = response.text

                return IntegrationResult(
                    success=True,
                    response_data=response_data,
                    error_message="",
                    response_time=time.time() - start_time,
                    timestamp=start_time
                )
            else:
                return IntegrationResult(
                    success=False,
                    response_data=None,
                    error_message=f"HTTP {response.status_code}: {response.text}",
                    response_time=time.time() - start_time,
                    timestamp=start_time
                )

        except requests.exceptions.RequestException as e:
            return IntegrationResult(
                success=False,
                response_data=None,
                error_message=f"Request failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=start_time
            )
        except Exception as e:
            return IntegrationResult(
                success=False,
                response_data=None,
                error_message=f"Unexpected error: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=start_time
            )


class ServiceNowIntegration:
    """Integration with ServiceNow ITSM."""

    def __init__(self, manager: ExternalAPIManager):
        self.manager = manager

    def create_incident(self, short_description: str, description: str,
                       priority: str = "3", category: str = "software") -> Optional[str]:
        """Create an incident in ServiceNow."""
        data = {
            "short_description": short_description,
            "description": description,
            "priority": priority,
            "category": category,
            "caller_id": "system_monitor",
            "contact_type": "monitoring_system"
        }

        result = self.manager.call_api(
            "servicenow",
            "api/now/table/incident",
            method="POST",
            data=data
        )

        if result.success and result.response_data:
            return result.response_data.get('result', {}).get('number')
        return None

    def update_incident(self, incident_number: str, updates: Dict[str, Any]) -> bool:
        """Update an incident in ServiceNow."""
        result = self.manager.call_api(
            "servicenow",
            f"api/now/table/incident",
            method="PATCH",
            data=updates
        )
        return result.success


class ZendeskIntegration:
    """Integration with Zendesk Support."""

    def __init__(self, manager: ExternalAPIManager):
        self.manager = manager

    def create_ticket(self, subject: str, description: str,
                     priority: str = "normal", tags: Optional[List[str]] = None) -> Optional[str]:
        """Create a ticket in Zendesk."""
        data = {
            "ticket": {
                "subject": subject,
                "comment": {"body": description},
                "priority": priority,
                "tags": tags or []
            }
        }

        result = self.manager.call_api(
            "zendesk",
            "api/v2/tickets.json",
            method="POST",
            data=data
        )

        if result.success and result.response_data:
            return str(result.response_data.get('ticket', {}).get('id'))
        return None

    def add_comment(self, ticket_id: str, comment: str, is_public: bool = True) -> bool:
        """Add a comment to a Zendesk ticket."""
        data = {
            "ticket": {
                "comment": {
                    "body": comment,
                    "public": is_public
                }
            }
        }

        result = self.manager.call_api(
            "zendesk",
            f"api/v2/tickets/{ticket_id}.json",
            method="PUT",
            data=data
        )
        return result.success


class JiraIntegration:
    """Integration with Atlassian Jira."""

    def __init__(self, manager: ExternalAPIManager):
        self.manager = manager

    def create_issue(self, project_key: str, summary: str, description: str,
                    issue_type: str = "Bug", priority: str = "Medium") -> Optional[str]:
        """Create an issue in Jira."""
        data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority}
            }
        }

        result = self.manager.call_api(
            "jira",
            "rest/api/3/issue",
            method="POST",
            data=data
        )

        if result.success and result.response_data:
            return result.response_data.get('key')
        return None

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to a Jira issue."""
        data = {
            "body": comment
        }

        result = self.manager.call_api(
            "jira",
            f"rest/api/3/issue/{issue_key}/comment",
            method="POST",
            data=data
        )
        return result.success


class SlackIntegration:
    """Integration with Slack for notifications."""

    def __init__(self, manager: ExternalAPIManager):
        self.manager = manager

    def send_message(self, channel: str, message: str,
                    username: str = "System Monitor", icon_emoji: str = ":warning:") -> bool:
        """Send a message to a Slack channel."""
        data = {
            "channel": channel,
            "text": message,
            "username": username,
            "icon_emoji": icon_emoji
        }

        result = self.manager.call_api(
            "slack",
            "api/chat.postMessage",
            method="POST",
            data=data
        )
        return result.success

    def send_alert(self, channel: str, alert_title: str, alert_details: Dict[str, Any],
                  color: str = "danger") -> bool:
        """Send a formatted alert message to Slack."""
        attachment = {
            "color": color,
            "title": alert_title,
            "fields": [
                {"title": key, "value": str(value), "short": True}
                for key, value in alert_details.items()
            ],
            "footer": "System Monitor",
            "ts": int(time.time())
        }

        data = {
            "channel": channel,
            "attachments": [attachment],
            "username": "System Monitor",
            "icon_emoji": ":rotating_light:"
        }

        result = self.manager.call_api(
            "slack",
            "api/chat.postMessage",
            method="POST",
            data=data
        )
        return result.success


class ExternalIntegrationManager:
    """
    High-level manager for all external integrations.
    Provides unified interface for different IT service management tools.
    """

    def __init__(self):
        self.api_manager = ExternalAPIManager()
        self.servicenow = ServiceNowIntegration(self.api_manager)
        self.zendesk = ZendeskIntegration(self.api_manager)
        self.jira = JiraIntegration(self.api_manager)
        self.slack = SlackIntegration(self.api_manager)

    def configure_servicenow(self, base_url: str, username: str, password: str):
        """Configure ServiceNow integration."""
        integration = APIIntegration(
            name="servicenow",
            base_url=base_url,
            username=username,
            password=password
        )
        self.api_manager.add_integration(integration)

    def configure_zendesk(self, base_url: str, api_key: str):
        """Configure Zendesk integration."""
        integration = APIIntegration(
            name="zendesk",
            base_url=base_url,
            api_key=api_key
        )
        self.api_manager.add_integration(integration)

    def configure_jira(self, base_url: str, username: str, token: str):
        """Configure Jira integration."""
        integration = APIIntegration(
            name="jira",
            base_url=base_url,
            username=username,
            token=token
        )
        self.api_manager.add_integration(integration)

    def configure_slack(self, webhook_url: str):
        """Configure Slack integration."""
        # Slack uses webhook URL directly, so we store it as base_url
        integration = APIIntegration(
            name="slack",
            base_url=webhook_url
        )
        self.api_manager.add_integration(integration)

    def send_alert_to_all(self, alert_data: Dict[str, Any]):
        """Send alert to all configured integrations."""
        alert_title = alert_data.get('title', 'System Alert')
        alert_details = {
            'Metric': alert_data.get('metric', 'Unknown'),
            'Value': f"{alert_data.get('value', 'N/A')} {alert_data.get('unit', '')}",
            'Threshold': f"{alert_data.get('threshold', 'N/A')} {alert_data.get('unit', '')}",
            'Severity': alert_data.get('severity', 'unknown')
        }

        # Send to ServiceNow
        if "servicenow" in self.api_manager.integrations:
            incident_number = self.servicenow.create_incident(
                short_description=alert_title,
                description=f"System monitoring alert: {alert_data.get('description', '')}"
            )
            if incident_number:
                logger.info(f"Created ServiceNow incident: {incident_number}")

        # Send to Zendesk
        if "zendesk" in self.api_manager.integrations:
            ticket_id = self.zendesk.create_ticket(
                subject=alert_title,
                description=f"System monitoring alert: {alert_data.get('description', '')}",
                priority=alert_data.get('severity', 'normal')
            )
            if ticket_id:
                logger.info(f"Created Zendesk ticket: {ticket_id}")

        # Send to Jira
        if "jira" in self.api_manager.integrations:
            # Would need project key from configuration
            pass

        # Send to Slack
        if "slack" in self.api_manager.integrations:
            color_map = {
                'critical': 'danger',
                'high': 'warning',
                'medium': 'good',
                'low': 'good'
            }
            color = color_map.get(alert_data.get('severity', 'medium'), 'good')

            success = self.slack.send_alert(
                channel="#alerts",  # Would be configurable
                alert_title=alert_title,
                alert_details=alert_details,
                color=color
            )
            if success:
                logger.info("Sent alert to Slack")

    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrations."""
        status = {}
        for name, integration in self.api_manager.integrations.items():
            status[name] = {
                'enabled': integration.enabled,
                'configured': bool(integration.api_key or integration.token or
                                 (integration.username and integration.password))
            }
        return status


# Global external integration manager instance
_external_integration_manager = ExternalIntegrationManager()


def get_external_integration_manager() -> ExternalIntegrationManager:
    """Get the global external integration manager instance."""
    return _external_integration_manager


def external_integration_collector() -> Dict[str, str]:
    """
    Metric collector for external integrations.
    This function integrates with the main metrics system.
    """
    try:
        manager = get_external_integration_manager()
        status = manager.get_integration_status()

        result = {}

        # Integration status
        enabled_integrations = [name for name, info in status.items() if info['enabled']]
        configured_integrations = [name for name, info in status.items() if info['configured']]

        result["🔗 Integrations"] = f"{len(enabled_integrations)} enabled"

        if configured_integrations:
            result["  Configured"] = ", ".join(configured_integrations)
        else:
            result["  Status"] = "No integrations configured"

        # Service status indicators
        services = {
            "servicenow": "🎫 SNOW",
            "zendesk": "🎫 Zendesk",
            "jira": "🎫 Jira",
            "slack": "💬 Slack"
        }

        for service, icon in services.items():
            if service in status and status[service]['enabled']:
                config_status = "✅" if status[service]['configured'] else "⚠️"
                result[f"  {icon}"] = f"{config_status} configured"

        return result

    except Exception as e:
        return {"Error": f"External integration failed: {str(e)}"}
