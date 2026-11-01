#!/usr/bin/env bash
# Release what was just deployed (okf/architecture/releases.md). Run on the laptop after tools/deploy.sh succeeds.
#   tools/release.sh --deployed   tag what just reached production, then publish
#   tools/release.sh              only publish tags not yet on GitHub
#   1. with --deployed, 'Unreleased' in CHANGELOG.md becomes today's version; committed and tagged
#   2. main and the tags go to GitHub, and each tag without a GitHub release gets one with its notes
set -euo pipefail
cd "$(dirname "$0")/.."
[ -z "$(git status --porcelain)" ] || { echo "Commit or stash changes first."; exit 1; }

notes() {   # the CHANGELOG section for a version, without its heading
  awk -v v="$1" '/^## /{on = index($0, "## " v " ") == 1 || $0 == "## " v; next} on' CHANGELOG.md | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'
}

if [ "${1:-}" != "--deployed" ]; then
  echo "Publishing only (pass --deployed right after a production deploy to tag it)."
elif grep -q '^## Unreleased' CHANGELOG.md; then
  [ -n "$(notes Unreleased | tr -d '[:space:]')" ] || { echo "Write the release notes under '## Unreleased' first."; exit 1; }
  v="v$(date +%Y.%m.%d)"; n=1
  while git rev-parse -q --verify "refs/tags/$v$([ $n -gt 1 ] && echo ".$n")" >/dev/null; do n=$((n + 1)); done
  [ $n -gt 1 ] && v="$v.$n"
  sed -i "s/^## Unreleased\$/## $v · $(date '+%-d %b %Y')/" CHANGELOG.md
  sed -i "0,/^## $v /s//## Unreleased\n\n&/" CHANGELOG.md
  git commit -q -m "Release $v" -- CHANGELOG.md
  git tag -a "$v" -m "$v" && echo "Tagged $v"
else
  echo "No '## Unreleased' section: nothing new to tag."
fi

if ! git remote get-url origin >/dev/null 2>&1; then echo "No GitHub remote yet: tags stay local until 'git remote add origin …'."; exit 0; fi
if ! gh auth status >/dev/null 2>&1; then echo "gh isn't signed in: run 'gh auth login', then tools/release.sh again."; exit 0; fi
git push -q origin main --follow-tags
for t in $(git tag -l 'v*' --sort=creatordate); do
  gh release view "$t" >/dev/null 2>&1 && continue
  notes "$t" > /tmp/kc-release-notes.$$
  gh release create "$t" --verify-tag --title "Kitchen Carbs $t" --notes-file /tmp/kc-release-notes.$$ && echo "Released $t on GitHub"
  rm -f /tmp/kc-release-notes.$$
done
