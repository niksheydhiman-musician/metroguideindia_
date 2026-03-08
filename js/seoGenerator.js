/**
 * seoGenerator.js
 * Generates dynamic SEO meta tags and route page content.
 */
const SEOGenerator = (() => {

  function slugify(str) {
    return str.toLowerCase().trim().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  }

  function routeSlug(from, to) {
    return `${slugify(from)}-to-${slugify(to)}`;
  }

  function setMeta(nameOrProp, content, isProp = false) {
    const attr = isProp ? 'property' : 'name';
    let tag = document.querySelector(`meta[${attr}="${nameOrProp}"]`);
    if (!tag) { tag = document.createElement('meta'); tag.setAttribute(attr, nameOrProp); document.head.appendChild(tag); }
    tag.setAttribute('content', content);
  }

  function applyRouteSEO(fromName, toName, distance, fare, time) {
    const title = `${fromName} to ${toName} — RRTS & Metro Route, Fare ₹${fare} | MetroGuideIndia`;
    const desc  = `${fromName} to ${toName} route: ${distance} km, ~${time} min, est. fare ₹${fare}. Station list, interchange guide and travel tips for Namo Bharat RRTS & Meerut Metro.`;
    document.title = title;
    setMeta('description', desc);
    setMeta('og:title',       title, true);
    setMeta('og:description', desc,  true);
    setMeta('twitter:title',       title);
    setMeta('twitter:description', desc);
  }

  function routeSEOBlock(fromName, toName, stationNames, distance, fare, time) {
    return `
      <div class="seo-block">
        <p>Travelling from <strong>${fromName}</strong> to <strong>${toName}</strong>?
        This route covers <strong>${distance} km</strong> across <strong>${stationNames.length} stations</strong>
        on the Namo Bharat RRTS and/or Meerut Metro network, with an estimated travel time of
        <strong>~${time} minutes</strong> and fare of approximately <strong>₹${fare}</strong>.</p>
        <p>Both services are operated by NCRTC. The Namo Bharat (Namo Bharat) RRTS connects Delhi to Meerut
        at speeds up to 180 km/h, while the Meerut Metro provides city-level connectivity within Meerut.</p>
      </div>`;
  }

  return { slugify, routeSlug, applyRouteSEO, routeSEOBlock };
})();
