#!/usr/bin/env bash
set -euo pipefail

# Description: Continuously probe a list of URLs with hey and report HTTP code distribution.
# Functioning: Loops through URLs, runs hey with configured parameters, parses the status codes, and logs results.
# How to use: Optionally set HEY_BIN, SLEEP_SEC, NREQ, and CONCURRENCY environment variables before running.

# Configuration via environment variables (overridable at launch)
HEY_BIN="${HEY_BIN:-hey}"       # hey binary
SLEEP_SEC="${SLEEP_SEC:-10}"    # pause between URLs
NREQ="${NREQ:-5}"               # number of requests per URL per iteration
CONCURRENCY="${CONCURRENCY:-1}" # concurrency level

URLS=(
  "https://mcp-token-api.service.pinax.network/health"
  "https://token-api.service.pinax.network/health"

  "https://ch-a.token-api.service.pinax.network/replicas_status"
  "https://ch-b.token-api.service.pinax.network/replicas_status"

  "https://antelope-api-wax.service.pinax.network/health"
  "https://antelope-api-eos.service.pinax.network/health"
  "https://antelope-api-kylin.service.pinax.network/health"
)

# Ensure hey is available
if ! command -v "$HEY_BIN" > /dev/null 2>&1; then
  echo "❌ hey not found. Install it and/or set HEY_BIN." >&2
  exit 1
fi

while true; do
  for url in "${URLS[@]}"; do
    ts="$(date -Is)"
    # Run hey (suppress the progress bar); capture output
    out="$("$HEY_BIN" --disable-keepalive -n "$NREQ" -c "$CONCURRENCY" "$url" 2>&1 || true)"

    # Parse the HTTP status code distribution
    # Grab lines from the "Status code distribution:" block
    status_block="$(printf "%s\n" "$out" \
      | awk '/Status code distribution:/{f=1;print;next} f&&/^[[:space:]]*\[[0-9]{3}\]/{print} f&&!/^[[:space:]]*\[[0-9]{3}\]/{ if(NR>1) exit }')"

    total=0
    ok200=0

    # Extract "  [200] 12 responses" => code=200, cnt=12
    while read -r code cnt _; do
      [[ -z "${code:-}" ]] && continue
      # code format "[200]"
      code="${code#[}"
      code="${code%]}"
      if [[ "$code" =~ ^[0-9]{3}$ && "$cnt" =~ ^[0-9]+$ ]]; then
        total=$((total + cnt))
        if [[ "$code" == "200" ]]; then
          ok200=$cnt
        fi
      fi
    done < <(printf "%s\n" "$status_block" | sed -n 's/^[[:space:]]*\[\([0-9]\{3\}\)\][[:space:]]*\([0-9]\+\).*/[\1] \2/p')

    # If parsing failed, treat as an error
    if [[ "$total" -eq 0 ]]; then
      echo "[$ts] ❌ $url → unable to validate responses (hey may have failed)"
      printf "%s\n" "$out" | sed -n '1,120p' >&2
    elif [[ "$ok200" -eq "$total" ]]; then
      echo "[$ts] ✅ $url → OK (all $ok200/$total responses are 200)"
    else
      echo "[$ts] ⚠️  $url → WARNING (non-200 codes detected: $((total - ok200))/$total)"
      # Show relevant snippet
      printf "%s\n" "$status_block"
      # If present, display the error block from hey
      err_block="$(printf "%s\n" "$out" | awk '/Error distribution:/{f=1;print;next} f&&/^[[:space:]]*\[[0-9]+\]/{print} f&&!/^[[:space:]]*\[[0-9]+\]/{ if(NR>1) exit }')"
      [[ -n "$err_block" ]] && printf "%s\n" "$err_block"
    fi

    sleep "$SLEEP_SEC"
  done
done
