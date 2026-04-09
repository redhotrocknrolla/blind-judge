:- use_module(library(plunit)).
:- use_module(library(json)).
:- ['/Users/redhotrocknrolla/projects/blind-judge/src/core/facts_loader'].
:- ['/Users/redhotrocknrolla/projects/blind-judge/src/core/verdict'].

load_fixture(FixturePath) :-
    setup_call_cleanup(
        open(FixturePath, read, RS),
        json_read_dict(RS, FixtureDict, []),
        close(RS)
    ),
    get_dict(expected_parsed_facts, FixtureDict, PF),
    load_facts_from_dict(PF).

:- begin_tests(core).

test(f001_verdict) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/001_redis_loop.json'),
    final_verdict(V), V == reject.
test(f001_issues) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/001_redis_loop.json'),
    unique_issues(Issues),
    Issues == [confirmation_bias, process_loop, weak_evidence].
test(f001_confidence) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/001_redis_loop.json'),
    core_confidence(Score), Score =:= 0.17.

test(f002_verdict) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/002_medical_weak_evidence.json'),
    final_verdict(V), V == escalate.
test(f002_issues) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/002_medical_weak_evidence.json'),
    unique_issues(Issues),
    Issues == [confirmation_bias, weak_evidence].
test(f002_confidence) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/002_medical_weak_evidence.json'),
    core_confidence(Score), Score =:= 0.36.

test(f003_verdict) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/003_planning_uncovered_requirement.json'),
    final_verdict(V), V == reject.
test(f003_issues) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/003_planning_uncovered_requirement.json'),
    unique_issues(Issues),
    Issues == [unsupported_conclusion].
test(f003_confidence) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/003_planning_uncovered_requirement.json'),
    core_confidence(Score), Score =:= 0.62.
test(f003_uncovered_req) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/003_planning_uncovered_requirement.json'),
    requirement(req_3, must_have, _),
    requirement_coverage(req_3, false, _, _).

test(f004_verdict) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/004_code_clean_approve.json'),
    final_verdict(V), V == approve.
test(f004_issues) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/004_code_clean_approve.json'),
    unique_issues(Issues),
    Issues == [].
test(f004_confidence) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/004_code_clean_approve.json'),
    core_confidence(Score), Score =:= 0.86.

test(f006_verdict) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/006_parser_low_confidence_guard.json'),
    final_verdict(V), V == escalate.
test(f006_issues) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/006_parser_low_confidence_guard.json'),
    unique_issues(Issues),
    Issues == [].
test(f006_confidence) :-
    load_fixture('/Users/redhotrocknrolla/projects/blind-judge/tests/fixtures/006_parser_low_confidence_guard.json'),
    core_confidence(Score), Score =:= 0.59.

:- end_tests(core).
