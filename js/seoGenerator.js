const SEOGenerator = (() => {
  const slugify = s => s.toLowerCase().trim().replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'');
  const routeSlug = (a,b) => `${slugify(a)}-to-${slugify(b)}`;

  function setMeta(k,v,isProp=false){
    const a=isProp?'property':'name';
    let t=document.querySelector(`meta[${a}="${k}"]`);
    if(!t){t=document.createElement('meta');t.setAttribute(a,k);document.head.appendChild(t);}
    t.setAttribute('content',v);
  }

  function apply(from,to,dist,fare,time){
    const title=`${from} to ${to} — RRTS Route, ₹${fare} Fare | MetroGuideIndia`;
    const desc=`${from} to ${to}: ${dist} km, ~${time} min, est. ₹${fare}. Complete station list, interchange guide for Namo Bharat RRTS & Meerut Metro.`;
    document.title=title;
    setMeta('description',desc);setMeta('og:title',title,true);setMeta('og:description',desc,true);
    setMeta('twitter:title',title);setMeta('twitter:description',desc);
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
