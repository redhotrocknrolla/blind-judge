:- multifile issue/1.
:- discontiguous issue/1.

issue(process_loop) :-
    action_repeat(_, _, N, false), N >= 2.

issue(weak_evidence) :-
    claim(C, _, high),
    \+ evidence(_, _, C, direct_support, strong, _).

issue(weak_evidence) :-
    claim(C, _, high),
    findall(E, evidence(E, _, C, _, strong, _), Strong), length(Strong, 0),
    findall(E, evidence(E, _, C, _, moderate, _), Mod), length(Mod, L), L =< 1.

issue(unsupported_conclusion) :-
    claim(C, _, _),
    \+ evidence(_, _, C, direct_support, _, _),
    \+ evidence(_, _, C, indirect_support, _, _).

issue(unsupported_conclusion) :-
    requirement(R, must_have, _),
    requirement_coverage(R, false, _, _).

issue(confirmation_bias) :-
    evidence(_, _, C, contradicts, Strength, _),
    member(Strength, [strong, moderate]),
    alternatives_considered(0, false, _),
    claim(C, _, _).

verdict(reject) :-
    issue(unsupported_conclusion), !.
verdict(reject) :-
    issue(process_loop), issue(confirmation_bias), !.
verdict(escalate) :-
    \+ verdict(reject),
    ( issue(weak_evidence) ; issue(confirmation_bias) ; issue(process_loop) ), !.
verdict(approve) :-
    \+ issue(_).
