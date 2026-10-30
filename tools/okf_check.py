"""Validate the OKF planning bundle and print its concept map.

Usage: okf_check.py [bundle_dir] [--mermaid]
Checks: every concept has frontmatter with `type`; every link resolves;
Features `uses` a domain concept and are `constrained_by` a Rule;
design components `implements` a Feature; nothing is orphaned.
"""
import os, re, sys
import yaml

root = next((a for a in sys.argv[1:] if not a.startswith("--")),
            os.path.join(os.path.dirname(__file__), "..", "okf"))
root = os.path.abspath(root)
RESERVED = {"index.md", "log.md"}

concepts, errors = {}, []
for d, _, files in os.walk(root):
    for f in sorted(files):
        if not f.endswith(".md"):
            continue
        rel = os.path.relpath(os.path.join(d, f), root)
        text = open(os.path.join(d, f)).read()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if f == "log.md":
            continue
        if not m:
            errors.append(f"{rel}: missing frontmatter"); continue
        fm = yaml.safe_load(m.group(1)) or {}
        if not fm.get("type"):
            errors.append(f"{rel}: missing type")
        if f not in RESERVED:
            concepts[rel] = fm

if not yaml.safe_load(open(os.path.join(root, "design", "index.md")).read().split("---")[1]).get("odsf_version"):
    errors.append("design/index.md: missing odsf_version (ODSF profile)")

edges, linked = [], set()
for rel, fm in concepts.items():
    for kind, targets in (fm.get("links") or {}).items():
        for t in targets or []:
            if t not in concepts:
                errors.append(f"{rel}: {kind} -> {t} does not exist")
            edges.append((rel, kind, t)); linked.update((rel, t))

def out(rel, kind):
    return [t for s, k, t in edges if s == rel and k == kind]

for rel, fm in concepts.items():
    t = fm.get("type")
    if t == "Feature":
        if not any(x.startswith("domain/") for x in out(rel, "uses")):
            errors.append(f"{rel}: Feature must `uses` a domain concept")
        if not out(rel, "constrained_by"):
            errors.append(f"{rel}: Feature must be `constrained_by` a Rule")
    if t == "component" and not out(rel, "implements"):
        errors.append(f"{rel}: component must `implements` a Feature")
    for st in fm.get("steps") or []:
        for f in st.get("features", []):
            if f not in concepts:
                errors.append(f"{rel}: step {st.get('id')} -> {f} does not exist")
    if t == "Feature" and not any(rel in (st.get("features") or []) for c in concepts.values() for st in c.get("steps") or []):
        errors.append(f"{rel}: Feature appears in no journey step")
    if rel not in linked:
        errors.append(f"{rel}: orphan (no links in or out)")

if "--mermaid" in sys.argv:
    nid = lambda p: re.sub(r"\W", "_", p[:-3])
    print("graph LR")
    for rel, fm in concepts.items():
        print(f'  {nid(rel)}["{fm.get("title", rel)}"]')
    for s, k, t in edges:
        print(f"  {nid(s)} -- {k} --> {nid(t)}")
else:
    by_type = {}
    for rel, fm in concepts.items():
        by_type.setdefault(fm.get("type"), []).append(rel)
    print(f"{len(concepts)} concepts, {len(edges)} links")
    for t, rels in sorted(by_type.items()):
        print(f"  {t}: {len(rels)}")

for e in errors:
    print("ERROR", e, file=sys.stderr)
sys.exit(1 if errors else 0)
