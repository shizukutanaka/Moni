"""
Ticket Management System for System Monitoring

This module provides incident management and ticketing capabilities,
allowing for systematic tracking and resolution of system issues.
"""

import logging
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class TicketPriority(Enum):
    """Ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(Enum):
    """Ticket status values."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class OnCallSchedule:
    """On-call schedule for a user."""
    user_id: str
    start_time: float
    end_time: float
    timezone: str = "UTC"
    contact_methods: List[str] = field(default_factory=lambda: ["email"])

    def is_active(self, current_time: Optional[float] = None) -> bool:
        """Check if this schedule is currently active."""
        now = current_time or time.time()
        return self.start_time <= now <= self.end_time


@dataclass
class EscalationPolicy:
    """Escalation policy for incident response."""
    id: str
    name: str
    description: str
    rules: List[Dict[str, Any]]  # Escalation rules
    enabled: bool = True

    def get_next_escalation(self, current_level: int, incident_age_seconds: float) -> Optional[Dict[str, Any]]:
        """Get the next escalation rule based on current level and incident age."""
        if not self.enabled or current_level >= len(self.rules):
            return None

        rule = self.rules[current_level]

        # Check if escalation condition is met
        condition = rule.get('condition', {})
        delay_seconds = condition.get('delay_seconds', 0)

        if incident_age_seconds >= delay_seconds:
            return rule

        return None


@dataclass
class IncidentResponse:
    """Incident response tracking."""
    incident_id: str
    current_level: int = 0
    escalated_at: Optional[float] = None
    notified_users: List[str] = field(default_factory=list)
    response_actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TicketComment:
    """A comment on a ticket."""
    id: str
    author: str
    content: str
    timestamp: float
    is_internal: bool = False


@dataclass
class Ticket:
    """A support ticket for incident management."""
    id: str
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    ticket_type: TicketType
    created_by: str
    assigned_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    due_date: Optional[float] = None

    # Related information
    related_metrics: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    comments: List[TicketComment] = field(default_factory=list)

    # System context
    system_info: Dict[str, Any] = field(default_factory=dict)

    def add_comment(self, author: str, content: str, is_internal: bool = False):
        """Add a comment to the ticket."""
        comment = TicketComment(
            id=str(uuid.uuid4()),
            author=author,
            content=content,
            timestamp=time.time(),
            is_internal=is_internal
        )
        self.comments.append(comment)
        self.updated_at = time.time()

    def update_status(self, new_status: TicketStatus, updated_by: str):
        """Update ticket status."""
        self.status = new_status
        self.updated_at = time.time()

        if new_status == TicketStatus.RESOLVED and not self.resolved_at:
            self.resolved_at = time.time()

        self.add_comment(
            updated_by,
            f"Status changed to {new_status.value}",
            is_internal=True
        )

    def assign_to(self, assignee: str, assigned_by: str):
        """Assign ticket to a user."""
        old_assignee = self.assigned_to
        self.assigned_to = assignee
        self.updated_at = time.time()

        if old_assignee:
            self.add_comment(
                assigned_by,
                f"Reassigned from {old_assignee} to {assignee}",
                is_internal=True
            )
        else:
            self.add_comment(
                assigned_by,
                f"Assigned to {assignee}",
                is_internal=True
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary for serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority.value,
            'status': self.status.value,
            'ticket_type': self.ticket_type.value,
            'created_by': self.created_by,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'resolved_at': self.resolved_at,
            'due_date': self.due_date,
            'related_metrics': self.related_metrics,
            'tags': self.tags,
            'comments': [
                {
                    'id': c.id,
                    'author': c.author,
                    'content': c.content,
                    'timestamp': c.timestamp,
                    'is_internal': c.is_internal
                } for c in self.comments
            ],
            'system_info': self.system_info
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Ticket:
        """Create ticket from dictionary."""
        # Convert enum values
        priority = TicketPriority(data['priority'])
        status = TicketStatus(data['status'])
        ticket_type = TicketType(data['ticket_type'])

        # Convert comments
        comments = []
        for comment_data in data.get('comments', []):
            comments.append(TicketComment(**comment_data))

        ticket = cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            priority=priority,
            status=status,
            ticket_type=ticket_type,
            created_by=data['created_by'],
            assigned_to=data.get('assigned_to'),
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            resolved_at=data.get('resolved_at'),
            due_date=data.get('due_date'),
            related_metrics=data.get('related_metrics', []),
            tags=data.get('tags', []),
            system_info=data.get('system_info', {})
        )
        ticket.comments = comments
        return ticket


class TicketManager:
    """
    Centralized ticket management system for incident tracking and resolution.

    Provides capabilities similar to NinjaOne's ticketing system for IT service management.
    PagerDuty-style on-call management and incident response.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.tickets: Dict[str, Ticket] = {}
        self.on_call_schedules: Dict[str, OnCallSchedule] = {}
        self.escalation_policies: Dict[str, EscalationPolicy] = {}
        self.incident_responses: Dict[str, IncidentResponse] = {}
        self._lock = threading.Lock()

        self.storage_path = storage_path or Path("tickets.json")
        self.on_call_storage = Path("on_call_schedules.json")
        self.escalation_storage = Path("escalation_policies.json")

        # Load existing data
        self._load_tickets()
        self._load_on_call_schedules()
        self._load_escalation_policies()

        # Default escalation policy
        self._create_default_escalation_policy()

    def _create_default_escalation_policy(self):
        """Create a default escalation policy."""
        if "default" not in self.escalation_policies:
            default_policy = EscalationPolicy(
                id="default",
                name="Default Incident Escalation",
                description="Standard escalation policy for incidents",
                rules=[
                    {
                        "level": 0,
                        "targets": ["primary_on_call"],
                        "condition": {"delay_seconds": 0},
                        "actions": ["notify", "page"]
                    },
                    {
                        "level": 1,
                        "targets": ["secondary_on_call", "manager"],
                        "condition": {"delay_seconds": 300},  # 5 minutes
                        "actions": ["notify", "page", "escalate"]
                    },
                    {
                        "level": 2,
                        "targets": ["all_technicians", "executive"],
                        "condition": {"delay_seconds": 900},  # 15 minutes
                        "actions": ["notify", "page", "conference_call"]
                    }
                ]
            )
            self.escalation_policies["default"] = default_policy

    def add_on_call_schedule(self, schedule: OnCallSchedule):
        """Add an on-call schedule."""
        with self._lock:
            schedule_id = f"{schedule.user_id}_{int(schedule.start_time)}"
            self.on_call_schedules[schedule_id] = schedule
            self._save_on_call_schedules()
            logger.info(f"Added on-call schedule for {schedule.user_id}")

    def remove_on_call_schedule(self, schedule_id: str):
        """Remove an on-call schedule."""
        with self._lock:
            if schedule_id in self.on_call_schedules:
                del self.on_call_schedules[schedule_id]
                self._save_on_call_schedules()

    def get_current_on_call(self) -> List[str]:
        """Get currently on-call users."""
        current_time = time.time()
        on_call_users = []

        with self._lock:
            for schedule in self.on_call_schedules.values():
                if schedule.is_active(current_time):
                    on_call_users.append(schedule.user_id)

        # Remove duplicates
        return list(set(on_call_users))

    def create_incident_with_escalation(self, title: str, description: str,
                                      priority: TicketPriority, created_by: str,
                                      escalation_policy_id: str = "default") -> Optional[Ticket]:
        """Create an incident ticket with automatic escalation setup."""
        ticket = self.create_ticket(
            title=title,
            description=description,
            priority=priority,
            ticket_type=TicketType.INCIDENT,
            created_by=created_by,
            tags=["incident", "auto_escalation"]
        )

        if ticket:
            # Set up incident response tracking
            incident_response = IncidentResponse(
                incident_id=ticket.id,
                current_level=0
            )

            with self._lock:
                self.incident_responses[ticket.id] = incident_response

            # Immediately trigger initial escalation
            self._process_escalation(ticket.id)

        return ticket

    def _process_escalation(self, ticket_id: str):
        """Process escalation for an incident."""
        with self._lock:
            if ticket_id not in self.incident_responses:
                return

            ticket = self.tickets.get(ticket_id)
            incident_response = self.incident_responses[ticket_id]

            if not ticket or ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                return

            # Get escalation policy
            policy = self.escalation_policies.get("default")
            if not policy:
                return

            # Calculate incident age
            incident_age = time.time() - ticket.created_at

            # Check if escalation is needed
            next_escalation = policy.get_next_escalation(
                incident_response.current_level,
                incident_age
            )

            if next_escalation:
                self._execute_escalation(ticket, incident_response, next_escalation)

    def _execute_escalation(self, ticket: Ticket, incident_response: IncidentResponse,
                          escalation_rule: Dict[str, Any]):
        """Execute an escalation action."""
        targets = escalation_rule.get('targets', [])
        actions = escalation_rule.get('actions', [])

        # Find actual users for targets
        target_users = []
        for target in targets:
            if target == "primary_on_call":
                target_users.extend(self.get_current_on_call()[:1])  # First on-call person
            elif target == "secondary_on_call":
                target_users.extend(self.get_current_on_call()[1:2])  # Second on-call person
            elif target == "all_technicians":
                target_users.extend(["admin", "system"])  # Default technicians
            elif target == "manager":
                target_users.append("manager")
            elif target == "executive":
                target_users.append("executive")

        # Remove duplicates
        target_users = list(set(target_users))

        # Execute actions
        for action in actions:
            if action == "notify":
                self._send_notifications(ticket, target_users, "notification")
            elif action == "page":
                self._send_notifications(ticket, target_users, "page")
            elif action == "escalate":
                self._escalate_ticket(ticket, target_users)
            elif action == "conference_call":
                self._initiate_conference_call(ticket, target_users)

        # Update incident response
        incident_response.current_level += 1
        incident_response.escalated_at = time.time()
        incident_response.notified_users.extend(target_users)

        # Log escalation
        ticket.add_comment(
            "system",
            f"Escalated to level {incident_response.current_level}: notified {', '.join(target_users)}",
            is_internal=True
        )

    def _send_notifications(self, ticket: Ticket, users: List[str], notification_type: str):
        """Send notifications to users (placeholder implementation)."""
        for user in users:
            # In a real implementation, this would integrate with email, SMS, Slack, etc.
            logger.info(f"Sending {notification_type} to {user} for ticket {ticket.id}: {ticket.title}")

            # Add notification record to ticket
            ticket.add_comment(
                "system",
                f"{notification_type.capitalize()} sent to {user}",
                is_internal=True
            )

    def _escalate_ticket(self, ticket: Ticket, users: List[str]):
        """Escalate ticket to higher priority users."""
        # Assign to first available escalated user
        for user in users:
            if user != ticket.assigned_to:
                ticket.assign_to(user, "system")
                break

    def _initiate_conference_call(self, ticket: Ticket, users: List[str]):
        """Initiate a conference call (placeholder)."""
        logger.info(f"Initiating conference call for ticket {ticket.id} with users: {', '.join(users)}")
        ticket.add_comment(
            "system",
            f"Conference call initiated with: {', '.join(users)}",
            is_internal=True
        )

    def process_pending_escalations(self):
        """Process all pending escalations."""
        with self._lock:
            for ticket_id in list(self.incident_responses.keys()):
                self._process_escalation(ticket_id)
                     ticket_type: TicketType, created_by: str,
                     related_metrics: Optional[List[str]] = None,
                     system_info: Optional[Dict[str, Any]] = None,
                     tags: Optional[List[str]] = None) -> Ticket:
        """Create a new ticket."""
        ticket_id = str(uuid.uuid4())

        ticket = Ticket(
            id=ticket_id,
            title=title,
            description=description,
            priority=priority,
            status=TicketStatus.OPEN,
            ticket_type=ticket_type,
            created_by=created_by,
            related_metrics=related_metrics or [],
            system_info=system_info or {},
            tags=tags or []
        )

        with self._lock:
            self.tickets[ticket_id] = ticket
            self._save_tickets()

        logger.info(f"Created ticket {ticket_id}: {title}")
        return ticket

    def create_incident_from_alert(self, alert_data: Dict[str, Any], metric_name: str) -> Ticket:
        """Create an incident ticket from an alert."""
        title = f"System Alert: {alert_data.get('metric', 'Unknown')} Issue"
        description = f"""
System alert detected:

Metric: {alert_data.get('metric', 'Unknown')}
Value: {alert_data.get('value', 'N/A')} {alert_data.get('unit', '')}
Threshold: {alert_data.get('threshold', 'N/A')} {alert_data.get('unit', '')}
Severity: {alert_data.get('severity', 'unknown')}

This ticket was automatically created from a system monitoring alert.
Please investigate and resolve the issue.
"""

        # Determine priority based on severity
        severity = alert_data.get('severity', 'warning')
        if severity == 'critical':
            priority = TicketPriority.CRITICAL
        elif severity == 'warning':
            priority = TicketPriority.HIGH
        else:
            priority = TicketPriority.MEDIUM

        system_info = {
            'alert_source': 'monitoring_system',
            'alert_timestamp': alert_data.get('timestamp', time.time()),
            'metric_name': metric_name
        }

        return self.create_ticket(
            title=title,
            description=description,
            priority=priority,
            ticket_type=TicketType.INCIDENT,
            created_by="monitoring_system",
            related_metrics=[metric_name],
            system_info=system_info,
            tags=["auto-generated", "alert", metric_name]
        )

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        with self._lock:
            return self.tickets.get(ticket_id)

    def update_ticket_status(self, ticket_id: str, new_status: TicketStatus,
                           updated_by: str) -> bool:
        """Update ticket status."""
        with self._lock:
            ticket = self.tickets.get(ticket_id)
            if not ticket:
                return False

            ticket.update_status(new_status, updated_by)
            self._save_tickets()
            return True

    def assign_ticket(self, ticket_id: str, assignee: str, assigned_by: str) -> bool:
        """Assign ticket to a technician."""
        with self._lock:
            ticket = self.tickets.get(ticket_id)
            if not ticket:
                return False

            ticket.assign_to(assignee, assigned_by)
            self._save_tickets()
            return True

    def add_ticket_comment(self, ticket_id: str, author: str, content: str,
                          is_internal: bool = False) -> bool:
        """Add a comment to a ticket."""
        with self._lock:
            ticket = self.tickets.get(ticket_id)
            if not ticket:
                return False

            ticket.add_comment(author, content, is_internal)
            self._save_tickets()
            return True

    def auto_assign_ticket(self, ticket: Ticket) -> Optional[str]:
        """Automatically assign ticket to an available technician."""
        # Simple round-robin assignment for now
        # In a real system, this would consider workload, expertise, etc.

        # Find least busy technician
        technician_workload = {}
        for tech in self._technicians:
            workload = sum(1 for t in self.tickets.values()
                          if t.assigned_to == tech and t.status in [TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            technician_workload[tech] = workload

        if technician_workload:
            least_busy = min(technician_workload, key=technician_workload.get)
            return least_busy

        return None

    def get_tickets_by_status(self, status: TicketStatus) -> List[Ticket]:
        """Get all tickets with a specific status."""
        with self._lock:
            return [ticket for ticket in self.tickets.values() if ticket.status == status]

    def get_tickets_by_priority(self, priority: TicketPriority) -> List[Ticket]:
        """Get all tickets with a specific priority."""
        with self._lock:
            return [ticket for ticket in self.tickets.values() if ticket.priority == priority]

    def get_overdue_tickets(self) -> List[Ticket]:
        """Get tickets that are past their due date."""
        current_time = time.time()
        with self._lock:
            return [ticket for ticket in self.tickets.values()
                   if ticket.due_date and ticket.due_date < current_time
                   and ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]

    def get_unassigned_tickets(self) -> List[Ticket]:
        """Get tickets that are not assigned to anyone."""
        with self._lock:
            return [ticket for ticket in self.tickets.values()
                   if ticket.assigned_to is None
                   and ticket.status in [TicketStatus.OPEN, TicketStatus.IN_PROGRESS]]

    def get_ticket_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all tickets."""
        with self._lock:
            total_tickets = len(self.tickets)
            status_counts = {}
            priority_counts = {}

            for ticket in self.tickets.values():
                status_counts[ticket.status.value] = status_counts.get(ticket.status.value, 0) + 1
                priority_counts[ticket.priority.value] = priority_counts.get(ticket.priority.value, 0) + 1

            # Calculate average resolution time for resolved tickets
            resolved_tickets = [t for t in self.tickets.values() if t.resolved_at]
            avg_resolution_time = 0
            if resolved_tickets:
                resolution_times = [(t.resolved_at - t.created_at) / 3600 for t in resolved_tickets]  # hours
                avg_resolution_time = sum(resolution_times) / len(resolution_times)

            return {
                'total_tickets': total_tickets,
                'status_breakdown': status_counts,
                'priority_breakdown': priority_counts,
                'unassigned_tickets': len(self.get_unassigned_tickets()),
                'overdue_tickets': len(self.get_overdue_tickets()),
                'avg_resolution_time_hours': round(avg_resolution_time, 2)
            }

    def _save_tickets(self):
        """Save tickets to persistent storage."""
        try:
            ticket_data = {tid: ticket.to_dict() for tid, ticket in self.tickets.items()}

            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(ticket_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save tickets: {e}")

    def _load_tickets(self):
        """Load tickets from persistent storage."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                ticket_data = json.load(f)

            for ticket_dict in ticket_data.values():
                ticket = Ticket.from_dict(ticket_dict)
                self.tickets[ticket.id] = ticket

            logger.info(f"Loaded {len(self.tickets)} tickets from storage")

        except Exception as e:
            logger.error(f"Failed to load tickets: {e}")

    def cleanup_old_tickets(self, days_old: int = 90):
        """Clean up old resolved/closed tickets."""
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)

        with self._lock:
            to_remove = []
            for ticket_id, ticket in self.tickets.items():
                if (ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED] and
                    ticket.updated_at < cutoff_time):
                    to_remove.append(ticket_id)

            for ticket_id in to_remove:
                del self.tickets[ticket_id]

            if to_remove:
                self._save_tickets()
                logger.info(f"Cleaned up {len(to_remove)} old tickets")

    def _save_on_call_schedules(self):
        """Save on-call schedules to persistent storage."""
        try:
            schedule_data = {sid: {
                'user_id': s.user_id,
                'start_time': s.start_time,
                'end_time': s.end_time,
                'timezone': s.timezone,
                'contact_methods': s.contact_methods
            } for sid, s in self.on_call_schedules.items()}

            with open(self.on_call_storage, 'w', encoding='utf-8') as f:
                json.dump(schedule_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save on-call schedules: {e}")

    def _load_on_call_schedules(self):
        """Load on-call schedules from persistent storage."""
        if not self.on_call_storage.exists():
            return

        try:
            with open(self.on_call_storage, 'r', encoding='utf-8') as f:
                schedule_data = json.load(f)

            for schedule_dict in schedule_data.values():
                schedule = OnCallSchedule(**schedule_dict)
                schedule_id = f"{schedule.user_id}_{int(schedule.start_time)}"
                self.on_call_schedules[schedule_id] = schedule

            logger.info(f"Loaded {len(self.on_call_schedules)} on-call schedules")

        except Exception as e:
            logger.error(f"Failed to load on-call schedules: {e}")

    def _save_escalation_policies(self):
        """Save escalation policies to persistent storage."""
        try:
            policy_data = {pid: {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'rules': p.rules,
                'enabled': p.enabled
            } for pid, p in self.escalation_policies.items()}

            with open(self.escalation_storage, 'w', encoding='utf-8') as f:
                json.dump(policy_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save escalation policies: {e}")

    def _load_escalation_policies(self):
        """Load escalation policies from persistent storage."""
        if not self.escalation_storage.exists():
            return

        try:
            with open(self.escalation_storage, 'r', encoding='utf-8') as f:
                policy_data = json.load(f)

            for policy_dict in policy_data.values():
                policy = EscalationPolicy(**policy_dict)
                self.escalation_policies[policy.id] = policy

            logger.info(f"Loaded {len(self.escalation_policies)} escalation policies")

        except Exception as e:
            logger.error(f"Failed to load escalation policies: {e}")
_ticket_manager = TicketManager()


def get_ticket_manager() -> TicketManager:
    """Get the global ticket manager instance."""
    return _ticket_manager


def ticket_system_collector() -> Dict[str, str]:
    """
    Metric collector for ticket management system.
    This function integrates with the main metrics system.
    """
    try:
        manager = get_ticket_manager()
        summary = manager.get_ticket_summary()

        result = {}

        # Overall ticket status
        total_tickets = summary['total_tickets']
        result["🎫 Tickets"] = f"{total_tickets} total"

        # Status breakdown
        status_breakdown = summary['status_breakdown']
        if status_breakdown:
            open_count = status_breakdown.get('open', 0)
            in_progress = status_breakdown.get('in_progress', 0)
            resolved = status_breakdown.get('resolved', 0)

            if open_count > 0:
                result["  Open Tickets"] = f"{open_count} pending"
            if in_progress > 0:
                result["  In Progress"] = f"{in_progress} active"
            if resolved > 0:
                result["  Resolved"] = f"{resolved} completed"

        # Priority alerts
        priority_breakdown = summary['priority_breakdown']
        critical_count = priority_breakdown.get('critical', 0)
        high_count = priority_breakdown.get('high', 0)

        if critical_count > 0:
            result["🚨 Critical"] = f"{critical_count} urgent tickets"
        if high_count > 0:
            result["⚠️ High Priority"] = f"{high_count} important tickets"

        # Management alerts
        unassigned = summary['unassigned_tickets']
        overdue = summary['overdue_tickets']

        if unassigned > 0:
            result["👤 Unassigned"] = f"{unassigned} tickets need assignment"
        if overdue > 0:
            result["⏰ Overdue"] = f"{overdue} tickets past due date"

        # Performance metric
        avg_resolution = summary['avg_resolution_time_hours']
        if avg_resolution > 0:
            result["  Avg Resolution"] = f"{avg_resolution:.1f} hours"

        # On-call status
        current_on_call = manager.get_current_on_call()
        if current_on_call:
            result["📞 On-Call"] = f"{', '.join(current_on_call[:3])}"
            if len(current_on_call) > 3:
                result["  +More"] = f"{len(current_on_call) - 3} additional"
        else:
            result["📞 On-Call"] = "No one currently on-call"

        # Escalation status
        pending_escalations = sum(1 for ticket_id in manager.incident_responses.keys()
                                if ticket_id in manager.tickets and
                                manager.tickets[ticket_id].status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED])
        if pending_escalations > 0:
            result["🚨 Escalations"] = f"{pending_escalations} active incidents"

        return result

    except Exception as e:
        return {"Error": f"Ticket system failed: {str(e)}"}
