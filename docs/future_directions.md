# Dexter Cockpit – Future Directions & Provider Integration Notes

This document captures the current state of the project, key improvement
opportunities, and guidance for adding support for additional model providers.

---

## Project Assessment

**What’s working well**

- **Windows-first autonomy experience**: Docking native windows, streaming OCR,
  and running guarded actions through the cockpit gives the user a tangible,
  inspectable workflow.
- **Strong safety posture**: The deny-first checks, layered policy overlays,
  and Dexter’s validation logic are clear differentiators.
- **Multi-agent coordination**: With Dexter orchestrating collaboration plans
  and publishing council events, the system is positioned for richer teamwork
  between tab agents.
- **Launch story**: `Start-Dexter.ps1` builds the cockpit automatically,
  validates Redis, and starts the full stack; `Launch-Dexter.bat` provides the
  click-to-run experience.

**Areas to refine**

- **Provider flexibility**: Slots currently assume an Ollama-compatible API.
  Without adapters or shims, providers such as OpenAI, Azure, or NVIDIA’s
  chat endpoints cannot be used directly.
- **Observability & testing**: We lack automated smoke tests that boot the full
  stack, hot-swap slots, and verify cockpit connectivity. Structured logging
  for Dexter’s decisions would make troubleshooting easier.
- **Chat UX scale**: As more events stream in (OCR snippets, collaboration
  plans, agent chatter) the logs can get noisy. Filtering, pinning, or
  thread-style conversations would help.
- **Packaging polish**: Consider bundling Redis or guiding users through a
  first-run setup wizard to smooth onboarding.
- **Roadmap visibility**: README_STATUS is a helpful internal note; consider
  mirroring its TODOs into GitHub issues or a public roadmap for contributors.

---

## Integrating Additional Model Providers (“Teaching Dexter”)

Dexter’s agents currently communicate with Ollama-compatible endpoints through
`OllamaClient`, `AUM`, and `BSM`. To support arbitrary providers, there are
two primary strategies:

### 1. Build an adapter layer inside Dexter

1. **Create a provider client**
   - Extend `dexter_autonomy/agents/adapters` with a class that speaks the
     provider’s REST contract (e.g., OpenAI Chat Completions or NVIDIA’s
     integrate API). Mirror the `chat` and `embed` methods expected by AUM/BSM.
   - Handle auth (API keys, headers), request parameters, and streaming modes.

2. **Teach AUM & BSM about providers**
   - Update `AUM`/`BSM` to accept a generic “client” instead of assuming
     `OllamaClient`. Either inject the adapter based on the slot configuration
     or create little strategy classes per provider.
   - Normalize the return shape (action lists, summaries) back into Dexter’s
     expected structures.

3. **Expose provider selection in slots**
   - Augment slot schema (`configs/slots.yml`) with a `provider` string or
     similar field. Use that to choose the right adapter when `_make_agents`
     runs in `ui_bridge/api.py`.
   - Continue to support per-slot prompts, sampler options, temperature, etc.

4. **Safety overlays per provider**
   - Some providers offer native guardrails; wire these into the deny-first
     flow (e.g., map policy tiers to provider-side safety settings).

### 2. Proxy external providers into the Ollama shape

If you prefer not to touch Dexter’s internals immediately:

1. **Run a shim or gateway** that exposes `/api/chat` and `/api/embed` but
   forwards to the real provider.
2. **Point the agent tab** to that shim (Base URL, model name, API key env var).
3. Dexter stays unchanged, and you can iterate on the proxy separately.

This is the quickest way to validate a new provider. Once satisfied, the
gateway logic can be moved into Dexter as a formal adapter.

### Runtime inputs from the cockpit

- The agent UI already lets an operator change endpoint URLs, API key env vars,
  model names, prompts, and sampling parameters. As long as the backend can
  speak the target protocol, those fields take effect immediately via the
  `/slot/set` hot reload.
- Additional deny rules or overlay prompts aren’t exposed in the tab today.
  If you need provider-specific safety tweaks (e.g., stronger refuse patterns),
  either extend the slot schema or add policy-editing controls.

---

## Suggested Near-Term Roadmap

1. **Provider adapters**: Implement native support for at least one non-Ollama
   provider (OpenAI or Azure). Use the adapter pattern above to keep the slot
   UX the same.
2. **End-to-end smoke tests**: Script a run that launches the backend, opens
   a WebSocket session, swaps slots, and asserts that Dexter answers. Catch
   regressions before they reach users.
3. **Chat console improvements**: Add filters (system/custom), optionally group
   messages by agent, and surface collaboration plans in their own pane.
4. **Observability**: Introduce structured logging (loguru/structlog) for
   Dexter decisions, policy validations, and action executions. Consider a
   “diagnostics” tab in the cockpit.
5. **Onboarding polish**: Package Redis installation steps, add a first-run
   script that checks prerequisites, and document the new `Launch-Dexter.bat`
   path in README and issues.

---

By tackling provider flexibility and operational polish next, you’ll give
Dexter broader reach while preserving the strong deny-first safety posture
that makes this project unique. Let the cockpit remain the authoritative
control surface, and keep layering observability/automation so humans can stay
in command even as the agent team grows. Happy hacking!
