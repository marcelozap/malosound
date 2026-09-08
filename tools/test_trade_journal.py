"""Behavior checks for honest daily result publishing; no live records are mutated."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import journal_pages
from record_trading_day import normalize, stage
from trade_journal import EXECUTION, execution_summary, presentation, segments, validate

NOW = '2026-09-07T18:00:00+00:00'
AFTER_CLOSE = '2026-09-04T17:30:00-04:00'


def raw(**changes):
    value = dict(date='2026-09-04', mode='live', final=True, netRealizedPnl='-12.50',
                 feesIncluded=True, tradeCount=2, sourceKind='imported_result')
    value.update(changes)
    return value


def reviewed(*spans, assessed=AFTER_CLOSE):
    """spans: (start, end, execution[, note])"""
    return dict(executionSections=[dict(startTime=s[0], endTime=s[1], execution=s[2],
                                        **({'note': s[3]} if len(s) > 3 else {}))
                                   for s in spans],
                executionAssessedAt=assessed)


def line(points, gap_ends=(), sections=()):
    return segments(points, set(gap_ends), list(sections))


def grid(n=8, start=0):
    """Evenly spaced points one minute apart, like the real minute boundaries."""
    return [dict(minute=start + i, x=float(start + i), y=float(i)) for i in range(n)]


class TradeJournalTests(unittest.TestCase):
    def test_sign_is_own_net_result(self):
        for value, expected in [('12.50', 'profit'), ('-0.01', 'loss'), ('0.00', 'flat')]:
            self.assertEqual(normalize(raw(netRealizedPnl=value), NOW)['outcome'], expected)

    def test_zero_trades_and_missing_are_distinct(self):
        row = normalize(raw(netRealizedPnl='0', tradeCount=0), NOW)
        self.assertEqual(row['outcome'], 'no_trade')
        self.assertEqual(presentation(None)['outcome'], 'unrecorded')
        self.assertIsNone(presentation(None)['setupRating'])
        self.assertEqual(presentation(None)['executionSections'], [])

    def test_rejects_partial_paper_fees_and_inconsistent_sign(self):
        for changes in [dict(mode='paper'), dict(final=False), dict(feesIncluded=False),
                        dict(outcome='profit'), dict(tradeCount=0), dict(tradeCount=True)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize(raw(**changes), NOW)

    def test_rejects_invalid_pnl(self):
        for value in ('NaN', 'Infinity', '-Infinity', 'unknown', None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(raw(netRealizedPnl=value), NOW)

    def test_manual_reports_respect_supplied_flags_and_counts(self):
        base = dict(date='2026-09-04', mode='live', final=True, feesIncluded=True, outcome='profit')
        self.assertEqual(normalize(base, NOW)['outcome'], 'profit')
        for extra in (dict(tradeCount=0), dict(feesIncluded=False), dict(tradeCount=-1), dict(tradeCount=True)):
            with self.subTest(extra=extra), self.assertRaises(ValueError): normalize(dict(base, **extra), NOW)
        with self.assertRaises(ValueError): normalize(dict(base, outcome='no_trade', tradeCount=1), NOW)

    def test_future_completed_results_and_new_york_date(self):
        for day, stamp in [('2026-09-30', NOW), ('2026-09-04', '2026-09-04T02:00:00+00:00')]:
            with self.subTest(day=day, stamp=stamp), self.assertRaises(ValueError): normalize(raw(date=day), stamp)

    def test_rating_bounds_and_real_assessment_time(self):
        for rating in (1, 14):
            row = normalize(raw(setupRating=rating, ratingAsOf='2026-09-04T09:00:00-04:00'), NOW)
            self.assertEqual(row['setupRating'], rating)
        for rating in (0, 15, True, 1.5, '14'):
            with self.subTest(rating=rating), self.assertRaises(ValueError):
                normalize(raw(setupRating=rating, ratingAsOf='2026-09-04T09:00:00-04:00'), NOW)
        for stamp in (None, '2026-09-04T09:00:00', '2026-09-08T09:00:00-04:00'):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                normalize(raw(setupRating=14, ratingAsOf=stamp), NOW)

    def test_public_allowlist_drops_private_fields(self):
        row = normalize(raw(accountNumber='PRIVATE-TEST', fills=[{'private': True}], sourcePath='private.json'), NOW)
        text = json.dumps(row)
        for private in ('PRIVATE-TEST', 'accountNumber', 'fills', 'sourcePath', 'netRealizedPnl', '-12.50'):
            self.assertNotIn(private, text)
        row['accountNumber'] = 'PRIVATE-TEST'
        with self.assertRaises(ValueError):
            validate(dict(schemaVersion=2, days=[row]))

    def test_duplicate_dates_rejected(self):
        row = normalize(raw(), NOW)
        with self.assertRaises(ValueError):
            validate(dict(schemaVersion=2, days=[row, row]))

    def test_retries_preserve_timestamp_and_corrections_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, ledger = Path(tmp)/'private.json', Path(tmp)/'public.json'
            source.write_text(json.dumps(raw()), encoding='utf-8')
            ledger.write_text(json.dumps(dict(schemaVersion=2, days=[])), encoding='utf-8')
            self.assertTrue(stage(source, ledger))
            before = ledger.read_bytes()
            self.assertFalse(stage(source, ledger))
            self.assertEqual(ledger.read_bytes(), before)
            source.write_text(json.dumps(raw(netRealizedPnl='10')), encoding='utf-8')
            with self.assertRaises(ValueError): stage(source, ledger)
            self.assertEqual(ledger.read_bytes(), before)
            self.assertTrue(stage(source, ledger, replace=True))

    # ---------------------------------------------------------------- execution

    def test_execution_sections_are_accepted_and_stay_public_safe(self):
        row = normalize(raw(**reviewed(('09:48', '09:52', 'good', 'Took the open cleanly.'),
                                       ('12:38', '12:48', 'misplayed'))), NOW)
        self.assertEqual([s['execution'] for s in row['executionSections']], ['good', 'misplayed'])
        self.assertIsNone(row['executionSections'][1]['note'])
        self.assertEqual(execution_summary(row['executionSections'])['label'], 'Reviewed · 1 played well, 1 misplayed')

    def test_execution_rejects_bad_spans_classes_and_times(self):
        bad = [
            (('09:48', '09:48', 'good'),),                    # zero length
            (('10:00', '09:50', 'good'),),                    # ends before it starts
            (('09:20', '09:50', 'good'),),                    # before the open
            (('15:50', '16:30', 'good'),),                    # past the close
            (('09:48', '09:52', 'unreviewed'),),              # neutral is a default, not a choice
            (('09:48', '09:52', 'great'),),                   # unknown class
            (('9:48', '09:52', 'good'),),                     # not HH:MM
            (('10:00', '11:00', 'good'), ('10:30', '11:30', 'misplayed')),   # overlap
            (('11:00', '12:00', 'good'), ('10:00', '10:30', 'misplayed')),   # out of order
        ]
        for spans in bad:
            with self.subTest(spans=spans), self.assertRaises(ValueError):
                normalize(raw(**reviewed(*spans)), NOW)

    def test_execution_needs_its_own_assessment_time_after_the_close(self):
        with self.assertRaises(ValueError):      # sections without a time
            normalize(raw(executionSections=[dict(startTime='09:48', endTime='09:52', execution='good')]), NOW)
        with self.assertRaises(ValueError):      # a time without sections
            normalize(raw(executionAssessedAt=AFTER_CLOSE), NOW)
        with self.assertRaises(ValueError):      # reviewed during the session
            normalize(raw(**reviewed(('09:48', '09:52', 'good'), assessed='2026-09-04T11:00:00-04:00')), NOW)

    def test_execution_notes_never_carry_amounts(self):
        for note in ('Paid $420 for that mistake.', 'Gave back 1,200 dollars.', 'Lost 3k on the fade.'):
            with self.subTest(note=note), self.assertRaises(ValueError):
                normalize(raw(**reviewed(('09:48', '09:52', 'misplayed', note))), NOW)
        ok = normalize(raw(**reviewed(('09:48', '09:52', 'misplayed', 'Chased the second push and paid for it.'))), NOW)
        self.assertIn('Chased', ok['executionSections'][0]['note'])

    def test_profit_never_implies_good_execution(self):
        row = normalize(raw(netRealizedPnl='500', **reviewed(('09:48', '09:52', 'misplayed'))), NOW)
        self.assertEqual(row['outcome'], 'profit')
        self.assertEqual(row['executionSections'][0]['execution'], 'misplayed')
        view = presentation(row)
        # The day label keeps its own color; the line takes its colors from execution only.
        self.assertEqual(view['color'], EXECUTION['good'][1])   # profit green as a text label
        self.assertEqual([EXECUTION[r['execution']][1] for r in line(grid(20), sections=view['executionSections'])
                          if r['execution'] != 'unreviewed'], [EXECUTION['misplayed'][1]])

    # ------------------------------------------------------- geometry integrity

    def test_segments_preserve_every_observed_point_in_order(self):
        points = grid(30)
        for sections in ([],
                         [dict(startTime='09:33', endTime='09:37', execution='good', note=None)],
                         [dict(startTime='09:31', endTime='09:34', execution='good', note=None),
                          dict(startTime='09:40', endTime='09:52', execution='misplayed', note=None)],
                         [dict(startTime='09:30', endTime='16:00', execution='sat_out', note=None)]):
            with self.subTest(n=len(sections)):
                runs = line(points, sections=sections)
                rebuilt = []
                for run in runs:
                    for p in run['points']:
                        if not rebuilt or rebuilt[-1] is not p:
                            rebuilt.append(p)
                self.assertEqual(rebuilt, points, 'the drawn line must be the observed line')

    def test_segment_boundaries_land_on_real_minutes_and_are_continuous(self):
        points = grid(20)
        runs = line(points, sections=[dict(startTime='09:35', endTime='09:40', execution='good', note=None)])
        self.assertEqual([r['execution'] for r in runs], ['unreviewed', 'good', 'unreviewed'])
        for before, after in zip(runs, runs[1:]):
            self.assertEqual(before['points'][-1], after['points'][0], 'runs must share their boundary point')
        self.assertEqual(runs[1]['points'][0]['minute'], 5)
        self.assertEqual(runs[1]['points'][-1]['minute'], 10)

    def test_source_gaps_still_break_the_line(self):
        points = [p for p in grid(20) if p['minute'] not in (7, 8)]
        runs = line(points, gap_ends=[9], sections=[])
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]['points'][-1]['minute'], 6)
        self.assertEqual(runs[1]['points'][0]['minute'], 9)
        self.assertNotEqual(runs[0]['points'][-1], runs[1]['points'][0], 'a gap is a real break, not a shared point')

    def test_unreviewed_day_is_entirely_neutral(self):
        runs = line(grid(40), sections=[])
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['execution'], 'unreviewed')
        self.assertEqual(EXECUTION['unreviewed'][1], '#50b8f5')

    # --------------------------------------------------------- rendered output

    def test_market_path_gaps_and_audio_unchanged_across_execution_reviews(self):
        root = journal_pages.ROOT
        editions = json.loads((root/'content/editions.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            (fixture/'content').mkdir()
            (fixture/'content/market-assets.json').write_text('[]', encoding='utf-8')
            for session in editions['sessions']:
                song = session.get('originalSong') or session.get('closing')
                if song and song.get('chart'):
                    relative = song['chart']['dataUrl'].lstrip('/')
                    dest = fixture/relative; dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes((root/relative).read_bytes())
            committed = {}
            for day in ('2026-09-03', '2026-09-04'):
                old = subprocess.check_output(['git', 'show', f'HEAD:assets/charts/{day}-line.svg'], cwd=root).decode()
                committed[day] = [m.group(1) for m in re.finditer(r'<path d="([^"]+)"', old)]
            cases = [
                ('none', {}, ['#50b8f5']),
                ('one_good', reviewed(('10:00', '11:00', 'good')), ['#50b8f5', '#58dfa4', '#50b8f5']),
                ('mixed', reviewed(('09:30', '10:00', 'sat_out'), ('10:00', '11:00', 'misplayed')),
                 ['#e5b657', '#ff7188', '#50b8f5']),
            ]
            for name, review, expected in cases:
                with self.subTest(case=name):
                    rows = [dict(date=s['date'], outcome='profit', setupRating=14,
                                 ratingAsOf='2026-09-03T09:00:00-04:00', recordedAt=NOW,
                                 sourceKind='user_reported',
                                 executionSections=review.get('executionSections'),
                                 executionAssessedAt=(f"{s['date']}T17:30:00-04:00" if review else None))
                            for s in editions['sessions']]
                    (fixture/'content/trading-journal.json').write_text(json.dumps(dict(schemaVersion=2, days=rows)), encoding='utf-8')
                    (fixture/'content/editions.json').write_text(json.dumps(editions), encoding='utf-8')
                    with patch.object(journal_pages, 'ROOT', fixture): journal_pages.refresh()
                    for day, original in committed.items():
                        svg = (fixture/f'assets/charts/{day}-line.svg').read_text(encoding='utf-8')
                        drawn = [m.group(1) for m in re.finditer(r'<path d="([^"]+)"', svg)]
                        # The union of the colored runs is the committed shape, coordinate for coordinate.
                        rebuilt, previous = [], None
                        for d in drawn:
                            for token in d.replace('M', ' ').replace('L', ' ').split():
                                if token != previous:
                                    rebuilt.append(token)
                                previous = token
                        flat = []
                        for d in original:
                            flat += d.replace('M', ' ').replace('L', ' ').split()
                        self.assertEqual(rebuilt, flat, f'{day} price path changed')
                        strokes = [m.group(1) for m in re.finditer(r'stroke="(#[0-9a-f]{6})"', svg)]
                        # Collapse repeats: a source gap splits a run without changing its color.
                        transitions = [c for i, c in enumerate(strokes) if i == 0 or c != strokes[i-1]]
                        self.assertEqual(transitions, expected)
                        # 2026-09-03 carries one real gap, so it must draw exactly one more
                        # path than the same review produces on the gapless 2026-09-04.
                        self.assertEqual(len(strokes), len(expected) + (1 if day == '2026-09-03' else 0),
                                         f'{day} run count should reflect its source gaps')
                        # Music timing and the playhead map never move with an execution review.
                        self.assertEqual(json.loads((fixture/f'assets/charts/{day}-timeline.json').read_text()),
                                         json.loads((root/f'assets/charts/{day}-timeline.json').read_text()))
                        report = (fixture/f'reports/{day}-spy-song.html').read_text(encoding='utf-8')
                        self.assertIn('data-trade-result="profit"', report)
                        self.assertEqual(report.count('<i class='), 14)
                        self.assertIn('exec-legend', report)
                    updated = json.loads((fixture/'content/editions.json').read_text(encoding='utf-8'))
                    for old, new in zip(editions['sessions'], updated['sessions']):
                        for key in ('morning', 'preOpen', 'closing', 'originalSong'):
                            self.assertEqual(old.get(key), new.get(key))


class DailyIntakeTests(unittest.TestCase):
    """log_day.py is the after-close entry point; it must never widen the allowlist."""

    def build(self, **changes):
        import log_day
        args = argparse.Namespace(date='2026-09-04', outcome='profit', setup=None, rated_at=None,
                                  played=[], misplayed=[], sat_out=[], assessed=AFTER_CLOSE,
                                  private_note=[], replace=False, show=False)
        for key, value in changes.items():
            setattr(args, key, value)
        return log_day.build(args)

    def test_flags_become_ordered_sections_with_their_classes(self):
        record = self.build(played=[['09:48', '09:52', 'Took the open cleanly.']],
                            misplayed=[['12:38', '12:48']],
                            sat_out=[['09:30', '09:48', 'Waited for the range.']])
        self.assertEqual([(s['startTime'], s['execution']) for s in record['executionSections']],
                         [('09:30', 'sat_out'), ('09:48', 'good'), ('12:38', 'misplayed')])
        self.assertEqual(record['executionSections'][0]['note'], 'Waited for the range.')
        # 12:38 was given no note, so no note key is invented for it.
        self.assertNotIn('note', record['executionSections'][2])

    def test_a_day_with_no_named_stretches_carries_no_review(self):
        record = self.build()
        self.assertIsNone(record['executionSections'])
        self.assertIsNone(record['executionAssessedAt'])
        self.assertEqual(presentation(normalize(record, NOW))['execution']['label'], 'Execution not reviewed')

    def test_review_before_the_close_is_refused(self):
        with self.assertRaises(SystemExit):
            self.build(played=[['10:00', '11:00']], assessed='2026-09-04T11:30:00-04:00')

    def test_private_notes_never_reach_the_public_row(self):
        record = self.build(played=[['09:48', '09:52']])
        row = normalize(dict(record, privateNotes=['Sized too big.'], netRealizedPnl='420.00',
                             tradeCount=3, accountNumber='PRIVATE-TEST'), NOW)
        text = json.dumps(row)
        for private in ('privateNotes', 'Sized too big', 'PRIVATE-TEST', 'accountNumber', '420.00'):
            self.assertNotIn(private, text)

    def test_setup_rating_stays_independent_of_execution(self):
        record = self.build(setup=14, misplayed=[['09:48', '09:52']])
        row = normalize(record, NOW)
        self.assertEqual(row['setupRating'], 14)
        self.assertEqual(row['executionSections'][0]['execution'], 'misplayed')


if __name__ == '__main__': unittest.main()
