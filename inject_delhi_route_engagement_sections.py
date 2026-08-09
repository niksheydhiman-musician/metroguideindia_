#!/usr/bin/env python3
from __future__ import annotations

import heapq
import json
import re
import difflib
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "delhi-metro" / "routes"
DELHI_JSON = REPO_ROOT / "data" / "delhi.json"

BRAND = "#1a2a6c"
WARN = "#C84B31"
CARD = "#fff"

SEQ_START = "<!-- MGI_ROUTE_SEQUENCE_START -->"
SEQ_END = "<!-- MGI_ROUTE_SEQUENCE_END -->"
ROAD_START = "<!-- MGI_ROAD_COMPARE_START -->"
ROAD_END = "<!-- MGI_ROAD_COMPARE_END -->"


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


def load_data() -> tuple[dict, dict, dict, dict]:
    data = json.loads(DELHI_JSON.read_text(encoding="utf-8"))
    stations = data["stations"]
    by_id = {s["station_id"]: s for s in stations}
    slug_to_ids: dict[str, list[str]] = defaultdict(list)
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for s in stations:
        slug_to_ids[slugify(s["station_name"])].append(s["station_id"])
        name_to_ids[s["station_name"].strip().lower()].append(s["station_id"])
    line_meta = {l["line_id"]: l for l in data["lines"]}
    return data, by_id, slug_to_ids, line_meta


ALIASES = {
    "mg-road": "m-g-road",
    "millennium-city-centre": "millennium-city-centre-gurugram",
    "huda-city-centre": "millennium-city-centre-gurugram",
    "igi-airport": "terminal-1-igi-airport",
    "airport": "terminal-1-igi-airport",
    "badarpur": "badarpur-border",
    "new-delhi-railway-station": "new-delhi",
    "noida-sector-62": "sector-62-noida",
    "south-campus": "durgabai-deshmukh-south-campus",
    "sarai-rohilla": "sarai",
    "brigadier-hoshiar-singh": "brig-hoshiar-singh",
    "iit-delhi": "iit",
    "gtb-nagar": "guru-teg-bahadur-nagar",
    "madhuban-chowk": "haiderpur-badli-mor",
    "ina": "dilli-haat-ina",
}


def simplify_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_slug_ids(slug: str, slug_to_ids: dict[str, list[str]]) -> list[str]:
    if slug in slug_to_ids:
        return slug_to_ids[slug]
    aliased = ALIASES.get(slug)
    if aliased and aliased in slug_to_ids:
        return slug_to_ids[aliased]
    target = simplify_slug(slug)
    for k, ids in slug_to_ids.items():
        if simplify_slug(k) == target:
            return ids
    for k, ids in slug_to_ids.items():
        sk = simplify_slug(k)
        if sk.startswith(target) or target.startswith(sk):
            return ids
    close = difflib.get_close_matches(slug, list(slug_to_ids.keys()), n=1, cutoff=0.82)
    if close:
        return slug_to_ids[close[0]]
    return []


def build_graph(data: dict, by_id: dict) -> dict[str, list[tuple[str, float, bool]]]:
    graph: dict[str, list[tuple[str, float, bool]]] = defaultdict(list)

    for c in data.get("connections", []):
        a = c.get("from_station")
        b = c.get("to_station")
        if not a or not b or a not in by_id or b not in by_id:
            continue
        d = float(c.get("distance_km") or 1.2)
        graph[a].append((b, d, False))
        graph[b].append((a, d, False))

    by_name: dict[str, list[str]] = defaultdict(list)
    for sid, st in by_id.items():
        by_name[st["station_name"].strip().lower()].append(sid)

    for _, ids in by_name.items():
        if len(ids) < 2:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                graph[a].append((b, 0.05, True))
                graph[b].append((a, 0.05, True))

    return graph


def shortest_path(
    graph: dict[str, list[tuple[str, float, bool]]],
    starts: list[str],
    ends: set[str],
) -> list[str]:
    pq: list[tuple[float, str]] = []
    dist: dict[str, float] = {}
    prev: dict[str, str | None] = {}

    for s in starts:
        dist[s] = 0.0
        prev[s] = None
        heapq.heappush(pq, (0.0, s))

    best_end = None
    while pq:
        cur, u = heapq.heappop(pq)
        if cur > dist.get(u, float("inf")):
            continue
        if u in ends:
            best_end = u
            break
        for v, edge_d, is_xfer in graph.get(u, []):
            penalty = 0.7 if is_xfer else 0.0
            nd = cur + edge_d + penalty
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if best_end is None:
        return []
    path: list[str] = []
    cur = best_end
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path


def route_path_for_file(
    stem: str,
    graph: dict[str, list[tuple[str, float, bool]]],
    slug_to_ids: dict[str, list[str]],
) -> list[str]:
    parts = stem.split("-to-")
    if len(parts) < 2:
        return []
    best: list[str] = []
    for i in range(1, len(parts)):
        origin_slug = "-to-".join(parts[:i])
        dest_slug = "-to-".join(parts[i:])
        starts = resolve_slug_ids(origin_slug, slug_to_ids)
        ends = set(resolve_slug_ids(dest_slug, slug_to_ids))
        if not starts or not ends:
            continue
        path = shortest_path(graph, starts, ends)
        if path and (not best or len(path) < len(best)):
            best = path
    return best


def clean_existing_blocks(html: str) -> str:
    html = re.sub(
        rf"{re.escape(SEQ_START)}.*?{re.escape(SEQ_END)}\s*",
        "",
        html,
        flags=re.S,
    )
    html = re.sub(
        rf"{re.escape(ROAD_START)}.*?{re.escape(ROAD_END)}\s*",
        "",
        html,
        flags=re.S,
    )
    html = re.sub(r'<section class="mgi-route-track"[^>]*>.*?</section>\s*', "", html, flags=re.S)
    return html


def build_station_sequence_html(path_ids: list[str], by_id: dict, line_meta: dict) -> str:
    rows = []
    interchanges = []
    for i, sid in enumerate(path_ids):
        st = by_id[sid]
        name = st["station_name"]
        line_id = st.get("line_id", "")
        line_name = line_meta.get(line_id, {}).get("line_name", "Delhi Metro")
        line_color = line_meta.get(line_id, {}).get("color") or BRAND
        badge = ""
        if i > 0:
            prev_line = by_id[path_ids[i - 1]].get("line_id", "")
            if prev_line != line_id and by_id[path_ids[i - 1]]["station_name"].lower() == name.lower():
                prev_name = line_meta.get(prev_line, {}).get("line_name", prev_line.replace("_", " ").title())
                badge = f'<span style="font-size:.75rem;color:{WARN};font-weight:700">Interchange: {prev_name} → {line_name}</span>'
                interchanges.append((name, prev_name, line_name))
        if i == len(path_ids) - 1:
            badge = (badge + " " if badge else "") + '<span style="font-size:.75rem;background:#eef2ff;color:#1a2a6c;padding:3px 8px;border-radius:999px;font-weight:700">Destination</span>'
        rows.append(
            f'<div style="display:flex;gap:10px;align-items:flex-start;position:relative;padding:8px 0">'
            f'<span style="margin-top:4px;width:11px;height:11px;border-radius:50%;background:{line_color};display:inline-block;flex-shrink:0"></span>'
            f'<div style="display:flex;flex-direction:column;gap:4px"><span style="font-weight:600">{name}</span>'
            f'<span style="font-size:.78rem;color:var(--muted)">{line_name}</span>{badge}</div></div>'
        )

    if interchanges:
        igrid_rows = "".join(
            f"<tr><td style='padding:8px;border:1px solid #e6e8ef'>{s}</td><td style='padding:8px;border:1px solid #e6e8ef'>{a}</td><td style='padding:8px;border:1px solid #e6e8ef'>{b}</td></tr>"
            for s, a, b in interchanges
        )
    else:
        igrid_rows = "<tr><td colspan='3' style='padding:8px;border:1px solid #e6e8ef'>Direct route (no line change)</td></tr>"

    return (
        f"{SEQ_START}\n"
        f'<section class="mgi-route-sequence-box" style="margin-top:16px;background:{CARD};border:1px solid #e6e8ef;border-radius:12px;padding:16px">'
        f'<div style="font-size:1rem;font-weight:800;color:{BRAND};margin-bottom:10px">Full Route Station Sequence &amp; Interchange Grid</div>'
        f'<div style="font-size:.84rem;color:var(--muted);margin-bottom:12px">Complete stop-by-stop sequence for this route.</div>'
        f'<div style="position:relative;padding-left:14px;border-left:3px solid {BRAND};margin-bottom:14px">{"".join(rows)}</div>'
        f'<div style="font-size:.88rem;font-weight:700;margin:8px 0">Interchange Grid</div>'
        f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;background:{CARD};font-size:.82rem">'
        f"<thead><tr style='background:#f6f8ff'><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>Station</th><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>From</th><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>To</th></tr></thead>"
        f"<tbody>{igrid_rows}</tbody></table></div></section>\n"
        f"{SEQ_END}"
    )


def pretty_slug_name(slug: str) -> str:
    special = {"igi": "IGI", "gtb": "GTB", "ina": "INA", "ii": "II", "iii": "III"}
    out = []
    for p in slug.split("-"):
        out.append(special.get(p, p.capitalize()))
    return " ".join(out)


def build_fallback_station_sequence_html(origin_slug: str, dest_slug: str, interchange_hint: str) -> str:
    origin = pretty_slug_name(origin_slug)
    dest = pretty_slug_name(dest_slug)
    igrid = "<tr><td colspan='3' style='padding:8px;border:1px solid #e6e8ef'>Interchange detail unavailable in route metadata.</td></tr>"
    if re.search(r"direct|no interchange|0", interchange_hint, re.I):
        igrid = "<tr><td colspan='3' style='padding:8px;border:1px solid #e6e8ef'>Direct route (no line change)</td></tr>"
    return (
        f"{SEQ_START}\n"
        f'<section class="mgi-route-sequence-box" style="margin-top:16px;background:{CARD};border:1px solid #e6e8ef;border-radius:12px;padding:16px">'
        f'<div style="font-size:1rem;font-weight:800;color:{BRAND};margin-bottom:10px">Full Route Station Sequence &amp; Interchange Grid</div>'
        f'<div style="font-size:.84rem;color:var(--muted);margin-bottom:12px">Route metadata is partially available; use the planner below for exact intermediate stops.</div>'
        f'<div style="position:relative;padding-left:14px;border-left:3px solid {BRAND};margin-bottom:14px">'
        f'<div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0"><span style="margin-top:4px;width:11px;height:11px;border-radius:50%;background:{BRAND};display:inline-block;flex-shrink:0"></span><div style="font-weight:600">{origin}</div></div>'
        f'<div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0"><span style="margin-top:4px;width:11px;height:11px;border-radius:50%;background:{BRAND};display:inline-block;flex-shrink:0"></span><div style="font-weight:600">{dest} <span style="font-size:.75rem;background:#eef2ff;color:#1a2a6c;padding:3px 8px;border-radius:999px;font-weight:700">Destination</span></div></div>'
        f"</div>"
        f'<div style="font-size:.88rem;font-weight:700;margin:8px 0">Interchange Grid</div>'
        f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;background:{CARD};font-size:.82rem">'
        f"<thead><tr style='background:#f6f8ff'><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>Station</th><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>From</th><th style='padding:8px;border:1px solid #e6e8ef;text-align:left'>To</th></tr></thead>"
        f"<tbody>{igrid}</tbody></table></div></section>\n"
        f"{SEQ_END}"
    )


def parse_metro_time_minutes(html: str) -> int | None:
    m = re.search(r"Travel Time</div>\s*<div[^>]*>([^<]+)</div>", html, flags=re.I | re.S)
    if not m:
        m = re.search(r"estimated travel time[^\d]*(\d+)\s*mins?", html, flags=re.I)
    if not m:
        return None
    mm = re.search(r"(\d+)", m.group(1))
    return int(mm.group(1)) if mm else None


def compute_route_stats(path_ids: list[str], graph: dict[str, list[tuple[str, float, bool]]], by_id: dict) -> tuple[float, int]:
    edge_map: dict[tuple[str, str], tuple[float, bool]] = {}
    for a, edges in graph.items():
        for b, d, is_xfer in edges:
            edge_map[(a, b)] = (d, is_xfer)
    metro_km = 0.0
    interchanges = 0
    for i in range(1, len(path_ids)):
        a, b = path_ids[i - 1], path_ids[i]
        d, is_xfer = edge_map.get((a, b), (0.0, False))
        if not is_xfer:
            metro_km += d
        if by_id[a]["station_name"].lower() == by_id[b]["station_name"].lower() and by_id[a].get("line_id") != by_id[b].get("line_id"):
            interchanges += 1
    return metro_km, interchanges


def build_road_compare_html(metro_km: float, metro_time_mins: int, interchanges: int) -> str:
    road_km = round(metro_km * (1.22 + min(0.14, interchanges * 0.05)), 1)
    road_time_peak = int(round((road_km / 17) * 60 + 8))
    road_time_offpeak = int(round((road_km / 25) * 60 + 5))
    time_saved = max(0, road_time_peak - metro_time_mins)
    return (
        f"{ROAD_START}\n"
        f'<section class="mgi-road-vs-metro" style="margin-top:22px;margin-bottom:10px;background:{CARD};border:1px solid #e7e9f2;border-left:4px solid {WARN};border-radius:12px;padding:16px">'
        f'<div style="font-size:1rem;font-weight:800;color:{BRAND};margin-bottom:8px">Road Travel vs Metro Time &amp; Distance Comparison</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px">'
        f'<div style="background:#f8f9ff;border:1px solid #e8ebfb;border-radius:10px;padding:12px"><div style="font-size:.76rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">Delhi Metro</div><div style="font-weight:800;font-size:1.05rem;color:{BRAND}">{metro_km:.1f} km · {metro_time_mins} mins</div></div>'
        f'<div style="background:#fff7f4;border:1px solid #f3d8cf;border-radius:10px;padding:12px"><div style="font-size:.76rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">By Road / Cab (est.)</div><div style="font-weight:800;font-size:1.05rem;color:{WARN}">{road_km:.1f} km · {road_time_peak} mins peak</div><div style="font-size:.78rem;color:var(--muted)">~{road_time_offpeak} mins off-peak</div></div>'
        f"</div>"
        f'<div style="margin-top:10px;font-size:.83rem;color:var(--muted)">Typical peak-time metro saving: <strong style="color:{BRAND}">~{time_saved} mins</strong>. Road estimates are dynamically derived from route-network distance and interchange complexity.</div>'
        f"</section>\n"
        f"{ROAD_END}"
    )


def parse_interchange_hint(html: str) -> str:
    m = re.search(r"Interchange</div>\s*<div[^>]*>([^<]+)</div>", html, flags=re.I | re.S)
    return m.group(1).strip() if m else ""


def inject_blocks(html: str, seq_html: str, road_html: str) -> str:
    html = clean_existing_blocks(html)

    if "<div><strong>Journey:</strong>" in html:
        html = html.replace("<div><strong>Journey:</strong>", seq_html + "\n<div><strong>Journey:</strong>", 1)
    elif '<div class="route-seo-box" style="margin-top:16px' in html:
        html = html.replace('<div class="route-seo-box" style="margin-top:16px', seq_html + '\n\n<div class="route-seo-box" style="margin-top:16px', 1)

    if '<section class="mgi-faq-wrap"' in html:
        html = html.replace('<section class="mgi-faq-wrap"', road_html + '\n\n<section class="mgi-faq-wrap"', 1)
    elif '<section id="global-search-section"' in html:
        html = html.replace('<section id="global-search-section"', road_html + '\n\n<section id="global-search-section"', 1)
    return html


def main() -> None:
    data, by_id, slug_to_ids, line_meta = load_data()
    graph = build_graph(data, by_id)
    files = sorted(ROUTES_DIR.glob("*.html"))
    updated = 0
    skipped = 0
    for f in files:
        path_ids = route_path_for_file(f.stem, graph, slug_to_ids)
        html = f.read_text(encoding="utf-8")
        metro_time_mins = parse_metro_time_minutes(html)
        interchange_hint = parse_interchange_hint(html)
        if len(path_ids) >= 2:
            metro_km, interchanges = compute_route_stats(path_ids, graph, by_id)
            if metro_time_mins is None:
                metro_time_mins = int(round((metro_km / 32) * 60 + interchanges * 4))
            seq_html = build_station_sequence_html(path_ids, by_id, line_meta)
        else:
            parts = f.stem.split("-to-")
            origin_slug = parts[0] if parts else f.stem
            dest_slug = "-to-".join(parts[1:]) if len(parts) > 1 else f.stem
            if metro_time_mins is None:
                metro_time_mins = 30
            interchanges = 0 if re.search(r"direct|no interchange|0", interchange_hint, re.I) else 1
            metro_km = max(3.0, round(metro_time_mins * 0.55, 1))
            seq_html = build_fallback_station_sequence_html(origin_slug, dest_slug, interchange_hint)
            skipped += 1
        road_html = build_road_compare_html(metro_km, metro_time_mins, interchanges)
        new_html = inject_blocks(html, seq_html, road_html)
        if new_html != html:
            f.write_text(new_html, encoding="utf-8")
            updated += 1
    print(f"Updated {updated} files. Skipped {skipped} files.")


if __name__ == "__main__":
    main()
