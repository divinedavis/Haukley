"""scripts/ingest_free_titles.py shows every title at its display aspect: DVD/NARA sources
with non-square pixels (720x480 at 8:9, 720x576 at 16:15) must come out 4:3, not 3:2 or 5:4
(The Black Pirate, The Woman in Green, Apollo e4 and WWII Combat Reports all shipped
distorted before 2026-10-10), and a source's display_aspect override wins."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ingest", ROOT / "scripts/ingest_free_titles.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)


def title(**source):
    return {"id": "x", "source": source}


class DisplayAspect(unittest.TestCase):
    def test_ntsc_dvd_is_four_by_three(self):
        v = {"width": 720, "height": 480, "sample_aspect_ratio": "8:9"}
        self.assertAlmostEqual(ingest.display_aspect(title(), v), 4 / 3, places=3)

    def test_pal_dvd_is_four_by_three(self):
        v = {"width": 720, "height": 576, "sample_aspect_ratio": "16:15"}
        self.assertAlmostEqual(ingest.display_aspect(title(), v), 4 / 3, places=3)

    def test_square_pixels_and_missing_sar(self):
        for sar in ("1:1", None, "0:1", "N/A"):
            v = {"width": 640, "height": 480, "sample_aspect_ratio": sar}
            self.assertAlmostEqual(ingest.display_aspect(title(), v), 4 / 3, places=3)

    def test_override_for_baked_in_distortion(self):
        v = {"width": 540, "height": 360, "sample_aspect_ratio": "1:1"}
        self.assertAlmostEqual(ingest.display_aspect(title(display_aspect="4:3"), v), 4 / 3, places=3)

    def test_filter_resamples_to_square_pixels(self):
        f = ingest.square_pixels(4 / 3)
        self.assertIn("setsar=1", f)
        self.assertIn("ih*1.333333", f)


if __name__ == "__main__":
    unittest.main()
