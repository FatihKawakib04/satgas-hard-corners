"""Tests for the TVL aggregation rules.

Run: python3 -m unittest tests.test_tvl -v   (from site/research)
"""
from __future__ import annotations

import unittest

import tvl


def rows(*triples):
    return list(triples)


class TestAggregate(unittest.TestCase):
    def test_total_row_wins_and_is_not_double_counted(self):
        data = rows(('2026-11-15', 'TOTAL', 100.0),
                    ('2026-11-15', 'Ethereum', 60.0),
                    ('2026-11-15', 'Solana', 40.0))
        point = tvl.latest(data)
        assert point is not None
        self.assertEqual(100.0, point.value)
        self.assertEqual('total', point.source)
        self.assertFalse(point.partial)

    def test_missing_total_falls_back_to_chains_and_is_flagged(self):
        data = rows(('2026-11-16', 'Ethereum', 60.0),
                    ('2026-11-16', 'Solana', 40.0))
        point = tvl.latest(data)
        assert point is not None
        self.assertEqual(100.0, point.value)
        self.assertEqual('chains', point.source)
        self.assertTrue(point.partial, 'a chain-only day must be marked partial')

    def test_duplicate_total_rows_collapse_to_one(self):
        data = rows(('2026-11-15', 'TOTAL', 100.0),
                    ('2026-11-15', 'TOTAL', 101.0),
                    ('2026-11-15', 'Ethereum', 60.0))
        points = tvl.aggregate(data)
        self.assertEqual(1, len(points))
        self.assertEqual(101.0, points[0].value, 'the last TOTAL wins')

    def test_historical_series_is_ordered_and_complete(self):
        data = rows(('2026-11-14', 'TOTAL', 90.0),
                    ('2026-11-15', 'TOTAL', 95.0),
                    ('2026-11-16', 'TOTAL', 100.0))
        points = tvl.aggregate(data)
        self.assertEqual(['2026-11-14', '2026-11-15', '2026-11-16'],
                         [p.date for p in points])
        self.assertEqual(100.0, points[-1].value)

    def test_change_uses_the_source_date_not_the_collection_date(self):
        data = rows(('2026-11-09', 'TOTAL', 100.0),
                    ('2026-11-16', 'TOTAL', 90.0))
        points = tvl.aggregate(data)
        change = tvl.change_pct(points, 7)
        assert change is not None
        self.assertAlmostEqual(-10.0, change, places=6)

    def test_change_is_none_without_enough_history(self):
        points = tvl.aggregate(rows(('2026-11-16', 'TOTAL', 90.0)))
        self.assertIsNone(tvl.change_pct(points, 7))

    def test_change_is_refused_when_the_newest_day_is_partial(self):
        data = rows(('2026-11-09', 'TOTAL', 100.0),
                    ('2026-11-16', 'Ethereum', 60.0))
        points = tvl.aggregate(data)
        self.assertIsNone(tvl.change_pct(points, 7),
                          'a partial day must not produce a change percentage')

    def test_off_by_one_date_is_detected(self):
        self.assertTrue(tvl.date_mismatch('2026-11-14', '2026-11-15'))
        self.assertFalse(tvl.date_mismatch('2026-11-15', '2026-11-15'))
        self.assertFalse(tvl.date_mismatch(None, '2026-11-15'))

    def test_none_values_are_ignored(self):
        data = rows(('2026-11-16', 'TOTAL', None),
                    ('2026-11-16', 'Ethereum', 60.0))
        point = tvl.latest(data)
        assert point is not None
        self.assertEqual(60.0, point.value)
        self.assertTrue(point.partial)

    def test_latest_complete_skips_a_partial_newest_day(self):
        data = rows(('2026-11-15', 'TOTAL', 100.0),
                    ('2026-11-16', 'Ethereum', 60.0),
                    ('2026-11-16', 'Solana', 40.0))
        points = tvl.aggregate(data)
        headline = tvl.latest_complete(points)
        assert headline is not None
        self.assertEqual('2026-11-15', headline.date)
        self.assertEqual(100.0, headline.value)
        self.assertFalse(headline.partial)

    def test_change_can_be_anchored_to_the_complete_day(self):
        data = rows(('2026-11-08', 'TOTAL', 100.0),
                    ('2026-11-15', 'TOTAL', 90.0),
                    ('2026-11-16', 'Ethereum', 60.0))
        points = tvl.aggregate(data)
        headline = tvl.latest_complete(points)
        assert headline is not None
        change = tvl.change_pct(points, 7, end=headline)
        assert change is not None
        self.assertAlmostEqual(-10.0, change, places=6)
        # without the anchor the partial newest day still refuses a percentage
        self.assertIsNone(tvl.change_pct(points, 7))


if __name__ == '__main__':
    unittest.main(verbosity=2)
