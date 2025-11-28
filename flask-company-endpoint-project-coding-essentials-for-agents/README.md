# Flask Company Data API

This project exposes four REST endpoints that wrap Yahoo Finance data via `yfinance` to surface company profiles, live quotes, historical prices, and simple analytics.

## Quick Start

1. Create a virtual environment and install requirements.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Start the Flask server.

   ```bash
   python run.py
   ```

   The API listens on `http://127.0.0.1:5000/api/...`.

## Endpoints

### `GET /api/company-info?symbol=<SYMBOL>`

Returns company metadata retrieved from Yahoo Finance.

**Response fields**
- `full_name`, `summary`, `industry`, `sector`
- `key_officers` (name/title/firm tuples)
- `region`, `website`, `employees`

Example:

```http
GET /api/company-info?symbol=AAPL
```

### `GET /api/market-data?symbol=<SYMBOL>`

Fetches the current market snapshot:
- `market_state`, `current_price`, `price_change`, `percent_change`
- intraday `day_range`, `volume`, `previous_close`

### `POST /api/historical-data`

Request JSON:

```json
{
  "symbol": "AAPL",
  "start": "2025-01-01",
  "end": "2025-11-25",
  "interval": "1d"
}
```

Returns ordered OHLCV data for the requested range plus metadata such as record count.

### `POST /api/analysis`

Analyzes supplied or fetched historical data to deliver insights.

Payload options:

1. **Fetch from Yahoo Finance**

   ```json
   {
     "symbol": "AAPL",
     "start": "2025-01-01",
     "end": "2025-11-25",
     "interval": "1d"
   }
   ```

2. **Provide historical data directly**

   ```json
   {
     "symbol": "AAPL",
     "historical_data": [
       {"date": "2025-11-25", "close": 175.0},
       {"date": "2025-11-24", "close": 174.4}
     ]
   }
   ```

Response includes trend direction, volatility profile, moving averages, and a short recommendation.

## Notes

- The endpoints rely on Yahoo Finance snapshots and will raise HTTP 502 if the upstream API is unreachable.
- The analysis endpoint always returns a `data_source` flag explaining whether it consumed the payload or fetched data internally.

