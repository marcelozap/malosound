"""The session stem is fixed and deterministic, so these tests pin its clock, pitch and silences."""
import unittest

import numpy as np

import instrument_audio as audio
import instrument_session as inst


def document(closes, skip=()):
    rows = [dict(minute=i, close=c) for i, c in enumerate(closes) if i not in skip]
    return inst.analyse({'date': '2026-01-02', 'symbol': 'SPY', 'sourceSha256': 'abc', 'bars': rows})


def dominant_hz(samples):
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return np.fft.rfftfreq(len(samples), 1 / audio.SR)[int(np.argmax(spectrum))]


class Clock(unittest.TestCase):
    def test_a_full_session_is_exactly_195_seconds(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)]))
        self.assertEqual(len(mono), round(195.0 * audio.SR))

    def test_edge_loss_is_silent_at_both_ends(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)]))
        edge = round(5 * audio.SECONDS_PER_OBSERVATION * audio.SR)
        self.assertTrue(np.all(mono[:edge] == 0))
        self.assertTrue(np.all(mono[-edge:] == 0))
        self.assertTrue(np.any(mono[edge:-edge] != 0))

    def test_a_missing_minute_is_silent_together_with_its_edge_loss(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)], skip={264}))
        # Run one derives through minute 258, run two from minute 270, so
        # minutes 259..269 carry nothing: 11 observations, 5.5 seconds.
        start = round(259 * audio.SECONDS_PER_OBSERVATION * audio.SR)
        end = round(270 * audio.SECONDS_PER_OBSERVATION * audio.SR)
        self.assertTrue(np.all(mono[start:end] == 0))
        self.assertTrue(np.any(mono[start - audio.SR:start] != 0))
        self.assertTrue(np.any(mono[end:end + audio.SR] != 0))


class Pitch(unittest.TestCase):
    def test_a_flat_window_sounds_the_tonic_at_220_hz(self):
        mono = audio.render(document([612.5] * 60))
        voiced = mono[round(5 * audio.SECONDS_PER_OBSERVATION * audio.SR):round(55 * audio.SECONDS_PER_OBSERVATION * audio.SR)]
        self.assertAlmostEqual(dominant_hz(voiced), audio.A_HZ, delta=2.0)

    def test_the_high_landmark_sounds_one_octave_up(self):
        closes = [100.0] * 30 + [200.0] * 30
        doc = document(closes)
        last = doc['noteEvents'][-1]
        self.assertEqual(last['semitone'], 12)
        mono = audio.render(doc)
        start = round(last['startMinute'] * audio.SECONDS_PER_OBSERVATION * audio.SR)
        end = round((last['endMinute'] + 1) * audio.SECONDS_PER_OBSERVATION * audio.SR)
        self.assertAlmostEqual(dominant_hz(mono[start:end]), 2 * audio.A_HZ, delta=4.0)

    def test_semitone_to_frequency(self):
        self.assertAlmostEqual(audio.pitch_hz(0), 220.0)
        self.assertAlmostEqual(audio.pitch_hz(12), 440.0)
        self.assertAlmostEqual(audio.pitch_hz(7), 220.0 * 2 ** (7 / 12))


class Level(unittest.TestCase):
    def test_peak_is_minus_one_dbfs_and_nothing_clips(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)]))
        self.assertAlmostEqual(float(np.max(np.abs(mono))), audio.TARGET_PEAK, places=5)
        self.assertEqual(int(np.count_nonzero(np.abs(mono) >= 1.0)), 0)
        self.assertTrue(np.all(np.isfinite(mono)))

    def test_silence_stays_silent_without_dividing_by_zero(self):
        doc = document([1, 2, 3, 4, 5, 6, 7, 8])   # shorter than the window: nothing derived
        mono = audio.render(doc)
        self.assertEqual(len(mono), round(8 * audio.SECONDS_PER_OBSERVATION * audio.SR))
        self.assertTrue(np.all(mono == 0))

    def test_same_document_same_samples(self):
        doc = document([100 + ((i * 7) % 13) * 0.5 for i in range(120)])
        self.assertTrue(np.array_equal(audio.render(doc), audio.render(doc)))


if __name__ == '__main__':
    unittest.main()
