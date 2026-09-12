"""The instrument mapping is fixed, so these tests pin its arithmetic and its refusals."""
import json
import unittest

import instrument_session as inst


def history(closes, key='bars', start=0, skip=(), date='2026-01-02'):
    rows = [dict(minute=start + i, close=c) for i, c in enumerate(closes) if (start + i) not in skip]
    return {'date': date, 'symbol': 'SPY', 'sourceSha256': 'abc', key: rows}


class Smoothing(unittest.TestCase):
    def test_cubic_fit_recovers_a_quadratic_exactly(self):
        # A cubic fit is exact for any polynomial of degree three or less, so a
        # quadratic price path must return its true slope and curvature.
        a, b, c = 500.0, 0.3, -0.002
        closes = [a + b * t + c * t * t for t in range(60)]
        doc = inst.analyse(history(closes))
        for p in doc['runs'][0]['points']:
            t = p['minute']
            self.assertAlmostEqual(p['smoothed'], a + b * t + c * t * t, places=6)
            self.assertAlmostEqual(p['velocity'], b + 2 * c * t, places=6)
            self.assertAlmostEqual(p['acceleration'], 2 * c, places=6)

    def test_five_observations_are_lost_at_each_edge(self):
        doc = inst.analyse(history([100 + (i % 7) for i in range(390)]))
        run = doc['runs'][0]
        self.assertEqual(len(run['points']), 380)
        self.assertEqual((run['derivedFrom'], run['derivedTo']), (5, 384))
        self.assertEqual(doc['source']['missingMinutes'], [])
        self.assertEqual(doc['derivedObservations'], 380)

    def test_a_missing_minute_ends_the_run_and_is_never_bridged(self):
        doc = inst.analyse(history([100 + (i % 5) * 0.5 for i in range(390)], skip={264}))
        self.assertEqual(doc['source']['missingMinutes'], [264])
        self.assertEqual([(r['startMinute'], r['endMinute']) for r in doc['runs']], [(0, 263), (265, 389)])
        first, second = doc['runs']
        self.assertEqual(first['points'][-1]['minute'], 258)
        self.assertEqual(second['points'][0]['minute'], 270)
        self.assertEqual(len(first['points']) + len(second['points']), 254 + 115)

    def test_a_run_shorter_than_the_window_derives_nothing(self):
        doc = inst.analyse(history([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        self.assertEqual(doc['runs'][0]['points'], [])
        self.assertIn('shorter', doc['runs'][0]['note'])
        self.assertEqual(doc['derivedObservations'], 0)


class Mapping(unittest.TestCase):
    def test_flat_window_is_the_tonic_and_a_stationary_orbit(self):
        doc = inst.analyse(history([612.5] * 40))
        self.assertTrue(doc['flat'])
        points = doc['runs'][0]['points']
        self.assertTrue(all(p['landmark'] == 0 and p['note'] == 'A' for p in points))
        self.assertTrue(all(p['velocity'] == 0.0 and p['acceleration'] == 0.0 for p in points))
        self.assertEqual(len(doc['noteEvents']), 1)
        self.assertEqual(doc['bounds'], dict(maxAbsVelocity=0.0, maxAbsAcceleration=0.0))

    def test_anchors_are_the_parent_five_minute_closes_not_the_open(self):
        closes = [110.0] + [100.0 + i for i in range(30)]   # open 110; minute m>=1 closes at 99+m
        doc = inst.analyse(history(closes))
        anchors = doc['method']['anchors']
        # Five-minute closes fall at minutes 4, 9, ..., 29: 103 .. 128.
        self.assertEqual((anchors['low'], anchors['high']), (103.0, 128.0))
        self.assertTrue(anchors['frozen'] and not anchors['sessionOpenIsAnchor'])
        self.assertIn('parent window', anchors['source'])

    def test_the_session_is_normalised_against_a_wider_parent(self):
        session = history([100.0 + (i % 30) for i in range(390)], date='2026-01-02')
        wide = history([50.0 + (i % 200) for i in range(390)], date='2025-12-31')
        alone = inst.analyse(session)
        nested = inst.analyse(session, parent={'2025-12-31': wide, '2026-01-02': session})
        self.assertEqual(nested['method']['anchors']['low'], min(c for _, c in inst.parent_observations(wide)))
        self.assertLess(max(p['position'] for r in nested['runs'] for p in r['points']), 0.5)
        self.assertGreater(max(p['landmark'] for r in alone['runs'] for p in r['points']),
                           max(p['landmark'] for r in nested['runs'] for p in r['points']))
        # The orbit does not depend on the anchors, only the notes and colours do.
        self.assertEqual([p['velocity'] for r in alone['runs'] for p in r['points']],
                         [p['velocity'] for r in nested['runs'] for p in r['points']])

    def test_nearest_landmark_and_midpoint_ties_go_up(self):
        self.assertEqual(inst.quantize(0.0), 0)
        self.assertEqual(inst.quantize(1.0), 7)
        self.assertEqual(inst.quantize(0.25), 1)
        self.assertEqual(inst.quantize(0.5), 3)
        self.assertEqual(inst.quantize((0.236 + 0.382) / 2), 2)
        self.assertEqual(inst.quantize((0.886 + 1.0) / 2), 7)
        self.assertEqual(inst.quantize((0.0 + 0.236) / 2), 1)

    def test_position_is_clamped_inside_the_anchors(self):
        self.assertEqual(inst.normalise(99.0, 100.0, 110.0), 0.0)
        self.assertEqual(inst.normalise(111.0, 100.0, 110.0), 1.0)
        self.assertAlmostEqual(inst.normalise(105.0, 100.0, 110.0), 0.5)

    def test_hue_is_thirty_degrees_per_semitone_and_both_a_share_zero(self):
        self.assertEqual([inst.hue_of(i) for i in range(8)], [0, 60, 90, 150, 210, 240, 300, 0])
        self.assertEqual(inst.NOTES[0], inst.NOTES[7])
        self.assertEqual(len(inst.LANDMARKS), 8)

    def test_note_events_hold_while_the_landmark_holds(self):
        closes = [100.0] * 20 + [200.0] * 20
        doc = inst.analyse(history(closes))
        events = doc['noteEvents']
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0]['landmark'], 0)
        self.assertEqual(events[-1]['landmark'], 7)
        self.assertEqual(sum(e['minutes'] for e in events), doc['derivedObservations'])
        for earlier, later in zip(events, events[1:]):
            self.assertEqual(later['startMinute'], earlier['endMinute'] + 1)
            self.assertNotEqual(earlier['landmark'], later['landmark'])


class Parent(unittest.TestCase):
    def test_trailing_five_sessions_skip_weekends_and_labor_day(self):
        self.assertEqual(inst.sessions_ending('2026-09-08'),
                         ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-08'])
        self.assertEqual(inst.sessions_ending('2026-08-31'),
                         ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28', '2026-08-31'])
        with self.assertRaises(ValueError):
            inst.sessions_ending('2026-09-07')

    def test_five_minute_closes_are_block_closes(self):
        obs = inst.parent_observations(history([float(i) for i in range(390)]))
        self.assertEqual(len(obs), 78)
        self.assertEqual(obs[0], (4, 4.0))
        self.assertEqual(obs[-1], (389, 389.0))
        self.assertTrue(all(m % 5 == 4 for m, _ in obs))

    def test_a_missing_block_close_breaks_the_parent_run(self):
        doc = inst.analyse(history([100 + (i % 9) * 0.5 for i in range(390)], skip={264}))
        day_runs = doc['parent']['runs']
        self.assertEqual([(r['startMinute'], r['endMinute']) for r in day_runs], [(4, 259), (269, 389)])
        self.assertEqual(doc['parent']['sessionDay']['derivedObservations'], (52 - 10) + (25 - 10))

    def test_each_session_is_its_own_run_and_overnight_is_never_bridged(self):
        a = history([100 + (i % 11) for i in range(390)], date='2025-12-31')
        b = history([100 + (i % 13) for i in range(390)], date='2026-01-02')
        doc = inst.analyse(b, parent={'2025-12-31': a, '2026-01-02': b})
        runs = doc['parent']['runs']
        self.assertEqual([r['date'] for r in runs], ['2025-12-31', '2026-01-02'])
        self.assertTrue(all(r['derivedFrom'] == 29 and r['derivedTo'] == 364 for r in runs))
        self.assertEqual(doc['parent']['derivedObservations'], 2 * 68)

    def test_missing_sessions_are_recorded_not_invented(self):
        b = history([100 + (i % 13) for i in range(390)], date='2026-01-02')
        doc = inst.analyse(b, parent={'2025-12-29': None, '2025-12-30': None, '2025-12-31': None, '2026-01-01': None, '2026-01-02': b})
        self.assertEqual(doc['parent']['observedSessions'], ['2026-01-02'])
        self.assertEqual(doc['parent']['missingSessions'], ['2025-12-29', '2025-12-30', '2025-12-31', '2026-01-01'])
        self.assertEqual(doc['method']['anchors']['low'], min(c for _, c in inst.parent_observations(b)))

    def test_parent_note_events_span_whole_five_minute_blocks(self):
        doc = inst.analyse(history([100.0] * 200 + [200.0] * 190))
        events = doc['parent']['sessionDay']['noteEvents']
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(sum(e['minutes'] for e in events), 5 * doc['parent']['sessionDay']['derivedObservations'])
        for e in events:
            self.assertEqual(e['startMinute'] % 5, 0)
            self.assertEqual(e['endMinute'] % 5, 4)
            self.assertEqual(e['minutes'], e['endMinute'] - e['startMinute'] + 1)
        self.assertEqual(events[0]['startMinute'], 25)
        self.assertEqual(events[-1]['endMinute'], 364)

    def test_the_parent_must_end_with_the_session(self):
        b = history([100 + (i % 13) for i in range(390)], date='2026-01-02')
        with self.assertRaises(ValueError):
            inst.analyse(b, parent={'2025-12-31': b})


class Palette(unittest.TestCase):
    def test_eight_entries_seven_colours_both_a_identical(self):
        palette = inst.palette()
        self.assertEqual([p['note'] for p in palette], list(inst.NOTES))
        self.assertEqual(palette[0]['srgbFallback'], palette[7]['srgbFallback'])
        self.assertEqual(len({p['srgbFallback'] for p in palette}), 7)
        for p in palette:
            self.assertRegex(p['srgbFallback'], r'^#[0-9a-f]{6}$')
            self.assertEqual(p['oklch'], f"oklch({inst.OKLCH_LIGHTNESS} {inst.OKLCH_CHROMA} {p['hue']})")

    def test_fallback_hues_point_the_right_way(self):
        def rgb(hex_colour):
            return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        by_hue = {p['hue']: rgb(p['srgbFallback']) for p in inst.palette()}
        r, g, b = by_hue[0]
        self.assertTrue(r > g and r > b)          # A: red-pink
        r, g, b = by_hue[150]
        self.assertTrue(g > r and g > b)          # D: green
        r, g, b = by_hue[240]
        self.assertTrue(b > r and b > g)          # F: blue

    def test_document_carries_the_palette(self):
        doc = inst.analyse(history([100 + i * 0.1 for i in range(30)]))
        self.assertEqual(doc['method']['colour']['palette'], inst.palette())


class Sources(unittest.TestCase):
    def test_both_history_schemas_derive_the_same_points(self):
        closes = [100 + ((i * 7) % 13) * 0.25 for i in range(60)]
        a = inst.analyse(history(closes, key='bars'))
        b = inst.analyse({'date': '2026-01-02', 'symbol': 'SPY', 'source_sha256': 'abc',
                          'minutes': [dict(minute=i, close=c, volume=1) for i, c in enumerate(closes)]})
        self.assertEqual(a['runs'], b['runs'])
        self.assertEqual(b['source']['sha256'], 'abc')

    def test_output_is_deterministic(self):
        closes = [100 + ((i * 3) % 11) for i in range(50)]
        self.assertEqual(inst.render_json(inst.analyse(history(closes))), inst.render_json(inst.analyse(history(closes))))

    def test_no_observations_is_refused(self):
        with self.assertRaises(ValueError):
            inst.analyse({'date': '2026-01-02', 'bars': []})

    def test_document_names_its_method_constants(self):
        doc = inst.analyse(history([100 + i * 0.1 for i in range(30)]))
        method = doc['method']
        self.assertEqual(doc['schemaVersion'], 2)
        self.assertEqual(method['smoothing']['window'], 11)
        self.assertEqual(method['smoothing']['degree'], 3)
        self.assertEqual(method['smoothing']['edgeLossEachSide'], 5)
        self.assertEqual(method['landmarks'], [0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1])
        self.assertEqual(method['semitones'], [0, 2, 3, 5, 7, 8, 10, 12])
        self.assertEqual(method['colour']['model'], 'oklch')
        self.assertEqual(doc['parent']['samplingMinutes'], 5)
        self.assertEqual(doc['parent']['observationsPerSession'], 78)
        self.assertEqual(doc['parent']['smoothing']['spacingMinutes'], 5)
        json.dumps(doc)


if __name__ == '__main__':
    unittest.main()
