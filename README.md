# Blind Judge

Гибридный аудитор для мультиагентных систем. Встраивается в цепочку агентов как фильтр последней мили — проверяет вывод агента перед тем как он уйдёт пользователю.

**Принцип слепоты:** Judge получает только факты, действия и вывод — без цепочки рассуждений агента. Он не знает «как думал» агент, только что тот сделал и что утверждает.

---

## Как это работает

Три компонента, строго разделённые по ответственности:

```
raw input
    │
    ▼
┌─────────────────────┐
│  1. Parser  (LLM)   │  классифицирует факты, claims, evidence
└─────────────────────┘
    │ parsed_facts.json
    ▼
┌─────────────────────┐
│  2. Core   (Prolog) │  детерминированные правила → issues + verdict_raw
│  + user_rules.pl    │
└─────────────────────┘
    │ verdict_raw.json
    ▼
┌─────────────────────┐
│  3. Formulator(LLM) │  переводит структуру в actionable feedback
└─────────────────────┘
    │
    ▼
final_verdict.json  →  APPROVE / ESCALATE / REJECT
```

**Два режима — переключается автоматически:**

| Режим | Когда | Компоненты |
|---|---|---|
| `hybrid` | задача формализуема: диагностика, код, планирование, исследования | Parser → Prolog → Formulator |
| `legacy` | задача субъективна: эстетика, стиль, вкусовщина | LLM-судья напрямую |

**Разделение обязанностей — три закона:**
- Парсер не выносит вердиктов. Никогда.
- Ядро не понимает естественный язык. Только символы из словаря.
- Формулировщик не меняет структурные поля. Только переводит в текст.

---

## Что проверяет

Четыре базовых правила Prolog:

| Issue | Когда срабатывает |
|---|---|
| `process_loop` | Агент вызвал один инструмент с одними аргументами ≥ 2 раз без новых данных между вызовами |
| `weak_evidence` | Высокая уверенность (`high`) в claim, но нет ни одного `direct_support/strong` evidence |
| `confirmation_bias` | Есть `contradicts/strong` или `contradicts/moderate` evidence, агент не рассмотрел альтернативы |
| `unsupported_conclusion` | Claim без какого-либо supporting evidence, или must_have требование не покрыто |

**Вердикты и логика их выбора:**

```prolog
verdict(reject)   :- issue(unsupported_conclusion).
verdict(reject)   :- issue(process_loop), issue(confirmation_bias).
verdict(escalate) :- issue(weak_evidence) ; issue(confirmation_bias) ; issue(process_loop).
verdict(approve)  :- \+ issue(_).

% Если parser_min_confidence < 0.75 — APPROVE автоматически становится ESCALATE
```

**Confidence scoring:**

```
core_confidence = base_score(N issues) × parser_min_confidence

base_score: 0 issues → 0.95 | 1 → 0.70 | 2 → 0.45 | 3+ → 0.20
```

---

## Установка

**Зависимости:**

```bash
# Python-пакеты
pip3 install anthropic openai fastapi uvicorn pyyaml jsonschema

# SWI-Prolog 10.0.2+
# macOS:
brew install swi-prolog
# Ubuntu/Debian:
sudo apt install swi-prolog
# Или: https://www.swi-prolog.org/Download.html
```

**Клонирование:**

```bash
git clone https://github.com/redhotrocknrolla/blind-judge
cd blind-judge
```

**Конфигурация:**

```bash
mkdir -p ~/.blind-judge
cat > ~/.blind-judge/config.yaml << 'EOF'
llm:
  base_url: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-haiku-4-5"
server:
  host: "127.0.0.1"
  port: 8080
parser:
  max_retries: 2
  double_check: false
EOF
```

Поддерживается любой OpenAI-совместимый эндпоинт — SDK выбирается автоматически:
- URL содержит `anthropic.com` → Anthropic SDK (`client.messages.create`)
- Иначе → OpenAI SDK (`client.chat.completions.create`)

Переменные окружения перекрывают конфиг-файл:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export BLIND_JUDGE_LLM_MODEL="claude-haiku-4-5"
export BLIND_JUDGE_PORT=8080
```

---

## Использование

### Способ 1 — CLI (audit файла)

```bash
# Прогнать input.json и получить результат
python3 cli.py audit input.json --pretty

# С пользовательскими правилами Prolog
python3 cli.py audit input.json --rules my_rules.pl --pretty
```

### Способ 2 — HTTP сервер

```bash
# Запустить сервер
python3 cli.py serve --port 8080

# Или с пользовательскими правилами
python3 cli.py serve --rules src/examples/user_rules/medical_research.pl
```

```bash
# Запрос
curl -X POST http://localhost:8080/audit \
  -H "Content-Type: application/json" \
  -d @input.json
```

### Способ 3 — Python API (есть оркестратор)

```python
import sys
sys.path.insert(0, "/path/to/blind-judge/src")
from orchestrator_hook import judge_check, handle_verdict

# После того как агент отработал:
verdict = judge_check(
    task="Найти причину 500-ошибки",
    inputs=["Redis CPU 94%", "Postgres migration OK"],
    conclusion="Причина — перегрузка Redis.",
    actions=[{"step": 1, "name": "check_redis_metrics", "args": {"period": "1h"}}],
    domain_hint="diagnostic"
)

# Автоматический retry при REJECT/ESCALATE
result = handle_verdict(verdict, agent_fn, task, inputs, max_retries=2)
```

### Способ 4 — Python API (нет оркестратора)

```python
from minimal_orchestrator import run_with_judge

result = run_with_judge(
    agent_fn=my_agent,        # (task, facts) → (conclusion, actions)
    task="Задача агента",
    facts=["факт 1", "факт 2"],
    domain_hint="diagnostic",
    max_retries=2
)
print(result["conclusion"])      # проверенный вывод
print(result["judge_verdict"])   # финальный вердикт Judge
```

### Способ 5 — CLI-режим (модель сама является судьёй)

Для Claude Code и любых CLI-агентов: модель читает промпты напрямую и выполняет роль парсера и формулировщика. Только Prolog-ядро запускается как subprocess — никаких дополнительных API вызовов.

```python
import sys, json
sys.path.insert(0, "src")
from judge_core import run

# Шаг 1: модель читает src/parser/prompts/parser_v1.md
#         и формирует parsed_facts из входных данных

# Шаг 2: Prolog-ядро (единственный subprocess)
verdict_raw = run(parsed_facts)

# Шаг 3: модель читает src/formulator/prompts/formulator_v1.md
#         и формирует финальный вердикт из (input, verdict_raw)
```

```bash
# Или напрямую из командной строки:
python3 src/judge_core.py parsed_facts.json
python3 src/judge_core.py parsed_facts.json --user-rules my_rules.pl
```

**Когда использовать какой способ:**

| Условие | Способ |
|---|---|
| Внешний агент, нужен HTTP API | Способ 2 (сервер) |
| Есть свой оркестратор на Python | Способ 3 |
| Нет оркестратора | Способ 4 |
| Claude Code / CLI-агент | Способ 5 (judge_core) |
| Баланс API исчерпан / нет ключа | Способ 5 (judge_core) |

---

## Формат входных данных

```json
{
  "schema_version": "1.0",
  "request_id": "uuid-v4",
  "task": "Исходная задача пользователя",
  "inputs": [
    {
      "id": "in_001",
      "text": "Сырой результат инструмента или факт",
      "source": "monitoring"
    }
  ],
  "conclusion": "Финальный вывод агента",
  "actions": [
    {"step": 1, "name": "имя_инструмента", "args": {"ключ": "значение"}}
  ],
  "domain_hint": "diagnostic"
}
```

`domain_hint` — подсказка для парсера: `diagnostic` `code` `research` `planning` `analysis` `medical` `other`.

**Поведение при вердикте:**

| Вердикт | Что делать оркестратору |
|---|---|
| `APPROVE` | Отдать ответ пользователю |
| `ESCALATE` | Retry агента с `feedback` в контексте |
| `REJECT` | Retry агента с `feedback` в контексте |

При исчерпании `max_retries` — отдать последний ответ с пометкой `[Judge: не прошло проверку]`.

---

## Пользовательские правила

Prolog-правила можно расширять не меняя базовый код. Пользователь **только добавляет** новые `issue/1` — удалять или переопределять базовые нельзя.

```prolog
% my_rules.pl
:- multifile issue/1.

% Кастомное правило для медицинского домена
issue(missing_rct) :-
    task_type(research),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

% Можно добавить своё правило вердикта
verdict(escalate) :-
    \+ verdict(reject),
    issue(missing_rct).
```

```bash
# Подключение
python3 cli.py audit input.json --rules my_rules.pl
python3 cli.py serve --rules my_rules.pl
```

Готовые примеры в `src/examples/user_rules/`:
- `medical_research.pl` — `missing_rct`, `manufacturer_bias`
- `code_review.pl` — правила для код-ревью

---

## Тесты

```bash
# Prolog-ядро (16 тестов)
swipl -g "load_files('tests/core.plt'), run_tests, halt" -t halt

# Парсер с моком LLM (12 тестов)
python3 tests/parser_test.py

# Формулировщик с моком LLM (13 тестов)
python3 tests/formulator_test.py

# E2E полный путь (6 тестов)
python3 tests/e2e_test.py

# Пользовательские правила (4 теста)
python3 tests/user_rules_test.py
```

**Итого: 51 тест, все зелёные.** LLM в тестах замокан через `patch("parser.bj_parser._call_llm")` — тесты детерминированы и не тратят API.

Фикстуры в `tests/fixtures/` — размеченные кейсы по всем доменам:

| Файл | Домен | Ожидаемый вердикт |
|---|---|---|
| `001_redis_loop.json` | diagnostic | REJECT |
| `002_medical_weak_evidence.json` | research | REJECT |
| `003_planning_uncovered_requirement.json` | planning | REJECT |
| `004_code_clean_approve.json` | code | APPROVE |
| `005_aesthetic_abstain.json` | other | ESCALATE (legacy) |
| `006_parser_low_confidence_guard.json` | analysis | ESCALATE |

---

## Живые тесты

Результаты прогонов через CLI-режим без API — см. [`docs/live_tests.md`](docs/live_tests.md):

| Сценарий | Домен | Вердикт | Issues |
|---|---|---|---|
| Агент диагностирует Redis, игнорирует Gateway log | diagnostic | REJECT 0.17 | confirmation_bias, process_loop, weak_evidence |
| Продуктовый агент рекомендует запуск push-уведомлений | planning | REJECT 0.16 | confirmation_bias, process_loop, weak_evidence |

---

## Структура репозитория

```
blind-judge/
├── cli.py                          # CLI: audit / serve
├── SKILL.md                        # инструкция по интеграции для оркестратора
├── CONTRACT.md                     # архитектурный контракт (источник истины)
│
├── schemas/                        # JSON Schema — контракты между компонентами
│   ├── input.schema.json
│   ├── parsed_facts.schema.json
│   ├── verdict_raw.schema.json
│   └── final_verdict.schema.json
│
├── src/
│   ├── config.py                   # загрузка ~/.blind-judge/config.yaml
│   ├── judge.py                    # оркестратор: parser → core → formulator
│   ├── judge_core.py               # Prolog-only core для CLI-режима
│   ├── api.py                      # FastAPI HTTP сервер
│   ├── orchestrator_hook.py        # хук для внешнего оркестратора
│   ├── minimal_orchestrator.py     # минимальный оркестратор без зависимостей
│   │
│   ├── parser/
│   │   ├── bj_parser.py            # LLM-вызов + JSON Schema валидация + retry
│   │   └── prompts/parser_v1.md   # промпт парсера
│   │
│   ├── core/
│   │   ├── blind_judge.pl          # базовые правила (issue/1, verdict/1)
│   │   ├── facts_loader.pl         # JSON → Prolog факты
│   │   ├── verdict.pl              # final_verdict/1, core_confidence/1
│   │   └── run_core.py             # Python-мост к SWI-Prolog subprocess
│   │
│   ├── formulator/
│   │   ├── formulator.py           # LLM-вызов + структурная валидация
│   │   └── prompts/formulator_v1.md
│   │
│   ├── legacy/
│   │   └── legacy_judge_prompt.md  # монолитный судья для субъективных задач
│   │
│   └── examples/user_rules/
│       ├── medical_research.pl     # missing_rct, manufacturer_bias
│       └── code_review.pl
│
├── tests/
│   ├── core.plt                    # plunit-тесты Prolog-ядра
│   ├── parser_test.py
│   ├── formulator_test.py
│   ├── e2e_test.py
│   ├── user_rules_test.py
│   └── fixtures/                   # 6 размеченных кейсов
│
├── skills/
│   ├── judge_formal.md             # документация формального режима
│   └── judge_creative.md           # творческий судья
│
└── docs/
    └── live_tests.md               # результаты живых прогонов
```

---

## Схемы данных

Четыре JSON Schema в `schemas/` описывают контракты между компонентами:

```
input.schema.json
    ↓ (Parser)
parsed_facts.schema.json
    ↓ (Prolog Core)
verdict_raw.schema.json
    ↓ (Formulator)
final_verdict.schema.json
```

Все `schema_version` всегда `"1.0"`. Несовпадение → fail-fast.  
`request_id` — UUID v4, сквозная трассировка через все компоненты.

---

## Ключевые соглашения

- **Цитата обязательна.** Каждое `evidence` должно содержать `proof_quote` — дословную подстроку из соответствующего `input.text`. Нельзя придумывать поддержку.
- **Атомарность claims.** Один `claim` = одна проверяемая претензия. «Препарат эффективен и безопасен» → два claims.
- **`parser_confidence`** — не оценка правдивости, а уверенность парсера в собственной классификации.
- **Пользовательские правила** только добавляют `issue/1`. Базовые правила защищены от переопределения.
- **`abstain: true`** → Prolog не запускается, управление переходит в legacy LLM-режим.
- **`parser_min_confidence < 0.75`** → APPROVE автоматически становится ESCALATE.
