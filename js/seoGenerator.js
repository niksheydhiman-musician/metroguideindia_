const SEOGenerator = (() => {
  const slugify = s => s.toLowerCase().trim().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'');
  const routeSlug = (a,b) => `${slugify(a)}-to-${slugify(b)}`;

  function setMeta(k,v,isProp=false){
    const a=isProp?'property':'name';
    let t=document.querySelector(`meta[${a}="${k}"]`);
    if(!t){t=document.createElement('meta');t.setAttribute(a,k);document.head.appendChild(t);}
    t.setAttribute('content',v);
  }

  /**
   * apply() — sets all SEO meta tags for a route result page.
   * @param {string} from       Origin station display name
   * @param {string} to         Destination station display name
   * @param {number} dist       Distance in km
   * @param {number} fare       Estimated fare in INR
   * @param {number} time       Estimated travel time in minutes
   * @param {string} [system]   Route system label: 'RRTS', 'Meerut Metro', or 'RRTS + Metro'
   * @param {string} [canonicalUrl] Full canonical URL for this route page
   */
  function apply(from,to,dist,fare,time,system,canonicalUrl,options){
    const opts = options || {};
    const pathname = String(window.location?.pathname || '').toLowerCase();
    const sys = String(system || '');
    const isRRTSBySystem = /rrts|meerut/i.test(sys);
    const isRRTSByPath = pathname.indexOf('/namo-bharat/') === 0 || pathname.indexOf('/meerut-metro/') === 0;
    const isRRTS = opts.isRRTS === true || isRRTSBySystem || isRRTSByPath;
    const title = isRRTS
      ? `${from} to ${to}: Distance, Fare & RRTS Timings | MetroGuideIndia`
      : `${from} to ${to} Metro Route: Fare, Time & Stations | MetroGuideIndia`;
    const desc = isRRTS
      ? `${from} to ${to} RRTS route with distance ${dist} km, fare ₹${fare}, and estimated travel time ~${time} min. Includes station-by-station route and interchange details.`
      : `${from} to ${to} Metro Route with fare ₹${fare}, travel time ~${time} min, and distance ${dist} km. Includes station-by-station route and interchange details.`;
    document.title=title;
    setMeta('description',desc);
    setMeta('og:title',title,true);
    setMeta('og:description',desc,true);
    setMeta('og:type','website',true);
    if(canonicalUrl) setMeta('og:url',canonicalUrl,true);
    setMeta('twitter:card','summary');
    setMeta('twitter:title',title);
    setMeta('twitter:description',desc);
  }

  function seoBlock(from,to,names,dist,fare,time,options){
    const isRRTS = options && options.isRRTS === true;
    return `<div class="seo-block">
      <p>Travelling from <strong>${from}</strong> to <strong>${to}</strong>?
      This route covers <strong>${dist} km</strong> across <strong>${names.length} stations</strong>,
      with an estimated travel time of <strong>~${time} minutes</strong>
      and a standard fare of <strong>₹${fare}</strong>.</p>
      <p>${isRRTS
        ? 'Namo Bharat RRTS and Meerut Metro are operated by NCRTC. The RRTS runs at up to 180 km/h between Delhi and Meerut, while Meerut Metro provides city-level connectivity within Meerut.'
        : 'Get the latest metro route details including fare, estimated travel time, key interchanges, and station sequence for easier journey planning.'}</p>
    </div>`;
  }

  return { slugify, routeSlug, apply, seoBlock };
})();
