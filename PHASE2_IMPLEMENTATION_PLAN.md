# Phase 2: Cockpit-Config Integration - Implementation Plan
**Date**: 2025-10-14  
**Status**: 🚀 ACTIVE - Implementation In Progress  
**Objective**: Seamless two-way sync between Cockpit UI and dexter_config.yml

---

## 🎯 Core Objectives

1. ✅ **Integrate agent slots** - BSM, SONAR PRO, Dexter
2. ✅ **Wire Cockpit UI** - Direct YAML read/write from UI
3. ✅ **Two-way sync** - Real-time bidirectional updates
4. ✅ **Edge case handling** - Concurrent edits, validation, rollback
5. ✅ **Comprehensive documentation** - Maintainable and scalable

---

## 🎨 Creative Enhancements (Innovation Focus)

### 1. **Config Versioning & Snapshots** 🔄
**Problem**: User makes breaking change, needs to rollback  
**Solution**: Git-like version history embedded in config system

**Implementation**:
```python
# dexter_autonomy/configs/config_versioning.py
class ConfigVersionManager:
    def create_snapshot(self, name: str, description: str):
        """Save current config as named snapshot"""
        snapshot = {
            "id": uuid.uuid4(),
            "name": name,
            "timestamp": datetime.now(),
            "config": config_manager.export_to_dict(),
            "description": description,
            "created_by": "user"  # or agent ID
        }
        self._save_snapshot(snapshot)
    
    def rollback_to_snapshot(self, snapshot_id: str):
        """Restore config from snapshot"""
        snapshot = self._load_snapshot(snapshot_id)
        config_manager.load_from_dict(snapshot["config"])
        config_manager.save()
```

**UI Features**:
- Timeline view of config changes
- One-click rollback
- Compare snapshots (diff viewer)
- Auto-snapshots before major changes

---

### 2. **AI-Powered Config Suggestions** 🤖
**Problem**: User doesn't know optimal settings  
**Solution**: BSM analyzes performance and suggests improvements

**Implementation**:
```python
# dexter_autonomy/configs/config_optimizer.py
class ConfigOptimizer:
    async def analyze_performance(self):
        """BSM analyzes recent metrics"""
        metrics = {
            "agent_response_times": brain.query("SELECT AVG(duration) FROM actions"),
            "error_rates": brain.query("SELECT COUNT(*) FROM effects WHERE status='error'"),
            "success_patterns": brain.get_patterns(min_confidence=0.85)
        }
        
        suggestions = await bsm.generate_suggestions(metrics)
        return suggestions
    
    async def suggest_improvements(self):
        """Return actionable suggestions"""
        return [
            {
                "path": "agents.dexter.temperature",
                "current": 0.15,
                "suggested": 0.12,
                "reason": "Lower temperature improved success rate by 8% in last 100 tasks",
                "confidence": 0.87
            },
            {
                "path": "providers.ollama.timeout",
                "current": 60,
                "suggested": 45,
                "reason": "95% of requests complete in <45s, reducing timeout prevents hangs",
                "confidence": 0.92
            }
        ]
```

**UI Features**:
- "Optimize" button in config panel
- Show suggestions with confidence scores
- One-click apply or dismiss
- Track improvement metrics after applying

---

### 3. **Visual Config Diff Viewer** 📊
**Problem**: Hard to see what changed between versions  
**Solution**: Side-by-side YAML diff with syntax highlighting

**Implementation**:
```csharp
// cockpit/DexterCockpit/Views/ConfigDiffView.xaml.cs
public class ConfigDiffViewModel
{
    public async Task<ConfigDiff> CompareSn apshots(string snapshotA, string snapshotB)
    {
        var diff = await _apiClient.CompareConfigSnapshotsAsync(snapshotA, snapshotB);
        
        return new ConfigDiff
        {
            Added = diff.Added,      // Highlighted green
            Removed = diff.Removed,  // Highlighted red
            Modified = diff.Modified // Highlighted yellow
        };
    }
}
```

**UI Features**:
- Split-pane diff viewer
- Syntax highlighting
- Collapsible sections
- Search/filter changes

---

### 4. **Hot-Reload Without Restart** ⚡
**Problem**: Restarting agents disrupts operations  
**Solution**: Agents subscribe to CONFIG_CHANGED and update in-place

**Implementation**:
```python
# dexter_autonomy/agents/dexter_orchestrator.py
class DexterOrchestrator:
    def __init__(self, ...):
        # Subscribe to config changes
        config_manager.register_change_callback(self._on_config_changed)
    
    async def _on_config_changed(self, path: str, value: Any):
        """Handle config change without restart"""
        if path.startswith("agents.dexter-orchestrator"):
            # Update in-memory settings
            if "temperature" in path:
                self.temperature = value
                logger.info(f"Hot-reloaded temperature: {value}")
            elif "model" in path:
                # Reinitialize LLM client
                await self._reinit_llm_client(value)
                logger.info(f"Hot-reloaded model: {value}")
        
        # Broadcast change to UI
        await self.buses.main.publish(MainTopic.TRACE, {
            "event": "config_hot_reload",
            "path": path,
            "value": value,
            "agent": "dexter-orchestrator"
        })
```

**Benefits**:
- Zero downtime config updates
- Agents remain in current state
- Gradual rollout (update one agent at a time)

---

### 5. **Config Validation Rules** ✅
**Problem**: Invalid configs break agents  
**Solution**: Schema-based validation with helpful error messages

**Implementation**:
```python
# dexter_autonomy/configs/config_validator.py
class ConfigValidator:
    RULES = {
        "agents.*.temperature": {
            "type": "float",
            "min": 0.0,
            "max": 2.0,
            "description": "Temperature controls randomness (0=deterministic, 2=creative)"
        },
        "agents.*.model": {
            "type": "string",
            "required": True,
            "validator": lambda v: validate_model_exists(v),
            "error": "Model must be pulled first: ollama pull {value}"
        },
        "deny_list.global.process.deny_cmd_patterns": {
            "type": "list[string]",
            "validator": lambda v: all(validate_glob_pattern(p) for p in v),
            "error": "Invalid glob pattern: {value}"
        }
    }
    
    def validate(self, path: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate value against rules"""
        rule = self._get_rule(path)
        if not rule:
            return True, None  # No rule = allow
        
        # Type check
        if not isinstance(value, rule["type"]):
            return False, f"Expected {rule['type']}, got {type(value)}"
        
        # Range check
        if "min" in rule and value < rule["min"]:
            return False, f"Value {value} below minimum {rule['min']}"
        
        # Custom validator
        if "validator" in rule and not rule["validator"](value):
            return False, rule["error"].format(value=value)
        
        return True, None
```

**UI Features**:
- Real-time validation as user types
- Helpful error messages
- Suggested fixes
- Prevent saving invalid configs

---

### 6. **Multi-Environment Profiles** 🌍
**Problem**: Different settings for dev/staging/prod  
**Solution**: Switchable environment configs

**Implementation**:
```yaml
# configs/dexter_config.yml
environments:
  dev:
    ui_bridge:
      port: 8765
      debug_mode: true
    agents:
      - id: dexter-orchestrator
        model: llama3:8b  # Lightweight for dev
  
  staging:
    ui_bridge:
      port: 8766
      debug_mode: false
    agents:
      - id: dexter-orchestrator
        model: qwen2.5:32b  # More powerful
  
  prod:
    ui_bridge:
      port: 443
      debug_mode: false
      ssl_enabled: true
    agents:
      - id: dexter-orchestrator
        provider: perplexity
        model: sonar-pro  # Production-grade

active_environment: dev
```

**UI Features**:
- Dropdown to switch environments
- Show current environment prominently
- Warn before editing prod config
- Environment-specific color schemes (dev=blue, prod=red)

---

### 7. **Config Analytics Dashboard** 📈
**Problem**: Don't know which settings work best  
**Solution**: Track correlations between config and performance

**Implementation**:
```python
# dexter_autonomy/configs/config_analytics.py
class ConfigAnalytics:
    async def track_config_change(self, path: str, old_value: Any, new_value: Any):
        """Record config change and track subsequent performance"""
        change_id = uuid.uuid4()
        await brain.add_memory(
            kind="config_change",
            content=f"Changed {path}: {old_value} → {new_value}",
            meta={
                "change_id": change_id,
                "path": path,
                "old_value": old_value,
                "new_value": new_value,
                "timestamp": datetime.now()
            }
        )
        
        # Track performance for next 100 actions
        asyncio.create_task(self._track_performance(change_id, duration=3600))
    
    async def get_best_configs(self):
        """Return configs with best historical performance"""
        return await brain.query("""
            SELECT config_path, config_value, AVG(success_rate) as avg_success
            FROM config_changes
            JOIN performance_metrics ON config_changes.change_id = performance_metrics.config_id
            GROUP BY config_path, config_value
            ORDER BY avg_success DESC
            LIMIT 10
        """)
```

**UI Features**:
- Performance graphs after config changes
- "Best performing configs" recommendations
- A/B testing support (try two configs, compare results)

---

### 8. **Natural Language Config Interface** 💬
**Problem**: YAML editing is tedious  
**Solution**: Chat with Dexter to change settings

**Implementation**:
```python
# dexter_autonomy/agents/config_nlp.py
class ConfigNLPHandler:
    async def process_command(self, user_text: str):
        """Parse natural language config commands"""
        
        # Examples:
        # "Set all agents to use Claude Sonnet with 8k context"
        # "Increase Dexter's temperature to 0.3"
        # "Switch to production environment"
        # "Enable debug mode for BSM"
        
        parsed = await aum.extract_config_intent(user_text)
        
        if parsed["action"] == "set_all_agents":
            for agent in config.get_section("agents"):
                config.set(f"agents.{agent['id']}.model", parsed["model"])
                config.set(f"agents.{agent['id']}.params.num_ctx", parsed["context"])
        
        elif parsed["action"] == "set_agent_param":
            config.set(f"agents.{parsed['agent']}.{parsed['param']}", parsed["value"])
        
        config.save()
        return f"✅ Updated {parsed['affected_count']} settings"
```

**UI Features**:
- Chat input in config panel
- Auto-complete suggestions
- Confirm before applying changes
- Show what will change before executing

---

## 🏗️ Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cockpit WPF UI                            │
├─────────────────────────────────────────────────────────────────┤
│  ConfigurationView  │  DiffView  │  SnapshotsView  │  ChatPanel │
│  ├─ Agent Editor    │  ├─ YAML   │  ├─ Timeline    │  ├─ NLP    │
│  ├─ Provider Editor │  └─ Visual │  └─ Compare     │  └─ Apply  │
│  └─ Security Editor │            │                 │            │
└──────────────┬──────────────────────────────────────────────────┘
               │
          HTTP │ REST API                     WebSocket
               ├───────────────┐              ├─────────────────┐
               ▼               ▼              ▼                 ▼
┌──────────────────────────────────────────────────────────────────┐
│             dexter_autonomy/ui_bridge/api.py                      │
├──────────────────────────────────────────────────────────────────┤
│  GET    /config                  WS  /ws/cockpit                 │
│  GET    /config/{section}        Event: CONFIG_CHANGED           │
│  PUT    /config/{section}        Event: CONFIG_VALIDATED         │
│  POST   /config/validate         Event: CONFIG_SNAPSHOT          │
│  POST   /config/reload                                           │
│  GET    /config/snapshots                                        │
│  POST   /config/snapshots                                        │
│  POST   /config/snapshots/{id}/restore                           │
│  GET    /config/diff/{a}/{b}                                     │
│  POST   /config/optimize                                         │
│  GET    /config/analytics                                        │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│       dexter_autonomy/configs/config_manager.py                   │
├──────────────────────────────────────────────────────────────────┤
│  • Load/Save (atomic operations)                                 │
│  • Validation (schema-based)                                     │
│  • Hot-reload (file system watcher)                              │
│  • Change callbacks (notify observers)                           │
│  • Version history (snapshots)                                   │
│  • Diff generation (compare configs)                             │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ├────────────────┬────────────────┬─────────────────┐
               ▼                ▼                ▼                 ▼
         ┌─────────┐      ┌─────────┐     ┌──────────┐     ┌──────────┐
         │ Dexter  │      │   BSM   │     │ Providers│     │  Policy  │
         │ Orchest │      │  Agent  │     │ Registry │     │  Engine  │
         └─────────┘      └─────────┘     └──────────┘     └──────────┘
              │                │                │                 │
              └────────────────┴────────────────┴─────────────────┘
                                      │
                                      ▼
                            Hot-reload on change
                         (no agent restart needed)
```

---

## 📁 File Structure

### New Files to Create

```
dexter_autonomy/
├── configs/
│   ├── __init__.py                 ✅ EXISTS
│   ├── config_manager.py           ✅ EXISTS
│   ├── config_versioning.py        🆕 CREATE
│   ├── config_validator.py         🆕 CREATE
│   ├── config_optimizer.py         🆕 CREATE
│   ├── config_analytics.py         🆕 CREATE
│   └── config_nlp.py               🆕 CREATE
│
├── api/
│   └── config_routes.py            🆕 CREATE (REST endpoints)
│
└── ui_bridge/
    └── api.py                      ⚙️ MODIFY (add config routes)

cockpit/DexterCockpit/
├── Models/
│   ├── ConfigSection.cs            🆕 CREATE
│   ├── ConfigSnapshot.cs           🆕 CREATE
│   ├── ConfigDiff.cs               🆕 CREATE
│   └── ConfigSuggestion.cs         🆕 CREATE
│
├── ViewModels/
│   ├── ConfigurationViewModel.cs   🆕 CREATE
│   ├── ConfigEditorViewModel.cs    🆕 CREATE
│   ├── SnapshotsViewModel.cs       🆕 CREATE
│   └── ConfigChatViewModel.cs      🆕 CREATE
│
├── Views/
│   ├── ConfigurationView.xaml      🆕 CREATE
│   ├── ConfigEditorView.xaml       🆕 CREATE
│   ├── ConfigDiffView.xaml         🆕 CREATE
│   └── SnapshotsView.xaml          🆕 CREATE
│
└── Services/
    └── DexterApiClient.cs          ⚙️ MODIFY (add config methods)

configs/
└── dexter_config.yml               🆕 CREATE (unified config)
```

---

## 🔧 Implementation Phases

### Phase 2.1: Core Config Sync (CURRENT)
**Priority**: HIGH  
**Estimated Time**: 4-6 hours

**Tasks**:
1. ✅ Create config API endpoints (`/config`, `/config/{section}`)
2. ✅ Add WebSocket CONFIG_CHANGED event
3. ✅ Implement file system watcher in ConfigManager
4. ✅ Create C# models (ConfigSection, etc.)
5. ✅ Update DexterApiClient with config methods
6. ✅ Create ConfigurationView in Cockpit
7. ✅ Test two-way sync (UI → file, file → UI)

---

### Phase 2.2: Versioning & Snapshots
**Priority**: HIGH  
**Estimated Time**: 3-4 hours

**Tasks**:
1. Implement ConfigVersionManager
2. Add snapshot endpoints
3. Create SnapshotsView in Cockpit
4. Add timeline UI
5. Test rollback scenarios

---

### Phase 2.3: Validation & Optimization
**Priority**: MEDIUM  
**Estimated Time**: 4-5 hours

**Tasks**:
1. Implement ConfigValidator with rules
2. Implement ConfigOptimizer with BSM integration
3. Add validation endpoints
4. Create suggestion UI in Cockpit
5. Test edge cases (invalid inputs, concurrent edits)

---

### Phase 2.4: Advanced Features
**Priority**: LOW (Nice-to-Have)  
**Estimated Time**: 6-8 hours

**Tasks**:
1. Implement multi-environment profiles
2. Add config analytics tracking
3. Create NLP interface for config changes
4. Build diff viewer UI
5. Add A/B testing support

---

## 🧪 Edge Cases & Testing

### Concurrent Edit Scenarios

#### Scenario 1: Two Cockpits Edit Same Config
**Problem**: Last write wins, data loss  
**Solution**: Optimistic locking with version numbers

```python
# config_manager.py
class ConfigManager:
    def __init__(self):
        self._version = 0  # Increments on each save
    
    def save_with_version_check(self, expected_version: int):
        if self._version != expected_version:
            raise ConfigConflictError(
                f"Config was modified by another client. "
                f"Expected version {expected_version}, current is {self._version}. "
                f"Please reload and reapply your changes."
            )
        self._version += 1
        self.save()
```

**UI Behavior**:
- Show "Config was modified" dialog
- Offer to reload or force save
- Highlight conflicting sections

---

#### Scenario 2: File Edited While Cockpit Open
**Problem**: Cockpit shows stale data  
**Solution**: File system watcher + WebSocket notification

```python
# File watcher detects change
async def on_file_modified(event):
    config_manager.reload(notify=True)
    
    # Broadcast to all connected Cockpits
    await ws_manager.broadcast(
        WebSocketMessage(
            type=EventType.CONFIG_CHANGED,
            payload={
                "source": "external_file_edit",
                "timestamp": datetime.now(),
                "sections_changed": ["agents", "providers"]
            }
        )
    )
```

**UI Behavior**:
- Show toast: "Config updated externally"
- Reload UI with new values
- Highlight changed sections in yellow

---

#### Scenario 3: Agent Restart During Config Update
**Problem**: Agent crashes mid-update  
**Solution**: Atomic writes + agent health checks

```python
# Atomic write ensures file never corrupted
temp_path.write_text(yaml.safe_dump(config))
temp_path.replace(config_path)  # Atomic

# Agent checks config version on restart
class DexterOrchestrator:
    def __init__(self):
        config_version = config_manager.get_version()
        if config_version > self._last_loaded_version:
            logger.info("Config changed during restart, reloading...")
            self._reload_config()
```

---

#### Scenario 4: Invalid Value Breaks Agent
**Problem**: Agent crashes after loading bad config  
**Solution**: Pre-validation + schema enforcement

```python
# Validate before save
valid, errors = validator.validate_all(config)
if not valid:
    raise ValidationError(f"Cannot save: {errors}")

# Agent validates on load
class DexterOrchestrator:
    def _load_config(self):
        config = config_manager.get_agent_config("dexter-orchestrator")
        
        # Validate critical fields
        if not 0.0 <= config["temperature"] <= 2.0:
            logger.error(f"Invalid temperature: {config['temperature']}, using default 0.15")
            config["temperature"] = 0.15
        
        return config
```

---

#### Scenario 5: Network Latency in WebSocket Sync
**Problem**: UI shows outdated state briefly  
**Solution**: Local cache + eventual consistency

```csharp
// Cockpit maintains local cache
public class ConfigurationViewModel
{
    private Dictionary<string, object> _localCache;
    private Timer _syncTimer;
    
    public async Task<void> UpdateValue(string path, object value)
    {
        // Optimistic update (instant UI feedback)
        _localCache[path] = value;
        OnPropertyChanged(nameof(Config));
        
        // Send to server (may take 100-500ms)
        try
        {
            await _apiClient.UpdateConfigAsync(path, value);
        }
        catch (Exception ex)
        {
            // Rollback on failure
            _localCache[path] = await _apiClient.GetConfigValueAsync(path);
            OnPropertyChanged(nameof(Config));
            ShowError($"Failed to save: {ex.Message}");
        }
    }
}
```

---

#### Scenario 6: File System Permissions Issue
**Problem**: Can't write to config file  
**Solution**: Graceful degradation + helpful error

```python
def save(self):
    try:
        temp_path.write_text(yaml.safe_dump(self._config))
        temp_path.replace(self.config_path)
    except PermissionError:
        logger.error(f"Permission denied writing to {self.config_path}")
        raise ConfigSaveError(
            f"Cannot write to {self.config_path}. "
            f"Fix: Run as administrator or check file permissions.\n"
            f"Windows: Right-click file → Properties → Security\n"
            f"Linux: chmod 644 {self.config_path}"
        )
    except OSError as e:
        logger.error(f"OS error saving config: {e}")
        raise ConfigSaveError(
            f"Failed to save config: {e}\n"
            f"Disk full? Path exists? Check logs for details."
        )
```

---

## 📊 Success Metrics

### Phase 2 Complete When:
- ✅ BSM agent configured in dexter_config.yml (llama3:8b)
- ✅ Dexter agent configured with SONAR PRO
- ✅ Cockpit can read/write config via REST API
- ✅ File changes reflected in Cockpit UI within 1 second
- ✅ UI changes saved to file within 1 second
- ✅ Concurrent edits handled gracefully (no data loss)
- ✅ Invalid configs rejected with helpful errors
- ✅ Config snapshots/rollback working
- ✅ All edge cases tested and passing
- ✅ Documentation complete and reviewed

---

## 🚀 Let's Begin!

**Next Steps**:
1. Create config API endpoints in `dexter_autonomy/api/config_routes.py`
2. Create unified `configs/dexter_config.yml`
3. Create C# models and API client methods
4. Build ConfigurationView in Cockpit
5. Test two-way sync
6. Implement versioning
7. Add validation layer
8. Document everything

**Estimated Total Time**: 20-30 hours (spread over multiple sessions)

---

**End of Implementation Plan**
