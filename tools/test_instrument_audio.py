"""The two stems are fixed and deterministic, so these tests pin their clock, pitch, silences and mix."""
import unittest

import numpy as np

import instrument_audio as audio
import instrument_session as inst


def document(closes, skip=(), parent=None):
    rows = [dict(minute=i, close=c) for i, c in enumerate(closes) if i not in skip]
    return inst.analyse({'date': '2026-01-02', 'symbol': 'SPY', 'sourceSha256': 'abc', 'bars': rows}, parent=parent)


def dominant_hz(samples):
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return np.fft.rfftfreq(len(samples), 1 / audio.SR)[int(np.argmax(spectrum))]


def seconds(minutes):
    return round(minutes * audio.SECONDS_PER_OBSERVATION * audio.SR)


class Clock(unittest.TestCase):
    def test_a_full_session_is_exactly_195_seconds_in_both_stems(self):
        stems = audio.render_stems(document([100 + (i % 9) * 0.25 for i in range(390)]))
        self.assertEqual(len(stems['session']), round(195.0 * audio.SR))
        self.assertEqual(len(stems['parent']), round(195.0 * audio.SR))

    def test_session_edge_loss_is_silent_at_both_ends(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)]), 'session')
        self.assertTrue(np.all(mono[:seconds(5)] == 0))
        self.assertTrue(np.all(mono[-seconds(5):] == 0))
        self.assertTrue(np.any(mono[seconds(5):-seconds(5)] != 0))

    def test_parent_edge_loss_is_twenty_five_minutes_at_both_ends(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)]), 'parent')
        self.assertTrue(np.all(mono[:seconds(25)] == 0))
        self.assertTrue(np.all(mono[-seconds(25):] == 0))
        self.assertTrue(np.any(mono[seconds(25):seconds(30)] != 0))

    def test_a_missing_minute_is_silent_together_with_its_edge_loss(self):
        mono = audio.render(document([100 + (i % 9) * 0.25 for i in range(390)], skip={264}), 'session')
        # Run one derives through minute 258, run two from minute 270, so
        # minutes 259..269 carry nothing: 11 observations, 5.5 seconds.
        self.assertTrue(np.all(mono[seconds(259):seconds(270)] == 0))
        self.assertTrue(np.any(mono[seconds(259) - audio.SR:seconds(259)] != 0))
        self.assertTrue(np.any(mono[seconds(270):seconds(270) + audio.SR] != 0))

    def test_parent_notes_start_on_five_minute_blocks(self):
        doc = document([100.0] * 200 + [200.0] * 190)
        for event in doc['parent']['sessionDay']['noteEvents']:
            self.assertEqual((event['startMinute'] * audio.SECONDS_PER_OBSERVATION) % 2.5, 0)


class Pitch(unittest.TestCase):
    def test_a_flat_window_sounds_the_tonic_at_220_and_110_hz(self):
        doc = document([612.5] * 100)
        session = audio.render(doc, 'session')[seconds(5):seconds(95)]
        parent = audio.render(doc, 'parent')[seconds(25):seconds(75)]
        self.assertAlmostEqual(dominant_hz(session), audio.A_HZ, delta=2.0)
        self.assertAlmostEqual(dominant_hz(parent), audio.A_HZ * audio.PARENT_OCTAVE, delta=2.0)

    def test_the_high_landmark_sounds_one_octave_up(self):
        doc = document([100.0] * 30 + [200.0] * 30)
        last = doc['noteEvents'][-1]
        self.assertEqual(last['semitone'], 12)
        mono = audio.render(doc, 'session')
        self.assertAlmostEqual(dominant_hz(mono[seconds(last['startMinute']):seconds(last['endMinute'] + 1)]), 2 * audio.A_HZ, delta=4.0)

    def test_semitone_to_frequency(self):
        self.assertAlmostEqual(audio.pitch_hz(0), 220.0)
        self.assertAlmostEqual(audio.pitch_hz(12), 440.0)
        self.assertAlmostEqual(audio.pitch_hz(7), 220.0 * 2 ** (7 / 12))
        self.assertAlmostEqual(audio.pitch_hz(0, audio.A_HZ * audio.PARENT_OCTAVE), 110.0)


class Mix(unittest.TestCase):
    def test_the_two_stem_sum_peaks_at_minus_one_dbfs_and_nothing_clips(self):
        stems = audio.render_stems(document([100 + (i % 9) * 0.25 for i in range(390)]))
        mix = stems['session'] + stems['parent']
        self.assertAlmostEqual(float(np.max(np.abs(mix))), audio.TARGET_PEAK, places=5)
        for mono in stems.values():
            self.assertEqual(int(np.count_nonzero(np.abs(mono) >= 1.0)), 0)
            self.assertTrue(np.all(np.isfinite(mono)))
            self.assertLessEqual(float(np.max(np.abs(mono))), audio.TARGET_PEAK + 1e-6)

    def test_silence_stays_silent_without_dividing_by_zero(self):
        doc = document([1, 2, 3, 4, 5, 6, 7, 8])   # shorter than the window: nothing derived
        stems = audio.render_stems(doc)
        self.assertEqual(len(stems['session']), seconds(8))
        self.assertTrue(np.all(stems['session'] == 0))
        self.assertTrue(np.all(stems['parent'] == 0))

    def test_same_document_same_samples(self):
        doc = document([100 + ((i * 7) % 13) * 0.5 for i in range(120)])
        a, b = audio.render_stems(doc), audio.render_stems(doc)
        self.assertTrue(np.array_equal(a['session'], b['session']))
        self.assertTrue(np.array_equal(a['parent'], b['parent']))


if __name__ == '__main__':
    unittest.main()
