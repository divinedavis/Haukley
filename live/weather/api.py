#!/usr/bin/env python3
"""Haukley local weather API: the forecast for where the viewer is, or a city they pick.

    GET /api/weather/local            locate by the caller's IP (city level)
    GET /api/weather/local?zip=11201  a US ZIP code
    GET /api/weather/local?lat=40.69&lon=-73.99   device location (opt-in in the apps)
    GET /api/weather/local?city=new-york-ny       one of /api/weather/cities
    GET /api/weather/cities           the city picker list

200 {"place":{"name","source","lat","lon"},"now":{"temp","unit","text","wind"},
     "periods":[{"name","temp","text","day"}...<=6],"alerts":[{"event","headline"}],
     "updated","attribution"}
422 {"error":"unknown_location"}   non-US, unknown ZIP/city, bad coordinates
503 {"error":"unavailable"}        NOAA down and nothing cached for that spot

Privacy (owner rule, 2026-10-10): the IP is used once, in memory, to find a city-level
location and is never stored or logged; coordinates are rounded to 2 decimals (~1 km)
before anything else sees them; this process logs no request parameters and nginx logs
nothing for /api/weather/. No cookies.

Sources: NOAA/NWS api.weather.gov (public domain), Census ZCTA gazetteer for ZIPs (public
domain, data/zcta.json), DB-IP City Lite for IP -> city (CC BY 4.0, attribution in every
response; refreshed monthly by `api.py refresh-db`, haukley-geoip.timer).

Run: api.py serve [--port 8131]   |   api.py refresh-db
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
UA = "Haukley Weather (hello@haukley.com)"
NWS = "https://api.weather.gov"
ATTRIBUTION = "Forecast: NOAA/National Weather Service. Location: DB-IP"
STATE = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/haukley-live"))
CITY_DB = Path(os.environ.get("HAUKLEY_CITY_DB", STATE / "dbip-city-lite.mmdb"))

POINT_TTL = 30 * 86400      # lat/lon -> NWS grid rarely changes
NOT_US_TTL = 86400          # a /points 404 (outside NWS coverage)
FORECAST_TTL = 15 * 60
ALERTS_TTL = 5 * 60
STALE_MAX = 6 * 3600        # serve a stale forecast this long when NOAA is down
OUT_BUDGET = (300, 600)     # at most 300 NOAA requests per 10 minutes, all viewers together
MAX_ENTRIES = 20000

ZIPS: dict[str, list[float]] = {}
CITIES: list[dict] = []
CITY_BY_SLUG: dict[str, dict] = {}


def load_data():
    global ZIPS, CITIES, CITY_BY_SLUG
    ZIPS = json.loads((HERE / "data" / "zcta.json").read_text())
    CITIES = json.loads((HERE / "data" / "cities.json").read_text())
    CITY_BY_SLUG = {c["slug"]: c for c in CITIES}


# ---------------------------------------------------------------- outbound (NOAA)

class Unavailable(Exception):
    pass


class NotUS(Exception):
    pass


_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}   # key -> (stored_at, value)
_budget: list[float] = []


def _get(key, ttl):
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1], True
    return (hit[1] if hit else None), False


def _put(key, value):
    with _lock:
        if len(_cache) > MAX_ENTRIES:   # crude bound: drop the oldest tenth
            for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[: MAX_ENTRIES // 10]:
                _cache.pop(k, None)
        _cache[key] = (time.time(), value)


def _spend():
    now = time.time()
    with _lock:
        while _budget and now - _budget[0] > OUT_BUDGET[1]:
            _budget.pop(0)
        if len(_budget) >= OUT_BUDGET[0]:
            return False
        _budget.append(now)
        return True


def fetch_json(url):
    """GET a NOAA URL. Raises NotUS on 404 from /points, Unavailable otherwise."""
    if not _spend():
        raise Unavailable("outbound budget spent")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404 and "/points/" in url:
            raise NotUS() from e
        raise Unavailable(f"NWS {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise Unavailable(type(e).__name__) from e


def cached(key, ttl, url, shape):
    """Fresh cache, else NOAA, else a stale copy up to STALE_MAX old, else Unavailable."""
    val, fresh = _get(key, ttl)
    if fresh:
        return val
    try:
        new = shape(fetch_json(url))
    except Unavailable:
        with _lock:
            hit = _cache.get(key)
        if hit and time.time() - hit[0] < STALE_MAX:
            return hit[1]
        raise
    _put(key, new)
    return new


def point(lat, lon):
    key = f"pt:{lat:.2f},{lon:.2f}"
    with _lock:
        neg = _cache.get("no:" + key)
    if neg and time.time() - neg[0] < NOT_US_TTL:
        raise NotUS()
    try:
        return cached(key, POINT_TTL, f"{NWS}/points/{lat:.4f},{lon:.4f}", lambda d: {
            "forecast": d["properties"]["forecast"],
            "hourly": d["properties"]["forecastHourly"],
            "grid": f'{d["properties"]["gridId"]}/{d["properties"]["gridX"]},{d["properties"]["gridY"]}',
            "name": _place_name(d["properties"].get("relativeLocation")),
        })
    except NotUS:
        _put("no:" + key, True)
        raise


def _place_name(rel):
    p = (rel or {}).get("properties") or {}
    city, state = p.get("city"), p.get("state")
    return f"{city}, {state}" if city and state else None


def forecast(pt):
    periods = cached("fc:" + pt["grid"], FORECAST_TTL, pt["forecast"], lambda d: {
        "updated": d["properties"].get("updateTime") or d["properties"].get("generatedAt"),
        "periods": [{"name": p["name"], "temp": p["temperature"], "text": p.get("shortForecast", ""),
                     "day": bool(p.get("isDaytime", True))} for p in d["properties"]["periods"][:6]],
    })
    now = cached("hr:" + pt["grid"], FORECAST_TTL, pt["hourly"], lambda d: (lambda p: {
        "temp": p["temperature"], "unit": p.get("temperatureUnit", "F"),
        "text": p.get("shortForecast", ""),
        "wind": f'{p.get("windDirection", "")} {p.get("windSpeed", "")}'.strip(),
    })(d["properties"]["periods"][0]))
    return now, periods


def alerts(lat, lon):
    try:
        return cached(f"al:{lat:.2f},{lon:.2f}", ALERTS_TTL,
                      f"{NWS}/alerts/active?status=actual&message_type=alert&point={lat:.4f},{lon:.4f}",
                      lambda d: [{"event": f["properties"].get("event") or "Alert",
                                  "headline": f["properties"].get("headline") or ""}
                                 for f in d.get("features", [])[:5]])
    except Unavailable:
        return []   # alerts are a bonus; never fail the forecast over them


# ---------------------------------------------------------------- locating the viewer

_mmdb = None


def ip_location(ip):
    """(lat, lon, name) for a US address from DB-IP City Lite, else None. In memory only."""
    global _mmdb
    if _mmdb is None:
        try:
            import maxminddb
            _mmdb = maxminddb.open_database(str(CITY_DB))
        except Exception:  # noqa: BLE001 - no DB yet: the apps fall back to the city picker
            _mmdb = False
    if not _mmdb or not ip:
        return None
    try:
        r = _mmdb.get(ip) or {}
    except ValueError:
        return None
    if (r.get("country") or {}).get("iso_code") != "US":
        return None
    loc = r.get("location") or {}
    if loc.get("latitude") is None:
        return None
    city = ((r.get("city") or {}).get("names") or {}).get("en")
    return round(float(loc["latitude"]), 2), round(float(loc["longitude"]), 2), city


def resolve(q, ip):
    """-> (lat, lon, source, name or None). Raises NotUS for anything unusable."""
    one = lambda k: (q.get(k) or [""])[0].strip()  # noqa: E731
    lat_s, lon_s, zip_s, slug = one("lat"), one("lon"), one("zip"), one("city")
    if lat_s or lon_s:
        try:
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            raise NotUS()
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise NotUS()
        return round(lat, 2), round(lon, 2), "gps", None
    if zip_s:
        if not re.fullmatch(r"\d{5}", zip_s) or zip_s not in ZIPS:
            raise NotUS()
        lat, lon = ZIPS[zip_s]
        return round(lat, 2), round(lon, 2), "zip", None
    if slug:
        c = CITY_BY_SLUG.get(slug)
        if not c:
            raise NotUS()
        return round(c["lat"], 2), round(c["lon"], 2), "city", c["name"]
    found = ip_location(ip)
    if not found:
        raise NotUS()
    return found[0], found[1], "ip", None


def local_weather(q, ip):
    lat, lon, source, name = resolve(q, ip)
    pt = point(lat, lon)
    now, fc = forecast(pt)
    return {
        "place": {"name": name or pt["name"] or "Your area", "source": source, "lat": lat, "lon": lon},
        "now": now,
        "periods": fc["periods"],
        "alerts": alerts(lat, lon),
        "updated": fc["updated"] or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "attribution": ATTRIBUTION,
    }


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "HaukleyWeather/1"
    sys_version = ""

    def log_message(self, *args):  # privacy: no request lines, no addresses, no params
        pass

    def _send(self, code, body, cache):
        raw = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/weather/cities":
            return self._send(200, {"cities": [{"slug": c["slug"], "name": c["name"]} for c in CITIES]},
                              "public, max-age=86400")
        if u.path != "/api/weather/local":
            return self._send(404, {"error": "not_found"}, "no-store")
        # nginx sets X-Real-IP from $remote_addr; a client-sent X-Forwarded-For is ignored.
        ip = self.headers.get("X-Real-IP", "")
        try:
            body = local_weather(parse_qs(u.query), ip)
        except NotUS:
            return self._send(422, {"error": "unknown_location"}, "private, max-age=600")
        except Unavailable:
            return self._send(503, {"error": "unavailable"}, "no-store")
        except Exception:  # noqa: BLE001 - never a 500 with a stack trace to a TV
            return self._send(503, {"error": "unavailable"}, "no-store")
        finally:
            ip = None
        return self._send(200, body, "private, max-age=600")


def refresh_db():
    """Download this month's DB-IP City Lite (CC BY 4.0) into the state directory."""
    STATE.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    last = (today.replace(day=1) - datetime.timedelta(days=1))
    for ym in (today.strftime("%Y-%m"), last.strftime("%Y-%m")):
        url = f"https://download.db-ip.com/free/dbip-city-lite-{ym}.mmdb.gz"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = gzip.decompress(r.read())
        except (urllib.error.URLError, OSError, EOFError):
            continue
        tmp = CITY_DB.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, CITY_DB)
        print(f"DB-IP City Lite {ym}: {len(data) // 1_000_000} MB -> {CITY_DB}")
        return 0
    print("DB-IP City Lite download failed; keeping the existing file", file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["serve", "refresh-db"])
    ap.add_argument("--port", type=int, default=int(os.environ.get("HAUKLEY_WEATHER_PORT", "8131")))
    a = ap.parse_args()
    if a.cmd == "refresh-db":
        return refresh_db()
    load_data()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main())
