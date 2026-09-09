#!/usr/bin/env python3
"""
Regenerates assets/stats.svg from the GitHub GraphQL API.

Run by .github/workflows/metrics.yml. Needs GH_TOKEN in the environment
(a classic PAT with `read:user` + `repo` scopes — set as the repo secret
METRICS_TOKEN and passed in by the workflow).

Stdlib only, on purpose: the workflow has no `pip install` step, so this
has to run on whatever ships with actions/setup-python.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime

TOKEN = os.environ.get("GH_TOKEN")
if not TOKEN:
    sys.exit("GH_TOKEN is not set — add repo secret METRICS_TOKEN and pass it in the workflow.")

OUT_PATH = "assets/stats.svg"

QUERY = """
query {
  viewer {
    login
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def gh_graphql(query: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-script",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        sys.exit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["viewer"]


def compute_stats(viewer: dict) -> dict:
    repos = viewer["repositories"]["nodes"]
    total_repos = viewer["repositories"]["totalCount"]
    total_stars = sum(r["stargazerCount"] for r in repos)

    lang_bytes = {}
    lang_color = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + edge["size"]
            lang_color[name] = edge["node"]["color"] or "#8b949e"
    total_bytes = sum(lang_bytes.values()) or 1
    lang_sorted = sorted(lang_bytes.items(), key=lambda kv: -kv[1])

    # collapse anything under 3% into "Other" so the bar/legend stay readable
    top, other = [], 0
    for name, size in lang_sorted:
        if size / total_bytes >= 0.03:
            top.append((name, size))
        else:
            other += size
    if other:
        top.append(("Other", other))

    weeks = viewer["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort(key=lambda d: d[0])

    total_contrib = viewer["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    active_days = sum(1 for _, c in days if c > 0)
    max_day = max((c for _, c in days), default=0)

    best = run = 0
    for _, c in days:
        if c > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    cur = 0
    for _, c in reversed(days):
        if c > 0:
            cur += 1
        else:
            break

    return {
        "login": viewer["login"],
        "followers": viewer["followers"]["totalCount"],
        "total_repos": total_repos,
        "total_stars": total_stars,
        "total_contrib": total_contrib,
        "active_days": active_days,
        "max_day": max_day,
        "best_streak": best,
        "cur_streak": cur,
        "days": days,
        "langs": top,
        "lang_color": lang_color,
        "total_bytes": total_bytes,
    }


LEVEL_COLORS = ["#161B22", "#0C3A2A", "#00754A", "#00A768", "#00E58A"]


def level_for(count: int, max_day: int) -> int:
    if count == 0 or max_day == 0:
        return 0
    frac = count / max_day
    if frac <= 0.15:
        return 1
    if frac <= 0.35:
        return 2
    if frac <= 0.65:
        return 3
    return 4


def build_calendar_svg(days, max_day):
    if not days:
        return "", "", 0
    start = date.fromisoformat(days[0][0])
    offset = (start.weekday() + 1) % 7  # Sunday = 0
    first_sunday_ord = start.toordinal() - offset

    cells = []
    month_seen = set()
    month_labels = []
    GX, GY, GAP = 34, 238, 16
    for d_str, count in days:
        d = date.fromisoformat(d_str)
        weekday = (d.weekday() + 1) % 7
        week = (d.toordinal() - first_sunday_ord) // 7
        x, y = GX + week * GAP, GY + weekday * GAP
        color = LEVEL_COLORS[level_for(count, max_day)]
        cells.append(
            f'<rect x="{x}.0" y="{y}.0" width="13" height="13" rx="2.5" fill="{color}">'
            f"<title>{d_str}: {count}</title></rect>"
        )
        key = (d.year, d.month)
        if key not in month_seen and weekday == 0:
            month_seen.add(key)
            month_labels.append((x, d.strftime("%b")))

    filtered, last_x = [], -100
    for x, name in month_labels:
        if x - last_x >= 40:
            filtered.append((x, name))
            last_x = x
    month_svg = "\n".join(
        f'<text x="{x}.0" y="230.0" font-size="11"><tspan fill="#7D8590">{name}</tspan></text>'
        for x, name in filtered
    )
    max_week = max(
        ((date.fromisoformat(d).toordinal() - first_sunday_ord) // 7) for d, _ in days
    )
    return "\n".join(cells), month_svg, max_week


def build_language_svg(langs, lang_color, total_bytes):
    bar_x, bar_w, bar_y = 34.0, 932.0, 430.0
    legend_y = 459.0
    bar_rects, legend_items = [], []
    x_cursor, leg_x = bar_x, bar_x + 5
    for name, size in langs:
        frac = size / total_bytes
        w = bar_w * frac
        color = lang_color.get(name, "#8b949e")
        pct = round(frac * 100)
        bar_rects.append(
            f'<rect x="{x_cursor:.2f}" y="{bar_y}" width="{w:.2f}" height="14" '
            f'fill="{color}" clip-path="url(#lb)"><title>{name} {pct}%</title></rect>'
        )
        label = f"{name}  {pct}%"
        legend_items.append(
            f'<circle cx="{leg_x:.1f}" cy="{legend_y}" r="5" fill="{color}"/>'
            f'<text x="{leg_x + 12:.1f}" y="{legend_y + 5}" font-size="13">'
            f'<tspan fill="#E6EDF3" font-weight="500">{name}</tspan>'
            f'<tspan fill="#7D8590">  {pct}%</tspan></text>'
        )
        x_cursor += w
        leg_x += 12 + (len(label) * 6.6) + 28
    return "\n".join(bar_rects), "\n".join(legend_items)


def render(stats: dict) -> str:
    cells_svg, month_svg, max_week = build_calendar_svg(stats["days"], stats["max_day"])
    lang_bar_svg, lang_legend_svg = build_language_svg(
        stats["langs"], stats["lang_color"], stats["total_bytes"]
    )
    login = stats["login"]

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="516" viewBox="0 0 1000 516" role="img" aria-label="GitHub statistics for {login}: {stats['total_contrib']} contributions in the last year, {stats['total_stars']} stars, {stats['total_repos']} repositories.">
<style>text{{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace;white-space:pre}}</style>
<defs>
<linearGradient id="glow" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#00E58A"/><stop offset=".5" stop-color="#56D4FF"/><stop offset="1" stop-color="#C792EA"/></linearGradient>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#161C28"/><stop offset="1" stop-color="#0B0E14"/></linearGradient>
</defs>
<rect width="1000" height="516" rx="12" fill="#0B0E14" stroke="#1F2733"/>
<path d="M12 0h976a12 12 0 0 1 12 12v28H0V12A12 12 0 0 1 12 0z" fill="url(#fade)"/>
<rect y="39" width="1000" height="1" fill="#1F2733"/>
<circle cx="26" cy="20" r="6" fill="#FF5F57"/><circle cx="48" cy="20" r="6" fill="#FEBC2E"/><circle cx="70" cy="20" r="6" fill="#28C840"/>
<text x="500" y="25" text-anchor="middle" fill="#7D8590" font-size="13">{login}@github &#8210; ~/metrics &#8210; zsh</text>

<text x="34.0" y="78.0" font-size="16"><tspan fill="#00E58A" font-weight="700">$ </tspan><tspan fill="#E6EDF3" font-weight="500">gh stats --last-12-months</tspan></text>

<rect x="34.0" y="108.0" width="221.0" height="62" rx="6" fill="#0E141D" stroke="#1F2733"/>
<text x="50.0" y="140.0" font-size="27"><tspan fill="#56D4FF" font-weight="700">{stats['total_contrib']}</tspan></text>
<text x="50.0" y="158.0" font-size="12"><tspan fill="#7D8590">contributions</tspan></text>

<rect x="267.0" y="108.0" width="221.0" height="62" rx="6" fill="#0E141D" stroke="#1F2733"/>
<text x="283.0" y="140.0" font-size="27"><tspan fill="#FFB86C" font-weight="700">{stats['total_stars']}</tspan></text>
<text x="283.0" y="158.0" font-size="12"><tspan fill="#7D8590">stars earned</tspan></text>

<rect x="500.0" y="108.0" width="221.0" height="62" rx="6" fill="#0E141D" stroke="#1F2733"/>
<text x="516.0" y="140.0" font-size="27"><tspan fill="#C792EA" font-weight="700">{stats['total_repos']}</tspan></text>
<text x="516.0" y="158.0" font-size="12"><tspan fill="#7D8590">repositories</tspan></text>

<rect x="733.0" y="108.0" width="221.0" height="62" rx="6" fill="#0E141D" stroke="#1F2733"/>
<text x="749.0" y="140.0" font-size="27"><tspan fill="#00E58A" font-weight="700">{stats['active_days']}</tspan></text>
<text x="749.0" y="158.0" font-size="12"><tspan fill="#7D8590">active days</tspan></text>

<text x="34.0" y="204.0" font-size="16"><tspan fill="#00E58A" font-weight="700">$ </tspan><tspan fill="#E6EDF3" font-weight="500">gh contributions --graph</tspan></text>

{month_svg}

{cells_svg}

<text x="34.0" y="370.0" font-size="13"><tspan fill="#E6EDF3" font-weight="600">{stats['cur_streak']}d current streak</tspan><tspan fill="#7D8590">   &#183;   </tspan><tspan fill="#E6EDF3" font-weight="600">{stats['best_streak']}d best streak</tspan><tspan fill="#7D8590">   &#183;   </tspan><tspan fill="#E6EDF3" font-weight="600">{stats['max_day']} contributions in a day</tspan></text>

<text x="821.0" y="370.0" font-size="11" text-anchor="end"><tspan fill="#7D8590">less</tspan></text>
<rect x="829.0" y="361.0" width="11" height="11" rx="2.5" fill="#161B22"/>
<rect x="843.0" y="361.0" width="11" height="11" rx="2.5" fill="#0C3A2A"/>
<rect x="857.0" y="361.0" width="11" height="11" rx="2.5" fill="#00754A"/>
<rect x="871.0" y="361.0" width="11" height="11" rx="2.5" fill="#00A768"/>
<rect x="885.0" y="361.0" width="11" height="11" rx="2.5" fill="#00E58A"/>
<text x="901.0" y="370.0" font-size="11"><tspan fill="#7D8590">more</tspan></text>

<text x="34.0" y="408.0" font-size="16"><tspan fill="#00E58A" font-weight="700">$ </tspan><tspan fill="#E6EDF3" font-weight="500">gh languages --source-only</tspan></text>

<clipPath id="lb"><rect x="34" y="430.0" width="932" height="14" rx="7"/></clipPath>
{lang_bar_svg}

{lang_legend_svg}

<text x="34.0" y="486.0" font-size="11"><tspan fill="#7D8590">byte-level source breakdown across owned, non-fork repositories</tspan></text>
<rect x="0" y="513" width="1000" height="3" fill="url(#glow)" opacity=".9"/>
</svg>
'''


def main():
    viewer = gh_graphql(QUERY)
    stats = compute_stats(viewer)
    svg = render(stats)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"[{datetime.now().isoformat(timespec='seconds')}] wrote {OUT_PATH} "
          f"({stats['total_contrib']} contributions, {stats['total_stars']} stars, "
          f"{stats['total_repos']} repos)")


if __name__ == "__main__":
    main()