#!/bin/sh
# Everything that can be checked without a model, a Claude session or audio:
# the client in dry-run, mode handling, the text rules end to end, both hooks.
# Runs on CI after install.sh. Uses a throwaway KOKORO_HOME; never plays sound.
#
#     sh evals/test_offline.sh
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUNTIME="${KOKORO_RUNTIME:-$HOME/.kokoro}"
K="$ROOT/bin/kokoro"
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
check() { label=$1; shift; if "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label"; fi; }

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
[ -x "$RUNTIME/.venv/bin/python" ] || { echo "no runtime at $RUNTIME - run install.sh first"; exit 2; }
ln -s "$RUNTIME/.venv" "$T/.venv"
run() { KOKORO_HOME="$T" KOKORO_DRY_RUN=1 "$K" "$@"; }
lines() { [ -f "$T/dryrun.jsonl" ] && wc -l < "$T/dryrun.jsonl" | tr -d ' ' || echo 0; }

echo "sources compile"
check "all python compiles" python3 -m py_compile "$ROOT"/bin/*.py "$ROOT"/bin/platforms/*.py "$ROOT"/evals/*.py
check "hooks are valid shell" sh -n "$ROOT/hooks/voice-hook"
check "stop hook is valid shell" sh -n "$ROOT/hooks/stop-hook"
check "hooks.json parses" python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$ROOT/hooks/hooks.json"
check "plugin manifests parse" python3 -c "import json,sys; [json.load(open(f)) for f in sys.argv[1:]]" "$ROOT/.claude-plugin/plugin.json" "$ROOT/.claude-plugin/marketplace.json"

echo "client"
run --bg --title unit "Hello there. This is a test."
check "dry-run records speech instead of playing" grep -q '"kind": "speak"' "$T/dryrun.jsonl"
run "Edited scripts/player_movement.py, freeing 300 MB."
check "text rules applied before speaking" grep -q "the player movement script, freeing 300 megabytes" "$T/dryrun.jsonl"
if run --set mode=loud; then bad "rejects an unknown mode"; else ok "rejects an unknown mode"; fi
run --set mode=off >/dev/null
N=$(lines)
if run "should not speak" 2>/dev/null; then bad "off refuses to speak"; else ok "off refuses to speak"; fi
check "off records nothing" [ "$(lines)" = "$N" ]
check "switching off also stops playback" grep -q '"kind": "hush"' "$T/dryrun.jsonl"
run --set mode=on-request >/dev/null
check "accepts a voice blend" sh -c "KOKORO_HOME='$T' '$K' --set voice=af_heart:0.7,bf_emma:0.3"
if KOKORO_HOME="$T" "$K" --set voice="not a voice" >/dev/null 2>&1; then bad "rejects a bad voice"; else ok "rejects a bad voice"; fi
KOKORO_HOME="$T" "$K" --set voice=af_heart >/dev/null
run --hush >/dev/null
check "control commands work in dry-run" [ "$(grep -c '"kind": "hush"' "$T/dryrun.jsonl")" -ge 2 ]

echo "voice hook"
for m in off on-request narrate; do
  printf '{"mode":"%s"}' "$m" > "$T/config.json"
  OUT=$(KOKORO_HOME="$T" sh "$ROOT/hooks/voice-hook")
  case $m in
    off)        check "off tells Claude voice is off"   sh -c "printf '%s' \"\$1\" | grep -q 'mode=\"off\"'" _ "$OUT" ;;
    on-request) check "on-request injects a short note" sh -c "printf '%s' \"\$1\" | grep -q 'mode=\"on-request\"'" _ "$OUT" ;;
    narrate)    check "narrate injects the rules"      sh -c "printf '%s' \"\$1\" | grep -q 'NEVER speak a filename'" _ "$OUT" ;;
  esac
done
rm -f "$T/config.json"; touch "$T/.narrate"
check "legacy narrate flag still honoured" sh -c "KOKORO_HOME='$T' sh '$ROOT/hooks/voice-hook' | grep -q 'mode=\"narrate\"'"
rm -f "$T/.narrate"
python3 -c "import json,time; open('$T/.now-playing','w').write(json.dumps({'index':1,'total':3,'current':'b.','sentences':['a.','b.','c.'],'at':time.time()-600,'title':'t'}))"
printf '{"mode":"on-request"}' > "$T/config.json"
check "stale speech is dropped" sh -c "! KOKORO_HOME='$T' sh '$ROOT/hooks/voice-hook' | grep -q speaking-now"
touch "$T/.paused"
check "paused speech is kept however old" sh -c "KOKORO_HOME='$T' sh '$ROOT/hooks/voice-hook' | grep -q speaking-now"
rm -f "$T/.paused" "$T/.now-playing"

echo "stop hook"
transcript() { # kind: work | voice | none
python3 - "$T/tr.jsonl" "$1" <<'PY'
import json, sys, datetime
path, kind = sys.argv[1], sys.argv[2]
now = datetime.datetime.now(datetime.timezone.utc)
ts = lambda s: (now + datetime.timedelta(seconds=s)).isoformat().replace("+00:00", "Z")
L = [{"type": "user", "message": {"role": "user", "content": "do the task"}, "timestamp": ts(-60)}]
if kind == "work":
    L.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "grep -r ROLES ."}}]}, "timestamp": ts(-50)})
if kind == "voice":
    L.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "kokoro --set mode=narrate"}}]}, "timestamp": ts(-50)})
open(path, "w").write("\n".join(json.dumps(x) for x in L))
PY
}
stop() { # label mode kind summary(none|new|old) active expected(block|allow)
  printf '{"mode":"%s"}' "$2" > "$T/config.json"; rm -f "$T/.last-summary"
  case $4 in new) python3 -c "import time; open('$T/.last-summary','w').write(str(time.time()))" ;;
             old) python3 -c "import time; open('$T/.last-summary','w').write(str(time.time()-3600))" ;; esac
  transcript "$3"
  OUT=$(printf '{"transcript_path":"%s","stop_hook_active":%s}' "$T/tr.jsonl" "$5" | KOKORO_HOME="$T" sh "$ROOT/hooks/stop-hook")
  if printf '%s' "$OUT" | grep -q '"block"'; then got=block; else got=allow; fi
  if [ "$got" = "$6" ]; then ok "$1"; else bad "$1 (got $got)"; fi
}
stop "narrate, work, no summary: blocks"        narrate    work  none false block
stop "narrate, work, summary this turn: allows" narrate    work  new  false allow
stop "narrate, work, old summary: blocks"       narrate    work  old  false block
stop "narrate, already asked once: allows"      narrate    work  none true  allow
stop "narrate, no tools: allows"                narrate    none  none false allow
stop "narrate, voice commands only: allows"     narrate    voice none false allow
stop "on-request: allows"                       on-request work  none false allow
stop "off: allows"                              off        work  none false allow

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
