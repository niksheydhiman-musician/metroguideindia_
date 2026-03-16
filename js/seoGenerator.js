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
  function apply(from,to,dist,fare,time,system,canonicalUrl){
    const sys = system || 'RRTS';
    const title=`${from} to ${to} ${sys} Fare ₹${fare}, Distance ${dist} km | MetroGuideIndia`;
    const desc=`${from} to ${to} via Namo Bharat ${sys}: ${dist} km, ~${time} min travel time, fare ₹${fare}. Step-by-step station list, interchange guide and latest ticket prices.`;
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

  function seoBlock(from,to,names,dist,fare,time){
    return `<div class="seo-block">
      <p>Travelling from <strong>${from}</strong> to <strong>${to}</strong>?
      This route covers <strong>${dist} km</strong> across <strong>${names.length} stations</strong>,
      with an estimated travel time of <strong>~${time} minutes</strong>
      and a standard fare of <strong>₹${fare}</strong>.</p>
      <p>Namo Bharat RRTS and Meerut Metro are operated by NCRTC.
      The RRTS runs at up to 180 km/h between Delhi and Meerut,
      while the Meerut Metro provides affordable city-level connectivity within Meerut.</p>
    </div>`;
  }

  return { slugify, routeSlug, apply, seoBlock };
})();
