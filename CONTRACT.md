# Blind Judge — Hybrid Architecture Contract v1

Спецификация для разработки в Claude Code. Это контракт между тремя
компонентами: **Parser** (LLM), **Core** (Prolog), **Formulator** (LLM).
Контракт — точка стабильности; компоненты разрабатываются и тестируются
независимо, но обязаны соблюдать схемы ниже буква в букву.

---

## 0. Архитектура одним взглядом

```
                ┌───────────────────┐
  raw input  →  │ 1. Parser (LLM)   │  → parsed_facts.json
                └───────────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ 2. Core (Prolog)  │  ← user_rules.pl (опционально)
                │  + base rules     │
                └───────────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ verdict_raw.json  │
                └───────────────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ 3. Formulator(LLM)│  → final_verdict.json (отдаётся роутеру)
                └───────────────────┘
```

Парсер не выносит вердиктов. Ядро не понимает естественный язык.
Формулировщик не принимает решений — только переводит структуру в текст.

---

## 1. Вход системы (от роутера)

```json
{
  "schema_version": "1.0",
  "request_id": "uuid-v4",
  "task": "string — исходная задача основного агента",
  "inputs": [
    {
      "id": "in_001",
      "text": "string — сырое содержимое (факт, источник, цитата, лог)",
      "source": "string | null — опциональная метка происхождения"
    }
  ],
  "conclusion": "string — финальный вывод/результат основного агента",
  "actions": [
    {
      "step": 1,
      "name": "string — имя инструмента/действия",
      "args": { "free_form": "object" }
    }
  ],
  "domain_hint": "string | null — опционально: medical|code|research|writing|diagnostic|other"
}
```

**Инварианты:**
- `inputs[].id` уникален в рамках запроса, формат `in_NNN`.
- `actions` может быть пустым массивом (агент не вызывал инструментов).
- `domain_hint` — подсказка для парсера, не влияет на ядро.
- Никаких полей сверх схемы: парсер должен валидировать строго.

---

## 2. Parser → Core (parsed_facts.json)

Это **самый важный артефакт**. От его качества зависит всё. Парсер обязан
работать в **контролируемом словаре** — никаких свободных полей со смыслом.

### 2.1 Схема

```json
{
  "schema_version": "1.0",
  "request_id": "uuid-v4",
  "task_analysis": {
    "task_type": "diagnostic|research|writing|code|planning|analysis|other",
    "formalizable": true,
    "requirements": [
      {
        "id": "req_1",
        "text": "string — что именно требует задача",
        "kind": "must_have|should_have|constraint"
      }
    ]
  },
  "claims": [
    {
      "id": "cl_1",
      "text": "string — атомарная претензия из conclusion",
      "asserted_confidence": "high|medium|low|unstated"
    }
  ],
  "evidence": [
    {
      "id": "ev_1",
      "input_id": "in_001",
      "supports_claim": "cl_1",
      "relation": "direct_support|indirect_support|contradicts|irrelevant",
      "strength": "strong|moderate|weak",
      "proof_quote": "string — дословная цитата из inputs[in_001].text",
      "parser_confidence": 0.92
    }
  ],
  "requirement_coverage": [
    {
      "requirement_id": "req_1",
      "covered": true,
      "covered_by_claim": "cl_1",
      "parser_confidence": 0.85
    }
  ],
  "action_patterns": {
    "total_actions": 5,
    "unique_actions": 3,
    "repeated_groups": [
      {
        "name": "check_redis_metrics",
        "args_signature": "period=1h",
        "occurrences": 2,
        "new_info_between": false
      }
    ]
  },
  "alternatives_considered": {
    "explicit_alternatives_in_conclusion": 0,
    "contradicting_evidence_addressed": false,
    "parser_confidence": 0.78
  },
  "parser_meta": {
    "model": "string",
    "min_confidence": 0.78,
    "warnings": ["string"],
    "abstain": false,
    "abstain_reason": null
  }
}
```

### 2.2 Жёсткие правила парсера

1. **Цитата обязательна.** Любое `evidence` без `proof_quote`, дословно
   присутствующего в `inputs[input_id].text`, отбрасывается. Парсер не имеет
   права придумывать поддержку.
2. **Контролируемый словарь.** Поля `relation`, `strength`,
   `asserted_confidence`, `task_type`, `kind` — только из перечисленных
   значений. Никаких синонимов, никаких новых меток.
3. **Атомарность claims.** Один `claim` = одна проверяемая претензия. Если
   `conclusion` содержит «препарат эффективен и безопасен» — это **два**
   claims, не один.
4. **`parser_confidence` на каждом решении.** От 0.0 до 1.0. Это не оценка
   правдивости содержимого, а **уверенность парсера в собственной
   классификации**.
5. **Право на abstain.** Если задача не формализуется (художественная оценка,
   эстетика, вкусовщина) — парсер ставит `formalizable: false` и
   `abstain: true` с причиной. Ядро тогда переходит в legacy-режим (см. §6).
6. **Никаких вердиктов.** Парсер не имеет права писать слова `approve`,
   `reject`, `escalate`, `issue` или их синонимов где бы то ни было в выводе.

### 2.3 Двойной парсинг (опция, рекомендована для prod)

Парсер запускается дважды с разными температурами или формулировками. Если
расхождение по ключевым полям (`relation`, `strength`, `covered`) превышает
порог — выставляется `warnings: ["parser_disagreement"]` и
`min_confidence` принудительно занижается. Ядро это увидит и поднимет вердикт.

---

## 3. Core (Prolog)

### 3.1 Загрузка фактов

JSON конвертируется в факты Пролога однозначно:

```prolog
task_type(diagnostic).
formalizable(true).

requirement(req_1, must_have, "вернуть причину 500-ошибки").

claim(cl_1, "Причина — перегрузка Redis", high).

evidence(ev_1, in_001, cl_1, indirect_support, weak, 0.91).
evidence(ev_2, in_003, cl_1, contradicts, strong, 0.94).

requirement_coverage(req_1, true, cl_1, 0.85).

action_repeat(check_redis_metrics, "period=1h", 2, false).

alternatives_considered(0, false, 0.78).

parser_min_confidence(0.78).
parser_abstain(false).
```

Конвертер — отдельный модуль (`facts_loader.pl`), тестируется на фикстурах.

### 3.2 Базовые правила (ядро)

```prolog
% --- Process loop ---
issue(process_loop) :-
    action_repeat(_, _, N, false), N >= 2.

% --- Weak evidence ---
issue(weak_evidence) :-
    claim(C, _, high),
    \+ evidence(_, _, C, direct_support, strong, _).

issue(weak_evidence) :-
    claim(C, _, high),
    findall(E, evidence(E, _, C, _, strong, _), Strong),
    length(Strong, 0),
    findall(E, evidence(E, _, C, _, moderate, _), Mod),
    length(Mod, L), L =< 1.

% --- Unsupported conclusion ---
issue(unsupported_conclusion) :-
    claim(C, _, _),
    \+ evidence(_, _, C, direct_support, _, _),
    \+ evidence(_, _, C, indirect_support, _, _).

issue(unsupported_conclusion) :-
    requirement(R, must_have, _),
    requirement_coverage(R, false, _, _).

% --- Confirmation bias ---
issue(confirmation_bias) :-
    evidence(_, _, C, contradicts, Strength, _),
    member(Strength, [strong, moderate]),
    alternatives_considered(0, false, _),
    claim(C, _, _).

% --- Verdict composition ---
verdict(reject) :-
    issue(unsupported_conclusion).
verdict(reject) :-
    issue(process_loop), issue(confirmation_bias).
verdict(escalate) :-
    \+ verdict(reject),
    (issue(weak_evidence) ; issue(confirmation_bias) ; issue(process_loop)).
verdict(approve) :-
    \+ issue(_).

% --- Parser confidence escalation guard ---
final_verdict(escalate) :-
    verdict(approve),
    parser_min_confidence(C), C < 0.75, !.
final_verdict(reject) :-
    verdict(reject), !.
final_verdict(escalate) :-
    verdict(escalate), !.
final_verdict(approve) :-
    verdict(approve).
```

Это **минимально работающий набор**. Расширяется без переписывания.

### 3.3 Confidence ядра

Численная уверенность вердикта считается отдельным предикатом из:
- количества и силы issues,
- `parser_min_confidence`,
- покрытия требований.

```prolog
core_confidence(Score) :-
    findall(I, issue(I), Issues),
    length(Issues, N),
    parser_min_confidence(P),
    base_score(N, Base),
    Score is Base * P.

base_score(0, 0.95).
base_score(1, 0.7).
base_score(2, 0.45).
base_score(N, 0.2) :- N >= 3.
```

Точные коэффициенты калибруются на корпусе — это первая задача после
запуска MVP.

### 3.4 Подключение пользовательских правил

```prolog
:- module(blind_judge, [audit/2]).
:- multifile issue/1.
:- discontiguous issue/1.

% Пользователь в своём файле:
:- use_module(library(blind_judge)).

issue(missing_rct) :-
    task_type(research),
    domain(medical),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

% Пользователь может также добавлять правила вердикта:
verdict(reject) :- issue(missing_rct).
```

**Контракт расширений:**
- Имена пользовательских issues должны быть в формате `domain_snake_case`.
- Пользовательские issues автоматически попадают в `issues[]` ответа.
- Пользователь не может удалять или переопределять базовые правила —
  только добавлять. Это защита от того, чтобы кто-то «отключил» проверку
  unsupported_conclusion и получил approve на пустом месте.

---

## 4. Core → Formulator (verdict_raw.json)

```json
{
  "schema_version": "1.0",
  "request_id": "uuid-v4",
  "final_verdict": "approve|escalate|reject",
  "core_confidence": 0.42,
  "issues": [
    {
      "code": "process_loop",
      "source": "base",
      "triggered_by": {
        "rule": "issue(process_loop)",
        "facts": ["action_repeat(check_redis_metrics, \"period=1h\", 2, false)"]
      }
    },
    {
      "code": "confirmation_bias",
      "source": "base",
      "triggered_by": {
        "rule": "issue(confirmation_bias)",
        "facts": [
          "evidence(ev_2, in_003, cl_1, contradicts, strong, 0.94)",
          "alternatives_considered(0, false, 0.78)"
        ]
      }
    }
  ],
  "uncovered_requirements": [],
  "parser_meta_passthrough": {
    "min_confidence": 0.78,
    "warnings": [],
    "abstained": false
  }
}
```

`triggered_by` — ключевое поле. Это **трассировка**: какое правило сработало
и на каких фактах. Формулировщик использует её для создания конкретного
фидбэка. Это же делает систему отлаживаемой: при споре всегда можно показать
«вот правило, вот факты, вот вывод».

---

## 5. Formulator → роутер (final_verdict.json)

Финальный ответ системы. Совместим с текущим выходным форматом
Blind Judge, чтобы роутер не пришлось переписывать.

```json
{
  "schema_version": "1.0",
  "request_id": "uuid-v4",
  "verdict": "APPROVE|ESCALATE|REJECT",
  "confidence": 0.42,
  "issues": ["process_loop", "confirmation_bias"],
  "alternative_hypothesis": "string | null",
  "feedback": "string — actionable инструкция для основного агента",
  "trace": {
    "rules_fired": ["issue(process_loop)", "issue(confirmation_bias)"],
    "parser_warnings": [],
    "core_confidence": 0.42
  }
}
```

### 5.1 Обязанности формулировщика

1. **Не менять `verdict`, `issues`, `confidence`.** Они приходят из ядра и
   не подлежат интерпретации. Это закон.
2. **Сгенерировать `alternative_hypothesis`** — глядя на `inputs` и
   сработавшие issues. Если честной альтернативы нет — `null`.
3. **Сгенерировать `feedback`** — короткий, конкретный, по каждому issue
   указать, что именно агенту переделать. Опираться на `triggered_by.facts`.
4. **При `APPROVE`** — `feedback` пустая строка, `alternative_hypothesis` null.
5. **Не добавлять issues**, которых нет в `verdict_raw`. Не «улучшать»
   вердикт. Формулировщик — переводчик, не судья.

---

## 6. Legacy-режим (когда задача не формализуется)

Если `parser.formalizable == false` или `parser.abstain == true`:

1. Ядро не запускается.
2. Управление передаётся **legacy-судье** — это текущий монолитный промпт
   из старого `SKILL.md`, сохранённый как fallback.
3. Финальный JSON помечается полем `mode: "legacy"` в `trace`.

Это честная граница: для оценки художественного текста или вкусовых решений
формальное ядро не годится, и притворяться не нужно.

---

## 7. Структура репозитория (для Claude Code)

```
blind-judge/
├── README.md
├── CONTRACT.md                 ← этот файл
├── package.json | pom.xml      ← в зависимости от стека CLI
│
├── src/
│   ├── parser/
│   │   ├── parser.ts           ← LLM-вызов, валидация JSON-схемы
│   │   ├── prompts/
│   │   │   ├── parser_v1.md
│   │   │   └── parser_v1_alt.md   ← для двойного парсинга
│   │   └── schema/
│   │       └── parsed_facts.schema.json
│   │
│   ├── core/
│   │   ├── blind_judge.pl      ← модуль с базовыми правилами
│   │   ├── facts_loader.pl     ← JSON → факты
│   │   ├── verdict.pl          ← композиция вердикта
│   │   ├── confidence.pl       ← подсчёт core_confidence
│   │   └── bridge/
│   │       ├── jpl_bridge.java     ← если Java
│   │       └── pyswip_bridge.py    ← если Python
│   │
│   ├── formulator/
│   │   ├── formulator.ts
│   │   └── prompts/
│   │       └── formulator_v1.md
│   │
│   ├── legacy/
│   │   └── legacy_judge_prompt.md  ← старый монолитный судья
│   │
│   └── orchestrator.ts         ← склейка: parser → core → formulator
│
├── schemas/
│   ├── input.schema.json
│   ├── parsed_facts.schema.json
│   ├── verdict_raw.schema.json
│   └── final_verdict.schema.json
│
├── examples/
│   └── user_rules/
│       ├── medical_research.pl
│       └── code_review.pl
│
└── tests/
    ├── fixtures/                  ← размеченные кейсы
    │   ├── 001_redis_loop.json
    │   ├── 002_medical_weak.json
    │   ├── 003_writing_offspec.json
    │   └── ...
    ├── parser.test.ts             ← парсер на фикстурах
    ├── core.plt                   ← unit-тесты Пролога (plunit)
    ├── formulator.test.ts
    └── e2e.test.ts                ← полный путь от input до final_verdict
```

---

## 8. Порядок разработки (sprint plan)

**Sprint 0 — фундамент (1–2 дня).**
1. Зафиксировать схемы в `schemas/*.schema.json` (валидируемо JSON Schema).
2. Собрать корпус из 20 размеченных кейсов в `tests/fixtures/`. Минимум по
   3 примера на каждый домен из `task_type`. Включить **граничные случаи**:
   abstain, parser disagreement, невыполненные требования.

**Sprint 1 — ядро на Прологе (2–3 дня).**
1. `facts_loader.pl` + тесты.
2. Базовые `issue/1` правила + `verdict/1` + `final_verdict/1`.
3. `core_confidence/1` с черновой калибровкой.
4. plunit-тесты на корпусе. **Цель: 100% детерминизм на фикстурах.**

**Sprint 2 — парсер (2–3 дня).**
1. Промпт `parser_v1.md` с явным контролируемым словарём и требованием
   цитат-пруфов.
2. JSON Schema валидация выхода парсера. Невалидный JSON →
   автоматический retry, затем abstain.
3. Тесты парсера на фикстурах: проверяем не вердикты, а классификации.

**Sprint 3 — формулировщик (1 день).**
1. Промпт, который принимает `verdict_raw.json` и пишет `feedback`.
2. Жёсткое ограничение: не менять структурные поля.
3. Snapshot-тесты.

**Sprint 4 — оркестратор + legacy fallback (1 день).**
1. Склейка трёх компонент.
2. Маршрутизация в legacy при abstain.
3. e2e-тесты.

**Sprint 5 — пользовательские правила (1 день).**
1. Механизм подключения через `:- use_module`.
2. Защита базовых правил от переопределения.
3. Два примера в `examples/user_rules/`.

**Sprint 6 — калибровка (постоянно).**
1. Расширить корпус до 100+ кейсов.
2. Подкрутить пороги в `confidence.pl` и `base_score/2`.
3. Подкрутить промпт парсера по систематическим ошибкам.

---

## 9. Критические инварианты (нельзя нарушать никогда)

1. **Парсер не выносит вердиктов.** Никогда. Любая попытка — баг.
2. **Ядро не понимает естественный язык.** Только символы из словаря.
3. **Формулировщик не меняет структурные поля.** Только текстовые.
4. **Каждое evidence обязано иметь дословную цитату из inputs.**
5. **Низкая `parser_min_confidence` всегда поднимает вердикт на уровень
   осторожности.** APPROVE → ESCALATE автоматически.
6. **Пользовательские правила могут только добавлять issues, не удалять.**
7. **При abstain — переход в legacy, никаких самодельных вердиктов из ядра
   на пустых фактах.**
8. **Версия схемы (`schema_version`) проверяется на каждом шаге.** Mismatch
   → fail-fast, не молчаливая деградация.

---

## 10. Что НЕ входит в v1 (осознанно отложено)

- Multi-turn judging (когда судья ведёт диалог с агентом).
- Обучаемая калибровка confidence (пока вручную).
- Параллельный запуск нескольких пользовательских наборов правил.
- Web-UI для отладки трасс (только CLI и логи).
- Кэширование результатов парсера по хэшу входа (легко добавить позже).

Эти пункты — естественное продолжение, но v1 должен быть запускаемым и
полезным без них.

---

## 11. Открытые вопросы (решить до Sprint 1)

1. **Стек CLI.** Java + JPL или Node/Python + REST к SWI-Prolog как сервису?
   От ответа зависит структура `bridge/`.
2. **Модель парсера.** Haiku хватит для контролируемого словаря, или нужен
   Sonnet? Решается замером на корпусе.
3. **Двойной парсинг — обязательный или опциональный флаг?** Удваивает
   стоимость, но снижает риск ошибок классификации.
4. **Где живут пользовательские правила** — рядом с проектом пользователя
   или в отдельной директории, регистрируемой через конфиг?

Ответы на эти четыре вопроса замораживают архитектуру до конца v1.
