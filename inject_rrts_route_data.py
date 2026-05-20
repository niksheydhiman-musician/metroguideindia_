#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "routes"
ROUTE_JSON = REPO_ROOT / "data" / "rrts-routes.json"

BLOCK_START = "<!-- RRTS_ROUTE_DATA_INJECT_START -->"
BLOCK_END = "<!-- RRTS_ROUTE_DATA_INJECT_END -->"


@dataclass
class StationMeta:
    station_name: str
    service_type: str
    operational_timings: dict[str, Any]
    exit_gates: Any


def normalize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def slug_to_path(slug: str) -> Path:
    return ROUTES_DIR / f"{slug}.html"


def normalize_service_type(system_type: str | None) -> str:
    txt = (system_type or "").lower()
    if "dual" in txt:
        return "Dual-Service"
    if "metro" in txt and "namo bharat" not in txt and "rrts" not in txt:
        return "Metro"
    if "metro" in txt and "rrts" in txt:
        return "Dual-Service"
    return "RRTS"


def strip_existing_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def extract_step_stations(html: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", s).strip()
        for s in re.findall(r'<div class="step-name">(.*?)</div>', html, flags=re.S)
    ]


def parse_sub_line(html: str) -> dict[str, str]:
    m = re.search(r'<p class="rp-sub">(.*?)</p>', html, flags=re.S)
    if not m:
        return {}
    sub = re.sub(r"<.*?>", "", m.group(1))
    sub = re.sub(r"\s+", " ", sub).strip()

    fare = ""
    est = ""
    fare_match = re.search(r"₹\s*([0-9,]+)", sub)
    if fare_match:
        fare = f"₹{fare_match.group(1)}"
    est_match = re.search(r"~\s*([0-9]+\s*min)", sub, flags=re.I)
    if est_match:
        est = est_match.group(1).replace("  ", " ").strip()
    return {"standard_fare": fare, "estimated_time": est}


def parse_interchanges(html: str) -> str:
    patterns = [
        r"Interchanges:</strong>\s*([^<.]+)",
        r"Interchanges:\s*<strong>([^<]+)</strong>",
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return "Not listed"


def parse_first_last_train(timings: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(timings, dict) or not timings:
        return "Not listed", "Not listed"

    first_candidates: list[str] = []
    last_candidates: list[str] = []
    for key, value in timings.items():
        if not isinstance(value, str):
            continue
        key_l = key.lower()
        label = key.replace("_", " ").title()
        pair = f"{label}: {value}"
        if "first" in key_l:
            first_candidates.append(pair)
        elif "last" in key_l:
            last_candidates.append(pair)

    first = " | ".join(first_candidates) if first_candidates else "Not listed"
    last = " | ".join(last_candidates) if last_candidates else "Not listed"
    return first, last


def extract_station_objects_from_malformed_json(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    i = 0
    while True:
        idx = raw.find('"station_code"', i)
        if idx == -1:
            break
        start = raw.rfind("{", 0, idx)
        if start == -1:
            i = idx + 1
            continue

        depth = 0
        end = None
        for j in range(start, len(raw)):
            ch = raw[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            break

        chunk = raw[start : end + 1]
        chunk = chunk.replace('"exit_gates":,', '"exit_gates": [] ,')
        chunk = re.sub(r":\s*,", ": [],", chunk)
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict) and obj.get("station_name"):
                items.append(obj)
        except json.JSONDecodeError:
            pass
        i = end + 1
    return items


def load_route_payload(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, StationMeta]]:
    raw = path.read_text(encoding="utf-8")

    route_map: dict[str, dict[str, Any]] = {}
    station_map: dict[str, StationMeta] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        if isinstance(data.get("routes"), dict):
            for k, v in data["routes"].items():
                if isinstance(v, dict):
                    route_map[normalize_slug(k)] = v
        for k, v in data.items():
            if "-to-" in k and isinstance(v, dict):
                route_map[normalize_slug(k)] = v
        stations = data.get("stations")
        if isinstance(stations, list):
            for st in stations:
                if not isinstance(st, dict):
                    continue
                name = (st.get("station_name") or "").strip()
                if not name:
                    continue
                station_map[normalize_slug(name)] = StationMeta(
                    station_name=name,
                    service_type=normalize_service_type(st.get("system_type")),
                    operational_timings=st.get("operational_timings")
                    if isinstance(st.get("operational_timings"), dict)
                    else {},
                    exit_gates=st.get("exit_gates"),
                )

    if not station_map:
        for st in extract_station_objects_from_malformed_json(raw):
            name = (st.get("station_name") or "").strip()
            if not name:
                continue
            station_map[normalize_slug(name)] = StationMeta(
                station_name=name,
                service_type=normalize_service_type(st.get("system_type")),
                operational_timings=st.get("operational_timings")
                if isinstance(st.get("operational_timings"), dict)
                else {},
                exit_gates=st.get("exit_gates"),
            )

    return route_map, station_map


def normalize_timeline(route: dict[str, Any], fallback_stations: list[str], station_map: dict[str, StationMeta]) -> list[dict[str, str]]:
    timeline = route.get("stations_timeline")
    normalized: list[dict[str, str]] = []

    if isinstance(timeline, list) and timeline:
        for node in timeline:
            if isinstance(node, str):
                name = node.strip()
                meta = station_map.get(normalize_slug(name))
                item = {
                    "station_name": name,
                    "service_type": (route.get("service_type") or (meta.service_type if meta else "RRTS")),
                    "interchange_info": "",
                }
                normalized.append(item)
                continue
            if isinstance(node, dict):
                name = str(node.get("station_name") or node.get("station") or node.get("name") or "").strip()
                if not name:
                    continue
                meta = station_map.get(normalize_slug(name))
                item = {
                    "station_name": name,
                    "service_type": str(node.get("service_type") or (meta.service_type if meta else route.get("service_type") or "RRTS")),
                    "interchange_info": str(node.get("interchange_info") or "").strip(),
                }
                normalized.append(item)

    if normalized:
        return normalized

    for st in fallback_stations:
        meta = station_map.get(normalize_slug(st))
        interchange = ""
        if meta and meta.service_type == "Dual-Service":
            interchange = "Cross-network transfer available"
        normalized.append(
            {
                "station_name": st,
                "service_type": meta.service_type if meta else "RRTS",
                "interchange_info": interchange,
            }
        )
    return normalized


def normalize_exit_items(route: dict[str, Any], origin_station: StationMeta | None) -> list[tuple[str, str, str]]:
    gates = route.get("exit_gates")
    if gates in (None, "", []):
        gates = origin_station.exit_gates if origin_station else None

    entries: list[tuple[str, str, str]] = []

    if isinstance(gates, dict):
        for station_name, values in gates.items():
            if isinstance(values, list):
                for idx, v in enumerate(values, 1):
                    if isinstance(v, dict):
                        gate = str(v.get("gate") or v.get("gate_no") or f"Gate {idx}")
                        landmark = str(v.get("landmark") or v.get("location") or v.get("towards") or "Not listed")
                    else:
                        gate = f"Gate {idx}"
                        landmark = str(v)
                    entries.append((str(station_name), gate, landmark))
            elif isinstance(values, dict):
                for gate, landmark in values.items():
                    entries.append((str(station_name), str(gate), str(landmark)))
            else:
                entries.append((str(station_name), "Gate", str(values)))
        return entries

    if isinstance(gates, list):
        for idx, item in enumerate(gates, 1):
            if isinstance(item, dict):
                station_name = str(item.get("station_name") or item.get("station") or (origin_station.station_name if origin_station else "Route"))
                gate = str(item.get("gate") or item.get("gate_no") or f"Gate {idx}")
                landmark = str(item.get("landmark") or item.get("location") or item.get("towards") or "Not listed")
            else:
                station_name = origin_station.station_name if origin_station else "Route"
                gate = f"Gate {idx}"
                landmark = str(item)
            entries.append((station_name, gate, landmark))

    return entries


def build_component_html(slug: str, html: str, route: dict[str, Any], station_map: dict[str, StationMeta]) -> str:
    fallback = parse_sub_line(html)
    fallback_stations = extract_step_stations(html)
    origin_name = fallback_stations[0] if fallback_stations else ""
    origin_meta = station_map.get(normalize_slug(origin_name)) if origin_name else None

    est_time = str(route.get("estimated_time") or fallback.get("estimated_time") or "Not listed")
    interchanges = str(route.get("interchanges") or parse_interchanges(html) or "Not listed")
    std_fare = str(route.get("standard_fare") or fallback.get("standard_fare") or "Not listed")
    smart_card = str(route.get("smart_card_fare") or route.get("premium_fare") or "Not listed")

    total = route.get("total_stations")
    if total in (None, ""):
        total = len(fallback_stations) if fallback_stations else "Not listed"

    first_train, last_train = parse_first_last_train(
        route.get("timings") if isinstance(route.get("timings"), dict) else (origin_meta.operational_timings if origin_meta else {})
    )

    timeline = normalize_timeline(route, fallback_stations, station_map)
    exits = normalize_exit_items(route, origin_meta)

    timeline_html = []
    for idx, node in enumerate(timeline, 1):
        label = ""
        info = node.get("interchange_info", "").strip()
        if info:
            label = f'<div class="rrts-chip rrts-chip-int">Transfer: {escape(info)}</div>'
        timeline_html.append(
            """
            <li class="rrts-stop">
              <span class="rrts-pill">{idx}</span>
              <div class="rrts-stop-body">
                <div class="rrts-stop-name">{name}</div>
                <div class="rrts-chip-row">
                  <div class="rrts-chip">Service: {service}</div>
                  {label}
                </div>
              </div>
            </li>
            """.format(
                idx=idx,
                name=escape(node.get("station_name", "")),
                service=escape(node.get("service_type", "RRTS")),
                label=label,
            )
        )

    if exits:
        exit_items = "".join(
            f"<li><strong>{escape(st)}</strong> — {escape(gate)}: {escape(landmark)}</li>"
            for st, gate, landmark in exits
        )
    else:
        exit_items = "<li>Exit gate landmarks are currently not published for this route.</li>"

    return f"""
{BLOCK_START}
<section class="rrts-route-injected" data-route="{escape(slug)}">
  <style>
    .rrts-route-injected{{margin:16px 0 24px;padding:14px;border:1px solid var(--border2,#e2e8f0);border-radius:12px;background:var(--surface2,#fff)}}
    .rrts-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
    .rrts-card{{border:1px solid var(--border2,#e2e8f0);border-radius:10px;padding:10px;background:#fff}}
    .rrts-title{{font-size:1rem;font-weight:700;margin:0 0 10px}}
    .rrts-meta-key{{font-size:.72rem;color:var(--muted,#64748b);text-transform:uppercase;letter-spacing:.04em}}
    .rrts-meta-val{{font-size:.96rem;font-weight:600}}
    .rrts-timeline{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}}
    .rrts-stop{{display:flex;gap:10px;align-items:flex-start}}
    .rrts-pill{{min-width:26px;height:26px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#C0392B;color:#fff;font-size:.78rem;font-weight:700}}
    .rrts-stop-body{{border:1px solid var(--border2,#e2e8f0);border-radius:9px;padding:8px 10px;flex:1}}
    .rrts-stop-name{{font-weight:700}}
    .rrts-chip-row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}}
    .rrts-chip{{font-size:.72rem;border:1px solid #d1d5db;border-radius:999px;padding:2px 8px;background:#f8fafc}}
    .rrts-chip-int{{border-color:#f59e0b;background:#fffbeb;color:#92400e}}
    .rrts-exits{{margin:0;padding-left:18px;display:grid;gap:6px}}
    @media (max-width:700px){{.rrts-grid{{grid-template-columns:1fr}}}}
  </style>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Route Summary Widget</h2>
    <div class="rrts-grid">
      <div><div class="rrts-meta-key">Estimated Time</div><div class="rrts-meta-val">{escape(est_time)}</div></div>
      <div><div class="rrts-meta-key">Interchanges</div><div class="rrts-meta-val">{escape(interchanges)}</div></div>
      <div><div class="rrts-meta-key">Standard Fare</div><div class="rrts-meta-val">{escape(std_fare)}</div></div>
      <div><div class="rrts-meta-key">Smart Card Fare</div><div class="rrts-meta-val">{escape(smart_card)}</div></div>
      <div><div class="rrts-meta-key">Total Stations</div><div class="rrts-meta-val">{escape(str(total))}</div></div>
    </div>
  </div>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Live Route Timeline</h2>
    <ol class="rrts-timeline">
      {''.join(timeline_html)}
    </ol>
  </div>

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Terminal Timings</h2>
    <div class="rrts-grid">
      <div><div class="rrts-meta-key">First Train (Origin)</div><div class="rrts-meta-val">{escape(first_train)}</div></div>
      <div><div class="rrts-meta-key">Last Train (Origin)</div><div class="rrts-meta-val">{escape(last_train)}</div></div>
    </div>
  </div>

  <div class="rrts-card">
    <h2 class="rrts-title">Exit Gate Blueprint</h2>
    <ul class="rrts-exits">{exit_items}</ul>
  </div>
</section>
{BLOCK_END}
""".strip()


def inject_in_main_block(html: str, block: str) -> str:
    clean = strip_existing_block(html)

    rp_sub = re.search(r'(<p class="rp-sub"[^>]*>.*?</p>)', clean, flags=re.S)
    if rp_sub:
        insert_at = rp_sub.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    wrap_open = re.search(r'(<div class="wrap"[^>]*>)', clean)
    if wrap_open:
        insert_at = wrap_open.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    main_open = re.search(r'(<main[^>]*>)', clean)
    if main_open:
        insert_at = main_open.end()
        prefix = clean[:insert_at].rstrip()
        suffix = clean[insert_at:].lstrip("\n")
        return prefix + "\n\n" + block + "\n\n" + suffix

    return clean + "\n" + block + "\n"


def fallback_route_data_from_html(html: str) -> dict[str, Any]:
    sub = parse_sub_line(html)
    return {
        "estimated_time": sub.get("estimated_time", "Not listed"),
        "standard_fare": sub.get("standard_fare", "Not listed"),
        "interchanges": parse_interchanges(html),
        "total_stations": len(extract_step_stations(html)),
    }


def iter_route_pages() -> list[Path]:
    return sorted(ROUTES_DIR.glob("*.html"))


def run(write: bool = True) -> int:
    route_map, station_map = load_route_payload(ROUTE_JSON)

    route_pages = iter_route_pages()
    updated = 0

    print(f"[inject] route pages found: {len(route_pages)}")
    print(f"[inject] route keys found in JSON: {len(route_map)}")
    print(f"[inject] station records parsed: {len(station_map)}")

    for path in route_pages:
        slug = path.stem
        original = path.read_text(encoding="utf-8")
        route_data = route_map.get(slug) or fallback_route_data_from_html(original)

        block = build_component_html(
            slug=slug,
            html=original,
            route=route_data,
            station_map=station_map,
        )
        result = inject_in_main_block(original, block)

        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[inject] pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
