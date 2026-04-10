% code_review.pl — дополнительные правила для code review задач
% Подключение: blind-judge serve --rules src/examples/user_rules/code_review.pl

% Нет тестов подтверждающих исправление — нельзя approve
issue(no_test_evidence) :-
    task_type(code),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

% Изменение без упоминания тестов в логе действий
issue(untested_change) :-
    task_type(code),
    \+ action_repeat('run_tests', _, _, _),
    claim(_, _, high).

verdict(reject) :-
    issue(no_test_evidence).
