"""Uji validasi integritas angka (research). Tidak menulis apa pun ke produksi."""
import copy
import json
import os
import sys

sys.path.insert(0, "/var/www/satgas-hard-corners/site/research")
import validasi_angka as V

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), "-", name, ("| " + str(detail)) if not cond else "")


fakta = json.load(open("/var/www/satgas-hard-corners/site/research/out/fakta.json"))

print("=" * 66)
print("A. VALIDATOR TERHADAP DATA NYATA")
print("=" * 66)

m = V.validasi_fakta(fakta)
check("fakta.json saat ini lolos validasi", not m, m)

print()
print("=" * 66)
print("B. VALIDATOR HARUS MENOLAK ANGKA YANG MENYIMPANG")
print("=" * 66)

# 1. Nilai TVL diganti angka lama 86,15B (kasus nyata yang dilaporkan Fatih).
f1 = copy.deepcopy(fakta)
f1["tvl"]["total_usd"] = 86_153_854_382.0
m1 = V.validasi_fakta(f1)
kode = [x["kode"] for x in m1]
check("TVL 86,15B (angka lama) ditolak", "tvl_nilai_tidak_cocok" in kode, kode)

# 2. chg_7d dimanipulasi.
f2 = copy.deepcopy(fakta)
f2["tvl"]["chg_7d"] = -6.38
m2 = V.validasi_fakta(f2)
check("chg_7d yang tidak cocok ditolak",
      any(x["kode"] == "tvl_chg_7d_tidak_cocok" for x in m2), [x["kode"] for x in m2])

# 3. Tanggal digeser ke tanggal yang tidak ada di deret.
f3 = copy.deepcopy(fakta)
f3["stablecoin"]["tanggal"] = "2026-10-28"
m3 = V.validasi_fakta(f3)
check("Tanggal tidak sinkron dengan nilai ditolak",
      any(x["kode"] == "stablecoin_nilai_tidak_cocok" for x in m3), [x["kode"] for x in m3])

# 4. Tanggal fiktif.
f4 = copy.deepcopy(fakta)
f4["stablecoin"]["tanggal"] = "2026-13-45"
m4 = V.validasi_fakta(f4)
check("Tanggal fiktif ditolak",
      any("tanggal_tidak_ada" in x["kode"] for x in m4), [x["kode"] for x in m4])

# 5. Blok stablecoin hilang.
f5 = copy.deepcopy(fakta)
f5.pop("stablecoin", None)
m5 = V.validasi_fakta(f5)
check("Stablecoin hilang terdeteksi",
      any(x["kode"] == "stablecoin_hilang" for x in m5), [x["kode"] for x in m5])

# 6. Selisih kecil (0,05%) masih lolos.
f6 = copy.deepcopy(fakta)
f6["tvl"]["total_usd"] *= 1.0005
check("Selisih 0,05% masih lolos", not V.validasi_fakta(f6), V.validasi_fakta(f6))

print()
print("=" * 66)
print("C. VALIDATOR TEKS LAPORAN")
print("=" * 66)

# Laporan nyata 30 Okt memuat TVL 86,15B (salah) -> harus ditolak terhadap fakta benar.
laporan_lama = "/var/www/satgas-hard-corners/site/research/reports/harian-2026-10-30.md"
if os.path.exists(laporan_lama):
    ml = V.validasi_laporan(laporan_lama, fakta)
    check("Laporan 30 Okt (TVL 86,15B) ditolak", any("tvl" in x["kode"] for x in ml),
          [x["kode"] for x in ml])

# Laporan sintetis dengan angka benar -> lolos.
tmp = "/tmp/laporan_benar.md"
tvl_b = fakta["tvl"]["total_usd"] / 1e9
stb_b = fakta["stablecoin"]["total_usd"] / 1e9
with open(tmp, "w") as fh:
    fh.write("Suplai stablecoin %.2f miliar dolar (data x).\n" % stb_b)
    fh.write("TVL DeFi total %.2f miliar dolar (data x).\n" % tvl_b)
check("Laporan dengan angka benar lolos", not V.validasi_laporan(tmp, fakta),
      V.validasi_laporan(tmp, fakta))

print()
print("=" * 66)
print("D. SATUAN KOMPONEN REZIM")
print("=" * 66)

k = fakta["rezim"]["komponen"]
btc = fakta["koin"]["BTC"]
harap = btc["vs_ma200"] * 100
check("btc_vs_ma200_pct dalam PERSEN (bukan fraksi)",
      abs(k["btc_vs_ma200_pct"] - harap) < 0.01,
      "komponen=%s harap=%s" % (k.get("btc_vs_ma200_pct"), harap))
check("spx_vs_ma50_pct dalam PERSEN",
      abs(k["spx_vs_ma50_pct"]) < 50, k["spx_vs_ma50_pct"])
check("Semua komponen rezim bersatuan persen/bps yang wajar",
      all(isinstance(v, (int, float)) and abs(v) < 200 for v in k.values()), k)

# Drawdown harus berada di rentang -100%..0% (persen, bukan fraksi).
dd = {s: c.get("drawdown_dari_puncak") for s, c in fakta["koin"].items()
      if c.get("drawdown_dari_puncak") is not None}
check("drawdown_dari_puncak dalam rentang -100..0 (persen)",
      all(-100.0 <= v <= 0.0 for v in dd.values()),
      {s: v for s, v in dd.items() if not (-100.0 <= v <= 0.0)})

print()
n = sum(1 for _, c, _ in R if c)
print("=== %d/%d PASSED ===" % (n, len(R)))
for nm, c, d in R:
    if not c:
        print("  FAIL:", nm, d)
sys.exit(0 if n == len(R) else 1)
