/**
 * blogBridge.js — MetroGuideIndia
 *
 * Fetches blog post data from /data/blogs/ (individual JSON files indexed
 * by /data/blogs/index.json) and renders cards or full post views.
 *
 * Public API:
 *   BlogBridge.loadNewsCards(containerId, limit)   — homepage news-card style
 *   BlogBridge.loadBlogCards(containerId, limit)   — blog-listing card style
 *   BlogBridge.loadPost(containerId)               — full single-post renderer
 */
(function (global) {
  'use strict';

  var SITE_DOMAIN = 'https://metroguideindia.in';
  var INDEX_URL   = '/data/blogs/index.json';
  var BASE_URL    = '/data/blogs/';

  /* ── helpers ─────────────────────────────────────────────────────────── */

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('Fetch failed: ' + url + ' (' + r.status + ')');
      return r.json();
    });
  }

  /** Format a YYYY-MM-DD date string to "D Month YYYY". */
  function formatDate(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr + 'T00:00:00');
    if (isNaN(d)) return dateStr;
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  /** Minimal Markdown → HTML converter (CommonMark subset). */
  function mdToHtml(md) {
    if (!md) return '';

    var lines = md.split('\n');
    var html = [];
    var i = 0;

    function escape(s) {
      return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }

    function inlineFormat(s) {
      return s
        /* Bold+italic */
        .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
        /* Bold */
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/__(.+?)__/g, '<strong>$1</strong>')
        /* Italic */
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/_(.+?)_/g, '<em>$1</em>')
        /* Code */
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        /* Links */
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    }

    while (i < lines.length) {
      var line = lines[i];

      /* Headings */
      var h = line.match(/^(#{1,6})\s+(.*)/);
      if (h) {
        var level = h[1].length;
        html.push('<h' + level + ' class="blog-h' + level + '">' + inlineFormat(h[2]) + '</h' + level + '>');
        i++; continue;
      }

      /* Fenced code block */
      if (/^```/.test(line)) {
        var code = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) {
          code.push(escape(lines[i]));
          i++;
        }
        html.push('<pre><code>' + code.join('\n') + '</code></pre>');
        i++; continue;
      }

      /* Unordered list */
      if (/^[-*+]\s/.test(line)) {
        var items = [];
        while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
          items.push('<li>' + inlineFormat(lines[i].replace(/^[-*+]\s+/, '')) + '</li>');
          i++;
        }
        html.push('<ul class="blog-ul">' + items.join('') + '</ul>');
        continue;
      }

      /* Ordered list */
      if (/^\d+\.\s/.test(line)) {
        var orderedItems = [];
        while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
          orderedItems.push('<li>' + inlineFormat(lines[i].replace(/^\d+\.\s+/, '')) + '</li>');
          i++;
        }
        html.push('<ol class="blog-ol">' + orderedItems.join('') + '</ol>');
        continue;
      }

      /* Horizontal rule */
      if (/^---+$/.test(line.trim()) || /^\*\*\*+$/.test(line.trim())) {
        html.push('<hr>');
        i++; continue;
      }

      /* Blockquote */
      if (/^>\s?/.test(line)) {
        var bq = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          bq.push(inlineFormat(lines[i].replace(/^>\s?/, '')));
          i++;
        }
        html.push('<blockquote class="blog-note">' + bq.join('<br>') + '</blockquote>');
        continue;
      }

      /* Table (GFM) */
      if (/\|/.test(line) && i + 1 < lines.length && /^\|?[\s\-:]+\|/.test(lines[i + 1])) {
        var trows = [];
        var thead = line.split('|').filter(function (c, idx, arr) {
          return idx > 0 && idx < arr.length - 1 || (c.trim() !== '');
        }).map(function (c) { return c.trim(); });

        /* If first char is | strip first empty */
        var rawCols = line.split('|');
        if (rawCols[0].trim() === '') rawCols.shift();
        if (rawCols[rawCols.length - 1].trim() === '') rawCols.pop();
        thead = rawCols.map(function (c) { return c.trim(); });

        i += 2; /* skip header and separator */
        while (i < lines.length && /\|/.test(lines[i])) {
          var rc2 = lines[i].split('|');
          if (rc2[0].trim() === '') rc2.shift();
          if (rc2[rc2.length - 1].trim() === '') rc2.pop();
          trows.push(rc2.map(function (c) { return c.trim(); }));
          i++;
        }
        var thHtml = thead.map(function (c) { return '<th>' + inlineFormat(c) + '</th>'; }).join('');
        var trHtml = trows.map(function (r) {
          return '<tr>' + r.map(function (c) { return '<td>' + inlineFormat(c) + '</td>'; }).join('') + '</tr>';
        }).join('');
        html.push('<div class="blog-table-wrap"><table class="blog-table"><thead><tr>' + thHtml + '</tr></thead><tbody>' + trHtml + '</tbody></table></div>');
        continue;
      }

      /* Empty line = paragraph break */
      if (line.trim() === '') {
        i++; continue;
      }

      /* Paragraph: collect consecutive non-empty, non-special lines */
      var para = [];
      while (i < lines.length && lines[i].trim() !== '' &&
             !/^#{1,6}\s/.test(lines[i]) &&
             !/^[-*+]\s/.test(lines[i]) &&
             !/^\d+\.\s/.test(lines[i]) &&
             !/^```/.test(lines[i]) &&
             !/^>\s?/.test(lines[i]) &&
             !/^---+$/.test(lines[i].trim())) {
        para.push(inlineFormat(lines[i]));
        i++;
      }
      if (para.length) {
        html.push('<p class="blog-p">' + para.join(' ') + '</p>');
      }
    }

    return html.join('\n');
  }

  /** Render the body field: if it looks like HTML pass through, else parse markdown. */
  function renderBody(body) {
    if (!body) return '';
    /* Heuristic: if body starts with an HTML tag, treat as HTML */
    if (/^\s*</.test(body)) return body;
    return mdToHtml(body);
  }

  /* ── card builders ───────────────────────────────────────────────────── */

  /**
   * Build a homepage-style news-card element.
   * @param {Object} post  - { title, date, image, description, url }
   * @param {string} slug
   */
  function buildNewsCard(post, slug) {
    var href = post.url || ('/post.html?id=' + encodeURIComponent(slug));
    var card = document.createElement('a');
    card.href = href;
    card.className = 'news-card';

    var dateEl = document.createElement('div');
    dateEl.className = 'news-date';
    dateEl.textContent = formatDate(post.date);

    var titleEl = document.createElement('h3');
    titleEl.className = 'news-title';
    titleEl.textContent = post.title;

    var summaryEl = document.createElement('p');
    summaryEl.className = 'news-summary';
    summaryEl.textContent = post.description;

    if (post.image) {
      var img = document.createElement('img');
      img.src = post.image;
      img.alt = post.title;
      img.style.cssText = 'width:100%;border-radius:8px;margin-bottom:10px;display:block;aspect-ratio:16/9;object-fit:cover';
      card.appendChild(img);
    }

    card.appendChild(dateEl);
    card.appendChild(titleEl);
    card.appendChild(summaryEl);
    return card;
  }

  /**
   * Build a blog-listing-style blog-card element.
   * @param {Object} post  - { title, date, image, description, tags, url }
   * @param {string} slug
   */
  function buildBlogCard(post, slug) {
    var href = post.url || ('/post.html?id=' + encodeURIComponent(slug));
    var tags = Array.isArray(post.tags) ? post.tags : [];

    var link = document.createElement('a');
    link.href = href;
    link.className = 'blog-card-link';

    var card = document.createElement('div');
    card.className = 'blog-card';

    var meta = document.createElement('div');
    meta.className = 'blog-meta';

    var dateEl = document.createElement('span');
    dateEl.className = 'blog-date';
    dateEl.textContent = formatDate(post.date);
    meta.appendChild(dateEl);

    tags.forEach(function (tag) {
      var t = document.createElement('span');
      t.className = 'blog-tag';
      t.textContent = tag;
      meta.appendChild(t);
    });

    var titleEl = document.createElement('div');
    titleEl.className = 'blog-title';
    titleEl.textContent = post.title;

    var summaryEl = document.createElement('div');
    summaryEl.className = 'blog-summary';
    summaryEl.textContent = post.description;

    var readEl = document.createElement('div');
    readEl.className = 'blog-read';
    readEl.textContent = 'Read more →';

    if (post.image) {
      var img = document.createElement('img');
      img.src = post.image;
      img.alt = post.title;
      img.style.cssText = 'width:100%;border-radius:8px;margin-bottom:12px;display:block;aspect-ratio:16/9;object-fit:cover';
      card.appendChild(img);
    }

    card.appendChild(meta);
    card.appendChild(titleEl);
    card.appendChild(summaryEl);
    card.appendChild(readEl);
    link.appendChild(card);
    return link;
  }

  /* ── loader helpers ──────────────────────────────────────────────────── */

  function getContainer(id) {
    var el = document.getElementById(id);
    if (!el) console.warn('[blogBridge] Container not found: #' + id);
    return el;
  }

  function showError(container, message) {
    container.innerHTML = '<p style="color:var(--muted,#6b7280);padding:16px 0">' + message + '</p>';
  }

  function loadSlugs() {
    return fetchJSON(INDEX_URL).then(function (data) {
      /* index.json may be a bare array (legacy) or {slugs:[...]} (CMS format) */
      return Array.isArray(data) ? data : (data.slugs || []);
    });
  }

  /**
   * Sort an array of { slug, post } items by post.date descending (newest first).
   * Items without a parseable date are pushed to the end.
   */
  function sortNewestFirst(items) {
    var withTime = items.map(function (item) {
      var dateStr = item && item.post && item.post.date;
      var t = dateStr ? new Date(dateStr).getTime() : NaN;
      return { item: item, t: isNaN(t) ? -Infinity : t };
    });
    withTime.sort(function (a, b) { return b.t - a.t; });
    return withTime.map(function (x) { return x.item; });
  }

  function loadPost(slug) {
    return fetchJSON(BASE_URL + slug + '.json');
  }

  /* ── public API ──────────────────────────────────────────────────────── */

  var BlogBridge = {};

  /**
   * Render homepage news-cards into `containerId`.
   * @param {string} containerId  - id of the container element
   * @param {number} [limit=4]    - max number of cards to show
   */
  BlogBridge.loadNewsCards = function (containerId, limit) {
    limit = limit || 4;
    var container = getContainer(containerId);
    if (!container) return;

    loadSlugs().then(function (slugs) {
      var promises = slugs.map(function (slug) {
        return loadPost(slug).then(function (post) {
          return { slug: slug, post: post };
        }).catch(function () { return null; });
      });

      return Promise.all(promises);
    }).then(function (results) {
      var sorted = sortNewestFirst(results.filter(Boolean));
      var toShow = sorted.slice(0, limit);
      container.innerHTML = '';
      toShow.forEach(function (item) {
        container.appendChild(buildNewsCard(item.post, item.slug));
      });
      if (!container.children.length) {
        showError(container, 'No posts found.');
      }
    }).catch(function (err) {
      console.error('[blogBridge] loadNewsCards failed:', err);
      showError(container, 'Could not load latest posts.');
    });
  };

  /**
   * Render blog-listing cards into `containerId`.
   * @param {string} containerId  - id of the container element
   * @param {number} [limit]      - max cards (0 = all)
   */
  BlogBridge.loadBlogCards = function (containerId, limit) {
    limit = limit || 0;
    var container = getContainer(containerId);
    if (!container) return;

    loadSlugs().then(function (slugs) {
      var promises = slugs.map(function (slug) {
        return loadPost(slug).then(function (post) {
          return { slug: slug, post: post };
        }).catch(function () { return null; });
      });
      return Promise.all(promises);
    }).then(function (results) {
      var sorted = sortNewestFirst(results.filter(Boolean));
      var toShow = limit ? sorted.slice(0, limit) : sorted;
      container.innerHTML = '';
      toShow.forEach(function (item) {
        container.appendChild(buildBlogCard(item.post, item.slug));
      });
      if (!container.children.length) {
        showError(container, 'No posts found.');
      }
    }).catch(function (err) {
      console.error('[blogBridge] loadBlogCards failed:', err);
      showError(container, 'Could not load blog posts.');
    });
  };

  /**
   * Render a single full post into `containerId`.
   * Reads `?id=<slug>` from the current URL.
   * Also updates document.title and meta[name="description"] for SEO.
   *
   * @param {string} containerId - id of the container element
   */
  BlogBridge.loadPost = function (containerId) {
    var container = getContainer(containerId);
    if (!container) return;

    var slug = new URLSearchParams(window.location.search).get('id');
    if (!slug) {
      /* No id param — redirect to blog listing */
      window.location.replace('/blog');
      return;
    }

    container.innerHTML = '<p style="color:var(--muted,#6b7280);text-align:center;padding:40px 0">Loading…</p>';

    loadPost(slug).then(function (post) {
      /* ── SEO: update title & meta description ── */
      document.title = post.title + ' | MetroGuideIndia';
      var metaDesc = document.querySelector('meta[name="description"]');
      if (metaDesc) {
        metaDesc.setAttribute('content', post.description || '');
      } else {
        metaDesc = document.createElement('meta');
        metaDesc.name = 'description';
        metaDesc.content = post.description || '';
        document.head.appendChild(metaDesc);
      }

      /* ── canonical URL ── */
      var canonical = document.querySelector('link[rel="canonical"]');
      var canonHref = post.url || ('/post.html?id=' + encodeURIComponent(slug));
      if (canonical) {
        canonical.href = SITE_DOMAIN + canonHref;
      }

      /* ── render post ── */
      var tags = Array.isArray(post.tags) ? post.tags : [];
      var tagsHtml = tags.map(function (t) {
        return '<span class="post-tag">' + t + '</span>';
      }).join('');

      var imageHtml = post.image
        ? '<img src="' + post.image + '" alt="' + post.title.replace(/"/g, '&quot;') + '" style="width:100%;border-radius:12px;margin-bottom:24px;display:block;aspect-ratio:16/9;object-fit:cover">'
        : '';

      container.innerHTML =
        '<div class="post-header">' +
          (tagsHtml ? '<div class="post-tags">' + tagsHtml + '</div>' : '') +
          '<h1 class="post-title">' + post.title + '</h1>' +
          '<div class="post-meta">' +
            '<span>' + formatDate(post.date) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="post-divider"></div>' +
        imageHtml +
        '<div class="blog-body">' + renderBody(post.body) + '</div>';

    }).catch(function (err) {
      console.error('[blogBridge] loadPost failed:', err);
      container.innerHTML =
        '<p style="text-align:center;padding:40px 0">Post not found. ' +
        '<a href="/blog">← Back to Blog</a></p>';
    });
  };

  global.BlogBridge = BlogBridge;

}(typeof window !== 'undefined' ? window : this));
