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

  var SITE_DOMAIN = 'https://metroguideindia.com';
  var INDEX_URL   = '/data/blogs/index.json';
  var BASE_URL    = '/data/blogs/';
  var FAQ_SCHEMA_SCRIPT_ID = 'post-faq-schema';
  var FAQ_HEADING_PATTERN = /\b(frequently asked questions|faqs?)\b/i;
  var TOURIST_MAP_HEADING_PATTERN = /\bcomplete delhi metro tourist map\b/i;
  var FAQ_SCHEMA_OVERRIDES = {
    'delhi-metro-fare-calculator-how-fares-are-calculated-by-distance-in-2026': [
      {
        name: 'What is the minimum Delhi Metro fare in 2026?',
        text: 'The minimum fare is ₹11 for journeys up to 2 km. This is the base fare for the shortest distance on all Delhi Metro lines.'
      },
      {
        name: 'What is the maximum Delhi Metro fare in 2026?',
        text: 'The maximum fare is ₹64 for journeys beyond 32 km. This applies to the longest commutes on the Delhi Metro network.'
      },
      {
        name: 'Is Delhi Metro fare the same on all days?',
        text: 'No. Sundays and national holidays have discounted fares that can save you ₹10–₹11 per journey compared to weekday rates. Weekday fares range from ₹11–₹64, while Sunday fares range from ₹11–₹54.'
      },
      {
        name: 'How much discount do I get with a Smart Card?',
        text: 'Smart Card users get a 10% discount on all fare slabs. For example, a ₹21 token fare becomes ₹19 with a Smart Card, and a ₹64 fare becomes ₹58.'
      },
      {
        name: 'When was the last Delhi Metro fare hike?',
        text: 'The last fare hike was on August 25, 2025, after an 8-year gap since 2017. The increase was minimal, ranging from ₹1 to ₹5 across various distance slabs.'
      },
      {
        name: 'How is Delhi Metro fare calculated?',
        text: 'Fares are calculated using a distance-based slab system where you pay a fixed rate for your distance range, not per kilometre. The system has 6 slabs: 0–2 km, 2–5 km, 5–12 km, 12–21 km, 21–32 km, and more than 32 km.'
      },
      {
        name: 'Can I use the same ticket for multiple journeys?',
        text: 'No. Token tickets (single-journey tickets) are valid for only one journey. For multiple journeys, you should use a Smart Card which can be recharged and used repeatedly.'
      },
      {
        name: 'What happens if I exceed the maximum travel time?',
        text: 'If you exceed the time limit for your distance slab (65–240 minutes depending on distance), you may need to pay additional fare at the exit station. Time starts from entry tap to exit tap.'
      },
      {
        name: 'Are there any free travels on Delhi Metro?',
        text: 'Children below 5 years travel free on Delhi Metro. No other free travel concessions are available for general passengers.'
      },
      {
        name: 'How do I find the distance between two metro stations?',
        text: 'Use the official Delhi Metro website fare calculator at delhimetrorail.com/fare, Google Maps, or apps like Delhi Metro Rail Info to find the exact distance between any two stations.'
      }
    ]
  };

  /* ── helpers ─────────────────────────────────────────────────────────── */

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('Fetch failed: ' + url + ' (' + r.status + ')');
      return r.json();
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /** Format a YYYY-MM-DD date string to "D Month YYYY". */
  function formatDate(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr + 'T00:00:00');
    if (isNaN(d)) return dateStr;
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function normalizeBlogPath(url, slug) {
    var fallback = '/blog/' + encodeURIComponent(slug);
    if (!url) return fallback;

    var normalized = String(url).trim();
    if (!normalized) return fallback;

    var querySlug = normalized.match(/^\/post\.html\?id=([^&#]+)/i);
    if (querySlug) return '/blog/' + decodeURIComponent(querySlug[1]);

    if (/^https?:\/\//i.test(normalized)) {
      try {
        var asUrl = new URL(normalized);
        normalized = asUrl.pathname + asUrl.search + asUrl.hash;
      } catch (e) {
        return fallback;
      }
    }

    if (!normalized.startsWith('/')) normalized = '/' + normalized;
    normalized = normalized.replace(/\/index\.html$/i, '/');
    normalized = normalized.replace(/\.html$/i, '');
    normalized = normalized.replace(/\/+$/, '');
    return normalized || fallback;
  }

  function getCurrentSlug() {
    var params = new URLSearchParams(window.location.search);
    var qsSlug = params.get('id');
    if (qsSlug) return qsSlug;

    var path = window.location.pathname || '';
    var m = path.match(/^\/blog\/([^/?#]+?)(?:\.html)?\/?$/i);
    if (m && m[1]) return decodeURIComponent(m[1]);
    return '';
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
        /* Images */
        .replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g, function (_, altText, src, title) {
          var safeAlt = escapeHtml(altText || '');
          var safeSrc = String(src || '').replace(/"/g, '&quot;');
          var safeTitle = title ? ' title="' + escapeHtml(title) + '"' : '';
          return '<img class="blog-inline-image" src="' + safeSrc + '" alt="' + safeAlt + '"' + safeTitle + ' loading="lazy" decoding="async">';
        })
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

    function isUnorderedListLine(line) {
      return /^\s*[-*+]\s+/.test(line);
    }

    function isOrderedListLine(line) {
      return /^\s*\d+\.\s+/.test(line);
    }

    function parseTableCells(row) {
      var cols = row.split('|');
      if (cols[0].trim() === '') cols.shift();
      if (cols[cols.length - 1].trim() === '') cols.pop();
      return cols.map(function (cell) { return cell.trim(); });
    }

    function isTableRowLine(line) {
      var trimmedLine = line.trim();
      if (!trimmedLine || isUnorderedListLine(trimmedLine) || isOrderedListLine(trimmedLine)) return false;
      var pipeCount = (trimmedLine.match(/\|/g) || []).length;
      return pipeCount >= 2;
    }

    function isTableSeparatorLine(line) {
      var trimmedLine = line.trim();
      /*
       * Accept both separator styles:
       * 1) ---|---
       * 2) | --- | --- |
       */
      return /^:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+$/.test(trimmedLine) || /^\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?$/.test(trimmedLine);
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
      if (isUnorderedListLine(line)) {
        var items = [];
        while (i < lines.length && isUnorderedListLine(lines[i])) {
          items.push('<li>' + inlineFormat(lines[i].replace(/^\s*[-*+]\s+/, '')) + '</li>');
          i++;
        }
        html.push('<ul class="blog-ul">' + items.join('') + '</ul>');
        continue;
      }

      /* Ordered list */
      if (isOrderedListLine(line)) {
        var orderedItems = [];
        while (i < lines.length && isOrderedListLine(lines[i])) {
          orderedItems.push('<li>' + inlineFormat(lines[i].replace(/^\s*\d+\.\s+/, '')) + '</li>');
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

      /* Table (GFM + relaxed variant without mandatory separator row) */
      if (
        i + 1 < lines.length &&
        isTableRowLine(line) &&
        isTableRowLine(lines[i + 1]) &&
        /* First row may be pipe-led, or second row may be a separator after "a | b" headers. */
        (line.trim().startsWith('|') || isTableSeparatorLine(lines[i + 1]))
      ) {
        var trows = [];
        var thead = parseTableCells(line);

        i += 1;
        if (i < lines.length && isTableSeparatorLine(lines[i])) {
          i += 1; /* optional markdown separator row */
        }

        while (i < lines.length && isTableRowLine(lines[i])) {
          trows.push(parseTableCells(lines[i]));
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
             !isUnorderedListLine(lines[i]) &&
             !isOrderedListLine(lines[i]) &&
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

  function parseTouristMapStops(rawText) {
    if (!rawText) return { intro: '', stops: [] };

    var intro = '';
    var stops = [];
    rawText.replace(/\r/g, '').split('\n').forEach(function (line) {
      var trimmed = line.trim();
      if (!trimmed || trimmed === '│' || trimmed === '▼') return;

      trimmed = trimmed.replace(/^text(?=[A-Z])/, '');

      var stopMatch = trimmed.match(/^(.+?)\s*\(([^)]+)\)\s*(?:—\s*(.+))?$/);
      if (stopMatch) {
        stops.push({
          station: stopMatch[1].trim(),
          lines: stopMatch[2].split(/\s*\+\s*/).map(function (lineName) {
            return lineName.trim();
          }).filter(Boolean),
          highlight: (stopMatch[3] || '').trim()
        });
        return;
      }

      if (!stops.length && !intro) {
        intro = trimmed;
      }
    });

    return { intro: intro, stops: stops };
  }

  function getMetroLineTheme(lineName) {
    var key = String(lineName || '').toLowerCase();
    if (key.indexOf('yellow') !== -1) return 'yellow';
    if (key.indexOf('blue') !== -1) return 'blue';
    if (key.indexOf('violet') !== -1) return 'violet';
    if (key.indexOf('magenta') !== -1) return 'magenta';
    if (key.indexOf('red') !== -1) return 'red';
    if (key.indexOf('green') !== -1) return 'green';
    if (key.indexOf('pink') !== -1) return 'pink';
    if (key.indexOf('grey') !== -1 || key.indexOf('gray') !== -1) return 'grey';
    if (key.indexOf('airport') !== -1 || key.indexOf('orange') !== -1) return 'orange';
    if (key.indexOf('purple') !== -1) return 'purple';
    return 'default';
  }

  function renderMetroLineChips(lines) {
    return (lines || []).map(function (lineName) {
      return '<span class="tourist-map-line tourist-map-line--' + getMetroLineTheme(lineName) + '">' + escapeHtml(lineName) + '</span>';
    }).join('');
  }

  function buildTouristMapWidget(parsedMap, rawText) {
    if (!parsedMap || !parsedMap.stops || !parsedMap.stops.length) return null;

    var wrapper = document.createElement('section');
    wrapper.className = 'tourist-map-widget';

    var introHtml = parsedMap.intro
      ? '<div class="tourist-map-intro">Start from <strong>' + escapeHtml(parsedMap.intro) + '</strong> and tap each stop for the nearest highlight.</div>'
      : '<div class="tourist-map-intro">Tap a stop to quickly scan the best nearby landmark and line interchange.</div>';

    var listHtml = parsedMap.stops.map(function (stop, index) {
      return (
        '<button class="tourist-map-stop' + (index === 0 ? ' is-active' : '') + '" type="button" data-stop-index="' + index + '" aria-pressed="' + (index === 0 ? 'true' : 'false') + '">' +
          '<span class="tourist-map-stop-index">' + String(index + 1).padStart(2, '0') + '</span>' +
          '<span class="tourist-map-stop-copy">' +
            '<span class="tourist-map-stop-name">' + escapeHtml(stop.station) + '</span>' +
            '<span class="tourist-map-stop-meta">' + escapeHtml(stop.lines.join(' • ')) + '</span>' +
          '</span>' +
        '</button>'
      );
    }).join('');

    wrapper.innerHTML =
      '<div class="tourist-map-head">' +
        '<div class="tourist-map-kicker">Delhi Metro tourist trail</div>' +
        introHtml +
      '</div>' +
      '<div class="tourist-map-layout">' +
        '<div class="tourist-map-list" role="tablist" aria-label="Delhi Metro tourist map stops">' + listHtml + '</div>' +
        '<div class="tourist-map-detail" id="tourist-map-detail-panel"></div>' +
      '</div>' +
      '<details class="tourist-map-text">' +
        '<summary>View text version</summary>' +
        '<pre>' + escapeHtml(rawText) + '</pre>' +
      '</details>';

    var detailEl = wrapper.querySelector('.tourist-map-detail');
    var stopButtons = Array.prototype.slice.call(wrapper.querySelectorAll('.tourist-map-stop'));

    function renderStopDetail(index) {
      var stop = parsedMap.stops[index];
      if (!stop) return;

      stopButtons.forEach(function (button, buttonIndex) {
        var isActive = buttonIndex === index;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-pressed', String(isActive));
      });

      detailEl.innerHTML =
        '<div class="tourist-map-detail-card">' +
          '<div class="tourist-map-detail-label">Stop ' + (index + 1) + ' of ' + parsedMap.stops.length + '</div>' +
          '<h3 class="tourist-map-detail-title">' + escapeHtml(stop.station) + '</h3>' +
          '<div class="tourist-map-detail-lines">' + renderMetroLineChips(stop.lines) + '</div>' +
          '<p class="tourist-map-detail-copy">' + escapeHtml(stop.highlight || 'Use this stop as a transfer point on your Delhi sightseeing route.') + '</p>' +
        '</div>';
    }

    stopButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        renderStopDetail(Number(button.getAttribute('data-stop-index')) || 0);
      });
    });

    renderStopDetail(0);
    return wrapper;
  }

  function enhanceTouristMap(articleEl) {
    if (!articleEl) return;

    Array.prototype.slice.call(articleEl.querySelectorAll('h2.blog-h2, h2')).forEach(function (heading) {
      if (!TOURIST_MAP_HEADING_PATTERN.test((heading.textContent || '').trim())) return;

      var node = heading.nextElementSibling;
      while (node && !node.matches('h2.blog-h2, h2')) {
        if (node.matches('pre')) {
          var parsedMap = parseTouristMapStops(node.textContent || '');
          var widget = buildTouristMapWidget(parsedMap, node.textContent || '');
          if (widget) node.replaceWith(widget);
          return;
        }
        node = node.nextElementSibling;
      }
    });
  }

  function slugify(text) {
    return String(text || '')
      .toLowerCase()
      .replace(/&amp;/g, ' and ')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .replace(/-{2,}/g, '-');
  }

  function stripHtmlToText(html) {
    var temp = document.createElement('div');
    temp.innerHTML = html || '';
    return (temp.textContent || temp.innerText || '').replace(/\s+/g, ' ').trim();
  }

  function normalizeFaqQuestion(text) {
    return String(text || '')
      .replace(/^\s*(q[:.)\-\s]+)/i, '')
      .replace(/^\s*\d+[\).\-\s]+/, '')
      .trim();
  }

  function looksLikeFaqQuestion(text) {
    var normalized = normalizeFaqQuestion(text);
    if (!normalized) return false;
    return /\?\s*$/.test(normalized);
  }

  function buildFaqFromPlainNodes(nodes) {
    var items = [];
    var question = '';
    var answerNodes = [];

    function pushCurrent() {
      if (!question || !answerNodes.length) return;
      var answerHtml = answerNodes.map(function (n) { return n.outerHTML; }).join('');
      var answerText = stripHtmlToText(answerHtml);
      if (!answerText) return;
      items.push({
        question: question,
        answerNodes: answerNodes.map(function (n) { return n.cloneNode(true); }),
        answerText: answerText
      });
    }

    nodes.forEach(function (node) {
      var nodeText = stripHtmlToText(node.outerHTML || '');
      if (!nodeText) return;

      if (looksLikeFaqQuestion(nodeText)) {
        pushCurrent();
        question = normalizeFaqQuestion(nodeText);
        answerNodes = [];
        return;
      }

      if (question) {
        answerNodes.push(node.cloneNode(true));
      }
    });

    pushCurrent();
    return items;
  }

  function buildFaqFromArticle(articleEl) {
    if (!articleEl) return [];
    var h2s = Array.prototype.slice.call(articleEl.querySelectorAll('h2.blog-h2, h2'));
    var faqHeading = h2s.find(function (h) { return FAQ_HEADING_PATTERN.test((h.textContent || '').trim()); });
    if (!faqHeading) return [];

    var items = [];
    var question = '';
    var answerNodes = [];
    var node = faqHeading.nextElementSibling;
    var faqNodes = [];

    function pushCurrent() {
      if (!question || !answerNodes.length) return;
      var answerHtml = answerNodes.map(function (n) { return n.outerHTML; }).join('');
      var answerText = stripHtmlToText(answerHtml);
      if (!answerText) return;
      items.push({
        question: question,
        answerNodes: answerNodes.map(function (n) { return n.cloneNode(true); }),
        answerText: answerText
      });
    }

    while (node) {
      if (node.matches('h2.blog-h2, h2')) break;
      faqNodes.push(node);

      if (node.matches('h3.blog-h3, h3')) {
        pushCurrent();
        question = (node.textContent || '').replace(/^\s*\d+[\).\-\s]+/, '').trim();
        answerNodes = [];
      } else if (question) {
        answerNodes.push(node.cloneNode(true));
      }

      node = node.nextElementSibling;
    }
    pushCurrent();

    if (!items.length) {
      items = buildFaqFromPlainNodes(faqNodes);
    }

    if (!items.length) return [];

    faqNodes.forEach(function (n) { n.remove(); });
    var accordion = document.createElement('div');
    accordion.className = 'faq-list';
    items.forEach(function (faq, idx) {
      var item = document.createElement('div');
      item.className = 'faq-item' + (idx === 0 ? ' open' : '');
      var btn = document.createElement('button');
      btn.className = 'faq-q';
      btn.type = 'button';
      btn.setAttribute('aria-expanded', idx === 0 ? 'true' : 'false');
      btn.textContent = faq.question;

      var ans = document.createElement('div');
      ans.className = 'faq-a';
      faq.answerNodes.forEach(function (n) { ans.appendChild(n.cloneNode(true)); });

      item.appendChild(btn);
      item.appendChild(ans);
      accordion.appendChild(item);
    });
    faqHeading.insertAdjacentElement('afterend', accordion);
    return items;
  }

  function buildToc(articleEl, tocEl) {
    if (!articleEl || !tocEl) return;
    var used = {};
    var headings = Array.prototype.slice.call(articleEl.querySelectorAll('h2.blog-h2, h2'));
    tocEl.innerHTML = '';
    headings.forEach(function (h, index) {
      var text = (h.textContent || '').trim();
      if (!text) return;
      var base = slugify(text) || ('section-' + (index + 1));
      var nextId = base;
      var c = 2;
      while (used[nextId]) {
        nextId = base + '-' + c;
        c += 1;
      }
      used[nextId] = true;
      h.id = h.id || nextId;
      var li = document.createElement('li');
      var a = document.createElement('a');
      /* Use full path + hash so the link is correct regardless of <base href>.
         The click handler also scrolls smoothly and prevents any navigation. */
      a.href = (window.location.pathname || '') + '#' + h.id;
      a.textContent = text;
      (function (targetId) {
        a.addEventListener('click', function (e) {
          e.preventDefault();
          var target = document.getElementById(targetId);
          if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            window.history.replaceState(null, '', (window.location.pathname || '') + '#' + targetId);
          }
        });
      }(h.id));
      li.appendChild(a);
      tocEl.appendChild(li);
    });

    if (!tocEl.children.length) {
      var emptyLi = document.createElement('li');
      var emptyText = document.createElement('span');
      emptyText.textContent = 'No sections found.';
      emptyLi.appendChild(emptyText);
      tocEl.appendChild(emptyLi);
    }
  }

  function setFaqSchema(slug, faqItems) {
    var old = document.getElementById(FAQ_SCHEMA_SCRIPT_ID);
    if (old) old.remove();

    var override = FAQ_SCHEMA_OVERRIDES[slug];
    var source = Array.isArray(override) && override.length
      ? override
      : (faqItems || []).map(function (faq) {
          return { name: faq.question, text: faq.answerText };
        }).filter(function (faq) { return faq.name && faq.text; });

    if (!source.length) return;

    var schema = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: source.map(function (faq) {
        return {
          '@type': 'Question',
          name: faq.name,
          acceptedAnswer: {
            '@type': 'Answer',
            text: faq.text
          }
        };
      })
    };

    var script = document.createElement('script');
    script.id = FAQ_SCHEMA_SCRIPT_ID;
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(schema);
    document.head.appendChild(script);
  }

  function bindFaqAccordion(root) {
    if (!root) return;
    root.querySelectorAll('.faq-q').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item = btn.closest('.faq-item');
        if (!item) return;
        var isOpen = item.classList.contains('open');
        item.classList.toggle('open', !isOpen);
        btn.setAttribute('aria-expanded', String(!isOpen));
      });
    });
  }

  /* ── card builders ───────────────────────────────────────────────────── */

  /**
   * Build a homepage-style news-card element.
   * @param {Object} post  - { title, date, image, description, url }
   * @param {string} slug
   */
  function buildNewsCard(post, slug) {
    var href = normalizeBlogPath(post.url, slug);
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
    var href = normalizeBlogPath(post.url, slug);
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

  /**
   * Load post by slug, with fallback for year-suffixed aliases.
   * Example: my-post-title-2026 -> my-post-title (only if first fetch fails).
   */
  function loadPostWithAliasFallback(slug) {
    return loadPost(slug).catch(function (err) {
      if (/-\d{4}$/.test(slug)) {
        var baseSlug = slug.replace(/-\d{4}$/, '');
        return loadPost(baseSlug);
      }
      throw err;
    });
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
   * Reads `?id=<slug>` or the `/blog/<slug>` path from the current URL.
   * Also updates document.title and meta[name="description"] for SEO.
   *
   * @param {string} containerId  - id of the container element
   * @param {string} [dataSlug]   - optional explicit data slug (overrides URL detection)
   */
  BlogBridge.loadPost = function (containerId, dataSlug) {
    var container = getContainer(containerId);
    if (!container) return;

    var slug = dataSlug || getCurrentSlug();
    if (!slug) {
      /* No id param — redirect to blog listing */
      window.location.replace('/blog');
      return;
    }

    container.innerHTML = '<p style="color:var(--muted,#6b7280);text-align:center;padding:40px 0">Loading…</p>';

    loadPostWithAliasFallback(slug).then(function (post) {
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
      var canonHref = normalizeBlogPath(post.url, slug);
      if (canonical) {
        canonical.href = SITE_DOMAIN + canonHref;
      }

      if (window.history && typeof window.history.replaceState === 'function') {
        var nextUrl = canonHref + (window.location.hash || '');
        var currentUrl = (window.location.pathname || '') + (window.location.search || '') + (window.location.hash || '');
        if (nextUrl && currentUrl !== nextUrl) {
          window.history.replaceState({ slug: slug }, '', nextUrl);
        }
      }

      /* ── render post ── */
      var tags = Array.isArray(post.tags) ? post.tags : [];
      var tagsHtml = tags.map(function (t) {
        return '<span class="post-tag">' + t + '</span>';
      }).join('');

      /* Estimate reading time (average 200 wpm) */
      var wordCount = (post.body || '').trim().split(/\s+/).length;
      var readMins = Math.max(1, Math.round(wordCount / 200));

      var imageHtml = post.image
        ? '<img src="' + post.image + '" alt="' + post.title.replace(/"/g, '&quot;') + '" style="width:100%;border-radius:12px;margin-bottom:24px;display:block;aspect-ratio:16/9;object-fit:cover">'
        : '';

      container.innerHTML =
        '<div class="post-header">' +
          (tagsHtml ? '<div class="post-tags">' + tagsHtml + '</div>' : '') +
          '<h1 class="post-title">' + post.title + '</h1>' +
          '<div class="post-meta">' +
            '<span>📅 ' + formatDate(post.date) + '</span>' +
            '<span>⏱️ ' + readMins + ' min read</span>' +
          '</div>' +
        '</div>' +
        '<hr class="post-divider"/>' +
        imageHtml +
        '<details class="mobile-toc-block" id="mobile-toc-details">' +
          '<summary>' +
            '<span>📋 Contents</span>' +
            '<span class="mobile-toc-count" id="mobile-toc-count"></span>' +
          '</summary>' +
          '<ul class="toc-list mobile-toc-list" id="mobile-toc"></ul>' +
        '</details>' +
        '<div class="post-grid">' +
          '<article class="blog-body" id="blog-article">' + renderBody(post.body) + '</article>' +
          '<aside class="sidebar-card">' +
            '<div class="sidebar-section-title">📋 Contents</div>' +
            '<ul class="toc-list" id="post-toc"></ul>' +
            '<div class="sidebar-section-title">🔗 Related Guides</div>' +
            '<div class="sidebar-list" id="post-related-guides"></div>' +
          '</aside>' +
        '</div>' +
        '<div class="mobile-related-block" id="mobile-related-block">' +
          '<div class="mobile-related-title">🔗 Related Guides</div>' +
          '<div class="sidebar-list" id="mobile-related-guides"></div>' +
        '</div>';

      var articleEl = container.querySelector('#blog-article');
      var tocEl = container.querySelector('#post-toc');
      var mobileTocEl = container.querySelector('#mobile-toc');
      var mobileTocCount = container.querySelector('#mobile-toc-count');
      var relatedEl = container.querySelector('#post-related-guides');
      var mobileRelatedEl = container.querySelector('#mobile-related-guides');
      var faqItems = buildFaqFromArticle(articleEl);
      enhanceTouristMap(articleEl);
      buildToc(articleEl, tocEl);
      /* Mirror TOC into the mobile collapsible block */
      if (mobileTocEl && tocEl) {
        mobileTocEl.innerHTML = tocEl.innerHTML;
        /* Re-attach click handlers since innerHTML copy doesn't preserve listeners */
        Array.prototype.slice.call(mobileTocEl.querySelectorAll('a[href]')).forEach(function (a) {
          var hash = (a.getAttribute('href') || '').replace(/^[^#]*#/, '');
          if (!hash) return;
          a.addEventListener('click', function (e) {
            e.preventDefault();
            var target = document.getElementById(hash);
            if (target) {
              target.scrollIntoView({ behavior: 'smooth', block: 'start' });
              window.history.replaceState(null, '', (window.location.pathname || '') + '#' + hash);
            }
          });
        });
        if (mobileTocCount) {
          var count = tocEl.children.length;
          mobileTocCount.textContent = count ? count + ' section' + (count !== 1 ? 's' : '') : '';
        }
      }
      bindFaqAccordion(container);
      setFaqSchema(slug, faqItems);

      loadSlugs().then(function (slugs) {
        var candidates = slugs.filter(function (s) { return s !== slug; }).slice(0, 8);
        return Promise.all(candidates.map(function (s) {
          return loadPost(s).then(function (p) { return { slug: s, post: p }; }).catch(function () { return null; });
        }));
      }).then(function (related) {
        if (!relatedEl && !mobileRelatedEl) return;
        var entries = related.filter(Boolean).slice(0, 4);
        if (relatedEl) relatedEl.innerHTML = '';
        if (mobileRelatedEl) mobileRelatedEl.innerHTML = '';
        if (!entries.length) {
          var emptyMsg = '<p class="sidebar-empty">No related guides available.</p>';
          if (relatedEl) relatedEl.innerHTML = emptyMsg;
          if (mobileRelatedEl) mobileRelatedEl.innerHTML = emptyMsg;
          return;
        }

        entries.forEach(function (item) {
          var link = document.createElement('a');
          link.className = 'related-guide';
          link.href = normalizeBlogPath(item.post.url, item.slug);

          var titleEl = document.createElement('div');
          titleEl.className = 'related-guide-title';
          titleEl.textContent = item.post.title || item.slug;

          var dateEl = document.createElement('div');
          dateEl.className = 'related-guide-date';
          dateEl.textContent = formatDate(item.post.date);

          link.appendChild(titleEl);
          link.appendChild(dateEl);
          if (relatedEl) relatedEl.appendChild(link);
          if (mobileRelatedEl) mobileRelatedEl.appendChild(link.cloneNode(true));
        });
      }).catch(function () {
        var errMsg = '<p class="sidebar-empty">Could not load related guides.</p>';
        if (relatedEl) relatedEl.innerHTML = errMsg;
        if (mobileRelatedEl) mobileRelatedEl.innerHTML = errMsg;
      });

    }).catch(function (err) {
      console.error('[blogBridge] loadPost failed:', err);
      setFaqSchema(slug, []);
      container.innerHTML =
        '<p style="text-align:center;padding:40px 0">Post not found. ' +
        '<a href="/blog">← Back to Blog</a></p>';
    });
  };

  global.BlogBridge = BlogBridge;

}(typeof window !== 'undefined' ? window : this));
