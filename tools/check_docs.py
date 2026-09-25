#!/usr/bin/env python3
"""The documents' own gate: the mistakes a documentation set can make, refused.

  1. Every relative markdown link in the checked documents resolves to a file
     or directory that exists. A broken link in a project about records is
     the cheapest possible own goal.
  2. docs/README.md, the index, links every document under docs/. An
     unindexed document is one nobody finds.

    python tools/check_docs.py      # 0 = clean; 1 = each problem printed by name
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")


def documents(root=ROOT):
    return ([root / n for n in ("README.md", "CLAUDE.md", "THIRD_PARTY_NOTICES.md") if (root / n).exists()]
            + sorted((root / "docs").glob("*.md")))


def problems(root=ROOT):
    out = []
    for doc in documents(root):
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (doc.parent / target).resolve().exists():
                out.append(f"{doc.relative_to(root)}: link to {target} does not resolve")
    index = root / "docs" / "README.md"
    if index.exists():
        linked = {(index.parent / t).resolve() for t in LINK.findall(index.read_text(encoding="utf-8"))}
        for doc in sorted((root / "docs").glob("*.md")):
            if doc != index and doc.resolve() not in linked:
                out.append(f"docs/README.md does not index {doc.name}")
    return out


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    if not found:
        print(f"{len(documents())} documents: every relative link resolves, and the index lists every document")
    sys.exit(1 if found else 0)
