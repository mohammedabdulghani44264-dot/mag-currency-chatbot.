"""Flask entry point.  Run with:  python app.py"""
import logging

from flask import Flask, jsonify, render_template, request

from chatbot.currencies import CURRENCIES
from chatbot.engine import MAX_MESSAGE_LENGTH, ChatEngine
from chatbot.rates import RateService
from config import Config


def create_app(config: type = Config, rate_service: RateService | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    rates = rate_service or RateService(
        api_key=config.EXCHANGE_RATE_API_KEY,
        ttl_seconds=config.RATE_CACHE_SECONDS,
        timeout=config.RATE_TIMEOUT_SECONDS,
    )
    engine = ChatEngine(rates)
    app.extensions["chat_engine"] = engine

    @app.get("/")
    def index():
        return render_template("index.html", max_length=MAX_MESSAGE_LENGTH)

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
            return jsonify(error="Send JSON like {\"message\": \"100 USD to INR\"}."), 400
        try:
            return jsonify(engine.respond(payload["message"], payload.get("context")))
        except Exception:  # never leak a traceback to the browser
            app.logger.exception("Unhandled error while answering a message")
            return jsonify(
                reply=engine.persona.say("error"), intent="error", data=None,
                context=None,
            ), 500

    @app.get("/api/currencies")
    def currencies():
        return jsonify([{"code": c, "name": n} for c, n in sorted(CURRENCIES.items())])

    @app.get("/api/health")
    def health():
        snap = rates.get_snapshot()
        return jsonify(status="ok", rates=snap.status, provider=snap.provider,
                       as_of=snap.fetched_at.isoformat())

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    application = create_app()
    print(f"\n  Aurelius is receiving visitors at http://{Config.HOST}:{Config.PORT}\n")
    application.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
