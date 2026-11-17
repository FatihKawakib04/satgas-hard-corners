"""Tests for the TVL writer's source-date rule.

Run from research/: python3 -m unittest tests.test_collect_tvl -v
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import collect          # noqa: E402
import store            # noqa: E402
import tvl              # noqa: E402


class TestSimpanTvl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "research.db")
        con = store.connect(self.db)
        con.commit()
        con.close()

    def _db(self):
        @contextlib.contextmanager
        def db_tmp(path=self.db):
            con = store.connect(path)
            try:
                yield con
                con.commit()
            finally:
                con.close()
        return db_tmp

    def _run(self, hist, chains):
        with mock.patch.object(collect.store, "db", self._db()), \
             mock.patch.object(collect.S, "tvl_history", return_value=hist), \
             mock.patch.object(collect.S, "chains_tvl", return_value=chains):
            return collect.simpan_tvl()

    def _rows(self, date):
        con = store.connect(self.db)
        try:
            return {r[0]: r[1] for r in con.execute(
                "SELECT chain, tvl FROM tvl WHERE d=?", (date,))}
        finally:
            con.close()

    def test_chain_rows_use_the_total_date_not_the_collection_date(self):
        hist = [("2026-11-14", 74.0), ("2026-11-15", 71.0)]
        chains = [("Ethereum", 40.0), ("Solana", 5.0)]
        result = self._run(hist, chains)
        self.assertEqual("2026-11-15", result["tanggal"])
        self.assertTrue(result["chain_ditulis"])
        rows = self._rows("2026-11-15")
        self.assertEqual(40.0, rows["Ethereum"])
        self.assertEqual(71.0, rows["TOTAL"])
        # no row may be created for a date the source has not published yet
        self.assertEqual({}, self._rows("2026-11-16"))

    def test_existing_chain_snapshot_is_not_overwritten(self):
        hist = [("2026-11-15", 71.0)]
        self._run(hist, [("Ethereum", 40.0)])
        result = self._run(hist, [("Ethereum", 999.0)])
        self.assertFalse(result["chain_ditulis"])
        self.assertEqual(40.0, self._rows("2026-11-15")["Ethereum"])

    def test_chain_rows_are_written_when_total_is_today(self):
        hist = [("2026-11-16", 71.05)]
        result = self._run(hist, [("Ethereum", 37.6)])
        self.assertTrue(result["chain_ditulis"])
        self.assertEqual(37.6, self._rows("2026-11-16")["Ethereum"])

    def test_no_total_means_no_chain_rows(self):
        result = self._run([], [("Ethereum", 40.0)])
        self.assertEqual(0, result["total"])
        self.assertFalse(result["chain_ditulis"])
        con = store.connect(self.db)
        try:
            self.assertEqual(0, con.execute("SELECT COUNT(*) FROM tvl").fetchone()[0])
        finally:
            con.close()

    def test_written_series_has_no_partial_day(self):
        hist = [("2026-11-14", 74.0), ("2026-11-15", 71.0)]
        self._run(hist, [("Ethereum", 40.0), ("Solana", 5.0)])
        con = store.connect(self.db)
        try:
            rows = con.execute("SELECT d, chain, tvl FROM tvl ORDER BY d").fetchall()
        finally:
            con.close()
        points = tvl.aggregate([(r[0], r[1], r[2]) for r in rows])
        self.assertEqual(["2026-11-14", "2026-11-15"], [p.date for p in points])
        self.assertFalse(any(p.partial for p in points))


if __name__ == "__main__":
    unittest.main(verbosity=2)
