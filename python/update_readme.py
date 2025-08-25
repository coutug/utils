#!/usr/bin/env python3
"""
Description: Generate README listing all scripts with descriptions.
Functioning: Recursively scans the repository for shell and Python scripts, groups them by directory, and writes README.md.
How to use: Run `python python/update_readme.py` from the repository root.
"""

import ast
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

# The static header that will be kept at the top of README.md
README_HEADER = """# utils
Useful scripts collection built along the journey

## Development

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The README generator itself has no external dependencies, but other scripts require those listed above.
"""


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
    scripts = [p for p in REPO_ROOT.rglob("*.sh")] + [p for p in REPO_ROOT.rglob("*.py")]
    categories: dict[str, list[Path]] = defaultdict(list)
    for script in scripts:
        rel = script.relative_to(REPO_ROOT)
        category = rel.parent.as_posix() if rel.parent != Path('.') else "root"
        categories[category].append(script)
    lines = [README_HEADER, ""]
    for category in sorted(categories):
        lines.append(f"## {category}")
        for script in sorted(categories[category]):
            desc = extract_description(script)
            lines.append(f"### {script.name}\n{desc}\n")
    return "\n".join(lines) + "\n"


def main() -> None:
    content = generate_readme_content()
    README_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
