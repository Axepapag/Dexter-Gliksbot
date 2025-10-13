# Executive Summary

Dexter is a Windows‑first autonomy stack: FastAPI API + agent orchestration (AUM/BSM) + Windows UI automation (pyautogui/pywinauto) + OCR (Tesseract) + a lightweight SQLite “brain,” with an optional WPF cockpit for supervision. It’s built to observe a Windows UI (via capture/OCR), interpret intent (LLM via Ollama), then safely execute clicks/keystrokes under a centralized deny‑policy.

**Value verdict:** strong bones (6.5/10 potential) but only 3/10 productization today. Package it with a simple installer, bulletproof recipes, and robust health checks, and it’s sellable to SMB ops teams and MSPs.

---

## How it Works (Architecture)

**Core modules**

- **Event bus** (`dexter_autonomy.core.event_bus`): async pub/sub topics `INTENT`, `EFFECT`, `ERROR`, `TRACE`, `COUNCIL`, `SYSTEM`.
- **Policy overlay (guardrails)** (`core.policy_overlay`, `configs/denylist.profiles.yml`): composited profile+overlay controls: process/command patterns, file write globs, window classes/titles, hotkeys, input regex & injection heuristics.
- **Memory (“brain”)** (`brain.memory`, `brain.enhanced_memory`, `brain.stm_store`): SQLite (WAL), FTS search, simple knowledge‑graph edges. Persists OCR, observations, tool outputs, logs; supports recall for RAG‑ish context.
- **Agents**
  - **AUM (Action Understanding Model)** (`agents.aum`): prompts LLM to return JSON actions (`click`, `type`, `hotkey`, `ocr`…), falls back to deterministic parser on failure.
  - **BSM (Brain/State Model)** (`agents.bsm`): summarizes observations into structured JSON; tags/entities/relations; writes to memory.
  - **ActionExecutor** (`agents.action_executor`): executes actions via Windows tools after policy checks; hotkeys normalized.
  - **ChatDockAgent** (`agents.chatdock`): chat‑to‑bus bridge, can trigger OCR on a window handle and push to BSM.
  - **DexterOrchestrator** (`agents/dexter_orchestrator.py`): wires bus+policy+memory+executor+AUM/BSM; talks to LLM through **OllamaAdapter**.
- **Model adapter** (`agents/adapters/ollama_adapter.py`): thin HTTP client for **Ollama** (`/api/chat`, `/api/embeddings`), with optional headers and timeouts.
- **Windows tools** (`tools/windows`):
  - `automation.py` (pyautogui): move/click, type, hotkeys.
  - `ocr.py` (pytesseract): ensures `eng.traineddata`, can download if missing; cleans text.
  - `capture.py` (ImageGrab) for screen capture.
- **API bridge** (`ui_bridge/api.py`): FastAPI app; endpoints include `/health`, `/healthz`, `/dexter/chat`, `/ocr/extract`, `/intent`, `/memory/*`, `/outbox/*`, `/policy/*`, `/ws`.
- **Workers** (`workers/tasks.py`): optional Celery tasks (email/outbox, schedules).
- **Cockpit** (`cockpit/DexterCockpit`): WPF/XAML supervisory UI.
- **Configs** (`configs/slots.yml`, `configs/denylist.profiles.yml`): model/temperature/prompt per slot; policy catalog & presets with modes `low/medium/high/paranoid`.

**Start & run**

- `start.py` launches uvicorn and (optionally) Celery/beat; prints service URLs.
- `requirements.txt` contains Windows‑specific libs (pyautogui, pywinauto, pytesseract, Pillow). Python ≥3.10.

---

## Capabilities (Current)

- **UI automation** on Windows: click/type/hotkey with policy checks and hotkey normalization.
- **OCR perception** of selected window or screen; cleaned text output.
- **Local LLM loop** via **Ollama** (default host `http://127.0.0.1:11434`); graceful fallback parsing if LLM fails (AUM).
- **Memory & recall** with FTS, plus simple edges.
- **HTTP & WebSocket** surface for integration.
- **Policy presets** with composable overlay and sane defaults.

**Notable strengths**

- Windows‑first focus (a real niche), local‑model support, deny‑first guardrails, simple memory APIs.

**Limitations**

- Windows dependency chain (pyautogui/pytesseract) is brittle in fresh environments.
- Health checks are shallow; do not verify Ollama/Tesseract/permissions.
- No installer/wizard; first‑run friction is high.

---

## Practical Uses & Revenue Angles

1. **SMB RPA‑lite** (invoice entry, claims portals, carrier/bank portals). Competes with UiPath/Power Automate on price/speed. *Price*: \$200–\$1.5k/site/mo.
2. **MSP/IT Copilot** (reset accounts, install/uninstall via GUI, collect diagnostics, ticket sync). *Price*: \$30–\$99/tech/mo.
3. **Claims/compliance auditing** (OCR evidence from web portals into case notes). *Price*: \$2–\$10/case or \$500–\$2k/mo/site.
4. **Sales ops enrichment** (scrape legacy portals → update CRM fields nightly). *Price*: \$500–\$2k/mo/team.
5. **Recipe marketplace** (YAML automation packs for Windows apps like QuickBooks, Sage, Epicor). *Monetize*: per‑recipe sales + revenue share.

**Go‑to‑market in 6–8 weeks**

- Ship 3–5 bulletproof “recipes” for one vertical; bundle with a one‑click installer and cockpit.
- Measure & show **minutes saved / keystrokes avoided**; sell outcomes, not features.

---

## Why It’s “Not Working Right” (Root Causes Observed)

**Symptoms you’ll hit on a fresh machine**

- Import‑time failures for `pyautogui`, `pytesseract`, `pywinauto` if not installed or on non‑Windows.
- OCR path issues: `tesseract.exe` not on PATH; missing `TESSDATA_PREFIX`; enterprise boxes may block model file download.
- LLM calls fail if **Ollama** isn’t running or model not pulled; no current readiness gate.
- “Full mode” features silently degrade when Celery/Redis aren’t present.
- Cockpit requires NuGet restore and proper target framework; `.vs` artifacts in repo are misleading.
- Health endpoints exist but only report mode/slot and whether the orchestrator object exists—no deep checks.

**Concrete code pitfalls**

- `tools/windows/automation.py` imports `pyautogui` at module import time (hard failure if missing). Should be lazy‑loaded.
- `ocr.py` attempts model download; missing `tesseract.exe` still crashes.
- Orchestrator and agents assume Ollama reachable; exceptions bubble to callers, relying on fallback only in AUM/BSM.

---

## Fixes (High‑Leverage, Minimal Diff)

### 1) Harden imports & feature flags

Lazy‑import Windows‑only libs and fail fast with friendly messages.

```python
# tools/windows/automation.py
try:
    import pyautogui  # type: ignore
except Exception as e:
    pyautogui = None

def _require_pyautogui():
    if pyautogui is None:
        raise RuntimeError("Windows automation not available: install pyautogui and run on Windows desktop session.")

def click(x:int,y:int):
    _require_pyautogui(); pyautogui.moveTo(x,y,duration=0.05); pyautogui.click()

def type_text(text:str):
    _require_pyautogui(); pyautogui.write(text, interval=0.01)

def hotkey(*keys:str):
    _require_pyautogui(); pyautogui.hotkey(*keys)
```

Add a startup banner that explicitly prints what’s enabled/disabled (core vs full mode).

### 2) Real health checks (Ollama + Tesseract + Windows session)

Augment `/healthz` to verify:

- **Ollama** reachable and model loaded.
- **Tesseract** installed and `eng.traineddata` present.
- **Windows session**: sanity check via `ImageGrab.grab()` or `pyautogui` presence.

```python
# ui_bridge/api.py (add helpers)
import shutil, requests

def _check_ollama(host: str, model: str) -> dict:
    try:
        r = requests.get(f"{host}/api/tags", timeout=2)
        r.raise_for_status()
        models = [m.get("name") for m in r.json().get("models", [])]
        return {"ok": model in models, "host": host, "models": models}
    except Exception as e:
        return {"ok": False, "error": str(e), "host": host}

from pytesseract import pytesseract as _pt

def _check_tesseract() -> dict:
    exe = shutil.which("tesseract") or _pt.tesseract_cmd
    return {"ok": bool(exe), "path": exe}

# inside _health_payload()
return {
  "ok": True,
  "mode": ACTIVE_MODE,
  "slot": ACTIVE_SLOT,
  "slot_model": CURRENT_SLOT.get("model"),
  "dexter_status": "active" if DEXTER_ORCHESTRATOR else "inactive",
  "ollama": _check_ollama(CURRENT_SLOT.get("endpoint","http://127.0.0.1:11434"), CURRENT_SLOT.get("model","")),
  "tesseract": _check_tesseract(),
}
```

### 3) First‑run wizard & installer

Provide `.env.example` and a PowerShell installer to smooth Tesseract/Ollama setup and Python venv creation.

```powershell
# Install-Dexter.ps1
param([string]$Model='qwen2.5:3b-instruct',[int]$Port=8765)
$ErrorActionPreference='Stop'

# 1) Tools
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
  Write-Host 'Install Tesseract and ensure it is on PATH.'; exit 1
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host 'Install Ollama from https://ollama.com and restart shell.'; exit 1
}

# 2) Python venv
python -m venv .venv; . .venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3) Pull model & start API
ollama pull $Model
python start.py --port $Port
```

### 4) Safer executor (dry‑run mode)

Add `?dry_run=true` or header to `/intent` and `/dexter/chat` that returns intended actions without executing. Great for demos and lowers risk in trials.

### 5) CI on `windows-latest`

GitHub Actions: install Tesseract, run `pytest -q`, then `uvicorn` smoke test that hits `/healthz` and `/ocr/extract` with a static image.

### 6) Cockpit build hygiene

Add `README-cockpit.md` with target framework, `dotnet restore`, and remove `.vs/` from repo.

---

## Minimal Repro & Runbook (Windows 11 Pro)

1. **Install** Python 3.11 x64, Tesseract, and Ollama; verify `tesseract --version` and `ollama serve`.
2. `pip install -r requirements.txt` (inside venv).
3. `ollama pull qwen2.5:3b-instruct` (or change in `configs/slots.yml`).
4. `python start.py --port 8765` (port must match tests).
5. Verify `GET /healthz` for `ollama.ok==true` and `tesseract.ok==true`.
6. Hit `POST /dexter/chat` with `{ "message": "type hello" }` in **dry‑run** first.

**Common failures & fixes**

- *`ModuleNotFoundError: pyautogui`*: ensure venv active, `pip install -r requirements.txt`; on headless/VMs, ensure interactive desktop session.
- *OCR empty or crashes*: install Tesseract; set `TESSDATA_PREFIX` (or put `eng.traineddata` in default tessdata dir); block auto‑download in locked networks and place the file manually.
- *LLM errors / timeouts*: ensure `ollama serve` is running; pull the configured model; verify `configs/slots.yml` host/model.
- *Celery/Redis complaints*: run in core mode (no workers) or install Redis and enable workers explicitly.

---

## Monetization Plan (Focused, 0→\$5–10k MRR)

**Package** a “Windows Autonomy Agent” bundle:

- **Starter** \$199/mo: API + 2 curated recipes + dry‑run + email support.
- **Pro** \$699/mo: + scheduling (workers), cockpit UI, priority support, custom recipe tweaks.
- **Enterprise** custom: on‑prem, SSO, audit logging.

**Sales motions**

- Target 50 bookkeeping firms + 50 MSPs with a 3‑minute demo of OCR→intent→dry‑run actions, then live execution with guardrails.
- Ship a tiny telemetry panel showing time saved and actions executed; that’s your renewal story.

---

## Next Steps (I can generate diffs/PR‑ready patches)

- Patch `automation.py` (lazy import), add deep `/healthz`, commit `.env.example`, and add the PowerShell installer.
- Optionally introduce a YAML **recipe** format with policy overlays per recipe for safer distribution.

---

## Quick Reference (Endpoints Discovered)

- `GET /health`, `GET /healthz`
- `POST /dexter/chat`
- `POST /ocr/extract`
- `POST /intent`
- `POST /memory/add`, `POST /memory/search`, `GET /memory/task/{task_root}`, `GET /memory/stats`, `POST /memory/snapshot`
- `GET /outbox/pending`, `POST /outbox/add`, `POST /outbox/email`, `POST /outbox/process`, `GET /outbox/stats`, `POST /outbox/cleanup`
- `GET /policy/presets`, `POST /policy/profile/update`
- `GET /slots`
- `WS /ws`

---

### TL;DR

Ship the installer + deep health checks + dry‑run mode + 3 solid Windows recipes. That turns today’s scaffolding into a product you can charge for within one sales cycle.



---

# Cockpit UI Redesign — Spec & Implementation Plan

## Goals

- Natural, human chat everywhere; banish “Unknown NL command”.
- Strict separation of **Chat**, **Logs**, and **OCR**.
- Full docking: every pane can pop out, float, resize, and re-dock.
- Real‑time, complete log streaming with export (JSONL/NDJSON + CSV).
- Two‑way sync between **Agent Slots UI** and `` (source of truth), with live add/remove/edit.
- Provider‑agnostic agent slots (Ollama, OpenAI, Azure OpenAI, Anthropic, Groq, Local LM Studio, custom HTTP…). Keys from env vars.
- Clear, honest error reporting (HTTP status + message), never placeholder NL command errors.
- OCR pane independent of chat; dynamic capture region locked to cockpit docking area with automatic resize.

## UX Layout (WPF / Docking)

- **Left Sidebar**: Agent Slots list (sortable). Buttons: **Add Agent**, **Duplicate**, **Delete**, **Export Logs**.
- **Main Docking Area** (AvalonDock recommended):
  - **Chat Pane** (one per agent):
    - Header: agent name + status chip (Ready/Streaming/Error) + provider tag.
    - Body: conversation messages (user/assistant). System/meta messages hidden by default; toggle “Show system messages”.
    - Footer: input box + Send, plus mic button (optional future).
  - **Logs Pane** (global or per agent):
    - Real‑time stream with filters: level, topic, agent, correlation id.
    - Controls: pause/resume stream, clear view, **Export**.
  - **OCR Pane** (global):
    - Live preview of capture region (toggled). Button: **Capture now**. Checkbox: “Auto‑capture on interval”. Result text and confidence; **Send to agent** button (does not post into chat unless explicitly chosen).

> All panes are **Dockable**, **Floatable**, **Closable**; reopening from **View** menu.

## Copy & Messaging Rules

- Replace all “NL command” strings with natural replies. Default assistant welcome: *“Hi! I’m ready. Ask me anything or click OCR if you need me to read the screen.”*
- On unknown intents or backend parse errors, show: *“I couldn’t parse that into an action. I kept your message in the log. Details →”* with a link that opens the relevant log filter.

## Error Handling (No more placeholders)

- **Transport**: When POST/WS fails, surface **HTTP status + reason** inline in the Chat Pane (banner), and log the full error.
- **AUM/Model**: If provider unreachable, show *“Model unreachable at {endpoint}. Check provider settings or network.”* and keep the message unsent; offer retry.
- **Policy block**: Show *“Action blocked by policy {rule\_id}. See Logs → Policy.”*

## Logs Spec

- Source all log events from backend WebSocket topic `TRACE` and `ERROR` plus app‑level events.
- **Schema (JSONL)**
  ```json
  {"ts":"2025-10-13T12:34:56.789Z","level":"INFO","topic":"AUM","agent_id":"salesbot","corr":"8e1b","msg":"Parsed actions","data":{"count":3}}
  ```
- **Export**: Save to `~/Dexter/logs/{YYYY-MM-DD}/session-{GUID}.jsonl` with optional CSV projection.
- **Filters**: level, topic, agent\_id, corr id, text search.
- **Performance**: ring buffer in UI (e.g., 10k rows) with virtualized list; export uses full retained buffer from backend.

## Two‑Way YAML Sync (Agent Slots ↔ `configs/slots.yml`)

**Source of truth**: the YAML file. UI watches file changes and applies updates; UI edits write back via backend.

- **File**: `configs/slots.yml`
- **Slot model**
  ```yaml
  slots:
    - id: salesbot
      name: Sales Bot
      provider: openai
      endpoint: https://api.openai.com/v1
      model: gpt-4o-mini
      api_key_env: OPENAI_API_KEY
      temperature: 0.3
      prompt: "You are…"
      params:
        max_tokens: 512
  ```
- **Backend contracts**
  - `GET /slots` → returns parsed YAML + hash.
  - `POST /slots` → upsert slot (validate, write YAML, return new hash).
  - `DELETE /slots/{id}` → remove slot (or set `archived: true`).
  - **FS watcher** in backend (watchdog) broadcasts `SYSTEM:SLOTS_UPDATED` over WS with the new hash; UI then calls `GET /slots` to refresh.
- **UI behavior**
  - On **Add Agent**: create slot with defaults; POST; open new Chat Pane.
  - On **Edit**: inline form (name, provider, endpoint, key env var, model, temperature, prompt, params). Save triggers POST.
  - On **External YAML edit**: receive WS `SLOTS_UPDATED` → soft refresh list and any open panes reflect changes.

## Provider Abstraction (Pluggable)

Introduce a provider adapter interface shared by backend agents and UI forms.

- **Backend Python**
  ```python
  class LLMProvider(Protocol):
      name: str
      def chat(self, messages: list[dict], **kwargs) -> dict: ...
      def health(self) -> dict: ...

  # Built-ins
  from .providers import ollama, openai_p, azure_openai, anthropic_p, groq_p, lmstudio_p, generic_http
  PROVIDERS = {p.name: p for p in [ollama, openai_p, azure_openai, anthropic_p, groq_p, lmstudio_p, generic_http]}
  ```
- **UI**
  - Provider dropdown sourced from `/providers`.
  - Fields shown/hidden per provider (e.g., Azure needs deployment name).
  - Keys read from env var name supplied in slot.

## Messaging Fixes (Why chat returns “Unknown NL command”)

- **Root cause**: frontend sends `NL_COMMAND` to backend action endpoint; backend expects `/dexter/chat` with `{messages:[...]}` OR provider not reachable → fallback placeholder.
- **Fix**:
  1. Frontend always POSTs to `/dexter/chat` for free‑text; never labels user input as a command.
  2. Backend returns assistant text even on empty tool plan; if the model fails, reply: *“I couldn’t reach the model.”* and include an error banner + logs.
  3. Add `health` preflight on send; if unhealthy, block send and show actionable error.

## OCR Pane Rules

- OCR **never** writes into Chat Pane by default.
- OCR Pane controls: **Capture**, **Auto‑capture (N s)**, **Copy text**, **Send to agent** (explicit), **Save result**.
- **Capture region** = cockpit docking area with padding (e.g., 12px inset). On resize, recompute region and inform backend via `/ocr/region`.
- **Backend** dynamically adjusts Tesseract crop (no capture outside docking bounds). Debounce rapid resizes (250ms).

## Streaming

- **Chat**: SSE or WS stream per message id; the UI shows tokens as they arrive, with stop button.
- **Logs**: Dedicated WS channel `TRACE` multiplexed by topic; UI virtualized list.
- **OCR**: Optional stream of text events to OCR Pane only.

## Implementation Tasks (Backend)

1. **Slots API & FS Watcher** (`ui_bridge/api.py`)
   - Implement `GET/POST/DELETE /slots` with YAML read/write + schema validation (pydantic) and file‑lock.
   - Broadcast `SLOTS_UPDATED` on change.
2. **Providers** (`agents/providers/*`)
   - Implement adapters: `ollama.py`, `openai_p.py`, `azure_openai.py`, `anthropic_p.py`, `groq_p.py`, `lmstudio_p.py`, `generic_http.py`.
   - `/providers` endpoint returns supported list + required fields.
3. **Chat Endpoint**
   - Accept `{messages:[...]}`, route to slot.provider adapter; stream tokens.
   - Uniform error schema: `{error:{code,http_status,message,details}}`.
4. **Logs streaming**
   - Emit structured JSON via WS topics; persist to rotating JSONL files per day; implement `GET /logs/export?from=...&to=...`.
5. **OCR region endpoint**
   - `POST /ocr/region` to set capture box; capture respects inset; supports auto‑capture interval.

## Implementation Tasks (WPF Cockpit)

1. **Docking**: integrate AvalonDock; register Chat/Logs/OCR panes as `LayoutDocument`/`LayoutAnchorable`.
2. **Agent Slots MVVM**
   - `AgentSlotViewModel` bound to YAML fields; changes trigger POST `/slots`.
   - FS watcher signal (`SLOTS_UPDATED`) refreshes collections.
3. **Chat Pane**
   - Use ObservableCollection for messages; streaming endpoint updates progressively.
   - Error banner control; retry button.
4. **Logs Pane**
   - Virtualized list; filters and pause/resume; **Export** button hits `/logs/export`.
5. **OCR Pane**
   - Canvas showing capture preview; configure inset; **Send to agent** optional.
6. **Copy & Strings**
   - Remove every “NL command” string; centralize in `Strings.resx`.

## Acceptance Criteria

- Typing “hello” in any Chat Pane yields a natural reply or an explicit, actionable error (never “Unknown NL command”).
- Adding/removing/editing an agent in UI updates `configs/slots.yml`; external YAML edits reflect in UI within 1–2s.
- OCR never floods chat; appears only in OCR Pane unless explicitly sent.
- Logs stream continuously; exporting produces a JSONL file containing everything visible + buffered.
- Provider can be switched per slot; health check shows status; failures are clear.

## Deliverables I Can Generate Next

- Backend PR: slots API, providers scaffold, logs export, OCR region handling, error schema.
- WPF PR: AvalonDock layout, new panes, MVVM for slots, streaming chat + logs, new copy.
- PowerShell installer updated to include provider env var prompts and YAML bootstrapping.

## Config & Security Notes

- Keys: stored only in environment; YAML stores `api_key_env` names. UI offers a “Test” button that resolves env var only for a health ping; never persists secrets to disk.
- YAML writes use atomic temp‑file swap; file‑watcher ignores self‑writes using hash.

## Copy Updates (ready‑to‑ship)

- Unknown intent: *“I couldn’t turn that into an action yet. I saved it to the logs.”*
- Provider down: *“Model unreachable at {endpoint}. Check your API key or network.”*
- Policy block: *“I’m not allowed to do that on this profile ({rule\_id}).”*
- Welcome: *“Hi! I’m ready. Ask me anything or use OCR to read what’s on screen.”*



---

# Provider Integration (NVIDIA + Perplexity) — Functional Stack & PR‑Ready Patches

You said you want **NVIDIA** and **Perplexity** providers, and you want a **functional** stack (not chasing a specific UI tech). Here’s a concrete plan with drop‑in code you can paste. Both providers expose **OpenAI‑compatible** chat endpoints, so we’ll implement a single OpenAI‑style adapter and register provider presets.

## Minimal Functional Stack

- **Backend**: Python 3.11, FastAPI/uvicorn (we already have this). Add `/providers`, `/chat`, `/slots`.
- **Cockpit**: WPF .NET 8 + AvalonDock (stable docking, fast). If you want Electron later, the backend contracts stay the same.
- **Config**: `configs/slots.yml` becomes source of truth; each slot picks a provider.

## Env Vars

```
# Perplexity
PPLX_API_KEY=...
# NVIDIA
NVIDIA_API_KEY=...
# Optional default model names
PPLX_MODEL=llama-3.1-sonar-small-online
NVIDIA_MODEL=meta/llama-3.1-70b-instruct
```

## YAML Schema (slots)

```yaml
slots:
  - id: default
    name: Default Assistant
    provider: perplexity   # one of: perplexity, nvidia, ollama, openai, azure_openai, anthropic, groq, generic_http
    endpoint: https://api.perplexity.ai
    model: llama-3.1-sonar-small-online
    api_key_env: PPLX_API_KEY
    temperature: 0.2
    prompt: |
      You are a helpful assistant. Speak naturally and concisely.
    params:
      max_tokens: 512
```

## Backend: Provider Abstraction

``

```python
from typing import Protocol, List, Dict, Any

class LLMProvider(Protocol):
    name: str
    def health(self) -> Dict[str, Any]: ...
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]: ...
```

`` (single adapter for OpenAI‑compatible APIs)

```python
import os, requests
from typing import List, Dict, Any, Optional

class OpenAICompatProvider:
    def __init__(self, name: str, base_url: str, api_key_env: str, model_default: Optional[str] = None, org_env: Optional[str] = None):
        self.name = name
        self.base_url = base_url.rstrip('/')
        self.api_key_env = api_key_env
        self.model_default = model_default
        self.org_env = org_env

    def _headers(self) -> Dict[str, str]:
        key = os.getenv(self.api_key_env, '')
        if not key:
            raise RuntimeError(f"Missing API key in env: {self.api_key_env}")
        h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if self.org_env and os.getenv(self.org_env):
            h["OpenAI-Organization"] = os.getenv(self.org_env)  # optional
        return h

    def health(self) -> Dict[str, Any]:
        try:
            # Many OpenAI‑compatible hosts mirror /models or /chat/completions. We'll do a cheap POST with a 1‑token limit.
            import json
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model_default or "",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            r = requests.post(url, headers=self._headers(), json=payload, timeout=6)
            return {"ok": r.status_code < 500, "status": r.status_code, "endpoint": self.base_url}
        except Exception as e:
            return {"ok": False, "error": str(e), "endpoint": self.base_url}

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": kwargs.get("model") or self.model_default,
            "messages": messages,
            "temperature": kwargs.get("temperature"),
            **({k:v for k,v in kwargs.items() if k not in {"model","temperature"}})
        }
        r = requests.post(url, headers=self._headers(), json=body, timeout=60)
        if r.status_code >= 400:
            # Uniform error bubble‑up for the UI
            try:
                detail = r.json()
            except Exception:
                detail = {"text": r.text}
            raise RuntimeError(f"Provider error {r.status_code}: {detail}")
        return r.json()
```

``

```python
from .openai_compat import OpenAICompatProvider
import os

# Presets
PERPLEXITY = OpenAICompatProvider(
    name="perplexity", base_url=os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai"),
    api_key_env="PPLX_API_KEY", model_default=os.getenv("PPLX_MODEL", "llama-3.1-sonar-small-online")
)

NVIDIA = OpenAICompatProvider(
    name="nvidia", base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    api_key_env="NVIDIA_API_KEY", model_default=os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
)

# Keep existing providers
try:
    from .ollama import OLLAMA
except Exception:
    OLLAMA = None

PROVIDERS = {p.name: p for p in [PERPLEXITY, NVIDIA] if p}  # extend with others
```

## Backend: `/providers` and `/dexter/chat`

``** (snippets)**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.providers import PROVIDERS
from configs.slots import get_active_slots  # helper to read YAML

router = APIRouter()

class ChatReq(BaseModel):
    slot_id: str
    messages: list[dict]
    params: dict | None = None

@router.get("/providers")
async def list_providers():
    return {"providers": list(PROVIDERS.keys())}

@router.post("/dexter/chat")
async def dexter_chat(req: ChatReq):
    slot = get_active_slots().by_id(req.slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail={"code":"slot_not_found","slot":req.slot_id})
    provider = PROVIDERS.get(slot.provider)
    if not provider:
        raise HTTPException(status_code=400, detail={"code":"provider_unsupported","provider":slot.provider})
    try:
        result = provider.chat(req.messages, model=slot.model, temperature=slot.temperature, **(req.params or {}))
        # normalize to {choices:[{message:{role,content}}]}
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail={"code":"provider_error","message":str(e)})
```

## Two‑Way YAML Sync (routes)

``** (slots)**

```python
class Slot(BaseModel):
    id: str
    name: str
    provider: str
    endpoint: str | None = None
    model: str
    api_key_env: str | None = None
    temperature: float | None = None
    prompt: str | None = None
    params: dict | None = None

@router.get("/slots")
async def slots_get():
    return get_active_slots().as_dict()

@router.post("/slots")
async def slot_upsert(slot: Slot):
    cfg = get_active_slots()
    cfg.upsert(slot.model_dump())
    cfg.save()  # writes YAML atomically
    await bus.broadcast("SYSTEM","SLOTS_UPDATED", {"hash": cfg.hash})
    return {"ok": True, "hash": cfg.hash}

@router.delete("/slots/{slot_id}")
async def slot_delete(slot_id: str):
    cfg = get_active_slots(); cfg.delete(slot_id); cfg.save()
    await bus.broadcast("SYSTEM","SLOTS_UPDATED", {"hash": cfg.hash})
    return {"ok": True}
```

## Cockpit Wiring (works now)

- **Agent Add** → opens a modal form (provider, endpoint, model, api key env, temp, prompt). On Save → `POST /slots` and immediately open Chat pane.
- **Chat send** → `POST /dexter/chat` with `slot_id` and OpenAI‑format messages. Stream if backend supports SSE/WS; otherwise poll.
- **Error copy** → shows provider’s HTTP error text, never “Unknown NL command”.

## Why this unlocks revenue

- NVIDIA gives you enterprise‑friendly, GPU‑optimized models with consistent latency; Perplexity gives you **online** and general models with strong reasoning. You can sell “bring your own key/provider” on day one rather than shipping a monolith.

## What I can generate next

- Full `configs/slots.py` helper (read/write/validate YAML, file‑watcher).
- WPF code‑behind + MVVM for AgentSlot editor, Chat pane, and Logs pane wired to the new endpoints.
- Unit tests for provider adapters (mocked HTTP) and slots round‑trip.



---

# Migration Plan: Ollama‑Only → Provider‑Agnostic (w/ Zero‑Break Option)

You’re right: today most code paths expect **Ollama**. Here’s how to make **NVIDIA/Perplexity** work without breaking anything.

## Option A — **Zero‑break shim** (fastest)

Create an **Ollama‑compatible shim** that implements the current `OllamaClient` surface but forwards to an OpenAI‑compatible provider under the hood. No orchestrator/UI changes required now.

### 1) Drop‑in replacement

``

```python
# A thin adapter that mimics the existing OllamaClient but calls an OpenAI‑compatible backend
from typing import List, Dict, Any, Optional
import os, requests

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, headers: Optional[Dict[str,str]] = None):
        # Preserve ctor signature used in code
        self.base_url = (base_url or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip('/')
        self.model = model or os.getenv("OLLAMA_MODEL", "")
        self.headers = headers or {}
        # If OLLAMA_HOST starts with http(s) and not localhost, assume OpenAI‑compat if OLLAMA_PROVIDER is set
        # e.g., OLLAMA_PROVIDER=perplexity|nvidia and relevant API key env present
        self.provider = os.getenv("OLLAMA_PROVIDER", "ollama")
        if self.provider != "ollama":
            # Map provider → base url + auth
            if self.provider == "perplexity":
                self.base_url = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai")
                self.headers.update({"Authorization": f"Bearer {os.getenv('PPLX_API_KEY','')}"})
                self.model = self.model or os.getenv("PPLX_MODEL", "llama-3.1-sonar-small-online")
            elif self.provider == "nvidia":
                self.base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
                self.headers.update({"Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY','')}"})
                self.model = self.model or os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        if self.provider == "ollama":
            # Keep original behavior
            url = f"{self.base_url}/api/chat"
            body = {"model": self.model, "messages": messages, "options": kwargs.get("options")}
            r = requests.post(url, json=body, headers=self.headers, timeout=60)
            r.raise_for_status(); return r.json()
        else:
            # OpenAI‑compatible path
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            body = {"model": self.model, "messages": messages}
            # Translate Ollama "options" → OpenAI params if present
            opts = kwargs.get("options") or {}
            if "temperature" in opts: body["temperature"] = opts["temperature"]
            if "top_p" in opts: body["top_p"] = opts["top_p"]
            r = requests.post(url, json=body, headers={**self.headers, "Content-Type":"application/json"}, timeout=60)
            r.raise_for_status(); return r.json()

    def embeddings(self, **kwargs) -> Dict[str, Any]:
        if self.provider == "ollama":
            url = f"{self.base_url}/api/embeddings"; r = requests.post(url, json=kwargs, headers=self.headers, timeout=60)
            r.raise_for_status(); return r.json()
        else:
            url = f"{self.base_url.rstrip('/')}/embeddings"; r = requests.post(url, json=kwargs, headers={**self.headers, "Content-Type":"application/json"}, timeout=60)
            r.raise_for_status(); return r.json()
```

**Wiring:** replace imports of `from .adapters.ollama_adapter import OllamaClient` with `from .adapters.ollama_shim import OllamaClient`. At runtime:

- Default remains **real Ollama**.
- To use **Perplexity**: set `OLLAMA_PROVIDER=perplexity` and `PPLX_API_KEY`.
- To use **NVIDIA**: set `OLLAMA_PROVIDER=nvidia` and `NVIDIA_API_KEY`.

**Pros:** zero orchestrator/UI refactor; immediate NVIDIA/Perplexity support.\
**Cons:** you’re still naming things “Ollama” in code; streaming/function‑calling remain mapped only if used before.

## Option B — **Proper Provider Registry** (clean, future‑proof)

Refactor orchestrator to depend on an abstract `LLMProvider` interface; slots declare provider in YAML; UI edits sync via `/slots`.

**Steps:**

1. Introduce `agents/providers/base.py` + `openai_compat.py` (done above).
2. Add `PROVIDERS` registry and `/providers`.
3. Orchestrator: resolve `slot.provider` to adapter; remove direct dependency on `OllamaClient`.
4. UI: render provider fields; save to YAML via `/slots`.

**Pros:** clear semantics, multi‑provider, streaming parity, cleaner errors.\
**Cons:** a bit more code touch than the shim.

## Streaming & Response Shape

- **Ollama** returns `{ message: {role, content}, ... }` (and can stream `data:` chunks).
- **OpenAI‑compat** returns `{ choices:[{message:{role,content}}], ... }` (streams `delta`).

Add a normalizer in the orchestrator so downstream code always sees:

```python
{ "role": "assistant", "content": "..." }
```

If streaming, accumulate `delta.content` pieces before emitting to UI.

## Acceptance Tests

- With **OLLAMA\_PROVIDER=ollama** and no keys → original behavior unchanged.
- With **perplexity**/**nvidia** and keys set → `hello` chat succeeds; health reports provider OK; no “Unknown NL command”.
- Error path: wrong key returns HTTP 401 surfaced in chat banner and logs (no placeholders).

## Recommendation

- **Do Option A now** to unblock providers today.
- Then move to **Option B** as you finalize slots YAML + UI sync (already spec’d above).



---

# Shim Implementation (incl. NVIDIA, Perplexity, **GitHub Models**) — Drop‑in for Current Ollama Client

Below is a **single-file shim** that preserves your existing `OllamaClient` API while routing to OpenAI‑compatible endpoints for NVIDIA, Perplexity, and GitHub Models. Keep all orchestrator/UI code the same; flip providers via env vars.

## Env Vars

```bash
# Core toggle (keep defaults to real Ollama)
OLLAMA_PROVIDER=ollama|perplexity|nvidia|github|openai_compat
OLLAMA_HOST=http://127.0.0.1:11434       # used when provider=ollama
OLLAMA_MODEL=llama3.1                     # optional default when provider=ollama

# Perplexity
PPLX_API_KEY=... 
PPLX_BASE_URL=https://api.perplexity.ai    # OpenAI-compatible
PPLX_MODEL=llama-3.1-sonar-small-online

# NVIDIA
NVIDIA_API_KEY=...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-70b-instruct

# GitHub Models (OpenAI-compatible)
GITHUB_TOKEN=...                           # a GitHub token with models access
GITHUB_MODELS_BASE_URL=...                 # required, e.g. https://models.inference.ai.azure.com
GITHUB_MODEL=gpt-4o-mini                   # example; set to any model your org exposes

# Generic OpenAI-compatible (fallback preset)
OPENAI_COMPAT_API_KEY=...
OPENAI_COMPAT_BASE_URL=https://your-endpoint
OPENAI_COMPAT_MODEL=...
```

## File: `agents/adapters/ollama_shim.py`

```python
"""
Drop-in replacement for the existing OllamaClient that can talk to:
- Real Ollama (/api/chat, /api/embeddings)
- OpenAI-compatible providers (/chat/completions, /embeddings):
  - Perplexity, NVIDIA, GitHub Models, or any custom endpoint

Usage:
  from agents.adapters.ollama_shim import OllamaClient
  client = OllamaClient()
  client.chat(messages=[{"role":"user","content":"hello"}])

Control via env var OLLAMA_PROVIDER in {ollama, perplexity, nvidia, github, openai_compat}
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, requests

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, headers: Optional[Dict[str,str]] = None):
        self.provider = os.getenv("OLLAMA_PROVIDER", "ollama").lower()
        self.headers = headers.copy() if headers else {}

        if self.provider == "ollama":
            self.base_url = (base_url or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
            self.model = model or os.getenv("OLLAMA_MODEL", "")
            self.mode = "ollama"
        elif self.provider == "perplexity":
            self.base_url = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai").rstrip("/")
            api_key = os.getenv("PPLX_API_KEY", "")
            if not api_key:
                raise RuntimeError("Perplexity selected but PPLX_API_KEY is missing")
            self.headers.setdefault("Authorization", f"Bearer {api_key}")
            self.headers.setdefault("Content-Type", "application/json")
            self.model = model or os.getenv("PPLX_MODEL", "llama-3.1-sonar-small-online")
            self.mode = "openai"
        elif self.provider == "nvidia":
            self.base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
            api_key = os.getenv("NVIDIA_API_KEY", "")
            if not api_key:
                raise RuntimeError("NVIDIA selected but NVIDIA_API_KEY is missing")
            self.headers.setdefault("Authorization", f"Bearer {api_key}")
            self.headers.setdefault("Content-Type", "application/json")
            self.model = model or os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
            self.mode = "openai"
        elif self.provider == "github":
            base = os.getenv("GITHUB_MODELS_BASE_URL", "").rstrip("/")
            if not base:
                raise RuntimeError("GitHub Models selected but GITHUB_MODELS_BASE_URL is not set")
            self.base_url = base
            token = os.getenv("GITHUB_TOKEN", "")
            if not token:
                raise RuntimeError("GitHub Models selected but GITHUB_TOKEN is missing")
            self.headers.setdefault("Authorization", f"Bearer {token}")
            self.headers.setdefault("Content-Type", "application/json")
            self.model = model or os.getenv("GITHUB_MODEL", "")
            if not self.model:
                raise RuntimeError("Set GITHUB_MODEL to a deployed GitHub model name")
            self.mode = "openai"
        else:  # generic openai-compatible
            base = os.getenv("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
            if not base:
                raise RuntimeError("OPENAI_COMPAT_BASE_URL must be set when OLLAMA_PROVIDER=openai_compat")
            self.base_url = base
            key = os.getenv("OPENAI_COMPAT_API_KEY", "")
            if not key:
                raise RuntimeError("OPENAI_COMPAT_API_KEY is missing")
            self.headers.setdefault("Authorization", f"Bearer {key}")
            self.headers.setdefault("Content-Type", "application/json")
            self.model = model or os.getenv("OPENAI_COMPAT_MODEL", "")
            if not self.model:
                raise RuntimeError("Set OPENAI_COMPAT_MODEL for your endpoint")
            self.mode = "openai"

    # --- Public surface kept compatible ---
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        if self.mode == "ollama":
            url = f"{self.base_url}/api/chat"
            body = {"model": self.model, "messages": messages}
            options = kwargs.get("options")
            if options:
                body["options"] = options
            r = requests.post(url, json=body, headers=self.headers, timeout=60)
            self._raise_for_response(r)
            return r.json()
        else:
            # OpenAI-compatible
            url = f"{self.base_url}/chat/completions"
            options = kwargs.get("options", {})
            body: Dict[str, Any] = {"model": self.model, "messages": messages}
            # Map common options
            if "temperature" in options: body["temperature"] = options["temperature"]
            if "top_p" in options: body["top_p"] = options["top_p"]
            if "max_tokens" in options: body["max_tokens"] = options["max_tokens"]
            r = requests.post(url, json=body, headers=self.headers, timeout=90)
            self._raise_for_response(r)
            return r.json()

    def embeddings(self, **kwargs) -> Dict[str, Any]:
        if self.mode == "ollama":
            url = f"{self.base_url}/api/embeddings"
            r = requests.post(url, json=kwargs, headers=self.headers, timeout=60)
            self._raise_for_response(r)
            return r.json()
        else:
            url = f"{self.base_url}/embeddings"
            r = requests.post(url, json=kwargs, headers=self.headers, timeout=90)
            self._raise_for_response(r)
            return r.json()

    # --- Helpers ---
    @staticmethod
    def _raise_for_response(r: requests.Response):
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = {"text": r.text}
            raise RuntimeError(f"Provider error {r.status_code}: {detail}")
```

## How to Wire It

1. Replace imports where the orchestrator builds the client:\
   `from agents.adapters.ollama_adapter import OllamaClient` → `from agents.adapters.ollama_shim import OllamaClient`
2. Keep **everything else the same**.
3. Set env vars for the provider you want and run.

## Acceptance Checklist

- `OLLAMA_PROVIDER=ollama` → unchanged behavior with real Ollama.
- \`OLLAMA\_PROVIDE
