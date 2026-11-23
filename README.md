# Baca 🐑

**A multi-LLM herder**, named after the Górale (Polish Highlander) master shepherd.

Baca takes one task — a *redyk* — and sends it out to a flock of large language models (his *juhasi*). They all work it in parallel; then the *gazda* presses their drafts into one finished answer — the *oscypek*.

It talks to every model through [LiteLLM](https://github.com/BerriAI/litellm), so you can freely mix cloud APIs (OpenAI/GPT, Anthropic/Claude, Google/Gemini, xAI/Grok) and local open-weight models (via Ollama or vLLM) with the exact same code. **No platform fee** — you pay only the model APIs you use, or nothing at all when running local models.

## The Górale naming

| Name | Meaning in Podhale | Role in Baca |
|------|--------------------|--------------|
| **Baca** | Master shepherd who leads the flock | The coordinator / herder |
| **Juhas** | Shepherd's assistant under the baca | Each worker LLM in the council |
| **Redyk** | Seasonal drive of the sheep up the mountain | One fan-out run (task → all juhasi) |
| **Narada** | Deliberation / council meeting | Critique round before synthesis |
| **Bacówka** | Wooden shepherd's hut | The config home (`models.yaml`) |
| **Gazda** | Homestead farmer / manager | The chairman model that merges answers |
| **Oscypek** | Traditional smoked sheep cheese | The final synthesized answer |

## Why

Different models have different strengths and blind spots. Asking several of them and synthesizing the best answer beats trusting any single one — especially for writing, review, and reasoning tasks.

## How it works

```
         ┌──────────┐
task ──► │   Baca   │
         └────┬─────┘
       redyk  │  (parallel)
     ┌─────────┼─────────┐
     ▼         ▼         ▼
   GPT      Claude    Gemini     ← the juhasi
     └─────────┼─────────┘
               ▼
            Gazda                ← presses into one oscypek
               ▼
           oscypek
```

Three modes:
- **`redyk`** (default) — every juhas answers, the gazda synthesizes one oscypek.
- **`narada`** — adds a round where each juhas critiques the others' (anonymized) drafts before the gazda synthesizes. Slower, higher quality.
- **`raw`** — just show every juhas's answer side by side (no synthesis).

Built-in resilience: automatic retry/backoff on rate limits, and per-juhas **fallback chains** so an overloaded model is swapped for a working one automatically.

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

| Juhas  | Env var             | Where to get a key                              | Cost |
|--------|---------------------|-------------------------------------------------|------|
| Gemini | `GEMINI_API_KEY`    | https://aistudio.google.com/apikey              | Free tier available |
| Claude | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys     | Prepaid credit (Billing) |
| GPT    | `OPENAI_API_KEY`    | https://platform.openai.com/api-keys            | Prepaid credit (Billing) |
| Grok   | `XAI_API_KEY`       | https://console.x.ai                            | Paid |

> **Note:** API access is separate from any chat subscription (ChatGPT Plus, Claude Pro, etc.). You need an **API key** and, for OpenAI/Anthropic, a small prepaid balance. A school/work account behind SSO often can't create API keys — use a personal account.

### 4. Turn on the juhasi you have keys for
Open the bacówka (`models.yaml`) and set `enabled: true` for each juhas whose key you added. Leave the rest `false`.

### 5. Run it
```bash
# one-off task (redyk → gazda → oscypek)
python baca.py "Summarize the pros and cons of microservices in 5 bullets"

# from a file, with a narada first
python baca.py --file draft.md --mode narada

# pipe it in
echo "Explain SSRF to a junior dev" | python baca.py

# see every juhas's raw answer
python baca.py "Capital of Poland + one fact" --mode raw
```

## Configuration (the bacówka — `models.yaml`)

```yaml
system: "You are a sharp, concise expert. Be accurate and specific; do not pad."

juhasi:
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

gazda:                            # presses the juhasi's answers into the oscypek
  name: Gazda
  model: gemini/gemini-3.5-flash
  temperature: 0.4
```

- **`model`** uses LiteLLM's `provider/model` naming — see the [LiteLLM provider list](https://docs.litellm.ai/docs/providers). Model names change often; list what your key can reach (see below).
- **`enabled`** — flip a juhas on/off without deleting it.
- **`fallbacks`** — optional ordered list of backup models used if the primary returns a transient error (429/503).
- **`gazda`** — can be any model; it writes the final oscypek.

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

Add a local juhas to the bacówka (no API key needed):
```yaml
  - name: Llama-local
    model: ollama/llama3.1
    enabled: true
    temperature: 0.7
```

The herder code doesn't change — only the bacówka. You can mix cloud and local juhasi in the same redyk, and phase out the paid ones as local models improve.

## Cost notes

- A short redyk (a few thousand tokens) is typically well under $0.01–$0.10.
- A long task (e.g. cleaning up a full paper) with three cloud juhasi might run a few dollars.
- `narada` mode roughly doubles token use vs `redyk` (extra critique round).
- Gemini's free tier and local Ollama models cost nothing.

## Inspiration & credits

The naming is drawn from the traditional **Górale (Highlander) crafts and pastoral professions** of Zakopane and the surrounding Podhale region — trades rooted in mountain living that are still practiced today.

- **Baca** — the master shepherd who leads seasonal sheep grazing (*redyk*) in the Tatra pastures and oversees production of smoked sheep cheeses (*oscypek*, *bundz*, *bryndza*) in wooden shepherd's huts (*bacówki*).
- **Juhas** — the shepherd's assistant who tends the flock under the baca.
- **Gazda** — the homestead farmer who manages the mountain farm and brings it all together.

Sources on Górale trades and culture that informed this naming:
- [Visit Małopolska — Tatry i Podhale](https://visitmalopolska.pl/-/tatry-i-podhale-zywiolowy-folklor-goralski)
- [Sery Góralskie — Tradycje górali](https://serygoralskie.pl/realizacja/tradycje-gorali-poznaj-ich-kulture.html)
- [HelloCracow — Echoes of Zakopane](https://www.hellocracow.com/echoes-of-zakopane-highlander-culture-wooden-villas-and-mountain-myths)
- [Zakopane Travel — Górale](https://www.zakopanetravel.com/gorals/)
- [Tatry Przewodnik — Tradycyjne zawody góralskie](https://www.tatry-przewodnik.com.pl/blog/?tradycyjne-zawody-goralskie)
- [Etnozagroda — Górale podhalańscy](https://www.etnozagroda.pl/gorale-podhalanscy)
- [Ginące zawody](https://www.ginace-zawody.watra.pl/)

The multi-model "council then chairman" pattern itself was inspired in part by [Andrej Karpathy's llm-council](https://github.com/karpathy/llm-council) (a local ChatGPT-like app where several models answer, peer-rank, and a chairman synthesizes). Baca takes that idea, keeps it self-hosted via LiteLLM (no aggregator lock-in), and dresses it in Podhale clothes.

## License

MIT
