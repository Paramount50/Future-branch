$ErrorActionPreference = 'Stop'
$repo = Join-Path ([System.IO.Path]::GetTempPath()) ("future-branch-demo-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $repo 'backend') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $repo 'frontend') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'demo/backend/app.py') -Destination (Join-Path $repo 'backend/app.py')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'demo/frontend/api.js') -Destination (Join-Path $repo 'frontend/api.js')
Push-Location $repo
git init -q -b main
git config user.email demo@example.com
git config user.name 'Future Branch Demo'
git add .; git commit -qm 'demo: base profile contract'
git checkout -qb agent-a-backend
(Get-Content backend/app.py -Raw).Replace('credits', 'creditsbalance') | Set-Content backend/app.py -NoNewline
git add backend/app.py; git commit -qm 'agent-a: rename credits to creditsbalance'
git checkout -qb agent-b-frontend main
Add-Content frontend/api.js @'

export function showBilling(profile) {
  return `Billing credits: ${profile.credits}`;
}
'@
git add frontend/api.js; git commit -qm 'agent-b: display billing credits'
git checkout -q main
Pop-Location
Write-Host "Demo repository created at: $repo"
Write-Host "Run: future-branch `"$repo`" agent-a-backend agent-b-frontend"
