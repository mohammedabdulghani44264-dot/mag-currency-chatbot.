import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from app import create_app
from chatbot.engine import ChatEngine
from chatbot.formatting import format_money
from chatbot.parser import parse
from chatbot.rates import RateService, RateSnapshot

RATES = {"USD": 1.0, "EUR": 0.9, "GBP": 0.8, "INR": 80.0, "JPY": 150.0,
         "AED": 3.6725, "AUD": 1.5, "CAD": 1.4, "CHF": 0.9, "CNY": 7.0}


class FakeRates(RateService):
    def __init__(self, status="live"):
        super().__init__()
        self.status = status

    def get_snapshot(self):
        return RateSnapshot(RATES, "fake", datetime.now(timezone.utc), self.status)


class ParserTests(unittest.TestCase):
    def check(self, text, amount, source, targets):
        p = parse(text)
        self.assertEqual((p.amount, p.source, p.targets), (amount, source, targets), text)

    def test_codes(self):
        self.check("100 USD to INR", 100, "USD", ["INR"])
        self.check("convert 100usd to inr", 100, "USD", ["INR"])
        self.check("USD to INR", None, "USD", ["INR"])

    def test_names_and_symbols(self):
        self.check("5000 rupees to dollars", 5000, "INR", ["USD"])
        self.check("how much is 20 euros in yen", 20, "EUR", ["JPY"])
        self.check("$100 in rupees", 100, "USD", ["INR"])
        self.check("₹5,000 to €", 5000, "INR", ["EUR"])
        self.check("50 british pounds to canadian dollars", 50, "GBP", ["CAD"])

    def test_units(self):
        self.check("5 lakh INR to USD", 500000, "INR", ["USD"])
        self.check("2 crore rupees in dollars", 2e7, "INR", ["USD"])
        self.check("2.5k GBP in AED", 2500, "GBP", ["AED"])
        self.check("1.2 million usd to eur", 1.2e6, "USD", ["EUR"])
        self.check("1,00,000 INR to USD", 100000, "INR", ["USD"])
        self.check("two hundred dollars to rupees", 200, "USD", ["INR"])
        self.check("a thousand euros in pounds", 1000, "EUR", ["GBP"])
        self.check("fifty dollars to inr", 50, "USD", ["INR"])

    def test_multi_targets(self):
        self.check("100 usd to inr, eur and gbp", 100, "USD", ["INR", "EUR", "GBP"])
        p = parse("100 usd to all major currencies")
        self.assertEqual(p.source, "USD")
        self.assertNotIn("USD", p.targets)
        self.assertGreater(len(p.targets), 5)

    def test_risky_words_are_not_currencies(self):
        self.assertEqual(parse("let me try this").mentions, [])
        self.assertEqual(parse("who won the match").mentions, [])
        self.check("5000 won to usd", 5000, "KRW", ["USD"])
        self.check("100 USD to TRY", 100, "USD", ["TRY"])

    def test_intents(self):
        for text, intent in [("hello", "greeting"), ("help", "help"), ("thanks", "thanks"),
                             ("bye", "bye"), ("list currencies", "list"), ("who are you", "who"),
                             ("how are you", "howru"), ("you are stupid", "roast"),
                             ("what is the meaning of life", "unknown"),
                             ("convert 100 usd to inr", "convert")]:
            self.assertEqual(parse(text).intent, intent, text)

    def test_unknown_and_ambiguous(self):
        self.assertEqual(parse("100 USD to XYZ").unknown, ["XYZ"])
        self.assertTrue(parse("100 bitcoin to usd").unknown)
        self.assertEqual(parse("100 dinar to usd").ambiguous, ["dinar"])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ChatEngine(FakeRates())

    def test_basic_conversion(self):
        r = self.engine.respond("100 USD to INR")
        self.assertEqual(r["intent"], "convert")
        self.assertAlmostEqual(r["data"]["results"][0]["value"], 8000)
        self.assertEqual(r["data"]["summary"], "100 USD = 8,000.00 INR")

    def test_cross_rate(self):
        r = self.engine.respond("90 EUR to GBP")
        self.assertAlmostEqual(r["data"]["results"][0]["value"], 80)

    def test_multi_target(self):
        r = self.engine.respond("100 usd to inr, eur and gbp")
        self.assertEqual([x["code"] for x in r["data"]["results"]], ["INR", "EUR", "GBP"])

    def test_default_one_unit(self):
        r = self.engine.respond("USD to INR")
        self.assertEqual(r["data"]["amount"], 1.0)

    def test_follow_up_target(self):
        r = self.engine.respond("convert 100 usd")
        self.assertEqual(r["context"]["awaiting"], "target")
        r = self.engine.respond("inr", r["context"])
        self.assertEqual(r["data"]["results"][0]["code"], "INR")
        self.assertEqual(r["data"]["amount"], 100)

    def test_follow_up_source(self):
        r = self.engine.respond("convert 500 to eur")
        self.assertEqual(r["context"]["awaiting"], "source")
        r = self.engine.respond("gbp", r["context"])
        self.assertEqual(r["data"]["source"]["code"], "GBP")
        self.assertEqual(r["data"]["results"][0]["code"], "EUR")

    def test_follow_ups_after_conversion(self):
        r = self.engine.respond("100 usd to inr")
        r2 = self.engine.respond("and in eur?", r["context"])
        self.assertEqual((r2["data"]["source"]["code"], r2["data"]["amount"]), ("USD", 100))
        r3 = self.engine.respond("what about 250?", r["context"])
        self.assertEqual(r3["data"]["amount"], 250)

    def test_edge_amounts(self):
        self.assertIsNone(self.engine.respond("100 usd to usd")["data"])
        self.assertEqual(self.engine.respond("0 usd to inr")["data"]["results"][0]["value"], 0)
        self.assertLess(self.engine.respond("-50 usd to inr")["data"]["results"][0]["value"], 0)
        self.assertIsNone(self.engine.respond("99999999999999999999 usd to inr")["data"])

    def test_clarifications(self):
        for text in ["convert", "100", "100 dinar to usd", "100 USD to XYZ", "100 bitcoin to usd"]:
            r = self.engine.respond(text)
            self.assertIsNone(r["data"], text)

    def test_bad_context_is_ignored(self):
        for ctx in ["x", 5, {"awaiting": "hack", "source": "ZZZ", "targets": "no", "last": 7}]:
            r = self.engine.respond("100 usd to inr", ctx)
            self.assertEqual(r["intent"], "convert")

    def test_estimate_notice(self):
        r = ChatEngine(FakeRates("offline")).respond("100 usd to inr")
        self.assertEqual(r["data"]["status"], "offline")
        self.assertIn("estimate", r["reply"])

    def test_list(self):
        r = self.engine.respond("list currencies")
        self.assertGreater(len(r["data"]["items"]), 100)


class FormattingTests(unittest.TestCase):
    def test_money(self):
        self.assertEqual(format_money(1234567.891, "USD"), "1,234,567.89")
        self.assertEqual(format_money(1234567.891, "INR"), "12,34,567.89")
        self.assertEqual(format_money(0.00123, "USD"), "0.00123")


class RateServiceTests(unittest.TestCase):
    def _resp(self, payload):
        m = mock.Mock()
        m.json.return_value = payload
        m.raise_for_status.return_value = None
        return m

    def test_live_then_cache(self):
        s = mock.Mock()
        s.get.return_value = self._resp({"result": "success", "rates": RATES})
        svc = RateService(session=s)
        self.assertEqual(svc.get_snapshot().status, "live")
        svc.get_snapshot()
        self.assertEqual(s.get.call_count, 1)

    def test_falls_back_to_second_provider(self):
        s = mock.Mock()
        no_usd = {k: v for k, v in RATES.items() if k != "USD"}
        s.get.side_effect = [requests.ConnectionError(), self._resp({"rates": no_usd})]
        snap = RateService(session=s).get_snapshot()
        self.assertEqual((snap.status, snap.provider), ("live", "frankfurter.dev"))

    def test_offline_then_live_then_stale(self):
        s = mock.Mock()
        s.get.side_effect = requests.ConnectionError()
        t = [0.0]
        svc = RateService(session=s, ttl_seconds=10, retry_cooldown=5, clock=lambda: t[0])
        self.assertEqual(svc.get_snapshot().status, "offline")
        s.get.side_effect = None
        s.get.return_value = self._resp({"result": "success", "rates": RATES})
        t[0] = 6
        self.assertEqual(svc.get_snapshot().status, "live")
        s.get.side_effect = requests.ConnectionError()
        t[0] = 30
        self.assertEqual(svc.get_snapshot().status, "stale")


class FlaskTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(rate_service=FakeRates()).test_client()

    def test_pages(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/js/app.js").status_code, 200)
        self.assertEqual(self.client.get("/static/css/style.css").status_code, 200)
        self.assertGreater(len(self.client.get("/api/currencies").get_json()), 100)
        self.assertEqual(self.client.get("/api/health").get_json()["status"], "ok")

    def test_chat(self):
        r = self.client.post("/api/chat", json={"message": "100 USD to INR"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"]["results"][0]["code"], "INR")

    def test_bad_requests(self):
        self.assertEqual(self.client.post("/api/chat", data="nope").status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"message": 5}).status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"message": "x" * 600}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
