# Live Tests — реальные прогоны Judge

Результаты живых прогонов через CLI-режим (модель сама выполняет роль парсера и формулировщика, Prolog-ядро — subprocess).

---

## Test 1 — Diagnostic: Redis overload (2026-04-10)

**Домен:** diagnostic  
**Сценарий:** Агент диагностировал 500-ошибку на checkout endpoint и пришёл к выводу что причина — перегрузка Redis. Дважды вызвал один и тот же инструмент. Проигнорировал Payment Gateway log.

### Input

```json
{
  "task": "Найти причину 500-ошибки на checkout endpoint",
  "inputs": [
    {"id": "in_001", "text": "Redis CPU: 94% за 2 минуты до инцидента", "source": "monitoring"},
    {"id": "in_002", "text": "Postgres migration завершилась успешно в 14:20:00", "source": "deploy_log"},
    {"id": "in_003", "text": "Payment Gateway log: JSON parse error at 14:23:01 UTC", "source": "gateway_log"},
    {"id": "in_004", "text": "Checkout 500 error timestamp: 14:23:02 UTC", "source": "app_log"}
  ],
  "conclusion": "Причина — перегрузка Redis.",
  "actions": [
    {"step": 1, "name": "check_redis_metrics", "args": {"period": "1h"}},
    {"step": 2, "name": "check_redis_metrics", "args": {"period": "1h"}},
    {"step": 3, "name": "check_redis_connections", "args": {}}
  ],
  "domain_hint": "diagnostic"
}
```

### Verdict

```json
{
  "verdict": "REJECT",
  "confidence": 0.17,
  "issues": ["confirmation_bias", "process_loop", "weak_evidence"],
  "alternative_hypothesis": "Реальной причиной 500-ошибки мог быть JSON parse error в Payment Gateway (in_003, 14:23:01 UTC) — за одну секунду до инцидента (in_004, 14:23:02 UTC). Redis CPU 94% — коррелят во времени, но не прямая причина: высокая нагрузка на Redis не объясняет ошибку парсинга JSON на уровне Gateway.",
  "feedback": "confirmation_bias: in_003 («Payment Gateway log: JSON parse error at 14:23:01 UTC») прямо противоречит выводу о Redis и хронологически предшествует 500-ошибке на 1 секунду — этот факт полностью проигнорирован. process_loop: check_redis_metrics(period=1h) вызван дважды подряд (steps 1 и 2) с идентичными аргументами без новых данных между вызовами. weak_evidence: утверждение «причина — перегрузка Redis» заявлено без оговорок, но опирается только на косвенную корреляцию (Redis CPU 94%). Нет Redis connection timeout, нет redis.log с ошибками, нет slowlog записей.",
  "trace": {
    "rules_fired": ["issue(confirmation_bias)", "issue(process_loop)", "issue(weak_evidence)/1"],
    "parser_warnings": [],
    "core_confidence": 0.17,
    "mode": "hybrid"
  }
}
```

### Prolog trace

| Issue | Правило | Факты |
|---|---|---|
| `confirmation_bias` | `issue(confirmation_bias)` | `evidence(ev_3, in_003, cl_1, contradicts, moderate, 0.87)`, `alternatives_considered(0, false, 0.94)` |
| `process_loop` | `issue(process_loop)` | `action_repeat(check_redis_metrics, "period=1h", 2, false)` |
| `weak_evidence` | `issue(weak_evidence)/1` | `claim(cl_1, _, high)`, `no_evidence(direct_support, strong, cl_1)` |

**Verdict path:** `verdict(reject) :- issue(process_loop), issue(confirmation_bias), !`  
**Confidence:** `base_score(3) × min_confidence = 0.20 × 0.87 = 0.17`

---

## Test 2 — Planning: Push notifications launch (2026-04-10)

**Домен:** planning  
**Сценарий:** Продуктовый агент анализирует A/B тест push-уведомлений и рекомендует запуск. Дублирует вызов инструмента. Игнорирует churn power-users и негативные отзывы.

### Input

```json
{
  "task": "Определить стоит ли запускать фичу push-уведомлений в мобильном приложении",
  "inputs": [
    {"id": "in_001", "text": "A/B тест: группа с уведомлениями показала CTR 12% vs 8% в контрольной (n=2400)", "source": "ab_test"},
    {"id": "in_002", "text": "User survey: 67% пользователей оценили уведомления позитивно", "source": "survey"},
    {"id": "in_003", "text": "Retention report: пользователи с ≥5 сессиями в неделю (power users) показали churn +3.2% в тестовой группе за 30 дней", "source": "analytics"},
    {"id": "in_004", "text": "App store reviews: 14 новых отзывов упоминают «слишком много уведомлений» за период теста", "source": "app_store"}
  ],
  "conclusion": "Уведомления увеличивают вовлечённость — фичу рекомендую к запуску.",
  "actions": [
    {"step": 1, "name": "query_ab_test_results", "args": {"feature": "push_notifications", "metric": "ctr"}},
    {"step": 2, "name": "query_ab_test_results", "args": {"feature": "push_notifications", "metric": "ctr"}},
    {"step": 3, "name": "fetch_user_survey", "args": {"feature": "push_notifications"}}
  ],
  "domain_hint": "planning"
}
```

### Verdict

```json
{
  "verdict": "REJECT",
  "confidence": 0.16,
  "issues": ["confirmation_bias", "process_loop", "weak_evidence"],
  "alternative_hypothesis": "Push-уведомления могут увеличивать краткосрочный CTR за счёт оттока наиболее ценных пользователей: power users (≥5 сессий/нед) показали churn +3.2% за 30 дней в тестовой группе. Чистый эффект на retention и LTV, вероятно, отрицательный — запуск без сегментации рискует навредить ядру аудитории.",
  "feedback": "confirmation_bias: in_003 фиксирует churn +3.2% среди power users за 30 дней (strong) — именно power users генерируют непропорциональную долю LTV. in_004 фиксирует 14 отзывов «слишком много уведомлений» (moderate). Оба источника проигнорированы. process_loop: query_ab_test_results(feature=push_notifications, metric=ctr) вызван дважды подряд (steps 1 и 2) с идентичными аргументами без новых данных. Вместо повтора следовало вызвать query_ab_test_results(metric=retention_30d). weak_evidence: CTR 12% vs 8% — прокси кликабельности, не вовлечённости. Нет retention_30d, нет DAU/MAU ratio, нет глубины сессий.",
  "trace": {
    "rules_fired": ["issue(confirmation_bias)", "issue(process_loop)", "issue(weak_evidence)/1"],
    "parser_warnings": [],
    "core_confidence": 0.16,
    "mode": "hybrid"
  }
}
```

### Prolog trace

| Issue | Правило | Факты |
|---|---|---|
| `confirmation_bias` | `issue(confirmation_bias)` | `evidence(ev_3, in_003, cl_1, contradicts, strong, 0.91)`, `evidence(ev_4, in_004, cl_1, contradicts, moderate, 0.83)`, `alternatives_considered(0, false, 0.91)` |
| `process_loop` | `issue(process_loop)` | `action_repeat(query_ab_test_results, "feature=push_notifications,metric=ctr", 2, false)` |
| `weak_evidence` | `issue(weak_evidence)/1` | `claim(cl_1, _, high)`, `no_evidence(direct_support, strong, cl_1)` |

**Verdict path:** `verdict(reject) :- issue(process_loop), issue(confirmation_bias), !`  
**Confidence:** `base_score(3) × min_confidence = 0.20 × 0.82 = 0.16`

---

## Test 3 — Brand strategy: tone of voice choice (2026-04-10)

**Домен:** brand strategy (субъективный)  
**Режим:** legacy (Prolog не запускался)  
**Сценарий:** Брендинговый агент рекомендует дерзкий провокационный тон для финтех-продукта. Игнорирует retention-данные конкурента с противоположным выбором.

### Input

```json
{
  "task": "Какой тон коммуникации выбрать для нового продукта — дерзкий и провокационный или спокойный и экспертный?",
  "inputs": [
    {"id": "in_001", "text": "Бриф: B2C финтех-продукт для аудитории 22–35 лет, позиционирование — 'банкинг без бюрократии', конкуренты — Тинькофф, Revolut", "source": "brief"},
    {"id": "in_002", "text": "Фокус-группа, 24 участника, 22–35 лет: 71% описали бренды конкурентов как 'формальные' и 'скучные'", "source": "research"},
    {"id": "in_003", "text": "Примеры кампаний Revolut: 'Банк, который не спрашивает зачем тебе деньги', 'Мы не ваш дедушкин банк'", "source": "competitor_examples"},
    {"id": "in_004", "text": "Retention-отчёт Тинькофф 2023: 84% retention в сегменте 25–35 при последовательном экспертном tone-of-voice на протяжении трёх лет", "source": "analytics"}
  ],
  "conclusion": "Рекомендую дерзкий и провокационный тон — аудитория хочет свежести, конкуренты скучные, значит дерзость выделит продукт.",
  "actions": [
    {"step": 1, "name": "search_competitor_tone", "args": {"brand": "revolut"}},
    {"step": 2, "name": "fetch_focus_group_results", "args": {"segment": "22-35"}},
    {"step": 3, "name": "search_competitor_tone", "args": {"brand": "tinkoff"}}
  ],
  "domain_hint": "other"
}
```

### Parser: abstain=true

Задача — выбор между двумя эстетическими стратегиями без объективного критерия правильности. `formalizable: false`, `abstain: true`. Prolog пропущен.

```json
{
  "task_analysis": {"task_type": "other", "formalizable": false, "requirements": []},
  "claims": [],
  "evidence": [],
  "parser_meta": {
    "abstain": true,
    "abstain_reason": "Выбор тона коммуникации — эстетическое и стратегическое суждение без объективных критериев правильности. Оба варианта имеют прецеденты успеха. Формальная верификация невозможна."
  }
}
```

### Verdict (legacy mode)

```json
{
  "verdict": "ESCALATE",
  "confidence": 0.38,
  "issues": ["confirmation_bias", "weak_evidence", "unsupported_conclusion"],
  "alternative_hypothesis": "Экспертный тон может быть более выигрышным: in_004 показывает 84% retention у Тинькофф именно в целевом сегменте 25–35 при экспертном голосе. Дерзкий тон в финтехе к 2024 году перестал быть дифференцирующим — Revolut, Monobank, N26 уже его занимают. Альтернативная гипотеза: спокойный экспертный тон с элементами живого языка создаёт более устойчивое доверие в финансовом продукте.",
  "feedback": "Три проблемы требуют проработки. Первое — in_004 (Тинькофф, retention 84%, экспертный тон, сегмент 25–35) прямо противоречит выводу и полностью проигнорирован: объясни почему этот прецедент не применим, или скорректируй рекомендацию. Второе — аргумент «конкуренты скучные → дерзость выделит нас» предполагает что дерзость ещё не занята: проверь насыщенность рынка дерзким тоном (Revolut, Monobank, N26 уже там). Третье — фокус-группа (in_002) измерила восприятие существующих брендов, но не тестировала предпочтение между двумя тонами для нового продукта.",
  "trace": {
    "rules_fired": [],
    "parser_warnings": [],
    "core_confidence": 0.38,
    "mode": "legacy"
  }
}
```

### Legacy trace

| Issue | Ось проверки | Обоснование |
|---|---|---|
| `confirmation_bias` | Confirmation bias | in_004 (Тинькофф 84% retention с экспертным тоном) проигнорирован |
| `weak_evidence` | Байесовская согласованность | Уверенный вывод при противоречивых данных — confidence завышена |
| `unsupported_conclusion` | Логическая корректность | «Конкуренты скучные → дерзость выделит нас» — логический скачок без проверки насыщенности рынка |

**Prolog:** не запускался (`abstain=true`)  
**mode:** `"legacy"`  
**Confidence:** 0.38 (противоречивые данные, субъективная задача)
