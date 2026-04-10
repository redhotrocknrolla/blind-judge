#!/usr/bin/env python3
"""
Тест пользовательских правил — проверяем что user_rules подключаются
и добавляют новые issues не ломая базовые.
"""

import sys
import json
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.run_core import run_core

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class TestUserRules(unittest.TestCase):

    def test_base_rules_work_without_user_rules(self):
        """Базовые правила работают без user_rules."""
        fixture = json.loads((FIXTURES / "001_redis_loop.json").read_text())
        result = run_core(fixture["expected_parsed_facts"])
        self.assertEqual(result["final_verdict"], "reject")
        codes = [i["code"] for i in result["issues"]]
        self.assertIn("process_loop", codes)

    def test_user_rules_add_issues(self):
        """Пользовательское правило добавляет новый issue."""
        fixture = json.loads((FIXTURES / "002_medical_weak_evidence.json").read_text())

        custom_rule = """
:- multifile issue/1.
issue(test_custom_issue) :-
    task_type(research).
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pl", delete=False, encoding="utf-8"
        ) as f:
            f.write(custom_rule)
            rules_path = f.name

        try:
            result = run_core(fixture["expected_parsed_facts"], user_rules=rules_path)
            codes = [i["code"] for i in result["issues"]]
            self.assertIn("test_custom_issue", codes)
            # Базовые issues тоже на месте
            self.assertIn("weak_evidence", codes)
        finally:
            Path(rules_path).unlink(missing_ok=True)

    def test_user_rules_cannot_remove_base_issues(self):
        """Пользовательские правила не могут удалить базовые issues."""
        fixture = json.loads((FIXTURES / "001_redis_loop.json").read_text())

        # Попытка переопределить — Prolog discontiguous просто добавит клоз,
        # базовый issue(process_loop) останется
        malicious_rule = """
:- multifile issue/1.
issue(process_loop) :- fail.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pl", delete=False, encoding="utf-8"
        ) as f:
            f.write(malicious_rule)
            rules_path = f.name

        try:
            result = run_core(fixture["expected_parsed_facts"], user_rules=rules_path)
            codes = [i["code"] for i in result["issues"]]
            # process_loop должен остаться — базовый клоз всё ещё работает
            self.assertIn("process_loop", codes)
        finally:
            Path(rules_path).unlink(missing_ok=True)

    def test_medical_example_rules(self):
        """Пример medical_research.pl добавляет missing_rct на фикстуре 002."""
        fixture = json.loads((FIXTURES / "002_medical_weak_evidence.json").read_text())
        rules_path = ROOT / "src" / "examples" / "user_rules" / "medical_research.pl"

        result = run_core(fixture["expected_parsed_facts"], user_rules=str(rules_path))
        codes = [i["code"] for i in result["issues"]]
        self.assertIn("missing_rct", codes)
        # Базовые тоже на месте
        self.assertIn("weak_evidence", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
