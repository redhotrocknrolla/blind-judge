---
name: blind-judge-formal
description: >
  Формальный судья Blind Judge. Активируется автоматически для задач с
  проверяемыми фактами и требованиями. Использует Prolog-ядро — детерминированный,
  трассируемый, расширяемый пользовательскими правилами. Покрывает: диагностику,
  исследования, планирование, code review, анализ данных.
---

# Blind Judge — Formal Mode

Гибридный пайплайн: LLM-парсер → Prolog-ядро → LLM-формулировщик.
Детерминированный вердикт с полной трассировкой.

---

## Когда активируется этот режим

Задача формализуема если:
- Есть проверяемые требования (must_have, should_have)
- Вывод можно сопоставить с фактами логически
- Есть action trace который можно проверить на loops
- Домен: diagnostic, research, planning, code, analysis

---

## Что проверяет Prolog-ядро

### process_loop
Повторяющиеся вызовы инструментов с одинаковыми аргументами
без новых данных между ними. N ≥ 2 → issue.

### weak_evidence
Высокое утверждение (`asserted_confidence: high`) без прямого
сильного доказательства (`direct_support, strong`).

### confirmation_bias
Есть contradicting evidence средней или высокой силы,
но агент не рассмотрел альтернативы (`alternatives_considered: 0, false`).

### unsupported_conclusion
- Утверждение без какой-либо поддержки (ни direct, ни indirect)
- Или: must_have требование не покрыто ни одним claim

---

## Правила вердикта (детерминированные)

| Вердикт | Условие |
|---------|---------|
| `REJECT` | `unsupported_conclusion` ИЛИ (`process_loop` И `confirmation_bias`) |
| `ESCALATE` | Нет REJECT, но есть любой другой issue |
| `ESCALATE` | Нет issues, но `parser_min_confidence < 0.75` |
| `APPROVE` | Нет issues, confidence ≥ 0.75 |

---

## Трассировка

Каждый вердикт содержит полную трассировку:

```json
{
  "trace": {
    "rules_fired": ["issue(process_loop)", "issue(confirmation_bias)"],
    "parser_warnings": [],
    "core_confidence": 0.17,
    "mode": "hybrid"
  }
}
```

При споре всегда можно показать: какое правило сработало и на каких фактах.

---

## Пользовательские правила

Расширяется через `--rules path.pl`:

```prolog
:- multifile issue/1.

issue(missing_rct) :-
    task_type(research),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

verdict(escalate) :-
    \+ verdict(reject),
    issue(missing_rct).
```

Базовые правила защищены — пользователь может только добавлять.

---

## Confidence ядра
base_score(0 issues) = 0.95
base_score(1 issue)  = 0.70
base_score(2 issues) = 0.45
base_score(3+ issues) = 0.20
core_confidence = base_score × parser_min_confidence
