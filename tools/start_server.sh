#!/usr/bin/env bash
# Publish this machine's model to everyone playing Kod AI.
#
#   ./tools/start_server.sh            # start, print the git command to run
#   ./tools/start_server.sh --push     # start and publish the address itself
#
# Before running: LM Studio open, a chat model loaded, its server started on
# port 1234, and Settings -> Max Concurrent Predictions set to 5.
#
# Leave this running for as long as anyone is playing. Ctrl-C stops it and
# marks the server offline for every player.

set -euo pipefail
cd "$(dirname "$0")/.."

PUSH=0
[ "${1:-}" = "--push" ] && PUSH=1

: "${LLM_TOKEN:?set LLM_TOKEN to the same shared token the game is built with}"
command -v cloudflared >/dev/null || { echo "cloudflared missing: brew install cloudflared"; exit 1; }

LOG="$(mktemp -t kodai-tunnel)"
GATEWAY_PID=""
TUNNEL_PID=""

offline() {
  # Whatever happens, players get told rather than left staring at a
  # connection error against an address that no longer exists.
  python3 - <<'PY'
import json, pathlib
p = pathlib.Path("server.json")
d = json.loads(p.read_text())
d["enabled"] = False
d["url"] = ""
d["token"] = ""
d["message"] = "The case server is offline right now. Try again later, or run your own model - see the README."
p.write_text(json.dumps(d, indent=2) + "\n")
PY
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  [ -n "$GATEWAY_PID" ] && kill "$GATEWAY_PID" 2>/dev/null || true
  echo
  # Marking the file offline locally does nothing for anyone: players read it
  # from GitHub. Left unpublished, the address they keep finding is the tunnel
  # that just died, so they get a connection error instead of the message this
  # whole mechanism exists to deliver. An operator who asked for --push on the
  # way up gets the same on the way down.
  if [ "$PUSH" = "1" ] \
     && git commit -qm "Server offline" server.json 2>/dev/null \
     && git push -q 2>/dev/null; then
    echo "Server stopped, and players now see the offline message."
  else
    echo "Server stopped. server.json set to offline — commit and push it so"
    echo "players see the message instead of a dead address:"
    echo "    git commit -am 'Server offline' && git push"
  fi
}
trap offline EXIT INT TERM

# LM Studio must already be up: starting a tunnel to nothing publishes an
# address that fails for everyone.
curl -sf --max-time 5 http://localhost:1234/v1/models >/dev/null \
  || { echo "LM Studio is not answering on :1234 — start its server first."; exit 1; }

LLM_TOKEN="$LLM_TOKEN" python3 tools/serve_llm.py --port 8080 --slots 5 &
GATEWAY_PID=$!
sleep 1
kill -0 "$GATEWAY_PID" 2>/dev/null || { echo "gateway failed to start"; exit 1; }

cloudflared tunnel --url http://localhost:8080 >"$LOG" 2>&1 &
TUNNEL_PID=$!

echo -n "waiting for the tunnel"
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  echo -n "."
  sleep 1
done
echo
[ -n "$URL" ] || { echo "tunnel produced no address; see $LOG"; exit 1; }

python3 - "$URL" "$LLM_TOKEN" <<'PY'
import json, pathlib, sys
p = pathlib.Path("server.json")
d = json.loads(p.read_text())
d["enabled"] = True
d["url"] = sys.argv[1].rstrip("/") + "/v1"
# Published alongside the address so players' copies present the token the
# gateway expects. Rotating it is an edit here plus a restart, not a rebuild.
d["token"] = sys.argv[2]
d["message"] = ""
p.write_text(json.dumps(d, indent=2) + "\n")
print("server.json ->", d["url"])
PY

if [ "$PUSH" = "1" ]; then
  # Tested rather than run bare: under `set -e` a push that fails for a passing
  # reason - stale credentials, a dropped connection, a remote that moved ahead
  # - would abort the script and trip the exit trap, tearing down a tunnel and
  # gateway that are working perfectly. A failed publish is worth a message,
  # not the server.
  if git commit -qm "Point players at the current server address" server.json \
     && git push -q; then
    echo "published — players pick it up within a minute, no reinstall"
  else
    echo "could not publish automatically — the server is up, so run this yourself:"
    echo "    git commit -am 'Point players at the current server address' && git push"
  fi
else
  echo
  echo "Publish it so players can connect:"
  echo "    git commit -am 'Point players at the current server address' && git push"
fi

echo
echo "Serving. Keep this window open and the lid up. Ctrl-C to stop."
wait "$TUNNEL_PID"
