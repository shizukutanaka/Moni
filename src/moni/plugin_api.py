"""Plugin API for custom metrics and extensibility."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import logging
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Type

from .metrics import MetricData, MetricCollector

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a plugin."""
    id: str
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    enabled: bool
    file_path: Path
    error: Optional[str] = None


class MetricPlugin(ABC):
    """Base class for metric plugins."""

    @property
    @abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """Return plugin information."""
        pass

    @property
    @abstractmethod
    def metric_id(self) -> str:
        """Return unique metric identifier."""
        pass

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Return human-readable metric name."""
        pass

    @property
    @abstractmethod
    def metric_description(self) -> str:
        """Return metric description."""
        pass

    @abstractmethod
    def collect_metrics(self) -> MetricData:
        """Collect and return metric data."""
        pass

    def initialize(self) -> bool:
        """Initialize the plugin. Return True if successful."""
        return True

    def cleanup(self):
        """Clean up plugin resources."""
        pass

    def get_configuration_schema(self) -> Optional[Dict[str, Any]]:
        """Return JSON schema for plugin configuration."""
        return None

    def configure(self, config: Dict[str, Any]) -> bool:
        """Configure the plugin with provided settings."""
        return True

    def validate_environment(self) -> List[str]:
        """Validate plugin environment. Return list of error messages."""
        return []


class ProcessorPlugin(ABC):
    """Base class for metric processor plugins."""

    @property
    @abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """Return plugin information."""
        pass

    @abstractmethod
    def process_metrics(self, metrics: Dict[str, MetricData]) -> Dict[str, MetricData]:
        """Process metric data and return modified/enhanced data."""
        pass

    def initialize(self) -> bool:
        """Initialize the plugin."""
        return True

    def cleanup(self):
        """Clean up plugin resources."""
        pass


class ExporterPlugin(ABC):
    """Base class for metric exporter plugins."""

    @property
    @abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """Return plugin information."""
        pass

    @property
    @abstractmethod
    def export_format(self) -> str:
        """Return export format identifier."""
        pass

    @abstractmethod
    def export_metrics(self, metrics: Dict[str, MetricData], file_path: Path, **kwargs) -> bool:
        """Export metrics to file."""
        pass

    def get_export_options(self) -> Dict[str, Any]:
        """Return available export options."""
        return {}


class PluginManager:
    """Manager for loading and controlling plugins."""

    def __init__(self, plugin_directories: Optional[List[Path]] = None):
        self.plugin_directories = plugin_directories or []
        self.loaded_plugins: Dict[str, Any] = {}
        self.metric_plugins: Dict[str, MetricPlugin] = {}
        self.processor_plugins: Dict[str, ProcessorPlugin] = {}
        self.exporter_plugins: Dict[str, ExporterPlugin] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}

        # Default plugin directories
        self._add_default_directories()

    def _add_default_directories(self):
        """Add default plugin directories."""
        # Application plugins directory
        app_plugins_dir = Path(__file__).parent / "plugins"
        if app_plugins_dir.exists():
            self.plugin_directories.append(app_plugins_dir)

        # User plugins directory
        user_plugins_dir = Path.home() / ".moni" / "plugins"
        self.plugin_directories.append(user_plugins_dir)

    def add_plugin_directory(self, directory: Path):
        """Add a plugin directory."""
        if directory not in self.plugin_directories:
            self.plugin_directories.append(directory)

    def discover_plugins(self) -> List[PluginInfo]:
        """Discover all available plugins."""
        discovered = []

        for plugin_dir in self.plugin_directories:
            if not plugin_dir.exists():
                continue

            # Look for Python files and plugin manifests
            for file_path in plugin_dir.rglob("*.py"):
                if file_path.name.startswith("__"):
                    continue

                plugin_info = self._analyze_plugin_file(file_path)
                if plugin_info:
                    discovered.append(plugin_info)
                    self.plugin_info[plugin_info.id] = plugin_info

            # Look for plugin manifest files
            for manifest_path in plugin_dir.rglob("plugin.json"):
                plugin_info = self._load_plugin_manifest(manifest_path)
                if plugin_info:
                    discovered.append(plugin_info)
                    self.plugin_info[plugin_info.id] = plugin_info

        return discovered

    def _analyze_plugin_file(self, file_path: Path) -> Optional[PluginInfo]:
        """Analyze a Python file for plugin classes."""
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", file_path)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for plugin classes
            plugin_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    not obj.__name__.startswith('_') and
                    (issubclass(obj, MetricPlugin) or
                     issubclass(obj, ProcessorPlugin) or
                     issubclass(obj, ExporterPlugin)) and
                    obj not in [MetricPlugin, ProcessorPlugin, ExporterPlugin]):
                    plugin_classes.append(obj)

            if not plugin_classes:
                return None

            # Use first plugin class found
            plugin_class = plugin_classes[0]
            plugin_instance = plugin_class()

            if hasattr(plugin_instance, 'plugin_info'):
                info = plugin_instance.plugin_info
                return PluginInfo(
                    id=info.get('id', file_path.stem),
                    name=info.get('name', plugin_class.__name__),
                    version=info.get('version', '1.0.0'),
                    description=info.get('description', ''),
                    author=info.get('author', 'Unknown'),
                    dependencies=info.get('dependencies', []),
                    enabled=False,
                    file_path=file_path
                )

        except Exception as e:
            return PluginInfo(
                id=file_path.stem,
                name=file_path.stem,
                version="0.0.0",
                description="Failed to load plugin",
                author="Unknown",
                dependencies=[],
                enabled=False,
                file_path=file_path,
                error=str(e)
            )

        return None

    def _load_plugin_manifest(self, manifest_path: Path) -> Optional[PluginInfo]:
        """Load plugin information from manifest file."""
        try:
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)

            plugin_file = manifest_path.parent / manifest_data.get('main', 'plugin.py')
            if not plugin_file.exists():
                return None

            return PluginInfo(
                id=manifest_data.get('id', manifest_path.parent.name),
                name=manifest_data.get('name', 'Unknown Plugin'),
                version=manifest_data.get('version', '1.0.0'),
                description=manifest_data.get('description', ''),
                author=manifest_data.get('author', 'Unknown'),
                dependencies=manifest_data.get('dependencies', []),
                enabled=False,
                file_path=plugin_file
            )

        except Exception as e:
            return PluginInfo(
                id=manifest_path.parent.name,
                name=manifest_path.parent.name,
                version="0.0.0",
                description="Failed to load manifest",
                author="Unknown",
                dependencies=[],
                enabled=False,
                file_path=manifest_path.parent / "plugin.py",
                error=str(e)
            )

    def load_plugin(self, plugin_id: str) -> bool:
        """Load and initialize a specific plugin."""
        if plugin_id not in self.plugin_info:
            return False

        if plugin_id in self.loaded_plugins:
            return True  # Already loaded

        plugin_info = self.plugin_info[plugin_id]

        try:
            # Check dependencies
            missing_deps = self._check_dependencies(plugin_info.dependencies)
            if missing_deps:
                logger.warning(f"Plugin {plugin_id} missing dependencies: {missing_deps}")
                return False

            # Load the module
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", plugin_info.file_path)
            if not spec or not spec.loader:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find and instantiate plugin classes
            plugin_instances = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    not obj.__name__.startswith('_') and
                    (issubclass(obj, MetricPlugin) or
                     issubclass(obj, ProcessorPlugin) or
                     issubclass(obj, ExporterPlugin)) and
                    obj not in [MetricPlugin, ProcessorPlugin, ExporterPlugin]):

                    instance = obj()

                    # Validate environment
                    if hasattr(instance, 'validate_environment'):
                        validation_errors = instance.validate_environment()
                        if validation_errors:
                            logger.warning(f"Plugin {plugin_id} validation failed: {validation_errors}")
                            continue

                    # Configure plugin
                    if plugin_id in self.plugin_configs:
                        if hasattr(instance, 'configure'):
                            instance.configure(self.plugin_configs[plugin_id])

                    # Initialize plugin
                    if hasattr(instance, 'initialize'):
                        if not instance.initialize():
                            logger.error(f"Plugin {plugin_id} initialization failed")
                            continue

                    plugin_instances.append(instance)

                    # Register plugin by type
                    if isinstance(instance, MetricPlugin):
                        self.metric_plugins[instance.metric_id] = instance
                    elif isinstance(instance, ProcessorPlugin):
                        self.processor_plugins[plugin_id] = instance
                    elif isinstance(instance, ExporterPlugin):
                        self.exporter_plugins[instance.export_format] = instance

            if plugin_instances:
                self.loaded_plugins[plugin_id] = plugin_instances
                plugin_info.enabled = True
                logger.info(f"Loaded plugin: {plugin_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}", exc_info=True)

        return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a specific plugin."""
        if plugin_id not in self.loaded_plugins:
            return False

        try:
            plugin_instances = self.loaded_plugins[plugin_id]

            for instance in plugin_instances:
                # Call cleanup if available
                if hasattr(instance, 'cleanup'):
                    instance.cleanup()

                # Remove from registries
                if isinstance(instance, MetricPlugin):
                    metric_id = instance.metric_id
                    if metric_id in self.metric_plugins:
                        del self.metric_plugins[metric_id]
                elif isinstance(instance, ProcessorPlugin):
                    if plugin_id in self.processor_plugins:
                        del self.processor_plugins[plugin_id]
                elif isinstance(instance, ExporterPlugin):
                    export_format = instance.export_format
                    if export_format in self.exporter_plugins:
                        del self.exporter_plugins[export_format]

            del self.loaded_plugins[plugin_id]

            if plugin_id in self.plugin_info:
                self.plugin_info[plugin_id].enabled = False

            logger.info(f"Unloaded plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}", exc_info=True)

        return False

    def _check_dependencies(self, dependencies: List[str]) -> List[str]:
        """Check if plugin dependencies are available."""
        missing = []

        for dep in dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                missing.append(dep)

        return missing

    def get_metric_collectors(self) -> Dict[str, MetricCollector]:
        """Get all metric collectors from loaded plugins."""
        collectors = {}

        for metric_id, plugin in self.metric_plugins.items():
            def make_collector(p=plugin):
                return lambda: p.collect_metrics()

            collectors[metric_id] = make_collector()

        return collectors

    def process_metrics_with_plugins(self, metrics: Dict[str, MetricData]) -> Dict[str, MetricData]:
        """Process metrics through all loaded processor plugins."""
        processed_metrics = metrics.copy()

        for plugin in self.processor_plugins.values():
            try:
                processed_metrics = plugin.process_metrics(processed_metrics)
            except Exception as e:
                logger.error(f"Error in processor plugin {plugin.__class__.__name__}", exc_info=True)

        return processed_metrics

    def export_with_plugin(self, export_format: str, metrics: Dict[str, MetricData],
                          file_path: Path, **kwargs) -> bool:
        """Export metrics using a specific exporter plugin."""
        if export_format not in self.exporter_plugins:
            return False

        try:
            plugin = self.exporter_plugins[export_format]
            return plugin.export_metrics(metrics, file_path, **kwargs)
        except Exception as e:
            logger.error(f"Error in exporter plugin {export_format}", exc_info=True)
            return False

    def get_plugin_status(self) -> Dict[str, Any]:
        """Get status of all plugins."""
        return {
            "total_plugins": len(self.plugin_info),
            "loaded_plugins": len(self.loaded_plugins),
            "metric_plugins": len(self.metric_plugins),
            "processor_plugins": len(self.processor_plugins),
            "exporter_plugins": len(self.exporter_plugins),
            "plugin_directories": [str(d) for d in self.plugin_directories],
            "plugins": [
                {
                    "id": info.id,
                    "name": info.name,
                    "version": info.version,
                    "enabled": info.enabled,
                    "error": info.error
                }
                for info in self.plugin_info.values()
            ]
        }

    def configure_plugin(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """Configure a plugin with provided settings."""
        self.plugin_configs[plugin_id] = config

        # If plugin is loaded, apply configuration
        if plugin_id in self.loaded_plugins:
            plugin_instances = self.loaded_plugins[plugin_id]
            for instance in plugin_instances:
                if hasattr(instance, 'configure'):
                    try:
                        return instance.configure(config)
                    except Exception as e:
                        logger.error(f"Failed to configure plugin {plugin_id}", exc_info=True)
                        return False

        return True

    def get_plugin_configuration_schema(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration schema for a plugin."""
        if plugin_id in self.loaded_plugins:
            plugin_instances = self.loaded_plugins[plugin_id]
            for instance in plugin_instances:
                if hasattr(instance, 'get_configuration_schema'):
                    return instance.get_configuration_schema()

        return None

    def reload_plugin(self, plugin_id: str) -> bool:
        """Reload a plugin."""
        was_loaded = plugin_id in self.loaded_plugins

        if was_loaded:
            self.unload_plugin(plugin_id)

        # Re-discover the plugin
        if plugin_id in self.plugin_info:
            plugin_info = self.plugin_info[plugin_id]
            updated_info = self._analyze_plugin_file(plugin_info.file_path)
            if updated_info:
                self.plugin_info[plugin_id] = updated_info

        if was_loaded:
            return self.load_plugin(plugin_id)

        return True

    def save_plugin_configuration(self, config_file: Path):
        """Save plugin configuration to file."""
        config_data = {
            "plugin_configs": self.plugin_configs,
            "enabled_plugins": [
                plugin_id for plugin_id, info in self.plugin_info.items()
                if info.enabled
            ]
        }

        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save plugin configuration", exc_info=True)

    def load_plugin_configuration(self, config_file: Path):
        """Load plugin configuration from file."""
        if not config_file.exists():
            return

        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)

            # Load plugin configurations
            self.plugin_configs = config_data.get("plugin_configs", {})

            # Enable configured plugins
            enabled_plugins = config_data.get("enabled_plugins", [])
            for plugin_id in enabled_plugins:
                self.load_plugin(plugin_id)

        except Exception as e:
            logger.error("Failed to load plugin configuration", exc_info=True)