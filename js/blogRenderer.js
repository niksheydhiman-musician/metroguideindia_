/**
 * blogRenderer.js
 * Renders blog content from structured JSON to HTML.
 * Supports: h1, h2, h3, p, table, ul (list), note (callout box)
 *
 * HOW TO FORMAT BLOGS IN JSON:
 *   { "type": "h1",    "text": "Your title" }
 *   { "type": "h2",    "text": "Section heading" }
 *   { "type": "h3",    "text": "Sub-heading" }
 *   { "type": "p",     "text": "Paragraph text. Use **bold** and *italic*." }
 *   { "type": "ul",    "items": ["Point one", "Point two", "Point three"] }
 *   { "type": "note",  "text": "Highlighted callout text" }
 *   { "type": "table", "headers": ["Col1","Col2"], "rows": [["A","B"],["C","D"]] }
 */
const BlogRenderer = (() => {

  // Simple inline markdown: **bold**, *italic*
  function inline(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g,     '<em>$1</em>');
  }

  function renderBlock(block) {
    switch (block.type) {
      case 'h1': return `<h1 class="blog-h1">${inline(block.text)}</h1>`;
      case 'h2': return `<h2 class="blog-h2">${inline(block.text)}</h2>`;
      case 'h3': return `<h3 class="blog-h3">${inline(block.text)}</h3>`;
      case 'p':  return `<p class="blog-p">${inline(block.text)}</p>`;
      case 'note': return `<div class="blog-note">${inline(block.text)}</div>`;
      case 'ul':
        return `<ul class="blog-ul">${(block.items||[]).map(i=>`<li>${inline(i)}</li>`).join('')}</ul>`;
      case 'table':
        const heads = (block.headers||[]).map(h=>`<th>${h}</th>`).join('');
        const rows  = (block.rows||[]).map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('');
        return `<div class="blog-table-wrap"><table class="blog-table"><thead><tr>${heads}</tr></thead><tbody>${rows}</tbody></table></div>`;
      default: return '';
    }
  }

  function render(contentArray) {
    return (contentArray || []).map(renderBlock).join('\n');
  }

  return { render };
})();
