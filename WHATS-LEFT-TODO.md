# 📋 WHAT'S LEFT TO DO - COMPLETE STATUS

**Current Date:** October 16, 2025  
**Phase 1 Progress:** 3/7 components (43%) ✅ WINDOWS TOOLS COMPLETE!  
**Total Remaining:** 25-26 hours (was 37-52)  
**Next Priority:** [P0-2] Deep Health Checks

---

## 🎯 EXECUTIVE SUMMARY

You have **7 major components** in Phase 1. Here's what's done and what's left:

| # | Component | Status | Hours | Priority |
|---|-----------|--------|-------|----------|
| 1 | 🪟 Docking Tab (UI) | ✅ DONE | 0.5 | - |
| 2 | 🔧 Installer Script | ✅ DONE | 1.5 | - |
| 3 | **🖱️ Windows Tools** | ✅ DONE | 4-6 | ✅ UNBLOCKED |
| 4 | **❤️ Health Checks** | ⏳ TODO | 3-4 | 🔴 CRITICAL |
| 5 | **⚙️ Config Unify** | ⏳ TODO | 6-8 | 🟡 HIGH |
| 6 | **🎬 Cockpit Impl** | 🟡 PARTIAL | 3+ | 🟡 HIGH |
| 7 | **✅ E2E Testing** | ⏳ TODO | 8-10 | 🟡 HIGH |

**Time Invested:** 2 hours  
**Time Remaining:** 29-32 hours to complete MVP  
**Estimated Completion:** 5-6 working days (parallel execution)

---

## 🔴 CRITICAL BLOCKERS (Must Do First)

### [P0-1] Windows Automation Tools - 4-6 HOURS ⭐⭐⭐ HIGHEST PRIORITY

**Current State:** Stubs return `True` without actually doing anything  
**Files to Fix:**
- `dexter_autonomy/tools/windows/automation.py`
- `dexter_autonomy/agents/action_executor.py`

**What Needs to Happen:**
```python
# CURRENT (BROKEN)
def click(x: int, y: int) -> bool:
    return True  # Doesn't actually click!

def type_text(text: str) -> bool:
    return True  # Doesn't actually type!

def hotkey(*keys: str) -> bool:
    return True  # Doesn't actually press keys!

# SHOULD BE (WORKING)
import pyautogui
import pytesseract
import time

def click(x: int, y: int) -> bool:
    try:
        pyautogui.click(x, y)
        time.sleep(0.1)  # Small delay after click
        return True
    except Exception as e:
        logger.error(f"Click at ({x}, {y}) failed: {e}")
        return False

def type_text(text: str, interval: float = 0.05) -> bool:
    try:
        pyautogui.typewrite(text, interval=interval)
        return True
    except Exception as e:
        logger.error(f"Type text failed: {e}")
        return False

def hotkey(*keys: str) -> bool:
    try:
        pyautogui.hotkey(*keys)
        time.sleep(0.1)
        return True
    except Exception as e:
        logger.error(f"Hotkey {keys} failed: {e}")
        return False

def ocr_capture(x: int = None, y: int = None, 
                width: int = None, height: int = None) -> str:
    try:
        if any([x, y, width, height]):
            bbox = (x, y, x + width, y + height)
            img = ImageGrab.grab(bbox=bbox)
        else:
            img = ImageGrab.grab()
        
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        logger.error(f"OCR capture failed: {e}")
        return ""
```

**Testing Strategy:**
1. Open Notepad
2. Click in text area → verify cursor appears
3. Type "Hello Dexter" → verify text appears
4. Press Ctrl+A → verify all text selected
5. Press Ctrl+C → verify copied (paste elsewhere to confirm)
6. Capture screen with OCR → verify text extracted
7. Close Notepad (Alt+F4) → verify it closes

**Why This Blocks Everything:**
- ❌ Can't test UI automation
- ❌ Can't demonstrate to customers
- ❌ Can't verify clicking/typing works
- ❌ Can't build customer workflows

**When Done:**
- ✅ Full end-to-end automation working
- ✅ Ready for customer demos
- ✅ Can unblock P0-6 E2E testing

---

### [P0-2] Deep Health Checks - 3-4 HOURS ⭐⭐ VERY HIGH

**Current State:** Returns basic "ok" status  
**File:** `dexter_autonomy/ui_bridge/api.py`  
**Need:** Enhanced `/healthz` endpoint

**What Needs to Happen:**
```python
@app.get("/healthz")
async def health_check():
    """Deep health check of all dependencies"""
    health = {
        "status": "healthy",  # or "degraded" or "unhealthy"
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # 1. Check Ollama
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        models = [m["name"] for m in response.json().get("models", [])]
        health["components"]["ollama"] = {
            "status": "ok" if models else "warning",
            "models": models,
            "endpoint": "http://localhost:11434"
        }
    except Exception as e:
        health["components"]["ollama"] = {
            "status": "error",
            "error": f"Ollama unreachable: {e}",
            "fix": "Run: ollama serve"
        }
        health["status"] = "degraded"
    
    # 2. Check Tesseract
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            timeout=2
        )
        health["components"]["tesseract"] = {
            "status": "ok",
            "version": result.stdout.decode().split("\n")[0]
        }
    except Exception as e:
        health["components"]["tesseract"] = {
            "status": "error",
            "error": f"Tesseract not found: {e}",
            "fix": "Install from: https://github.com/UB-Mannheim/tesseract/wiki"
        }
        health["status"] = "degraded"
    
    # 3. Check Redis (if used)
    try:
        redis_client.ping()
        health["components"]["redis"] = {"status": "ok"}
    except Exception as e:
        health["components"]["redis"] = {
            "status": "error",
            "error": f"Redis unreachable: {e}",
            "fix": "Run: redis-server"
        }
        health["status"] = "degraded"
    
    # 4. Check Brain database
    try:
        brain = BrainDB("data/brain.db")
        size = os.path.getsize("data/brain.db") / (1024*1024)  # MB
        health["components"]["brain"] = {
            "status": "ok",
            "size_mb": size,
            "path": "data/brain.db"
        }
    except Exception as e:
        health["components"]["brain"] = {
            "status": "error",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # 5. Check triple bus
    try:
        health["components"]["triple_bus"] = {
            "status": "ok",
            "channels": ["main", "collab", "private"]
        }
    except Exception as e:
        health["components"]["triple_bus"] = {"status": "error"}
        health["status"] = "degraded"
    
    # 6. Check disk space
    import shutil
    disk = shutil.disk_usage("/")
    free_gb = disk.free / (1024**3)
    health["components"]["disk"] = {
        "status": "ok" if free_gb > 1 else "warning",
        "free_gb": free_gb
    }
    
    return health
```

**When Done:**
- ✅ Users get clear error messages
- ✅ Troubleshooting becomes easy
- ✅ Can tell what's broken vs. what's working
- ✅ Ready for production deployment

---

### [P0-3] Config Unification - 6-8 HOURS ⭐⭐ HIGH

**Current State:** 7 scattered YAML files  
**Task:** Merge into single `configs/dexter_config.yml`

**Files to Consolidate:**
```
configs/
├─ dexter.yml                 ← Main config
├─ slots.yml                  ← Agent LLM slots
├─ denylist.master.yml        ← Global deny list
├─ denylist.profiles.yml      ← Tiered profiles
├─ policy_catalog.yml         ← Policy definitions
├─ agents.overlays.yml        ← Per-agent overrides
└─ denylist.yml               ← Duplicate (consolidate)

TARGET:
├─ dexter_config.yml          ← Single source of truth
├─ config_manager.py          ← Load/validate/watch
└─ migrate_configs.py         ← Migration script
```

**What Needs to Happen:**
1. Design unified schema
2. Merge all config values into single file
3. Update `config_manager.py` to load it
4. Add file watcher for live reload
5. Create migration script
6. Test all agent configurations
7. Update documentation

**When Done:**
- ✅ Single source of truth
- ✅ Easier to manage configuration
- ✅ Live reload without restart
- ✅ Cleaner repository structure

---

## 🟡 HIGH PRIORITY TASKS

### [P0-5] Cockpit Implementation (Remaining) - 3+ HOURS

**Current State:** UI partially integrated (docking tab works)  
**Still Need:**
- [ ] Actual window enumeration (replace hardcoded list)
- [ ] Real HwndHost docking (not just UI placeholder)
- [ ] OCR capture integration with backend
- [ ] Window focus/unfocus control
- [ ] Agent communication integration
- [ ] Live updates from backend

**Key Functions to Implement:**
```csharp
// Enumerate actual Windows
public async Task RefreshWindowsAsync()
{
    // Use Win32 APIs to find open windows
    // Filter by process name
    // Populate WindowOptions list
    // Update UI
}

// Actually dock a window
public async Task DockWindowAsync(WindowOption window)
{
    // Get window handle (hwnd)
    // Create HwndHost in UI
    // Reparent window to HwndHost
    // Hide from taskbar
}

// Capture OCR from docked window
public async Task CaptureOcrAsync()
{
    // Screenshot docked window area
    // Send to backend /ocr/extract
    // Display results in gallery
}
```

**When Done:**
- ✅ Real windows can be selected and docked
- ✅ OCR actually captures from docked windows
- ✅ Full mission control UI operational

---

### [P0-6] E2E Testing - 8-10 HOURS

**Current State:** No systematic testing  
**Need:**
- [ ] Fresh Windows Server 2022 VM setup script
- [ ] Smoke test suite (basic functionality)
- [ ] Full workflow tests (invoice entry, scraping, etc.)
- [ ] Error scenario tests (network down, model unavailable)
- [ ] Performance tests (response time, throughput)
- [ ] Security tests (policy enforcement)

**Test Scenarios:**
```python
# Smoke test
def test_basic_startup():
    # Install Dexter on fresh Windows
    # Verify all services start
    # Check health endpoint
    # Verify Cockpit launches

# Integration test
def test_full_workflow():
    # Open Notepad
    # Dexter clicks and types "Test Entry"
    # Captures OCR
    # Verifies text recognized

# Error scenario
def test_redis_unavailable():
    # Stop Redis
    # Verify health check catches it
    # Check error message is actionable
    # Show user how to fix
```

**When Done:**
- ✅ Confident the system works end-to-end
- ✅ Ready for customer trials
- ✅ Can verify bugs are fixed

---

## 📊 COMPLETE TODO BREAKDOWN

### Phase 1 Detailed Breakdown

```
P0-1: Windows Tools (4-6h)
├─ Real pyautogui.click() implementation
├─ Real pyautogui.typewrite() implementation
├─ Real pyautogui.hotkey() implementation
├─ Real pytesseract OCR integration
├─ Error handling & logging
├─ Test on Windows Server 2022
└─ Documentation

P0-2: Health Checks (3-4h)
├─ Ollama connectivity check
├─ Tesseract validation
├─ Redis connectivity
├─ Brain.db accessibility
├─ Triple bus initialization
├─ Disk space check
├─ Actionable error messages
└─ Timeout protections

P0-3: Config Unification (6-8h)
├─ Design unified schema
├─ Merge 7 YAML files
├─ Update config_manager.py
├─ Add file watcher
├─ Create migration script
├─ Test all configurations
└─ Documentation

P0-5: Cockpit Impl (3+ hours remaining)
├─ Real window enumeration
├─ HwndHost docking
├─ OCR capture integration
├─ Window control (focus/unfocus)
├─ Backend communication
└─ Live updates

P0-6: E2E Testing (8-10h)
├─ Fresh Windows VM setup
├─ Smoke test suite
├─ Full workflow tests
├─ Error scenario tests
├─ Performance tests
└─ Security tests

TOTAL: 29-32 hours
```

---

## 🚀 RECOMMENDED SEQUENCE

### Session 1: Windows Tools (4-6 hours) 🔴 DO THIS FIRST
```
1. Open dexter_autonomy/tools/windows/automation.py
2. Replace click/type/hotkey stubs with real pyautogui
3. Add pytesseract OCR integration
4. Test with Notepad
5. Test with Calculator
6. Test with Chrome
7. Verify all functions work
```

### Session 2: Health Checks (3-4 hours) 🟡 DO SECOND
```
1. Open dexter_autonomy/ui_bridge/api.py
2. Enhance /healthz endpoint
3. Add Ollama check
4. Add Tesseract check
5. Add Redis check
6. Add Brain.db check
7. Add disk space check
8. Test each component independently
```

### Session 3: Config Unification (6-8 hours) 🟡 DO THIRD
```
1. Design unified schema
2. Create dexter_config.yml
3. Merge all 7 YAML files
4. Update config_manager.py
5. Create migration script
6. Update all references
7. Test with all agents
8. Verify file watcher works
```

### Session 4: Cockpit Implementation (3+ hours) 🟡 DO FOURTH
```
1. Implement window enumeration
2. Implement HwndHost docking
3. Connect OCR capture
4. Test with real windows
5. Verify agent communication
6. Add live updates
```

### Session 5: E2E Testing (8-10 hours) 🟡 DO LAST
```
1. Create fresh Windows VM
2. Run installer (test P0-4)
3. Run smoke tests (test P0-1, P0-2)
4. Test full workflows
5. Test error scenarios
6. Performance testing
7. Security testing
```

---

## 📈 EFFORT ESTIMATES

| Task | Low | High | Best Guess |
|------|-----|------|-----------|
| P0-1 Windows Tools | 3h | 8h | 4-6h |
| P0-2 Health Checks | 2h | 5h | 3-4h |
| P0-3 Config Unify | 5h | 10h | 6-8h |
| P0-5 Cockpit Impl | 2h | 6h | 3-4h |
| P0-6 E2E Testing | 6h | 12h | 8-10h |
| **TOTAL** | **18h** | **41h** | **29-32h** |

**With Parallel Execution:** 5-6 working days  
**Sequential:** 7-8 working days

---

## 💰 BUSINESS IMPACT

### Timeline to Revenue
```
Week 1-2: Phase 1 Complete ✅ (29-32 hours)
├─ MVP running
├─ 3 customer trials ready
└─ Initial feedback collected

Week 3-4: Phase 2 Start 🚀 (56-77 hours)
├─ Brain learning
├─ Recipe marketplace
├─ Authentication
└─ First customers paying ($1.5K MRR)

Week 5+: Scale Phase 📈 (104-146 hours)
├─ Enterprise features
├─ Multi-tenancy
├─ $40K MRR target
└─ Production hardening
```

---

## ✅ QUICK CHECKLIST

- [ ] **Understand Windows Tools (P0-1)** - Read above section
- [ ] **Understand Health Checks (P0-2)** - Read above section
- [ ] **Understand Config Unify (P0-3)** - Read above section
- [ ] **Understand Cockpit Impl (P0-5)** - Read above section
- [ ] **Understand E2E Testing (P0-6)** - Read above section
- [ ] **Ready to start P0-1** - Windows Tools
- [ ] **Have Python environment ready** - venv activated
- [ ] **Have Tesseract installed** - tesseract.exe on PATH
- [ ] **Have pyautogui & pytesseract** - pip install

---

## 🎯 YOUR NEXT IMMEDIATE STEP

**Pick ONE:**

### Option A: Start Coding Right Now 🚀
```
1. Open: dexter_autonomy/tools/windows/automation.py
2. Replace the 3 stubs with real pyautogui code
3. Test with Notepad
4. You'll unblock everything else
```

### Option B: Understand What's Left 📚
```
1. Read TODO-MASTER.md (full details)
2. Review the breakdown above
3. Ask questions
4. Plan your approach
```

### Option C: Plan the Entire Phase 🎯
```
1. Review all 5 components above
2. Create GitHub issues for each
3. Estimate team capacity
4. Schedule work
5. Start execution
```

---

**Status:** ✅ Everything is clear and documented  
**Blocker:** None - ready to start immediately  
**Confidence:** HIGH (9/10)  

**Next:** P0-1 Windows Tools (4-6 hours)

---

_Last Updated: October 16, 2025_  
_Phase 1 MVP: 29-32 hours remaining_  
_Completion Target: 5-6 working days_
