#!/usr/bin/env bash
set -euo pipefail

# Description: Fetch all Grafana dashboards via the Grafana Operator API and save them as JSON files.
# Functioning: Queries the API, iterates over dashboards, and writes each spec to FOLDER/<title>.json.
# How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

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
