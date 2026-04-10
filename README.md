# Blind Judge

Гибридный аудитор для мультиагентных систем: LLM-парсер + Prolog-ядро +
LLM-формулировщик. Подключаемая библиотека для CLI-сервисов с роутером
скиллов.

Встраивается в цепочку вызовов оркестратора как фильтр. Два режима работы:
локальный (прямой вызов) и удалённый (HTTP POST). Не имеет собственной
модели — использует LLM клиента через OpenAI-совместимый интерфейс.

См. `CONTRACT.md` — единственный источник истины по архитектуре.

## Статус: Sprint 3 — LLM-формулировщик

В этом коммите:

- `schemas/` — четыре JSON-схемы, фиксирующие контракты между компонентами.
- `tests/fixtures/` — корпус из 6 размеченных кейсов.
- `src/core/` — Prolog-ядро: `facts_loader.pl`, `blind_judge.pl`, `verdict.pl`.
- `src/parser/prompts/parser_v1.md` — промпт парсера с контролируемым словарём.
- `src/parser/bj_parser.py` — вызов LLM, валидация JSON Schema, retry, abstain.
- `src/formulator/prompts/formulator_v1.md` — промпт формулировщика.
- `src/formulator/formulator.py` — генерация feedback, защита структурных полей.
- `src/config.py` — конфиг из `~/.blind-judge/config.yaml` или env.
- `tests/core.plt` — 16 plunit-тестов ядра.
- `tests/parser_test.py` — тесты парсера с моком LLM.
- `tests/formulator_test.py` — тесты формулировщика с моком LLM.

**Запуск тестов:**

```bash
# Prolog-ядро
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt

# Парсер
python3 tests/parser_test.py

# Формулировщик
python3 tests/formulator_test.py
```

## Конфигурация

```yaml
# ~/.blind-judge/config.yaml
llm:
  base_url: "https://api.anthropic.com"  # или localhost если модель локальная
  api_key: "sk-ant-..."                  # или через BLIND_JUDGE_LLM_API_KEY
  model: "claude-haiku-4-5"
server:
  host: "127.0.0.1"
  port: 8080
parser:
  max_retries: 2
  double_check: false
```

## Что дальше

**Sprint 4 — оркестратор + API.** Склейка parser → core → formulator.
FastAPI сервер с `POST /audit`. Локальный и удалённый режим.
Legacy fallback при `abstain=true`.

## Расширение корпуса

6 фикстур — минимум для запуска ядра. До Sprint 6 нужно дойти до 100+.
Формат фикстуры описан в `tests/fixtures/README.md`.

## Соглашения

- `schema_version` всегда `"1.0"` в v1. Mismatch → fail-fast.
- `request_id` — UUID v4, для трассировки сквозь все компоненты.
- В фикстурах `request_id` зафиксирован, чтобы тесты были воспроизводимыми.
- Пользовательские правила могут только **добавлять** `issue/1`, не удалять базовые.
