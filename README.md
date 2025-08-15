# utils
Useful scripts collection built along the journey

## extract-dashboards.sh
Simple script to fetch all Grafana dashboards via the Grafana Operator API and store each one as a JSON file under the directory defined by FOLDER.

## rename.sh
Rename every file and directory under ./the-graph to lowercase while preserving the directory structure. Existing lowercase targets are skipped to avoid overwriting.

## status-page-sync.sh
Download a single Grafana dashboard from the Grafana Operator API and save it to the FOLDER directory as a JSON file. Useful for syncing the status page.

## test-alert.sh
Send a test alert to a local Alertmanager instance, repeatedly firing until the user resolves it, to verify alert delivery and routing.

## update-sops.sh
Iterate over all *.enc and *.env files in the tree and refresh their SOPS encryption keys using `sops updatekeys`.

## rework_dashboards.py
Rework Grafana dashboard JSON files: - If file has {"dashboard": {...}, "meta": {...}}, unwrap to just {...} (the "dashboard" content). - Ensure a templating variable of type "datasource" named DS_PROMETHEUS pointing to VictoriaMetrics-ops. - Replace all "datasource" fields (object or string) across the dashboard with "${DS_PROMETHEUS}", skipping Grafana's internal annotation datasource objects ({"type":"datasource","uid":"grafana"}). By default, only objects are rewritten conservatively when they are Prometheus-like; use --all-sources to rewrite string datasources too.

## update_readme.py
Generate README listing all scripts with descriptions.

