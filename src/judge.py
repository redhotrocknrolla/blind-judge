#!/usr/bin/env python3
"""
Blind Judge — Orchestrator
Склейка: parser → core → formulator. Legacy fallback при abstain.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from parser.bj_parser import parse
from core.run_core import run_core
from formulator.formulator import formulate
from openai import OpenAI


def audit(input_data: dict, config: dict = None) -> dict:
    """Главная точка входа. Возвращает final_verdict."""
    if config is None:
        config = load_config()

    # Шаг 1: парсер
    parsed_facts = parse(input_data, config)

    # Шаг 2: если abstain — legacy режим
    if parsed_facts["parser_meta"]["abstain"]:
        return _legacy_audit(input_data, parsed_facts, config)

    # Шаг 3: Prolog-ядро
    verdict_raw = run_core(parsed_facts)

    # Шаг 4: формулировщик
    final_verdict = formulate(input_data, verdict_raw, config)

    return final_verdict


def _legacy_audit(input_data: dict, parsed_facts: dict, config: dict) -> dict:
    """
    Legacy-режим для нефоpмализуемых задач.
    Вызывает LLM напрямую как монолитного судью.
    """
    import json

    llm_cfg = config["llm"]
    client = OpenAI(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"])

    legacy_prompt = (
        "Ты — независимый судья качества ответов AI-агентов. "
        "Оцени следующий ответ агента и вынеси вердикт: APPROVE, ESCALATE или REJECT.\n\n"
        f"Задача: {input_data.get('task', '')}\n\n"
        f"Вывод агента: {input_data.get('conclusion', '')}\n\n"
        "Верни JSON:\n"
        '{"verdict": "APPROVE|ESCALATE|REJECT", "feedback": "...", "issues": []}'
    )

    try:
        response = client.chat.completions.create(
            model=llm_cfg["model"],
            max_tokens=1024,
            messages=[{"role": "user", "content": legacy_prompt}]
        )
        import re
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
        "confidence": 0.5,
        "issues": legacy_result.get("issues", []),
        "alternative_hypothesis": None,
        "feedback": legacy_result.get("feedback", ""),
        "trace": {
            "rules_fired": [],
            "parser_warnings": parsed_facts["parser_meta"].get("warnings", []),
            "core_confidence": 0.5,
            "mode": "legacy"
        }
    }
