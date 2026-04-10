#!/usr/bin/env python3
"""
Blind Judge — Prolog Core Bridge
"""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
CORE_DIR = Path(__file__).parent


def run_core(parsed_facts: dict) -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f_in:
        json.dump(parsed_facts, f_in, ensure_ascii=False)
        input_file = f_in.name

    facts_loader_pl = str(CORE_DIR / "facts_loader.pl").replace("\\", "/")
    verdict_pl      = str(CORE_DIR / "verdict.pl").replace("\\", "/")
    input_file_fwd  = input_file.replace("\\", "/")

    prolog_goal = (
        f"['{facts_loader_pl}'],"
        f"['{verdict_pl}'],"
        f"load_facts('{input_file_fwd}'),"
        f"final_verdict(V),"
        f"unique_issues(Issues),"
        f"core_confidence(Score),"
        f"parser_min_confidence(MinConf),"
        f"parser_warnings(Warnings),"
        f"parser_abstain(Abstained),"
        f"request_id(ReqId),"
        f"atom_string(V, VStr),"
        f"atom_string(ReqId, ReqIdStr),"
        f"maplist([I, json([code=C, source=base])]>>(atom_string(I,C)), Issues, IssuesJson),"
        f"maplist([W,S]>>(atom_string(W,S)), Warnings, WarnStrings),"
        f"Result = json(["
        f"  schema_version='1.0',"
        f"  request_id=ReqIdStr,"
        f"  final_verdict=VStr,"
        f"  core_confidence=Score,"
        f"  issues=IssuesJson,"
        f"  uncovered_requirements=[],"
        f"  parser_meta_passthrough=json(["
        f"    min_confidence=MinConf,"
        f"    warnings=WarnStrings,"
        f"    abstained=Abstained"
        f"  ])"
        f"]),"
        f"json_write(current_output, Result, [width(0)]),"
        f"nl,"
        f"halt."
    )

    try:
        result = subprocess.run(
            ["swipl", "-q", "-g", prolog_goal],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Prolog core failed (exit {result.returncode}):\n{result.stderr}"
            )

        output = result.stdout.strip()
        if not output:
            raise RuntimeError(f"Prolog core returned empty output.\nstderr:\n{result.stderr}")

        verdict_raw = json.loads(output)
        verdict_raw = _enrich_issues(verdict_raw, parsed_facts)
        verdict_raw = _fix_types(verdict_raw)
        return verdict_raw

    finally:
        Path(input_file).unlink(missing_ok=True)


def _enrich_issues(verdict_raw: dict, parsed_facts: dict) -> dict:
    rule_map = {
        "process_loop": {
            "rule": "issue(process_loop)",
            "facts": _action_repeat_facts(parsed_facts)
        },
        "weak_evidence": {
            "rule": "issue(weak_evidence)/1",
            "facts": _weak_evidence_facts(parsed_facts)
        },
        "confirmation_bias": {
            "rule": "issue(confirmation_bias)",
            "facts": _confirmation_bias_facts(parsed_facts)
        },
        "unsupported_conclusion": {
            "rule": "issue(unsupported_conclusion)/2",
            "facts": _unsupported_facts(parsed_facts)
        },
    }

    for issue in verdict_raw.get("issues", []):
        code = issue.get("code")
        if code in rule_map:
            issue["triggered_by"] = rule_map[code]
        elif "triggered_by" not in issue:
            issue["triggered_by"] = {"rule": f"issue({code})", "facts": []}

    uncovered = []
    for cov in parsed_facts.get("requirement_coverage", []):
        if not cov.get("covered"):
            req_id = cov["requirement_id"]
            for req in parsed_facts.get("task_analysis", {}).get("requirements", []):
                if req["id"] == req_id and req["kind"] == "must_have":
                    uncovered.append({"requirement_id": req_id, "kind": "must_have"})
    verdict_raw["uncovered_requirements"] = uncovered

    return verdict_raw


def _action_repeat_facts(pf: dict) -> list:
    facts = []
    for g in pf.get("action_patterns", {}).get("repeated_groups", []):
        facts.append(
            f'action_repeat({g["name"]}, "{g["args_signature"]}", {g["occurrences"]}, {str(g["new_info_between"]).lower()})'
        )
    return facts


def _weak_evidence_facts(pf: dict) -> list:
    facts = []
    for cl in pf.get("claims", []):
        if cl["asserted_confidence"] == "high":
            facts.append(f'claim({cl["id"]}, _, high)')
            facts.append(f'no_evidence(direct_support, strong, {cl["id"]})')
    return facts


def _confirmation_bias_facts(pf: dict) -> list:
    facts = []
    for ev in pf.get("evidence", []):
        if ev["relation"] == "contradicts" and ev["strength"] in ("strong", "moderate"):
            facts.append(
                f'evidence({ev["id"]}, {ev["input_id"]}, {ev["supports_claim"]}, '
                f'contradicts, {ev["strength"]}, {ev["parser_confidence"]})'
            )
    ac = pf.get("alternatives_considered", {})
    facts.append(
        f'alternatives_considered({ac.get("explicit_alternatives_in_conclusion", 0)}, '
        f'{str(ac.get("contradicting_evidence_addressed", False)).lower()}, '
        f'{ac.get("parser_confidence", 0)})'
    )
    return facts


def _unsupported_facts(pf: dict) -> list:
    facts = []
    for cov in pf.get("requirement_coverage", []):
        if not cov.get("covered"):
            req_id = cov["requirement_id"]
            for req in pf.get("task_analysis", {}).get("requirements", []):
                if req["id"] == req_id:
                    facts.append(f'requirement({req_id}, {req["kind"]}, "{req["text"]}")')
                    facts.append(
                        f'requirement_coverage({req_id}, false, _, {cov["parser_confidence"]})'
                    )
    return facts


def _fix_types(verdict_raw: dict) -> dict:
    """Исправляем типы после JSON парсинга из Prolog."""
    pmt = verdict_raw.get("parser_meta_passthrough", {})
    if isinstance(pmt.get("abstained"), str):
        pmt["abstained"] = pmt["abstained"].lower() == "true"
    return verdict_raw
