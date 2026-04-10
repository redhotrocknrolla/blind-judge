#!/usr/bin/env python3
"""
E2E тест — полный путь от input до final_verdict с моком LLM.
Prolog-ядро работает реально (subprocess), LLM замокан.
"""

import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from judge import audit

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

CONFIG = {
    "llm": {
        "base_url": "https://api.anthropic.com",
        "api_key": "test-key",
        "model": "claude-haiku-4-5",
        "max_tokens": 4096,
    },
    "parser": {"max_retries": 2, "double_check": False}
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def mock_response(content: dict):
    msg = MagicMock()
    msg.content = json.dumps(content, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def make_final_verdict(fixture: dict) -> dict:
    """Строим валидный final_verdict для мока формулировщика."""
    vr = fixture["expected_verdict_raw"]
    ef = fixture["expected_final"]
    return {
        "schema_version": "1.0",
        "request_id": vr["request_id"],
        "verdict": ef["verdict"],
        "confidence": vr["core_confidence"],
        "issues": ef["issues"],
        "alternative_hypothesis": "Альтернативная гипотеза." if ef.get("alternative_hypothesis_required") else None,
        "feedback": "Feedback." if ef["verdict"] != "APPROVE" else "",
        "trace": {
            "rules_fired": [i["triggered_by"]["rule"] for i in vr["issues"]],
            "parser_warnings": vr["parser_meta_passthrough"]["warnings"],
            "core_confidence": vr["core_confidence"],
            "mode": ef["trace_mode"]
        }
    }


class TestE2E(unittest.TestCase):

    def _run(self, fixture_name: str):
        fixture = load_fixture(fixture_name)
        input_data = fixture["input"]
        parsed_facts = fixture["expected_parsed_facts"]
        final = make_final_verdict(fixture)

        with patch("parser.bj_parser.OpenAI") as MockParser, \
             patch("formulator.formulator.OpenAI") as MockFormulator:

            MockParser.return_value.chat.completions.create.return_value = mock_response(parsed_facts)
            MockFormulator.return_value.chat.completions.create.return_value = mock_response(final)

            result = audit(input_data, CONFIG)

        return result, fixture["expected_final"]

    def test_001_full_path(self):
        result, ef = self._run("001_redis_loop.json")
        self.assertEqual(result["verdict"], ef["verdict"])
        self.assertEqual(sorted(result["issues"]), sorted(ef["issues"]))
        self.assertEqual(result["trace"]["mode"], ef["trace_mode"])

    def test_002_full_path(self):
        result, ef = self._run("002_medical_weak_evidence.json")
        self.assertEqual(result["verdict"], ef["verdict"])
        self.assertEqual(sorted(result["issues"]), sorted(ef["issues"]))

    def test_003_full_path(self):
        result, ef = self._run("003_planning_uncovered_requirement.json")
        self.assertEqual(result["verdict"], ef["verdict"])
        self.assertEqual(sorted(result["issues"]), sorted(ef["issues"]))

    def test_004_full_path(self):
        result, ef = self._run("004_code_clean_approve.json")
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["feedback"], "")

    def test_006_full_path(self):
        result, ef = self._run("006_parser_low_confidence_guard.json")
        self.assertEqual(result["verdict"], "ESCALATE")
        self.assertEqual(result["issues"], [])

    def test_005_legacy_mode(self):
        """Фикстура 005 — abstain=true, должен уйти в legacy."""
        fixture = load_fixture("005_aesthetic_abstain.json")
        input_data = fixture["input"]
        parsed_facts = fixture["expected_parsed_facts"]

        legacy_response = {
            "verdict": "ESCALATE",
            "feedback": "Эстетическое суждение субъективно.",
            "issues": []
        }

        with patch("parser.bj_parser.OpenAI") as MockParser, \
             patch("judge.OpenAI") as MockLegacy:

            MockParser.return_value.chat.completions.create.return_value = mock_response(parsed_facts)
            MockLegacy.return_value.chat.completions.create.return_value = mock_response(legacy_response)

            result = audit(input_data, CONFIG)

        self.assertEqual(result["trace"]["mode"], "legacy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
