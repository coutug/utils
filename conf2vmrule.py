#!/usr/bin/env python3
"""
Description: Convert an Icinga-style .conf service definition using a Prometheus check into a VictoriaMetrics VMRule YAML.
Functioning: Extracts metric details and thresholds from the .conf file, cleans label matchers, and builds a VMRule expression.
How to use: python3 conf2vmrule.py /path/to/myAlert.conf [--write | -o out.yaml]

Notes & assumptions:
- Expects variables like:
  vars.check_prometheus_metric_name
  vars.check_prometheus_metric_query
  vars.check_prometheus_metric_warning
  vars.check_prometheus_metric_critical
- Thresholds like "0:10000000000" will use the right side (upper bound).
  If a single number is provided, it's used as-is.
- If check_prometheus_metric_name is missing, falls back to the Service name.
- The YAML expr uses the query (after cleaning variable-based label filters)
  as the left-hand side, e.g. `round(metric, 0.1) > 123`.

Label cleaning rules:
- Any label matcher whose value contains a variable placeholder is removed.
  Recognized placeholders: %VAR%, {{var}}, $VAR, ${VAR}
- If the label set becomes empty after removals, the entire `{ ... }` is dropped.
"""

import argparse
import re
from pathlib import Path
from typing import Optional, Tuple, List

# --- Patterns to extract values (support inner quotes/newlines) ---
RE_SERVICE_NAME = re.compile(r'apply\s+Service\s+"([^"]+)"')
RE_METRIC_NAME  = re.compile(r'vars\.check_prometheus_metric_name\s*=\s*(["\'])(.*?)\1', re.DOTALL)
RE_METRIC_QUERY = re.compile(r'vars\.check_prometheus_metric_query\s*=\s*(["\'])(.*?)\1', re.DOTALL)
RE_WARN         = re.compile(r'vars\.check_prometheus_metric_warning\s*=\s*(["\'])(.*?)\1', re.DOTALL)
RE_CRIT         = re.compile(r'vars\.check_prometheus_metric_critical\s*=\s*(["\'])(.*?)\1', re.DOTALL)

def extract(text: str, regex: re.Pattern) -> Optional[str]:
  m = regex.search(text)
  if not m:
    return None
  try:
    return m.group(2)  # value inside quotes
  except IndexError:
    return m.group(1)

def parse_threshold(raw: Optional[str]) -> Optional[str]:
  if not raw:
    return None
  s = raw.strip()
  if ":" in s:
    left, right = s.split(":", 1)
    right = right.strip()
    return right if right not in ("", "~") else left.strip()
  return s

def metric_to_slug(name: str) -> str:
  return name.strip().lower().replace("_", "-")

def metric_to_words(name: str) -> str:
  return name.strip().lower().replace("_", " ")

# --- Query cleaning utilities ---

def _split_label_matchers(s: str) -> List[str]:
  """Split label matchers by commas *outside* quotes; return raw matcher strings."""
  parts = []
  buf = []
  in_single = False
  in_double = False
  esc = False
  for ch in s:
    if esc:
      buf.append(ch)
      esc = False
      continue
    if ch == "\\":
      buf.append(ch)
      esc = True
      continue
    if ch == "'" and not in_double:
      in_single = not in_single
      buf.append(ch)
      continue
    if ch == '"' and not in_single:
      in_double = not in_double
      buf.append(ch)
      continue
    if ch == "," and not in_single and not in_double:
      parts.append("".join(buf).strip())
      buf = []
      continue
    buf.append(ch)
  if buf:
    parts.append("".join(buf).strip())
  return [p for p in parts if p]

_PLACEHOLDER_RE = re.compile(r'(%[^%]+%|\{\{[^}]+\}\}|\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*)')
_LABEL_MATCHER_RE = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(=~|!~|=|!=)\s*(.+?)\s*$')

def clean_query(expr: str) -> str:
  """
  Remove label matchers whose values contain placeholders (e.g., hostname='%HOSTNAME%').
  If a label set becomes empty, remove the entire `{ ... }`.
  Brace/quote aware.
  """
  def has_placeholder(s: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(s))

  def reconstruct_labelset(content: str) -> str:
    matchers = _split_label_matchers(content)
    kept = []
    for m in matchers:
      mobj = _LABEL_MATCHER_RE.match(m.strip())
      if not mobj:
        # Keep unrecognized fragments to be conservative
        kept.append(m.strip())
        continue
      key, op, val = mobj.groups()
      v = val.strip()
      inner = v[1:-1] if (len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'"))) else v
      if has_placeholder(inner):
        continue
      kept.append(f"{key}{op}{v}" if v == val.strip() else m.strip())
    if not kept:
      return ""  # signal to remove entire label set
    return "{" + ", ".join(kept) + "}"

  out = []
  i = 0
  n = len(expr)
  in_single = in_double = False
  while i < n:
    ch = expr[i]
    if ch == "'" and not in_double:
      in_single = not in_single
      out.append(ch)
      i += 1
      continue
    if ch == '"' and not in_single:
      in_double = not in_double
      out.append(ch)
      i += 1
      continue
    if ch == "{" and not in_single and not in_double:
      # capture until matching }
      depth = 1
      j = i + 1
      sub_in_single = sub_in_double = False
      content = []
      while j < n and depth > 0:
        cj = expr[j]
        if cj == "'" and not sub_in_double:
          sub_in_single = not sub_in_single
          content.append(cj)
          j += 1
          continue
        if cj == '"' and not sub_in_single:
          sub_in_double = not sub_in_double
          content.append(cj)
          j += 1
          continue
        if cj == "{" and not sub_in_single and not sub_in_double:
          depth += 1
          content.append(cj)
          j += 1
          continue
        if cj == "}" and not sub_in_single and not sub_in_double:
          depth -= 1
          if depth == 0:
            j += 1
            break
          content.append(cj)
          j += 1
          continue
        content.append(cj)
        j += 1
      inner = "".join(content)
      rebuilt = reconstruct_labelset(inner) if ("{" not in inner and "}" not in inner) else "{" + inner + "}"
      if rebuilt == "":
        # remove entire label set
        pass
      else:
        out.append(rebuilt)
      i = j
      continue
    out.append(ch)
    i += 1
  result = "".join(out)
  result = result.replace("{ ", "{").replace(" }", "}")
  return result

# --- YAML building ---

def build_rule_block(metric_for_text: str, expr_left: str, threshold: str, severity: str) -> str:
  words = metric_to_words(metric_for_text)
  expr_line = f"{expr_left} > {threshold}"
  return (
    f"    - alert: {metric_for_text}\n"
    f"      annotations:\n"
    f"        summary: \"{words}\"\n"
    f"        description: \"{words} at {{ $value }} from {{ $labels.hostname }}\"\n"
    f"      expr: |\n"
    f"        {expr_line}\n"
    f"      labels:\n"
    f"        severity: {severity}\n"
  )

def convert_conf_to_yaml(conf_text: str) -> Tuple[str, str]:
  # Extract fields
  service_name = extract(conf_text, RE_SERVICE_NAME) or "unnamed_service"
  metric_name = extract(conf_text, RE_METRIC_NAME) or service_name
  metric_query = extract(conf_text, RE_METRIC_QUERY)
  warn_raw = extract(conf_text, RE_WARN)
  crit_raw = extract(conf_text, RE_CRIT)

  warn = parse_threshold(warn_raw)
  crit = parse_threshold(crit_raw)

  meta = metric_to_slug(metric_name)

  # Expr LHS: prefer cleaned query if available; else fall back to metric name
  expr_left = clean_query(metric_query) if metric_query else metric_name

  # Header
  header = (
    "apiVersion: operator.victoriametrics.com/v1beta1\n"
    "kind: VMRule\n"
    "metadata:\n"
    f"  name: {meta}\n"
    "spec:\n"
    "  groups:\n"
    f"  - name: {meta}\n"
    "    rules:\n"
  )

  rules = ""
  if warn is not None:
    rules += build_rule_block(metric_name, expr_left, warn, "warning")
    if not rules.endswith("\n"):
      rules += "\n"
  if crit is not None:
    if rules and not rules.endswith("\n"):
      rules += "\n"
    rules += build_rule_block(metric_name, expr_left, crit, "critical")

  if not rules:
    # If no thresholds, still output a single rule with just the query (no comparator).
    if metric_query:
      words = metric_to_words(metric_name)
      rules += (
        f"    - alert: {metric_name}\n"
        f"      annotations:\n"
        f"        summary: \"{words}\"\n"
        f"        description: \"{words} at {{ $value }} from {{ $labels.hostname }}\"\n"
        f"      expr: |\n"
        f"        {expr_left}\n"
        f"      labels:\n"
        f"        severity: info\n"
      )
    else:
      raise ValueError("No thresholds (warning/critical) found and no query available in the .conf file.")

  return metric_name, header + rules

def main():
  parser = argparse.ArgumentParser(description="Convert myAlert.conf to a VMRule YAML.")
  parser.add_argument("conf_path", help="Path to the .conf file to convert")
  parser.add_argument("-o", "--output", help="Write result to this path (overwrites if exists)")
  parser.add_argument("-w", "--write", action="store_true",
            help="Write next to input, using same name with .yaml extension")
  parser.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8)")
  args = parser.parse_args()

  conf_p = Path(args.conf_path)
  text = conf_p.read_text(encoding=args.encoding)
  metric_name, yaml_text = convert_conf_to_yaml(text)

  if args.output:
    out_p = Path(args.output)
    out_p.write_text(yaml_text, encoding="utf-8")
    print(f"Wrote {out_p}")
  elif args.write:
    out_p = conf_p.with_suffix(".yaml")
    out_p.write_text(yaml_text, encoding="utf-8")
    print(f"Wrote {out_p}")
  else:
    # Dry-run: print to stdout
    print(yaml_text)

if __name__ == "__main__":
  main()
