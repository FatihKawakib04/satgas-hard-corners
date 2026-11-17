"""Uji publikasi TVL dengan mock LLM (tanpa API sungguhan). Tidak menulis ke produksi."""
import copy, json, os, sys, tempfile, unittest
from unittest.mock import patch

sys.path.insert(0, "/var/www/satgas-hard-corners/site/research")
import report as R
import validasi_angka as V

ROOT = "/var/www/satgas-hard-corners/site/research"
FAKTA_PATH = os.path.join(ROOT, "out", "fakta.json")
fakta = json.load(open(FAKTA_PATH))

# TVL kanonis dari fakta.json
TVL_KANONIS = fakta["tvl"]["total_usd"] / 1e9
TVL_SALAH = 86.15  # angka lama yang salah


def _pct(v):
    """Persen opsional: chg kalender bisa None saat tanggal acuan tidak ada."""
    return "n/a" if v is None else f"{v:.2f}%"


def _narrative_benar():
    """Narasi LLM yang benar (salin angka kanonis)."""
    return {
        "judul": "Test",
        "ringkasan": ["ringkasan"],
        "apa_terjadi": ["apa"],
        "mengapa_penting": ["mp"],
        "makro": [],
        "derivatif": [],
        "aliran": [
            f"TVL DeFi total {TVL_KANONIS:.2f} miliar dolar "
            f"(data {fakta['tvl']['tanggal']}), {_pct(fakta['tvl']['chg_7d'])} 7 hari, "
            f"{_pct(fakta['tvl']['chg_30d'])} 30 hari."
        ],
        "skenario": {"dasar": {"prob": 50, "teks": "x"}, "naik": {"prob": 25, "teks": "y"}, "turun": {"prob": 25, "teks": "z"}},
        "risiko": [], "pantau": [], "katalis": [], "fakta": [], "spekulasi": [],
        "keyakinan": {"level": "sedang", "alasan": "test"},
    }


def _narrative_salah():
    """Narasi LLM dengan angka TVL salah."""
    n = _narrative_benar()
    n["aliran"] = [
        f"TVL DeFi total {TVL_SALAH:.2f} miliar dolar "
        f"(data {fakta['tvl']['tanggal']}), {_pct(fakta['tvl']['chg_7d'])} 7 hari, "
        f"{_pct(fakta['tvl']['chg_30d'])} 30 hari."
    ]
    return n


class TestMockLLM(unittest.TestCase):
    """Skenario A/B/C dengan mock LLM."""

    def _run_report(self, llm_return, tmpdir):
        """Jalankan report.main() dengan mock LLM, tangkap exit code."""
        # Patch call_llm untuk return nilai yang ditentukan
        with patch.object(R, "call_llm", return_value=llm_return):
            # Patch OUT_DIR ke tmpdir supaya tidak menulis produksi
            orig_out = R.OUT_DIR
            R.OUT_DIR = tmpdir
            os.makedirs(tmpdir, exist_ok=True)
            # Patch STATE juga
            orig_state = R.STATE
            R.STATE = os.path.join(tmpdir, "state")
            os.makedirs(R.STATE, exist_ok=True)
            # tulis fakta.json ke state
            with open(os.path.join(R.STATE, "fakta.json"), "w") as fh:
                json.dump(fakta, fh)
            try:
                # monkeypatch sys.argv
                import sys as _sys
                old_argv = _sys.argv[:]
                _sys.argv = ["report.py", "--jenis", "harian", "--tanpa-llm"] if llm_return is None else ["report.py", "--jenis", "harian"]
                # Jika llm_return bukan None, kita tetap perlu bypass --tanpa-llm
                if llm_return is not None:
                    _sys.argv = ["report.py", "--jenis", "harian"]
                # patch analyze.build untuk return fakta
                with patch.object(R.analyze, "build", return_value=copy.deepcopy(fakta)):
                    rc = R.main()
                _sys.argv = old_argv
                return rc
            finally:
                R.OUT_DIR = orig_out
                R.STATE = orig_state
                _sys.argv = old_argv

    def test_A_llm_salah_fallback_benar(self):
        """Skenario A: LLM salah → fallback benar → lolos."""
        tmpdir = tempfile.mkdtemp()
        rc = self._run_report(_narrative_salah(), tmpdir)
        # fallback harus menghasilkan angka benar
        md_files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
        self.assertTrue(len(md_files) > 0, "file .md harus ada")
        # cek angka di file
        md_path = os.path.join(tmpdir, md_files[0])
        teks = open(md_path).read()
        kanonis = f"{TVL_KANONIS:.2f}".replace(".", ",")
        self.assertIn(kanonis, teks, "TVL harus kanonis di MD")
        # validasi lulus
        masalah = V.validasi_laporan(md_path, fakta)
        self.assertEqual(masalah, [], f"validasi harus lulus: {masalah}")

    def test_B_llm_benar_lolos(self):
        """Skenario B: LLM benar → lolos validasi."""
        tmpdir = tempfile.mkdtemp()
        rc = self._run_report(_narrative_benar(), tmpdir)
        md_files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
        self.assertTrue(len(md_files) > 0, "file .md harus ada")
        md_path = os.path.join(tmpdir, md_files[0])
        teks = open(md_path).read()
        self.assertIn(f"{TVL_KANONIS:.2f}", teks)
        masalah = V.validasi_laporan(md_path, fakta)
        self.assertEqual(masalah, [], f"validasi harus lulus: {masalah}")

    def test_C_llm_gagal_fallback_gagal_abort(self):
        """Skenario C: LLM gagal + fallback invalid → abort exit 2."""
        # Patch fallback_narrative untuk menghasilkan angka salah
        def bad_fallback(f):
            n = _narrative_benar()
            n["aliran"] = [
                f"TVL DeFi total {TVL_SALAH:.2f} miliar dolar "
                f"(data {fakta['tvl']['tanggal']}), {_pct(fakta['tvl']['chg_7d'])} 7 hari, "
                f"{_pct(fakta['tvl']['chg_30d'])} 30 hari."
            ]
            n["_fallback"] = True
            return n

        tmpdir = tempfile.mkdtemp()
        with patch.object(R, "fallback_narrative", side_effect=bad_fallback):
            with patch.object(R, "call_llm", return_value=None):
                orig_out = R.OUT_DIR
                R.OUT_DIR = tmpdir
                os.makedirs(tmpdir, exist_ok=True)
                orig_state = R.STATE
                R.STATE = os.path.join(tmpdir, "state")
                os.makedirs(R.STATE, exist_ok=True)
                with open(os.path.join(R.STATE, "fakta.json"), "w") as fh:
                    json.dump(fakta, fh)
                import sys as _sys
                old_argv = _sys.argv[:]
                _sys.argv = ["report.py", "--jenis", "harian"]
                with patch.object(R.analyze, "build", return_value=copy.deepcopy(fakta)):
                    rc = R.main()
                _sys.argv = old_argv
                R.OUT_DIR = orig_out
                R.STATE = orig_state

        self.assertEqual(rc, 2, "harus abort dengan exit code 2")
        # file tidak boleh dipublikasikan
        md_files = [f for f in os.listdir(tmpdir) if f.endswith(".md") and not f.startswith(".")]
        self.assertEqual(len(md_files), 0, "tidak boleh ada file .md terpublikasi")


class TestCalendarChg(unittest.TestCase):
    """Unit test chg() dengan tanggal kosong."""

    def test_chg_normal(self):
        series = [("2026-11-01", 100.0), ("2026-11-02", 110.0)]
        # 1 hari kalender
        r = R.analyze.chg(series, 1)
        self.assertAlmostEqual(r, 10.0, places=1)

    def test_chg_missing_date_returns_none(self):
        # data hanya ada di 11-01 dan 11-03, minta 1 hari dari 11-03 → 11-02 tidak ada
        series = [("2026-11-01", 100.0), ("2026-11-03", 110.0)]
        r = R.analyze.chg(series, 1)
        self.assertIsNone(r, "harus None jika tanggal pembanding tidak ada")

    def test_chg_7d_missing_returns_none(self):
        series = [("2026-10-20", 100.0), ("2026-11-02", 110.0)]
        # 7 hari dari 11-02 = 10-26, tidak ada
        r = R.analyze.chg(series, 7)
        self.assertIsNone(r, "harus None jika 7 hari pembanding tidak ada")


class TestMDHTMLConsistency(unittest.TestCase):
    """Pastikan angka TVL sama di MD dan HTML."""

    def test_consistency(self):
        tmpdir = tempfile.mkdtemp()
        rc = self._run_helper(tmpdir)
        # cari file
        md_files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
        html_files = [f for f in os.listdir(tmpdir) if f.endswith(".html")]
        self.assertTrue(md_files and html_files)
        md_text = open(os.path.join(tmpdir, md_files[0])).read()
        html_text = open(os.path.join(tmpdir, html_files[0])).read()
        # extract TVL number from both
        import re
        md_m = re.search(r"TVL DeFi total ([\d,\.]+) miliar", md_text)
        html_m = re.search(r"TVL DeFi total ([\d,\.]+) miliar", html_text)
        self.assertIsNotNone(md_m)
        self.assertIsNotNone(html_m)
        self.assertEqual(md_m.group(1), html_m.group(1), "TVL harus sama di MD dan HTML")

    def _run_helper(self, tmpdir):
        n = _narrative_benar()
        with patch.object(R, "call_llm", return_value=n):
            orig_out = R.OUT_DIR
            R.OUT_DIR = tmpdir
            os.makedirs(tmpdir, exist_ok=True)
            orig_state = R.STATE
            R.STATE = os.path.join(tmpdir, "state")
            os.makedirs(R.STATE, exist_ok=True)
            with open(os.path.join(R.STATE, "fakta.json"), "w") as fh:
                json.dump(fakta, fh)
            import sys as _sys
            old_argv = _sys.argv[:]
            _sys.argv = ["report.py", "--jenis", "harian"]
            with patch.object(R.analyze, "build", return_value=copy.deepcopy(fakta)):
                rc = R.main()
            _sys.argv = old_argv
            R.OUT_DIR = orig_out
            R.STATE = orig_state
            return rc


if __name__ == "__main__":
    unittest.main(verbosity=2)
PY