# Blind Judge

Гибридный аудитор для мультиагентных систем: LLM-парсер + Prolog-ядро +
LLM-формулировщик. Самостоятельный сервис-фильтр, встраивается в цепочку
вызовов CLI оркестратора.

Не имеет собственной LLM — использует модель клиента через OpenAI-совместимый
интерфейс. Работает локально или удалённо.

См. `CONTRACT.md` — единственный источник истины по архитектуре.

## Статус: Sprint 2 — LLM-парсер

В этом коммите:

- `schemas/` — четыре JSON-схемы, фиксирующие контракты между компонентами.
- `tests/fixtures/` — стартовый корпус из 6 размеченных кейсов.
- `src/core/` — Prolog-ядро: `facts_loader.pl`, `blind_judge.pl`, `verdict.pl`.
- `src/config.py` — читает `~/.blind-judge/config.yaml` и переменные окружения.
- `src/parser/prompts/parser_v1.md` — промпт парсера с контролируемым словарём.
- `src/parser/bj_parser.py` — вызов LLM клиента, валидация схемы, retry, abstain.
- `tests/parser_test.py` — тесты парсера на моке (retry, abstain, schema validation).

**Запуск тестов ядра:**

```bash
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt
```

**Запуск тестов парсера:**

```bash
python3 tests/parser_test.py
```

## Конфигурация

Создай `~/.blind-judge/config.yaml`:

```yaml
llm:
  base_url: "https://api.anthropic.com"   # или локальный эндпоинт
  api_key: "sk-ant-..."                    # ключ клиента
  model: "claude-haiku-4-5"

server:
  host: "127.0.0.1"
  port: 8080

parser:
  max_retries: 2
  double_check: false
```

Или через переменные окружения:

```bash
export BLIND_JUDGE_LLM_BASE_URL="https://api.anthropic.com"
export BLIND_JUDGE_LLM_API_KEY="sk-ant-..."
export BLIND_JUDGE_LLM_MODEL="claude-haiku-4-5"
```

## Что дальше

**Sprint 3 — формулировщик.** Промпт + `formulator.py`. Принимает
`verdict_raw.json`, генерирует `feedback` и `alternative_hypothesis`.
Не меняет структурные поля — только текст.

## Расширение корпуса

6 фикстур — минимум для запуска ядра. До Sprint 6 нужно дойти до 100+.
Формат фикстуры описан в `tests/fixtures/README.md`.

## Соглашения

- `schema_version` всегда `"1.0"` в v1. Mismatch → fail-fast.
- `request_id` — UUID v4, для трассировки сквозь все компоненты.
- В фикстурах `request_id` зафиксирован, чтобы тесты были воспроизводимыми.
- Пользовательские правила могут только **добавлять** `issue/1`, не удалять базовые.
