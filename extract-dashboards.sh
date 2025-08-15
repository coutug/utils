#!/usr/bin/env bash
set -euo pipefail

# Simple script to fetch all Grafana dashboards via the Grafana Operator API and store each one
# as a JSON file under the directory defined by FOLDER.
GRAFANA_AUTH=pinax:eosneosn
GRAFANA_URL=grafana.monitor.riv-monitor1.pinax.io
FOLDER=dashboard-result

mkdir -p "$FOLDER"

curl -s "https://$GRAFANA_AUTH@$GRAFANA_URL/apis/dashboard.grafana.app/v1beta1/namespaces/default/dashboards" \
| jq -c '.items[] | {title: .spec.title, spec: .spec}' \
| while IFS= read -r dash; do
    title=$(echo "$dash" | jq -r '.title' | sed 's|/|>|g' | sed 's/ /-/g')
    echo "$dash" | jq '.spec' > "$FOLDER/$title.json"
  done
