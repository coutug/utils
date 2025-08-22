# utils
Useful scripts collection built along the journey

## clean-ns.sh
Interactively delete all namespaced Kubernetes resources in the specified namespace and clear finalizers.

## extract-dashboards.sh
Simple script to fetch all Grafana dashboards via the Grafana Operator API and store each one as a JSON file under the directory defined by FOLDER.

## migration-arch-nix.sh
============================================================================= Script : dedupe-arch-vs-hm.sh  Description : Ce script détecte les paquets qui sont installés à la fois via Arch Linux (pacman/yay) et via Nix Home-Manager (flakes). Pour chaque doublon trouvé, il propose de désinstaller la version Arch afin d’éviter les conflits et doublons entre les deux systèmes de gestion de paquets.  Fonctionnement : 1. Récupère la liste des paquets installés explicitement par pacman/yay. 2. Récupère la liste des paquets déclarés dans ta configuration Home-Manager (flake). 3. Fait l’intersection des deux listes, avec un petit mappage de noms pour les paquets qui diffèrent entre Nix et Arch (ex. helm, yq, zoom). 4. Parcourt les doublons un par un et demande confirmation avant de lancer la désinstallation du paquet côté Arch (yay -Rns ou pacman -Rns).  Utilisation : - Par défaut (dans le dossier de ton flake HM) : ./dedupe-arch-vs-hm.sh  - Flake + nœud HM explicite : FLAKE_REF=~/config/home-manager HM_NODE="gabriel@pc-gabriel" ./dedupe-arch-vs-hm.sh  - Mode non-interactif (désinstalle tout sans confirmation) : ASSUME_YES=1 ./dedupe-arch-vs-hm.sh  - Mode simulation (ne supprime rien, affiche seulement les commandes) : DRY_RUN=1 ./dedupe-arch-vs-hm.sh  Prérequis : - jq (pour parser la sortie JSON de nix eval) - yay ou pacman - Nix avec Home-Manager (flakes) =============================================================================

## rename.sh
Rename every file and directory under ./the-graph to lowercase while preserving the directory structure. Existing lowercase targets are skipped to avoid overwriting.

## status-page-sync.sh
Download a single Grafana dashboard from the Grafana Operator API and save it to the FOLDER directory as a JSON file. Useful for syncing the status page.

## test-alert.sh
Send a test alert to a local Alertmanager instance, repeatedly firing until the user resolves it, to verify alert delivery and routing.

## update-sops.sh
Iterate over all *.enc and *.env files in the tree and refresh their SOPS encryption keys using `sops updatekeys`.

## conf2vmrule.py
conf2vmrule.py Convert a simple Icinga-style .conf service definition using a Prometheus check into a VictoriaMetrics VMRule YAML.

## rework_dashboards.py
Rework Grafana dashboard JSON files: - If file has {"dashboard": {...}, "meta": {...}}, unwrap to just {...} (the "dashboard" content). - Ensure a templating variable of type "datasource" named DS_PROMETHEUS pointing to VictoriaMetrics-ops. - Replace all "datasource" fields (object or string) across the dashboard with "${DS_PROMETHEUS}", skipping Grafana's internal annotation datasource objects ({"type":"datasource","uid":"grafana"}). By default, only objects are rewritten conservatively when they are Prometheus-like; use --all-sources to rewrite string datasources too.

## update_readme.py
Generate README listing all scripts with descriptions.

