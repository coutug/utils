#!/usr/bin/env python3
"""
Description: Generate README listing all scripts with descriptions.
Functioning: Scans the bash/ and python/ folders for scripts, extracts their description blocks, and writes README.md.
How to use: Run `python python/update_readme.py` from the repository root.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

# The static header that will be kept at the top of README.md
README_HEADER = "# utils\nUseful scripts collection built along the journey\n"


def extract_description(path: Path) -> str:
  """Return the standardized description block for the script."""
  lines: list[str] = []
  if path.suffix == ".py":
    with path.open("r", encoding="utf-8") as f:
      try:
        module = ast.parse(f.read())
        doc = ast.get_docstring(module)
        if doc:
          lines = [l.strip() for l in doc.strip().splitlines() if l.strip()]
      except SyntaxError:
        pass
  if not lines:
    with path.open("r", encoding="utf-8") as f:
      for line in f:
        s = line.strip()
        if s.startswith("#!"):
          continue
        if s.startswith("#"):
          lines.append(s.lstrip("# "))
        elif lines and s == "":
          break
        elif lines:
          break
  fields = []
  for key in ("Description:", "Functioning:", "How to use:"):
    for l in lines:
      if l.startswith(key):
        fields.append(l)
        break
  if fields:
    return "\n".join(fields)
  if lines:
    return " ".join(lines)
  return "No description available"


def collect_scripts() -> list[Path]:
  """Return all shell and Python scripts under bash/ and python/ folders."""
  scripts: list[Path] = []
  for folder in (REPO_ROOT / "bash", REPO_ROOT / "python"):
    if folder.exists():
      scripts.extend(sorted(folder.rglob("*.sh")))
      scripts.extend(sorted(folder.rglob("*.py")))
  return scripts


def generate_readme_content() -> str:
  sections = []
  for script in collect_scripts():
    desc = extract_description(script)
    rel = script.relative_to(REPO_ROOT)
    sections.append(f"## {rel}\n{desc}\n")
  return README_HEADER + "\n" + "\n".join(sections) + "\n"


def main() -> None:
  content = generate_readme_content()
  README_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
  main()
