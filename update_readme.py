#!/usr/bin/env python3
"""Generate README listing all scripts with descriptions.

Scans the repository for Python and shell scripts in the root directory and
updates README.md so that each script is listed with a ``##`` header followed by
its description.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
README_PATH = REPO_ROOT / "README.md"

# The static header that will be kept at the top of README.md
README_HEADER = "# utils\nUseful scripts collection built along the journey\n"


def extract_description(path: Path) -> str:
    """Return the leading comment or docstring describing the script."""
    if path.suffix == ".py":
        with path.open("r", encoding="utf-8") as f:
            try:
                module = ast.parse(f.read())
                doc = ast.get_docstring(module)
                if doc:
                    first_paragraph = doc.strip().split("\n\n", 1)[0]
                    return " ".join(line.strip() for line in first_paragraph.splitlines())
            except SyntaxError:
                pass
        # Fallback to comments if no docstring
    desc_lines = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#!"):
                continue
            if line.startswith("#"):
                desc_lines.append(line.lstrip("# "))
            elif desc_lines and line == "":
                break
            elif desc_lines:
                break
        if desc_lines:
            return " ".join(l.strip() for l in desc_lines)
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
