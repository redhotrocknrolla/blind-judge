#!/usr/bin/env python3
"""
Blind Judge — Parser
Вызывает LLM клиента (OpenAI-совместимый интерфейс), валидирует выход по JSON Schema.
"""

import json
import sys
import re
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent.parent.parent
PROMPT_PATH = Path(__file__).parent / "prompts" / "parser_v1.md"
SCHEMA_PATH = ROOT / "schemas" / "parsed_facts.schema.json"


def _call_llm(llm_cfg: dict, prompt: str) -> str:
    """Вызывает LLM: anthropic SDK если base_url содержит 'anthropic.com', иначе openai SDK."""
    base_url = llm_cfg["base_url"]
    api_key = llm_cfg["api_key"]
    model = llm_cfg["model"]
    max_tokens = llm_cfg.get("max_tokens", 4096)

    if "anthropic.com" in base_url:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def build_prompt(template: str, input_json: dict) -> str:
    return template.replace("{{INPUT_JSON}}", json.dumps(input_json, ensure_ascii=False, indent=2))


def extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


def parse(input_data: dict, config: dict) -> dict:
    llm_cfg = config["llm"]
    parser_cfg = config["parser"]
    max_retries = parser_cfg.get("max_retries", 2)

    prompt_template = load_prompt()
    schema = load_schema()
    prompt = build_prompt(prompt_template, input_data)

    last_error = None
    for attempt in range(1, max_retries + 2):
        try:
            raw_text = _call_llm(llm_cfg, prompt)
            result = extract_json(raw_text)

            if result.get("schema_version") != "1.0":
                raise ValueError(f"schema_version mismatch: {result.get('schema_version')}")

            jsonschema.validate(instance=result, schema=schema)
            return result

        except (json.JSONDecodeError, jsonschema.ValidationError, ValueError) as e:
            last_error = e
            if attempt <= max_retries:
                print(f"[parser] attempt {attempt} failed: {e}. Retrying...", file=sys.stderr)

    print(f"[parser] all attempts failed. Returning abstain. Last error: {last_error}", file=sys.stderr)
    return _make_abstain(input_data, llm_cfg["model"], str(last_error))


def _make_abstain(input_data: dict, model: str, reason: str) -> dict:
    return {
        "schema_version": "1.0",
        "request_id": input_data.get("request_id", ""),
        "task_analysis": {
            "task_type": "other",
            "formalizable": False,
            "requirements": []
        },
        "claims": [],
        "evidence": [],
        "requirement_coverage": [],
        "action_patterns": {
            "total_actions": len(input_data.get("actions", [])),
            "unique_actions": 0,
            "repeated_groups": []
        },
        "alternatives_considered": {
            "explicit_alternatives_in_conclusion": 0,
            "contradicting_evidence_addressed": False,
            "parser_confidence": 0.0
        },
        "parser_meta": {
            "model": model,
            "min_confidence": 0.0,
            "warnings": ["parser_failed"],
            "abstain": True,
            "abstain_reason": reason
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parser.py <input.json> [--pretty]", file=sys.stderr)
        sys.exit(1)

    from config import load_config
    sys.path.insert(0, str(Path(__file__).parent.parent))

    cfg = load_config()
    pretty = "--pretty" in sys.argv

    with open(sys.argv[1], encoding="utf-8") as f:
        input_data = json.load(f)

    result = parse(input_data, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2 if pretty else None))
