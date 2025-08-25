#!/usr/bin/env python3
"""
Description: Generate README listing all scripts with descriptions.
Functioning: Scans root for shell and Python scripts, extracts their description blocks, and writes README.md.
How to use: Run `python update_readme.py` from the repository root.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
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


def generate_readme_content() -> str:
  scripts = sorted(Path(REPO_ROOT).glob("*.sh")) + sorted(Path(REPO_ROOT).glob("*.py"))
  sections = []
  for script in scripts:
    desc = extract_description(script)
    sections.append(f"## {script.name}\n{desc}\n")
  return README_HEADER + "\n" + "\n".join(sections) + "\n"


def main() -> None:
  content = generate_readme_content()
  README_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
  main()
