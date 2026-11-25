#!/usr/bin/env python3
"""
generate_blog_rich_html.py — MetroGuideIndia

Builds CMS posts and their existing aliases using blog_template.py,
blog_content.py, blog_faq.py and the site's post.html template.
FAQ schema is derived from the rendered article, not a separate override.

Run:
    python3 generate_blog_rich_html.py
"""

from __future__ import annotations

import json
import re
import os
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import quote
from urllib.parse import unquote, urlparse

from blog_template import render as render_shared_post

BLOGS_DIR = Path('data/blogs')
BLOG_HTML_DIR = Path('blog')
SITEMAP_PATH = Path('sitemap.xml')
SITE_DOMAIN = 'https://metroguideindia.com'
GA4_ID = 'G-SV6378N2ZW'
ADSENSE_ID = 'ca-pub-5420399473611868'

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ''
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

def slugify(text: str) -> str:
    """Convert heading text to URL slug."""
    if not text:
        return ''
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

def inline_format(text: str) -> str:
    """Convert markdown inline formatting to HTML."""
    if not text:
        return text
    
    # Bold + italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
    # Code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Images
    def replace_img(m):
        alt = escape_html(m.group(1) or '')
        src = m.group(2)
        return f'<img class="blog-inline-image" src="{src}" alt="{alt}" loading="lazy" decoding="async">'
    text = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)', replace_img, text)
    
    return text

def md_to_html(md: str) -> tuple[str, list[tuple[int, str, str]]]:
    """
    Convert Markdown to HTML.
    Returns: (html, toc_items) where toc_items = [(level, text, slug), ...]
    """
    if not md:
        return '', []
    
    lines = md.split('\n')
    html = []
    toc = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Headings
        h_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if h_match:
            level = len(h_match.group(1))
            heading_text = h_match.group(2).strip()
            heading_html = inline_format(heading_text)
            
            # Skip h1 (assume it's the article title)
            if level == 1:
                i += 1
                continue
            
            if heading_html:
                slug = slugify(heading_text)
                html.append(f'<h{level} class="blog-h{level}" id="{slug}">{heading_html}</h{level}>')
                
                # Add to TOC if h2 or h3
                if level in (2, 3):
                    toc.append((level, heading_text, slug))
            
            i += 1
            continue
        
        # Code blocks (fenced)
        if re.match(r'^```', line):
            code_lines = []
            i += 1
            while i < len(lines) and not re.match(r'^```', lines[i]):
                code_lines.append(escape_html(lines[i]))
                i += 1
            if code_lines or (i < len(lines) and re.match(r'^```', lines[i])):
                html.append(f'<pre><code>{"".join(code_lines)}</code></pre>')
            i += 1
            continue
        
        # Unordered lists
        if re.match(r'^\s*[-*+]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*+]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*+]\s+', '', lines[i])
                items.append(f'<li>{inline_format(item_text.strip())}</li>')
                i += 1
            if items:
                html.append(f'<ul class="blog-ul">{"".join(items)}</ul>')
            continue
        
        # Ordered lists
        if re.match(r'^\s*\d+\.\s+', line):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i])
                items.append(f'<li>{inline_format(item_text.strip())}</li>')
                i += 1
            if items:
                html.append(f'<ol class="blog-ol">{"".join(items)}</ol>')
            continue
        
        # Tables (pipe-delimited markdown)
        if re.match(r'^\s*\|.+\|', line):
            rows = []
            is_first = True
            while i < len(lines) and re.match(r'^\s*\|', lines[i]):
                row_line = lines[i].strip()
                # Skip separator row
                if re.match(r'^\|\s*[-:\s|]+\s*\|?$', row_line):
                    i += 1
                    continue
                cells = [c.strip() for c in row_line.split('|')[1:-1]]
                if is_first:
                    th_html = "".join(f"<th>{inline_format(c)}</th>" for c in cells)
                    html.append(f'<div class="blog-table-wrap"><table class="blog-table"><thead><tr>{th_html}</tr></thead><tbody>')
                    is_first = False
                else:
                    td_html = "".join(f"<td>{inline_format(c)}</td>" for c in cells)
                    html.append(f'<tr>{td_html}</tr>')
                i += 1
            if not is_first:
                html.append('</tbody></table></div>')
            continue
        
        # Blockquote note boxes (starting with >)
        if re.match(r'^\s*>\s+', line):
            notes = []
            while i < len(lines) and re.match(r'^\s*>\s+', lines[i]):
                note_text = re.sub(r'^\s*>\s+', '', lines[i])
                notes.append(inline_format(note_text.strip()))
                i += 1
            if notes:
                note_html = ' '.join(notes)
                html.append(f'<div class="blog-note"><div class="blog-note-icon">ℹ️</div><div>{note_html}</div></div>')
            continue
        
        # Paragraphs (including HTML blocks if escaped properly)
        if line.strip():
            # Check if line contains HTML (treat as raw if it looks like HTML)
            if line.strip().startswith('<') and '>' in line:
                # Allow raw HTML for embedded components
                html.append(line)
            else:
                para_text = inline_format(line.strip())
                html.append(f'<p class="blog-p">{para_text}</p>')
        
        i += 1
    
    return '\n'.join(html), toc


def extract_faq_from_body(body: str) -> list[dict]:
    """Extract FAQ Q&A pairs from markdown body."""
    faq_items = []
    if not body:
        return faq_items
    
    lines = body.split('\n')
    i = 0
    in_faq = False
    
    while i < len(lines):
        line = lines[i]
        
        # Look for FAQ section heading
        if re.search(r'(frequently asked questions|faqs?)', line, re.I):
            in_faq = True
            i += 1
            continue
        
        if in_faq:
            # Pattern 1: h4 heading (####) followed by answer paragraph
            h4_match = re.match(r'^####\s+(.+)', line)
            if h4_match:
                question = h4_match.group(1).strip()
                i += 1
                # Skip blank lines
                while i < len(lines) and not lines[i].strip():
                    i += 1
                # Next non-blank line is the answer
                if i < len(lines):
                    answer = lines[i].strip()
                    # Clean up markdown formatting
                    answer = answer.replace('**', '').replace('_', '')
                    if answer and not re.match(r'^#+\s+', answer):
                        faq_items.append({
                            '@type': 'Question',
                            'name': question,
                            'acceptedAnswer': {
                                '@type': 'Answer',
                                'text': answer
                            }
                        })
                    i += 1
                continue
            
            # Pattern 2: **Q:** followed by question
            q1_match = re.match(r'^\*\*Q:\*\*\s*(.+)', line)
            if q1_match:
                question = q1_match.group(1).strip()
                i += 1
                # Next line is typically **A:** followed by answer
                if i < len(lines):
                    a_line = lines[i]
                    a_match = re.match(r'^\*\*A:\*\*\s*(.+)', a_line)
                    answer = a_match.group(1).strip() if a_match else a_line.strip()
                    if answer:
                        faq_items.append({
                            '@type': 'Question',
                            'name': question,
                            'acceptedAnswer': {
                                '@type': 'Answer',
                                'text': answer
                            }
                        })
                    i += 1
                continue
            
            # Pattern 3: **Question text?** followed by answer
            q2_match = re.match(r'^\*\*([^*]+\?)\*\*\s*$', line)
            if q2_match:
                question = q2_match.group(1).strip()
                i += 1
                # Skip blank lines
                while i < len(lines) and not lines[i].strip():
                    i += 1
                # Next non-blank line is the answer
                if i < len(lines):
                    answer = lines[i].replace('**', '').strip()
                    if answer and not re.match(r'^#+\s+', answer):
                        faq_items.append({
                            '@type': 'Question',
                            'name': question,
                            'acceptedAnswer': {
                                '@type': 'Answer',
                                'text': answer
                            }
                        })
                    i += 1
                continue
            
            # Exit FAQ section if we hit another major heading
            if re.match(r'^#+\s+', line) and not re.search(r'(frequently asked|faq)', line, re.I):
                in_faq = False
        
        i += 1
    
    return faq_items

def build_faq_schema(post: dict) -> str:
    """Build FAQPage JSON-LD schema."""
    faq_items = extract_faq_from_body(post.get('body', ''))
    
    if not faq_items:
        return ''
    
    schema = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': faq_items
    }
    
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'

def build_article_schema(post: dict, slug: str) -> str:
    """Build Article JSON-LD schema."""
    schema = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': post.get('title', ''),
        'description': post.get('description', ''),
        'image': post.get('image', ''),
        'datePublished': post.get('date', ''),
        'dateModified': post.get('date', ''),
        'author': {
            '@type': 'Organization',
            'name': post.get('author', 'MetroGuideIndia')
        },
        'mainEntityOfPage': {
            '@type': 'WebPage',
            '@id': f'{SITE_DOMAIN}/blog/{slug}.html'
        }
    }
    
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'

def build_toc_html(toc: list[tuple[int, str, str]], slug: str) -> str:
    """Build table of contents HTML."""
    if not toc:
        return ''
    
    html = ['<nav class="blog-toc" aria-label="Table of contents">']
    html.append('<div class="blog-toc-header">On this page</div>')
    html.append('<ul class="blog-toc-list">')
    
    for level, text, anchor in toc:
        indent = 'blog-toc-h2' if level == 2 else 'blog-toc-h3'
        page = quote(slug, safe='-._~')
        html.append(f'<li class="{indent}"><a href="/blog/{page}.html#{escape_html(anchor)}">{escape_html(text)}</a></li>')
    
    html.append('</ul>')
    html.append('</nav>')
    
    return '\n'.join(html)

def get_related_guides(tags: list[str], current_slug: str) -> list[dict]:
    """
    Get related blog posts based on shared tags.
    Returns up to 3 related posts.
    """
    related = []
    tag_set = set(t.lower() for t in tags) if tags else set()
    
    if not tag_set:
        return related
    
    # Scan all blog files for tag matches
    for filepath in BLOGS_DIR.glob('*.json'):
        slug = filepath.stem
        if slug == 'index' or slug == current_slug:
            continue
        
        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
            
            post_tags = set(t.lower() for t in data.get('tags', []))
            matches = tag_set & post_tags
            
            if matches:
                related.append({
                    'slug': slug,
                    'title': data.get('title', ''),
                    'description': data.get('description', ''),
                    'date': data.get('date', ''),
                    'matches': len(matches)
                })
        except Exception:
            continue
    
    # Sort by relevance (more tag matches first) then by date (newest first)
    related.sort(key=lambda x: (-x['matches'], x['date']), reverse=True)
    
    return related[:3]

def build_related_guides_html(related: list[dict]) -> str:
    """Build related guides section HTML."""
    if not related:
        return ''
    
    html = ['<section class="blog-related" aria-labelledby="related-heading">']
    html.append('<h2 id="related-heading" class="blog-h2">Related Guides</h2>')
    html.append('<div class="blog-related-grid">')
    
    for guide in related:
        guide_url = f'/blog/{guide["slug"]}.html'
        html.append(f'''<a href="{guide_url}" class="blog-related-card">
  <h3 class="blog-related-title">{escape_html(guide["title"])}</h3>
  <p class="blog-related-desc">{escape_html(guide["description"])}</p>
  <span class="blog-related-date">{guide["date"]}</span>
</a>''')
    
    html.append('</div>')
    html.append('</section>')
    
    return '\n'.join(html)


def calculate_read_time(body: str) -> int:
    """Estimate reading time in minutes (avg 200 words per minute)."""
    if not body:
        return 1
    words = len(body.split())
    return max(1, round(words / 200))

def render_post_html(slug: str, post: dict) -> str:
    """Render complete HTML page for a blog post."""
    title = post.get('title', slug)
    description = post.get('description', '')
    body = post.get('body', '')
    body_html, toc = md_to_html(body)
    date = post.get('date', '')
    author = post.get('author', 'MetroGuideIndia')
    tags = post.get('tags', [])
    
    canonical_url = f'{SITE_DOMAIN}/blog/{slug}.html'
    page_title = f'{title} | MetroGuideIndia'
    
    # Generate schemas
    faq_schema = build_faq_schema(post)
    article_schema = build_article_schema(post, slug)
    
    # Generate TOC
    toc_html = build_toc_html(toc, slug)
    
    # Get related guides
    related = get_related_guides(tags, slug)
    related_html = build_related_guides_html(related)
    
    # Read time
    read_time = calculate_read_time(body)
    
    # Tags HTML
    tags_html = ''.join(f'<span class="post-tag">{escape_html(tag)}</span>' for tag in tags)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_ID}" crossorigin="anonymous"></script>
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon/favicon-32x32.png"/>
  <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon/favicon-16x16.png"/>
  <link rel="apple-touch-icon" sizes="180x180" href="/assets/favicon/apple-touch-icon.png"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <base href="/"/>
  <title>{escape_html(page_title)}</title>
  <meta name="description" content="{escape_html(description)}"/>
  <meta name="article:published_time" content="{date}"/>
  <meta name="article:author" content="{escape_html(author)}"/>
  <link rel="canonical" href="{canonical_url}"/>
  <meta property="og:title" content="{escape_html(page_title)}"/>
  <meta property="og:description" content="{escape_html(description)}"/>
  <meta property="og:type" content="article"/>
  <meta property="og:url" content="{canonical_url}"/>
  <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"/>
  <link rel="stylesheet" href="/css/styles.css"/>
  <style>
    .post-wrap{{max-width:1200px;margin:0 auto;padding:32px 18px 64px 18px}}
    .post-grid{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:32px;align-items:start}}
    @media(max-width:980px){{.post-grid{{grid-template-columns:1fr;gap:28px}}}}
    .blog-toc{{position:sticky;top:100px;background:var(--surface);border:1px solid var(--border2);border-radius:var(--r);padding:16px;font-size:.85rem;max-height:60vh;overflow-y:auto}}
    .blog-toc-header{{font-weight:700;font-size:.8rem;color:var(--text);margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em}}
    .blog-toc-list{{list-style:none;margin:0;padding:0}}
    .blog-toc-list li{{margin:0;padding:0}}
    .blog-toc-h2 a{{display:block;padding:6px 0;color:var(--text2);text-decoration:none;border-left:2px solid transparent;padding-left:8px;transition:all .15s}}
    .blog-toc-h2 a:hover,.blog-toc-h2 a:focus{{color:var(--red);border-left-color:var(--red)}}
    .blog-toc-h3{{margin-left:12px;margin-top:4px}}
    .blog-toc-h3 a{{display:block;padding:4px 0;color:var(--muted);font-size:.8rem;text-decoration:none;border-left:2px solid transparent;padding-left:8px;transition:all .15s}}
    .blog-toc-h3 a:hover,.blog-toc-h3 a:focus{{color:var(--red);border-left-color:var(--red)}}
    .blog-body{{font-size:.96rem;line-height:1.85;color:var(--text2)}}
    .blog-h1{{font-size:1.55rem;margin:32px 0 12px}}
    .blog-h2{{font-size:1.18rem;margin:36px 0 12px;padding-left:14px;border-left:3px solid var(--red)}}
    .blog-h3{{font-size:1.02rem;margin:24px 0 10px}}
    .blog-p{{margin:0 0 18px}}
    .blog-p a{{color:var(--red);border-bottom:1px dotted rgba(192,57,43,.4)}}
    .blog-p a:hover{{border-bottom-color:var(--red)}}
    .blog-ul,.blog-ol{{margin:0 0 18px;padding-left:22px}}
    .blog-ul li,.blog-ol li{{margin-bottom:7px;color:var(--text2)}}
    .blog-table-wrap{{overflow-x:auto;margin:22px 0;border:1px solid var(--border2);border-radius:var(--r);box-shadow:var(--shadow)}}
    .blog-table{{width:100%;border-collapse:collapse;font-size:.875rem}}
    .blog-table thead{{background:linear-gradient(135deg,var(--surface3),var(--surface2))}}
    .blog-table th{{color:var(--text);font-family:'Syne',sans-serif;font-weight:700;padding:13px 16px;text-align:left;border-bottom:2px solid var(--border2);white-space:nowrap;font-size:.82rem;text-transform:uppercase;letter-spacing:.04em}}
    .blog-table td{{padding:11px 16px;border-bottom:1px solid var(--border2);color:var(--text2);vertical-align:top}}
    .blog-table tbody tr:hover td{{background:var(--surface2);transition:background .12s}}
    .blog-note{{background:var(--amber-bg);border:1px solid var(--amber-border);border-left:3px solid var(--amber);border-radius:var(--r-sm);padding:14px 18px;margin:22px 0;font-size:.9rem;color:var(--text2);display:flex;gap:10px;align-items:flex-start}}
    .blog-note-icon{{flex-shrink:0}}
    .blog-inline-image{{display:block;max-width:100%;height:auto;margin:16px auto;border-radius:12px;border:1px solid var(--border2);box-shadow:var(--shadow);background:var(--surface);object-fit:cover}}
    .blog-related{{margin:48px 0 0;padding-top:32px;border-top:2px solid var(--border2)}}
    .blog-related-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:16px}}
    .blog-related-card{{display:flex;flex-direction:column;padding:16px;background:var(--surface);border:1px solid var(--border2);border-radius:var(--r);text-decoration:none;color:inherit;transition:transform .15s var(--ease),box-shadow .15s var(--ease)}}
    .blog-related-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow-md)}}
    .blog-related-title{{font-family:'Syne',sans-serif;font-weight:700;font-size:.95rem;color:var(--text);margin:0 0 8px}}
    .blog-related-desc{{font-size:.85rem;color:var(--text2);margin:0 0 10px;flex-grow:1}}
    .blog-related-date{{font-size:.75rem;color:var(--muted)}}
    .post-title{{font-family:'Syne',sans-serif;font-weight:800;font-size:clamp(1.5rem,4vw,2.1rem);margin-bottom:12px}}
    .post-meta{{font-size:.79rem;color:var(--muted);display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:20px}}
    .post-tags{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px}}
    .post-tag{{font-size:.65rem;font-weight:600;padding:3px 10px;border-radius:11px;background:var(--red-bg);color:var(--red);border:1px solid rgba(192,57,43,.2)}}
    .post-back{{display:inline-flex;align-items:center;gap:6px;font-size:.82rem;color:var(--muted);margin-bottom:20px;cursor:pointer;transition:color .15s;text-decoration:none}}
    .post-back:hover{{color:var(--red)}}
  </style>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_ID}');
  </script>
  {article_schema}
  {faq_schema}
</head>
<body>
<nav class="nav">
  <div class="nav-inner">
    <a href="/" class="logo"><div class="logo-icon">🚄</div>MetroGuideIndia</a>
    <div class="nav-right">
      <span class="nav-chip">Beta</span>
      <a href="/blog" style="font-size:.8rem;color:var(--muted);padding:6px 10px;border-radius:8px;border:1px solid var(--border2)">← Blog</a>
    </div>
  </div>
</nav>
<main>
<div class="post-wrap">
  <a href="/blog" class="post-back">← Back to blog</a>
  <div class="post-grid">
    <article class="blog-article">
      <div class="post-header">
        <div class="post-tags">{tags_html}</div>
        <h1 class="post-title">{escape_html(title)}</h1>
        <div class="post-meta">
          <span>{escape_html(author)}</span>
          <span>{date}</span>
          <span>{read_time} min read</span>
        </div>
      </div>
      <div class="blog-body">
        {body_html}
      </div>
      {related_html}
    </article>
    {toc_html}
  </div>
</div>
</main>
<footer>
  <div class="wrap" style="text-align:center;padding:20px;color:var(--muted);font-size:.85rem">
    <div>© 2026 MetroGuideIndia. Not affiliated with any transit agency.</div>
  </div>
</footer>
</body>
</html>'''
    
    return html

def main():
    """Generate static pages and their existing aliases from CMS data."""
    if not BLOGS_DIR.exists():
        raise SystemExit(f'Error: {BLOGS_DIR} does not exist')
    BLOG_HTML_DIR.mkdir(exist_ok=True)
    posts = {}
    for filepath in sorted(BLOGS_DIR.glob('*.json')):
        if filepath.stem != 'index':
            posts[filepath.stem] = json.loads(filepath.read_text(encoding='utf-8'))
    aliases = {
        'anand-vihar-to-meerut-metro-route-fare-timings-and-complete-guide-2026':
            'anand-vihar-to-meerut-metro-route-fare-timings-and-complete-guide-2026-1',
        'the-ultimate-anand-vihar-to-ghaziabad-transit-guide-distance-metro-routes-and-commuter-hacks-2026':
            'the-ultimate-anand-vihar-to-ghaziabad-transit-guide-distance-metro-routes-and-commuter-hacks',
    }
    canonicals = {}
    for slug, post in posts.items():
        path = unquote(urlparse(str(post.get('url') or '')).path)
        match = re.fullmatch(r'/blog/([^/]+)\.html', path)
        canonical = match.group(1) if match else slug
        canonicals[slug] = canonical
        if canonical != slug:
            if canonical in posts or canonical in aliases and aliases[canonical] != slug:
                raise ValueError(f'Conflicting blog alias: {canonical}')
            aliases[canonical] = slug
    rendered = {}
    for slug, post in posts.items():
        rendered[slug] = render_shared_post(slug, post, posts, canonicals[slug])
    for alias, source in aliases.items():
        if source in posts:
            canonical = alias if alias == 'anand-vihar-to-meerut-metro-route-fare-timings-and-complete-guide-2026' else canonicals[source]
            rendered[alias] = render_shared_post(alias, posts[source], posts, canonical, source)
    for slug, content in rendered.items():
        (BLOG_HTML_DIR / f'{slug}.html').write_text(content, encoding='utf-8')
    print(f'Generated {len(rendered)} static blog pages.')

if __name__ == '__main__':
    main()

