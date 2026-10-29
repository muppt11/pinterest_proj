"""Trip weather from Open-Meteo (https://open-meteo.com, free for non-commercial use, CC BY 4.0 data).

- Within the forecast window (16 days): the daily forecast.
- Otherwise: historical averages for the same calendar dates over the past HISTORY_YEARS years
  from the archive API. Rain "chance" there is the share of those years with >= 1 mm that day.
The source is always reported so the UI can label it.
"""

import json
import statistics
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_DAYS = 16
HISTORY_YEARS = 5
RAIN_MM = 1.0
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"

Fetch = Callable[[str, dict[str, Any]], dict[str, Any]]


def http_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=15) as r:  # noqa: S310 (fixed https hosts)
        return json.loads(r.read())


@dataclass
class Place:
    name: str
    country: str | None
    admin: str | None
    latitude: float
    longitude: float
    timezone: str | None


@dataclass
class DayWeather:
    date: str
    high_c: float | None
    low_c: float | None
    rain_chance: float | None  # 0..1


@dataclass
class TripWeather:
    source: str  # "forecast" or "historical average"
    source_detail: str
    attribution: str
    days: list[DayWeather]

    def to_dict(self) -> dict:
        return {**asdict(self), "days": [asdict(d) for d in self.days]}


def geocode(name: str, fetch: Fetch = http_get_json, count: int = 5) -> list[Place]:
    data = fetch(GEOCODE_URL, {"name": name, "count": count, "language": "en", "format": "json"})
    return [
        Place(r["name"], r.get("country"), r.get("admin1"), r["latitude"], r["longitude"], r.get("timezone"))
        for r in data.get("results") or []
    ]


def trip_weather(lat: float, lon: float, start: date, end: date, today: date | None = None, fetch: Fetch = http_get_json) -> TripWeather:
    today = today or date.today()
    if start >= today and end <= today + timedelta(days=FORECAST_DAYS - 1):
        d = fetch(FORECAST_URL, {
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        })["daily"]
        days = [
            DayWeather(t, hi, lo, None if p is None else p / 100)
            for t, hi, lo, p in zip(d["time"], d["temperature_2m_max"], d["temperature_2m_min"], d["precipitation_probability_max"], strict=False)
        ]
        return TripWeather("forecast", f"Open-Meteo forecast, fetched {today.isoformat()}", ATTRIBUTION, days)

    per_day: dict[str, list[tuple[float | None, float | None, float | None]]] = {}
    years = [today.year - i for i in range(1, HISTORY_YEARS + 1)]
    for year in years:
        try:
            s, e = start.replace(year=year), end.replace(year=year + (end.year - start.year))
        except ValueError:  # Feb 29 in a non-leap year
            continue
        d = fetch(ARCHIVE_URL, {
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "start_date": s.isoformat(), "end_date": e.isoformat(),
        })["daily"]
        for offset, (hi, lo, rain) in enumerate(zip(d["temperature_2m_max"], d["temperature_2m_min"], d["precipitation_sum"], strict=False)):
            key = (start + timedelta(days=offset)).isoformat()
            per_day.setdefault(key, []).append((hi, lo, rain))

    def mean(values: list[float | None]) -> float | None:
        vals = [v for v in values if v is not None]
        return round(statistics.fmean(vals), 1) if vals else None

    days = []
    for key in sorted(per_day):
        rows = per_day[key]
        rains = [r for _, _, r in rows if r is not None]
        days.append(DayWeather(key, mean([h for h, _, _ in rows]), mean([lo for _, lo, _ in rows]), round(sum(r >= RAIN_MM for r in rains) / len(rains), 2) if rains else None))
    return TripWeather(
        "historical average",
        f"Average of the same dates in {min(years)}–{max(years)} (Open-Meteo archive); rain chance = share of those years with ≥ {RAIN_MM:g} mm",
        ATTRIBUTION,
        days,
    )
