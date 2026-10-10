"""Every HLS ladder the ingest makes carries audio. Roku's player never starts a stream
without an audio track (verified 2026-10-10 on a Streaming Stick: 32 silent films sat in
"buffering" at position 0 until scripts/add_silent_audio.py gave them a silent track), so a
source with no usable audio gets silent AAC instead of a video-only ladder."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ingest", ROOT / "scripts/ingest_free_titles.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)

RUNGS = [(720, 2800), (480, 1400), (360, 800)]


def cmd(real_audio):
    out = pathlib.Path("/tmp/x")
    return ingest.ladder_cmd(pathlib.Path("/tmp/src.mp4"), out, RUNGS, 0.0, 60.0, 4 / 3, real_audio)


class LadderAudio(unittest.TestCase):
    def test_every_rung_maps_audio(self):
        for real in (True, False):
            c = cmd(real)
            maps = [c[i + 1] for i, a in enumerate(c) if a == "-map"]
            audio_maps = [m for m in maps if m.endswith(":a:0")]
            self.assertEqual(len(audio_maps), len(RUNGS), f"real_audio={real}: {maps}")
            vsm = c[c.index("-var_stream_map") + 1].split()
            self.assertEqual(vsm, [f"v:{i},a:{i}" for i in range(len(RUNGS))], f"real_audio={real}")

    def test_silent_source_gets_generated_silence(self):
        c = cmd(False)
        self.assertIn("anullsrc=channel_layout=stereo:sample_rate=48000", c)
        self.assertIn("-shortest", c)  # anullsrc never ends
        self.assertNotIn("0:a:0", c)   # nothing read from the (silent) source's audio

    def test_real_audio_source_is_not_padded(self):
        c = cmd(True)
        self.assertNotIn("anullsrc=channel_layout=stereo:sample_rate=48000", c)
        self.assertIn("0:a:0", c)


class SilentAudioTool(unittest.TestCase):
    def test_master_rewrite_adds_audio_codec_and_bitrate(self):
        spec2 = importlib.util.spec_from_file_location("silent", ROOT / "scripts/add_silent_audio.py")
        silent = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(silent)
        master = ('#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-STREAM-INF:BANDWIDTH=1000000,AVERAGE-BANDWIDTH=900000,'
                  'RESOLUTION=640x480,CODECS="avc1.64001e"\nv0/index.m3u8\n')
        self.assertTrue(silent.video_only(master))
        fixed = silent.with_audio_master(master)
        self.assertIn('CODECS="avc1.64001e,mp4a.40.2"', fixed)
        self.assertIn("BANDWIDTH=1064000,AVERAGE-BANDWIDTH=964000", fixed)
        self.assertFalse(silent.video_only(fixed))


if __name__ == "__main__":
    unittest.main()
