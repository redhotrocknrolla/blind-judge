#!/usr/bin/env python3
"""
Blind Judge — Orchestrator
Склейка: parser → core → formulator. Legacy fallback при abstain.
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from parser.bj_parser import parse
from core.run_core import run_core
from formulator.formulator import formulate
from openai import OpenAI


def audit(input_data: dict, config: dict = None, user_rules: str = None) -> dict:
    if config is None:
        config = load_config()

    parsed_facts = parse(input_data, config)

    if parsed_facts["parser_meta"]["abstain"]:
        return _legacy_audit(input_data, parsed_facts, config)

    verdict_raw = run_core(parsed_facts, user_rules=user_rules)
    final_verdict = formulate(input_data, verdict_raw, config)
    return final_verdict


def _load_legacy_prompt() -> str:
    prompt_path = Path(__file__).parent / "legacy" / "legacy_judge_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


def _legacy_audit(input_data: dict, parsed_facts: dict, config: dict) -> dict:
    llm_cfg = config["llm"]
    client = OpenAI(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"])

    facts = [i["text"] for i in input_data.get("inputs", [])]
    tool_trace = [
        {"name": a["name"], "args": a.get("args", {})}
        for a in input_data.get("actions", [])
    ]
    stripped = {
        "task": input_data.get("task", ""),
        "facts": facts,
        "conclusion": input_data.get("conclusion", ""),
        "tool_trace": tool_trace
    }

    legacy_skill = _load_legacy_prompt()
    json_schema = '{"verdict": "APPROVE|ESCALATE|REJECT", "confidence": 0.0, "issues": [], "alternative_hypothesis": null, "feedback": ""}'
    prompt = (
        legacy_skill
        + "\n\n---\n\n"
        + "Входные данные для анализа:\n\n"
        + f"```json\n{json.dumps(stripped, ensure_ascii=False, indent=2)}\n```\n\n"
        + "Верни результат строго в формате JSON без преамбулы:\n"
        + json_schema
    )

    try:
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            text = match.group(1)
        legacy_result = json.loads(text)
    except Exception as e:
        legacy_result = {"verdict": "ESCALATE", "feedback": str(e), "issues": []}

    return {
        "schema_version": "1.0",
        "request_id": input_data.get("request_id", ""),
        "verdict": legacy_result.get("verdict", "ESCALATE"),
        "confidence": legacy_result.get("confidence", 0.5),
        "issues": legacy_result.get("issues", []),
        "alternative_hypothesis": legacy_result.get("alternative_hypothesis"),
        "feedback": legacy_result.get("feedback", ""),
        "trace": {
            "rules_fired": [],
            "parser_warnings": parsed_facts["parser_meta"].get("warnings", []),
            "core_confidence": legacy_result.get("confidence", 0.5),
            "mode": "legacy"
        }
    }
