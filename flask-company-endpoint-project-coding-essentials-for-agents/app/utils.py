from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_HISTORY_DAYS = 180
DEFAULT_INTERVAL = "1d"
TREND_SLOPE_THRESHOLD = 0.01


def normalize_symbol(symbol: str) -> str:
    if not symbol:
        raise ValueError("A symbol must be provided.")

    return symbol.strip().upper()


def parse_iso_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(date_str)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date: {date_str}") from exc


def build_date_range(
    start: Optional[str], end: Optional[str], default_window: int = DEFAULT_HISTORY_DAYS
) -> tuple[datetime, datetime]:
    if end:
        end_dt = parse_iso_date(end)
    else:
        end_dt = datetime.utcnow()

    if start:
        start_dt = parse_iso_date(start)
    else:
        start_dt = end_dt - timedelta(days=default_window)

    if start_dt > end_dt:
        raise ValueError("start date cannot be after end date")

    return start_dt, end_dt


def download_historical_data(
    symbol: str,
    start: Optional[str],
    end: Optional[str],
    interval: str = DEFAULT_INTERVAL,
) -> pd.DataFrame:
    start_dt, end_dt = build_date_range(start, end)
    ticker = yf.Ticker(symbol)
    history = ticker.history(
        start=start_dt,
        end=end_dt + timedelta(days=1),
        interval=interval,
        actions=False,
    )
    if history.empty:
        raise ValueError("No historical data found for the requested range and symbol.")

    history = history.loc[:, ["Open", "High", "Low", "Close", "Volume"]].copy()
    history.index = history.index.tz_convert(None) if history.index.tz else history.index
    history = history.reset_index()
    history.rename(columns={"Date": "Date"}, inplace=True)
    return history


def historical_records_from_dataframe(df: pd.DataFrame) -> list[dict]:
    records: list[dict] = []
    for row in df.itertuples(index=False):
        records.append(
            {
                "date": getattr(row, "Date").strftime("%Y-%m-%d"),
                "open": float(round(getattr(row, "Open", 0.0), 4) if not pd.isna(getattr(row, "Open")) else 0.0),
                "high": float(round(getattr(row, "High", 0.0), 4) if not pd.isna(getattr(row, "High")) else 0.0),
                "low": float(round(getattr(row, "Low", 0.0), 4) if not pd.isna(getattr(row, "Low")) else 0.0),
                "close": float(round(getattr(row, "Close", 0.0), 4) if not pd.isna(getattr(row, "Close")) else 0.0),
                "volume": int(getattr(row, "Volume", 0)) if not pd.isna(getattr(row, "Volume")) else 0,
            }
        )

    return records


def normalize_history_payload(data: Sequence[Mapping]) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError("Historical payload is empty.")

    column_map = {}
    for original in df.columns:
        normalized = original.strip().lower()
        if normalized == "date":
            column_map[original] = "Date"
        elif normalized == "open":
            column_map[original] = "Open"
        elif normalized in {"high", "high_price"}:
            column_map[original] = "High"
        elif normalized in {"low", "low_price"}:
            column_map[original] = "Low"
        elif normalized == "close":
            column_map[original] = "Close"
        elif normalized in {"volume", "vol"}:
            column_map[original] = "Volume"

    df.rename(columns=column_map, inplace=True)
    if "Date" not in df.columns or "Close" not in df.columns:
        raise ValueError("Historical payload must include at least 'date' and 'close' fields.")

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def extract_company_officers(company_info: Mapping) -> list[dict]:
    officers = company_info.get("companyOfficers") or []
    formatted = []
    for officer in officers:
        name = officer.get("name")
        title = officer.get("title")
        if name or title:
            formatted.append(
                {
                    "name": name,
                    "title": title,
                    "firm": officer.get("firm"),
                }
            )

    return formatted


def generate_insights_from_history(symbol: str, df: pd.DataFrame) -> dict:
    df_augmented = df.copy()
    if "Date" not in df_augmented.columns:
        if df_augmented.index.name == "Date":
            df_augmented = df_augmented.reset_index()
        else:
            raise ValueError("Historical data must contain a 'Date' column.")

    df_augmented["Date"] = pd.to_datetime(df_augmented["Date"])
    df_augmented = df_augmented.sort_values("Date")

    close = df_augmented["Close"].astype(float)
    df_augmented["daily_return"] = close.pct_change()

    avg_return = float(close.pct_change().mean(skipna=True) or 0.0)
    volatility = float(df_augmented["daily_return"].std(skipna=True) or 0.0)

    latest_close = float(close.iloc[-1])
    first_close = float(close.iloc[0]) if not pd.isna(close.iloc[0]) else latest_close
    percent_change = ((latest_close - first_close) / first_close * 100) if first_close else 0.0

    valid_data = df_augmented.dropna(subset=["Close"])
    trend_direction = "flat"
    slope_value = 0.0
    if len(valid_data) >= 2:
        x_values = valid_data["Date"].map(datetime.toordinal).astype(float)
        y_values = valid_data["Close"].astype(float)
        slope_value = float(np.polyfit(x_values, y_values, 1)[0])
        if slope_value > TREND_SLOPE_THRESHOLD:
            trend_direction = "upward"
        elif slope_value < -TREND_SLOPE_THRESHOLD:
            trend_direction = "downward"

    avg_volume = int(valid_data["Volume"].mean()) if "Volume" in valid_data else None
    moving_average_20 = float(close.tail(20).mean())

    recommendations = "Neutral momentum; continue observing."
    if trend_direction == "upward" and avg_return >= 0:
        recommendations = "Bullish momentum; consider accumulation with risk controls."
    elif trend_direction == "downward" and avg_return <= 0:
        recommendations = "Bearish momentum; prefer defensive posture."

    volatility_profile = "low"
    if volatility > 0.03:
        volatility_profile = "high"
    elif volatility > 0.015:
        volatility_profile = "moderate"

    return {
        "symbol": symbol,
        "date_range": {
            "start": df_augmented["Date"].dt.date.iloc[0].isoformat(),
            "end": df_augmented["Date"].dt.date.iloc[-1].isoformat(),
        },
        "latest_close": latest_close,
        "percent_change": round(percent_change, 2),
        "trend_direction": trend_direction,
        "volatility_profile": volatility_profile,
        "volatility": round(volatility, 4),
        "average_daily_return": round(avg_return, 4),
        "average_volume": avg_volume,
        "20_day_moving_average": round(moving_average_20, 4),
        "momentum_slope": round(slope_value, 6),
        "recommendation": recommendations,
    }

