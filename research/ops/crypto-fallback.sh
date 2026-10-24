#!/bin/bash
# Jaring pengaman riset: menjalankan pekerjaan inti saat scheduler Hermes tidak
# berdenyut (gateway restart, macet, atau sesi berakhir).
#
# Kenapa tidak me-restart gateway: proses gateway dijaga systemd dengan
# Restart=always, jadi crash sudah pulih sendiri. Yang perlu ditutup adalah
# celah "proses hidup tapi scheduler tidak jalan": di kondisi itu skrip ini
# mengambil alih pekerjaan yang tidak butuh LLM.
#
# Normal: keluar diam dalam <1 detik karena ticker masih segar.
set -u

LOG=/var/log/crypto-fallback.log
TICKER=/root/.hermes/cron/ticker_last_success
R=/var/www/satgas-hard-corners/site/research
LOCK=/run/crypto-fallback.lock

say() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

[ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 524288 ] && mv "$LOG" "$LOG.1"

AKTIF=$(systemctl is-active hermes-gateway.service 2>/dev/null)
TICK=$(cut -d. -f1 "$TICKER" 2>/dev/null || echo 0)
[ -z "${TICK:-}" ] && TICK=0
UMUR=$(( $(date +%s) - TICK ))

# gateway sehat dan scheduler berdenyut: tidak ada yang perlu dilakukan
if [ "$AKTIF" = "active" ] && [ "$UMUR" -lt 900 ]; then
  exit 0
fi

exec 9>"$LOCK" || exit 0
flock -n 9 || exit 0

say "fallback aktif (gateway=$AKTIF, ticker ${UMUR}s)"
cd "$R" || exit 0
timeout 240 python3 collect.py --snapshot >/dev/null 2>&1 && say "snapshot ok"
timeout 240 python3 collect.py --news >/dev/null 2>&1 && say "berita ok"
cd "$R/lab" || exit 0
if python3 due.py 3; then
  timeout 300 python3 cycle.py >>"$LOG" 2>&1 && say "siklus lab ok"
fi
timeout 120 python3 paper.py >/dev/null 2>&1 && say "paper ok"
exit 0
