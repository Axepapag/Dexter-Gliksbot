"""
Configuration Manager for Dexter-Gliksbot

Provides centralized configuration management with:
- Atomic read/write operations
- YAML validation
- File system watching for hot-reload
- Fallback to legacy configs during migration
- Thread-safe singleton pattern

Usage:
    from dexter_autonomy.configs.config_manager import ConfigManager
    
    config = ConfigManager()
    dexter_slot = config.get("agents.dexter-orchestrator")
    config.set("agents.bsm.model", "llama3:8b")
    config.save()
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for config file changes."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._last_modified = 0
        
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification events."""
        if not isinstance(event, FileModifiedEvent):
            return
            
        # Debounce rapid file changes (some editors trigger multiple events)
        import time
        current_time = time.time()
        if current_time - self._last_modified < 0.5:
            return
        self._last_modified = current_time
        
        if Path(event.src_path) == self.config_manager.config_path:
            logger.info(f"Config file modified: {event.src_path}")
            try:
                self.config_manager.reload(notify=True)
            except Exception as e:
                logger.error(f"Failed to reload config: {e}")


class ConfigManager:
    """
    Centralized configuration manager for Dexter-Gliksbot.
    
    Singleton pattern ensures only one instance exists globally.
    Thread-safe for concurrent access.
    """
    
    _instance: Optional[ConfigManager] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        watch: bool = True,
        fallback_legacy: bool = True
    ):
        """
        Initialize ConfigManager.
        
        Args:
            config_path: Path to dexter_config.yml (default: configs/dexter_config.yml)
            watch: Enable file system watching for hot-reload
            fallback_legacy: Fall back to legacy configs if unified config missing
        """
        # Only initialize once (singleton)
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._observers: List[Observer] = []
        self._change_callbacks: List[callable] = []
        
        # Determine config path
        if config_path is None:
            repo_root = Path(__file__).parent.parent.parent
            config_path = repo_root / "configs" / "dexter_config.yml"
        
        self.config_path = Path(config_path)
        self.fallback_legacy = fallback_legacy
        
        # Load configuration
        self.reload(notify=False)
        
        # Start file system watcher
        if watch:
            self.start_watching()
    
    def reload(self, notify: bool = True) -> None:
        """
        Reload configuration from disk.
        
        Args:
            notify: Trigger change callbacks after reload
        """
        with self._lock:
            logger.info(f"Loading configuration from {self.config_path}")
            
            if self.config_path.exists():
                # Load unified config
                self._config = self._load_unified_config()
                logger.info("Loaded unified configuration")
            elif self.fallback_legacy:
                # Fall back to legacy configs
                logger.warning("Unified config not found, falling back to legacy configs")
                self._config = self._load_legacy_configs()
            else:
                raise FileNotFoundError(
                    f"Configuration file not found: {self.config_path}\n"
                    "Create configs/dexter_config.yml or enable fallback_legacy=True"
                )
            
            # Validate configuration
            valid, errors = self._validate_config(self._config)
            if not valid:
                error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Notify callbacks
            if notify:
                self._notify_change("*", self._config)
    
    def _load_unified_config(self) -> Dict[str, Any]:
        """Load unified dexter_config.yml."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            return config
        except Exception as e:
            logger.error(f"Failed to load {self.config_path}: {e}")
            raise
    
    def _load_legacy_configs(self) -> Dict[str, Any]:
        """
        Load and merge legacy config files during migration period.
        
        Merges:
        - configs/dexter.yml → system
        - configs/slots.yml → agents
        - configs/denylist.master.yml → deny_list.global
        - configs/denylist.profiles.yml → security_profiles
        - configs/agents.overlays.yml → deny_list.agents
        """
        config_dir = self.config_path.parent
        merged = {
            "version": "1.0.0-legacy",
            "system": {},
            "agents": [],
            "deny_list": {"global": {}, "agents": {}},
            "security_profiles": {},
            "providers": {},
            "brain": {},
            "workers": {},
            "ui_bridge": {},
            "cockpit": {},
            "collaboration": {},
            "windows": {},
            "logging": {},
            "development": {}
        }
        
        # Load dexter.yml
        dexter_yml = config_dir / "dexter.yml"
        if dexter_yml.exists():
            with open(dexter_yml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                merged["system"] = {
                    "data_dir": data.get("data_dir", "./data"),
                    "collab_dir": data.get("collab_dir", "./collaboration"),
                }
                merged["ui_bridge"]["host"] = data.get("server", {}).get("host", "0.0.0.0")
                merged["ui_bridge"]["port"] = data.get("server", {}).get("port", 8765)
                merged["providers"]["ollama"] = {
                    "endpoint": data.get("ollama", {}).get("host", "http://127.0.0.1:11434")
                }
                merged["windows"]["ocr"] = {
                    "tesseract_path": data.get("tesseract_path", "C:/Program Files/Tesseract-OCR/tesseract.exe")
                }
        
        # Load slots.yml
        slots_yml = config_dir / "slots.yml"
        if slots_yml.exists():
            with open(slots_yml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                slots = data.get("slots", {})
                
                for slot_id, slot_config in slots.items():
                    agent = {
                        "id": slot_id,
                        "name": slot_config.get("label", slot_id),
                        "description": slot_config.get("description", ""),
                        "enabled": True,
                        "provider": "ollama",  # Default, can be overridden
                        "model": slot_config.get("model", ""),
                        "temperature": slot_config.get("temperature", 0.2),
                        "system_prompt": slot_config.get("system_prompt", ""),
                        "params": slot_config.get("ollama_options", {})
                    }
                    merged["agents"].append(agent)
        
        # Load denylist.master.yml
        denylist_master = config_dir / "denylist.master.yml"
        if denylist_master.exists():
            with open(denylist_master, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                merged["deny_list"]["global"] = data
        
        # Load denylist.profiles.yml
        denylist_profiles = config_dir / "denylist.profiles.yml"
        if denylist_profiles.exists():
            with open(denylist_profiles, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                merged["security_profiles"] = {
                    "active_profile": data.get("mode_default", "medium"),
                    "profiles": data.get("profiles", {})
                }
        
        # Load agents.overlays.yml
        agents_overlays = config_dir / "agents.overlays.yml"
        if agents_overlays.exists():
            with open(agents_overlays, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                merged["deny_list"]["agents"] = data
        
        logger.info("Merged legacy configurations")
        return merged
    
    def _validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration structure.
        
        Returns:
            (is_valid, error_list)
        """
        errors = []
        
        # Check required top-level sections
        required_sections = ["agents", "deny_list", "providers"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Validate agents section
        if "agents" in config:
            agents = config["agents"]
            if not isinstance(agents, list):
                errors.append("'agents' must be a list")
            else:
                for i, agent in enumerate(agents):
                    if not isinstance(agent, dict):
                        errors.append(f"Agent {i} must be a dict")
                        continue
                    
                    required_agent_fields = ["id", "name"]
                    for field in required_agent_fields:
                        if field not in agent:
                            errors.append(f"Agent {i} missing required field: {field}")
        
        # Validate deny_list structure
        if "deny_list" in config:
            deny_list = config["deny_list"]
            if not isinstance(deny_list, dict):
                errors.append("'deny_list' must be a dict")
            elif "global" not in deny_list:
                errors.append("'deny_list.global' is required")
        
        # Validate providers
        if "providers" in config:
            providers = config["providers"]
            if not isinstance(providers, dict):
                errors.append("'providers' must be a dict")
        
        return len(errors) == 0, errors
    
    def _validate_section(self, section: str, data: Any) -> Tuple[bool, List[str]]:
        """
        Validate specific configuration section.
        
        Args:
            section: Section name (e.g., "agents", "providers")
            data: Section data to validate
        
        Returns:
            (is_valid, error_list)
        """
        errors = []
        
        # Section-specific validation
        if section == "agents":
            if not isinstance(data, list):
                errors.append("'agents' must be a list")
            else:
                for i, agent in enumerate(data):
                    if not isinstance(agent, dict):
                        errors.append(f"Agent {i} must be a dict")
                        continue
                    
                    # Required fields
                    if "id" not in agent:
                        errors.append(f"Agent {i} missing 'id' field")
                    if "name" not in agent:
                        errors.append(f"Agent {i} missing 'name' field")
                    
                    # Validate temperature
                    if "temperature" in agent:
                        temp = agent["temperature"]
                        if not isinstance(temp, (int, float)):
                            errors.append(f"Agent {i} temperature must be a number")
                        elif not 0.0 <= temp <= 2.0:
                            errors.append(f"Agent {i} temperature {temp} must be between 0.0 and 2.0")
        
        elif section == "providers":
            if not isinstance(data, dict):
                errors.append("'providers' must be a dict")
            else:
                for provider_name, provider_config in data.items():
                    if not isinstance(provider_config, dict):
                        errors.append(f"Provider '{provider_name}' config must be a dict")
                    # Additional provider validation can be added here
        
        elif section == "deny_list":
            if not isinstance(data, dict):
                errors.append("'deny_list' must be a dict")
            elif "global" not in data:
                errors.append("'deny_list.global' is required")
        
        # Generic validation for unknown sections
        elif not isinstance(data, (dict, list)):
            errors.append(f"Section '{section}' must be a dict or list")
        
        return len(errors) == 0, errors
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        
        Args:
            path: Dot-separated path (e.g., "agents.bsm.model")
            default: Default value if path not found
        
        Returns:
            Configuration value or default
        
        Example:
            config.get("ui_bridge.port")  # Returns 8765
            config.get("agents.bsm.model", "llama3:8b")
        """
        with self._lock:
            keys = path.split(".")
            value = self._config
            
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list):
                    try:
                        idx = int(key)
                        value = value[idx]
                    except (ValueError, IndexError):
                        return default
                else:
                    return default
                
                if value is None:
                    return default
            
            return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Top-level section name (e.g., "agents", "providers")
        
        Returns:
            Section dictionary or empty dict if not found
        """
        with self._lock:
            return self._config.get(section, {})
    
    def set(self, path: str, value: Any) -> None:
        """
        Set configuration value by dot-separated path.
        
        Args:
            path: Dot-separated path (e.g., "agents.bsm.model")
            value: Value to set
        
        Example:
            config.set("agents.bsm.model", "llama3:8b")
            config.set("ui_bridge.port", 9000)
        
        Note: Changes are in-memory only until save() is called.
        """
        with self._lock:
            keys = path.split(".")
            target = self._config
            
            # Navigate to parent
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            
            # Set value
            target[keys[-1]] = value
            
            # Notify callbacks
            self._notify_change(path, value)
    
    def update_section(self, section: str, data: Dict[str, Any]) -> None:
        """
        Update entire configuration section.
        
        Args:
            section: Top-level section name
            data: New section data
        """
        with self._lock:
            self._config[section] = data
            self._notify_change(section, data)
    
    def save(self) -> None:
        """
        Save configuration to disk atomically.
        
        Uses atomic write pattern: write to temp file, then rename.
        This ensures config file is never corrupted even if process crashes.
        """
        with self._lock:
            # Validate before saving
            valid, errors = self._validate_config(self._config)
            if not valid:
                error_msg = "Cannot save invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write: temp file → rename
            temp_path = self.config_path.with_suffix(".tmp")
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(
                        self._config,
                        f,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                        indent=2
                    )
                
                # Atomic rename
                temp_path.replace(self.config_path)
                logger.info(f"Configuration saved to {self.config_path}")
            
            except Exception as e:
                # Clean up temp file on error
                if temp_path.exists():
                    temp_path.unlink()
                logger.error(f"Failed to save configuration: {e}")
                raise
    
    def start_watching(self) -> None:
        """Start file system watcher for hot-reload."""
        if not self.config_path.exists():
            logger.warning(f"Cannot watch non-existent config: {self.config_path}")
            return
        
        event_handler = ConfigFileHandler(self)
        observer = Observer()
        observer.schedule(
            event_handler,
            path=str(self.config_path.parent),
            recursive=False
        )
        observer.start()
        self._observers.append(observer)
        logger.info(f"Started watching config file: {self.config_path}")
    
    def stop_watching(self) -> None:
        """Stop all file system watchers."""
        for observer in self._observers:
            observer.stop()
            observer.join()
        self._observers.clear()
        logger.info("Stopped watching config file")
    
    def register_change_callback(self, callback: callable) -> None:
        """
        Register callback for configuration changes.
        
        Args:
            callback: Function called with (path, value) when config changes
        
        Example:
            def on_config_change(path, value):
                print(f"Config changed: {path} = {value}")
            
            config.register_change_callback(on_config_change)
        """
        self._change_callbacks.append(callback)
    
    def _notify_change(self, path: str, value: Any) -> None:
        """Notify all registered callbacks of configuration change."""
        for callback in self._change_callbacks:
            try:
                callback(path, value)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")
    
    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for specific agent by ID.
        
        Args:
            agent_id: Agent identifier (e.g., "bsm", "dexter-orchestrator")
        
        Returns:
            Agent configuration dict or None if not found
        """
        agents = self.get_section("agents")
        if not isinstance(agents, list):
            return None
        
        for agent in agents:
            if agent.get("id") == agent_id:
                return agent
        
        return None
    
    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for specific provider.
        
        Args:
            provider_name: Provider name (e.g., "ollama", "openai", "perplexity")
        
        Returns:
            Provider configuration dict or None if not found
        """
        providers = self.get_section("providers")
        return providers.get(provider_name)
    
    def export_to_dict(self) -> Dict[str, Any]:
        """
        Export full configuration as dictionary.
        
        Returns:
            Deep copy of configuration
        """
        import copy
        with self._lock:
            return copy.deepcopy(self._config)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop watchers."""
        self.stop_watching()


# Global singleton instance
_global_config: Optional[ConfigManager] = None


def get_global_config() -> ConfigManager:
    """
    Get global ConfigManager singleton.
    
    Returns:
        Global ConfigManager instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config


def reload_global_config() -> None:
    """Force reload of global configuration."""
    config = get_global_config()
    config.reload(notify=True)
