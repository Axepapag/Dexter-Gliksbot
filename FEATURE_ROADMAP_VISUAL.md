# 🗺️ Feature Implementation Roadmap - Visual Timeline

## 📊 6-Week Implementation Schedule

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                      DEXTER COCKPIT FEATURE ROADMAP                            │
│                     4-6 Weeks | 3 Major Features                               │
└────────────────────────────────────────────────────────────────────────────────┘

Week 1-2: DOCKED WINDOWS MANAGER
┌──────────────────────────────────────────────────────────────────────────────┐
│ Week 1: Core Infrastructure                                                  │
│ ├─ Day 1-2:  WindowsInterop.cs (P/Invoke Win32 APIs)         ████████        │
│ ├─ Day 3-5:  DockedWindowHost.cs (HwndHost control)          ████████████    │
│ └─ Day 6-7:  Unit tests & validation                         ████            │
│                                                                               │
│ Week 2: ViewModel & UI Integration                                           │
│ ├─ Day 1-3:  DockedWindowsViewModel (scan/dock logic)        ████████████    │
│ ├─ Day 4-5:  DockedWindowsView.xaml (UI)                     ████████        │
│ └─ Day 6-7:  Integration testing (Unity, QB, Browsers)       ████            │
│                                                                               │
│ Deliverables: ✅ Functional window docking, ✅ Auto-detection               │
└──────────────────────────────────────────────────────────────────────────────┘

Week 3-4: AGENT CHAT TABS
┌──────────────────────────────────────────────────────────────────────────────┐
│ Week 3: Per-Agent Chat Implementation                                        │
│ ├─ Day 1-2:  AgentChatViewModel (isolated chats)             ████████        │
│ ├─ Day 3-4:  AgentChatTabManager (dynamic tabs)              ████████        │
│ ├─ Day 5-6:  AgentRosterView integration (chat buttons)      ████████        │
│ └─ Day 7:    Multi-agent chat testing                        ████            │
│                                                                               │
│ Week 4 (first half): Polish & Edge Cases                                     │
│ ├─ Day 1-2:  Chat history persistence                        ████████        │
│ └─ Day 3:    TTS per-tab, tab icons                          ████            │
│                                                                               │
│ Deliverables: ✅ Per-agent tabs, ✅ Isolated history, ✅ TTS per agent      │
└──────────────────────────────────────────────────────────────────────────────┘

Week 4-5: MULTI-MONITOR SUPPORT
┌──────────────────────────────────────────────────────────────────────────────┐
│ Week 4 (second half) - Week 5 (first half)                                   │
│ ├─ Day 4-5:  LayoutManager.cs (XML serialization)            ████████        │
│ ├─ Day 6-7:  MonitorManager.cs (display detection)           ████████        │
│ ├─ Day 1-2:  MainWindow integration (save/restore)           ████████        │
│ └─ Day 3:    Multi-monitor edge case testing                 ████            │
│                                                                               │
│ Deliverables: ✅ Layout persistence, ✅ Monitor detection, ✅ Restoration    │
└──────────────────────────────────────────────────────────────────────────────┘

Week 5-6: POLISH & DOCUMENTATION
┌──────────────────────────────────────────────────────────────────────────────┐
│ Week 5 (second half) - Week 6                                                │
│ ├─ Day 4-5:  UI polish (icons, tooltips, colors)             ████████        │
│ ├─ Day 6-7:  Performance optimization (handle validation)    ████████        │
│ ├─ Day 1-2:  Comprehensive integration testing               ████████        │
│ ├─ Day 3-4:  Bug fixes & refinements                         ████████        │
│ └─ Day 5-7:  Documentation updates (README, copilot-inst)    ████████████    │
│                                                                               │
│ Deliverables: ✅ Production-ready, ✅ Full docs, ✅ Zero critical bugs       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Feature Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FEATURE DEPENDENCIES                            │
└─────────────────────────────────────────────────────────────────────┘

                        [Multi-Monitor Support]
                              │ Required by
                              ▼
            ┌──────────────────────────────────────────┐
            │   [Docked Windows]  ← ─ ┐                │
            └─────────┬────────────────┼────────────────┘
                      │ Enhances       │ Independent
                      ▼                │
            [Agent Chat Tabs] ←────────┘

Legend:
  → Required by (blocking dependency)
  ⇢ Enhances (optional integration)

Recommended Order:
  1. Multi-Monitor (foundational)
  2. Agent Chat Tabs (parallel with 3)
  3. Docked Windows (most complex)
```

---

## 📈 Risk Matrix

```
Impact
  ^
5 │                           ┌──────────────────┐
  │                           │ Window Handle    │ ← HIGH RISK
4 │                           │ Lifecycle Mgmt   │   Mitigation: Validation + Finalizers
  │                           └──────────────────┘
3 │          ┌──────────────┐    ┌──────────────┐
  │          │ Layout       │    │ DPI Scaling  │ ← MEDIUM RISK
2 │          │ Corruption   │    │ Conflicts    │   Mitigation: Backups + SetDpiAwareness
  │          └──────────────┘    └──────────────┘
1 │  ┌──────────────┐  ┌──────────────┐
  │  │ Tab          │  │ TTS Audio    │ ← LOW RISK
  │  │ Confusion    │  │ Overlap      │   Mitigation: Color-coding + Queue
  └──┴──────────────┴──┴──────────────┴───────────────────────────────>
     1              2              3              4              5    Likelihood

Risk Scores (Impact × Likelihood):
  - Window Handle Lifecycle:  4 × 4 = 16 (HIGH - top priority mitigation)
  - Layout Corruption:        3 × 3 = 9  (MEDIUM)
  - DPI Scaling:              3 × 3 = 9  (MEDIUM)
  - Tab Confusion:            2 × 2 = 4  (LOW)
  - TTS Overlap:              1 × 2 = 2  (LOW)
```

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                      DEXTER COCKPIT ARCHITECTURE                        │
│                       (After Feature Implementation)                    │
└────────────────────────────────────────────────────────────────────────┘

                             MainWindow.xaml
                      ┌────────────────────────────┐
                      │  AvalonDock DockingManager │
                      └──────────┬─────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼────────┐    ┌──────────▼─────────┐   ┌────────▼─────────┐
│ Agent Roster   │    │  LayoutDocumentPane│   │ Docked Windows   │
│                │    │                    │   │ Manager          │
│ [Agent Cards]  │    │ ┌────────────────┐ │   │                  │
│                │    │ │ Dexter Chat    │ │   │ ┌──────────────┐ │
│ 💬 Chat Button │───▶│ └────────────────┘ │   │ │ Unity Editor │ │
│ per agent      │    │ ┌────────────────┐ │   │ │ (HWND Host)  │ │
└────────────────┘    │ │ AUM Chat (NEW) │ │   │ └──────────────┘ │
                      │ └────────────────┘ │   │ ┌──────────────┐ │
                      │ ┌────────────────┐ │   │ │ ChatGPT Win  │ │
                      │ │ BSM Chat (NEW) │ │   │ │ (HWND Host)  │ │
                      │ └────────────────┘ │   │ └──────────────┘ │
                      │ ┌────────────────┐ │   └──────────────────┘
                      │ │ Performance    │ │
                      │ └────────────────┘ │
                      └────────────────────┘
                                 │
                      ┌──────────▼─────────┐
                      │  LayoutManager     │ ← Multi-Monitor
                      │  (Save/Restore)    │   Support
                      └────────────────────┘

Key Integrations:
  1. AgentRosterViewModel → AgentChatTabManager (opens per-agent tabs)
  2. DockedWindowsViewModel → DockedWindowHost (embeds HWND)
  3. MainWindow → LayoutManager (save/restore on startup/shutdown)
  4. MonitorManager → SystemEvents.DisplaySettingsChanged (detect changes)
```

---

## 💡 Code Complexity Breakdown

```
Component                  | Files | Lines | Complexity | Risk
─────────────────────────────────────────────────────────────────
Docked Windows Manager     |   5   | 1,500 |   High     | 🔴 High
  ├─ WindowsInterop.cs     |   1   |   300 |   High     | Win32 P/Invoke
  ├─ DockedWindowHost.cs   |   1   |   400 |   High     | HwndHost lifecycle
  ├─ DockedWindowsVM.cs    |   1   |   450 |   Medium   | State management
  ├─ DockedWindow.cs       |   1   |    50 |   Low      | Simple model
  └─ DockedWindowsView.xaml|   1   |   300 |   Low      | XAML markup
─────────────────────────────────────────────────────────────────
Agent Chat Tabs            |   3   | 1,200 |   Medium   | 🟡 Medium
  ├─ AgentChatViewModel.cs |   1   |   500 |   Medium   | Per-agent state
  ├─ AgentChatTabManager.cs|   1   |   400 |   Medium   | Tab lifecycle
  └─ Integration changes   |   1   |   300 |   Low      | Hook into roster
─────────────────────────────────────────────────────────────────
Multi-Monitor Support      |   3   |   800 |   Medium   | 🟡 Medium
  ├─ LayoutManager.cs      |   1   |   450 |   Medium   | XML serialization
  ├─ MonitorManager.cs     |   1   |   250 |   Low      | Screen enumeration
  └─ MainWindow changes    |   1   |   100 |   Low      | Event wiring
─────────────────────────────────────────────────────────────────
Testing & Integration      |   4   |   600 |   Medium   | 🟢 Low
  ├─ Unit tests            |   2   |   300 |   Low      | Win32 mocks
  ├─ Integration tests     |   1   |   200 |   Medium   | Full stack
  └─ Manual test plans     |   1   |   100 |   Low      | Checklist
─────────────────────────────────────────────────────────────────
TOTAL                      |  15   | 4,100 |   Medium   | 🟡 Medium
```

---

## 🧪 Testing Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                      TESTING PYRAMID                             │
└─────────────────────────────────────────────────────────────────┘

                        ╱╲
                       ╱  ╲
                      ╱ E2E╲           5% (Manual multi-monitor)
                     ╱──────╲
                    ╱        ╲
                   ╱Integration╲      20% (Full stack, mock backend)
                  ╱────────────╲
                 ╱              ╲
                ╱  Unit Tests    ╲    75% (ViewModels, Win32 interop)
               ╱──────────────────╲

Test Counts:
  - Unit Tests:        ~80 tests  (Win32 APIs, ViewModels, Tab lifecycle)
  - Integration Tests: ~20 tests  (Docking flow, Layout persistence)
  - E2E Tests:         ~10 tests  (Multi-monitor, External apps)

Coverage Targets:
  - ViewModels:        85%+
  - Services:          80%+
  - Win32 Interop:     90%+ (critical for stability)
  - Views (XAML):      Manual testing only

Key Test Scenarios:
  1. Dock Unity → Resize → Undock → Verify no leaks
  2. Open 10 agent chats → Close all → Memory check
  3. Save layout → Change resolution → Restore → Fallback to default
  4. Multi-monitor: Move window → Save → Restart → Verify position
  5. 24hr soak test with 5 docked windows + 10 agent tabs
```

---

## 📦 Deliverables Checklist

### Feature 1: Docked Windows Manager ✅
- [ ] WindowsInterop.cs with P/Invoke wrappers
- [ ] DockedWindowHost.cs (HwndHost implementation)
- [ ] DockedWindowsViewModel.cs (scan/dock/undock)
- [ ] DockedWindow.cs model with ApplicationType enum
- [ ] DockedWindowsView.xaml with scan UI
- [ ] Unit tests (80%+ coverage on Win32 calls)
- [ ] Integration test: Dock Unity, QB, Browser
- [ ] Documentation: Win32 API risks, handle validation
- [ ] Performance test: 5+ docked windows for 1 hour

### Feature 2: Agent Chat Tabs ✅
- [ ] AgentChatViewModel.cs (per-agent state)
- [ ] AgentChatTabManager.cs (dynamic tab lifecycle)
- [ ] Integration with AgentRosterView (chat buttons)
- [ ] Chat history persistence to brain/SQLite
- [ ] Per-tab TTS with mute controls
- [ ] Unit tests for tab creation/closure
- [ ] Integration test: 10 simultaneous chats
- [ ] Documentation: MVVM pattern, tab lifecycle
- [ ] Memory test: Open/close 100 tabs, check leaks

### Feature 3: Multi-Monitor Support ✅
- [ ] LayoutManager.cs with XML serialization
- [ ] MonitorManager.cs with display detection
- [ ] MainWindow integration (Loaded/Closing events)
- [ ] Monitor configuration JSON persistence
- [ ] ContentId assignment to all dockable elements
- [ ] "Reset Layout" menu item
- [ ] Unit tests for layout save/restore
- [ ] Multi-monitor test: 1→2→1 monitor transitions
- [ ] Documentation: Layout XML structure, monitor detection

### Documentation & Polish ✅
- [ ] Update README-COCKPIT.md with new features
- [ ] Update .github/copilot-instructions.md
- [ ] Create DOCKED_WINDOWS_GUIDE.md
- [ ] Create AGENT_CHAT_TABS_GUIDE.md
- [ ] Add tooltips to all new UI elements
- [ ] Add icons for application types (Unity, QB, etc.)
- [ ] Performance optimization pass
- [ ] Security review (Win32 handle permissions)

---

## 🎓 Success Metrics

```
Metric                          | Target  | How to Measure
────────────────────────────────────────────────────────────
Docked Window Success Rate      | 95%+    | Successful docks / Total attempts
Average Dock Time               | <500ms  | Time from click to embedded window
Handle Leak Rate                | 0%      | Finalizer calls / Total undocks
Agent Tab Open Time             | <100ms  | Tab creation to visible
Layout Restore Success          | 98%+    | Successful restores / Total attempts
Multi-Monitor Transition Time   | <2s     | Layout adjust after display change
User-Reported Crashes           | 0       | Zero crashes in 24hr soak test
Memory Growth (24hr)            | <10%    | Heap size after 24hr vs. baseline
CPU Overhead (docked windows)   | <5%     | Additional CPU with 5 docked windows
User Satisfaction (Beta)        | 4.5/5   | User feedback after 1 week testing
```

---

## 🚀 Next Steps After Approval

1. **Create feature branches:**
   - `feature/docked-windows-manager`
   - `feature/agent-chat-tabs`
   - `feature/multi-monitor-support`

2. **Setup project tracking:**
   - GitHub Projects board with timeline
   - Daily standup (async via GitHub Discussions)
   - Weekly progress reports to stakeholders

3. **Environment setup:**
   - Multi-monitor test rig (2-3 displays)
   - Unity, QuickBooks, Browser instances
   - Performance profiling tools (dotTrace, PerfView)

4. **Sprint kickoff (Week 1, Day 1):**
   - Architecture walkthrough
   - Code review guidelines
   - Testing strategy alignment

---

**Visual Roadmap Version:** 1.0  
**Created:** October 16, 2025  
**Companion to:** TECHNICAL_PLAN_DOCKED_WINDOWS_AGENT_TABS.md
