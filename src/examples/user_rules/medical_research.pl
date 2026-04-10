% medical_research.pl — дополнительные правила для медицинских исследований
% Подключение: blind-judge serve --rules src/examples/user_rules/medical_research.pl

% Высокое утверждение в медицинском домене без RCT требует escalate
issue(missing_rct) :-
    task_type(research),
    claim(_, _, high),
    \+ evidence(_, _, _, direct_support, strong, _).

% Источник производителя без независимого подтверждения — слабая доказательная база
issue(manufacturer_bias) :-
    claim(C, _, _),
    evidence(_, _, C, direct_support, weak, _),
    \+ evidence(_, _, C, direct_support, strong, _),
    \+ evidence(_, _, C, indirect_support, strong, _).

% Пользовательские правила вердикта
verdict(escalate) :-
    \+ verdict(reject),
    issue(missing_rct).

verdict(escalate) :-
    \+ verdict(reject),
    issue(manufacturer_bias).
