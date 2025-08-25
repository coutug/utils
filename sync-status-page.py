#!/usr/bin/env python3

import os
import sys
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

# =======================
# Configuration loading
# =======================
load_dotenv()

# ---- Logging (stderr) ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
  level=getattr(logging, LOG_LEVEL, logging.INFO),
  format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("spm-checker")

# ---- API config / Type & attribute names ----
BASE = os.getenv("INCIDENT_API_BASE", "https://api.incident.io")
TOKEN = os.getenv("INCIDENT_API_TOKEN")

# Alertmanager config (only used when count > 0, or if you choose to resolve)
ALERTMANAGER_ENABLE = os.getenv("ALERTMANAGER_ENABLE", "true")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://vmalertmanager-vmks-victoria-metrics-k8s-stack.monitoring.svc")
ALERTMANAGER_ROUTE = os.getenv("ALERTMANAGER_ROUTE", "/api/v2/alerts")
ALERTMANAGER_TIMEOUT = float(os.getenv("ALERTMANAGER_TIMEOUT", "10"))
ALERTMANAGER_ALERTNAME = os.getenv("ALERTMANAGER_ALERTNAME", "IncidentStatusPageMapDrift")
ALERTMANAGER_SEVERITY = os.getenv("ALERTMANAGER_SEVERITY", "warning")
ALERTMANAGER_COMPONENT_LABEL = os.getenv("ALERTMANAGER_COMPONENT_LABEL", "monitoring")
ALERTMANAGER_EXTRA_LABELS_JSON = os.getenv("ALERTMANAGER_EXTRA_LABELS_JSON", "")  # e.g. {"env":"prod"}

# Logical type names — case-insensitive.
TYPE_NAMES = {
  "component": os.getenv("COMPONENT_TYPE_NAME", "Component"),
  "network":   os.getenv("NETWORK_TYPE_NAME", "Network"),
  "spm":       os.getenv("SPM_TYPE_NAME", "Status Page Map"),  # default adapted to your schema
}

# Attribute names/IDs — matched by name (case-insensitive) or by exact id.
# By default, we follow your schema:
#  - Component.networks -> name "Networks supported" (id "networks")
#  - SPM.component      -> name "Component associated"
#  - SPM.network        -> name "Network associated"
ATTR_NAMES = {
  "component_networks": os.getenv("COMPONENT_NETWORKS_ATTR_NAME", "Networks supported"),
  "spm_component": os.getenv("SPM_COMPONENT_ATTR_NAME", "Component associated"),
  "spm_network":   os.getenv("SPM_NETWORK_ATTR_NAME", "Network associated"),
}

if not TOKEN:
  print("Missing INCIDENT_API_TOKEN", file=sys.stderr)
  sys.exit(2)

S = requests.Session()
S.headers.update({"Authorization": f"Bearer {TOKEN}"})


# =======================
# incident.io API helpers
# =======================
def list_types():
  r = S.get(f"{BASE}/v3/catalog_types", timeout=30)
  r.raise_for_status()
  return r.json()["catalog_types"]

def find_type(types, name):
  for t in types:
    if (t.get("name","") or "").lower() == name.lower():
      return t
  raise RuntimeError(f"Catalog type not found: {name}")

def attr_id_by_name_or_id(cat_type, key):
  """
  Return (attribute_id, attribute_object) matching either by name (case-insensitive)
  or by exact id if 'key' looks like an id.
  """
  attrs = cat_type.get("schema",{}).get("attributes",[])
  # 1) Try by exact id
  for a in attrs:
    if key == a.get("id"):
      return a["id"], a
  # 2) Try by name (case-insensitive)
  key_low = (key or "").lower()
  for a in attrs:
    if (a.get("name","") or "").lower() == key_low:
      return a["id"], a
  # 3) Nothing found
  raise RuntimeError(f"Attribute not found on type '{cat_type.get('name')}': {key}")

def paginate_entries(catalog_type_id):
  after = None
  while True:
    params = {"catalog_type_id": catalog_type_id, "page_size": 250}
    if after:
      params["after"] = after
    r = S.get(f"{BASE}/v3/catalog_entries", params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    for e in data.get("catalog_entries", []):
      yield e
    after = data.get("pagination_meta", {}).get("after")
    if not after:
      break

def show_entry(entry_id):
  r = S.get(f"{BASE}/v3/catalog_entries/{entry_id}", timeout=30)
  r.raise_for_status()
  return r.json()["catalog_entry"]


# ===========================================
# Helpers for resolving & extracting values
# ===========================================
def build_extindex(catalog_type_id):
  """
  Build an index external_id -> (id, name) for a given type.
  Useful to resolve Custom[...] attributes (value.literal = external_id).
  """
  idx = {}
  count = 0
  for e in paginate_entries(catalog_type_id):
    count += 1
    ext = e.get("external_id")
    if ext:
      idx[ext] = (e["id"], e.get("name") or ext)
  logger.info("Index built for type %s (entries=%d, external_ids=%d)",
        catalog_type_id, count, len(idx))
  return idx

def extract_single_custom(attr_value_obj, ext_index=None):
  """
  Supports two formats:
    - Custom[...] format (current V3): value.literal (= external_id) and value.label
    - Relational 'catalog_entry' format (legacy / client library)
  Returns: (id, name) if resolved, otherwise (None, label/literal) for diagnostics.
  """
  if not attr_value_obj:
    return (None, None)
  v = attr_value_obj.get("value") or {}

  # Custom[...] format: external_id in 'literal'
  lit = v.get("literal")
  if lit is not None:
    if ext_index:
      rid, rname = ext_index.get(lit, (None, v.get("label") or lit))
      return (rid, rname)
    return (None, v.get("label") or lit)

  # Legacy format: catalog_entry object
  ce = v.get("catalog_entry") or {}
  rid = ce.get("catalog_entry_id")
  rname = ce.get("catalog_entry_name")
  if rid:
    return (rid, rname)

  # Last resort: label
  return (None, v.get("label"))

def extract_array_custom(attr_value_obj, ext_index=None):
  """
  Handle 'array' attributes containing Custom[...] references to catalog entries.
  Supports:
    - array_value: [ {"label":"...","literal":"..."} ]              # flat format
    - array_value: [ {"value":{"label":"...","literal":"..."}} ]    # value format
    - array_value: [ {"value":{"catalog_entry":{...}}} ]            # legacy relational format
  Returns a list of tuples (id, name, external_id_or_none).
    - id can be None if the external_id doesn't match a known entry (missing index)
    - name will be the label (or literal) if not resolved
    - external_id_or_none is useful for logging/diagnostics
  """
  out = []
  if not attr_value_obj:
    return out

  arr = attr_value_obj.get("array_value")
  if isinstance(arr, list) and arr:
    for item in arr:
      if not isinstance(item, dict):
        continue

      # --- Flat format: {label, literal}
      if "literal" in item or "label" in item:
        lit = item.get("literal")
        lab = item.get("label")
        if lit is not None:
          if ext_index:
            rid, rname = ext_index.get(lit, (None, lab or lit))
            out.append((rid, rname, lit))
          else:
            out.append((None, lab or lit, lit))
        else:
          out.append((None, lab, None))
        continue

      # --- Format with 'value': {...}
      v = (item or {}).get("value") or {}

      # 2.1) Custom[...] via literal/label
      lit = v.get("literal")
      if lit is not None:
        lab = v.get("label") or lit
        if ext_index:
          rid, rname = ext_index.get(lit, (None, lab))
          out.append((rid, rname, lit))
        else:
          out.append((None, lab, lit))
        continue

      # 2.2) Legacy relational format via catalog_entry
      ce = v.get("catalog_entry") or {}
      rid = ce.get("catalog_entry_id")
      rname = ce.get("catalog_entry_name")
      if rid or rname:
        out.append((rid, rname, None))

  # Fallback if the API returns a simple value instead of an array
  if not out:
    rid, rname = extract_single_custom(attr_value_obj, ext_index)
    if rid or rname:
      out.append((rid, rname, None))

  return out


# ===========================================
# Alertmanager — send alert
# ===========================================
def send_alert_to_alertmanager(diff_count, missing):
  """
  Send an alert to Alertmanager (POST /api/v2/alerts) describing the drift.
  Called only when diff_count > 0.
  """
  if not ALERTMANAGER_URL:
    logger.info("ALERTMANAGER_URL is not set — skipping Alertmanager POST.")
    return

  labels = {
    "alertname": ALERTMANAGER_ALERTNAME,
    "severity": ALERTMANAGER_SEVERITY,
    "component": ALERTMANAGER_COMPONENT_LABEL,
  }
  # Optional extra labels as JSON
  if ALERTMANAGER_EXTRA_LABELS_JSON:
    try:
      labels.update(json.loads(ALERTMANAGER_EXTRA_LABELS_JSON))
    except Exception as e:
      logger.warning("ALERTMANAGER_EXTRA_LABELS_JSON invalid JSON: %s", e)

  # Compose a readable preview list (limited)
  MAX_LINES = int(os.getenv("ALERTMANAGER_ANNOTATION_MAX_LINES", "20"))
  lines = []
  for i, m in enumerate(missing[:MAX_LINES], start=1):
    comp = f'{m.get("component_name") or m.get("component_id")}'
    net  = f'{m.get("network_name") or m.get("network_id")}'
    lines.append(f"{i}. {comp} ↔ {net}")
  if len(missing) > MAX_LINES:
    lines.append(f"... (+{len(missing)-MAX_LINES} more)")

  annotations = {
    "summary": f"{diff_count} Status Page Map mapping(s) missing",
    "description": "\n".join(lines) if lines else "No details",
  }
  alert = {
    "labels": labels,
    "annotations": annotations,
    "startsAt": datetime.now(timezone.utc).isoformat(),
  }

  url = ALERTMANAGER_URL.rstrip("/") + ALERTMANAGER_ROUTE
  headers = {"Content-Type": "application/json"}

  try:
    r = requests.post(
      url, json=[alert], headers=headers,
      timeout=ALERTMANAGER_TIMEOUT, verify="false"
    )
    if r.status_code >= 300:
      logger.error("Alertmanager POST %s -> %s: %s", url, r.status_code, r.text[:500])
    else:
      logger.info("Alert sent to Alertmanager (%s)", url)
  except Exception as e:
    logger.exception("Failed to POST to Alertmanager: %s", e)


# =========
# Program
# =========
def main():
  # 1) Resolve types & attributes
  types = list_types()
  t_component = find_type(types, TYPE_NAMES["component"])
  t_network   = find_type(types, TYPE_NAMES["network"])
  t_spm       = find_type(types, TYPE_NAMES["spm"])

  comp_networks_attr_id, _ = attr_id_by_name_or_id(t_component, ATTR_NAMES["component_networks"])
  spm_component_attr_id, _ = attr_id_by_name_or_id(t_spm, ATTR_NAMES["spm_component"])
  spm_network_attr_id, _   = attr_id_by_name_or_id(t_spm, ATTR_NAMES["spm_network"])

  # 2) Index external_id -> (id, name) for Component & Network
  idx_component = build_extindex(t_component["id"])
  idx_network   = build_extindex(t_network["id"])

  # 3) Read SPM entries: extract (component_id, network_id)
  logger.info("Reading entries for 'Status page map' type...")
  spm_pairs = defaultdict(set)  # comp_id -> set([network_id or None])
  components_in_spm = set()
  component_names = {}          # comp_id -> friendly name
  count_spm = 0

  first_dump_done = False

  for spm in paginate_entries(t_spm["id"]):
    count_spm += 1
    av = spm.get("attribute_values", {}) or {}

    # Diagnostic dump (only once, in DEBUG)
    if LOG_LEVEL == "DEBUG" and not first_dump_done:
      logger.debug("Sample SPM attribute_values: %s", json.dumps(av, ensure_ascii=False))
      first_dump_done = True

    comp_id, comp_name = extract_single_custom(av.get(spm_component_attr_id), idx_component)
    if not comp_id:
      logger.warning(
        "SPM '%s' without resolved component (value=%s). Verify that the Component external_id exists.",
        spm.get("name"),
        json.dumps((av.get(spm_component_attr_id) or {}).get("value"), ensure_ascii=False)
      )
      continue

    if comp_name:
      component_names[comp_id] = comp_name
    components_in_spm.add(comp_id)

    net_id, _ = extract_single_custom(av.get(spm_network_attr_id), idx_network)
    # net_id can be None if there is no network (expected case)
    spm_pairs[comp_id].add(net_id)

  # LOG #1 — Components extracted from SPM
  comp_list_for_log = [
    {"component_id": cid, "component_name": component_names.get(cid)}
    for cid in sorted(components_in_spm)
  ]
  logger.info("Components extracted from Status page map (total=%d): %s",
        len(comp_list_for_log), json.dumps(comp_list_for_log, ensure_ascii=False))

  # 4) For each component present in SPM, discover its actual networks
  logger.info("Inspecting components to discover their networks...")
  missing = []
  comp_to_discovered_networks = {}  # comp_id -> [{"network_id":..., "network_name":..., "network_external_id":...}, ...]
  unresolved_all = []               # for output JSON

  cache = {}
  def get_component(entry_id):
    if entry_id not in cache:
      cache[entry_id] = show_entry(entry_id)
    return cache[entry_id]

  for comp_id in sorted(components_in_spm):
    comp = get_component(comp_id)
    comp_name = comp.get("name", comp_id)
    component_names[comp_id] = component_names.get(comp_id) or comp_name

    nets_attr = (comp.get("attribute_values", {}) or {}).get(comp_networks_attr_id)
    nets = extract_array_custom(nets_attr, idx_network)  # list of (nid, nname, nlit)

    unresolved = [(nlit or nname) for (nid, nname, nlit) in nets if not nid]
    if unresolved:
      logger.warning(
        "Component '%s' (%s): %d/%d network(s) unresolved via external_id: %s",
        comp_name, comp_id, len(unresolved), len(nets), ", ".join(unresolved)
      )
      for u in unresolved:
        unresolved_all.append({
          "component_id": comp_id,
          "component_name": comp_name,
          "network_external_id": u
        })

    comp_to_discovered_networks[comp_id] = [
      {
        "network_id": nid,
        "network_name": nname,
        "network_external_id": nlit
      }
      for (nid, nname, nlit) in nets
    ]

    # If there is no network, skip verification (as requested)
    if not nets:
      continue

    existing_nets = spm_pairs.get(comp_id, set())
    for nid, nname, nlit in nets:
      if not nid:
        # Unresolved → already logged above
        continue
      if nid not in existing_nets:
        missing.append({
          "component_id": comp_id,
          "component_name": comp_name,
          "network_id": nid,
          "network_name": nname,
        })

  # 5) Output & Alertmanager
  diff_count = len(missing)

  if diff_count == 0:
    # As requested: only output the count when there is no difference
    print(json.dumps({"count": 0}, indent=2, ensure_ascii=False))
    return # exit the function

  # LOG #2 — Networks discovered for each component
  networks_log = []
  for comp_id in sorted(components_in_spm):
    networks_log.append({
      "component_id": comp_id,
      "component_name": component_names.get(comp_id),
      "networks": comp_to_discovered_networks.get(comp_id, [])
    })
  logger.info("Networks discovered for each component referenced in SPM: %s",
        json.dumps(networks_log, indent=2, ensure_ascii=False))

  # Send alert to Alertmanager (only if configured)
  if ALERTMANAGER_ENABLE == "true":
    send_alert_to_alertmanager(diff_count, missing)

  # Detailed JSON output when differences exist
  result = {
    "count": diff_count,
    "missing_component_network_mappings": missing,
    "unresolved_networks": unresolved_all,  # useful to fix inconsistent external_ids
    "stats": {
      "status_page_map_entries": sum(len(v) for v in spm_pairs.values()),
      "unique_components_in_spm": len(components_in_spm),
    }
  }
  print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    logger.exception("Script failed")
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
