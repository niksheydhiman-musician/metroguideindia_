#!/usr/bin/env python3
"""
generate_blog_static_html.py — MetroGuideIndia

Generates real static .html files for each blog post in /data/blogs/*.json.

Each generated file includes:
  • Markdown-to-HTML rendering (matching blogBridge.js logic)
  • FAQPage JSON-LD schema extracted from FAQ sections
  • Full metadata: title, description, canonical URL, og:*
  • GA4 tracking (G-SV6378N2ZW) and AdSense (ca-pub-5420399473611868)
  • Responsive styling with the site's CSS framework
  • Returns HTTP 200 (real file, not client-side route)

FAQ extraction: looks for headings matching "Frequently Asked Questions" or
"FAQs", then finds patterns like "**Q:** ..." followed by "**A:** ...".

Generated files: /blog/<slug>.html
Updated files: sitemap.xml (adds /blog/<slug>.html URLs)

Run:
    python3 generate_blog_static_html.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

BLOGS_DIR = Path('data/blogs')
BLOG_HTML_DIR = Path('blog')
SITEMAP_PATH = Path('sitemap.xml')
SITE_DOMAIN = 'https://metroguideindia.com'
GA4_ID = 'G-SV6378N2ZW'
ADSENSE_ID = 'ca-pub-5420399473611868'


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


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


def md_to_html(md: str) -> str:
    """Convert Markdown to HTML (matching blogBridge.js logic)."""
    if not md:
        return ''
    
    lines = md.split('\n')
    html = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Headings
        h_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if h_match:
            level = len(h_match.group(1))
            heading_text = inline_format(h_match.group(2).strip())
            if heading_text:
                html.append(f'<h{level} class="blog-h{level}">{heading_text}</h{level}>')
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
        
        # Tables
        if re.match(r'^\s*\|.+\|', line):
            rows = []
            is_first = True
            while i < len(lines) and re.match(r'^\s*\|', lines[i]):
                row_line = lines[i].strip()
                if re.match(r'^\|\s*[-:\s|]+\s*\|?$', row_line):
                    i += 1
                    continue
                cells = [c.strip() for c in row_line.split('|')[1:-1]]
                if is_first:
                    html.append(f'<table class="blog-table"><thead><tr>{"".join(f"<th>{inline_format(c)}</th>" for c in cells)}</tr></thead><tbody>')
                    is_first = False
                else:
                    html.append(f'<tr>{"".join(f"<td>{inline_format(c)}</td>" for c in cells)}</tr>')
                i += 1
            if not is_first:
                html.append('</tbody></table>')
            continue
        
        # Paragraphs
        if line.strip():
            para_text = inline_format(line.strip())
            html.append(f'<p class="blog-p">{para_text}</p>')
        
        i += 1
    
    return '\n'.join(html)


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
            # Look for Q&A pattern: **Q:** or **Question text?** followed by answer
            # Pattern 1: **Q:** followed by question
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
            
            # Pattern 2: **Question text?** followed by answer
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
    
    return f'<!-- FAQ_SCHEMA_INJECT_START -->\n<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>\n<!-- FAQ_SCHEMA_INJECT_END -->'


def render_post_html(slug: str, post: dict) -> str:
    """Render complete HTML page for a blog post."""
    title = post.get('title', slug)
    description = post.get('description', '')
    body_html = md_to_html(post.get('body', ''))
    date = post.get('date', '')
    author = post.get('author', 'MetroGuideIndia')
    tags = post.get('tags', [])
    
    canonical_url = f'{SITE_DOMAIN}/blog/{slug}.html'
    page_title = f'{title} | MetroGuideIndia'
    
    faq_schema = build_faq_schema(post)
    tags_html = ''.join(f'<span class="post-tag">{tag}</span>' for tag in tags)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_ID}" crossorigin="anonymous"></script>
  <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon/favicon-32x32.png"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <base href="/"/>
  <title>{escape_html(page_title)}</title>
  <meta name="description" content="{escape_html(description)}"/>
  <link rel="canonical" href="{canonical_url}"/>
  <meta property="og:title" content="{escape_html(page_title)}"/>
  <meta property="og:description" content="{escape_html(description)}"/>
  <meta property="og:type" content="article"/>
  <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"/>
  <link rel="stylesheet" href="/css/styles.css"/>
  <style>
    .post-wrap{{max-width:1080px;margin:0 auto;padding:32px 18px 64px}}
    .blog-body{{font-size:.96rem;line-height:1.85;color:var(--text2)}}
    .blog-h1{{font-size:1.55rem;margin:32px 0 12px}}
    .blog-h2{{font-size:1.18rem;margin:36px 0 12px;padding-left:14px;border-left:3px solid var(--red)}}
    .blog-h3{{font-size:1.02rem;margin:24px 0 10px}}
    .blog-p{{margin:0 0 18px}}
    .post-title{{font-family:'Syne',sans-serif;font-weight:800;font-size:clamp(1.5rem,4vw,2.1rem);margin-bottom:12px}}
    .post-meta{{font-size:.79rem;color:var(--muted);margin-bottom:20px}}
    .post-tags{{display:flex;gap:7px;margin-bottom:12px}}
    .post-tag{{font-size:.65rem;font-weight:600;padding:3px 10px;border-radius:11px;background:var(--red-bg);color:var(--red)}}
  </style>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
  <script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_ID}');
  </script>
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
  <a href="/blog" class="post-back" style="display:inline-flex;gap:6px;font-size:.82rem;color:var(--muted);margin-bottom:20px;text-decoration:none">← Back to all posts</a>
  <div class="post-header">
    <div class="post-tags">{tags_html}</div>
    <h1 class="post-title">{escape_html(title)}</h1>
    <div class="post-meta"><span>{author}</span> · <span>{date}</span></div>
  </div>
  <article class="blog-body">
    {body_html}
  </article>
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


def update_sitemap():
    """Add blog HTML URLs to sitemap.xml."""
    if not SITEMAP_PATH.exists():
        return
    
    try:
        tree = ET.parse(SITEMAP_PATH)
        root = tree.getroot()
        
        ns = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        ET.register_namespace('', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        existing_blog_urls = set()
        for url_elem in root.findall('sitemap:url', ns):
            loc = url_elem.find('sitemap:loc', ns)
            if loc is not None and '/blog/' in loc.text:
                existing_blog_urls.add(loc.text)
        
        blog_files = sorted(BLOG_HTML_DIR.glob('*.html'))
        today = datetime.now().strftime('%Y-%m-%d')
        
        added = 0
        for blog_file in blog_files:
            slug = blog_file.stem
            blog_url = f'{SITE_DOMAIN}/blog/{slug}.html'
            
            if blog_url not in existing_blog_urls:
                url_elem = ET.Element('url')
                loc = ET.SubElement(url_elem, 'loc')
                loc.text = blog_url
                lastmod = ET.SubElement(url_elem, 'lastmod')
                lastmod.text = today
                changefreq = ET.SubElement(url_elem, 'changefreq')
                changefreq.text = 'weekly'
                priority = ET.SubElement(url_elem, 'priority')
                priority.text = '0.7'
                root.append(url_elem)
                added += 1
        
        if added > 0:
            tree.write(SITEMAP_PATH, encoding='utf-8', xml_declaration=True)
            print(f'Updated sitemap.xml. Added {added} blog URL(s).')
    
    except Exception as e:
        print(f'Warning: could not update sitemap: {e}')


def main():
    BLOG_HTML_DIR.mkdir(exist_ok=True)
    
    created = 0
    updated = 0
    
    for filepath in sorted(BLOGS_DIR.glob('*.json')):
        slug = filepath.stem
        if slug == 'index':
            continue
        
        try:
            with open(filepath, encoding='utf-8') as f:
                post = json.load(f)
        except Exception as e:
            print(f'Warning: could not read {filepath}: {e}')
            continue
        
        html_path = BLOG_HTML_DIR / f'{slug}.html'
        html_content = render_post_html(slug, post)
        
        try:
            existing = html_path.read_text(encoding='utf-8') if html_path.exists() else None
            if existing != html_content:
                html_path.write_text(html_content, encoding='utf-8')
                if existing:
                    updated += 1
                else:
                    print(f'Created {html_path}')
                    created += 1
        except Exception as e:
            print(f'Warning: could not write {html_path}: {e}')
    
    update_sitemap()
    print(f'Done. Created {created}, updated {updated} blog HTML file(s).')


if __name__ == '__main__':
    main()
