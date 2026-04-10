#!/usr/bin/env python3
"""
Blind Judge — Core Bridge (CLI mode)

Тонкая обёртка над Prolog-ядром для использования в CLI-режиме,
где модель сама выполняет роль парсера и формулировщика.

Принимает parsed_facts (подготовленный моделью CLI),
прогоняет через Prolog subprocess,
возвращает verdict_raw (структурный вердикт для модели CLI).

Схема CLI-режима:
  [модель читает parser_v1.md]
        ↓ parsed_facts
  judge_core.run(parsed_facts)
        ↓ verdict_raw
  [модель читает formulator_v1.md]
        ↓ final_verdict
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.run_core import run_core


def run(parsed_facts: dict, user_rules: str = None) -> dict:
    """
    Запустить Prolog-ядро на готовых parsed_facts.

    Args:
        parsed_facts: JSON-объект по схеме parsed_facts.schema.json,
                      подготовленный моделью CLI из parser_v1.md промпта.
        user_rules:   Опциональный путь к .pl файлу с пользовательскими правилами.

    Returns:
        verdict_raw: структурный вердикт для передачи в formulator_v1.md промпт.
    """
    return run_core(parsed_facts, user_rules=user_rules)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: judge_core.py <parsed_facts.json> [--user-rules path.pl]",
            file=sys.stderr,
        )
        sys.exit(1)

    user_rules = None
    if "--user-rules" in sys.argv:
        idx = sys.argv.index("--user-rules")
        user_rules = sys.argv[idx + 1]

    with open(sys.argv[1], encoding="utf-8") as f:
        parsed_facts = json.load(f)

    verdict_raw = run(parsed_facts, user_rules=user_rules)
    print(json.dumps(verdict_raw, ensure_ascii=False, indent=2))
