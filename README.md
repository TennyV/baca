# Baca 🐑

**A multi-LLM herder.** Baca (Polish for a highland shepherd) takes one task, fans it out to several large language models in parallel — the *council* — then has a *chairman* model merge their answers into one. Think of it as a shepherd keeping a flock of LLMs working together.

It talks to every model through [LiteLLM](https://github.com/BerriAI/litellm), so you can freely mix cloud APIs (OpenAI/GPT, Anthropic/Claude, Google/Gemini, xAI/Grok) and local open-weight models (via Ollama or vLLM) with the exact same code. **No platform fee** — you pay only the model APIs you use, or nothing at all when running local models.

## Why

Different models have different strengths and blind spots. Asking three of them and synthesizing the best answer beats trusting any single one — especially for writing, review, and reasoning tasks.

## How it works

```
         ┌──────────┐
task ──► │   Baca   │
         └────┬─────┘
       fan out │  (parallel)
     ┌─────────┼─────────┐
     ▼         ▼         ▼
   GPT      Claude    Gemini     ← the council
     └─────────┼─────────┘
               ▼
          Chairman            ← merges into one final answer
               ▼
         final answer
```

Three modes:
- **`ensemble`** (default) — every model answers, the chairman synthesizes one answer.
- **`council`** — adds a round where each model critiques the others' (anonymized) drafts before the chairman synthesizes. Slower, higher quality.
- **`raw`** — just show every model's answer side by side (no synthesis).

Built-in resilience: automatic retry/backoff on rate limits, and per-model **fallback chains** so an overloaded model is swapped for a working one automatically.

## Quick start (≈5 minutes)

### 1. Get the code
```bash
git clone https://github.com/TennyV/baca.git
cd baca
```

### 2. Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Add at least one API key
Baca reads keys from environment variables. You only need the ones you want to use.

```bash
cp .env.example .env
# edit .env, then:
export $(grep -v '^#' .env | xargs)
```

| Model  | Env var             | Where to get a key                              | Cost |
|--------|---------------------|-------------------------------------------------|------|
| Gemini | `GEMINI_API_KEY`    | https://aistudio.google.com/apikey              | Free tier available |
| Claude | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys     | Prepaid credit (Billing) |
| GPT    | `OPENAI_API_KEY`    | https://platform.openai.com/api-keys            | Prepaid credit (Billing) |
| Grok   | `XAI_API_KEY`       | https://console.x.ai                            | Paid |

> **Note:** API access is separate from any chat subscription (ChatGPT Plus, Claude Pro, etc.). You need an **API key** and, for OpenAI/Anthropic, a small prepaid balance. A school/work account behind SSO often can't create API keys — use a personal account.

### 4. Turn on the models you have keys for
Open `models.yaml` and set `enabled: true` for each model whose key you added. Leave the rest `false`.

### 5. Run it
```bash
# one-off task
python baca.py "Summarize the pros and cons of microservices in 5 bullets"

# from a file
python baca.py --file draft.md --mode council

# pipe it in
echo "Explain SSRF to a junior dev" | python baca.py

# see every model's raw answer
python baca.py "Capital of Poland + one fact" --mode raw
```

## Configuration (`models.yaml`)

```yaml
system: "You are a sharp, concise expert. Be accurate and specific; do not pad."

council:
  - name: Gemini
    model: gemini/gemini-3.5-flash
    enabled: true
    temperature: 0.7
    fallbacks:                    # tried in order if the primary is overloaded
      - gemini/gemini-3-flash-preview
      - gemini/gemini-flash-lite-latest

  - name: Claude
    model: anthropic/claude-sonnet-5-5
    enabled: true
    temperature: 0.7

  - name: GPT
    model: openai/gpt-5.1
    enabled: true
    temperature: 0.7

chairman:                         # synthesizes the council's answers
  name: Chairman
  model: gemini/gemini-3.5-flash
  temperature: 0.4
```

- **`model`** uses LiteLLM's `provider/model` naming — see the [LiteLLM provider list](https://docs.litellm.ai/docs/providers). Model names change often; list what your key can reach (see below).
- **`enabled`** — flip a model on/off without deleting it.
- **`fallbacks`** — optional ordered list of backup models used if the primary returns a transient error (429/503).
- **`chairman`** — can be any model; it writes the final merged answer.

### Find which models your key can actually use
Model availability changes constantly. Quick checks:

```bash
# Gemini
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | grep '"name"'

# OpenAI
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | grep '"id"'

# Anthropic
curl -s https://api.anthropic.com/v1/models -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" | grep '"id"'
```

## Going fully local / open source (optional)

Want zero per-call cost and full privacy? Run open-weight models with [Ollama](https://ollama.com):

```bash
# install Ollama, then:
ollama pull llama3.1
```

Add to `models.yaml` (no API key needed):
```yaml
  - name: Llama-local
    model: ollama/llama3.1
    enabled: true
    temperature: 0.7
```

The herder code doesn't change — only the config. You can mix cloud and local models in the same council, and phase out the paid ones as local models improve.

## Cost notes

- A short run (a few thousand tokens) is typically well under $0.01–$0.10.
- A long task (e.g. cleaning up a full paper) with three cloud models might run a few dollars.
- `council` mode roughly doubles token use vs `ensemble` (extra critique round).
- Gemini's free tier and local Ollama models cost nothing.

## License

MIT
