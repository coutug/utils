#!/usr/bin/env bash
set -euo pipefail

# Description: Remove finalizers from every namespaced CRD instance found in a namespace.
# Functioning: Lists namespaced resources, retrieves objects in the namespace, and patches each to clear metadata.finalizers.
# How to use: Run with the namespace as the first argument. Example: ./bash/remove-crd-finalizers.sh my-namespace

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <namespace>" >&2
  exit 1
fi

NAMESPACE=$1
PATCH_PAYLOAD='{"metadata":{"finalizers":null}}'

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required in PATH." >&2
  exit 1
fi

if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
  echo "Namespace '$NAMESPACE' not found." >&2
  exit 1
fi

resources=$(kubectl api-resources --namespaced=true --verbs=list | awk 'NR>1 {print $1}' | grep -Ev '^(events)$')

for resource in $resources; do
  [[ -z "$resource" ]] && continue

  instances=$(kubectl get "$resource" -n "$NAMESPACE" --ignore-not-found -o name 2>/dev/null || true)
  [[ -z "$instances" ]] && continue

  echo "Processing $resource in namespace $NAMESPACE"

  for instance in $instances; do
    echo "  - Patching $instance"
    if ! kubectl patch "$instance" -n "$NAMESPACE" --type=merge -p "$PATCH_PAYLOAD" >/dev/null && kubectl delete "$instance" -n "$NAMESPACE"; then
      echo "    Failed to patch $instance" >&2
    fi
  done
done
