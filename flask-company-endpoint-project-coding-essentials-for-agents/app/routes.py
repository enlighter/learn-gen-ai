from datetime import datetime

import yfinance as yf
from flask import Blueprint, current_app, jsonify, request

from .utils import (
    DEFAULT_INTERVAL,
    download_historical_data,
    extract_company_officers,
    generate_insights_from_history,
    historical_records_from_dataframe,
    normalize_history_payload,
    normalize_symbol,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _build_error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def _maybe_log(exception: Exception):
    current_app.logger.warning("Yahoo Finance lookup failed: %s", exception)


@bp.route("/company-info", methods=["GET"])
def company_info():
    symbol = request.args.get("symbol")
    try:
        symbol = normalize_symbol(symbol)
    except ValueError as exc:
        return _build_error(str(exc), 400)

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover - defensive
        _maybe_log(exc)
        return _build_error("Unable to reach Yahoo Finance for the symbol.", 502)

    if not info:
        return _build_error(f"Symbol {symbol} could not be resolved.", 404)

    return jsonify(
        {
            "symbol": symbol,
            "full_name": info.get("longName"),
            "summary": info.get("longBusinessSummary"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "country": info.get("country"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "key_officers": extract_company_officers(info),
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
    )


@bp.route("/market-data", methods=["GET"])
def market_data():
    symbol = request.args.get("symbol")
    try:
        symbol = normalize_symbol(symbol)
    except ValueError as exc:
        return _build_error(str(exc), 400)

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover - defensive
        _maybe_log(exc)
        return _build_error("Unable to reach Yahoo Finance for the market snapshot.", 502)

    current_price = info.get("regularMarketPrice") or info.get("previousClose")
    change = info.get("regularMarketChange")
    percent_change = info.get("regularMarketChangePercent")

    return jsonify(
        {
            "symbol": symbol,
            "market_state": info.get("marketState"),
            "current_price": current_price,
            "price_change": change,
            "percent_change": percent_change,
            "previous_close": info.get("regularMarketPreviousClose"),
            "open": info.get("regularMarketOpen"),
            "day_range": {
                "low": info.get("regularMarketDayLow"),
                "high": info.get("regularMarketDayHigh"),
            },
            "volume": info.get("volume"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@bp.route("/historical-data", methods=["POST"])
def historical_data():
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return _build_error("Payload is required.", 400)

    try:
        symbol = normalize_symbol(payload.get("symbol"))
    except ValueError as exc:
        return _build_error(str(exc), 400)

    interval = payload.get("interval", DEFAULT_INTERVAL)
    try:
        df = download_historical_data(
            symbol=symbol,
            start=payload.get("start"),
            end=payload.get("end"),
            interval=interval,
        )
    except ValueError as exc:
        return _build_error(str(exc), 400)

    records = historical_records_from_dataframe(df)
    return jsonify(
        {
            "symbol": symbol,
            "interval": interval,
            "count": len(records),
            "data": records,
        }
    )


@bp.route("/analysis", methods=["POST"])
def analytical_insights():
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return _build_error("Payload is required for analysis.", 400)

    try:
        symbol = normalize_symbol(payload.get("symbol"))
    except ValueError as exc:
        return _build_error(str(exc), 400)

    historical_payload = payload.get("historical_data")
    start = payload.get("start")
    end = payload.get("end")
    interval = payload.get("interval", DEFAULT_INTERVAL)

    try:
        if historical_payload:
            history_df = normalize_history_payload(historical_payload)
            data_source = "payload"
        else:
            history_df = download_historical_data(
                symbol=symbol, start=start, end=end, interval=interval
            )
            data_source = "yfinance"
    except ValueError as exc:
        return _build_error(str(exc), 400)

    insights = generate_insights_from_history(symbol, history_df)
    insights["data_source"] = data_source

    return jsonify({"symbol": symbol, "insights": insights})

