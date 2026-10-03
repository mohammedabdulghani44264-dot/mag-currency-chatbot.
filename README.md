# Aurelius — Arrogant Currency Conversion Chatbot

Flask backend + live exchange-rate API + a banknote-styled chat page.
Aurelius understands amounts, units (k, million, billion, lakh, crore, "two hundred"),
currency codes (USD), symbols ($ € £ ¥ ₹), and names (rupees, dollars, yen, quid...).

## Run it (VS Code)

1. Open this folder in VS Code (File > Open Folder).
2. Open a terminal (Ctrl + `) and create a virtual environment:

   **Windows (PowerShell)**
   ```
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   If activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

   **macOS / Linux**
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies and start:
   ```
   pip install -r requirements.txt
   python app.py
   ```
4. Open http://127.0.0.1:5050 in your browser.

Run the tests (no internet needed): `python -m unittest discover -s tests -t .`

## Things to try
- `100 USD to INR`
- `5 lakh rupees in dollars`
- `€50 into yen, pounds and rupees`
- `how much is 2.5k GBP in AED?`
- `100 usd to all major currencies`
- `convert 100 usd` (it asks for the target, then you reply `inr`)
- then `and in eur?` or `what about 250?` (follow-ups remember the last conversion)
- `list currencies`, `help`

## Exchange-rate sources
Tried in order; the first that works is used, and results are cached for 1 hour.
1. ExchangeRate-API with your key (optional): set `EXCHANGE_RATE_API_KEY`
2. open.er-api.com (free, no key, ~160 currencies; attribution: https://www.exchangerate-api.com)
3. Frankfurter (free, no key, ~30 currencies)

If none is reachable, the last good rates are reused ("last known rates" stamp); if there
were never any, built-in approximate rates are used ("offline estimate" stamp), so the
app never crashes without internet.

## Configuration (environment variables, all optional)
| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `5050` | Port to serve on |
| `HOST` | `127.0.0.1` | Use `0.0.0.0` to expose on your network |
| `FLASK_DEBUG` | `0` | `1` enables auto-reload |
| `EXCHANGE_RATE_API_KEY` | none | Your exchangerate-api.com key |
| `RATE_CACHE_SECONDS` | `3600` | How long rates are cached |

PowerShell example: `$env:PORT=8000; python app.py`

## Structure
```
app.py                 Flask app + routes (/, /api/chat, /api/currencies, /api/health)
config.py              Settings from environment variables
chatbot/
  currencies.py        160 currencies, names, symbols, aliases, detection
  parser.py            Intent + entity extraction (amount, units, source, targets)
  engine.py            Dialogue logic, follow-ups, conversion
  rates.py             API providers, caching, fallback
  personality.py       Every line Aurelius says (edit here to change the attitude)
  formatting.py        Number formatting (lakh/crore grouping for INR)
templates/index.html   Chat page
static/css, static/js  Styling and front-end logic
tests/                 26 unit tests
```
