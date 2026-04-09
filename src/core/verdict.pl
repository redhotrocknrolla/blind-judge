:- [blind_judge].

unique_issues(Issues) :-
    findall(I, issue(I), All),
    sort(All, Issues).

% Confidence guard
final_verdict(escalate) :-
    verdict(approve),
    parser_min_confidence(C), C < 0.75, !.
final_verdict(reject) :-
    verdict(reject), !.
final_verdict(escalate) :-
    verdict(escalate), !.
final_verdict(approve) :-
    verdict(approve), !.

base_score(0, 0.95) :- !.
base_score(1, 0.70) :- !.
base_score(2, 0.45) :- !.
base_score(N, 0.20) :- N >= 3, !.

core_confidence(Score) :-
    unique_issues(Issues),
    length(Issues, N),
    parser_min_confidence(P),
    base_score(N, Base),
    Score is round(Base * P * 100) / 100.
