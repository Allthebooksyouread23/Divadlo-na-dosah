#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/theatre_scraper.log"
CRON_TAG="divadlo-infotable-scraper"
CRON_SCHEDULE="0 13 * * 0"
CRON_COMMAND="cd \"$SCRIPT_DIR\" && python3 src/scraper.py >> \"$LOG_FILE\" 2>&1"
CRON_ENTRY="$CRON_SCHEDULE $CRON_COMMAND # $CRON_TAG"

TEMP_FILE="$(mktemp)"
cleanup() {
    rm -f "$TEMP_FILE"
}

trap cleanup EXIT

crontab -l 2>/dev/null | grep -v "$CRON_TAG" > "$TEMP_FILE" || true
echo "$CRON_ENTRY" >> "$TEMP_FILE"
crontab "$TEMP_FILE"

echo "Installed weekly scraper cron job for Sundays at 13:00."