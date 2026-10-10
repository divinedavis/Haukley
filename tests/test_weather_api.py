"""Local weather API (live/weather/api.py): locating the viewer, the contract shape, caching,
privacy (no request logging, rounded coordinates) and failure codes. NOAA is mocked, stdlib only."""
import importlib.util
import io
import json
import pathlib
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("weather_api", ROOT / "live/weather/api.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
api.load_data()

POINTS = {"properties": {"forecast": "https://api.weather.gov/gridpoints/OKX/33,35/forecast",
                         "forecastHourly": "https://api.weather.gov/gridpoints/OKX/33,35/forecast/hourly",
                         "gridId": "OKX", "gridX": 33, "gridY": 35,
                         "relativeLocation": {"properties": {"city": "Brooklyn", "state": "NY"}}}}
FORECAST = {"properties": {"updateTime": "2026-10-10T18:00:00+00:00", "periods": [
    {"name": f"P{i}", "temperature": 60 + i, "shortForecast": "Sunny", "isDaytime": i % 2 == 0} for i in range(14)]}}
HOURLY = {"properties": {"periods": [{"temperature": 69, "temperatureUnit": "F", "shortForecast": "Sunny",
                                      "windDirection": "W", "windSpeed": "15 mph"}]}}
ALERTS = {"features": [{"properties": {"event": "Flood Watch", "headline": "Flood Watch until 8 PM"}}]}


def fake_noaa(calls):
    def fetch(url):
        calls.append(url)
        if "/points/" in url:
            if url.split("/points/")[1].startswith("51.5"):
                raise api.NotUS()
            return POINTS
        if url.endswith("/forecast/hourly"):
            return HOURLY
        if url.endswith("/forecast"):
            return FORECAST
        if "/alerts/active" in url:
            return ALERTS
        raise AssertionError(url)
    return fetch


class Contract(unittest.TestCase):
    def setUp(self):
        api._cache.clear()
        self.calls = []
        p = mock.patch.object(api, "fetch_json", side_effect=fake_noaa(self.calls))
        p.start()
        self.addCleanup(p.stop)

    def test_zip_shape_matches_contract(self):
        b = api.local_weather({"zip": ["11201"]}, "")
        self.assertEqual(set(b), {"place", "now", "periods", "alerts", "updated", "attribution"})
        self.assertEqual(b["place"]["source"], "zip")
        self.assertEqual(b["place"]["name"], "Brooklyn, NY")
        self.assertEqual(b["now"], {"temp": 69, "unit": "F", "text": "Sunny", "wind": "W 15 mph"})
        self.assertEqual(len(b["periods"]), 6)
        self.assertEqual(set(b["periods"][0]), {"name", "temp", "text", "day"})
        self.assertEqual(b["alerts"], [{"event": "Flood Watch", "headline": "Flood Watch until 8 PM"}])
        self.assertIn("DB-IP", b["attribution"])

    def test_gps_is_rounded_to_about_a_kilometre(self):
        b = api.local_weather({"lat": ["40.69321"], "lon": ["-73.98765"]}, "")
        self.assertEqual((b["place"]["lat"], b["place"]["lon"]), (40.69, -73.99))
        self.assertTrue(all("40.6932" not in u for u in self.calls), self.calls)

    def test_city_uses_its_own_name(self):
        b = api.local_weather({"city": ["chicago-il"]}, "")
        self.assertEqual((b["place"]["name"], b["place"]["source"]), ("Chicago, IL", "city"))

    def test_unknown_inputs_are_unknown_location(self):
        for q in ({"zip": ["00000"]}, {"zip": ["1120"]}, {"city": ["atlantis"]},
                  {"lat": ["x"], "lon": ["1"]}, {"lat": ["95"], "lon": ["0"]}, {"lat": ["51.5"], "lon": ["-0.12"]}):
            with self.assertRaises(api.NotUS, msg=q):
                api.local_weather(q, "")

    def test_ip_without_a_us_match_is_unknown(self):
        with mock.patch.object(api, "ip_location", return_value=None):
            with self.assertRaises(api.NotUS):
                api.local_weather({}, "81.2.69.142")

    def test_ip_location_is_used_when_no_param(self):
        with mock.patch.object(api, "ip_location", return_value=(40.69, -73.99, "Brooklyn")):
            b = api.local_weather({}, "72.1.1.1")
        self.assertEqual(b["place"]["source"], "ip")

    def test_grid_cache_bounds_noaa_calls(self):
        api.local_weather({"zip": ["11201"]}, "")
        n = len(self.calls)
        api.local_weather({"zip": ["11201"]}, "")
        self.assertEqual(len(self.calls), n, "second request for the same spot must be served from cache")

    def test_stale_forecast_served_when_noaa_is_down(self):
        api.local_weather({"zip": ["11201"]}, "")
        for k, (t, v) in list(api._cache.items()):
            api._cache[k] = (t - api.FORECAST_TTL - 1, v)   # expire the fresh window
        with mock.patch.object(api, "fetch_json", side_effect=api.Unavailable("down")):
            b = api.local_weather({"zip": ["11201"]}, "")
        self.assertEqual(b["now"]["temp"], 69)

    def test_nothing_cached_and_noaa_down_is_unavailable(self):
        with mock.patch.object(api, "fetch_json", side_effect=api.Unavailable("down")):
            with self.assertRaises(api.Unavailable):
                api.local_weather({"zip": ["11201"]}, "")

    def test_cities_list(self):
        self.assertGreaterEqual(len(api.CITIES), 100)
        slugs = [c["slug"] for c in api.CITIES]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual([c["name"] for c in api.CITIES], sorted(c["name"] for c in api.CITIES))
        self.assertIn("new-york-ny", slugs)


class Http(unittest.TestCase):
    """The real handler on a loopback port: status codes, headers, no logging."""

    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path, headers=None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, dict(r.headers), json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), json.load(e)

    def test_local_ok_headers_and_no_cookie(self):
        api._cache.clear()
        with mock.patch.object(api, "fetch_json", side_effect=fake_noaa([])):
            code, h, b = self.get("/api/weather/local?zip=11201")
        self.assertEqual(code, 200)
        self.assertEqual(h.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(h.get("Cache-Control"), "private, max-age=600")
        self.assertNotIn("Set-Cookie", h)

    def test_status_codes(self):
        self.assertEqual(self.get("/api/weather/local?zip=00000")[0], 422)
        self.assertEqual(self.get("/api/weather/local?zip=00000")[2], {"error": "unknown_location"})
        api._cache.clear()
        with mock.patch.object(api, "fetch_json", side_effect=api.Unavailable("down")):
            code, _, b = self.get("/api/weather/local?zip=11201")
        self.assertEqual((code, b), (503, {"error": "unavailable"}))
        with mock.patch.object(api, "local_weather", side_effect=KeyError("boom")):
            self.assertEqual(self.get("/api/weather/local?zip=11201")[0], 503)
        code, h, b = self.get("/api/weather/cities")
        self.assertEqual((code, h.get("Cache-Control")), (200, "public, max-age=86400"))

    def test_x_real_ip_is_used_and_forwarded_for_ignored(self):
        seen = []
        with mock.patch.object(api, "ip_location", side_effect=lambda ip: seen.append(ip)):
            self.get("/api/weather/local", {"X-Real-IP": "72.1.1.1", "X-Forwarded-For": "8.8.8.8"})
        self.assertEqual(seen, ["72.1.1.1"])

    def test_handler_logs_nothing(self):
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            self.get("/api/weather/local?zip=00000")
            time.sleep(0.1)
        self.assertNotIn("00000", buf.getvalue())
        self.assertNotIn("zip", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
