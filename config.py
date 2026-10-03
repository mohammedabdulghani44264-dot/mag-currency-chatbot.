"""Configuration, read from environment variables with safe defaults."""
import os


class Config:
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5050"))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Optional. Without a key the free open.er-api.com endpoint is used.
    EXCHANGE_RATE_API_KEY = os.environ.get("EXCHANGE_RATE_API_KEY") or None
    RATE_CACHE_SECONDS = float(os.environ.get("RATE_CACHE_SECONDS", "3600"))
    RATE_TIMEOUT_SECONDS = float(os.environ.get("RATE_TIMEOUT_SECONDS", "6"))
    JSON_SORT_KEYS = False
