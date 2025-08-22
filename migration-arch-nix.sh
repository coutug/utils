#!/usr/bin/env bash
# Désinstalle (optionnellement) les paquets Arch qui sont aussi gérés par Home‑Manager (Nix).
# Prérequis: yay (ou pacman) et home-manager.
# Options:
#   --yes / -y    : ne pas demander de confirmation, désinstaller directement
#   --dry-run     : n'affiche que la liste, ne désinstalle rien
#   --include-yay : autorise la désinstallation de 'yay' s'il est en doublon (par défaut, on l'ignore)

set -u
set -o pipefail

CONFIRM=1
DRYRUN=0
INCLUDE_YAY=0

while (( "$#" )); do
  case "$1" in
    --yes|-y) CONFIRM=0; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    --include-yay) INCLUDE_YAY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--yes|-y] [--dry-run] [--include-yay]"
      exit 0
      ;;
    *)
      echo "Option inconnue: $1" >&2
      exit 2
      ;;
  esac
done

have_cmd() { command -v "$1" >/dev/null 2>&1; }

# 1) Récupérer les paquets Arch explicitement installés (AUR inclus)
if have_cmd yay; then
  mapfile -t ARCH_PKGS < <(yay -Qqe 2>/dev/null | sort -u)
elif have_cmd pacman; then
  mapfile -t ARCH_PKGS < <(pacman -Qqe 2>/dev/null | sort -u)
else
  echo "Erreur: ni 'yay' ni 'pacman' n'ont été trouvés dans le PATH." >&2
  exit 1
fi

# 2) Récupérer les paquets Home‑Manager installés (sans version)
if ! have_cmd home-manager; then
  echo "Erreur: 'home-manager' n'est pas dans le PATH." >&2
  exit 1
fi

# home-manager packages retourne des noms du type 'act-0.2.77' (ou parfois des chemins .drv).
# On garde juste le nom sans version.
mapfile -t HM_PKGS < <(
  home-manager packages \
  | sed -E 's#.*/##' \
  | sed -E 's/\.drv$//' \
  | sed -E 's/-[0-9][0-9A-Za-z._+~-]*$//' \
  | sed '/^$/d' \
  | sort -u
)

# 3) Mapping Nix -> Arch pour les noms divergents
#    Ajoute ici tes correspondances perso si besoin.
declare -A MAP_NIX_TO_ARCH=(
  # Nix                  Arch
  [kubernetes-helm]=helm
  [yq-go]=go-yq
  [zoom-us]=zoom
  [kubelogin-oidc]=kubelogin
  [qbittorrent-enhanced]=qbittorrent
)

# Ensemble de paquets Arch pour lookup O(1)
declare -A ARCH_SET=()
for p in "${ARCH_PKGS[@]}"; do
  ARCH_SET["$p"]=1
done

# Fonction de résolution du nom Arch à partir du nom Nix
resolve_arch_name() {
  local nix="$1"
  local cand="${MAP_NIX_TO_ARCH[$nix]:-$nix}"

  # direct
  if [[ -n "${ARCH_SET[$cand]:-}" ]]; then
    echo "$cand"
    return 0
  fi

  # variantes fréquentes sur Arch/AUR
  local v
  for v in "$cand-bin" "$cand-git" "$cand-bin-git"; do
    if [[ -n "${ARCH_SET[$v]:-}" ]]; then
      echo "$v"
      return 0
    fi
  done

  return 1
}

# 4) Calcul des doublons (Arch <-> Nix)
declare -a DUP_ARCH=()
declare -a DUP_NIX=()

for nix in "${HM_PKGS[@]}"; do
  if arch_name="$(resolve_arch_name "$nix")"; then
    # Protéger 'yay' par défaut (on l'affichera mais on ne le supprimera pas sauf --include-yay)
    if [[ "$arch_name" == "yay" && $INCLUDE_YAY -eq 0 ]]; then
      :
    fi
    DUP_ARCH+=("$arch_name")
    DUP_NIX+=("$nix")
  fi
done

# Dédupliquer en gardant l'alignement Arch<->Nix
declare -A seen=()
declare -a U_ARCH=()
declare -a U_NIX=()
for i in "${!DUP_ARCH[@]}"; do
  key="${DUP_ARCH[$i]}|${DUP_NIX[$i]}"
  if [[ -z "${seen[$key]:-}" ]]; then
    seen[$key]=1
    U_ARCH+=("${DUP_ARCH[$i]}")
    U_NIX+=("${DUP_NIX[$i]}")
  fi
done

if [[ ${#U_ARCH[@]} -eq 0 ]]; then
  echo "Aucun doublon Arch/Home‑Manager détecté 🎉"
  exit 0
fi

# 5) Affichage demandé: "Arch -> Nix"
echo "Doublons détectés (Arch -> Nix):"
for i in "${!U_ARCH[@]}"; do
  printf "  %s -> %s\n" "${U_ARCH[$i]}" "${U_NIX[$i]}"
done

# Préparer la liste pour désinstallation (en excluant 'yay' sauf --include-yay)
declare -a TO_REMOVE=()
for i in "${!U_ARCH[@]}"; do
  if [[ "${U_ARCH[$i]}" == "yay" && $INCLUDE_YAY -eq 0 ]]; then
    continue
  fi
  TO_REMOVE+=("${U_ARCH[$i]}")
done

if [[ ${#TO_REMOVE[@]} -eq 0 ]]; then
  echo
  echo "Rien à désinstaller (ou seulement 'yay', ignoré par défaut)."
  exit 0
fi

echo
echo "Total à désinstaller côté Arch: ${#TO_REMOVE[@]} paquet(s)"
printf '  %s\n' "${TO_REMOVE[@]}"

if [[ $DRYRUN -eq 1 ]]; then
  echo
  echo "[Dry‑run] Aucune désinstallation ne sera effectuée."
  exit 0
fi

if [[ $CONFIRM -ne 0 ]]; then
  read -r -p "Confirmer la désinstallation via 'yay -Rns' ? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "Annulé."; exit 0 ;;
  esac
fi

# 6) Désinstallation
if have_cmd yay; then
  # On met 'yay' en dernier si --include-yay est activé (sécurité)
  if [[ $INCLUDE_YAY -eq 1 ]]; then
    # séparer 'yay' du reste
    declare -a NOYAY=() YAYLAST=()
    for p in "${TO_REMOVE[@]}"; do
      if [[ "$p" == "yay" ]]; then YAYLAST+=("$p"); else NOYAY+=("$p"); fi
    done
    TO_REMOVE=("${NOYAY[@]}" "${YAYLAST[@]}")
  fi
  yay -Rns "${TO_REMOVE[@]}"
else
  # Fallback pacman (pour paquets officiels seulement)
  echo "Avertissement: 'yay' introuvable, fallback vers 'sudo pacman -Rns'."
  sudo pacman -Rns "${TO_REMOVE[@]}"
fi
