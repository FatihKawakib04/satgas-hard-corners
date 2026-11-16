"""Regression tests for the lab cycle generator.

Run from site/research: python3 -m unittest tests.test_lab_cycle -v
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lab"))

import cycle          # noqa: E402
import store          # noqa: E402
import strategies as S  # noqa: E402


def _ctx(prices):
    return type("Ctx", (), {"dates": [str(i) for i in range(len(prices))],
                            "prices": {"BTC": prices}})()


class TestGridDomain(unittest.TestCase):
    def test_percentile_is_clamped_to_1_100(self):
        grid = cycle._grid_dari({"lookback": 180, "pct_max": 70}, set())
        self.assertTrue(grid)
        for params in grid:
            self.assertGreaterEqual(params["pct_max"], 1)
            self.assertLessEqual(params["pct_max"], 100,
                                 f"pct_max {params['pct_max']} keluar rentang")

    def test_used_combination_is_not_repeated(self):
        base = {"lookback": 100, "pct_max": 50}
        first = cycle._grid_dari(base, set())
        self.assertTrue(first)
        used = {cycle._kunci_params(first[0])}
        second = cycle._grid_dari(base, used)
        self.assertNotIn(cycle._kunci_params(first[0]),
                         {cycle._kunci_params(p) for p in second})

    def test_all_combinations_used_returns_empty(self):
        base = {"lookback": 100, "pct_max": 50}
        used = {cycle._kunci_params(p) for p in cycle._grid_dari(base, set())}
        self.assertEqual([], cycle._grid_dari(base, used))


class TestMomVolPercentile(unittest.TestCase):
    def test_out_of_range_percentile_does_not_raise(self):
        prices = [100.0 * (1.0 + 0.0005 * i) for i in range(700)]
        out = S.mom_vol(_ctx(prices), {"lookback": 90, "pct_max": 112})
        self.assertEqual(len(prices), len(out))
        self.assertIn(out[-1], ({}, {"BTC": 1.0}))

    def test_zero_percentile_does_not_raise(self):
        prices = [100.0 * (1.0 + 0.0005 * i) for i in range(700)]
        out = S.mom_vol(_ctx(prices), {"lookback": 90, "pct_max": 0})
        self.assertEqual(len(prices), len(out))


class TestFailedExperimentsAreNotRepeated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "lab.db")
        con = store.connect(self.db)
        con.execute("INSERT INTO lab_exp (id, strategi, status, keputusan, wf_sharpe) "
                    "VALUES ('E01','mom_vol','selesai','gagal',0.4)")
        con.execute("INSERT INTO lab_exp (id, strategi, status, keputusan, wf_sharpe) "
                    "VALUES ('E02','mom_vol','selesai','gagal',0.3)")
        con.execute("INSERT INTO lab_runs (exp_id, strategi, params, oos_sharpe) "
                    "VALUES ('E01','mom_vol',?,0.4)",
                    (json.dumps({"lookback": 180, "pct_max": 70}),))
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

    def test_failed_queue_entries_count_toward_the_limit(self):
        failed = [{"id": f"E{n:02d}", "strategi": "mom_vol", "status": "error",
                   "grid": [{"lookback": 108, "pct_max": 42}]}
                  for n in range(3, 6)]
        with mock.patch.object(cycle.store, "db", self._db()), \
             mock.patch.object(cycle.X, "load_queue", return_value=failed):
            self.assertIsNone(cycle.turunan(),
                              "mom_vol sudah 2 sukses + 3 gagal, harus dilewati")

    def test_failed_grid_is_treated_as_used(self):
        failed = [{"id": "E03", "strategi": "mom_vol", "status": "error",
                   "grid": [{"lookback": 108, "pct_max": 42}]}]
        with mock.patch.object(cycle.store, "db", self._db()), \
             mock.patch.object(cycle.X, "load_queue", return_value=failed):
            exp = cycle.turunan()
        if exp is not None:
            self.assertNotIn({"lookback": 108, "pct_max": 42}, exp["grid"])


class TestPaperStepOnFailure(unittest.TestCase):
    def test_paper_step_is_not_called_when_the_experiment_fails(self):
        exp = {"id": "E99", "strategi": "mom_vol", "status": "menunggu",
               "grid": [{"lookback": 90, "pct_max": 50}]}
        with mock.patch.object(cycle.X, "next_experiment", return_value=exp), \
             mock.patch.object(cycle.X, "run_experiment",
                               side_effect=RuntimeError("boom")), \
             mock.patch.object(cycle.X, "mark"), \
             mock.patch.object(cycle.render, "main"), \
             mock.patch.object(cycle, "log_state"), \
             mock.patch.object(cycle.paper, "step") as step:
            rc, text = cycle.siklus(notify=False)
        self.assertEqual(1, rc)
        step.assert_not_called()
        self.assertIn("E99", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
