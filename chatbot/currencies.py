"""Currency catalogue and free-text currency detection.

Recognises currencies written as ISO codes (USD), symbols ($, €, ₹),
full names (Indian Rupee) and everyday words (dollars, bucks, quid, yen).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_RAW = """
AED|UAE Dirham
AFN|Afghan Afghani
ALL|Albanian Lek
AMD|Armenian Dram
ANG|Netherlands Antillean Guilder
AOA|Angolan Kwanza
ARS|Argentine Peso
AUD|Australian Dollar
AWG|Aruban Florin
AZN|Azerbaijani Manat
BAM|Bosnia-Herzegovina Convertible Mark
BBD|Barbadian Dollar
BDT|Bangladeshi Taka
BGN|Bulgarian Lev
BHD|Bahraini Dinar
BIF|Burundian Franc
BMD|Bermudian Dollar
BND|Brunei Dollar
BOB|Bolivian Boliviano
BRL|Brazilian Real
BSD|Bahamian Dollar
BTN|Bhutanese Ngultrum
BWP|Botswana Pula
BYN|Belarusian Ruble
BZD|Belize Dollar
CAD|Canadian Dollar
CDF|Congolese Franc
CHF|Swiss Franc
CLP|Chilean Peso
CNY|Chinese Yuan
COP|Colombian Peso
CRC|Costa Rican Colon
CUP|Cuban Peso
CVE|Cape Verdean Escudo
CZK|Czech Koruna
DJF|Djiboutian Franc
DKK|Danish Krone
DOP|Dominican Peso
DZD|Algerian Dinar
EGP|Egyptian Pound
ERN|Eritrean Nakfa
ETB|Ethiopian Birr
EUR|Euro
FJD|Fijian Dollar
FKP|Falkland Islands Pound
GBP|British Pound Sterling
GEL|Georgian Lari
GHS|Ghanaian Cedi
GIP|Gibraltar Pound
GMD|Gambian Dalasi
GNF|Guinean Franc
GTQ|Guatemalan Quetzal
GYD|Guyanese Dollar
HKD|Hong Kong Dollar
HNL|Honduran Lempira
HRK|Croatian Kuna
HTG|Haitian Gourde
HUF|Hungarian Forint
IDR|Indonesian Rupiah
ILS|Israeli New Shekel
INR|Indian Rupee
IQD|Iraqi Dinar
IRR|Iranian Rial
ISK|Icelandic Krona
JMD|Jamaican Dollar
JOD|Jordanian Dinar
JPY|Japanese Yen
KES|Kenyan Shilling
KGS|Kyrgyzstani Som
KHR|Cambodian Riel
KMF|Comorian Franc
KRW|South Korean Won
KWD|Kuwaiti Dinar
KYD|Cayman Islands Dollar
KZT|Kazakhstani Tenge
LAK|Lao Kip
LBP|Lebanese Pound
LKR|Sri Lankan Rupee
LRD|Liberian Dollar
LSL|Lesotho Loti
LYD|Libyan Dinar
MAD|Moroccan Dirham
MDL|Moldovan Leu
MGA|Malagasy Ariary
MKD|Macedonian Denar
MMK|Myanmar Kyat
MNT|Mongolian Tugrik
MOP|Macanese Pataca
MRU|Mauritanian Ouguiya
MUR|Mauritian Rupee
MVR|Maldivian Rufiyaa
MWK|Malawian Kwacha
MXN|Mexican Peso
MYR|Malaysian Ringgit
MZN|Mozambican Metical
NAD|Namibian Dollar
NGN|Nigerian Naira
NIO|Nicaraguan Cordoba
NOK|Norwegian Krone
NPR|Nepalese Rupee
NZD|New Zealand Dollar
OMR|Omani Rial
PAB|Panamanian Balboa
PEN|Peruvian Sol
PGK|Papua New Guinean Kina
PHP|Philippine Peso
PKR|Pakistani Rupee
PLN|Polish Zloty
PYG|Paraguayan Guarani
QAR|Qatari Riyal
RON|Romanian Leu
RSD|Serbian Dinar
RUB|Russian Ruble
RWF|Rwandan Franc
SAR|Saudi Riyal
SBD|Solomon Islands Dollar
SCR|Seychellois Rupee
SDG|Sudanese Pound
SEK|Swedish Krona
SGD|Singapore Dollar
SHP|Saint Helena Pound
SLE|Sierra Leonean Leone
SOS|Somali Shilling
SRD|Surinamese Dollar
SSP|South Sudanese Pound
STN|Sao Tome and Principe Dobra
SYP|Syrian Pound
SZL|Eswatini Lilangeni
THB|Thai Baht
TJS|Tajikistani Somoni
TMT|Turkmenistani Manat
TND|Tunisian Dinar
TOP|Tongan Paanga
TRY|Turkish Lira
TTD|Trinidad and Tobago Dollar
TWD|New Taiwan Dollar
TZS|Tanzanian Shilling
UAH|Ukrainian Hryvnia
UGX|Ugandan Shilling
USD|United States Dollar
UYU|Uruguayan Peso
UZS|Uzbekistani Som
VES|Venezuelan Bolivar
VND|Vietnamese Dong
VUV|Vanuatu Vatu
WST|Samoan Tala
XAF|Central African CFA Franc
XCD|East Caribbean Dollar
XCG|Caribbean Guilder
XOF|West African CFA Franc
XPF|CFP Franc
YER|Yemeni Rial
ZAR|South African Rand
ZMW|Zambian Kwacha
ZWL|Zimbabwean Dollar
"""

CURRENCIES: dict[str, str] = {}
for _line in _RAW.strip().splitlines():
    _code, _name = _line.split("|")
    CURRENCIES[_code.strip()] = _name.strip()

# Shown first when listing currencies / converting into "major currencies".
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "INR", "AUD", "CAD", "CHF", "CNY", "AED"]

# Codes that are also ordinary English words / names. They only count as a
# currency when typed in capitals ("TRY"), never as "try" or "all".
RISKY_CODES = {
    "ALL", "ANG", "BAM", "BOB", "COP", "CUP", "DOP", "GEL", "LAK",
    "MAD", "MOP", "PEN", "RON", "RUB", "SOS", "TOP", "TRY",
}

# Everyday words with a sensible default when several currencies share a name.
DEFAULT_ALIASES = {
    "dollar": "USD", "us dollar": "USD", "u.s. dollar": "USD", "american dollar": "USD",
    "buck": "USD", "bucks": "USD", "greenback": "USD",
    "pound": "GBP", "pound sterling": "GBP", "british pound": "GBP", "sterling": "GBP",
    "quid": "GBP", "uk pound": "GBP", "english pound": "GBP",
    "peso": "MXN", "franc": "CHF", "rupee": "INR", "riyal": "SAR", "riyals": "SAR",
    "krona": "SEK", "kronor": "SEK", "krone": "NOK", "kroner": "NOK",
    "ruble": "RUB", "rouble": "RUB", "leu": "RON", "lei": "RON", "dirham": "AED",
    "renminbi": "CNY", "rmb": "CNY", "chinese renminbi": "CNY",
    "korean won": "KRW", "israeli shekel": "ILS", "nis": "ILS",
    "taiwan dollar": "TWD", "taiwanese dollar": "TWD",
    "aussie dollar": "AUD", "aussie": "AUD", "kiwi dollar": "NZD", "nz dollar": "NZD",
    "loonie": "CAD", "reais": "BRL", "lire": "TRY", "nepali rupee": "NPR",
    "emirati dirham": "AED", "singapore dollars": "SGD",
}

# Only valid when they directly follow a number ("5000 won"), to avoid "who won?".
NEEDS_NUMBER = {"won": "KRW", "real": "BRL", "sol": "PEN", "soles": "PEN"}

# Last-word shortcuts that are too likely to be ordinary words.
_NEVER_SHORT = {"mark", "colon", "sterling", "leone", "balboa"}

# Words that name several currencies with no obvious default -> ask the user.
AMBIGUOUS_WORDS = {
    "dinar": ["KWD", "BHD", "JOD", "IQD", "DZD", "TND", "LYD", "RSD"],
    "rial": ["OMR", "IRR", "YER"],
    "shilling": ["KES", "UGX", "TZS", "SOS"],
    "som": ["KGS", "UZS"],
    "manat": ["AZN", "TMT"],
    "kwacha": ["MWK", "ZMW"],
    "guilder": ["ANG", "XCG"],
}

SYMBOLS = {
    "US$": "USD", "NZ$": "NZD", "HK$": "HKD", "R$": "BRL", "A$": "AUD", "C$": "CAD",
    "S$": "SGD", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR",
    "₩": "KRW", "₽": "RUB", "₺": "TRY", "₪": "ILS", "₫": "VND", "฿": "THB",
    "₦": "NGN", "₱": "PHP", "zł": "PLN", "Rs": "INR",
}

# Names of things people ask for that we cannot convert.
UNSUPPORTED_WORDS = {
    "bitcoin": "Bitcoin", "btc": "Bitcoin", "ethereum": "Ethereum", "eth": "Ethereum",
    "dogecoin": "Dogecoin", "doge": "Dogecoin", "usdt": "Tether", "xrp": "XRP",
    "crypto": "cryptocurrency", "cryptocurrency": "cryptocurrency",
}


def _build_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    last_word_owners: dict[str, set[str]] = {}
    for code, name in CURRENCIES.items():
        full = name.lower()
        aliases[full] = code
        last_word_owners.setdefault(full.split()[-1], set()).add(code)
    for word, owners in last_word_owners.items():
        if (
            len(owners) == 1
            and len(word) >= 3
            and word not in _NEVER_SHORT
            and word not in NEEDS_NUMBER
        ):
            aliases[word] = next(iter(owners))
    aliases.update(DEFAULT_ALIASES)
    return aliases


ALIASES = _build_aliases()


def _phrase(alias: str) -> str:
    return r"\s+".join(re.escape(tok) for tok in alias.split())


_ALIAS_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(_phrase(a) for a in sorted(ALIASES, key=len, reverse=True))
    + r")(?:e?s)?(?![A-Za-z])",
    re.I,
)
_NEEDS_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(sorted(NEEDS_NUMBER, key=len, reverse=True)) + r")(?![A-Za-z])",
    re.I,
)
_AFTER_NUMBER_RE = re.compile(r"\d\s*(?:k|m|mn|bn|b|lakhs?|crores?|million|thousand)?\s*$", re.I)
_CODE_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]{3}(?![A-Za-z])")
_SYMBOL_RE = re.compile(
    r"(?:(?<![A-Za-z])(?:US\$|NZ\$|HK\$|R\$|A\$|C\$|S\$)|\$|€|£|¥|₹|₩|₽|₺|₪|₫|฿|₦|₱|zł"
    r"|(?<![A-Za-z])Rs\.?(?![A-Za-z]))"
)
_AMBIGUOUS_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(AMBIGUOUS_WORDS) + r")s?(?![A-Za-z])", re.I
)
_UNSUPPORTED_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(UNSUPPORTED_WORDS) + r")(?![A-Za-z])", re.I
)


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    code: str
    kind: str  # "code" | "name" | "symbol"


def _lookup_alias(text: str) -> str | None:
    key = re.sub(r"\s+", " ", text.lower())
    if key in ALIASES:
        return ALIASES[key]
    for suffix in ("s", "es"):
        if key.endswith(suffix) and key[: -len(suffix)] in ALIASES:
            return ALIASES[key[: -len(suffix)]]
    return None


def find_mentions(text: str) -> list[Mention]:
    """Return non-overlapping currency mentions in reading order."""
    found: list[Mention] = []

    for m in _CODE_RE.finditer(text):
        token = m.group()
        code = token.upper()
        if code in CURRENCIES and (code not in RISKY_CODES or token.isupper()):
            found.append(Mention(m.start(), m.end(), code, "code"))

    for m in _ALIAS_RE.finditer(text):
        code = _lookup_alias(m.group())
        if code:
            found.append(Mention(m.start(), m.end(), code, "name"))

    for m in _NEEDS_NUMBER_RE.finditer(text):
        if _AFTER_NUMBER_RE.search(text[: m.start()]):
            found.append(Mention(m.start(), m.end(), NEEDS_NUMBER[m.group().lower()], "name"))

    for m in _SYMBOL_RE.finditer(text):
        key = m.group().rstrip(".")
        found.append(Mention(m.start(), m.end(), SYMBOLS[key], "symbol"))

    found.sort(key=lambda x: (x.start, -(x.end - x.start)))
    picked: list[Mention] = []
    last_end = -1
    for mention in found:
        if mention.start >= last_end:
            picked.append(mention)
            last_end = mention.end
    return picked


def find_ambiguous_words(text: str, mentions: list[Mention]) -> list[str]:
    words = []
    for m in _AMBIGUOUS_RE.finditer(text):
        if any(x.start <= m.start() < x.end for x in mentions):
            continue
        word = m.group(1).lower()
        if word not in words:
            words.append(word)
    return words


def find_unsupported_words(text: str) -> list[str]:
    seen: list[str] = []
    for m in _UNSUPPORTED_RE.finditer(text):
        label = UNSUPPORTED_WORDS[m.group(1).lower()]
        if label not in seen:
            seen.append(label)
    return seen


def currency_name(code: str) -> str:
    return CURRENCIES.get(code, code)
