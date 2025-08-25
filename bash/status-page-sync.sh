#!/usr/bin/env bash
set -euo pipefail

# Description: Download a single Grafana dashboard and save it as JSON for status page syncing.
# Functioning: Queries the Grafana Operator API for one dashboard and writes it to FOLDER/<title>.json.
# How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

GRAFANA_AUTH=pinax:eosneosn
GRAFANA_URL=grafana.monitor.riv-monitor1.pinax.io
FOLDER=dashboard-result

mkdir -p "$FOLDER"

curl -s "https://${GRAFANA_AUTH}@${GRAFANA_URL}/apis/dashboard.grafana.app/v1beta1/namespaces/default/dashboards?limit=1" \
| jq -c '.items[] | {title: .spec.title, spec: .spec}' \
| while IFS= read -r dash; do
    title=$(echo "$dash" | jq -r '.title' | sed 's/ /-/g')
    echo "$dash" | jq '.spec' > "$FOLDER/$title.json"
  done
