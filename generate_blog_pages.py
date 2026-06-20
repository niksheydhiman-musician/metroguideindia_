#!/usr/bin/env python3
"""
generate_blog_pages.py — MetroGuideIndia

Refreshes every static /blog/<slug>.html page from data/blogs/*.json by
customizing the shared post.html template with post-specific metadata.
"""

from __future__ import annotations

import glob
import json
import os
import re

BLOGS_DIR = 'data/blogs'
BLOG_HTML_DIR = 'blog'
POST_TEMPLATE_PATH = 'post.html'


def html_attr_escape(text):
    """Escape text for use in an HTML attribute value."""
    return (str(text or '')
            .replace('&', '&amp;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


def replace_once(text, pattern, replacement):
    """Replace a single regex match or raise if the template changed."""
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.IGNORECASE | re.DOTALL)
    if count != 1:
        raise ValueError(f'Could not apply template replacement for pattern: {pattern}')
    return updated


def render_post_html(template, slug, title, description):
    """Render a blog detail page from the shared post template."""
    page_title = f'{title} | MetroGuideIndia'
    canonical = f'https://metroguideindia.com/blog/{slug}'

    rendered = template
    rendered = replace_once(rendered, r'<title>.*?</title>', f'<title>{page_title}</title>')
    rendered = replace_once(
        rendered,
        r'<meta\s+name="description"\s+content=".*?"\s*/?>',
        f'<meta name="description" content="{description}"/>',
    )
    rendered = replace_once(
        rendered,
        r'<link\s+rel="canonical"\s+href=".*?"\s*/?>',
        f'<link rel="canonical" href="{canonical}"/>',
    )
    rendered = replace_once(
        rendered,
        r'<meta\s+property="og:title"\s+content=".*?"\s*/?>',
        f'<meta property="og:title" content="{page_title}"/>',
    )
    rendered = replace_once(
        rendered,
        r'<meta\s+property="og:description"\s+content=".*?"\s*/?>',
        f'<meta property="og:description" content="{description}"/>',
    )
    rendered = replace_once(
        rendered,
        r'<meta\s+property="og:type"\s+content=".*?"\s*/?>',
        '<meta property="og:type" content="article"/>',
    )
    return rendered


def main():
    os.makedirs(BLOG_HTML_DIR, exist_ok=True)

    try:
        with open(POST_TEMPLATE_PATH, encoding='utf-8') as f:
            template = f.read()
    except Exception as e:
        raise SystemExit(f'Error: could not read {POST_TEMPLATE_PATH}: {e}')

    created = 0
    updated = 0
    unchanged = 0

    for filepath in sorted(glob.glob(os.path.join(BLOGS_DIR, '*.json'))):
        slug = os.path.splitext(os.path.basename(filepath))[0]
        if slug == 'index':
            continue

        html_path = os.path.join(BLOG_HTML_DIR, slug + '.html')

        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f'Warning: could not read {filepath}: {e}')
            continue

        title = html_attr_escape(data.get('title', slug))
        description = html_attr_escape(data.get('description', ''))
        content = render_post_html(template, slug, title, description)

        previous = None
        if os.path.exists(html_path):
            try:
                with open(html_path, encoding='utf-8') as f:
                    previous = f.read()
            except Exception as e:
                print(f'Warning: could not read {html_path}: {e}')

        if previous == content:
            unchanged += 1
            continue

        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            if previous is None:
                print(f'Created {html_path}')
                created += 1
            else:
                print(f'Updated {html_path}')
                updated += 1
        except Exception as e:
            print(f'Warning: could not write {html_path}: {e}')

    print(f'Done. Created {created}, updated {updated}, unchanged {unchanged} blog HTML file(s).')


if __name__ == '__main__':
    main()
