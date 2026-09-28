#!/usr/bin/env bash
# CTQ share-link helper (Git Bash on Windows).
# Starts the backend (if not running) + a free public cloudflared tunnel,
# then prints the shareable URL. The URL changes every time you rerun this.
cd "$(dirname "$0")"

# 0. Tunnel binary — download on first use
if [ ! -f cloudflared.exe ]; then
  echo "Downloading cloudflared..."
  curl -sL -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
fi

# 1. Backend on :8000 — start only if not already listening
if ! netstat -ano | grep ":8000" | grep -q LISTENING; then
  echo "Starting CTQ backend on port 8000..."
  (cd backend && ../.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 > ../uvicorn.log 2>&1 &)
  sleep 6
fi

# 2. Fresh public tunnel
echo "Creating public link (this takes ~10 seconds)..."
rm -f quicktunnel.log
(./cloudflared.exe tunnel --url http://127.0.0.1:8000 --logfile quicktunnel.log > /dev/null 2>&1 &)
for i in $(seq 1 20); do
  URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" quicktunnel.log 2>/dev/null | head -1)
  [ -n "$URL" ] && break
  sleep 2
done

if [ -z "$URL" ]; then
  echo "FAILED to create tunnel. Check quicktunnel.log"
  exit 1
fi

echo ""
echo "====================================================="
echo "  Share this link:  $URL"
echo "====================================================="
echo ""
echo "Note: works while this computer is on. Rerun this"
echo "script next time for a fresh link (the URL changes)."
