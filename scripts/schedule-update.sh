#!/usr/bin/env bash
# Entropia V18 — install a DAILY auto-update cron job for THIS checkout.
# The repo path is detected automatically, so there is nothing to edit.
#   ./scripts/schedule-update.sh [HH:MM]    # default 09:00 (re-run to change time)
#   ./scripts/schedule-update.sh --remove   # remove the daily job
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
marker="# entropia-auto-update"

if [ "${1:-}" = "--remove" ]; then
  { crontab -l 2>/dev/null | grep -v "$marker" || true; } | crontab -
  echo "Removed the Entropia daily auto-update job."
  exit 0
fi

when="${1:-09:00}"
hour=$(( 10#${when%%:*} ))
minute=$(( 10#${when##*:} ))

# The trailing '#' marker is a shell comment inside the cron command — harmless,
# and it lets us find/replace our own line idempotently.
line="$minute $hour * * * cd $repo_root && ./scripts/update.sh >> $repo_root/update.log 2>&1 $marker"
{ crontab -l 2>/dev/null | grep -v "$marker" || true; echo "$line"; } | crontab -

printf 'Installed daily Entropia auto-update at %02d:%02d.\n' "$hour" "$minute"
echo "Repo: $repo_root"
echo "Log:  $repo_root/update.log"
echo "Change time: ./scripts/schedule-update.sh 21:30   |   Remove: ./scripts/schedule-update.sh --remove"
