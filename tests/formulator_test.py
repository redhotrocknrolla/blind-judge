#!/usr/bin/env python3
"""
Тест формулировщика на фикстурах с моком LLM.
"""

import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from formulator.formulator import formulate, validate_structural_fields, _make_fallback

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

MOCK_CONFIG = {
    "llm": {
        "base_url": "https://api.anthropic.com",
        "api_key": "test-key",
        "model": "claude-haiku-4-5",
        "max_tokens": 4096,
    },
    "parser": {"max_retries": 2}
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_final_verdict(fixture: dict) -> dict:
    """Строим валидный final_verdict из expected_verdict_raw фикстуры."""
    vr = fixture["expected_verdict_raw"]
    ef = fixture["expected_final"]
    return {
        "schema_version": "1.0",
        "request_id": vr["request_id"],
        "verdict": ef["verdict"],
        "confidence": vr["core_confidence"],
        "issues": [i["code"] for i in vr["issues"]],
        "alternative_hypothesis": "Тестовая альтернативная гипотеза." if ef.get("alternative_hypothesis_required") else None,
        "feedback": "Тестовый feedback." if ef["verdict"] != "APPROVE" else "",
        "trace": {
            "rules_fired": [i["triggered_by"]["rule"] for i in vr["issues"]],
            "parser_warnings": vr["parser_meta_passthrough"]["warnings"],
            "core_confidence": vr["core_confidence"],
            "mode": "hybrid"
        }
    }


def mock_llm_response(final_verdict: dict) -> str:
    """Возвращает строку JSON — то, что возвращает _call_llm."""
    return json.dumps(final_verdict, ensure_ascii=False)


class TestStructuralValidation(unittest.TestCase):

    def test_verdict_mismatch_raises(self):
        verdict_raw = {
            "final_verdict": "reject",
            "core_confidence": 0.17,
            "issues": []
        }
        result = {"verdict": "APPROVE", "confidence": 0.17, "issues": []}
        with self.assertRaises(ValueError):
            validate_structural_fields(result, verdict_raw)

    def test_confidence_mismatch_raises(self):
        verdict_raw = {
            "final_verdict": "reject",
            "core_confidence": 0.17,
            "issues": []
        }
        result = {"verdict": "REJECT", "confidence": 0.99, "issues": []}
        with self.assertRaises(ValueError):
            validate_structural_fields(result, verdict_raw)

    def test_issues_mismatch_raises(self):
        verdict_raw = {
            "final_verdict": "reject",
            "core_confidence": 0.17,
            "issues": [{"code": "process_loop"}]
        }
        result = {"verdict": "REJECT", "confidence": 0.17, "issues": []}
        with self.assertRaises(ValueError):
            validate_structural_fields(result, verdict_raw)

    def test_valid_passes(self):
        verdict_raw = {
            "final_verdict": "reject",
            "core_confidence": 0.17,
            "issues": [{"code": "process_loop"}]
        }
        result = {"verdict": "REJECT", "confidence": 0.17, "issues": ["process_loop"]}
        validate_structural_fields(result, verdict_raw)  # не должно бросить


class TestFormulatorOnFixtures(unittest.TestCase):

    def _run(self, fixture_name: str):
        fixture = load_fixture(fixture_name)
        input_data = fixture["input"]
        verdict_raw = fixture["expected_verdict_raw"]
        expected_final = make_final_verdict(fixture)

        with patch("formulator.formulator._call_llm", return_value=mock_llm_response(expected_final)):
            result = formulate(input_data, verdict_raw, MOCK_CONFIG)

        return result, fixture["expected_final"]

    def test_001_verdict(self):
        result, ef = self._run("001_redis_loop.json")
        self.assertEqual(result["verdict"], ef["verdict"])

    def test_001_issues(self):
        result, ef = self._run("001_redis_loop.json")
        self.assertEqual(sorted(result["issues"]), sorted(ef["issues"]))

    def test_001_trace_mode(self):
        result, ef = self._run("001_redis_loop.json")
        self.assertEqual(result["trace"]["mode"], ef["trace_mode"])

    def test_002_verdict(self):
        result, ef = self._run("002_medical_weak_evidence.json")
        self.assertEqual(result["verdict"], ef["verdict"])

    def test_003_verdict(self):
        result, ef = self._run("003_planning_uncovered_requirement.json")
        self.assertEqual(result["verdict"], ef["verdict"])

    def test_004_approve_empty_feedback(self):
        result, ef = self._run("004_code_clean_approve.json")
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["feedback"], "")
        self.assertIsNone(result["alternative_hypothesis"])

    def test_006_escalate(self):
        result, ef = self._run("006_parser_low_confidence_guard.json")
        self.assertEqual(result["verdict"], "ESCALATE")


class TestFallback(unittest.TestCase):

    def test_fallback_reject(self):
        verdict_raw = {
            "request_id": "00000000-0000-4000-8000-000000000001",
            "final_verdict": "reject",
            "core_confidence": 0.17,
            "issues": [{"code": "process_loop", "triggered_by": {"rule": "issue(process_loop)"}}],
            "parser_meta_passthrough": {"warnings": []}
        }
        result = _make_fallback(verdict_raw)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertNotEqual(result["feedback"], "")

    def test_fallback_approve(self):
        verdict_raw = {
            "request_id": "00000000-0000-4000-8000-000000000004",
            "final_verdict": "approve",
            "core_confidence": 0.86,
            "issues": [],
            "parser_meta_passthrough": {"warnings": []}
        }
        result = _make_fallback(verdict_raw)
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["feedback"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
