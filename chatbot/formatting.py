"""Number formatting helpers (Indian lakh/crore grouping included)."""
from __future__ import annotations

import math

INDIAN_GROUPING = {"INR", "PKR", "NPR", "BDT"}


def _group_indian(integer_part: str) -> str:
    if len(integer_part) <= 3:
        return integer_part
    head, tail = integer_part[:-3], integer_part[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def _decimals_for(value: float, minimum: int) -> int:
    a = abs(value)
    if a == 0 or a >= 1:
        return minimum
    return min(10, max(minimum, -math.floor(math.log10(a)) + 3))


def format_money(value: float, code: str | None = None, minimum_decimals: int = 2) -> str:
    """12345.6 -> '12,345.60'; INR -> '12,345.60' with lakh grouping when large."""
    decimals = _decimals_for(value, minimum_decimals)
    text = f"{abs(value):.{decimals}f}"
    integer, _, fraction = text.partition(".")
    while len(fraction) > minimum_decimals and fraction.endswith("0"):
        fraction = fraction[:-1]
    integer = _group_indian(integer) if code in INDIAN_GROUPING else f"{int(integer):,}"
    out = f"{integer}.{fraction}" if fraction else integer
    return f"-{out}" if value < 0 else out


def format_amount(value: float) -> str:
    """Echo of what the user typed: 100 -> '100', 2500.5 -> '2,500.5'."""
    if float(value).is_integer():
        return f"{int(value):,}"
    text = f"{value:,.6f}".rstrip("0").rstrip(".")
    return text


def format_rate(rate: float) -> str:
    return format_money(rate, minimum_decimals=4)
