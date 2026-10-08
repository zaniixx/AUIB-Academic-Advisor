"""Prerequisite and corequisite rules (requirements F0.2 and F0.3).

AUIB records requisites only as free text inside course descriptions
("Prerequisite: CSC 230 and MAT 111"). This module turns that text into a rule
tree and back. The same tree has three forms:

* JSON, stored in the database (``to_json`` / ``from_json``);
* a small rule language admins use to correct rules, e.g.
  ``CSC 230 AND (MAT 111 OR MAT 102)`` (``parse_rule`` / ``format_rule``);
* plain English for students (``describe``).

Conditions the app cannot check from a course history (instructor consent,
placement tests, unclear text) are *advisory*: they never block a plan, but
they are always shown so the student can check them with an advisor.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.codes import normalize_code

# ---------------------------------------------------------------------------
# Rule tree
# ---------------------------------------------------------------------------


class RuleKind(StrEnum):
    PRE = "pre"  # must be completed in an earlier term
    CO = "co"  # must be taken in the same term or earlier
    PRE_OR_CO = "pre_or_co"  # same as CO for planning; SIS words it "Prerequisite / Corequisite"


class ParseStatus(StrEnum):
    PARSED = "parsed"  # every part of the text became a rule
    PARTIAL = "partial"  # some text could not be understood and is kept as a note
    UNPARSED = "unparsed"  # nothing could be understood; the whole text is a note
    NONE = "none"  # the description says there is no requisite


class Standing(StrEnum):
    FRESHMAN = "freshman"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    SENIOR = "senior"


class Advisory(StrEnum):
    CONSENT = "consent"  # approval of an instructor, advisor or department
    PLACEMENT = "placement"  # placement test or English (ASP) level
    RECOMMENDED = "recommended"  # suggested but not required
    NOTE = "note"  # text the parser could not understand


@dataclass(frozen=True)
class CourseReq:
    code: str


@dataclass(frozen=True)
class AllOf:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class AnyOf:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class StandingReq:
    standing: Standing


@dataclass(frozen=True)
class CreditsReq:
    minimum: int


@dataclass(frozen=True)
class LevelReq:
    """Every course of the student's major at this level, e.g. "All major program 300-level classes"."""

    level: int


@dataclass(frozen=True)
class AdvisoryReq:
    category: Advisory
    text: str


Expr = CourseReq | AllOf | AnyOf | StandingReq | CreditsReq | LevelReq | AdvisoryReq

DEFAULT_STANDING_CREDITS: Mapping[Standing, int] = {
    Standing.FRESHMAN: 0,
    Standing.SOPHOMORE: 30,
    Standing.JUNIOR: 60,
    Standing.SENIOR: 90,
}


def all_of(items: Iterable[Expr]) -> Expr | None:
    """AND the items together, flattening nested ANDs and dropping duplicates."""
    flat: list[Expr] = []
    for item in items:
        for part in item.items if isinstance(item, AllOf) else (item,):
            if part not in flat:
                flat.append(part)
    if not flat:
        return None
    return flat[0] if len(flat) == 1 else AllOf(tuple(flat))


def any_of(items: Iterable[Expr]) -> Expr | None:
    flat: list[Expr] = []
    for item in items:
        for part in item.items if isinstance(item, AnyOf) else (item,):
            if part not in flat:
                flat.append(part)
    if not flat:
        return None
    return flat[0] if len(flat) == 1 else AnyOf(tuple(flat))


# ---------------------------------------------------------------------------
# JSON form
# ---------------------------------------------------------------------------


def to_json(expr: Expr | None) -> dict[str, Any] | None:
    if expr is None:
        return None
    match expr:
        case CourseReq(code):
            return {"course": code}
        case AllOf(items):
            return {"all": [to_json(item) for item in items]}
        case AnyOf(items):
            return {"any": [to_json(item) for item in items]}
        case StandingReq(standing):
            return {"standing": standing.value}
        case CreditsReq(minimum):
            return {"credits": minimum}
        case LevelReq(level):
            return {"level": level}
        case AdvisoryReq(category, text):
            return {"advisory": category.value, "text": text}
    raise TypeError(f"Not a rule expression: {expr!r}")


def from_json(data: Mapping[str, Any] | None) -> Expr | None:
    if data is None:
        return None
    if "course" in data:
        return CourseReq(str(data["course"]))
    if "all" in data:
        return AllOf(tuple(_required(from_json(item)) for item in data["all"]))
    if "any" in data:
        return AnyOf(tuple(_required(from_json(item)) for item in data["any"]))
    if "standing" in data:
        return StandingReq(Standing(data["standing"]))
    if "credits" in data:
        return CreditsReq(int(data["credits"]))
    if "level" in data:
        return LevelReq(int(data["level"]))
    if "advisory" in data:
        return AdvisoryReq(Advisory(data["advisory"]), str(data["text"]))
    raise ValueError(f"Unknown rule node: {dict(data)!r}")


def _required(expr: Expr | None) -> Expr:
    if expr is None:
        raise ValueError("Empty rule inside AND/OR")
    return expr


# ---------------------------------------------------------------------------
# Walking the tree
# ---------------------------------------------------------------------------


def course_codes(expr: Expr | None, *, include_alternatives: bool = True) -> set[str]:
    """Course codes a rule refers to (advisory text such as "recommended" is ignored)."""
    if expr is None:
        return set()
    match expr:
        case CourseReq(code):
            return {code}
        case AllOf(items):
            return set().union(*(course_codes(i, include_alternatives=include_alternatives) for i in items))
        case AnyOf(items):
            if not include_alternatives:
                return set()
            return set().union(*(course_codes(i) for i in items))
    return set()


@dataclass(frozen=True)
class EvalContext:
    """What is known about the student at the start of a term."""

    completed: frozenset[str]
    credits: float
    concurrent: frozenset[str] = frozenset()  # courses in the same term (CO / PRE_OR_CO rules only)
    level_courses: Mapping[int, frozenset[str]] = field(default_factory=dict)
    standing_credits: Mapping[Standing, int] = field(default_factory=lambda: DEFAULT_STANDING_CREDITS)


@dataclass(frozen=True)
class Evaluation:
    satisfied: bool
    advisories: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def evaluate(expr: Expr | None, ctx: EvalContext) -> Evaluation:
    if expr is None:
        return Evaluation(True)
    match expr:
        case CourseReq(code):
            ok = code in ctx.completed or code in ctx.concurrent
            return Evaluation(ok, missing=() if ok else (code,))
        case AllOf(items):
            results = [evaluate(item, ctx) for item in items]
            return Evaluation(
                all(r.satisfied for r in results),
                tuple(a for r in results for a in r.advisories),
                tuple(m for r in results for m in r.missing),
            )
        case AnyOf(items):
            results = [evaluate(item, ctx) for item in items]
            clean = [r for r in results if r.satisfied and not r.advisories]
            if clean:
                return clean[0]
            passed = [r for r in results if r.satisfied]
            if passed:
                return passed[0]
            return Evaluation(False, missing=("one of: " + " / ".join(describe(i) for i in items),))
        case StandingReq(standing):
            needed = ctx.standing_credits.get(standing, 0)
            ok = ctx.credits >= needed
            return Evaluation(ok, missing=() if ok else (f"{standing.value} standing ({needed}+ credits)",))
        case CreditsReq(minimum):
            ok = ctx.credits >= minimum
            return Evaluation(ok, missing=() if ok else (f"{minimum}+ credits completed",))
        case LevelReq(level):
            outstanding = sorted(ctx.level_courses.get(level, frozenset()) - ctx.completed - ctx.concurrent)
            return Evaluation(not outstanding, missing=tuple(outstanding))
        case AdvisoryReq():
            return Evaluation(True, advisories=(describe(expr),))
    raise TypeError(f"Not a rule expression: {expr!r}")


def courses_to_add(
    expr: Expr | None,
    have: frozenset[str],
    level_courses: Mapping[int, frozenset[str]],
    cost: Callable[[str], float],
) -> frozenset[str]:
    """Smallest set of extra courses that makes the course parts of ``expr`` satisfiable.

    Time-based parts (standing, credits) need no extra courses; advisory parts are
    assumed satisfiable. For OR rules the cheapest alternative wins, where ``cost``
    lets the planner prefer courses that also count toward a requirement.
    """
    if expr is None:
        return frozenset()
    match expr:
        case CourseReq(code):
            return frozenset() if code in have else frozenset({code})
        case AllOf(items):
            return frozenset().union(*(courses_to_add(i, have, level_courses, cost) for i in items))
        case AnyOf(items):
            options = [courses_to_add(i, have, level_courses, cost) for i in items]
            return min(options, key=lambda option: (sum(cost(c) for c in option), sorted(option)))
        case LevelReq(level):
            return level_courses.get(level, frozenset()) - have
    return frozenset()


# ---------------------------------------------------------------------------
# Plain English
# ---------------------------------------------------------------------------


def describe(expr: Expr | None, standing_credits: Mapping[Standing, int] = DEFAULT_STANDING_CREDITS) -> str:
    if expr is None:
        return "None"
    match expr:
        case CourseReq(code):
            return code
        case AllOf(items):
            return _join([_describe_nested(i, standing_credits) for i in items], "and")
        case AnyOf(items):
            return _join([_describe_nested(i, standing_credits) for i in items], "or")
        case StandingReq(standing):
            return f"{standing.value.capitalize()} standing ({standing_credits.get(standing, 0)}+ credits)"
        case CreditsReq(minimum):
            return f"{minimum}+ credits completed"
        case LevelReq(level):
            return f"All {level}-level courses in the major"
        case AdvisoryReq(Advisory.CONSENT, text):
            return f"Approval needed: {text}"
        case AdvisoryReq(Advisory.PLACEMENT, text):
            return f"Placement: {text}"
        case AdvisoryReq(Advisory.RECOMMENDED, text):
            return f"Recommended, not required: {text}"
        case AdvisoryReq(_, text):
            return f"Check with your advisor: {text}"
    raise TypeError(f"Not a rule expression: {expr!r}")


def _describe_nested(expr: Expr, standing_credits: Mapping[Standing, int]) -> str:
    text = describe(expr, standing_credits)
    return f"({text})" if isinstance(expr, AllOf | AnyOf) else text


def _join(parts: list[str], word: str) -> str:
    if len(parts) <= 2:
        return f" {word} ".join(parts)
    return ", ".join(parts[:-1]) + f" {word} " + parts[-1]


# ---------------------------------------------------------------------------
# Rule language (admin corrections)
# ---------------------------------------------------------------------------


class RuleSyntaxError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (at character {position + 1})")
        self.position = position


_STRING_FUNCTIONS = {
    "CONSENT": Advisory.CONSENT,
    "PLACEMENT": Advisory.PLACEMENT,
    "RECOMMENDED": Advisory.RECOMMENDED,
    "NOTE": Advisory.NOTE,
}
_RULE_TOKEN_RE = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<course>[A-Za-z]{2,4}\s?-?(?:\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3})(?![A-Za-z0-9]))
  | (?P<number>\d+)
  | (?P<word>[A-Za-z_]+)
  """,
    re.X,
)


def parse_rule(text: str) -> Expr | None:
    """Parse the admin rule language. ``NONE`` (or empty text) means no requisite.

    Grammar: ``expr := term (OR term)*``, ``term := atom (AND atom)*``, where an
    atom is a course code, ``(expr)``, ``STANDING(junior)``, ``CREDITS(90)``,
    ``LEVEL(300)`` or ``CONSENT|PLACEMENT|RECOMMENDED|NOTE("text")``.
    """
    tokens: list[tuple[str, str, int]] = []
    position = 0
    while position < len(text):
        match = _RULE_TOKEN_RE.match(text, position)
        if not match:
            raise RuleSyntaxError(f"Unexpected character {text[position]!r}", position)
        kind = match.lastgroup or ""
        if kind != "space":
            tokens.append((kind, match.group(), position))
        position = match.end()
    if not tokens or (len(tokens) == 1 and tokens[0][1].upper() == "NONE"):
        return None
    parser = _RuleParser(tokens, len(text))
    expr = parser.parse_or()
    if parser.index < len(tokens):
        _kind, value, at = tokens[parser.index]
        raise RuleSyntaxError(f"Unexpected {value!r}", at)
    return expr


class _RuleParser:
    def __init__(self, tokens: list[tuple[str, str, int]], length: int) -> None:
        self.tokens = tokens
        self.index = 0
        self.length = length

    def peek_word(self) -> str | None:
        if self.index < len(self.tokens) and self.tokens[self.index][0] == "word":
            return self.tokens[self.index][1].upper()
        return None

    def expect(self, kind: str) -> tuple[str, str, int]:
        if self.index >= len(self.tokens):
            raise RuleSyntaxError(f"Expected {kind} but the rule ended", self.length)
        token = self.tokens[self.index]
        if token[0] != kind:
            raise RuleSyntaxError(f"Expected {kind} but found {token[1]!r}", token[2])
        self.index += 1
        return token

    def parse_or(self) -> Expr:
        items = [self.parse_and()]
        while self.peek_word() == "OR":
            self.index += 1
            items.append(self.parse_and())
        return items[0] if len(items) == 1 else AnyOf(tuple(items))

    def parse_and(self) -> Expr:
        items = [self.parse_atom()]
        while self.peek_word() == "AND":
            self.index += 1
            items.append(self.parse_atom())
        return items[0] if len(items) == 1 else AllOf(tuple(items))

    def parse_atom(self) -> Expr:
        if self.index >= len(self.tokens):
            raise RuleSyntaxError("Rule ended where a course or condition was expected", self.length)
        kind, value, at = self.tokens[self.index]
        if kind == "course":
            self.index += 1
            code = normalize_code(value)
            if code is None:  # pragma: no cover - the token pattern only matches codes
                raise RuleSyntaxError(f"Not a course code: {value!r}", at)
            return CourseReq(code)
        if kind == "lparen":
            self.index += 1
            expr = self.parse_or()
            self.expect("rparen")
            return expr
        if kind == "word":
            name = value.upper()
            self.index += 1
            if name in ("STANDING", "CREDITS", "LEVEL") or name in _STRING_FUNCTIONS:
                self.expect("lparen")
                argument = self.parse_argument(name, at)
                self.expect("rparen")
                return argument
            raise RuleSyntaxError(f"Unknown word {value!r}", at)
        raise RuleSyntaxError(f"Unexpected {value!r}", at)

    def parse_argument(self, name: str, at: int) -> Expr:
        if name == "STANDING":
            _kind, value, value_at = self.expect("word")
            try:
                return StandingReq(Standing(value.lower()))
            except ValueError:
                raise RuleSyntaxError(
                    "STANDING takes freshman, sophomore, junior or senior", value_at
                ) from None
        if name in ("CREDITS", "LEVEL"):
            _kind, value, _value_at = self.expect("number")
            return CreditsReq(int(value)) if name == "CREDITS" else LevelReq(int(value))
        _kind, value, _value_at = self.expect("string")
        text = value[1:-1].replace('\\"', '"').replace("\\\\", "\\").strip()
        if not text:
            raise RuleSyntaxError(f"{name} needs some text", at)
        return AdvisoryReq(_STRING_FUNCTIONS[name], text)


def format_rule(expr: Expr | None) -> str:
    """Inverse of ``parse_rule``; nested groups are always parenthesised."""
    if expr is None:
        return "NONE"
    match expr:
        case CourseReq(code):
            return code
        case AllOf(items):
            return " AND ".join(_format_nested(item) for item in items)
        case AnyOf(items):
            return " OR ".join(_format_nested(item) for item in items)
        case StandingReq(standing):
            return f"STANDING({standing.value})"
        case CreditsReq(minimum):
            return f"CREDITS({minimum})"
        case LevelReq(level):
            return f"LEVEL({level})"
        case AdvisoryReq(category, text):
            escaped = text.replace("\\", "\\\\").replace('"', '\\"')
            return f'{category.name}("{escaped}")'
    raise TypeError(f"Not a rule expression: {expr!r}")


def _format_nested(expr: Expr) -> str:
    text = format_rule(expr)
    return f"({text})" if isinstance(expr, AllOf | AnyOf) else text


# ---------------------------------------------------------------------------
# Description text -> rule (the heuristic parser behind F0.2)
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(
    r"(?P<prefix>\b(?:UG\s+)?Course\s+)?"
    r"(?P<label>"
    r"(?:\b(?:pre|co)\s*-?\s*/\s*)?"
    r"\b(?:pre|co)?\s*-?\s*requisites?(?:\s*\(s\))?"
    r"(?:\s*(?:/|\bor\b|\band/or\b)\s*(?:pre|co)\s*-?\s*requisites?(?:\s*\(s\))?)?"
    r")"
    r"\s*(?:\(s\))?\s*:?",
    re.I,
)
_NOT_A_LABEL_BEFORE = re.compile(r"\bis\s+an?\s*$", re.I)
_STOP_PHRASES_RE = re.compile(
    r"\b(?:language\s+of\s+instruction|key\s+topics|cross-listed|course\s+description|note\s*:"
    r"|this\s+course\b|students\s+(?:cannot|who|may|must)|equivalent\s+to\b)",
    re.I,
)
_SENTENCE_END_RE = re.compile(r"\.(?=\s+[A-Z(])|\.(?=[A-Z][a-z])|\.\s*$")
_NONE_RE = re.compile(r"^\W*(?:none|n/a|no\s+prerequisites?)\W*$", re.I)

_ROLE = (
    r"(?:the\s+)?(?:instructor|faculty\s+advisor|advisor|head\s+of\s+(?:the\s+)?department"
    r"|department(?:\s+chair)?|dean|chair|program\s+director)"
)
_STANDING_WORD = r"(?:freshman|sophomore|junior|senior)"
_TOKEN_RE = re.compile(
    rf"""
    (?P<consent>(?:consent|approval|permission)\s+of\s+{_ROLE}(?:\s*(?:,|\bor\b|\band\b|/)\s*{_ROLE})*
               |(?:instructor|department|advisor)(?:'s)?\s+(?:consent|approval|permission))
  | (?P<placement>(?:successful\s+completion\s+of\s+|completed\s+or\s+enrolled\s+in\s+)?
                 (?:level\s+\w+\s+ASP|ASP\s+(?:level\s+)?\w+)(?:\s+or\s+(?:its\s+)?equivalent)?
               |(?:mathematics|math|english)\s+(?:assessment|placement)\s+test[^,;.]*
               |placement\s+test[^,;.]*)
  | (?P<level>all\s+(?:major\s+)?(?:program\s+)?(?P<level_digit>\d)00-level\s+(?:classes|courses))
  | (?P<standing>(?P<standing_words>{_STANDING_WORD}(?:\s*(?:\bor\b|/|,)\s*{_STANDING_WORD})*)\s+standing)
  | (?P<credits>(?:completion(?:\s+of)?\s+|complete\s+|completed\s+)?(?:a\s+)?
               (?:minimum\s+of\s+|total\s+of\s+|at\s+least\s+)?(?P<credit_count>\d{{2,3}})\s*\+?\s*
               (?:credit\s*hours?|credits?|units?|hours?)
               (?:\s+(?:of\s+program\s+requirements|successfully\s+completed|completed))?)
  | (?P<course>\b(?!(?:and|or|the|of|for|all|in|to|any)\b)[A-Za-z]{{2,4}}\s?-?\d{{3}}[A-Za-z]?\b)
  | (?P<bare>\b\d{{3}}[A-Za-z]?\b)
  | (?P<recommended>\(\s*recommended\s*\))
  | (?P<or>\band\s*/\s*or\b|\bor\b|/)
  | (?P<and>\band\b|&|,|;)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<word>[^\s,;/&()]+)
    """,
    re.I | re.X,
)
_FILLER_WORDS = {
    "completion", "of", "successful", "successfully", "completed", "complete", "course", "courses",
    "ug", "the", "both", "either", "a", "an", "its", "equivalent", "with", ".", "-", ":",
}  # fmt: skip
_TITLE_SMALL_WORDS = {"and", "of", "the", "to", "in", "for", "&", "-", "a", "on", "with"}


@dataclass(frozen=True)
class Clause:
    kind: RuleKind
    text: str  # the label and the rule text, as it appears in the description


@dataclass(frozen=True)
class ParsedRule:
    kind: RuleKind
    source_text: str
    expr: Expr | None
    status: ParseStatus
    unparsed_text: str = ""


def extract_clauses(description: str) -> list[Clause]:
    """Find the requisite sentences in a course description."""
    text = re.sub(r"\s+", " ", description or "")
    matches = [
        m
        for m in _LABEL_RE.finditer(text)
        if not _NOT_A_LABEL_BEFORE.search(text[: m.start()])
        and not re.match(r"\s*for\b", text[m.end() :], re.I)
    ]
    clauses: list[Clause] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        if stop := _STOP_PHRASES_RE.search(body):
            body = body[: stop.start()]
        if sentence_end := _SENTENCE_END_RE.search(body):
            body = body[: sentence_end.start()]
        body = body.strip(" .;,")
        label_start = match.start("label")
        clauses.append(
            Clause(_label_kind(match.group("label")), f"{text[label_start : match.end()]} {body}".strip())
        )
    return clauses


def _label_kind(label: str) -> RuleKind:
    lower = label.lower()
    has_pre = "pre" in lower
    has_co = re.search(r"(?<![a-z])co(?![a-z])|corequisite", lower) is not None
    if has_pre and has_co:
        return RuleKind.PRE_OR_CO
    return RuleKind.CO if has_co else RuleKind.PRE


def parse_description(description: str, known_subjects: frozenset[str]) -> list[ParsedRule]:
    """Parse every requisite clause of a description, merged into one rule per kind."""
    by_kind: dict[RuleKind, list[tuple[Clause, Expr | None, ParseStatus, str]]] = {}
    for clause in extract_clauses(description):
        body = clause.text.split(":", 1)[1] if ":" in clause.text else _strip_label(clause.text)
        expr, status, unparsed = parse_requisite_text(body, known_subjects)
        by_kind.setdefault(clause.kind, []).append((clause, expr, status, unparsed))

    order = [ParseStatus.NONE, ParseStatus.PARSED, ParseStatus.PARTIAL, ParseStatus.UNPARSED]
    rules = []
    for kind, parts in by_kind.items():
        exprs = [expr for _c, expr, _s, _u in parts if expr is not None]
        rules.append(
            ParsedRule(
                kind=kind,
                source_text=" ".join(clause.text for clause, *_rest in parts),
                expr=all_of(exprs),
                status=max((status for _c, _e, status, _u in parts), key=order.index),
                unparsed_text="; ".join(u for *_rest, u in parts if u),
            )
        )
    return rules


def _strip_label(text: str) -> str:
    match = _LABEL_RE.match(text)
    return text[match.end() :] if match else text


def parse_requisite_text(text: str, known_subjects: frozenset[str]) -> tuple[Expr | None, ParseStatus, str]:
    """Parse the text after a "Prerequisite:" label.

    Returns the rule, how much of the text was understood, and the text that was
    not (which is also kept in the rule as a NOTE so nothing is silently lost).
    """
    clean = re.sub(r"\s+", " ", text).strip(" .;,")
    if not clean or _NONE_RE.match(clean):
        return None, ParseStatus.NONE, ""

    tokens = [(m.lastgroup or "word", m) for m in _TOKEN_RE.finditer(clean)]
    atoms: list[Expr] = []
    joins: list[str] = []  # "and" / "or" between atoms[i] and atoms[i + 1]
    pending_join: str | None = None
    leftovers: list[str] = []
    words: list[str] = []
    last_course_subject: str | None = None
    previous_kind: str | None = None

    def flush_words(next_kind: str | None) -> None:
        nonlocal words
        meaningful = [w for w in words if w.lower() not in _FILLER_WORDS]
        if meaningful and not _is_course_title(meaningful, previous_kind, next_kind):
            leftovers.append(" ".join(words))
        words = []

    def add_atom(expr: Expr) -> None:
        nonlocal pending_join
        if atoms:
            joins.append(pending_join or "and")
        atoms.append(expr)
        pending_join = None

    for index, (kind, match) in enumerate(tokens):
        value = match.group()
        next_kind = tokens[index + 1][0] if index + 1 < len(tokens) else None
        if kind == "course":
            code = normalize_code(value)
            subject = code.split(" ")[0] if code else ""
            if code and (subject in known_subjects or value[:2].isupper()):
                flush_words(_kind_before(tokens, index))
                add_atom(CourseReq(code))
                last_course_subject = subject
                previous_kind = "course"
                continue
            kind = "word"
        if kind == "bare" and last_course_subject and previous_kind in ("course", "join"):
            flush_words(_kind_before(tokens, index))
            add_atom(CourseReq(f"{last_course_subject} {value.upper()}"))
            previous_kind = "course"
            continue
        if kind == "recommended":
            if atoms:
                atoms[-1] = AdvisoryReq(Advisory.RECOMMENDED, describe(atoms[-1]))
            continue
        if kind in ("and", "or"):
            if atoms and not words:
                pending_join = "or" if kind == "or" or pending_join == "or" else "and"
                previous_kind = "join"
            elif kind == "or":
                pending_join = "or"
            continue
        if kind in ("lparen", "rparen"):
            if kind == "rparen" and words:
                flush_words(None)
            continue
        if kind in ("consent", "placement", "level", "standing", "credits"):
            flush_words(kind)
            add_atom(_condition_atom(kind, match))
            previous_kind = kind
            last_course_subject = None
            continue
        if kind in ("word", "bare"):
            words.append(value)
            if next_kind in ("and", "or") and _peek_title_continues(tokens, index):
                continue
            if next_kind not in ("word", "bare", "lparen") and next_kind is not None:
                flush_words(next_kind)
                previous_kind = "word"
            continue
    flush_words(None)

    expr = _combine(atoms, joins)
    leftover = "; ".join(part.strip(" ,;:-") for part in leftovers if part.strip(" ,;:-"))
    if expr is None:
        return AdvisoryReq(Advisory.NOTE, clean), ParseStatus.UNPARSED, clean
    if leftover:
        return all_of([expr, AdvisoryReq(Advisory.NOTE, leftover)]), ParseStatus.PARTIAL, leftover
    return expr, ParseStatus.PARSED, ""


def _kind_before(tokens: list[tuple[str, re.Match[str]]], index: int) -> str:
    """ "lparen" when a code is wrapped in brackets ("Title (CODE)"), so the words before it are its title."""
    return "lparen" if index > 0 and tokens[index - 1][0] == "lparen" else "course"


def _peek_title_continues(tokens: list[tuple[str, re.Match[str]]], index: int) -> bool:
    """True for "Pharmacokinetics and biopharmaceutics (PHA 400)": an AND inside a course title."""
    for kind, _match in tokens[index + 1 :]:
        if kind in ("word", "and", "or"):
            continue
        return kind == "lparen"
    return False


def _is_course_title(words: list[str], previous_kind: str | None, next_kind: str | None) -> bool:
    """Words around a course code that are its title, e.g. "Introduction to Reading, (TLD 204)"."""
    if next_kind == "lparen" or (next_kind == "course" and words and words[-1].endswith(",")):
        return True
    if previous_kind == "course":
        return all(w[:1].isupper() or w.lower() in _TITLE_SMALL_WORDS or w.isdigit() for w in words)
    return False


def _condition_atom(kind: str, match: re.Match[str]) -> Expr:
    text = match.group().strip()
    if kind == "consent":
        return AdvisoryReq(Advisory.CONSENT, text[:1].upper() + text[1:])
    if kind == "placement":
        return AdvisoryReq(Advisory.PLACEMENT, text[:1].upper() + text[1:])
    if kind == "level":
        return LevelReq(int(match.group("level_digit")) * 100)
    if kind == "standing":
        levels = re.findall(_STANDING_WORD, match.group("standing_words"), re.I)
        order = list(Standing)
        return StandingReq(min((Standing(level.lower()) for level in levels), key=order.index))
    return CreditsReq(int(match.group("credit_count")))


def _combine(atoms: list[Expr], joins: list[str]) -> Expr | None:
    """OR binds tighter than AND in catalog prose: "Sophomore standing, and MAT 101 or MAT 102"."""
    if not atoms:
        return None
    groups: list[list[Expr]] = [[atoms[0]]]
    for join, atom in zip(joins, atoms[1:], strict=True):
        if join == "or":
            groups[-1].append(atom)
        else:
            groups.append([atom])
    return all_of(_required(any_of(group)) for group in groups)
