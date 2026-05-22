#!/usr/bin/env python3
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ROUTES_DIR = REPO_ROOT / "routes"
SECTION_START = "<!-- STATION_ROUTE_MATRIX_START -->"
SECTION_END = "<!-- STATION_ROUTE_MATRIX_END -->"


@dataclass(frozen=True)
class TargetConfig:
    stations_dir: Path
    color: str
    route_context: str
    replace_existing_popular_section: bool = False


@dataclass
class StationPage:
    path: Path
    title: str
    keys: set[str]
    routes: list["RouteEntry"] = field(default_factory=list)


@dataclass(frozen=True)
class RouteRecord:
    slug: str
    origin_slug: str
    destination_slug: str
    origin_label: str
    destination_label: str


@dataclass(frozen=True)
class RouteEntry:
    record: RouteRecord
    role: str


TARGETS = (
    TargetConfig(
        stations_dir=REPO_ROOT / "namo-bharat" / "stations",
        color="#0f766e",
        route_context="Namo Bharat and Meerut Metro route guides linked to this station hub.",
        replace_existing_popular_section=True,
    ),
    TargetConfig(
        stations_dir=REPO_ROOT / "delhi-metro" / "stations",
        color="#1a2a6c",
        route_context="Namo Bharat corridor route guides linked to this interchange station.",
    ),
    TargetConfig(
        stations_dir=REPO_ROOT / "bengaluru-metro" / "stations",
        color="#6c2e9d",
        route_context="Namo Bharat corridor route guides linked to this station name.",
    ),
)


def compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def pretty_label(slug: str) -> str:
    return re.sub(r"\s+", " ", slug.replace("-", " ").strip()).title()


def extract_h1(html: str) -> str:
    m = re.search(r'<h1 class="rp-title"[^>]*>(.*?)</h1>', html, flags=re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()


def extract_route_labels(html: str, origin_slug: str, destination_slug: str) -> tuple[str, str]:
    title = extract_h1(html)
    if "→" in title:
        left, right = [part.strip() for part in title.split("→", 1)]
        if left and right:
            return left, right
    return pretty_label(origin_slug), pretty_label(destination_slug)


def strip_existing_block(html: str) -> str:
    return re.sub(
        rf"\n?{re.escape(SECTION_START)}.*?{re.escape(SECTION_END)}\n?",
        "\n",
        html,
        flags=re.S,
    )


def build_station_page(path: Path) -> StationPage:
    html = path.read_text(encoding="utf-8")
    title = extract_h1(html) or pretty_label(path.stem)
    key_sources = {
        path.stem,
        title,
        title.replace("&", "and"),
        title.split("(")[0].strip(),
    }
    keys = {compact_key(item) for item in key_sources if item.strip()}
    return StationPage(path=path, title=title, keys=keys)


def resolve_station_page(endpoint_slug: str, pages: list[StationPage]) -> StationPage | None:
    target_key = compact_key(endpoint_slug)
    exact = [page for page in pages if target_key in page.keys]
    if len(exact) == 1:
        return exact[0]

    prefix = [
        page
        for page in pages
        if any(key.startswith(target_key) or target_key.startswith(key) for key in page.keys)
    ]
    if len(prefix) == 1:
        return prefix[0]

    best_page: StationPage | None = None
    best_score = 0.0
    second_score = 0.0
    for page in pages:
        score = max((difflib.SequenceMatcher(a=target_key, b=key).ratio() for key in page.keys), default=0.0)
        if score > best_score:
            second_score = best_score
            best_score = score
            best_page = page
        elif score > second_score:
            second_score = score
    if best_page and best_score >= 0.88 and (best_score - second_score) >= 0.03:
        return best_page
    return None


def load_routes(all_pages: list[StationPage]) -> list[RouteRecord]:
    records: list[RouteRecord] = []
    for path in sorted(ROUTES_DIR.glob("*.html")):
        stem = path.stem
        if "-to-" not in stem:
            continue
        origin_slug, destination_slug = stem.split("-to-", 1)
        html = path.read_text(encoding="utf-8")
        origin_label, destination_label = extract_route_labels(html, origin_slug, destination_slug)
        origin_page = resolve_station_page(origin_slug, all_pages)
        destination_page = resolve_station_page(destination_slug, all_pages)
        records.append(
            RouteRecord(
                slug=stem,
                origin_slug=origin_slug,
                destination_slug=destination_slug,
                origin_label=origin_page.title if origin_page else origin_label,
                destination_label=destination_page.title if destination_page else destination_label,
            )
        )
    return records


def route_sort_key(entry: RouteEntry, station_title: str) -> tuple[int, str, str]:
    counterpart = entry.record.destination_label if entry.role == "origin" else entry.record.origin_label
    return (0 if entry.role == "origin" else 1, counterpart.lower(), entry.record.slug)


def build_route_card(entry: RouteEntry, color: str) -> str:
    record = entry.record
    descriptor = f"{record.origin_label} to {record.destination_label} Route Guide"
    badge = "Starts here" if entry.role == "origin" else "Ends here"
    return (
        f'      <a href="/routes/{escape(record.slug)}.html" class="pr-card" style="--gc:{escape(color)}">'
        f'<div class="pr-card-route"><span class="pr-card-from">{escape(record.origin_label)}</span>'
        f'<span class="pr-card-arrow">→</span><span class="pr-card-to">{escape(record.destination_label)}</span></div>'
        f'<div class="pr-card-meta"><span>{escape(descriptor)}</span><span>{escape(badge)}</span></div></a>'
    )


def build_block(station: StationPage, color: str, route_context: str) -> str:
    outgoing = sum(1 for entry in station.routes if entry.role == "origin")
    incoming = len(station.routes) - outgoing
    detail = f"{outgoing} route guides start here"
    if incoming:
        detail += f" and {incoming} more end here"
    cards = "\n".join(build_route_card(entry, color) for entry in sorted(station.routes, key=lambda item: route_sort_key(item, station.title)))
    return (
        f"{SECTION_START}\n"
        f'  <section class="station-route-matrix" style="margin-bottom:36px">\n'
        f'    <div class="sec-eye">Route Matrix</div>\n'
        f'    <h3 class="sec-head">Popular Routes from {escape(station.title)}</h3>\n'
        f'    <p style="color:var(--muted);font-size:.88rem;margin:0 0 16px">{escape(route_context)} {escape(detail)}.</p>\n'
        f'    <div class="popular-routes-grid pr-grid" style="--gc:{escape(color)}">\n'
        f"{cards}\n"
        f"    </div>\n"
        f"  </section>\n"
        f"{SECTION_END}"
    )


def replace_namo_popular_section(html: str, block: str) -> str:
    pattern = re.compile(
        r"\n\s*<section[^>]*>\s*<div class=\"sec-eye\">Internal Links</div>\s*<h[23] class=\"sec-head\">Popular Routes from .*?</section>\s*",
        flags=re.S,
    )
    match = pattern.search(html)
    if not match:
        return html
    return html[: match.start()].rstrip() + "\n\n" + block + "\n\n" + html[match.end() :].lstrip("\n")


def insert_before_wrap_end(html: str, block: str) -> str:
    global_search_at = html.find('<section id="global-search-section"')
    if global_search_at == -1:
        return html
    wrap_close_at = html.rfind("\n</div>", 0, global_search_at)
    if wrap_close_at == -1:
        return html
    return html[:wrap_close_at].rstrip() + "\n\n" + block + "\n" + html[wrap_close_at:]


def inject_block(html: str, block: str, *, replace_existing_popular_section: bool) -> str:
    clean = strip_existing_block(html)
    if replace_existing_popular_section:
        updated = replace_namo_popular_section(clean, block)
        if updated != clean:
            return updated
    return insert_before_wrap_end(clean, block)


def run(write: bool = True) -> int:
    target_pages: dict[TargetConfig, list[StationPage]] = {}
    for target in TARGETS:
        pages = [build_station_page(path) for path in sorted(target.stations_dir.glob("*.html")) if path.stem != "index"]
        target_pages[target] = pages
    all_pages = [page for pages in target_pages.values() for page in pages]
    routes = load_routes(all_pages)

    for route in routes:
        for target, pages in target_pages.items():
            origin_page = resolve_station_page(route.origin_slug, pages)
            destination_page = resolve_station_page(route.destination_slug, pages)
            if origin_page:
                origin_page.routes.append(RouteEntry(record=route, role="origin"))
            if destination_page and destination_page is not origin_page:
                destination_page.routes.append(RouteEntry(record=route, role="destination"))

    updated = 0
    touched = 0
    for target, pages in target_pages.items():
        for station in pages:
            if not station.routes:
                continue
            touched += 1
            original = station.path.read_text(encoding="utf-8")
            block = build_block(station, target.color, target.route_context)
            result = inject_block(
                original,
                block,
                replace_existing_popular_section=target.replace_existing_popular_section,
            )
            if write and result != original:
                station.path.write_text(result, encoding="utf-8")
                updated += 1

    print(f"[route-matrix] routes parsed: {len(routes)}")
    print(f"[route-matrix] station pages matched: {touched}")
    print(f"[route-matrix] station pages updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
