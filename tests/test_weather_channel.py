"""Haukley Weather live channel (live/weather/channel.py): the live playlist logic and the
NWS parsing, stdlib only (rendering needs Pillow + ffmpeg and is checked on the droplet)."""
import importlib.util
import math
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("channel", ROOT / "live/weather/channel.py")
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)

SEG = ch.SEG


def parse(pl):
    head = dict(re.findall(r"#EXT-X-([A-Z-]+):(\d+)", pl))
    segs = re.findall(r"^(c\d+/seg\d{3}\.ts)$", pl, re.M)
    return head, segs


class Timeline(unittest.TestCase):
    def test_cold_start_backfills_a_full_window(self):
        tl = ch.Timeline()
        tl.tick(1000.0, {"1": [SEG] * 10}, "1")
        head, segs = parse(tl.playlist())
        self.assertEqual(len(segs), ch.WINDOW)
        self.assertEqual(segs[0], "c1/seg000.ts")
        self.assertNotIn("#EXT-X-ENDLIST", tl.playlist())   # live, not VOD
        self.assertEqual(head["TARGETDURATION"], str(math.ceil(SEG)))

    def test_sequence_counts_dropped_segments(self):
        tl = ch.Timeline()
        cycles = {"1": [SEG] * 100}
        tl.tick(0.0, cycles, "1")
        tl.tick(10 * SEG, cycles, "1")
        head, segs = parse(tl.playlist())
        self.assertEqual(int(head["MEDIA-SEQUENCE"]), 10)
        self.assertEqual(segs[0], "c1/seg010.ts")

    def test_cycle_wrap_switches_to_newest_with_discontinuity(self):
        tl = ch.Timeline()
        tl.tick(0.0, {"1": [SEG] * 10}, "1")
        cycles = {"1": [SEG] * 10, "2": [SEG] * 20}
        tl.tick(3 * SEG, cycles, "2")
        pl = tl.playlist()
        self.assertIn(f"#EXT-X-DISCONTINUITY\n#EXTINF:{SEG:.3f},\nc2/seg000.ts", pl)
        # the old cycle is still referenced until it leaves the window
        self.assertEqual(tl.referenced(), {"1", "2"})
        tl.tick(3 * SEG + ch.WINDOW * SEG, cycles, "2")
        head, segs = parse(tl.playlist())
        self.assertEqual(tl.referenced(), {"2"})
        self.assertEqual(int(head["DISCONTINUITY-SEQUENCE"]), 1)
        self.assertNotIn("#EXT-X-DISCONTINUITY\n", tl.playlist())

    def test_same_cycle_repeats_with_discontinuity(self):
        tl = ch.Timeline()
        cycles = {"1": [SEG] * 3}
        tl.tick(0.0, cycles, "1")
        _, segs = parse(tl.playlist())
        self.assertEqual(segs, [f"c1/seg{i % 3:03d}.ts" for i in range(ch.WINDOW)])
        self.assertEqual(tl.playlist().count("#EXT-X-DISCONTINUITY\n"), (ch.WINDOW - 1) // 3)

    def test_state_round_trip_and_outage_restart(self):
        tl = ch.Timeline()
        cycles = {"1": [SEG] * 50}
        tl.tick(0.0, cycles, "1")
        seq = tl.seq
        tl2 = ch.Timeline(tl.state())
        tl2.tick(SEG, cycles, "1")
        self.assertEqual(tl2.seq, seq + 1)
        # an hour of downtime: restart near now, never go backwards in sequence
        tl2.tick(3600.0, cycles, "1")
        head, _ = parse(tl2.playlist())
        self.assertGreater(int(head["MEDIA-SEQUENCE"]), seq)
        self.assertLessEqual(len(tl2.entries), ch.WINDOW)

    def test_deleted_cycle_restarts_on_newest(self):
        tl = ch.Timeline()
        tl.tick(0.0, {"1": [SEG] * 50}, "1")
        tl.tick(SEG, {"2": [SEG] * 50}, "2")
        self.assertEqual(tl.cycle, "2")

    def test_master_playlist_points_at_live(self):
        m = ch.master_playlist()
        self.assertIn("mp4a.40.2", m)  # Roku won't play video-only HLS
        self.assertIn("#EXT-X-STREAM-INF:BANDWIDTH=", m)
        self.assertTrue(m.rstrip().endswith("live.m3u8"))


class Parsing(unittest.TestCase):
    def test_summarize_city(self):
        hourly = {"properties": {"periods": [{"temperature": 69, "temperatureUnit": "F",
                  "shortForecast": "Sunny", "windDirection": "W", "windSpeed": "15 mph"}]}}
        fc = {"properties": {"periods": [{"name": f"P{i}", "temperature": 60 + i,
              "shortForecast": "Rain", "isDaytime": i % 2 == 0} for i in range(14)]}}
        c = ch.summarize_city(fc, hourly)
        self.assertEqual((c["temp"], c["now"], c["wind"]), (69, "Sunny", "W 15 mph"))
        self.assertEqual(len(c["periods"]), 6)

    def test_summarize_alerts(self):
        feats = [{"properties": {"event": e}} for e in ["Flood Warning"] * 3 + ["Tornado Warning"]]
        a = ch.summarize_alerts({"features": feats})
        self.assertEqual(a["total"], 4)
        self.assertEqual(a["top"][0], ("Flood Warning", 3))

    def test_segment_is_whole_video_and_audio_frames(self):
        # audio and video must cut on the same instant (no per-segment A/V offset)
        self.assertAlmostEqual(SEG * ch.FPS, round(SEG * ch.FPS), places=9)
        aac_frames = SEG * ch.AUDIO_RATE / 1024
        self.assertAlmostEqual(aac_frames, round(aac_frames), places=9)
        self.assertGreaterEqual(len(ch.CITIES), 10)


if __name__ == "__main__":
    unittest.main()
