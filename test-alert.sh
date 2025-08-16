#!/bin/bash
# Send a test alert to a local Alertmanager instance, repeatedly firing until
# the user resolves it, to verify alert delivery and routing.
url='http://localhost:9093/api/v2/alerts'

declare -A ALERT_LABELS=(
  [alertname]="TEST-tokenAPI"
  [alertgroup]="TEST-tokenAPI"
  [component]="token-api-sink"
  [cluster]="riv-prod1"
  [network]="avalanche"
)

summary='Testing summary!'
default_severity='critical'

send_alert() {
  local status=$1
  local current_severity=${2:-$default_severity}
  ALERT_LABELS[severity]="$current_severity"

  local labels_json="{"
  local first=true
  for key in "${!ALERT_LABELS[@]}"; do
    value="${ALERT_LABELS[$key]}"
    if $first; then first=false; else labels_json+=","; fi
    labels_json+="\"$key\":\"$value\""
  done
  labels_json+="}"

  cat <<EOF | curl -s -X POST $url -H "Content-Type: application/json" -d @-
[
  {
    "status": "$status",
    "labels": $labels_json,
    "annotations": {
      "summary": "$summary"
    },
    "generatorURL": "https://prometheus.local/<generating_expression>"
  }
]
EOF
  echo "Sent alert status=$status severity=$current_severity"
}

echo "→ Firing alert ${ALERT_LABELS[alertname]}"
send_alert "firing" "$1"

echo "Relaying alert firing every 60s until you press Enter..."
while true; do
  read -t 60 -p "Press Enter to resolve alert or wait: " input
  if [ $? -eq 0 ]; then
    echo "User pressed Enter. Resolving alert..."
    send_alert "resolved" "$1"
    break
  else
    echo "Alert fired again..."
    send_alert "firing" "$1"
  fi
done
echo "Done."
