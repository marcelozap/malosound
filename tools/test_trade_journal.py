"""Behavior checks for honest daily result publishing; no live records are mutated."""
import argparse
import datetime
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
import trade_journal
import reconcile_xiv_archive
import verify_published_charts
import session_chart
import trade_overlays
import derive_trade_sections
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

    def test_market_path_gaps_and_audio_unchanged_across_trade_overlays(self):
        """A trade overlay may move colour and nothing else.

        The day line is coloured by trade outcome, not by execution review:
        gold profit, blue loss, grey everywhere else. Execution quality is a
        separate axis and deliberately does not touch this line, so that gold
        can mean exactly one thing.
        """
        root = journal_pages.ROOT
        editions = json.loads((root/'content/editions.json').read_text(encoding='utf-8'))
        GREY, GOLD, BLUE = '#81929e', '#e5b657', '#50b8f5'

        def trade(start, end, outcome):
            return dict(startTime=start, endTime=end, outcome=outcome,
                        underlying='SPY', sourceKind='imported_result')

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
            cases = [
                ('none', None, {GREY}),
                ('one_profit', [trade('10:00', '11:00', 'profit')], {GREY, GOLD}),
                ('profit_and_loss', [trade('10:00', '11:00', 'profit'),
                                     trade('13:00', '13:30', 'loss')], {GREY, GOLD, BLUE}),
            ]
            # The invariant is compared between the cases themselves rather than
            # against a committed drawing. An overlay must move colour and nothing
            # else, and stating it that way means the test does not have to be
            # regenerated every time the drawing legitimately changes shape.
            geometry, run_counts = {}, {}
            for name, sections, expected_colours in cases:
                with self.subTest(case=name):
                    # Each row records its own session after that session's close.
                    # A single fixed timestamp went stale the moment the archive
                    # was extended past it, because a result cannot be recorded
                    # before the day it describes.
                    rows = [dict(date=s['date'], outcome='profit', setupRating=14,
                                 ratingAsOf=f"{s['date']}T09:00:00-04:00",
                                 recordedAt=f"{s['date']}T18:00:00-04:00",
                                 sourceKind='user_reported',
                                 executionSections=None, executionAssessedAt=None,
                                 **({'tradeSections': sections} if sections else {}))
                            for s in editions['sessions']]
                    (fixture/'content/trading-journal.json').write_text(json.dumps(dict(schemaVersion=2, days=rows)), encoding='utf-8')
                    (fixture/'content/editions.json').write_text(json.dumps(editions), encoding='utf-8')
                    with patch.object(journal_pages, 'ROOT', fixture): journal_pages.refresh()
                    for day in ('2026-09-03', '2026-09-04'):
                        svg = (fixture/f'assets/charts/{day}-line.svg').read_text(encoding='utf-8')
                        # Distinct drawn geometry. A clipped overlay repeats the
                        # base path verbatim, so the set of shapes must not grow.
                        shapes = sorted(set(re.findall(r'<path d="([^"]+)"', svg)))
                        self.assertTrue(shapes, f'{day} drew no line')
                        geometry.setdefault(day, {})[name] = shapes
                        if name == 'none':
                            run_counts[day] = len(shapes)
                        self.assertEqual(set(re.findall(r'stroke="(#[0-9a-f]{6})"', svg)), expected_colours,
                                         f'{day} colour did not follow the trade outcomes')
                        # Music timing and the playhead map never move with an
                        # overlay. The timeline may gain a tradeSections key so
                        # playback can mark the window, but every geometry and
                        # timing field must stay exactly where it was.
                        built = json.loads((fixture/f'assets/charts/{day}-timeline.json').read_text())
                        committed = json.loads((root/f'assets/charts/{day}-timeline.json').read_text())
                        self.assertEqual({k: v for k, v in built.items() if k != 'tradeSections'},
                                         {k: v for k, v in committed.items() if k != 'tradeSections'},
                                         f'{day} playback geometry moved with the overlay')
                        self.assertEqual(built.get('tradeSections', []), sections or [],
                                         f'{day} timeline did not carry the supplied trades')
            for day, by_case in geometry.items():
                shapes = list(by_case.values())
                for other in shapes[1:]:
                    self.assertEqual(shapes[0], other, f'{day} geometry moved when the overlay changed')
            # 2026-09-03 carries one real source gap, so it draws one more
            # separate run than the gapless 2026-09-04. The hole is left open —
            # the line breaks there, never bridged.
            self.assertEqual(run_counts['2026-09-03'], run_counts['2026-09-04'] + 1)
class ChartOnlySourceTests(unittest.TestCase):
    def test_source_without_music_builds_a_day_and_preserves_gaps(self):
        root = journal_pages.ROOT
        editions = json.loads((root/'content/editions.json').read_text(encoding='utf-8'))
        session = next(s for s in editions['sessions'] if s['date'] == '2026-09-03')
        song = session.get('originalSong') or session['closing']
        source_path = song['chart']['dataUrl'].lstrip('/')
        source = json.loads((root/source_path).read_text(encoding='utf-8'))
        source.pop('duration_seconds', None)
        source.pop('sections', None)
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            (fixture/'content').mkdir()
            (fixture/source_path).parent.mkdir(parents=True, exist_ok=True)
            (fixture/source_path).write_text(json.dumps(source), encoding='utf-8')
            for name, value in {
                'market-assets': [],
                'trading-journal': {'schemaVersion': 2, 'days': []},
                'editions': {'sessions': [{'date': session['date'], 'closing': {
                    'title': 'Historical session', 'chart': song['chart']}}]},
            }.items():
                (fixture/f'content/{name}.json').write_text(json.dumps(value), encoding='utf-8')
            with patch.object(journal_pages, 'ROOT', fixture):
                journal_pages.refresh()
            day = json.loads((fixture/'content/days/2026-09-03.json').read_text(encoding='utf-8'))
            chart = day['lineChart']
            self.assertNotIn('playheadUrl', chart)
            self.assertNotIn('song', chart['gapNote'])
            self.assertNotIn('silence', chart['gapShort'])
            self.assertFalse(list(fixture.rglob('*timeline.json')))
            svg = (fixture/chart['url'].lstrip('/')).read_text(encoding='utf-8')
            # The missing minute breaks the line rather than being bridged: one
            # real gap draws as two separate runs, unreviewed so both blue.
            self.assertEqual(svg.count('<path '), 2)
            self.assertNotIn('<rect ', svg)
            index = json.loads((fixture/'content/journal-index.json').read_text(encoding='utf-8'))
            self.assertTrue(index['days'][0]['hasChart'])
            self.assertFalse(index['days'][0]['hasSong'])
            assets = json.loads((fixture/'content/market-assets.json').read_text(encoding='utf-8'))
            self.assertTrue(all((fixture/p).is_file() for p in assets))


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
        with patch('log_day.now_et', return_value=AFTER_CLOSE):
            self.log('--private-note', 'Sized too big.', timestamped=False)
        public, private = self.ledger.read_bytes(), self.private.read_bytes()
        with patch('log_day.now_et', return_value='2026-09-04T18:00:00-04:00'):
            self.log(timestamped=False)      # later retry, default timestamps, note omitted
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


class RendererFieldTests(unittest.TestCase):
    """The browser must read the same section fields the schema is willing to publish.

    These two halves drifted once already: the schema renamed the publishable text
    to publicNote and started refusing a plain note, while journal.js kept reading
    x.note. Nothing broke loudly, because no published day had sections yet. The
    cost would have landed later and quietly: Marcelo designates a line of public
    text, the page renders the stretch without it, and nothing anywhere reports a
    problem. A name is not a contract until something checks it.
    """

    SCRIPT = Path(__file__).resolve().parents[1] / 'journal.js'

    def script(self):
        return self.SCRIPT.read_text(encoding='utf-8')

    def test_the_page_reads_the_publishable_text_field(self):
        line = [x for x in self.script().splitlines() if 'executionSections' in x and 'EXECUTION_LABELS' in x]
        self.assertEqual(len(line), 1, 'Expected exactly one line rendering the per-stretch record.')
        self.assertIn('publicNote', line[0])

    def test_the_page_never_reads_the_refused_private_field(self):
        # `.notes` is a real chart field, so match the property name exactly rather
        # than as a substring: `.note` followed by anything that could continue it
        # is a different property and not this mistake.
        text = self.script()
        offenders = []
        for i in range(len(text)):
            if text.startswith('.note', i):
                after = text[i + 5] if i + 5 < len(text) else ''
                if not (after.isalnum() or after == '_'):
                    offenders.append(text[max(0, i - 30):i + 10])
        self.assertEqual(offenders, [], f'journal.js reads a plain .note, which the schema refuses: {offenders}')

    def test_every_section_field_the_page_reads_is_one_the_schema_allows(self):
        allowed = trade_journal.SECTION_FIELDS | trade_journal.SECTION_OPTIONAL
        line = [x for x in self.script().splitlines() if 'executionSections' in x and 'EXECUTION_LABELS' in x][0]
        read = set()
        for i in range(len(line)):
            if line.startswith('x.', i):
                j = i + 2
                while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                    j += 1
                read.add(line[i + 2:j])
        self.assertTrue(read, 'Expected the render line to read at least one section field.')
        self.assertTrue(read <= allowed, f'journal.js reads fields the schema will never publish: {sorted(read - allowed)}')


class ArchiveReconciliationTests(unittest.TestCase):
    """Reconciling the archived XIV$ workspace into the private archive.

    Every fixture here is synthetic. These tests never read Marcelo's real broker
    exports and never write into the real archive, which is why the source and
    archive roots are arguments rather than constants in the tool.
    """

    LOT_HEADER = ('closed_date,opened_date,symbol,underlying,direction,expiration,quantity,'
                  'proceeds,cost_basis,lot_pnl,transaction_pnl,same_day,zero_dte,wash_sale,'
                  'disallowed_loss,name')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'xiv'
        self.archive = Path(self.tmp.name) / 'archive'
        (self.source / 'journal_backfill').mkdir(parents=True)
        (self.source / 'reports').mkdir(parents=True)

    def lots(self, name, rows):
        body = [self.LOT_HEADER]
        for day, under, pnl, qty in rows:
            body.append(f'{day},{day},{under} X,{under},call,{day},{qty},0,0,{pnl},,True,True,False,0.0,NAME')
        path = self.source / 'journal_backfill' / name
        path.write_text('\n'.join(body) + '\n', encoding='utf-8')
        return path

    def journal(self, name, rows):
        lines = [json.dumps(dict(id='pnl-journal-' + d, type='pnl_journal_entry', date=d,
                                 source_file='export.csv', exact_pnl=p, lot_rows=n,
                                 process_color=c, agent_notes=['Backfilled from broker export.']))
                 for d, p, n, c in rows]
        (self.source / 'journal_backfill' / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def shell(self, name, rows):
        lines = [json.dumps(dict(id='pnl-journal-' + d, date=d, traded=t)) for d, t in rows]
        (self.source / 'journal_backfill' / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def receipts(self, month, exports):
        payload = dict(latest_by_date={}, all=[
            dict(name=n, date=d, asof=a, rows=r, contracts=c, pnl=p)
            for n, d, a, r, c, p in exports])
        (self.source / 'reports' / f'recent_realized_receipts_{month}.json').write_text(
            json.dumps(payload), encoding='utf-8')

    def standard(self, month='2026-07', span='2026-05-04_to_2026-07-31'):
        self.lots(f'trade_receipts_lots_{span}.csv',
                  [('2026-07-02', 'SPY', 796.11, 1), ('2026-07-06', 'SPY', 235.39, 1)])
        self.journal(f'pnl_journal_entries_daily_{span}.jsonl',
                     [('2026-07-02', 796.11, 1, 'red'), ('2026-07-06', 235.39, 1, 'red')])
        self.shell(f'daily_calendar_journal_shell_weekdays_{span}.jsonl',
                   [('2026-07-02', True), ('2026-07-03', False), ('2026-07-06', True)])
        self.receipts(month, [('e1.csv', '07/02/2026', 'Thu Jul 02  16:06:07 EDT 2026', 96, 263.0, 837.73)])

    def run_tool(self, month='2026-07'):
        return reconcile_xiv_archive.reconcile(self.source, month, 'TESTRUN')

    # --- choosing the right export -------------------------------------------------

    def test_the_month_is_read_from_the_export_whose_range_covers_it(self):
        # A stale generation of every export sits beside the current one. Taking
        # the first glob match reconciled July against a file ending in June and
        # reported zero trading days: a confident, empty, wrong answer.
        self.standard()
        self.lots('trade_receipts_lots_2024-01-01_to_2026-06-20.csv', [('2026-06-01', 'SPY', 1.0, 1)])
        self.journal('pnl_journal_entries_daily_2024-01-01_to_2026-06-20.jsonl', [])
        self.shell('daily_calendar_journal_shell_weekdays_2024-01-01_to_2026-06-20.jsonl', [])
        _, index = self.run_tool()
        self.assertEqual(index['tradingDates'], ['2026-07-02', '2026-07-06'])

    def test_a_month_no_export_covers_is_refused_rather_than_reported_empty(self):
        self.standard()
        with self.assertRaises(ValueError):
            self.run_tool('2026-11')

    # --- disagreements survive -----------------------------------------------------

    def test_a_settled_total_that_differs_from_the_last_receipt_records_both(self):
        # The receipt was taken while the session was still moving; the export is
        # what settled. Choosing one silently would hide the only interesting
        # thing about the pair.
        self.standard()
        _, index = self.run_tool()
        clash = [c for c in index['conflicts'] if c.get('date') == '2026-07-02' and 'settled' in c]
        self.assertEqual(len(clash), 1)
        self.assertEqual(clash[0]['settled'], 796.11)
        self.assertEqual(clash[0]['lastSnapshot'], 837.73)

    def test_a_receipt_export_dated_outside_the_month_is_never_a_trading_day(self):
        # A bulk history export is filed under the earliest date it contains. It
        # is thousands of rows spanning months, and it is not a session.
        self.standard()
        self.receipts('2026-07', [
            ('e1.csv', '07/02/2026', 'Thu Jul 02  16:06:07 EDT 2026', 96, 263.0, 837.73),
            ('bulk.csv', '04/10/2026', 'Fri Jul 10  09:44:36 EDT 2026', 2803, 5780.0, -4849.51)])
        records, index = self.run_tool()
        self.assertNotIn('2026-04-10', records)
        self.assertEqual([e['reportedDate'] for e in index['unmatchedReceiptExports']], ['2026-04-10'])

    def test_every_receipt_for_a_day_is_kept_in_the_order_it_was_taken(self):
        self.standard()
        self.receipts('2026-07', [
            ('c.csv', '07/02/2026', 'Thu Jul 02  13:02:13 EDT 2026', 35, 57.0, 843.64),
            ('a.csv', '07/02/2026', 'Thu Jul 02  09:53:39 EDT 2026', 4, 6.0, 216.33)])
        records, _ = self.run_tool()
        chain = records['2026-07-02']['receiptSnapshots']['chain']
        self.assertEqual([c['realized'] for c in chain], [216.33, 843.64])

    # --- the line that must not be crossed ------------------------------------------

    def test_no_record_ever_carries_an_execution_assessment(self):
        self.standard()
        records, index = self.run_tool()
        self.assertTrue(records)
        for day, record in records.items():
            self.assertEqual(record['execution']['executionSections'], [], day)
            self.assertIsNone(record['execution']['executionAssessedAt'], day)
            self.assertEqual(record['execution']['status'], 'unreviewed', day)
        self.assertEqual(index['executionAssessmentsFound'], 0)

    def test_the_machine_colour_is_kept_only_as_refused_provenance(self):
        # process_color is arithmetic over profit and lot count. It uses the same
        # three words as a real review and means nothing like them, so it is
        # carried in a block that says so and never near executionSections.
        self.standard()
        records, _ = self.run_tool()
        block = records['2026-07-02']['notAnAssessment']
        self.assertEqual(block['processColor'], 'red')
        self.assertIn('Profit does not establish execution quality', block['reason'])
        self.assertNotIn('process', json.dumps(records['2026-07-02']['execution']))

    def test_the_site_execution_vocabulary_never_appears_in_a_reconciled_record(self):
        # The published classes are good / misplayed / sat_out. If one of those
        # words ever reaches a reconciliation record, something has started
        # translating broker data into a grade.
        self.standard()
        records, index = self.run_tool()
        blob = json.dumps([records, index], ensure_ascii=False)
        for word in ('"good"', '"misplayed"', '"sat_out"'):
            self.assertNotIn(word, blob)

    def test_a_day_is_never_chart_eligible_without_a_price_series(self):
        self.standard()
        records, index = self.run_tool()
        self.assertEqual(index['chartEligibleDates'], [])
        for record in records.values():
            self.assertFalse(record['chartEligible'])
            self.assertIsNone(record['marketPathSource'])

    # --- what gets written, and where ------------------------------------------------

    def test_a_quiet_weekday_is_listed_but_is_not_a_trading_date(self):
        self.standard()
        _, index = self.run_tool()
        self.assertEqual(index['quietWeekdays'], ['2026-07-03'])
        self.assertNotIn('2026-07-03', index['tradingDates'])
        self.assertIn('not proof', index['quietWeekdayNote'].lower())

    def test_records_are_written_only_under_the_private_archive_root(self):
        self.standard()
        records, index = self.run_tool()
        written = reconcile_xiv_archive.write(records, index, self.archive, '2026-07')
        for path in written:
            self.assertTrue(path.is_absolute() or True)
            self.assertIn(self.archive, path.parents)
        self.assertTrue((self.archive / '2026-07-02' / 'archive-reconciliation.json').is_file())
        self.assertTrue((self.archive / '_reconciliation' / '2026-07.json').is_file())

    def test_a_dry_run_writes_nothing(self):
        self.standard()
        with patch('sys.stdout', io.StringIO()):
            reconcile_xiv_archive.main(['--month', '2026-07', '--source', str(self.source),
                                        '--archive', str(self.archive), '--dry-run'])
        self.assertFalse(self.archive.exists())

    # --- chart eligibility is detected, not asserted ---------------------------------

    def snapshot(self, folder, stamps, offset=-14400, granularity='1h'):
        path = self.archive / folder / 'source-yahoo-hourly-3mo.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(chart=dict(result=[dict(
            meta=dict(symbol='SPY', gmtoffset=offset, dataGranularity=granularity,
                      exchangeTimezoneName='America/New_York'),
            timestamps_note='unused', timestamp=list(stamps),
            indicators=dict(quote=[dict(open=[], high=[], low=[], close=[])]))]))),
            encoding='utf-8')
        return path

    def stamps_for(self, day, hours, offset=-14400):
        base = datetime.datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
        return [int(base.timestamp()) + h * 3600 - offset for h in hours]

    def test_a_date_becomes_chart_eligible_when_its_bars_are_saved(self):
        # The first run of this tool found no July price series at all and every
        # record said so. A snapshot saved afterwards has to make those same
        # records true without anyone editing a constant, so the archive is
        # rescanned each run rather than trusted to a flag.
        self.standard()
        _, index = self.run_tool()
        self.assertEqual(index['chartEligibleDates'], [])

        self.snapshot('2026-07', self.stamps_for('2026-07-02', range(10, 16)))
        records, index = reconcile_xiv_archive.reconcile(self.source, '2026-07', 'TESTRUN', self.archive)
        self.assertEqual(index['chartEligibleDates'], ['2026-07-02'])
        self.assertTrue(records['2026-07-02']['chartEligible'])
        self.assertEqual(records['2026-07-02']['marketPathBars'], 6)
        self.assertEqual(len(records['2026-07-02']['marketPathSource']['sha256']), 64)
        self.assertIsNone(records['2026-07-02']['chartBlockedBecause'])
        # A day the market was open for but nothing closed on is still not a
        # trading date, so it never turns up as an eligible session.
        self.assertFalse(records['2026-07-06']['chartEligible'])

    def test_bars_are_bucketed_by_exchange_date_not_utc(self):
        # A late bar belongs to the session it traded in. Bucketing by UTC would
        # move it silently onto the following date, which is the kind of error
        # that produces a chart nobody can tell is wrong.
        self.standard()
        self.snapshot('2026-07', [int(datetime.datetime(
            2026, 7, 3, 1, 0, tzinfo=datetime.timezone.utc).timestamp())])
        records, index = reconcile_xiv_archive.reconcile(self.source, '2026-07', 'TESTRUN', self.archive)
        self.assertEqual(index['marketDatesWithPrices'], ['2026-07-02'])
        self.assertEqual(records['2026-07-02']['marketPathBars'], 1)

    def test_chart_eligible_never_means_reviewed(self):
        # Drawable and assessed are different questions. Having the price path
        # says the line can be drawn; it says nothing about how it was traded.
        self.standard()
        self.snapshot('2026-07', self.stamps_for('2026-07-02', range(10, 16)))
        records, index = reconcile_xiv_archive.reconcile(self.source, '2026-07', 'TESTRUN', self.archive)
        self.assertEqual(index['chartEligibleDates'], ['2026-07-02'])
        self.assertEqual(index['executionAssessmentsFound'], 0)
        self.assertEqual(records['2026-07-02']['execution']['executionSections'], [])
        self.assertEqual(records['2026-07-02']['execution']['status'], 'unreviewed')

    def test_a_snapshot_that_is_not_a_chart_payload_is_skipped_quietly(self):
        self.standard()
        path = self.archive / '2026-07' / 'source-yahoo-daily.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"not": "a chart"}', encoding='utf-8')
        _, index = reconcile_xiv_archive.reconcile(self.source, '2026-07', 'TESTRUN', self.archive)
        self.assertEqual(index['chartEligibleDates'], [])

    def test_every_figure_names_the_file_and_hash_it_came_from(self):
        self.standard()
        records, _ = self.run_tool()
        settled = records['2026-07-02']['settled']
        self.assertEqual(len(settled['source']['sha256']), 64)
        self.assertTrue(settled['source']['path'].endswith('.csv'))
        self.assertNotIn(str(self.source), settled['source']['path'])


class PublishedChartTests(unittest.TestCase):
    """The checker that says the published charts are right.

    A checker nobody checks is worth nothing, and this one has already been wrong
    once: an earlier version knew only the archive's `sourceSha256`/`bars` schema
    and reported the two song days, which write `source_sha256`/`minutes`, as
    having no provenance at all. It manufactured the fault it existed to find.
    So each test here breaks a published day on purpose and asserts the fault is
    seen.
    """

    def day(self, date='2026-07-15', **over):
        payload = dict(
            date=date,
            lineChart=dict(url=f'/assets/charts/{date}-hourly.svg',
                           dataUrl=f'/content/history/{date}-hourly.json',
                           caption='Hourly bars', gapShort='Hourly bars, not a minute path',
                           gapNote='Seven bars.', alt='SPY hourly'),
            performance=dict(executionSections=[], executionAssessedAt=None, setupRating=None,
                             execution=dict(label='Execution not reviewed')))
        payload.update(over)
        return payload

    def tree(self, date='2026-07-15', history=None, payload=None):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(root, ignore_errors=True))
        (root / 'assets/charts').mkdir(parents=True)
        (root / 'content/history').mkdir(parents=True)
        (root / f'assets/charts/{date}-hourly.svg').write_text('<svg/>', encoding='utf-8')
        body = dict(date=date, symbol='SPY', interval='1h', sourceSha256='a' * 64,
                    bars=[dict(open=1, high=2, low=0, close=1) for _ in range(7)])
        body.update(history or {})
        (root / f'content/history/{date}-hourly.json').write_text(
            json.dumps(body), encoding='utf-8')
        return root, payload or self.day(date)

    def faults(self, date='2026-07-15', history=None, payload=None):
        root, body = self.tree(date, history, payload)
        return verify_published_charts.check_day(date, body, root)

    def test_a_correct_day_reports_nothing(self):
        self.assertEqual(self.faults(), [])

    def test_a_chart_drawing_another_date_is_caught(self):
        # The failure Marcelo actually reported: the page shows a session that is
        # not the one selected.
        faults = self.faults(history=dict(date='2026-07-14'))
        self.assertTrue(any('dated 2026-07-14' in f for f in faults), faults)

    def test_a_payload_filed_under_the_wrong_date_is_caught(self):
        faults = self.faults(payload=self.day('2026-07-15') | dict(date='2026-07-13'))
        self.assertTrue(any('dated 2026-07-13' in f for f in faults), faults)

    def test_missing_supplied_data_is_caught(self):
        root, body = self.tree()
        (root / 'content/history/2026-07-15-hourly.json').unlink()
        faults = verify_published_charts.check_day('2026-07-15', body, root)
        self.assertTrue(any('supplied data missing' in f for f in faults), faults)

    def test_hourly_bars_sold_as_a_minute_path_are_caught(self):
        chart = dict(url='/assets/charts/2026-07-15-hourly.svg',
                     dataUrl='/content/history/2026-07-15-hourly.json',
                     caption='The minute line', gapShort='', gapNote='', alt='')
        faults = self.faults(payload=self.day() | dict(lineChart=chart))
        self.assertTrue(any('not described as hourly' in f for f in faults), faults)
        self.assertTrue(any('disclaim being a minute path' in f for f in faults), faults)

    def test_an_invented_execution_section_is_caught(self):
        perf = dict(executionSections=[dict(startTime='09:30', endTime='09:48', execution='good')],
                    executionAssessedAt='2026-07-15T17:00', setupRating=9,
                    execution=dict(label='Played well'))
        faults = self.faults(payload=self.day() | dict(performance=perf))
        self.assertTrue(any('execution sections' in f for f in faults), faults)
        self.assertTrue(any('assessment timestamp' in f for f in faults), faults)
        self.assertTrue(any('setup rating' in f for f in faults), faults)

    def test_both_history_schemas_are_read_as_provenance(self):
        # The archive writes sourceSha256/bars; the song days write
        # source_sha256/minutes. Neither is missing provenance.
        self.assertEqual(self.faults(), [])
        song = dict(sourceSha256=None, source_sha256='b' * 64, bars=None,
                    minutes=[{'close': 1}] * 390, interval=None)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(root, ignore_errors=True))
        (root / 'assets/charts').mkdir(parents=True)
        (root / 'content/history').mkdir(parents=True)
        (root / 'assets/charts/2026-09-03-hourly.svg').write_text('<svg/>', encoding='utf-8')
        body = {k: v for k, v in dict(date='2026-09-03', symbol='SPY', **song).items() if v is not None}
        (root / 'content/history/2026-09-03-hourly.json').write_text(json.dumps(body), encoding='utf-8')
        chart = dict(url='/assets/charts/2026-09-03-hourly.svg',
                     dataUrl='/content/history/2026-09-03-hourly.json',
                     caption='The day\'s line', gapShort='', gapNote='', alt='')
        faults = verify_published_charts.check_day('2026-09-03', self.day('2026-09-03') | dict(lineChart=chart), root)
        self.assertEqual([f for f in faults if 'source hash' in f], [])


class SessionCandleTests(unittest.TestCase):
    """Candles: placed by the clock, coloured only by Marcelo's review."""

    BLUE, GREEN, RED, GOLD = '#50b8f5', '#58dfa4', '#ff7188', '#e5b657'

    def hour(self, start, o, h, l, c, minutes=60):
        return dict(startMinute=start, durationMinutes=minutes, open=o, high=h, low=l, close=c)

    def session(self):
        # Seven hourly bars, the last covering 15:30 to 16:00.
        spans = [(0, 60), (60, 60), (120, 60), (180, 60), (240, 60), (300, 60), (360, 30)]
        return [self.hour(s, 100, 102, 99, 101, d) for s, d in spans]

    # --- position -------------------------------------------------------------

    def test_the_drawing_spans_the_regular_session_exactly(self):
        self.assertEqual(session_chart.x_of(0), session_chart.MARGIN_X)
        self.assertEqual(session_chart.x_of(390), session_chart.WIDTH - session_chart.MARGIN_X)

    def test_bars_are_placed_by_the_clock_not_by_their_index(self):
        # Seven bars evenly spaced would put the last one at six sevenths of the
        # width. It belongs at 360/390, because it starts at 15:30.
        bars = self.session()
        last = bars[-1]
        self.assertAlmostEqual(session_chart.x_of(last['startMinute']),
                               session_chart.MARGIN_X + 360 / 390 * session_chart.PLOT_WIDTH, places=6)
        evenly = session_chart.MARGIN_X + 6 / 7 * session_chart.PLOT_WIDTH
        self.assertNotAlmostEqual(session_chart.x_of(last['startMinute']), evenly, places=1)

    def test_the_final_short_bar_is_drawn_narrower(self):
        svg = session_chart.candles(self.session())
        widths = [float(w) for w in re.findall(r'<rect [^>]*width="([\d.]+)"', svg)]
        self.assertEqual(len(widths), 7)
        self.assertLess(widths[-1], widths[0] * 0.75)

    def test_a_candle_carries_a_body_and_a_wick(self):
        svg = session_chart.candles([self.hour(0, 100, 105, 95, 103)])
        self.assertEqual(svg.count('<rect'), 1)
        self.assertEqual(svg.count('<line'), 1)

    # --- colour ----------------------------------------------------------------

    def test_an_unreviewed_session_is_entirely_neutral(self):
        svg = session_chart.candles(self.session())
        self.assertIn(self.BLUE, svg)
        for colour in (self.GREEN, self.RED, self.GOLD):
            self.assertNotIn(colour, svg)

    def test_a_reviewed_stretch_takes_its_colour(self):
        sections = [dict(startTime='09:30', endTime='10:30', execution='good'),
                    dict(startTime='10:30', endTime='11:30', execution='misplayed')]
        svg = session_chart.candles(self.session(), sections)
        self.assertIn(self.GREEN, svg)
        self.assertIn(self.RED, svg)
        self.assertIn(self.BLUE, svg)  # the five unreviewed hours stay neutral

    def test_direction_never_decides_colour(self):
        # The whole point. A candle that fell inside a stretch Marcelo played well
        # is green; a candle that rose inside a stretch he misplayed is red. Every
        # other candle chart in the world does the opposite of this.
        rose = self.hour(0, 100, 106, 99, 105)
        fell = self.hour(60, 105, 106, 98, 99)
        good = [dict(startTime='09:30', endTime='11:30', execution='good')]
        bad = [dict(startTime='09:30', endTime='11:30', execution='misplayed')]
        self.assertEqual(re.findall(r'fill="(#\w+)"', session_chart.candles([rose, fell], good)),
                         [self.GREEN, self.GREEN])
        self.assertEqual(re.findall(r'fill="(#\w+)"', session_chart.candles([rose, fell], bad)),
                         [self.RED, self.RED])

    def test_a_partly_covered_bar_is_not_coloured(self):
        # A review that starts at 09:48 does not reach back and grade the hour
        # that began at 09:30.
        sections = [dict(startTime='09:48', endTime='10:30', execution='good')]
        svg = session_chart.candles([self.hour(0, 100, 102, 99, 101)], sections)
        self.assertIn(self.BLUE, svg)
        self.assertNotIn(self.GREEN, svg)

    def test_a_flat_candle_still_draws(self):
        svg = session_chart.candles([self.hour(0, 100, 100, 100, 100)])
        height = float(re.search(r'<rect [^>]*height="([\d.]+)"', svg).group(1))
        self.assertGreater(height, 0.9)

    # --- reading the saved shapes ------------------------------------------------

    def test_hourly_bars_take_their_duration_from_the_next_bar(self):
        source = dict(interval='1h', bars=[
            dict(startTime=f'2026-06-15T{h:02d}:{m:02d}:00-04:00', open=1, high=2, low=0, close=1)
            for h, m in ((9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30))])
        bars = session_chart.bars_from(source)
        self.assertEqual([b['startMinute'] for b in bars], [0, 60, 120, 180, 240, 300, 360])
        self.assertEqual([b['durationMinutes'] for b in bars], [60] * 6 + [30])

    def test_minute_bars_are_read_from_either_minute_schema(self):
        archive = dict(bars=[dict(minute=i, open=1, high=2, low=0, close=1) for i in range(3)])
        song = dict(minutes=[dict(minute=i, open=1, high=2, low=0, close=1, missing=False)
                             for i in range(3)])
        for source in (archive, song):
            bars = session_chart.bars_from(source)
            self.assertEqual([b['startMinute'] for b in bars], [0, 1, 2])
            self.assertTrue(all(b['durationMinutes'] == 1 for b in bars))

    def test_a_missing_minute_is_dropped_rather_than_drawn(self):
        source = dict(minutes=[dict(minute=0, open=1, high=2, low=0, close=1, missing=False),
                               dict(minute=1, open=None, high=None, low=None, close=None, missing=True)])
        self.assertEqual([b['startMinute'] for b in session_chart.bars_from(source)], [0])


class SessionLineTests(unittest.TestCase):
    """Thin lines: same clock, same colour rule as candles — a different mark."""

    BLUE, GREEN, RED, GOLD = '#50b8f5', '#58dfa4', '#ff7188', '#e5b657'

    def hour(self, start, o, h, l, c, minutes=60):
        return dict(startMinute=start, durationMinutes=minutes, open=o, high=h, low=l, close=c)

    def session(self):
        # Seven hourly bars, the last covering 15:30 to 16:00.
        spans = [(0, 60), (60, 60), (120, 60), (180, 60), (240, 60), (300, 60), (360, 30)]
        return [self.hour(s, 100, 102, 99, 101, d) for s, d in spans]

    # --- geometry ---------------------------------------------------------------

    def test_the_line_spans_the_regular_session_exactly_by_the_clock(self):
        svg = session_chart.document('2026-06-15', self.session())
        points = re.findall(r'[ML]([\d.]+),([\d.]+)', svg)
        xs = [float(x) for x, y in points]
        self.assertAlmostEqual(min(xs), session_chart.MARGIN_X, places=6)
        self.assertAlmostEqual(max(xs), session_chart.WIDTH - session_chart.MARGIN_X, places=6)
        # Not evenly spaced by index: the last bar starts at 15:30, six sevenths
        # of the width would be a different x than the true 360/390 position.
        evenly = session_chart.MARGIN_X + 6 / 7 * session_chart.PLOT_WIDTH
        self.assertNotAlmostEqual(xs[-2], evenly, places=1)

    def test_hourly_data_draws_eight_connected_points_not_smoothed(self):
        # Open plus seven closes: exactly the boundaries that were observed,
        # joined by straight segments, nothing invented in between.
        svg = session_chart.lines(self.session())
        self.assertEqual(svg.count('<path'), 1)
        d = re.search(r'<path d="([^"]+)"', svg).group(1)
        self.assertEqual(d.count('M') + d.count('L'), 8)

    def test_no_candle_shapes_are_drawn(self):
        svg = session_chart.document('2026-06-15', self.session())
        self.assertNotIn('<rect', svg)
        self.assertIn('<path', svg)

    # --- colour ------------------------------------------------------------------

    def test_an_unreviewed_session_is_entirely_neutral(self):
        svg = session_chart.lines(self.session())
        self.assertIn(self.BLUE, svg)
        for colour in (self.GREEN, self.RED, self.GOLD):
            self.assertNotIn(colour, svg)

    def test_a_reviewed_stretch_takes_its_colour(self):
        sections = [dict(startTime='09:30', endTime='10:30', execution='good'),
                    dict(startTime='10:30', endTime='11:30', execution='misplayed')]
        svg = session_chart.lines(self.session(), sections)
        self.assertIn(self.GREEN, svg)
        self.assertIn(self.RED, svg)
        self.assertIn(self.BLUE, svg)  # the five unreviewed hours stay neutral

    def test_direction_never_decides_colour(self):
        rose = self.hour(0, 100, 106, 99, 105)
        fell = self.hour(60, 105, 106, 98, 99)
        good = [dict(startTime='09:30', endTime='11:30', execution='good')]
        bad = [dict(startTime='09:30', endTime='11:30', execution='misplayed')]
        self.assertIn(self.GREEN, session_chart.lines([rose, fell], good))
        self.assertNotIn(self.RED, session_chart.lines([rose, fell], good))
        self.assertIn(self.RED, session_chart.lines([rose, fell], bad))
        self.assertNotIn(self.GREEN, session_chart.lines([rose, fell], bad))

    def test_a_partly_covered_hour_is_not_coloured(self):
        sections = [dict(startTime='09:48', endTime='10:30', execution='good')]
        svg = session_chart.lines([self.hour(0, 100, 102, 99, 101)], sections)
        self.assertIn(self.BLUE, svg)
        self.assertNotIn(self.GREEN, svg)

    # --- gaps ----------------------------------------------------------------------

    def test_a_source_gap_breaks_the_line_into_two_runs(self):
        bars = [self.hour(0, 100, 101, 99, 100, 60), self.hour(120, 105, 106, 104, 105, 60)]
        svg = session_chart.lines(bars)
        self.assertEqual(svg.count('<path'), 2)

    # --- same presentation regardless of resolution ---------------------------------

    def test_hourly_and_minute_sources_draw_the_same_kind_of_mark(self):
        hourly_source = dict(interval='1h', bars=[
            dict(startTime=f'2026-06-15T{h:02d}:{m:02d}:00-04:00', open=1, high=2, low=0, close=1)
            for h, m in ((9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30))])
        minute_source = dict(bars=[dict(minute=i, open=1, high=2, low=0, close=1) for i in range(390)])
        for source in (hourly_source, minute_source):
            svg = session_chart.lines(session_chart.bars_from(source))
            self.assertIn('<path', svg)
            self.assertNotIn('<rect', svg)
            self.assertNotIn('<line', svg)


class TradeOverlayTests(unittest.TestCase):
    """Gold profit, blue loss, neutral everything else — and never an inference."""

    GREY, GOLD, BLUE = '#81929e', '#e5b657', '#50b8f5'

    def trade(self, start, end, outcome='profit', **changes):
        value = dict(startTime=start, endTime=end, outcome=outcome,
                     underlying='SPY', sourceKind='imported_result')
        value.update(changes)
        return value

    # --- what may enter the ledger -------------------------------------------

    def test_only_spy_may_colour_a_spy_chart(self):
        # The whole reason this field exists: an AAPL-only trading day must not
        # paint a window onto the SPY line.
        with self.assertRaises(ValueError):
            trade_overlays.validate([self.trade('10:00', '11:00', underlying='AAPL')])
        self.assertEqual(len(trade_overlays.validate([self.trade('10:00', '11:00')])), 1)

    def test_outcome_and_source_must_be_explicit(self):
        for changes in (dict(outcome='win'), dict(outcome=None), dict(sourceKind='guessed'),
                        dict(sourceKind='inferred_from_pnl')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                trade_overlays.validate([self.trade('10:00', '11:00', **changes)])

    def test_exit_must_follow_entry(self):
        # No guessing an overnight hold or a half-filled span.
        for start, end in (('11:00', '10:00'), ('10:00', '10:00')):
            with self.subTest(span=(start, end)), self.assertRaises(ValueError):
                trade_overlays.validate([self.trade(start, end)])

    def test_times_must_sit_inside_the_regular_session(self):
        for start, end in (('09:00', '10:00'), ('15:00', '16:30'), ('08:15', '09:00')):
            with self.subTest(span=(start, end)), self.assertRaises(ValueError):
                trade_overlays.validate([self.trade(start, end)])

    def test_seconds_are_accepted_and_ordered(self):
        rows = trade_overlays.validate([self.trade('12:44:35', '12:47:13'),
                                        self.trade('09:48:48', '09:51:01')])
        self.assertEqual([r['startTime'] for r in rows], ['09:48:48', '12:44:35'])

    def test_unexpected_fields_are_refused(self):
        with self.assertRaises(ValueError):
            trade_overlays.validate([self.trade('10:00', '11:00', netPnl=412.0)])

    # --- what the colours actually say ----------------------------------------

    def test_time_outside_any_trade_is_neutral(self):
        spans = trade_overlays.intervals([self.trade('10:00', '11:00')])
        self.assertEqual([o for _, _, o in spans], ['unrecorded', 'profit', 'unrecorded'])

    def test_conflicting_overlapping_trades_go_neutral(self):
        # One profitable and one losing trade covering the same minute cannot
        # both colour it, so that stretch says nothing rather than picking one.
        spans = trade_overlays.intervals([self.trade('10:00', '12:00', 'profit'),
                                          self.trade('10:30', '11:00', 'loss')])
        covered = [o for a, b, o in spans if 60 <= a and b <= 90]
        self.assertTrue(covered)
        self.assertEqual(set(covered), {'unrecorded'})

    def test_agreeing_overlapping_trades_keep_their_colour(self):
        spans = trade_overlays.intervals([self.trade('10:00', '12:00', 'profit'),
                                          self.trade('10:30', '11:00', 'profit')])
        covered = [o for a, b, o in spans if 60 <= a and b <= 90]
        self.assertEqual(set(covered), {'profit'})

    def test_breakeven_never_takes_a_colour(self):
        svg = session_chart.trade_lines([dict(startMinute=0, durationMinutes=390,
                                              open=1, high=2, low=0, close=1)],
                                        [self.trade('10:00', '11:00', 'flat')])
        self.assertIn(self.GREY, svg)
        for colour in (self.GOLD, self.BLUE):
            self.assertNotIn(colour, svg)

    def test_an_overlay_clips_and_never_adds_a_price_point(self):
        bars = [dict(startMinute=m, durationMinutes=1, open=1, high=2, low=0, close=1)
                for m in range(390)]
        plain = session_chart.trade_lines(bars)
        overlaid = session_chart.trade_lines(bars, [self.trade('10:00', '11:00')])
        self.assertEqual(sorted(set(re.findall(r'<path d="([^"]+)"', plain))),
                         sorted(set(re.findall(r'<path d="([^"]+)"', overlaid))),
                         'an overlay must reuse the drawn path, not add geometry')
        self.assertIn('clipPath', overlaid)
        self.assertIn(self.GOLD, overlaid)

    # --- the empty state ------------------------------------------------------

    def test_empty_state_names_the_missing_evidence(self):
        text = trade_overlays.note([])
        for needed in ('entry time', 'exit time', 'settled outcome', 'disagree'):
            self.assertIn(needed, text)
        self.assertIn('Neutral never means no trades occurred.', text)

    def test_hourly_empty_state_adds_its_own_limitation(self):
        hourly = trade_overlays.note([], 'hourly')
        minute = trade_overlays.note([], 'minute')
        self.assertIn('hourly observations', hourly)
        self.assertNotIn('hourly observations', minute)
        self.assertNotEqual(hourly, minute, 'the empty state should not read identically everywhere')


class TradeCoverageTests(unittest.TestCase):
    """One record, more than one source. A source that cannot time its trades
    leaves the record incomplete; it does not make the day idle."""

    def test_a_source_is_a_broker_name_never_an_account(self):
        self.assertEqual(trade_overlays.validate_coverage(dict(timed=['Webull'], untimed=['Schwab'])),
                         dict(timed=['Webull'], untimed=['Schwab']))
        # An account identifier must not reach public output by habit.
        for bad in ('XXXX5208', 'Schwab 5208', '5208', ''):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                trade_overlays.validate_coverage(dict(timed=[bad]))

    def test_coverage_shape_is_enforced(self):
        for bad in ({}, dict(timed=[]), dict(unknown=['Webull']), [], 'Webull'):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                trade_overlays.validate_coverage(bad)
        self.assertIsNone(trade_overlays.validate_coverage(None))

    def test_partial_coverage_says_the_record_is_incomplete(self):
        text = trade_overlays.coverage_note(dict(timed=['Webull'], untimed=['Schwab']))
        self.assertIn('Partial coverage: Webull timed trades; Schwab timing unavailable.', text)
        self.assertIn('not that no trading happened', text)

    def test_full_coverage_adds_no_caveat(self):
        self.assertEqual(trade_overlays.coverage_note(dict(timed=['Webull'])), '')
        self.assertEqual(trade_overlays.coverage_note(None), '')

    def test_the_visible_strip_states_partial_coverage_not_only_the_alt_text(self):
        # A sighted reader never sees an image description, so the caveat has to
        # appear in the page text too.
        view = presentation(dict(date='2026-06-03', outcome='unrecorded', setupRating=None,
                                 ratingAsOf=None, recordedAt=NOW, sourceKind='imported_result',
                                 executionSections=None, executionAssessedAt=None,
                                 tradeSections=[dict(startTime='09:48:48', endTime='09:51:01',
                                                     outcome='profit', underlying='SPY',
                                                     sourceKind='imported_result')],
                                 tradeCoverage=dict(timed=['Webull'], untimed=['Schwab'])))
        rendered = trade_journal.strip(view)
        self.assertIn('Partial coverage', rendered)
        self.assertIn('Webull timed', rendered)
        self.assertIn('Schwab timing unavailable', rendered)
        self.assertIn('Partial coverage', ' '.join(trade_journal.notes(view)))

    def test_note_carries_the_caveat_whether_or_not_windows_exist(self):
        coverage = dict(timed=['Webull'], untimed=['Schwab'])
        drawn = trade_overlays.note([dict(startTime='10:00', endTime='11:00', outcome='profit',
                                          underlying='SPY', sourceKind='imported_result')],
                                    'hourly', coverage)
        empty = trade_overlays.note([], 'hourly', coverage)
        for text in (drawn, empty):
            self.assertIn('Partial coverage', text)

    # --- the ledger rule that lets trades stand on their own -------------------

    def test_a_day_may_record_trades_without_declaring_a_day_result(self):
        row = dict(date='2026-06-03', outcome='unrecorded', setupRating=None, ratingAsOf=None,
                   recordedAt=NOW, sourceKind='imported_result',
                   executionSections=None, executionAssessedAt=None,
                   tradeSections=[dict(startTime='09:48:48', endTime='09:51:01', outcome='profit',
                                       underlying='SPY', sourceKind='imported_result')])
        days = validate(dict(schemaVersion=2, days=[row]))
        self.assertEqual(len(days['2026-06-03']['tradeSections']), 1)
        self.assertEqual(days['2026-06-03']['outcome'], 'unrecorded')

    def test_an_unrecorded_day_with_no_trades_is_still_refused(self):
        row = dict(date='2026-06-03', outcome='unrecorded', setupRating=None, ratingAsOf=None,
                   recordedAt=NOW, sourceKind='imported_result',
                   executionSections=None, executionAssessedAt=None)
        with self.assertRaises(ValueError):
            validate(dict(schemaVersion=2, days=[row]))


class DeriveTradeSectionsTests(unittest.TestCase):
    """Windows come from completed positions, and outcomes from their own fills."""

    def fill(self, time, side, quantity, price, contract='SPY 756 call'):
        return dict(time=time, side=side, quantity=quantity, price=price, contract=contract)

    def test_scaling_out_is_one_window_not_three(self):
        fills = [self.fill('11:25:02', 'Buy', 7, 0.99),
                 self.fill('11:27:43', 'Sell', 5, 1.12),
                 self.fill('11:29:20', 'Sell', 2, 1.18)]
        public, private, _ = derive_trade_sections.derive(fills)
        self.assertEqual(len(public), 1)
        self.assertEqual((public[0]['startTime'], public[0]['endTime']), ('11:25:02', '11:29:20'))
        self.assertEqual(private[0]['grossRealized'], 103.00)
        self.assertEqual(public[0]['outcome'], 'profit')

    def test_two_contracts_held_at_once_are_two_windows(self):
        fills = [self.fill('09:48:48', 'Buy', 6, 1.45, 'SPY 756 call'),
                 self.fill('09:49:21', 'Buy', 7, 1.90, 'SPY 755 call'),
                 self.fill('09:50:55', 'Sell', 7, 2.05, 'SPY 755 call'),
                 self.fill('09:51:01', 'Sell', 6, 1.55, 'SPY 756 call')]
        public, _, _ = derive_trade_sections.derive(fills)
        self.assertEqual(len(public), 2)
        self.assertEqual(sorted((p['startTime'], p['endTime']) for p in public),
                         [('09:48:48', '09:51:01'), ('09:49:21', '09:50:55')])

    def test_reentering_the_same_contract_is_a_second_window(self):
        fills = [self.fill('09:48:48', 'Buy', 6, 1.45),
                 self.fill('09:51:01', 'Sell', 6, 1.55),
                 self.fill('11:25:02', 'Buy', 7, 0.99),
                 self.fill('11:29:20', 'Sell', 7, 1.18)]
        public, _, _ = derive_trade_sections.derive(fills)
        self.assertEqual([(p['startTime'], p['endTime']) for p in public],
                         [('09:48:48', '09:51:01'), ('11:25:02', '11:29:20')])

    def test_a_loss_is_a_loss_from_its_own_fills(self):
        fills = [self.fill('10:00:00', 'Buy', 4, 2.00), self.fill('10:30:00', 'Sell', 4, 1.50)]
        public, private, _ = derive_trade_sections.derive(fills)
        self.assertEqual(private[0]['grossRealized'], -200.00)
        self.assertEqual(public[0]['outcome'], 'loss')

    def test_a_position_still_open_cannot_be_drawn(self):
        fills = [self.fill('15:50:00', 'Buy', 3, 1.00)]
        public, _, skipped = derive_trade_sections.derive(fills)
        self.assertEqual(public, [])
        self.assertIn('still open', skipped[0]['reason'])

    def test_another_underlying_never_reaches_a_spy_chart(self):
        fills = [self.fill('10:00:00', 'Buy', 1, 5.00, 'AAPL 230 call'),
                 self.fill('10:30:00', 'Sell', 1, 6.00, 'AAPL 230 call')]
        public, _, skipped = derive_trade_sections.derive(fills)
        self.assertEqual(public, [])
        self.assertIn('may not colour', skipped[0]['reason'])

    def test_breakeven_is_recorded_but_not_coloured(self):
        fills = [self.fill('10:00:00', 'Buy', 2, 1.00), self.fill('10:10:00', 'Sell', 2, 1.00)]
        public, private, skipped = derive_trade_sections.derive(fills)
        self.assertEqual(public, [])
        self.assertEqual(private[0]['outcome'], 'flat')
        self.assertIn('breakeven', skipped[0]['reason'])

    def test_a_result_small_enough_for_fees_to_flip_is_flagged(self):
        fills = [self.fill('10:00:00', 'Buy', 1, 1.00), self.fill('10:10:00', 'Sell', 1, 1.01)]
        _, private, _ = derive_trade_sections.derive(fills)
        self.assertTrue(private[0]['feeSensitive'], 'a one dollar gross result must be flagged')

    def test_derived_sections_satisfy_the_public_schema(self):
        fills = [self.fill('11:25:02', 'Buy', 7, 0.99), self.fill('11:29:20', 'Sell', 7, 1.18)]
        public, _, _ = derive_trade_sections.derive(fills)
        self.assertEqual(trade_overlays.validate(public), public)


if __name__ == '__main__': unittest.main()
