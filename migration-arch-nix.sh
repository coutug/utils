#!/usr/bin/env bash
# =============================================================================
# Script : dedupe-arch-vs-hm.sh
#
# Description :
#   Ce script détecte les paquets qui sont installés à la fois via Arch Linux
#   (pacman/yay) et via Nix Home-Manager (flakes). Pour chaque doublon trouvé,
#   il propose de désinstaller la version Arch afin d’éviter les conflits et
#   doublons entre les deux systèmes de gestion de paquets.
#
# Fonctionnement :
#   1. Récupère la liste des paquets installés explicitement par pacman/yay.
#   2. Récupère la liste des paquets déclarés dans ta configuration
#      Home-Manager (flake).
#   3. Fait l’intersection des deux listes, avec un petit mappage de noms
#      pour les paquets qui diffèrent entre Nix et Arch (ex. helm, yq, zoom).
#   4. Parcourt les doublons un par un et demande confirmation avant de lancer
#      la désinstallation du paquet côté Arch (yay -Rns ou pacman -Rns).
#
# Utilisation :
#   - Par défaut (dans le dossier de ton flake HM) :
#       ./dedupe-arch-vs-hm.sh
#
#   - Flake + nœud HM explicite :
#       FLAKE_REF=~/config/home-manager HM_NODE="gabriel@pc-gabriel" ./dedupe-arch-vs-hm.sh
#
#   - Mode non-interactif (désinstalle tout sans confirmation) :
#       ASSUME_YES=1 ./dedupe-arch-vs-hm.sh
#
#   - Mode simulation (ne supprime rien, affiche seulement les commandes) :
#       DRY_RUN=1 ./dedupe-arch-vs-hm.sh
#
# Prérequis :
#   - jq (pour parser la sortie JSON de nix eval)
#   - yay ou pacman
#   - Nix avec Home-Manager (flakes)
# =============================================================================

set -euo pipefail

# === Config par défaut ===
FLAKE_REF="${FLAKE_REF:-.}"                    # ex: .  ou  ~/dotfiles
HM_NODE="${HM_NODE:-$USER@$(hostname)}"        # ex: gabriel@pc-gabriel
ASSUME_YES="${ASSUME_YES:-0}"                  # 1 = ne pas demander confirmation
DRY_RUN="${DRY_RUN:-0}"                        # 1 = n'exécute pas les suppressions

# === Détection yay/pacman ===
if command -v yay >/dev/null 2>&1; then
  PM="yay"
  REMOVE_CMD=(yay -Rns)
else
  PM="pacman"
  REMOVE_CMD=(sudo pacman -Rns)
fi

echo ">> Gestionnaire AUR: $PM"
echo ">> Flake: $FLAKE_REF  |  Home-Manager node: $HM_NODE"
echo

# === 1) Paquets Arch (explicites) ===
echo ">> Récupération des paquets Arch installés explicitement…"
if [[ "$PM" == "yay" ]]; then
  mapfile -t ARCH_PKGS < <(yay -Qqe | sort -u)
else
  mapfile -t ARCH_PKGS < <(pacman -Qqe | sort -u)
fi
echo "   → ${#ARCH_PKGS[@]} paquets (Arch)"

# === 2) Paquets Home-Manager ===
# On évalue la liste des derivations home.packages et on en extrait un "nom logique".
# - p.pname si dispo
# - sinon parseDrvName p.name (pour séparer nom vs version)
echo ">> Évaluation des paquets Home-Manager (flakes)…"
NIX_EXPR='builtins.map (p: (p.pname or (builtins.parseDrvName p.name).name))'
NIX_ATTR="$FLAKE_REF#homeConfigurations.$HM_NODE.config.home.packages"

# Sortie : JSON array de strings
HM_JSON=$(nix eval --json "$NIX_ATTR" --apply "$NIX_EXPR")
# Convertir JSON → lignes (jq requis)
if ! command -v jq >/dev/null 2>&1; then
  echo "ERREUR: jq est requis (pacman -S jq / yay -S jq)."
  exit 1
fi
mapfile -t HM_PKGS < <(printf '%s' "$HM_JSON" | jq -r '.[]' | sort -u)
echo "   → ${#HM_PKGS[@]} paquets (Home-Manager)"

# === 3) Mappage Nix → Arch (noms divergents) ===
# Ajoute ici tes overrides si besoin.
# clé = nom dans Nix/HM ; valeur = nom du paquet Arch correspondant.
declare -A NAME_MAP=(
  # exemples fréquents :
  [kubernetes-helm]="helm"
  [yq-go]="go-yq"
  [zoom-us]="zoom"
  # [qbittorrent-enhanced]="qbittorrent-enhanced"   # identique (exemple)
  # [github-cli]="github-cli"                       # identique (exemple)
)

# Applique le mapping à la liste HM
map_hm_to_arch() {
  local n="$1"
  if [[ -n "${NAME_MAP[$n]+x}" ]]; then
    printf '%s\n' "${NAME_MAP[$n]}"
  else
    printf '%s\n' "$n"
  fi
}

# === 4) Construire des sets pour l'intersection ===
declare -A SET_ARCH=()
for p in "${ARCH_PKGS[@]}"; do
  SET_ARCH["$p"]=1
done

DUPES=()
for n in "${HM_PKGS[@]}"; do
  a_name="$(map_hm_to_arch "$n")"
  # ignore vide
  [[ -z "$a_name" ]] && continue
  if [[ -n "${SET_ARCH[$a_name]+x}" ]]; then
    DUPES+=("$a_name")
  fi
done

# Uniques + tri
mapfile -t DUPES < <(printf '%s\n' "${DUPES[@]}" | sort -u)

echo
echo "==> Doublons (installés à la fois via Arch et listés par Home-Manager): ${#DUPES[@]}"
printf '    %s\n' "${DUPES[@]}" || true
echo

if [[ ${#DUPES[@]} -eq 0 ]]; then
  echo "Aucun doublon détecté. 👍"
  exit 0
fi

# === 5) Désinstallation interactive (ou non) ===
for pkg in "${DUPES[@]}"; do
  if [[ "$ASSUME_YES" != "1" ]]; then
    read -rp "Supprimer \"$pkg\" via ${REMOVE_CMD[*]} ? [y/N] " ans
    case "${ans:-}" in
      y|Y|yes|YES) ;;
      *) echo "   → ignoré: $pkg"; continue ;;
    esac
  fi

  echo "   → suppression: $pkg"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "      (DRY_RUN) ${REMOVE_CMD[*]} $pkg"
  else
    "${REMOVE_CMD[@]}" "$pkg"
  fi
done

echo
echo "Terminé."
echo "Astuce: relance 'home-manager switch --flake $FLAKE_REF#$HM_NODE' après ménage si besoin."

