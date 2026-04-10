# Blind Judge

Гибридный аудитор для мультиагентных систем: LLM-парсер + Prolog-ядро +
LLM-формулировщик. Встраивается в цепочку вызовов оркестратора как фильтр.

Два режима работы: локальный (прямой вызов) и удалённый (HTTP POST).
Не имеет собственной модели — использует LLM клиента через OpenAI-совместимый
интерфейс. Расширяется пользовательскими Prolog-правилами.

См. `CONTRACT.md` — единственный источник истины по архитектуре.

## Статус: Sprint 5 — пользовательские правила

Все спринты закрыты. Система полностью собрана.

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
  base_url: "https://api.anthropic.com"  # или localhost для локальной модели
  api_key: "sk-ant-..."                  # или BLIND_JUDGE_LLM_API_KEY
  model: "claude-haiku-4-5"
server:
  host: "127.0.0.1"
  port: 8080
parser:
  max_retries: 2
  double_check: false
```

**Запуск сервера:**

```bash
python3 cli.py serve
# → http://127.0.0.1:8080

# С пользовательскими правилами:
python3 cli.py serve --rules src/examples/user_rules/medical_research.pl
```

**Аудит файла напрямую:**

```bash
python3 cli.py audit input.json --pretty
python3 cli.py audit input.json --rules my_rules.pl --pretty
```

**HTTP запрос:**

```bash
curl -X POST http://localhost:8080/audit \
  -H "Content-Type: application/json" \
  -d @input.json
```

## Архитектура
POST /audit
│
├── [Parser LLM]     prompt → parsed_facts.json
│
├── formalizable?
│     ├── да  → [Prolog Core + user_rules.pl] → verdict_raw.json
│     │                └── [Formulator LLM] → final_verdict.json
│     └── нет → [Legacy LLM Judge] → final_verdict.json (mode=legacy)
│
└── response: final_verdict.json

## Пользовательские правила

Правила подключаются через `--rules path.pl` или `BLIND_JUDGE_RULES`.
Могут только **добавлять** новые `issue/1` — базовые правила защищены.

```prolog
% my_rules.pl
:- multifile issue/1.

issue(missing_rct) :-
    task_type(research),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

verdict(escalate) :-
    \+ verdict(reject),
    issue(missing_rct).
```

Примеры: `src/examples/user_rules/medical_research.pl`, `code_review.pl`.

## Запуск тестов

```bash
# Prolog-ядро (детерминированные)
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt

# Парсер, формулировщик, e2e, пользовательские правила
python3 tests/parser_test.py
python3 tests/formulator_test.py
python3 tests/e2e_test.py
python3 tests/user_rules_test.py
```

## Структура репозитория
blind-judge/
├── CONTRACT.md                        ← единственный источник истины
├── cli.py                             ← точка входа
├── schemas/                           ← JSON Schema для всех контрактов
├── src/
│   ├── config.py                      ← конфиг
│   ├── judge.py                       ← оркестратор
│   ├── api.py                         ← FastAPI сервер
│   ├── parser/                        ← промпт + bj_parser.py
│   ├── core/                          ← Prolog ядро + Python мост
│   ├── formulator/                    ← промпт + formulator.py
│   └── examples/user_rules/           ← примеры пользовательских правил
└── tests/
├── core.plt                       ← plunit тесты ядра
├── parser_test.py
├── formulator_test.py
├── e2e_test.py
└── user_rules_test.py

## Соглашения

- `schema_version` всегда `"1.0"` в v1. Mismatch → fail-fast.
- `request_id` — UUID v4, для трассировки сквозь все компоненты.
- Пользовательские правила могут только **добавлять** `issue/1`, не удалять базовые.
- При `abstain=true` — legacy режим, Prolog-ядро не запускается.
