#!/usr/bin/env python3
"""Penjaga macet siklus lab.

cycle.py bisa keluar dengan kode 0 tetapi TIDAK menghasilkan eksperimen baru
(antrean habis dan generator turunan buntu). Kondisi itu dulu diam total selama
4 hari (25-29 Okt 2026) karena tidak ada yang membedakan "siklus jalan normal"
dari "siklus jalan tapi tidak berbuat apa-apa".

Skrip ini mencetak peringatan HANYA kalau siklus produktif terakhir lebih tua
dari ambang (default 6 jam, target jadwal 3 jam) dan peringatan terakhir sudah
lebih dari 24 jam. Diam kalau sehat.

Dipakai crypto-lab.sh setelah cycle.py; tidak perlu cron sendiri.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "cycle_state.json")
STAMP = os.path.join(HERE, ".stall_alert")
AMBANG_JAM = float(os.environ.get("LAB_STALL_JAM", "6"))
JEDA_ALERT = float(os.environ.get("LAB_STALL_JEDA_JAM", "24"))


def umur_jam() -> float | None:
    try:
        with open(STATE) as f:
            t = datetime.fromisoformat(json.load(f)["terakhir"]["waktu"])
    except (OSError, KeyError, ValueError, TypeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0


def antrean() -> str:
    try:
        with open(os.path.join(HERE, "queue.json")) as f:
            q = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "queue.json tidak terbaca"
    n = sum(1 for e in q if e.get("status") == "menunggu")
    return f"{n} menunggu dari {len(q)} eksperimen di antrean"


def main() -> int:
    umur = umur_jam()
    if umur is None:
        print("Lab riset: riwayat siklus tidak terbaca, tidak bisa memastikan siklus jalan.")
        return 0
    if umur < AMBANG_JAM:
        return 0
    now = datetime.now(timezone.utc).timestamp()
    try:
        with open(STAMP) as f:
            terakhir_alert = float(f.read().strip())
    except (OSError, ValueError):
        terakhir_alert = 0.0
    if now - terakhir_alert < JEDA_ALERT * 3600:
        return 0
    print(f"Lab riset macet: siklus produktif terakhir {umur:.1f} jam lalu "
          f"(target maksimal 3 jam).")
    print(f"Antrean: {antrean()}.")
    print("Cek cycle.py: generator turunan harus memilih strategi yang ada di "
          "strategies.KATALOG, dan id baru tidak boleh bertabrakan dengan queue.json.")
    try:
        with open(STAMP, "w") as f:
            f.write(str(now))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
