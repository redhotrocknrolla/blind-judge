#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from orchestrator_hook import judge_check, handle_verdict
from config import load_config


def run_with_judge(agent_fn, task, facts, domain_hint=None, max_retries=2, config=None, user_rules=None):
    if config is None:
        config = load_config()

    result = agent_fn(task, facts)
    if isinstance(result, tuple):
        conclusion, actions = result
    else:
        conclusion, actions = result, []

    verdict = judge_check(
        task=task, inputs=facts, conclusion=conclusion,
        actions=actions, domain_hint=domain_hint,
        config=config, user_rules=user_rules
    )

    return handle_verdict(
        verdict=verdict, agent_fn=agent_fn, task=task,
        inputs=facts, max_retries=max_retries,
        config=config, user_rules=user_rules
    )


def print_result(result):
    v = result["judge_verdict"]
    status = "APPROVE" if result["approved"] else v["verdict"]
    print(f"\n{status} (попыток: {result['attempts']}, confidence: {v['confidence']:.2f})")
    if v["issues"]:
        print(f"Issues: {', '.join(v['issues'])}")
    if v.get("feedback"):
        print(f"Feedback: {v['feedback']}")
    print(f"\nВывод: {result['conclusion']}")
    print(f"Trace mode: {v['trace']['mode']}")
