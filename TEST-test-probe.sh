#!/usr/bin/env bash
set -euo pipefail

# Config par variables d'env (modifiables au lancement)
HEY_BIN="${HEY_BIN:-hey}"       # binaire hey
SLEEP_SEC="${SLEEP_SEC:-10}"    # pause entre URLs
NREQ="${NREQ:-5}"               # nb de requêtes par URL et par tour
CONCURRENCY="${CONCURRENCY:-1}" # concurrence

URLS=(
  "https://mcp-token-api.service.pinax.network/health"
  "https://token-api.service.pinax.network/health"

  "https://ch-a.token-api.service.pinax.network/replicas_status"
  "https://ch-b.token-api.service.pinax.network/replicas_status"

  "https://antelope-api-wax.service.pinax.network/health"
  "https://antelope-api-eos.service.pinax.network/health"
  "https://antelope-api-kylin.service.pinax.network/health"
)

# Vérif hey présent
if ! command -v "$HEY_BIN" >/dev/null 2>&1; then
  echo "❌ hey introuvable. Installe-le et/ou fixe HEY_BIN." >&2
  exit 1
fi

while true; do
  for url in "${URLS[@]}"; do
    ts="$(date -Is)"
    # Lance hey (silence la barre de progression); capture sortie
    out="$("$HEY_BIN" --disable-keepalive -n "$NREQ" -c "$CONCURRENCY" "$url" 2>&1 || true)"

    # Parse la distribution des codes HTTP
    # On récupère les lignes du bloc "Status code distribution:"
    status_block="$(printf "%s\n" "$out" \
      | awk '/Status code distribution:/{f=1;print;next} f&&/^[[:space:]]*\[[0-9]{3}\]/{print} f&&!/^[[:space:]]*\[[0-9]{3}\]/{ if(NR>1) exit }')"

    total=0
    ok200=0

    # Extrait "  [200] 12 responses" => code=200, cnt=12
    while read -r code cnt _; do
      [[ -z "${code:-}" ]] && continue
      # code format "[200]"
      code="${code#[}"
      code="${code%]}"
      if [[ "$code" =~ ^[0-9]{3}$ && "$cnt" =~ ^[0-9]+$ ]]; then
        total=$((total + cnt))
        if [[ "$code" == "200" ]]; then
          ok200=$cnt
        fi
      fi
    done < <(printf "%s\n" "$status_block" | sed -n 's/^[[:space:]]*\[\([0-9]\{3\}\)\][[:space:]]*\([0-9]\+\).*/[\1] \2/p')

    # Si on n'a pas réussi à parser, considère comme erreur
    if [[ "$total" -eq 0 ]]; then
      echo "[$ts] ❌ $url → impossible de valider les réponses (hey a peut-être échoué)"
      printf "%s\n" "$out" | sed -n '1,120p' >&2
    elif [[ "$ok200" -eq "$total" ]]; then
      echo "[$ts] ✅ $url → OK (toutes $ok200/$total réponses sont 200)"
    else
      echo "[$ts] ⚠️  $url → ERREUR (codes non-200 détectés : $((total-ok200))/$total)"
      # Affiche un extrait utile
      printf "%s\n" "$status_block"
      # S'il existe, affiche aussi l'éventuel bloc d'erreurs de hey
      err_block="$(printf "%s\n" "$out" | awk '/Error distribution:/{f=1;print;next} f&&/^[[:space:]]*\[[0-9]+\]/{print} f&&!/^[[:space:]]*\[[0-9]+\]/{ if(NR>1) exit }')"
      [[ -n "$err_block" ]] && printf "%s\n" "$err_block"
    fi

    sleep "$SLEEP_SEC"
  done
done
