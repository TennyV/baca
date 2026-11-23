#!/usr/bin/env python3
"""
Baca — a multi-LLM "herder".

Fans one task out to several models in parallel (the council), optionally lets
them critique each other, then a chairman model synthesizes a single answer.

Talks to every model through LiteLLM, so you can mix cloud APIs (OpenAI,
Anthropic, Gemini, xAI/Grok) and local open-weight models (Ollama/vLLM) with
the same code. No platform fee: you pay only the model APIs, or nothing if local.

Usage:
    python baca.py "Clean up the intro of my paper" --mode ensemble
    python baca.py --file draft.md --mode council
    echo "prompt" | python baca.py --mode ensemble

Config lives in models.yaml. API keys come from the environment
(OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY).
"""
import argparse
import concurrent.futures
import os
import sys
import textwrap
import time

import yaml

try:
    import litellm
    from litellm import completion
    litellm.drop_params = True  # tolerate models that reject params like temperature
    litellm.suppress_debug_info = True
    import logging; logging.getLogger("LiteLLM").setLevel(logging.ERROR)
except ImportError:
    sys.exit("litellm not installed. Run: pip install litellm")

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path=None):
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


def ask(member, prompt, system=None, retries=3):
    """Query one council member. Tries member['model'] then any member['fallbacks'].
    Returns (name, text) or (name, '[error] ...')."""
    name = member["name"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    models = [member["model"]] + list(member.get("fallbacks", []))
    temperature = member.get("temperature", 0.7)
    timeout = member.get("timeout", 120)
    last = None
    for model in models:
        try:
            return name, _one_call(model, messages, temperature, timeout, retries)
        except Exception as e:  # noqa: BLE001 - try next fallback
            last = e
            continue
    return name, f"[error] {type(last).__name__}: {last}"


def fan_out(members, prompt, system=None):
    """Query all enabled members in parallel. Returns dict name -> text."""
    enabled = [m for m in members if m.get("enabled", True)]
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(enabled))) as ex:
        futures = {ex.submit(ask, m, prompt, system): m for m in enabled}
        for fut in concurrent.futures.as_completed(futures):
            name, text = fut.result()
            out[name] = text
    return out


def format_answers(answers):
    blocks = []
    for name, text in answers.items():
        blocks.append(f"### {name}\n{text}")
    return "\n\n".join(blocks)


def critique_round(members, prompt, answers):
    """Each member sees the others' (anonymized) answers and critiques/improves."""
    labeled = {f"Answer {i+1}": t for i, t in enumerate(answers.values())}
    pool = "\n\n".join(f"### {k}\n{v}" for k, v in labeled.items())
    crit_prompt = textwrap.dedent(f"""\
        Original task:
        {prompt}

        Here are anonymous draft answers from a panel. Critique them, point out
        errors or gaps, and produce your own improved answer to the original task.

        {pool}
    """)
    return fan_out(members, crit_prompt)


def synthesize(chairman, prompt, answers):
    pool = format_answers(answers)
    syn_prompt = textwrap.dedent(f"""\
        You are the chairman of a panel of AI models. The original task was:

        {prompt}

        The panel produced these answers:

        {pool}

        Write the single best final answer to the original task. Merge the
        strongest points, resolve disagreements, drop anything wrong or redundant.
        Do not mention the panel or that multiple models were involved. Just give
        the final answer.
    """)
    _, text = ask(chairman, syn_prompt)
    return text


def run(prompt, mode, cfg):
    members = cfg["council"]
    chairman = cfg["chairman"]
    system = cfg.get("system")

    print(f"[baca] fanning out to {len([m for m in members if m.get('enabled', True)])} models...", file=sys.stderr)
    answers = fan_out(members, prompt, system)

    if mode == "council":
        print("[baca] critique round...", file=sys.stderr)
        answers = critique_round(members, prompt, answers)

    if mode in ("ensemble", "council"):
        print("[baca] chairman synthesizing...", file=sys.stderr)
        return synthesize(chairman, prompt, answers)

    # mode == raw: just show everyone's answers
    return format_answers(answers)


def main():
    ap = argparse.ArgumentParser(description="Baca — multi-LLM herder")
    ap.add_argument("prompt", nargs="?", help="The task. Or use --file, or pipe stdin.")
    ap.add_argument("--file", help="Read the task from a file.")
    ap.add_argument("--mode", default="ensemble",
                    choices=["ensemble", "council", "raw"],
                    help="ensemble: fan-out + synthesize. council: + critique round. raw: show all answers.")
    ap.add_argument("--config", help="Path to models.yaml")
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

    cfg = load_config(args.config)
    print(run(prompt, args.mode, cfg))


if __name__ == "__main__":
    main()
