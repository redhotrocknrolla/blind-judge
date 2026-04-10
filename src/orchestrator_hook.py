#!/usr/bin/env python3
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from judge import audit
from config import load_config


def make_input(task, inputs, conclusion, actions=None, domain_hint=None, request_id=None):
    return {
        "schema_version": "1.0",
        "request_id": request_id or str(uuid.uuid4()),
        "task": task,
        "inputs": [
            {
                "id": f"in_{i+1:03d}",
                "text": str(f) if not isinstance(f, dict) else f.get("text", str(f)),
                "source": f.get("source") if isinstance(f, dict) else None
            }
            for i, f in enumerate(inputs)
        ],
        "conclusion": conclusion,
        "actions": actions or [],
        "domain_hint": domain_hint
    }


def judge_check(task, inputs, conclusion, actions=None, domain_hint=None, config=None, user_rules=None):
    if config is None:
        config = load_config()
    input_data = make_input(task, inputs, conclusion, actions, domain_hint)
    return audit(input_data, config, user_rules=user_rules)


def handle_verdict(verdict, agent_fn, task, inputs, max_retries=2, config=None, user_rules=None):
    if config is None:
        config = load_config()

    attempts = 1
    last_conclusion = None

    if verdict["verdict"] == "APPROVE":
        return {"conclusion": verdict.get("feedback", ""), "judge_verdict": verdict, "attempts": attempts, "approved": True}

    for attempt in range(max_retries):
        attempts += 1
        retry_context = (
            f"{task}\n\n"
            f"[Judge вернул {verdict['verdict']}]\n"
            f"[Issues: {', '.join(verdict['issues'])}]\n"
            f"[Feedback]: {verdict['feedback']}\n\n"
            f"Учти замечания и повтори работу."
        )
        result = agent_fn(retry_context, inputs)
        if isinstance(result, tuple):
            last_conclusion, actions = result
        else:
            last_conclusion, actions = result, []

        verdict = judge_check(task, inputs, last_conclusion, actions, config=config, user_rules=user_rules)

        if verdict["verdict"] == "APPROVE":
            return {"conclusion": last_conclusion, "judge_verdict": verdict, "attempts": attempts, "approved": True}

    return {"conclusion": last_conclusion, "judge_verdict": verdict, "attempts": attempts, "approved": False}
