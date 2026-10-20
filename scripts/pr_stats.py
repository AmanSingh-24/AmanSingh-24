#!/usr/bin/env python3
"""Builds assets/pr-stats.svg: PR totals + per-org donut and bar chart.

Env:
  GH_USER   GitHub username (default: AmanSingh-24)
  GH_TOKEN  Token for the GitHub API. The default Actions token only sees public
            repos; a PAT with `repo` read access also counts PRs in private org repos.
"""
import json, math, os, urllib.request, urllib.parse
from collections import OrderedDict
from datetime import datetime, timezone
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "AmanSingh-24")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("OUT", "pr-stats.svg")
PALETTE = ["#00F7FF", "#7B00FF", "#FF6B6B", "#4ECDC4", "#FFD93D", "#A66CFF", "#6BCB77", "#FF9F43"]


def fetch_prs():
    items, page = [], 1
    while page <= 10:  # search API caps at 1000 results
        q = urllib.parse.quote(f"author:{USER} type:pr")
        url = f"https://api.github.com/search/issues?q={q}&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "pr-stats"})
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        items += data["items"]
        if len(data["items"]) < 100 or len(items) >= data["total_count"]:
            break
        page += 1
    return items


def aggregate(items):
    orgs = OrderedDict()
    for it in items:
        owner = it["repository_url"].split("/repos/")[1].split("/")[0]
        merged = bool((it.get("pull_request") or {}).get("merged_at"))
        o = orgs.setdefault(owner, {"raised": 0, "merged": 0, "open": 0, "closed": 0})
        o["raised"] += 1
        if merged:
            o["merged"] += 1
        elif it["state"] == "open":
            o["open"] += 1
        else:
            o["closed"] += 1
    return OrderedDict(sorted(orgs.items(), key=lambda kv: (-kv[1]["raised"], -kv[1]["merged"], kv[0].lower())))


def short(s, n=20):
    return s if len(s) <= n else s[: n - 1] + "…"


def build_svg(orgs):
    tot = {k: sum(o[k] for o in orgs.values()) for k in ("raised", "merged", "open", "closed")}
    n = max(len(orgs), 1)
    panel_h = max(n * 44, 170)
    W, H = 848, 190 + panel_h + 20
    font = "font-family=\"'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif\""
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Pull request statistics">',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="#0D1117" stroke="#30363d"/>',
         f'<text x="30" y="40" {font} font-size="18" font-weight="700" fill="#00F7FF" letter-spacing="1.5">PULL REQUEST ACTIVITY</text>',
         f'<text x="{W-30}" y="40" {font} font-size="11" fill="#8b949e" text-anchor="end">@{escape(USER)} · updated {datetime.now(timezone.utc):%d %b %Y}</text>']

    rate = round(100 * tot["merged"] / tot["raised"]) if tot["raised"] else 0
    tiles = [("RAISED", tot["raised"], "#00F7FF", "total pull requests"),
             ("MERGED", tot["merged"], "#6BCB77", f"{rate}% merge rate"),
             ("OPEN", tot["open"], "#FFD93D", "awaiting review"),
             ("CLOSED", tot["closed"], "#FF6B6B", "closed without merge")]
    for i, (lab, val, col, sub) in enumerate(tiles):
        x = 30 + i * 201
        p += [f'<rect x="{x}" y="60" width="185" height="82" rx="10" fill="#161b22" stroke="#30363d"/>',
              f'<rect x="{x}" y="60" width="4" height="82" rx="2" fill="{col}"/>',
              f'<text x="{x+20}" y="84" {font} font-size="11" font-weight="600" fill="#8b949e" letter-spacing="1.2">{lab}</text>',
              f'<text x="{x+20}" y="119" {font} font-size="32" font-weight="700" fill="{col}">{val}</text>',
              f'<text x="{x+20}" y="134" {font} font-size="10" fill="#8b949e">{sub}</text>']

    top = 170
    p.append(f'<text x="30" y="{top+8}" {font} font-size="12" font-weight="600" fill="#c9d1d9" letter-spacing="1">PRs RAISED BY ORG</text>')
    cx, cy, r, sw = 105, top + 100, 62, 24
    C = 2 * math.pi * r
    if tot["raised"]:
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#161b22" stroke-width="{sw}"/>')
        cum = 0.0
        for i, (name, o) in enumerate(orgs.items()):
            ln = C * o["raised"] / tot["raised"]
            gap = 2 if len(orgs) > 1 else 0
            p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{PALETTE[i % len(PALETTE)]}" stroke-width="{sw}" '
                     f'stroke-dasharray="{max(ln-gap,0.1):.2f} {C-max(ln-gap,0.1):.2f}" stroke-dashoffset="{-cum:.2f}" transform="rotate(-90 {cx} {cy})"/>')
            cum += ln
    p += [f'<text x="{cx}" y="{cy+8}" {font} font-size="26" font-weight="700" fill="#ffffff" text-anchor="middle">{tot["raised"]}</text>',
          f'<text x="{cx}" y="{cy+24}" {font} font-size="9" fill="#8b949e" text-anchor="middle" letter-spacing="1">TOTAL</text>']
    for i, (name, o) in enumerate(orgs.items()):
        y = top + 50 + i * 26
        pct = round(100 * o["raised"] / tot["raised"]) if tot["raised"] else 0
        p += [f'<rect x="205" y="{y-9}" width="10" height="10" rx="2" fill="{PALETTE[i % len(PALETTE)]}"/>',
              f'<text x="222" y="{y}" {font} font-size="12" fill="#c9d1d9">{escape(short(name, 18))}</text>',
              f'<text x="402" y="{y}" {font} font-size="12" fill="#8b949e" text-anchor="end">{o["raised"]} · {pct}%</text>']

    bx, bw = 450, 368
    p.append(f'<text x="{bx}" y="{top+8}" {font} font-size="12" font-weight="600" fill="#c9d1d9" letter-spacing="1">MERGED vs RAISED</text>')
    mx = max((o["raised"] for o in orgs.values()), default=1)
    for i, (name, o) in enumerate(orgs.items()):
        y = top + 38 + i * 44
        col = PALETTE[i % len(PALETTE)]
        full = bw * o["raised"] / mx
        mw = bw * o["merged"] / mx
        p += [f'<text x="{bx}" y="{y}" {font} font-size="12" fill="#c9d1d9">{escape(short(name, 26))}</text>',
              f'<text x="{bx+bw}" y="{y}" {font} font-size="11" fill="#8b949e" text-anchor="end">{o["merged"]} merged / {o["raised"]} raised</text>',
              f'<rect x="{bx}" y="{y+8}" width="{bw}" height="12" rx="6" fill="#161b22"/>',
              f'<rect x="{bx}" y="{y+8}" width="{max(full,12):.1f}" height="12" rx="6" fill="{col}" fill-opacity="0.3"/>']
        if o["merged"]:
            p.append(f'<rect x="{bx}" y="{y+8}" width="{max(mw,12):.1f}" height="12" rx="6" fill="{col}"/>')
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    prs = fetch_prs()
    orgs = aggregate(prs)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_svg(orgs))
    print(f"{len(prs)} PRs across {len(orgs)} owners -> {OUT}")
    for k, v in orgs.items():
        print(f"  {k}: {v}")
