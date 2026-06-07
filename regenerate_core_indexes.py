#!/usr/bin/env python3
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

SITE_ROOT = "https://metroguideindia.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ET.register_namespace("", SITEMAP_NS)

REPO_ROOT = Path(__file__).resolve().parent
ROBOTS_PATH = REPO_ROOT / "robots.txt"
SITEMAP_PATH = REPO_ROOT / "sitemap.xml"
ROUTES_DIR = REPO_ROOT / "routes"

ROBOTS_TEXT = """User-agent: *
Allow: /
Disallow: /assets/js/
Disallow: /assets/css/

Sitemap: https://metroguideindia.com/sitemap.xml
"""

ROUTE_CHANGEFREQ = "weekly"
ROUTE_PRIORITY = "0.7"


def normalize_site_url(raw_url: str) -> str:
    raw = (raw_url or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        raw = f"{SITE_ROOT}{raw}"

    parts = urlsplit(raw)
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    scheme = "https" if parts.scheme in {"http", "https", ""} else parts.scheme
    netloc = parts.netloc or "metroguideindia.com"
    hostname = (parts.hostname or "metroguideindia.com").lower()

    if hostname in {"metroguideindia.com", "www.metroguideindia.com"}:
        netloc = "metroguideindia.com"
        return urlunsplit((scheme, netloc, path, "", ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def strip_root_route_entries(urlset: ET.Element) -> tuple[dict[str, dict[str, str]], list[ET.Element]]:
    route_meta: dict[str, dict[str, str]] = {}
    removed: list[ET.Element] = []

    for url in list(urlset.findall(f"{{{SITEMAP_NS}}}url")):
        loc_el = url.find(f"{{{SITEMAP_NS}}}loc")
        loc = normalize_site_url(loc_el.text if loc_el is not None and loc_el.text else "")
        if loc.startswith(f"{SITE_ROOT}/routes/"):
            route_meta[loc] = {
                "lastmod": (url.findtext(f"{{{SITEMAP_NS}}}lastmod") or "").strip(),
                "changefreq": (url.findtext(f"{{{SITEMAP_NS}}}changefreq") or "").strip() or ROUTE_CHANGEFREQ,
                "priority": (url.findtext(f"{{{SITEMAP_NS}}}priority") or "").strip() or ROUTE_PRIORITY,
            }
            removed.append(url)

    for url in removed:
        urlset.remove(url)

    return route_meta, removed


def clean_remaining_entries(urlset: ET.Element) -> None:
    seen: set[str] = set()
    for url in list(urlset.findall(f"{{{SITEMAP_NS}}}url")):
        loc_el = url.find(f"{{{SITEMAP_NS}}}loc")
        if loc_el is None:
            urlset.remove(url)
            continue

        normalized = normalize_site_url(loc_el.text or "")
        if not normalized or normalized in seen:
            urlset.remove(url)
            continue

        loc_el.text = normalized
        seen.add(normalized)


def build_route_url(loc: str, meta: dict[str, str]) -> ET.Element:
    url = ET.Element(f"{{{SITEMAP_NS}}}url")

    loc_el = ET.SubElement(url, f"{{{SITEMAP_NS}}}loc")
    loc_el.text = loc

    lastmod = ET.SubElement(url, f"{{{SITEMAP_NS}}}lastmod")
    lastmod.text = meta.get("lastmod") or ""

    changefreq = ET.SubElement(url, f"{{{SITEMAP_NS}}}changefreq")
    changefreq.text = meta.get("changefreq") or ROUTE_CHANGEFREQ

    priority = ET.SubElement(url, f"{{{SITEMAP_NS}}}priority")
    priority.text = meta.get("priority") or ROUTE_PRIORITY

    return url


def sitemap_needs_regeneration(urlset: ET.Element, expected_route_urls: set[str]) -> bool:
    seen: set[str] = set()
    current_route_urls: list[str] = []

    for url in urlset.findall(f"{{{SITEMAP_NS}}}url"):
        loc_el = url.find(f"{{{SITEMAP_NS}}}loc")
        if loc_el is None or not (loc_el.text or "").strip():
            return True

        raw_loc = (loc_el.text or "").strip()
        normalized_loc = normalize_site_url(raw_loc)
        if raw_loc != normalized_loc or normalized_loc in seen:
            return True

        if normalized_loc.startswith(f"{SITE_ROOT}/routes/"):
            current_route_urls.append(normalized_loc)

        seen.add(normalized_loc)

    return set(current_route_urls) != expected_route_urls or len(current_route_urls) != len(expected_route_urls)


def indent_xml(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + ("  " * level)
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in element:
            indent_xml(child, level + 1)
        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = indent
    elif level and (not element.tail or not element.tail.strip()):
        element.tail = indent


def normalize_route_canonical(html: str, slug: str) -> str:
    expected_url = f"{SITE_ROOT}/routes/{slug}.html"
    matches = re.findall(r'<link rel="canonical" href="([^"]+)"\s*/?>', html, flags=re.I)
    if matches == [expected_url]:
        return html

    canonical_tag = f'  <link rel="canonical" href="{expected_url}"/>'
    cleaned = re.sub(r'^\s*<link rel="canonical" href=".*?"\s*/?>\s*\n?', "", html, flags=re.I | re.M)

    if re.search(r'^\s*<meta name="description" content=".*?"\s*/?>\s*$', cleaned, flags=re.I | re.M):
        return re.sub(
            r'(^\s*<meta name="description" content=".*?"\s*/?>\s*$)',
            r"\1\n" + canonical_tag,
            cleaned,
            count=1,
            flags=re.I | re.M,
        )

    return re.sub(r"</head>", canonical_tag + "\n</head>", cleaned, count=1, flags=re.I)


def normalize_route_files() -> int:
    updated = 0
    for path in sorted(ROUTES_DIR.glob("*.html")):
        original = path.read_text(encoding="utf-8")
        normalized = normalize_route_canonical(original, path.stem)
        if normalized != original:
            path.write_text(normalized, encoding="utf-8")
            updated += 1
    return updated


def regenerate_sitemap() -> int:
    tree = ET.parse(SITEMAP_PATH)
    urlset = tree.getroot()
    expected_route_urls = {f"{SITE_ROOT}/routes/{path.name}" for path in ROUTES_DIR.glob("*.html")}

    if not sitemap_needs_regeneration(urlset, expected_route_urls):
        return len(expected_route_urls)

    route_meta, _ = strip_root_route_entries(urlset)
    clean_remaining_entries(urlset)

    for path in sorted(ROUTES_DIR.glob("*.html")):
        loc = f"{SITE_ROOT}/routes/{path.name}"
        urlset.append(build_route_url(loc, route_meta.get(loc, {})))

    indent_xml(urlset)
    tree.write(SITEMAP_PATH, encoding="utf-8", xml_declaration=True)
    return len(list(ROUTES_DIR.glob("*.html")))


def main() -> int:
    ROBOTS_PATH.write_text(ROBOTS_TEXT, encoding="utf-8")
    route_updates = normalize_route_files()
    route_count = regenerate_sitemap()
    print(f"[core-indexes] robots.txt updated")
    print(f"[core-indexes] route canonicals normalized: {route_updates}")
    print(f"[core-indexes] sitemap route URLs regenerated: {route_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
