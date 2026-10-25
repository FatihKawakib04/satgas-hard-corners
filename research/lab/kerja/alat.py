#!/usr/bin/env python3
"""Alat kerja: menyiapkan folder proyek klien dan memeriksa kesiapan serah terima.

Dua perintah:

  python3 alat.py baru <nama>     # scaffold proyek dengan README, tes, dan checklist
  python3 alat.py periksa <nama>  # jalankan pemeriksaan sebelum diserahkan

Pemeriksaan mengecek hal yang paling sering terlewat: kode tidak bisa diimpor,
tidak ada tes, tidak ada cara menjalankan, tidak ada batas penerimaan, dan data
rahasia yang ikut terkirim.
"""
from __future__ import annotations

import os
import py_compile
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERJA = os.path.dirname(HERE)

README = """# {nama}

Proyek klien. Dokumen ini ditulis untuk orang yang menerima hasilnya, bukan untuk
pembuatnya.

## Apa yang dikerjakan

-

## Cara menjalankan

```bash
pip install -r requirements.txt
python src/main.py --input data/contoh.csv
```

## Struktur

```
src/        kode
tests/      tes otomatis
data/       contoh data, bukan data klien
docs/       catatan metode dan keputusan
```

## Batas penerimaan

Isi `acceptance.md`. Setiap butir harus bisa diperiksa dengan perintah, bukan opini.

## Yang tidak termasuk

-
"""

ACCEPTANCE = """# Kriteria penerimaan: {nama}

Setiap butir harus bisa dijawab ya atau tidak, tanpa debat.

- [ ] Perintah di README berjalan tanpa error pada mesin bersih
- [ ] Ada minimal satu tes otomatis yang gagal kalau logika inti dirusak
- [ ] Hasil bisa direproduksi: menjalankan ulang pada data yang sama menghasilkan
      angka yang sama
- [ ] Sumber data dan tanggal pengambilan tercatat di keluaran
- [ ] Kalau sumber data gagal, program berhenti dengan pesan jelas, bukan diam
- [ ] Tidak ada kredensial atau data pribadi di dalam paket
"""

HANDOFF = """# Serah terima: {nama}

- [ ] Kode diserahkan sebagai arsip atau repositori, bukan folder di mesin saya
- [ ] README menjelaskan cara menjalankan
- [ ] acceptance.md terisi dan semua butir tercentang
- [ ] Tidak ada kunci API di dalam paket
- [ ] Klien sudah menjalankan sendiri minimal sekali
- [ ] Catatan metode diserahkan (docs/metode.md)
"""

TEST = '''"""Tes dasar. Ganti dengan tes yang benar-benar menguji logika inti.

Ditulis dengan unittest supaya jalan tanpa memasang apa pun. pytest juga bisa
menjalankan berkas ini kalau nanti dipakai.
"""
import unittest


def tambah(a: int, b: int) -> int:
    return a + b


class TesDasar(unittest.TestCase):
    def test_tambah(self):
        self.assertEqual(tambah(2, 3), 5)
'''

MAIN = '''#!/usr/bin/env python3
"""Titik masuk. Ganti dengan logika proyek."""
import argparse


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=False, help="berkas masukan")
    a = p.parse_args()
    print(f"masukan: {a.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

METODE = """# Metode

Tulis di sini: sumber data, asumsi, rumus, dan keputusan yang diambil beserta alasannya.
Bagian ini yang membuat hasil bisa dipertanggungjawabkan setelah proyek selesai.
"""


def baru(nama: str) -> int:
    root = os.path.join(HERE, nama)
    if os.path.exists(root):
        print(f"{nama} sudah ada")
        return 1
    for sub in ("src", "tests", "data", "docs"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    berkas = {
        "README.md": README.format(nama=nama),
        "acceptance.md": ACCEPTANCE.format(nama=nama),
        "SERAH_TERIMA.md": HANDOFF.format(nama=nama),
        "docs/metode.md": METODE,
        "src/main.py": MAIN,
        "tests/test_dasar.py": TEST,
        "requirements.txt": "pytest\n",
        ".gitignore": "__pycache__/\n*.pyc\n.env\ndata/klien/\n",
    }
    for path, isi in berkas.items():
        with open(os.path.join(root, path), "w") as f:
            f.write(isi)
    print(f"proyek {nama} disiapkan di {root}")
    return 0


def periksa(nama: str) -> int:
    root = os.path.join(HERE, nama)
    if not os.path.isdir(root):
        print(f"{nama} tidak ada")
        return 1
    masalah, catatan = [], []

    py = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".py")]
    if not py:
        masalah.append("tidak ada berkas .py")
    for path in py:
        try:
            py_compile.compile(path, doraise=True)
        except Exception as e:
            masalah.append(f"gagal dikompilasi: {os.path.relpath(path, root)} ({e})")

    tes = [p for p in py if os.sep + "tests" + os.sep in p]
    if not tes:
        masalah.append("tidak ada tes otomatis")

    for wajib in ("README.md", "acceptance.md", "docs/metode.md"):
        if not os.path.exists(os.path.join(root, wajib)):
            masalah.append(f"tidak ada {wajib}")

    acc = ""
    if os.path.exists(os.path.join(root, "acceptance.md")):
        acc = open(os.path.join(root, "acceptance.md")).read()
        sisa = len(re.findall(r"- \[ \]", acc))
        if sisa:
            masalah.append(f"{sisa} butir penerimaan belum dicentang")

    rahasia = re.compile(r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,}|api[_-]?key\s*=\s*['\"][^'\"]{8,})")
    for path in py + [os.path.join(root, f) for f in os.listdir(root) if f.endswith((".md", ".txt"))]:
        try:
            if rahasia.search(open(path, errors="ignore").read()):
                masalah.append(f"kemungkinan kredensial di {os.path.relpath(path, root)}")
        except OSError:
            pass

    if os.path.exists(os.path.join(root, "tests")):
        # pytest kalau ada, kalau tidak pakai unittest bawaan Python
        cek = subprocess.run([sys.executable, "-m", "pytest", "--version"],
                             capture_output=True)
        if cek.returncode == 0:
            cmd, nama_alat = [sys.executable, "-m", "pytest", "-q", "tests"], "pytest"
        else:
            cmd, nama_alat = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], "unittest"
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        gabung = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            masalah.append(f"{nama_alat} gagal: " + (gabung.splitlines()[-1] if gabung else "tanpa keluaran"))
        else:
            catatan.append(f"{nama_alat} lulus")

    print(f"pemeriksaan {nama}: {len(py)} berkas python, {len(tes)} berkas tes")
    for c in catatan:
        print("  ok:", c)
    if masalah:
        print("  masalah:")
        for m in masalah:
            print("   -", m)
        return 1
    print("  siap diserahkan")
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == "baru":
        return baru(sys.argv[2])
    if sys.argv[1] == "periksa":
        return periksa(sys.argv[2])
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
