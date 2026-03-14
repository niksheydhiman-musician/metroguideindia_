/**
 * popularRoutes.js — Popular Routes grid component
 *
 * Renders a grouped, crawlable Popular Routes grid.
 * URLs use standard <a> tags with ?from=&to= params so they are
 * indexable by search engines without JavaScript.
 *
 * Usage:
 *   <div id="popular-routes"></div>
 *   <script src="js/popularRoutes.js"></script>
 *   <script>PopularRoutes.render('popular-routes');</script>
 */
const PopularRoutes = (() => {

  // Groups: RRTS, Interchange, Meerut Metro
  const GROUPS = [
    {
      label: 'Namo Bharat RRTS',
      icon: '🚄',
      color: '#C0392B',
      routes: [
        { from: 'sarai_kale_khan',   to: 'modipuram_rrts',      fromName: 'Sarai Kale Khan',  toName: 'Modipuram',       dist: 82.15, time: 58 },
        { from: 'anand_vihar',       to: 'modipuram_rrts',      fromName: 'Anand Vihar',      toName: 'Modipuram',       dist: 73.4,  time: 52 },
        { from: 'new_ashok_nagar',   to: 'modipuram_rrts',      fromName: 'New Ashok Nagar',  toName: 'Modipuram',       dist: 70.5,  time: 50 },
        { from: 'sahibabad',         to: 'modipuram_rrts',      fromName: 'Sahibabad',        toName: 'Modipuram',       dist: 64.1,  time: 46 },
        { from: 'anand_vihar',       to: 'meerut_south_rrts',   fromName: 'Anand Vihar',      toName: 'Meerut South',    dist: 44.3,  time: 38 },
        { from: 'ghaziabad',         to: 'shatabdi_nagar_rrts', fromName: 'Ghaziabad',        toName: 'Shatabdi Nagar',  dist: 39.6,  time: 28 },
        { from: 'sarai_kale_khan',   to: 'anand_vihar',         fromName: 'Sarai Kale Khan',  toName: 'Anand Vihar',     dist: 9.5,   time: 8  },
        { from: 'anand_vihar',       to: 'ghaziabad',           fromName: 'Anand Vihar',      toName: 'Ghaziabad',       dist: 10.8,  time: 10 },
        { from: 'ghaziabad',         to: 'murad_nagar',         fromName: 'Ghaziabad',        toName: 'Murad Nagar',     dist: 14.5,  time: 12 },
        { from: 'modi_nagar_north',  to: 'meerut_south_rrts',   fromName: 'Modi Nagar North', toName: 'Meerut South',    dist: 11.2,  time: 11 },
        { from: 'meerut_south_rrts', to: 'modipuram_rrts',      fromName: 'Meerut South',     toName: 'Modipuram',       dist: 18.9,  time: 22 },
      ],
    },
    {
      label: 'RRTS + Meerut Metro (Interchange)',
      icon: '🔄',
      color: '#A0620A',
      routes: [
        { from: 'anand_vihar',     to: 'brahampuri_meerut_metro',          fromName: 'Anand Vihar',     toName: 'Brahampuri',        dist: 49.5, time: 48 },
        { from: 'ghaziabad',       to: 'meerut_north_meerut_metro',        fromName: 'Ghaziabad',       toName: 'Meerut North',      dist: 52.1, time: 50 },
        { from: 'new_ashok_nagar', to: 'bhaisali_bus_adda_meerut_metro',   fromName: 'New Ashok Nagar', toName: 'Bhaisali Bus Adda', dist: 72.4, time: 58 },
        { from: 'sarai_kale_khan', to: 'meerut_central_meerut_metro',      fromName: 'Sarai Kale Khan', toName: 'Meerut Central',    dist: 79.8, time: 62 },
      ],
    },
    {
      label: 'Meerut Metro',
      icon: '🚇',
      color: '#27764A',
      routes: [
        { from: 'meerut_south_meerut_metro',    to: 'modipuram_meerut_metro',         fromName: 'Meerut South',   toName: 'Modipuram',    dist: 18.9, time: 28 },
        { from: 'meerut_south_meerut_metro',    to: 'begumpul_meerut_metro',           fromName: 'Meerut South',   toName: 'Begumpul',     dist: 9.3,  time: 16 },
        { from: 'shatabdi_nagar_meerut_metro',  to: 'meerut_north_meerut_metro',       fromName: 'Shatabdi Nagar', toName: 'Meerut North', dist: 6.2,  time: 13 },
      ],
    },
  ];

  function render(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;

    el.innerHTML = `
      <div class="sec-eye">Popular Routes</div>
      <h2 class="sec-head" style="margin-bottom:6px">Top Delhi–Meerut Journeys</h2>
      <p style="color:var(--muted);font-size:.88rem;margin:0 0 22px">Click any route to see fare, distance and full station list.</p>
      <div class="pr-groups">
        ${GROUPS.map(g => `
          <div class="pr-group">
            <div class="pr-group-header" style="--gc:${g.color}">
              <span class="pr-group-icon">${g.icon}</span>
              <span class="pr-group-label">${g.label}</span>
            </div>
            <div class="pr-grid">
              ${g.routes.map(r => {
                const href = `/route?from=${encodeURIComponent(r.from)}&to=${encodeURIComponent(r.to)}`;
                return `<a href="${href}" class="pr-card" style="--gc:${g.color}">
                  <div class="pr-card-route">
                    <span class="pr-card-from">${r.fromName}</span>
                    <span class="pr-card-arrow">→</span>
                    <span class="pr-card-to">${r.toName}</span>
                  </div>
                  <div class="pr-card-meta">
                    <span>${r.dist} km</span>
                    <span>~${r.time} min</span>
                  </div>
                </a>`;
              }).join('')}
            </div>
          </div>
        `).join('')}
      </div>`;
  }

  return { render };
})();
