import os
import sqlite3
import hashlib
import secrets
import functools
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from flask import (
    Flask, request, redirect, render_template_string, session,
    jsonify, g, abort, url_for
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "app.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

TEMPLATES = {
    "template1": {"label": "Front Desk (light)"},
    "template2": {"label": "Night Lounge (dark)"},
}

# ---------------------------------------------------------------------------
# HTML templates (kept as strings so this whole app is a single file)
# ---------------------------------------------------------------------------

LANDING_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1">
<title>{{ site_title }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: __BG__; --bg-glow: __BGGLOW__; --card: __CARD__; --border: __BORDER__;
    --ink: __INK__; --ink-soft: __INKSOFT__; --heading: __HEADING__; --brass: __BRASS__;
    --cta-bg: __CTABG__; --cta-text: __CTATEXT__; --cta-shadow: __CTASHADOW__;
    --perk-bg: __PERKBG__; --perk-color: __PERKCOLOR__;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; background: var(--bg); color: var(--ink); font-family: 'Inter', sans-serif; }
  body {
    display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px;
    background-image: radial-gradient(circle at 50% 0%, var(--bg-glow) 0%, var(--bg) 60%);
  }
  .card {
    width: 100%; max-width: 440px; background: var(--card);
    border: 1px solid var(--border); border-radius: 10px; padding: 40px 32px 34px;
    box-shadow: __SHADOW__;
    opacity: 0; transform: translateY(10px);
    animation: rise 0.5s ease-out forwards;
  }
  @keyframes rise { to { opacity: 1; transform: translateY(0); } }
  .eyebrow {
    display: flex; align-items: center; gap: 8px; font-size: 11px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--brass); font-weight: 600; margin-bottom: 18px;
  }
  .eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--brass); animation: pulse 2.2s ease-in-out infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.7); } }
  h1 { font-family: 'Fraunces', serif; font-weight: 700; font-size: 29px; line-height: 1.22; margin: 0 0 10px; color: var(--heading); }
  p.sub { font-size: 15px; line-height: 1.55; color: var(--ink-soft); margin: 0 0 22px; }
  .perks { list-style: none; margin: 0 0 26px; padding: 0; display: flex; flex-direction: column; gap: 9px; }
  .perks li { display: flex; align-items: center; gap: 10px; font-size: 13.5px; color: var(--ink); }
  .perks .check {
    flex-shrink: 0; width: 18px; height: 18px; border-radius: 50%;
    background: var(--perk-bg); color: var(--perk-color); font-size: 11px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
  }
  .cta-group { display: flex; flex-direction: column; gap: 10px; }
  a.cta {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    background: var(--cta-bg); color: var(--cta-text); text-decoration: none;
    font-size: 15.5px; font-weight: 600; padding: 15px 20px; border-radius: 7px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    box-shadow: 0 8px 20px -8px var(--cta-shadow);
  }
  a.cta:hover, a.cta:active { transform: translateY(-1px); box-shadow: 0 12px 24px -8px var(--cta-shadow); }
  a.cta .arrow { font-size: 16px; transition: transform 0.18s ease; opacity: 0.8; }
  a.cta:hover .arrow { transform: translateX(3px); }
  a.cta:nth-child(n+2) { background: transparent; color: var(--heading); border: 1.5px solid var(--border); box-shadow: none; }
  .foot { margin-top: 24px; text-align: center; font-size: 11.5px; color: var(--ink-soft); }
  @media (prefers-reduced-motion: reduce) { .eyebrow .dot { animation: none; } .card { animation: none; opacity: 1; transform: none; } }
</style>
</head>
<body>
  <main class="card">
    <div class="eyebrow"><span class="dot"></span> {{ site_badge }}</div>
    <h1>{{ site_title }}</h1>
    <p class="sub">{{ site_subtitle }}</p>
    <ul class="perks">
      {% for perk in perks %}
      <li><span class="check">&#10003;</span> {{ perk }}</li>
      {% endfor %}
    </ul>
    <div class="cta-group">
      {% for link in links %}
      <a class="cta" href="{{ url_for('go', link_id=link['id']) }}">
        {{ link['name'] }} <span class="arrow">&#8594;</span>
      </a>
      {% endfor %}
    </div>
    <div class="foot">Free to join &middot; leave anytime.</div>
  </main>
</body>
</html>
"""

LANDING_TEMPLATE_1 = (
    LANDING_BASE
    .replace("__BG__", "#FAF6EF").replace("__BGGLOW__", "#E7EEE9")
    .replace("__CARD__", "#FFFFFF").replace("__BORDER__", "rgba(15,61,62,0.10)")
    .replace("__INK__", "#22262B").replace("__INKSOFT__", "#6B7268")
    .replace("__HEADING__", "#0F3D3E").replace("__BRASS__", "#C9A66B")
    .replace("__CTABG__", "#0F3D3E").replace("__CTATEXT__", "#FFFFFF")
    .replace("__CTASHADOW__", "rgba(15,61,62,0.35)")
    .replace("__PERKBG__", "#E7EEE9").replace("__PERKCOLOR__", "#0F3D3E")
    .replace("__SHADOW__", "0 20px 50px -20px rgba(15,61,62,0.25)")
)

LANDING_TEMPLATE_2 = (
    LANDING_BASE
    .replace("__BG__", "#14181A").replace("__BGGLOW__", "rgba(62,142,130,0.12)")
    .replace("__CARD__", "#1B2123").replace("__BORDER__", "rgba(217,178,124,0.16)")
    .replace("__INK__", "#F2EEE4").replace("__INKSOFT__", "#8B9391")
    .replace("__HEADING__", "#F2EEE4").replace("__BRASS__", "#D9B27C")
    .replace("__CTABG__", "#D9B27C").replace("__CTATEXT__", "#14181A")
    .replace("__CTASHADOW__", "rgba(217,178,124,0.35)")
    .replace("__PERKBG__", "rgba(217,178,124,0.15)").replace("__PERKCOLOR__", "#D9B27C")
    .replace("__SHADOW__", "0 24px 60px -20px rgba(0,0,0,0.6)")
)

TEMPLATE_HTML = {"template1": LANDING_TEMPLATE_1, "template2": LANDING_TEMPLATE_2}

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Login</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: #14181A; font-family: 'Inter', sans-serif; color: #F2EEE4; }
  form { width: 100%; max-width: 320px; background: #1B2123; border: 1px solid rgba(217,178,124,0.14);
    border-radius: 4px; padding: 32px; }
  h1 { font-size: 18px; margin: 0 0 20px; }
  label { font-size: 12px; color: #8B9391; display: block; margin-bottom: 6px; }
  input { width: 100%; padding: 10px 12px; background: #14181A; border: 1px solid rgba(217,178,124,0.25);
    border-radius: 3px; color: #F2EEE4; font-size: 14px; margin-bottom: 16px; }
  button { width: 100%; padding: 11px; background: #D9B27C; border: none; border-radius: 3px;
    color: #14181A; font-weight: 600; font-size: 14px; cursor: pointer; }
  .error { color: #E28B7A; font-size: 13px; margin-bottom: 14px; }
</style>
</head>
<body>
  <form method="post">
    <h1>Admin login</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autofocus required>
    <button type="submit">Sign in</button>
  </form>
</body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; }
body { margin: 0; background: #F4F2EE; color: #22262B; font-family: 'Inter', sans-serif; font-size: 14px; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 16px 28px; background: #0F3D3E; color: #FAF6EF; }
.brand { font-weight: 600; }
.logout { color: #C9A66B; text-decoration: none; font-size: 13px; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 28px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 8px; }
.stat-card { background: #fff; border: 1px solid rgba(15,61,62,0.10); border-radius: 6px; padding: 16px 18px; }
.stat-label { font-size: 12px; color: #6B7268; margin-bottom: 6px; }
.stat-value { font-size: 26px; font-weight: 700; color: #0F3D3E; }
.live-note { font-size: 12px; color: #6B7268; display: flex; align-items: center; gap: 6px; margin-bottom: 24px; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: #3E8E82; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
.panel { background: #fff; border: 1px solid rgba(15,61,62,0.10); border-radius: 6px; padding: 20px 22px; margin-bottom: 18px; }
.panel h2 { font-size: 15px; margin: 0 0 12px; color: #0F3D3E; }
.hint { font-size: 12.5px; color: #6B7268; margin: -6px 0 14px; }
.hint a { color: #C9A66B; }
.code-block { background: #14181A; color: #D9B27C; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12.5px; padding: 12px 14px; border-radius: 4px; overflow-x: auto; white-space: pre; margin: 10px 0; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl thead th { text-align: left; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.04em; color: #6B7268; border-bottom: 1px solid rgba(15,61,62,0.10); padding: 6px 4px; }
.tbl tbody td { padding: 8px 4px; border-bottom: 1px solid rgba(15,61,62,0.06); font-size: 13.5px; }
.tbl .right { text-align: right; }
.tbl .center { text-align: center; }
.tbl .muted { color: #9CA39B; font-style: italic; }
.links-tbl input[type="text"] { width: 100%; border: 1px solid rgba(15,61,62,0.15); border-radius: 3px; padding: 6px 8px; font-size: 13px; font-family: inherit; }
.links-tbl .url-input { min-width: 220px; }
.row-actions { display: flex; gap: 6px; white-space: nowrap; }
.inline { display: inline; }
.btn-small { border: none; border-radius: 3px; padding: 6px 10px; font-size: 12.5px; font-weight: 600; cursor: pointer; background: #0F3D3E; color: #fff; }
.btn-small.danger { background: #B0483C; }
.btn-primary { border: none; border-radius: 3px; padding: 9px 16px; font-size: 13.5px; font-weight: 600; cursor: pointer; background: #C9A66B; color: #22262B; }
.add-link-form { display: flex; gap: 8px; margin-top: 16px; }
.add-link-form input { flex: 1; border: 1px solid rgba(15,61,62,0.15); border-radius: 3px; padding: 9px 10px; font-size: 13px; font-family: inherit; }
.settings-form { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.settings-form .field { display: flex; flex-direction: column; gap: 6px; }
.settings-form label { font-size: 12px; color: #6B7268; }
.settings-form input, .settings-form select { border: 1px solid rgba(15,61,62,0.15); border-radius: 3px; padding: 8px 10px; font-size: 13px; font-family: inherit; min-width: 220px; }
.settings-form-stacked { flex-direction: column; align-items: stretch; }
.settings-form-stacked .field { width: 100%; }
.settings-form-stacked input, .settings-form-stacked select { width: 100%; min-width: 0; }
.key-row { display: flex; gap: 8px; align-items: center; margin: 10px 0; }
.key-row input { flex: 1; border: 1px solid rgba(15,61,62,0.15); border-radius: 3px; padding: 8px 10px; font-size: 12.5px; font-family: 'SFMono-Regular', Consolas, monospace; background: #F4F2EE; color: #22262B; }
@media (max-width: 800px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } .grid-2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
  <header class="topbar">
    <div class="brand">Front Desk &middot; Admin</div>
    <a class="logout" href="{{ url_for('admin_logout') }}">Log out</a>
  </header>
  <main class="wrap">
    <section class="stats-grid">
      <div class="stat-card"><div class="stat-label">Total visits</div><div class="stat-value" id="stat-visits">&mdash;</div></div>
      <div class="stat-card"><div class="stat-label">Unique visitors</div><div class="stat-value" id="stat-unique">&mdash;</div></div>
      <div class="stat-card"><div class="stat-label">Total clicks</div><div class="stat-value" id="stat-clicks">&mdash;</div></div>
      <div class="stat-card"><div class="stat-label">Click-through rate</div><div class="stat-value" id="stat-ctr">&mdash;</div></div>
      <div class="stat-card"><div class="stat-label">Bot conversions</div><div class="stat-value" id="stat-conversions">&mdash;</div></div>
      <div class="stat-card"><div class="stat-label">Conversion rate</div><div class="stat-value" id="stat-convrate">&mdash;</div></div>
    </section>
    <div class="live-note"><span class="live-dot"></span> Live &mdash; refreshes every 5s</div>

    <section class="panel">
      <h2>Traffic by platform</h2>
      <p class="hint">Detected automatically from each visitor's browser (referrer) — same link works everywhere. Shows "direct" when a browser doesn't share where it came from.</p>
      <table class="tbl">
        <thead><tr><th>Source</th><th class="right">Visits</th><th class="right">Clicks</th><th class="right">CTR</th></tr></thead>
        <tbody id="tbl-by-source"></tbody>
      </table>
    </section>

    <div class="grid-2">
      <section class="panel"><h2>Clicks by link</h2><table class="tbl" id="tbl-clicks-by-link"><thead><tr><th>Link</th><th class="right">Clicks</th><th class="right">Conversions</th></tr></thead><tbody></tbody></table></section>
      <section class="panel"><h2>Top locations</h2><table class="tbl" id="tbl-locations"><tbody></tbody></table></section>
    </div>
    <div class="grid-2">
      <section class="panel"><h2>Recent visits</h2><table class="tbl" id="tbl-recent-visits"><tbody></tbody></table></section>
      <section class="panel"><h2>Recent clicks</h2><table class="tbl" id="tbl-recent-clicks"><tbody></tbody></table></section>
    </div>

    <section class="panel">
      <h2>Links</h2>
      <p class="hint">These show up as buttons on the landing page, in this order.</p>
      <table class="tbl links-tbl">
        <thead><tr><th>Name</th><th>URL</th><th>Active</th><th></th></tr></thead>
        <tbody>
          {% for link in links %}
          <tr>
            <form method="post" action="{{ url_for('admin_update_link', link_id=link['id']) }}">
              <td><input type="text" name="name" value="{{ link['name'] }}"></td>
              <td><input type="text" name="url" value="{{ link['url'] }}" class="url-input"></td>
              <td class="center"><input type="checkbox" name="active" {% if link['active'] %}checked{% endif %}></td>
              <td class="row-actions">
                <button type="submit" class="btn-small">Save</button>
            </form>
            <form method="post" action="{{ url_for('admin_delete_link', link_id=link['id']) }}" class="inline">
                <button type="submit" class="btn-small danger" onclick="return confirm('Delete this link?')">Delete</button>
            </form>
              </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <form method="post" action="{{ url_for('admin_add_link') }}" class="add-link-form">
        <input type="text" name="name" placeholder="Button label (e.g. Contact Receptionist)" required>
        <input type="text" name="url" placeholder="https://t.me/your_bot" required>
        <button type="submit" class="btn-primary">Add link</button>
      </form>
    </section>

    <section class="panel">
      <h2>Bot integration (conversion tracking)</h2>
      <p class="hint">
        Each click carries a one-time token to your Telegram bot as a
        <code>?start=</code> deep-link parameter. In your bot's <code>/start</code>
        handler, read that parameter and report it back here — this key is
        managed right here, no server config needed:
      </p>
      <div class="key-row">
        <input type="text" id="api-key-field" value="{{ conversion_api_key }}" readonly>
        <button type="button" class="btn-small" onclick="copyApiKey()">Copy</button>
      </div>
      <form method="post" action="{{ url_for('admin_regenerate_api_key') }}" class="inline">
        <button type="submit" class="btn-small danger" onclick="return confirm('Regenerate the key? Your bot code will need updating with the new key.')">Regenerate key</button>
      </form>
      <pre class="code-block">POST {{ request.host_url }}api/conversion
Header: X-API-Key: {{ conversion_api_key }}
JSON body: {"token": "&lt;the start param the bot received&gt;"}</pre>
      <p class="hint">
        In <code>python-telegram-bot</code>, that's <code>context.args[0]</code>
        inside your <code>/start</code> handler — send it to the URL above with
        this key in the header, and this dashboard will show the conversion.
      </p>
    </section>

    <section class="panel">
      <h2>Landing page copy &amp; template</h2>
      <form method="post" action="{{ url_for('admin_update_settings') }}" class="settings-form settings-form-stacked">
        <div class="field"><label>Badge (small text above headline)</label><input type="text" name="site_badge" value="{{ site_badge }}"></div>
        <div class="field"><label>Headline</label><input type="text" name="site_title" value="{{ site_title }}"></div>
        <div class="field"><label>Subheading</label><input type="text" name="site_subtitle" value="{{ site_subtitle }}"></div>
        <div class="field"><label>Benefits (comma-separated)</label><input type="text" name="site_perks" value="{{ site_perks }}"></div>
        <div class="field">
          <label>Active template</label>
          <select name="active_template">
            {% for key, tpl in templates.items() %}
            <option value="{{ key }}" {% if key == active_template %}selected{% endif %}>{{ tpl.label }}</option>
            {% endfor %}
          </select>
        </div>
        <button type="submit" class="btn-primary">Save settings</button>
      </form>
      <p class="hint">Open <a href="{{ url_for('landing') }}" target="_blank">the live page</a> in a new tab to preview.</p>
    </section>
  </main>

<script>
function escapeHtml(s) { return (s || "").toString().replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }
function fmtTime(iso) { try { return new Date(iso).toLocaleString(); } catch (e) { return iso; } }

function copyApiKey() {
  const field = document.getElementById("api-key-field");
  navigator.clipboard.writeText(field.value).then(() => {
    field.focus();
    field.select();
  }).catch(() => {
    field.focus();
    field.select();
  });
}

async function refreshStats() {
  try {
    const res = await fetch("{{ url_for('admin_stats') }}");
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("stat-visits").textContent = data.total_visits;
    document.getElementById("stat-unique").textContent = data.unique_visitors;
    document.getElementById("stat-clicks").textContent = data.total_clicks;
    document.getElementById("stat-ctr").textContent = data.ctr + "%";
    document.getElementById("stat-conversions").textContent = data.total_conversions;
    document.getElementById("stat-convrate").textContent = data.conversion_rate + "%";

    document.querySelector("#tbl-clicks-by-link tbody").innerHTML = data.clicks_by_link.map(r =>
      `<tr><td>${escapeHtml(r.name)}</td><td class="right">${r.click_count}</td><td class="right">${r.conversion_count}</td></tr>`
    ).join("") || "<tr><td colspan='3' class='muted'>No clicks yet</td></tr>";

    document.querySelector("#tbl-locations tbody").innerHTML = data.top_cities.map(r =>
      `<tr><td>${escapeHtml(r.city)}${r.country ? ", " + escapeHtml(r.country) : ""}</td><td class="right">${r.c}</td></tr>`
    ).join("") || "<tr><td colspan='2' class='muted'>No location data yet</td></tr>";

    document.querySelector("#tbl-by-source").innerHTML = data.by_source.map(r =>
      `<tr><td>${escapeHtml(r.source)}</td><td class="right">${r.visits}</td><td class="right">${r.clicks}</td><td class="right">${r.ctr}%</td></tr>`
    ).join("") || "<tr><td colspan='4' class='muted'>No traffic yet</td></tr>";

    document.querySelector("#tbl-recent-visits tbody").innerHTML = data.recent_visits.map(r =>
      `<tr><td>${fmtTime(r.created_at)}</td><td>${escapeHtml(r.city || r.country || "Unknown")}</td><td class="muted">${r.ip_hash}</td></tr>`
    ).join("") || "<tr><td colspan='3' class='muted'>No visits yet</td></tr>";

    document.querySelector("#tbl-recent-clicks tbody").innerHTML = data.recent_clicks.map(r =>
      `<tr><td>${fmtTime(r.created_at)}</td><td>${escapeHtml(r.link_name)}</td><td class="muted">${r.ip_hash}</td></tr>`
    ).join("") || "<tr><td colspan='3' class='muted'>No clicks yet</td></tr>";
  } catch (e) { console.error("stats refresh failed", e); }
}
refreshStats();
setInterval(refreshStats, 5000);
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_hash TEXT NOT NULL,
            country TEXT,
            region TEXT,
            city TEXT,
            user_agent TEXT,
            source TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            ip_hash TEXT NOT NULL,
            source TEXT,
            token TEXT,
            converted_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (link_id) REFERENCES links (id)
        );
        """
    )
    # Migrate older databases created before these columns existed.
    for table, column in [("visits", "source"), ("clicks", "source"), ("clicks", "token"), ("clicks", "converted_at")]:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_template', 'template1')")
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('site_badge', 'Instant access · Online now')")
    db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('site_title', 'You''re one tap away from joining')")
    db.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES "
        "('site_subtitle', 'Join for instant updates, exclusive content, and direct access to the team.')"
    )
    db.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES "
        "('site_perks', 'Instant access, no forms,Daily updates & exclusive content,Real replies from our team')"
    )
    existing_key = db.execute("SELECT value FROM settings WHERE key = 'conversion_api_key'").fetchone()
    if not existing_key:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('conversion_api_key', ?)",
            (secrets.token_urlsafe(24),),
        )
    cur = db.execute("SELECT COUNT(*) FROM links")
    if cur.fetchone()[0] == 0:
        db.execute(
            "INSERT INTO links (name, url, active, sort_order) VALUES (?, ?, 1, 0)",
            ("Join Now", "https://t.me/your_bot_here"),
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def hash_ip(ip):
    salt = app.secret_key
    return hashlib.sha256((salt + ip).encode("utf-8")).hexdigest()[:16]


def is_private_ip(ip):
    return (
        ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168.")
        or ip == "0.0.0.0" or ip == "::1"
    )


def geolocate(ip):
    if is_private_ip(ip):
        return {"country": "Local", "region": "", "city": ""}
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,regionName,city"},
            timeout=2,
        )
        data = resp.json()
        if data.get("status") == "success":
            return {"country": data.get("country", ""), "region": data.get("regionName", ""), "city": data.get("city", "")}
    except requests.RequestException:
        pass
    return {"country": "Unknown", "region": "", "city": ""}


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def get_source():
    """Detect which platform sent this visitor — from the HTTP Referer header,
    no tracking params or separate links needed. Falls back to a cookie so a
    click later in the same visit is still attributed correctly, then 'direct'."""
    referrer = request.referrer or ""
    if referrer:
        try:
            host = urlparse(referrer).netloc.lower()
        except ValueError:
            host = ""
        host = host.replace("www.", "")
        patterns = [
            ("facebook", ["facebook.com", "fb.com", "l.facebook.com", "m.facebook.com", "lm.facebook.com"]),
            ("instagram", ["instagram.com", "l.instagram.com"]),
            ("whatsapp", ["whatsapp.com", "wa.me"]),
            ("messenger", ["messenger.com", "l.messenger.com"]),
            ("google", ["google.com", "googleadservices.com", "googlesyndication.com"]),
            ("youtube", ["youtube.com", "youtu.be"]),
            ("tiktok", ["tiktok.com"]),
            ("twitter/x", ["twitter.com", "t.co", "x.com"]),
            ("telegram", ["t.me", "telegram.org"]),
            ("linkedin", ["linkedin.com"]),
            ("snapchat", ["snapchat.com"]),
        ]
        for label, domains in patterns:
            if any(d in host for d in domains):
                return label
        if host:
            return host[:40]
    return request.cookies.get("src", "direct")


@app.route("/")
def landing():
    db = get_db()
    ip = client_ip()
    ip_hashed = hash_ip(ip)
    geo = geolocate(ip)
    source = get_source()

    db.execute(
        "INSERT INTO visits (ip_hash, country, region, city, user_agent, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ip_hashed, geo["country"], geo["region"], geo["city"], request.headers.get("User-Agent", ""), source, now_iso()),
    )
    db.commit()

    links = db.execute("SELECT * FROM links WHERE active = 1 ORDER BY sort_order ASC, id ASC").fetchall()
    template_key = get_setting("active_template", "template1")
    html = TEMPLATE_HTML.get(template_key, LANDING_TEMPLATE_1)
    site_title = get_setting("site_title", "You're one tap away from joining")
    site_subtitle = get_setting("site_subtitle", "Join for instant updates, exclusive content, and direct access to the team.")
    site_badge = get_setting("site_badge", "Instant access · Online now")
    perks_raw = get_setting("site_perks", "Instant access, no forms,Daily updates & exclusive content,Real replies from our team")
    perks = [p.strip() for p in perks_raw.split(",") if p.strip()]

    resp = render_template_string(html, links=links, site_title=site_title, site_subtitle=site_subtitle, site_badge=site_badge, perks=perks)
    response = app.make_response(resp)
    response.set_cookie("src", source, max_age=60 * 60 * 24 * 7, samesite="Lax")
    return response


def build_redirect_url(url, token):
    """If this is a t.me / telegram.me link, attach the tracking token as a
    Telegram deep-link start parameter so the bot can report back a
    conversion. Left untouched for any other kind of link."""
    host = urlparse(url).netloc.lower()
    if "t.me" in host or "telegram.me" in host:
        separator = "&" if "?" in url else "?"
        if "start=" not in url:
            return f"{url}{separator}start={token}"
    return url


@app.route("/go/<int:link_id>")
def go(link_id):
    db = get_db()
    link = db.execute("SELECT * FROM links WHERE id = ? AND active = 1", (link_id,)).fetchone()
    if not link:
        abort(404)
    ip_hashed = hash_ip(client_ip())
    source = request.cookies.get("src", "direct")
    token = secrets.token_urlsafe(12)
    db.execute(
        "INSERT INTO clicks (link_id, ip_hash, source, token, created_at) VALUES (?, ?, ?, ?, ?)",
        (link_id, ip_hashed, source, token, now_iso()),
    )
    db.commit()
    return redirect(build_redirect_url(link["url"], token))


@app.route("/api/conversion", methods=["POST"])
def api_conversion():
    """Called by your Telegram bot's /start handler to report that a
    tracked click actually reached the bot. Send:
        POST /api/conversion
        Header: X-API-Key: <CONVERSION_API_KEY>
        JSON body: {"token": "<the start-param value the bot received>"}
    """
    if request.headers.get("X-API-Key") != get_setting("conversion_api_key"):
        abort(401)
    token = (request.get_json(silent=True) or {}).get("token") or request.form.get("token")
    if not token:
        return jsonify({"ok": False, "error": "missing token"}), 400

    db = get_db()
    row = db.execute("SELECT id, converted_at FROM clicks WHERE token = ?", (token,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "unknown token"}), 404
    if not row["converted_at"]:
        db.execute("UPDATE clicks SET converted_at = ? WHERE id = ?", (now_iso(), row["id"]))
        db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Admin: auth
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Wrong password."
    return render_template_string(ADMIN_LOGIN_HTML, error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin: dashboard + management
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    links = db.execute("SELECT * FROM links ORDER BY sort_order ASC, id ASC").fetchall()
    active_template = get_setting("active_template", "template1")
    site_title = get_setting("site_title", "You're one tap away from joining")
    site_subtitle = get_setting("site_subtitle", "Join for instant updates, exclusive content, and direct access to the team.")
    site_badge = get_setting("site_badge", "Instant access · Online now")
    site_perks = get_setting("site_perks", "Instant access, no forms,Daily updates & exclusive content,Real replies from our team")
    conversion_api_key = get_setting("conversion_api_key", "")
    return render_template_string(
        ADMIN_DASHBOARD_HTML, links=links, templates=TEMPLATES,
        active_template=active_template, site_title=site_title,
        site_subtitle=site_subtitle, site_badge=site_badge, site_perks=site_perks,
        conversion_api_key=conversion_api_key,
    )


@app.route("/admin/links/add", methods=["POST"])
@login_required
def admin_add_link():
    db = get_db()
    name = request.form.get("name", "").strip() or "Contact Receptionist"
    url = request.form.get("url", "").strip()
    if url:
        db.execute("INSERT INTO links (name, url, active, sort_order) VALUES (?, ?, 1, 0)", (name, url))
        db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/links/<int:link_id>/update", methods=["POST"])
@login_required
def admin_update_link(link_id):
    db = get_db()
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    active = 1 if request.form.get("active") == "on" else 0
    db.execute("UPDATE links SET name = ?, url = ?, active = ? WHERE id = ?", (name, url, active, link_id))
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/links/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_delete_link(link_id):
    db = get_db()
    db.execute("DELETE FROM links WHERE id = ?", (link_id,))
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/settings", methods=["POST"])
@login_required
def admin_update_settings():
    template_key = request.form.get("active_template")
    site_title = request.form.get("site_title", "").strip()
    site_subtitle = request.form.get("site_subtitle", "").strip()
    site_badge = request.form.get("site_badge", "").strip()
    site_perks = request.form.get("site_perks", "").strip()
    if template_key in TEMPLATES:
        set_setting("active_template", template_key)
    if site_title:
        set_setting("site_title", site_title)
    if site_subtitle:
        set_setting("site_subtitle", site_subtitle)
    if site_badge:
        set_setting("site_badge", site_badge)
    if site_perks:
        set_setting("site_perks", site_perks)
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/regenerate-api-key", methods=["POST"])
@login_required
def admin_regenerate_api_key():
    set_setting("conversion_api_key", secrets.token_urlsafe(24))
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Admin: live analytics API
# ---------------------------------------------------------------------------

@app.route("/admin/api/stats")
@login_required
def admin_stats():
    db = get_db()
    total_visits = db.execute("SELECT COUNT(*) c FROM visits").fetchone()["c"]
    total_clicks = db.execute("SELECT COUNT(*) c FROM clicks").fetchone()["c"]
    total_conversions = db.execute("SELECT COUNT(*) c FROM clicks WHERE converted_at IS NOT NULL").fetchone()["c"]
    unique_visitors = db.execute("SELECT COUNT(DISTINCT ip_hash) c FROM visits").fetchone()["c"]
    ctr = round((total_clicks / total_visits) * 100, 1) if total_visits else 0.0
    conversion_rate = round((total_conversions / total_clicks) * 100, 1) if total_clicks else 0.0

    clicks_by_link = db.execute(
        """SELECT l.id, l.name, COUNT(c.id) as click_count,
                  COUNT(c.converted_at) as conversion_count
           FROM links l LEFT JOIN clicks c ON c.link_id = l.id
           GROUP BY l.id ORDER BY click_count DESC"""
    ).fetchall()

    top_cities = db.execute(
        """SELECT COALESCE(city, 'Unknown') as city, COALESCE(country, '') as country, COUNT(*) as c
           FROM visits WHERE city IS NOT NULL AND city != '' GROUP BY city, country ORDER BY c DESC LIMIT 10"""
    ).fetchall()

    by_source = db.execute(
        """SELECT COALESCE(v.source, 'direct') as source,
                  COUNT(DISTINCT v.id) as visits,
                  COUNT(DISTINCT cl.id) as clicks
           FROM visits v
           LEFT JOIN clicks cl ON cl.source = v.source
           GROUP BY COALESCE(v.source, 'direct')
           ORDER BY visits DESC"""
    ).fetchall()
    by_source_rows = []
    for r in by_source:
        v, c = r["visits"], r["clicks"]
        by_source_rows.append({
            "source": r["source"], "visits": v, "clicks": c,
            "ctr": round((c / v) * 100, 1) if v else 0.0,
        })

    recent_visits = db.execute(
        "SELECT ip_hash, country, city, created_at FROM visits ORDER BY id DESC LIMIT 15"
    ).fetchall()

    recent_clicks = db.execute(
        """SELECT c.created_at, l.name as link_name, c.ip_hash FROM clicks c
           JOIN links l ON l.id = c.link_id ORDER BY c.id DESC LIMIT 15"""
    ).fetchall()

    return jsonify({
        "total_visits": total_visits, "total_clicks": total_clicks, "unique_visitors": unique_visitors,
        "ctr": ctr, "total_conversions": total_conversions, "conversion_rate": conversion_rate,
        "clicks_by_link": [dict(r) for r in clicks_by_link],
        "top_cities": [dict(r) for r in top_cities],
        "by_source": by_source_rows,
        "recent_visits": [dict(r) for r in recent_visits],
        "recent_clicks": [dict(r) for r in recent_clicks],
    })


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
