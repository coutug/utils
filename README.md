# utils
Useful scripts collection built along the journey

## Development

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The README generator itself has no external dependencies, but other scripts require those listed above.


## bash
### clean-ns.sh
Description: Interactively delete all namespaced Kubernetes resources in a namespace and clear finalizers.
Functioning: Lists each resource type, prompts for deletion, deletes resources, and removes finalizers.
How to use: Run with the namespace as the first argument.

### extract-dashboards.sh
Description: Fetch all Grafana dashboards via the Grafana Operator API and save them as JSON files.
Functioning: Queries the API, iterates over dashboards, and writes each spec to FOLDER/<title>.json.
How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

### migrate-arch-nix.sh
Description: Uninstall Arch packages that are also managed by Home‑Manager.
Functioning: Collects Arch and Home‑Manager packages, maps names, optionally prompts, and removes duplicates.
How to use: Requires yay (or pacman) and home-manager. Options: --yes/-y skip confirmation, --dry-run show only, --include-yay allow removing 'yay'.

### rename.sh
Description: Rename all files and directories under ./the-graph to lowercase without overwriting existing entries.
Functioning: Traverses the directory tree and renames each item to its lowercase counterpart if the destination does not exist.
How to use: Run without arguments from the repository root; it operates on ./the-graph.

### status-page-sync.sh
Description: Download a single Grafana dashboard and save it as JSON for status page syncing.
Functioning: Queries the Grafana Operator API for one dashboard and writes it to FOLDER/<title>.json.
How to use: Set GRAFANA_AUTH, GRAFANA_URL, and FOLDER variables then run the script.

### test-alert.sh
Description: Send a test alert to a local Alertmanager to verify delivery and routing.
Functioning: Fires an alert, repeats until the user resolves it, and then sends a resolve notification.
How to use: Run without arguments or pass a severity as the first argument.

### test-probe.sh
Description: Continuously probe a list of URLs with hey and report HTTP code distribution.
Functioning: Loops through URLs, runs hey with configured parameters, parses the status codes, and logs results.
How to use: Optionally set HEY_BIN, SLEEP_SEC, NREQ, and CONCURRENCY environment variables before running.

### update-sops.sh
Description: Refresh SOPS encryption keys for all *.enc and *.env files recursively.
Functioning: Finds matching files, runs `sops updatekeys` on each, and returns to the starting directory.
How to use: Run from the repository root; requires `sops` in the PATH.

## python
### conf2vmrule.py
Description: Convert an Icinga-style .conf service definition using a Prometheus check into a VictoriaMetrics VMRule YAML.
Functioning: Extracts metric details and thresholds from the .conf file, cleans label matchers, and builds a VMRule expression.
How to use: python3 conf2vmrule.py /path/to/myAlert.conf [--write | -o out.yaml]

### rework_dashboards.py
Description: Rework Grafana dashboard JSON files to standardize datasource usage.
Functioning: Unwraps exported dashboards, ensures a datasource variable, and rewrites panel datasource fields.
How to use: python3 rework_dashboards.py <input> [--output-dir DIR | --in-place] [--prom-only | --all-sources]

### sync-status-page.py
======================= Configuration loading =======================

### update_readme.py
Description: Generate README listing all scripts with descriptions.
Functioning: Recursively scans the repository for shell and Python scripts, groups them by directory, and writes README.md.
How to use: Run `python python/update_readme.py` from the repository root.

