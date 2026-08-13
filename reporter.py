"""Self-contained, high-fidelity dark HTML incident reports with rich visual aesthetics."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  color-scheme: dark;
  --bg: #07090e;
  --bg-subtle: #0d111a;
  --panel: rgba(16, 22, 36, 0.75);
  --panel-hover: rgba(22, 30, 48, 0.85);
  --border: rgba(255, 255, 255, 0.08);
  --border-glow: rgba(99, 102, 241, 0.25);
  --text: #f1f5f9;
  --text-muted: #8492a6;
  --text-dim: #4b5563;
  --accent: #6366f1;
  --accent-glow: rgba(99, 102, 241, 0.4);
  --red: #f43f5e;
  --red-bg: rgba(244, 63, 94, 0.12);
  --red-border: rgba(244, 63, 94, 0.35);
  --red-glow: rgba(244, 63, 94, 0.3);
  --green: #10b981;
  --green-bg: rgba(16, 185, 129, 0.12);
  --green-border: rgba(16, 185, 129, 0.35);
  --cyan: #06b6d4;
  --amber: #f59e0b;
  --code-bg: #080b11;
  --radius-lg: 16px;
  --radius-md: 10px;
  --radius-sm: 6px;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--bg);
  background-image: 
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.15), transparent),
    radial-gradient(circle at 15% 15%, rgba(244, 63, 94, 0.06), transparent 25%),
    radial-gradient(circle at 85% 25%, rgba(6, 182, 212, 0.06), transparent 25%);
  color: var(--text);
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  min-height: 100vh;
  padding: 40px 20px 80px;
  -webkit-font-smoothing: antialiased;
}

main {
  max-width: 1080px;
  margin: 0 auto;
}

/* Header & Brand */
.header-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 36px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}

.brand-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cyan);
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.2);
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 12px;
}

.brand-eyebrow .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--cyan);
  box-shadow: 0 0 8px var(--cyan);
}

h1 {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #ffffff;
  line-height: 1.2;
}

.tagline {
  color: var(--text-muted);
  font-size: 15px;
  margin-top: 6px;
}

.tagline strong {
  color: var(--text);
}

/* Status Pill in Header */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 18px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.status-badge.error {
  background: var(--red-bg);
  border: 1px solid var(--red-border);
  color: var(--red);
  box-shadow: 0 0 20px var(--red-glow);
}

.status-badge.clean {
  background: var(--green-bg);
  border: 1px solid var(--green-border);
  color: var(--green);
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.25);
}

.pulse-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-badge.error .pulse-indicator {
  background: var(--red);
  box-shadow: 0 0 8px var(--red);
}

.status-badge.clean .pulse-indicator {
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.2); }
}

/* Top Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--panel);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  border-color: var(--border-glow);
  background: var(--panel-hover);
  transform: translateY(-1px);
}

.stat-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 6px;
  display: block;
}

.stat-value {
  font-size: 24px;
  font-weight: 800;
  color: #ffffff;
  font-family: 'JetBrains Mono', monospace;
}

.stat-value.error-text {
  color: var(--red);
}

.stat-value.clean-text {
  color: var(--green);
}

/* Rehearsal Branch Visual Flow */
.flow-card {
  background: var(--panel);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 32px;
}

.flow-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.branches-flow-wrapper {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.branch-node {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.25);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #c7d2fe;
}

.branch-node .git-icon {
  opacity: 0.7;
}

.flow-arrow {
  color: var(--text-dim);
  font-size: 18px;
  font-weight: 700;
}

.future-main-node {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(244, 63, 94, 0.12);
  border: 1px dashed var(--red);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--red);
}

.future-main-node.clean {
  background: rgba(16, 185, 129, 0.12);
  border: 1px dashed var(--green);
  color: var(--green);
}

.meta-timestamp {
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-dim);
  font-family: 'JetBrains Mono', monospace;
}

/* Incident Detail Card */
.incident-card {
  background: var(--panel);
  backdrop-filter: blur(16px);
  border: 1px solid var(--red-border);
  border-radius: var(--radius-lg);
  padding: 28px;
  margin-bottom: 24px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4), 0 0 24px var(--red-glow);
  position: relative;
  overflow: hidden;
}

.incident-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--red);
  box-shadow: 0 0 12px var(--red);
}

.incident-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.incident-type-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: var(--red-bg);
  border: 1px solid var(--red-border);
  color: var(--red);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.incident-title {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  margin: 10px 0 8px;
  line-height: 1.35;
}

.file-path {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--cyan);
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.2);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: 18px;
}

.owners-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}

.owners-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.owner-tag {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text);
}

/* Side-by-Side Diff Comparison */
.code-comparison-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.code-box {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.code-box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.code-box.changed .code-box-header {
  color: var(--red);
  border-bottom-color: rgba(244, 63, 94, 0.2);
}

.code-box.expected .code-box-header {
  color: var(--amber);
  border-bottom-color: rgba(245, 158, 11, 0.2);
}

.code-content {
  padding: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #e2e8f0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Evidence List */
.evidence-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  margin-bottom: 22px;
}

.evidence-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.evidence-list {
  padding-left: 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.evidence-list li {
  margin-bottom: 6px;
}

/* Action / Fix Box */
.intervention-box {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(6, 182, 212, 0.06) 100%);
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: var(--radius-md);
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.intervention-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a5b4fc;
}

.intervention-text {
  font-size: 14px;
  color: #ffffff;
  line-height: 1.5;
}

/* Clean State */
.clean-card {
  background: var(--panel);
  border: 1px solid var(--green-border);
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  box-shadow: 0 12px 36px rgba(16, 185, 129, 0.1);
}

.clean-card h3 {
  font-size: 22px;
  color: var(--green);
  margin-bottom: 8px;
}

.clean-card p {
  color: var(--text-muted);
  font-size: 15px;
}

@media (max-width: 768px) {
  .code-comparison-grid {
    grid-template-columns: 1fr;
  }
  .header-wrapper {
    flex-direction: column;
    align-items: flex-start;
  }
}
"""


def render_report(result: dict[str, Any], title: str = "Future Branch Pre-Merge Rehearsal") -> str:
    conflicts = result.get("conflicts", [])
    branches = result.get("branches", [])
    status = str(result.get("status", "error")).lower()
    is_clean = len(conflicts) == 0 and status != "error"

    cards: list[str] = []
    for item in conflicts:
        evidence = "".join(f"<li>{html.escape(str(x))}</li>" for x in item.get("evidence", []))
        owners = "".join(f"<span class='owner-tag'>{html.escape(str(x))}</span>" for x in item.get("branches", []))
        
        cards.append(f"""
        <article class="incident-card">
          <div class="incident-header">
            <span class="incident-type-badge">{html.escape(str(item.get('kind', 'semantic')))}</span>
          </div>
          <h2 class="incident-title">{html.escape(str(item.get('description', 'Integration Conflict Detected')))}</h2>
          <div class="file-path">📄 {html.escape(str(item.get('path', 'unknown/file')))}</div>
          
          <div class="owners-row">
            <span class="owners-label">Conflicting Sessions:</span>
            {owners}
          </div>
          
          <div class="code-comparison-grid">
            <div class="code-box changed">
              <div class="code-box-header">
                <span>🔴 Changed Contract</span>
                <span>Branch A</span>
              </div>
              <pre class="code-content">{html.escape(str(item.get('changed_code', 'No code excerpt available.')))}</pre>
            </div>
            
            <div class="code-box expected">
              <div class="code-box-header">
                <span>🟡 Consumer Expectation</span>
                <span>Branch B</span>
              </div>
              <pre class="code-content">{html.escape(str(item.get('expected_code', 'No code excerpt available.')))}</pre>
            </div>
          </div>
          
          {f'''<div class="evidence-section">
            <div class="evidence-title">Analysis Trace & Evidence</div>
            <ul class="evidence-list">{evidence}</ul>
          </div>''' if evidence else ''}
          
          <div class="intervention-box">
            <div class="intervention-header">
              <span>⚡ Suggested Agent Intervention (AO Send)</span>
            </div>
            <p class="intervention-text">{html.escape(str(item.get('suggested_fix', 'Reconcile the contract mismatch and rerun future-branch rehearse.')))}</p>
          </div>
        </article>
        """)

    body = "".join(cards) if cards else """
    <div class="clean-card">
      <div style="font-size: 40px; margin-bottom: 12px;">✨</div>
      <h3>Rehearsal Complete: Zero Conflicts</h3>
      <p>All active worktrees can cleanly merge into main without contract or build breaks.</p>
    </div>
    """

    status_class = "clean" if is_clean else "error"
    status_label = "REHEARSAL CLEAN" if is_clean else "CONFLICT DETECTED"
    
    branch_nodes = " ".join(
        f"<span class='branch-node'><span class='git-icon'>⎇</span> {html.escape(str(b))}</span>"
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
        <div class="brand-eyebrow">
          <span class="dot"></span>
          Future Branch · Pre-Merge Rehearsal Gate
        </div>
        <h1>{html.escape(title)}</h1>
        <p class="tagline">Individually correct. <strong>Collectively broken.</strong> Caught before merge.</p>
      </div>
      
      <div>
        <div class="status-badge {status_class}">
          <span class="pulse-indicator"></span>
          {status_label}
        </div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-label">Integration Status</span>
        <div class="stat-value {'clean-text' if is_clean else 'error-text'}">
          {html.escape(status.upper())}
        </div>
      </div>
      
      <div class="stat-card">
        <span class="stat-label">Base Target Branch</span>
        <div class="stat-value" style="font-size: 20px; color: var(--cyan);">
          {html.escape(str(result.get('base', 'main')))}
        </div>
      </div>
      
      <div class="stat-card">
        <span class="stat-label">Active Conflicts</span>
        <div class="stat-value {'clean-text' if is_clean else 'error-text'}">
          {len(conflicts)}
        </div>
      </div>
    </div>

    <div class="flow-card">
      <div class="flow-title">Live Rehearsal Flow</div>
      <div class="branches-flow-wrapper">
        {branch_nodes}
        <span class="flow-arrow">→</span>
        <span class="future-main-node {'clean' if is_clean else ''}">
          ⚡ temporary future-main
        </span>
      </div>
      <div class="meta-timestamp">
        Rehearsed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
      </div>
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
