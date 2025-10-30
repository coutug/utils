# utils
Useful scripts collection built along the journey

## bash/clean-ns.sh
Description: Remove finalizers from every namespaced CRD instance found in a namespace.
Functioning: Lists namespaced resources, retrieves objects in the namespace, and patches each to clear metadata.finalizers.
How to use: Run with the namespace as the first argument. Example: ./bash/remove-crd-finalizers.sh my-namespace

## bash/extract-dashboards.sh
Description: Fetch all Grafana dashboards via the Grafana Operator API and save them as JSON files.
Functioning: Queries the API, iterates over dashboards, and writes each spec to FOLDER/<title>.json.
How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

## bash/migrate-arch-nix.sh
Description: Uninstall Arch packages that are also managed by Home‑Manager.
Functioning: Collects Arch and Home‑Manager packages, maps names, optionally prompts, and removes duplicates.
How to use: Requires yay (or pacman) and home-manager. Options: --yes/-y skip confirmation, --dry-run show only, --include-yay allow removing 'yay'.

## bash/rename.sh
Description: Rename all files and directories under ./the-graph to lowercase without overwriting existing entries.
Functioning: Traverses the directory tree and renames each item to its lowercase counterpart if the destination does not exist.
How to use: Run without arguments from the repository root; it operates on ./the-graph.

## bash/status-page-sync.sh
Description: Download a single Grafana dashboard and save it as JSON for status page syncing.
Functioning: Queries the Grafana Operator API for one dashboard and writes it to FOLDER/<title>.json.
How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

## bash/test-alert.sh
Description: Send a test alert to a local Alertmanager to verify delivery and routing.
Functioning: Fires an alert, repeats until the user resolves it, and then sends a resolve notification.
How to use: Run without arguments or pass a severity as the first argument.

## bash/test-probe.sh
Description: Continuously probe a list of URLs with hey and report HTTP code distribution.
Functioning: Loops through URLs, runs hey with configured parameters, parses the status codes, and logs results.
How to use: Optionally set HEY_BIN, SLEEP_SEC, NREQ, and CONCURRENCY environment variables before running.

## bash/update-sops.sh
Description: Refresh SOPS encryption keys for all *.enc and *.env files recursively.
Functioning: Finds matching files, runs `sops updatekeys` on each, and returns to the starting directory.
How to use: Run from the repository root; requires `sops` in the PATH.

## python/conf2vmrule.py
Description: Convert an Icinga-style .conf service definition using a Prometheus check into a VictoriaMetrics VMRule YAML.
Functioning: Extracts metric details and thresholds from the .conf file, cleans label matchers, and builds a VMRule expression.
How to use: python3 conf2vmrule.py /path/to/myAlert.conf [--write | -o out.yaml]

## python/extract-gh-issues.py
Usage: python extract_projectv2_issues_export.py     --org-v2-project eosnationftw:7 --org-v2-project pinax-network:12     --out export.csv [--users alice,bob] Requires: Python 3.9+, requests, a GitHub token via --token or $GITHUB_TOKEN.

## python/rework_dashboards.py
Description: Rework Grafana dashboard JSON files to standardize datasource usage.
Functioning: Unwraps exported dashboards, ensures a datasource variable, and rewrites panel datasource fields.
How to use: python3 rework_dashboards.py <input> [--output-dir DIR | --in-place] [--prom-only | --all-sources]

## python/sync-status-page.py
======================= Configuration loading =======================

## python/update_readme.py
Description: Generate README listing all scripts with descriptions.
Functioning: Scans the bash/ and python/ folders for scripts, extracts their description blocks, and writes README.md.
How to use: Run `python python/update_readme.py` from the repository root.

