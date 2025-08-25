#!/usr/bin/env bash

# Description: Uninstall Arch packages that are also managed by Home‑Manager.
# Functioning: Collects Arch and Home‑Manager packages, maps names, optionally prompts, and removes duplicates.
# How to use: Requires yay (or pacman) and home-manager. Options: --yes/-y skip confirmation, --dry-run show only, --include-yay allow removing 'yay'.

set -u
set -o pipefail

CONFIRM=1
DRYRUN=0
INCLUDE_YAY=0

while (("$#")); do
  case "$1" in
    --yes | -y)
      CONFIRM=0
      shift
      ;;
    --dry-run)
      DRYRUN=1
      shift
      ;;
    --include-yay)
      INCLUDE_YAY=1
      shift
      ;;
    -h | --help)
      echo "Usage: $0 [--yes|-y] [--dry-run] [--include-yay]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

have_cmd() { command -v "$1" > /dev/null 2>&1; }

# 1) Retrieve explicitly installed Arch packages (AUR included)
if have_cmd yay; then
  mapfile -t ARCH_PKGS < <(yay -Qqe 2> /dev/null | sort -u)
elif have_cmd pacman; then
  mapfile -t ARCH_PKGS < <(pacman -Qqe 2> /dev/null | sort -u)
else
  echo "Error: neither 'yay' nor 'pacman' found in PATH." >&2
  exit 1
fi

# 2) Retrieve installed Home‑Manager packages (without version)
if ! have_cmd home-manager; then
  echo "Error: 'home-manager' not found in PATH." >&2
  exit 1
fi

# home-manager packages outputs names like 'act-0.2.77' (or sometimes .drv paths).
# Keep only the name without version.
mapfile -t HM_PKGS < <(
  home-manager packages \
    | sed -E 's#.*/##' \
    | sed -E 's/\.drv$//' \
    | sed -E 's/-[0-9][0-9A-Za-z._+~-]*$//' \
    | sed '/^$/d' \
    | sort -u
)

# 3) Mapping Nix -> Arch for divergent names
#    Add personal mappings here if needed.
declare -A MAP_NIX_TO_ARCH=(
  # Nix                  Arch
  [kubernetes - helm]=helm
  [yq - go]=go-yq
  [zoom - us]=zoom
  [kubelogin - oidc]=kubelogin
  [qbittorrent - enhanced]=qbittorrent
)

# Set of Arch packages for O(1) lookup
declare -A ARCH_SET=()
for p in "${ARCH_PKGS[@]}"; do
  ARCH_SET["$p"]=1
done

# Resolve the Arch package name from the Nix name
resolve_arch_name() {
  local nix="$1"
  local cand="${MAP_NIX_TO_ARCH[$nix]:-$nix}"

  # direct
  if [[ -n "${ARCH_SET[$cand]:-}" ]]; then
    echo "$cand"
    return 0
  fi

  # common Arch/AUR variants
  local v
  for v in "$cand-bin" "$cand-git" "$cand-bin-git"; do
    if [[ -n "${ARCH_SET[$v]:-}" ]]; then
      echo "$v"
      return 0
    fi
  done

  return 1
}

# 4) Compute duplicates (Arch <-> Nix)
declare -a DUP_ARCH=()
declare -a DUP_NIX=()

for nix in "${HM_PKGS[@]}"; do
  if arch_name="$(resolve_arch_name "$nix")"; then
    # Protect 'yay' by default (show but do not remove unless --include-yay)
    if [[ "$arch_name" == "yay" && $INCLUDE_YAY -eq 0 ]]; then
      :
    fi
    DUP_ARCH+=("$arch_name")
    DUP_NIX+=("$nix")
  fi
done

# Deduplicate while keeping Arch<->Nix alignment
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
  echo "No Arch/Home‑Manager duplicates detected 🎉"
  exit 0
fi

# 5) Display duplicates "Arch -> Nix"
echo "Duplicates detected (Arch -> Nix):"
for i in "${!U_ARCH[@]}"; do
  printf "  %s -> %s\n" "${U_ARCH[$i]}" "${U_NIX[$i]}"
done

# Prepare list for removal (excluding 'yay' unless --include-yay)
declare -a TO_REMOVE=()
for i in "${!U_ARCH[@]}"; do
  if [[ "${U_ARCH[$i]}" == "yay" && $INCLUDE_YAY -eq 0 ]]; then
    continue
  fi
  TO_REMOVE+=("${U_ARCH[$i]}")
done

if [[ ${#TO_REMOVE[@]} -eq 0 ]]; then
  echo
  echo "Nothing to uninstall (or only 'yay', ignored by default)."
  exit 0
fi

echo
echo "Total to uninstall on Arch side: ${#TO_REMOVE[@]} package(s)"
printf '  %s\n' "${TO_REMOVE[@]}"

if [[ $DRYRUN -eq 1 ]]; then
  echo
  echo "[Dry‑run] No uninstallation will be performed."
  exit 0
fi

if [[ $CONFIRM -ne 0 ]]; then
  read -r -p "Confirm removal via 'yay -Rns'? [y/N] " ans
  case "$ans" in
    y | Y | yes | YES) ;;
    *)
      echo "Cancelled."
      exit 0
      ;;
  esac
fi

# 6) Uninstall
if have_cmd yay; then
  # Place 'yay' last if --include-yay is enabled (safety)
  if [[ $INCLUDE_YAY -eq 1 ]]; then
    # separate 'yay' from the rest
    declare -a NOYAY=() YAYLAST=()
    for p in "${TO_REMOVE[@]}"; do
      if [[ "$p" == "yay" ]]; then YAYLAST+=("$p"); else NOYAY+=("$p"); fi
    done
    TO_REMOVE=("${NOYAY[@]}" "${YAYLAST[@]}")
  fi
  yay -Rns "${TO_REMOVE[@]}"
else
  # Fallback pacman (official packages only)
  echo "Warning: 'yay' not found, falling back to 'sudo pacman -Rns'."
  sudo pacman -Rns "${TO_REMOVE[@]}"
fi
