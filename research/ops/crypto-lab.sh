#!/bin/bash
# Satu siklus lab riset: ambil satu eksperimen dari antrean, uji, publikasikan.
# Dipanggil tiap 15 menit tetapi hanya bekerja kalau siklus terakhir > 6 jam,
# supaya tick cron yang terlewat (gateway restart) tetap menyusul di tick berikutnya.
# Diam kalau tidak ada temuan penting; cron mengirim stdout apa adanya.
set -u
cd /var/www/satgas-hard-corners/site/research/lab || exit 1
python3 due.py 3 || exit 0
out=$(timeout 300 python3 cycle.py 2>&1)
rc=$?
if [ $rc -ne 0 ]; then
  echo "Lab riset gagal (exit $rc):"
  echo "$out" | tail -10
  exit 0
fi
if [ -n "$out" ]; then echo "$out"; fi
# arsipkan halaman lab ke repo
REPO=/var/www/satgas-hard-corners/site
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$REPO" add research/reports/lab.html research/reports/peluang.html \
    research/lab/queue.json research/lab/paper_state.json \
    research/lab/cycle_state.json >/dev/null 2>&1
  if ! git -C "$REPO" diff --cached --quiet; then
    TGL=$(TZ=Asia/Jakarta date +%Y-%m-%d)
    git -C "$REPO" commit -q -m "chore(lab): siklus riset $TGL" >/dev/null 2>&1
    git -C "$REPO" push -q origin main >/dev/null 2>&1 || true
  fi
fi
exit 0
