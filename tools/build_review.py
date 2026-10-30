"""Build review/index.html (concept map, look, journey) from the OKF bundle.

Usage: build_review.py
Reads okf/**/*.md, runs okf_check.py, and injects both into review/template.html.
"""
import json, os, re, subprocess, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OKF = os.path.join(ROOT, "okf")

concepts = []
for d, _, files in os.walk(OKF):
    for f in sorted(files):
        if not f.endswith(".md") or f in ("index.md", "log.md"):
            continue
        rel = os.path.relpath(os.path.join(d, f), OKF)
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", open(os.path.join(d, f)).read(), re.S)
        fm = yaml.safe_load(m.group(1))
        concepts.append({
            "path": rel, "type": fm["type"], "title": fm.get("title", rel),
            "description": fm.get("description", ""), "tags": fm.get("tags", []),
            "status": fm.get("status", ""), "links": fm.get("links") or {},
            "steps": fm.get("steps") or [], "body": m.group(2).strip(),
        })

chk = subprocess.run([sys.executable, os.path.join(HERE, "okf_check.py"), OKF], capture_output=True, text=True)
check = {"ok": chk.returncode == 0, "summary": chk.stdout.splitlines()[0] if chk.stdout else "",
         "errors": [l for l in chk.stderr.splitlines() if l.startswith("ERROR")]}

tpl = open(os.path.join(ROOT, "review", "template.html")).read()
data = json.dumps({"concepts": concepts, "check": check}, ensure_ascii=False).replace("</", "<\\/")
out = os.path.join(ROOT, "review", "index.html")
open(out, "w").write(tpl.replace("/*OKF_DATA*/null", data))
print("wrote", out, "-", check["summary"], "- ok" if check["ok"] else "- CHECK FAILED")
