#!/usr/bin/env python3
"""The documents' own gate: the mistakes a documentation set can make, refused.

  1. Every relative markdown link in the checked documents resolves to a file
     or directory that exists. A broken link in a project about records is
     the cheapest possible own goal.
  2. docs/README.md, the index, links every document under docs/. An
     unindexed document is one nobody finds.
  3. Every repository path named in plain text exists: in the documents, and
     in the package's, the tools', the tests' and the runner's own text.
     Moving the tests into stage directories left seven such names pointing
     at nothing, one of them DETERMINISM.md's pointer to its own check, and
     the link check could not see them (verifier-P0 8f). Not checked: a
     path marked "(new)", which a plan names before it exists; a line that
     names another repository (atlas-film, cft-fp256, ...), whose paths are
     that repository's; and tests/docs/, whose tests plant missing paths on
     purpose.

    python tools/check_docs.py      # 0 = clean; 1 = each problem printed by name
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
PATH = re.compile(r"(?<![\w./-])((?:tests|quantum_film|tools|docs|verify)/[\w./-]*\w)")
FOREIGN = ("atlas-film", "atlas_film", "atlas-engine", "cft-fp256", "HonestFramework", "ParcelRound")


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
    return out + missing_paths(root)


def texts(root=ROOT):
    """The documents, and the text of the package, the tools, the tests and the runner."""
    out = documents(root)
    for d in ("quantum_film", "tools", "tests", "verify"):
        out += sorted(p for p in (root / d).rglob("*") if p.suffix in (".py", ".sh"))
    return out


def missing_paths(root=ROOT):
    out = []
    for f in texts(root):
        rel = f.relative_to(root).as_posix()
        if rel.startswith("tests/docs/"):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(name in line for name in FOREIGN):
                continue
            for m in PATH.finditer(line):
                planned = line[m.end():].lstrip("/`'\" ").startswith("(new)")
                if not planned and not (root / m.group(1)).exists():
                    out.append(f"{rel}:{n}: names {m.group(1)}, which does not exist")
    return out


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    if not found:
        print(f"{len(documents())} documents: every relative link resolves, and the index lists every document")
    sys.exit(1 if found else 0)
