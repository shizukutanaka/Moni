"""
Workflow Automation Module for System Monitoring

This module provides automated response capabilities for system monitoring,
including conditional script execution, automated remediation, and workflow management.
"""

from __future__ import annotations

import logging
import time
import subprocess
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class AutomationRule:
    """A rule for automated system response."""
    id: str
    name: str
    description: str
    condition: str  # Python expression to evaluate
    action: str  # Script or command to execute
    cooldown_seconds: int = 300
    enabled: bool = True
    last_triggered: Optional[float] = None
    trigger_count: int = 0
    max_triggers_per_hour: int = 5


@dataclass
class AutomationResult:
    """Result of an automation execution."""
    rule_id: str
    success: bool
    output: str
    error: str
    execution_time: float
    timestamp: float


class WorkflowAutomator:
    """
    Automated workflow system for system monitoring.

    Provides conditional execution of remediation scripts and automated responses
    to system conditions, similar to NinjaOne's automation capabilities.
    """

    def __init__(self):
        self.rules: Dict[str, AutomationRule] = {}
        self.execution_history: List[AutomationResult] = []
        self._lock = threading.Lock()
        self._script_dir = Path("automation_scripts")
        self._script_dir.mkdir(exist_ok=True)

        # Default automation rules
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default automation rules."""
        default_rules = [
            AutomationRule(
                id="high_cpu_restart_service",
                name="High CPU Service Restart",
                description="Restart service when CPU usage is consistently high",
                condition="cpu_percent > 90 and trend == 'Increasing'",
                action="restart_high_cpu_service.sh",
                cooldown_seconds=600
            ),
            AutomationRule(
                id="memory_cleanup",
                name="Memory Cleanup",
                description="Run memory cleanup when usage exceeds threshold",
                condition="memory_percent > 85",
                action="memory_cleanup.py",
                cooldown_seconds=300
            ),
            AutomationRule(
                id="disk_space_alert",
                name="Disk Space Alert",
                description="Send alert when disk space is critically low",
                condition="disk_usage_percent > 95",
                action="disk_space_alert.sh",
                cooldown_seconds=3600
            ),
            AutomationRule(
                id="network_restart",
                name="Network Service Restart",
                description="Restart network services when connectivity issues detected",
                condition="network_errors > 10",
                action="network_restart.sh",
                cooldown_seconds=300
            )
        ]

        for rule in default_rules:
            self.rules[rule.id] = rule

    def add_rule(self, rule: AutomationRule):
        """Add a new automation rule."""
        with self._lock:
            self.rules[rule.id] = rule
            logger.info(f"Added automation rule: {rule.name}")

    def remove_rule(self, rule_id: str):
        """Remove an automation rule."""
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                logger.info(f"Removed automation rule: {rule_id}")

    def enable_rule(self, rule_id: str, enabled: bool = True):
        """Enable or disable an automation rule."""
        with self._lock:
            if rule_id in self.rules:
                self.rules[rule_id].enabled = enabled
                logger.info(f"{'Enabled' if enabled else 'Disabled'} automation rule: {rule_id}")

    def evaluate_conditions(self, context: Dict[str, Any]) -> List[str]:
        """
        Evaluate all enabled rules against the current system context.

        Args:
            context: Dictionary containing current system metrics

        Returns:
            List of rule IDs that should trigger
        """
        triggered_rules = []

        with self._lock:
            current_time = time.time()

            for rule in self.rules.values():
                if not rule.enabled:
                    continue

                # Check cooldown
                if rule.last_triggered and (current_time - rule.last_triggered) < rule.cooldown_seconds:
                    continue

                # Check hourly trigger limit
                recent_triggers = sum(1 for result in self.execution_history
                                    if result.rule_id == rule.id and
                                    (current_time - result.timestamp) < 3600)
                if recent_triggers >= rule.max_triggers_per_hour:
                    continue

                # Evaluate condition
                if self._evaluate_condition(rule.condition, context):
                    triggered_rules.append(rule.id)
                    rule.last_triggered = current_time
                    rule.trigger_count += 1

        return triggered_rules

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Safely evaluate a condition expression."""
        try:
            # Create a safe evaluation environment
            safe_globals = {
                '__builtins__': {
                    'abs': abs, 'max': max, 'min': min, 'sum': sum, 'len': len,
                    'all': all, 'any': any, 'bool': bool, 'int': int, 'float': float,
                    'str': str, 'list': list, 'dict': dict, 'tuple': tuple
                }
            }

            # Add context variables
            safe_locals = context.copy()

            # Evaluate the condition
            result = eval(condition, safe_globals, safe_locals)
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to evaluate condition '{condition}': {e}")
            return False

    def execute_rule(self, rule_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[AutomationResult]:
        """Execute a specific automation rule."""
        with self._lock:
            if rule_id not in self.rules:
                logger.error(f"Rule not found: {rule_id}")
                return None

            rule = self.rules[rule_id]

        start_time = time.time()

        try:
            # Execute the action
            success, output, error = self._execute_action(rule.action, context or {})

            execution_time = time.time() - start_time

            result = AutomationResult(
                rule_id=rule_id,
                success=success,
                output=output,
                error=error,
                execution_time=execution_time,
                timestamp=time.time()
            )

            # Store execution history
            with self._lock:
                self.execution_history.append(result)
                # Keep only last 1000 results
                if len(self.execution_history) > 1000:
                    self.execution_history = self.execution_history[-1000:]

            logger.info(f"Executed automation rule '{rule.name}': {'SUCCESS' if success else 'FAILED'}")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to execute automation rule '{rule.name}': {e}")

            result = AutomationResult(
                rule_id=rule_id,
                success=False,
                output="",
                error=str(e),
                execution_time=execution_time,
                timestamp=time.time()
            )

            with self._lock:
                self.execution_history.append(result)

            return result

    def _execute_action(self, action: str, context: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute an automation action."""
        try:
            # Check if it's a script file
            script_path = self._script_dir / action
            if script_path.exists():
                return self._execute_script(script_path, context)
            else:
                # Try to execute as a direct command
                return self._execute_command(action, context)

        except Exception as e:
            return False, "", str(e)

    def _execute_script(self, script_path: Path, context: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a script file."""
        try:
            # Set environment variables from context
            env = {**dict(context), 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}

            # Convert context values to strings for environment
            env = {k: str(v) for k, v in env.items()}

            result = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout
                env=env
            )

            success = result.returncode == 0
            output = result.stdout
            error = result.stderr

            return success, output, error

        except subprocess.TimeoutExpired:
            return False, "", "Script execution timed out"
        except Exception as e:
            return False, "", str(e)

    def _execute_command(self, command: str, context: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a direct command."""
        try:
            # Replace context variables in command
            for key, value in context.items():
                command = command.replace(f"{{{key}}}", str(value))

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout for commands
            )

            success = result.returncode == 0
            output = result.stdout
            error = result.stderr

            return success, output, error

        except subprocess.TimeoutExpired:
            return False, "", "Command execution timed out"
        except Exception as e:
            return False, "", str(e)

    def create_script_template(self, script_name: str, script_type: str = "bash") -> Optional[Path]:
        """Create a script template for automation."""
        script_path = self._script_dir / script_name

        if script_path.exists():
            return None  # Already exists

        if script_type.lower() == "bash":
            template = f'''#!/bin/bash
# Automation script: {script_name}
# Generated by Moni Workflow Automator

set -e  # Exit on any error

echo "Starting automation: {script_name}"
echo "Timestamp: $(date)"
echo "Working directory: $(pwd)"

# Add your automation logic here
# Available environment variables:
# CPU_PERCENT, MEMORY_PERCENT, DISK_USAGE_PERCENT, etc.

# Example: Log current system status
echo "System Status:"
echo "CPU Usage: ${{CPU_PERCENT:-'N/A'}}%"
echo "Memory Usage: ${{MEMORY_PERCENT:-'N/A'}}%"
echo "Disk Usage: ${{DISK_USAGE_PERCENT:-'N/A'}}%"

# Example automation action:
# if [ "${{CPU_PERCENT:-0}}" -gt 90 ]; then
#     echo "High CPU detected, taking action..."
#     # Add your remediation logic here
# fi

echo "Automation completed successfully"
'''
        elif script_type.lower() == "python":
            template = f'''#!/usr/bin/env python3
# Automation script: {script_name}
# Generated by Moni Workflow Automator

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main automation function."""
    print(f"Starting automation: {script_name}")
    print(f"Timestamp: {datetime.now()}")

    # Get environment variables
    cpu_percent = os.getenv('CPU_PERCENT')
    memory_percent = os.getenv('MEMORY_PERCENT')
    disk_usage = os.getenv('DISK_USAGE_PERCENT')

    print("System Status:")
    print(f"CPU Usage: {cpu_percent or 'N/A'}%")
    print(f"Memory Usage: {memory_percent or 'N/A'}%")
    print(f"Disk Usage: {disk_usage or 'N/A'}%")

    # Add your automation logic here
    # Example:
    # if cpu_percent and float(cpu_percent) > 90:
    #     print("High CPU detected, taking action...")
    #     # Add your remediation logic here

    print("Automation completed successfully")

if __name__ == "__main__":
    main()
'''
        else:
            return None

        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(template)

            # Make executable on Unix-like systems
            script_path.chmod(0o755)

            logger.info(f"Created automation script template: {script_path}")
            return script_path

        except Exception as e:
            logger.error(f"Failed to create script template: {e}")
            return None

    def get_automation_summary(self) -> Dict[str, Any]:
        """Get summary of automation system status."""
        with self._lock:
            enabled_rules = sum(1 for rule in self.rules.values() if rule.enabled)
            total_triggers = sum(result.trigger_count for result in self.rules.values())

            recent_executions = [result for result in self.execution_history
                               if (time.time() - result.timestamp) < 3600]  # Last hour

            return {
                'total_rules': len(self.rules),
                'enabled_rules': enabled_rules,
                'total_triggers': total_triggers,
                'recent_executions': len(recent_executions),
                'success_rate': len([r for r in recent_executions if r.success]) / len(recent_executions) if recent_executions else 0
            }

    def get_execution_history(self, limit: int = 50) -> List[AutomationResult]:
        """Get recent execution history."""
        with self._lock:
            return list(self.execution_history[-limit:])


# Global workflow automator instance
_workflow_automator = WorkflowAutomator()


def get_workflow_automator() -> WorkflowAutomator:
    """Get the global workflow automator instance."""
    return _workflow_automator


def workflow_automation_collector() -> Dict[str, str]:
    """
    Metric collector for workflow automation.
    This function integrates with the main metrics system.
    """
    try:
        automator = get_workflow_automator()
        summary = automator.get_automation_summary()

        result = {}

        # Automation status
        result["🤖 Automation"] = f"{summary['enabled_rules']}/{summary['total_rules']} rules active"

        # Recent activity
        recent_executions = summary['recent_executions']
        if recent_executions > 0:
            success_rate = summary['success_rate'] * 100
            result["  Recent Activity"] = f"{recent_executions} execs | {success_rate:.1f}% success"
        else:
            result["  Recent Activity"] = "No recent executions"

        # Trigger summary
        total_triggers = summary['total_triggers']
        if total_triggers > 0:
            result["  Total Triggers"] = f"{total_triggers} rule activations"

        return result

    except Exception as e:
        return {"Error": f"Workflow automation failed: {str(e)}"}
