# Blind Judge

Гибридный аудитор для мультиагентных систем: LLM-парсер + Prolog-ядро +
LLM-формулировщик. Встраивается в цепочку вызовов оркестратора как фильтр.

Два режима работы: локальный (прямой вызов/subprocess) и удалённый (HTTP POST).
Не имеет собственной модели — использует LLM клиента через OpenAI-совместимый
интерфейс.

См. `CONTRACT.md` — единственный источник истины по архитектуре.

## Статус: Sprint 4 — оркестратор + API

В этом коммите:

- `src/core/` — Prolog-ядро + Python-мост (`run_core.py`).
- `src/parser/` — промпт и `bj_parser.py`.
- `src/formulator/` — промпт и `formulator.py`.
- `src/judge.py` — оркестратор: parser → core → formulator, legacy fallback.
- `src/api.py` — FastAPI сервер, `POST /audit`, `GET /health`.
- `src/config.py` — конфиг из `~/.blind-judge/config.yaml` или env.
- `cli.py` — точка входа: `blind-judge serve` / `blind-judge audit`.

## Быстрый старт

**Установка зависимостей:**

```bash
pip3 install anthropic openai fastapi uvicorn pyyaml jsonschema
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

**Локальный запуск сервера:**

```bash
python3 cli.py serve
# Сервер на http://127.0.0.1:8080
```

**Аудит файла напрямую:**

```bash
python3 cli.py audit input.json --pretty
```

**HTTP запрос:**

```bash
curl -X POST http://localhost:8080/audit \
  -H "Content-Type: application/json" \
  -d @input.json
```

## Запуск тестов

```bash
# Prolog-ядро (детерминированные)
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt

# Парсер (мок LLM)
python3 tests/parser_test.py

# Формулировщик (мок LLM)
python3 tests/formulator_test.py

# E2E — полный путь, реальный Prolog, мок LLM
python3 tests/e2e_test.py
```

## Архитектура
POST /audit
│
├── [Parser LLM]     prompt → parsed_facts.json
│
├── formalizable?
│     ├── да  → [Prolog Core] → verdict_raw.json
│     │              └── [Formulator LLM] → final_verdict.json
│     └── нет → [Legacy LLM Judge] → final_verdict.json (mode=legacy)
│
└── response: final_verdict.json

## Что дальше

**Sprint 5 — пользовательские правила.** Механизм подключения через
`--rules path.pl` или `BLIND_JUDGE_RULES`. Защита базовых правил.
Примеры в `src/examples/user_rules/`.

## Соглашения

- `schema_version` всегда `"1.0"` в v1. Mismatch → fail-fast.
- `request_id` — UUID v4, для трассировки сквозь все компоненты.
- Пользовательские правила могут только **добавлять** `issue/1`, не удалять базовые.
