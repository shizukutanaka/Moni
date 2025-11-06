"""Global hotkey support for overlay controls."""

from __future__ import annotations

import logging
import sys
from typing import Dict, Callable, Optional, List, Set
from enum import Enum
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    if sys.platform == "win32":
        import win32con
        import win32gui
        import win32api
        WIN32_AVAILABLE = True
    else:
        WIN32_AVAILABLE = False
except ImportError:
    WIN32_AVAILABLE = False


class HotkeyAction(Enum):
    """Available hotkey actions."""
    TOGGLE_OVERLAY = "toggle_overlay"
    SHOW_OVERLAY = "show_overlay"
    HIDE_OVERLAY = "hide_overlay"
    TOGGLE_CPU_SPARKLINE = "toggle_cpu_sparkline"
    CYCLE_THEME = "cycle_theme"
    OPEN_PROCESS_MANAGER = "open_process_manager"
    EXPORT_METRICS = "export_metrics"
    CLEAR_ALERTS = "clear_alerts"
    REFRESH_METRICS = "refresh_metrics"
    TOGGLE_ALWAYS_ON_TOP = "toggle_always_on_top"


@dataclass
class HotkeyBinding:
    """Hotkey binding configuration."""
    key_combination: str
    action: HotkeyAction
    enabled: bool = True
    description: str = ""


class GlobalHotkeyManager:
    """Manager for global hotkey functionality across platforms."""

    def __init__(self):
        self.hotkey_bindings: Dict[str, HotkeyBinding] = {}
        self.action_callbacks: Dict[HotkeyAction, Callable[[], None]] = {}
        self.registered_hotkeys: Set[str] = set()
        self.enabled = False
        self.hotkey_thread: Optional[threading.Thread] = None
        self.stop_listening = False

        # Default hotkey bindings
        self._setup_default_bindings()

    def _setup_default_bindings(self):
        """Setup default hotkey bindings."""
        default_bindings = [
            HotkeyBinding(
                key_combination="ctrl+alt+m",
                action=HotkeyAction.TOGGLE_OVERLAY,
                description="Toggle main overlay visibility"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+c",
                action=HotkeyAction.TOGGLE_CPU_SPARKLINE,
                description="Toggle CPU sparkline overlay"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+t",
                action=HotkeyAction.CYCLE_THEME,
                description="Cycle through available themes"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+p",
                action=HotkeyAction.OPEN_PROCESS_MANAGER,
                description="Open process manager"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+e",
                action=HotkeyAction.EXPORT_METRICS,
                description="Export current metrics"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+x",
                action=HotkeyAction.CLEAR_ALERTS,
                description="Clear all alerts"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+r",
                action=HotkeyAction.REFRESH_METRICS,
                description="Refresh metrics immediately"
            ),
            HotkeyBinding(
                key_combination="ctrl+alt+a",
                action=HotkeyAction.TOGGLE_ALWAYS_ON_TOP,
                description="Toggle always on top mode"
            )
        ]

        for binding in default_bindings:
            self.hotkey_bindings[binding.key_combination] = binding

    def register_action_callback(self, action: HotkeyAction, callback: Callable[[], None]):
        """Register a callback for a specific action."""
        self.action_callbacks[action] = callback

    def unregister_action_callback(self, action: HotkeyAction):
        """Unregister a callback for a specific action."""
        if action in self.action_callbacks:
            del self.action_callbacks[action]

    def set_hotkey_binding(self, key_combination: str, action: HotkeyAction, enabled: bool = True, description: str = ""):
        """Set or update a hotkey binding."""
        # Unregister old binding if it exists
        if key_combination in self.hotkey_bindings:
            self._unregister_hotkey(key_combination)

        # Create new binding
        binding = HotkeyBinding(
            key_combination=key_combination,
            action=action,
            enabled=enabled,
            description=description
        )

        self.hotkey_bindings[key_combination] = binding

        # Register if enabled and manager is active
        if enabled and self.enabled:
            self._register_hotkey(key_combination)

    def remove_hotkey_binding(self, key_combination: str):
        """Remove a hotkey binding."""
        if key_combination in self.hotkey_bindings:
            self._unregister_hotkey(key_combination)
            del self.hotkey_bindings[key_combination]

    def enable_hotkey(self, key_combination: str):
        """Enable a specific hotkey."""
        if key_combination in self.hotkey_bindings:
            self.hotkey_bindings[key_combination].enabled = True
            if self.enabled:
                self._register_hotkey(key_combination)

    def disable_hotkey(self, key_combination: str):
        """Disable a specific hotkey."""
        if key_combination in self.hotkey_bindings:
            self.hotkey_bindings[key_combination].enabled = False
            self._unregister_hotkey(key_combination)

    def start_listening(self) -> bool:
        """Start listening for global hotkeys."""
        if not KEYBOARD_AVAILABLE:
            logger.warning("Keyboard library not available. Global hotkeys disabled.")
            return False

        if self.enabled:
            return True  # Already listening

        self.enabled = True
        self.stop_listening = False

        # Register all enabled hotkeys
        for key_combination, binding in self.hotkey_bindings.items():
            if binding.enabled:
                self._register_hotkey(key_combination)

        # Start background listening thread
        self.hotkey_thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self.hotkey_thread.start()

        return True

    def stop_listening(self):
        """Stop listening for global hotkeys."""
        if not self.enabled:
            return

        self.enabled = False
        self.stop_listening = True

        # Unregister all hotkeys
        for key_combination in list(self.registered_hotkeys):
            self._unregister_hotkey(key_combination)

        # Wait for thread to finish
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=1)

    def _register_hotkey(self, key_combination: str):
        """Register a single hotkey."""
        if not KEYBOARD_AVAILABLE or key_combination in self.registered_hotkeys:
            return

        try:
            # Parse key combination for keyboard library
            normalized_combo = self._normalize_key_combination(key_combination)

            def hotkey_callback():
                binding = self.hotkey_bindings.get(key_combination)
                if binding and binding.enabled and binding.action in self.action_callbacks:
                    try:
                        self.action_callbacks[binding.action]()
                    except Exception as e:
                        logger.error(f"Error executing hotkey callback for {key_combination}", exc_info=True)

            keyboard.add_hotkey(normalized_combo, hotkey_callback)
            self.registered_hotkeys.add(key_combination)
            logger.info(f"Registered global hotkey: {key_combination}")

        except Exception as e:
            logger.error(f"Failed to register hotkey {key_combination}", exc_info=True)

    def _unregister_hotkey(self, key_combination: str):
        """Unregister a single hotkey."""
        if not KEYBOARD_AVAILABLE or key_combination not in self.registered_hotkeys:
            return

        try:
            normalized_combo = self._normalize_key_combination(key_combination)
            keyboard.remove_hotkey(normalized_combo)
            self.registered_hotkeys.discard(key_combination)
            logger.info(f"Unregistered global hotkey: {key_combination}")

        except Exception as e:
            logger.error(f"Failed to unregister hotkey {key_combination}", exc_info=True)

    def _normalize_key_combination(self, key_combination: str) -> str:
        """Normalize key combination for the keyboard library."""
        # Convert common key names to keyboard library format
        replacements = {
            'ctrl': 'ctrl',
            'alt': 'alt',
            'shift': 'shift',
            'win': 'windows',
            'cmd': 'cmd',
            'super': 'windows'
        }

        normalized = key_combination.lower()
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized

    def _hotkey_listener_loop(self):
        """Background loop for hotkey listening."""
        try:
            # Keep the keyboard listener alive
            while not self.stop_listening:
                import time
                time.sleep(0.1)
        except Exception as e:
            logger.error("Hotkey listener loop error", exc_info=True)

    def get_hotkey_status(self) -> Dict[str, any]:
        """Get status of all hotkey bindings."""
        return {
            "enabled": self.enabled,
            "keyboard_available": KEYBOARD_AVAILABLE,
            "total_bindings": len(self.hotkey_bindings),
            "active_bindings": len(self.registered_hotkeys),
            "bindings": [
                {
                    "key_combination": combo,
                    "action": binding.action.value,
                    "enabled": binding.enabled,
                    "description": binding.description,
                    "registered": combo in self.registered_hotkeys
                }
                for combo, binding in self.hotkey_bindings.items()
            ]
        }

    def validate_key_combination(self, key_combination: str) -> bool:
        """Validate if a key combination is valid."""
        if not key_combination:
            return False

        # Basic validation - check for common patterns
        parts = key_combination.lower().split('+')

        # Must have at least one modifier and one key
        if len(parts) < 2:
            return False

        modifiers = {'ctrl', 'alt', 'shift', 'win', 'cmd', 'super'}
        has_modifier = any(part in modifiers for part in parts[:-1])

        return has_modifier

    def test_hotkey(self, key_combination: str) -> bool:
        """Test if a hotkey combination can be registered."""
        if not KEYBOARD_AVAILABLE:
            return False

        try:
            normalized_combo = self._normalize_key_combination(key_combination)

            # Try to register temporarily
            def test_callback():
                pass

            keyboard.add_hotkey(normalized_combo, test_callback)
            keyboard.remove_hotkey(normalized_combo)
            return True

        except Exception:
            return False

    def get_available_actions(self) -> List[Dict[str, str]]:
        """Get list of available hotkey actions."""
        return [
            {
                "action": action.value,
                "description": self._get_action_description(action)
            }
            for action in HotkeyAction
        ]

    def _get_action_description(self, action: HotkeyAction) -> str:
        """Get description for a hotkey action."""
        descriptions = {
            HotkeyAction.TOGGLE_OVERLAY: "Toggle main overlay visibility",
            HotkeyAction.SHOW_OVERLAY: "Show main overlay",
            HotkeyAction.HIDE_OVERLAY: "Hide main overlay",
            HotkeyAction.TOGGLE_CPU_SPARKLINE: "Toggle CPU sparkline overlay",
            HotkeyAction.CYCLE_THEME: "Cycle through available themes",
            HotkeyAction.OPEN_PROCESS_MANAGER: "Open process manager dialog",
            HotkeyAction.EXPORT_METRICS: "Export current metrics to file",
            HotkeyAction.CLEAR_ALERTS: "Clear all active alerts",
            HotkeyAction.REFRESH_METRICS: "Refresh metrics immediately",
            HotkeyAction.TOGGLE_ALWAYS_ON_TOP: "Toggle always on top mode"
        }
        return descriptions.get(action, "Unknown action")

    def export_configuration(self) -> Dict[str, any]:
        """Export hotkey configuration."""
        return {
            "hotkey_bindings": {
                combo: {
                    "action": binding.action.value,
                    "enabled": binding.enabled,
                    "description": binding.description
                }
                for combo, binding in self.hotkey_bindings.items()
            }
        }

    def import_configuration(self, config: Dict[str, any]):
        """Import hotkey configuration."""
        # Stop current listening
        was_enabled = self.enabled
        if self.enabled:
            self.stop_listening()

        # Clear existing bindings
        self.hotkey_bindings.clear()

        # Import bindings
        bindings_config = config.get("hotkey_bindings", {})
        for combo, binding_data in bindings_config.items():
            try:
                action = HotkeyAction(binding_data["action"])
                binding = HotkeyBinding(
                    key_combination=combo,
                    action=action,
                    enabled=binding_data.get("enabled", True),
                    description=binding_data.get("description", "")
                )
                self.hotkey_bindings[combo] = binding
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid hotkey binding in config: {combo}", exc_info=True)

        # Restart listening if it was enabled
        if was_enabled:
            self.start_listening()