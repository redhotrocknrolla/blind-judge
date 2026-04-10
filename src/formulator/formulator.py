#!/usr/bin/env python3
"""
Blind Judge — Formulator
Принимает verdict_raw + original input, генерирует final_verdict через LLM клиента.
"""

import json
import sys
import re
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent.parent.parent
PROMPT_PATH = Path(__file__).parent / "prompts" / "formulator_v1.md"
SCHEMA_PATH = ROOT / "schemas" / "final_verdict.schema.json"


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


def build_prompt(template: str, input_data: dict, verdict_raw: dict) -> str:
    return template \
        .replace("{{INPUT_JSON}}", json.dumps(input_data, ensure_ascii=False, indent=2)) \
        .replace("{{VERDICT_RAW_JSON}}", json.dumps(verdict_raw, ensure_ascii=False, indent=2))


def extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


def validate_structural_fields(result: dict, verdict_raw: dict) -> None:
    """Проверяем что формулировщик не поменял структурные поля."""
    expected_verdict = verdict_raw["final_verdict"].upper()
    if result["verdict"] != expected_verdict:
        raise ValueError(
            f"Formulator changed verdict: {result['verdict']} != {expected_verdict}"
        )

    if abs(result["confidence"] - verdict_raw["core_confidence"]) > 0.001:
        raise ValueError(
            f"Formulator changed confidence: {result['confidence']} != {verdict_raw['core_confidence']}"
        )

    expected_issues = [i["code"] for i in verdict_raw["issues"]]
    if sorted(result["issues"]) != sorted(expected_issues):
        raise ValueError(
            f"Formulator changed issues: {result['issues']} != {expected_issues}"
        )


def formulate(input_data: dict, verdict_raw: dict, config: dict) -> dict:
    llm_cfg = config["llm"]
    max_retries = config.get("parser", {}).get("max_retries", 2)

    prompt_template = load_prompt()
    schema = load_schema()
    prompt = build_prompt(prompt_template, input_data, verdict_raw)

    last_error = None
    for attempt in range(1, max_retries + 2):
        try:
            raw_text = _call_llm(llm_cfg, prompt)
            result = extract_json(raw_text)

            if result.get("schema_version") != "1.0":
                raise ValueError(f"schema_version mismatch: {result.get('schema_version')}")

            jsonschema.validate(instance=result, schema=schema)
            validate_structural_fields(result, verdict_raw)

            return result

        except (json.JSONDecodeError, jsonschema.ValidationError, ValueError) as e:
            last_error = e
            if attempt <= max_retries:
                print(f"[formulator] attempt {attempt} failed: {e}. Retrying...", file=sys.stderr)

    print(f"[formulator] all attempts failed. Returning fallback. Last error: {last_error}", file=sys.stderr)
    return _make_fallback(verdict_raw)


def _make_fallback(verdict_raw: dict) -> dict:
    """Если формулировщик сломался — возвращаем минимальный валидный ответ."""
    verdict = verdict_raw["final_verdict"].upper()
    return {
        "schema_version": "1.0",
        "request_id": verdict_raw["request_id"],
        "verdict": verdict,
        "confidence": verdict_raw["core_confidence"],
        "issues": [i["code"] for i in verdict_raw["issues"]],
        "alternative_hypothesis": None,
        "feedback": "" if verdict == "APPROVE" else "Формулировщик недоступен. См. issues.",
        "trace": {
            "rules_fired": [i["triggered_by"]["rule"] for i in verdict_raw["issues"]],
            "parser_warnings": verdict_raw["parser_meta_passthrough"]["warnings"],
            "core_confidence": verdict_raw["core_confidence"],
            "mode": "hybrid"
        }
    }
