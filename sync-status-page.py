#!/usr/bin/env python3

import os
import sys
import json
import logging
from collections import defaultdict

import requests
from dotenv import load_dotenv

# =======================
# Chargement configuration
# =======================
load_dotenv()

# ---- Logging (stderr) ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("spm-checker")

# ---- Config API / Noms de types & attributs ----
BASE = os.getenv("INCIDENT_API_BASE", "https://api.incident.io")
TOKEN = os.getenv("INCIDENT_API_TOKEN")

# Noms logiques des types — insensibles à la casse.
TYPE_NAMES = {
    "component": os.getenv("COMPONENT_TYPE_NAME", "Component"),
    "network":   os.getenv("NETWORK_TYPE_NAME", "Network"),
    "spm":       os.getenv("SPM_TYPE_NAME", "Status Page Map"),  # défaut adapté à ton schéma
}

# Noms / IDs des attributs — on matche par nom (case-insensitive) OU par id exact.
# Par défaut, on colle à ton schéma:
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
# Helpers API incident.io
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
    Retourne (attribute_id, attribute_object) en matant soit par 'name' (case-insensitive),
    soit par 'id' exact si 'key' semble être un id.
    """
    attrs = cat_type.get("schema",{}).get("attributes",[])
    # 1) Essai par id exact
    for a in attrs:
        if key == a.get("id"):
            return a["id"], a
    # 2) Essai par nom (case-insensitive)
    key_low = (key or "").lower()
    for a in attrs:
        if (a.get("name","") or "").lower() == key_low:
            return a["id"], a
    # 3) Rien trouvé
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
# Helpers de résolution & extraction de valeurs
# ===========================================
def build_extindex(catalog_type_id):
    """
    Construit un index external_id -> (id, name) pour un type donné.
    Utile pour résoudre les attributs Custom[...] (value.literal = external_id).
    """
    idx = {}
    count = 0
    for e in paginate_entries(catalog_type_id):
        count += 1
        ext = e.get("external_id")
        if ext:
            idx[ext] = (e["id"], e.get("name") or ext)
    logger.info("Index construit pour type %s (entrées=%d, external_ids=%d)",
                catalog_type_id, count, len(idx))
    return idx

def extract_single_custom(attr_value_obj, ext_index=None):
    """
    Supporte deux formats:
      - Format Custom[...] (V3 courant): value.literal (= external_id) et value.label
      - Format relationnel 'catalog_entry' (héritage / clients lib)
    Retour: (id, name) si résolu, sinon (None, label/literal) pour diagnostic.
    """
    if not attr_value_obj:
        return (None, None)
    v = attr_value_obj.get("value") or {}

    # Format Custom[...] : external_id dans 'literal'
    lit = v.get("literal")
    if lit is not None:
        if ext_index:
            rid, rname = ext_index.get(lit, (None, v.get("label") or lit))
            return (rid, rname)
        return (None, v.get("label") or lit)

    # Ancien format: objet catalog_entry
    ce = v.get("catalog_entry") or {}
    rid = ce.get("catalog_entry_id")
    rname = ce.get("catalog_entry_name")
    if rid:
        return (rid, rname)

    # Dernier recours: label
    return (None, v.get("label"))

def extract_array_custom(attr_value_obj, ext_index=None):
    """
    Gère les attributs 'array' contenant des références Custom[...] à des catalog entries.
    Supporte:
      - array_value: [ {"label":"...","literal":"..."} ]              # format 'plat'
      - array_value: [ {"value":{"label":"...","literal":"..."}} ]    # format 'value'
      - array_value: [ {"value":{"catalog_entry":{...}}} ]            # ancien format relationnel
    Retourne une liste de tuples (id, name, external_id_or_none).
      - id peut être None si l'external_id ne matche pas une entrée connue (index absent)
      - name sera le label (ou literal) si pas résolu
      - external_id_or_none est utile pour logger/diagnostiquer
    """
    out = []
    if not attr_value_obj:
        return out

    arr = attr_value_obj.get("array_value")
    if isinstance(arr, list) and arr:
        for item in arr:
            if not isinstance(item, dict):
                continue

            # --- Format plat: {label, literal}
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

            # --- Format avec 'value': {...}
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

            # 2.2) Ancien format relationnel via catalog_entry
            ce = v.get("catalog_entry") or {}
            rid = ce.get("catalog_entry_id")
            rname = ce.get("catalog_entry_name")
            if rid or rname:
                out.append((rid, rname, None))

    # Fallback si l'API renvoie une valeur simple au lieu d'un tableau
    if not out:
        rid, rname = extract_single_custom(attr_value_obj, ext_index)
        if rid or rname:
            out.append((rid, rname, None))

    return out


# =========
# Programme
# =========
def main():
    # 1) Résolution des types & attributs
    types = list_types()
    t_component = find_type(types, TYPE_NAMES["component"])
    t_network   = find_type(types, TYPE_NAMES["network"])
    t_spm       = find_type(types, TYPE_NAMES["spm"])

    comp_networks_attr_id, _ = attr_id_by_name_or_id(t_component, ATTR_NAMES["component_networks"])
    spm_component_attr_id, _ = attr_id_by_name_or_id(t_spm, ATTR_NAMES["spm_component"])
    spm_network_attr_id, _   = attr_id_by_name_or_id(t_spm, ATTR_NAMES["spm_network"])

    # 2) Index external_id -> (id, name) pour Component & Network
    idx_component = build_extindex(t_component["id"])
    idx_network   = build_extindex(t_network["id"])

    # 3) Lecture des SPM: extraction (component_id, network_id)
    logger.info("Lecture des entrées du type 'Status page map'...")
    spm_pairs = defaultdict(set)  # comp_id -> set([network_id or None])
    components_in_spm = set()
    component_names = {}          # comp_id -> friendly name
    count_spm = 0

    first_dump_done = False

    for spm in paginate_entries(t_spm["id"]):
        count_spm += 1
        av = spm.get("attribute_values", {}) or {}

        # Dump de diagnostic (une seule fois, en DEBUG)
        if LOG_LEVEL == "DEBUG" and not first_dump_done:
            logger.debug("Exemple attribute_values SPM: %s", json.dumps(av, ensure_ascii=False))
            first_dump_done = True

        comp_id, comp_name = extract_single_custom(av.get(spm_component_attr_id), idx_component)
        if not comp_id:
            logger.warning(
                "SPM '%s' sans component résolu (value=%s). Vérifie que le external_id du Component existe.",
                spm.get("name"),
                json.dumps((av.get(spm_component_attr_id) or {}).get("value"), ensure_ascii=False)
            )
            continue

        if comp_name:
            component_names[comp_id] = comp_name
        components_in_spm.add(comp_id)

        net_id, net_name = extract_single_custom(av.get(spm_network_attr_id), idx_network)
        # net_id peut être None si pas de network (cas attendu)
        spm_pairs[comp_id].add(net_id)

    # LOG #1 — Components extraits depuis SPM
    comp_list_for_log = [
        {"component_id": cid, "component_name": component_names.get(cid)}
        for cid in sorted(components_in_spm)
    ]
    logger.info("Components extraits depuis Status page map (total=%d): %s",
                len(comp_list_for_log), json.dumps(comp_list_for_log, ensure_ascii=False))

    # 4) Pour chaque component présent dans SPM, découvrir ses networks réels
    logger.info("Inspection des components pour découvrir leurs networks...")
    missing = []
    comp_to_discovered_networks = {}  # comp_id -> [{"network_id":..., "network_name":..., "network_external_id":...}, ...]
    unresolved_all = []               # pour output JSON

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
        nets = extract_array_custom(nets_attr, idx_network)  # liste de (nid, nname, nlit)

        # Stats & logs résolutions
        resolved = sum(1 for (nid, _, _) in nets if nid)
        unresolved = [(nlit or nname) for (nid, nname, nlit) in nets if not nid]
        if unresolved:
            logger.warning(
                "Component '%s' (%s): %d/%d network(s) non résolus via external_id: %s",
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

        # S'il n'y a aucun network: on ne vérifie rien (comme demandé)
        if not nets:
            continue

        existing_nets = spm_pairs.get(comp_id, set())
        for nid, nname, nlit in nets:
            if not nid:
                # Non résolu → déjà loggé ci-dessus
                continue
            if nid not in existing_nets:
                missing.append({
                    "component_id": comp_id,
                    "component_name": comp_name,
                    "network_id": nid,
                    "network_name": nname,
                })

    # LOG #2 — Networks découverts pour chaque component
    networks_log = []
    for comp_id in sorted(components_in_spm):
        networks_log.append({
            "component_id": comp_id,
            "component_name": component_names.get(comp_id),
            "networks": comp_to_discovered_networks.get(comp_id, [])
        })
    logger.info("Networks découverts pour chaque component référencé dans SPM: %s",
                json.dumps(networks_log, ensure_ascii=False))

    # 5) Sortie JSON finale (stdout)
    result = {
        "count": len(missing),
        "missing_component_network_mappings": missing,
        "unresolved_networks": unresolved_all,  # utile pour corriger les external_id incohérents
        "stats": {
            "status_page_map_entries": count_spm,
            "unique_components_in_spm": len(components_in_spm),
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Échec du script")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)