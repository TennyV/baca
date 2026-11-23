#!/usr/bin/env python3
"""
Baca — a multi-LLM herder, themed after the Górale (Polish Highlander) trades.

A baca (master shepherd) leads the seasonal drive — the *redyk* — sending the
flock out with his *juhasi* (shepherd's assistants). Here each juhas is a large
language model. They all work the same task in parallel; then the *gazda*
(homestead manager) presses their work into one finished answer — the *oscypek*.

Every model is reached through LiteLLM, so you can mix cloud APIs (OpenAI,
Anthropic, Gemini, xAI/Grok) and local open-weight models (Ollama/vLLM) with
the same code. No platform fee: you pay only the model APIs, or nothing if local.

Config lives in the bacówka (models.yaml). API keys come from the environment
(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY).

Usage:
    python baca.py "Clean up the intro of my paper"
    python baca.py --file draft.md --mode narada
    echo "prompt" | python baca.py --mode redyk
"""
import argparse
import concurrent.futures
import os
import sys
import textwrap
import time

try:
    import litellm
    from litellm import completion
    litellm.drop_params = True  # tolerate models that reject params like temperature
    litellm.suppress_debug_info = True
    import logging; logging.getLogger("LiteLLM").setLevel(logging.ERROR)
except ImportError:
    sys.exit("litellm not installed. Run: pip install litellm")

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def load_bacowka(path=None):
    """Load the bacówka (config): the juhasi and the gazda."""
    path = path or os.path.join(HERE, "models.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def _one_call(model, messages, temperature, timeout, retries):
    """Call a single model with backoff on transient errors. Raises on final failure."""
    last = None
    for attempt in range(retries + 1):
        try:
            resp = completion(model=model, messages=messages,
                              temperature=temperature, timeout=timeout)
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001
            last = e
            transient = any(c in str(e) for c in ("503", "429", "UNAVAILABLE", "overloaded", "high demand"))
            if transient and attempt < retries:
                time.sleep(1.5 * (2 ** attempt))
                continue
            raise
    raise last


def ask_juhas(juhas, prompt, system=None, retries=3):
    """Send one juhas (model) out with the task. Tries its model then any
    'fallbacks'. Returns (name, text) or (name, '[error] ...')."""
    name = juhas["name"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    models = [juhas["model"]] + list(juhas.get("fallbacks", []))
    temperature = juhas.get("temperature", 0.7)
    timeout = juhas.get("timeout", 120)
    last = None
    for model in models:
        try:
            return name, _one_call(model, messages, temperature, timeout, retries)
        except Exception as e:  # noqa: BLE001 - try next fallback
            last = e
            continue
    return name, f"[error] {type(last).__name__}: {last}"


def redyk(juhasi, prompt, system=None):
    """The redyk: send every enabled juhas out on the task in parallel.
    Returns dict name -> text."""
    flock = [j for j in juhasi if j.get("enabled", True)]
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(flock))) as ex:
        futures = {ex.submit(ask_juhas, j, prompt, system): j for j in flock}
        for fut in concurrent.futures.as_completed(futures):
            name, text = fut.result()
            out[name] = text
    return out


def format_answers(answers):
    return "\n\n".join(f"### {name}\n{text}" for name, text in answers.items())


def narada(juhasi, prompt, answers):
    """A narada (deliberation): each juhas sees the others' anonymized drafts,
    critiques them, and returns an improved answer."""
    labeled = {f"Answer {i+1}": t for i, t in enumerate(answers.values())}
    pool = "\n\n".join(f"### {k}\n{v}" for k, v in labeled.items())
    crit_prompt = textwrap.dedent(f"""\
        Original task:
        {prompt}

        Here are anonymous draft answers from a panel. Critique them, point out
        errors or gaps, and produce your own improved answer to the original task.

        {pool}
    """)
    return redyk(juhasi, crit_prompt)


def press_oscypek(gazda, prompt, answers):
    """The gazda presses the juhasi's work into one finished answer — the oscypek."""
    pool = format_answers(answers)
    syn_prompt = textwrap.dedent(f"""\
        You are the gazda — the head of a panel of AI models. The original task was:

        {prompt}

        The panel produced these answers:

        {pool}

        Write the single best final answer to the original task. Merge the
        strongest points, resolve disagreements, drop anything wrong or redundant.
        Do not mention the panel or that multiple models were involved. Just give
        the final answer.
    """)
    _, text = ask_juhas(gazda, syn_prompt)
    return text


def run(prompt, mode, cfg):
    juhasi = cfg["juhasi"]
    gazda = cfg["gazda"]
    system = cfg.get("system")

    n = len([j for j in juhasi if j.get("enabled", True)])
    print(f"[baca] sending the redyk out to {n} juhasi...", file=sys.stderr)
    answers = redyk(juhasi, prompt, system)

    if mode == "narada":
        print("[baca] narada — the juhasi critique each other...", file=sys.stderr)
        answers = narada(juhasi, prompt, answers)

    if mode in ("redyk", "narada"):
        print("[baca] the gazda presses the oscypek...", file=sys.stderr)
        return press_oscypek(gazda, prompt, answers)

    # mode == raw: just show every juhas's answer
    return format_answers(answers)


def main():
    ap = argparse.ArgumentParser(description="Baca — a multi-LLM herder")
    ap.add_argument("prompt", nargs="?", help="The task. Or use --file, or pipe stdin.")
    ap.add_argument("--file", help="Read the task from a file.")
    ap.add_argument("--mode", default="redyk",
                    choices=["redyk", "narada", "raw"],
                    help="redyk: fan-out + gazda synthesizes (default). "
                         "narada: + a critique round first. "
                         "raw: show every juhas's answer, no synthesis.")
    ap.add_argument("--config", help="Path to the bacówka (models.yaml)")
    args = ap.parse_args()

    if args.file:
        with open(args.file) as f:
            prompt = f.read()
    elif args.prompt:
        prompt = args.prompt
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        ap.error("Give a prompt, --file, or pipe it on stdin.")

    cfg = load_bacowka(args.config)
    print(run(prompt, args.mode, cfg))


if __name__ == "__main__":
    main()
