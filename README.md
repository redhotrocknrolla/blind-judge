# Blind Judge

Гибридный аудитор для мультиагентных систем: LLM-парсер + Prolog-ядро +
LLM-формулировщик. Встраивается в цепочку агентов как фильтр последней мили.

Два режима — переключается автоматически:
- **Формальный** — Prolog-ядро для задач с критериями (диагностика, код, планирование, исследования)
- **Творческий** — LLM-судья для субъективных задач (эстетика, стиль, открытые вопросы)

Не имеет собственной модели — использует LLM клиента через OpenAI-совместимый интерфейс.

См. `CONTRACT.md` — источник истины по архитектуре.
См. `SKILL.md` — инструкция по интеграции для оркестратора.

---

## Быстрый старт

**Зависимости:**

```bash
pip3 install openai fastapi uvicorn pyyaml jsonschema
# SWI-Prolog 10.0.2+: https://www.swi-prolog.org/Download.html
```

**Конфигурация:**

```yaml
# ~/.blind-judge/config.yaml
llm:
  base_url: "https://api.anthropic.com"
  api_key: "sk-ant-..."
  model: "claude-haiku-4-5"
server:
  host: "127.0.0.1"
  port: 8080
parser:
  max_retries: 2
```

---

## Интеграция

### Сценарий A — есть оркестратор

```python
import sys
sys.path.insert(0, "/path/to/blind-judge/src")
from orchestrator_hook import judge_check, handle_verdict

# После того как агент отработал:
verdict = judge_check(
    task="Найти причину ошибки",
    inputs=["fact1", "fact2"],
    conclusion="Вывод агента",
    actions=[{"step": 1, "name": "tool", "args": {}}],
    domain_hint="diagnostic"
)

result = handle_verdict(verdict, agent_fn, task, inputs, max_retries=2)
# result["approved"] == True → отдать пользователю
```

### Сценарий B — нет оркестратора

```python
from minimal_orchestrator import run_with_judge, print_result

result = run_with_judge(
    agent_fn=my_agent,       # (task, facts) → (conclusion, actions)
    task="Задача",
    facts=["fact1", "fact2"],
    domain_hint="diagnostic",
    max_retries=2
)
print_result(result)
```

### Локальный запуск

```bash
# Прямой аудит файла
python3 cli.py audit input.json --pretty

# С пользовательскими правилами
python3 cli.py audit input.json --rules my_rules.pl --pretty
```

### Удалённый сервер

```bash
python3 cli.py serve --port 8080

curl -X POST http://localhost:8080/audit \
  -H "Content-Type: application/json" \
  -d @input.json
```

---

## Архитектура
Запрос пользователя
│
▼
Агент делает работу
│
▼
Judge (фильтр последней мили)
│
├── formalizable?
│     ├── да  → Parser → Prolog Core → Formulator  (mode: hybrid)
│     └── нет → Legacy LLM Judge                   (mode: legacy)
│
├── APPROVE  → ответ идёт пользователю
├── ESCALATE → retry агента с feedback
└── REJECT   → retry агента с feedback

---

## Скиллы

| Файл | Назначение |
|------|-----------|
| `SKILL.md` | Главный скилл — инструкция для оркестратора |
| `skills/judge_formal.md` | Документация Prolog-пути |
| `skills/judge_creative.md` | Творческий судья для субъективных задач |

---

## Структура репозитория
blind-judge/
├── SKILL.md                        ← точка входа для оркестратора
├── CONTRACT.md                     ← архитектурный контракт
├── cli.py                          ← CLI: serve / audit
├── skills/
│   ├── judge_formal.md             ← описание формального режима
│   └── judge_creative.md           ← скилл для творческих задач
├── schemas/                        ← JSON Schema контракты
├── src/
│   ├── config.py
│   ├── judge.py                    ← оркестратор
│   ├── api.py                      ← FastAPI сервер
│   ├── orchestrator_hook.py        ← хук для существующего оркестратора
│   ├── minimal_orchestrator.py     ← минимальный оркестратор без зависимостей
│   ├── parser/                     ← промпт + bj_parser.py
│   ├── core/                       ← Prolog ядро + Python мост
│   ├── formulator/                 ← промпт + formulator.py
│   ├── legacy/                     ← промпт для творческого режима
│   └── examples/user_rules/        ← примеры пользовательских правил
└── tests/
├── core.plt
├── parser_test.py
├── formulator_test.py
├── e2e_test.py
└── user_rules_test.py

---

## Запуск тестов

```bash
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt
python3 tests/parser_test.py
python3 tests/formulator_test.py
python3 tests/e2e_test.py
python3 tests/user_rules_test.py
```

---

## Соглашения

- `schema_version` всегда `"1.0"`. Mismatch → fail-fast.
- `request_id` — UUID v4, сквозная трассировка.
- Пользовательские правила только **добавляют** `issue/1`, не удаляют базовые.
- При `abstain=true` — творческий режим, Prolog не запускается.
