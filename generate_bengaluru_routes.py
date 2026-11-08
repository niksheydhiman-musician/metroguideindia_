#!/usr/bin/env python3
"""Generate Bengaluru route pages from the master data and benchmark styling."""
from __future__ import annotations

import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
ROUTES = ROOT / "bengaluru-metro/routes"
DATA = json.loads((ROOT / "data/bengaluru.json").read_text(encoding="utf-8"))
STATIONS = {s["id"]: s for s in DATA["stations"]}
LINES = {line["lineId"]: line for line in DATA["operationalLines"]}
HUBS = {hub["stationId"]: hub for hub in DATA["interchangeHubs"]}
ALIASES = DATA["stationMappings"] | {
    "city-railway-station": "city-railway-station-ksr-bengaluru",
    "sandal-soap": "sandal-soap-factory",
    "mysore-road": "mysuru-road",
    "pattandur-agrahara": "pattanduru-agrahara",
    "sir-m-v": "sir-m-visvesvaraya-station-central-college",
    "kuvempu-road": "mahakavi-kuvempu-road",
    "chickpet": "chickpete",
    "hebbagodi": "biocon-hebbagodi",
    "nayandahalli": "pantharapalya-nayandahalli",
}
COLORS = {"PURPLE": "#7B1FA2", "GREEN": "#2E7D32", "YELLOW": "#FBC02D"}
BADGES = {"PURPLE": "", "GREEN": " g", "YELLOW": " y"}
BENCHMARK = ROUTES / "whitefield-to-challaghatta.html"
STYLE = re.search(r"<style>(.*?)</style>", BENCHMARK.read_text(encoding="utf-8"), re.S).group(1)
STYLE = STYLE.split("/* Bengaluru route additions */", 1)[0].rstrip()
EXTRA_STYLE = """
/* Bengaluru route additions */
.mgi-sections{min-width:0;grid-template-columns:minmax(0,1fr)}
.mgi-card{min-width:0}
.line-tag{display:inline-block;font-size:.78rem;font-weight:700;padding:3px 10px;border-radius:999px}
.line-tag.purple{background:#F3E5F5;color:#7B1FA2;border:1px solid #BA68C8}
.line-tag.green{background:#E8F5E9;color:#2E7D32;border:1px solid #81C784}
.line-tag.yellow{background:#FFFDE7;color:#614800;border:1px solid #F57F17}
.rc-step.step-xchange::before{background:#1A1A1A;box-shadow:0 0 0 2px #1A1A1A}
details.rc-more{padding:0}.rc-more summary{padding:12px;cursor:pointer}
details.rc-more .rc-list{display:block;margin:0;columns:2}
.mgi-map{width:max-content;min-width:100%}.mgi-map .s{min-width:100px}
.mgi-map .s::before{background:var(--line-color)}
.mgi-map .s i{border-color:var(--line-color);background:var(--line-color)}
.mgi-map .s.x i{border-color:#1A1A1A;background:#1A1A1A}
@media(max-width:560px){details.rc-more .rc-list{columns:1}}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def money(value: Decimal | int) -> str:
    return "₹" + f"{Decimal(value):,.2f}".rstrip("0").rstrip(".")


def station(slug: str) -> dict:
    return STATIONS[ALIASES.get(slug, slug)]


def segments(start: str, end: str) -> list[tuple[str, list[str]]]:
    """Find a route with the fewest transfers, then the shortest distance."""
    import heapq

    graph: dict[str, list[tuple[str, str, Decimal]]] = {}
    for line, edges in DATA["interstationDistances"].items():
        for edge in edges:
            a, b = edge["fromStationId"], edge["toStationId"]
            distance = Decimal(str(edge["distanceKm"]))
            graph.setdefault(a, []).append((b, line, distance))
            graph.setdefault(b, []).append((a, line, distance))
    heap = [(0, Decimal(0), start, "", [])]
    best = {}
    while heap:
        changes, distance, current, previous_line, path = heapq.heappop(heap)
        key = (current, previous_line)
        if key in best and best[key] <= (changes, distance):
            continue
        best[key] = (changes, distance)
        if current == end:
            result: list[tuple[str, list[str]]] = []
            for a, b, line in path:
                if not result or result[-1][0] != line:
                    result.append((line, [a, b]))
                else:
                    result[-1][1].append(b)
            return result
        for nxt, line, km in graph[current]:
            heapq.heappush(heap, (changes + int(bool(previous_line) and line != previous_line),
                                  distance + km, nxt, line, path + [(current, nxt, line)]))
    raise ValueError(f"No route between {start} and {end}")


def distance_of(route: list[tuple[str, list[str]]]) -> Decimal:
    total = Decimal(0)
    for line, ids in route:
        edges = {frozenset((e["fromStationId"], e["toStationId"])): Decimal(str(e["distanceKm"]))
                 for e in DATA["interstationDistances"][line]}
        total += sum((edges[frozenset(pair)] for pair in zip(ids, ids[1:])), Decimal(0))
    return total


def fare_for(distance: Decimal) -> int:
    for slab in DATA["fareRules"]["distanceSlabs"]:
        upper = slab["maxDistanceKm"]
        if upper is None or distance <= Decimal(str(upper)):
            return slab["tokenFare"]
    raise ValueError(f"No fare slab for {distance} km")


def discount_fare(fare: int, period: str) -> Decimal:
    percentage = DATA["fareRules"]["discounts"][period]["percentage"]
    return Decimal(fare) * (Decimal(1) - Decimal(percentage) / 100)


def display_distance(distance: Decimal) -> str:
    return str(distance.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def platform(st: dict, line: str, ids: list[str], arriving: bool = False) -> str:
    order = LINES[line]["stationsOrder"]
    forward = order.index(ids[-1]) > order.index(ids[0])
    terminal = STATIONS[order[-1 if forward else 0]]["name"]
    choices = [p for p in st["directionalPlatforms"] if p["line"] == line]
    # At a terminus the source marks the arrival platform rather than its direction.
    if arriving and st["id"] == order[-1 if forward else 0]:
        for p in choices:
            if any(word in p["direction"].lower() for word in ("termin", "reversal", "arrivals")):
                return f"Platform {p['platformNumber']}"
    for p in choices:
        if terminal.lower() in p["direction"].lower():
            return f"Platform {p['platformNumber']}"
    return "follow station platform signs"


def direction(line: str, ids: list[str]) -> str:
    order = LINES[line]["stationsOrder"]
    return STATIONS[order[-1 if order.index(ids[-1]) > order.index(ids[0]) else 0]]["name"]


def tag(line: str) -> str:
    return f'<span class="line-tag {line.lower()}">{esc(LINES[line]["lineName"])}</span>'


def transfer_text(before: str, after: str, ids: list[str]) -> str:
    hub = HUBS[ids[0]]
    target = platform(STATIONS[ids[0]], after, ids)
    if hub["id"] == "majestic":
        levels = {"PURPLE": "Underground Level 2", "GREEN": "Underground Level 1"}
        walk = f'{levels[before]} ({LINES[before]["lineName"]}) to {levels[after]} ({LINES[after]["lineName"]})'
    else:
        walk = f'{LINES[before]["lineName"]} to {LINES[after]["lineName"]} via the cross-platform concourse'
    return f'Allow about {hub["transferTimeMinutes"]} minutes. Follow signs from {walk}; board {target} towards {direction(after, ids)}.'


def gate_text(st: dict) -> str:
    return "; ".join(f'{g["gate"]}: {g["direction"]}' for g in st["gates"])


def gates_table(st: dict) -> str:
    rows = "".join(f'<tr><td>{esc(g["gate"])}</td><td>{esc(g["direction"])}</td></tr>' for g in st["gates"])
    p = st["parking"]
    parking = f'{p["twoWheelerCapacity"]} two-wheelers, {p["fourWheelerCapacity"]} cars and {p["bicycleCapacity"]} bicycles'
    if not p["available"]:
        parking = f'No vehicle parking listed; bicycle capacity {p["bicycleCapacity"]}'
    feeder = "Feeder bus connection available; check the gate directions and current BMTC services." if st["feederBusAvailable"] else "Check BMTC for current feeder connections."
    return (f'<div><h3>{esc(st["name"])}</h3><div class="mgi-scroll"><table class="mgi-tbl">'
            f'<thead><tr><th>Gate</th><th>Roads, landmarks and bus connections</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p>Nearby: {esc(", ".join(st["landmarks"]))}.</p><p>{esc(feeder)}</p><p>Parking capacity: {esc(parking)}.</p></div>')


def sec(id_: str, title: str, content: str, extra: str = "") -> str:
    return (f'<section class="mgi-card{extra}" id="{id_}">\n'
            f'  <div class="mgi-sec-head"><h2 class="mgi-sec-title">{esc(title)}</h2><span class="mgi-sec-line"></span></div>\n'
            f'  {content}\n</section>')


def metrics(items: list[tuple[str, str, str]]) -> str:
    return '<div class="rc-summary">' + "".join(
        f'<div><span>{esc(label)}</span><b>{esc(value)}</b>{f"<small>{esc(note)}</small>" if note else ""}</div>'
        for label, value, note in items) + '</div>'


def faq_html(faq: list[tuple[str, str]]) -> str:
    return '<div class="mgi-faq-wrap">' + "".join(
        f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq) + '</div>'


def planner() -> str:
    return """<section id="global-search-section" class="mgi-card">
  <h2>Plan a Route</h2>
  <div class="sc">
    <div class="fd"><label class="fl" for="global-src-search">From</label><div class="ac-wrap"><input type="text" id="global-src-search" class="ac-input" autocomplete="off"><input type="hidden" id="global-src"><ul class="ac-list" id="global-src-list" hidden></ul></div></div>
    <div class="swap-row"><button class="swap" id="global-swap-btn" type="button" aria-label="Swap stations">⇄</button></div>
    <div class="fd"><label class="fl" for="global-dst-search">To</label><div class="ac-wrap"><input type="text" id="global-dst-search" class="ac-input" autocomplete="off"><input type="hidden" id="global-dst"><ul class="ac-list" id="global-dst-list" hidden></ul></div></div>
    <button class="btn-find" id="global-find-btn" type="button">Find Route</button>
  </div>
</section>"""


def common_sections(start: dict, end: dict, route: list[tuple[str, list[str]]],
                    fare: int | None, minutes: int | None, faq: list[tuple[str, str]]) -> str:
    peak = [
        ("Early morning · 5:00–8:00 AM", "Generally lighter; check the first departure."),
        ("Morning rush · 8:00–11:00 AM", "Allow extra time for crowds."),
        ("Off-peak midday · 11:00 AM–4:30 PM", "Often less crowded."),
        ("Evening rush · 4:30–8:00 PM", "Allow extra time for crowds."),
        ("Post-rush taper · 8:00–10:00 PM", "Crowds usually ease."),
        ("Late night · 10:00–11:00 PM", "Check the last train from your station."),
    ]
    cards = '<div class="mgi-peak-grid">'
    for i, ((label, note), width) in enumerate(zip(peak, (25, 95, 40, 100, 50, 20))):
        meter_class = ' class="hi"' if i in (1, 3) else ''
        cards += f'<div><b>{esc(label)}</b><small>{esc(note)}</small><div class="meter"><i{meter_class} style="width:{width}%"></i></div></div>'
    cards += '</div>'
    parts = [sec("peak", "Peak Traveling Hours", cards)]
    if fare is not None and minutes is not None:
        peak_fare = discount_fare(fare, "peak")
        off_peak_fare = discount_fare(fare, "offPeak")
        rows = [
            ("Namma Metro Smart Card / QR", f"{money(peak_fare)} peak / {money(off_peak_fare)} off-peak", f"~{minutes} min", "Rail time; allow for access and waiting"),
            ("Namma Metro Token", money(fare), f"~{minutes} min", "Allow time to buy a token"),
            ("App Cab", "Check app quote", "Check live traffic", "ORR, Old Madras Road, Hosur Road and Mysore Road may be congested"),
            ("Auto Rickshaw", "Check meter or quote", "Check live traffic", "Road traffic varies"),
            ("Two-Wheeler", "Check fuel and parking cost", "Check live traffic", "Road traffic and parking vary"),
        ]
        table = '<div class="mgi-scroll"><table class="mgi-tbl"><thead><tr><th>Mode</th><th>One-way cost</th><th>Time</th><th>Notes</th></tr></thead><tbody>' + "".join(
            '<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'
        parts.append(sec("compare", "Multimodal Commute Cost & Time Comparison", table))
        table = '<div class="mgi-scroll"><table class="mgi-tbl"><thead><tr><th>Period</th><th>Single Token</th><th>Smart Card (Peak 5%)</th><th>Smart Card (Off-Peak 10%)</th><th>Total Monthly Savings</th></tr></thead><tbody>'
        for label, trips in [("Per trip", 1), ("Daily round trip", 2), ("Weekly 6 days", 12), ("Monthly 24 workdays", 48)]:
            savings = (f'Peak {money((Decimal(fare) - peak_fare) * 48)} / off-peak {money((Decimal(fare) - off_peak_fare) * 48)}'
                       if trips == 48 else "See monthly row")
            values = [label, money(Decimal(fare) * trips), money(peak_fare * trips), money(off_peak_fare * trips), savings]
            table += '<tr>' + ''.join(f'<td>{esc(value)}</td>' for value in values) + '</tr>'
        table += '</tbody></table></div><p>Estimates assume the same fare both ways and that every trip uses the indicated rate. Off-peak: 05:00–08:00, 11:00–16:30 and 20:00–23:00, and all day Sunday. Other times use the peak rate.</p>'
        parts.append(sec("savings", "Commuter Pass & Monthly Budget Savings", table))
    parts.append(sec("gates", "Gate & Landmark Blueprint", '<div class="mgi-gates">' + gates_table(start) + (gates_table(end) if start["id"] != end["id"] else "") + '</div>'))
    guides = [
        ("/bengaluru-metro/stations/nadaprabhu-kempegowda-station-majestic.html", "Majestic Metro Station: Purple and Green Interchange"),
        ("/blog/bengaluru-metro-fare-chart-2026-slabs-smart-card-discounts-price-calculator.html", "Namma Metro Fare, Smart Card & QR Guide"),
        ("/bengaluru-metro/stations/banashankari.html", "Banashankari Station & Feeder Connections"),
        ("/bengaluru-metro/stations/", "Namma Metro Station Facilities & Parking"),
    ]
    parts.append(sec("guides", "Related Commuter Guides", '<div class="related-guides-grid">' + "".join(f'<a href="{esc(url)}">{esc(label)}</a>' for url, label in guides) + '</div>', " related-guides-section"))
    amenities = [("Washrooms", "Ask station staff for locations."), ("Drinking Water", "Check availability at the station."),
                 ("First Aid", "Contact the station controller."), ("Food Stalls", "Availability varies by station."),
                 ("Divyangjan Lifts & Braille", "Ask station staff for accessible routes."), ("Parking", "See the station capacities above.")]
    parts.append(sec("amenities", "Station Amenities", '<div class="mgi-fac-grid">' + "".join(f'<div><b>{esc(a)}</b><p>{esc(b)}</p></div>' for a, b in amenities) + '</div>'))
    if route:
        nodes = []
        for i, (line, ids) in enumerate(route):
            for j, id_ in enumerate(ids):
                if i and j == 0:
                    continue
                interchange = j == len(ids) - 1 and i < len(route) - 1
                nodes.append(f'<div class="s{" x" if interchange else ""}" style="--line-color:{COLORS[line]}"><i></i>{esc(STATIONS[id_]["name"])}</div>')
        track = '<div class="mgi-map-outer"><div class="mgi-map" aria-label="Namma Metro route track">' + ''.join(nodes) + '</div></div>' + ' '.join(tag(line) for line, _ in route)
        parts.append(sec("schematic", "Route Map: Namma Metro Track", track))
    safety = [("Platform gap", "Mind the gap when boarding and alighting."), ("Yellow tactile strip", "Wait behind the yellow safety line."),
              ("Women priority coach", "Observe the signs for the reserved coach."), ("Luggage", "The stated luggage limit is 15 kg per passenger; confirm current BMRCL rules before travelling."),
              ("Emergency plunger", "Use the platform emergency stop only in a real emergency."),
              ("BMRCL helpline", "24x7 customer care: 1800-425-12345.")]
    parts.append(sec("safety", "Commuter Safety Tips", '<div class="mgi-safety-grid">' + "".join(f'<div><b>{esc(a)}</b><p>{esc(b)}</p></div>' for a, b in safety) + '</div>'))
    parts.append(sec("faq", "Frequently Asked Questions", faq_html(faq)))
    return '\n'.join(parts)


def render(path: Path) -> str:
    origin_slug, dest_slug = path.stem.split("-to-")
    origin = station(origin_slug)
    airport = dest_slug == "airport"
    destination = station("kr-puram" if origin_slug == "kr-puram" else "silk-board") if airport else station(dest_slug)
    same = origin["id"] == destination["id"]
    route = [] if same else segments(origin["id"], destination["id"])
    distance = distance_of(route) if route else Decimal(0)
    fare = fare_for(distance) if route else None
    displayed_distance = display_distance(distance)
    minutes = sum(len(ids) - 1 for _, ids in route) * 2 + sum(HUBS[ids[0]]["transferTimeMinutes"] for _, ids in route[1:])
    benchmark_ids = {"whitefield-kadugodi", "challaghatta"}
    benchmark_time = not airport and {origin["id"], destination["id"]} == benchmark_ids
    if benchmark_time:
        minutes = DATA["metadata"]["whitefieldToChallaghattaTrip"]["travelTimeMinutes"]
    dest_name = "Kempegowda International Airport" if airport else ("Orion Mall" if dest_slug == "orion-mall" else destination["name"])
    origin_name = "Orion Mall" if origin_slug == "orion-mall" else origin["name"]
    name = f"{origin_name} to {dest_name}"
    canonical = f"https://metroguideindia.com/bengaluru-metro/routes/{path.name}"
    transfer_count = max(0, len(route) - 1)
    transfer_label = "Direct" if not transfer_count else f"{transfer_count} Interchange{'s' if transfer_count != 1 else ''}"
    line_label = " / ".join(LINES[line]["lineName"] for line, _ in route)
    if route:
        headline = f"{line_label} · {displayed_distance} km · ~{minutes} min · {money(fare)} · {transfer_label}"
        desc = (f"{name}: metro to {destination['name']} is {displayed_distance} km, ~{minutes} min, {money(fare)} token fare; connect to an airport bus."
                if airport else f"{name} Namma Metro route: {displayed_distance} km, ~{minutes} min, {money(fare)} token fare. Platform, transfer, gate and timing information.")
        title = (f"{name}: Metro to {destination['name']} & Airport Bus Connection" if airport
                 else f"{name} Metro: Route, Fare ({money(fare)}) & Timings")
        frequency = " / ".join(f'{LINES[line]["lineName"]}: {LINES[line]["frequencyMinutes"]["peak"]}' for line, _ in route)
        summary = metrics([("Distance", f"{displayed_distance} km", "Metro portion" if airport else ""),
                           ("Token Fare", money(fare), f'Smart Card / QR: {money(discount_fare(fare, "peak"))} peak / {money(discount_fare(fare, "offPeak"))} off-peak'),
                           ("Est. Time", f"~{minutes} min", "Metro portion" if airport else ""),
                           ("Frequency", frequency, "Peak")])
        first_line, first_ids = route[0]
        last_line, last_ids = route[-1]
        step = [f'<div class="rc-step"><h2>Board at {esc(origin["name"])}</h2>{tag(first_line)} <b>{esc(platform(origin, first_line, first_ids))}</b><p>Take the train towards {esc(direction(first_line, first_ids))}.</p></div>']
        for i, (line, ids) in enumerate(route):
            if i:
                text = transfer_text(route[i-1][0], line, ids)
                step.append(f'<div class="rc-step step-xchange"><h2>Change at {esc(STATIONS[ids[0]]["name"])}</h2>{tag(line)}<p>{esc(text)}</p></div>')
            middle = ids[1:-1]
            if middle:
                li = ''.join(f'<li>{esc(STATIONS[s]["name"])}</li>' for s in middle)
                if len(middle) > 6:
                    step.append(f'<details class="rc-more"><summary>Show all {len(middle)} intermediate stops</summary><ol class="rc-list">{li}</ol></details>')
                else:
                    step.append(f'<div class="rc-step"><h2>Intermediate stops</h2><ol>{li}</ol></div>')
        step.append(f'<div class="rc-step"><h2>Arrive at {esc(destination["name"])}</h2>{tag(last_line)} <b>{esc(platform(destination, last_line, last_ids, True))}</b><p>{esc(gate_text(destination))}.</p></div>')
        steps = ''.join(step)
        transfer_answer = " ".join(transfer_text(route[i-1][0], line, ids) for i, (line, ids) in enumerate(route) if i) or f'Direct {line_label} journey; stay on the train.'
        fare_answer = (f'The token fare for the metro portion is {money(fare)}; Smart Card and WhatsApp QR fare is '
                       f'{money(discount_fare(fare, "peak"))} at peak (5% off) and {money(discount_fare(fare, "offPeak"))} off-peak (10% off). '
                       'Off-peak hours are 05:00–08:00, 11:00–16:30 and 20:00–23:00, and all day Sunday.')
        estimate = "as given in the network data" if benchmark_time else "estimated at two minutes per stop plus interchange walks"
        duration_answer = f'The metro portion covers {displayed_distance} km in about {minutes} minutes, {estimate}. Allow extra time for waiting.'
    else:
        headline = "No metro ride required"
        desc = f'{name}: local connection information, station gates and onward travel.'
        title = f"{name}: Station Connection & Travel Information"
        summary = ""
        steps = f'<div class="rc-step"><h2>{esc(origin["name"])}</h2><p>No metro ride is needed for this connection. {esc(gate_text(origin))}.</p></div>'
        transfer_answer = 'No train transfer is required for this connection.'
        fare_answer = 'No metro token is required for this connection.'
        duration_answer = 'No metro journey is required. Allow extra time for the onward connection.'
    alert = ""
    if airport:
        alert = f'<p class="mgi-note"><b>Airport connection:</b> The Blue Line airport corridor is under construction. Connect via KR Puram or Central Silk Board to BMTC Vayu Vajra airport feeder buses; this page covers only the metro portion to {esc(destination["name"])}. Confirm bus times and fares with BMTC.</p>'
    if origin_slug == "orion-mall" or dest_slug == "orion-mall":
        alert += '<p class="mgi-note">Orion Mall connects to Sandal Soap Factory station via the Brigade Gateway skybridge; follow local signs.</p>'
    reverse = ROUTES / f"{dest_slug}-to-{origin_slug}.html"
    if reverse.exists():
        reverse_url = f"/bengaluru-metro/routes/{reverse.name}"
    elif not airport and not same:
        reverse_url = "/route.html?" + urlencode({"city": "bengaluru", "from": destination["id"], "to": origin["id"]})
    else:
        reverse_url = "/bengaluru-metro/"
    steps += f'<a class="mgi-btn" href="{esc(reverse_url)}">⇄ Reverse Route ({esc(dest_name)} to {esc(origin_name)})</a>'
    if airport:
        duration_answer += ' The airport bus is additional; check BMTC for its journey time.'
        fare_answer += ' The airport bus fare is additional.'
    times = DATA["serviceTimings"]
    timing_answer = (f'Network service runs {times["mondayToSaturday"]["firstTrain"]} to {times["mondayToSaturday"]["lastTrain"]} Monday to Saturday, '
                     f'and {times["sundayAndHolidays"]["firstTrain"]} to {times["sundayAndHolidays"]["lastTrain"]} on Sundays and holidays. '
                     'Confirm first and last departures at your station.')
    faq = [(f'How long does the journey from {origin_name} to {dest_name} take?', duration_answer),
           (f'What is the token and Smart Card fare from {origin_name} to {dest_name}?', fare_answer),
           ('Where do I change platforms?', transfer_answer),
           ('What are the first and last train timings?', timing_answer),
           (f'Which exit gates serve {destination["name"]}?', gate_text(destination) + '.')]
    crumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": label, "item": url} for i, (label, url) in enumerate([
            ("Home", "https://metroguideindia.com/"), ("Bengaluru Metro", "https://metroguideindia.com/bengaluru-metro/"),
            ("Routes", "https://metroguideindia.com/bengaluru-metro/routes/"), (name, canonical)], 1)]}
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    ld = lambda obj: json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
    sections = common_sections(origin, destination, route, fare, minutes if route else None, faq)
    return f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5420399473611868" crossorigin="anonymous"></script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-SV6378N2ZW"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-SV6378N2ZW');</script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css">
<link rel="stylesheet" href="/css/styles.css">
<link rel="stylesheet" href="/assets/css/main.css">
<script type="application/ld+json">{ld(crumb)}</script>
<script type="application/ld+json">{ld(schema)}</script>
<style>{STYLE}
{EXTRA_STYLE}</style>
</head>
<body>
<main class="mgi-wrap">
<a class="mgi-back" href="/bengaluru-metro/">← Plan Another Route</a>
<h1>{esc(origin_name)} → {esc(dest_name)}</h1>
<p class="mgi-sub">Namma Metro (BMRCL) · {esc(headline)}</p>
{alert}
{summary}
<div class="rc-steps">{steps}</div>
<div class="mgi-sections">
{sections}
</div>
<p class="mgi-note">MetroGuideIndia is independent and not affiliated with BMRCL. Fares, timings, platforms and facilities can change; confirm with the official <a href="https://www.bmrc.co.in/">BMRCL website</a> or call 1800-425-12345. <a href="https://wa.me/918105556677?text=Hi">BMRCL WhatsApp ticketing</a>.</p>
{planner()}
</main>
<footer><div class="wrap"><div class="foot-logo">MetroGuideIndia</div><p>Independent transit resource, not affiliated with BMRCL.</p><div class="foot-links"><a href="/">Home</a> · <a href="/blog.html">Blog</a> · <a href="/contact.html">Contact</a> · <a href="/disclaimer.html">Disclaimer</a></div></div></footer>
<script src="/js/globalSearchBar.js?v=20260410"></script>
</body>
</html>
'''


def main() -> None:
    paths = sorted(ROUTES.glob("*.html"))
    pages = [(path, render(path)) for path in paths]
    for offset in range(0, len(pages), 10):
        for path, content in pages[offset:offset + 10]:
            path.write_text(content, encoding="utf-8")
    print(f"Generated {len(pages)} routes in batches of 10.")


if __name__ == "__main__":
    main()
