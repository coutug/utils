#!/usr/bin/env bash
set -euo pipefail

GRAFANA_AUTH=pinax:eosneosn
GRAFANA_URL=grafana.monitor.riv-monitor1.pinax.io
FOLDER=dashboard-result

mkdir -p "$FOLDER"

curl -s "https://$GRAFANA@grafana.monitor.riv-monitor1.pinax.io/apis/dashboard.grafana.app/v1beta1/namespaces/default/dashboards?limit=1" \
| jq -c '.items[] | {title: .spec.title, spec: .spec}' \
| while IFS= read -r dash; do
    title=$(echo "$dash" | jq -r '.title' | sed 's/ /-/g')
    echo "$dash" | jq '.spec' > "$FOLDER/$title.json"
  done
