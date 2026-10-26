#!/usr/bin/env bash
set -euo pipefail
repo="$(mktemp -d "${TMPDIR:-/tmp}/future-branch-demo.XXXXXX")"
mkdir -p "$repo/backend" "$repo/frontend"
cp demo/backend/app.py "$repo/backend/app.py"
cp demo/frontend/api.js "$repo/frontend/api.js"
cd "$repo"
git init -q -b main
git config user.email demo@example.com
git config user.name 'Future Branch Demo'
git add . && git commit -qm 'demo: base profile contract'
git checkout -qb agent-a-backend
sed -i 's/credits/creditsbalance/g' backend/app.py
git add backend/app.py && git commit -qm 'agent-a: rename credits to creditsbalance'
git checkout -qb agent-b-frontend main
python - <<'PY'
from pathlib import Path
path = Path('frontend/api.js')
path.write_text(path.read_text() + "\nexport function showBilling(profile) {\n  return `Billing credits: ${profile.credits}`;\n}\n")
PY
git add frontend/api.js && git commit -qm 'agent-b: display billing credits'
git checkout -q main
cd - >/dev/null
echo "Demo repository created at: $repo"
echo "Run: future-branch \"$repo\" agent-a-backend agent-b-frontend"
