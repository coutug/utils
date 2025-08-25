#!/usr/bin/env python3
"""
Description: Rework Grafana dashboard JSON files to standardize datasource usage.
Functioning: Unwraps exported dashboards, ensures a datasource variable, and rewrites panel datasource fields.
How to use: python3 rework_dashboards.py <input> [--output-dir DIR | --in-place] [--prom-only | --all-sources]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

def parse_args():
    p = argparse.ArgumentParser(description="Rework Grafana dashboard JSON files.")
    p.add_argument("inputs", nargs="+", help="Input files and/or directories")
    p.add_argument("-o", "--output-dir", default=None, help="Write outputs under this directory (mirror structure)")
    p.add_argument("--glob", default="*.json", help="Glob to match when inputs include directories (default: *.json)")
    p.add_argument("--in-place", action="store_true", help="Overwrite files in place")
    p.add_argument("--ds-name", default="VictoriaMetrics-ops", help="Datasource name to set as current (default: VictoriaMetrics-ops)")
    p.add_argument("--var-name", default="DS_PROMETHEUS", help="Dashboard variable name (default: DS_PROMETHEUS)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--prom-only", action="store_true", help='Only rewrite datasource OBJECTS with type=="prometheus"; leave STRING values untouched (conservative)')
    mode.add_argument("--all-sources", action="store_true", help="Rewrite both OBJECT and STRING datasource fields (except Grafana internal annotations)")
    p.add_argument("--dry-run", action="store_true", help="Do not write files, just print what would be done")
    return p.parse_args()

def iter_input_files(paths: List[str], pattern: str) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for f in path.rglob(pattern):
                if f.is_file():
                    files.append(f)
        else:
            print(f"⚠️  Not found: {path}", file=sys.stderr)
    return files

def unwrap_dashboard_root(data: Any) -> Any:
    # Some exports wrap {"dashboard": {...}, "meta": {...}}; unwrap to the "dashboard" content.
    if isinstance(data, dict) and "dashboard" in data and isinstance(data["dashboard"], dict):
        return data["dashboard"]
    return data

def ensure_ds_variable(d: Dict[str, Any], var_name: str, ds_name: str) -> None:
    d.setdefault("templating", {})
    if not isinstance(d["templating"], dict):
        d["templating"] = {}
    d["templating"].setdefault("list", [])
    if not isinstance(d["templating"]["list"], list):
        d["templating"]["list"] = []

    ds_var = {
        "type": "datasource",
        "name": var_name,
        "label": "Datasource",
        "query": "prometheus",
        "current": {"text": ds_name, "value": ds_name, "selected": True},
        "hide": 2
    }

    # Replace if an existing var with same name & type exists; else append
    replaced = False
    for i, var in enumerate(d["templating"]["list"]):
        if isinstance(var, dict) and var.get("type") == "datasource" and var.get("name") == var_name:
            d["templating"]["list"][i] = ds_var
            replaced = True
            break
    if not replaced:
        d["templating"]["list"].append(ds_var)

def is_annotation_ds(obj: Any) -> bool:
    # Grafana built-in annotation datasource looks like {"type":"datasource","uid":"grafana"}
    return isinstance(obj, dict) and obj.get("type") == "datasource"

def rewrite_datasources(node: Any, var_name: str, prom_only: bool, rewrite_strings: bool) -> Any:
    """
    Recursively rewrite panel/target "datasource" fields to "${VAR_NAME}".
    - Skip Grafana internal annotation datasource objects.
    - If prom_only is True: only rewrite OBJECT datasources where .type == "prometheus".
      (STRING datasources left as-is unless rewrite_strings is True.)
    - If prom_only is False: rewrite all OBJECT datasources except annotations. STRINGs based on rewrite_strings.
    """
    if isinstance(node, dict):
        new_node = {}
        for k, v in node.items():
            if k == "datasource":
                # Determine what to do based on value type
                if is_annotation_ds(v):
                    # leave annotation datasources untouched
                    new_node[k] = v
                elif isinstance(v, dict):
                    if prom_only:
                        if v.get("type") == "prometheus":
                            new_node[k] = f"${{{var_name}}}"
                        else:
                            new_node[k] = v
                    else:
                        # rewrite any non-annotation object
                        new_node[k] = f"${{{var_name}}}"
                elif isinstance(v, str):
                    if rewrite_strings:
                        new_node[k] = f"${{{var_name}}}"
                    else:
                        new_node[k] = v
                else:
                    new_node[k] = v
            else:
                new_node[k] = rewrite_datasources(v, var_name, prom_only, rewrite_strings)
        return new_node
    elif isinstance(node, list):
        return [rewrite_datasources(x, var_name, prom_only, rewrite_strings) for x in node]
    else:
        return node

def process_file(path: Path, outdir: Union[Path, None], in_place: bool, var_name: str, ds_name: str,
                 prom_only: bool, all_sources: bool, dry_run: bool) -> Union[Path, None]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as e:
        print(f"❌ Failed to read/parse {path}: {e}", file=sys.stderr)
        return None

    # 1) Unwrap {"dashboard": {...}, "meta": {...}} to just {...}
    dash = unwrap_dashboard_root(data)

    # 2) Ensure templating variable
    ensure_ds_variable(dash, var_name=var_name, ds_name=ds_name)

    # 3) Rewrite datasources
    rewrite_strings = all_sources  # only rewrite strings when --all-sources is used
    dash = rewrite_datasources(dash, var_name=var_name, prom_only=prom_only, rewrite_strings=rewrite_strings)

    # Decide output path
    if in_place:
        out_path = path
    elif outdir:
        rel = path.name if path.is_file() else path.as_posix()
        out_path = Path(outdir) / Path(rel).name
    else:
        out_path = path.with_name(path.stem + "_reworked.json")

    if dry_run:
        print(f"DRY-RUN would write: {out_path}")
        return out_path

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(dash, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"✅ Wrote {out_path}")
        return out_path
    except Exception as e:
        print(f"❌ Failed to write {out_path}: {e}", file=sys.stderr)
        return None

def main():
    args = parse_args()
    files = iter_input_files(args.inputs, args.glob)
    if not files:
        print("No files found.", file=sys.stderr)
        sys.exit(2)

    for f in files:
        process_file(
            path=f,
            outdir=Path(args.output_dir) if args.output_dir else None,
            in_place=args.in_place,
            var_name=args.var_name,
            ds_name=args.ds_name,
            prom_only=args.prom_only,
            all_sources=args.all_sources,
            dry_run=args.dry_run,
        )

if __name__ == "__main__":
    main()
