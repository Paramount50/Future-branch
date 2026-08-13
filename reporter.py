"""Self-contained, ultra-clean technical dark HTML incident reports styled with pure monospaced aesthetic."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Geist+Mono:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

:root {
  color-scheme: dark;
  --bg: #000000;
  --surface: #0a0a0a;
  --surface-raised: #121212;
  --surface-hover: #181818;
  --border: #222222;
  --border-focus: #333333;
  --text: #ededed;
  --text-muted: #888888;
  --text-dim: #555555;
  --accent: #ffffff;
  --red: #ff334b;
  --red-dim: rgba(255, 51, 75, 0.12);
  --red-border: #44161c;
  --green: #00e599;
  --green-dim: rgba(0, 229, 153, 0.1);
  --green-border: #0e3d2c;
  --amber: #f5a623;
  --radius: 6px;
  --font-mono: 'Geist Mono', 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  font-family: var(--font-mono) !important;
}

body {
  background-color: var(--bg);
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.6;
  min-height: 100vh;
  padding: 48px 24px 96px;
  -webkit-font-smoothing: antialiased;
}

main {
  max-width: 980px;
  margin: 0 auto;
}

/* Header */
.header-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 40px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}

.eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 12px;
}

h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: #ffffff;
  line-height: 1.2;
}

.tagline {
  color: var(--text-muted);
  font-size: 13.5px;
  margin-top: 8px;
}

.tagline strong {
  color: var(--text);
  font-weight: 600;
}

/* Status Pill */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: var(--radius);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.status-badge.error {
  background: var(--red-dim);
  border: 1px solid var(--red-border);
  color: var(--red);
}

.status-badge.clean {
  background: var(--green-dim);
  border: 1px solid var(--green-border);
  color: var(--green);
}

.status-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-badge.error .status-indicator {
  background: var(--red);
}

.status-badge.clean .status-indicator {
  background: var(--green);
}

/* Stats / Info Row */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
}

.stat-label {
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  margin-bottom: 8px;
  display: block;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
}

.stat-value.error-text {
  color: var(--red);
}

.stat-value.clean-text {
  color: var(--green);
}

/* Terminal / Rehearsal Bar */
.terminal-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 32px;
  font-size: 12.5px;
}

.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.terminal-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.terminal-tab {
  background: var(--surface-raised);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: 4px;
  color: var(--text);
  font-size: 11.5px;
}

.terminal-tab.active {
  background: #222222;
  color: #ffffff;
  border-color: #444444;
}

.terminal-command {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #cccccc;
}

.terminal-prompt {
  color: var(--text-muted);
}

.timestamp {
  color: var(--text-dim);
  font-size: 11px;
  margin-top: 10px;
}

/* Incident Block */
.incident-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--red);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
}

.incident-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 10px;
}

.incident-kind {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--red);
  background: var(--red-dim);
  border: 1px solid var(--red-border);
  padding: 3px 8px;
  border-radius: 4px;
}

.incident-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 10px;
  line-height: 1.4;
  letter-spacing: -0.01em;
}

.incident-file {
  font-size: 12px;
  color: var(--text-muted);
  background: #080808;
  border: 1px solid var(--border);
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  margin-bottom: 20px;
}

/* Code Comparison Panels */
.diff-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.diff-box {
  background: #050505;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.diff-box-head {
  padding: 8px 12px;
  background: #0f0f0f;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
}

.diff-box.changed .diff-box-head {
  color: var(--red);
}

.diff-box.expected .diff-box-head {
  color: var(--amber);
}

.diff-code {
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.6;
  color: #e0e0e0;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
}

/* Root Cause */
.root-cause {
  background: #050505;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px 18px;
  margin-bottom: 12px;
}

.root-cause-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--red);
  margin-bottom: 8px;
}

.root-cause-text {
  color: #ffffff;
  font-size: 13px;
  line-height: 1.6;
}

.root-cause-text strong {
  color: var(--amber);
  font-weight: 600;
}

/* Evidence Trace */
.evidence {
  background: #050505;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px 18px;
  margin-bottom: 12px;
}

.evidence-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 6px;
}

.evidence ul {
  list-style: none;
  padding: 0;
}

.evidence li {
  font-size: 12px;
  color: var(--text-muted);
  padding: 3px 0;
  border-bottom: 1px solid #1a1a1a;
}

.evidence li:last-child {
  border-bottom: none;
}

.evidence li::before {
  content: '› ';
  color: var(--text-dim);
}

/* Action Box */
.action-box {
  background: #050505;
  border: 1px solid #242424;
  border-radius: 4px;
  padding: 14px 18px;
}

.action-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #a0a0a0;
  margin-bottom: 6px;
}

.action-desc {
  color: #ffffff;
  font-size: 13px;
  line-height: 1.5;
}

/* Clean State */
.clean-block {
  background: var(--surface);
  border: 1px solid var(--green-border);
  border-radius: var(--radius);
  padding: 40px 24px;
  text-align: center;
}

.clean-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--green);
  margin-bottom: 6px;
}

.clean-desc {
  color: var(--text-muted);
  font-size: 13.5px;
}

@media (max-width: 720px) {
  .stats-grid, .diff-grid {
    grid-template-columns: 1fr;
  }
}
"""


def render_report(result: dict[str, Any], title: str = "Future Branch Rehearsal") -> str:
    conflicts = result.get("conflicts", [])
    branches = result.get("branches", [])
    status = str(result.get("status", "error")).lower()
    is_clean = len(conflicts) == 0 and status != "error"

    cards: list[str] = []
    for item in conflicts:
        evidence_items = item.get("evidence", [])
        evidence_html = "".join(f"<li>{html.escape(str(x))}</li>" for x in evidence_items)
        owners = " ".join(
            f"<span class='terminal-tab active'>{html.escape(str(x))}</span>"
            for x in item.get("branches", [])
        )

        # Deterministic root cause from analyzer data
        owner_changed = item.get("owner_changed", "")
        owner_consumer = item.get("owner_consumer", "")
        description = item.get("description", "Contract conflict detected.")
        root_cause = f"{description} Branch <strong>{html.escape(owner_changed)}</strong> modified the contract, but branch <strong>{html.escape(owner_consumer)}</strong> still depends on the original."

        branch_a_label = html.escape(owner_changed) if owner_changed else "Branch A"
        branch_b_label = html.escape(owner_consumer) if owner_consumer else "Branch B"

        evidence_section = f"""
          <div class="evidence">
            <div class="evidence-label">Evidence Trace</div>
            <ul>{evidence_html}</ul>
          </div>
        """ if evidence_items else ""

        cards.append(f"""
        <div class="incident-block">
          <div class="incident-top">
            <span class="incident-kind">{html.escape(str(item.get('kind', 'semantic')))}</span>
            <div class="terminal-tabs">{owners}</div>
          </div>
          
          <h2 class="incident-title">{html.escape(str(item.get('description', 'Conflict detected')))}</h2>
          <div class="incident-file">FILE: {html.escape(str(item.get('path', '')))}</div>
          
          <div class="diff-grid">
            <div class="diff-box changed">
              <div class="diff-box-head">
                <span>Changed contract</span>
                <span>{branch_a_label}</span>
              </div>
              <pre class="diff-code">{html.escape(str(item.get('changed_code', 'No code excerpt.')))}</pre>
            </div>
            
            <div class="diff-box expected">
              <div class="diff-box-head">
                <span>Expected by consumer</span>
                <span>{branch_b_label}</span>
              </div>
              <pre class="diff-code">{html.escape(str(item.get('expected_code', 'No code excerpt.')))}</pre>
            </div>
          </div>

          <div class="root-cause">
            <div class="root-cause-label">Root Cause</div>
            <div class="root-cause-text">{root_cause}</div>
          </div>

          {evidence_section}

          <div class="action-box">
            <div class="action-label">&gt; Recommended Intervention (ao send)</div>
            <div class="action-desc">{html.escape(str(item.get('suggested_fix', 'Resolve the contract mismatch.')))}</div>
          </div>
        </div>
        """)

    body = "".join(cards) if cards else """
    <div class="clean-block">
      <div class="clean-title">Rehearsal passed</div>
      <div class="clean-desc">No merge conflicts or contract breaks detected across active branches.</div>
    </div>
    """

    status_class = "clean" if is_clean else "error"
    status_label = "REHEARSAL CLEAN" if is_clean else "CONFLICT DETECTED"

    branch_tabs = " ".join(
        f"<span class='terminal-tab'>{html.escape(str(b))}</span>"
        for b in branches
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <main>
    <div class="header-wrapper">
      <div>
        <div class="eyebrow">
          <span>AO / PRE-MERGE REHEARSAL GATE</span>
        </div>
        <h1>{html.escape(title)}</h1>
        <p class="tagline">Individually correct. <strong>Collectively broken.</strong> Caught before merge.</p>
      </div>
      
      <div>
        <div class="status-badge {status_class}">
          <span class="status-indicator"></span>
          {status_label}
        </div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-label">Status</span>
        <div class="stat-value {'clean-text' if is_clean else 'error-text'}">
          {html.escape(status.upper())}
        </div>
      </div>
      
      <div class="stat-card">
        <span class="stat-label">Base branch</span>
        <div class="stat-value">
          {html.escape(str(result.get('base', 'main')))}
        </div>
      </div>
      
      <div class="stat-card">
        <span class="stat-label">Conflicts</span>
        <div class="stat-value {'clean-text' if is_clean else 'error-text'}">
          {len(conflicts)}
        </div>
      </div>
    </div>

    <div class="terminal-card">
      <div class="terminal-header">
        <span class="stat-label" style="margin: 0;">Rehearsed Branches</span>
        <div class="terminal-tabs">
          {branch_tabs}
        </div>
      </div>
      <div class="terminal-command">
        <span class="terminal-prompt">&gt;</span>
        <span>future-branch rehearse {' '.join(branches)} --base {html.escape(str(result.get('base', 'main')))}</span>
      </div>
      <div class="timestamp">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
    </div>

    {body}
  </main>
</body>
</html>
"""


def write_report(result: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(result), encoding="utf-8")
    return path
