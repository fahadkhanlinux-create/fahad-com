#!/usr/bin/env bash
# Continue the library build: render PDFs, then write the manifests and verify.
# Split out of build_library.py so a re-run after an interrupted render does not
# re-do phase 1 and can be left running unattended.
set -u
cd "$(dirname "$0")/.."

export LIB_TARGET="${LIB_TARGET:-5500}"
LOG=logs/finish.log

echo "[$(date +%T)] render phase (procs=${PDF_PROCS:-auto})" | tee -a "$LOG"
nice -n 5 python3 tools/build_library.py >> "$LOG" 2>&1
echo "[$(date +%T)] build_library exit=$?" | tee -a "$LOG"

echo "[$(date +%T)] finalize (manifests + sitemap)" | tee -a "$LOG"
nice -n 5 python3 tools/finalize.py >> "$LOG" 2>&1
echo "[$(date +%T)] finalize exit=$?" | tee -a "$LOG"

echo "[$(date +%T)] verify" | tee -a "$LOG"
nice -n 5 python3 tools/verify.py 2>&1 | tee -a "$LOG"
echo "[$(date +%T)] done" | tee -a "$LOG"