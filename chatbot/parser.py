"""Turns a free-text message into an intent plus entities.

Entities extracted:
  * amount (with units such as k, million, lakh, crore, or words like "two hundred")
  * source currency and target currencies (codes, symbols, names)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .currencies import (
    CURRENCIES,
    MAJOR_CURRENCIES,
    Mention,
    find_ambiguous_words,
    find_mentions,
    find_unsupported_words,
)

# ---------------------------------------------------------------- amounts
MULTIPLIERS = {
    "k": 1e3, "thousand": 1e3, "hundred": 1e2,
    "m": 1e6, "mn": 1e6, "mm": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
    "crore": 1e7, "crores": 1e7, "cr": 1e7,
}
_MULT_ALT = "|".join(sorted(MULTIPLIERS, key=len, reverse=True))
NUMBER_RE = re.compile(
    rf"(?<![\d.,])(?P<num>\d+(?:,\d+)*(?:\.\d+)?|\.\d+)"
    rf"(?:\s*(?P<mult>{_MULT_ALT})(?![A-Za-z]))?",
    re.I,
)

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_WORD_MULTS = {
    "hundred": 1e2, "thousand": 1e3, "million": 1e6, "billion": 1e9,
    "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7,
}
_NUM_WORDS = "|".join(sorted({**_UNITS, **_TENS}, key=len, reverse=True))
_MULT_WORDS = "|".join(sorted(_WORD_MULTS, key=len, reverse=True))
WORD_MULT_RE = re.compile(
    rf"\b(?:(?P<n>a|an|{_NUM_WORDS})\s+)?(?P<m>{_MULT_WORDS})\b", re.I
)
_TENS_WORDS = "|".join(_TENS)
_UNIT_WORDS = "|".join(w for w in _UNITS if w != "zero")
WORD_PLAIN_RE = re.compile(
    rf"\b(?:(?P<t>{_TENS_WORDS})(?:[\s-]+(?P<u>{_UNIT_WORDS}))?|(?P<w>{'|'.join(_UNITS)}))\b",
    re.I,
)


@dataclass
class Amount:
    value: float
    start: int
    end: int


def _adjacent(text: str, amount: Amount, mention: Mention) -> bool:
    """True if the currency is written right next to the amount."""
    if mention.start >= amount.end:
        return re.fullmatch(r"\s*(?:of\s+)?", text[amount.end:mention.start], re.I) is not None
    if mention.end <= amount.start:
        return text[mention.end:amount.start].strip() == ""
    return False


def find_amount(text: str, mentions: list[Mention]) -> Optional[Amount]:
    candidates: list[Amount] = []

    for m in NUMBER_RE.finditer(text):
        try:
            value = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        if m.group("mult"):
            value *= MULTIPLIERS[m.group("mult").lower()]
        if m.start() > 0 and text[m.start() - 1] == "-" and (
            m.start() == 1 or text[m.start() - 2] in " (=:"
        ):
            value = -value
        candidates.append(Amount(value, m.start(), m.end()))

    if not candidates:
        for m in WORD_MULT_RE.finditer(text):
            n = m.group("n")
            base = 1 if not n or n.lower() in ("a", "an") else {**_UNITS, **_TENS}[n.lower()]
            candidates.append(Amount(base * _WORD_MULTS[m.group("m").lower()], m.start(), m.end()))
        for m in WORD_PLAIN_RE.finditer(text):
            if m.group("w"):
                value = _UNITS[m.group("w").lower()]
            else:
                value = _TENS[m.group("t").lower()] + (_UNITS[m.group("u").lower()] if m.group("u") else 0)
            amount = Amount(float(value), m.start(), m.end())
            if any(_adjacent(text, amount, x) and x.start >= amount.end for x in mentions):
                candidates.append(amount)
        candidates.sort(key=lambda a: a.start)

    if not candidates:
        return None
    for amount in candidates:
        if any(_adjacent(text, amount, m) for m in mentions):
            return amount
    return candidates[0]


# ---------------------------------------------------------------- roles
_FROM_BEFORE = re.compile(r"\bfrom\s*$", re.I)
_TARGET_BEFORE = re.compile(r"(?:\b(?:to|into|in|as)|->|=>|→|=|\bvs\.?|\bversus)\s*$", re.I)
_CONT_BEFORE = re.compile(r"(?:,|&|\band|\bor|\bplus|\balso)\s*$", re.I)
_MAJOR_RE = re.compile(
    r"\b(?:all|every|major|popular|top|main|common)\s+(?:the\s+)?(?:world\s+)?(?:major\s+)?"
    r"currenc(?:y|ies)\b|\beverything\b",
    re.I,
)

# ---------------------------------------------------------------- intents
GREETING_RE = re.compile(
    r"\b(hi|hello|hey|heya|hiya|yo|hola|namaste|greetings|good\s+(?:morning|afternoon|evening)|sup)\b", re.I)
THANKS_RE = re.compile(r"\b(thanks|thank\s*you|thx|ty|cheers|much\s+appreciated)\b", re.I)
BYE_RE = re.compile(r"\b(bye|goodbye|see\s+you|cya|farewell|quit|exit)\b", re.I)
HELP_RE = re.compile(
    r"\b(help|what\s+can\s+you\s+do|how\s+(?:do|does|can|to)\s+(?:i|you|this|it)\b|commands|usage|"
    r"examples?|instructions|guide|what\s+do\s+you\s+do)\b", re.I)
WHO_RE = re.compile(
    r"\b(who\s+are\s+you|what\s+are\s+you|your\s+name|who\s+made\s+you|who\s+built\s+you|"
    r"introduce\s+yourself)\b", re.I)
HOWRU_RE = re.compile(r"\bhow\s+are\s+(?:you|u)\b|\bhow'?s\s+it\s+going\b|\bwhat'?s\s+up\b", re.I)
ROAST_RE = re.compile(
    r"\b(stupid|dumb|idiot|useless|rubbish|trash|worst|hate\s+you|shut\s+up|bad\s+bot|"
    r"arrogant|rude|annoying|ego)\b", re.I)
COMPLIMENT_RE = re.compile(
    r"\b(smart|clever|genius|brilliant|awesome|amazing|good\s+bot|well\s+done|impressive|great)\b", re.I)
LIST_RE = re.compile(
    r"\b(?:list|show|supported|available)\b[^.?!]*\bcurrenc(?:y|ies)\b|"
    r"\b(?:which|what)\s+currenc(?:y|ies)\s+(?:do\s+you|are)\s+(?:support|available|know|handle)|"
    r"\bcurrency\s+list\b|\ball\s+(?:the\s+)?currencies\b|\bsupported\s+currencies\b", re.I)
CONVERT_KW_RE = re.compile(
    r"\b(convert|conversion|exchange|change|swap|worth|rates?|how\s+much|value)\b", re.I)

_STOP_CAPS = {
    "THE", "AND", "FOR", "YOU", "CAN", "HOW", "WHY", "NOW", "GET", "MAY", "SEE", "WHO", "WAS",
    "ARE", "NOT", "BUT", "HAS", "HAD", "ANY", "OUR", "OUT", "YES", "PLS", "PLZ", "OMG", "LOL",
    "HEY", "USA", "UAE", "TELL", "ASK", "GIVE", "MUCH", "WHAT", "THIS", "THAT", "WITH", "HAVE",
    "DOES", "WILL", "FROM", "INTO", "ONE", "TWO", "TEN", "HOW", "ITS", "MEH", "SHOW", "ALL",
}
_CAPS_TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])")


@dataclass
class Parsed:
    text: str
    intent: str = "unknown"
    amount: Optional[float] = None
    source: Optional[str] = None
    source_certain: bool = False
    targets: list[str] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


def _find_unknown_codes(text: str, mentions: list[Mention]) -> list[str]:
    all_caps_message = text == text.upper()
    out: list[str] = []
    for m in _CAPS_TOKEN_RE.finditer(text):
        token = m.group()
        if token in CURRENCIES or token in _STOP_CAPS:
            continue
        if any(x.start <= m.start() < x.end for x in mentions):
            continue
        if all_caps_message and not re.search(r"\b(?:to|into|in|from)\s*$", text[: m.start()], re.I):
            continue
        if token not in out:
            out.append(token)
    return out


def _assign_roles(text: str, mentions: list[Mention], amount: Optional[Amount]):
    roles: list[str] = []
    for i, m in enumerate(mentions):
        before = text[: m.start]
        prev = roles[i - 1] if i else None
        if _FROM_BEFORE.search(before):
            role = "source"
        elif _TARGET_BEFORE.search(before):
            role = "target"
        elif prev == "target" and _CONT_BEFORE.search(before):
            role = "target"
        elif amount is not None and _adjacent(text, amount, m):
            role = "source"
        else:
            role = "unknown"
        roles.append(role)

    source_idx = next((i for i, r in enumerate(roles) if r == "source"), None)
    certain = source_idx is not None
    if source_idx is None:
        source_idx = next((i for i, r in enumerate(roles) if r == "unknown"), None)

    source = mentions[source_idx].code if source_idx is not None else None
    targets: list[str] = []
    for i, (m, r) in enumerate(zip(mentions, roles)):
        if i == source_idx:
            continue
        if r in ("target", "unknown") and m.code not in targets:
            targets.append(m.code)
    return source, certain, targets


def parse(text: str) -> Parsed:
    text = (text or "").strip()
    mentions = find_mentions(text)
    amount = find_amount(text, mentions)
    p = Parsed(text=text, mentions=mentions, amount=amount.value if amount else None)

    p.source, p.source_certain, p.targets = _assign_roles(text, mentions, amount)
    if _MAJOR_RE.search(text) and p.source:
        p.targets += [c for c in MAJOR_CURRENCIES if c != p.source and c not in p.targets]

    p.unknown = find_unsupported_words(text) + _find_unknown_codes(text, mentions)
    p.ambiguous = find_ambiguous_words(text, mentions)

    if mentions or p.unknown or p.ambiguous:
        p.intent = "convert"
    elif LIST_RE.search(text):
        p.intent = "list"
    elif p.amount is not None:
        p.intent = "convert"
    elif HELP_RE.search(text):
        p.intent = "help"
    elif WHO_RE.search(text):
        p.intent = "who"
    elif HOWRU_RE.search(text):
        p.intent = "howru"
    elif ROAST_RE.search(text):
        p.intent = "roast"
    elif THANKS_RE.search(text):
        p.intent = "thanks"
    elif BYE_RE.search(text):
        p.intent = "bye"
    elif COMPLIMENT_RE.search(text):
        p.intent = "compliment"
    elif GREETING_RE.search(text):
        p.intent = "greeting"
    elif CONVERT_KW_RE.search(text):
        p.intent = "convert"
    else:
        p.intent = "unknown"
    return p
