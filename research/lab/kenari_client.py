#!/usr/bin/env python3
"""Klien Kenari dengan anggaran harian dan retry yang menghormati Retry-After.

Kenari free tier membatasi 5 request per menit dan 50 per hari per akun
(dari endpoint pricing publik, 25 Okt 2026). Model gratis juga berbagi kuota
akun yang sama, jadi ganti model tidak menambah jatah.

Modul ini dipakai untuk jalur cadangan: hanya dipanggil kalau model utama gagal,
dengan anggaran kecil supaya kuota tidak habis oleh percobaan otomatis. Setiap
pemakaian dicatat di state file agar sisa anggaran bisa diperiksa kapan saja.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import time
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
STATE = "/root/.hermes/cache/kenari_budget.json"
API = "https://kenari.id/v1/chat/completions"
ENV = "/root/.hermes/.env"
ANGGARAN_HARIAN = 10          # sengaja jauh di bawah 50 supaya ada sisa untuk manual
MAX_PERCOBAAN = 3
RETRYABLE = ("rate_limit_exceeded", "free_quota_rpm", "upstream_error", "all_providers_failed")


def _key() -> str:
    for line in open(ENV, errors="ignore"):
        if line.startswith("KENARI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("KENARI_API_KEY tidak ada di .env")


def _state() -> dict:
    hari = datetime.now(WIB).strftime("%Y-%m-%d")
    if os.path.exists(STATE):
        try:
            s = json.load(open(STATE))
            if s.get("hari") == hari:
                return s
        except Exception:
            pass
    return {"hari": hari, "terpakai": 0, "gagal": 0, "riwayat": []}


def _simpan(s: dict) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


def sisa() -> int:
    return max(0, ANGGARAN_HARIAN - _state()["terpakai"])


def chat(pesan: str, model: str = "nemotron-3-ultra-550b-a55b:free",
         max_tokens: int = 400, paksa: bool = False) -> dict:
    """Kirim satu pesan. Kembalikan {ok, teks, error, sisa}.

    paksa=True melewati anggaran, hanya untuk uji manual yang disengaja.
    """
    s = _state()
    if not paksa and s["terpakai"] >= ANGGARAN_HARIAN:
        return {"ok": False, "error": "anggaran_harian_habis", "sisa": 0}

    body = {"model": model, "messages": [{"role": "user", "content": pesan}],
            "max_tokens": max_tokens, "stream": False}
    for percobaan in range(1, MAX_PERCOBAAN + 1):
        r = subprocess.run(["curl", "-s", "-D", "/tmp/kenari_h.txt", "--max-time", "90", API,
                            "-H", f"Authorization: Bearer {_key()}",
                            "-H", "Content-Type: application/json",
                            "-d", json.dumps(body)], capture_output=True, text=True)
        s["terpakai"] += 1
        try:
            d = json.loads(r.stdout)
        except Exception:
            d = {"error": {"code": "parse_fail"}}

        if "error" not in d:
            teks = ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            s["riwayat"].append({"t": datetime.now(WIB).isoformat(timespec="seconds"),
                                 "ok": True, "model": model})
            _simpan(s)
            return {"ok": True, "teks": (teks or "").strip(), "sisa": sisa()}

        kode = str((d.get("error") or {}).get("code"))
        s["gagal"] += 1
        if kode in RETRYABLE and percobaan < MAX_PERCOBAAN:
            jeda = _retry_after() or min(30, 2 ** percobaan) + random.random()
            time.sleep(jeda)
            continue
        s["riwayat"].append({"t": datetime.now(WIB).isoformat(timespec="seconds"),
                             "ok": False, "kode": kode})
        _simpan(s)
        return {"ok": False, "error": kode, "sisa": sisa()}
    return {"ok": False, "error": "habis_percobaan", "sisa": sisa()}


def _retry_after() -> float | None:
    try:
        for line in open("/tmp/kenari_h.txt", errors="ignore"):
            if line.lower().startswith("retry-after:"):
                return float(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return None


if __name__ == "__main__":
    print(f"anggaran harian {ANGGARAN_HARIAN}, sisa {sisa()}")
    if sisa() > 0:
        h = chat("Balas satu kata: siap", max_tokens=10)
        print("uji:", h)
