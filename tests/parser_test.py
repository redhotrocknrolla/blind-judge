#!/usr/bin/env python3
"""
Тест парсера на фикстурах с моком LLM — проверяем валидацию, retry, abstain.
"""

import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.bj_parser import parse, extract_json, _make_abstain

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

MOCK_CONFIG = {
    "llm": {
        "base_url": "https://api.anthropic.com",
        "api_key": "test-key",
        "model": "claude-haiku-4-5",
        "max_tokens": 4096,
    },
    "parser": {"max_retries": 2, "double_check": False}
}


def mock_llm_response(parsed_facts: dict):
    """Возвращает мок OpenAI-совместимого ответа с готовым JSON."""
    msg = MagicMock()
    msg.content = json.dumps(parsed_facts, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestExtractJson(unittest.TestCase):

    def test_plain_json(self):
        data = {"schema_version": "1.0"}
        result = extract_json(json.dumps(data))
        self.assertEqual(result, data)

    def test_markdown_wrapped(self):
        data = {"schema_version": "1.0"}
        wrapped = f"```json\n{json.dumps(data)}\n```"
        result = extract_json(wrapped)
        self.assertEqual(result, data)

    def test_markdown_no_lang(self):
        data = {"key": "value"}
        wrapped = f"```\n{json.dumps(data)}\n```"
        result = extract_json(wrapped)
        self.assertEqual(result, data)


class TestParserOnFixtures(unittest.TestCase):

    def _load_fixture(self, name: str):
        path = FIXTURES / name
        return json.loads(path.read_text(encoding="utf-8"))

    def _run_parser_with_mock(self, fixture_name: str):
        fixture = self._load_fixture(fixture_name)
        input_data = fixture["input"]
        expected = fixture["expected_parsed_facts"]

        with patch("parser.bj_parser.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = mock_llm_response(expected)
            result = parse(input_data, MOCK_CONFIG)

        return result, expected

    def test_001_schema_version(self):
        result, _ = self._run_parser_with_mock("001_redis_loop.json")
        self.assertEqual(result["schema_version"], "1.0")

    def test_001_request_id_passthrough(self):
        result, expected = self._run_parser_with_mock("001_redis_loop.json")
        self.assertEqual(result["request_id"], expected["request_id"])

    def test_001_valid_against_schema(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas" / "parsed_facts.schema.json").read_text())
        result, _ = self._run_parser_with_mock("001_redis_loop.json")
        jsonschema.validate(instance=result, schema=schema)

    def test_002_valid_against_schema(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas" / "parsed_facts.schema.json").read_text())
        result, _ = self._run_parser_with_mock("002_medical_weak_evidence.json")
        jsonschema.validate(instance=result, schema=schema)

    def test_003_valid_against_schema(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas" / "parsed_facts.schema.json").read_text())
        result, _ = self._run_parser_with_mock("003_planning_uncovered_requirement.json")
        jsonschema.validate(instance=result, schema=schema)

    def test_004_valid_against_schema(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas" / "parsed_facts.schema.json").read_text())
        result, _ = self._run_parser_with_mock("004_code_clean_approve.json")
        jsonschema.validate(instance=result, schema=schema)

    def test_005_abstain_passthrough(self):
        """Фикстура 005 — парсер должен вернуть abstain=true."""
        fixture = self._load_fixture("005_aesthetic_abstain.json")
        input_data = fixture["input"]
        expected = fixture["expected_parsed_facts"]

        with patch("parser.bj_parser.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = mock_llm_response(expected)
            result = parse(input_data, MOCK_CONFIG)

        self.assertTrue(result["parser_meta"]["abstain"])
        self.assertFalse(result["task_analysis"]["formalizable"])

    def test_retry_on_invalid_json(self):
        """Первый ответ — невалидный JSON, второй — правильный."""
        fixture = self._load_fixture("001_redis_loop.json")
        input_data = fixture["input"]
        expected = fixture["expected_parsed_facts"]

        bad_msg = MagicMock()
        bad_msg.content = "это не json {"
        bad_choice = MagicMock()
        bad_choice.message = bad_msg
        bad_resp = MagicMock()
        bad_resp.choices = [bad_choice]

        good_resp = mock_llm_response(expected)

        with patch("parser.bj_parser.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.side_effect = [bad_resp, good_resp]
            result = parse(input_data, MOCK_CONFIG)

        self.assertEqual(result["schema_version"], "1.0")

    def test_all_retries_exhausted_returns_abstain(self):
        """Все попытки провалились — должен вернуть abstain."""
        fixture = self._load_fixture("001_redis_loop.json")
        input_data = fixture["input"]

        bad_msg = MagicMock()
        bad_msg.content = "не json"
        bad_choice = MagicMock()
        bad_choice.message = bad_msg
        bad_resp = MagicMock()
        bad_resp.choices = [bad_choice]

        with patch("parser.bj_parser.OpenAI") as MockOpenAI:
            instance = MockOpenAI.return_value
            instance.chat.completions.create.return_value = bad_resp
            result = parse(input_data, MOCK_CONFIG)

        self.assertTrue(result["parser_meta"]["abstain"])
        self.assertIn("parser_failed", result["parser_meta"]["warnings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
