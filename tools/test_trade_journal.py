"""Behavior checks for honest daily result publishing; no live records are mutated."""
import argparse
import hashlib
import io
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
    """spans: (start, end, execution[, published text])"""
    return dict(executionSections=[dict(startTime=s[0], endTime=s[1], execution=s[2],
                                        **({'publicNote': s[3]} if len(s) > 3 else {}))
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
        self.assertIsNone(row['executionSections'][1]['publicNote'])
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
        with self.assertRaises(ValueError):      # reviewed after the row was recorded
            normalize(raw(**reviewed(('09:48', '09:52', 'good'), assessed='2026-09-08T09:00:00-04:00')), NOW)

    def test_execution_notes_never_carry_amounts(self):
        for note in ('Paid $420 for that mistake.', 'Gave back 1,200 dollars.', 'Lost 3k on the fade.'):
            with self.subTest(note=note), self.assertRaises(ValueError):
                normalize(raw(**reviewed(('09:48', '09:52', 'misplayed', note))), NOW)
        ok = normalize(raw(**reviewed(('09:48', '09:52', 'misplayed', 'Chased the second push and paid for it.'))), NOW)
        self.assertIn('Chased', ok['executionSections'][0]['publicNote'])

    def test_public_text_refuses_position_detail_and_overlong_notes(self):
        for note in ('Sold 7 contracts into it.', 'Held 12 puts too long.', 'Averaged into 250 shares.',
                     'Bought the 756 call late.', 'Emailed me@example.com about it.', 'x' * 141):
            with self.subTest(note=note), self.assertRaises(ValueError):
                normalize(raw(**reviewed(('09:48', '09:52', 'misplayed', note))), NOW)

    def test_an_ordinary_note_key_is_refused_so_private_text_cannot_arrive_by_habit(self):
        with self.assertRaises(ValueError):
            normalize(raw(executionSections=[dict(startTime='09:48', endTime='09:52', execution='good',
                                                  note='Sized too big on that entry.')],
                          executionAssessedAt=AFTER_CLOSE), NOW)

    def test_malformed_sections_are_refused_not_silently_dropped(self):
        for sections in ([dict(startTime='09:48', endTime='09:52')],          # no class
                         [dict(startTime='09:48', execution='good')],          # no end
                         ['09:48-09:52 good'],                                 # not a mapping
                         [dict(startTime='09:48', endTime='09:52', execution='good', account='X')]):
            with self.subTest(sections=sections), self.assertRaises(ValueError):
                normalize(raw(executionSections=sections, executionAssessedAt=AFTER_CLOSE), NOW)

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
                         [dict(startTime='09:33', endTime='09:37', execution='good', publicNote=None)],
                         [dict(startTime='09:31', endTime='09:34', execution='good', publicNote=None),
                          dict(startTime='09:40', endTime='09:52', execution='misplayed', publicNote=None)],
                         [dict(startTime='09:30', endTime='16:00', execution='sat_out', publicNote=None)]):
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
        runs = line(points, sections=[dict(startTime='09:35', endTime='09:40', execution='good', publicNote=None)])
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


class BuiltArchiveTests(unittest.TestCase):
    """The browser reads a day file, so the day file is what has to be right."""

    RECORDING = b'ID3' + b'\x00' * 64

    def data(self, **changes):
        digest = hashlib.sha256(self.RECORDING).hexdigest()
        value = dict(seriesStartDate='2026-09-01', songDurationSeconds=195,
                     sessions=[dict(date='2026-09-04', closing=dict(
                         title='Close', summary='A day.', durationSeconds=195,
                         audioUrl='https://example.invalid/spy-2026-09-04.mp3', audioSha256=digest))])
        value.update(changes)
        return value, digest

    def staged(self, data, output):
        """Run the two build steps in the order build_website runs them."""
        import build_website
        import website_audio
        replacements = website_audio.stage_audio(data, output)
        for name, text in journal_pages.archive(data, {}).items():
            (output / name).parent.mkdir(parents=True, exist_ok=True)
            (output / name).write_text(text, encoding='utf-8')
        return replacements, list(build_website.check_day_audio(output, replacements))

    def test_a_built_day_payload_serves_the_staged_recording_not_the_release_url(self):
        data, digest = self.data()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            local = output / 'assets' / 'audio' / f'{digest}.mp3'
            local.parent.mkdir(parents=True)
            local.write_bytes(self.RECORDING)        # already staged, so no network
            replacements, checked = self.staged(data, output)
            payload = json.loads((output / 'content' / 'days' / '2026-09-04.json').read_text(encoding='utf-8'))
            self.assertEqual(payload['closing']['audioUrl'], f'/assets/audio/{digest}.mp3')
            self.assertNotIn('example.invalid', json.dumps(payload))
            self.assertEqual(replacements, {'https://example.invalid/spy-2026-09-04.mp3': f'/assets/audio/{digest}.mp3'})
            self.assertEqual(checked, [('2026-09-04.json', True)])

    def test_a_day_payload_left_pointing_off_origin_is_caught(self):
        import build_website
        data, _ = self.data()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for name, text in journal_pages.archive(data, {}).items():   # written without staging
                (output / name).parent.mkdir(parents=True, exist_ok=True)
                (output / name).write_text(text, encoding='utf-8')
            self.assertEqual(list(build_website.check_day_audio(output, {})), [('2026-09-04.json', False)])

    def test_the_index_reaches_back_to_an_entry_older_than_the_declared_start(self):
        data, _ = self.data()
        data['sessions'].append(dict(date='2026-06-03', closing=dict(title='June', summary='Older.')))
        index = json.loads(journal_pages.archive(data, {})['content/journal-index.json'])
        self.assertEqual(index['seriesStartDate'], '2026-06-03')
        self.assertEqual(index['declaredStartDate'], '2026-09-01')
        self.assertEqual(index['months'], ['2026-06', '2026-09'])
        self.assertIn('2026-06-03', [d['date'] for d in index['days']])

    def test_a_chart_only_day_is_indexed_without_promising_a_song(self):
        data, _ = self.data()
        data['sessions'] = [dict(date='2026-06-03', closing=dict(title='June', summary='Older.'),
                                 lineChart=dict(url='/assets/charts/2026-06-03-line.svg'))]
        entry = json.loads(journal_pages.archive(data, {})['content/journal-index.json'])['days'][0]
        self.assertFalse(entry['hasSong'])
        self.assertTrue(entry['hasChart'])
        self.assertFalse(entry['marketClosed'])


class DailyIntakeTests(unittest.TestCase):
    """log_day.py is the after-close entry point; it must never widen the allowlist."""

    def flags(self, **changes):
        args = argparse.Namespace(date='2026-09-04', outcome='profit', setup=None, rated_at=None,
                                  played=[], misplayed=[], sat_out=[], public_note=[],
                                  assessed=AFTER_CLOSE, private_note=[], replace=False, show=False)
        for key, value in changes.items():
            setattr(args, key, value)
        return args

    def both(self, **changes):
        import log_day
        args = self.flags(**changes)
        return log_day.build(args, log_day.spans(args), None, None)

    def build(self, **changes):
        return self.both(**changes)[0]

    def test_flags_become_ordered_sections_with_their_classes(self):
        record = self.build(played=[['09:48', '09:52', 'Took the open cleanly.']],
                            misplayed=[['12:38', '12:48']],
                            sat_out=[['09:30', '09:48', 'Waited for the range.']])
        self.assertEqual([(s['startTime'], s['execution']) for s in record['executionSections']],
                         [('09:30', 'sat_out'), ('09:48', 'good'), ('12:38', 'misplayed')])

    def test_a_stretch_note_stays_private_until_it_is_explicitly_published(self):
        record, private = self.both(played=[['09:48', '09:52', 'Took the open cleanly.']],
                                    misplayed=[['12:38', '12:48', 'Chased the second push.']])
        self.assertNotIn('Took the open cleanly', json.dumps(record))
        self.assertNotIn('Chased the second push', json.dumps(record))
        self.assertNotIn('publicNote', json.dumps(record))
        self.assertEqual([x['note'] for x in private['sections']],
                         ['Took the open cleanly.', 'Chased the second push.'])

    def test_designated_text_is_the_only_text_that_crosses_over(self):
        record, _ = self.both(played=[['09:48', '09:52', 'Took the open cleanly, felt slow after.']],
                              misplayed=[['12:38', '12:48', 'Chased the second push.']],
                              public_note=[['09:48', '09:52', 'Took the open cleanly.']])
        self.assertEqual(record['executionSections'][0]['publicNote'], 'Took the open cleanly.')
        self.assertNotIn('publicNote', record['executionSections'][1])
        self.assertNotIn('felt slow after', json.dumps(record))

    def test_publishing_text_for_a_stretch_that_does_not_exist_is_refused(self):
        with self.assertRaises(SystemExit):
            self.both(played=[['09:48', '09:52']], public_note=[['10:00', '11:00', 'Anything.']])

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


class IntakeOnDiskTests(unittest.TestCase):
    """End to end on temporary roots. No real trade record is read or written."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'site'
        (self.root / 'content').mkdir(parents=True)
        self.ledger = self.root / 'content' / 'trading-journal.json'
        self.ledger.write_text('{"schemaVersion": 2, "days": []}\n', encoding='utf-8')
        self.private_root = Path(tmp.name) / 'private'
        self.private = self.private_root / '2026-09-04' / 'day-review.json'

    def log(self, *extra, outcome='profit', timestamped=True):
        import log_day
        argv = ['--date', '2026-09-04', '--outcome', outcome, '--setup', '9',
                '--played', '09:48', '09:52', 'Took the open cleanly.', *extra]
        if timestamped:
            argv += ['--assessed', AFTER_CLOSE]
        with patch('sys.stdout', new=io.StringIO()):
            return log_day.main(argv, root=self.root, private_root=self.private_root)

    def row(self):
        return json.loads(self.ledger.read_text(encoding='utf-8'))['days'][0]

    def test_the_ledger_gets_the_span_and_the_note_stays_in_the_private_file(self):
        self.log('--private-note', 'Sized too big on that entry.')
        published = self.ledger.read_text(encoding='utf-8')
        self.assertNotIn('Took the open cleanly', published)
        self.assertNotIn('Sized too big', published)
        self.assertEqual(self.row()['executionSections'][0]['execution'], 'good')
        stored = json.loads(self.private.read_text(encoding='utf-8'))
        self.assertEqual(stored['sections'][0]['note'], 'Took the open cleanly.')
        self.assertEqual(stored['privateNotes'], ['Sized too big on that entry.'])

    def test_designated_text_reaches_the_ledger(self):
        self.log('--public-note', '09:48', '09:52', 'Took the open cleanly.')
        self.assertIn('Took the open cleanly', self.ledger.read_text(encoding='utf-8'))

    def test_repeating_the_same_command_keeps_both_files_byte_identical(self):
        self.log('--private-note', 'Sized too big.', timestamped=False)
        public, private = self.ledger.read_bytes(), self.private.read_bytes()
        self.log(timestamped=False)          # same command, default timestamps, note omitted
        self.assertEqual(self.ledger.read_bytes(), public)
        self.assertEqual(self.private.read_bytes(), private)
        self.assertEqual(json.loads(private.decode())['privateNotes'], ['Sized too big.'])

    def test_a_refused_change_leaves_the_private_file_and_the_ledger_untouched(self):
        self.log('--private-note', 'Sized too big.')
        public, private = self.ledger.read_bytes(), self.private.read_bytes()
        with self.assertRaises(ValueError):
            self.log(outcome='loss')
        self.assertEqual(self.ledger.read_bytes(), public)
        self.assertEqual(self.private.read_bytes(), private)

    def test_a_refused_first_run_writes_nothing_at_all(self):
        with self.assertRaises(ValueError):
            self.log('--public-note', '09:48', '09:52', 'Paid $420 for that.')
        self.assertFalse(self.private.exists())
        self.assertEqual(json.loads(self.ledger.read_text(encoding='utf-8'))['days'], [])

    def test_replace_corrects_both_records(self):
        self.log()
        self.log('--replace', outcome='loss')
        self.assertEqual(self.row()['outcome'], 'loss')
        self.assertEqual(json.loads(self.private.read_text(encoding='utf-8'))['outcome'], 'loss')


if __name__ == '__main__': unittest.main()
