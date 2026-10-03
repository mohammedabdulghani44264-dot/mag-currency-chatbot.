"""Dialogue logic. Stateless on the server: the client echoes `context` back."""
from __future__ import annotations

import math
from typing import Any, Optional

from .currencies import AMBIGUOUS_WORDS, CURRENCIES, MAJOR_CURRENCIES, currency_name
from .formatting import format_amount, format_money, format_rate
from .parser import Parsed, parse
from .personality import Persona
from .rates import RateService

MAX_MESSAGE_LENGTH = 500
MAX_TARGETS = 12
MAX_AMOUNT = 1e15

EMPTY_CONTEXT: dict[str, Any] = {
    "awaiting": None, "amount": None, "source": None, "targets": [], "last": None,
}


def sanitize_context(raw: Any) -> dict[str, Any]:
    """Never trust client-supplied state."""
    ctx = {**EMPTY_CONTEXT, "targets": []}
    if not isinstance(raw, dict):
        return ctx

    def num(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None

    def code(v):
        return v if isinstance(v, str) and v in CURRENCIES else None

    def codes(v):
        return [c for c in v if code(c)][:MAX_TARGETS] if isinstance(v, list) else []

    if raw.get("awaiting") in ("source", "target"):
        ctx["awaiting"] = raw["awaiting"]
    ctx["amount"] = num(raw.get("amount"))
    ctx["source"] = code(raw.get("source"))
    ctx["targets"] = codes(raw.get("targets"))
    last = raw.get("last")
    if isinstance(last, dict) and num(last.get("amount")) is not None and code(last.get("source")):
        targets = codes(last.get("targets"))
        if targets:
            ctx["last"] = {"amount": num(last["amount"]), "source": last["source"], "targets": targets}
    return ctx


class ChatEngine:
    def __init__(self, rates: RateService, persona: Optional[Persona] = None):
        self.rates = rates
        self.persona = persona or Persona()

    # ------------------------------------------------------------ public
    def respond(self, message: str, context: Any = None) -> dict[str, Any]:
        ctx = sanitize_context(context)
        message = (message or "").strip()
        if not message:
            return self._reply("empty", self.persona.say("empty"), ctx)
        if len(message) > MAX_MESSAGE_LENGTH:
            return self._reply("too_long", self.persona.say("too_long"), ctx)

        parsed = parse(message)
        say = self.persona.say

        if parsed.intent == "convert":
            return self._convert(parsed, ctx)
        if parsed.intent == "list":
            return self._list(ctx)
        simple = {
            "greeting": "greeting", "help": "help", "who": "who", "howru": "howru",
            "thanks": "thanks", "bye": "bye", "roast": "roast", "compliment": "compliment",
        }
        if parsed.intent in simple:
            key = simple[parsed.intent]
            return self._reply(parsed.intent, say(key), ctx)
        return self._reply("unknown", say("unknown"), ctx)

    # ----------------------------------------------------------- helpers
    def _reply(self, intent: str, text: str, ctx: dict, data: Optional[dict] = None,
               new_ctx: Optional[dict] = None) -> dict[str, Any]:
        return {"reply": text, "intent": intent, "data": data, "context": new_ctx or ctx}

    def _ask(self, intent: str, text: str, ctx: dict, awaiting: Optional[str],
             amount, source, targets) -> dict[str, Any]:
        new_ctx = {
            "awaiting": awaiting, "amount": amount, "source": source,
            "targets": list(targets), "last": ctx.get("last"),
        }
        return self._reply(intent, text, ctx, new_ctx=new_ctx)

    def _list(self, ctx: dict) -> dict[str, Any]:
        text = self.persona.say(
            "list", count=len(CURRENCIES), major=", ".join(MAJOR_CURRENCIES))
        items = [{"code": c, "name": n} for c, n in sorted(CURRENCIES.items())]
        return self._reply("list", text, ctx, data={"type": "currencies", "items": items})

    # ------------------------------------------------------- conversion
    def _fill_from_context(self, p: Parsed, ctx: dict):
        """Combine this message with what we were waiting for / last converted."""
        amount, source, targets = p.amount, p.source, list(p.targets)
        awaiting, last = ctx["awaiting"], ctx["last"]

        if awaiting == "target":
            if source and not targets and not p.source_certain:
                source, targets = ctx["source"], [source]
            elif targets and not source:
                source = ctx["source"]
            if amount is None:
                amount = ctx["amount"]
        elif awaiting == "source":
            if source and not targets:
                targets = ctx["targets"]
            if amount is None:
                amount = ctx["amount"]
        elif last:
            if source and not targets and amount is None and not p.source_certain:
                source, targets, amount = last["source"], [source], last["amount"]
            elif targets and not source and amount is None:
                source, amount = last["source"], last["amount"]
            elif amount is not None and not source and not targets:
                source, targets = last["source"], list(last["targets"])
        return amount, source, targets

    def _convert(self, p: Parsed, ctx: dict) -> dict[str, Any]:
        say = self.persona.say
        amount, source, targets = self._fill_from_context(p, ctx)
        shown = format_amount(amount) if amount is not None else ""

        if p.unknown:
            unsupported = [u for u in p.unknown if u[0].isupper() and u not in CURRENCIES and len(u) != 3]
            key = "unsupported" if unsupported else "unknown_currency"
            return self._reply("error", say(key, token=p.unknown[0]), ctx)

        if p.ambiguous and (not source or not targets):
            word = p.ambiguous[0]
            options = ", ".join(AMBIGUOUS_WORDS[word])
            return self._reply("clarify", say("ask_ambiguous", word=word, options=options), ctx)

        if not source and not targets:
            if amount is not None:
                return self._ask("clarify", say("ask_source_amount", amount=shown), ctx,
                                 "source", amount, None, [])
            return self._reply("clarify", say("ask_general"), ctx)
        if not source:
            return self._ask("clarify", say("ask_source", amount=shown or "That",
                             targets=", ".join(targets)), ctx, "source", amount, None, targets)
        if not targets:
            return self._ask("clarify", say("ask_target", amount=shown or "One", source=source),
                             ctx, "target", amount, source, [])

        assumed_one = amount is None
        if assumed_one:
            amount = 1.0
        if abs(amount) > MAX_AMOUNT:
            return self._reply("error", say("too_big"), ctx)

        targets = targets[:MAX_TARGETS]
        same = source in targets
        targets = [t for t in targets if t != source]
        if not targets:
            return self._reply("convert", say("same_currency", code=source, amount=format_amount(amount)), ctx)

        snapshot = self.rates.get_snapshot()
        missing = [c for c in [source, *targets] if c not in snapshot.rates]
        if missing:
            return self._reply("error", say("unavailable", codes=", ".join(missing)), ctx)

        results = []
        for t in targets:
            value = RateService.convert(amount, source, t, snapshot)
            rate = RateService.rate(source, t, snapshot)
            results.append({
                "code": t, "name": currency_name(t),
                "value": value, "value_fmt": format_money(value, t),
                "rate": rate, "rate_fmt": f"1 {source} = {format_rate(rate)} {t}",
            })

        summary = "\n".join(
            f"{format_amount(amount)} {source} = {r['value_fmt']} {r['code']}" for r in results)
        data = {
            "type": "conversion",
            "amount": amount, "amount_fmt": format_amount(amount),
            "source": {"code": source, "name": currency_name(source)},
            "results": results,
            "summary": summary,
            "as_of": snapshot.fetched_at.isoformat(),
            "provider": snapshot.provider,
            "status": snapshot.status,
        }

        parts = [say("convert_one" if len(results) == 1 else "convert_many")]
        if amount == 0:
            parts = [say("zero")]
        elif amount < 0:
            parts.append(say("negative_note"))
        if assumed_one:
            parts.append(say("assumed_one"))
        if same:
            parts.append(say("same_currency_note", code=source))
        if snapshot.status == "stale":
            parts.append(say("stale"))
        elif snapshot.status == "offline":
            parts.append(say("offline"))

        new_ctx = {**EMPTY_CONTEXT, "targets": [],
                   "last": {"amount": amount, "source": source, "targets": targets}}
        return self._reply("convert", " ".join(parts), ctx, data=data, new_ctx=new_ctx)
