"""Self-contained dark HTML incident reports."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CSS = """:root{color-scheme:dark;--bg:#0b1020;--panel:#131b2e;--line:#283650;--text:#edf3ff;--muted:#9aa9c2;--red:#ff6b81;--green:#5ee6a8}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0,#1b2a4a 0,#0b1020 42%);color:var(--text);font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}main{max-width:1120px;margin:0 auto;padding:44px 24px 80px}h1{font-size:clamp(30px,5vw,52px);line-height:1.05;margin:8px 0 12px}h2{margin:0 0 12px}.eyebrow{letter-spacing:.16em;color:#86a4d8;font-weight:700;font-size:12px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}.card{background:rgba(19,27,46,.88);border:1px solid var(--line);border-radius:16px;padding:20px;margin:16px 0;box-shadow:0 12px 40px #05081255}.stat{min-height:92px}.stat strong{display:block;font-size:25px}.pill{display:inline-block;border-radius:999px;padding:3px 10px;background:#263654;color:#bcd0f4;font-size:12px;font-weight:700}.error{border-left:4px solid var(--red)}.clean{color:var(--green)}.owners{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.owner{background:#202d49;padding:5px 10px;border-radius:8px}.code-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.code-panel{min-width:0}.code-panel h3{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}pre{margin:0;min-height:72px;white-space:pre-wrap;overflow:auto;background:#080d18;border:1px solid #1f2b43;border-radius:10px;padding:14px;color:#d7e4ff}code{color:#c8dafd}li{margin:4px 0}.fix{background:#192c32;border:1px solid #2b5a59;border-radius:10px;padding:13px}@media(max-width:700px){.grid,.code-grid{grid-template-columns:1fr}}"""


def render_report(result: dict[str, Any], title: str = "Future Branch incident rehearsal") -> str:
    conflicts = result.get("conflicts", [])
    branches = result.get("branches", [])
    cards: list[str] = []
    for item in conflicts:
        evidence = "".join(f"<li>{html.escape(str(x))}</li>" for x in item.get("evidence", []))
        owners = "".join(f"<span class='owner'>{html.escape(str(x))}</span>" for x in item.get("branches", []))
        cards.append(f"<article class='card error'><span class='pill'>{html.escape(str(item.get('kind','semantic')).upper())}</span><h2>{html.escape(str(item.get('description','Conflict')))}</h2><p><code>{html.escape(str(item.get('path','')))}</code></p><div class='owners'><b>Owners:</b>{owners}</div><div class='code-grid'><div class='code-panel'><h3>Changed</h3><pre>{html.escape(str(item.get('changed_code','No code excerpt available.')))}</pre></div><div class='code-panel'><h3>Expected by other side</h3><pre>{html.escape(str(item.get('expected_code','No code excerpt available.')))}</pre></div></div>{('<ul>'+evidence+'</ul>') if evidence else ''}<p class='fix'><b>Suggested intervention:</b> {html.escape(str(item.get('suggested_fix','Resolve the contract mismatch and rerun the rehearsal.')))}</p></article>")
    status = str(result.get("status", "error"))
    body = "".join(cards) or "<div class='card'><p class='clean'>✓ No conflicts found. These branches are ready to merge.</p></div>"
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}</style></head><body><main><div class='eyebrow'>FUTURE BRANCH / PRE-MERGE REHEARSAL</div><h1>{html.escape(title)}</h1><p class='muted'>Individually correct. Collectively broken. Caught before merge.</p><div class='grid'><div class='card stat'><span class='muted'>Status</span><strong>{html.escape(status.upper())}</strong></div><div class='card stat'><span class='muted'>Base branch</span><strong><code>{html.escape(str(result.get('base','')))}</code></strong></div><div class='card stat'><span class='muted'>Conflicts</span><strong>{len(conflicts)}</strong></div></div><div class='card'><b>Branches rehearsed</b><p>{' · '.join(f"<code>{html.escape(str(branch))}</code>" for branch in branches)}</p><p class='muted'>Generated {datetime.now(timezone.utc).isoformat()}.</p></div>{body}</main></body></html>"


def write_report(result: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(result), encoding="utf-8")
    return path
