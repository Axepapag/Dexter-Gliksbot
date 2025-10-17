# Hot-Swappable LLM Provider System

**Date**: October 16, 2025  
**Status**: ✅ **IMPLEMENTED**

---

## Overview

The Dexter-Gliksbot system now supports **hot-swappable LLM providers**. You can configure any provider (Google Gemini, OpenAI, Anthropic, Ollama, etc.) in `configs/dexter_config.yml` and the system will automatically use it.

No code changes required - just edit the config file!

---

## Supported Providers

| Provider | Name | Models | API Key Required |
|----------|------|--------|-----------------|
| **Google Gemini** | `google` or `gemini` | gemini-2.5-pro, gemini-2.5-flash, learnlm-1.5-pro-experimental | Yes (`GOOGLE_API_KEY`) |
| **Ollama** | `ollama` | Any local model (qwen2.5, llama3, etc.) | No |
| **OpenAI** | `openai` | gpt-4o, gpt-4o-mini, o1, etc. | Yes (`OPENAI_API_KEY`) |
| **Anthropic** | `anthropic` | claude-3-5-sonnet, claude-3-opus | Yes (`ANTHROPIC_API_KEY`) |
| **NVIDIA** | `nvidia` | llama-3.1-70b, mistral, etc. | Yes (`NVIDIA_API_KEY`) |
| **Perplexity** | `perplexity` | llama-3.1-sonar online models | Yes (`PERPLEXITY_API_KEY`) |
| **GitHub Models** | `github` | Various models via GitHub | Yes (`GITHUB_TOKEN`) |
| **Groq** | `groq` | Fast inference models | Yes (`GROQ_API_KEY`) |
| **Azure OpenAI** | `azure` | Deployed models | Yes (`AZURE_OPENAI_API_KEY`) |
| **LM Studio** | `lmstudio` | Local models | No |
| **Generic** | `generic` | Any OpenAI-compatible endpoint | Optional |

---

## Configuration

### Edit `configs/dexter_config.yml`

```yaml
agents:
  
  # Dexter - Main Orchestrator
  dexter-orchestrator:
    label: "Dexter Central Orchestrator"
    
    provider: "google"              # Change this to switch providers!
    model: "gemini-2.5-pro"         # Provider-specific model name
    endpoint: null                  # Auto for Google, set for custom
    api_key_env: "GOOGLE_API_KEY"   # Environment variable name
    
    temperature: 0.15               # LLM temperature
    max_output_tokens: 81920        # Max tokens
    timeout: 120                    # Request timeout
    
    # Gemini-specific features
    thinking_enabled: true          # Enable thinking mode
    thinking_budget: 15000          # Thinking tokens
    
    system_prompt: |
      You are Dexter, the central orchestrator...
  
  # BSM - Brain/State Model
  bsm-brain:
    label: "Brain State Model (BSM)"
    
    provider: "google"
    model: "learnlm-1.5-pro-experimental"
    endpoint: null
    api_key_env: "GOOGLE_API_KEY"
    
    temperature: 0.3
    max_output_tokens: 2048
    timeout: 60
    
    system_prompt: |
      You are BSM, the omniscient observer...
```

### Set API Keys

Create `.env` file or export environment variables:

```bash
# Google Gemini (recommended for Dexter)
export GOOGLE_API_KEY=your_google_api_key_here

# OpenAI (alternative)
export OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Claude (alternative)
export ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Ollama (no key needed, local)
# Just have Ollama running: ollama serve
```

---

## Example Configurations

### 1. Google Gemini (Production Quality)

**Best for**: Dexter's complex reasoning with thinking mode

```yaml
dexter-orchestrator:
  provider: "google"
  model: "gemini-2.5-pro"
  api_key_env: "GOOGLE_API_KEY"
  thinking_enabled: true
  thinking_budget: 15000
  temperature: 0.15
```

### 2. Ollama (Local, Free)

**Best for**: Development, testing, no API costs

```yaml
dexter-orchestrator:
  provider: "ollama"
  model: "qwen2.5:3b-instruct"
  endpoint: "http://127.0.0.1:11434"
  api_key_env: null
  temperature: 0.15
```

### 3. OpenAI GPT-4o (Alternative)

**Best for**: High quality, fast responses

```yaml
dexter-orchestrator:
  provider: "openai"
  model: "gpt-4o-mini"
  endpoint: "https://api.openai.com/v1"
  api_key_env: "OPENAI_API_KEY"
  temperature: 0.15
```

### 4. Anthropic Claude (Alternative)

**Best for**: Long context, careful reasoning

```yaml
dexter-orchestrator:
  provider: "anthropic"
  model: "claude-3-5-sonnet-20241022"
  api_key_env: "ANTHROPIC_API_KEY"
  temperature: 0.15
```

### 5. NVIDIA NIMs (Fast Inference)

**Best for**: Fast, cost-effective inference

```yaml
dexter-orchestrator:
  provider: "nvidia"
  model: "meta/llama-3.1-70b-instruct"
  endpoint: "https://integrate.api.nvidia.com/v1"
  api_key_env: "NVIDIA_API_KEY"
  temperature: 0.15
```

---

## How It Works

### Architecture

```
User → POST /dexter/chat
         ↓
    Load config from dexter_config.yml
         ↓
    Get provider ("google", "ollama", etc.)
         ↓
    Provider Factory creates instance
         ↓
    Chat via provider.chat()
         ↓
    Standardized ChatResponse
         ↓
    Return to user
```

### Provider Abstraction

All providers implement the same interface:

```python
class LLMProvider(ABC):
    def chat(messages, model, temperature, **kwargs) -> ChatResponse:
        """Unified chat interface"""
    
    def health() -> Dict[str, Any]:
        """Health check"""
    
    def list_models() -> List[str]:
        """List available models"""
```

Responses are standardized:

```python
@dataclass
class ChatResponse:
    content: str              # Response text
    model: str                # Model used
    finish_reason: str        # "stop", "length", etc.
    usage: Dict[str, int]     # Token counts
    raw_response: Any         # Original response
```

---

## Hot-Swapping Providers

### Method 1: Edit Config (Recommended)

1. Stop the server (Ctrl+C)
2. Edit `configs/dexter_config.yml`
3. Change `provider` and `model` fields
4. Start the server: `python start.py --port 8765`

**Example**: Switch from Ollama to Google Gemini

```yaml
# Before
dexter-orchestrator:
  provider: "ollama"
  model: "qwen2.5:3b-instruct"

# After  
dexter-orchestrator:
  provider: "google"
  model: "gemini-2.5-pro"
  api_key_env: "GOOGLE_API_KEY"
  thinking_enabled: true
```

### Method 2: Environment Variables (Override)

Set environment variables to override config:

```bash
export DEXTER_PROVIDER=google
export DEXTER_MODEL=gemini-2.5-flash
export GOOGLE_API_KEY=your_key_here

python start.py --port 8765
```

---

## Provider Features

### Google Gemini

**Special Features**:
- ✅ Thinking mode (gemini-2.5 models)
- ✅ Thinking budget control
- ✅ LearnLM for education/learning tasks
- ✅ Very large context windows
- ✅ Multimodal (images, audio)

**Configuration**:
```yaml
provider: "google"
model: "gemini-2.5-pro"
thinking_enabled: true
thinking_budget: 15000  # Tokens for thinking
```

### Ollama

**Special Features**:
- ✅ Runs 100% locally
- ✅ No API costs
- ✅ Works offline
- ✅ Privacy (data never leaves machine)
- ✅ Fast for small models

**Configuration**:
```yaml
provider: "ollama"
model: "qwen2.5:3b-instruct"  # or llama3:8b, phi3, etc.
endpoint: "http://127.0.0.1:11434"
```

**Install Ollama**:
```bash
# Windows
winget install Ollama.Ollama

# Start service
ollama serve

# Pull models
ollama pull qwen2.5:3b-instruct
ollama pull llama3:8b
ollama pull deepseek-r1:8b
```

### OpenAI

**Special Features**:
- ✅ GPT-4o (best quality)
- ✅ GPT-4o-mini (cost-effective)
- ✅ o1/o3 reasoning models
- ✅ Function calling
- ✅ JSON mode

**Configuration**:
```yaml
provider: "openai"
model: "gpt-4o-mini"
endpoint: "https://api.openai.com/v1"
api_key_env: "OPENAI_API_KEY"
```

### Anthropic Claude

**Special Features**:
- ✅ 200K+ context window
- ✅ Careful, thoughtful responses
- ✅ Strong at analysis
- ✅ Citations and sourcing

**Configuration**:
```yaml
provider: "anthropic"
model: "claude-3-5-sonnet-20241022"
api_key_env: "ANTHROPIC_API_KEY"
```

---

## Testing Providers

### Test Configuration

```powershell
# Check current provider
curl http://localhost:8765/health | jq

# Test Dexter with current provider
$body = @{message="Hello Dexter"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8765/dexter/chat" -Method Post -Body $body -ContentType "application/json"

# Check which provider was used (in response metadata)
```

### Provider Health Check

```python
from dexter_autonomy.agents.providers import get_provider

# Test Google Gemini
provider = get_provider("google", api_key_env="GOOGLE_API_KEY")
health = provider.health()
print(health)  # {"ok": True, "models": 15, ...}

# Test Ollama
provider = get_provider("ollama")
health = provider.health()
print(health)  # {"ok": True, "models": [...], ...}
```

---

## Response Metadata

Chat responses now include provider information:

```json
{
  "response": "Hello! I am Dexter...",
  "agent": "dexter",
  "timestamp": 1234567890.123,
  "metadata": {
    "provider": "google",
    "model": "gemini-2.5-pro",
    "usage": {
      "prompt_tokens": 45,
      "completion_tokens": 123,
      "total_tokens": 168
    }
  }
}
```

---

## Benefits

### 1. Flexibility ✅
- Use any provider for any agent
- Mix and match (Gemini for Dexter, Ollama for BSM)
- Easy experimentation

### 2. Cost Control ✅
- Use Ollama for development (free)
- Use cloud providers for production
- Switch based on budget

### 3. Quality Optimization ✅
- Use best model for each task
- Gemini thinking for complex reasoning
- Fast models for simple tasks

### 4. Resilience ✅
- Fallback to Ollama if API fails
- No vendor lock-in
- Easy disaster recovery

### 5. Privacy ✅
- Use Ollama for sensitive data
- Keep data on-premise
- Compliance requirements met

---

## Recommended Configurations

### Production (Best Quality)

```yaml
dexter-orchestrator:
  provider: "google"
  model: "gemini-2.5-pro"
  thinking_enabled: true

bsm-brain:
  provider: "google"
  model: "learnlm-1.5-pro-experimental"
```

### Development (Free, Fast)

```yaml
dexter-orchestrator:
  provider: "ollama"
  model: "qwen2.5:3b-instruct"

bsm-brain:
  provider: "ollama"
  model: "qwen2.5:3b-instruct"
```

### Hybrid (Quality + Cost)

```yaml
dexter-orchestrator:
  provider: "google"          # Quality for main agent
  model: "gemini-2.5-flash"   # Fast Gemini

bsm-brain:
  provider: "ollama"          # Local for observation
  model: "qwen2.5:3b-instruct"
```

---

## Troubleshooting

### Error: Provider not found

**Solution**: Check provider name matches supported list.

```yaml
# Wrong
provider: "openai-gpt"

# Correct
provider: "openai"
```

### Error: API key not set

**Solution**: Set environment variable or update .env

```bash
export GOOGLE_API_KEY=your_key_here
# or edit .env file
```

### Error: google-genai not installed

**Solution**: Install Google AI SDK

```bash
pip install google-genai
```

### Error: Model not available

**Solution**: Check model name with provider

```python
provider = get_provider("google")
models = provider.list_models()
print(models)
```

---

## Next Steps

1. ✅ **Configure Your Provider** - Edit `dexter_config.yml`
2. ✅ **Set API Keys** - Add to `.env` or environment
3. ✅ **Restart Server** - `python start.py --port 8765`
4. ✅ **Test Chat** - Try `/dexter/chat` endpoint
5. ✅ **Monitor Usage** - Check response metadata

---

**System is now provider-agnostic and hot-swappable!** 🎉

