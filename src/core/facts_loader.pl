% facts_loader.pl — не модуль, факты ассертируются в user-пространство
:- use_module(library(json)).

:- dynamic task_type/1.
:- dynamic formalizable/1.
:- dynamic requirement/3.
:- dynamic claim/3.
:- dynamic evidence/6.
:- dynamic requirement_coverage/4.
:- dynamic action_repeat/4.
:- dynamic alternatives_considered/3.
:- dynamic parser_min_confidence/1.
:- dynamic parser_abstain/1.
:- dynamic parser_warnings/1.
:- dynamic request_id/1.
:- dynamic schema_version/1.

retract_all_facts :-
    retractall(task_type(_)),
    retractall(formalizable(_)),
    retractall(requirement(_, _, _)),
    retractall(claim(_, _, _)),
    retractall(evidence(_, _, _, _, _, _)),
    retractall(requirement_coverage(_, _, _, _)),
    retractall(action_repeat(_, _, _, _)),
    retractall(alternatives_considered(_, _, _)),
    retractall(parser_min_confidence(_)),
    retractall(parser_abstain(_)),
    retractall(parser_warnings(_)),
    retractall(request_id(_)),
    retractall(schema_version(_)).

% JSON-строка → атом; числа и булевы проходят насквозь
s(X, X) :- atom(X), !.
s(X, X) :- number(X), !.
s(X, X) :- is_list(X), !.
s(X, A) :- string(X), !, atom_string(A, X).

load_facts(File) :-
    setup_call_cleanup(
        open(File, read, Stream),
        json_read_dict(Stream, Dict, []),
        close(Stream)
    ),
    load_facts_from_dict(Dict).

load_facts_from_dict(Dict) :-
    retract_all_facts,
    assert_all(Dict).

assert_all(Dict) :-
    get_dict(schema_version, Dict, V),
    ( V = "1.0" -> true
    ; throw(error(schema_version_mismatch(V), context(facts_loader, _))) ),
    assertz(schema_version('1.0')),

    get_dict(request_id, Dict, RID),
    s(RID, RIDa), assertz(request_id(RIDa)),

    get_dict(task_analysis, Dict, TA),
    get_dict(task_type, TA, TT), s(TT, TTa), assertz(task_type(TTa)),
    get_dict(formalizable, TA, Formal), assertz(formalizable(Formal)),
    get_dict(requirements, TA, Reqs), maplist(assert_req, Reqs),

    get_dict(claims, Dict, Claims), maplist(assert_claim, Claims),

    get_dict(evidence, Dict, Evs), maplist(assert_ev, Evs),

    get_dict(requirement_coverage, Dict, Cov), maplist(assert_cov, Cov),

    get_dict(action_patterns, Dict, AP),
    get_dict(repeated_groups, AP, Groups), maplist(assert_action, Groups),

    get_dict(alternatives_considered, Dict, AC),
    get_dict(explicit_alternatives_in_conclusion, AC, AltN),
    get_dict(contradicting_evidence_addressed, AC, Addr),
    get_dict(parser_confidence, AC, AltConf),
    assertz(alternatives_considered(AltN, Addr, AltConf)),

    get_dict(parser_meta, Dict, PM),
    get_dict(min_confidence, PM, MinC), assertz(parser_min_confidence(MinC)),
    get_dict(abstain, PM, Ab), assertz(parser_abstain(Ab)),
    get_dict(warnings, PM, Ws), assertz(parser_warnings(Ws)).

assert_req(R) :-
    get_dict(id, R, Id), get_dict(kind, R, Kind), get_dict(text, R, Text),
    s(Id, IdA), s(Kind, KA),
    assertz(requirement(IdA, KA, Text)).

assert_claim(C) :-
    get_dict(id, C, Id), get_dict(text, C, Text),
    get_dict(asserted_confidence, C, Conf),
    s(Id, IdA), s(Conf, ConfA),
    assertz(claim(IdA, Text, ConfA)).

assert_ev(E) :-
    get_dict(id, E, Id),
    get_dict(input_id, E, InId),
    get_dict(supports_claim, E, ClId),
    get_dict(relation, E, Rel),
    get_dict(strength, E, Str),
    get_dict(parser_confidence, E, Conf),
    s(Id, IdA), s(InId, InIdA), s(ClId, ClIdA),
    s(Rel, RelA), s(Str, StrA),
    assertz(evidence(IdA, InIdA, ClIdA, RelA, StrA, Conf)).

assert_cov(C) :-
    get_dict(requirement_id, C, ReqId),
    get_dict(covered, C, Covered),
    get_dict(parser_confidence, C, Conf),
    s(ReqId, ReqIdA),
    ( get_dict(covered_by_claim, C, ClId), string(ClId)
    -> atom_string(ClIdA, ClId)
    ;  ClIdA = null ),
    assertz(requirement_coverage(ReqIdA, Covered, ClIdA, Conf)).

assert_action(G) :-
    get_dict(name, G, Name),
    get_dict(args_signature, G, ArgsSig),
    get_dict(occurrences, G, Occ),
    get_dict(new_info_between, G, NewInfo),
    assertz(action_repeat(Name, ArgsSig, Occ, NewInfo)).
