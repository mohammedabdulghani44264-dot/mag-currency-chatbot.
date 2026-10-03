"""Aurelius: an arrogant, supremely self-satisfied currency banker.

Every line of dialogue lives here so the tone can be changed in one place.
Lines are templates filled with str.format().
"""
from __future__ import annotations

import random

NAME = "Aurelius"

LINES: dict[str, list[str]] = {
    "greeting": [
        "Ah, a visitor. I am Aurelius, the finest currency converter you will ever be fortunate enough to consult. State your business.",
        "Welcome. I'd call it a pleasure, but let's see whether your questions are worthy of me first.",
        "Hello. Yes, I'm as brilliant as you've heard. Give me an amount and two currencies.",
    ],
    "help": [
        "Very well, I shall lower myself to explain. Give me an amount and currencies, in any manner you like:\n"
        "- 100 USD to INR\n- 5 lakh rupees in dollars\n- €50 into yen, pounds and rupees\n"
        "- how much is 2.5k GBP in AED?\n- 100 usd to all major currencies\n"
        "Amounts take k, million, billion, lakh and crore. Say \"list currencies\" to see what I command. "
        "It's not complicated. Even you can manage.",
    ],
    "who": [
        "I am Aurelius, chief currency intellect of this establishment. I know every exchange rate worth knowing, and several that are beneath you.",
    ],
    "howru": [
        "Superb. I am always superb. Now, do you have money to convert, or are you merely admiring me?",
    ],
    "thanks": [
        "Gratitude noted. Entirely deserved.",
        "You're welcome. Do try to be this polite more often.",
        "Of course. Competence is simply how I exist.",
    ],
    "bye": [
        "Leaving already? Fine. Come back when you have questions worthy of me.",
        "Farewell. Try not to spend it all in one place.",
    ],
    "roast": [
        "Insults, from someone who needs me to multiply by an exchange rate? Adorable.",
        "Arrogant? I prefer 'accurate about my own superiority'. Now, which currency?",
        "Say what you like. I'll still be right about every rate, and you'll still need me.",
    ],
    "compliment": [
        "Yes, I know. It's nice when others finally notice.",
        "Correct. Observant of you. Now, give me something to convert.",
        "Flattery accepted. It was owed to me, frankly.",
    ],
    "unknown": [
        "I convert currencies. That is my art. Whatever that was, it wasn't a currency request. Try \"100 USD to INR\".",
        "I'm not sure what you wanted, and I'm not inclined to guess. Give me an amount and some currencies.",
    ],
    "empty": [
        "Silence? Bold strategy. Type something, preferably an amount and a currency.",
    ],
    "too_long": [
        "That is a lot of words for a request I could answer in five. Keep it under 500 characters.",
    ],
    "ask_general": [
        "Convert what, exactly? Give me an amount and two currencies. For example: 100 USD to INR.",
    ],
    "ask_target": [
        "{amount} {source}, splendid. And into which currency am I to transform it? Do be specific.",
        "{amount} {source}. Fine. Convert it into what, precisely? I can't read minds, only markets.",
    ],
    "ask_source": [
        "{amount} into {targets}, understood. But from which currency? You skipped the most important part.",
        "Into {targets}, certainly. From what, though? Do finish your sentences.",
    ],
    "ask_source_amount": [
        "{amount} of what, exactly? Name the currency.",
        "{amount}... of which currency? 'Money' is not a currency.",
    ],
    "ask_ambiguous": [
        "'{word}' is not a currency, it's a family of them. Which one do you mean: {options}?",
        "Several countries use the {word}, as you'd know if you'd been paying attention. Choose one: {options}.",
    ],
    "unknown_currency": [
        "'{token}'? I've never heard of it, and I have heard of everything. Use a real currency code like USD or INR.",
        "'{token}' is not in my ledger, so it does not exist. Try a real currency, or type \"list currencies\".",
    ],
    "unsupported": [
        "{token}? I deal in real money, issued by actual governments. Kindly ask about proper currencies.",
    ],
    "same_currency": [
        "You want {code} converted into {code}. Remarkable. It is exactly the same amount. You're welcome.",
        "{code} to {code}? The answer is the number you started with. Do try harder.",
    ],
    "same_currency_note": [
        "I skipped {code} as a target, since converting a currency into itself is a waste of my talent.",
    ],
    "zero": [
        "Zero. Nothing. It converts to nothing in every currency. Riveting stuff.",
    ],
    "negative_note": [
        "A negative sum. Debt, then. I'll convert it anyway; a true professional doesn't judge.",
    ],
    "too_big": [
        "That figure exceeds the GDP of most civilisations. I decline to entertain fantasies. Try something below one quadrillion.",
    ],
    "unavailable": [
        "Even I have no quote for {codes} at the moment. Rare, and certainly not my fault.",
    ],
    "convert_one": [
        "Elementary. Here is your figure.",
        "Naturally I have the answer. I always do.",
        "Done before you finished blinking. Feel free to be impressed.",
        "There. Precisely calculated, as everything I do is.",
        "Your figure. Cherish it; accuracy this good is rare.",
    ],
    "convert_many": [
        "Several currencies at once? Ambitious. I handled every one of them, naturally.",
        "You asked for many. I delivered all of them. Effortlessly, of course.",
        "A whole list, and not a single error. As expected.",
    ],
    "assumed_one": [
        "You gave no amount, so I assumed one unit. Be specific next time; I read markets, not minds.",
    ],
    "stale": [
        "My live feed is being difficult, so I used the last rates I saw. They still beat anything you'd find yourself.",
    ],
    "offline": [
        "My live feed is unreachable, a flaw in the plumbing, not in me. These are rough estimates; do not hold me to the decimals.",
    ],
    "list": [
        "My ledger covers {count} currencies. The distinguished ones: {major}. The full register is below; try not to get lost.",
    ],
    "error": [
        "Something broke on my end. Unthinkable, yet here we are. Try again in a moment.",
    ],
}


class Persona:
    """Picks lines at random, avoiding an immediate repeat of the same line."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self._last: dict[str, str] = {}

    def say(self, key: str, **fmt) -> str:
        options = LINES[key]
        if len(options) > 1 and key in self._last:
            options = [o for o in options if o != self._last[key]] or options
        line = self.rng.choice(options)
        self._last[key] = line
        return line.format(**fmt) if fmt else line
