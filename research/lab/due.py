#!/usr/bin/env python3
"""Cek apakah siklus lab sudah jatuh tempo (dipakai wrapper cron 15 menit).

Keluar 0 kalau sudah lebih dari `jam` sejak siklus terakhir, 1 kalau belum.
Dengan cara ini jadwal tidak bergantung pada satu tick cron tertentu: kalau
gateway sempat mati atau satu tick terlewat, siklus tetap menyusul di tick
berikutnya tanpa menunggu enam jam.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "cycle_state.json")
FORCE = os.path.join(DIR, ".force_cycle")
JAM = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0

# penanda untuk menjalankan siklus di luar jadwal (riset atas permintaan)
if os.path.exists(FORCE):
    os.remove(FORCE)
    sys.exit(0)

try:
    with open(STATE) as f:
        terakhir = json.load(f)["terakhir"]["waktu"]
    t = datetime.fromisoformat(terakhir)
except (OSError, KeyError, ValueError):
    sys.exit(0)          # belum pernah jalan: jalankan sekarang

if t.tzinfo is None:
    t = t.replace(tzinfo=timezone.utc)
umur = datetime.now(timezone.utc) - t
sys.exit(0 if umur > timedelta(hours=JAM) else 1)
