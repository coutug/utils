NS=$1

echo "Namespace: $NS"

for resource in $(kubectl api-resources --verbs=list --namespaced -o name); do
  echo "-> Getting: $resource"
  resources=$(kubectl get "$resource" -n "$NS" --ignore-not-found=true)

  if [ -n "$resources" ]; then
    echo "$resources"

    read -p "Do you want to delete? (y/n): " answer
    if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
        echo "Not deleting"
        continue
    fi

    kubectl delete "$resource" --all -n "$NS" --wait=false --ignore-not-found=true

    for obj in $(kubectl get "$resource" -n "$NS" -o jsonpath='{.items[*].metadata.name}'); do
      echo "Patch finalizers for $resource/$obj"
      kubectl patch "$resource" "$obj" -n "$NS" -p '{"metadata":{"finalizers":null}}' --type=merge
    done
  fi
done
