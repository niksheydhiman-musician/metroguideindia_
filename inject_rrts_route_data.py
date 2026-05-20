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
PARKING_BLOG_URL = "https://metroguideindia.com/blog/rrts-parking-charges-monthly-pass-station-locations.html"

BLOCK_START = "<!-- RRTS_ROUTE_DATA_INJECT_START -->"
BLOCK_END = "<!-- RRTS_ROUTE_DATA_INJECT_END -->"
SUMMARY_DETAILS_START = "<!-- RRTS_ROUTE_SUMMARY_DETAILS_START -->"
SUMMARY_DETAILS_END = "<!-- RRTS_ROUTE_SUMMARY_DETAILS_END -->"


@dataclass
class StationMeta:
    station_name: str
    service_type: str
    operational_timings: dict[str, Any]
    exit_gates: Any
    parking_profile: dict[str, Any]
    special_facilities: dict[str, Any]
    parking_tariff_summary: str = ""


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
        clean_label = re.sub(r"^(first|last)(?:_train)?_?", "", key_l).strip("_")
        label = clean_label.replace("_", " ").strip().title()
        pair = f"{label}: {value}" if label else value
        if "first" in key_l:
            first_candidates.append(pair)
        elif "last" in key_l:
            last_candidates.append(pair)

    first = " | ".join(first_candidates) if first_candidates else "Not listed"
    last = " | ".join(last_candidates) if last_candidates else "Not listed"
    return first, last


def normalize_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def summarize_parking(origin_station: StationMeta | None) -> str:
    if not origin_station or not isinstance(origin_station.parking_profile, dict) or not origin_station.parking_profile:
        return "Not listed"
    profile = origin_station.parking_profile
    parts: list[str] = []
    available = profile.get("parking_available")
    if isinstance(available, bool):
        parts.append("Available" if available else "Not available")
    zone = profile.get("zone")
    if zone:
        parts.append(f"Zone: {zone}")
    live = profile.get("live_capacity")
    if isinstance(live, dict) and live:
        caps = []
        for key, value in live.items():
            if value in (None, "", [], {}):
                continue
            caps.append(f"{normalize_label(str(key))} {value}")
        if caps:
            parts.append("Capacity: " + ", ".join(caps))
    if origin_station.parking_tariff_summary:
        parts.append(f"Tariff: {origin_station.parking_tariff_summary}")
    return " | ".join(parts) if parts else "Not listed"


def list_facilities(origin_station: StationMeta | None) -> list[str]:
    if not origin_station or not isinstance(origin_station.special_facilities, dict) or not origin_station.special_facilities:
        return []
    details: list[str] = []
    for key, value in origin_station.special_facilities.items():
        label = normalize_label(str(key))
        if value is True:
            details.append(label)
        elif value in (False, None, "", [], {}):
            continue
        elif isinstance(value, list):
            joined = ", ".join(str(v) for v in value if v not in (None, "", [], {}))
            if joined:
                details.append(f"{label}: {joined}")
        else:
            details.append(f"{label}: {value}")
    return details


def summarize_facilities(origin_station: StationMeta | None, limit: int | None = None) -> str:
    facilities = list_facilities(origin_station)
    if not facilities:
        return "Not listed"
    if not limit or len(facilities) <= limit:
        return ", ".join(facilities)
    return ", ".join(facilities[:limit]) + f", +{len(facilities) - limit} more"


def get_station_route_details(
    html: str, route: dict[str, Any], station_map: dict[str, StationMeta]
) -> tuple[str, str, list[tuple[str, str, str]], StationMeta | None]:
    fallback_stations = extract_step_stations(html)
    origin_name = fallback_stations[0] if fallback_stations else ""
    origin_meta = station_map.get(normalize_slug(origin_name)) if origin_name else None

    first_train, last_train = parse_first_last_train(
        route.get("timings") if isinstance(route.get("timings"), dict) else (origin_meta.operational_timings if origin_meta else {})
    )
    exits = normalize_exit_items(route, origin_meta)
    return first_train, last_train, exits, origin_meta


def summarize_exit_blueprints(exits: list[tuple[str, str, str]], limit: int | None = None) -> str:
    if not exits:
        return "Not listed"
    clipped = exits[:limit] if limit else exits
    text = "; ".join(f"{st} — {gate}: {landmark}" for st, gate, landmark in clipped)
    if limit and len(exits) > limit:
        text += f"; +{len(exits) - limit} more"
    return text


def strip_existing_summary_details(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(SUMMARY_DETAILS_START)}.*?{re.escape(SUMMARY_DETAILS_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def build_route_summary_details_html(
    first_train: str, last_train: str, exit_summary: str, parking_summary: str, facilities_summary: str
) -> str:
    parking_text = escape(parking_summary)
    parking_link = (
        f'<a href="{escape(PARKING_BLOG_URL)}" target="_blank" rel="noopener noreferrer" '
        'style="color:#B42318;font-weight:700;text-decoration:none">Read parking charges, passes & station locations ↗</a>'
    )
    return f"""
{SUMMARY_DETAILS_START}
<div class="rc-route-meta" style="margin-top:12px;padding:12px 14px;border:1px solid var(--border2,#e2e8f0);border-radius:14px;background:linear-gradient(180deg,#fff,#fcfcfd);box-shadow:0 6px 24px rgba(2,6,23,.03);display:grid;gap:0">
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">First Train:</strong> {escape(first_train)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Last Train:</strong> {escape(last_train)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Exit Gate Blueprint:</strong> {escape(exit_summary)}</div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5;border-bottom:1px dashed var(--border2,#e2e8f0)"><strong style="font-size:1.02rem">Parking:</strong> {parking_text}<br><span style="display:inline-block;margin-top:6px">{parking_link}</span></div>
  <div style="padding:10px 2px;font-size:.95rem;line-height:1.5"><strong style="font-size:1.02rem">Facilities:</strong> {escape(facilities_summary)}</div>
</div>
{SUMMARY_DETAILS_END}
""".strip()


def inject_route_summary_details(
    html: str, first_train: str, last_train: str, exit_summary: str, parking_summary: str, facilities_summary: str
) -> str:
    clean = strip_existing_summary_details(html)
    details = build_route_summary_details_html(first_train, last_train, exit_summary, parking_summary, facilities_summary)

    if '<div class="rc-steps">' in clean and re.search(r'<div class="route-seo-box"(?:\s|>)', clean):
        return re.sub(
            r'(\s*<div class="route-seo-box"(?:\s|>))',
            "\n" + details + r"\1",
            clean,
            count=1,
            flags=re.S,
        )

    if '<div class="rc-steps">' in clean and re.search(r'<div class="quick-facts"(?:\s|>)', clean):
        return re.sub(
            r'(\s*<div class="quick-facts"(?:\s|>))',
            "\n" + details + r"\1",
            clean,
            count=1,
            flags=re.S,
        )

    fallback_pattern = r'(<div class="rc-summary">.*?</div>\s*)(<div class="rc-steps">)'
    fallback_replacement = r"\1\n" + details + r"\n      \2"
    return re.sub(fallback_pattern, fallback_replacement, clean, count=1, flags=re.S)


def format_inr(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return f"₹{int(value)}"
    return f"₹{value:.2f}".rstrip("0").rstrip(".")


def summarize_zone_tariff(zone_name: str, zone_data: dict[str, Any]) -> str:
    def lane_values(four_val: str, two_val: str) -> str:
        parts: list[str] = []
        if four_val:
            parts.append(f"{four_val} (4W)")
        if two_val:
            parts.append(f"{two_val} (2W)")
        return ", ".join(parts)

    zone = zone_name.lower()
    if "delhi" in zone:
        four_daily = format_inr(zone_data.get("four_wheeler_daily_inr"))
        two_daily = format_inr(zone_data.get("two_wheeler_daily_inr"))
        four_monthly = format_inr(zone_data.get("four_wheeler_monthly_pass_inr"))
        two_monthly = format_inr(zone_data.get("two_wheeler_monthly_pass_inr"))
        parts = []
        daily = lane_values(four_daily, two_daily)
        monthly = lane_values(four_monthly, two_monthly)
        if daily:
            parts.append(f"Daily {daily}")
        if monthly:
            parts.append(f"Monthly {monthly}")
        return "; ".join(p for p in parts if p).strip()

    if "uttar pradesh" in zone:
        four = zone_data.get("four_wheelers") if isinstance(zone_data.get("four_wheelers"), dict) else {}
        two = zone_data.get("two_wheelers") if isinstance(zone_data.get("two_wheelers"), dict) else {}
        up_to_6h_four = format_inr(four.get("up_to_6_hours_inr"))
        up_to_6h_two = format_inr(two.get("up_to_6_hours_inr"))
        up_to_12h_four = format_inr(four.get("up_to_12_hours_inr"))
        up_to_12h_two = format_inr(two.get("up_to_12_hours_inr"))
        monthly_four = format_inr(four.get("monthly_pass_no_time_limit_inr"))
        monthly_two = format_inr(two.get("monthly_pass_no_time_limit_inr"))
        parts = []
        upto6h = lane_values(up_to_6h_four, up_to_6h_two)
        upto12h = lane_values(up_to_12h_four, up_to_12h_two)
        monthly = lane_values(monthly_four, monthly_two)
        if upto6h:
            parts.append(f"Up to 6h {upto6h}")
        if upto12h:
            parts.append(f"Up to 12h {upto12h}")
        if monthly:
            parts.append(f"Monthly {monthly}")
        return "; ".join(p for p in parts if p).strip()

    return ""


def extract_object_for_key(raw: str, key: str) -> dict[str, Any]:
    key_pat = re.compile(rf'"{re.escape(key)}"\s*:\s*\{{', flags=re.I)
    m = key_pat.search(raw)
    if not m:
        return {}
    start = raw.find("{", m.start())
    if start == -1:
        return {}
    depth = 0
    end = None
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return {}
    chunk = raw[start : end + 1]
    chunk = re.sub(r":\s*,", ": [],", chunk)
    try:
        parsed = json.loads(chunk)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
    parking_tariff_by_zone: dict[str, str] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        tariff_structure = (
            data.get("standard_parking_tariff_structure")
            if isinstance(data.get("standard_parking_tariff_structure"), dict)
            else {}
        )
        if tariff_structure:
            delhi_zone = (
                tariff_structure.get("delhi_stations_zone")
                if isinstance(tariff_structure.get("delhi_stations_zone"), dict)
                else {}
            )
            up_zone = (
                tariff_structure.get("uttar_pradesh_stations_zone")
                if isinstance(tariff_structure.get("uttar_pradesh_stations_zone"), dict)
                else {}
            )
            if delhi_zone:
                parking_tariff_by_zone["delhi"] = summarize_zone_tariff("delhi", delhi_zone)
            if up_zone:
                parking_tariff_by_zone["uttar pradesh"] = summarize_zone_tariff("uttar pradesh", up_zone)
    else:
        delhi_zone = extract_object_for_key(raw, "delhi_stations_zone")
        up_zone = extract_object_for_key(raw, "uttar_pradesh_stations_zone")
        if delhi_zone:
            parking_tariff_by_zone["delhi"] = summarize_zone_tariff("delhi", delhi_zone)
        if up_zone:
            parking_tariff_by_zone["uttar pradesh"] = summarize_zone_tariff("uttar pradesh", up_zone)

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
                parking_profile = st.get("parking_profile") if isinstance(st.get("parking_profile"), dict) else {}
                zone_name = str(parking_profile.get("zone") or "").strip().lower()
                station_map[normalize_slug(name)] = StationMeta(
                    station_name=name,
                    service_type=normalize_service_type(st.get("system_type")),
                    operational_timings=st.get("operational_timings")
                    if isinstance(st.get("operational_timings"), dict)
                    else {},
                    exit_gates=st.get("exit_gates"),
                    parking_profile=parking_profile,
                    special_facilities=st.get("special_facilities")
                    if isinstance(st.get("special_facilities"), dict)
                    else {},
                    parking_tariff_summary=parking_tariff_by_zone.get(zone_name, ""),
                )

    if not station_map:
        for st in extract_station_objects_from_malformed_json(raw):
            name = (st.get("station_name") or "").strip()
            if not name:
                continue
            parking_profile = st.get("parking_profile") if isinstance(st.get("parking_profile"), dict) else {}
            zone_name = str(parking_profile.get("zone") or "").strip().lower()
            station_map[normalize_slug(name)] = StationMeta(
                station_name=name,
                service_type=normalize_service_type(st.get("system_type")),
                operational_timings=st.get("operational_timings")
                if isinstance(st.get("operational_timings"), dict)
                else {},
                exit_gates=st.get("exit_gates"),
                parking_profile=parking_profile,
                special_facilities=st.get("special_facilities")
                if isinstance(st.get("special_facilities"), dict)
                else {},
                parking_tariff_summary=parking_tariff_by_zone.get(zone_name, ""),
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
    first_train, last_train, exits, origin_meta = get_station_route_details(html, route, station_map)
    parking_summary = summarize_parking(origin_meta)
    facilities_summary = summarize_facilities(origin_meta)

    timeline = normalize_timeline(route, fallback_stations, station_map)

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

  <div class="rrts-card" style="margin-bottom:12px">
    <h2 class="rrts-title">Origin Station Amenities</h2>
    <div class="rrts-grid">
      <div><div class="rrts-meta-key">Parking</div><div class="rrts-meta-val">{escape(parking_summary)}</div></div>
      <div><div class="rrts-meta-key">Facilities</div><div class="rrts-meta-val">{escape(facilities_summary)}</div></div>
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

        first_train, last_train, exits, origin_meta = get_station_route_details(original, route_data, station_map)
        exit_summary = summarize_exit_blueprints(exits)
        parking_summary = summarize_parking(origin_meta)
        facilities_summary = summarize_facilities(origin_meta)

        result = strip_existing_block(original)
        result = inject_route_summary_details(
            result, first_train, last_train, exit_summary, parking_summary, facilities_summary
        )

        if write and result != original:
            path.write_text(result, encoding="utf-8")
            updated += 1

    print(f"[inject] pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
