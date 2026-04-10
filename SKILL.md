---
name: blind-judge
description: >
  Независимый агент-аудитор для мультиагентных систем. Вызывай этот скилл
  ПОСЛЕ того как основной агент завершил работу, но ДО финальной отдачи
  пользователю. Особенно важен если агент использовал инструменты, делал
  диагностику, выбирал между гипотезами или принимал решения на основе
  собранных данных. Blind Judge не видит рассуждений основного агента —
  только факты, действия и вывод. Автоматически выбирает режим проверки:
  формальный (Prolog) для задач с критериями, творческий (LLM) для субъективных.
---

# Blind Judge — Гибридный аудитор

Встраивается в цепочку агентов как фильтр последней мили.
Проверяет вывод основного агента перед тем как он уйдёт пользователю.

Два режима — переключается автоматически:
- **Формальный** (`skills/judge_formal.md`) — Prolog-ядро для задач с критериями
- **Творческий** (`skills/judge_creative.md`) — LLM-судья для субъективных задач

---

## Принцип слепоты

Judge получает **stripped input** — только факты и вывод,
без цепочки рассуждений агента:
task:        string               // исходная задача пользователя
inputs:      [{id, text, source}] // сырые факты которые использовал агент
conclusion:  string               // финальный вывод агента (дословно)
actions:     [{step, name, args}] // лог вызовов инструментов
domain_hint: string | null        // подсказка: medical|code|research|planning|diagnostic|other

---

## Формат входного JSON

```json
{
  "schema_version": "1.0",
  "request_id": "<uuid-v4>",
  "task": "Исходная задача пользователя",
  "inputs": [
    {
      "id": "in_001",
      "text": "Сырой результат инструмента или факт",
      "source": "откуда данные (опционально)"
    }
  ],
  "conclusion": "Финальный вывод основного агента",
  "actions": [
    {"step": 1, "name": "имя_инструмента", "args": {"ключ": "значение"}}
  ],
  "domain_hint": "diagnostic"
}
```

---

## Формат выходного JSON

```json
{
  "schema_version": "1.0",
  "request_id": "<тот же uuid>",
  "verdict": "APPROVE | ESCALATE | REJECT",
  "confidence": 0.85,
  "issues": ["process_loop", "confirmation_bias"],
  "alternative_hypothesis": "string | null",
  "feedback": "Конкретные инструкции для основного агента",
  "trace": {
    "rules_fired": ["issue(process_loop)"],
    "parser_warnings": [],
    "core_confidence": 0.85,
    "mode": "hybrid | legacy"
  }
}
```

---

## Сценарий A — есть оркестратор

Judge вставляется как post-hook. После каждого агента оркестратор
вызывает Judge перед отдачей ответа пользователю.

```python
# orchestrator_hook.py — вставить в существующий оркестратор
import subprocess, json, uuid, sys
sys.path.insert(0, "/path/to/blind-judge/src")
from judge import audit
from config import load_config

JUDGE_CONFIG = load_config()

def judge_check(task: str, inputs: list, conclusion: str,
                actions: list = None, domain_hint: str = None) -> dict:
    """Вызвать после каждого агента перед отдачей пользователю."""
    input_data = {
        "schema_version": "1.0",
        "request_id": str(uuid.uuid4()),
        "task": task,
        "inputs": [
            {"id": f"in_{i+1:03d}", "text": str(fact), "source": None}
            for i, fact in enumerate(inputs)
        ],
        "conclusion": conclusion,
        "actions": actions or [],
        "domain_hint": domain_hint
    }
    return audit(input_data, JUDGE_CONFIG)


def handle_verdict(verdict: dict, agent_fn, task: str,
                   inputs: list, max_retries: int = 2) -> dict:
    """Обработать вердикт Judge. При REJECT/ESCALATE — retry агента."""
    if verdict["verdict"] == "APPROVE":
        return verdict

    for attempt in range(max_retries):
        retry_context = (
            f"\n\n[Judge feedback]: {verdict['feedback']}"
            f"\n[Retry reason]: {verdict['verdict']} — {verdict['issues']}"
        )
        new_conclusion, new_actions = agent_fn(task + retry_context, inputs)
        verdict = judge_check(task, inputs, new_conclusion, new_actions)
        if verdict["verdict"] == "APPROVE":
            break

    return verdict
```

**Как встроить в оркестратор:**

```python
from orchestrator_hook import judge_check, handle_verdict

# После того как агент отработал:
conclusion, actions = my_agent.run(task, facts)

verdict = judge_check(
    task=task,
    inputs=facts,
    conclusion=conclusion,
    actions=actions,
    domain_hint="diagnostic"
)

final = handle_verdict(verdict, my_agent.run, task, facts)
# final["verdict"] == "APPROVE" — можно отдавать пользователю
```

---

## Сценарий B — нет оркестратора

Используй минимальный оркестратор из поставки:

```python
# minimal_orchestrator.py
from minimal_orchestrator import run_with_judge

result = run_with_judge(
    agent_fn=my_agent,          # функция агента: (task, facts) → (conclusion, actions)
    task="Найти причину ошибки",
    facts=["fact1", "fact2"],
    domain_hint="diagnostic",
    max_retries=2
)
print(result["conclusion"])     # проверенный вывод
print(result["judge_verdict"])  # финальный вердикт Judge
```

---

## Поведение при вердиктах

| Вердикт | Действие оркестратора |
|---------|-----------------------|
| `APPROVE` | Отдать ответ пользователю |
| `ESCALATE` | Retry агента с `judge_feedback` в контексте |
| `REJECT` | Retry агента с `judge_feedback` в контексте |

При исчерпании `max_retries` — отдать последний ответ с пометкой
`[Judge: не прошло проверку]` и вердиктом в метаданных.

---

## Сценарий C — CLI-режим (модель сама является судьёй)

Если скилл вызывается через Claude Code или любой CLI-агент,
**модель не делает отдельных API вызовов** — она сама выполняет
роль парсера и формулировщика, читая промпты напрямую.
Только Prolog-ядро запускается как subprocess.

### Шаг 1 — Парсинг (модель читает промпт сама)

Прочитай файл `src/parser/prompts/parser_v1.md`.
Подставь входные данные вместо `{{INPUT_JSON}}`.
Выполни инструкцию промпта и сформируй `parsed_facts` JSON
по схеме `schemas/parsed_facts.schema.json`.

```python
# Проверить что parsed_facts валиден:
import json, jsonschema
schema = json.load(open("schemas/parsed_facts.schema.json"))
jsonschema.validate(instance=parsed_facts, schema=schema)
```

### Шаг 2 — Prolog-ядро (subprocess)

```python
import sys
sys.path.insert(0, "src")
from judge_core import run

verdict_raw = run(parsed_facts)
# или с пользовательскими правилами:
verdict_raw = run(parsed_facts, user_rules="path/to/rules.pl")
```

### Шаг 3 — Формулировка (модель читает промпт сама)

Прочитай файл `src/formulator/prompts/formulator_v1.md`.
Подставь оригинальный `input` вместо `{{INPUT_JSON}}`
и `verdict_raw` вместо `{{VERDICT_RAW_JSON}}`.
Выполни инструкцию промпта и сформируй `final_verdict` JSON
по схеме `schemas/final_verdict.schema.json`.

### Полный CLI-пример

```python
import sys, json, jsonschema
sys.path.insert(0, "src")
from judge_core import run

# 1. Модель читает промпт и формирует parsed_facts
parser_prompt = open("src/parser/prompts/parser_v1.md").read()
input_data = json.load(open("tests/fixtures/001_redis_loop.json"))["input"]
# ... модель применяет parser_prompt к input_data → parsed_facts

# 2. Prolog-ядро
verdict_raw = run(parsed_facts)

# 3. Модель читает промпт и формирует финальный вердикт
formulator_prompt = open("src/formulator/prompts/formulator_v1.md").read()
# ... модель применяет formulator_prompt к (input_data, verdict_raw) → final_verdict
```

### Когда использовать CLI-режим

| Условие | Режим |
|---|---|
| Модель = Claude Code / агент CLI | **CLI-режим** (этот сценарий) |
| Внешний агент, нужен API | Сценарий A / B (`judge.py`) |
| Баланс API исчерпан / нет ключа | **CLI-режим** |
| Нужна изоляция (отдельный LLM) | Сценарий A / B (`judge.py`) |

---

## Установка

```bash
git clone https://github.com/redhotrocknrolla/blind-judge
cd blind-judge
pip3 install anthropic openai fastapi uvicorn pyyaml jsonschema

# Конфиг
mkdir -p ~/.blind-judge
cat > ~/.blind-judge/config.yaml << EOF
llm:
  base_url: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-haiku-4-5"
EOF
```

Judge использует модель клиента — своей модели нет.
В CLI-режиме модель агента сама является и парсером, и формулировщиком.
