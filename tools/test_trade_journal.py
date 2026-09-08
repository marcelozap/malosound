"""Behavior checks for honest daily result publishing; no live records are mutated."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import journal_pages
from record_trading_day import normalize, stage
from trade_journal import presentation, validate

NOW = '2026-09-07T18:00:00+00:00'


def raw(**changes):
    value = dict(date='2026-09-04', mode='live', final=True, netRealizedPnl='-12.50',
                 feesIncluded=True, tradeCount=2, sourceKind='imported_result')
    value.update(changes)
    return value


class TradeJournalTests(unittest.TestCase):
    def test_sign_is_own_net_result(self):
        for value, expected in [('12.50', 'profit'), ('-0.01', 'loss'), ('0.00', 'flat')]:
            self.assertEqual(normalize(raw(netRealizedPnl=value), NOW)['outcome'], expected)

    def test_zero_trades_and_missing_are_distinct(self):
        row = normalize(raw(netRealizedPnl='0', tradeCount=0), NOW)
        self.assertEqual(row['outcome'], 'no_trade')
        self.assertEqual(presentation(None)['outcome'], 'unrecorded')
        self.assertIsNone(presentation(None)['setupRating'])

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
            validate(dict(schemaVersion=1, days=[row]))

    def test_duplicate_dates_rejected(self):
        row = normalize(raw(), NOW)
        with self.assertRaises(ValueError):
            validate(dict(schemaVersion=1, days=[row, row]))

    def test_retries_preserve_timestamp_and_corrections_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, ledger = Path(tmp)/'private.json', Path(tmp)/'public.json'
            source.write_text(json.dumps(raw()), encoding='utf-8')
            ledger.write_text(json.dumps(dict(schemaVersion=1, days=[])), encoding='utf-8')
            self.assertTrue(stage(source, ledger))
            before = ledger.read_bytes()
            self.assertFalse(stage(source, ledger))
            self.assertEqual(ledger.read_bytes(), before)
            source.write_text(json.dumps(raw(netRealizedPnl='10')), encoding='utf-8')
            with self.assertRaises(ValueError): stage(source, ledger)
            self.assertEqual(ledger.read_bytes(), before)
            self.assertTrue(stage(source, ledger, replace=True))

    def test_market_path_gaps_and_audio_unchanged_for_each_result(self):
        root = journal_pages.ROOT
        editions = json.loads((root/'content/editions.json').read_text(encoding='utf-8'))
        # Source fixture is the real market path; only result metadata is synthetic, in temp files.
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
            original_shapes = {}
            for day in ('2026-09-03', '2026-09-04'):
                old = subprocess.check_output(['git', 'show', f'HEAD:assets/charts/{day}-line.svg'], cwd=root).decode()
                original_shapes[day] = re.search(r'<path d="([^"]+)"', old).group(1)
            for outcome, color in [('profit','#58dfa4'), ('loss','#ff7188'), ('flat','#b8c5d0'), ('no_trade','#81929e'), ('unrecorded','#81929e')]:
                rows = [] if outcome == 'unrecorded' else [dict(date=s['date'], outcome=outcome, setupRating=14, ratingAsOf='2026-09-03T09:00:00-04:00', recordedAt=NOW, sourceKind='user_reported') for s in editions['sessions']]
                (fixture/'content/trading-journal.json').write_text(json.dumps(dict(schemaVersion=1, days=rows)), encoding='utf-8')
                (fixture/'content/editions.json').write_text(json.dumps(editions), encoding='utf-8')
                with patch.object(journal_pages, 'ROOT', fixture): journal_pages.refresh()
                for day, shape in original_shapes.items():
                    svg = (fixture/f'assets/charts/{day}-line.svg').read_text(encoding='utf-8')
                    self.assertEqual(re.search(r'<path d="([^"]+)"', svg).group(1), shape)
                    self.assertIn(f'stroke="{color}"', svg)
                    self.assertEqual(json.loads((fixture/f'assets/charts/{day}-timeline.json').read_text()), json.loads((root/f'assets/charts/{day}-timeline.json').read_text()))
                    report = (fixture/f'reports/{day}-spy-song.html').read_text(encoding='utf-8')
                    self.assertIn(f'data-trade-result="{outcome}"', report)
                    self.assertEqual(report.count('<i class='), 14)
                updated = json.loads((fixture/'content/editions.json').read_text(encoding='utf-8'))
                for old, new in zip(editions['sessions'], updated['sessions']):
                    for key in ('morning','preOpen','closing','originalSong'):
                        self.assertEqual(old.get(key), new.get(key))


if __name__ == '__main__': unittest.main()
